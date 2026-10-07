"""Los comandos sueltos de deckard, agrupados en sub-apps (N-DECKARD-02).

deckard tenía 64 comandos en el primer nivel (`deckard --help` era una lista de una pantalla y
media). Cada uno pasa a su grupo: `bank`, `verify`, `export`, `quality` y `exercise`. El nombre
anterior sigue andando, oculto en la ayuda y con un aviso en stderr, hasta que se retire.

La tabla se aplica después de registrar todos los comandos (el import de cada módulo los registra
con sus decoradores), así que los módulos no cambian.
"""

from __future__ import annotations

import functools
import sys
from typing import Dict, Tuple

import typer

from deckard.cli import _shared

quality_app = typer.Typer(name="quality", help="Calidad de consignas y bancos: terminología, tono, ambigüedad, ortografía, duplicados.", no_args_is_help=True)
exercise_app = typer.Typer(name="exercise", help="Crear y completar ejercicios: esqueletos, variantes, pruebas, rúbricas y diagramas.", no_args_is_help=True)
_shared.app.add_typer(quality_app, name="quality")
_shared.app.add_typer(exercise_app, name="exercise")

GRUPOS = {
    "bank": _shared.bank_app, "verify": _shared.verify_app, "export": _shared.export_app,
    "quality": quality_app, "exercise": exercise_app,
}

# nombre en el primer nivel → (grupo, nombre en el grupo)
REUBICACION: Dict[str, Tuple[str, str]] = {
    # bank
    "stats": ("bank", "stats"), "lint": ("bank", "lint"), "duplicate": ("bank", "duplicate"),
    "deps": ("bank", "deps"), "index": ("bank", "index"), "browse": ("bank", "browse"),
    "organize": ("bank", "organize"), "show": ("bank", "show"), "sync": ("bank", "sync"),
    "graph": ("bank", "graph"), "cache": ("bank", "cache"), "select-prereqs": ("bank", "select-prereqs"),
    "license-manager": ("bank", "license-manager"),
    # verify
    "fuzz": ("verify", "fuzz"), "audit": ("verify", "audit"), "test-harness": ("verify", "test-harness"),
    "audit-sanitizers": ("verify", "sanitizers"), "sanitizers": ("verify", "sanitizers"),
    "multiplex": ("verify", "multiplex"),
    # export
    "export-classroom": ("export", "classroom"), "publish-classroom": ("export", "publish-classroom"),
    "export-notebook": ("export", "notebook"), "export-moodle": ("export", "moodle"),
    "export-web": ("export", "web"), "export-anki": ("export", "anki"), "anki": ("export", "anki"),
    "export-hints": ("export", "hints"), "hints": ("export", "hints"), "to-md": ("export", "to-md"),
    "from-md": ("export", "from-md"), "bundle-offline": ("export", "bundle-offline"),
    "pack": ("export", "pack"), "pack-zip": ("export", "pack-zip"), "export-zip": ("export", "pack-zip"),
    "unpack": ("export", "unpack"),
    # quality
    "check-terms": ("quality", "terms"), "lint-consigna": ("quality", "consigna"), "check-tone": ("quality", "tone"),
    "check-ambiguity": ("quality", "ambiguity"), "audit-statements": ("quality", "statements"),
    "spellcheck": ("quality", "spellcheck"), "grammar": ("quality", "grammar"),
    "languagetool": ("quality", "languagetool"), "find-duplicates": ("quality", "duplicates"),
    "check-signatures": ("quality", "signatures"), "checklist": ("quality", "checklist"),
    "audit-guide": ("quality", "guide"), "check-load": ("quality", "load"),
    # exercise
    "new": ("exercise", "new"), "scaffold": ("exercise", "scaffold"), "variant": ("exercise", "variant"),
    "compose-variant": ("exercise", "compose-variant"), "init-tests": ("exercise", "init-tests"),
    "init-io-files": ("exercise", "init-io-files"), "acsl-tests": ("exercise", "acsl-tests"),
    "rubric": ("exercise", "rubric"), "failure-hints": ("exercise", "failure-hints"),
    "diagram-memory": ("exercise", "diagram-memory"), "diagram": ("exercise", "diagram"),
    "ascii-diagram": ("exercise", "ascii-diagram"), "diagram-ascii": ("exercise", "ascii-diagram"),
}


def _con_aviso(callback, viejo: str, nuevo: str):
    @functools.wraps(callback)
    def envoltorio(*args, **kwargs):
        print(f"Aviso: `deckard {viejo}` pasa a `deckard {nuevo}`; el nombre anterior se va a retirar.",
              file=sys.stderr)
        return callback(*args, **kwargs)
    return envoltorio


def aplicar() -> None:
    for info in list(_shared.app.registered_commands):
        destino = REUBICACION.get(info.name or "")
        if destino is None:
            continue
        grupo_nombre, nuevo = destino
        if info.callback is None:
            continue
        grupo = GRUPOS[grupo_nombre]
        if all(c.name != nuevo for c in grupo.registered_commands):
            grupo.command(nuevo, help=info.help)(info.callback)
        info.callback = _con_aviso(info.callback, info.name or "", f"{grupo_nombre} {nuevo}")
        info.hidden = True


aplicar()
