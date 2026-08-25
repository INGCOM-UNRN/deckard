"""Modelos de dominio de deckard: ejercicios, guías y taxonomía de Bloom."""

from __future__ import annotations

from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NivelBloom(IntEnum):
    """Taxonomía de Bloom recortada a la cátedra."""

    RECORDAR = 1
    COMPRENDER = 2
    APLICAR = 3
    ANALIZAR = 4
    EVALUAR = 5


class Ejercicio(BaseModel):
    """Un ejercicio práctico versionado como unidad atómica de cátedra."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]*$")
    titulo: str
    tema: str                       # p.ej. "punteros", "memoria_dinamica"
    bloom: NivelBloom
    minutos_estimados: int = Field(..., ge=1, le=600)
    enunciado_md: str               # markdown del enunciado
    solucion_c: str                 # solución modelo (verificada con ripley)
    pistas: List[str] = Field(default_factory=list)  # progresivas, ordenadas
    tags: List[str] = Field(default_factory=list)
    verificado: bool = False        # lo setea `deckard verify`

    @field_validator("pistas")
    @classmethod
    def pistas_ordenadas_sin_vacias(cls, v: List[str]) -> List[str]:
        limpias = [p.strip() for p in v if p and p.strip()]
        return limpias

    def to_yaml_dict(self) -> dict:
        datos = self.model_dump()
        datos["bloom"] = int(self.bloom)
        return datos


class GuiaSpec(BaseModel):
    """Definición declarativa de una guía o parcial (`deckard compose`)."""

    nombre: str
    duracion_min: int = Field(..., ge=10, le=480)
    margen_carga: float = Field(0.8, ge=0.3, le=1.0)   # presupuesto útil de la duración
    temas: List[str] = Field(default_factory=list)      # filtro opcional por tema
    bloom_min: NivelBloom = NivelBloom.RECORDAR
    bloom_max: NivelBloom = NivelBloom.EVALUAR
    cantidad_maxima: Optional[int] = None


class Seleccion(BaseModel):
    """Resultado de `compose`: ejercicios elegidos + métricas de balanceo."""

    guia: str
    ejercicios: List[Ejercicio]
    minutos_totales: int

    @property
    def distribucion_bloom(self) -> dict:
        conteo: dict = {}
        for e in self.ejercicios:
            conteo[e.bloom.name] = conteo.get(e.bloom.name, 0) + 1
        return conteo
