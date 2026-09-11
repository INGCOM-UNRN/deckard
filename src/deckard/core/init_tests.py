"""Generación e inicialización de suites de prueba basadas en aserciones C (p1_test / assert)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from deckard.core.models import Ejercicio


def generar_suite_tests_c(ej: Ejercicio, framework: str = "p1_test") -> str:
    """Genera código fuente C para una suite de pruebas unitarias del ejercicio."""
    fw = framework.lower().strip()
    usa_p1 = "p1" in fw or "lib" in fw

    lineas: list[str] = []
    lineas.append("/* Test suite generada automáticamente por Deckard */")
    lineas.append("#include <stdio.h>")
    lineas.append("#include <stdlib.h>")
    lineas.append("#include <stdbool.h>")
    lineas.append("#include <string.h>")

    if usa_p1:
        lineas.append('#include "p1_test.h"')
    else:
        lineas.append("#include <assert.h>")

    lineas.append(f'#include "{ej.id}.h"')
    lineas.append("")

    funciones = ej.funciones
    tests_fn = ej.tests_funciones

    if not funciones and not tests_fn:
        # Template básico
        if usa_p1:
            lineas.append('TEST(test_inicial) {')
            lineas.append('    ASSERT_TRUE(true, "Verificación básica de inicialización");')
            lineas.append('}')
            lineas.append("")
            lineas.append('int main(void) {')
            lineas.append(f'    INIT_TESTS("{ej.titulo}");')
            lineas.append('    RUN_TEST(test_inicial);')
            lineas.append('    return TEST_REPORT();')
            lineas.append('}')
        else:
            lineas.append('void test_inicial(void) {')
            lineas.append('    assert(true);')
            lineas.append('    printf("  [OK] test_inicial pasado con éxito.\\n");')
            lineas.append('}')
            lineas.append("")
            lineas.append('int main(void) {')
            lineas.append(f'    printf("=== Suite: {ej.titulo} ===\\n");')
            lineas.append('    test_inicial();')
            lineas.append('    printf("Todos los tests pasaron exitosamente.\\n");')
            lineas.append('    return 0;')
            lineas.append('}')
        return "\n".join(lineas) + "\n"

    # Generar casos para cada función o tests_funciones definidos
    nombres_tests: list[str] = []

    if tests_fn:
        for i, tf in enumerate(tests_fn):
            nombre_t = f"test_{tf.funcion}_{i+1}"
            nombres_tests.append(nombre_t)
            if usa_p1:
                lineas.append(f"TEST({nombre_t}) {{")
                if tf.descripcion:
                    lineas.append(f"    /* {tf.descripcion} */")
                if tf.codigo:
                    for cl in tf.codigo.strip().splitlines():
                        lineas.append(f"    {cl}")
                elif tf.args is not None and tf.retorno_esperado is not None:
                    lineas.append(f"    ASSERT_EQ({tf.funcion}({tf.args}), {tf.retorno_esperado});")
                elif tf.args is not None:
                    lineas.append(f"    {tf.funcion}({tf.args});")
                if tf.postcondiciones:
                    lineas.append(f"    ASSERT_TRUE({tf.postcondiciones});")
                lineas.append("}")
            else:
                lineas.append(f"void {nombre_t}(void) {{")
                if tf.descripcion:
                    lineas.append(f"    /* {tf.descripcion} */")
                if tf.codigo:
                    for cl in tf.codigo.strip().splitlines():
                        lineas.append(f"    {cl}")
                elif tf.args is not None and tf.retorno_esperado is not None:
                    lineas.append(f"    assert({tf.funcion}({tf.args}) == {tf.retorno_esperado});")
                elif tf.args is not None:
                    lineas.append(f"    {tf.funcion}({tf.args});")
                if tf.postcondiciones:
                    lineas.append(f"    assert({tf.postcondiciones});")
                lineas.append(f'    printf("  [OK] {nombre_t}\\n");')
                lineas.append("}")
            lineas.append("")
    else:
        for fn in funciones:
            nombre_t = f"test_{fn.nombre}_basico"
            nombres_tests.append(nombre_t)
            if usa_p1:
                lineas.append(f"TEST({nombre_t}) {{")
                lineas.append(f"    /* Probar invocación básica de {fn.nombre} */")
                params = fn.parametros.strip()
                if not params or params == "void":
                    if fn.retorno == "void":
                        lineas.append(f"    {fn.nombre}();")
                        lineas.append('    ASSERT_TRUE(true, "Ejecución sin fallos");')
                    else:
                        lineas.append(f"    ASSERT_EQ({fn.nombre}(), 0);")
                else:
                    lineas.append(f"    // TODO: Configurar parámetros ({params}) y verificar resultado")
                    lineas.append('    ASSERT_TRUE(true, "Stub de test");')
                lineas.append("}")
            else:
                lineas.append(f"void {nombre_t}(void) {{")
                lineas.append(f"    /* Probar invocación básica de {fn.nombre} */")
                params = fn.parametros.strip()
                if not params or params == "void":
                    if fn.retorno == "void":
                        lineas.append(f"    {fn.nombre}();")
                    else:
                        lineas.append(f"    assert({fn.nombre}() == 0);")
                else:
                    lineas.append(f"    // TODO: Configurar parámetros ({params})")
                lineas.append(f'    printf("  [OK] {nombre_t}\\n");')
                lineas.append("}")
            lineas.append("")

    # Runner main
    if usa_p1:
        lineas.append("int main(void) {")
        lineas.append(f'    INIT_TESTS("{ej.titulo}");')
        for nt in nombres_tests:
            lineas.append(f"    RUN_TEST({nt});")
        lineas.append("    return TEST_REPORT();")
        lineas.append("}")
    else:
        lineas.append("int main(void) {")
        lineas.append(f'    printf("=== Suite de Pruebas: {ej.titulo} ===\\n");')
        for nt in nombres_tests:
            lineas.append(f"    {nt}();")
        lineas.append('    printf(">>> Todas las aserciones se cumplieron exitosamente. <<<\\n");')
        lineas.append("    return 0;")
        lineas.append("}")

    return "\n".join(lineas) + "\n"


def generar_makefile_test(ej: Ejercicio, framework: str = "p1_test") -> str:
    """Genera un Makefile auxiliar para compilar y correr la suite de tests."""
    usa_p1 = "p1" in framework.lower()
    cflags = "-Wall -Wextra -std=c11 -g"
    if usa_p1:
        cflags += " -I. -Iinclude -I../../include -I../include"
        libs = "-L. -Lbuild -L../../build -L../build -lp1_test"
    else:
        libs = ""

    return f"""# Makefile para tests de {ej.id}
CC ?= gcc
CFLAGS = {cflags}
LDFLAGS = {libs}

all: test

test: test_{ej.id}
\t./test_{ej.id}

test_{ej.id}: tests/test_{ej.id}.c {ej.id}.c
\t$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
\trm -f test_{ej.id} *.o
"""


def inicializar_tests_ejercicio(
    dir_ejercicio: Path,
    framework: str = "p1_test",
    sobrescribir: bool = False,
) -> Path:
    """Inicializa la carpeta tests/ y crea el archivo test_<id>.c en dir_ejercicio."""
    from deckard.core.bank import cargar_ejercicio
    ej = cargar_ejercicio(dir_ejercicio)

    tests_dir = dir_ejercicio / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    test_file = tests_dir / f"test_{ej.id}.c"
    if test_file.exists() and not sobrescribir:
        return test_file

    contenido = generar_suite_tests_c(ej, framework=framework)
    test_file.write_text(contenido, encoding="utf-8")

    # Header si no existe
    h_file = dir_ejercicio / f"{ej.id}.h"
    if not h_file.exists() and ej.funciones:
        h_file.write_text(ej.generar_cabecera_c(), encoding="utf-8")

    # Makefile auxiliar de tests si no existe
    mk_test = dir_ejercicio / "Makefile.test"
    if not mk_test.exists():
        mk_test.write_text(generar_makefile_test(ej, framework), encoding="utf-8")

    return test_file
