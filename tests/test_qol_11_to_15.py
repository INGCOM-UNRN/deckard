"""Tests para las mejoras QoL 11 a 15 de Deckard:
11. Starter ZIPs con clave de entrega
12. Detector de ambigüedades en enunciados
13. Badges de dificultad y Bloom en Typst
14. Generador de diagramas de estructuras de datos ASCII
15. Gestor de pistas escalonadas (Hints)
"""

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner
import zipfile

from deckard.cli import app
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.starter_zip import empaquetar_starter_zip, empaquetar_guia_zip, generar_clave_entrega
from deckard.core.ambiguity_checker import (
    analizar_ambiguedades_ejercicio,
    auditar_banco_ambiguedades,
)
from deckard.core.ascii_diagrams import (
    generar_diagrama_lista_enlazada,
    generar_diagrama_lista_doble,
    generar_diagrama_arbol_binario,
    generar_diagrama_pila,
    generar_diagrama_cola,
    generar_diagrama_matriz,
    generar_diagrama_punteros_dobles,
    obtener_diagrama_por_tipo,
)
from deckard.core.hints import (
    ofuscar_texto_rot13,
    formatear_pistas_comentarios_c,
    generar_archivo_pistas_md,
    incrustar_pistas_en_starter,
)
from deckard.core.export import generar_badges_typst, renderizar_ejercicio_typst, renderizar_guia_typst

runner = CliRunner()


@pytest.fixture
def ejercicio_ejemplo():
    return Ejercicio(
        id="tp1_lista",
        titulo="Implementación de Lista Enlazada",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=45,
        enunciado_md="Desarrollar una lista simplemente enlazada en C.\n\nEntrada: [10, 20]\nSalida: 30\nSi el puntero es NULL retornar error.",
        tags=["punteros", "tda", "memoria_dinamica"],
        pistas=[
            "Recordá reservar memoria con malloc para cada nuevo nodo.",
            "No te olvides de verificar si malloc retorna NULL.",
            "Para liberar la lista, guardá el puntero al siguiente nodo antes de liberar el actual.",
        ],
        archivos={
            "tp1_lista.c": "int main(void) { return 0; }\n",
            "test_lista.c": "int test(void) { return 0; }\n",
        },
    )


# ==============================================================================
# QoL 11: STARTER ZIP
# ==============================================================================

def test_starter_zip_empaquetado_individual(tmp_path, ejercicio_ejemplo):
    dest_zip = tmp_path / "starter_tp1.zip"
    zip_path, clave, sha_h = empaquetar_starter_zip(
        ejercicio_ejemplo, out_zip=dest_zip, incluir_tests=True, incluir_pistas=True
    )
    assert zip_path.exists()
    assert clave.startswith("DKD-")
    assert len(sha_h) == 64

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "tp1_lista/README.md" in namelist
        assert "tp1_lista/tp1_lista.c" in namelist
        assert "tp1_lista/Makefile" in namelist
        assert "tp1_lista/ENTREGA_KEY.txt" in namelist
        assert "tp1_lista/metadata.json" in namelist

        key_data = zf.read("tp1_lista/ENTREGA_KEY.txt").decode("utf-8").strip()
        assert key_data == clave


def test_cli_pack_zip(tmp_path, ejercicio_ejemplo):
    ej_yaml = tmp_path / "ejercicio.yaml"
    import yaml
    ej_yaml.write_text(yaml.safe_dump({
        "id": "tp1_lista",
        "titulo": ejercicio_ejemplo.titulo,
        "tema": "punteros",
        "bloom": "APLICAR",
        "minutos_estimados": 45,
        "enunciado_md": ejercicio_ejemplo.enunciado_md,
    }), encoding="utf-8")
    out_zip = tmp_path / "test_out.zip"
    res = runner.invoke(app, ["pack-zip", str(ej_yaml), "-o", str(out_zip)])
    assert res.exit_code == 0
    assert "Starter ZIP empaquetado exitosamente" in res.stdout
    assert out_zip.exists()


# ==============================================================================
# QoL 12: AMBIGUITY CHECKER
# ==============================================================================

def test_ambiguity_checker_deteccion():
    ej_ambiguo = Ejercicio(
        id="ej_vago",
        titulo="Ejercicio de Prueba",
        tema="vectores",
        bloom=NivelBloom.COMPRENDER,
        minutos_estimados=20,
        enunciado_md="Hacer una función rápida para saber si un vector es bueno y eficiente, etc.",
    )
    obs = analizar_ambiguedades_ejercicio(ej_ambiguo)
    assert len(obs) >= 2
    categorias = [o.categoria for o in obs]
    assert "Taxonomía Bloom" in categorias or "Precisión Técnica" in categorias

    banco_report = auditar_banco_ambiguedades([ej_ambiguo])
    assert banco_report["total_observaciones"] >= 2


def test_cli_check_ambiguity(tmp_path):
    ej_dir = tmp_path / "ej1"
    ej_dir.mkdir()
    import yaml
    (ej_dir / "ejercicio.yaml").write_text(yaml.safe_dump({
        "id": "ej1",
        "titulo": "Calcular Promedio",
        "tema": "vectores",
        "bloom": "APLICAR",
        "minutos_estimados": 15,
        "enunciado_md": "Implementar una función que calcule el promedio de un arreglo de enteros. Si el vector está vacío retornar 0. Entrada: [1, 2, 3] Salida: 2.0.",
    }), encoding="utf-8")
    res = runner.invoke(app, ["check-ambiguity", str(ej_dir / "ejercicio.yaml"), "--json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["total_ejercicios"] == 1
    assert data["total_observaciones"] == 0


# ==============================================================================
# QoL 13: BADGES TYPST
# ==============================================================================

def test_typst_badges_generation(ejercicio_ejemplo):
    badges_code = generar_badges_typst(ejercicio_ejemplo)
    assert "APLICAR" in badges_code
    assert "45 min" in badges_code
    assert "PUNTEROS" in badges_code

    typst_salida, _ = renderizar_ejercicio_typst(ejercicio_ejemplo, incluir_badges=True)
    assert "APLICAR" in typst_salida


# ==============================================================================
# QoL 14: ASCII DIAGRAMS
# ==============================================================================

def test_ascii_diagrams_generation():
    d_lista = generar_diagrama_lista_enlazada(["A", "B", "C"])
    assert "HEAD ->" in d_lista
    assert "[ A | •-]->" in d_lista

    d_doble = generar_diagrama_lista_doble(["X", "Y"])
    assert "<===>" in d_doble

    d_arbol = generar_diagrama_arbol_binario(raiz="100")
    assert "[100]" in d_arbol

    d_pila = generar_diagrama_pila(["X", "Y"])
    assert "TOPE ->" in d_pila

    d_cola = generar_diagrama_cola(["1", "2"])
    assert "FRENTE" in d_cola

    d_matriz = generar_diagrama_matriz(filas=2, columnas=2)
    assert "M[0][0]" in d_matriz

    d_ptr = generar_diagrama_punteros_dobles("tabla", filas=2)
    assert "tabla (int**)" in d_ptr

    assert "HEAD" in obtener_diagrama_por_tipo("lista")
    assert "<===>" in obtener_diagrama_por_tipo("lista-doble")
    assert "TOPE" in obtener_diagrama_por_tipo("pila")


def test_cli_ascii_diagram(tmp_path):
    out_file = tmp_path / "diagrama.txt"
    res = runner.invoke(app, ["ascii-diagram", "arbol", "-o", str(out_file)])
    assert res.exit_code == 0
    assert out_file.exists()
    assert "[50]" in out_file.read_text(encoding="utf-8")


# ==============================================================================
# QoL 15: HINTS ESCALONADAS
# ==============================================================================

def test_hints_generation_and_rot13(ejercicio_ejemplo):
    md_pistas = generar_archivo_pistas_md(ejercicio_ejemplo, ofuscar=False)
    assert "Pistas Escalonadas" in md_pistas
    assert "malloc" in md_pistas

    c_pistas = formatear_pistas_comentarios_c(ejercicio_ejemplo.pistas, nivel_maximo=2)
    assert "PISTA 1" in c_pistas
    assert "PISTA 2" in c_pistas
    assert "PISTA 3" not in c_pistas

    c_incrustado = incrustar_pistas_en_starter("int main(void) {}", ejercicio_ejemplo.pistas)
    assert "DECKARD HINTS" in c_incrustado
    assert "int main(void) {}" in c_incrustado

    rot = ofuscar_texto_rot13("Hola Mundo")
    assert rot != "Hola Mundo"
    assert ofuscar_texto_rot13(rot) == "Hola Mundo"


def test_cli_export_hints(tmp_path, ejercicio_ejemplo):
    ej_yaml = tmp_path / "ejercicio.yaml"
    import yaml
    ej_yaml.write_text(yaml.safe_dump({
        "id": ejercicio_ejemplo.id,
        "titulo": ejercicio_ejemplo.titulo,
        "tema": "punteros",
        "bloom": "APLICAR",
        "minutos_estimados": 45,
        "enunciado_md": "Test",
        "pistas": [
            "Pista 1 conceptual",
            "Pista 2 tecnica",
        ],
    }), encoding="utf-8")
    out_md = tmp_path / "PISTAS.md"
    res = runner.invoke(app, ["export-hints", str(ej_yaml), "-o", str(out_md)])
    assert res.exit_code == 0
    assert out_md.exists()
    assert "Pista 1 conceptual" in out_md.read_text(encoding="utf-8")

    # Prueba con formato comentarios C y rot13
    res_c = runner.invoke(app, ["export-hints", str(ej_yaml), "-c", "--rot13"])
    assert res_c.exit_code == 0
    assert "PISTA 1 (Ofuscada con ROT13" in res_c.stdout
