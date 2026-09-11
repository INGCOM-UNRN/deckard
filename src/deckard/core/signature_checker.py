"""Validador estático de consistencia de firmas de funciones entre consigna y solución (QoL 16)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional

from deckard.core.models import Ejercicio, FuncionSpec


@dataclass
class DiscrepanciaFirma:
    ejercicio_id: str
    nombre_funcion: str
    tipo: str  # "FALTA_EN_SOLUCION", "RETORNO_DISPAR", "PARAMETROS_DISPARES", "EXTRA_NO_DECLARADA"
    declarada: str
    encontrada: str
    detalle: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ejercicio_id": self.ejercicio_id,
            "nombre_funcion": self.nombre_funcion,
            "tipo": self.tipo,
            "declarada": self.declarada,
            "encontrada": self.encontrada,
            "detalle": self.detalle,
        }


def _extraer_firmas_de_codigo_c(codigo_c: str) -> Dict[str, FuncionSpec]:
    """Extrae firmas de funciones definidas en un archivo C mediante regex."""
    firmas: Dict[str, FuncionSpec] = {}
    # Patrón básico para capturar declaraciones o definiciones de funciones C
    # ej: int calcular_suma(const int* vec, size_t n) {
    patron = re.compile(
        r"^\s*([a-zA-Z_][\w\s\*]*?)\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*(?:\{|;)",
        re.MULTILINE,
    )
    for match in patron.finditer(codigo_c):
        ret, nombre, params = match.groups()
        ret = ret.strip()
        nombre = nombre.strip()
        params = params.strip()
        if nombre not in ("if", "for", "while", "switch", "return"):
            firmas[nombre] = FuncionSpec(
                nombre=nombre,
                retorno=ret,
                parametros=params,
            )
    return firmas


def verificar_firmas_ejercicio(ejercicio: Ejercicio) -> List[DiscrepanciaFirma]:
    """Verifica correspondencia de firmas entre las funciones declaradas en el ejercicio y la solución/starter."""
    discrepancias: List[DiscrepanciaFirma] = []
    if not ejercicio.funciones:
        return discrepancias

    codigo_analizar = ejercicio.solucion_c or ejercicio.starter_code
    if not codigo_analizar:
        return discrepancias

    firmas_codigo = _extraer_firmas_de_codigo_c(codigo_analizar)

    for fn_decl in ejercicio.funciones:
        nom = fn_decl.nombre
        if nom not in firmas_codigo:
            discrepancias.append(DiscrepanciaFirma(
                ejercicio_id=ejercicio.id,
                nombre_funcion=nom,
                tipo="FALTA_EN_SOLUCION",
                declarada=fn_decl.firma,
                encontrada="No encontrada en el código",
                detalle=f"La función '{nom}' requerida en la consigna no se encuentra implementada en la solución/starter.",
            ))
        else:
            fn_encontrada = firmas_codigo[nom]
            # Normalizar tipos de retorno básicos
            ret_decl = fn_decl.retorno.strip().replace(" ", "")
            ret_enc = fn_encontrada.retorno.strip().replace(" ", "")
            if ret_decl != ret_enc:
                discrepancias.append(DiscrepanciaFirma(
                    ejercicio_id=ejercicio.id,
                    nombre_funcion=nom,
                    tipo="RETORNO_DISPAR",
                    declarada=fn_decl.retorno,
                    encontrada=fn_encontrada.retorno,
                    detalle=f"Tipo de retorno inconsistente para '{nom}': consigna dice '{fn_decl.retorno}' pero código define '{fn_encontrada.retorno}'.",
                ))

    return discrepancias


def auditar_firmas_banco(ejercicios: List[Ejercicio]) -> Dict[str, Any]:
    """Audita todas las firmas en un lote de ejercicios."""
    resumen: Dict[str, Any] = {
        "total_ejercicios": len(ejercicios),
        "ejercicios_con_discrepancias": 0,
        "total_discrepancias": 0,
        "por_ejercicio": {},
    }

    for ej in ejercicios:
        disc = verificar_firmas_ejercicio(ej)
        if disc:
            resumen["por_ejercicio"][ej.id] = [d.to_dict() for d in disc]
            resumen["total_discrepancias"] += len(disc)

    resumen["ejercicios_con_discrepancias"] = len(resumen["por_ejercicio"])
    return resumen
