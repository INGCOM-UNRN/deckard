"""deckard verify — valida la solución modelo de un ejercicio con ripley.

Delegación pura: deckard nunca compila por su cuenta; invoca `ripley check`
(ubicable vía PATH o --ripley) sobre el directorio del ejercicio y traduce el
resultado al estado del banco (verificado / fallido).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResultadoVerify:
    ejercicio: str
    ok: bool
    detalle: str

    @property
    def marca(self) -> str:
        return "✓" if self.ok else "✗"


def verificar_ejercicio(dir_ejercicio: Path,
                        ruta_ripley: Optional[str] = None,
                        timeout: int = 120) -> ResultadoVerify:
    """Corre `ripley check <dir>` y devuelve el veredicto."""
    dir_ejercicio = Path(dir_ejercicio)
    ripley = ruta_ripley or shutil.which("ripley")
    if ripley is None:
        # último recurso: zipapp portable del entorno
        candidato = Path(__file__).resolve()
        for padre in [candidato] + list(candidato.parents):
            pyz = padre / "bin" / "ripley.pyz"
            if pyz.is_file():
                ripley = f"{shutil.which('python3') or 'python3'} {pyz}"
                break
    if not ripley:
        return ResultadoVerify(dir_ejercicio.name, False,
                               "ripley no está disponible (PATH ni bin/ripley.pyz)")

    cmd = f"{ripley} check {dir_ejercicio}"
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return ResultadoVerify(dir_ejercicio.name, False, "timeout de ripley")

    salida = proc.stdout + proc.stderr
    ok = proc.returncode == 0 and "Fallo" not in salida and "✗" not in salida.splitlines()[-1]
    resumen = next((l for l in reversed(salida.strip().splitlines()) if l.strip()), "")
    return ResultadoVerify(dir_ejercicio.name, ok, resumen[:160])
