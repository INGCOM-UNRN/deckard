"""`deckard exercise cubrir`: driver de funciones y casos con tyrell (Ola 32)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from deckard.core.bank import cargar_ejercicio
from deckard.core.cubrir import (NoAutomatizable, constantes_comparadas, driver_c, especificacion, FuncionDriver,
                                 funciones_driver,
                                 funciones_de_relleno, generar, Parametro, solucion_sin_main)
from deckard.core.models import Ejercicio, FuncionSpec

YAML = """id: abs-y-signo
titulo: Valor absoluto y signo
tema: funciones
bloom: 2
minutos_estimados: 10
funciones:
- {nombre: absoluto, retorno: int, parametros: int n}
- {nombre: es_par, retorno: bool, parametros: int n}
- {nombre: promedio, retorno: double, parametros: 'int a, int b'}
"""
SOLUCION = """#include <stdbool.h>
#include <stdio.h>
int absoluto(int n) { return n < 0 ? -n : n; }
bool es_par(int n) { return n % 2 == 0; }
double promedio(int a, int b) { return (a + b) / 2.0; }
int main(void) { printf("%d\\n", absoluto(-3)); return 0; }
"""


def _ejercicio(tmp_path: Path) -> Path:
    d = tmp_path / "banco" / "funciones" / "abs-y-signo"
    d.mkdir(parents=True)
    (d / "ejercicio.yaml").write_text(YAML, encoding="utf-8")
    (d / "solucion.c").write_text(SOLUCION, encoding="utf-8")
    return d


def test_driver_compila_con_la_solucion_y_responde(tmp_path):
    if shutil.which("gcc") is None:
        pytest.skip("requiere gcc")
    d = _ejercicio(tmp_path)
    driver = tmp_path / "driver.c"
    driver.write_text(driver_c(cargar_ejercicio(d)), encoding="utf-8")
    fuente = solucion_sin_main(d / "solucion.c", tmp_path / "solucion.c")
    subprocess.run(["gcc", "-std=c11", "-Wall", "-Werror", str(fuente), str(driver), "-o", str(tmp_path / "b")], check=True)
    salida = subprocess.run([str(tmp_path / "b")], input="absoluto -7\nes_par 4\npromedio 3 4\n",
                            capture_output=True, text=True).stdout
    assert salida == "7\n1\n3.5000\n"


def test_parametros_no_escalares_no_se_automatizan():
    ej = Ejercicio(id="x", titulo="X", tema="t", bloom=1, minutos_estimados=5,
                   funciones=[{"nombre": "sumar", "retorno": "int", "parametros": "const int *v"}])
    with pytest.raises(NoAutomatizable, match="no es escalar"):
        driver_c(ej)


@pytest.mark.skipif(shutil.which("tyrell") is None or shutil.which("gcc") is None, reason="requiere tyrell y gcc")
def test_generar_respeta_las_especificaciones_revisadas(tmp_path):
    d = _ejercicio(tmp_path)
    res = generar(d, cargar_ejercicio(d), cobertura=False)
    casos = d / "tests" / "funciones"
    assert (casos / "driver.c").is_file() and set(res.casos) == {"absoluto", "es_par", "promedio"}
    assert all(n > 0 for n in res.casos.values())
    assert (casos / "absoluto_01.out").read_text() == str(abs(int((casos / "absoluto_01.in").read_text().split()[1]))) + "\n"
    spec = casos / "tyrell" / "absoluto.yaml"
    spec.write_text(spec.read_text().replace("min_val: -10", "min_val: 5"), encoding="utf-8")
    generar(d, cargar_ejercicio(d), cobertura=False)  # no pisa la especificación revisada
    assert all(int(f.read_text().split()[1]) >= 5 for f in casos.glob("absoluto_*.in"))


RELLENO = """int ejecutar_algo(int val)
{
    /* relleno */
    if (val <= 0) return 0;
    return val * 2;
}
"""
requiere_herramientas = pytest.mark.skipif(shutil.which("tyrell") is None or shutil.which("gcc") is None,
                                           reason="requiere tyrell y gcc")


def _ejercicio_con(tmp_path: Path, funciones: str, solucion: str) -> Path:
    d = tmp_path / "ej"
    d.mkdir()
    (d / "ejercicio.yaml").write_text("id: ej\ntitulo: Ej\ntema: funciones\nbloom: 2\nminutos_estimados: 10\n"
                                      f"funciones:\n{funciones}", encoding="utf-8")
    (d / "enunciado.md").write_text("# Ej\n", encoding="utf-8")
    (d / "solucion.c").write_text(solucion, encoding="utf-8")
    return d


def test_reconoce_el_relleno_y_no_una_funcion_parecida():
    assert funciones_de_relleno(RELLENO) == {"ejecutar_algo"}
    assert funciones_de_relleno("int doble(int val)\n{\n    return val * 2;\n}\n") == set()


def test_una_solucion_de_relleno_no_genera_casos(tmp_path):
    d = _ejercicio_con(tmp_path, "- {nombre: ejecutar_algo, retorno: int, parametros: int val}\n",
                       RELLENO + "int main(void) { return 0; }\n")
    with pytest.raises(NoAutomatizable, match="relleno"):
        generar(d, cargar_ejercicio(d), cobertura=False)
    assert not (d / "tests").exists()


@requiere_herramientas
def test_omite_el_relleno_y_lo_no_escalar_pero_prueba_el_resto(tmp_path):
    d = _ejercicio_con(tmp_path, "- {nombre: ejecutar_algo, retorno: int, parametros: int val}\n"
                                 "- {nombre: suma, retorno: int, parametros: 'const int *v'}\n"
                                 "- {nombre: siguiente, retorno: int, parametros: int n}\n",
                       RELLENO + "int suma(const int *v) { return v[0]; }\n"
                                 "int siguiente(int n) { return n + 1; }\nint main(void) { return 0; }\n")
    res = generar(d, cargar_ejercicio(d), cobertura=False)
    assert set(res.casos) == {"siguiente"} and res.omitidas == ["ejecutar_algo", "suma"]


@requiere_herramientas
def test_void_con_escalares_compara_lo_que_imprime(tmp_path):
    d = _ejercicio_con(tmp_path, "- {nombre: mostrar, retorno: void, parametros: int n}\n",
                       '#include <stdio.h>\nvoid mostrar(int n) { printf("<%d>\\n", n); }\n'
                       "int main(void) { return 0; }\n")
    generar(d, cargar_ejercicio(d), cobertura=False)
    casos = d / "tests" / "funciones"
    entrada = (casos / "mostrar_01.in").read_text().split()[1]
    assert (casos / "mostrar_01.out").read_text() == f"<{entrada}>\n"


@requiere_herramientas
def test_la_solucion_puede_incluir_cabeceras_del_ejercicio(tmp_path):
    d = _ejercicio_con(tmp_path, "- {nombre: tope, retorno: int, parametros: int n}\n",
                       '#include "tope.h"\nint tope(int n) { return n > TOPE ? TOPE : n; }\n'
                       "int main(void) { return 0; }\n")
    (d / "tope.h").write_text("#define TOPE 10\nint tope(int n);\n", encoding="utf-8")
    assert generar(d, cargar_ejercicio(d), cobertura=False).casos["tope"] > 0


def test_el_rango_alcanza_las_constantes_de_la_solucion():
    constantes = constantes_comparadas("if (x >= 75 && y != -20) { /* > 9999 */ } switch (x) { case 100: break; } "
                                       "if (z < 100000) {}")
    assert constantes == [-20, 75, 100]
    con_signo = FuncionDriver("f", "int", [Parametro("int", "x")])
    regla = especificacion(None, con_signo, constantes=constantes)["rules"][0]
    assert (regla["min_val"], regla["max_val"]) == (-21, 101)
    sin_signo = FuncionDriver("f", "int", [Parametro("unsigned int", "x")])
    assert especificacion(None, sin_signo, constantes=constantes)["rules"][0]["min_val"] == 0
    logico = FuncionDriver("f", "int", [Parametro("bool", "x")])
    assert especificacion(None, logico, constantes=constantes)["rules"][0]["max_val"] == 1


@pytest.mark.skipif(any(shutil.which(h) is None for h in ("tyrell", "dietrich", "gcc")),
                    reason="requiere tyrell, dietrich y gcc")
def test_la_medida_de_ramas_no_cuenta_el_main_ni_los_test_de_la_solucion(tmp_path):
    d = _ejercicio_con(tmp_path, "- {nombre: tramo, retorno: int, parametros: int n}\n",
                       "#include <assert.h>\nint tramo(int n) { if (n >= 75) { return 2; } return 1; }\n"
                       "void test_tramo(void) { assert(tramo(80) == 2); }\n"
                       "int main(int argc, char **argv) { if (argc > 5) { return 1; } return 0; }\n")
    res = generar(d, cargar_ejercicio(d))
    assert res.ramas == {"tomadas": 2, "totales": 2}


def _ej_con(parametros, retorno="int", nombre="f"):
    return Ejercicio(id="prueba", titulo="Prueba", tema="arreglos", bloom=1, minutos_estimados=5,
                     funciones=[FuncionSpec(nombre=nombre, retorno=retorno, parametros=parametros)])


def _correr(tmp_path, ej, solucion, entrada):
    driver = tmp_path / "driver.c"
    fuente = tmp_path / "solucion.c"
    binario = tmp_path / "prog"
    driver.write_text(driver_c(ej), encoding="utf-8")
    fuente.write_text(solucion, encoding="utf-8")
    subprocess.run(["gcc", "-std=c11", "-Wall", "-Werror", str(driver), str(fuente), "-o", str(binario)], check=True)
    return subprocess.run([str(binario)], input=entrada, capture_output=True, text=True, check=True).stdout


@pytest.mark.skipif(shutil.which("gcc") is None, reason="requiere gcc")
def test_un_arreglo_con_su_largo_se_lee_y_se_escribe_despues_de_la_llamada(tmp_path):
    solucion = ("int f(int v[], int n)\n{\n    int suma = 0;\n    for (int i = 0; i < n; i++) { suma += v[i]; v[i] = 0; }\n"
                "    return suma;\n}\n")
    assert _correr(tmp_path, _ej_con("int v[], int n"), solucion, "f 3 1 2 3\nf 0\n") == "6\n0 0 0\n0\n\n"


@pytest.mark.skipif(shutil.which("gcc") is None, reason="requiere gcc")
def test_un_arreglo_const_no_se_vuelve_a_escribir(tmp_path):
    solucion = "double f(const double *datos, size_t cant, int k)\n{\n    return cant ? datos[0] * k : 0;\n}\n"
    ej = _ej_con("const double *datos, size_t cant, int k", "double")
    assert _correr(tmp_path, ej, "#include <stddef.h>\n" + solucion, "f 2 1.5 9 2\n") == "3.0000\n"


@pytest.mark.skipif(shutil.which("gcc") is None, reason="requiere gcc")
def test_enteros_de_ancho_fijo(tmp_path):
    solucion = "#include <stdint.h>\nuint16_t f(uint32_t x)\n{\n    return (uint16_t)(x + 1);\n}\n"
    assert _correr(tmp_path, _ej_con("uint32_t x", "uint16_t"), solucion, "f 65535\nf 2\n") == "0\n3\n"


@pytest.mark.parametrize("parametros", [
    "int v[], int buscado",   # el nombre no dice que sea el largo
    "int *a, int *b, int n",  # dos punteros: no se sabe cuál es de entrada
    "int v[]",
    "char s[], int n",        # una cadena no es un arreglo numérico
    "int **m, int n",
    "punto_t *p, int n",
])
def test_lo_que_no_se_sabe_leer_sigue_sin_automatizarse(parametros):
    with pytest.raises(NoAutomatizable):
        driver_c(_ej_con(parametros))


def test_la_especificacion_de_un_arreglo_pide_el_largo_y_no_una_regla_para_el(tmp_path):
    fn = funciones_driver(_ej_con("int v[], int n, int k"))[0]
    datos = especificacion(_ej_con("int v[], int n, int k"), fn)
    assert datos["format_template"] == "f {v_n} {v} {k}\n"
    assert [r["name"] for r in datos["rules"]] == ["v", "k"] and datos["rules"][0]["type"] == "array"


@requiere_herramientas
def test_generar_cubre_una_funcion_con_arreglo(tmp_path):
    d = _ejercicio_con(tmp_path, "- {nombre: maximo, retorno: int, parametros: 'const int v[], int n'}\n",
                       "int maximo(const int v[], int n)\n{\n    int m = 0;\n"
                       "    for (int i = 0; i < n; i++) { if (v[i] > m) { m = v[i]; } }\n    return m;\n}\n"
                       "int main(void) { return 0; }\n")
    res = generar(d, cargar_ejercicio(d), cobertura=False)
    assert res.casos["maximo"] > 0
    entradas = sorted((d / "tests" / "funciones").glob("maximo_*.in"))
    linea = entradas[0].read_text(encoding="utf-8").split()
    assert linea[0] == "maximo" and int(linea[1]) == len(linea) - 2
