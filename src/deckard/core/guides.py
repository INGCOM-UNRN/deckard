"""Gestión, inspección y manipulación de guías de trabajos prácticos."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from deckard.core.bank import buscar_ejercicios, cargar_ejercicio
from deckard.core.models import Ejercicio, GuiaSpec, NivelBloom


@dataclass
class InfoGuia:
    """Información consolidada de una guía para listados y vistas rápidas."""

    archivo: Path
    nombre: str
    es_spec: bool
    cantidad_ejercicios: int
    duracion_minutos: int
    distribucion_bloom: Dict[str, int] = field(default_factory=dict)
    temas: List[str] = field(default_factory=list)
    ejercicios_ids: List[str] = field(default_factory=list)
    verificados_count: int = 0


def cargar_yaml_guia(ruta: Path) -> dict:
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def guardar_yaml_guia(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        yaml.safe_dump(datos, f, allow_unicode=True, sort_keys=False)


def inspeccionar_guia(ruta_guia: Path, dir_banco: Optional[Path] = None) -> InfoGuia:
    """Inspecciona un archivo de guía (sea GuiaSpec o Guia compuesta) y extrae métricas."""
    datos = cargar_yaml_guia(ruta_guia)
    nombre = datos.get("nombre", ruta_guia.stem.replace("_", " ").title())

    # Detectar si es una GuiaSpec
    es_spec = "duracion_min" in datos and "ejercicios" not in datos

    ejercicios_ids: List[str] = []
    duracion = 0
    bloom_dist: Dict[str, int] = {}
    temas: List[str] = datos.get("temas", [])
    verificados = 0

    if es_spec:
        duracion = datos.get("duracion_min", 0)
        # Si tenemos dir_banco, podríamos simular candidatos o dejarlo referencial
    else:
        # Guia compuesta con lista de ejercicios
        raw_ejs = datos.get("ejercicios", [])
        duracion = datos.get("minutos_totales", 0)
        bloom_dist = datos.get("distribucion_bloom", {})

        for item in raw_ejs:
            if isinstance(item, dict):
                eid = item.get("id", "")
                ejercicios_ids.append(eid)
                if "minutos" in item and not duracion:
                    duracion += item["minutos"]
            elif isinstance(item, str):
                ejercicios_ids.append(item)

        # Si se proveyó dir_banco, verificar estado de cada ejercicio
        if dir_banco and dir_banco.is_dir():
            for eid in ejercicios_ids:
                matches = buscar_ejercicios(dir_banco, patron=eid, recursivo=True)
                if matches and matches[0][1].verificado:
                    verificados += 1

    return InfoGuia(
        archivo=ruta_guia,
        nombre=nombre,
        es_spec=es_spec,
        cantidad_ejercicios=len(ejercicios_ids),
        duracion_minutos=duracion,
        distribucion_bloom=bloom_dist,
        temas=temas,
        ejercicios_ids=ejercicios_ids,
        verificados_count=verificados,
    )


def listar_guias(dir_guias: Path, dir_banco: Optional[Path] = None) -> List[InfoGuia]:
    """Lista todas las guías (.yaml / .yml) en el directorio especificado."""
    if not dir_guias.is_dir():
        return []

    guias: List[InfoGuia] = []
    for f in sorted(dir_guias.glob("*.yaml")) + sorted(dir_guias.glob("*.yml")):
        try:
            guias.append(inspeccionar_guia(f, dir_banco=dir_banco))
        except Exception:
            continue
    return guias


def cargar_guia_con_ejercicios(
    ruta_guia: Path, dir_banco: Path
) -> Tuple[dict, List[Tuple[Optional[Path], Optional[Ejercicio]]]]:
    """Carga los metadatos de la guía y resuelve los objetos Ejercicio correspondientes."""
    datos = cargar_yaml_guia(ruta_guia)
    raw_ejs = datos.get("ejercicios", [])

    items: List[Tuple[Optional[Path], Optional[Ejercicio]]] = []
    for item in raw_ejs:
        eid = item.get("id") if isinstance(item, dict) else str(item)
        matches = buscar_ejercicios(dir_banco, patron=eid, recursivo=True)
        if matches:
            items.append(matches[0])
        else:
            items.append((None, None))
    return datos, items


def agregar_ejercicio_a_guia(ruta_guia: Path, dir_banco: Path, ejercicio_id: str) -> dict:
    """Agrega un ejercicio a una guía compuesta existente."""
    datos = cargar_yaml_guia(ruta_guia)
    if "ejercicios" not in datos or not isinstance(datos["ejercicios"], list):
        datos["ejercicios"] = []

    matches = buscar_ejercicios(dir_banco, patron=ejercicio_id, recursivo=True)
    if not matches:
        raise FileNotFoundError(f"No se encontró el ejercicio '{ejercicio_id}' en el banco.")

    _, ej = matches[0]

    # Verificar si ya está
    for item in datos["ejercicios"]:
        if isinstance(item, dict) and item.get("id") == ej.id:
            return datos
        elif item == ej.id:
            return datos

    datos["ejercicios"].append({
        "id": ej.id,
        "minutos": ej.minutos_estimados,
        "bloom": int(ej.bloom),
        "tema": ej.tema,
    })

    # Recalcular totales
    total_min = sum(e.get("minutos", 0) for e in datos["ejercicios"] if isinstance(e, dict))
    distribucion: Dict[str, int] = {}
    for e in datos["ejercicios"]:
        if isinstance(e, dict):
            b_val = e.get("bloom", 1)
            b_name = NivelBloom(b_val).name
            distribucion[b_name] = distribucion.get(b_name, 0) + 1

    datos["minutos_totales"] = total_min
    datos["distribucion_bloom"] = distribucion
    guardar_yaml_guia(ruta_guia, datos)
    return datos


def remover_ejercicio_de_guia(ruta_guia: Path, ejercicio_id: str) -> dict:
    """Remueve un ejercicio de una guía compuesta."""
    datos = cargar_yaml_guia(ruta_guia)
    if "ejercicios" not in datos or not isinstance(datos["ejercicios"], list):
        return datos

    original_count = len(datos["ejercicios"])
    datos["ejercicios"] = [
        e for e in datos["ejercicios"]
        if (isinstance(e, dict) and e.get("id") != ejercicio_id) and e != ejercicio_id
    ]

    if len(datos["ejercicios"]) == original_count:
        raise ValueError(f"El ejercicio '{ejercicio_id}' no formaba parte de la guía.")

    total_min = sum(e.get("minutos", 0) for e in datos["ejercicios"] if isinstance(e, dict))
    distribucion: Dict[str, int] = {}
    for e in datos["ejercicios"]:
        if isinstance(e, dict):
            b_val = e.get("bloom", 1)
            b_name = NivelBloom(b_val).name
            distribucion[b_name] = distribucion.get(b_name, 0) + 1

    datos["minutos_totales"] = total_min
    datos["distribucion_bloom"] = distribucion
    guardar_yaml_guia(ruta_guia, datos)
    return datos


def cargar_spec(ruta: Path) -> GuiaSpec:
    """Carga y valida un archivo YAML como GuiaSpec."""
    datos = cargar_yaml_guia(ruta)
    return GuiaSpec(**datos)


def guardar_spec(ruta: Path, spec: GuiaSpec) -> None:
    """Guarda un objeto GuiaSpec en formato YAML."""
    datos = spec.model_dump(mode="json", exclude_none=True)
    guardar_yaml_guia(ruta, datos)


def listar_specs(dir_guias: Path) -> List[Tuple[Path, GuiaSpec]]:
    """Lista todos los archivos de especificación (GuiaSpec) encontrados en dir_guias."""
    if not dir_guias.is_dir():
        return []
    specs: List[Tuple[Path, GuiaSpec]] = []
    for f in sorted(dir_guias.glob("*.yaml")) + sorted(dir_guias.glob("*.yml")):
        try:
            datos = cargar_yaml_guia(f)
            if "duracion_min" in datos and "ejercicios" not in datos:
                specs.append((f, GuiaSpec(**datos)))
        except Exception:
            continue
    return specs


def validar_spec(spec: GuiaSpec, dir_banco: Path) -> Dict[str, Any]:
    """Evalúa si el banco de ejercicios tiene suficientes candidatos para satisfacer la especificación."""
    todos = buscar_ejercicios(dir_banco, recursivo=True)
    candidatos = [
        (p, e) for p, e in todos
        if (not spec.temas or e.tema in spec.temas)
        and (spec.bloom_min <= int(e.bloom) <= spec.bloom_max)
    ]

    minutos_disponibles = sum(e.minutos_estimados for _, e in candidatos)
    minutos_requeridos = int(spec.duracion_min * spec.margen_carga)
    verificados_count = sum(1 for _, e in candidatos if e.verificado)

    temas_faltantes = []
    if spec.temas:
        temas_presentes = {e.tema for _, e in candidatos}
        temas_faltantes = [t for t in spec.temas if t not in temas_presentes]

    es_satisfactible = (
        minutos_disponibles >= minutos_requeridos
        and len(temas_faltantes) == 0
        and len(candidatos) > 0
    )

    return {
        "satisfactible": es_satisfactible,
        "candidatos_total": len(candidatos),
        "minutos_disponibles": minutos_disponibles,
        "minutos_requeridos": minutos_requeridos,
        "verificados_count": verificados_count,
        "temas_faltantes": temas_faltantes,
        "candidatos": candidatos,
    }
