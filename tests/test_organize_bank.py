"""Tests para la funcionalidad de reorganización del banco de ejercicios en Deckard."""

from pathlib import Path
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import buscar_ejercicios, cargar_ejercicio, guardar_ejercicio, reorganizar_banco
from deckard.core.models import CasoTestFuncion, Ejercicio, FuncionSpec, NivelBloom

runner = CliRunner()


def test_ejercicio_ruta_categoria():
    ej_fn = Ejercicio(
        id="inv-vec",
        titulo="Invertir Vector",
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=20,
        enunciado_md="Consigna",
        funciones=[FuncionSpec(nombre="invertir", retorno="void", parametros="int* v, size_t n")],
    )

    ej_io = Ejercicio(
        id="sum-stdin",
        titulo="Sumar Stdin",
        tema="basicos",
        bloom=NivelBloom.RECORDAR,
        minutos_estimados=10,
        enunciado_md="Consigna",
    )

    assert ej_fn.tipo_ejercicio == "funciones"
    assert ej_io.tipo_ejercicio == "io"

    # Criterio bloom
    assert ej_fn.ruta_categoria("bloom") == Path("b3-aplicar/inv-vec")
    assert ej_io.ruta_categoria("bloom") == Path("b1-recordar/sum-stdin")

    # Criterio tipo
    assert ej_fn.ruta_categoria("tipo") == Path("funciones/inv-vec")
    assert ej_io.ruta_categoria("tipo") == Path("io/sum-stdin")

    # Criterio bloom/tipo
    assert ej_fn.ruta_categoria("bloom/tipo") == Path("b3-aplicar/funciones/inv-vec")
    assert ej_io.ruta_categoria("bloom/tipo") == Path("b1-recordar/io/sum-stdin")

    # Criterio tipo/bloom
    assert ej_fn.ruta_categoria("tipo/bloom") == Path("funciones/b3-aplicar/inv-vec")
    assert ej_io.ruta_categoria("tipo/bloom") == Path("io/b1-recordar/sum-stdin")

    # Criterio tema/bloom
    assert ej_fn.ruta_categoria("tema/bloom") == Path("arreglos/b3-aplicar/inv-vec")
    assert ej_io.ruta_categoria("tema/bloom") == Path("basicos/b1-recordar/sum-stdin")

    # Criterio plano
    assert ej_fn.ruta_categoria("plano") == Path("inv-vec")


def test_reorganizar_banco_dry_run_y_move(tmp_path: Path):
    banco = tmp_path / "banco"
    banco.mkdir()

    ej1 = Ejercicio(
        id="ej-func-1",
        titulo="Test Funciones",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=20,
        enunciado_md="Consigna 1",
        funciones=[FuncionSpec(nombre="swap", retorno="void", parametros="int* a, int* b")],
    )
    ej2 = Ejercicio(
        id="ej-io-1",
        titulo="Test IO",
        tema="flujo",
        bloom=NivelBloom.RECORDAR,
        minutos_estimados=15,
        enunciado_md="Consigna 2",
    )

    d1 = guardar_ejercicio(ej1, banco)
    d2 = guardar_ejercicio(ej2, banco)

    # 1. Simulación (dry-run)
    movs_sim = reorganizar_banco(banco, criterio="bloom/tipo", dry_run=True)
    assert len(movs_sim) == 2
    assert all(m.cambio for m in movs_sim)
    # Verificar que los directorios originales siguen intactos
    assert d1.is_dir()
    assert d2.is_dir()

    # 2. Ejecución real del movimiento
    movs = reorganizar_banco(banco, criterio="bloom/tipo", dry_run=False)
    assert len(movs) == 2

    # Verificar nueva estructura
    nuevo_d1 = banco / "b3-aplicar" / "funciones" / "ej-func-1"
    nuevo_d2 = banco / "b1-recordar" / "io" / "ej-io-1"

    assert nuevo_d1.is_dir()
    assert (nuevo_d1 / "ejercicio.yaml").is_file()
    assert (nuevo_d1 / "ej-func-1.h").is_file()

    assert nuevo_d2.is_dir()
    assert (nuevo_d2 / "ejercicio.yaml").is_file()

    # Los directorios viejos planos no deben existir
    assert not (banco / "ej-func-1").exists()
    assert not (banco / "ej-io-1").exists()

    # buscar_ejercicios debe encontrar ambos
    encontrados = buscar_ejercicios(banco, recursivo=True)
    assert len(encontrados) == 2
    ids = [e.id for _, e in encontrados]
    assert "ej-func-1" in ids
    assert "ej-io-1" in ids


def test_reorganizar_banco_copy(tmp_path: Path):
    banco = tmp_path / "banco"
    banco.mkdir()
    destino = tmp_path / "banco_organizado"

    ej = Ejercicio(
        id="ej-test",
        titulo="Test Copia",
        tema="memoria",
        bloom=NivelBloom.ANALIZAR,
        minutos_estimados=25,
        enunciado_md="Consigna",
    )
    guardar_ejercicio(ej, banco)

    movs = reorganizar_banco(banco, criterio="bloom", dir_destino=destino, copy=True)
    assert len(movs) == 1

    # El original debe persistir
    assert (banco / "ej-test").is_dir()

    # La copia debe existir en destino
    copia_dir = destino / "b4-analizar" / "ej-test"
    assert copia_dir.is_dir()
    assert (copia_dir / "ejercicio.yaml").is_file()


def test_cli_organize_command(tmp_path: Path):
    banco = tmp_path / "banco"
    banco.mkdir()

    ej = Ejercicio(
        id="reorg-cli",
        titulo="CLI Reorg",
        tema="arreglos",
        bloom=NivelBloom.EVALUAR,
        minutos_estimados=30,
        enunciado_md="Consigna CLI",
        funciones=[FuncionSpec(nombre="evaluar", retorno="bool", parametros="void")],
    )
    guardar_ejercicio(ej, banco)

    # Probar CLI con dry-run
    res_dry = runner.invoke(app, ["organize", "--banco", str(banco), "--by", "bloom/tipo", "--dry-run"])
    assert res_dry.exit_code == 0
    assert "reorg-cli" in res_dry.stdout
    assert "b5-evaluar" in res_dry.stdout
    assert "funciones" in res_dry.stdout
    assert "Simulación" in res_dry.stdout

    # Probar CLI real
    res = runner.invoke(app, ["organize", "--banco", str(banco), "--by", "bloom/tipo"])
    assert res.exit_code == 0
    assert "reorganizados" in res.stdout

    # Verificar existencia en disco
    target = banco / "b5-evaluar" / "funciones" / "reorg-cli"
    assert target.is_dir()
    assert (target / "ejercicio.yaml").is_file()
