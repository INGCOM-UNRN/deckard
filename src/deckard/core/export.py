"""Exportación multiformato (Markdown, HTML, PDF, Typst) y gestión de plantillas de deckard."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import jinja2

from deckard.core.models import Ejercicio

from deckard.core.export_plantillas import (  # noqa: F401
    DIR_BUILTIN_TEMPLATES,
    FormatoExport,
    buscar_plantilla,
    cargar_css_estilos,
    cargar_tests_ejercicio,
    inicializar_plantillas,
    markdown_a_html,
)

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


BLOOM_TYPST_COLORS: Dict[str, Tuple[str, str]] = {
    "RECORDAR": ('rgb("dbeafe")', 'rgb("1e40af")'),       # Azul
    "COMPRENDER": ('rgb("cffafe")', 'rgb("155e75")'),     # Cian
    "APLICAR": ('rgb("dcfce7")', 'rgb("166534")'),        # Verde
    "ANALIZAR": ('rgb("fef9c3")', 'rgb("854d0e")'),       # Amarillo
    "EVALUAR": ('rgb("ffedd5")', 'rgb("9a3412")'),        # Naranja
    "CREAR": ('rgb("f3e8ff")', 'rgb("6b21a8")'),          # Púrpura
}


def generar_badges_typst(ejercicio: Ejercicio, incluir_tags: bool = True) -> str:
    """Genera código Typst para renderizar badges visuales de dificultad, tiempo y tags (QoL 13)."""
    bloom_nombre = ejercicio.bloom.name
    bg_color, text_color = BLOOM_TYPST_COLORS.get(bloom_nombre, ('rgb("f3f4f6")', 'rgb("374151")'))

    badge_def = (
        '#let badge(txt, fill: rgb("e5e7eb"), text-color: black) = box('
        'fill: fill, radius: 3.5pt, inset: (x: 6pt, y: 3pt), baseline: 0%, '
        'text(fill: text-color, size: 7.5pt, weight: "bold", txt))\n'
    )
    badges = [
        f'badge("{bloom_nombre}", fill: {bg_color}, text-color: {text_color})',
        f'badge("⏱ {ejercicio.minutos_estimados} min", fill: rgb("fef3c7"), text-color: rgb("b45309"))',
        f'badge("{ejercicio.tema.upper()}", fill: rgb("e0e7ff"), text-color: rgb("3730a3"))',
    ]
    if incluir_tags and hasattr(ejercicio, "tags") and ejercicio.tags:
        for tag in ejercicio.tags[:3]:
            badges.append(f'badge("#{tag}", fill: rgb("f1f5f9"), text-color: rgb("475569"))')

    return badge_def + "#stack(dir: ltr, spacing: 5pt, " + ", ".join(badges) + ")\n"


def renderizar_ejercicio_typst(
    ejercicio: Ejercicio,
    dir_ejercicio: Optional[Path] = None,
    template_nombre_o_ruta: Optional[str] = None,
    incluir_solucion: bool = False,
    incluir_pistas: bool = False,
    incluir_badges: bool = True,
    dir_banco: Optional[Path] = None,
) -> Tuple[str, Optional[Path]]:
    """Renderiza un ejercicio a formato Typst (.typ) con badges visuales."""
    template_str, base_path = buscar_plantilla(
        template_nombre_o_ruta, tipo="ejercicio", extension=".typ.j2", dir_banco=dir_banco
    )
    env = jinja2.Environment(autoescape=False)
    template = env.from_string(template_str)

    badges_code = generar_badges_typst(ejercicio) if incluir_badges else ""

    typst_salida = template.render(
        ejercicio=ejercicio,
        dir_ejercicio=dir_ejercicio,
        incluir_soluciones=incluir_solucion,
        incluir_pistas=incluir_pistas,
        badges_typst=badges_code,
        generar_badges=generar_badges_typst,
    )
    return typst_salida, base_path


def renderizar_guia_typst(
    guia_meta: dict,
    ejercicios_con_dir: List[Tuple[Optional[Path], Ejercicio]],
    template_nombre_o_ruta: Optional[str] = None,
    incluir_soluciones: bool = False,
    incluir_pistas: bool = False,
    incluir_badges: bool = True,
    dir_banco: Optional[Path] = None,
    dos_columnas: bool = False,
) -> Tuple[str, Optional[Path]]:
    """Renderiza una guía completa a formato Typst (.typ) con badges por ejercicio."""
    template_str, base_path = buscar_plantilla(
        template_nombre_o_ruta, tipo="guia", extension=".typ.j2", dir_banco=dir_banco
    )
    env = jinja2.Environment(autoescape=False)
    template = env.from_string(template_str)

    items = []
    total_min = 0
    for dir_ej, ej in ejercicios_con_dir:
        items.append({
            "ejercicio": ej,
            "dir": dir_ej,
            "enunciado_typst": ej.enunciado_md,
            "badges_typst": generar_badges_typst(ej) if incluir_badges else "",
        })
        total_min += ej.minutos_estimados

    typst_salida = template.render(
        guia=guia_meta,
        ejercicios=[e for _, e in ejercicios_con_dir],
        items=items,
        total_minutos=total_min,
        incluir_soluciones=incluir_soluciones,
        incluir_pistas=incluir_pistas,
        dos_columnas=dos_columnas,
        generar_badges=generar_badges_typst,
    )
    return typst_salida, base_path


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
    """Renderiza un ejercicio a HTML."""
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


def compilar_typst_a_pdf(
    typst_content: str,
    salida_pdf: Path,
    root_dir: Optional[Path] = None,
) -> Path:
    """Compila contenido Typst a PDF usando el paquete python 'typst' o el binario CLI."""
    salida_pdf = Path(salida_pdf)
    salida_pdf.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".typ", mode="w", encoding="utf-8", delete=False) as tmp:
        tmp.write(typst_content)
        tmp_path = Path(tmp.name)

    try:
        try:
            import typst
            typst.compile(str(tmp_path), output=str(salida_pdf), root=str(root_dir) if root_dir else None)
            return salida_pdf
        except Exception as e_py:
            res = subprocess.run(
                ["typst", "compile", str(tmp_path), str(salida_pdf)],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode != 0:
                raise RuntimeError(f"Error compilando Typst a PDF: {res.stderr or e_py}") from e_py
            return salida_pdf
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def compilar_pdf(
    html_or_typst_content: str,
    salida_pdf: Path,
    base_url: Optional[str] = None,
    asset_dirs: Optional[List[Path]] = None,
) -> Path:
    """Compila contenido a PDF.
    
    Typst es el motor prioritario y oficial del ecosistema.
    WeasyPrint se mantiene exclusivamente como fallback legacy para documentos HTML y está deprecado.
    """
    salida_pdf = Path(salida_pdf)
    salida_pdf.parent.mkdir(parents=True, exist_ok=True)

    # Si es contenido Typst (#set o #align o //)
    if "#set" in html_or_typst_content or "//" in html_or_typst_content.splitlines()[0]:
        return compilar_typst_a_pdf(html_or_typst_content, salida_pdf, root_dir=Path(base_url) if base_url else None)

    # Si es HTML, intentar WeasyPrint (legacy) si está disponible, o convertir vía typst
    resolved_base_url = str(base_url) if base_url else "."
    try:
        import warnings
        import weasyprint
        warnings.warn(
            "El renderizado PDF vía WeasyPrint está deprecado en favor del motor nativo Typst.",
            DeprecationWarning,
            stacklevel=2,
        )
        weasyprint.HTML(string=html_or_typst_content, base_url=resolved_base_url).write_pdf(
            target=str(salida_pdf)
        )
        return salida_pdf
    except Exception:
        # Fallback generando documento typst básico
        typ_fallback = f"""#set page(paper: "a4", margin: 2cm)\n#set text(font: ("Liberation Sans", "Arial"), size: 10.5pt)\n= Documento\n{html_or_typst_content}\n"""
        return compilar_typst_a_pdf(typ_fallback, salida_pdf, root_dir=Path(base_url) if base_url else None)
