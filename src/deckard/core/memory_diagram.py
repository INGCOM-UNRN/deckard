"""Generador de diagramas de memoria Stack/Heap integrados con convenciones Bishop (QoL 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional

from deckard.core.models import Ejercicio


@dataclass
class VariableMemoria:
    nombre: str
    tipo: str
    valor: str
    direccion: Optional[str] = None
    apunta_a: Optional[str] = None  # Dirección o ID de bloque destino en Heap


@dataclass
class MarcoPila:
    funcion: str
    variables: List[VariableMemoria] = field(default_factory=list)


@dataclass
class BloqueHeap:
    direccion: str
    tamano_bytes: int
    tipo_contenido: str
    valores: List[str] = field(default_factory=list)
    origen_malloc: str = ""


def generar_diagrama_memoria_ascii(
    marcos: List[MarcoPila],
    heap: Optional[List[BloqueHeap]] = None,
    titulo: str = "ESTADO DE LA MEMORIA (Stack & Heap)",
) -> str:
    """Construye un esquema ASCII alineado y claro para incluir en enunciados o terminal."""
    lineas = [
        "```text",
        "+" + "=" * 68 + "+",
        f"| {titulo.center(66)} |",
        "+" + "=" * 68 + "+",
        "|                       STACK (Memoria Automática)                   |",
        "+" + "-" * 68 + "+",
    ]

    for marco in marcos:
        lineas.append(f"|  [ Marco: {marco.funcion}() ]" + " " * (66 - len(marco.funcion) - 13) + "|")
        for v in marco.variables:
            dir_str = f"{v.direccion} " if v.direccion else "0x7ffd... "
            flecha = f" ----> [{v.apunta_a}]" if v.apunta_a else ""
            contenido = f"{dir_str}[ {v.nombre} : {v.tipo} ] = {v.valor}{flecha}"
            lineas.append(f"|     * {contenido:<61} |")
        lineas.append("+" + "-" * 68 + "+")

    if heap:
        lineas.append("|                       HEAP (Memoria Dinámica)                      |")
        lineas.append("+" + "-" * 68 + "+")
        for b in heap:
            vals_str = ", ".join(b.valores) if b.valores else "..."
            info = f"{b.direccion} [{b.tamano_bytes} B] ({b.tipo_contenido}): {{ {vals_str} }}"
            if b.origen_malloc:
                info += f" <- {b.origen_malloc}"
            lineas.append(f"|   # {info:<63} |")
        lineas.append("+" + "-" * 68 + "+")

    lineas.append("```")
    return "\n".join(lineas)


def generar_diagrama_memoria_mermaid(
    marcos: List[MarcoPila],
    heap: Optional[List[BloqueHeap]] = None,
    titulo: str = "Diagrama de Memoria",
) -> str:
    """Construye un diagrama de memoria Mermaid con subgrafos para Stack y Heap."""
    lineas = [
        "```mermaid",
        "graph LR",
        f"    %% {titulo}",
        "    subgraph STACK[\"Stack (Memoria Automática)\"]",
    ]

    flechas: List[str] = []

    for f_idx, marco in enumerate(marcos):
        lineas.append(f'        subgraph F_{f_idx}["Marco: {marco.funcion}()"]')
        for v_idx, v in enumerate(marco.variables):
            node_id = f"VAR_{f_idx}_{v_idx}"
            label = f"{v.nombre} ({v.tipo}): {v.valor}"
            lineas.append(f'            {node_id}["{label}"]')
            if v.apunta_a:
                flechas.append(f"    {node_id} -.-> {v.apunta_a}")
        lineas.append("        end")
    lineas.append("    end")

    if heap:
        lineas.append('    subgraph HEAP["Heap (Memoria Dinámica)"]')
        for b_idx, b in enumerate(heap):
            node_id = b.direccion.replace("0x", "H_")
            vals_str = ", ".join(b.valores) if b.valores else "datos"
            lineas.append(f'        {node_id}["{b.direccion} [{b.tamano_bytes}B]<br/>{b.tipo_contenido}: [{vals_str}]"]')
        lineas.append("    end")

    for f in flechas:
        lineas.append(f)

    lineas.append("```")
    return "\n".join(lineas)


def inferir_diagrama_desde_ejercicio(
    ejercicio: Ejercicio,
    formato: str = "ascii",
) -> str:
    """Genera un esquema didáctico representativo basado en el tema y código del ejercicio."""
    texto = f"{ejercicio.titulo} {ejercicio.enunciado_md} {ejercicio.tema}".lower()

    # Si trata sobre punteros/dinámica
    if "heap" in texto or "malloc" in texto or "dinam" in texto or "puntero" in texto:
        marcos = [
            MarcoPila(
                funcion="main",
                variables=[
                    VariableMemoria(nombre="n", tipo="int", valor="5", direccion="0x7ffd10"),
                    VariableMemoria(nombre="vec", tipo="int*", valor="0x55a1b0", direccion="0x7ffd18", apunta_a="0x55a1b0"),
                ],
            )
        ]
        heap = [
            BloqueHeap(
                direccion="0x55a1b0",
                tamano_bytes=20,
                tipo_contenido="int[5]",
                valores=["10", "20", "30", "40", "50"],
                origen_malloc="malloc(5 * sizeof(int))",
            )
        ]
    else:
        marcos = [
            MarcoPila(
                funcion="main",
                variables=[
                    VariableMemoria(nombre="a", tipo="int", valor="10", direccion="0x7ffd20"),
                    VariableMemoria(nombre="b", tipo="int", valor="20", direccion="0x7ffd24"),
                    VariableMemoria(nombre="res", tipo="int", valor="0", direccion="0x7ffd28"),
                ],
            ),
            MarcoPila(
                funcion="calcular",
                variables=[
                    VariableMemoria(nombre="x", tipo="int", valor="10", direccion="0x7ffd00"),
                    VariableMemoria(nombre="y", tipo="int", valor="20", direccion="0x7ffd04"),
                ],
            ),
        ]
        heap = None

    if formato.lower() == "mermaid":
        return generar_diagrama_memoria_mermaid(marcos, heap, titulo=f"Memoria: {ejercicio.titulo}")
    return generar_diagrama_memoria_ascii(marcos, heap, titulo=f"Memoria: {ejercicio.titulo}")
