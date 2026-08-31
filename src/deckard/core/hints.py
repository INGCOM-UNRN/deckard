"""Generador y gestor de pistas escalonadas (Hints) progresivas para starter kits de C (QoL 15)."""

from __future__ import annotations

import codecs
from typing import List, Optional
from deckard.core.models import Ejercicio


def ofuscar_texto_rot13(texto: str) -> str:
    """Aplica ofuscación ROT13 al texto para evitar spoilers involuntarios."""
    return codecs.encode(texto, "rot_13")


def formatear_pistas_comentarios_c(
    pistas: List[str],
    nivel_maximo: Optional[int] = None,
    ofuscar: bool = False,
) -> str:
    """Genera un bloque de comentarios C estructurados con las pistas escalonadas."""
    if not pistas:
        return ""

    limite = nivel_maximo if nivel_maximo is not None else len(pistas)
    pistas_a_incluir = pistas[:limite]

    lineas = [
        "/* =========================================================================",
        " * 💡 PISTAS ESCALONADAS DE RESOLUCIÓN (DECKARD HINTS)",
        " * =========================================================================",
    ]

    for idx, pista in enumerate(pistas_a_incluir, 1):
        contenido = ofuscar_texto_rot13(pista) if ofuscar else pista
        tag_ofuscado = " (Ofuscada con ROT13 para evitar spoilers)" if ofuscar else ""
        lineas.append(f" * PISTA {idx}{tag_ofuscado}:")
        for linea_pista in contenido.splitlines():
            lineas.append(f" *   {linea_pista}")
        if idx < len(pistas_a_incluir):
            lineas.append(" * -------------------------------------------------------------------------")

    lineas.append(" * ========================================================================= */\n")
    return "\n".join(lineas)


def generar_archivo_pistas_md(
    ejercicio: Ejercicio,
    ofuscar: bool = False,
) -> str:
    """Genera el contenido para un archivo PISTAS.md interactivo con desplegables."""
    lineas = [
        f"# Pistas Escalonadas para '{ejercicio.titulo}'",
        "",
        f"- **ID:** `{ejercicio.id}`",
        f"- **Tema:** `{ejercicio.tema}`",
        "",
        "> [!TIP]",
        "> Leé las pistas de manera progresiva únicamente si te quedás trabado en algún paso.",
        "",
    ]

    if not ejercicio.pistas:
        lineas.append("*Este ejercicio no tiene pistas adicionales configuradas.*")
        return "\n".join(lineas)

    for idx, pista in enumerate(ejercicio.pistas, 1):
        contenido = ofuscar_texto_rot13(pista) if ofuscar else pista
        ayuda_rot13 = "\n\n*(Texto ofuscado en ROT13)*" if ofuscar else ""
        lineas.append(f"<details>")
        lineas.append(f"<summary>🔍 Desplegar Pista {idx} ({'Nivel Inicial' if idx == 1 else 'Nivel Avanzado'})</summary>")
        lineas.append("")
        lineas.append(f"{contenido}{ayuda_rot13}")
        lineas.append("")
        lineas.append(f"</details>")
        lineas.append("")

    return "\n".join(lineas)


def incrustar_pistas_en_starter(
    codigo_c: str,
    pistas: List[str],
    nivel_maximo: Optional[int] = None,
    ofuscar: bool = False,
) -> str:
    """Inserta el bloque de pistas al inicio del código starter de C."""
    if not pistas:
        return codigo_c

    bloque_pistas = formatear_pistas_comentarios_c(pistas, nivel_maximo=nivel_maximo, ofuscar=ofuscar)
    return bloque_pistas + "\n" + codigo_c
