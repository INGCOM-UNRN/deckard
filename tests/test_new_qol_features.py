"""Tests para las mejoras QoL de Deckard: cache SQLite, stats, lint, duplicate, deps, unpack, 2 columnas."""

from pathlib import Path
import pytest
from typer.testing import CliRunner
import yaml

from deckard.cli import app
from deckard.core.cache import update_bank_cache, search_cached_exercises, get_cache_db_path
from deckard.core.deps import build_dependency_graph
from deckard.core.bank import buscar_ejercicios, cargar_ejercicio
from deckard.core.pack import empaquetar_bundle_deckard, desempaquetar_bundle_deckard

runner = CliRunner()


@pytest.fixture
def sample_bank(tmp_path: Path) -> Path:
    banco = tmp_path / "banco"
    banco.mkdir()

    # Ejercicio 1: arreglos
    ej1_dir = banco / "sumar_elementos"
    ej1_dir.mkdir()
    ej1_data = {
        "id": "sumar_elementos",
        "titulo": "Suma de elementos de un arreglo",
        "tema": "arreglos",
        "bloom": 2,
        "minutos": 20,
        "starter_code": "int sumar(int* arr, int n) { return 0; }\n",
        "tags": ["arreglos", "punteros"],
        "verificado": True,
    }
    (ej1_dir / "ejercicio.yaml").write_text(yaml.safe_dump(ej1_data), encoding="utf-8")
    (ej1_dir / "enunciado.md").write_text("# Suma\nImplementar suma.", encoding="utf-8")
    (ej1_dir / "solucion.c").write_text("int sumar(int* arr, int n){ return 0; }", encoding="utf-8")
    (ej1_dir / "tests").mkdir()
    (ej1_dir / "tests" / "caso1.in").write_text("3\n1 2 3\n")
    (ej1_dir / "tests" / "caso1.out").write_text("6\n")

    # Ejercicio 2: punteros
    ej2_dir = banco / "invertir_punteros"
    ej2_dir.mkdir()
    ej2_data = {
        "id": "invertir_punteros",
        "titulo": "Inversión de vector con punteros",
        "tema": "punteros",
        "bloom": 3,
        "minutos": 30,
        "starter_code": "void invertir(int* arr, int n) { }\n",
        "tags": ["punteros", "aritmetica_punteros"],
        "verificado": False,
    }
    (ej2_dir / "ejercicio.yaml").write_text(yaml.safe_dump(ej2_data), encoding="utf-8")
    (ej2_dir / "enunciado.md").write_text("# Invertir\nImplementar inversión.", encoding="utf-8")
    (ej2_dir / "solucion.c").write_text("void invertir(int* arr, int n){}", encoding="utf-8")

    return banco


def test_cache_sqlite_indexing_and_search(sample_bank: Path, tmp_path: Path):
    db_p = tmp_path / "test_index.db"
    count = update_bank_cache(sample_bank, db_path=db_p, force=True)
    assert count == 2

    # Búsqueda por tema
    res_arreglos = search_cached_exercises(sample_bank, tema="arreglos", db_path=db_p)
    assert res_arreglos is not None
    assert len(res_arreglos) == 1
    assert res_arreglos[0][1].id == "sumar_elementos"

    # Búsqueda por bloom
    res_bloom = search_cached_exercises(sample_bank, bloom=3, db_path=db_p)
    assert res_bloom is not None
    assert len(res_bloom) == 1
    assert res_bloom[0][1].id == "invertir_punteros"


def test_cli_stats(sample_bank: Path):
    res = runner.invoke(app, ["stats", "--banco", str(sample_bank)])
    assert res.exit_code == 0
    assert "Estadísticas del Banco Deckard" in res.stdout
    assert "Recordar" in res.stdout or "Comprender" in res.stdout
    assert "arreglos" in res.stdout


def test_cli_lint(sample_bank: Path):
    res = runner.invoke(app, ["lint", "--banco", str(sample_bank)])
    assert res.exit_code == 0
    assert "Deckard Linter" in res.stdout
    assert "Conforme" in res.stdout


def test_cli_duplicate(sample_bank: Path):
    res = runner.invoke(app, ["duplicate", "sumar_elementos", "sumar_elementos_v2", "--banco", str(sample_bank)])
    assert res.exit_code == 0
    assert (sample_bank / "sumar_elementos_v2" / "ejercicio.yaml").is_file()
    
    clonado = cargar_ejercicio(sample_bank / "sumar_elementos_v2")
    assert clonado.id == "sumar_elementos_v2"
    assert not clonado.verificado


def test_cli_deps_graph(sample_bank: Path):
    res = runner.invoke(app, ["deps", "--banco", str(sample_bank)])
    assert res.exit_code == 0
    assert "Grafo de Dependencias Conceptuales" in res.stdout
    assert "sumar_elementos" in res.stdout

    res_mermaid = runner.invoke(app, ["deps", "--banco", str(sample_bank), "--mermaid"])
    assert res_mermaid.exit_code == 0
    assert "graph TD" in res_mermaid.stdout


def test_pack_and_unpack_bundle(sample_bank: Path, tmp_path: Path):
    tar_dest = tmp_path / "bundle.deckard.tar.gz"
    res_pack = empaquetar_bundle_deckard(sample_bank, tar_dest)
    assert res_pack.is_file()

    extract_dest = tmp_path / "extracted_bank"
    res_unpack = desempaquetar_bundle_deckard(tar_dest, extract_dest)
    assert (extract_dest / "sumar_elementos" / "ejercicio.yaml").is_file()
