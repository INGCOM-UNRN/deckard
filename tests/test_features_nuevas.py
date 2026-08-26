"""Pruebas para las nuevas funcionalidades de deckard: show, pdf y gestión de guías."""

from pathlib import Path
from unittest.mock import patch
import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import guardar_ejercicio
from deckard.core.guides import (
    agregar_ejercicio_a_guia,
    inspeccionar_guia,
    listar_guias,
    remover_ejercicio_de_guia,
)
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.pdf import (
    buscar_plantilla,
    renderizar_ejercicio_html,
    renderizar_guia_html,
)

runner = CliRunner()


@pytest.fixture()
def banco_con_tests(tmp_path) -> Path:
    banco = tmp_path / "banco"
    banco.mkdir()
    ej1 = Ejercicio(
        id="invertir-vector",
        titulo="Invertir Vector",
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=25,
        enunciado_md="# Invertir Vector\nDado un vector de `N` enteros, invertirlo in-place.",
        solucion_c="#include <stdio.h>\nint main(void){ printf(\"invertido\\n\"); return 0; }\n",
        pistas=["Pensá en intercambiar el primer y último elemento."],
        tags=["arreglos", "punteros"],
        verificado=True,
    )
    dir_ej1 = guardar_ejercicio(ej1, banco)
    tests_dir = dir_ej1 / "tests"
    tests_dir.mkdir()
    (tests_dir / "caso_01.in").write_text("1 2 3\n", encoding="utf-8")
    (tests_dir / "caso_01.out").write_text("3 2 1\n", encoding="utf-8")

    ej2 = Ejercicio(
        id="contar-pares",
        titulo="Contar Pares",
        tema="arreglos",
        bloom=NivelBloom.COMPRENDER,
        minutos_estimados=15,
        enunciado_md="# Contar Pares\nContar números pares.",
        solucion_c="#include <stdio.h>\nint main(void){ return 0; }\n",
        pistas=["Usá el operador módulo % 2."],
    )
    guardar_ejercicio(ej2, banco)
    return banco


@pytest.fixture()
def guias_dir(tmp_path, banco_con_tests) -> Path:
    g_dir = tmp_path / "guias"
    g_dir.mkdir()

    # Guía spec
    (g_dir / "guia_spec.yaml").write_text(
        "nombre: \"Guía 1 — Arreglos\"\n"
        "duracion_min: 60\n"
        "margen_carga: 0.8\n"
        "temas: [arreglos]\n"
        "bloom_min: 1\n"
        "bloom_max: 4\n",
        encoding="utf-8"
    )

    # Guía compuesta
    (g_dir / "guia_compuesta.yaml").write_text(
        "nombre: \"Guía Práctica 1\"\n"
        "minutos_totales: 40\n"
        "distribucion_bloom:\n"
        "  COMPRENDER: 1\n"
        "  APLICAR: 1\n"
        "ejercicios:\n"
        "  - id: invertir-vector\n"
        "    minutos: 25\n"
        "    bloom: 3\n"
        "    tema: arreglos\n"
        "  - id: contar-pares\n"
        "    minutos: 15\n"
        "    bloom: 2\n"
        "    tema: arreglos\n",
        encoding="utf-8"
    )
    return g_dir


# ---------------------------------------------------------------------------
# Tests de comando `deckard show`
# ---------------------------------------------------------------------------


def test_show_ejercicio_default(banco_con_tests):
    res = runner.invoke(app, ["show", "invertir-vector", "--banco", str(banco_con_tests)])
    assert res.exit_code == 0
    assert "invertir-vector" in res.stdout
    assert "Invertir Vector" in res.stdout
    assert "Dado un vector de N enteros" in res.stdout


def test_show_ejercicio_con_secciones(banco_con_tests):
    # Ver solución y pistas
    res = runner.invoke(app, [
        "show", "invertir-vector",
        "--banco", str(banco_con_tests),
        "-s", "-p", "-t"
    ])
    assert res.exit_code == 0
    assert "Pistas Progresivas" in res.stdout
    assert "Solución Modelo" in res.stdout
    assert "Casos de Prueba" in res.stdout
    assert "caso_01" in res.stdout


def test_show_ejercicio_raw(banco_con_tests):
    res = runner.invoke(app, [
        "show", "invertir-vector",
        "--banco", str(banco_con_tests),
        "--todos", "--raw"
    ])
    assert res.exit_code == 0
    assert "ID: invertir-vector" in res.stdout
    assert "--- ENUNCIADO ---" in res.stdout
    assert "--- PISTAS ---" in res.stdout
    assert "--- SOLUCION ---" in res.stdout
    assert "--- TESTS ---" in res.stdout


def test_show_ejercicio_inexistente(banco_con_tests):
    res = runner.invoke(app, ["show", "no-existe", "--banco", str(banco_con_tests)])
    assert res.exit_code == 1
    assert "No se encontró el ejercicio" in res.stdout


# ---------------------------------------------------------------------------
# Tests de comando `deckard pdf` y renderizado
# ---------------------------------------------------------------------------


def test_renderizar_ejercicio_html(banco_con_tests):
    dir_ej = banco_con_tests / "invertir-vector"
    from deckard.core.bank import cargar_ejercicio
    ej = cargar_ejercicio(dir_ej)

    html, _ = renderizar_ejercicio_html(
        ejercicio=ej,
        dir_ejercicio=dir_ej,
        incluir_solucion=True,
        incluir_pistas=True,
        incluir_tests=True,
    )
    assert "<title>Invertir Vector — invertir-vector</title>" in html
    assert "Pistas Progresivas" in html
    assert "Solución Modelo" in html
    assert "caso_01" in html


def test_export_markdown_ejercicio(banco_con_tests, tmp_path):
    out_md = tmp_path / "ejercicio.md"
    res = runner.invoke(app, [
        "export", "invertir-vector",
        "--banco", str(banco_con_tests),
        "-f", "md",
        "-o", str(out_md),
        "-s", "-p", "-t"
    ])
    assert res.exit_code == 0
    assert out_md.is_file()
    contenido = out_md.read_text(encoding="utf-8")
    assert "# Invertir Vector" in contenido
    assert "### 💡 Pistas Progresivas" in contenido
    assert "### ✓ Solución Modelo" in contenido
    assert "### 🧪 Casos de Prueba" in contenido


def test_export_markdown_guia(guias_dir, banco_con_tests, tmp_path):
    out_md = tmp_path / "guia.md"
    res = runner.invoke(app, [
        "export", str(guias_dir / "guia_compuesta.yaml"),
        "--banco", str(banco_con_tests),
        "-f", "markdown",
        "-o", str(out_md),
        "-s"
    ])
    assert res.exit_code == 0
    assert out_md.is_file()
    contenido = out_md.read_text(encoding="utf-8")
    assert "# Guía Práctica 1" in contenido
    assert "## 1. Invertir Vector" in contenido
    assert "## 2. Contar Pares" in contenido


def test_export_pdf_via_pipeline_markdown(banco_con_tests, tmp_path):
    out_pdf = tmp_path / "pipeline.pdf"
    with patch("deckard.cli.compilar_pdf") as mock_pdf:
        mock_pdf.return_value = out_pdf
        res = runner.invoke(app, [
            "export", "invertir-vector",
            "--banco", str(banco_con_tests),
            "-f", "pdf",
            "--pipeline-md",
            "-o", str(out_pdf)
        ])
        assert res.exit_code == 0
        assert "exportado a PDF" in res.stdout
        mock_pdf.assert_called_once()


def test_init_templates(tmp_path):
    dest = tmp_path / "custom_templates"
    res = runner.invoke(app, ["templates", "init", str(dest)])
    assert res.exit_code == 0
    assert (dest / "ejercicio.html").is_file()
    assert (dest / "guia.html").is_file()
    assert (dest / "ejercicio.md").is_file()
    assert (dest / "guia.md").is_file()
    assert (dest / "estilos.css").is_file()


def test_export_con_imagen_en_plantilla(banco_con_tests, tmp_path):
    # Simular plantilla personalizada con imagen en la misma carpeta
    tmpl_dir = tmp_path / "custom_tmpl"
    tmpl_dir.mkdir()
    logo_file = tmpl_dir / "logo.png"
    logo_file.write_bytes(b"dummy image data")
    custom_html = tmpl_dir / "ejercicio_custom.html"
    custom_html.write_text(
        '<!DOCTYPE html><html><body><img src="logo.png"><h1>{{ ejercicio.titulo }}</h1>{{ enunciado_html }}</body></html>',
        encoding="utf-8"
    )

    out_html = tmp_path / "con_logo.html"
    res = runner.invoke(app, [
        "export", "invertir-vector",
        "--banco", str(banco_con_tests),
        "-T", str(custom_html),
        "-f", "html",
        "-o", str(out_html)
    ])
    assert res.exit_code == 0
    assert out_html.is_file()
    assert 'img src="logo.png"' in out_html.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests de comandos `deckard guide`
# ---------------------------------------------------------------------------


def test_guide_list(guias_dir, banco_con_tests):
    res = runner.invoke(app, ["guide", "list", "--guias", str(guias_dir), "--banco", str(banco_con_tests)])
    assert res.exit_code == 0
    assert "Práctica" in res.stdout
    assert "Arreglos" in res.stdout
    assert "compuesta" in res.stdout
    assert "spec" in res.stdout


def test_guide_compose_subcommand(guias_dir, banco_con_tests):
    res = runner.invoke(app, [
        "guide", "compose", str(guias_dir / "guia_spec.yaml"),
        "--banco", str(banco_con_tests)
    ])
    assert res.exit_code == 0
    assert "Guía escrita" in res.stdout


def test_guide_show(guias_dir, banco_con_tests):
    res = runner.invoke(app, [
        "guide", "show", "guia_compuesta.yaml",
        "--guias", str(guias_dir),
        "--banco", str(banco_con_tests),
        "-e"
    ])
    assert res.exit_code == 0
    assert "Guía Práctica 1" in res.stdout
    assert "invertir-vector" in res.stdout
    assert "contar-pares" in res.stdout
    assert "Dado un vector de N enteros" in res.stdout


def test_guide_new(tmp_path):
    g_dir = tmp_path / "guias"
    res = runner.invoke(app, [
        "guide", "new", "nueva_guia.yaml",
        "--titulo", "Guía 3 — Recursión",
        "--duracion", "120",
        "--temas", "recursion,punteros",
        "--bloom-min", "2",
        "--bloom-max", "4",
        "--guias", str(g_dir)
    ])
    assert res.exit_code == 0
    assert (g_dir / "nueva_guia.yaml").is_file()


def test_guide_add_and_remove(guias_dir, banco_con_tests):
    guia_file = guias_dir / "guia_compuesta.yaml"

    # Remover contar-pares
    res_rem = runner.invoke(app, [
        "guide", "remove", str(guia_file), "contar-pares",
        "--guias", str(guias_dir)
    ])
    assert res_rem.exit_code == 0
    assert "removido" in res_rem.stdout

    # Re-agregar contar-pares
    res_add = runner.invoke(app, [
        "guide", "add", str(guia_file), "contar-pares",
        "--banco", str(banco_con_tests),
        "--guias", str(guias_dir)
    ])
    assert res_add.exit_code == 0
    assert "agregado" in res_add.stdout


def test_guide_verify(guias_dir, banco_con_tests):
    with patch("deckard.cli.verificar_ejercicio") as mock_verify:
        from deckard.core.verify import ResultadoVerify
        mock_verify.return_value = ResultadoVerify("ej", True, "OK")

        res = runner.invoke(app, [
            "guide", "verify", str(guias_dir / "guia_compuesta.yaml"),
            "--banco", str(banco_con_tests)
        ])
        assert res.exit_code == 0
        assert "Verificación de guía finalizada: 2/2 exitosos" in res.stdout
