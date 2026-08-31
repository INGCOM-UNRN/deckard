"""Generador y selector de variantes de ejercicios y guías homólogas para recuperatorios."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from deckard.core.bank import listar_ejercicios
from deckard.core.models import Ejercicio, GuiaSpec, NivelBloom


def seleccionar_variantes_homologas(
    banco_dir: Path,
    ejercicios_base: List[Ejercicio],
    semilla: Optional[int] = None,
) -> Tuple[List[Ejercicio], List[Tuple[Ejercicio, Optional[Ejercicio]]]]:
    """Para cada ejercicio base, busca un ejercicio alternativo en el banco con igual nivel Bloom y tema afín."""
    if semilla is not None:
        random.seed(semilla)

    todos = listar_ejercicios(banco_dir)
    ids_base = {ej.id for ej in ejercicios_base}

    nuevos_ejercicios: List[Ejercicio] = []
    mapeo_variantes: List[Tuple[Ejercicio, Optional[Ejercicio]]] = []

    for base in ejercicios_base:
        # Candidatos: mismo nivel Bloom, tema afín o id distinto
        candidatos_exactos = [
            ej for ej in todos
            if ej.id not in ids_base and ej.id not in {n.id for n in nuevos_ejercicios}
            and ej.bloom == base.bloom and ej.tema == base.tema
        ]

        if not candidatos_exactos:
            # Fallback: mismo nivel Bloom aunque varíe el tema
            candidatos_exactos = [
                ej for ej in todos
                if ej.id not in ids_base and ej.id not in {n.id for n in nuevos_ejercicios}
                and ej.bloom == base.bloom
            ]

        if candidatos_exactos:
            elegido = random.choice(candidatos_exactos)
            nuevos_ejercicios.append(elegido)
            mapeo_variantes.append((base, elegido))
        else:
            # Si no hay alternativo, se conserva el base
            nuevos_ejercicios.append(base)
            mapeo_variantes.append((base, None))

    return nuevos_ejercicios, mapeo_variantes
