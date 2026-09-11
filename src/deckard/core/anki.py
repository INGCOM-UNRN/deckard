"""Exportador de bancos de ejercicios y conceptos de C a formato de flashcards Anki (TSV)."""

from __future__ import annotations

import csv
import html
import io
from pathlib import Path
from typing import List, Optional

from deckard.core.models import Ejercicio


def ejercicio_a_flashcards(ej: Ejercicio) -> List[dict]:
    """Genera tarjetas de estudio espaciado para un ejercicio específico."""
    cards: List[dict] = []

    # Tarjeta 1: Enunciado -> Estrategia y Solución C
    frente_enunciado = f"""<div style="font-family: sans-serif;">
<h3>[Programación 1] {html.escape(ej.titulo)}</h3>
<p><strong>Tema:</strong> {html.escape(ej.tema)} | <strong>Nivel Bloom:</strong> {int(ej.bloom)} ({ej.bloom.name})</p>
<hr>
<div>{html.escape(ej.enunciado_md).replace(chr(10), '<br>')}</div>
</div>"""

    dorso_enunciado = f"""<div style="font-family: sans-serif;">
<h4>Solución Modelo Canónica</h4>
<pre style="background:#272822; color:#f8f8f2; padding:10px; border-radius:5px; text-align:left;">
<code>{html.escape(ej.solucion_c.strip() if ej.solucion_c else '/* Pendiente */')}</code>
</pre>
<h4>Pistas Clave</h4>
<ul>
{''.join(f'<li>{html.escape(p)}</li>' for p in ej.pistas)}
</ul>
</div>"""

    tags_base = [
        "deckard",
        f"tema::{ej.tema.replace(' ', '_')}",
        f"bloom::b{int(ej.bloom)}",
    ] + [f"tag::{t.replace(' ', '_')}" for t in ej.tags]

    cards.append({
        "frente": frente_enunciado.replace("\n", " ").strip(),
        "dorso": dorso_enunciado.replace("\n", " ").strip(),
        "tags": " ".join(tags_base),
    })

    # Tarjeta 2: Firmas de funciones y contratos
    for fn in ej.funciones:
        frente_fn = f"""<div style="font-family: sans-serif;">
<h3>Firma de Función C: {html.escape(fn.nombre)}</h3>
<p>¿Cuál es la firma canónica, tipo de retorno y parámetros para <strong>{html.escape(fn.nombre)}</strong> en el tema <em>{html.escape(ej.tema)}</em>?</p>
</div>"""
        dorso_fn = f"""<div style="font-family: sans-serif;">
<pre style="background:#272822; color:#a6e22e; padding:10px; border-radius:5px;">
<code>{html.escape(fn.firma)}</code>
</pre>
<p>{html.escape(fn.descripcion or 'Sin descripción adicional.')}</p>
</div>"""
        cards.append({
            "frente": frente_fn.replace("\n", " ").strip(),
            "dorso": dorso_fn.replace("\n", " ").strip(),
            "tags": " ".join(tags_base + ["firmas_c"]),
        })

    return cards


def exportar_mazo_anki_tsv(
    ejercicios: List[Ejercicio],
    ruta_salida: Path,
) -> int:
    """Genera un archivo TSV formateado para importación directa en Anki."""
    todas_las_cards: List[dict] = []
    for ej in ejercicios:
        todas_las_cards.extend(ejercicio_a_flashcards(ej))

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8", newline="") as f:
        # Encabezado Anki para configuración de campos y HTML
        f.write("#separator:tab\n")
        f.write("#html:true\n")
        f.write("#tags column:3\n")

        writer = csv.writer(f, delimiter="\t")
        for card in todas_las_cards:
            writer.writerow([card["frente"], card["dorso"], card["tags"]])

    return len(todas_las_cards)
