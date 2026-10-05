"""Errores de ejercicio.yaml en español, JSON Schema publicado y comandos agrupados (N-DECKARD-02)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import cargar_ejercicio
from deckard.core.esquema import EjercicioInvalido, esquema_json

runner = CliRunner()
RAIZ = Path(__file__).resolve().parents[1]


def _ejercicio(tmp_path: Path, texto: str) -> Path:
    d = tmp_path / "ej"
    d.mkdir()
    (d / "ejercicio.yaml").write_text(texto, encoding="utf-8")
    return d


def test_errores_en_espanol(tmp_path):
    with pytest.raises(EjercicioInvalido) as exc:
        cargar_ejercicio(_ejercicio(tmp_path, "id: Mal Id\nminutos_estimados: muchos\n"))
    texto = str(exc.value)
    assert "ejercicio.yaml" in texto and "falta el campo obligatorio «titulo»" in texto
    assert "«id» = 'Mal Id' no tiene el formato esperado" in texto


def test_yaml_roto(tmp_path):
    with pytest.raises(EjercicioInvalido, match="no es YAML válido"):
        cargar_ejercicio(_ejercicio(tmp_path, "id: [sin cerrar\n"))


def test_el_esquema_publicado_esta_al_dia():
    publicado = json.loads((RAIZ / "esquemas" / "ejercicio.schema.json").read_text(encoding="utf-8"))
    assert publicado == esquema_json(), "regenerá con: deckard bank schema -o esquemas/ejercicio.schema.json"
    assert "titulo" in publicado["required"]


def test_comandos_agrupados_y_alias_con_aviso(tmp_path):
    assert runner.invoke(app, ["quality", "--help"]).exit_code == 0
    nuevo = runner.invoke(app, ["exercise", "--help"])
    assert "scaffold" in nuevo.stdout
    viejo = runner.invoke(app, ["check-terms", "--help"])
    assert viejo.exit_code == 0
    principal = runner.invoke(app, ["--help"]).stdout
    assert "check-terms" not in principal and "quality" in principal
