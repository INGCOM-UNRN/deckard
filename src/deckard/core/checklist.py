"""Generador de listas de autoevaluación (checklists) en Markdown para estudiantes (QoL 12)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from deckard.core.models import Ejercicio


def generar_checklist_ejercicio(ejercicio: Ejercicio) -> str:
    """Genera una lista de cotejo en Markdown adaptada al tema y requerimientos del ejercicio."""
    tema_lower = ejercicio.tema.lower()
    lineas = [
        f"## Lista de Autoevaluación previa a la Entrega: [{ejercicio.id}] {ejercicio.titulo}",
        "",
        "> [!IMPORTANT]",
        "> Completá y verificá cada punto en tu entorno local antes de realizar el commit y push final.",
        "",
        "### 1. Robustez y Precondiciones",
        "- [ ] **Validación de punteros:** Se verifica que los punteros recibidos no sean `NULL` antes de desreferenciarlos.",
    ]

    if any(k in tema_lower for k in ("vector", "arreglo", "matriz", "lista", "cadena", "string")):
        lineas.append("- [ ] **Casos borde:** Se contempló el comportamiento ante colecciones vacías (longitud 0) o cadenas vacías (`\"\"`).")
        lineas.append("- [ ] **Límites de índice:** No se accede a posiciones negativas ni a `v[n]` (off-by-one).")

    if any(k in tema_lower for k in ("memoria", "dinamica", "dinámica", "heap", "malloc", "tda")):
        lineas.append("- [ ] **Verificación de malloc:** Se chequea que la memoria asignada no haya retornado `NULL`.")
        lineas.append("- [ ] **Liberación completa:** Por cada `malloc`/`calloc` existe un `free` correspondiente sin fugas (comprobado con Valgrind/ASan).")

    if any(k in tema_lower for k in ("archivo", "file", "fopen", "io")):
        lineas.append("- [ ] **Cierre de descriptores:** Todo archivo abierto con `fopen` es cerrado con `fclose` en todas las rutas de ejecución.")

    lineas.extend([
        "",
        "### 2. Estilo y Convenciones Cátedra",
        "- [ ] **Sin números mágicos:** Las constantes numéricas utilizan `#define` descriptivos o enumeraciones `enum`.",
        "- [ ] **Convención de nombres:** Funciones y variables utilizan `snake_case` estricto.",
        "- [ ] **Modularidad y longitud:** Las funciones no exceden las 40 líneas y cumplen una única responsabilidad.",
        "",
        "### 3. Verificación y Pruebas",
        "- [ ] **Compilación limpia:** El código compila con `-Wall -Wextra -Werror -std=c11 -pedantic` sin advertencias.",
        "- [ ] **Pruebas unitarias:** Todos los casos de prueba provistos y casos propios pasan con éxito.",
        "- [ ] **Formato de entrega:** El repositorio contiene los archivos `.c`, `.h` y `Makefile` requeridos.",
        "",
    ])

    return "\n".join(lineas)


def generar_checklist_guia(ejercicios: List[Ejercicio], ruta_salida: Optional[Path] = None) -> str:
    """Genera un documento consolidado con listas de verificación para una colección de ejercicios."""
    bloques = [generar_checklist_ejercicio(ej) for ej in ejercicios]
    contenido = "# Listas de Autoevaluación de Guía de Trabajos Prácticos\n\n" + "\n\n---\n\n".join(bloques)
    if ruta_salida:
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        ruta_salida.write_text(contenido, encoding="utf-8")
    return contenido
