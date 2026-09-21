"""Tests para las 4 mejoras QoL implementadas ahora en Deckard:
1. checklist (listas de autoevaluación en Markdown)
2. check-signatures (consistencia de firmas de funciones)
3. license-manager (gestión de autoría y licencias)
4. failure-hints (pistas pedagógicas ante fallas)
"""

from pathlib import Path
import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import guardar_ejercicio
from deckard.core.checklist import generar_checklist_ejercicio, generar_checklist_guia
from deckard.core.failure_hints import obtener_pista_falla
from deckard.core.license_manager import inyectar_creditos_ejercicio, obtener_creditos_ejercicio
from deckard.core.models import Ejercicio, FuncionSpec, NivelBloom
from deckard.core.signature_checker import verificar_firmas_ejercicio

runner = CliRunner()


def test_checklist(tmp_path: Path):
    ej = Ejercicio(
        id="ej-chk",
        titulo="Ordenar Vector Dinámico",
        tema="memoria_dinamica",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=30,
        enunciado_md="Ordenar un vector asignado en el heap.",
    )
    guardar_ejercicio(ej, tmp_path)

    md = generar_checklist_ejercicio(ej)
    assert "Lista de Autoevaluación previa a la Entrega" in md
    assert "Validación de punteros" in md
    assert "Liberación completa" in md

    # CLI test
    res = runner.invoke(app, ["checklist", "ej-chk", "--banco", str(tmp_path)])
    assert res.exit_code == 0
    assert "Lista de Autoevaluación" in res.stdout


def test_signature_checker(tmp_path: Path):
    # Caso 1: Firma coincidente
    ej_ok = Ejercicio(
        id="ej-sig-ok",
        titulo="Sumar Números",
        tema="funciones",
        bloom=NivelBloom.COMPRENDER,
        minutos_estimados=15,
        funciones=[FuncionSpec(nombre="sumar", retorno="int", parametros="int a, int b")],
        solucion_c="int sumar(int a, int b) {\n    return a + b;\n}\n",
    )
    guardar_ejercicio(ej_ok, tmp_path)
    disc_ok = verificar_firmas_ejercicio(ej_ok)
    assert len(disc_ok) == 0

    # Caso 2: Firma con retorno dispar o ausente
    ej_bad = Ejercicio(
        id="ej-sig-bad",
        titulo="Calcular Promedio",
        tema="funciones",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=20,
        funciones=[FuncionSpec(nombre="calcular_promedio", retorno="double", parametros="const int* v, size_t n")],
        solucion_c="int calcular_promedio(const int* v, size_t n) {\n    return 0;\n}\n",
    )
    guardar_ejercicio(ej_bad, tmp_path)
    disc_bad = verificar_firmas_ejercicio(ej_bad)
    assert len(disc_bad) == 1
    assert disc_bad[0].tipo == "RETORNO_DISPAR"

    # CLI test
    res = runner.invoke(app, ["check-signatures", "ej-sig-bad", "--banco", str(tmp_path)])
    assert res.exit_code == 0
    assert "Discrepancias de Firmas" in res.stdout


def test_license_manager(tmp_path: Path):
    dir_ej = tmp_path / "ej-lic"
    dir_ej.mkdir()
    (dir_ej / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    ej = Ejercicio(
        id="ej-lic",
        titulo="Ejercicio con Licencia",
        tema="variables",
        bloom=NivelBloom.RECORDAR,
        minutos_estimados=10,
    )
    guardar_ejercicio(ej, tmp_path)

    meta = inyectar_creditos_ejercicio(ej, dir_ej, autor="Docente Cátedra", licencia="MIT", anio=2026)
    assert meta.autor == "Docente Cátedra"
    assert (dir_ej / "creditos.yaml").is_file()

    # CLI test
    res = runner.invoke(app, ["license-manager", "ej-lic", "--banco", str(tmp_path)])
    assert res.exit_code == 0
    assert "Docente Cátedra" in res.stdout


def test_failure_hints():
    pista_segv = obtener_pista_falla("SIGSEGV")
    assert "Segmentation Fault" in pista_segv.concepto_clave
    assert any("NULL" in q for q in pista_segv.preguntas_guia)

    pista_abort = obtener_pista_falla("Assertion failed: n > 0 (SIGABRT)")
    assert "Aborto de Proceso" in pista_abort.concepto_clave

    pista_leak = obtener_pista_falla("Memory leak detected: 48 bytes lost")
    assert "Fuga de Memoria" in pista_leak.concepto_clave

    # CLI test
    res = runner.invoke(app, ["failure-hints", "SIGSEGV"])
    assert res.exit_code == 0
    assert "Pista Pedagógica" in res.stdout
