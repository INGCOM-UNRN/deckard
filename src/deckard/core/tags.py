"""Gestión, consulta y manipulación de etiquetas (tags) de ejercicios."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set, Tuple

from deckard.core.bank import buscar_ejercicios, guardar_ejercicio
from deckard.core.models import Ejercicio


def listar_tags_banco(banco: Path) -> Dict[str, List[str]]:
    """Devuelve un mapeo {tag: [ejercicio_id_1, ejercicio_id_2, ...]} de todo el banco."""
    ejercicios = buscar_ejercicios(banco, recursivo=True)
    tag_map: Dict[str, List[str]] = {}
    for _, ej in ejercicios:
        for t in ej.tags:
            tag_map.setdefault(t, []).append(ej.id)
    return {k: sorted(v) for k, v in sorted(tag_map.items())}


def agregar_tags_a_ejercicios(
    banco: Path,
    patron: str,
    tags_a_agregar: List[str],
) -> List[Tuple[str, List[str]]]:
    """Agrega una o más etiquetas a todos los ejercicios que coincidan con el patrón."""
    candidatos = buscar_ejercicios(banco, patron=patron, recursivo=True)
    modificados: List[Tuple[str, List[str]]] = []

    tags_limpios = [t.strip() for t in tags_a_agregar if t.strip()]
    if not tags_limpios:
        return []

    for dir_ej, ej in candidatos:
        tags_set = set(ej.tags)
        nuevos = [t for t in tags_limpios if t not in tags_set]
        if nuevos:
            ej.tags.extend(nuevos)
            guardar_ejercicio(ej, dir_ej.parent)
            modificados.append((ej.id, ej.tags))

    return modificados


def remover_tags_de_ejercicios(
    banco: Path,
    patron: str,
    tags_a_remover: List[str],
) -> List[Tuple[str, List[str]]]:
    """Remueve una o más etiquetas de todos los ejercicios que coincidan con el patrón."""
    candidatos = buscar_ejercicios(banco, patron=patron, recursivo=True)
    modificados: List[Tuple[str, List[str]]] = []

    tags_set_rem = {t.strip().lower() for t in tags_a_remover if t.strip()}
    if not tags_set_rem:
        return []

    for dir_ej, ej in candidatos:
        original_len = len(ej.tags)
        ej.tags = [t for t in ej.tags if t.lower() not in tags_set_rem]
        if len(ej.tags) != original_len:
            guardar_ejercicio(ej, dir_ej.parent)
            modificados.append((ej.id, ej.tags))

    return modificados
