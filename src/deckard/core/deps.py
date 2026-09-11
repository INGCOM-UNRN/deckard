"""Análisis y visualización de dependencias conceptuales y prerrequisitos entre ejercicios."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, List, Optional, Set, Tuple

from deckard.core.bank import listar_ejercicios
from deckard.core.models import Ejercicio

# Orden canónico pedagógico de temas en Programación 1
THEME_ORDER = {
    "introduccion": 0,
    "variables": 1,
    "operadores": 2,
    "control_flujo": 3,
    "condicionales": 3,
    "bucles": 4,
    "ciclos": 4,
    "funciones": 5,
    "arreglos": 6,
    "vectores": 6,
    "matrices": 7,
    "cadenas": 8,
    "strings": 8,
    "punteros": 9,
    "aritmetica_punteros": 10,
    "memoria_dinamica": 11,
    "estructuras": 12,
    "structs": 12,
    "archivos": 13,
    "recursion": 14,
    "tda": 15,
    "listas": 16,
    "pilas": 17,
    "colas": 18,
    "arboles": 19,
    "ordenamiento": 20,
    "busqueda": 21,
}


@dataclass
class ExerciseNode:
    id: str
    titulo: str
    tema: str
    bloom: int
    prerequisites: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)


@dataclass
class DependencyGraph:
    nodes: Dict[str, ExerciseNode] = field(default_factory=dict)

    def add_edge(self, source_id: str, target_id: str):
        """source_id es prerrequisito de target_id (source -> target)."""
        if source_id in self.nodes and target_id in self.nodes:
            self.nodes[target_id].prerequisites.add(source_id)
            self.nodes[source_id].dependents.add(target_id)

    def to_mermaid(self) -> str:
        """Genera diagrama Mermaid del grafo de dependencias."""
        lines = ["graph TD"]
        for node_id, node in self.nodes.items():
            clean_title = node.titulo.replace('"', "'")
            lines.append(f'    {node_id}["{node.id}: {clean_title} (B{node.bloom})"]')

        for node_id, node in self.nodes.items():
            for dep in sorted(node.dependents):
                lines.append(f"    {node_id} --> {dep}")

        return "\n".join(lines)

    def to_ascii(self) -> str:
        """Genera una representación jerárquica ASCII en texto plano."""
        lines = []
        # Encontrar raíces (nodos sin prerrequisitos)
        roots = [n for n in sorted(self.nodes.values(), key=lambda x: (THEME_ORDER.get(x.tema.lower(), 99), x.bloom, x.id)) if not n.prerequisites]
        
        visited = set()

        def _print_tree(node: ExerciseNode, prefix: str = "", is_last: bool = True):
            conn = "└── " if is_last else "├── "
            lines.append(f"{prefix}{conn}[{node.id}] {node.titulo} (Tema: {node.tema}, Bloom: {node.bloom})")
            visited.add(node.id)

            next_prefix = prefix + ("    " if is_last else "│   ")
            deps = [self.nodes[d_id] for d_id in sorted(node.dependents) if d_id in self.nodes]
            for i, dep in enumerate(deps):
                _print_tree(dep, prefix=next_prefix, is_last=(i == len(deps) - 1))

        for r in roots:
            lines.append(f"• [{r.id}] {r.titulo} (Tema: {r.tema}, Bloom: {r.bloom})")
            visited.add(r.id)
            deps = [self.nodes[d_id] for d_id in sorted(r.dependents) if d_id in self.nodes]
            for i, dep in enumerate(deps):
                _print_tree(dep, prefix="  ", is_last=(i == len(deps) - 1))

        # Nodos huérfanos o con ciclos no visitados
        remaining = [n for n in self.nodes.values() if n.id not in visited]
        if remaining:
            lines.append("\n• Otros ejercicios:")
            for rem in remaining:
                lines.append(f"  - [{rem.id}] {rem.titulo} (Tema: {rem.tema}, Bloom: {rem.bloom})")

        return "\n".join(lines)


def build_dependency_graph(exercises: List[Tuple[Path, Ejercicio]]) -> DependencyGraph:
    """Construye el grafo de dependencias conceptuales entre ejercicios."""
    graph = DependencyGraph()

    # 1. Crear nodos
    for p, ej in exercises:
        graph.nodes[ej.id] = ExerciseNode(
            id=ej.id,
            titulo=ej.titulo,
            tema=ej.tema,
            bloom=ej.bloom.value if hasattr(ej.bloom, "value") else int(ej.bloom),
        )

    # 2. Conectar dependencias explícitas en yaml
    for p, ej in exercises:
        # Prerrequisitos explícitos si existen en metadata
        explicit_prereqs = getattr(ej, "prerrequisitos", None) or []
        for prereq in explicit_prereqs:
            if prereq in graph.nodes:
                graph.add_edge(prereq, ej.id)

    # 3. Conectar heurísticamente por progresión temática y niveles Bloom
    theme_buckets: Dict[str, List[Tuple[Path, Ejercicio]]] = {}
    for p, ej in exercises:
        t = ej.tema.lower().strip()
        theme_buckets.setdefault(t, []).append((p, ej))

    # Conectar progresiones de Bloom dentro del mismo tema
    for theme, ejs_list in theme_buckets.items():
        sorted_ejs = sorted(ejs_list, key=lambda x: (x[1].bloom.value if hasattr(x[1].bloom, "value") else int(x[1].bloom), x[1].id))
        for i in range(len(sorted_ejs) - 1):
            source_ej = sorted_ejs[i][1]
            target_ej = sorted_ejs[i + 1][1]
            s_bloom = source_ej.bloom.value if hasattr(source_ej.bloom, "value") else int(source_ej.bloom)
            t_bloom = target_ej.bloom.value if hasattr(target_ej.bloom, "value") else int(target_ej.bloom)
            if s_bloom < t_bloom and not target_ej.id in graph.nodes[source_ej.id].dependents:
                graph.add_edge(source_ej.id, target_ej.id)

    # Conectar entre temas según la jerarquía THEME_ORDER si hay ejercicios de nivel introductorio vs avanzado
    themes_present = sorted(theme_buckets.keys(), key=lambda t: THEME_ORDER.get(t, 99))
    for i in range(len(themes_present) - 1):
        prev_theme = themes_present[i]
        curr_theme = themes_present[i + 1]
        
        prev_order = THEME_ORDER.get(prev_theme, 99)
        curr_order = THEME_ORDER.get(curr_theme, 99)

        if prev_order < curr_order:
            # Conectar el ejercicio más representativo de nivel bajo del tema previo al tema siguiente
            top_prev = sorted(theme_buckets[prev_theme], key=lambda x: (x[1].bloom.value if hasattr(x[1].bloom, "value") else 1))[-1][1]
            base_curr = sorted(theme_buckets[curr_theme], key=lambda x: (x[1].bloom.value if hasattr(x[1].bloom, "value") else 1))[0][1]
            if base_curr.id not in graph.nodes[top_prev.id].dependents and base_curr.id != top_prev.id:
                graph.add_edge(top_prev.id, base_curr.id)

    return graph


def ordenar_topologicamente(graph: DependencyGraph) -> List[str]:
    """Retorna los IDs de ejercicios en orden topológico respetando prerrequisitos."""
    in_degree = {node_id: len(node.prerequisites) for node_id, node in graph.nodes.items()}
    queue = [node_id for node_id, deg in in_degree.items() if deg == 0]
    result: List[str] = []

    while queue:
        queue.sort(key=lambda nid: (THEME_ORDER.get(graph.nodes[nid].tema.lower(), 99), graph.nodes[nid].bloom, nid))
        curr = queue.pop(0)
        result.append(curr)

        for dep in graph.nodes[curr].dependents:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    for node_id in graph.nodes:
        if node_id not in result:
            result.append(node_id)

    return result


def seleccionar_por_prerrequisitos(
    exercises: List[Tuple[Path, Ejercicio]],
    temas_conocidos: List[str],
    max_bloom: Optional[int] = None,
) -> List[Ejercicio]:
    """Selecciona ejercicios cuyos prerrequisitos temáticos estén cubiertos por los temas conocidos."""
    conocidos_set = {t.lower().strip() for t in temas_conocidos}
    max_order_known = max([THEME_ORDER.get(t, -1) for t in conocidos_set], default=-1)

    candidatos: List[Ejercicio] = []
    for _, ej in exercises:
        t = ej.tema.lower().strip()
        t_order = THEME_ORDER.get(t, 99)

        if max_order_known >= 0 and t_order > max_order_known + 1:
            continue

        if max_bloom and int(ej.bloom) > max_bloom:
            continue

        deps_ok = True
        for dep in getattr(ej, "dependencias", []):
            if dep.lower().strip() not in conocidos_set:
                deps_ok = False
                break

        if deps_ok:
            candidatos.append(ej)

    return candidatos

