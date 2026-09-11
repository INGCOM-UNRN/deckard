"""Auditor de consistencia terminológica de consignas y guías didácticas (QoL 1)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from deckard.core.models import Ejercicio


@dataclass
class FindingTerminologia:
    """Representa una observación sobre el uso terminológico en un enunciado."""
    regla: str
    severidad: str  # "ERROR", "ADVERTENCIA", "INFO"
    termino_encontrado: str
    termino_sugerido: str
    motivo: str
    contexto: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regla": self.regla,
            "severidad": self.severidad,
            "termino_encontrado": self.termino_encontrado,
            "termino_sugerido": self.termino_sugerido,
            "motivo": self.motivo,
            "contexto": self.contexto,
        }


TERMINOS_INADECUADOS_C: List[Tuple[str, str, str, str]] = [
    (
        r"\bm[eé]todo(s)?\b",
        "método",
        "función",
        "En lenguaje C puro no existen métodos; utilizar 'función' para evitar confusión con POO.",
    ),
    (
        r"\bclase(s)?\b",
        "clase",
        "struct / TDA",
        "En lenguaje C no existen clases; utilizar 'estructura (struct)' o 'Tipo de Dato Abstracto (TDA)'.",
    ),
    (
        r"\bherencia\b",
        "herencia",
        "composición",
        "El concepto de herencia pertenece a POO; en C se utiliza composición de estructuras.",
    ),
    (
        r"\binterfaz\b(?!\s+(?:de\s+usuario|gráfica|consola))",
        "interfaz",
        "encabezado (.h) / contrato de TDA",
        "En C la especificación pública se define en archivos de cabecera (.h).",
    ),
]

PAREJAS_SINONIMOS: List[Tuple[str, str, str, str]] = [
    (
        r"\bvector(es)?\b",
        r"\barreglo(s)?\b",
        "vector",
        "arreglo",
    ),
    (
        r"\bregistro(s)?\b",
        r"\bestructura(s)?\b",
        "registro",
        "estructura (struct)",
    ),
    (
        r"\bstring(s)?\b",
        r"\bcadena(s)?\b",
        "string",
        "cadena de caracteres",
    ),
]


def verificar_consistencia_terminologica(
    texto: str,
    ejercicio_id: str = "",
    preferencia_coleccion: Optional[str] = None,
) -> List[FindingTerminologia]:
    """Inspecciona el texto de una consigna en busca de términos no estándar o mezclas inconsistentes."""
    findings: List[FindingTerminologia] = []
    texto_lower = texto.lower()

    # 1. Chequeo de términos no aplicables al paradigma procedimental de C
    for patron, term_enc, term_sug, motivo in TERMINOS_INADECUADOS_C:
        matches = list(re.finditer(patron, texto_lower))
        for m in matches:
            inicio = max(0, m.start() - 30)
            fin = min(len(texto), m.end() + 30)
            snippet = texto[inicio:fin].replace("\n", " ").strip()
            findings.append(FindingTerminologia(
                regla="TERM_PARADIGMA_INVALIDO",
                severidad="ERROR",
                termino_encontrado=m.group(0),
                termino_sugerido=term_sug,
                motivo=motivo,
                contexto=f"...{snippet}...",
            ))

    # 2. Detección de mezclas de sinónimos antagónicos en la misma consigna
    for pat_a, pat_b, nombre_a, nombre_b in PAREJAS_SINONIMOS:
        match_a = re.search(pat_a, texto_lower)
        match_b = re.search(pat_b, texto_lower)
        if match_a and match_b:
            findings.append(FindingTerminologia(
                regla="TERM_MEZCLA_SINONIMOS",
                severidad="ADVERTENCIA",
                termino_encontrado=f"'{match_a.group(0)}' y '{match_b.group(0)}'",
                termino_sugerido=f"Unificar todo a '{nombre_a}' o todo a '{nombre_b}'",
                motivo=f"Uso alternado de sinónimos '{nombre_a}' vs '{nombre_b}' en el mismo enunciado.",
                contexto=f"Detectados '{match_a.group(0)}' en pos {match_a.start()} y '{match_b.group(0)}' en pos {match_b.start()}",
            ))

    # 3. Forzar preferencia de cátedra si fue configurada explícitamente
    if preferencia_coleccion in ("vector", "arreglo"):
        patron_no_deseado = r"\barreglo(s)?\b" if preferencia_coleccion == "vector" else r"\bvector(es)?\b"
        sugerido = preferencia_coleccion
        for m in re.finditer(patron_no_deseado, texto_lower):
            inicio = max(0, m.start() - 20)
            fin = min(len(texto), m.end() + 20)
            findings.append(FindingTerminologia(
                regla="TERM_VIOLACION_CONVENCION",
                severidad="INFO",
                termino_encontrado=m.group(0),
                termino_sugerido=sugerido,
                motivo=f"La convención institucional fijada exige el uso de '{sugerido}'.",
                contexto=f"...{texto[inicio:fin].strip()}...",
            ))

    return findings


def auditar_terminologia_ejercicios(
    ejercicios: List[Ejercicio],
    preferencia_coleccion: Optional[str] = None,
) -> Dict[str, Any]:
    """Audita una colección de ejercicios y devuelve un resumen estructurado."""
    resultado: Dict[str, Any] = {
        "total_ejercicios": len(ejercicios),
        "ejercicios_con_hallazgos": 0,
        "total_hallazgos": 0,
        "por_ejercicio": {},
    }

    for ej in ejercicios:
        texto = f"{ej.titulo}\n{ej.enunciado_md}"
        findings = verificar_consistencia_terminologica(
            texto,
            ejercicio_id=ej.id,
            preferencia_coleccion=preferencia_coleccion,
        )
        if findings:
            resultado["por_ejercicio"][ej.id] = [f.to_dict() for f in findings]
            resultado["total_hallazgos"] += len(findings)

    resultado["ejercicios_con_hallazgos"] = len(resultado["por_ejercicio"])
    return resultado
