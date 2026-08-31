"""Calibrador de carga horaria acumulada y balance pedagógico en guías de Deckard."""

from __future__ import annotations

from typing import Dict, List, Tuple
from rich.console import Console
from rich.table import Table

from deckard.core.models import Ejercicio, GuiaSpec, NivelBloom


def calcular_estadisticas_carga(ejercicios: List[Ejercicio]) -> Dict[str, Any]:
    """Calcula totales de tiempo y desglose por nivel Bloom."""
    minutos_totales = sum(ej.minutos_estimados for ej in ejercicios)
    horas_totales = round(minutos_totales / 60.0, 2)

    bloom_counts: Dict[str, int] = {b.name: 0 for b in NivelBloom}
    bloom_minutos: Dict[str, int] = {b.name: 0 for b in NivelBloom}

    for ej in ejercicios:
        bloom_counts[ej.bloom.name] += 1
        bloom_minutos[ej.bloom.name] += ej.minutos_estimados

    return {
        "total_ejercicios": len(ejercicios),
        "minutos_totales": minutos_totales,
        "horas_totales": horas_totales,
        "desglose_bloom_cantidades": bloom_counts,
        "desglose_bloom_minutos": bloom_minutos,
    }


def auditar_carga_horaria(
    ejercicios: List[Ejercicio],
    max_horas_semanales: float = 6.0,
    console: Optional[Console] = None,
) -> Tuple[bool, str]:
    """Audita si la guía excede las horas máximas permitidas y reporta en consola."""
    stats = calcular_estadisticas_carga(ejercicios)
    horas = stats["horas_totales"]
    excede = horas > max_horas_semanales

    cons = console or Console()
    tabla = Table(title=f"⏱️ Auditoría de Carga Horaria y Balance Pedagógico", border_style="cyan")
    tabla.add_column("Métrica / Nivel Bloom", style="bold white")
    tabla.add_column("Cantidad", justify="center")
    tabla.add_column("Tiempo Estimado", justify="right")
    tabla.add_column("Proporción", justify="right")

    for b in NivelBloom:
        cant = stats["desglose_bloom_cantidades"][b.name]
        mins = stats["desglose_bloom_minutos"][b.name]
        pct = (mins / stats["minutos_totales"] * 100) if stats["minutos_totales"] > 0 else 0
        tabla.add_row(f"Nivel {b.value}: {b.name}", str(cant), f"{mins} min", f"{pct:.1f}%")

    tabla.add_section()
    estado_tiempo = f"[bold red]{horas} h (EXCEDE límite {max_horas_semanales} h)[/bold red]" if excede else f"[bold green]{horas} h (Dentro de {max_horas_semanales} h)[/bold green]"
    tabla.add_row("[bold]Total Acumulado[/bold]", f"[bold]{stats['total_ejercicios']}[/bold]", estado_tiempo, "100.0%")

    cons.print(tabla)
    if excede:
        msg = f"La guía acumula {horas} horas pedagógicas, superando el límite configurado de {max_horas_semanales} horas."
        cons.print(f"[bold red]⚠️ Alerta de Sobrecarga:[/bold red] {msg}")
        return False, msg
    else:
        msg = f"Carga horaria balanceada ({horas} h <= {max_horas_semanales} h)."
        cons.print(f"[bold green]✓ Carga Aceptable:[/bold green] {msg}")
        return True, msg
