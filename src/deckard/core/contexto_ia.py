"""Qué se le envía al modelo en `deckard improve`: sólo lo que cada aspecto necesita.

Cada aspecto usa una parte distinta del ejercicio: mejorar la redacción (`clarity`) no necesita
la solución ni las pistas; las pistas nuevas (`hints`) reemplazan a las viejas, que no hace falta
enviar; el código inicial (`starter`) no debe ver la solución. El ID y la duración no los usa
ningún aspecto. La solución, cuando hace falta, va sin comentarios ni líneas en blanco.

Para GIFT, los comentarios (`// …`) y las categorías (`$CATEGORY`) no viajan: se envían las
preguntas numeradas y el archivo se rearma con lo que vuelve (las que no vuelven quedan igual).
"""

from __future__ import annotations

import re
from typing import Dict, FrozenSet, List, Optional, Tuple

from deckard.core.models import Ejercicio

# Qué campos del ejercicio necesita cada aspecto (los valores de AspectoMejora).
CAMPOS: Dict[str, FrozenSet[str]] = {
    "clarity": frozenset({"titulo", "bloom", "enunciado"}),
    "edge-cases": frozenset({"tema", "enunciado", "funciones", "solucion"}),
    "examples": frozenset({"enunciado", "funciones", "solucion"}),
    "hints": frozenset({"tema", "enunciado", "funciones", "solucion"}),
    "bloom": frozenset({"bloom", "enunciado"}),
    "testcases": frozenset({"tema", "enunciado", "funciones", "solucion"}),
    "starter": frozenset({"enunciado", "funciones", "starter"}),
    "all": frozenset({"titulo", "tema", "bloom", "enunciado", "funciones"}),
}

MAX_CODIGO = 4000  # caracteres de solución compactada (una solución de cátedra entra entera)

_LITERAL_O_COMENTARIO = re.compile(
    r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|/\*.*?\*/|//[^\n]*', re.DOTALL)


def compactar_c(codigo: str, maximo: int = MAX_CODIGO) -> str:
    """El código sin comentarios, sin espacios finales ni líneas en blanco (las cadenas quedan intactas)."""
    sin_comentarios = _LITERAL_O_COMENTARIO.sub(
        lambda m: m.group(0) if m.group(0)[0] in "\"'" else ("\n" * m.group(0).count("\n")), codigo or "")
    lineas = [linea.rstrip() for linea in sin_comentarios.splitlines()]
    compacto = "\n".join(linea for linea in lineas if linea.strip())
    if len(compacto) > maximo:
        compacto = compacto[:maximo].rsplit("\n", 1)[0] + "\n/* … recortado */"
    return compacto


def contexto_ejercicio(ej: Ejercicio, aspecto: str, nombre_bloom: str) -> List[str]:
    """Las líneas de contexto del ejercicio que usa `aspecto`."""
    campos = CAMPOS.get(aspecto, CAMPOS["all"])
    partes: List[str] = []
    if "titulo" in campos:
        partes.append(f"Título: {ej.titulo}")
    if "tema" in campos:
        partes.append(f"Tema: {ej.tema}")
    if "bloom" in campos:
        partes.append(f"Nivel Bloom: {nombre_bloom}")
    if "funciones" in campos and ej.funciones:
        partes.append("\nFunciones C requeridas:\n" + "\n".join(
            f"- `{f.firma}`" + (f": {f.descripcion}" if f.descripcion else "") for f in ej.funciones))
    if "enunciado" in campos and ej.enunciado_md:
        _, cuerpo, _ = separar_marcas(ej.enunciado_md)
        partes.append(f"\n--- ENUNCIADO ACTUAL ---\n{cuerpo.strip()}\n--- FIN ENUNCIADO ACTUAL ---")
    if "solucion" in campos and ej.solucion_c.strip():
        partes.append(f"\n--- SOLUCIÓN MODELO (REFERENCIA, NO LA REVELES) ---\n```c\n{compactar_c(ej.solucion_c)}\n```")
    if "starter" in campos and ej.starter_code.strip():
        partes.append(f"\n--- CÓDIGO INICIAL ACTUAL ---\n```c\n{ej.starter_code.strip()}\n```")
    return partes


# ── Enunciado: marcas que no viajan y secciones que vuelven solas ─────────────

_MARCA = re.compile(r"^\s*(?:---+|\([^)\s]+\)=|<!--.*-->)?\s*$")


def separar_marcas(enunciado: str) -> Tuple[str, str, str]:
    """(prefijo, cuerpo, sufijo): las etiquetas MyST `(x)=`, los `---` y los comentarios HTML al
    principio y al final del enunciado no le sirven al modelo; se reponen al aplicar la respuesta."""
    lineas = (enunciado or "").splitlines()
    i, j = 0, len(lineas)
    while i < j and _MARCA.match(lineas[i]):
        i += 1
    while j > i and _MARCA.match(lineas[j - 1]):
        j -= 1
    return "\n".join(lineas[:i]), "\n".join(lineas[i:j]), "\n".join(lineas[j:])


def reponer_marcas(prefijo: str, cuerpo: str, sufijo: str) -> str:
    return "\n".join(x for x in (prefijo, cuerpo.strip("\n"), sufijo) if x)


# Aspectos que agregan una sección al enunciado: el modelo devuelve sólo esa sección.
SECCIONES = {"edge-cases": "### Casos Límite y Precondiciones", "examples": "### Ejemplos"}


def insertar_seccion(enunciado: str, encabezado: str, seccion: str) -> str:
    """El enunciado con `seccion` en lugar de la que tenga el mismo encabezado, o al final del cuerpo."""
    prefijo, cuerpo, sufijo = separar_marcas(enunciado)
    seccion = seccion.strip()
    if not seccion.lstrip().startswith("#"):
        seccion = f"{encabezado}\n\n{seccion}"
    nivel = len(encabezado) - len(encabezado.lstrip("#"))
    lineas = cuerpo.splitlines()
    titulo = encabezado.lstrip("# ").strip().lower()
    inicio = next((k for k, linea in enumerate(lineas)
                   if linea.startswith("#") and linea.lstrip("# ").strip().lower() == titulo), None)
    if inicio is None:
        nuevo = cuerpo.rstrip() + "\n\n" + seccion
    else:
        fin = next((k for k in range(inicio + 1, len(lineas)) if re.match(rf"^#{{1,{nivel}}}\s", lineas[k])),
                   len(lineas))
        nuevo = "\n".join(lineas[:inicio] + seccion.splitlines() + ([""] if fin < len(lineas) else []) + lineas[fin:])
    return reponer_marcas(prefijo, nuevo, sufijo)


# ── GIFT ──────────────────────────────────────────────────────────────────────

MARCADOR = re.compile(r"^-{3,}\s*PREGUNTA\s+(\d+)\s*-{3,}\s*$", re.MULTILINE | re.IGNORECASE)


def separar_gift(texto: str) -> Tuple[List[Tuple[List[str], str]], str]:
    """([(líneas previas: comentarios y $CATEGORY, cuerpo de la pregunta)], final) del archivo.

    Las preguntas GIFT se separan por líneas en blanco; un bloque sin pregunta (sólo comentarios
    o una categoría) queda como líneas previas de la pregunta siguiente.
    """
    preguntas: List[Tuple[List[str], str]] = []
    previas: List[str] = []
    for bloque in re.split(r"\n\s*\n", texto.strip("\n")):
        lineas = bloque.splitlines()
        cabecera = []
        while lineas and (lineas[0].lstrip().startswith("//") or lineas[0].lstrip().startswith("$CATEGORY")):
            cabecera.append(lineas.pop(0))
        cuerpo = "\n".join(lineas).strip()
        if cuerpo:
            preguntas.append((previas + cabecera, cuerpo))
            previas = []
        else:
            previas += cabecera + [""]
    final = "\n".join(previas).strip()
    return preguntas, final


def lote_gift(preguntas: List[Tuple[List[str], str]]) -> str:
    return "\n\n".join(f"--- PREGUNTA {i} ---\n{cuerpo}" for i, (_, cuerpo) in enumerate(preguntas, 1))


def rearmar_gift(preguntas: List[Tuple[List[str], str]], final: str, respuesta: str) -> Optional[str]:
    """El archivo con cada pregunta devuelta en su lugar (None si la respuesta no trae marcadores)."""
    marcas = list(MARCADOR.finditer(respuesta))
    if not marcas:
        return None
    nuevos: Dict[int, str] = {}
    for actual, siguiente in zip(marcas, marcas[1:] + [None], strict=True):
        bloque = respuesta[actual.end():siguiente.start() if siguiente else len(respuesta)].strip()
        bloque = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", bloque).strip()
        if bloque:
            nuevos.setdefault(int(actual.group(1)), bloque)
    partes = []
    for i, (previas, cuerpo) in enumerate(preguntas, 1):
        cabecera = "\n".join(previas).strip("\n")
        partes.append((cabecera + "\n" if cabecera else "") + nuevos.get(i, cuerpo))
    return "\n\n".join(partes + ([final] if final else [])) + "\n"
