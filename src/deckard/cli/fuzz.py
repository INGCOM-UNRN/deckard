"""Comando `fuzz`: fuzzing de ejercicios vía dredd."""

from __future__ import annotations

from pathlib import Path
import subprocess
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

from deckard.cli._shared import (
    app,
    console,
    verify_app,
)

# ---------------------------------------------------------------------------
# fuzz
# ---------------------------------------------------------------------------


def _escribir_log_fallos(
    ruta_log: Path,
    fallos: List[dict],
    total_analizados: int,
    total_exitos: int,
    total_omitidos: int,
    total_fallos: int,
) -> None:
    from datetime import datetime
    ruta_log = Path(ruta_log)
    ruta_log.parent.mkdir(parents=True, exist_ok=True)

    lineas = [
        "# Reporte de Fallos de Fuzzing — Deckard",
        f"- **Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Total analizados:** {total_analizados}",
        f"- **Exitosos:** {total_exitos}",
        f"- **Omitidos:** {total_omitidos}",
        f"- **Fallidos:** {total_fallos}",
        "",
        "---",
        "",
    ]
    if not fallos:
        lineas.append("No se registraron fallos durante la ejecución.\n")
    else:
        lineas.append("## Detalle de Ejercicios Afectados\n")
        for f in fallos:
            lineas.append(f"### `{f['id']}` ({f.get('tipo', 'Fallo')})")
            lineas.append(f"- **Tema:** {f.get('tema', '—')}")
            lineas.append(f"- **Directorio:** `{f['dir']}`")
            lineas.append(f"- **Estado en banco:** Marcado como no-verificado (`verificado: false`)")
            lineas.append("- **Detalle del error / salida:**")
            lineas.append("```")
            lineas.append(f.get("error", "Error no especificado"))
            lineas.append("```\n")

    ruta_log.write_text("\n".join(lineas), encoding="utf-8")


def _generador() -> Optional[List[str]]:
    """El comando que genera los casos: `drake gen-casos` (drake es el dueño del fuzzing, N-ECO-12) o,
    si no está instalado, `dredd fuzz-gen` (que se va a retirar)."""
    import shutil as _shutil
    if _shutil.which("drake"):
        return [_shutil.which("drake") or "drake", "gen-casos"]
    if _shutil.which("dredd"):
        return [_shutil.which("dredd") or "dredd", "fuzz-gen"]
    return None



@verify_app.command("fuzz")
@app.command("fuzz", hidden=True)
def fuzz(
    ejercicio_id: Optional[str] = typer.Argument(None, help="Id del ejercicio o patrón comodín (ej: '*', 'invertir-*', 'punteros/*')."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    all_exercises: bool = typer.Option(False, "--all", "-a", help="Ejecutar fuzzing sobre todos los ejercicios del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-t", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", min=1, max=5, help="Filtrar por nivel de Bloom (1-5)."),
    cantidad: int = typer.Option(8, "--cantidad", "-n", help="Cantidad de testcases a generar por ejercicio."),
    segundos: int = typer.Option(15, "--segundos", help="Segundos de fuzzing si libFuzzer está disponible."),
    sin_libfuzzer: bool = typer.Option(False, "--sin-libfuzzer", help="Forzar modo determinista sin libFuzzer."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Detenerse inmediatamente ante el primer error."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Solo listar ejercicios que se procesarían sin ejecutar."),
    log_fallos: Optional[Path] = typer.Option(None, "--log-fallos", "-l", help="Ruta de archivo para guardar el reporte de ejercicios fallidos u omitidos."),
) -> None:
    """Endurece los tests de ejercicios con `drake gen-casos` (o `dredd fuzz-gen`) (soporta wildcards, batch y tracking de progreso)."""
    if ejercicio_id is None and not all_exercises and not tema and not bloom:
        console.print("[yellow]Especificá un id de ejercicio, un patrón comodín (ej: '*') o usá --all para todo el banco.[/yellow]")
        raise typer.Exit(code=1)

    pat = "*" if (all_exercises and not ejercicio_id) else ejercicio_id
    candidatos = buscar_ejercicios(banco, patron=pat, tema=tema, bloom=bloom)

    if not candidatos:
        console.print(f"[red]No se encontraron ejercicios en '{banco}' con el criterio especificado.[/red]")
        raise typer.Exit(code=1)

    if dry_run:
        tabla = Table(title=f"Ejercicios seleccionados para fuzz ({len(candidatos)})")
        tabla.add_column("id", style="cyan")
        tabla.add_column("tema")
        tabla.add_column("bloom", justify="center")
        tabla.add_column("solucion.c", justify="center")
        for dir_ej, ej in candidatos:
            tiene_sol = (dir_ej / "solucion.c").is_file()
            tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", "✓" if tiene_sol else "[red]✗[/red]")
        console.print(tabla)
        return

    if _generador() is None:
        console.print("[red]Hace falta drake (o dredd) en el PATH para generar los casos.[/red]")
        raise typer.Exit(code=127)


    es_unico_puntual = len(candidatos) == 1 and pat and not any(c in pat for c in "*?[]") and not all_exercises
    if es_unico_puntual:
        dir_ej, ej = candidatos[0]
        modelo = dir_ej / "solucion.c"
        if not modelo.is_file():
            actualizar_verificacion(dir_ej, False)
            if log_fallos:
                _escribir_log_fallos(
                    log_fallos,
                    [{"id": ej.id, "tema": ej.tema, "dir": dir_ej, "tipo": "Omitido", "error": "No tiene solucion.c"}],
                    1, 0, 1, 0
                )
            console.print(f"[red]El ejercicio '{ej.id}' no tiene solucion.c en {dir_ej}[/red] (marcado como no-verificado)")
            raise typer.Exit(code=1)

        destino = dir_ej / "tests"
        cmd_args = [
            *_generador(),
            str(modelo),
            "-o",
            str(destino),
            "--cantidad",
            str(cantidad),
            "--segundos",
            str(segundos),
        ]
        if sin_libfuzzer:
            cmd_args.append("--sin-libfuzzer")
        cmd_str = " ".join(cmd_args)
        console.print(f"[dim]$ {cmd_str}[/dim]")
        proc = subprocess.run(cmd_args, capture_output=True, text=True)
        rc = proc.returncode
        if rc == 0:
            console.print("[green]✓ Testcases endurecidos. Recordá marcar 'verificado' tras re-correr deckard verify.[/green]")
        else:
            actualizar_verificacion(dir_ej, False)
            console.print(f"[red]✗ Fallo en fuzzing para '{ej.id}'. Marcado como no-verificado.[/red]")
            if proc.stderr:
                console.print(f"[dim]{proc.stderr.strip()}[/dim]")
            if log_fallos:
                _escribir_log_fallos(
                    log_fallos,
                    [{"id": ej.id, "tema": ej.tema, "dir": dir_ej, "tipo": "Fallo", "error": proc.stderr.strip() or f"Código {rc}"}],
                    1, 0, 0, 1
                )
        raise typer.Exit(code=rc)

    # Modo masivo / wildcard con barra de progreso
    console.print(f"[bold]Ejecutando fuzz-gen sobre {len(candidatos)} ejercicios...[/bold]")
    tabla = Table(title="Resultados de fuzzing")
    tabla.add_column("Ejercicio", style="cyan")
    tabla.add_column("Tema")
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Estado", justify="center")
    tabla.add_column("Testcases / Detalle")

    total_exitos = 0
    total_omitidos = 0
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
        task = progress.add_task("[cyan]Fuzzing ejercicios...", total=len(candidatos))

        for dir_ej, ej in candidatos:
            progress.update(task, description=f"[cyan]Fuzzing: [bold]{ej.id}[/bold]")
            modelo = dir_ej / "solucion.c"

            if not modelo.is_file():
                actualizar_verificacion(dir_ej, False)
                tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", "[yellow]⚠ Omitido[/yellow]", "Sin solucion.c (no-verificado)")
                total_omitidos += 1
                fallos_info.append({
                    "id": ej.id,
                    "tema": ej.tema,
                    "dir": dir_ej,
                    "tipo": "Omitido",
                    "error": "No tiene archivo solucion.c",
                })
                progress.advance(task)
                if fail_fast:
                    break
                continue

            destino = dir_ej / "tests"
            cmd_args = [
                *_generador(),
                str(modelo),
                "-o",
                str(destino),
                "--cantidad",
                str(cantidad),
                "--segundos",
                str(segundos),
            ]
            if sin_libfuzzer:
                cmd_args.append("--sin-libfuzzer")

            proc = subprocess.run(cmd_args, capture_output=True, text=True)
            if proc.returncode == 0:
                total_exitos += 1
                casos_in = list(destino.glob("*.in")) if destino.is_dir() else []
                tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", "[green]✓ Generado[/green]", f"{len(casos_in)} testcases en tests/")
            else:
                total_fallos += 1
                actualizar_verificacion(dir_ej, False)
                err_line = next((l for l in reversed(proc.stderr.strip().splitlines()) if l.strip()), "Error de ejecución")
                tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", "[red]✗ Fallo[/red]", f"{err_line[:60]} (no-verificado)")
                fallos_info.append({
                    "id": ej.id,
                    "tema": ej.tema,
                    "dir": dir_ej,
                    "tipo": "Fallo",
                    "error": proc.stderr.strip() or f"Código de retorno {proc.returncode}",
                })
                if fail_fast:
                    progress.advance(task)
                    break

            progress.advance(task)

    console.print(tabla)
    console.print(f"\n[bold]Resumen:[/bold] [green]{total_exitos} completados[/green] · "
                  f"[yellow]{total_omitidos} omitidos[/yellow] · [red]{total_fallos} fallidos[/red]")

    if log_fallos:
        _escribir_log_fallos(log_fallos, fallos_info, len(candidatos), total_exitos, total_omitidos, total_fallos)
        console.print(f"[yellow]📝 Reporte de fallos guardado en:[/yellow] {log_fallos}")

    raise typer.Exit(code=0 if total_fallos == 0 else 1)



