"""`deckard exercise cubrir`: driver de funciones y casos con tyrell (Ola 32)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from deckard.core.bank import cargar_ejercicio
from deckard.core.cubrir import NoAutomatizable, driver_c, generar, solucion_sin_main
from deckard.core.models import Ejercicio

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
                   funciones=[{"nombre": "sumar", "retorno": "int", "parametros": "const int *v, size_t n"}])
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
