"""Visualizador y navegador interactivo CLI / Rich para el banco de ejercicios en Deckard."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from deckard.core.models import Ejercicio


def mostrar_vista_resumen_ejercicios(ejercicios: List[Tuple[Path, Ejercicio]], console: Optional[Console] = None) -> None:
    """Imprime una tabla interactiva con detalles de Bloom, tags, tiempo y estado de verificación."""
    cons = console or Console()
    
    tabla = Table(title="📚 Catálogo Interactivo del Banco de Ejercicios", border_style="cyan", show_header=True)
    tabla.add_column("ID / Slug", style="bold cyan", no_wrap=True)
    tabla.add_column("Título", style="white")
    tabla.add_column("Bloom", style="magenta", justify="center")
    tabla.add_column("Tiempo", justify="right", style="yellow")
    tabla.add_column("Tags", style="green")
    tabla.add_column("Verificado", justify="center")

    for dir_p, ej in ejercicios:
        verif_str = "[bold green]✓[/bold green]" if ej.verificado else "[dim red]✗[/dim red]"
        tiempo_str = f"{ej.tiempo_estimado} min"
        tags_str = ", ".join(ej.tags[:3]) if ej.tags else "-"
        tabla.add_row(ej.id, ej.titulo, ej.nivel.name, tiempo_str, tags_str, verif_str)

    cons.print(tabla)


def mostrar_detalle_ejercicio(ejercicio: Ejercicio, dir_p: Path, console: Optional[Console] = None) -> None:
    """Muestra una ficha detallada con enunciado renderizado y starter code."""
    cons = console or Console()
    
    header = f"[bold cyan]{ejercicio.id}[/bold cyan] — [bold white]{ejercicio.titulo}[/bold white]\n" \
             f"Nivel Bloom: [magenta]{ejercicio.nivel.value}[/magenta] | Tiempo: [yellow]{ejercicio.tiempo_estimado} min[/yellow] | Tags: [green]{', '.join(ejercicio.tags)}[/green]"
    
    cons.print(Panel(header, title="Detalle del Ejercicio", border_style="cyan"))
    
    # Enunciado
    cons.print("\n[bold]📖 Enunciado:[/bold]")
    cons.print(Panel(Markdown(ejercicio.enunciado or "_Sin enunciado_"), border_style="dim"))
    
    # Starter code si existe
    if ejercicio.starter_code:
        cons.print("\n[bold]💻 Starter Code:[/bold]")
        from rich.syntax import Syntax
        cons.print(Syntax(ejercicio.starter_code, "c", theme="monokai", line_numbers=True))
