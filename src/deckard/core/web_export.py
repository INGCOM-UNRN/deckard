"""Exportador a formato Web estático y MyST Markdown con soluciones y pistas desplegables."""

from __future__ import annotations

import html
from pathlib import Path
from typing import List, Optional

from deckard.core.models import Ejercicio


def renderizar_ejercicio_myst(ej: Ejercicio) -> str:
    """Renderiza un ejercicio en formato MyST Markdown con bloques desplegables."""
    partes = [
        f"# {ej.titulo}",
        "",
        f"```{{badge}} Bloom: {ej.bloom.name.capitalize()} (Nivel {int(ej.bloom)})\n:color: primary\n``` "
        f"```{{badge}} Tiempo estimado: {ej.minutos_estimados} min\n:color: secondary\n``` "
        f"```{{badge}} Tema: {ej.tema}\n:color: info\n```",
        "",
        "## Consigna",
        "",
        ej.enunciado_md.strip() if ej.enunciado_md else "_Sin consigna._",
        "",
    ]

    if ej.starter_code.strip():
        partes.extend([
            "## Código Inicial (Starter Code)",
            "",
            "```{code-block} c",
            ej.starter_code.strip(),
            "```",
            "",
        ])

    if ej.pistas:
        partes.extend([
            "## Pistas Didácticas",
            "",
            "````{tab-set}",
        ])
        for i, pista in enumerate(ej.pistas, 1):
            partes.extend([
                f"```{{tab-item}} Pista {i}",
                pista,
                "```",
            ])
        partes.extend([
            "````",
            "",
        ])

    if ej.solucion_c.strip():
        partes.extend([
            "## Solución Modelo",
            "",
            "```{dropdown} 💡 Ver Solución Canónica de Cátedra",
            ":color: warning",
            ":icon: check",
            "",
            "```{code-block} c",
            ej.solucion_c.strip(),
            "```",
            "```",
            "",
        ])

    return "\n".join(partes)


def renderizar_ejercicio_web_html(ej: Ejercicio) -> str:
    """Genera una página HTML autocontenida y estilizada con soluciones plegables."""
    bloom_colores = {
        1: "#28a745",
        2: "#17a2b8",
        3: "#007bff",
        4: "#fd7e14",
        5: "#dc3545",
    }
    bloom_color = bloom_colores.get(int(ej.bloom), "#6c757d")

    pistas_html = ""
    if ej.pistas:
        pistas_items = "".join(f"<li>{html.escape(p)}</li>" for p in ej.pistas)
        pistas_html = f"""
        <section class="pistas-box">
            <h3>💡 Pistas Progresivas</h3>
            <ol class="pistas-list">
                {pistas_items}
            </ol>
        </section>
        """

    solucion_html = ""
    if ej.solucion_c.strip():
        codigo_escapado = html.escape(ej.solucion_c.strip())
        solucion_html = f"""
        <details class="solucion-desplegable">
            <summary class="solucion-summary">🔍 Revelar Solución Canónica (Cátedra)</summary>
            <div class="solucion-content">
                <pre><code class="language-c">{codigo_escapado}</code></pre>
            </div>
        </details>
        """

    starter_html = ""
    if ej.starter_code.strip():
        sc_escapado = html.escape(ej.starter_code.strip())
        starter_html = f"""
        <section class="starter-box">
            <h3>📦 Código Inicial</h3>
            <pre><code class="language-c">{sc_escapado}</code></pre>
        </section>
        """

    enunciado_formateado = html.escape(ej.enunciado_md).replace("\n", "<br>")

    css = f"""
    :root {{
        --font-main: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        --bg-color: #f8f9fa;
        --card-bg: #ffffff;
        --border-color: #e9ecef;
        --text-color: #212529;
    }}
    body {{
        font-family: var(--font-main);
        background-color: var(--bg-color);
        color: var(--text-color);
        line-height: 1.6;
        padding: 2rem;
        max-width: 900px;
        margin: 0 auto;
    }}
    .ejercicio-card {{
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }}
    .badges {{
        display: flex;
        gap: 0.5rem;
        margin-bottom: 1rem;
    }}
    .badge {{
        padding: 0.25rem 0.6rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        color: #fff;
    }}
    .badge-bloom {{ background-color: {bloom_color}; }}
    .badge-tiempo {{ background-color: #6c757d; }}
    .badge-tema {{ background-color: #495057; }}
    pre {{
        background: #272822;
        color: #f8f8f2;
        padding: 1rem;
        border-radius: 6px;
        overflow-x: auto;
    }}
    .solucion-desplegable {{
        margin-top: 1.5rem;
        border: 1px solid #ffeeba;
        border-radius: 6px;
        background-color: #fff3cd;
        overflow: hidden;
    }}
    .solucion-summary {{
        padding: 0.8rem 1rem;
        cursor: pointer;
        font-weight: bold;
        color: #856404;
        user-select: none;
    }}
    .solucion-content {{
        padding: 1rem;
        background: #fff;
        border-top: 1px solid #ffeeba;
    }}
    .pistas-box {{
        background: #e7f5ff;
        border-left: 4px solid #1c7ed6;
        padding: 0.8rem 1.2rem;
        margin: 1.5rem 0;
        border-radius: 0 6px 6px 0;
    }}
    """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(ej.titulo)}</title>
    <style>{css}</style>
</head>
<body>
    <article class="ejercicio-card">
        <header>
            <div class="badges">
                <span class="badge badge-bloom">Bloom {int(ej.bloom)} ({ej.bloom.name})</span>
                <span class="badge badge-tiempo">⏱ {ej.minutos_estimados} min</span>
                <span class="badge badge-tema">🏷 {html.escape(ej.tema)}</span>
            </div>
            <h1>{html.escape(ej.titulo)}</h1>
        </header>

        <section class="consigna">
            <h3>📖 Consigna</h3>
            <p>{enunciado_formateado}</p>
        </section>

        {starter_html}
        {pistas_html}
        {solucion_html}
    </article>
</body>
</html>"""


def exportar_web_estatica(
    ejercicios: List[Ejercicio],
    dir_salida: Path,
    titulo_guia: str = "Guía de Ejercicios Prácticos",
    formato_myst: bool = False,
) -> Path:
    """Exporta una colección de ejercicios como un sitio estático HTML o MyST Markdown."""
    dir_salida.mkdir(parents=True, exist_ok=True)

    if formato_myst:
        # Generar archivos .myst.md y toc _toc.yml
        toc_entries = []
        for ej in ejercicios:
            archivo_ej = dir_salida / f"{ej.id}.md"
            archivo_ej.write_text(renderizar_ejercicio_myst(ej), encoding="utf-8")
            toc_entries.append(f"  - file: {ej.id}")

        toc_content = f"""format: jb-book
root: index
chapters:
""" + "\n".join(toc_entries) + "\n"
        (dir_salida / "_toc.yml").write_text(toc_content, encoding="utf-8")

        index_myst = f"""# {titulo_guia}

Bienvenido a la guía interactiva generada por **Deckard**.

```{{tableofcontents}}
```
"""
        (dir_salida / "index.md").write_text(index_myst, encoding="utf-8")
    else:
        # Generar sitio web HTML
        index_items = []
        for ej in ejercicios:
            ej_html_path = dir_salida / f"{ej.id}.html"
            ej_html_path.write_text(renderizar_ejercicio_web_html(ej), encoding="utf-8")
            index_items.append(
                f'<li><a href="{ej.id}.html"><strong>{html.escape(ej.titulo)}</strong></a> '
                f'<span style="color:#6c757d">({ej.tema} · B{int(ej.bloom)} · {ej.minutos_estimados} min)</span></li>'
            )

        index_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(titulo_guia)}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 2rem; max-width: 800px; margin: 0 auto; line-height: 1.6; background: #f8f9fa; color: #212529; }}
        .guia-box {{ background: #fff; padding: 2rem; border-radius: 8px; border: 1px solid #dee2e6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        h1 {{ border-bottom: 2px solid #007bff; padding-bottom: 0.5rem; }}
        ul {{ padding-left: 1.2rem; }}
        li {{ margin: 0.8rem 0; }}
        a {{ color: #007bff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <main class="guia-box">
        <h1>{html.escape(titulo_guia)}</h1>
        <p>Índice de ejercicios de la guía compilada por Deckard:</p>
        <ul>
            {"".join(index_items)}
        </ul>
    </main>
</body>
</html>"""
        (dir_salida / "index.html").write_text(index_html, encoding="utf-8")

    return dir_salida
