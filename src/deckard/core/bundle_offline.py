"""Empaquetador de bundles portables offline con visor Web incorporado (QoL 18)."""

from __future__ import annotations

import html
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional
import zipfile

from deckard.core.models import Ejercicio


CSS_OFFLINE = """
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.6;
    color: #24292e;
    max-width: 960px;
    margin: 0 auto;
    padding: 24px;
    background-color: #f6f8fa;
}
.header {
    background: #24292e;
    color: white;
    padding: 20px 24px;
    border-radius: 8px;
    margin-bottom: 24px;
}
.header h1 { margin: 0; font-size: 24px; }
.header p { margin: 8px 0 0 0; color: #d1d5da; font-size: 14px; }
.card {
    background: white;
    border: 1px solid #e1e4e8;
    border-radius: 6px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.card h2 {
    margin-top: 0;
    color: #0366d6;
    font-size: 20px;
    border-bottom: 1px solid #eaecef;
    padding-bottom: 8px;
}
.badge {
    display: inline-block;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 12px;
    background-color: #e1e4e8;
    color: #24292e;
    margin-right: 6px;
}
.badge-bloom { background-color: #ffd33d; color: #24292e; }
.badge-time { background-color: #28a745; color: white; }
pre {
    background-color: #f6f8fa;
    border: 1px solid #e1e4e8;
    border-radius: 6px;
    padding: 16px;
    overflow-x: auto;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 13px;
}
details {
    margin-top: 12px;
    background: #fafbfc;
    border: 1px solid #e1e4e8;
    border-radius: 6px;
    padding: 8px 12px;
}
summary {
    font-weight: bold;
    cursor: pointer;
    color: #0366d6;
}
"""


def _generar_index_html(ejercicios: List[Ejercicio], titulo: str, incluir_soluciones: bool = False) -> str:
    cards = []
    for ej in ejercicios:
        cuerpo_consigna = html.escape(ej.enunciado_md).replace("\n", "<br/>")
        starter_bloque = f"<pre><code>{html.escape(ej.starter)}</code></pre>" if ej.starter else ""
        solucion_bloque = ""
        if incluir_soluciones and ej.solucion:
            solucion_bloque = f"""
            <details>
                <summary>💡 Solución de Referencia (Docente)</summary>
                <pre><code>{html.escape(ej.solucion)}</code></pre>
            </details>
            """

        pistas_bloque = ""
        if ej.pistas:
            pistas_html = "".join(f"<li>{html.escape(p)}</li>" for p in ej.pistas)
            pistas_bloque = f"""
            <details>
                <summary>🔍 Pistas Didácticas</summary>
                <ul>{pistas_html}</ul>
            </details>
            """

        card = f"""
        <div class="card" id="{html.escape(ej.id)}">
            <h2>[{html.escape(ej.id)}] {html.escape(ej.titulo)}</h2>
            <div>
                <span class="badge">Tema: {html.escape(ej.tema)}</span>
                <span class="badge badge-bloom">Bloom: {int(ej.bloom)}</span>
                <span class="badge badge-time">⏱ {ej.minutos_estimados} min</span>
            </div>
            <div style="margin-top: 14px;">
                <p>{cuerpo_consigna}</p>
            </div>
            {starter_bloque}
            {pistas_bloque}
            {solucion_bloque}
        </div>
        """
        cards.append(card)

    cards_html = "\n".join(cards)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(titulo)} - Visor Offline</title>
    <style>
    {CSS_OFFLINE}
    </style>
</head>
<body>
    <div class="header">
        <h1>{html.escape(titulo)}</h1>
        <p>Visor offline interactivo para laboratorios sin conexión | Total de ejercicios: {len(ejercicios)}</p>
    </div>
    <div class="container">
        {cards_html}
    </div>
</body>
</html>
"""


def empaquetar_bundle_offline(
    ejercicios: List[Ejercicio],
    ruta_zip: Path,
    titulo: str = "Guía de Ejercicios Offline",
    incluir_soluciones: bool = False,
) -> Path:
    """Crea un archivo ZIP autocontenido con el visor web HTML y los archivos de cada ejercicio."""
    ruta_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ruta_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. index.html con visor completo
        html_content = _generar_index_html(ejercicios, titulo, incluir_soluciones=incluir_soluciones)
        zf.writestr("index.html", html_content)
        zf.writestr("estilos.css", CSS_OFFLINE)

        # 2. Carpeta por cada ejercicio con sus fuentes
        for ej in ejercicios:
            prefijo = f"ejercicios/{ej.id}"
            zf.writestr(f"{prefijo}/consigna.md", f"# {ej.titulo}\n\n{ej.enunciado_md}")
            if ej.starter:
                zf.writestr(f"{prefijo}/main.c", ej.starter)
            if incluir_soluciones and ej.solucion:
                zf.writestr(f"{prefijo}/solucion.c", ej.solucion)

            # Incluir archivos adicionales del ejercicio si existen
            for nombre_rel, contenido_bin in ej.archivos.items():
                if not nombre_rel.startswith("__"):
                    zf.writestr(f"{prefijo}/{nombre_rel}", contenido_bin)

    return ruta_zip
