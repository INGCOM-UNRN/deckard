"""CLI de deckard: banco de ejercicios, guías, verificación, fuzzing y exportación multiformato.

Paquete partido de un único `cli.py` de 4.336 líneas (DECKARD-D0201) en
módulos temáticos bajo `deckard/cli/`. `_shared.py` concentra la app raíz,
los sub-apps de typer y los helpers compartidos; cada módulo de acá abajo
solo necesita importarse una vez para registrar sus comandos.
"""

from deckard.cli._shared import app  # noqa: F401  (punto de entrada, ver pyproject [project.scripts])

from deckard.cli import (  # noqa: F401  (el import registra los comandos vía sus decoradores)
    init,
    bank,
    show,
    verify,
    audit,
    tag,
    compose,
    fuzz,
    export,
    guide,
    spec,
    harness_pack,
    bank_reports,
    export_extra,
    quality_checks,
    improve,
    qol_a,
    qol_b,
)
