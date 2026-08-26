"""Banco de ejercicios: carga/guardado YAML y algoritmo de composición de guías."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import yaml

from deckard.core.models import Ejercicio, GuiaSpec, NivelBloom, Seleccion

import fnmatch
from typing import List, Optional, Tuple

ARCHIVO_EJERCICIO = "ejercicio.yaml"


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------

def cargar_ejercicio(dir_ejercicio: Path) -> Ejercicio:
    """Lee `<dir>/ejercicio.yaml` (y completa solucion_c desde solucion.c si existe)."""
    meta = dir_ejercicio / ARCHIVO_EJERCICIO
    if not meta.is_file():
        raise FileNotFoundError(f"No se encontró {ARCHIVO_EJERCICIO} en {dir_ejercicio}")
    with open(meta, "r", encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}

    solucion_archivo = dir_ejercicio / "solucion.c"
    if solucion_archivo.is_file():
        datos["solucion_c"] = solucion_archivo.read_text(encoding="utf-8")
    else:
        datos.setdefault("solucion_c", "")
    return Ejercicio(**datos)


def guardar_ejercicio(ejercicio: Ejercicio, dir_base: Path) -> Path:
    destino = dir_base / ejercicio.id
    destino.mkdir(parents=True, exist_ok=True)
    solucion = destino / "solucion.c"
    if ejercicio.solucion_c and not solucion.exists():
        solucion.write_text(ejercicio.solucion_c, encoding="utf-8")

    datos = ejercicio.to_yaml_dict()
    solucion_texto = datos.pop("solucion_c", None)
    with open(destino / ARCHIVO_EJERCICIO, "w", encoding="utf-8") as f:
        yaml.safe_dump(datos, f, allow_unicode=True, sort_keys=False)
    return destino


def actualizar_verificacion(dir_ejercicio: Path, verificado: bool) -> None:
    """Actualiza el campo 'verificado' en ejercicio.yaml."""
    ej = cargar_ejercicio(dir_ejercicio)
    ej.verificado = verificado
    meta = dir_ejercicio / ARCHIVO_EJERCICIO
    datos = ej.to_yaml_dict()
    datos.pop("solucion_c", None)
    with open(meta, "w", encoding="utf-8") as f:
        yaml.safe_dump(datos, f, allow_unicode=True, sort_keys=False)


def buscar_ejercicios(
    banco: Path,
    patron: Optional[str] = None,
    tema: Optional[str] = None,
    bloom: Optional[int] = None,
    verificado: Optional[bool] = None,
    tags: Optional[List[str]] = None,
    recursivo: bool = True,
) -> List[Tuple[Path, Ejercicio]]:
    """Busca y filtra ejercicios en el banco según patrón comodín, tema, bloom y verificación.

    Retorna una lista de tuplas (directorio_ejercicio, Ejercicio) ordenadas por id.
    """
    banco = Path(banco)
    candidatos_dirs: set[Path] = set()

    if not banco.exists():
        return []

    # Si el propio 'banco' es un ejercicio
    if (banco / ARCHIVO_EJERCICIO).is_file():
        candidatos_dirs.add(banco)
    else:
        if banco.is_dir():
            for p in banco.iterdir():
                if p.is_dir() and (p / ARCHIVO_EJERCICIO).is_file():
                    candidatos_dirs.add(p)
            if recursivo:
                for yaml_path in banco.rglob(ARCHIVO_EJERCICIO):
                    candidatos_dirs.add(yaml_path.parent)

    resultados: List[Tuple[Path, Ejercicio]] = []
    for dir_ej in sorted(candidatos_dirs, key=lambda p: str(p)):
        try:
            ej = cargar_ejercicio(dir_ej)
        except Exception:
            continue

        # Filtro por patrón comodín
        if patron and patron.strip():
            pat = patron.strip()
            try:
                rel_path = dir_ej.relative_to(banco).as_posix()
            except ValueError:
                rel_path = dir_ej.name

            id_match = fnmatch.fnmatch(ej.id, pat)
            name_match = fnmatch.fnmatch(dir_ej.name, pat)
            rel_match = fnmatch.fnmatch(rel_path, pat)
            exact_match = (ej.id == pat) or (dir_ej.name == pat)

            if not (id_match or name_match or rel_match or exact_match):
                continue

        # Filtro por tema
        if tema and ej.tema.lower() != tema.lower():
            continue

        # Filtro por nivel de Bloom
        if bloom is not None and int(ej.bloom) != bloom:
            continue

        # Filtro por verificación
        if verificado is not None and ej.verificado != verificado:
            continue

        # Filtro por tags
        if tags and not any(t.lower() in [x.lower() for x in ej.tags] for t in tags):
            continue

        resultados.append((dir_ej, ej))

    resultados.sort(key=lambda t: t[1].id)
    return resultados


def listar_ejercicios(banco: Path) -> List[Ejercicio]:
    """Recorre banco/*/ejercicio.yaml y devuelve los ejercicios ordenados por id."""
    return [ej for _, ej in buscar_ejercicios(banco, recursivo=True)]


# ---------------------------------------------------------------------------
# Composición de guías (balanceo cognitivo)
# ---------------------------------------------------------------------------

def _candidatos(banco_ejercicios: List[Ejercicio], spec: GuiaSpec) -> List[Ejercicio]:
    filtrados = []
    for e in banco_ejercicios:
        if spec.temas and e.tema not in spec.temas:
            continue
        if not (spec.bloom_min <= e.bloom <= spec.bloom_max):
            continue
        filtrados.append(e)
    # prioriza mayor nivel de Bloom y luego menor duración (diversidad barata primero)
    filtrados.sort(key=lambda e: (-int(e.bloom), e.minutos_estimados, e.id))
    return filtrados


def componer_guia(banco: Path | List[Ejercicio], spec: GuiaSpec) -> Seleccion:
    """Greedy knapsack pedagógico: respeta presupuesto de minutos y diversidad de Bloom.

    Recorre los candidatos priorizando niveles altos de Bloom; agrega un
    ejercicio si no excede el presupuesto (`duracion_min * margen`) ni repite
    tema cuando ya hay uno del mismo tema con menor nivel.
    """
    ejercicios = banco if isinstance(banco, list) else listar_ejercicios(banco)
    presupuesto = int(spec.duracion_min * spec.margen_carga)

    elegidos: List[Ejercicio] = []
    minutos = 0
    temas_usados: set = set()

    for e in _candidatos(ejercicios, spec):
        if minutos + e.minutos_estimados > presupuesto:
            continue
        # diversidad: máximo 2 por tema hasta completar la mitad del presupuesto
        mismo_tema = sum(1 for x in elegidos if x.tema == e.tema)
        if mismo_tema >= 2 and minutos < presupuesto // 2:
            continue
        elegidos.append(e)
        minutos += e.minutos_estimados
        temas_usados.add(e.tema)
        if spec.cantidad_maxima and len(elegidos) >= spec.cantidad_maxima:
            break

    elegidos.sort(key=lambda e: (int(e.bloom), e.minutos_estimados))  # dificultad creciente
    return Seleccion(guia=spec.nombre, ejercicios=elegidos, minutos_totales=minutos)
