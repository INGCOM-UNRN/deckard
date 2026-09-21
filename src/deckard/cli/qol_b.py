"""Mejoras QoL (grupo B): check-terms, diagram-memory, export-moodle, find-duplicates, lint-consigna, scaffold, bundle-offline, check-tone, checklist, check-signatures, license-manager, failure-hints."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
import typer

from deckard.core.bank import (
    buscar_ejercicios,
    cargar_ejercicio,
)

from deckard.cli._shared import (
    app,
    console,
    _resolver_dir_ejercicio,
    _cargar_ejercicios_target,
)

@app.command("check-terms")
def cmd_check_terms(
    target: str = typer.Argument(..., help="ID de ejercicio o ruta a guía YAML o raíz del banco."),
    preferencia: Optional[str] = typer.Option(None, "--preferencia", "-p", help="Preferencia: 'vector' o 'arreglo'."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Verifica la consistencia terminológica de consignas y detecta términos no válidos en C."""
    from deckard.core.terminology import auditar_terminologia_ejercicios

    ejercicios = _cargar_ejercicios_target(target, banco)
    res = auditar_terminologia_ejercicios(ejercicios, preferencia_coleccion=preferencia)

    if not res["por_ejercicio"]:
        console.print("[bold green]✓ Consistencia terminológica perfecta: no se detectaron irregularidades.[/bold green]")
        return

    tabla = Table(title=f"Auditoría Terminológica ({res['ejercicios_con_hallazgos']}/{res['total_ejercicios']} ejercicios con avisos)")
    tabla.add_column("Ejercicio", style="bold cyan")
    tabla.add_column("Regla", style="yellow")
    tabla.add_column("Detectado", style="red")
    tabla.add_column("Sugerido", style="green")
    tabla.add_column("Motivo")

    for ej_id, lista in res["por_ejercicio"].items():
        for f in lista:
            tabla.add_row(ej_id, f["regla"], f["termino_encontrado"], f["termino_sugerido"], f["motivo"])

    console.print(tabla)


@app.command("diagram-memory")
def cmd_diagram_memory(
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio."),
    formato: str = typer.Option("ascii", "--formato", "-f", help="Formato de salida: 'ascii' o 'mermaid'."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Ruta de archivo para guardar el esquema."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Genera esquemas de memoria Stack/Heap con convenciones Bishop para enunciados."""
    from deckard.core.memory_diagram import inferir_diagrama_desde_ejercicio

    dir_ej = _resolver_dir_ejercicio(ejercicio_id, banco)
    ej = cargar_ejercicio(dir_ej)
    diagrama = inferir_diagrama_desde_ejercicio(ej, formato=formato)

    if salida:
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(diagrama, encoding="utf-8")
        console.print(f"[bold green]✓ Diagrama de memoria ({formato}) guardado en:[/bold green] [cyan]{salida}[/cyan]")
    else:
        console.print(diagrama)


@app.command("export-moodle")
def cmd_export_moodle(
    target: str = typer.Argument(..., help="ID de ejercicio o ruta a guía YAML."),
    salida: Path = typer.Option(..., "--salida", "-o", help="Ruta del archivo XML Moodle generado."),
    categoria: Optional[str] = typer.Option(None, "--categoria", "-c", help="Categoría para agrupar preguntas."),
    tipo: str = typer.Option("multichoice", "--tipo", "-t", help="Tipo de pregunta: 'multichoice' o 'shortanswer'."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Exporta ejercicios a formato Moodle XML para cuestionarios virtuales."""
    from deckard.core.moodle_export import exportar_moodle_archivo

    ejercicios = _cargar_ejercicios_target(target, banco)
    exportar_moodle_archivo(ejercicios, salida, categoria=categoria, tipo_pregunta=tipo)
    console.print(f"[bold green]✓ Exportadas {len(ejercicios)} preguntas a Moodle XML en:[/bold green] [cyan]{salida}[/cyan]")


@app.command("find-duplicates")
def cmd_find_duplicates(
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    umbral: float = typer.Option(0.70, "--umbral", "-u", help="Umbral mínimo de similitud (0.0 a 1.0)."),
    sin_soluciones: bool = typer.Option(False, "--sin-soluciones", help="Omitir comparación de soluciones."),
) -> None:
    """Detecta redundancias y ejercicios duplicados en el banco según similitud léxica y estructural."""
    from deckard.core.duplicates import buscar_ejercicios_duplicados

    tuplas = buscar_ejercicios(banco, recursivo=True)
    ejercicios = [cargar_ejercicio(t[0]) for t in tuplas]
    dups = buscar_ejercicios_duplicados(ejercicios, umbral=umbral, comparar_soluciones=not sin_soluciones)

    if not dups:
        console.print(f"[bold green]✓ No se detectaron duplicados con umbral >= {umbral}.[/bold green]")
        return

    tabla = Table(title=f"Ejercicios Similares / Posibles Duplicados (Umbral >= {umbral})")
    tabla.add_column("Ejercicio A", style="bold cyan")
    tabla.add_column("Ejercicio B", style="bold cyan")
    tabla.add_column("Sim. Global", justify="right", style="yellow")
    tabla.add_column("Sim. Consigna", justify="right")
    tabla.add_column("Motivo")

    for d in dups:
        tabla.add_row(
            d.ejercicio_a_id,
            d.ejercicio_b_id,
            f"{int(d.similitud_global * 100)}%",
            f"{int(d.similitud_enunciado * 100)}%",
            d.motivo,
        )

    console.print(tabla)


@app.command("lint-consigna")
def cmd_lint_consigna(
    target: str = typer.Argument(..., help="ID de ejercicio, guía YAML o raíz del banco."),
    estricto: bool = typer.Option(False, "--estricto", help="Modo estricto: eleva severidad de omisiones."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Linter pedagógico de precondiciones y casos borde en consignas (NULL, vector vacío, archivos)."""
    from deckard.core.consigna_linter import lint_consigna_banco

    ejercicios = _cargar_ejercicios_target(target, banco)
    res = lint_consigna_banco(ejercicios, estricto=estricto)

    if not res["por_ejercicio"]:
        console.print("[bold green]✓ Consignas completas: todas especifican precondiciones y casos de borde requeridos.[/bold green]")
        return

    tabla = Table(title=f"Linter de Consignas ({res['ejercicios_con_observaciones']}/{res['total_ejercicios']} con observaciones)")
    tabla.add_column("Ejercicio", style="bold cyan")
    tabla.add_column("Severidad", style="bold")
    tabla.add_column("Regla", style="yellow")
    tabla.add_column("Diagnóstico")
    tabla.add_column("Sugerencia Pedagógica", style="green")

    for ej_id, lista in res["por_ejercicio"].items():
        for f in lista:
            color = "red" if f["severidad"] == "ALTA" else ("yellow" if f["severidad"] == "MEDIA" else "blue")
            tabla.add_row(
                ej_id,
                f"[{color}]{f['severidad']}[/{color}]",
                f["regla"],
                f["mensaje"],
                f["sugerencia"],
            )

    console.print(tabla)


@app.command("scaffold")
def cmd_scaffold(
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio."),
    steps: bool = typer.Option(False, "--steps", help="Generar andamiaje guiado con 4 pasos metodológicos TODO."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Ruta del archivo C de salida."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Genera plantillas de esqueletos de código con andamiaje pedagógico graduado."""
    from deckard.core.scaffold_steps import generar_esqueleto_con_pasos

    dir_ej = _resolver_dir_ejercicio(ejercicio_id, banco)
    ej = cargar_ejercicio(dir_ej)

    codigo = generar_esqueleto_con_pasos(ej, ruta_salida=salida)
    if salida:
        console.print(f"[bold green]✓ Esqueleto con pasos graduados generado en:[/bold green] [cyan]{salida}[/cyan]")
    else:
        console.print(Syntax(codigo, "c", theme="monokai", line_numbers=True))


@app.command("bundle-offline")
def cmd_bundle_offline(
    target: str = typer.Argument(..., help="Ruta a guía YAML o directorio raíz del banco."),
    salida: Path = typer.Option(Path("bundle_offline.zip"), "--salida", "-o", help="Ruta del archivo ZIP generado."),
    titulo: str = typer.Option("Guía de Ejercicios Offline", "--titulo", "-t", help="Título del visor web offline."),
    incluir_soluciones: bool = typer.Option(False, "--incluir-soluciones", help="Incluir soluciones de referencia."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Empaqueta guías y ejercicios en un bundle portable ZIP con visor web HTML/CSS 100% offline."""
    from deckard.core.bundle_offline import empaquetar_bundle_offline

    ejercicios = _cargar_ejercicios_target(target, banco)
    empaquetar_bundle_offline(ejercicios, salida, titulo=titulo, incluir_soluciones=incluir_soluciones)
    console.print(f"[bold green]✓ Bundle portable offline ({len(ejercicios)} ejercicios) creado en:[/bold green] [cyan]{salida}[/cyan]")


@app.command("check-tone")
def cmd_check_tone(
    target: str = typer.Argument(..., help="ID de ejercicio, guía YAML o raíz del banco."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Audita ambigüedades lingüísticas, dobles negaciones y consistencia de tono en consignas."""
    from deckard.core.tone_checker import auditar_tono_banco

    ejercicios = _cargar_ejercicios_target(target, banco)
    res = auditar_tono_banco(ejercicios)

    if not res["por_ejercicio"]:
        console.print("[bold green]✓ Tono y redacción claros: no se detectaron ambigüedades ni mezclas de estilo.[/bold green]")
        return

    tabla = Table(title=f"Auditoría de Tono Pedagógico ({res['ejercicios_con_observaciones']}/{res['total_ejercicios']} observados)")
    tabla.add_column("Ejercicio", style="bold cyan")
    tabla.add_column("Severidad", style="bold")
    tabla.add_column("Regla", style="yellow")
    tabla.add_column("Fragmento")
    tabla.add_column("Sugerencia", style="green")

    for ej_id, lista in res["por_ejercicio"].items():
        for f in lista:
            color = "red" if f["severidad"] == "ALTA" else ("yellow" if f["severidad"] == "MEDIA" else "blue")
            tabla.add_row(
                ej_id,
                f"[{color}]{f['severidad']}[/{color}]",
                f["regla"],
                f["fragmento"],
                f["sugerencia"],
            )

    console.print(tabla)


@app.command("checklist")
def cmd_checklist(
    target: str = typer.Argument(..., help="ID de ejercicio o ruta a guía YAML."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Ruta de archivo Markdown de salida."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Genera listas de autoevaluación previas a la entrega en formato Markdown."""
    from deckard.core.checklist import generar_checklist_guia

    ejercicios = _cargar_ejercicios_target(target, banco)
    md_text = generar_checklist_guia(ejercicios, ruta_salida=salida)
    if salida:
        console.print(f"[bold green]✓ Checklist Markdown guardada en:[/bold green] [cyan]{salida}[/cyan]")
    else:
        console.print(Markdown(md_text))


@app.command("check-signatures")
def cmd_check_signatures(
    target: str = typer.Argument(..., help="ID de ejercicio, guía YAML o directorio del banco."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Valida la consistencia de firmas de función entre el enunciado y la solución canónica."""
    from deckard.core.signature_checker import auditar_firmas_banco

    ejercicios = _cargar_ejercicios_target(target, banco)
    res = auditar_firmas_banco(ejercicios)

    if not res["por_ejercicio"]:
        console.print("[bold green]✓ Firmas consistentes: las funciones declaradas coinciden con la solución.[/bold green]")
        return

    tabla = Table(title=f"Discrepancias de Firmas ({res['ejercicios_con_discrepancias']}/{res['total_ejercicios']} observados)")
    tabla.add_column("Ejercicio", style="bold cyan")
    tabla.add_column("Función", style="bold")
    tabla.add_column("Tipo", style="yellow")
    tabla.add_column("Declarada", style="green")
    tabla.add_column("Encontrada", style="red")
    tabla.add_column("Detalle")

    for ej_id, lista in res["por_ejercicio"].items():
        for d in lista:
            tabla.add_row(ej_id, d["nombre_funcion"], d["tipo"], d["declarada"], d["encontrada"], d["detalle"])

    console.print(tabla)


@app.command("license-manager")
def cmd_license_manager(
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio."),
    autor: Optional[str] = typer.Option(None, "--autor", "-a", help="Nombre del autor o equipo docente."),
    licencia: str = typer.Option("CC-BY-SA-4.0", "--licencia", "-l", help="Identificador de licencia (CC-BY-SA-4.0, MIT, etc.)."),
    anio: int = typer.Option(2026, "--anio", help="Año de autoría."),
    aplicar: bool = typer.Option(False, "--aplicar", help="Inyectar y persistir los metadatos en archivos."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Gestiona metadatos de autoría, licencias educativas y headers de copyright."""
    from deckard.core.license_manager import inyectar_creditos_ejercicio, obtener_creditos_ejercicio

    dir_ej = _resolver_dir_ejercicio(ejercicio_id, banco)
    ej = cargar_ejercicio(dir_ej)

    if aplicar and autor:
        meta = inyectar_creditos_ejercicio(ej, dir_ej, autor=autor, licencia=licencia, anio=anio)
        console.print(f"[bold green]✓ Metadatos de licencia aplicados a:[/bold green] [cyan]{dir_ej}[/cyan]")
    else:
        meta = obtener_creditos_ejercicio(ej, dir_ejercicio=dir_ej)
        tabla = Table(title=f"Créditos de Autoría [{ej.id}]")
        tabla.add_column("Campo", style="bold")
        tabla.add_column("Valor", style="cyan")
        tabla.add_row("Autor", meta.autor)
        tabla.add_row("Licencia", meta.licencia)
        tabla.add_row("Año", str(meta.anio))
        tabla.add_row("Institución", meta.institucion)
        console.print(tabla)


@app.command("failure-hints")
def cmd_failure_hints(
    codigo_o_error: str = typer.Argument(..., help="Código de falla, señal o assert (ej: SIGSEGV, SIGABRT, ASSERT_EQ)."),
) -> None:
    """Brinda orientación pedagógica y preguntas guía ante fallas en tests o ejecución."""
    from deckard.core.failure_hints import obtener_pista_falla

    pista = obtener_pista_falla(codigo_o_error)
    panel_content = (
        f"[bold cyan]Concepto Clave:[/bold cyan] {pista.concepto_clave}\n\n"
        f"[white]{pista.explicacion_didactica}[/white]\n\n"
        f"[bold yellow]Preguntas Guía para Reflexionar:[/bold yellow]\n"
        + "\n".join(f"  • {q}" for q in pista.preguntas_guia)
        + f"\n\n[bold green]Acción Sugerida:[/bold green] {pista.sugerencia_accion}"
    )
    console.print(Panel(panel_content, title=f"Pista Pedagógica: {pista.codigo_falla}", border_style="cyan"))


if __name__ == "__main__":
    app()
