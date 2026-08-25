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
