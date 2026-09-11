"""Detector de ambigüedades lingüísticas, tono y estilo en consignas (QoL 20)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Tuple

from deckard.core.models import Ejercicio


@dataclass
class FindingTono:
    regla: str
    severidad: str  # "ALTA", "MEDIA", "BAJA"
    fragmento: str
    motivo: str
    sugerencia: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regla": self.regla,
            "severidad": self.severidad,
            "fragmento": self.fragmento,
            "motivo": self.motivo,
            "sugerencia": self.sugerencia,
        }


PATRONES_TONO: List[Tuple[str, str, str, str, str]] = [
    # (regex, regla, severidad, motivo, sugerencia)
    (
        r"\b(podr[íi]as|si\s+quer[eé]s|si\s+te\s+parece|tal\s+vez|quiz[aá]s?)\b",
        "TONE_MODAL_UNCERTAINTY",
        "MEDIA",
        "Uso de condicionales o expresiones dubitativas que debilitan el requerimiento técnico.",
        "Utilizar imperativos directos y firmes (ej: 'Implementá la función...', 'Verificá que...').",
    ),
    (
        r"\bno\s+(?:dejes?\s+de\s+no|est[aá]\s+prohibido\s+no|olvides?\s+no)\b",
        "TONE_DOUBLE_NEGATIVE",
        "ALTA",
        "Doble negación que entorpece la comprensión lógica del enunciado.",
        "Reescribir la condición en forma afirmativa directa.",
    ),
    (
        r"\b(como\s+quieras|a\s+tu\s+criterio|de\s+la\s+forma\s+que\s+te\s+guste|hac[eé]\s+lo\s+que\s+puedas)\b",
        "TONE_VAGUE_INSTRUCTION",
        "ALTA",
        "Instrucción subjetiva o indeterminada que dificulta la verificación objetiva.",
        "Especificar las cotas exactas de diseño o formato admitido.",
    ),
    (
        r"\b(coso|bicho|choclo|chamuyo|magia|truquito|currito)\b",
        "TONE_COLLOQUIALISM",
        "BAJA",
        "Término excesivamente coloquial que deteriora la precisión técnica del enunciado.",
        "Emplear terminología técnica formal de ciencias de la computación.",
    ),
]

VOSEO_PATTERNS = [r"\b(hac[eé]|ten[eé]s|pod[eé]s|escrib[ií]|defin[ií]|retorn[aá])\b"]
TUTEO_PATTERNS = [r"\b(haz|tienes|puedes|escribe|define|retorna)\b"]
USTED_PATTERNS = [r"\b(haga|tenga|pueda|escriba|defina|retorne)\b"]


def auditar_tono_consigna(ejercicio: Ejercicio) -> List[FindingTono]:
    """Inspecciona la redacción del enunciado en busca de ambigüedades de tono y mezclas de tratamiento."""
    findings: List[FindingTono] = []
    texto = f"{ejercicio.titulo}\n{ejercicio.enunciado_md}"
    texto_lower = texto.lower()

    # 1. Reglas léxicas de tono
    for patron, regla, sev, motivo, sug in PATRONES_TONO:
        for m in re.finditer(patron, texto_lower):
            findings.append(FindingTono(
                regla=regla,
                severidad=sev,
                fragmento=m.group(0),
                motivo=motivo,
                sugerencia=sug,
            ))

    # 2. Inconsistencia de tratamiento pronominal (voseo vs tuteo vs usted)
    tiene_voseo = any(re.search(p, texto_lower) for p in VOSEO_PATTERNS)
    tiene_tuteo = any(re.search(p, texto_lower) for p in TUTEO_PATTERNS)
    tiene_usted = any(re.search(p, texto_lower) for p in USTED_PATTERNS)

    tratamientos = []
    if tiene_voseo:
        tratamientos.append("voseo ('hacé', 'podés')")
    if tiene_tuteo:
        tratamientos.append("tuteo ('haz', 'puedes')")
    if tiene_usted:
        tratamientos.append("formal usted ('haga', 'pueda')")

    if len(tratamientos) > 1:
        findings.append(FindingTono(
            regla="TONE_PRONOUN_MIX",
            severidad="MEDIA",
            fragmento=", ".join(tratamientos),
            motivo="Mezcla de tratamientos gramaticales en la misma consigna.",
            sugerencia="Estandarizar al registro de cátedra (se recomienda voseo rioplatense o imperativo neutro).",
        ))

    return findings


def auditar_tono_banco(ejercicios: List[Ejercicio]) -> Dict[str, Any]:
    """Audita el tono de redacción para una lista de ejercicios."""
    resumen: Dict[str, Any] = {
        "total_ejercicios": len(ejercicios),
        "ejercicios_con_observaciones": 0,
        "total_observaciones": 0,
        "por_ejercicio": {},
    }

    for ej in ejercicios:
        obs = auditar_tono_consigna(ej)
        if obs:
            resumen["por_ejercicio"][ej.id] = [o.to_dict() for o in obs]
            resumen["total_observaciones"] += len(obs)

    resumen["ejercicios_con_observaciones"] = len(resumen["por_ejercicio"])
    return resumen
