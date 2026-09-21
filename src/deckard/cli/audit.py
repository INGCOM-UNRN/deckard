"""Comando `audit`: auditoría de calidad de ejercicios."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from rich.table import Table
import typer


from deckard.cli._shared import (
    app,
    console,
    verify_app,
)

@verify_app.command("audit")
@verify_app.command("health")
@app.command("audit")
def audit_cmd(
    patron: Optional[str] = typer.Argument(None, help="ID o patrón comodín de ejercicios a auditar."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-t", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", min=1, max=5, help="Filtrar por nivel de Bloom."),
    tag: Optional[str] = typer.Option(None, "--tag", "-T", help="Filtrar por etiqueta/tag."),
    min_chars: int = typer.Option(100, "--min-chars", "-m", help="Largo mínimo de caracteres en enunciado para considerar redacción suficiente."),
    solo_pobres: bool = typer.Option(False, "--pobres", "--short", "-p", help="Mostrar únicamente ejercicios con redacción pobre o incompleta."),
    solo_incompletos: bool = typer.Option(False, "--incompletos", "-i", help="Mostrar solo ejercicios con componentes faltantes."),
    sin_tests: bool = typer.Option(False, "--sin-tests", help="Filtrar ejercicios sin casos de prueba (I/O ni funciones)."),
    sin_pistas: bool = typer.Option(False, "--sin-pistas", help="Filtrar ejercicios sin pistas progresivas."),
    sin_solucion: bool = typer.Option(False, "--sin-solucion", help="Filtrar ejercicios sin solución modelo."),
    json_output: bool = typer.Option(False, "--json", help="Emitir reporte estructurado en formato JSON."),
) -> None:
    """Audita la salud del banco: longitud y calidad de redacción del enunciado, y completitud de especificación."""
    from deckard.core.audit import auditar_banco

    reportes = auditar_banco(
        banco=banco,
        patron=patron,
        tema=tema,
        bloom=bloom,
        tag=tag,
        min_chars=min_chars,
        solo_pobres=solo_pobres,
        solo_incompletos=solo_incompletos,
        sin_tests=sin_tests,
        sin_pistas=sin_pistas,
        sin_solucion=sin_solucion,
    )

    if json_output:
        data = [
            {
                "id": r.id,
                "tema": r.tema,
                "bloom": r.bloom,
                "minutos": r.minutos,
                "longitud_enunciado_chars": r.longitud_enunciado_chars,
                "longitud_enunciado_words": r.longitud_enunciado_words,
                "redaccion_pobre": r.redaccion_pobre,
                "diagnostico_redaccion": r.diagnostico_redaccion,
                "tiene_enunciado_md": r.tiene_enunciado_md_file,
                "tiene_solucion": r.tiene_solucion,
                "pistas_count": r.cantidad_pistas,
                "tests_io_count": r.cantidad_testcases_io,
                "tests_fn_count": r.cantidad_tests_funciones,
                "tags": r.tags,
                "verificado": r.verificado,
                "faltantes": r.faltantes,
                "alertas": r.alertas,
            }
            for r in reportes
        ]
        console.print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not reportes:
        console.print(f"[yellow]No se encontraron ejercicios en '{banco}' con los filtros especificados.[/yellow]")
        return

    tabla = Table(title=f"Auditoría de Salud del Banco ({len(reportes)} ejercicios)")
    tabla.add_column("Ejercicio", style="cyan", no_wrap=True)
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Enunciado", justify="right")
    tabla.add_column("Redac.", justify="center")
    tabla.add_column("MD", justify="center")
    tabla.add_column("Sol.", justify="center")
    tabla.add_column("Pistas", justify="center")
    tabla.add_column("Tests", justify="center")
    tabla.add_column("Tags", style="dim")
    tabla.add_column("Faltantes / Alertas", style="yellow")

    total_chars = 0
    total_words = 0
    pobres_count = 0
    sin_tests_count = 0
    sin_sol_count = 0
    sin_pistas_count = 0

    for r in reportes:
        total_chars += r.longitud_enunciado_chars
        total_words += r.longitud_enunciado_words

        if r.redaccion_pobre:
            pobres_count += 1
            if r.diagnostico_redaccion == "pobre":
                redac_str = "[bold red]Pobre[/bold red]"
            else:
                redac_str = "[yellow]Breve[/yellow]"
        else:
            redac_str = "[green]Completo[/green]"

        md_str = "[green]enunciado.md[/green]" if r.tiene_enunciado_md_file else "[yellow]en yaml[/yellow]"
        sol_str = "[green]✓[/green]" if r.tiene_solucion else "[red]✗[/red]"
        if not r.tiene_solucion:
            sin_sol_count += 1

        pistas_str = f"{r.cantidad_pistas}" if r.cantidad_pistas > 0 else "[yellow]0[/yellow]"
        if r.cantidad_pistas == 0:
            sin_pistas_count += 1

        if r.total_tests > 0:
            tests_str = f"{r.total_tests} ({r.cantidad_testcases_io} io, {r.cantidad_tests_funciones} fn)"
        else:
            tests_str = "[red]0[/red]"
            sin_tests_count += 1

        tags_str = ", ".join(r.tags) if r.tags else "[dim]—[/dim]"
        obs = ", ".join(r.faltantes) if r.faltantes else "[green]✓ Completo[/green]"

        largo_str = f"{r.longitud_enunciado_chars} ch ({r.longitud_enunciado_words} w)"
        tabla.add_row(
            r.id,
            f"B{r.bloom}",
            largo_str,
            redac_str,
            md_str,
            sol_str,
            pistas_str,
            tests_str,
            tags_str,
            obs,
        )

    console.print(tabla)

    avg_chars = total_chars / len(reportes) if reportes else 0
    avg_words = total_words / len(reportes) if reportes else 0
    console.print(f"[bold]Resumen de Auditoría:[/bold]")
    console.print(f"  • Total analizados: [cyan]{len(reportes)}[/cyan]")
    console.print(f"  • Longitud media de enunciado: [bold]{avg_chars:.0f} caracteres[/bold] (~{avg_words:.0f} palabras)")
    if pobres_count > 0:
        console.print(f"  • [red]⚠️  {pobres_count} ejercicio(s) con redacción pobre o breve (<{min_chars} chars)[/red]")
    if sin_tests_count > 0:
        console.print(f"  • [red]⚠️  {sin_tests_count} ejercicio(s) sin casos de prueba (I/O o funciones)[/red]")
    if sin_sol_count > 0:
        console.print(f"  • [red]⚠️  {sin_sol_count} ejercicio(s) sin solución modelo[/red]")
    if sin_pistas_count > 0:
        console.print(f"  • [yellow]💡 {sin_pistas_count} ejercicio(s) sin pistas progresivas[/yellow]")
    if pobres_count == 0 and sin_tests_count == 0 and sin_sol_count == 0:
        console.print(f"[green]✓ Todos los ejercicios analizados cuentan con especificación completa y saludable.[/green]")


