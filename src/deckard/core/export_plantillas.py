"""Plantillas, estilos y utilidades base de exportación de deckard (formato, búsqueda de plantillas, CSS, Markdown→HTML, tests de ejercicio)."""

from __future__ import annotations

from enum import Enum
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import markdown

DIR_BUILTIN_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


class FormatoExport(str, Enum):
    PDF = "pdf"
    MD = "md"
    MARKDOWN = "markdown"
    HTML = "html"
    TYP = "typ"
    TYPST = "typst"


def inicializar_plantillas(destino: Path, sobrescribir: bool = False) -> List[Path]:
    """Copia las plantillas y hojas de estilo built-in al directorio de destino para personalización."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    archivos_creados: List[Path] = []
    for plantilla in DIR_BUILTIN_TEMPLATES.iterdir():
        if plantilla.is_file():
            target = destino / plantilla.name
            if target.exists() and not sobrescribir:
                continue
            shutil.copy2(plantilla, target)
            archivos_creados.append(target)

    return archivos_creados


def buscar_plantilla(
    nombre_o_ruta: Optional[str] = None,
    tipo: str = "ejercicio",
    extension: str = ".html",
    dir_banco: Optional[Path] = None,
) -> Tuple[str, Optional[Path]]:
    """Busca la plantilla en orden: ruta directa -> local -> global -> built-in.

    Retorna una tupla (contenido_jinja2, directorio_base_plantilla).
    """
    if not extension.startswith("."):
        extension = f".{extension}"

    if nombre_o_ruta:
        ruta_directa = Path(nombre_o_ruta)
        if ruta_directa.is_file():
            return ruta_directa.read_text(encoding="utf-8"), ruta_directa.parent

    nombre_archivo = nombre_o_ruta or f"{tipo}{extension}"
    if not any(nombre_archivo.endswith(ext) for ext in (".html", ".jinja2", ".md", ".markdown", ".css", ".typ", ".typ.j2")):
        nombre_archivo = f"{nombre_archivo}{extension}"

    # 1. Local en el directorio de trabajo o banco
    candidatos_locales = [
        Path("templates") / nombre_archivo,
        Path("plantillas") / nombre_archivo,
    ]
    if dir_banco:
        candidatos_locales.append(Path(dir_banco) / "templates" / nombre_archivo)
        candidatos_locales.append(Path(dir_banco) / "plantillas" / nombre_archivo)

    for cand in candidatos_locales:
        if cand.is_file():
            return cand.read_text(encoding="utf-8"), cand.parent

    # 2. Global usuario
    home = Path.home()
    candidatos_globales = [
        home / ".config" / "deckard" / "templates" / nombre_archivo,
        home / ".deckard" / "templates" / nombre_archivo,
    ]
    for cand in candidatos_globales:
        if cand.is_file():
            return cand.read_text(encoding="utf-8"), cand.parent

    # 3. Built-in del paquete
    cand_builtin = DIR_BUILTIN_TEMPLATES / (nombre_archivo if nombre_o_ruta else f"{tipo}{extension}")
    if cand_builtin.is_file():
        return cand_builtin.read_text(encoding="utf-8"), cand_builtin.parent

    cand_builtin_fallback = DIR_BUILTIN_TEMPLATES / f"{tipo}{extension}"
    if cand_builtin_fallback.is_file():
        return cand_builtin_fallback.read_text(encoding="utf-8"), cand_builtin_fallback.parent

    raise FileNotFoundError(f"No se pudo encontrar la plantilla '{nombre_o_ruta or tipo + extension}'")


def cargar_css_estilos(
    nombre_o_ruta: Optional[str] = None,
    dir_banco: Optional[Path] = None,
) -> Tuple[str, Optional[Path]]:
    """Carga la hoja de estilo CSS por defecto o personalizada."""
    return buscar_plantilla(nombre_o_ruta, tipo="estilos", extension=".css", dir_banco=dir_banco)


def markdown_a_html(texto_md: str) -> str:
    """Convierte texto en Markdown a HTML seguro con extensiones comunes."""
    return markdown.markdown(
        texto_md,
        extensions=[
            "extra",
            "codehilite",
            "fenced_code",
            "tables",
            "toc",
            "sane_lists",
        ],
    )


def cargar_tests_ejercicio(dir_ejercicio: Optional[Path]) -> List[Dict[str, Any]]:
    """Carga los casos de test .in / .out de un ejercicio si existen."""
    if not dir_ejercicio or not Path(dir_ejercicio).is_dir():
        return []

    dir_tests = Path(dir_ejercicio) / "tests"
    if not dir_tests.is_dir():
        return []

    casos: List[Dict[str, Any]] = []
    archivos_in = sorted(dir_tests.glob("*.in"))
    for file_in in archivos_in:
        nombre_base = file_in.stem
        file_out = dir_tests / f"{nombre_base}.out"
        entrada = file_in.read_text(encoding="utf-8", errors="replace")
        salida = file_out.read_text(encoding="utf-8", errors="replace") if file_out.is_file() else ""
        casos.append({
            "nombre": nombre_base,
            "in": entrada,
            "out": salida,
            "entrada": entrada,
            "salida": salida,
        })
    return casos
