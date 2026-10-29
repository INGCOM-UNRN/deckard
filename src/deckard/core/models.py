"""Modelos de dominio de deckard: ejercicios, guías y taxonomía de Bloom."""

from __future__ import annotations

import re
from enum import IntEnum
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class ReferenciasTeoria(BaseModel):
    """Dónde está la teoría del ejercicio: página del apunte, sección y bibliografía."""

    model_config = ConfigDict(validate_assignment=True)

    apunte: Optional[str] = None            # URL o ruta de la página del apunte
    seccion: Optional[str] = None
    bibliografia: List[str] = Field(default_factory=list)


class CriterioRubrica(BaseModel):
    """Un criterio de la rúbrica y su peso en porcentaje."""

    model_config = ConfigDict(validate_assignment=True)

    criterio: str
    peso: float


Dificultad = Literal["inicial", "intermedia", "avanzada", "desafio"]
TipoEjercicio = Literal["concepto", "practica_guiada", "desafio", "parcial_previo"]
VisibilidadSolucion = Literal["publica", "desplegable", "protegida", "oculta"]


class DiagramaSpec(BaseModel):
    """Diagrama o esquema de estructura de datos asociado al enunciado."""

    model_config = ConfigDict(validate_assignment=True)

    nombre: str = "Diagrama"
    tipo: str = "lista"                     # lista, lista_doble, arbol, pila, cola, matriz, punteros_dobles
    formato: str = "ascii"                  # ascii, mermaid, plantuml
    contenido: Optional[str] = None         # Código o representación textual del diagrama


class Ejercicio(BaseModel):
    """Un ejercicio práctico versionado como unidad atómica de cátedra."""

    model_config = ConfigDict(validate_assignment=True, populate_by_name=True)

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]*$")
    titulo: str
    tema: str                       # p.ej. "punteros", "memoria_dinamica"
    bloom: NivelBloom
    minutos_estimados: int = Field(..., ge=1, le=600, alias="minutos")
    enunciado_md: str = Field(default="", alias="enunciado")          # markdown del enunciado
    solucion_c: str = ""            # solución modelo (verificada con ripley)
    starter_code: str = ""          # código inicial o prototipo
    pistas: List[str] = Field(default_factory=list)  # progresivas, ordenadas
    tags: List[str] = Field(default_factory=list)
    verificado: bool = False        # lo setea `deckard verify`
    funciones: List[FuncionSpec] = Field(default_factory=list)
    tests_funciones: List[CasoTestFuncion] = Field(default_factory=list)
    tests_ocultos: List[CasoTestFuncion] = Field(default_factory=list, description="Casos de prueba ocultos para autograding ciego.")
    benchmarks: Dict[str, str] = Field(default_factory=dict, description="Límites o benchmarks de rendimiento de tiempo y memoria.")
    rubrica: Optional[List[CriterioRubrica]] = Field(default=None, description="Criterios de evaluación con su peso en porcentaje ([{criterio, peso}]; también se acepta {criterio: peso}).")
    acsl_contratos: List[str] = Field(default_factory=list, description="Especificaciones formales ACSL.")
    archivos_prueba: Dict[str, str] = Field(default_factory=dict, description="Archivos de prueba requeridos (ej. binarios, csv, stdin/stdout fixtures).")
    diagramas: List[DiagramaSpec] = Field(default_factory=list, description="Diagramas de estructuras de datos (ascii, mermaid, plantuml).")
    tipo_entrega: str = Field(default="archivos_individuales", description="Tipo de entrega / modo de construcción: 'archivos_individuales', 'makefile', 'libreria', 'proyecto'")
    familia: Optional[str] = Field(default=None, description="Identificador de la familia o grupo de ejercicios relacionados (ej. 'tda_lista', 'lib_string').")
    rol_familia: Optional[str] = Field(default=None, description="Rol dentro de la familia: 'libreria' (TDA/módulo), 'tests' (pruebas unitarias), 'uso'/'app' (aplicación cliente).")
    dependencias: List[str] = Field(default_factory=list, description="IDs de ejercicios requeridos previamente.")
    archivos_adicionales: List[str] = Field(default_factory=list, description="Archivos de cabecera, Makefile o datos adicionales.")
    archivos: Dict[str, str] = Field(default_factory=dict, description="Mapeo de nombre de archivo a contenido.")

    # Metadatos pedagógicos de las plantillas de enunciados (ejercicio.md / guia.md): todos opcionales.
    unidad: Optional[int | str] = Field(default=None, description="Unidad del programa.")
    modulo: Optional[str] = Field(default=None, description="Bloque curricular.")
    subtema: Optional[str] = Field(default=None, description="Foco específico dentro del tema.")
    dificultad: Optional[Dificultad] = None
    esfuerzo_lineas_codigo: Optional[int] = Field(default=None, ge=1, description="Líneas de código estimadas de la solución.")
    tipo: Optional[TipoEjercicio] = Field(default=None, description="Rol didáctico: concepto, practica_guiada, desafio o parcial_previo.")
    obligatorio: Optional[bool] = None
    prerrequisitos: List[str] = Field(default_factory=list, description="Temas (del grafo temático) o ids de ejercicios que hay que saber antes.")
    correquisitos: List[str] = Field(default_factory=list, description="Temas o ids que se trabajan en paralelo.")
    siguiente_recomendado: List[str] = Field(default_factory=list, description="Ids de ejercicios para seguir.")
    referencias_teoria: Optional[ReferenciasTeoria] = None
    visibilidad_solucion: Optional[VisibilidadSolucion] = Field(default=None, description="publica, desplegable (por omisión), protegida u oculta (la solución nunca se exporta).")
    # Cabecera <id>.h del banco: la carga `bank.cargar_ejercicio`; no va al ejercicio.yaml.
    header_c: str = Field(default="", exclude=True)
    header_name: str = Field(default="", exclude=True)

    @property
    def nivel(self) -> NivelBloom:
        return self.bloom

    @property
    def minutos(self) -> int:
        return self.minutos_estimados

    @property
    def tiempo_estimado(self) -> int:
        return self.minutos_estimados

    @property
    def enunciado(self) -> str:
        return self.enunciado_md

    @property
    def starter(self) -> str:
        return self.starter_code

    @property
    def solucion(self) -> str:
        return self.solucion_c

    @property
    def pesos_rubrica(self) -> Optional[Dict[str, float]]:
        """La rúbrica como {criterio: peso}, la forma que usan la calibración y la calificación."""
        if not self.rubrica:
            return None
        return {c.criterio: c.peso for c in self.rubrica}

    @property
    def solucion_publicable(self) -> bool:
        """False si la solución no se exporta nunca (`visibilidad_solucion: oculta`)."""
        return self.visibilidad_solucion != "oculta"

    @property
    def tiene_funciones(self) -> bool:
        return bool(self.funciones or self.tests_funciones)

    @property
    def tipo_ejercicio(self) -> str:
        """Determina el tipo de ejercicio (funciones vs io vs makefile/proyecto)."""
        if self.tipo_entrega in ("makefile", "proyecto", "libreria"):
            return self.tipo_entrega
        return "funciones" if self.tiene_funciones else "io"

    def ruta_categoria(self, criterio: str = "bloom/tipo") -> Path:
        """Calcula el directorio relativo dentro del banco según el criterio indicado."""
        c = criterio.lower().replace("-", "/").strip()
        bloom_slug = f"b{int(self.bloom)}-{self.bloom.name.lower()}"
        tipo_slug = self.tipo_ejercicio
        tema_slug = re.sub(r"[^a-z0-9_-]+", "-", self.tema.lower()).strip("-") or "general"

        if c in ("bloom", "b"):
            return Path(bloom_slug) / self.id
        elif c in ("tipo", "t"):
            return Path(tipo_slug) / self.id
        elif c in ("tema",):
            return Path(tema_slug) / self.id
        elif c in ("bloom/tipo", "bloom-tipo"):
            return Path(bloom_slug) / tipo_slug / self.id
        elif c in ("tipo/bloom", "tipo-bloom"):
            return Path(tipo_slug) / bloom_slug / self.id
        elif c in ("tema/bloom", "tema-bloom"):
            return Path(tema_slug) / bloom_slug / self.id
        elif c in ("bloom/tema", "bloom-tema"):
            return Path(bloom_slug) / tema_slug / self.id
        elif c in ("tema/tipo", "tema-tipo"):
            return Path(tema_slug) / tipo_slug / self.id
        elif c in ("plano", "flat", "root"):
            return Path(self.id)
        else:
            tokens = [t.strip() for t in c.split("/") if t.strip()]
            partes = []
            for token in tokens:
                if token in ("bloom", "b"):
                    partes.append(bloom_slug)
                elif token in ("tipo", "type", "t"):
                    partes.append(tipo_slug)
                elif token in ("tema", "topic"):
                    partes.append(tema_slug)
            if not partes:
                partes = [bloom_slug, tipo_slug]
            return Path(*partes) / self.id

    @field_validator("bloom", mode="before")
    @classmethod
    def parse_bloom(cls, v):
        if isinstance(v, str):
            v_clean = v.strip().upper()
            if v_clean in NivelBloom.__members__:
                return NivelBloom[v_clean]
            if v_clean.isdigit():
                return NivelBloom(int(v_clean))
        return v

    @field_validator("rubrica", mode="before")
    @classmethod
    def rubrica_desde_mapa(cls, v):
        # Forma anterior del banco: {criterio: peso}.
        if isinstance(v, dict):
            return [{"criterio": str(k), "peso": peso} for k, peso in v.items()]
        return v

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
        if not self.tests_ocultos:
            datos.pop("tests_ocultos", None)
        if not self.benchmarks:
            datos.pop("benchmarks", None)
        if not self.rubrica:
            datos.pop("rubrica", None)
        for vacio in ("prerrequisitos", "correquisitos", "siguiente_recomendado"):
            if not datos.get(vacio):
                datos.pop(vacio, None)
        if datos.get("referencias_teoria") is not None and not datos["referencias_teoria"].get("bibliografia"):
            datos["referencias_teoria"].pop("bibliografia", None)
        if not self.acsl_contratos:
            datos.pop("acsl_contratos", None)
        if not self.archivos_prueba:
            datos.pop("archivos_prueba", None)
        return datos


_REF_FIJADA = re.compile(r"^(?:[0-9a-f]{40}|v\d+\.\d+\.\d+)$")
PLANTILLA_LIBRERIA = "https://github.com/INGCOM-UNRN-P1/plantilla-libreria"


class LibreriaGuia(BaseModel):
    """Una librería de la práctica (Ola 30).

    - `catedra`: de la cátedra, con su repositorio y un commit (o tag vX.Y.Z) fijado; se copia en
      `libs/<nombre>` con un `.catedra` y no la edita el alumno (p1_test, bitmaps, sonido…).
    - `crear`: la escribe el alumno en esta práctica; `plana` (`.c`/`.h` sueltos, `./tp.sh add-lib`)
      o `estructurada` (desde `plantilla-libreria`). Con `ejercicio`, su API y sus pruebas salen de
      ese ejercicio del banco (con `rol_familia = "libreria"`).
    - `reutilizar`: la escribió el alumno en una guía anterior (`guia`); la trae desde su repositorio.
    """

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(..., pattern=r"^[a-z_][a-z0-9_]*$")
    origen: Literal["catedra", "crear", "reutilizar"]
    descripcion: str = ""
    repositorio: Optional[str] = None
    commit: Optional[str] = None
    forma: Literal["plana", "estructurada"] = "plana"
    ejercicio: Optional[str] = None
    guia: Optional[str] = None

    @model_validator(mode="after")
    def _por_origen(self) -> "LibreriaGuia":
        if self.origen == "catedra":
            if not self.repositorio or not self.commit:
                raise ValueError(f"la librería de la cátedra «{self.nombre}» necesita `repositorio` y `commit`")
            if not _REF_FIJADA.match(self.commit):
                raise ValueError(f"«{self.nombre}»: `commit` tiene que ser un commit completo (40 hex) o un tag vX.Y.Z")
        if self.origen == "reutilizar" and not self.guia:
            raise ValueError(f"la librería «{self.nombre}» se reutiliza: falta `guia` (la guía donde se creó)")
        if self.origen != "catedra" and self.commit:
            raise ValueError(f"«{self.nombre}»: `commit` es sólo para las librerías de la cátedra")
        return self


class TargetDocente(BaseModel):
    """Un target de la corrección (`make dredd-<nombre>`) que dredd agrega con `dredd.mk` (Ola 30).

    `tipo`: `comando` (la `receta` dada), `memcheck` y `fallos` (los targets de la plantilla),
    `bench` (`ripley check --bench <cota>`) o `pruebas_ocultas` (los `tests_ocultos` del ejercicio,
    compilados contra el código del alumno). `produce` dice qué lee dredd: el código de salida o un
    archivo JSON o Markdown (`archivo`, relativo al ejercicio).
    """

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]*$")
    descripcion: str
    tipo: Literal["comando", "memcheck", "fallos", "bench", "pruebas_ocultas"] = "comando"
    receta: List[str] = Field(default_factory=list)
    cota: Optional[str] = None
    ejercicios: List[str] = Field(default_factory=list)   # vacío: todos los de la guía
    produce: Literal["codigo", "json", "markdown"] = "codigo"
    archivo: Optional[str] = None
    peso: float = Field(0.0, ge=0, le=100)
    visible: bool = False

    @model_validator(mode="after")
    def _por_tipo(self) -> "TargetDocente":
        if self.tipo == "comando" and not self.receta:
            raise ValueError(f"el target «{self.nombre}» es un comando: falta `receta`")
        if self.tipo != "comando" and self.receta:
            raise ValueError(f"el target «{self.nombre}» es de tipo {self.tipo}: `receta` es sólo para `comando`")
        if self.tipo == "bench" and not self.cota:
            raise ValueError(f"el target «{self.nombre}» mide una cota: falta `cota` (p. ej. O(n))")
        if self.produce != "codigo" and not self.archivo:
            raise ValueError(f"el target «{self.nombre}» produce {self.produce}: falta `archivo`")
        return self

    @property
    def target_make(self) -> str:
        return f"dredd-{self.nombre}"


class GuiaSpec(BaseModel):
    """Definición declarativa de una guía o parcial (`deckard compose`)."""

    nombre: str
    duracion_min: int = Field(..., ge=10, le=480)
    margen_carga: float = Field(0.8, ge=0.3, le=1.0)   # presupuesto útil de la duración
    temas: List[str] = Field(default_factory=list)      # filtro opcional por tema
    bloom_min: NivelBloom = NivelBloom.RECORDAR
    bloom_max: NivelBloom = NivelBloom.EVALUAR
    cantidad_maxima: Optional[int] = None
    tipo_entrega: Optional[str] = Field(default=None, description="Tipo de entrega / modo de construcción: 'archivos_individuales', 'makefile', 'libreria', 'proyecto'")
    familias: List[str] = Field(default_factory=list, description="Familias de ejercicios requeridas o incluidas.")
    librerias: List[LibreriaGuia] = Field(default_factory=list, description="Librerías de la práctica (cátedra, a crear, reutilizadas).")
    targets_docente: List[TargetDocente] = Field(default_factory=list, description="Targets de la corrección (dredd.mk).")


class Seleccion(BaseModel):
    """Resultado de `compose`: ejercicios elegidos + métricas de balanceo."""

    guia: str
    ejercicios: List[Ejercicio]
    minutos_totales: int
    tipo_entrega: Optional[str] = None
    familias: List[str] = Field(default_factory=list)

    @property
    def distribucion_bloom(self) -> dict:
        conteo: dict = {}
        for e in self.ejercicios:
            conteo[e.bloom.name] = conteo.get(e.bloom.name, 0) + 1
        return conteo
