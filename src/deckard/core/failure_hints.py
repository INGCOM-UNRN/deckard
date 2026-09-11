"""Generador de retroalimentación pedagógica orientativa ante fallas de ejecución o asserts (QoL 38)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional


@dataclass
class PistaFalla:
    codigo_falla: str
    concepto_clave: str
    explicacion_didactica: str
    preguntas_guia: List[str]
    sugerencia_accion: str


CATALOGO_PISTAS_FALLA: Dict[str, PistaFalla] = {
    "SIGSEGV": PistaFalla(
        codigo_falla="SIGSEGV",
        concepto_clave="Violación de Acceso a Memoria (Segmentation Fault)",
        explicacion_didactica="El proceso intentó leer o escribir en una dirección de memoria no asignada o protegida.",
        preguntas_guia=[
            "¿Estás desreferenciando un puntero NULL sin verificarlo previamente?",
            "¿Accediste al índice 'n' en un vector de tamaño 'n' (índice fuera de rango)?",
            "¿Estás usando memoria luego de liberarla con free() (Use-After-Free)?",
        ],
        sugerencia_accion="Ejecutá el programa bajo GDB con 'gdb ./programa' y luego 'backtrace' (bt) para ubicar la línea exacta.",
    ),
    "SIGABRT": PistaFalla(
        codigo_falla="SIGABRT",
        concepto_clave="Aborto de Proceso por Aserción o Doble Liberación",
        explicacion_didactica="El programa fue abortado deliberadamente por una falla en un assert() o corrupción del Heap en free().",
        preguntas_guia=[
            "¿Falló una aserción de precondición en tu suite de pruebas?",
            "¿Intentaste liberar dos veces el mismo bloque dinámico (Double Free)?",
            "¿Escribiste más bytes de los solicitados corrompiendo los metadatos de glibc malloc?",
        ],
        sugerencia_accion="Revisá el mensaje emitido por la aserción o ejecutá con Valgrind para auditar la integridad del Heap.",
    ),
    "SIGFPE": PistaFalla(
        codigo_falla="SIGFPE",
        concepto_clave="Excepción Aritmética Fatal",
        explicacion_didactica="Ocurrió una operación matemática no válida a nivel de microprocesador.",
        preguntas_guia=[
            "¿Existe una división por cero en un cociente o en una operación de módulo ('% 0')?",
            "¿Ocurrió un desborde con INT_MIN / -1?",
        ],
        sugerencia_accion="Agregá una guarda 'if (denominador == 0)' antes de ejecutar cualquier división o cálculo modular.",
    ),
    "ASSERT_EQ": PistaFalla(
        codigo_falla="ASSERT_EQ",
        concepto_clave="Discrepancia entre Valor Esperado y Obtenido",
        explicacion_didactica="La función retornó un valor diferente al estipulado por el oráculo del test.",
        preguntas_guia=[
            "¿Contemplaste los casos borde (vector de 0 elementos, números negativos)?",
            "¿El bucle principal itera exactamente la cantidad de veces necesaria?",
            "¿El acumulador fue inicializado correctamente en 0 o 1?",
        ],
        sugerencia_accion="Imprimí con printf o inspeccioná con el depurador las variables internas en cada ciclo de la función.",
    ),
    "MEMORY_LEAK": PistaFalla(
        codigo_falla="MEMORY_LEAK",
        concepto_clave="Fuga de Memoria Dinámica en el Heap",
        explicacion_didactica="Se reservó memoria con malloc/calloc que no fue liberada antes de que el puntero saliera de ámbito.",
        preguntas_guia=[
            "¿Existe algún 'return' temprano dentro de la función que olvide invocar free()?",
            "¿Sobrescribiste la variable puntero con una nueva asignación antes de liberar la anterior?",
        ],
        sugerencia_accion="Verificá que cada bloque asignado tenga una única ruta determinista de liberación hacia free().",
    ),
}


def obtener_pista_falla(codigo_o_texto: str) -> PistaFalla:
    """Retorna una pista pedagógica orientativa basada en el código o mensaje de error recibido."""
    texto_upper = codigo_o_texto.upper()
    for clave, pista in CATALOGO_PISTAS_FALLA.items():
        if clave in texto_upper:
            return pista

    # Búsqueda por palabras clave
    if "NULL" in texto_upper or "SEGMENTATION" in texto_upper:
        return CATALOGO_PISTAS_FALLA["SIGSEGV"]
    if "FREE" in texto_upper or "ABORT" in texto_upper:
        return CATALOGO_PISTAS_FALLA["SIGABRT"]
    if "DIVIS" in texto_upper or "ZERO" in texto_upper:
        return CATALOGO_PISTAS_FALLA["SIGFPE"]
    if "LEAK" in texto_upper or "FUGA" in texto_upper:
        return CATALOGO_PISTAS_FALLA["MEMORY_LEAK"]

    return PistaFalla(
        codigo_falla="FALLA_GENERAL",
        concepto_clave="Comportamiento Anómalo o No Determinista",
        explicacion_didactica=f"Diagnóstico recibido: {codigo_o_texto}",
        preguntas_guia=[
            "¿Compilaste con flags de advertencia completas (-Wall -Wextra -Werror)?",
            "¿Todas las variables locales están debidamente inicializadas antes de su lectura?",
        ],
        sugerencia_accion="Aislá la función conflictiva en un testcase mínimo reproducible.",
    )
