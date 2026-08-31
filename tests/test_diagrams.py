"""Tests para generador de diagramas de estructuras de datos (ASCII, Mermaid, PlantUML)."""

from deckard.core.diagrams import (
    generar_diagrama_lista_enlazada,
    generar_diagrama_lista_doble,
    generar_diagrama_arbol_binario,
    generar_diagrama_pila,
    generar_diagrama_cola,
    generar_diagrama_matriz,
    generar_diagrama_punteros_dobles,
    obtener_diagrama_por_tipo,
)
from deckard.core.models import Ejercicio, DiagramaSpec, NivelBloom


def test_diagramas_formatos_lista():
    ascii_diag = generar_diagrama_lista_enlazada(formato="ascii")
    assert "HEAD ->" in ascii_diag
    assert "```text" in ascii_diag

    mermaid_diag = generar_diagrama_lista_enlazada(formato="mermaid")
    assert "graph LR" in mermaid_diag
    assert "```mermaid" in mermaid_diag

    puml_diag = generar_diagrama_lista_enlazada(formato="plantuml")
    assert "@startuml" in puml_diag
    assert "```plantuml" in puml_diag


def test_diagramas_formatos_arbol():
    mermaid_tree = generar_diagrama_arbol_binario(formato="mermaid")
    assert "graph TD" in mermaid_tree

    puml_tree = generar_diagrama_arbol_binario(formato="plantuml")
    assert "@startuml" in puml_tree


def test_diagrama_spec_en_modelo_ejercicio():
    ej = Ejercicio(
        id="tp1_ej1",
        titulo="Lista Enlazada",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos=60,
        diagramas=[
            DiagramaSpec(nombre="Esquema Lista", tipo="lista", formato="mermaid"),
            DiagramaSpec(nombre="Esquema Pila", tipo="pila", formato="ascii"),
        ]
    )
    assert len(ej.diagramas) == 2
    assert ej.diagramas[0].formato == "mermaid"
    assert ej.diagramas[1].formato == "ascii"
