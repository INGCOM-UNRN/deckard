"""Detector de similitud y duplicación entre ejercicios del banco (QoL 6)."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from deckard.core.models import Ejercicio


@dataclass
class ParDuplicado:
    ejercicio_a_id: str
    ejercicio_b_id: str
    similitud_enunciado: float
    similitud_solucion: Optional[float]
    similitud_global: float
    motivo: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ejercicio_a_id": self.ejercicio_a_id,
            "ejercicio_b_id": self.ejercicio_b_id,
            "similitud_enunciado": round(self.similitud_enunciado, 3),
            "similitud_solucion": round(self.similitud_solucion, 3) if self.similitud_solucion is not None else None,
            "similitud_global": round(self.similitud_global, 3),
            "motivo": self.motivo,
        }


def _limpiar_texto(texto: str) -> str:
    """Normaliza un texto eliminando puntuación y mayúsculas para comparación estocástica."""
    t = re.sub(r"[^\w\s]", " ", texto.lower())
    return " ".join(t.split())


def _calcular_jaccard_ngramas(texto_a: str, texto_b: str, n: int = 3) -> float:
    """Calcula similitud de Jaccard sobre n-gramas de palabras."""
    palabras_a = texto_a.split()
    palabras_b = texto_b.split()
    if len(palabras_a) < n or len(palabras_b) < n:
        # Fallback a palabras directas
        set_a = set(palabras_a)
        set_b = set(palabras_b)
    else:
        set_a = {" ".join(palabras_a[i : i + n]) for i in range(len(palabras_a) - n + 1)}
        set_b = {" ".join(palabras_b[i : i + n]) for i in range(len(palabras_b) - n + 1)}

    if not set_a or not set_b:
        return 0.0
    interseccion = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return interseccion / union if union > 0 else 0.0


def _calcular_similitud_secuencia(a: str, b: str) -> float:
    """Calcula el ratio de similitud de SequenceMatcher (tipo Levenshtein difflib)."""
    return SequenceMatcher(None, a, b).ratio()


def buscar_ejercicios_duplicados(
    ejercicios: List[Ejercicio],
    umbral: float = 0.70,
    comparar_soluciones: bool = True,
) -> List[ParDuplicado]:
    """Compara todos los pares de ejercicios y reporta aquellos que superen el umbral de similitud."""
    duplicados: List[ParDuplicado] = []
    n = len(ejercicios)

    for i in range(n):
        for j in range(i + 1, n):
            ej_a = ejercicios[i]
            ej_b = ejercicios[j]

            txt_a = _limpiar_texto(f"{ej_a.titulo} {ej_a.enunciado_md}")
            txt_b = _limpiar_texto(f"{ej_b.titulo} {ej_b.enunciado_md}")

            jaccard = _calcular_jaccard_ngramas(txt_a, txt_b, n=2)
            seq_ratio = _calcular_similitud_secuencia(txt_a, txt_b)
            sim_enunciado = max(jaccard, seq_ratio)

            sim_sol = None
            sim_global = sim_enunciado

            if comparar_soluciones and ej_a.solucion and ej_b.solucion:
                sol_a = _limpiar_texto(ej_a.solucion)
                sol_b = _limpiar_texto(ej_b.solucion)
                sim_sol = _calcular_similitud_secuencia(sol_a, sol_b)
                # Ponderación combinada
                sim_global = 0.6 * sim_enunciado + 0.4 * sim_sol

            if sim_global >= umbral:
                if sim_global >= 0.90:
                    motivo = "Consigna idéntica o cuasi-idéntica (posible duplicado directo)."
                elif sim_enunciado >= umbral:
                    motivo = f"Alta similitud de enunciado ({int(sim_enunciado*100)}%)."
                else:
                    motivo = f"Alta similitud estructural en soluciones ({int(sim_sol*100) if sim_sol else 0}%)."

                duplicados.append(
                    ParDuplicado(
                        ejercicio_a_id=ej_a.id,
                        ejercicio_b_id=ej_b.id,
                        similitud_enunciado=sim_enunciado,
                        similitud_solucion=sim_sol,
                        similitud_global=sim_global,
                        motivo=motivo,
                    )
                )

    duplicados.sort(key=lambda x: x.similitud_global, reverse=True)
    return duplicados
