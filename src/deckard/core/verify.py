"""deckard verify — valida la solución modelo de un ejercicio con ripley.

Delegación pura: deckard nunca compila por su cuenta; invoca `ripley check`
(ubicable vía PATH o --ripley) sobre el directorio del ejercicio y traduce el
resultado al estado del banco (verificado / fallido).
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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

    if not ripley:
        if detalle_fn:
            return ResultadoVerify(dir_ejercicio.name, True, detalle_fn)
        return ResultadoVerify(dir_ejercicio.name, False, "ripley no está disponible en PATH")

    if isinstance(ripley, str):
        cmd = shlex.split(ripley) + ["check", str(dir_ejercicio), "--format", "json"]
    else:
        cmd = [str(ripley), "check", str(dir_ejercicio), "--format", "json"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ResultadoVerify(dir_ejercicio.name, False, "timeout de ripley")

    ok = False
    resumen = ""
    try:
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            errores = data.get("errors") or data.get("fallos") or []
            ok = (proc.returncode == 0) and not errores and data.get("ok", True)
            resumen = data.get("summary") or data.get("resumen") or ("✓ OK" if ok else "✗ Fallo en verificación")
    except Exception:
        salida = (proc.stdout + proc.stderr).strip()
        lineas = [l for l in salida.splitlines() if l.strip()]
        ultimo = lineas[-1] if lineas else ""
        ok = (proc.returncode == 0) and ("Fallo" not in salida) and ("✗" not in ultimo)
        resumen = ultimo if lineas else ("✓ OK" if ok else "✗ Fallo")

    if detalle_fn:
        resumen_final = f"{detalle_fn} · {resumen[:100]}"
    else:
        resumen_final = resumen[:160]

    return ResultadoVerify(dir_ejercicio.name, ok, resumen_final)
