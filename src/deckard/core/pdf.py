"""Compatibilidad hacia atrás para módulos que importen desde deckard.core.pdf."""

from deckard.core.export import (
    buscar_plantilla,
    cargar_tests_ejercicio,
    compilar_pdf,
    markdown_a_html,
    renderizar_ejercicio_html,
    renderizar_guia_html,
)

__all__ = [
    "buscar_plantilla",
    "cargar_tests_ejercicio",
    "compilar_pdf",
    "markdown_a_html",
    "renderizar_ejercicio_html",
    "renderizar_guia_html",
]
