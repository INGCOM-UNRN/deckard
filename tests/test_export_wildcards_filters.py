"""Tests para exportación con wildcards, filtros y --all en deckard."""

from pathlib import Path
import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import guardar_ejercicio
from deckard.core.models import Ejercicio

runner = CliRunner()


@pytest.fixture
def banco_poblado(tmp_path):
    banco = tmp_path / "banco"
    banco.mkdir(parents=True, exist_ok=True)

    ejercicios = [
        Ejercicio(
            id="vec-invertir",
            titulo="Invertir Vector",
            tema="arreglos",
            bloom=2,
            minutos_estimados=15,
            tags=["vectores", "algoritmos"],
            verificado=True,
            enunciado_md="Invertir un vector in-place.",
            starter_code="void invertir(int *v, size_t n);",
            solucion_c="void invertir(int *v, size_t n) {}",
        ),
        Ejercicio(
            id="vec-ordenar",
            titulo="Ordenar Vector",
            tema="arreglos",
            bloom=3,
            minutos_estimados=25,
            tags=["vectores", "ordenamiento"],
            verificado=False,
            enunciado_md="Ordenar un vector con bubble sort.",
            starter_code="void ordenar(int *v, size_t n);",
            solucion_c="void ordenar(int *v, size_t n) {}",
        ),
        Ejercicio(
            id="str-longitud",
            titulo="Longitud de Cadena",
            tema="cadenas",
            bloom=1,
            minutos_estimados=10,
            tags=["strings"],
            verificado=True,
            enunciado_md="Calcular longitud de string sin strlen.",
            starter_code="size_t mi_strlen(const char *s);",
            solucion_c="size_t mi_strlen(const char *s) { return 0; }",
        ),
        Ejercicio(
            id="ptr-swap",
            titulo="Intercambio de Punteros",
            tema="punteros",
            bloom=2,
            minutos_estimados=10,
            tags=["punteros", "algoritmos"],
            verificado=True,
            enunciado_md="Intercambiar dos valores vía punteros.",
            starter_code="void swap(int *a, int *b);",
            solucion_c="void swap(int *a, int *b) { int tmp=*a; *a=*b; *b=tmp; }",
        ),
    ]

    for ej in ejercicios:
        guardar_ejercicio(ej, banco)

    return banco


def test_export_all_flag(banco_poblado, tmp_path):
    """Debe exportar todos los ejercicios con --all / -a."""
    out_dir = tmp_path / "out_all"
    res = runner.invoke(app, [
        "export", "--all",
        "--banco", str(banco_poblado),
        "--type", "md",
        "-o", str(out_dir)
    ])
    assert res.exit_code == 0
    assert (out_dir / "vec-invertir.md").is_file()
    assert (out_dir / "vec-ordenar.md").is_file()
    assert (out_dir / "str-longitud.md").is_file()
    assert (out_dir / "ptr-swap.md").is_file()


def test_export_wildcard_patron(banco_poblado, tmp_path):
    """Debe soportar comodines como 'vec-*'."""
    out_dir = tmp_path / "out_wildcard"
    res = runner.invoke(app, [
        "export", "vec-*",
        "--banco", str(banco_poblado),
        "--type", "typst",
        "-o", str(out_dir)
    ])
    assert res.exit_code == 0
    assert (out_dir / "vec-invertir.typ").is_file()
    assert (out_dir / "vec-ordenar.typ").is_file()
    assert not (out_dir / "str-longitud.typ").exists()
    assert not (out_dir / "ptr-swap.typ").exists()


def test_export_filtro_tema(banco_poblado, tmp_path):
    """Debe filtrar por tema con --tema."""
    out_dir = tmp_path / "out_tema"
    res = runner.invoke(app, [
        "export",
        "--tema", "arreglos",
        "--banco", str(banco_poblado),
        "--type", "html",
        "-o", str(out_dir)
    ])
    assert res.exit_code == 0
    assert (out_dir / "vec-invertir.html").is_file()
    assert (out_dir / "vec-ordenar.html").is_file()
    assert not (out_dir / "str-longitud.html").exists()


def test_export_filtro_bloom(banco_poblado, tmp_path):
    """Debe filtrar por Bloom con --bloom."""
    out_dir = tmp_path / "out_bloom"
    res = runner.invoke(app, [
        "export",
        "--bloom", "1",
        "--banco", str(banco_poblado),
        "--type", "md",
        "-o", str(out_dir)
    ])
    assert res.exit_code == 0
    assert (out_dir / "str-longitud.md").is_file()
    assert not (out_dir / "vec-invertir.md").exists()


def test_export_filtro_tag(banco_poblado, tmp_path):
    """Debe filtrar por tag con --tag."""
    out_dir = tmp_path / "out_tag"
    res = runner.invoke(app, [
        "export",
        "--tag", "algoritmos",
        "--banco", str(banco_poblado),
        "--type", "md",
        "-o", str(out_dir)
    ])
    assert res.exit_code == 0
    assert (out_dir / "vec-invertir.md").is_file()
    assert (out_dir / "ptr-swap.md").is_file()
    assert not (out_dir / "str-longitud.md").exists()


def test_export_filtro_verificado(banco_poblado, tmp_path):
    """Debe filtrar por estado de verificación."""
    out_dir = tmp_path / "out_verif"
    res = runner.invoke(app, [
        "export",
        "--no-verificado",
        "--banco", str(banco_poblado),
        "--type", "md",
        "-o", str(out_dir)
    ])
    assert res.exit_code == 0
    assert (out_dir / "vec-ordenar.md").is_file()
    assert not (out_dir / "vec-invertir.md").exists()


def test_export_combinacion_wildcard_y_filtros(banco_poblado, tmp_path):
    """Debe combinar wildcard y filtros simultáneamente."""
    out_dir = tmp_path / "out_comb"
    res = runner.invoke(app, [
        "export", "vec-*",
        "--bloom", "2",
        "--banco", str(banco_poblado),
        "--type", "md",
        "-o", str(out_dir)
    ])
    assert res.exit_code == 0
    assert (out_dir / "vec-invertir.md").is_file()
    assert not (out_dir / "vec-ordenar.md").exists()


def test_export_sin_criterios_falla(banco_poblado):
    """Debe fallar si no se provee objetivo, --all ni filtros."""
    res = runner.invoke(app, ["export", "--banco", str(banco_poblado)])
    assert res.exit_code == 1
    assert "Debe especificar un objetivo" in res.stdout


def test_export_criterios_sin_resultados_falla(banco_poblado):
    """Debe fallar limpiamente con mensaje explicativo si no hay coincidencias."""
    res = runner.invoke(app, [
        "export",
        "--tema", "inexistente",
        "--banco", str(banco_poblado)
    ])
    assert res.exit_code == 1
    assert "No se encontró ningún ejercicio" in res.stdout
