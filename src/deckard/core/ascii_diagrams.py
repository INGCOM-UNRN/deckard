"""Módulo de compatibilidad para diagramas de estructuras de datos (ASCII, Mermaid, PlantUML)."""

from deckard.core.diagrams import (
    FormatoDiagrama,
    generar_diagrama_lista_enlazada,
    generar_diagrama_lista_doble,
    generar_diagrama_arbol_binario,
    generar_diagrama_pila,
    generar_diagrama_cola,
    generar_diagrama_matriz,
    generar_diagrama_punteros_dobles,
    obtener_diagrama_por_tipo,
)

__all__ = [
    "FormatoDiagrama",
    "generar_diagrama_lista_enlazada",
    "generar_diagrama_lista_doble",
    "generar_diagrama_arbol_binario",
    "generar_diagrama_pila",
    "generar_diagrama_cola",
    "generar_diagrama_matriz",
    "generar_diagrama_punteros_dobles",
    "obtener_diagrama_por_tipo",
]
