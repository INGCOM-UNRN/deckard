"""Prácticas generadas desde la guía: librerías, targets del docente y dredd.mk (Ola 30)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from deckard.core.init_tests import generar_suite_tests_c
from deckard.core.models import CasoTestFuncion, Ejercicio, FuncionSpec, LibreriaGuia, TargetDocente
from deckard.core.practica import (
    PracticaInvalida, armar_practica, catedra_desactualizadas, comparar, escribir_dredd, leer_guia, validar,
)

PLANTILLA_REAL = Path(__file__).resolve().parents[2] / "plantillas" / "plantilla-TP"

TP_FALSO = """#!/usr/bin/env bash
# tp.sh mínimo para las pruebas: add-lib y add-ex como los de plantilla-TP.
set -e
case "$1" in
  add-lib) mkdir -p "libs/$2"; echo "// $2" > "libs/$2/$2.h"; echo "lib $2 ${3:-plana}" > "libs/$2/origen.txt" ;;
  add-ex) mkdir -p "ejercicios/$2"; echo "int main(void) { return 0; }" > "ejercicios/$2/main.c";
          echo "#include \\"p1_test.h\\"" > "ejercicios/$2/prueba.c"; echo "LIB_NAME ?= ${3//,/ }" > "ejercicios/$2/Makefile" ;;
esac
"""


def _ejercicio(banco: Path, eid: str, **extra) -> None:
    d = banco / eid
    d.mkdir(parents=True)
    datos = {"id": eid, "titulo": eid, "tema": "funciones", "bloom": 3, "minutos": 10, **extra}
    (d / "ejercicio.yaml").write_text(yaml.safe_dump(datos), encoding="utf-8")
    (d / "enunciado.md").write_text(f"Enunciado de {eid}\n", encoding="utf-8")
    (d / "solucion.c").write_text("int secreto(void) { return 42; }\n", encoding="utf-8")
    (d / f"{eid}.h").write_text("int sumar(int a, int b);\n", encoding="utf-8")


@pytest.fixture
def entorno(tmp_path):
    banco, guias, plantilla = tmp_path / "banco", tmp_path / "guias", tmp_path / "plantilla"
    _ejercicio(banco, "suma", funciones=[{"nombre": "sumar", "retorno": "int", "parametros": "int a, int b"}],
               tests_funciones=[{"nombre": "t", "funcion": "sumar", "args": "2, 3", "retorno_esperado": "5"}],
               tests_ocultos=[{"nombre": "o", "funcion": "sumar", "args": "-1, 1", "retorno_esperado": "0"}])
    _ejercicio(banco, "lista", rol_familia="libreria")
    (banco / "suma" / "tests").mkdir()
    (banco / "suma" / "tests" / "caso_01.in").write_text("2 3\n", encoding="utf-8")
    (plantilla / "libs" / "p1_test").mkdir(parents=True)
    (plantilla / "libs" / "p1_test" / ".catedra").write_text('commit = "x"\n', encoding="utf-8")
    (plantilla / "libs" / "ejemplo").mkdir()
    (plantilla / "ejercicios" / "viejo").mkdir(parents=True)
    (plantilla / "tp.sh").write_text(TP_FALSO, encoding="utf-8")
    (plantilla / "README.md").write_text("plantilla\n", encoding="utf-8")
    (guias / "anterior").mkdir(parents=True)
    (guias / "anterior" / "guia.yaml").write_text(yaml.safe_dump({
        "nombre": "Anterior", "ejercicios": ["lista"],
        "librerias": [{"nombre": "arreglos", "origen": "crear"}]}), encoding="utf-8")
    guia = guias / "actual" / "guia.yaml"
    guia.parent.mkdir()
    guia.write_text(yaml.safe_dump({
        "nombre": "Actual",
        "ejercicios": [{"id": "suma", "librerias": ["cadenas", "arreglos"]}, {"id": "lista"}],
        "librerias": [{"nombre": "cadenas", "origen": "crear", "descripcion": "Cadenas"},
                      {"nombre": "pila", "origen": "crear", "ejercicio": "lista"},
                      {"nombre": "arreglos", "origen": "reutilizar", "guia": "anterior"}],
        "targets_docente": [
            {"nombre": "ocultas", "descripcion": "Casos ocultos", "tipo": "pruebas_ocultas", "ejercicios": ["suma"], "peso": 30},
            {"nombre": "memoria", "descripcion": "Memoria", "tipo": "memcheck", "peso": 20, "visible": True},
            {"nombre": "estilo", "descripcion": "Estilo", "receta": ["ripley check . --json > r.json"],
             "produce": "json", "archivo": "r.json"}],
    }), encoding="utf-8")
    return banco, guias, plantilla, guia


def test_modelos_validan_cada_origen_y_tipo():
    with pytest.raises(ValueError, match="repositorio"):
        LibreriaGuia(nombre="x", origen="catedra")
    with pytest.raises(ValueError, match="commit completo"):
        LibreriaGuia(nombre="x", origen="catedra", repositorio="r", commit="main")
    with pytest.raises(ValueError, match="falta `guia`"):
        LibreriaGuia(nombre="x", origen="reutilizar")
    with pytest.raises(ValueError, match="falta `receta`"):
        TargetDocente(nombre="x", descripcion="d")
    with pytest.raises(ValueError, match="falta `archivo`"):
        TargetDocente(nombre="x", descripcion="d", tipo="memcheck", produce="json")
    assert TargetDocente(nombre="x", descripcion="d", tipo="fallos").target_make == "dredd-x"


def test_validar(entorno):
    banco, guias, _, ruta = entorno
    guia = leer_guia(ruta)
    errores, avisos = validar(guia, banco, guias)
    assert errores == [] and avisos == []
    datos = yaml.safe_load(ruta.read_text())
    datos["ejercicios"][0]["librerias"].append("inventada")
    datos["librerias"][2]["guia"] = "no-existe"
    ruta.write_text(yaml.safe_dump(datos), encoding="utf-8")
    errores, _ = validar(leer_guia(ruta), banco, guias)
    assert any("«inventada», que la guía no declara" in e for e in errores)
    assert any("guía «no-existe», que no existe" in e for e in errores)


def test_guia_con_librerias_mal_declaradas(tmp_path):
    ruta = tmp_path / "guia.yaml"
    ruta.write_text(yaml.safe_dump({"ejercicios": ["a"], "librerias": [{"nombre": "x", "origen": "catedra"}]}))
    with pytest.raises(PracticaInvalida, match=r"librerias\[1\]: .*repositorio"):
        leer_guia(ruta)


def test_armar_practica(entorno, tmp_path):
    banco, guias, plantilla, ruta = entorno
    destino = tmp_path / "practica"
    armar_practica(leer_guia(ruta), banco, str(plantilla), destino)
    assert (destino / "libs" / "p1_test" / ".catedra").is_file()           # la cátedra se conserva
    assert not (destino / "libs" / "ejemplo").exists() and not (destino / "ejercicios" / "viejo").exists()
    assert (destino / "libs" / "cadenas" / "origen.txt").read_text().startswith("lib cadenas plana")
    assert (destino / "libs" / "pila" / "pila.h").is_file()                # API desde el ejercicio del banco
    assert not (destino / "libs" / "arreglos").exists()                    # reutilizada: la trae el alumno
    suma = destino / "ejercicios" / "suma"
    assert (suma / "enunciado.md").is_file() and (suma / "tests" / "caso_01.in").is_file()
    assert not (suma / "solucion.c").exists() and not (suma / "ejercicio.yaml").exists()
    assert "TEST_SUITE_BEGIN_ARGS" in (suma / "prueba.c").read_text()       # generada desde tests_funciones
    assert (suma / "Makefile").read_text().strip() == "LIB_NAME ?= cadenas arreglos"
    leeme = (destino / "PRACTICA.md").read_text()
    assert "./tp.sh add-lib arreglos" in leeme and "Memoria" in leeme and "Casos ocultos" not in leeme


def test_regenerar_muestra_las_diferencias(entorno, tmp_path):
    banco, _, plantilla, ruta = entorno
    a, b = tmp_path / "a", tmp_path / "b"
    armar_practica(leer_guia(ruta), banco, str(plantilla), a)
    assert comparar(a, a).vacias
    (banco / "suma" / "enunciado.md").write_text("Nuevo\n", encoding="utf-8")
    armar_practica(leer_guia(ruta), banco, str(plantilla), b)
    (a / "ejercicios" / "suma" / "mio.c").write_text("// del alumno\n")
    dif = comparar(b, a)
    assert dif.cambiados == ["ejercicios/suma/enunciado.md"] and dif.quitados == ["ejercicios/suma/mio.c"]


def test_dredd_mk(entorno, tmp_path):
    banco, _, _, ruta = entorno
    escritos = escribir_dredd(leer_guia(ruta), banco, tmp_path / "dredd")
    mk = (tmp_path / "dredd" / "dredd.mk").read_text()
    assert "dredd-ocultas:" in mk and "ifneq ($(filter $(DREDD_EJERCICIO),suma),)" in mk
    assert "dredd-memoria:" in mk and "ifneq ($(filter $(DREDD_EJERCICIO),suma lista),)" in mk
    assert "\tripley check . --json > r.json" in mk and "$(MAKE) --no-print-directory memcheck" in mk
    oculta = tmp_path / "dredd" / ".dredd" / "ocultas" / "suma.c"
    assert oculta in escritos and "sumar(-1, 1)" in oculta.read_text()
    desc = json.loads((tmp_path / "dredd" / "targets.json").read_text())
    assert desc["ejercicios"] == ["suma", "lista"]
    assert [(t["target"], t["peso"], t["visible"]) for t in desc["targets"]] == [
        ("dredd-ocultas", 30, False), ("dredd-memoria", 20, True), ("dredd-estilo", 0, False)]


def test_catedra_desactualizadas(entorno):
    guia = leer_guia(entorno[3])
    guia.librerias.append(LibreriaGuia(nombre="p1_test", origen="catedra", repositorio="r", commit="a" * 40))
    assert catedra_desactualizadas(guia, consultar=lambda r: "a" * 40) == []
    assert "ya va por bbbbbbbbbbbb" in catedra_desactualizadas(guia, consultar=lambda r: "b" * 40)[0]


def test_suite_p1_test_generada_usa_las_macros_reales():
    """N-DECKARD-07: INIT_TESTS, ASSERT_EQ y ASSERT_TRUE con mensaje no existen en p1_test."""
    ej = Ejercicio(id="s", titulo='Con "comillas"', tema="t", bloom=3, minutos=5,
                   funciones=[FuncionSpec(nombre="f", retorno="int", parametros="int x")],
                   tests_funciones=[CasoTestFuncion(nombre="a", funcion="f", args="1", retorno_esperado="2"),
                                    CasoTestFuncion(nombre="b", funcion="f", codigo="assert(f(0) == 1);")])
    codigo = generar_suite_tests_c(ej, framework="p1_test")
    assert "INIT_TESTS" not in codigo and "ASSERT_EQ(" not in codigo and "assert(" not in codigo
    assert 'TEST_SUITE_BEGIN_ARGS("Con \\"comillas\\"", argc, argv);' in codigo
    assert "ASSERT_TRUE(f(0) == 1);" in codigo


@pytest.mark.skipif(not (PLANTILLA_REAL / "tp.sh").is_file() or shutil.which("make") is None
                    or shutil.which("gcc") is None, reason="requiere plantilla-TP al lado, make y gcc")
def test_con_la_plantilla_real(entorno, tmp_path):
    """Con plantilla-TP de verdad: la práctica compila y las pruebas generadas pasan con una solución."""
    banco, guias, _, ruta = entorno
    destino = tmp_path / "practica"
    armar_practica(leer_guia(ruta), banco, str(PLANTILLA_REAL), destino)
    (destino / "ejercicios" / "suma" / "suma.c").write_text('#include "suma.h"\nint sumar(int a, int b) { return a + b; }\n')
    # arreglos se reutiliza de la guía anterior: la trae el alumno (acá, una librería plana nueva).
    subprocess.run(["bash", "tp.sh", "add-lib", "arreglos"], cwd=destino, check=True, capture_output=True)
    subprocess.run(["make", "-s", "librerias"], cwd=destino, check=False, capture_output=True)
    res = subprocess.run(["make", "-s", "test"], cwd=destino / "ejercicios" / "suma", capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    escribir_dredd(leer_guia(ruta), banco, destino)   # dredd.mk y .dredd/ en la raíz, como al corregir
    res = subprocess.run(["make", "-s", "dredd-ocultas"], cwd=destino / "ejercicios" / "suma", capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    res = subprocess.run(["make", "-s", "dredd-ocultas"], cwd=destino / "ejercicios" / "lista", capture_output=True, text=True)
    assert "no aplica a lista" in res.stdout
