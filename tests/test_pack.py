"""Pruebas de empaquetado de ejercicios y guías (.ripkg y starter repos) en deckard."""

from pathlib import Path
import tomllib
import zipfile
import pytest
import yaml
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import guardar_ejercicio
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.pack import (
    MANIFEST_NAME,
    PAYLOAD_PREFIX,
    PackError,
    empaquetar_ejercicio,
    empaquetar_guia,
    exportar_starter_repo,
)

runner = CliRunner()


@pytest.fixture()
def ejercicio_con_tests(tmp_path) -> Path:
    banco = tmp_path / "banco"
    banco.mkdir()
    ej = Ejercicio(
        id="invertir-vector",
        titulo="Invertir Vector",
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=25,
        enunciado_md="# Invertir Vector\nDado un vector, invertirlo in-place.",
        solucion_c=(
            "#include <stdio.h>\n"
            "int main(void) {\n"
            "    int a, b;\n"
            "    if (scanf(\"%d %d\", &a, &b) == 2) {\n"
            "        printf(\"%d %d\\n\", b, a);\n"
            "    }\n"
            "    return 0;\n"
            "}\n"
        ),
        pistas=["Usá una variable auxiliar para el swap.", "Recorré hasta n/2."],
    )
    dir_ej = guardar_ejercicio(ej, banco)
    # Crear testcases
    tests_dir = dir_ej / "tests"
    tests_dir.mkdir()
    (tests_dir / "caso_01.in").write_text("10 20\n", encoding="utf-8")
    (tests_dir / "caso_01.out").write_text("20 10\n", encoding="utf-8")
    return dir_ej


def test_empaquetar_ejercicio_genera_ripkg_valido(ejercicio_con_tests, tmp_path):
    dest = tmp_path / "invertir-vector.ripkg"
    resultado = empaquetar_ejercicio(ejercicio_con_tests, out_path=dest)

    assert dest.is_file()
    assert resultado.output_path == dest
    assert resultado.archivos_payload >= 4  # enunciado, readme, pistas, caso_01.in, caso_01.out
    assert resultado.checks_habilitados > 0
    assert not resultado.firmado

    # Verificar estructura interna del ZIP
    with zipfile.ZipFile(dest) as zf:
        nombres = zf.namelist()
        assert MANIFEST_NAME in nombres
        assert f"{PAYLOAD_PREFIX}enunciado.md" in nombres
        assert f"{PAYLOAD_PREFIX}pistas.txt" in nombres
        assert f"{PAYLOAD_PREFIX}caso_01.in" in nombres
        assert f"{PAYLOAD_PREFIX}caso_01.out" in nombres

        # Validar TOML del manifiesto
        manifest = tomllib.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        assert manifest["meta"]["practica"] == "invertir-vector"
        assert manifest["compiler"]["executable"] == "gcc"
        assert "dynamic.testcases" in manifest["checks"]
        assert manifest["integrity"]["unsigned"] is True

        # Validar integridad SHA-256
        sha_dict = manifest["integrity"]["sha256"]
        for rel_name, expected_hash in sha_dict.items():
            content = zf.read(f"{PAYLOAD_PREFIX}{rel_name}")
            import hashlib
            assert hashlib.sha256(content).hexdigest() == expected_hash


def test_exportar_starter_repo(ejercicio_con_tests, tmp_path):
    dir_starter = tmp_path / "starter_repo"
    exportar_starter_repo(
        ejercicio=guardar_ejercicio(
            Ejercicio(
                id="sumar",
                titulo="Sumar",
                tema="intro",
                bloom=NivelBloom.RECORDAR,
                minutos_estimados=10,
                enunciado_md="Sumar 2 números.",
                solucion_c="int main(void){return 0;}\n",
            ),
            tmp_path / "banco2",
        ).parent / "sumar",  # carga desde banco
        destino=dir_starter,
        tests_dir=ejercicio_con_tests / "tests",
    )

    assert (dir_starter / "README.md").is_file()
    assert (dir_starter / "main.c").is_file()
    assert (dir_starter / "Makefile").is_file()
    assert (dir_starter / "ripley.toml").is_file()
    assert (dir_starter / "tests" / "caso_01.in").is_file()


def test_empaquetar_guia(ejercicio_con_tests, tmp_path):
    banco = ejercicio_con_tests.parent
    guia_yaml = tmp_path / "guia_tp1.yaml"
    with open(guia_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "nombre": "TP1 - Vectores",
            "ejercicios": [{"id": "invertir-vector", "minutos": 25}],
        }, f)

    out_dir = tmp_path / "dist"
    resultados = empaquetar_guia(
        guia_spec_file=guia_yaml,
        banco=banco,
        out_dir=out_dir,
        generar_starter=True,
    )

    assert len(resultados) == 1
    assert (out_dir / "invertir-vector.ripkg").is_file()
    assert (out_dir / "starters" / "invertir-vector" / "Makefile").is_file()


def test_cli_pack_ejercicio(ejercicio_con_tests):
    banco = ejercicio_con_tests.parent
    res = runner.invoke(app, ["pack", "invertir-vector", "--banco", str(banco), "--starter"])
    assert res.exit_code == 0
    assert "✓ Paquete creado" in res.stdout
    assert "✓ Starter repo" in res.stdout
    assert (banco / "invertir-vector.ripkg").is_file()


def test_cli_pack_guia(ejercicio_con_tests, tmp_path):
    banco = ejercicio_con_tests.parent
    guia_yaml = tmp_path / "guia_parcial.yaml"
    with open(guia_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "nombre": "Parcial",
            "ejercicios": [{"id": "invertir-vector"}],
        }, f)

    res = runner.invoke(app, ["pack", str(guia_yaml), "--banco", str(banco)])
    assert res.exit_code == 0
    assert "✓ Guía empaquetada: 1 paquetes generados" in res.stdout


def test_compatibilidad_con_ripley_bundle(ejercicio_con_tests, tmp_path):
    """Verifica que el bundle emitido por deckard es leído y ejecutado sin errores por Ripley."""
    try:
        import sys
        sys.path.insert(0, "/home/mrtin/dev/forks/ripley/src")
        from ripley.pipeline.bundle import load_bundle
        from ripley.pipeline.student_runner import run_bundle
    except ImportError:
        pytest.skip("Ripley no disponible en PYTHONPATH")

    dest = tmp_path / "test_ripley_compat.ripkg"
    empaquetar_ejercicio(ejercicio_con_tests, out_path=dest)

    # 1. Cargar con Ripley
    bundle = load_bundle(dest)
    assert bundle.practica == "invertir-vector"
    assert not bundle.signed

    # 2. Ejecutar solución contra el bundle empaquetado por deckard
    solucion_path = ejercicio_con_tests / "solucion.c"
    reporte = run_bundle(dest, [solucion_path])
    assert reporte.compiled_ok
    assert reporte.success
