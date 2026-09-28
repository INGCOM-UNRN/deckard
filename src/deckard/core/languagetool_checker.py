"""Módulo de verificación y corrección ortográfica con LanguageTool en deckard — Delegado a myst-tools."""

from __future__ import annotations

from typing import List, Optional, Set, Tuple, Dict, Any

try:
    from myst_tools.languagetool_checker import (
        DEFAULT_LANGUAGETOOL_URL,
        DEFAULT_LANGUAGETOOL_PREMIUM_URL,
        LOCAL_LANGUAGETOOL_URL,
        PALABRAS_IGNORADAS_DEFAULT,
        LanguageToolIssue,
        enmascarar_enunciado,
        consultar_languagetool,
        analizar_texto_languagetool,
        aplicar_autofix_texto,
    )
except ImportError as error:  # sin el extra `languagetool` (myst-tools)
    raise ModuleNotFoundError(
        "La revisión con LanguageTool usa myst-tools, que no está instalado. Instalá deckard con el "
        "extra languagetool: uv tool install \"deckard[languagetool] @ git+https://github.com/INGCOM-UNRN/deckard\"",
        name="myst_tools",
    ) from error

from deckard.core.models import Ejercicio


def analizar_ejercicio_languagetool(
    ejercicio: Ejercicio,
    lang: str = "es-AR",
    server_url: Optional[str] = None,
    username: Optional[str] = None,
    api_key: Optional[str] = None,
    premium: bool = False,
    ignore_words: Optional[Set[str]] = None,
    ignore_rules: Optional[Set[str]] = None,
) -> List[LanguageToolIssue]:
    """Audita todos los campos textuales de un ejercicio con LanguageTool."""
    issues = []
    # 1. Título
    issues.extend(analizar_texto_languagetool(
        ejercicio.titulo,
        ejercicio_id=ejercicio.id,
        campo="titulo",
        lang=lang,
        server_url=server_url,
        username=username,
        api_key=api_key,
        premium=premium,
        ignore_words=ignore_words,
        ignore_rules=ignore_rules,
        custom_mask_fn=enmascarar_enunciado,
    ))
    # 2. Enunciado Markdown
    issues.extend(analizar_texto_languagetool(
        ejercicio.enunciado_md,
        ejercicio_id=ejercicio.id,
        campo="enunciado",
        lang=lang,
        server_url=server_url,
        username=username,
        api_key=api_key,
        premium=premium,
        ignore_words=ignore_words,
        ignore_rules=ignore_rules,
        custom_mask_fn=enmascarar_enunciado,
    ))
    # 3. Pistas
    for idx, pista in enumerate(ejercicio.pistas, start=1):
        issues.extend(analizar_texto_languagetool(
            pista,
            ejercicio_id=ejercicio.id,
            campo=f"pista_{idx}",
            lang=lang,
            server_url=server_url,
            username=username,
            api_key=api_key,
            premium=premium,
            ignore_words=ignore_words,
            ignore_rules=ignore_rules,
            custom_mask_fn=enmascarar_enunciado,
        ))
    return issues


def aplicar_autofix_ejercicio(ejercicio: Ejercicio, issues: List[LanguageToolIssue]) -> int:
    """Aplica correcciones ortográficas sobre los campos del ejercicio in-place."""
    total_cambios = 0
    issues_por_campo: Dict[str, List[LanguageToolIssue]] = {}
    for iss in issues:
        if iss.campo:
            issues_por_campo.setdefault(iss.campo, []).append(iss)

    if "titulo" in issues_por_campo:
        nuevo_tit, c = aplicar_autofix_texto(ejercicio.titulo, issues_por_campo["titulo"])
        if c > 0:
            ejercicio.titulo = nuevo_tit
            total_cambios += c

    if "enunciado" in issues_por_campo:
        nuevo_enun, c = aplicar_autofix_texto(ejercicio.enunciado_md, issues_por_campo["enunciado"])
        if c > 0:
            ejercicio.enunciado_md = nuevo_enun
            total_cambios += c

    for idx in range(len(ejercicio.pistas)):
        campo_pista = f"pista_{idx + 1}"
        if campo_pista in issues_por_campo:
            nueva_pista, c = aplicar_autofix_texto(ejercicio.pistas[idx], issues_por_campo[campo_pista])
            if c > 0:
                ejercicio.pistas[idx] = nueva_pista
                total_cambios += c

    return total_cambios


def generar_reporte_markdown_languagetool(issues: List[LanguageToolIssue]) -> str:
    """Genera sección de auditoría ortográfica en Markdown para los ejercicios."""
    lines = ["## Auditoría Ortográfica y Gramatical de Enunciados (LanguageTool)\n"]
    lines.append(f"- **Total de observaciones encontradas:** {len(issues)}\n")

    if not issues:
        lines.append("> [!TIP]\n> **Enunciados Impecables:** No se detectaron faltas de ortografía ni errores gramaticales en los ejercicios analizados.\n")
        return "\n".join(lines)

    lines.append("| Ejercicio | Campo | Línea:Col | Categoría | Regla | Palabra / Contexto | Sugerencia |")
    lines.append("| :--- | :--- | :---: | :--- | :---: | :--- | :--- |")
    for iss in issues:
        sug = ", ".join(f"`{r}`" for r in iss.replacements[:3]) if iss.replacements else "*Ninguna*"
        ctx = iss.context.replace("\n", " ").replace("|", "\\|")
        lines.append(f"| `{iss.ejercicio_id}` | `{iss.campo}` | {iss.line}:{iss.column} | {iss.category} | `{iss.rule_id}` | `{iss.original_word}` ({ctx[:35]}...) | {sug} |")
    lines.append("")
    return "\n".join(lines)
