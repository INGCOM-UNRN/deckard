"""Generador de esqueletos y andamiaje guiado con pasos TODO graduados (QoL 14)."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Optional

from deckard.core.models import Ejercicio


def generar_esqueleto_con_pasos(
    ejercicio: Ejercicio,
    ruta_salida: Optional[Path] = None,
) -> str:
    """Genera un archivo fuente C con andamiaje pedagógico estructurado en 4 pasos secuenciales."""
    # Extraer firma de función o usar una genérica según el título
    id_clean = re.sub(r"[^\w]", "_", ejercicio.id)
    nombre_fn = f"resolver_{id_clean}"

    # Si el starter existente ya tiene una firma, intentar preservarla
    firma_declarada = None
    if ejercicio.starter:
        match_fn = re.search(r"\b([a-zA-Z_]\w*\s+\*?[a-zA-Z_]\w*\s*\([^)]*\))\s*\{?", ejercicio.starter)
        if match_fn:
            firma_declarada = match_fn.group(1).strip()

    firma_final = firma_declarada or f"int {nombre_fn}(const int* datos, size_t n)"

    bloques = [
        f"/*",
        f" * Ejercicio: {ejercicio.titulo} [{ejercicio.id}]",
        f" * Tema: {ejercicio.tema} | Taxonomía Bloom: {int(ejercicio.bloom)}",
        f" *",
        f" * Consigna resumida:",
        f" * {ejercicio.enunciado_md[:120].replace(chr(10), ' ')}...",
        f" */",
        "",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <stdbool.h>",
        "#include <string.h>",
        "",
        f"// Prototipo de la función principal",
        f"{firma_final} {{",
        "    // =======================================================================",
        "    // PASO 1 [Precondiciones y Validación de Entrada]:",
        "    // Verificar punteros no nulos y parámetros dentro de rangos válidos.",
        "    // Si no se cumplen las precondiciones, retornar código de error o neutro.",
        "    // =======================================================================",
        "    // TODO: if (datos == NULL) { return -1; }",
        "",
        "    // =======================================================================",
        "    // PASO 2 [Casos Base y Casos Borde]:",
        "    // Considerar colecciones vacías (longitud 0), cadenas nulas o condición de corte.",
        "    // =======================================================================",
        "    // TODO: if (n == 0) { return 0; }",
        "",
        "    // =======================================================================",
        "    // PASO 3 [Lógica Algorítmica Principal]:",
        "    // Implementar la iteración, recursión o transformación requerida.",
        "    // Mantener invariantes de ciclo y evitar accesos fuera de rango.",
        "    // =======================================================================",
        "    // TODO: Implementar el procesamiento principal aquí.",
        "    int resultado = 0;",
        "",
        "    // =======================================================================",
        "    // PASO 4 [Limpieza de Recursos y Retorno]:",
        "    // Liberar cualquier bloque de memoria dinámico asignado auxiliarmente.",
        "    // =======================================================================",
        "    // TODO: free(recursos_temporales);",
        "    return resultado;",
        "}",
        "",
    ]

    codigo_c = "\n".join(bloques)

    if ruta_salida:
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        ruta_salida.write_text(codigo_c, encoding="utf-8")

    return codigo_c
