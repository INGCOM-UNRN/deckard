"""Regresiones que encontró mypy (N-ECO-08): comandos que reciben una guía YAML como objetivo.

`cargar_guia_con_ejercicios` devuelve una tupla (metadatos, [(ruta, ejercicio)]); varios comandos
le pedían `.ejercicios` y `.guia` y terminaban en AttributeError. `exercise variant` armaba un
GuiaSpec con campos que no existen y le pasaba los argumentos invertidos a `guardar_yaml_guia`.
"""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.models import CasoTestFuncion, Ejercicio, FuncionSpec, NivelBloom
from deckard.core.notebook import generar_notebook_ejercicio

runner = CliRunner()


def _banco_con_guia(tmp_path: Path) -> tuple[Path, Path]:
    assert runner.invoke(app, ["init", str(tmp_path)]).exit_code == 0
    guia = tmp_path / "guias" / "g.yaml"
    guia.write_text("nombre: Guía de prueba\nejercicios:\n  - id: ejemplo-invertir\n", encoding="utf-8")
    return tmp_path / "banco", guia


def test_export_web_con_una_guia(tmp_path):
    banco, guia = _banco_con_guia(tmp_path)
    res = runner.invoke(app, ["export", "web", str(guia), "--banco", str(banco), "-o", str(tmp_path / "web")])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "web").exists()


def test_quality_terms_con_una_guia(tmp_path):
    banco, guia = _banco_con_guia(tmp_path)
    res = runner.invoke(app, ["quality", "terms", str(guia), "--banco", str(banco)])
    assert res.exit_code == 0, res.output


def test_exercise_variant_escribe_una_guia(tmp_path):
    banco, guia = _banco_con_guia(tmp_path)
    salida = tmp_path / "guias" / "recuperatorio.yaml"
    res = runner.invoke(app, ["exercise", "variant", str(guia), "--banco", str(banco), "-o", str(salida)])
    assert res.exit_code == 0, res.output
    datos = yaml.safe_load(salida.read_text(encoding="utf-8"))
    assert datos["nombre"] == "Guía de prueba (Variante Recuperatorio)"
    assert datos["ejercicios"] == ["ejemplo-invertir"]


def test_notebook_con_casos_de_funcion():
    ej = Ejercicio(
        id="suma", titulo="Suma", tema="funciones", bloom=NivelBloom.APLICAR, minutos_estimados=10,
        funciones=[FuncionSpec(nombre="suma", retorno="int", parametros="int a, int b")],
        tests_funciones=[CasoTestFuncion(nombre="basico", funcion="suma", args="2, 3", retorno_esperado="5")],
    )
    texto = str(generar_notebook_ejercicio(ej))
    assert "suma(2, 3) == 5" in texto
