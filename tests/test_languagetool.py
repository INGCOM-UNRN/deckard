"""Tests para el validador y corrector de LanguageTool en deckard."""

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.languagetool_checker import (
    enmascarar_enunciado,
    consultar_languagetool,
    analizar_ejercicio_languagetool,
    aplicar_autofix_ejercicio,
    generar_reporte_markdown_languagetool,
    LanguageToolIssue,
)

runner = CliRunner()


def test_enmascarar_enunciado_deckard():
    texto = (
        "# Título del Ejercicio\n\n"
        "Implementar la función `int sumar(int a, int b);` en C.\n\n"
        "```c\n"
        "int main() {\n"
        "    return 0;\n"
        "}\n"
        "```\n\n"
        "Ver fórmula $O(N)$ y enlace [guía](https://example.com/guia).\n"
    )
    enmascarado, _ = enmascarar_enunciado(texto)
    assert "# Título del Ejercicio" in enmascarado
    assert "Implementar la función" in enmascarado
    assert "int main()" not in enmascarado
    assert "https://example.com" not in enmascarado
    assert len(enmascarado) == len(texto)


def test_consultar_languagetool_mock(monkeypatch):
    captured_requests = []

    class MockResponse:
        status = 200
        def read(self):
            return json.dumps({"matches": [{"message": "Error", "shortMessage": "Error", "offset": 0, "length": 5, "rule": {"id": "TEST", "category": {"name": "Ortografia"}}, "context": {"text": "errrr", "offset": 0, "length": 5}, "replacements": [{"value": "error"}]}]}).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10.0: MockResponse())

    # 1. Local / Free
    res = consultar_languagetool("errrr en C")
    assert "matches" in res
    assert len(res["matches"]) == 1

    # 2. Premium con credenciales
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10.0: (captured_requests.append(req), MockResponse())[1])
    consultar_languagetool("errrr", username="profesor@uba.ar", api_key="clave-123", premium=True)
    assert len(captured_requests) == 1
    assert "api.languagetoolplus.com" in captured_requests[0].full_url
    data = captured_requests[0].data.decode("utf-8")
    assert "username=profesor%40uba.ar" in data
    assert "apiKey=clave-123" in data


def test_analizar_y_autofix_ejercicio(monkeypatch):
    ej = Ejercicio(
        id="ej-test",
        titulo="Titulo con prueva",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos=20,
        enunciado="En este ejerzicio se debe ordenar un vector.",
        pistas=["Primera pista con eror."],
    )

    sample_response = {
        "matches": [
            {
                "message": "Falta de ortografía",
                "shortMessage": "Error",
                "offset": 11,
                "length": 6,
                "rule": {"id": "MORFOLOGIK_RULE_ES", "category": {"name": "Ortografía"}},
                "context": {"text": "Titulo con prueva", "offset": 11, "length": 6},
                "replacements": [{"value": "prueba"}],
            }
        ]
    }

    class MockResponse:
        status = 200
        def read(self):
            return json.dumps(sample_response).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10.0: MockResponse())

    issues = analizar_ejercicio_languagetool(ej)
    assert len(issues) >= 1
    assert issues[0].original_word == "prueva"

    # Aplicar autofix
    cambios = aplicar_autofix_ejercicio(ej, issues)
    assert cambios >= 1
    assert "prueba" in ej.titulo


def test_cli_spellcheck(tmp_path: Path, monkeypatch):
    banco = tmp_path / "banco"
    ej_dir = banco / "invertir"
    ej_dir.mkdir(parents=True)
    ej_yaml = ej_dir / "ejercicio.yaml"
    ej_yaml.write_text("""
id: invertir
titulo: Invertir vector con errror
tema: punteros
bloom: 3
minutos: 30
enunciado: Enunciado de prueba.
""", encoding="utf-8")

    sample_response = {
        "matches": [
            {
                "message": "Falta de ortografía",
                "shortMessage": "Error",
                "offset": 24,
                "length": 6,
                "rule": {"id": "MORFOLOGIK_RULE_ES", "category": {"name": "Ortografía"}},
                "context": {"text": "Invertir vector con errror", "offset": 24, "length": 6},
                "replacements": [{"value": "error"}],
            }
        ]
    }

    class MockResponse:
        status = 200
        def read(self):
            return json.dumps(sample_response).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10.0: MockResponse())

    # 1. Chequeo CLI sin fix (exit code 1)
    res = runner.invoke(app, ["spellcheck", "--banco", str(banco)])
    assert res.exit_code == 1
    assert "Observaciones de LanguageTool" in res.output

    # 2. Salida JSON
    res_json = runner.invoke(app, ["spellcheck", "--banco", str(banco), "--json"])
    assert res_json.exit_code == 1
    assert "total_issues" in res_json.output

    # 3. Reporte Markdown
    md_file = tmp_path / "reporte.md"
    res_md = runner.invoke(app, ["spellcheck", "--banco", str(banco), "--md", str(md_file)])
    assert res_md.exit_code == 1
    assert md_file.is_file()

    # 4. Autofix
    res_fix = runner.invoke(app, ["spellcheck", "--banco", str(banco), "--fix"])
    assert res_fix.exit_code == 1
    assert "correcciones automáticas" in res_fix.output
