"""Sub-app `spec`: gestión y validación de especificaciones de guías (GuiaSpec)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.panel import Panel
from rich.table import Table
import typer

from deckard.core.guides import (
    cargar_spec,
    guardar_spec,
    listar_specs,
    validar_spec,
)
from deckard.core.models import GuiaSpec

from deckard.cli._shared import (
    console,
    spec_app,
)
from deckard.cli.compose import compose

# ---------------------------------------------------------------------------
# spec app (list, show, new, edit, validate, compose)
# ---------------------------------------------------------------------------


def _resolver_ruta_spec(spec_archivo: str, guias_dir: Path) -> Path:
    ruta = Path(spec_archivo)
    if not ruta.is_file():
        ruta = guias_dir / spec_archivo
    if not ruta.is_file() and not ruta.suffix:
        ruta = guias_dir / f"{spec_archivo}.yaml"
    if not ruta.is_file():
        console.print(f"[red]No se encontró el archivo spec '{spec_archivo}'.[/red]")
        raise typer.Exit(code=1)
    return ruta


@spec_app.command("list")
def spec_list(
    guias_dir: Path = typer.Option(Path("guias"), "--guias", "-g", help="Directorio donde se ubican los specs."),
) -> None:
    """Lista todas las especificaciones de guías (GuiaSpec) disponibles."""
    specs = listar_specs(guias_dir)
    if not specs:
        console.print(f"[yellow]No se encontraron specs en '{guias_dir}'. Creá una con 'deckard spec new'.[/yellow]")
        return
    tabla = Table(title=f"Especificaciones de Guías ({len(specs)} encontradas)")
    tabla.add_column("Archivo", style="cyan")
    tabla.add_column("Título")
    tabla.add_column("Duración", justify="right")
    tabla.add_column("Carga Útil", justify="right")
    tabla.add_column("Temas")
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Max Ej.", justify="center")
    for ruta, s in specs:
        util = int(s.duracion_min * s.margen_carga)
        temas_str = ", ".join(s.temas) if s.temas else "(todos)"
        max_ej = str(s.cantidad_maxima) if s.cantidad_maxima else "—"
        tabla.add_row(
            ruta.name,
            s.nombre,
            f"{s.duracion_min} min",
            f"~{util} min ({int(s.margen_carga*100)}%)",
            temas_str,
            f"B{s.bloom_min}..B{s.bloom_max}",
            max_ej,
        )
    console.print(tabla)


@spec_app.command("new")
def spec_new(
    archivo: str = typer.Argument(..., help="Nombre del archivo (ej: 'guia_parcial1.yaml')."),
    titulo: str = typer.Option(..., "--titulo", "-t", help="Título pedagógico de la especificación."),
    duracion: int = typer.Option(90, "--duracion", "-d", help="Duración estimada total en minutos."),
    margen: float = typer.Option(0.8, "--margen", "-m", help="Margen de carga útil (0.1 a 1.0)."),
    temas: Optional[str] = typer.Option(None, "--temas", help="Temas obligatorios separados por comas."),
    bloom_min: int = typer.Option(1, "--bloom-min", min=1, max=5),
    bloom_max: int = typer.Option(5, "--bloom-max", min=1, max=5),
    cantidad_max: Optional[int] = typer.Option(None, "--max-ejercicios", "-n"),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", "-g"),
) -> None:
    """Crea una nueva especificación de guía (GuiaSpec)."""
    guias_dir.mkdir(parents=True, exist_ok=True)
    nombre_f = archivo if archivo.endswith((".yaml", ".yml")) else f"{archivo}.yaml"
    dest = guias_dir / nombre_f
    lista_temas = [t.strip() for t in temas.split(",") if t.strip()] if temas else []
    spec = GuiaSpec(
        nombre=titulo,
        duracion_min=duracion,
        margen_carga=margen,
        temas=lista_temas,
        bloom_min=bloom_min,
        bloom_max=bloom_max,
        cantidad_maxima=cantidad_max,
    )
    guardar_spec(dest, spec)
    console.print(f"[green]✓ Spec creada exitosamente en:[/green] {dest}")
    console.print(f"Podés validarla con [bold]deckard spec validate {dest}[/bold] o componerla con [bold]deckard spec compose {dest}[/bold].")


@spec_app.command("show")
def spec_show(
    spec_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo spec YAML."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Muestra los detalles de una especificación y su universo de ejercicios candidatos en el banco."""
    ruta = _resolver_ruta_spec(spec_archivo, guias_dir)
    spec = cargar_spec(ruta)
    diag = validar_spec(spec, banco)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("Archivo:", str(ruta))
    grid.add_row("Título:", spec.nombre)
    grid.add_row("Duración nominal:", f"{spec.duracion_min} minutos")
    grid.add_row("Presupuesto útil:", f"~{diag['minutos_requeridos']} min (margen: {int(spec.margen_carga*100)}%)")
    grid.add_row("Temas requeridos:", ", ".join(spec.temas) if spec.temas else "(cualquiera)")
    grid.add_row("Rango Bloom:", f"B{spec.bloom_min} a B{spec.bloom_max}")
    if spec.cantidad_maxima:
        grid.add_row("Límite ejercicios:", str(spec.cantidad_maxima))

    console.print(Panel(grid, title=f"[bold cyan]Spec: {spec.nombre}[/bold cyan]", border_style="cyan"))

    candidatos = diag["candidatos"]
    tabla_c = Table(title=f"Candidatos elegibles en el banco ({len(candidatos)} ejercicios · ~{diag['minutos_disponibles']} min disponibles)")
    tabla_c.add_column("ID", style="cyan")
    tabla_c.add_column("Título")
    tabla_c.add_column("Tema")
    tabla_c.add_column("Bloom", justify="center")
    tabla_c.add_column("Min", justify="right")
    tabla_c.add_column("Verificado", justify="center")

    for _, e in candidatos:
        tabla_c.add_row(e.id, e.titulo, e.tema, f"B{int(e.bloom)}", str(e.minutos_estimados), "[green]✓[/green]" if e.verificado else "[dim]—[/dim]")
    console.print(tabla_c)


@spec_app.command("validate")
def spec_validate(
    spec_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo spec YAML."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Verifica si el banco de ejercicios tiene suficientes candidatos para satisfacer el spec."""
    ruta = _resolver_ruta_spec(spec_archivo, guias_dir)
    spec = cargar_spec(ruta)
    diag = validar_spec(spec, banco)

    if diag["satisfactible"]:
        console.print(f"[bold green]✓ Spec satisfactible[/bold green]: {diag['candidatos_total']} ejercicios disponibles (~{diag['minutos_disponibles']} min para cubrir ~{diag['minutos_requeridos']} min requeridos).")
        if diag["verificados_count"] < diag["candidatos_total"]:
            console.print(f"[yellow]Nota:[/yellow] Solo {diag['verificados_count']}/{diag['candidatos_total']} candidatos están verificados.")
    else:
        console.print(f"[bold red]✗ Spec NO satisfactible con el banco actual[/bold red]")
        if diag["minutos_disponibles"] < diag["minutos_requeridos"]:
            console.print(f"  • Minutos disponibles ({diag['minutos_disponibles']} min) < requeridos ({diag['minutos_requeridos']} min).")
        if diag["temas_faltantes"]:
            console.print(f"  • Temas sin ejercicios en el banco: [red]{', '.join(diag['temas_faltantes'])}[/red]")
        raise typer.Exit(code=1)


@spec_app.command("edit")
def spec_edit(
    spec_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo spec YAML."),
    titulo: Optional[str] = typer.Option(None, "--titulo", "-t"),
    duracion: Optional[int] = typer.Option(None, "--duracion", "-d"),
    margen: Optional[float] = typer.Option(None, "--margen", "-m"),
    temas: Optional[str] = typer.Option(None, "--temas"),
    bloom_min: Optional[int] = typer.Option(None, "--bloom-min", min=1, max=5),
    bloom_max: Optional[int] = typer.Option(None, "--bloom-max", min=1, max=5),
    cantidad_max: Optional[int] = typer.Option(None, "--max-ejercicios", "-n"),
    guias_dir: Path = typer.Option(Path("guias"), "--guias"),
) -> None:
    """Modifica parámetros de una especificación existente."""
    ruta = _resolver_ruta_spec(spec_archivo, guias_dir)
    spec = cargar_spec(ruta)

    if titulo is not None:
        spec.nombre = titulo
    if duracion is not None:
        spec.duracion_min = duracion
    if margen is not None:
        spec.margen_carga = margen
    if temas is not None:
        spec.temas = [t.strip() for t in temas.split(",") if t.strip()]
    if bloom_min is not None:
        spec.bloom_min = bloom_min
    if bloom_max is not None:
        spec.bloom_max = bloom_max
    if cantidad_max is not None:
        spec.cantidad_maxima = cantidad_max

    guardar_spec(ruta, spec)
    console.print(f"[green]✓ Spec actualizada:[/green] {ruta}")


@spec_app.command("compose")
def spec_compose_cmd(
    spec_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo spec YAML."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Compone una guía a partir de esta especificación."""
    ruta = _resolver_ruta_spec(spec_archivo, guias_dir)
    compose(spec_file=ruta, banco=banco)


