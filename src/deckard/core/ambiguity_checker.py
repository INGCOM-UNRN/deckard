"""Detector de ambigüedades, términos vagos y falta de especificación en enunciados de ejercicios (QoL 12)."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import List, Dict, Any, Optional

from deckard.core.models import Ejercicio, NivelBloom


@dataclass
class ObservacionEnunciado:
    """Representa una advertencia de ambigüedad o calidad pedagógica en el enunciado."""
    ejercicio_id: str
    categoria: str
    severidad: str  # "alta", "media", "baja"
    mensaje: str
    contexto: str
    sugerencia: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ejercicio_id": self.ejercicio_id,
            "categoria": self.categoria,
            "severidad": self.severidad,
            "mensaje": self.mensaje,
            "contexto": self.contexto,
            "sugerencia": self.sugerencia,
        }


# Verbos pasivos o no medibles en taxonomía de Bloom
VERBOS_NO_OPERATIVOS = {
    "saber": "Reemplazar por verbos de acción como 'implementar', 'calcular' o 'demostrar'.",
    "conocer": "Reemplazar por 'identificar', 'describir' o 'seleccionar'.",
    "entender": "Reemplazar por 'explicar', 'interpretar' o 'ejemplificar'.",
    "aprender": "Reemplazar por un resultado de aprendizaje medible.",
    "ver": "Especificar la acción concreta esperada.",
    "darse cuenta": "Reemplazar por 'detectar' o 'verificar'.",
}

# Términos vagos y subjetivos
TERMINOS_VAGOS = [
    (r"\b(rapido|rapida|rapidamente)\b", "Definir la cota de complejidad temporal esperada (ej: O(N) o O(log N))."),
    (r"\b(eficiente|eficientemente)\b", "Especificar la cota asintótica de tiempo o memoria requerida."),
    (r"\b(bueno|buena|adecuado|adecuada|correcto|correcta)\b", "Definir el criterio objetivo de corrección o formato esperado."),
    (r"\b(mas o menos|aproximadamente)\b", "Definir la tolerancia o precisión numérica requerida."),
    (r"\b(etc\.|etcetera|entre otros|entre otras)\b", "Enumerar exhaustivamente todos los casos o tipos admitidos."),
    (r"\b(facil|sencillo|trivial)\b", "Evitar adjetivos subjetivos sobre la dificultad percibida."),
]

# Casos borde recomendados por tema
CASOS_BORDE_POR_TEMA = {
    "puntero": ("puntero nulo / NULL", r"\b(null|nulo|nula|memoria)\b"),
    "vector": ("vector vacío o tamaño cero", r"\b(vacio|vacío|vacia|vacía|longitud 0|tamano 0|tamaño 0|cero)\b"),
    "matriz": ("dimensiones nulas o no cuadradas", r"\b(filas|columnas|dimension|dimensión)\b"),
    "string": ("cadena vacía o terminador nulo '\\0'", r"\b(\\0|vacia|vacía|terminador)\b"),
    "archivo": ("error al abrir o fin de archivo EOF", r"\b(fopen|eof|error|null)\b"),
    "recurs": ("caso base o condición de corte", r"\b(caso base|corte|base)\b"),
}


def analizar_ambiguedades_ejercicio(ejercicio: Ejercicio) -> List[ObservacionEnunciado]:
    """Audita sintáctica y pedagógicamente el enunciado de un ejercicio."""
    observaciones: List[ObservacionEnunciado] = []
    texto = f"{ejercicio.titulo}\n{ejercicio.enunciado_md}".strip()
    texto_lower = texto.lower()
    palabras = re.findall(r"\b\w+\b", texto_lower)

    # 1. Longitud del enunciado
    if len(palabras) < 20:
        observaciones.append(ObservacionEnunciado(
            ejercicio_id=ejercicio.id,
            categoria="Longitud",
            severidad="alta",
            mensaje=f"Enunciado excesivamente breve ({len(palabras)} palabras).",
            contexto=texto[:60] + "...",
            sugerencia="Expandí la consigna detallando precondiciones, formato de entrada/salida y restricciones.",
        ))
    elif len(palabras) > 600:
        observaciones.append(ObservacionEnunciado(
            ejercicio_id=ejercicio.id,
            categoria="Longitud",
            severidad="baja",
            mensaje=f"Enunciado muy extenso ({len(palabras)} palabras), puede sobrecargar cognitivamente.",
            contexto=texto[:60] + "...",
            sugerencia="Considerá modularizar la explicación o mover detalles de formato a una tabla anexa.",
        ))

    # 2. Verbos no operativos
    for verbo, sug in VERBOS_NO_OPERATIVOS.items():
        pattern = rf"\b{verbo}\w*\b"
        match = re.search(pattern, texto_lower)
        if match:
            observaciones.append(ObservacionEnunciado(
                ejercicio_id=ejercicio.id,
                categoria="Taxonomía Bloom",
                severidad="media",
                mensaje=f"Uso de verbo no operativo '{match.group(0)}' en la consigna.",
                contexto=match.group(0),
                sugerencia=sug,
            ))

    # 3. Términos vagos
    for regex_vago, sug in TERMINOS_VAGOS:
        match = re.search(regex_vago, texto_lower, re.IGNORECASE)
        if match:
            observaciones.append(ObservacionEnunciado(
                ejercicio_id=ejercicio.id,
                categoria="Precisión Técnica",
                severidad="media",
                mensaje=f"Término ambiguo o no cuantificable '{match.group(0)}' detectado.",
                contexto=match.group(0),
                sugerencia=sug,
            ))

    # 4. Omisión de casos borde según tema
    tema_lower = ejercicio.tema.lower()
    for clave_tema, (desc_borde, regex_borde) in CASOS_BORDE_POR_TEMA.items():
        if clave_tema in tema_lower or clave_tema in texto_lower:
            if not re.search(regex_borde, texto_lower):
                observaciones.append(ObservacionEnunciado(
                    ejercicio_id=ejercicio.id,
                    categoria="Casos Borde",
                    severidad="baja",
                    mensaje=f"El ejercicio trata sobre '{clave_tema}' pero no especifica cómo actuar ante {desc_borde}.",
                    contexto=f"Tema: {ejercicio.tema}",
                    sugerencia=f"Aclarar explícitamente el comportamiento esperado ante {desc_borde}.",
                ))

    # 5. Ausencia de ejemplos de entrada / salida
    tiene_ejemplo = bool(
        re.search(r"(ejemplo|entrada:|salida:|input:|output:|```)", texto_lower)
        or "testcases" in ejercicio.archivos
        or any(k.endswith(".in") for k in ejercicio.archivos)
    )
    if not tiene_ejemplo and ejercicio.bloom != NivelBloom.RECORDAR:
        observaciones.append(ObservacionEnunciado(
            ejercicio_id=ejercicio.id,
            categoria="Claridad de Requisitos",
            severidad="media",
            mensaje="El enunciado no incluye ejemplos claros de entrada/salida ni bloques de código de muestra.",
            contexto=texto[:50] + "...",
            sugerencia="Agregá una sección de 'Ejemplo de Entrada y Salida' para que el alumno verifique su solución.",
        ))

    return observaciones


def auditar_banco_ambiguedades(ejercicios: List[Ejercicio]) -> Dict[str, Any]:
    """Audita un conjunto de ejercicios y genera un reporte consolidado de calidad de enunciados."""
    todas_observaciones: List[ObservacionEnunciado] = []
    por_ejercicio: Dict[str, List[ObservacionEnunciado]] = {}

    for ej in ejercicios:
        obs = analizar_ambiguedades_ejercicio(ej)
        if obs:
            por_ejercicio[ej.id] = obs
            todas_observaciones.extend(obs)

    return {
        "total_ejercicios": len(ejercicios),
        "ejercicios_con_observaciones": len(por_ejercicio),
        "total_observaciones": len(todas_observaciones),
        "observaciones": todas_observaciones,
        "por_ejercicio": por_ejercicio,
    }
