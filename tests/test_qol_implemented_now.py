"""Tests automatizados exhaustivos para las mejoras QoL implementadas ahora en Deckard."""

from pathlib import Path
import pytest
from typer.testing import CliRunner
import yaml

from deckard.cli import app
from deckard.core.bank import cargar_ejercicio, guardar_ejercicio
from deckard.core.init_tests import generar_suite_tests_c, inicializar_tests_ejercicio
from deckard.core.markdown_sync import (
    ejercicio_a_markdown,
    markdown_a_ejercicio,
    exportar_ejercicio_md_interactivo,
    importar_ejercicio_desde_md,
)
from deckard.core.web_export import (
    renderizar_ejercicio_myst,
    renderizar_ejercicio_web_html,
    exportar_web_estatica,
)
from deckard.core.sanitizer_audit import auditar_solucion_sanitizers
from deckard.core.acsl_synth import extraer_contratos_acsl, sintetizar_tests_de_acsl
from deckard.core.anki import ejercicio_a_flashcards, exportar_mazo_anki_tsv
from deckard.core.rubric import (
    calibrar_pesos_rubrica,
    generar_rubrica_markdown,
    exportar_rubrica_dredd_json,
)
from deckard.core.io_files import scaffolding_ejercicio_archivos
from deckard.core.deps import (
    build_dependency_graph,
    ordenar_topologicamente,
    seleccionar_por_prerrequisitos,
)
from deckard.core.pack import empaquetar_ejercicio
from deckard.core.models import Ejercicio, FuncionSpec, CasoTestFuncion, NivelBloom

runner = CliRunner()


@pytest.fixture
def sample_bank(tmp_path: Path) -> Path:
    banco = tmp_path / "banco"
    banco.mkdir()

    # Ejercicio 1: funciones con ACSL
    ej1_dir = banco / "calcular_potencia"
    ej1_dir.mkdir()
    ej1 = Ejercicio(
        id="calcular_potencia",
        titulo="Cálculo de Potencia Entera",
        tema="funciones",
        bloom=NivelBloom.APLICAR,
        minutos=25,
        enunciado="Calcular base elevada a exponente entero positivo.",
        starter_code="int potencia(int base, int exp) { return 0; }\n",
        solucion_c="""/*@
  @ requires exp >= 0;
  @ ensures \\result >= 0;
  @*/
int potencia(int base, int exp) {
    int res = 1;
    for (int i = 0; i < exp; i++) res *= base;
    return res;
}
""",
        pistas=["El caso exp == 0 debe retornar 1."],
        tags=["funciones", "aritmetica"],
        funciones=[FuncionSpec(nombre="potencia", retorno="int", parametros="int base, int exp")],
        tests_funciones=[
            CasoTestFuncion(nombre="caso_cero", funcion="potencia", args="2, 0", retorno_esperado="1"),
            CasoTestFuncion(nombre="caso_cuadrado", funcion="potencia", args="3, 2", retorno_esperado="9"),
        ],
        verificado=True,
    )
    guardar_ejercicio(ej1, banco)

    # Ejercicio 2: arreglos dependiente de funciones
    ej2_dir = banco / "sumar_vector"
    ej2_dir.mkdir()
    ej2 = Ejercicio(
        id="sumar_vector",
        titulo="Suma de Vector",
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos=30,
        enunciado="Sumar elementos de un vector de enteros.",
        starter_code="int suma_vector(const int* v, int n) { return 0; }\n",
        solucion_c="""#include <stddef.h>
int suma_vector(const int* v, int n) {
    if (!v || n <= 0) return 0;
    int acc = 0;
    for (int i = 0; i < n; i++) acc += v[i];
    return acc;
}
""",
        tags=["arreglos"],
        dependencias=["funciones"],
        verificado=True,
    )
    guardar_ejercicio(ej2, banco)

    return banco


def test_init_tests_p1_test_and_assert(sample_bank: Path):
    ej1_dir = sample_bank / "calcular_potencia"
    ej = cargar_ejercicio(ej1_dir)

    # Framework p1_test
    codigo_p1 = generar_suite_tests_c(ej, framework="p1_test")
    assert '#include "p1_test.h"' in codigo_p1
    assert "TEST(test_potencia_1)" in codigo_p1
    assert "ASSERT_EQ(potencia(2, 0), 1);" in codigo_p1

    # Framework assert
    codigo_assert = generar_suite_tests_c(ej, framework="assert")
    assert "#include <assert.h>" in codigo_assert
    assert "assert(potencia(2, 0) == 1);" in codigo_assert

    # CLI test
    res = runner.invoke(app, ["init-tests", "calcular_potencia", "--banco", str(sample_bank), "--framework", "p1_test"])
    assert res.exit_code == 0
    assert (ej1_dir / "tests" / "test_calcular_potencia.c").is_file()
    assert (ej1_dir / "Makefile.test").is_file()


def test_markdown_sync_bidirectional(sample_bank: Path, tmp_path: Path):
    ej1_dir = sample_bank / "calcular_potencia"
    ej = cargar_ejercicio(ej1_dir)

    # Serializar a Markdown interactivo
    md_text = ejercicio_a_markdown(ej)
    assert "---" in md_text
    assert "id: calcular_potencia" in md_text
    assert "## Enunciado" in md_text
    assert "## Solución Modelo" in md_text
    assert "## Pistas" in md_text

    # Reconstruir objeto Ejercicio desde Markdown
    ej_reconstruido = markdown_a_ejercicio(md_text)
    assert ej_reconstruido.id == ej.id
    assert ej_reconstruido.titulo == ej.titulo
    assert ej_reconstruido.bloom == ej.bloom
    assert len(ej_reconstruido.funciones) == 1
    assert ej_reconstruido.funciones[0].nombre == "potencia"

    # Exportar e Importar via CLI
    md_out = tmp_path / "potencia.interactive.md"
    res_to_md = runner.invoke(app, ["to-md", "calcular_potencia", "-o", str(md_out), "--banco", str(sample_bank)])
    assert res_to_md.exit_code == 0
    assert md_out.is_file()

    banco_dest = tmp_path / "nuevo_banco"
    banco_dest.mkdir()
    res_from_md = runner.invoke(app, ["from-md", str(md_out), "-d", str(banco_dest)])
    assert res_from_md.exit_code == 0
    assert (banco_dest / "calcular_potencia" / "ejercicio.yaml").is_file()


def test_export_web_static_and_myst(sample_bank: Path, tmp_path: Path):
    ej1_dir = sample_bank / "calcular_potencia"
    ej = cargar_ejercicio(ej1_dir)

    # HTML
    html_out = renderizar_ejercicio_web_html(ej)
    assert "<!DOCTYPE html>" in html_out
    assert "Cálculo de Potencia Entera" in html_out
    assert "details class=\"solucion-desplegable\"" in html_out
    assert "potencia(int base, int exp)" in html_out

    # MyST Markdown
    myst_out = renderizar_ejercicio_myst(ej)
    assert "{dropdown} 💡 Ver Solución Canónica de Cátedra" in myst_out
    assert "```{code-block} c" in myst_out

    # CLI export-web
    web_dir = tmp_path / "web_dist"
    res_web = runner.invoke(app, ["export-web", "calcular_potencia", "-o", str(web_dir), "--banco", str(sample_bank)])
    assert res_web.exit_code == 0
    assert (web_dir / "calcular_potencia.html").is_file()
    assert (web_dir / "index.html").is_file()

    # CLI export-web --myst
    myst_dir = tmp_path / "myst_dist"
    res_myst = runner.invoke(app, ["export-web", "calcular_potencia", "-o", str(myst_dir), "--myst", "--banco", str(sample_bank)])
    assert res_myst.exit_code == 0
    assert (myst_dir / "calcular_potencia.md").is_file()
    assert (myst_dir / "_toc.yml").is_file()


def test_sanitizer_audit(sample_bank: Path):
    ej1_dir = sample_bank / "calcular_potencia"
    res_clean = auditar_solucion_sanitizers(ej1_dir)
    assert res_clean.ok is True
    assert res_clean.leak_detected is False
    assert res_clean.ub_detected is False

    # CLI invocation
    res_cli = runner.invoke(app, ["audit-sanitizers", "calcular_potencia", "--banco", str(sample_bank)])
    assert res_cli.exit_code == 0
    assert "Limpio" in res_cli.stdout or "calcular_potencia" in res_cli.stdout


def test_acsl_synthesis(sample_bank: Path):
    ej1_dir = sample_bank / "calcular_potencia"
    ej = cargar_ejercicio(ej1_dir)

    contratos = extraer_contratos_acsl(ej.solucion_c)
    assert len(contratos) == 1
    assert contratos[0]["funcion"] == "potencia"
    assert "exp >= 0" in contratos[0]["requires"]
    assert "\\result >= 0" in contratos[0]["ensures"]

    tests_acsl = sintetizar_tests_de_acsl(ej)
    assert len(tests_acsl) == 1
    assert "acsl_potencia_ensures_1" == tests_acsl[0].nombre
    assert "res >= 0" in tests_acsl[0].postcondiciones or "potencia" in tests_acsl[0].postcondiciones

    # CLI invocation
    res = runner.invoke(app, ["acsl-tests", "calcular_potencia", "--banco", str(sample_bank)])
    assert res.exit_code == 0
    assert "acsl_potencia_ensures_1" in res.stdout


def test_anki_export(sample_bank: Path, tmp_path: Path):
    ej1_dir = sample_bank / "calcular_potencia"
    ej = cargar_ejercicio(ej1_dir)

    cards = ejercicio_a_flashcards(ej)
    assert len(cards) >= 2  # Una de consigna + una de firma
    assert "Cálculo de Potencia Entera" in cards[0]["frente"]
    assert "potencia" in cards[1]["frente"]

    tsv_path = tmp_path / "anki.tsv"
    res = runner.invoke(app, ["export-anki", "calcular_potencia", "-o", str(tsv_path), "--banco", str(sample_bank)])
    assert res.exit_code == 0
    assert tsv_path.is_file()
    contenido_tsv = tsv_path.read_text(encoding="utf-8")
    assert "#separator:tab" in contenido_tsv
    assert "calcular_potencia" in contenido_tsv or "Potencia" in contenido_tsv


def test_rubric_calibration_and_export(sample_bank: Path, tmp_path: Path):
    ej1_dir = sample_bank / "calcular_potencia"
    ej = cargar_ejercicio(ej1_dir)

    pesos = calibrar_pesos_rubrica({"tests_unitarios": 50, "estilo_gaff": 25, "sanitizers_memoria": 25})
    assert sum(pesos.values()) == 100.0
    assert pesos["tests_unitarios"] == 50.0

    md_rubrica = generar_rubrica_markdown(ej, pesos)
    assert "| **Tests unitarios** | `50.0%` |" in md_rubrica
    assert "Niveles de Desempeño" in md_rubrica

    json_dredd = tmp_path / "rubrica.json"
    res = runner.invoke(app, ["rubric", "calcular_potencia", "--dredd", str(json_dredd), "--banco", str(sample_bank)])
    assert res.exit_code == 0
    assert json_dredd.is_file()
    datos = yaml.safe_load(json_dredd.read_text(encoding="utf-8"))
    assert "criterios_globales" in datos
    assert "calcular_potencia" in datos["ejercicios"]


def test_io_files_scaffolding(sample_bank: Path):
    ej1_dir = sample_bank / "calcular_potencia"
    res = runner.invoke(app, ["init-io-files", "calcular_potencia", "--modo", "binario", "--banco", str(sample_bank)])
    assert res.exit_code == 0
    assert (ej1_dir / "tests" / "entrada_muestra.bin").is_file()
    ej_actualizado = cargar_ejercicio(ej1_dir)
    assert "archivos" in ej_actualizado.tags
    assert "binario" in ej_actualizado.tags


def test_select_prereqs(sample_bank: Path):
    todos = [(sample_bank / "calcular_potencia", cargar_ejercicio(sample_bank / "calcular_potencia")),
             (sample_bank / "sumar_vector", cargar_ejercicio(sample_bank / "sumar_vector"))]

    # Con solo 'variables' dominado, funciones no está habilitado si requiere orden superior
    elegibles = seleccionar_por_prerrequisitos(todos, temas_conocidos=["funciones", "control_flujo"])
    assert any(e.id == "calcular_potencia" for e in elegibles)

    res = runner.invoke(app, ["select-prereqs", "funciones,arreglos", "--banco", str(sample_bank)])
    assert res.exit_code == 0
    assert "calcular_potencia" in res.stdout


def test_pack_hidden_tests_and_benchmarks(sample_bank: Path, tmp_path: Path):
    ej1_dir = sample_bank / "calcular_potencia"
    # Crear un test oculto y un benchmark
    (ej1_dir / "tests" / "hidden").mkdir(parents=True, exist_ok=True)
    (ej1_dir / "tests" / "hidden" / "caso_oculto.in").write_text("10 5\n")
    (ej1_dir / "tests" / "hidden" / "caso_oculto.out").write_text("100000\n")

    (ej1_dir / "benchmarks").mkdir(parents=True, exist_ok=True)
    (ej1_dir / "benchmarks" / "bench1.in").write_text("1000000\n")

    # Empaquetado completo (incluye ocultos)
    pkg_full = tmp_path / "potencia_full.ripkg"
    res_full = empaquetar_ejercicio(ej1_dir, out_path=pkg_full, include_hidden=True)
    assert res_full.output_path.is_file()

    # Empaquetado limpio (sin ocultos)
    pkg_clean = tmp_path / "potencia_clean.ripkg"
    res_clean = empaquetar_ejercicio(ej1_dir, out_path=pkg_clean, include_hidden=False)
    assert res_clean.output_path.is_file()
    assert res_clean.archivos_payload < res_full.archivos_payload
