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


def test_exercise_family_and_project_modes():
    from deckard.core.models import Ejercicio, NivelBloom, GuiaSpec

    ej_lib = Ejercicio(
        id="tda_vector_lib",
        titulo="TDA Vector Dinámico - Librería",
        tema="estructuras_dinamicas",
        bloom=NivelBloom.APLICAR,
        minutos=45,
        tipo_entrega="libreria",
        familia="tda_vector",
        rol_familia="libreria",
        archivos_adicionales=["vector.h", "vector.c", "Makefile"],
    )

    ej_test = Ejercicio(
        id="tda_vector_tests",
        titulo="TDA Vector Dinámico - Suite de Tests",
        tema="estructuras_dinamicas",
        bloom=NivelBloom.ANALIZAR,
        minutos=30,
        tipo_entrega="makefile",
        familia="tda_vector",
        rol_familia="tests",
        dependencias=["tda_vector_lib"],
    )

    ej_app = Ejercicio(
        id="tda_vector_app",
        titulo="TDA Vector Dinámico - Aplicación Demo",
        tema="estructuras_dinamicas",
        bloom=NivelBloom.APLICAR,
        minutos=20,
        tipo_entrega="makefile",
        familia="tda_vector",
        rol_familia="uso",
        dependencias=["tda_vector_lib"],
    )

    assert ej_lib.tipo_ejercicio == "libreria"
    assert ej_test.familia == "tda_vector"
    assert ej_test.rol_familia == "tests"
    assert "tda_vector_lib" in ej_app.dependencias

    spec = GuiaSpec(
        nombre="Guía 4 - TDAs y Modularidad",
        duracion_min=120,
        tipo_entrega="makefile",
        familias=["tda_vector"],
    )
    assert spec.tipo_entrega == "makefile"
    assert "tda_vector" in spec.familias


def test_doctor_diagnostics():
    from deckard.core.doctor import ejecutar_diagnostico_doctor, chequear_herramienta
    from rich.console import Console
    cons = Console(record=True)
    res = ejecutar_diagnostico_doctor(console=cons)
    out = cons.export_text()
    assert "Diagnóstico del Entorno de Deckard" in out
    assert "gcc" in out


def test_classroom_export(tmp_path):
    from deckard.core.classroom import exportar_github_classroom
    from deckard.core.models import Ejercicio, NivelBloom

    ej = Ejercicio(
        id="demo_classroom",
        titulo="Invertir Vector Dinámico",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos=30,
        enunciado="Escribí una función que invierta un arreglo de enteros.",
        starter_code="void invertir(int *arr, int n) { /* tu codigo */ }\n",
    )
    dir_ej = tmp_path / "src_ej"
    dir_ej.mkdir()

    out_dir = tmp_path / "out_classroom"
    res = exportar_github_classroom(ej, dir_ej, out_dir)
    assert res.is_dir()
    assert (res / "README.md").is_file()
    assert (res / "Makefile").is_file()
    assert (res / "src" / "solution.c").is_file()
    assert (res / ".github" / "workflows" / "classroom.yml").is_file()
    
    readme = (res / "README.md").read_text(encoding="utf-8")
    assert "Invertir Vector Dinámico" in readme


def test_browser_rich_views(tmp_path):
    from deckard.core.browser import mostrar_vista_resumen_ejercicios, mostrar_detalle_ejercicio
    from deckard.core.models import Ejercicio, NivelBloom
    from rich.console import Console

    ej = Ejercicio(
        id="demo_browser",
        titulo="Ejercicio para Browser",
        tema="control",
        bloom=NivelBloom.RECORDAR,
        minutos=15,
        enunciado="Enunciado de prueba.",
        starter_code="int main(void) { return 0; }\n",
        verificado=True,
    )
    cons = Console(record=True)
    mostrar_vista_resumen_ejercicios([(tmp_path, ej)], console=cons)
    out = cons.export_text()
    assert "demo_browser" in out
    assert "RECORDAR" in out

    cons_det = Console(record=True)
    mostrar_detalle_ejercicio(ej, tmp_path, console=cons_det)
    out_det = cons_det.export_text()
    assert "Enunciado de prueba" in out_det


def test_export_notebook(tmp_path):
    from deckard.core.models import Ejercicio, NivelBloom
    from deckard.core.notebook import exportar_ejercicio_notebook
    import json

    ej = Ejercicio(
        id="ej_nb",
        titulo="Ejercicio Notebook",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos=20,
        enunciado="Enunciado con *markdown*.",
        starter_code="int main(void) { return 0; }\n",
    )
    nb_file = tmp_path / "ej_nb.ipynb"
    res = exportar_ejercicio_notebook(ej, nb_file)
    assert res.is_file()

    data = json.loads(res.read_text(encoding="utf-8"))
    assert data["nbformat"] == 4
    assert len(data["cells"]) >= 2
    assert "Ejercicio Notebook" in "".join(data["cells"][0]["source"])


def test_load_checker():
    from deckard.core.models import Ejercicio, NivelBloom
    from deckard.core.load_checker import auditar_carga_horaria, calcular_estadisticas_carga
    from rich.console import Console

    ej1 = Ejercicio(id="e1", titulo="E1", tema="t", bloom=NivelBloom.RECORDAR, minutos=60, enunciado="...")
    ej2 = Ejercicio(id="e2", titulo="E2", tema="t", bloom=NivelBloom.APLICAR, minutos=120, enunciado="...")

    stats = calcular_estadisticas_carga([ej1, ej2])
    assert stats["minutos_totales"] == 180
    assert stats["horas_totales"] == 3.0

    cons = Console(record=True)
    ok, msg = auditar_carga_horaria([ej1, ej2], max_horas_semanales=4.0, console=cons)
    assert ok is True

    ok_fail, msg_fail = auditar_carga_horaria([ej1, ej2], max_horas_semanales=2.0, console=cons)
    assert ok_fail is False


def test_variant_selection(tmp_path):
    from deckard.core.models import Ejercicio, NivelBloom
    from deckard.core.bank import guardar_ejercicio
    from deckard.core.variant import seleccionar_variantes_homologas

    banco_dir = tmp_path / "banco"
    banco_dir.mkdir()

    e1 = Ejercicio(id="ej_base", titulo="Base", tema="punteros", bloom=NivelBloom.APLICAR, minutos=30, enunciado="...")
    e2 = Ejercicio(id="ej_alt", titulo="Alternativo", tema="punteros", bloom=NivelBloom.APLICAR, minutos=30, enunciado="...")

    guardar_ejercicio(e1, banco_dir / "ej_base")
    guardar_ejercicio(e2, banco_dir / "ej_alt")

    variantes, mapeo = seleccionar_variantes_homologas(banco_dir, [e1], semilla=42)
    assert len(variantes) == 1
    assert variantes[0].id == "ej_alt"


def test_audit_guide_completeness():
    from deckard.core.models import Ejercicio, NivelBloom
    from deckard.core.audit_guide import auditar_completitud_guia
    from rich.console import Console

    e_completo = Ejercicio(
        id="comp",
        titulo="Completo",
        tema="t",
        bloom=NivelBloom.RECORDAR,
        minutos=15,
        enunciado="Este es un enunciado con suficiente longitud descriptiva.",
        starter_code="int main(void) { return 0; }\n",
        solucion_c="int main(void) { return 0; }\n",
    )
    cons = Console(record=True)
    res = auditar_completitud_guia([e_completo], console=cons)
    assert res["calidad_optima"] is True


def test_sync_git(tmp_path):
    from deckard.core.sync import sincronizar_banco_git
    res = sincronizar_banco_git(tmp_path / "nuevo_banco")
    assert res["ok"] is True



