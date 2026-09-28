"""Auditor dinámico de soluciones modelo contra Sanitizers (AddressSanitizer y UBSan)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Optional

from deckard.core.models import Ejercicio


@dataclass
class ResultadoSanitizer:
    ejercicio: str
    ok: bool
    leak_detected: bool = False
    ub_detected: bool = False
    error_compilacion: bool = False
    detalle: str = ""

    @property
    def marca(self) -> str:
        return "✓" if self.ok else "✗"


def _compilar_con_daedalus(archivos: list[Path], binario: Path, extra_flags: list[str]) -> Optional[tuple[bool, str]]:
    try:
        from daedalus.core.compiler import compilar_archivos
    except ImportError:
        return None  # sin el extra `ecosistema` se usa el camino propio
    res = compilar_archivos(archivos, binario_salida=binario, flags_adicionales=extra_flags)
    return res.exito, res.stderr_crudo


def auditar_solucion_sanitizers(
    dir_ejercicio: Path,
    ej: Optional[Ejercicio] = None,
    timeout: int = 20,
) -> ResultadoSanitizer:
    """Compila y ejecuta la solución con -fsanitize=address,undefined para auditar fugas y UB."""
    from deckard.core.bank import cargar_ejercicio

    if ej is None:
        try:
            ej = cargar_ejercicio(dir_ejercicio)
        except Exception as e:
            return ResultadoSanitizer(
                ejercicio=dir_ejercicio.name,
                ok=False,
                error_compilacion=True,
                detalle=f"Error cargando ejercicio: {e}",
            )

    solucion_path = dir_ejercicio / "solucion.c"
    if not solucion_path.is_file():
        # Intentar extraer solucion_c de ej
        if not ej.solucion_c.strip():
            return ResultadoSanitizer(
                ejercicio=ej.id,
                ok=False,
                error_compilacion=True,
                detalle="No se encontró solucion.c ni contenido solucion_c.",
            )

    gcc = shutil.which("gcc")
    if not gcc:
        return ResultadoSanitizer(
            ejercicio=ej.id,
            ok=False,
            error_compilacion=True,
            detalle="gcc no está disponible en el entorno.",
        )

    with tempfile.TemporaryDirectory(prefix="deckard_asan_") as tmpdir:
        tmp_path = Path(tmpdir)

        # Copiar o escribir solución
        sol_c = tmp_path / "solucion.c"
        if solucion_path.is_file():
            sol_c.write_text(solucion_path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            sol_c.write_text(ej.solucion_c, encoding="utf-8")

        # Headers si existen
        for h in dir_ejercicio.glob("*.h"):
            shutil.copy(h, tmp_path / h.name)
        if ej.funciones and not (tmp_path / f"{ej.id}.h").exists():
            (tmp_path / f"{ej.id}.h").write_text(ej.generar_cabecera_c(), encoding="utf-8")

        # Harness de prueba
        harness_c = tmp_path / "harness.c"
        # Verificar si la solución tiene main()
        codigo_sol = sol_c.read_text(encoding="utf-8")
        tiene_main = "main(" in codigo_sol or "main (" in codigo_sol

        archivos_compilar = [str(sol_c)]

        if not tiene_main:
            # Generar un main de prueba invocando las funciones
            lineas_main = [
                f'#include "{ej.id}.h"',
                "#include <stdio.h>",
                "#include <stdlib.h>",
                "#include <stdbool.h>",
                "int main(void) {",
            ]
            if ej.tests_funciones:
                for tf in ej.tests_funciones:
                    if tf.codigo:
                        lineas_main.append(f"    {tf.codigo}")
                    elif tf.args is not None:
                        lineas_main.append(f"    {tf.funcion}({tf.args});")
            elif ej.funciones:
                for fn in ej.funciones:
                    params = fn.parametros.strip()
                    if not params or params == "void":
                        lineas_main.append(f"    {fn.nombre}();")
            lineas_main.append("    return 0;")
            lineas_main.append("}")
            harness_c.write_text("\n".join(lineas_main), encoding="utf-8")
            archivos_compilar.append(str(harness_c))

        binario = tmp_path / "bin_asan"
        archivos_c_paths = [Path(p) for p in archivos_compilar]
        daed_res = _compilar_con_daedalus(
            archivos_c_paths,
            binario,
            ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g", "-O1"]
        )

        usa_asan = True
        if daed_res is not None:
            ok, stderr = daed_res
            if not ok:
                if "cannot find" in stderr and ("libasan" in stderr or "libubsan" in stderr):
                    usa_asan = False
                    daed_fb = _compilar_con_daedalus(archivos_c_paths, binario, ["-g", "-O1"])
                    if daed_fb is not None and not daed_fb[0]:
                        return ResultadoSanitizer(
                            ejercicio=ej.id,
                            ok=False,
                            error_compilacion=True,
                            detalle=f"Error de compilación: {daed_fb[1][:200]}",
                        )
                else:
                    return ResultadoSanitizer(
                        ejercicio=ej.id,
                        ok=False,
                        error_compilacion=True,
                        detalle=f"Error de compilación con sanitizers: {stderr[:200]}",
                    )
        else:
            cmd_comp = [
                gcc,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer",
                "-g",
                "-O1",
                *archivos_compilar,
                "-o",
                str(binario),
                "-lm",
            ]
            proc_comp = subprocess.run(cmd_comp, capture_output=True, text=True)
            if proc_comp.returncode != 0:
                if "cannot find" in proc_comp.stderr and ("libasan" in proc_comp.stderr or "libubsan" in proc_comp.stderr):
                    # Fallback sin sanitizers dinamicos
                    usa_asan = False
                    cmd_comp_fb = [
                        gcc,
                        "-std=c11",
                        "-Wall",
                        "-Wextra",
                        "-g",
                        "-O1",
                        *archivos_compilar,
                        "-o",
                        str(binario),
                        "-lm",
                    ]
                    proc_comp_fb = subprocess.run(cmd_comp_fb, capture_output=True, text=True)
                    if proc_comp_fb.returncode != 0:
                        return ResultadoSanitizer(
                            ejercicio=ej.id,
                            ok=False,
                            error_compilacion=True,
                            detalle=f"Error de compilación: {proc_comp_fb.stderr[:200]}",
                        )
                else:
                    return ResultadoSanitizer(
                        ejercicio=ej.id,
                        ok=False,
                        error_compilacion=True,
                        detalle=f"Error de compilación con sanitizers: {proc_comp.stderr[:200]}",
                    )

        # Ejecutar binario
        # Si hay archivos de entrada en tests/*.in, ejecutar con el primer caso
        tests_in = list((dir_ejercicio / "tests").glob("*.in")) if (dir_ejercicio / "tests").is_dir() else []
        input_bytes = None
        if tests_in:
            input_bytes = tests_in[0].read_bytes()

        env_asan = {
            **subprocess.os.environ,
            "ASAN_OPTIONS": "detect_leaks=1:abort_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1",
        }

        try:
            proc_run = subprocess.run(
                [str(binario)],
                input=input_bytes,
                capture_output=True,
                timeout=timeout,
                env=env_asan,
            )
        except subprocess.TimeoutExpired:
            return ResultadoSanitizer(
                ejercicio=ej.id,
                ok=False,
                detalle="Timeout durante la ejecución con sanitizers.",
            )

        salida_err = proc_run.stderr.decode("utf-8", errors="replace") if isinstance(proc_run.stderr, bytes) else str(proc_run.stderr)
        
        leak = "LeakSanitizer" in salida_err or "detected memory leaks" in salida_err
        ub = "runtime error:" in salida_err or "UndefinedBehaviorSanitizer" in salida_err
        segv = "AddressSanitizer:" in salida_err or proc_run.returncode != 0

        if leak or ub or segv:
            primer_error = next(
                (l.strip() for l in salida_err.splitlines() if "runtime error:" in l or "ERROR: AddressSanitizer" in l or "detected memory leaks" in l),
                f"Código de salida no cero ({proc_run.returncode})",
            )
            return ResultadoSanitizer(
                ejercicio=ej.id,
                ok=False,
                leak_detected=leak,
                ub_detected=ub,
                detalle=f"Falla detectada por Sanitizer: {primer_error}",
            )

        msg = (
            "Limpio: sin pérdidas de memoria (ASan) ni comportamientos indefinidos (UBSan)."
            if usa_asan
            else "Limpio: ejecución y compilación exitosas (libasan no disponible en el entorno)."
        )
        return ResultadoSanitizer(
            ejercicio=ej.id,
            ok=True,
            detalle=msg,
        )
