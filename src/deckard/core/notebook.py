"""Exportador de ejercicios y guías de Deckard a formato Jupyter Notebook (.ipynb) con kernel C."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from deckard.core.models import Ejercicio


def generar_notebook_ejercicio(ej: Ejercicio) -> Dict[str, Any]:
    """Convierte un Ejercicio en un diccionario de Jupyter Notebook v4."""
    celdas: List[Dict[str, Any]] = []

    # Celda 1: Markdown con Título, Metadata y Enunciado
    md_lines = [
        f"# {ej.titulo}\n",
        f"**Tema:** `{ej.tema}` | **Nivel Bloom:** `{ej.bloom.name}` | **Tiempo estimado:** `{ej.minutos_estimados} min`\n",
        "\n---\n\n",
        "## Enunciado\n",
        ej.enunciado_md or "Sin enunciado específico.\n",
    ]
    if ej.pistas:
        md_lines.append("\n\n<details><summary>💡 Ver pistas progresivas</summary>\n\n")
        for i, p in enumerate(ej.pistas, 1):
            md_lines.append(f"{i}. {p}\n")
        md_lines.append("\n</details>\n")

    celdas.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" if not line.endswith("\n") else line for line in "".join(md_lines).splitlines()],
    })

    # Celda 2: Código inicial (Starter code) en C
    starter = ej.starter_code.strip() or "/* Escribí tu solución aquí */\n#include <stdio.h>\n\nint main(void) {\n    return 0;\n}\n"
    celdas.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in starter.splitlines()],
    })

    # Celda 3: Tests o validación interactiva si existen
    if ej.tests_funciones:
        test_code_lines = ["// Pruebas unitarias de cátedra\n"]
        for tc in ej.tests_funciones:
            args_str = ", ".join(tc.argumentos)
            test_code_lines.append(f"// Caso: {tc.nombre}\n")
            test_code_lines.append(f"// Invocación esperada: {ej.funciones[0].nombre if ej.funciones else 'fn'}({args_str}) == {tc.esperado}\n")
        celdas.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": test_code_lines,
        })

    notebook = {
        "cells": celdas,
        "metadata": {
            "kernelspec": {
                "display_name": "C (xeus-cling / gcc)",
                "language": "c",
                "name": "xc",
            },
            "language_info": {
                "name": "c",
                "version": "11",
                "mimetype": "text/x-csrc",
                "file_extension": ".c",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return notebook


def exportar_ejercicio_notebook(ej: Ejercicio, output_path: Path) -> Path:
    """Guarda el ejercicio como archivo .ipynb."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nb_data = generar_notebook_ejercicio(ej)
    output_path.write_text(json.dumps(nb_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path
