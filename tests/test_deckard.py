"""Pruebas de deckard: modelos, banco y composición de guías."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from deckard.core.bank import componer_guia, guardar_ejercicio, listar_ejercicios
from deckard.core.models import Ejercicio, GuiaSpec, NivelBloom


def _ejercicio(eid: str, tema: str, bloom: int, minutos: int) -> Ejercicio:
    return Ejercicio(
        id=eid, titulo=f"T {eid}", tema=tema,
        bloom=bloom, minutos_estimados=minutos,
        enunciado_md=f"Enunciado {eid}", solucion_c="int main(void){return 0;}\n",
    )


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

def test_id_valida_formato():
    with pytest.raises(ValidationError):
        _ejercicio("ID Invalido!", "arreglos", 3, 10)


def test_bloom_solo_1_a_5():
    with pytest.raises(ValidationError):
        _ejercicio("x", "arreglos", 6, 10)
    e = _ejercicio("x", "arreglos", 5, 10)
    assert e.bloom is NivelBloom.EVALUAR


def test_pistas_vacias_se_descartan():
    e = _ejercicio("pistas", "recursion", 4, 15)
    e.pistas = ["", "   ", "Pista real"]
    assert e.pistas == ["Pista real"]


# ---------------------------------------------------------------------------
# Banco persistido
# ---------------------------------------------------------------------------

@pytest.fixture()
def banco(tmp_path):
    for eid, tema, bloom, mins in (
        ("suma-basica", "aritmetica", 1, 10),
        ("lista-enlazada", "punteros", 3, 30),
        ("hash-tabla", "estructuras", 5, 45),
        ("invertir-arreglo", "arreglos", 2, 20),
        ("arbol-abb", "estructuras", 4, 50),
    ):
        guardar_ejercicio(_ejercicio(eid, tema, bloom, mins), tmp_path)
    return tmp_path


def test_guardar_y_listar_roundtrip(banco):
    ejercicios = listar_ejercicios(banco)
    ids = [e.id for e in ejercicios]
    assert "suma-basica" in ids and "arbol-abb" in ids


def test_solucion_c_se_persiste_como_archivo(banco):
    dir_ej = banco / "suma-basica"
    assert (dir_ej / "solucion.c").is_file()
    # el YAML no duplica la solución embebida si ya existe el archivo
    texto = (dir_ej / "ejercicio.yaml").read_text()
    assert "solucion_c" not in texto or "int main" not in texto.split("solucion_c")[1][:5]


# ---------------------------------------------------------------------------
# Composición de guías
# ---------------------------------------------------------------------------

def test_compose_respeta_presupuesto_de_minutos(banco):
    spec = GuiaSpec(nombre="Corta", duracion_min=120, margen_carga=0.8)  # 96 min útiles
    seleccion = componer_guia(banco, spec)
    assert seleccion.minutos_totales <= 96
    assert len(seleccion.ejercicios) >= 2  # hay ejercicios baratos que sí entran


def test_compose_orden_por_dificultad_creciente(banco):
    spec = GuiaSpec(nombre="Progresiva", duracion_min=200, margen_carga=0.9,
                    cantidad_maxima=5)
    seleccion = componer_guia(banco, spec)
    blooms = [int(e.bloom) for e in seleccion.ejercicios]
    assert blooms == sorted(blooms)


def test_compose_filtra_por_tema(banco):
    spec = GuiaSpec(nombre="Solo punteros", duracion_min=120,
                    temas=["punteros"], cantidad_maxima=5)
    sel = componer_guia(banco, spec)
    assert all(e.tema == "punteros" for e in sel.ejercicios)
    assert sel.minutos_totales == 30


def test_compose_diversidad_maximo_dos_por_tema_al_principio(banco):
    # banco con muchos de un mismo tema barato: no debe llenarse con repetidos
    banco_rico = banco
    for i in range(5):
        guardar_ejercicio(_ejercicio(f"arit-{i}", "aritmetica", 2, 8), banco_rico)
    spec = GuiaSpec(nombre="Diversa", duracion_min=90, margen_carga=0.9)
    sel = componer_guia(banco_rico, spec)
    temas_primeros = [e.tema for e in sel.ejercicios[: len(sel.ejercicios) // 2]]
    assert temas_primeros.count("aritmetica") <= 2


def test_compose_sin_candidatos_devuelve_seleccion_vacia(banco):
    spec = GuiaSpec(nombre="Imposible", duracion_min=30,
                    temas=["cuantica"], cantidad_maxima=5)
    sel = componer_guia(banco, spec)
    assert sel.ejercicios == [] and sel.minutos_totales == 0


# ---------------------------------------------------------------------------
# Búsqueda y operaciones masivas (repositorios grandes / comodines)
# ---------------------------------------------------------------------------

from deckard.core.bank import buscar_ejercicios, actualizar_verificacion
from typer.testing import CliRunner
from deckard.cli import app
from unittest.mock import patch

runner = CliRunner()


def test_buscar_ejercicios_con_wildcard(banco):
    # Buscar con comodín '*-tabla' o 'arbol-*'
    res = buscar_ejercicios(banco, patron="*-tabla")
    assert len(res) == 1
    assert res[0][1].id == "hash-tabla"

    # Buscar con comodín general '*'
    todos = buscar_ejercicios(banco, patron="*")
    assert len(todos) == 5

    # Buscar por tema
    estructuras = buscar_ejercicios(banco, tema="estructuras")
    assert len(estructuras) == 2
    assert {e.id for _, e in estructuras} == {"hash-tabla", "arbol-abb"}

    # Buscar por nivel de Bloom
    bloom1 = buscar_ejercicios(banco, bloom=1)
    assert len(bloom1) == 1
    assert bloom1[0][1].id == "suma-basica"


def test_buscar_ejercicios_recursivo(tmp_path):
    # Estructura anidada: banco/tp1/ej1 y banco/tp2/avanzado/ej2
    banco = tmp_path / "banco_anidado"
    dir_tp1 = banco / "tp1"
    dir_tp2 = banco / "tp2" / "avanzado"
    guardar_ejercicio(_ejercicio("ej-uno", "intro", 1, 10), dir_tp1)
    guardar_ejercicio(_ejercicio("ej-dos", "punteros", 3, 20), dir_tp2)

    encontrados = buscar_ejercicios(banco, recursivo=True)
    assert len(encontrados) == 2
    ids = {e.id for _, e in encontrados}
    assert ids == {"ej-uno", "ej-dos"}


def test_actualizar_verificacion(banco):
    dir_ej = banco / "suma-basica"
    actualizar_verificacion(dir_ej, True)
    ej = buscar_ejercicios(banco, patron="suma-basica")[0][1]
    assert ej.verificado is True


def test_cli_bank_list_con_filtros(banco):
    res = runner.invoke(app, ["bank", "list", "*-tabla", "--banco", str(banco)])
    assert res.exit_code == 0
    assert "hash-tabla" in res.stdout
    assert "suma-basica" not in res.stdout

    res_tema = runner.invoke(app, ["bank", "list", "--tema", "punteros", "--banco", str(banco)])
    assert res_tema.exit_code == 0
    assert "lista-enlazada" in res_tema.stdout


def test_cli_fuzz_dry_run_con_wildcard(banco):
    res = runner.invoke(app, ["fuzz", "*", "--banco", str(banco), "--dry-run"])
    assert res.exit_code == 0
    assert "Ejercicios seleccionados para fuzz" in res.stdout
    assert "suma-basica" in res.stdout
    assert "hash-tabla" in res.stdout


def test_cli_fuzz_all_ejecuta_batch(banco):
    with patch("shutil.which", return_value="/usr/bin/dredd"), \
         patch("subprocess.run") as mock_subproc:
        mock_subproc.return_value.returncode = 0
        mock_subproc.return_value.stdout = ""
        mock_subproc.return_value.stderr = ""

        res = runner.invoke(app, ["fuzz", "--all", "--banco", str(banco), "-n", "4"])
        assert res.exit_code == 0
        assert "Ejecutando fuzz-gen sobre 5 ejercicios" in res.stdout
        assert "5 completados" in res.stdout


def test_cli_verify_all_batch(banco):
    with patch("deckard.cli.verificar_ejercicio") as mock_verify:
        from deckard.core.verify import ResultadoVerify
        mock_verify.return_value = ResultadoVerify("ej", True, "Todo en orden")

        res = runner.invoke(app, ["verify", "--all", "--banco", str(banco)])
        assert res.exit_code == 0
        assert "Verificando 5 ejercicios" in res.stdout
        assert "5/5 exitosos" in res.stdout
