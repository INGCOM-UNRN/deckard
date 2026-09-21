"""Sub-app `bank`: listado del banco de ejercicios."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.table import Table
import typer

from deckard.core.bank import (
    buscar_ejercicios,
)

from deckard.cli._shared import (
    app,
    console,
    bank_app,
)

# ---------------------------------------------------------------------------
# bank app (list / show)
# ---------------------------------------------------------------------------

@bank_app.command("list")
def bank_list(
    patron: Optional[str] = typer.Argument(None, help="Filtro o comodín (ej: 'invertir-*', 'punteros/*')."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-t", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", min=1, max=5, help="Filtrar por nivel de Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", "-T", help="Filtrar por etiqueta/tag."),
    verificado: Optional[bool] = typer.Option(None, "--verificado/--no-verificado", help="Filtrar por estado de verificación."),
    as_json: bool = typer.Option(False, "--json", help="Salida en formato JSON estructurado."),
) -> None:
    """Lista los ejercicios del banco con su nivel, carga, tags y filtros."""
    items = buscar_ejercicios(banco, patron=patron, tema=tema, bloom=bloom, tag=tag, verificado=verificado)
    total_min = sum(e.minutos_estimados for _, e in items)
    verificados_count = sum(1 for _, e in items if e.verificado)

    if as_json:
        data = {
            "total": len(items),
            "total_minutos": total_min,
            "verificados": verificados_count,
            "ejercicios": [
                {
                    "id": e.id,
                    "tema": e.tema,
                    "bloom": int(e.bloom),
                    "minutos": e.minutos_estimados,
                    "tags": e.tags or [],
                    "verificado": e.verificado,
                }
                for _, e in items
            ],
        }
        console.print_json(data=data)
        return

    tabla = Table(title=f"Banco de ejercicios ({len(items)} encontrados)")
    tabla.add_column("id", style="cyan")
    tabla.add_column("tema")
    tabla.add_column("bloom", justify="center")
    tabla.add_column("min", justify="right")
    tabla.add_column("tags", style="dim")
    tabla.add_column("verificado", justify="center")
    for _, e in items:
        tags_str = ", ".join(e.tags) if e.tags else "—"
        tabla.add_row(e.id, e.tema, f"B{int(e.bloom)} {e.bloom.name.lower()}",
                      str(e.minutos_estimados), tags_str, "✓" if e.verificado else "—")
    console.print(tabla)
    pct = (verificados_count / len(items) * 100) if items else 0
    console.print(f"[dim]{total_min} minutos totales ({total_min/60:.1f}h) · Verificados: {verificados_count}/{len(items)} ({pct:.0f}%)[/dim]")


@bank_app.command("organize")
@bank_app.command("reorganize")
@app.command("organize")
def bank_organize(
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco de ejercicios."),
    criterio: str = typer.Option(
        "bloom/tipo",
        "--by",
        "-b",
        "--criterio",
        help="Criterio de reorganización: 'bloom', 'tipo', 'bloom/tipo', 'tipo/bloom', 'tema/bloom', 'bloom/tema', 'tema/tipo', 'plano'.",
    ),
    destino: Optional[Path] = typer.Option(
        None,
        "--destino",
        "-d",
        help="Directorio de destino (por defecto, reorganiza dentro del mismo banco).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Simula la reorganización y muestra los movimientos sin modificar el disco.",
    ),
    copy: bool = typer.Option(
        False,
        "--copy",
        "-c",
        help="Copia los ejercicios al nuevo esquema en vez de moverlos.",
    ),
) -> None:
    """Reorganiza los ejercicios en carpetas según nivel de Bloom, tipo (funciones vs io) y/o tema."""
    from deckard.core.bank import reorganizar_banco

    if not banco.is_dir():
        console.print(f"[bold red]El directorio del banco no existe:[/bold red] {banco}")
        raise typer.Exit(code=1)

    movimientos = reorganizar_banco(
        banco=banco,
        criterio=criterio,
        dir_destino=destino,
        dry_run=dry_run,
        copy=copy,
    )

    if not movimientos:
        console.print(f"[yellow]No se encontraron ejercicios en '{banco}'.[/yellow]")
        return

    accion_verbo = "Copiado" if copy else "Movido"
    sim_tag = "[yellow](Simulación / Dry-run)[/yellow] " if dry_run else ""

    tabla = Table(title=f"{sim_tag}Reorganización del Banco (Criterio: {criterio})")
    tabla.add_column("Ejercicio", style="cyan")
    tabla.add_column("Bloom")
    tabla.add_column("Tipo")
    tabla.add_column("Origen", style="dim")
    tabla.add_column("Destino", style="green")
    tabla.add_column("Estado", justify="center")

    total_movidos = 0
    total_sin_cambio = 0

    for mov in movimientos:
        try:
            rel_orig = mov.origen.relative_to(banco).as_posix()
        except Exception:
            rel_orig = str(mov.origen)
        try:
            target_base = destino or banco
            rel_dest = mov.destino.relative_to(target_base).as_posix()
        except Exception:
            rel_dest = str(mov.destino)

        if mov.cambio:
            total_movidos += 1
            estado = f"[green]✓ {accion_verbo}[/green]" if not dry_run else "[yellow]→ Pendiente[/yellow]"
        else:
            total_sin_cambio += 1
            estado = "[dim]— En lugar[/dim]"

        tabla.add_row(
            mov.id,
            mov.bloom,
            f"[magenta]{mov.tipo}[/magenta]",
            rel_orig,
            rel_dest,
            estado,
        )

    console.print(tabla)
    console.print(
        f"\n[bold]Resumen:[/bold] [green]{total_movidos} {'a mover/copiar' if dry_run else 'reorganizados'}[/green] · "
        f"[dim]{total_sin_cambio} sin cambios[/dim] (Total: {len(movimientos)})"
    )


