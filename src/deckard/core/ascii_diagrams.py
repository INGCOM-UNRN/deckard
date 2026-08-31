"""Generador de esquemas y diagramas de estructuras de datos en ASCII para enunciados en C (QoL 14)."""

from __future__ import annotations

from typing import List, Optional


def generar_diagrama_lista_enlazada(elementos: Optional[List[str]] = None, circular: bool = False) -> str:
    """Genera un diagrama ASCII de lista simplemente enlazada."""
    elems = elementos or ["10", "20", "30"]
    nodos_str = []
    for e in elems:
        nodos_str.append(f"[ {e} | •-]-> ")
    
    cierre = f"[ {elems[0]} ] (Circular)" if circular else "NULL"
    cuerpo = "HEAD -> " + "".join(nodos_str) + cierre
    return f"```text\n{cuerpo}\n```"


def generar_diagrama_lista_doble(elementos: Optional[List[str]] = None) -> str:
    """Genera un diagrama ASCII de lista doblemente enlazada."""
    elems = elementos or ["A", "B", "C"]
    bloques = []
    for e in elems:
        bloques.append(f"[ •<- | {e} | -• ]")
    
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
) -> str:
    """Genera un diagrama ASCII de árbol binario de búsqueda."""
    lineas = [
        f"          [{raiz}]",
        f"         /      \\",
        f"      [{izq}]       [{der}]",
        f"     /   \\     /   \\",
        f"   [{izq_izq}]  [{izq_der}] [{der_izq}]  [{der_der}]",
    ]
    return "```text\n" + "\n".join(lineas) + "\n```"


def generar_diagrama_pila(elementos: Optional[List[str]] = None) -> str:
    """Genera un diagrama ASCII de una pila (LIFO)."""
    elems = elementos or ["Tope (Elemento 3)", "Elemento 2", "Fondo (Elemento 1)"]
    lineas = ["  +-------------------------+"]
    for idx, e in enumerate(elems):
        prefix = "TOPE ->" if idx == 0 else "       "
        lineas.append(f"{prefix} | {e:^23} |")
        lineas.append("       +-------------------------+")
    return "```text\n" + "\n".join(lineas) + "\n```"


def generar_diagrama_cola(elementos: Optional[List[str]] = None) -> str:
    """Genera un diagrama ASCII de una cola (FIFO)."""
    elems = elementos or ["Primero (Sale)", "Dato 2", "Dato 3", "Último (Entra)"]
    nodos = " | ".join(f" {e} " for e in elems)
    borde = "+" + "-" * (len(nodos) + 2) + "+"
    lineas = [
        "FRENTE (Dequeue)                       FINAL (Enqueue)",
        "       <===  " + borde + " <===",
        "             | " + nodos + " |",
        "             " + borde,
    ]
    return "```text\n" + "\n".join(lineas) + "\n```"


def generar_diagrama_matriz(filas: int = 3, columnas: int = 3) -> str:
    """Genera un diagrama ASCII de matriz bidimensional con índices."""
    header = "       " + "   ".join(f"Col {j}" for j in range(columnas))
    lineas = [header]
    for i in range(filas):
        fila_str = f"Fila {i} | " + " | ".join(f"M[{i}][{j}]" for j in range(columnas)) + " |"
        borde = "       +" + "--------+" * columnas
        lineas.append(borde)
        lineas.append(fila_str)
    lineas.append("       +" + "--------+" * columnas)
    return "```text\n" + "\n".join(lineas) + "\n```"


def generar_diagrama_punteros_dobles(nombre_ptr: str = "matriz", filas: int = 3) -> str:
    """Genera un diagrama de vector dinámico de punteros (double pointers)."""
    lineas = [
        f"{nombre_ptr} (int**)",
        "   |",
        "   v",
        " [ * ] ---> [ Bloque Fila 0:  10 | 20 | 30 ]",
        " [ * ] ---> [ Bloque Fila 1:  40 | 50 | 60 ]",
        " [ * ] ---> [ Bloque Fila 2:  70 | 80 | 90 ]",
    ]
    return "```text\n" + "\n".join(lineas) + "\n```"


def obtener_diagrama_por_tipo(tipo: str, **kwargs) -> str:
    """Retorna el esquema ASCII según el tipo de estructura solicitada."""
    t = tipo.lower().strip().replace("-", "_")
    if t in ("lista", "lista_simple", "linked_list"):
        return generar_diagrama_lista_enlazada()
    elif t in ("lista_doble", "doubly_linked_list"):
        return generar_diagrama_lista_doble()
    elif t in ("arbol", "tree", "bst"):
        return generar_diagrama_arbol_binario()
    elif t in ("pila", "stack"):
        return generar_diagrama_pila()
    elif t in ("cola", "queue"):
        return generar_diagrama_cola()
    elif t in ("matriz", "matrix"):
        return generar_diagrama_matriz()
    elif t in ("punteros", "punteros_dobles", "double_pointers"):
        return generar_diagrama_punteros_dobles()
    else:
        return generar_diagrama_lista_enlazada()
