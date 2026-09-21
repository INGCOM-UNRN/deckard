"""Sub-app `verify`: verificación pedagógica de ejercicios (ripley check)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
import typer

from deckard.core.bank import (
    actualizar_verificacion,
    buscar_ejercicios,
)
from deckard.core.verify import verificar_ejercicio

from deckard.cli._shared import (
    console,
    verify_app,
)

# ---------------------------------------------------------------------------
# verify app (verify, fuzz, test-harness)
# ---------------------------------------------------------------------------

def _escribir_log_fallos_verificacion(
    ruta_log: Path,
    fallos: List[dict],
    total_analizados: int,
    total_exitos: int,
    total_fallos: int,
) -> None:
    from datetime import datetime
    ruta_log = Path(ruta_log)
    ruta_log.parent.mkdir(parents=True, exist_ok=True)

    lineas = [
        "# Reporte de Fallos de Verificación — Deckard",
        f"- **Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Total analizados:** {total_analizados}",
        f"- **Exitosos:** {total_exitos}",
        f"- **Fallidos:** {total_fallos}",
        "",
        "---",
        "",
    ]
    if not fallos:
        lineas.append("No se registraron fallos durante la verificación.\n")
    else:
        lineas.append("## Detalle de Ejercicios con Fallas\n")
        for f in fallos:
            lineas.append(f"### `{f['id']}` (Fallo de Verificación)")
            lineas.append(f"- **Tema:** {f.get('tema', '—')}")
            lineas.append(f"- **Directorio:** `{f['dir']}`")
            lineas.append(f"- **Estado en banco:** Marcado como no-verificado (`verificado: false`)")
            lineas.append("- **Detalle del fallo:**")
            lineas.append("```")
            lineas.append(f.get("error", "Error no especificado"))
            lineas.append("```\n")

    ruta_log.write_text("\n".join(lineas), encoding="utf-8")


@verify_app.command("run", hidden=True)
def verify(
    ejercicio_id: Optional[str] = typer.Argument(None, help="Id del ejercicio o patrón comodín (ej: '*', 'invertir-*')."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    all_exercises: bool = typer.Option(False, "--all", "-a", help="Verificar todos los ejercicios del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-t", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", min=1, max=5, help="Filtrar por nivel de Bloom (1-5)."),
    pendientes: bool = typer.Option(False, "--pendientes", "-p", help="Verificar solo ejercicios pendientes."),
    guardar: bool = typer.Option(True, "--guardar/--no-guardar", help="Persistir veredicto en ejercicio.yaml."),
    log_fallos: Optional[Path] = typer.Option(None, "--log-fallos", "-l", help="Ruta de archivo para guardar el reporte de ejercicios fallidos."),
    ripley: Optional[str] = typer.Option(None, "--ripley", help="Ruta al binario/zipapp de ripley."),
    as_json: bool = typer.Option(False, "--json", help="Salida en formato JSON estructurado."),
) -> None:
    """Verifica la solución modelo de ejercicios usando ripley check."""
    if ejercicio_id is None and not all_exercises and not tema and not bloom and not pendientes:
        console.print("[yellow]Especificá un id de ejercicio, un patrón comodín (ej: '*') o usá --all para verificar todo el banco.[/yellow]")
        raise typer.Exit(code=1)

    pat = "*" if (all_exercises and not ejercicio_id) else ejercicio_id
    verif_filtro = False if pendientes else None
    candidatos = buscar_ejercicios(banco, patron=pat, tema=tema, bloom=bloom, verificado=verif_filtro)

    if not candidatos:
        console.print(f"[red]No se encontraron ejercicios en '{banco}' con el criterio especificado.[/red]")
        raise typer.Exit(code=1)

    es_unico_puntual = len(candidatos) == 1 and pat and not any(c in pat for c in "*?[]") and not all_exercises
    if es_unico_puntual:
        dir_ej, ej = candidatos[0]
        resultado = verificar_ejercicio(dir_ej, ruta_ripley=ripley)
        if (dir_ej / "ejercicio.yaml").is_file():
            if not resultado.ok or guardar:
                actualizar_verificacion(dir_ej, resultado.ok)

        if as_json:
            console.print_json(data={
                "total": 1,
                "exitosos": 1 if resultado.ok else 0,
                "fallidos": 0 if resultado.ok else 1,
                "ejercicios": [
                    {"id": ej.id, "tema": ej.tema, "ok": resultado.ok, "detalle": resultado.detalle}
                ],
            })
            raise typer.Exit(code=0 if resultado.ok else 1)

        color = "green" if resultado.ok else "red"
        console.print(f"[{color}]{resultado.marca} {resultado.ejercicio}[/{color}] — {resultado.detalle}")
        if not resultado.ok:
            console.print(f"[dim]Marcado como no-verificado (verificado: false).[/dim]")
            if log_fallos:
                _escribir_log_fallos_verificacion(
                    log_fallos,
                    [{"id": ej.id, "tema": ej.tema, "dir": dir_ej, "error": resultado.detalle}],
                    1, 0, 1
                )
                console.print(f"[yellow]📝 Reporte de fallos guardado en:[/yellow] {log_fallos}")
        raise typer.Exit(code=0 if resultado.ok else 1)

    if as_json:
        total_ok = 0
        total_fallos = 0
        items_json = []
        for dir_ej, ej in candidatos:
            res = verificar_ejercicio(dir_ej, ruta_ripley=ripley)
            if (dir_ej / "ejercicio.yaml").is_file():
                if not res.ok or guardar:
                    actualizar_verificacion(dir_ej, res.ok)
            if res.ok:
                total_ok += 1
            else:
                total_fallos += 1
            items_json.append({
                "id": ej.id,
                "tema": ej.tema,
                "bloom": int(ej.bloom),
                "ok": res.ok,
                "detalle": res.detalle,
            })
        console.print_json(data={
            "total": len(candidatos),
            "exitosos": total_ok,
            "fallidos": total_fallos,
            "ejercicios": items_json,
        })
        raise typer.Exit(code=0 if total_fallos == 0 else 1)

    console.print(f"[bold]Verificando {len(candidatos)} ejercicios con ripley...[/bold]")
    tabla = Table(title="Resultados de verificación")
    tabla.add_column("Ejercicio", style="cyan")
    tabla.add_column("Tema")
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Veredicto", justify="center")
    tabla.add_column("Detalle")

    total_ok = 0
    total_fallos = 0
    fallos_info = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Verificando ejercicios...", total=len(candidatos))

        for dir_ej, ej in candidatos:
            progress.update(task, description=f"[cyan]Verificando: [bold]{ej.id}[/bold]")
            res = verificar_ejercicio(dir_ej, ruta_ripley=ripley)

            if (dir_ej / "ejercicio.yaml").is_file():
                if not res.ok or guardar:
                    actualizar_verificacion(dir_ej, res.ok)

            if res.ok:
                total_ok += 1
                veredicto_str = "[green]✓ OK[/green]"
            else:
                total_fallos += 1
                veredicto_str = "[red]✗ Fallo[/red]"
                fallos_info.append({
                    "id": ej.id,
                    "tema": ej.tema,
                    "dir": dir_ej,
                    "error": res.detalle,
                })

            tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", veredicto_str, res.detalle)
            progress.advance(task)

    console.print(tabla)
    color_resumen = "green" if total_ok == len(candidatos) else "yellow" if total_ok > 0 else "red"
    console.print(f"[{color_resumen}]Verificación completada: {total_ok}/{len(candidatos)} exitosos[/{color_resumen}]")

    if log_fallos:
        _escribir_log_fallos_verificacion(
            log_fallos,
            fallos_info,
            len(candidatos),
            total_ok,
            total_fallos,
        )
        console.print(f"[yellow]📝 Reporte de fallos guardado en:[/yellow] {log_fallos}")

    raise typer.Exit(code=0 if total_ok == len(candidatos) else 1)


