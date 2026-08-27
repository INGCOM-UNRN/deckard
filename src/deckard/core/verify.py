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


from deckard.core.bank import cargar_ejercicio
from deckard.core.function_runner import ejecutar_tests_funciones


def verificar_ejercicio(
    dir_ejercicio: Path,
    ruta_ripley: Optional[str] = None,
    timeout: int = 120,
) -> ResultadoVerify:
    """Valida la solución modelo ejecutando tests granulares de funciones y ripley check."""
    dir_ejercicio = Path(dir_ejercicio)

    # 1. Tests granulares de funciones (si están especificados en el ejercicio)
    try:
        ej = cargar_ejercicio(dir_ejercicio)
    except Exception:
        ej = None

    detalle_fn = ""
    if ej and ej.tests_funciones:
        res_fn = ejecutar_tests_funciones(ej, dir_ejercicio, timeout=min(timeout, 30))
        if not res_fn.ok:
            return ResultadoVerify(
                ejercicio=ej.id,
                ok=False,
                detalle=f"Fallo en tests de funciones: {res_fn.detalle}",
            )
        detalle_fn = f"Tests C: {res_fn.detalle}"

    # Si es un ejercicio puramente de funciones y no tiene tests I/O en tests/
    tests_io = list((dir_ejercicio / "tests").glob("*.in")) if (dir_ejercicio / "tests").is_dir() else []
    if ej and ej.tiene_funciones and not tests_io:
        return ResultadoVerify(dir_ejercicio.name, True, detalle_fn)

    # 2. Verificación estática / dinámica con Ripley (para ejercicios con main() o tests I/O)
    ripley = ruta_ripley or shutil.which("ripley")
    if ripley is None:
        candidato = Path(__file__).resolve()
        for padre in [candidato] + list(candidato.parents):
            pyz = padre / "bin" / "ripley.pyz"
            if pyz.is_file():
                ripley = f"{shutil.which('python3') or 'python3'} {pyz}"
                break

    if not ripley:
        if detalle_fn:
            return ResultadoVerify(dir_ejercicio.name, True, detalle_fn)
        return ResultadoVerify(dir_ejercicio.name, False, "ripley no está disponible (PATH ni bin/ripley.pyz)")

    cmd = f"{ripley} check {dir_ejercicio}"
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ResultadoVerify(dir_ejercicio.name, False, "timeout de ripley")

    salida = proc.stdout + proc.stderr
    ok = proc.returncode == 0 and "Fallo" not in salida and "✗" not in salida.splitlines()[-1]
    resumen = next((l for l in reversed(salida.strip().splitlines()) if l.strip()), "")

    if detalle_fn:
        resumen_final = f"{detalle_fn} · {resumen[:100]}"
    else:
        resumen_final = resumen[:160]

    return ResultadoVerify(dir_ejercicio.name, ok, resumen_final)
