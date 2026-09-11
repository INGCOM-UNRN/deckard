"""Exportador de ejercicios del banco a formato Moodle XML para cuestionarios virtuales (QoL 4)."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

from deckard.core.models import Ejercicio


def generar_moodle_xml_cuestionario(
    ejercicios: List[Ejercicio],
    categoria: Optional[str] = None,
    tipo_pregunta: str = "multichoice",
) -> str:
    """Genera la estructura XML de Moodle para importar en bancos de preguntas de campus virtual."""
    root = ET.Element("quiz")

    # Si se define categoría, agregar pregunta de categoría Moodle
    if categoria:
        cat_q = ET.SubElement(root, "question", type="category")
        cat_elem = ET.SubElement(cat_q, "category")
        cat_text = ET.SubElement(cat_elem, "text")
        cat_text.text = f"$course$/top/{categoria}"

    for ej in ejercicios:
        q = ET.SubElement(root, "question", type=tipo_pregunta)

        # Nombre de la pregunta
        name = ET.SubElement(q, "name")
        name_text = ET.SubElement(name, "text")
        name_text.text = f"[{ej.id}] {ej.titulo}"

        # Enunciado
        qtext = ET.SubElement(q, "questiontext", format="html")
        qtext_text = ET.SubElement(qtext, "text")
        
        # Formateo HTML para Moodle
        cuerpo_html = f"<p><strong>{html.escape(ej.titulo)}</strong></p>\n"
        cuerpo_html += f"<div><p>{html.escape(ej.enunciado_md)}</p></div>\n"
        if ej.starter:
            cuerpo_html += f"<pre><code>{html.escape(ej.starter)}</code></pre>\n"

        qtext_text.text = cuerpo_html

        # Calificación por defecto
        defgrade = ET.SubElement(q, "defaultgrade")
        defgrade.text = "1.0000000"

        # Penalización por intento erróneo
        penalty = ET.SubElement(q, "penalty")
        penalty.text = "0.3333333"

        # Opciones específicas según el tipo
        if tipo_pregunta == "multichoice":
            single = ET.SubElement(q, "single")
            single.text = "true"

            shuffle = ET.SubElement(q, "shuffleanswers")
            shuffle.text = "true"

            ansnum = ET.SubElement(q, "answernumbering")
            ansnum.text = "abc"

            # 1. Opción correcta (100%)
            ans_ok = ET.SubElement(q, "answer", fraction="100", format="html")
            ans_ok_text = ET.SubElement(ans_ok, "text")
            ans_ok_text.text = "<p>Comportamiento canónico y salida esperada según la especificación de la cátedra.</p>"
            ans_ok_fb = ET.SubElement(ans_ok, "feedback", format="html")
            ans_ok_fb_text = ET.SubElement(ans_ok_fb, "text")
            ans_ok_fb_text.text = "<p>¡Correcto! Cumple con las precondiciones y el contrato de la función.</p>"

            # 2. Distractor Off-by-one
            ans_d1 = ET.SubElement(q, "answer", fraction="0", format="html")
            ans_d1_text = ET.SubElement(ans_d1, "text")
            ans_d1_text.text = "<p>Error de desborde de índice (Off-by-one: recorre hasta N en lugar de N-1).</p>"
            ans_d1_fb = ET.SubElement(ans_d1, "feedback", format="html")
            ans_d1_fb_text = ET.SubElement(ans_d1_fb, "text")
            ans_d1_fb_text.text = "<p>Incorrecto: provoca acceso fuera de los límites del vector.</p>"

            # 3. Distractor Desreferencia nula / memoria sin inicializar
            ans_d2 = ET.SubElement(q, "answer", fraction="0", format="html")
            ans_d2_text = ET.SubElement(ans_d2, "text")
            ans_d2_text.text = "<p>Fallo de segmentación por desreferencia de puntero NULL o sin inicializar.</p>"
            ans_d2_fb = ET.SubElement(ans_d2, "feedback", format="html")
            ans_d2_fb_text = ET.SubElement(ans_d2_fb, "text")
            ans_d2_fb_text.text = "<p>Incorrecto: la solución debe verificar precondiciones antes de desreferenciar.</p>"

            # 4. Distractor Fuga de memoria
            ans_d3 = ET.SubElement(q, "answer", fraction="0", format="html")
            ans_d3_text = ET.SubElement(ans_d3, "text")
            ans_d3_text.text = "<p>Fuga de memoria (memory leak) por omitir la llamada a free() antes de retornar.</p>"
            ans_d3_fb = ET.SubElement(ans_d3, "feedback", format="html")
            ans_d3_fb_text = ET.SubElement(ans_d3_fb, "text")
            ans_d3_fb_text.text = "<p>Incorrecto: todo bloque asignado dinámicamente debe ser liberado.</p>"

        elif tipo_pregunta == "shortanswer":
            usecase = ET.SubElement(q, "usecase")
            usecase.text = "0"
            ans_ok = ET.SubElement(q, "answer", fraction="100", format="moodle_auto_format")
            ans_ok_text = ET.SubElement(ans_ok, "text")
            ans_ok_text.text = ej.id.replace("-", "_")

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")


def exportar_moodle_archivo(
    ejercicios: List[Ejercicio],
    ruta_salida: Path,
    categoria: Optional[str] = None,
    tipo_pregunta: str = "multichoice",
) -> Path:
    """Escribe las preguntas de los ejercicios en un archivo Moodle XML."""
    contenido = generar_moodle_xml_cuestionario(
        ejercicios,
        categoria=categoria,
        tipo_pregunta=tipo_pregunta,
    )
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_text(contenido, encoding="utf-8")
    return ruta_salida
