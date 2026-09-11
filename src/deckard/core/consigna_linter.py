"""Linter pedagógico de precondiciones, contratos y casos borde en consignas (QoL 10)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional

from deckard.core.models import Ejercicio


@dataclass
class FindingConsigna:
    regla: str
    severidad: str  # "ALTA", "MEDIA", "BAJA"
    titulo: str
    mensaje: str
    sugerencia: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regla": self.regla,
            "severidad": self.severidad,
            "titulo": self.titulo,
            "mensaje": self.mensaje,
            "sugerencia": self.sugerencia,
        }


def lint_consigna_ejercicio(ejercicio: Ejercicio, estricto: bool = False) -> List[FindingConsigna]:
    """Audita si la consigna explicita precondiciones y casos borde esenciales de C."""
    findings: List[FindingConsigna] = []
    texto = f"{ejercicio.titulo}\n{ejercicio.enunciado_md}".lower()
    tema = ejercicio.tema.lower()

    # 1. Puntero nulo (NULL)
    trata_punteros = any(k in tema or k in texto for k in ("puntero", "punteros", "vector", "arreglo", "string", "cadena", "tda", "lista", "arbol"))
    menciona_null = bool(re.search(r"\b(null|nulo|nulos|inválido|invalido|puntero nulo)\b", texto))
    if trata_punteros and not menciona_null:
        findings.append(FindingConsigna(
            regla="LINT_NULL_PTR",
            severidad="ALTA" if estricto else "MEDIA",
            titulo="Precondición de puntero NULL omitida",
            mensaje="El ejercicio trabaja con punteros o arreglos pero no aclara el comportamiento si se recibe NULL.",
            sugerencia="Indicar explícitamente: 'Si el puntero recibido es NULL, la función debe retornar ... o no realizar cambios'.",
        ))

    # 2. Vector vacío o longitud cero
    trata_colecciones = any(k in tema or k in texto for k in ("vector", "arreglo", "matriz", "lista", "pila", "cola"))
    menciona_vacio = bool(re.search(r"\b(vac[ií]o|vac[ií]a|longitud 0|tamaño 0|tamano 0|cero elementos|sin elementos)\b", texto))
    if trata_colecciones and not menciona_vacio:
        findings.append(FindingConsigna(
            regla="LINT_EMPTY_ARRAY",
            severidad="MEDIA",
            titulo="Comportamiento ante colección vacía no especificado",
            mensaje="La consigna no define qué debe devolver o hacer la rutina ante un arreglo de tamaño 0 o lista vacía.",
            sugerencia="Aclarar el resultado esperado cuando n == 0 (ej: retornar 0, NULL o código de error específico).",
        ))

    # 3. Terminador nulo en cadenas de caracteres
    trata_strings = any(k in tema or k in texto for k in ("string", "cadena", "caracteres", "texto", "str"))
    menciona_terminador = bool(re.search(r"\b(\\0|terminador|nulo final|car[aá]cter nulo)\b", texto))
    if trata_strings and not menciona_terminador:
        findings.append(FindingConsigna(
            regla="LINT_STRING_TERMINATOR",
            severidad="BAJA",
            titulo="Mención al terminador '\\0' omitida",
            mensaje="Al tratar cadenas en C, omitir la mención al '\\0' suele inducir accesos fuera de límite en estudiantes.",
            sugerencia="Recordar en las notas de la consigna que la cadena debe finalizar con '\\0'.",
        ))

    # 4. Fallos en operaciones de archivo (fopen)
    trata_archivos = any(k in tema or k in texto for k in ("archivo", "file", "fichero", "fopen", "fread", "fwrite"))
    menciona_fopen_fail = bool(re.search(r"\b(error de lectura|no existe|no se puede abrir|retorna null|fallo|fopen)\b", texto))
    if trata_archivos and not menciona_fopen_fail:
        findings.append(FindingConsigna(
            regla="LINT_FILE_ERROR",
            severidad="ALTA",
            titulo="Manejo de archivo inexistente o error de E/S omitido",
            mensaje="No se especifica cómo actuar si el archivo no puede ser abierto o si ocurre un error de lectura.",
            sugerencia="Especificar si debe cerrarse el descriptor y cuál es el código de error devuelto ante fopen == NULL.",
        ))

    # 5. Fallo de asignación dinámica de memoria (malloc / realloc)
    trata_dinamica = any(k in tema or k in texto for k in ("malloc", "calloc", "realloc", "memoria dinámica", "dinamica"))
    menciona_malloc_fail = bool(re.search(r"\b(sin memoria|malloc falla|fallo de asignaci[oó]n|falla la memoria)\b", texto))
    if trata_dinamica and not menciona_malloc_fail:
        findings.append(FindingConsigna(
            regla="LINT_MALLOC_FAIL",
            severidad="MEDIA",
            titulo="Manejo de fallo de memoria dinámica omitido",
            mensaje="El ejercicio requiere reserva dinámica pero no estipula el protocolo ante fallo de malloc.",
            sugerencia="Aclarar si ante malloc == NULL se debe retornar NULL, liberar recursos previos o finalizar con error.",
        ))

    return findings


def lint_consigna_banco(ejercicios: List[Ejercicio], estricto: bool = False) -> Dict[str, Any]:
    """Audita todas las consignas de una colección y genera estadísticas de calidad pedagógica."""
    resumen: Dict[str, Any] = {
        "total_ejercicios": len(ejercicios),
        "ejercicios_con_observaciones": 0,
        "total_observaciones": 0,
        "por_regla": {},
        "por_ejercicio": {},
    }

    for ej in ejercicios:
        obs = lint_consigna_ejercicio(ej, estricto=estricto)
        if obs:
            resumen["por_ejercicio"][ej.id] = [o.to_dict() for o in obs]
            resumen["total_observaciones"] += len(obs)
            for o in obs:
                resumen["por_regla"][o.regla] = resumen["por_regla"].get(o.regla, 0) + 1

    resumen["ejercicios_con_observaciones"] = len(resumen["por_ejercicio"])
    return resumen
