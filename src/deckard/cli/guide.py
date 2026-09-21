"""Sub-app `guide`: gestión, inspección y exportación de guías."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
import typer

from deckard.core.guides import (
    agregar_ejercicio_a_guia,
    cargar_guia_con_ejercicios,
    guardar_yaml_guia,
    inspeccionar_guia,
    listar_guias,
    remover_ejercicio_de_guia,
    resolver_ruta_guia,
)
from deckard.core.verify import verificar_ejercicio

from deckard.cli._shared import (
    console,
    guide_app,
)
from deckard.cli.compose import compose
from deckard.cli.export import exportar_contenido


@guide_app.command("list")
def guide_list(
    guias_dir: Path = typer.Option(Path("guias"), "--guias", "-g", help="Directorio de guías."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
) -> None:
    """Lista las guías existentes en guias/ con métricas y estado de verificación."""
    guias = listar_guias(guias_dir, dir_banco=banco)
    if not guias:
        console.print(f"[yellow]No se encontraron guías en '{guias_dir}'. Creá una con 'deckard compose' o 'deckard guide new'.[/yellow]")
        return

    tabla = Table(title=f"Catálogo de Guías ({len(guias)} encontradas)")
    tabla.add_column("Archivo", style="cyan")
    tabla.add_column("Nombre de Guía")
    tabla.add_column("Tipo", justify="center")
    tabla.add_column("Ejercicios", justify="right")
    tabla.add_column("Duración", justify="right")
    tabla.add_column("Bloom", style="dim")
    tabla.add_column("Verificados", justify="center")

    for g in guias:
        tipo_str = "[dim]spec[/dim]" if g.es_spec else "[blue]compuesta[/blue]"
        cant_str = "—" if g.es_spec else str(g.cantidad_ejercicios)
        dur_str = f"~{g.duracion_minutos} min"
        bloom_str = ", ".join(f"{k}:{v}" for k, v in g.distribucion_bloom.items()) if g.distribucion_bloom else "—"
        verif_str = "—" if g.es_spec else (f"{g.verificados_count}/{g.cantidad_ejercicios} ✓" if g.verificados_count == g.cantidad_ejercicios else f"[yellow]{g.verificados_count}/{g.cantidad_ejercicios}[/yellow]")
        tabla.add_row(g.archivo.name, g.nombre, tipo_str, cant_str, dur_str, bloom_str, verif_str)

    console.print(tabla)


@guide_app.command("show")
def guide_show(
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo YAML o carpeta de la guía."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
    enunciados: bool = typer.Option(False, "--enunciados", "-e", help="Mostrar enunciados completos."),
    soluciones: bool = typer.Option(False, "--soluciones", "-s", help="Mostrar soluciones modelo."),
    pistas: bool = typer.Option(False, "--pistas", "-p", help="Mostrar pistas progresivas."),
) -> None:
    """Muestra el detalle estructurado de una guía y sus ejercicios."""
    ruta = resolver_ruta_guia(guia_archivo, dir_guias=guias_dir)
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    info = inspeccionar_guia(ruta, dir_banco=banco)
    guia_meta, items = cargar_guia_con_ejercicios(ruta, banco)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("Archivo:", str(ruta))
    grid.add_row("Tipo:", "Especificación (spec)" if info.es_spec else "Guía Compuesta")
    grid.add_row("Carga estimada:", f"~{info.duracion_minutos} minutos ({info.duracion_minutos/60:.1f}h)")
    if info.distribucion_bloom:
        grid.add_row("Distribución Bloom:", ", ".join(f"{k}: {v}" for k, v in info.distribucion_bloom.items()))
    if info.temas:
        grid.add_row("Temas:", ", ".join(info.temas))

    console.print(Panel(grid, title=f"[bold blue]{info.nombre}[/bold blue]", border_style="blue"))

    if not info.es_spec and items:
        tabla = Table(title=f"Ejercicios de la guía ({len(items)})")
        tabla.add_column("#", justify="right")
        tabla.add_column("ID", style="cyan")
        tabla.add_column("Título")
        tabla.add_column("Tema")
        tabla.add_column("Bloom", justify="center")
        tabla.add_column("Min", justify="right")
        tabla.add_column("Verificado", justify="center")

        for i, (dir_ej, ej) in enumerate(items, 1):
            if ej:
                tabla.add_row(
                    str(i), ej.id, ej.titulo, ej.tema,
                    f"B{int(ej.bloom)}", str(ej.minutos_estimados),
                    "[green]✓[/green]" if ej.verificado else "[dim]—[/dim]"
                )
            else:
                tabla.add_row(str(i), "[red](no encontrado)[/red]", "—", "—", "—", "—", "✗")
        console.print(tabla)

        if enunciados or soluciones or pistas:
            for i, (dir_ej, ej) in enumerate(items, 1):
                if not ej:
                    continue
                console.print(f"\n[bold underline]Ejercicio {i}: {ej.titulo}[/bold underline] ([cyan]{ej.id}[/cyan])")
                if enunciados:
                    console.print(Markdown(ej.enunciado_md))
                if pistas and ej.pistas:
                    pistas_txt = "\n".join(f"{idx}. {p}" for idx, p in enumerate(ej.pistas, 1))
                    console.print(Panel(pistas_txt, title="💡 Pistas", border_style="yellow"))
                if soluciones and ej.solucion_c:
                    console.print(Panel(
                        Syntax(ej.solucion_c, "c", theme="monokai", line_numbers=True),
                        title="Solución Modelo",
                        border_style="green",
                    ))


@guide_app.command("new")
def guide_new(
    archivo: str = typer.Argument(..., help="Nombre del archivo YAML o carpeta (ej: 'guia_punteros.yaml' o 'guia_punteros')."),
    titulo: str = typer.Option(..., "--titulo", "-t", help="Título descriptivo de la guía."),
    duracion: int = typer.Option(90, "--duracion", "-d", help="Duración estimada en minutos."),
    margen: float = typer.Option(0.8, "--margen", "-m", help="Margen de carga (0.3 - 1.0)."),
    temas: Optional[str] = typer.Option(None, "--temas", help="Temas separados por comas."),
    bloom_min: int = typer.Option(1, "--bloom-min", min=1, max=5),
    bloom_max: int = typer.Option(5, "--bloom-max", min=1, max=5),
    cantidad_max: Optional[int] = typer.Option(None, "--max-ejercicios", "-n"),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Crea una nueva especificación de guía (GuiaSpec) en guias/."""
    guias_dir.mkdir(parents=True, exist_ok=True)
    if archivo.endswith(".yaml") or archivo.endswith(".yml"):
        dest = guias_dir / archivo
    else:
        # Carpeta unificada
        dest = guias_dir / archivo / "guia.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)

    lista_temas = [t.strip() for t in temas.split(",") if t.strip()] if temas else []
    datos = {
        "nombre": titulo,
        "duracion_min": duracion,
        "margen_carga": margen,
        "temas": lista_temas,
        "bloom_min": bloom_min,
        "bloom_max": bloom_max,
    }
    if cantidad_max:
        datos["cantidad_maxima"] = cantidad_max

    guardar_yaml_guia(dest, datos)
    console.print(f"[green]✓ Especificación de guía creada en:[/green] {dest}")
    console.print(f"Para componerla automáticamente con el banco: [bold]deckard guide compose {dest}[/bold]")


@guide_app.command("compose")
def guide_compose_cmd(
    spec_file: Path = typer.Argument(..., exists=True, help="guia.yaml con nombre/duración/temas."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
) -> None:
    """Compone una guía balanceada por carga cognitiva y taxonomía de Bloom."""
    compose(spec_file=spec_file, banco=banco)


@guide_app.command("add")
def guide_add(
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo/carpeta de la guía."),
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio a agregar."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Agrega un ejercicio del banco a una guía compuesta."""
    ruta = resolver_ruta_guia(guia_archivo, dir_guias=guias_dir)
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    try:
        datos = agregar_ejercicio_a_guia(ruta, banco, ejercicio_id)
        console.print(f"[green]✓ Ejercicio '{ejercicio_id}' agregado a {ruta}.[/green]")
        console.print(f"  Total ejercicios: {len(datos.get('ejercicios', []))} · Carga total: ~{datos.get('minutos_totales', 0)} min")
    except Exception as e:
        console.print(f"[red]Error al agregar ejercicio: {e}[/red]")
        raise typer.Exit(code=1)


@guide_app.command("remove")
def guide_remove(
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo/carpeta de la guía."),
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio a remover."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Remueve un ejercicio de una guía compuesta."""
    ruta = resolver_ruta_guia(guia_archivo, dir_guias=guias_dir)
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    try:
        datos = remover_ejercicio_de_guia(ruta, ejercicio_id)
        console.print(f"[green]✓ Ejercicio '{ejercicio_id}' removido de {ruta}.[/green]")
        console.print(f"  Total ejercicios: {len(datos.get('ejercicios', []))} · Carga total: ~{datos.get('minutos_totales', 0)} min")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@guide_app.command("verify")
def guide_verify(
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo/carpeta de la guía."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
    ripley: Optional[str] = typer.Option(None, "--ripley", help="Ruta a ripley."),
) -> None:
    """Verifica con ripley todas las soluciones modelo de los ejercicios de la guía."""
    ruta = resolver_ruta_guia(guia_archivo, dir_guias=guias_dir)
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    _, items = cargar_guia_con_ejercicios(ruta, banco)
    if not items:
        console.print(f"[yellow]La guía no contiene ejercicios.[/yellow]")
        return

    tabla = Table(title=f"Verificación de ejercicios: {ruta.name}")
    tabla.add_column("Ejercicio", style="cyan")
    tabla.add_column("Veredicto", justify="center")
    tabla.add_column("Detalle")

    total_ok = 0
    for dir_ej, ej in items:
        if not ej or not dir_ej:
            tabla.add_row("(no encontrado)", "[red]✗ Error[/red]", "Ejercicio faltante en el banco")
            continue
        res = verificar_ejercicio(dir_ej, ruta_ripley=ripley)
        if res.ok:
            total_ok += 1
            v_str = "[green]✓ OK[/green]"
        else:
            v_str = "[red]✗ Fallo[/red]"
        tabla.add_row(ej.id, v_str, res.detalle)

    console.print(tabla)
    color = "green" if total_ok == len(items) else "red"
    console.print(f"[{color}]Verificación de guía finalizada: {total_ok}/{len(items)} exitosos[/{color}]")
    raise typer.Exit(code=0 if total_ok == len(items) else 1)


@guide_app.command("export")
@guide_app.command("pdf")
def guide_export_cmd(
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo/carpeta de la guía."),
    type: str = typer.Option("pdf", "--type", "-t", help="Formatos de salida separados por comas: pdf, md, html (ej: --type=pdf,md)."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Archivo de salida o directorio destino."),
    template: Optional[str] = typer.Option(None, "--template", "-T", help="Plantilla personalizada."),
    pipeline_md: bool = typer.Option(False, "--pipeline-md", help="Generar Markdown intermedio antes de compilar PDF."),
    soluciones: bool = typer.Option(False, "--soluciones", "-s", help="Incluir apéndice de soluciones."),
    pistas: bool = typer.Option(False, "--pistas", "-p", help="Incluir pistas progresivas."),
    css: Optional[Path] = typer.Option(None, "--css", exists=True, help="Archivo CSS adicional."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Exporta la guía completa a PDF, Markdown o HTML."""
    ruta = resolver_ruta_guia(guia_archivo, dir_guias=guias_dir)
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    exportar_contenido(
        objetivo=str(ruta),
        type=type,
        banco=banco,
        salida=salida,
        template=template,
        pipeline_md=pipeline_md,
        solucion=soluciones,
        pistas=pistas,
        tests=False,
        css=css,
    )


