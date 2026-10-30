"""Trazabilidad entre el apunte y el banco de enunciados.

El `temas.yaml` del repositorio de enunciados dice, para cada tema, qué páginas del apunte lo
explican (`apunte: [apunte/bloque_2_memoria/2_punteros.md]`) y dónde están publicados los dos
sitios (`sitios: {apunte: …, enunciados: …}`). Con eso:

- cada página de tema y de ejercicio del sitio de enunciados enlaza a la teoría del apunte;
- `deckard export apunte` escribe en esas páginas del apunte un bloque `seealso` con los
  ejercicios del tema, entre las marcas `% deckard export apunte: inicio` y `…: fin`.

Las URL se arman como las arma MyST: una página por archivo, con un slug plano que sale del
nombre (sin el número del principio, en minúsculas y con guiones) y `-1`, `-2`… si se repite.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml

MARCA_INICIO = "% deckard export apunte: inicio"
MARCA_FIN = "% deckard export apunte: fin"
_BLOQUE = re.compile(rf"^{re.escape(MARCA_INICIO)}[^\n]*\n.*?^{re.escape(MARCA_FIN)}[^\n]*\n?", re.MULTILINE | re.DOTALL)

EJERCICIOS_POR_BLOQUE = 5


def slug_myst(ruta: str) -> str:
    """El slug de una página MyST: `bloque_2_memoria/2_punteros.md` → `punteros`."""
    nombre = Path(ruta).stem
    nombre = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    nombre = re.sub(r"^\d+[_\-.\s]*", "", nombre)
    return re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")


def slugs_de_toc(archivos: Iterable[str]) -> Dict[str, str]:
    """Slug de cada archivo del TOC, en orden, con el sufijo `-N` que MyST agrega a los repetidos."""
    vistos: Dict[str, int] = {}
    slugs: Dict[str, str] = {}
    for archivo in archivos:
        base = slug_myst(archivo)
        if base in vistos:
            vistos[base] += 1
            slugs[archivo] = f"{base}-{vistos[base]}"
        else:
            vistos[base] = 0
            slugs[archivo] = base
    return slugs


def archivos_del_toc(myst_yml: Path) -> List[str]:
    """Los `file:` del `project.toc` de un myst.yml, en orden."""
    datos = yaml.safe_load(myst_yml.read_text(encoding="utf-8")) or {}
    archivos: List[str] = []

    def recorrer(entradas: object) -> None:
        for e in entradas if isinstance(entradas, list) else []:
            if isinstance(e, dict):
                if e.get("file"):
                    archivos.append(str(e["file"]))
                recorrer(e.get("children"))

    recorrer((datos.get("project") or {}).get("toc"))
    return archivos


def titulo_de_pagina(archivo: Path) -> Optional[str]:
    """El `title:` del frontmatter o el primer título `# …` de una página MyST."""
    try:
        texto = archivo.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.match(r"---\n(.*?)\n---\n", texto, re.DOTALL)
    if m:
        try:
            datos = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            datos = {}
        if isinstance(datos, dict) and datos.get("title"):
            return str(datos["title"])
    m = re.search(r"^#\s+(.+?)\s*$", texto, re.MULTILINE)
    return m.group(1) if m else None


@dataclass
class SitioApunte:
    """Dónde está publicado el apunte y el slug y el título de cada página (si se tiene su repositorio)."""

    url: str
    slugs: Dict[str, str]
    titulos: Dict[str, str] = field(default_factory=dict)

    def titulo_de(self, ruta: str) -> str:
        pagina = ruta.partition("#")[0]
        return self.titulos.get(pagina) or slug_myst(pagina).replace("-", " ").capitalize()

    def url_de(self, ruta: str) -> str:
        ruta_pag, _, ancla = ruta.partition("#")
        slug = self.slugs.get(ruta_pag) or slug_myst(ruta_pag)
        return f"{self.url.rstrip('/')}/{slug}" + (f"#{ancla}" if ancla else "")


def sitio_apunte(url: str, dir_apunte: Optional[Path] = None) -> SitioApunte:
    myst = dir_apunte / "myst.yml" if dir_apunte else None
    if dir_apunte is None or myst is None or not myst.is_file():
        return SitioApunte(url=url, slugs={})
    archivos = archivos_del_toc(myst)
    titulos = {a: t for a in archivos if (t := titulo_de_pagina(dir_apunte / a))}
    return SitioApunte(url=url, slugs=slugs_de_toc(archivos), titulos=titulos)


def url_enunciados(base: str, pagina: str) -> str:
    """URL publicada de una página del sitio de enunciados (`consignas/<tema>/<id>.md`)."""
    return f"{base.rstrip('/')}/{slug_myst(pagina)}"


# ---------------------------------------------------------------------------
# Bloques en el apunte
# ---------------------------------------------------------------------------

@dataclass
class EnlaceEjercicio:
    titulo: str
    url: str
    bloom: int
    minutos: int


@dataclass
class TemaEnApunte:
    tema: str
    titulo: str
    url: str          # página del tema en el sitio de enunciados
    total: int
    ejercicios: List[EnlaceEjercicio]


def bloque_seealso(temas: List[TemaEnApunte]) -> str:
    """El bloque que va en una página del apunte, con sus marcas."""
    lineas = [
        MARCA_INICIO + " (generado: no editar a mano)",
        ":::{seealso} Ejercicios para practicar",
    ]
    for t in temas:
        lineas.append(f"- **[{t.titulo}]({t.url})**: {t.total} ejercicios en el banco de enunciados.")
        for e in t.ejercicios:
            lineas.append(f"  - [{e.titulo}]({e.url}) · B{e.bloom} · ~{e.minutos} min")
    lineas += [
        "",
        "Cada ejercicio trae su paquete `.ripkg` con los casos de prueba: descargalo desde la página del",
        "ejercicio y verificá tu solución con `ripley run <ejercicio>.ripkg`.",
        ":::",
        MARCA_FIN,
        "",
    ]
    return "\n".join(lineas)


def insertar_bloque(texto: str, bloque: str) -> str:
    """El texto de la página con el bloque reemplazado (o agregado al final si todavía no estaba)."""
    if _BLOQUE.search(texto):
        return _BLOQUE.sub(lambda _m: bloque, texto, count=1)
    return texto.rstrip("\n") + "\n\n" + bloque


def bloque_actual(texto: str) -> Optional[str]:
    m = _BLOQUE.search(texto)
    return m.group(0) if m else None


def actualizar_paginas(dir_apunte: Path, bloques: Dict[str, str], escribir: bool = True) -> Tuple[List[str], List[str]]:
    """Escribe cada bloque en su página del apunte; devuelve (cambiadas, faltantes).

    Con `escribir=False` sólo informa qué páginas cambiarían (para verificar en CI).
    """
    cambiadas: List[str] = []
    faltantes: List[str] = []
    for ruta, bloque in sorted(bloques.items()):
        archivo = dir_apunte / ruta
        if not archivo.is_file():
            faltantes.append(ruta)
            continue
        texto = archivo.read_text(encoding="utf-8")
        nuevo = insertar_bloque(texto, bloque)
        if nuevo != texto:
            cambiadas.append(ruta)
            if escribir:
                archivo.write_text(nuevo, encoding="utf-8")
    return cambiadas, faltantes


def paginas_con_bloque(dir_apunte: Path) -> List[str]:
    """Las páginas del apunte que tienen un bloque generado (para sacar los que ya no corresponden)."""
    return sorted(
        p.relative_to(dir_apunte).as_posix()
        for p in dir_apunte.rglob("*.md")
        if "_build" not in p.parts and MARCA_INICIO in p.read_text(encoding="utf-8", errors="ignore")
    )


def quitar_bloque(texto: str) -> str:
    return _BLOQUE.sub("", texto).rstrip("\n") + "\n"
