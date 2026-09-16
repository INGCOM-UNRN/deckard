"""Motor de ejecución y compilación de tests granulares sobre invocación de funciones C."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from deckard.core.models import CasoTestFuncion, Ejercicio


@dataclass
class DetalleCasoFuncion:
    nombre: str
    funcion: str
    ok: bool
    mensaje: str = ""


@dataclass
class ResultadoTestsFunciones:
    ok: bool
    total: int
    exitosos: int
    fallidos: int
    detalle: str
    casos: List[DetalleCasoFuncion] = field(default_factory=list)


def generar_codigo_harness_c(ejercicio: Ejercicio, solucion_c: str) -> str:
    """Genera un archivo fuente C autocontenido para compilar y ejecutar los tests de funciones."""
    cabeceras_fns = []
    for fn in ejercicio.funciones:
        cabeceras_fns.append(fn.firma)

    lineas = [
        "/* Harness de pruebas de funciones generado por Deckard */",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <stdbool.h>",
        "#include <stdint.h>",
        "#include <string.h>",
        "#include <assert.h>",
        "#include <math.h>",
        "#include <stddef.h>",
        "",
        "/* Implementación / Solución bajo prueba */",
        "#define main __deckard_unused_main",
        solucion_c,
        "#undef main",
        "",
        "/* Casos de prueba individuales */",
    ]

    casos_defs = []
    for i, caso in enumerate(ejercicio.tests_funciones, 1):
        fn_test_name = f"__deckard_test_{i}_{re.sub(r'[^a-zA-Z0-9_]', '_', caso.nombre)}"
        casos_defs.append((fn_test_name, caso))

        c_body = []
        c_body.append(f"static int {fn_test_name}(char* err_buf, size_t err_size) {{")
        c_body.append("    (void)err_buf; (void)err_size;")

        if caso.codigo and caso.codigo.strip():
            # Bloque C directo
            c_body.append("    /* Bloque de aserciones */")
            for linea_cod in caso.codigo.strip().splitlines():
                c_body.append(f"    {linea_cod}")
        else:
            # Generar invocación con args y retorno/postcondiciones
            args_str = caso.args or ""
            fn_call = f"{caso.funcion}({args_str})"
            if caso.retorno_esperado is not None:
                c_body.append(f"    if (!({fn_call} == ({caso.retorno_esperado}))) {{")
                c_body.append(f"        snprintf(err_buf, err_size, \"Retorno esperado '{caso.retorno_esperado}' no coincide.\");")
                c_body.append("        return 1;")
                c_body.append("    }")
            else:
                c_body.append(f"    {fn_call};")

            if caso.postcondiciones:
                c_body.append(f"    if (!({caso.postcondiciones})) {{")
                c_body.append(f"        snprintf(err_buf, err_size, \"Fallo de postcondicion: {caso.postcondiciones}\");")
                c_body.append("        return 1;")
                c_body.append("    }")

        c_body.append("    return 0; /* OK */")
        c_body.append("}")
        c_body.append("")
        lineas.append("\n".join(c_body))

    # Main runner
    lineas.append("int main(void) {")
    lineas.append("    int exitosos = 0;")
    lineas.append("    int fallidos = 0;")
    lineas.append("    char err[256];")
    lineas.append("")

    for fn_test_name, caso in casos_defs:
        lineas.append(f"    memset(err, 0, sizeof(err));")
        lineas.append(f"    if ({fn_test_name}(err, sizeof(err)) == 0) {{")
        lineas.append(f'        printf("[TEST_OK]|%s|%s\\n", "{caso.nombre}", "{caso.funcion}");')
        lineas.append("        exitosos++;")
        lineas.append("    } else {")
        lineas.append(f'        printf("[TEST_FAIL]|%s|%s|%s\\n", "{caso.nombre}", "{caso.funcion}", err[0] ? err : "Fallo de asercion");')
        lineas.append("        fallidos++;")
        lineas.append("    }")

    lineas.append("")
    lineas.append('    printf("=== RESUMEN: %d/%d exitosos ===\\n", exitosos, exitosos + fallidos);')
    lineas.append("    return fallidos == 0 ? 0 : 1;")
    lineas.append("}")
    lineas.append("")

    return "\n".join(lineas)


def _compilar_con_daedalus(src_file: Path, bin_file: Path) -> Optional[Tuple[bool, str]]:
    try:
        from daedalus.core.compiler import compilar_archivos
        res = compilar_archivos([src_file], binario_salida=bin_file)
        return res.exito, res.stderr_crudo
    except ImportError:
        import sys
        sibling = Path(__file__).resolve().parents[4] / "daedalus" / "src"
        if sibling.is_dir() and str(sibling) not in sys.path:
            sys.path.insert(0, str(sibling))
            try:
                from daedalus.core.compiler import compilar_archivos
                res = compilar_archivos([src_file], binario_salida=bin_file)
                return res.exito, res.stderr_crudo
            except ImportError:
                return None
        return None


def ejecutar_tests_funciones(
    ejercicio: Ejercicio,
    dir_ejercicio: Optional[Path] = None,
    timeout: int = 15,
) -> ResultadoTestsFunciones:
    """Compila y ejecuta el arnés de tests de funciones C sobre la solución del ejercicio."""
    if not ejercicio.tests_funciones:
        return ResultadoTestsFunciones(
            ok=True,
            total=0,
            exitosos=0,
            fallidos=0,
            detalle="No hay tests de funciones declarados.",
            casos=[],
        )

    solucion_c = ejercicio.solucion_c
    if not solucion_c and dir_ejercicio and (dir_ejercicio / "solucion.c").is_file():
        solucion_c = (dir_ejercicio / "solucion.c").read_text(encoding="utf-8")

    if not solucion_c:
        return ResultadoTestsFunciones(
            ok=False,
            total=len(ejercicio.tests_funciones),
            exitosos=0,
            fallidos=len(ejercicio.tests_funciones),
            detalle="Sin solución modelo (solucion.c) para ejecutar tests de funciones.",
            casos=[],
        )

    codigo_harness = generar_codigo_harness_c(ejercicio, solucion_c)

    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        return ResultadoTestsFunciones(
            ok=False,
            total=len(ejercicio.tests_funciones),
            exitosos=0,
            fallidos=len(ejercicio.tests_funciones),
            detalle="No se encontró compilador C (gcc o clang) en el sistema.",
            casos=[],
        )

    with tempfile.TemporaryDirectory() as td:
        src_file = Path(td) / "harness.c"
        bin_file = Path(td) / "harness_bin"
        src_file.write_text(codigo_harness, encoding="utf-8")

        # 1. Compilar delegando en Daedalus con fallback a GCC
        daed_res = _compilar_con_daedalus(src_file, bin_file)
        if daed_res is not None:
            comp_ok, comp_err = daed_res
            if not comp_ok:
                err_line = next((l for l in comp_err.splitlines() if "error:" in l or "fatal error:" in l), comp_err[:160])
                return ResultadoTestsFunciones(
                    ok=False,
                    total=len(ejercicio.tests_funciones),
                    exitosos=0,
                    fallidos=len(ejercicio.tests_funciones),
                    detalle=f"Error de compilación en tests de funciones: {err_line.strip()}",
                    casos=[],
                )
        else:
            cmd_compile = [
                compiler,
                "-Wall",
                "-Wextra",
                "-std=c11",
                str(src_file),
                "-o",
                str(bin_file),
                "-lm",
            ]
            proc_comp = subprocess.run(cmd_compile, capture_output=True, text=True)
            if proc_comp.returncode != 0:
                err_line = next((l for l in proc_comp.stderr.splitlines() if "error:" in l or "fatal error:" in l), proc_comp.stderr[:160])
                return ResultadoTestsFunciones(
                    ok=False,
                    total=len(ejercicio.tests_funciones),
                    exitosos=0,
                    fallidos=len(ejercicio.tests_funciones),
                    detalle=f"Error de compilación en tests de funciones: {err_line.strip()}",
                    casos=[],
                )

        # 2. Ejecutar binario
        try:
            proc_run = subprocess.run([str(bin_file)], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return ResultadoTestsFunciones(
                ok=False,
                total=len(ejercicio.tests_funciones),
                exitosos=0,
                fallidos=len(ejercicio.tests_funciones),
                detalle="Timeout en la ejecución de tests de funciones (bucle infinito o bloqueo).",
                casos=[],
            )

        # 3. Parsear resultados por caso
        casos_res: List[DetalleCasoFuncion] = []
        exitosos = 0
        fallidos = 0

        for line in proc_run.stdout.splitlines():
            line = line.strip()
            if line.startswith("[TEST_OK]"):
                parts = line.split("|")
                nom = parts[1] if len(parts) > 1 else "caso"
                fn = parts[2] if len(parts) > 2 else ""
                casos_res.append(DetalleCasoFuncion(nombre=nom, funcion=fn, ok=True))
                exitosos += 1
            elif line.startswith("[TEST_FAIL]"):
                parts = line.split("|")
                nom = parts[1] if len(parts) > 1 else "caso"
                fn = parts[2] if len(parts) > 2 else ""
                msg = parts[3] if len(parts) > 3 else "Fallo"
                casos_res.append(DetalleCasoFuncion(nombre=nom, funcion=fn, ok=False, mensaje=msg))
                fallidos += 1

        total = len(ejercicio.tests_funciones)
        if total == 0:
            total = exitosos + fallidos

        if proc_run.returncode != 0 and fallidos == 0 and exitosos == 0:
            # Fallo general (ej. abort por assert)
            fallidos = total
            detalle = f"Fallo en ejecución (código {proc_run.returncode}): {proc_run.stderr.strip() or 'Abort'}"
        else:
            detalle = f"{exitosos}/{total} tests de función aprobados"

        return ResultadoTestsFunciones(
            ok=(proc_run.returncode == 0 and fallidos == 0 and exitosos == total),
            total=total,
            exitosos=exitosos,
            fallidos=fallidos,
            detalle=detalle,
            casos=casos_res,
        )
