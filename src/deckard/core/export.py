"""Exportación multiformato (Markdown, HTML, PDF) y gestión de plantillas de deckard."""

from __future__ import annotations

from enum import Enum
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple

import jinja2
import markdown

from deckard.core.models import Ejercicio

DIR_BUILTIN_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


class FormatoExport(str, Enum):
    PDF = "pdf"
    MD = "md"
    MARKDOWN = "markdown"
    HTML = "html"


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
    if not any(nombre_archivo.endswith(ext) for ext in (".html", ".jinja2", ".md", ".markdown", ".css")):
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
        home / ".gemini" / "config" / "deckard" / "templates" / nombre_archivo,
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


def markdown_a_html(md_texto: str) -> str:
    """Convierte texto Markdown a HTML enriquecido."""
    if not md_texto:
        return ""
    return markdown.markdown(
        md_texto,
        extensions=["fenced_code", "tables", "codehilite", "nl2br", "sane_lists"],
    )


def cargar_tests_ejercicio(dir_ejercicio: Optional[Path]) -> List[Dict[str, str]]:
    """Carga los pares .in y .out en la subcarpeta tests/ si existen."""
    if not dir_ejercicio or not dir_ejercicio.is_dir():
        return []
    tests_dir = dir_ejercicio / "tests"
    if not tests_dir.is_dir():
        return []

    casos = []
    for in_file in sorted(tests_dir.glob("*.in")):
        out_file = in_file.with_suffix(".out")
        out_content = out_file.read_text(encoding="utf-8") if out_file.is_file() else "(sin salida esperada)"
        casos.append({
            "nombre": in_file.stem,
            "entrada": in_file.read_text(encoding="utf-8"),
            "salida": out_content,
        })
    return casos


def cargar_css_estilos(custom_css_path: Optional[Path] = None, dir_banco: Optional[Path] = None) -> Tuple[str, Optional[Path]]:
    """Carga la hoja de estilos CSS (custom o estilos.css)."""
    if custom_css_path and Path(custom_css_path).is_file():
        p = Path(custom_css_path)
        return p.read_text(encoding="utf-8"), p.parent

    try:
        css_content, base_p = buscar_plantilla("estilos.css", tipo="estilos", extension=".css", dir_banco=dir_banco)
        return css_content, base_p
    except Exception:
        return "", None


def renderizar_ejercicio_md(
    ejercicio: Ejercicio,
    dir_ejercicio: Optional[Path] = None,
    template_nombre_o_ruta: Optional[str] = None,
    incluir_meta: bool = True,
    incluir_solucion: bool = False,
    incluir_pistas: bool = False,
    incluir_tests: bool = False,
    dir_banco: Optional[Path] = None,
) -> Tuple[str, Optional[Path]]:
    """Renderiza un ejercicio a Markdown usando plantilla Jinja2."""
    template_str, base_path = buscar_plantilla(
        template_nombre_o_ruta, tipo="ejercicio", extension=".md", dir_banco=dir_banco
    )
    env = jinja2.Environment(autoescape=False)
    template = env.from_string(template_str)

    tests_casos = cargar_tests_ejercicio(dir_ejercicio) if incluir_tests else []

    md_salida = template.render(
        ejercicio=ejercicio,
        incluir_meta=incluir_meta,
        incluir_solucion=incluir_solucion,
        incluir_pistas=incluir_pistas,
        incluir_tests=incluir_tests,
        tests_casos=tests_casos,
    )
    return md_salida, base_path


def renderizar_guia_md(
    guia_meta: dict,
    ejercicios_con_dir: List[Tuple[Optional[Path], Ejercicio]],
    template_nombre_o_ruta: Optional[str] = None,
    incluir_soluciones: bool = False,
    incluir_pistas: bool = False,
    dir_banco: Optional[Path] = None,
) -> Tuple[str, Optional[Path]]:
    """Renderiza una guía completa a Markdown usando plantilla Jinja2."""
    template_str, base_path = buscar_plantilla(
        template_nombre_o_ruta, tipo="guia", extension=".md", dir_banco=dir_banco
    )
    env = jinja2.Environment(autoescape=False)
    template = env.from_string(template_str)

    items = []
    total_min = 0
    for dir_ej, ej in ejercicios_con_dir:
        items.append({
            "ejercicio": ej,
            "dir": dir_ej,
        })
        total_min += ej.minutos_estimados

    md_salida = template.render(
        guia=guia_meta,
        ejercicios=[e for _, e in ejercicios_con_dir],
        items=items,
        total_minutos=total_min,
        incluir_soluciones=incluir_soluciones,
        incluir_pistas=incluir_pistas,
    )
    return md_salida, base_path


def renderizar_ejercicio_html(
    ejercicio: Ejercicio,
    dir_ejercicio: Optional[Path] = None,
    template_nombre_o_ruta: Optional[str] = None,
    incluir_meta: bool = True,
    incluir_solucion: bool = False,
    incluir_pistas: bool = False,
    incluir_tests: bool = False,
    extra_css: Optional[str] = None,
    dir_banco: Optional[Path] = None,
    via_markdown_pipeline: bool = False,
) -> Tuple[str, Optional[Path]]:
    """Renderiza un ejercicio a HTML (directo con HTML o pasando primero por Markdown)."""
    if via_markdown_pipeline or (template_nombre_o_ruta and template_nombre_o_ruta.endswith((".md", ".markdown"))):
        md_text, md_base = renderizar_ejercicio_md(
            ejercicio=ejercicio,
            dir_ejercicio=dir_ejercicio,
            template_nombre_o_ruta=template_nombre_o_ruta,
            incluir_meta=incluir_meta,
            incluir_solucion=incluir_solucion,
            incluir_pistas=incluir_pistas,
            incluir_tests=incluir_tests,
            dir_banco=dir_banco,
        )
        css_content, css_base = cargar_css_estilos(None, dir_banco=dir_banco)
        html_body = markdown_a_html(md_text)
        html_salida = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{ejercicio.titulo} — {ejercicio.id}</title>
<style>
{css_content}
{extra_css or ''}
</style>
</head>
<body>
<div class="header-banner">
    <div class="materia-tag">Cátedra de Programación 1 · Ejercicio Práctico</div>
</div>
<div class="enunciado-content">
{html_body}
</div>
</body>
</html>"""
        return html_salida, md_base or css_base

    # Renderizado directo mediante plantilla HTML
    template_str, base_path = buscar_plantilla(
        template_nombre_o_ruta, tipo="ejercicio", extension=".html", dir_banco=dir_banco
    )
    env = jinja2.Environment(autoescape=True)
    template = env.from_string(template_str)

    enunciado_html = markdown_a_html(ejercicio.enunciado_md)
    tests_casos = cargar_tests_ejercicio(dir_ejercicio) if incluir_tests else []

    html_salida = template.render(
        ejercicio=ejercicio,
        enunciado_html=enunciado_html,
        incluir_meta=incluir_meta,
        incluir_solucion=incluir_solucion,
        incluir_pistas=incluir_pistas,
        incluir_tests=incluir_tests,
        tests_casos=tests_casos,
        extra_css=extra_css or "",
    )
    return html_salida, base_path


def renderizar_guia_html(
    guia_meta: dict,
    ejercicios_con_dir: List[Tuple[Optional[Path], Ejercicio]],
    template_nombre_o_ruta: Optional[str] = None,
    incluir_soluciones: bool = False,
    incluir_pistas: bool = False,
    extra_css: Optional[str] = None,
    dir_banco: Optional[Path] = None,
    via_markdown_pipeline: bool = False,
) -> Tuple[str, Optional[Path]]:
    """Renderiza una guía completa a HTML."""
    if via_markdown_pipeline or (template_nombre_o_ruta and template_nombre_o_ruta.endswith((".md", ".markdown"))):
        md_text, md_base = renderizar_guia_md(
            guia_meta=guia_meta,
            ejercicios_con_dir=ejercicios_con_dir,
            template_nombre_o_ruta=template_nombre_o_ruta,
            incluir_soluciones=incluir_soluciones,
            incluir_pistas=incluir_pistas,
            dir_banco=dir_banco,
        )
        css_content, css_base = cargar_css_estilos(None, dir_banco=dir_banco)
        html_body = markdown_a_html(md_text)
        nombre_guia = guia_meta.get("nombre", "Guía de Ejercicios")
        html_salida = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{nombre_guia}</title>
<style>
{css_content}
{extra_css or ''}
</style>
</head>
<body>
<div class="guia-content">
{html_body}
</div>
</body>
</html>"""
        return html_salida, md_base or css_base

    template_str, base_path = buscar_plantilla(
        template_nombre_o_ruta, tipo="guia", extension=".html", dir_banco=dir_banco
    )
    env = jinja2.Environment(autoescape=True)
    template = env.from_string(template_str)

    items = []
    total_min = 0
    for dir_ej, ej in ejercicios_con_dir:
        items.append({
            "ejercicio": ej,
            "dir": dir_ej,
            "enunciado_html": markdown_a_html(ej.enunciado_md),
        })
        total_min += ej.minutos_estimados

    html_salida = template.render(
        guia=guia_meta,
        ejercicios=[e for _, e in ejercicios_con_dir],
        items=items,
        total_minutos=total_min,
        incluir_soluciones=incluir_soluciones,
        incluir_pistas=incluir_pistas,
        extra_css=extra_css or "",
    )
    return html_salida, base_path


def compilar_pdf(
    html_content: str,
    salida_pdf: Path,
    base_url: Optional[str] = None,
    asset_dirs: Optional[List[Path]] = None,
) -> Path:
    """Compila HTML a PDF usando WeasyPrint configurando el base_url para imágenes de plantillas y ejercicios."""
    salida_pdf = Path(salida_pdf)
    salida_pdf.parent.mkdir(parents=True, exist_ok=True)

    # Determinar el base_url para resolución de imágenes
    resolved_base_url = str(base_url) if base_url else "."

    try:
        import weasyprint
        weasyprint.HTML(string=html_content, base_url=resolved_base_url).write_pdf(
            target=str(salida_pdf)
        )
        return salida_pdf
    except Exception as e:
        raise RuntimeError(f"Error compilando PDF con WeasyPrint: {e}")
