"""Generador de esquemas y diagramas de estructuras de datos en ASCII, Mermaid y PlantUML para enunciados en C (QoL 14)."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional


class FormatoDiagrama(str, Enum):
    ASCII = "ascii"
    MERMAID = "mermaid"
    PLANTUML = "plantuml"


def generar_diagrama_lista_enlazada(
    elementos: Optional[List[str]] = None,
    circular: bool = False,
    formato: str = "ascii",
) -> str:
    """Genera un diagrama de lista simplemente enlazada en el formato especificado."""
    elems = elementos or ["10", "20", "30"]
    fmt = formato.lower().strip()

    if fmt == "mermaid":
        nodos = []
        nodos.append("graph LR")
        nodos.append("    HEAD((HEAD)) --> N0")
        for i, e in enumerate(elems):
            nodos.append(f'    N{i}["Dato: {e} | Next: •"]')
            if i < len(elems) - 1:
                nodos.append(f"    N{i} --> N{i+1}")
        if circular:
            nodos.append("    N2 --> N0")
        else:
            nodos.append(f'    N{len(elems)-1} --> NULL["NULL"]')
        return "```mermaid\n" + "\n".join(nodos) + "\n```"

    elif fmt == "plantuml":
        puml = ["@startuml", "left to right direction", 'class HEAD <<pointer>>']
        for i, e in enumerate(elems):
            puml.append(f'object "Nodo {i}" as N{i} {{\n  dato = {e}\n  sig = •\n}}')
        puml.append("HEAD --> N0")
        for i in range(len(elems) - 1):
            puml.append(f"N{i} --> N{i+1}")
        if circular:
            puml.append(f"N{len(elems)-1} --> N0 : (circular)")
        else:
            puml.append(f"N{len(elems)-1} --> [*] : NULL")
        puml.append("@enduml")
        return "```plantuml\n" + "\n".join(puml) + "\n```"

    else: # ascii
        nodos_str = [f"[ {e} | •-]-> " for e in elems]
        cierre = f"[ {elems[0]} ] (Circular)" if circular else "NULL"
        cuerpo = "HEAD -> " + "".join(nodos_str) + cierre
        return f"```text\n{cuerpo}\n```"


def generar_diagrama_lista_doble(
    elementos: Optional[List[str]] = None,
    formato: str = "ascii",
) -> str:
    """Genera un diagrama de lista doblemente enlazada."""
    elems = elementos or ["A", "B", "C"]
    fmt = formato.lower().strip()

    if fmt == "mermaid":
        lineas = ["graph LR", "    NULL1[NULL] <--> N0"]
        for i, e in enumerate(elems):
            lineas.append(f'    N{i}["•<- | {e} | -•"]')
            if i < len(elems) - 1:
                lineas.append(f"    N{i} <--> N{i+1}")
        lineas.append(f"    N{len(elems)-1} <--> NULL2[NULL]")
        return "```mermaid\n" + "\n".join(lineas) + "\n```"

    elif fmt == "plantuml":
        puml = ["@startuml", "left to right direction"]
        for i, e in enumerate(elems):
            puml.append(f'object "Nodo {e}" as N{i} {{\n  ant = •\n  dato = {e}\n  sig = •\n}}')
        for i in range(len(elems) - 1):
            puml.append(f"N{i} <--> N{i+1}")
        puml.append("@enduml")
        return "```plantuml\n" + "\n".join(puml) + "\n```"

    else: # ascii
        bloques = [f"[ •<- | {e} | -• ]" for e in elems]
        linea = "NULL <- " + " <===> ".join(bloques) + " -> NULL"
        return f"```text\n{linea}\n```"


def generar_diagrama_arbol_binario(
    raiz: str = "50",
    izq: str = "25",
    der: str = "75",
    izq_izq: str = "10",
    izq_der: str = "30",
    der_izq: str = "60",
    der_der: str = "90",
    formato: str = "ascii",
) -> str:
    """Genera un diagrama de árbol binario de búsqueda."""
    fmt = formato.lower().strip()

    if fmt == "mermaid":
        return (
            "```mermaid\n"
            "graph TD\n"
            f'    R["{raiz}"] --> I["{izq}"]\n'
            f'    R --> D["{der}"]\n'
            f'    I --> II["{izq_izq}"]\n'
            f'    I --> ID["{izq_der}"]\n'
            f'    D --> DI["{der_izq}"]\n'
            f'    D --> DD["{der_der}"]\n'
            "```"
        )

    elif fmt == "plantuml":
        return (
            "```plantuml\n"
            "@startuml\n"
            f'object "Raíz: {raiz}" as R\n'
            f'object "Izq: {izq}" as I\n'
            f'object "Der: {der}" as D\n'
            f'object "{izq_izq}" as II\n'
            f'object "{izq_der}" as ID\n'
            f'object "{der_izq}" as DI\n'
            f'object "{der_der}" as DD\n'
            "R --> I : left\n"
            "R --> D : right\n"
            "I --> II : left\n"
            "I --> ID : right\n"
            "D --> DI : left\n"
            "D --> DD : right\n"
            "@enduml\n"
            "```"
        )

    else: # ascii
        lineas = [
            f"          [{raiz}]",
            f"         /      \\",
            f"      [{izq}]       [{der}]",
            f"     /   \\     /   \\",
            f"   [{izq_izq}]  [{izq_der}] [{der_izq}]  [{der_der}]",
        ]
        return "```text\n" + "\n".join(lineas) + "\n```"


def generar_diagrama_pila(elementos: Optional[List[str]] = None, formato: str = "ascii") -> str:
    """Genera un diagrama de una pila (LIFO)."""
    elems = elementos or ["Tope (Elemento 3)", "Elemento 2", "Fondo (Elemento 1)"]
    fmt = formato.lower().strip()

    if fmt == "mermaid":
        lineas = ["graph TD", "    TOPE((TOPE)) --> E0"]
        for i, e in enumerate(elems):
            lineas.append(f'    E{i}["| {e} |"]')
            if i < len(elems) - 1:
                lineas.append(f"    E{i} --> E{i+1}")
        return "```mermaid\n" + "\n".join(lineas) + "\n```"

    elif fmt == "plantuml":
        puml = ["@startuml", 'class "PILA (LIFO)" {']
        for e in elems:
            puml.append(f"  + {e}")
        puml.append("}")
        puml.append("@enduml")
        return "```plantuml\n" + "\n".join(puml) + "\n```"

    else: # ascii
        lineas = ["  +-------------------------+"]
        for idx, e in enumerate(elems):
            prefix = "TOPE ->" if idx == 0 else "       "
            lineas.append(f"{prefix} | {e:^23} |")
            lineas.append("       +-------------------------+")
        return f"```text\n" + "\n".join(lineas) + "\n```"


def generar_diagrama_cola(elementos: Optional[List[str]] = None, formato: str = "ascii") -> str:
    """Genera un diagrama de una cola (FIFO)."""
    elems = elementos or ["Primero (Sale)", "Dato 2", "Dato 3", "Último (Entra)"]
    fmt = formato.lower().strip()

    if fmt == "mermaid":
        lineas = ["graph LR", "    FRENTE((FRENTE)) --> N0"]
        for i, e in enumerate(elems):
            lineas.append(f'    N{i}["[ {e} ]"]')
            if i < len(elems) - 1:
                lineas.append(f"    N{i} --> N{i+1}")
        lineas.append(f'    N{len(elems)-1} <-- FINAL((FINAL))')
        return "```mermaid\n" + "\n".join(lineas) + "\n```"

    elif fmt == "plantuml":
        puml = ["@startuml", "left to right direction", 'class "COLA (FIFO)" {']
        for e in elems:
            puml.append(f"  - {e}")
        puml.append("}")
        puml.append("@enduml")
        return "```plantuml\n" + "\n".join(puml) + "\n```"

    else: # ascii
        nodos = " | ".join(f" {e} " for e in elems)
        borde = "+" + "-" * (len(nodos) + 2) + "+"
        lineas = [
            "FRENTE (Dequeue)                       FINAL (Enqueue)",
            "       <===  " + borde + " <===",
            "             | " + nodos + " |",
            "             " + borde,
        ]
        return "```text\n" + "\n".join(lineas) + "\n```"


def generar_diagrama_matriz(filas: int = 3, columnas: int = 3, formato: str = "ascii") -> str:
    """Genera un diagrama de matriz bidimensional."""
    fmt = formato.lower().strip()

    if fmt == "mermaid":
        lineas = ["graph TD"]
        for i in range(filas):
            for j in range(columnas):
                lineas.append(f'    M_{i}_{j}["M[{i}][{j}]"]')
        return "```mermaid\n" + "\n".join(lineas) + "\n```"

    elif fmt == "plantuml":
        puml = ["@startuml", "class Matriz {"]
        for i in range(filas):
            fila_cells = " | ".join(f"[{i}][{j}]" for j in range(columnas))
            puml.append(f"  + Fila {i}: {fila_cells}")
        puml.append("}")
        puml.append("@enduml")
        return "```plantuml\n" + "\n".join(puml) + "\n```"

    else: # ascii
        header = "       " + "   ".join(f"Col {j}" for j in range(columnas))
        lineas = [header]
        for i in range(filas):
            fila_str = f"Fila {i} | " + " | ".join(f"M[{i}][{j}]" for j in range(columnas)) + " |"
            borde = "       +" + "--------+" * columnas
            lineas.append(borde)
            lineas.append(fila_str)
        lineas.append("       +" + "--------+" * columnas)
        return "```text\n" + "\n".join(lineas) + "\n```"


def generar_diagrama_punteros_dobles(nombre_ptr: str = "matriz", filas: int = 3, formato: str = "ascii") -> str:
    """Genera un diagrama de vector dinámico de punteros (double pointers)."""
    fmt = formato.lower().strip()

    if fmt == "mermaid":
        lineas = [
            "graph LR",
            f'    PTR["{nombre_ptr} (int**)"] --> VEC["Vector de Punteros [ * | * | * ]"]',
            '    VEC --> B0["Bloque Fila 0: 10 | 20 | 30"]',
            '    VEC --> B1["Bloque Fila 1: 40 | 50 | 60"]',
            '    VEC --> B2["Bloque Fila 2: 70 | 80 | 90"]',
        ]
        return "```mermaid\n" + "\n".join(lineas) + "\n```"

    elif fmt == "plantuml":
        return (
            "```plantuml\n"
            "@startuml\n"
            "left to right direction\n"
            f'object "{nombre_ptr}" as PTR\n'
            'object "int* [3]" as VEC {\n  [0] = •\n  [1] = •\n  [2] = •\n}\n'
            'object "Fila 0 (int[3])" as F0\n'
            'object "Fila 1 (int[3])" as F1\n'
            'object "Fila 2 (int[3])" as F2\n'
            "PTR --> VEC\n"
            "VEC --> F0\n"
            "VEC --> F1\n"
            "VEC --> F2\n"
            "@enduml\n"
            "```"
        )

    else: # ascii
        lineas = [
            f"{nombre_ptr} (int**)",
            "   |",
            "   v",
            " [ * ] ---> [ Bloque Fila 0:  10 | 20 | 30 ]",
            " [ * ] ---> [ Bloque Fila 1:  40 | 50 | 60 ]",
            " [ * ] ---> [ Bloque Fila 2:  70 | 80 | 90 ]",
        ]
        return "```text\n" + "\n".join(lineas) + "\n```"


def obtener_diagrama_por_tipo(tipo: str, formato: str = "ascii", **kwargs) -> str:
    """Retorna el esquema según el tipo de estructura y formato (ascii, mermaid, plantuml) solicitado."""
    t = tipo.lower().strip().replace("-", "_")
    fmt = formato.lower().strip()
    if t in ("lista", "lista_simple", "linked_list"):
        return generar_diagrama_lista_enlazada(formato=fmt, **kwargs)
    elif t in ("lista_doble", "doubly_linked_list"):
        return generar_diagrama_lista_doble(formato=fmt, **kwargs)
    elif t in ("arbol", "tree", "bst"):
        return generar_diagrama_arbol_binario(formato=fmt, **kwargs)
    elif t in ("pila", "stack"):
        return generar_diagrama_pila(formato=fmt, **kwargs)
    elif t in ("cola", "queue"):
        return generar_diagrama_cola(formato=fmt, **kwargs)
    elif t in ("matriz", "matrix"):
        return generar_diagrama_matriz(formato=fmt, **kwargs)
    elif t in ("punteros", "punteros_dobles", "double_pointers"):
        return generar_diagrama_punteros_dobles(formato=fmt, **kwargs)
    else:
        return generar_diagrama_lista_enlazada(formato=fmt, **kwargs)
