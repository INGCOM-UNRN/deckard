"""Sub-app `export` (+ `templates`): exportación multiformato de ejercicios y guías."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from rich.table import Table
import typer

from deckard.core.bank import (
    buscar_ejercicios,
    cargar_ejercicio,
)
from deckard.core.export import (
    inicializar_plantillas,
)
from deckard.core.guides import (
    cargar_guia_con_ejercicios,
)

from deckard.cli._shared import (
    console,
    export_app,
    templates_sub_app,
)
from deckard.cli.export_run import (
    OpcionesExport,
    emitir_json,
    exportar_guia,
    exportar_un_ejercicio,
    exportar_varios_ejercicios,
)

# ---------------------------------------------------------------------------
# export (Exportación multiformato: PDF, MD, HTML) + init-templates
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# export (Exportación multiformato: PDF, MD, HTML) + templates
# ---------------------------------------------------------------------------



@templates_sub_app.command("init")
def export_init_templates(
    destino: Path = typer.Argument(Path("templates"), help="Directorio destino para las plantillas."),
    global_config: bool = typer.Option(False, "--global", "-g", help="Instalar en la configuración global de usuario (~/.config/deckard/templates)."),
    sobrescribir: bool = typer.Option(False, "--force", "-f", help="Sobrescribir plantillas existentes."),
) -> None:
    """Inicializa y copia las plantillas (HTML, Markdown y CSS) para personalizarlas."""
    target_dir = Path.home() / ".config" / "deckard" / "templates" if global_config else destino
    creados = inicializar_plantillas(target_dir, sobrescribir=sobrescribir)

    console.print(f"[bold green]✓ Plantillas inicializadas en:[/bold green] {target_dir.resolve()}")
    for p in creados:
        console.print(f"  • [cyan]{p.name}[/cyan] ({p.suffix.upper()})")
    if not creados:
        console.print("  [yellow]Las plantillas ya existían. Usá --force para sobrescribir.[/yellow]")
    console.print("\nPodés editar [bold]estilos.css[/bold], [bold]ejercicio.html[/bold], [bold]ejercicio.md[/bold] o agregar imágenes en este directorio.")


@templates_sub_app.command("list")
def export_templates_list() -> None:
    """Lista las plantillas disponibles (locales, globales y built-in)."""
    tabla = Table(title="Plantillas y Estilos Disponibles")
    tabla.add_column("Tipo", style="cyan")
    tabla.add_column("Ubicación / Archivo", style="green")
    tabla.add_column("Existe", justify="center")

    builtin_dir = Path(__file__).parent / "templates"
    global_dir = Path.home() / ".config" / "deckard" / "templates"
    local_dir = Path("templates")

    rutas = [
        ("Local (./templates)", local_dir),
        ("Global (~/.config/deckard/templates)", global_dir),
        ("Built-in (deckard/templates)", builtin_dir),
    ]
    for tipo, d in rutas:
        if d.is_dir():
            archivos = [f.name for f in sorted(d.iterdir()) if f.is_file()]
            tabla.add_row(tipo, f"{d} ({', '.join(archivos)})", "[green]✓[/green]")
        else:
            tabla.add_row(tipo, str(d), "[dim]—[/dim]")
    console.print(tabla)


def _parse_output_types(tipo_str: str) -> List[str]:
    raw_list = [t.strip().lower() for t in tipo_str.split(",") if t.strip()]
    res = []
    for r in raw_list:
        val = "md" if r == "markdown" else ("typ" if r == "typst" else r)
        if val not in ("pdf", "md", "html", "typ", "typst"):
            console.print(f"[red]Formato de salida no válido: '{r}'. Opciones permitidas: pdf, md, html, typ, typst.[/red]")
            raise typer.Exit(code=1)
        if val not in res:
            res.append(val)
    return res or ["pdf"]


@export_app.command("run", hidden=True)
def exportar_contenido(
    objetivo: Optional[str] = typer.Argument(None, help="Id de ejercicio, comodín/wildcard ('*', 'invertir-*'), o ruta a guía (.yaml)."),
    type: str = typer.Option("pdf", "--type", "-t", help="Formatos de salida (ej: --type=pdf,md o --type=typst). Separar por comas."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Archivo de salida o directorio destino."),
    template: Optional[str] = typer.Option(None, "--template", "-T", help="Nombre o ruta de plantilla personalizada (.typ.j2, .html, .md)."),
    pipeline_md: bool = typer.Option(False, "--pipeline-md", help="Generar Markdown intermedio antes de compilar PDF."),
    solucion: bool = typer.Option(False, "--solucion", "-s", help="Incluir solución modelo."),
    pistas: bool = typer.Option(False, "--pistas", "-p", help="Incluir pistas progresivas."),
    tests: bool = typer.Option(False, "--tests", help="Incluir casos de prueba."),
    css: Optional[Path] = typer.Option(None, "--css", exists=True, help="Archivo CSS adicional para PDF/HTML."),
    todos: bool = typer.Option(False, "--all", "-a", help="Exportar todos los ejercicios del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-m", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", help="Filtrar por nivel Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtrar por etiqueta/tag."),
    verificado: Optional[bool] = typer.Option(None, "--verificado/--no-verificado", help="Filtrar por estado de verificación."),
    single_pdf: bool = typer.Option(False, "--single-pdf", "--combined", "-c", help="Generar un único PDF consolidado cuando hay múltiples ejercicios para exportar."),
    titulo: Optional[str] = typer.Option(None, "--titulo", help="Título del compendio consolidado (usado con --single-pdf)."),
    dos_columnas: bool = typer.Option(False, "--dos-columnas", "--two-columns", "-2", help="Diseño compacto en 2 columnas para exámenes de laboratorio (ahorro de papel)."),
    as_json: bool = typer.Option(False, "--json", help="Salida en formato JSON estructurado."),
) -> None:
    """Exporta ejercicios o guías a Typst, PDF, Markdown o HTML con plantillas personalizables, comodines y filtros."""
    tipos = _parse_output_types(type)
    opts = OpcionesExport(
        tipos=tipos,
        banco=banco,
        template=template,
        pipeline_md=pipeline_md,
        solucion=solucion,
        pistas=pistas,
        tests=tests,
        extra_css=css.read_text(encoding="utf-8") if css else None,
        dos_columnas=dos_columnas,
    )

    patron = objetivo
    if todos:
        patron = objetivo or "*"
    elif not objetivo:
        if tema or bloom or tag or verificado is not None:
            patron = "*"
        else:
            console.print("[red]Debe especificar un objetivo (ID, comodín '*'), ruta a guía (.yaml), '--all' o al menos un filtro (--tema, --bloom, --tag).[/red]")
            raise typer.Exit(code=1)

    # Caso 1: archivo de guía YAML
    if objetivo:
        ruta_obj = Path(objetivo)
        if ruta_obj.is_file() and (ruta_obj.suffix in (".yaml", ".yml") or "guia" in ruta_obj.name):
            guia_meta, items = cargar_guia_con_ejercicios(ruta_obj, banco)
            validos = [(d, e) for d, e in items if e is not None]
            if not validos:
                console.print(f"[red]La guía '{objetivo}' no tiene ejercicios válidos en el banco.[/red]")
                raise typer.Exit(code=1)
            exportar_guia(opts, guia_meta, validos, salida, ruta_obj.stem, "Guía exportada")
            if as_json:
                emitir_json(opts)
            return

    # Caso 2: ejercicio(s) del banco (wildcards, filtros, --all)
    candidatos = _buscar_candidatos(objetivo, patron, banco, tema, bloom, tag, verificado)
    es_multiple = len(candidatos) > 1 or todos or bool(patron and ("*" in patron or "?" in patron))

    consolidar = single_pdf or (
        len(candidatos) > 1 and salida and not salida.is_dir()
        and salida.suffix.lower() == ".pdf" and len(tipos) == 1 and tipos[0] == "pdf"
    )
    if consolidar:
        titulo_compendio = titulo or (
            f"Guía de Ejercicios — Tema: {tema.capitalize()}" if tema else
            f"Compendio de Ejercicios ({len(candidatos)} ejercicios)"
        )
        guia_meta = {
            "titulo": titulo_compendio,
            "materia": "Programación 1",
            "descripcion": f"Compendio generado automáticamente con {len(candidatos)} ejercicios del banco.",
        }
        nombre_base = Path(objetivo).stem if objetivo and "*" not in objetivo else (f"compendio_{tema}" if tema else "compendio")
        exportar_guia(
            opts, guia_meta, candidatos, salida, nombre_base,
            f"Compendio consolidado ({len(candidatos)} ejercicios) exportado",
        )
        if as_json:
            emitir_json(opts)
        return

    if len(candidatos) == 1 and not es_multiple:
        dir_ej, ej = candidatos[0]
        exportar_un_ejercicio(opts, dir_ej, ej, salida)
        if as_json:
            emitir_json(opts)
        return

    exportar_varios_ejercicios(opts, candidatos, salida, as_json)


def _buscar_candidatos(objetivo, patron, banco, tema, bloom, tag, verificado):
    """Ejercicios que cumplen patrón y filtros; sale con error si no hay ninguno."""
    candidatos = buscar_ejercicios(
        banco,
        patron=patron,
        tema=tema,
        bloom=bloom,
        tag=tag,
        verificado=verificado,
        recursivo=True,
    )
    if not candidatos and objetivo:
        ruta_dir = Path(objetivo)
        if (ruta_dir / "ejercicio.yaml").is_file():
            ej_cand = cargar_ejercicio(ruta_dir)
            pasa = True
            if tema and ej_cand.tema != tema:
                pasa = False
            if bloom and int(ej_cand.bloom) != int(bloom):
                pasa = False
            if tag and tag not in ej_cand.tags:
                pasa = False
            if verificado is not None and ej_cand.verificado != verificado:
                pasa = False
            if pasa:
                candidatos = [(ruta_dir, ej_cand)]

    if not candidatos:
        criterios = []
        if patron and patron != "*":
            criterios.append(f"patrón='{patron}'")
        if tema:
            criterios.append(f"tema='{tema}'")
        if bloom:
            criterios.append(f"bloom={bloom}")
        if tag:
            criterios.append(f"tag='{tag}'")
        if verificado is not None:
            criterios.append(f"verificado={verificado}")
        crit_str = f" ({', '.join(criterios)})" if criterios else ""
        console.print(f"[red]No se encontró ningún ejercicio que coincida con los criterios especificados{crit_str}.[/red]")
        raise typer.Exit(code=1)
    return candidatos


# ---------------------------------------------------------------------------
# guide app (list, show, new, add, remove, verify, export, pdf)
# ---------------------------------------------------------------------------

