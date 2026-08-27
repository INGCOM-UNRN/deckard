"""Tests para el módulo de auditoría de salud de enunciados y gestión de tags en deckard."""

from pathlib import Path
import json
import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import cargar_ejercicio, guardar_ejercicio, buscar_ejercicios
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.audit import auditar_ejercicio, auditar_banco
from deckard.core.tags import listar_tags_banco, agregar_tags_a_ejercicios, remover_tags_de_ejercicios

runner = CliRunner()


@pytest.fixture
def banco_auditoria(tmp_path):
    """Crea un banco con ejercicios de diversas calidades para auditar."""
    banco = tmp_path / "banco"
    banco.mkdir()

    # 1. Ejercicio completo y saludable con enunciado.md
    ej1 = Ejercicio(
        id="ej-completo",
        titulo="Ejercicio Completo",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=25,
        enunciado_md="Este es un enunciado detallado y completo que describe el problema paso a paso con contexto claro y restricciones definidas.",
        solucion_c="int main(void) { return 0; }",
        pistas=["Pista 1", "Pista 2"],
        tags=["punteros", "avanzado"],
    )
    dir_ej1 = guardar_ejercicio(ej1, banco)
    (dir_ej1 / "tests").mkdir()
    (dir_ej1 / "tests" / "1.in").write_text("10\n")
    (dir_ej1 / "tests" / "1.out").write_text("20\n")

    # 2. Ejercicio con redacción pobre y sin tests
    ej2 = Ejercicio(
        id="ej-pobre",
        titulo="Ejercicio Pobre",
        tema="arreglos",
        bloom=NivelBloom.RECORDAR,
        minutos_estimados=10,
        enunciado_md="TODO",
        solucion_c="",
        pistas=[],
        tags=[],
    )
    guardar_ejercicio(ej2, banco)

    # 3. Ejercicio con redacción breve pero con solución
    ej3 = Ejercicio(
        id="ej-breve",
        titulo="Ejercicio Breve",
        tema="punteros",
        bloom=NivelBloom.COMPRENDER,
        minutos_estimados=15,
        enunciado_md="Invertir una cadena de caracteres recibida.",
        solucion_c="void invertir(char* s) { (void)s; }",
        pistas=["Usar dos punteros"],
        tags=["strings"],
    )
    guardar_ejercicio(ej3, banco)

    return banco


def test_enunciado_md_archivo_separado(tmp_path):
    """Verifica que el enunciado se guarde en enunciado.md y no duplique en ejercicio.yaml."""
    banco = tmp_path / "banco"
    banco.mkdir()

    ej = Ejercicio(
        id="invertir-texto",
        titulo="Invertir Texto",
        tema="strings",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=20,
        enunciado_md="# Invertir Texto\n\nDado un string de longitud N, invertirlo in-place.",
        solucion_c="void f(void) {}",
    )
    dir_creado = guardar_ejercicio(ej, banco)

    # Verificar que existe archivo enunciado.md
    md_file = dir_creado / "enunciado.md"
    assert md_file.is_file()
    assert "# Invertir Texto" in md_file.read_text(encoding="utf-8")

    # Cargar ejercicio y confirmar que levanta el texto de enunciado.md
    cargado = cargar_ejercicio(dir_creado)
    assert cargado.enunciado_md == ej.enunciado_md


def test_tag_add_remove_and_list(banco_auditoria):
    """Verifica comandos de tags: list, add, remove."""
    # Listar tags iniciales
    tags_map = listar_tags_banco(banco_auditoria)
    assert "punteros" in tags_map
    assert "ej-completo" in tags_map["punteros"]

    # Agregar tags
    mod = agregar_tags_a_ejercicios(banco_auditoria, "ej-pobre", ["arreglos", "facil"])
    assert len(mod) == 1
    assert "facil" in mod[0][1]

    # Verificar persistencia en disco
    ej_reloaded = cargar_ejercicio(banco_auditoria / "ej-pobre")
    assert "facil" in ej_reloaded.tags

    # Remover tag
    mod_rem = remover_tags_de_ejercicios(banco_auditoria, "ej-pobre", ["facil"])
    assert len(mod_rem) == 1
    assert "facil" not in mod_rem[0][1]


def test_cli_tag_commands(banco_auditoria):
    """Verifica la ejecución de subcomandos de tag por CLI."""
    res_list = runner.invoke(app, ["tag", "list", "--banco", str(banco_auditoria)])
    assert res_list.exit_code == 0
    assert "punteros" in res_list.stdout

    res_add = runner.invoke(app, ["tag", "add", "ej-pobre", "nuevo-tag,urgente", "--banco", str(banco_auditoria)])
    assert res_add.exit_code == 0
    assert "Tags agregados" in res_add.stdout

    res_rem = runner.invoke(app, ["tag", "remove", "ej-pobre", "urgente", "--banco", str(banco_auditoria)])
    assert res_rem.exit_code == 0
    assert "Tags removidos" in res_rem.stdout


def test_cli_bank_list_filtro_tag(banco_auditoria):
    """Verifica filtrado por tag en deckard bank list."""
    res = runner.invoke(app, ["bank", "list", "--tag", "punteros", "--banco", str(banco_auditoria)])
    assert res.exit_code == 0
    assert "ej-completo" in res.stdout
    assert "ej-pobre" not in res.stdout


def test_auditoria_salud_ejercicios(banco_auditoria):
    """Verifica el cálculo de métricas de salud en auditar_ejercicio y auditar_banco."""
    rep_completo = auditar_ejercicio(banco_auditoria / "ej-completo", min_chars=50)
    assert rep_completo.es_saludable is True
    assert rep_completo.diagnostico_redaccion == "completo"
    assert rep_completo.cantidad_testcases_io == 1
    assert rep_completo.tiene_solucion is True
    assert len(rep_completo.faltantes) == 0

    rep_pobre = auditar_ejercicio(banco_auditoria / "ej-pobre", min_chars=100)
    assert rep_pobre.es_saludable is False
    assert rep_pobre.redaccion_pobre is True
    assert "solucion.c" in rep_pobre.faltantes
    assert "testcases" in rep_pobre.faltantes


def test_cli_audit_command(banco_auditoria):
    """Verifica el comando deckard audit y sus banderas de filtrado."""
    # Auditoría general
    res = runner.invoke(app, ["audit", "--banco", str(banco_auditoria)])
    assert res.exit_code == 0
    assert "Auditoría de Salud del Banco" in res.stdout
    assert "ej-completo" in res.stdout
    assert "ej-pobre" in res.stdout

    # Filtrar solo redacción pobre
    res_pobres = runner.invoke(app, ["audit", "--pobres", "--banco", str(banco_auditoria)])
    assert res_pobres.exit_code == 0
    assert "ej-pobre" in res_pobres.stdout
    assert "ej-completo" not in res_pobres.stdout

    # Salida JSON
    res_json = runner.invoke(app, ["audit", "--json", "--banco", str(banco_auditoria)])
    assert res_json.exit_code == 0
    data = json.loads(res_json.stdout)
    assert len(data) == 3
    assert any(d["id"] == "ej-completo" and d["redaccion_pobre"] is False for d in data)
    assert any(d["id"] == "ej-pobre" and d["redaccion_pobre"] is True for d in data)


def test_cli_verify_audit_subcommand(banco_auditoria):
    """Verifica el subcomando deckard verify audit / verify health."""
    res = runner.invoke(app, ["verify", "audit", "--banco", str(banco_auditoria)])
    assert res.exit_code == 0
    assert "Auditoría de Salud del Banco" in res.stdout
