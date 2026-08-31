"""Auditor integral de calidad y completitud pedagógica de guías de ejercicios en Deckard."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table

from deckard.core.models import Ejercicio, GuiaSpec


def auditar_completitud_guia(
    ejercicios: List[Ejercicio],
    guia_spec: Optional[GuiaSpec] = None,
    console: Optional[Console] = None,
) -> Dict[str, Any]:
    """Audita completitud de enunciados, starter code, soluciones modelo y tests unitarios."""
    cons = console or Console()
    hallazgos: List[Dict[str, str]] = []

    tabla = Table(title="🔍 Auditoría de Calidad de la Guía de Ejercicios", border_style="cyan")
    tabla.add_column("Ejercicio ID", style="bold white")
    tabla.add_column("Enunciado", justify="center")
    tabla.add_column("Starter Code", justify="center")
    tabla.add_column("Solución C", justify="center")
    tabla.add_column("Tests Unitarios", justify="center")
    tabla.add_column("Observaciones", style="yellow")

    for ej in ejercicios:
        obs: List[str] = []

        # 1. Enunciado
        tiene_enunciado = bool(ej.enunciado_md and len(ej.enunciado_md.strip()) >= 20)
        enunc_str = "[green]✓ Completo[/green]" if tiene_enunciado else "[red]✗ Breve/Falta[/red]"
        if not tiene_enunciado:
            obs.append("Enunciado demasiado breve o ausente")

        # 2. Starter code
        tiene_starter = bool(ej.starter_code and len(ej.starter_code.strip()) >= 10)
        start_str = "[green]✓ Presente[/green]" if tiene_starter else "[yellow]— Opcional[/yellow]"

        # 3. Solución C
        tiene_solucion = bool(ej.solucion_c and len(ej.solucion_c.strip()) >= 15)
        sol_str = "[green]✓ Modelo OK[/green]" if tiene_solucion else "[red]✗ Falta Solución[/red]"
        if not tiene_solucion:
            obs.append("Sin solución modelo de cátedra")

        # 4. Tests
        cant_tests = len(ej.tests_funciones)
        tests_str = f"[green]✓ {cant_tests} tests[/green]" if cant_tests > 0 else "[yellow]0 tests[/yellow]"
        if cant_tests == 0 and ej.tiene_funciones:
            obs.append("Sin testcases para validar funciones")

        obs_str = "; ".join(obs) if obs else "[green]Todo correcto[/green]"
        tabla.add_row(ej.id, enunc_str, start_str, sol_str, tests_str, obs_str)

    cons.print(tabla)
    total_obs = sum(1 for ej in ejercicios if not (ej.enunciado_md and ej.solucion_c))
    return {
        "total_ejercicios": len(ejercicios),
        "ejercicios_con_observaciones": total_obs,
        "calidad_optima": total_obs == 0,
    }
