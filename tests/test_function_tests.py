"""Tests para soporte de tests de invocación de funciones y especificación de firmas C en Deckard."""

from pathlib import Path
from unittest.mock import patch
import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import cargar_ejercicio, guardar_ejercicio
from deckard.core.function_runner import ejecutar_tests_funciones, generar_codigo_harness_c
from deckard.core.models import CasoTestFuncion, Ejercicio, FuncionSpec, NivelBloom

runner = CliRunner()


def test_funcion_spec_parsing():
    fn1 = FuncionSpec.parse("void invertir_vector(int* vec, size_t n);", descripcion="Invierte un vector")
    assert fn1.nombre == "invertir_vector"
    assert fn1.retorno == "void"
    assert fn1.parametros == "int* vec, size_t n"
    assert fn1.firma == "void invertir_vector(int* vec, size_t n);"
    assert fn1.descripcion == "Invierte un vector"

    fn2 = FuncionSpec.parse("int sumar(int a, int b)")
    assert fn2.nombre == "sumar"
    assert fn2.retorno == "int"
    assert fn2.parametros == "int a, int b"
    assert fn2.firma == "int sumar(int a, int b);"


def test_ejercicio_cabecera_y_esqueleto():
    ej = Ejercicio(
        id="ej-vector",
        titulo="Invertir Vector",
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=20,
        enunciado_md="Invertir vector",
        funciones=[
            FuncionSpec(nombre="invertir_vector", retorno="void", parametros="int* vec, size_t n", descripcion="Invierte in-place"),
            FuncionSpec(nombre="contar_pares", retorno="int", parametros="const int* vec, size_t n"),
        ],
    )
    header = ej.generar_cabecera_c()
    assert "#ifndef EJERCICIO_EJ_VECTOR_H" in header
    assert "void invertir_vector(int* vec, size_t n);" in header
    assert "int contar_pares(const int* vec, size_t n);" in header

    esqueleto = ej.generar_esqueleto_c()
    assert '#include "ej-vector.h"' in esqueleto
    assert "void invertir_vector(int* vec, size_t n)" in esqueleto
    assert "int contar_pares(const int* vec, size_t n)" in esqueleto


def test_guardar_y_cargar_ejercicio_con_funciones(tmp_path: Path):
    banco = tmp_path / "banco"
    banco.mkdir()

    ej = Ejercicio(
        id="calc-potencia",
        titulo="Potencia Entera",
        tema="aritmetica",
        bloom=NivelBloom.RECORDAR,
        minutos_estimados=15,
        enunciado_md="Calcular potencia",
        solucion_c="int potencia(int base, int exp) { int r = 1; while(exp--) r *= base; return r; }",
        funciones=[
            FuncionSpec(nombre="potencia", retorno="int", parametros="int base, int exp", descripcion="Calcula base^exp"),
        ],
        tests_funciones=[
            CasoTestFuncion(
                nombre="test_potencia_cero",
                funcion="potencia",
                codigo="assert(potencia(5, 0) == 1);",
            ),
            CasoTestFuncion(
                nombre="test_potencia_cubo",
                funcion="potencia",
                codigo="assert(potencia(2, 3) == 8);",
            ),
        ],
    )
    dir_ej = guardar_ejercicio(ej, banco)
    assert (dir_ej / "calc-potencia.h").is_file()

    ej_cargado = cargar_ejercicio(dir_ej)
    assert len(ej_cargado.funciones) == 1
    assert ej_cargado.funciones[0].nombre == "potencia"
    assert len(ej_cargado.tests_funciones) == 2
    assert ej_cargado.tests_funciones[0].nombre == "test_potencia_cero"


def test_ejecutar_tests_funciones_exitoso():
    ej = Ejercicio(
        id="sumador",
        titulo="Sumador Simple",
        tema="aritmetica",
        bloom=NivelBloom.RECORDAR,
        minutos_estimados=10,
        enunciado_md="Sumar",
        solucion_c="int sumar(int a, int b) { return a + b; }",
        funciones=[FuncionSpec(nombre="sumar", retorno="int", parametros="int a, int b")],
        tests_funciones=[
            CasoTestFuncion(nombre="test_suma_pos", funcion="sumar", codigo="assert(sumar(2, 3) == 5);"),
            CasoTestFuncion(nombre="test_suma_neg", funcion="sumar", codigo="assert(sumar(-2, 2) == 0);"),
        ],
    )
    res = ejecutar_tests_funciones(ej)
    assert res.ok is True
    assert res.total == 2
    assert res.exitosos == 2
    assert res.fallidos == 0
    assert "2/2 tests de función aprobados" in res.detalle


def test_ejecutar_tests_funciones_fallo():
    ej = Ejercicio(
        id="restador-fallido",
        titulo="Restador con Bug",
        tema="aritmetica",
        bloom=NivelBloom.RECORDAR,
        minutos_estimados=10,
        enunciado_md="Restar",
        solucion_c="int restar(int a, int b) { return a + b; /* Bug */ }",
        funciones=[FuncionSpec(nombre="restar", retorno="int", parametros="int a, int b")],
        tests_funciones=[
            CasoTestFuncion(nombre="test_resta_correcta", funcion="restar", codigo="assert(restar(5, 3) == 2);"),
        ],
    )
    res = ejecutar_tests_funciones(ej)
    assert res.ok is False
    assert res.fallidos > 0


def test_cli_new_con_funciones(tmp_path: Path):
    banco = tmp_path / "banco"
    res = runner.invoke(app, [
        "new", "invertir-arreglo",
        "--titulo", "Invertir Arreglo",
        "--tema", "arreglos",
        "--banco", str(banco),
        "-F", "void invertir(int* v, size_t n); int longitud(const int* v)",
    ])
    assert res.exit_code == 0
    dir_ej = banco / "invertir-arreglo"
    assert (dir_ej / "invertir-arreglo.h").is_file()
    ej = cargar_ejercicio(dir_ej)
    assert len(ej.funciones) == 2
    assert ej.funciones[0].nombre == "invertir"
    assert ej.funciones[1].nombre == "longitud"


def test_cli_show_con_funciones(tmp_path: Path):
    banco = tmp_path / "banco"
    banco.mkdir()
    ej = Ejercicio(
        id="fn-show",
        titulo="Test Show Funciones",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=15,
        enunciado_md="Consigna de punteros",
        funciones=[FuncionSpec(nombre="duplicar", retorno="void", parametros="int* p")],
        tests_funciones=[CasoTestFuncion(nombre="test_dup", funcion="duplicar", codigo="int x=2; duplicar(&x); assert(x==4);")],
    )
    guardar_ejercicio(ej, banco)

    res = runner.invoke(app, ["show", "fn-show", "--banco", str(banco), "-t"])
    assert res.exit_code == 0
    assert "duplicar" in res.stdout
    assert "test_dup" in res.stdout

    # Test raw
    res_raw = runner.invoke(app, ["show", "fn-show", "--banco", str(banco), "--raw", "-t"])
    assert res_raw.exit_code == 0
    assert "--- FUNCIONES REQUERIDAS ---" in res_raw.stdout
    assert "void duplicar(int* p);" in res_raw.stdout
    assert "--- TESTS DE FUNCIONES ---" in res_raw.stdout


def test_verify_con_tests_de_funciones(tmp_path: Path):
    banco = tmp_path / "banco"
    banco.mkdir()

    ej_ok = Ejercicio(
        id="fn-verif-ok",
        titulo="Verif OK",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=15,
        enunciado_md="Consigna",
        solucion_c="int duplicar_val(int x) { return x * 2; }",
        funciones=[FuncionSpec(nombre="duplicar_val", retorno="int", parametros="int x")],
        tests_funciones=[CasoTestFuncion(nombre="test_1", funcion="duplicar_val", codigo="assert(duplicar_val(3) == 6);")],
        verificado=False,
    )
    guardar_ejercicio(ej_ok, banco)

    ej_fail = Ejercicio(
        id="fn-verif-fail",
        titulo="Verif Fail",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=15,
        enunciado_md="Consigna",
        solucion_c="int duplicar_val(int x) { return x * 3; /* Bug */ }",
        funciones=[FuncionSpec(nombre="duplicar_val", retorno="int", parametros="int x")],
        tests_funciones=[CasoTestFuncion(nombre="test_1", funcion="duplicar_val", codigo="assert(duplicar_val(3) == 6);")],
        verificado=True,
    )
    guardar_ejercicio(ej_fail, banco)

    log_fallos = tmp_path / "fallos_fn.md"
    res = runner.invoke(app, [
        "verify", "--all",
        "--banco", str(banco),
        "--log-fallos", str(log_fallos),
    ])

    assert res.exit_code == 1
    # Comprobar actualización de estados
    assert cargar_ejercicio(banco / "fn-verif-ok").verificado is True
    assert cargar_ejercicio(banco / "fn-verif-fail").verificado is False

    # Comprobar reporte de fallos
    assert log_fallos.is_file()
    assert "fn-verif-fail" in log_fallos.read_text(encoding="utf-8")
