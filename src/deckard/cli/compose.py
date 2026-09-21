"""Comando `compose`: composición de guías a partir de una GuiaSpec."""

from __future__ import annotations

from pathlib import Path

from rich.table import Table
import typer
import yaml

from deckard.core.bank import (
    componer_guia,
)
from deckard.core.models import GuiaSpec

from deckard.cli._shared import (
    app,
    console,
    _leer_yaml,
)

# ---------------------------------------------------------------------------
# compose
# ---------------------------------------------------------------------------


@app.command()
def compose(
    spec_file: Path = typer.Argument(..., exists=True, help="guia.yaml con nombre/duración/temas."),
    banco: Path = typer.Option(Path("banco"), "--banco"),
) -> None:
    """Compone una guía balanceada por carga cognitiva y taxonomía de Bloom."""
    spec = GuiaSpec(**_leer_yaml(spec_file))
    seleccion = componer_guia(banco, spec)

    tabla = Table(title=f"{seleccion.guia} — {len(seleccion.ejercicios)} ejercicios · "
                        f"{seleccion.minutos_totales}/{int(spec.duracion_min * spec.margen_carga)} min útiles")
    tabla.add_column("#", justify="right")
    tabla.add_column("ejercicio", style="cyan")
    tabla.add_column("tema")
    tabla.add_column("bloom", justify="center")
    tabla.add_column("min", justify="right")
    for i, e in enumerate(seleccion.ejercicios, 1):
        tabla.add_row(str(i), e.id, e.tema, f"B{int(e.bloom)}", str(e.minutos_estimados))
    console.print(tabla)
    console.print(f"Distribución Bloom: {seleccion.distribucion_bloom}")

    slug = spec.nombre.replace(' ', '_').lower()
    dir_guia = Path("guias") / slug
    dir_guia.mkdir(parents=True, exist_ok=True)
    salida = dir_guia / "guia.yaml"
    with open(salida, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "nombre": seleccion.guia,
            "minutos_totales": seleccion.minutos_totales,
            "distribucion_bloom": seleccion.distribucion_bloom,
            "ejercicios": [{"id": e.id, "minutos": e.minutos_estimados,
                            "bloom": int(e.bloom), "tema": e.tema}
                           for e in seleccion.ejercicios],
        }, f, allow_unicode=True, sort_keys=False)
    console.print(f"[green]✓ Guía escrita[/green] en {salida}")


