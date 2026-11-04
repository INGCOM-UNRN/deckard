"""Diagramas de los enunciados en el sitio MyST (`deckard export myst`).

Los enunciados se escriben como texto:

- un diagrama de estructura de datos es un bloque ```estructura (o ```statics) con el bloque de
  statics en YAML/JSON, el formato que dibuja alucarD;
- un diagrama mermaid es un bloque ```mermaid.

deckard no dibuja las estructuras: el hook de pre-commit `alucard-diagramas` de alucarD
(`alucard diagramas-md`) las deja versionadas junto al ejercicio, en
`<ejercicio>/diagramas/estructura-<hash>.svg`, con `<hash>` = los 12 primeros dígitos del SHA-1 del
cuerpo del bloque sin espacios al principio ni al final. Acá cada bloque se cambia por esa imagen
(copiada junto a la página) y cada mermaid por la directiva `{mermaid}` de MyST. Un bloque sin su
SVG es un error: el sitio no publica el YAML en crudo.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List

DIR_SVGS = "diagramas"

# Mismas expresiones que `generador_examenes.diagramas` (alucarD): el bloque empieza en la columna 0.
_FENCE_ESTRUCTURA = re.compile(
    r"^(?P<valla>`{3,}|~{3,})[ \t]*(?:estructura|statics)[ \t]*\n(?P<cuerpo>.*?)^(?P=valla)[ \t]*$", re.S | re.M)
_FENCE_MERMAID = re.compile(r"^(?P<valla>`{3,}|~{3,})[ \t]*mermaid[ \t]*\n(?P<cuerpo>.*?)^(?P=valla)[ \t]*$",
                            re.S | re.M)


def nombre_svg(cuerpo: str) -> str:
    """El nombre que `alucard diagramas-md` le da al SVG de un bloque ```estructura."""
    return f"estructura-{hashlib.sha1(cuerpo.strip().encode('utf-8')).hexdigest()[:12]}.svg"


@dataclass
class DiagramasPagina:
    markdown: str
    faltantes: List[str] = field(default_factory=list)   # SVG que el hook todavía no generó


def publicar_diagramas(markdown: str, fuentes: Iterable[Path], pagina: Path) -> DiagramasPagina:
    """Cambia los bloques de diagramas de `markdown` por imágenes para la página `pagina`.

    `fuentes` son los directorios de ejercicio donde buscar `diagramas/<nombre>.svg` (uno para la
    página de un ejercicio; los de todos sus ejercicios para una guía). El SVG se copia a
    `<dir de pagina>/diagramas/`.
    """
    fuentes = list(fuentes)
    res = DiagramasPagina(markdown)

    def estructura(m: re.Match) -> str:
        nombre = nombre_svg(m.group("cuerpo"))
        origen = next((d / DIR_SVGS / nombre for d in fuentes if (d / DIR_SVGS / nombre).is_file()), None)
        if origen is None:
            res.faltantes.append(nombre)
            return m.group(0)
        destino = pagina.parent / DIR_SVGS / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen, destino)
        return f"![Diagrama de la estructura]({DIR_SVGS}/{nombre})"

    def mermaid(m: re.Match) -> str:
        return f"{m.group('valla')}{{mermaid}}\n{m.group('cuerpo')}{m.group('valla')}"

    texto = _FENCE_ESTRUCTURA.sub(estructura, markdown)
    res.markdown = _FENCE_MERMAID.sub(mermaid, texto)
    return res


def svgs_faltantes(markdown: str, dir_ejercicio: Path) -> List[str]:
    """Los SVG de los ```estructura de `markdown` que no están en `dir_ejercicio/diagramas/`."""
    return [n for n in (nombre_svg(m.group("cuerpo")) for m in _FENCE_ESTRUCTURA.finditer(markdown))
            if not (dir_ejercicio / DIR_SVGS / n).is_file()]


def mensaje_faltantes(pagina: str, faltantes: List[str], fuentes: Iterable[Path]) -> str:
    dirs = ", ".join(os.fspath(d) for d in fuentes)
    return (f"{pagina}: {len(faltantes)} diagrama(s) ```estructura sin su SVG ({', '.join(faltantes)}) en "
            f"{dirs}. Generalos con `alucard diagramas-md` (hook de pre-commit `alucard-diagramas`) y "
            f"versionalos.")
