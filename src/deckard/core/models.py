"""Modelos de dominio de deckard: ejercicios, guías y taxonomía de Bloom."""

from __future__ import annotations

import re
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


class FuncionSpec(BaseModel):
    """Especificación de una función C requerida en el ejercicio."""

    model_config = ConfigDict(validate_assignment=True)

    nombre: str
    retorno: str = "void"
    parametros: str = ""
    descripcion: Optional[str] = None

    @property
    def firma(self) -> str:
        params = self.parametros.strip() if self.parametros else "void"
        return f"{self.retorno.strip()} {self.nombre.strip()}({params});"

    @classmethod
    def parse(cls, firma_str: str, descripcion: Optional[str] = None) -> FuncionSpec:
        """Parsea un string de prototipo C tipo 'int contar_pares(const int* v, size_t n);'"""
        limpia = firma_str.strip().rstrip(";").strip()
        match = re.match(r"^([\w\s\*]+?)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)$", limpia, re.DOTALL)
        if match:
            ret, nom, params = match.groups()
            return cls(nombre=nom.strip(), retorno=ret.strip(), parametros=params.strip(), descripcion=descripcion)
        return cls(nombre=limpia, retorno="void", parametros="", descripcion=descripcion)


class CasoTestFuncion(BaseModel):
    """Caso de prueba granular sobre la invocación directa de una función C."""

    model_config = ConfigDict(validate_assignment=True)

    nombre: str
    funcion: str
    descripcion: Optional[str] = None
    codigo: Optional[str] = None            # Bloque de código o aserción en C
    args: Optional[str] = None              # Argumentos pasados (si no se especifica bloque C)
    retorno_esperado: Optional[str] = None  # Valor de retorno esperado (ej: "42", "true")
    postcondiciones: Optional[str] = None   # Aserción sobre efectos colaterales (ej: "vec[0] == 5")


class Ejercicio(BaseModel):
    """Un ejercicio práctico versionado como unidad atómica de cátedra."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]*$")
    titulo: str
    tema: str                       # p.ej. "punteros", "memoria_dinamica"
    bloom: NivelBloom
    minutos_estimados: int = Field(..., ge=1, le=600)
    enunciado_md: str               # markdown del enunciado
    solucion_c: str = ""            # solución modelo (verificada con ripley)
    pistas: List[str] = Field(default_factory=list)  # progresivas, ordenadas
    tags: List[str] = Field(default_factory=list)
    verificado: bool = False        # lo setea `deckard verify`
    funciones: List[FuncionSpec] = Field(default_factory=list)
    tests_funciones: List[CasoTestFuncion] = Field(default_factory=list)

    @property
    def tiene_funciones(self) -> bool:
        return bool(self.funciones or self.tests_funciones)

    @field_validator("pistas")
    @classmethod
    def pistas_ordenadas_sin_vacias(cls, v: List[str]) -> List[str]:
        limpias = [p.strip() for p in v if p and p.strip()]
        return limpias

    def generar_cabecera_c(self) -> str:
        """Genera el código de cabecera C (.h) con las firmas declaradas."""
        guard = f"EJERCICIO_{self.id.upper().replace('-', '_')}_H"
        lineas = [
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            "#include <stddef.h>",
            "#include <stdbool.h>",
            "#include <stdint.h>",
            "",
        ]
        for fn in self.funciones:
            if fn.descripcion:
                lineas.append(f"/* {fn.descripcion} */")
            lineas.append(fn.firma)
        lineas.extend(["", f"#endif /* {guard} */", ""])
        return "\n".join(lineas)

    def generar_esqueleto_c(self) -> str:
        """Genera un esqueleto de implementación en C a partir de las funciones."""
        lineas = [
            f'#include "{self.id}.h"',
            "#include <stdio.h>",
            "#include <stdlib.h>",
            "#include <stdbool.h>",
            "",
        ]
        for fn in self.funciones:
            params = fn.parametros.strip() if fn.parametros else "void"
            ret_val = " 0;" if fn.retorno == "int" else " false;" if fn.retorno == "bool" else " NULL;" if "*" in fn.retorno else ";"
            if fn.retorno == "void":
                body = "    /* TODO: implementar */\n    (void)0;"
            else:
                body = f"    /* TODO: implementar */\n    return{ret_val}"
            lineas.append(f"{fn.retorno} {fn.nombre}({params}) {{\n{body}\n}}\n")
        return "\n".join(lineas)

    def to_yaml_dict(self) -> dict:
        datos = self.model_dump(exclude_none=True)
        datos["bloom"] = int(self.bloom)
        if not self.funciones:
            datos.pop("funciones", None)
        if not self.tests_funciones:
            datos.pop("tests_funciones", None)
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
