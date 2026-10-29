"""`deckard exercise cubrir`: casos de un ejercicio de funciones con tyrell y la solución de la cátedra (Ola 32)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import typer

from rich.console import Console

from deckard.cli._shared import _resolver_dir_ejercicio, console
from deckard.cli.agrupacion import exercise_app

err_console = Console(stderr=True)


@exercise_app.command("cubrir")
def cubrir_cmd(
    ejercicios: List[str] = typer.Argument(..., help="Ids (o carpetas) de ejercicios de funciones del banco."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco (también organizado por tema)."),
    sin_cobertura: bool = typer.Option(False, "--sin-cobertura", help="Sólo la suite de la especificación (sin `tyrell cubrir`, que necesita dietrich y gcov)."),
    regenerar_specs: bool = typer.Option(False, "--regenerar-specs", help="Volver a proponer las especificaciones de tyrell (pisa las revisadas)."),
    as_json: bool = typer.Option(False, "--json", help="Salida JSON."),
) -> None:
    """Genera tests/funciones/ (driver, especificaciones de tyrell y casos .in/.out) desde los prototipos
    y la solución de la cátedra. Las especificaciones existentes se respetan: revisalas y volvé a correr."""
    from deckard.core.bank import cargar_ejercicio
    from deckard.core.cubrir import NoAutomatizable, generar

    informes: List[Dict[str, Any]] = []
    for eid in ejercicios:
        try:
            dir_ej = _resolver_dir_ejercicio(eid, banco)
            ej = cargar_ejercicio(dir_ej)
            res = generar(dir_ej, ej, cobertura=not sin_cobertura, regenerar_specs=regenerar_specs)
            informes.append({"id": ej.id, "ok": True, "casos": res.casos, "descartados": res.descartados,
                             "cobertura": res.cobertura, "carpeta": str(dir_ej / "tests" / "funciones")})
        except (NoAutomatizable, typer.BadParameter) as exc:
            informes.append({"id": eid, "ok": False, "motivo": str(exc)})
    if as_json:
        print(json.dumps({"ejercicios": informes}, indent=2, ensure_ascii=False))
    else:
        for inf in informes:
            if inf["ok"]:
                total = sum(inf["casos"].values())
                desc = sum(len(v) for v in inf["descartados"].values())
                medida = "con cobertura" if all(inf["cobertura"].values()) else "sin cobertura de ramas"
                console.print(f"[green]✓[/green] {inf['id']}: {total} casos ({medida})"
                              + (f", {desc} descartados por comportamiento indefinido en la solución" if desc else ""))
            else:
                err_console.print(f"[yellow]⏸[/yellow] {inf['id']}: {inf['motivo']}")
    if not any(i["ok"] for i in informes):
        raise typer.Exit(code=1)
