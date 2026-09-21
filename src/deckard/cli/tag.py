"""Sub-app `tag`: gestión y consulta de etiquetas del banco."""

from __future__ import annotations

from pathlib import Path
from typing import List

from rich.table import Table
import typer


from deckard.cli._shared import (
    console,
    tag_app,
)

# ---------------------------------------------------------------------------
# tag app
# ---------------------------------------------------------------------------


@tag_app.command("list")
def tag_list_cmd(
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
) -> None:
    """Lista todas las etiquetas presentes en el banco de ejercicios."""
    from deckard.core.tags import listar_tags_banco

    tag_map = listar_tags_banco(banco)
    if not tag_map:
        console.print(f"[yellow]No se encontraron etiquetas en '{banco}'.[/yellow]")
        return

    tabla = Table(title=f"Etiquetas del Banco ({len(tag_map)} encontradas)")
    tabla.add_column("Tag / Etiqueta", style="bold cyan")
    tabla.add_column("Ejercicios", justify="right")
    tabla.add_column("IDs de Ejemplo", style="dim")

    for tag_name, eids in tag_map.items():
        ejemplos = ", ".join(eids[:6]) + ("..." if len(eids) > 6 else "")
        tabla.add_row(tag_name, str(len(eids)), ejemplos)

    console.print(tabla)


@tag_app.command("add")
def tag_add_cmd(
    patron: str = typer.Argument(..., help="ID o patrón comodín de ejercicios (ej: 'invertir-*', '*')."),
    tags: List[str] = typer.Argument(..., help="Etiquetas a agregar."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
) -> None:
    """Agrega una o más etiquetas a ejercicios del banco."""
    from deckard.core.tags import agregar_tags_a_ejercicios

    tags_flat: List[str] = []
    for t in tags:
        tags_flat.extend([x.strip() for x in t.split(",") if x.strip()])

    modificados = agregar_tags_a_ejercicios(banco, patron, tags_flat)
    if not modificados:
        console.print(f"[yellow]No se modificaron ejercicios para '{patron}'.[/yellow]")
        return

    console.print(f"[green]✓ Tags agregados a {len(modificados)} ejercicio(s):[/green]")
    for eid, t_list in modificados:
        console.print(f"  • [cyan]{eid}[/cyan] -> tags: [dim]{', '.join(t_list)}[/dim]")


@tag_app.command("remove")
def tag_remove_cmd(
    patron: str = typer.Argument(..., help="ID o patrón comodín de ejercicios."),
    tags: List[str] = typer.Argument(..., help="Etiquetas a remover."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
) -> None:
    """Remueve una o más etiquetas de ejercicios del banco."""
    from deckard.core.tags import remover_tags_de_ejercicios

    tags_flat: List[str] = []
    for t in tags:
        tags_flat.extend([x.strip() for x in t.split(",") if x.strip()])

    modificados = remover_tags_de_ejercicios(banco, patron, tags_flat)
    if not modificados:
        console.print(f"[yellow]No se modificaron ejercicios para '{patron}'.[/yellow]")
        return

    console.print(f"[green]✓ Tags removidos de {len(modificados)} ejercicio(s):[/green]")
    for eid, t_list in modificados:
        console.print(f"  • [cyan]{eid}[/cyan] -> tags: [dim]{', '.join(t_list)}[/dim]")


