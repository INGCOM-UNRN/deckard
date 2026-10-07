"""Comandos de calidad y empaquetado adicionales: audit-guide, spellcheck, pack-zip, check-ambiguity, diagram, export-hints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from rich.panel import Panel
from rich.table import Table
import typer

from deckard.core.bank import (
    buscar_ejercicios,
    cargar_ejercicio,
    guardar_ejercicio,
    listar_ejercicios,
)
from deckard.core.guides import (
    cargar_guia_con_ejercicios,
)

from deckard.cli._shared import (
    app,
    console,
)

@app.command("audit-guide")
def cmd_audit_guide(
    guia: Path = typer.Argument(..., help="Ruta a la guía YAML a auditar."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Audita la completitud y calidad técnica de todos los ejercicios de una guía."""
    from deckard.core.audit_guide import auditar_completitud_guia

    if not guia.exists():
        console.print(f"[bold red]No se encontró la guía '{guia}'.[/bold red]")
        raise typer.Exit(code=1)

    datos, items = cargar_guia_con_ejercicios(guia, banco)
    ejercicios = [ej for _, ej in items if ej is not None]
    auditar_completitud_guia(ejercicios, None, console=console)


@app.command("spellcheck")
@app.command("grammar")
@app.command("languagetool")
def cmd_spellcheck(
    objetivo: Optional[str] = typer.Argument(
        None,
        help="ID de ejercicio, ruta a archivo .yaml o ruta a guía a revisar con LanguageTool (por defecto todo el banco).",
    ),
    banco: Path = typer.Option(
        Path("banco"),
        "--banco",
        "-b",
        help="Directorio raíz del banco de ejercicios.",
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        "-f",
        help="Aplica automáticamente las sugerencias de corrección ortográfica y gramatical.",
    ),
    lang: str = typer.Option(
        "es-AR",
        "--lang",
        "-l",
        help="Código de idioma para LanguageTool (ej: 'es-AR', 'es', 'en-US').",
    ),
    server: Optional[str] = typer.Option(
        None,
        "--server",
        "-s",
        help="URL del servidor LanguageTool (por defecto http://localhost:8081 y API pública).",
    ),
    username: Optional[str] = typer.Option(
        None,
        "--username",
        "-u",
        help="Usuario / correo de LanguageTool Premium.",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        "-k",
        help="API Key / Token de LanguageTool Premium.",
    ),
    premium: bool = typer.Option(
        False,
        "--premium",
        help="Fuerza el uso de la API LanguageTool Premium (https://api.languagetoolplus.com/v2/check).",
    ),
    ignore_rules: Optional[str] = typer.Option(
        None,
        "--ignore-rules",
        help="Reglas a ignorar separadas por comas (ej: 'MORFOLOGIK_RULE_ES,UPPERCASE_SENTENCE_START').",
    ),
    ignore_words: Optional[str] = typer.Option(
        None,
        "--ignore-words",
        help="Palabras personalizadas a ignorar separadas por comas.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emite salida estructurada en formato JSON.",
    ),
    output_md: Optional[Path] = typer.Option(
        None,
        "--md",
        "--output-md",
        "-o",
        help="Genera reporte en formato Markdown para el informe docente.",
    ),
) -> None:
    """Verifica y corrige ortografía y gramática en enunciados y pistas de ejercicios usando LanguageTool."""
    import json
    from deckard.core.guides import cargar_guia_con_ejercicios
    try:
        from deckard.core.languagetool_checker import (
            analizar_ejercicio_languagetool,
            aplicar_autofix_ejercicio,
            generar_reporte_markdown_languagetool,
        )
    except ModuleNotFoundError as error:
        console.print(f"[bold red]Error:[/bold red] {error}")
        raise typer.Exit(1) from error

    reglas_ign = set(r.strip() for r in ignore_rules.split(",") if r.strip()) if ignore_rules else None
    palabras_ign = set(w.strip() for w in ignore_words.split(",") if w.strip()) if ignore_words else None

    ejercicios_a_revisar = []
    if objetivo:
        obj_path = Path(objetivo)
        if obj_path.is_file() and obj_path.suffix in (".yaml", ".yml"):
            # Puede ser una guía o un ejercicio
            try:
                ej = cargar_ejercicio(obj_path)
                ejercicios_a_revisar.append(ej)
            except Exception:
                _, items = cargar_guia_con_ejercicios(obj_path, banco)
                ejercicios_a_revisar = [ej for _, ej in items if ej is not None]
        else:
            # Buscar por ID
            ej = cargar_ejercicio(banco / objetivo / "ejercicio.yaml")
            ejercicios_a_revisar.append(ej)
    else:
        # Todo el banco
        ejercicios_a_revisar = listar_ejercicios(banco)

    if not ejercicios_a_revisar:
        console.print("[yellow]No se encontraron ejercicios para analizar con LanguageTool.[/yellow]")
        raise typer.Exit(code=0)

    todos_los_issues = []
    total_arreglos = 0

    for ej in ejercicios_a_revisar:
        issues_ej = analizar_ejercicio_languagetool(
            ej,
            lang=lang,
            server_url=server,
            username=username,
            api_key=api_key,
            premium=premium,
            ignore_words=palabras_ign,
            ignore_rules=reglas_ign,
        )
        if fix and issues_ej:
            arreglos = aplicar_autofix_ejercicio(ej, issues_ej)
            if arreglos > 0:
                guardar_ejercicio(ej, banco / ej.id)
                total_arreglos += arreglos
        todos_los_issues.extend(issues_ej)

    if output_md:
        md_text = generar_reporte_markdown_languagetool(todos_los_issues)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(md_text, encoding="utf-8")
        console.print(f"[bold green]✓ Reporte Markdown generado en:[/bold green] [cyan]{output_md}[/cyan]")
        raise typer.Exit(code=0 if not todos_los_issues else 1)

    if json_output:
        res = {
            "total_ejercicios": len(ejercicios_a_revisar),
            "total_issues": len(todos_los_issues),
            "total_arreglos": total_arreglos,
            "issues": [i.to_dict() for i in todos_los_issues],
        }
        print(json.dumps(res, indent=2, ensure_ascii=False))
        raise typer.Exit(code=0 if not todos_los_issues else 1)

    if not todos_los_issues:
        console.print(Panel(
            f"[bold green]✓ Enunciados y Pistas Impecables[/bold green]\n"
            f"Se analizaron {len(ejercicios_a_revisar)} ejercicios sin faltas ortográficas ni gramaticales.",
            title="[bold green]LanguageTool Passed[/bold green]",
            border_style="green",
        ))
        raise typer.Exit(code=0)

    tabla = Table(title=f"⚠️ Observaciones de LanguageTool ({len(todos_los_issues)} encontradas)", border_style="yellow")
    tabla.add_column("Ejercicio", style="bold cyan")
    tabla.add_column("Campo", style="magenta")
    tabla.add_column("L:C", justify="center")
    tabla.add_column("Error / Contexto", style="white")
    tabla.add_column("Sugerencia", style="bold green")

    for iss in todos_los_issues:
        sug = ", ".join(iss.replacements[:2]) if iss.replacements else "[dim]—[/dim]"
        tabla.add_row(
            iss.ejercicio_id,
            iss.campo,
            f"{iss.line}:{iss.column}",
            f"[red]{iss.original_word}[/red] ({iss.context})",
            sug,
        )

    console.print(tabla)
    if fix:
        console.print(f"\n[bold green]✓ Se aplicaron {total_arreglos} correcciones automáticas en los archivos del banco.[/bold green]")
    else:
        console.print("\n[dim]Tip: Usá '--fix' para aplicar automáticamente las sugerencias.[/dim]")

    raise typer.Exit(code=1)


@app.command("pack-zip")
@app.command("export-zip")
def cmd_pack_zip(
    objetivo: str = typer.Argument(..., help="ID de ejercicio, ruta a ejercicio.yaml o guía .yaml."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Ruta de destino del archivo .zip."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    no_tests: bool = typer.Option(False, "--no-tests", help="Excluir archivos de prueba en el starter kit."),
    no_pistas: bool = typer.Option(False, "--no-pistas", help="Excluir pistas en el starter kit."),
) -> None:
    """Empaqueta un starter kit o guía completa en un archivo ZIP con clave de entrega (QoL 11)."""
    from deckard.core.starter_zip import empaquetar_starter_zip, empaquetar_guia_zip

    obj_path = Path(objetivo)
    if obj_path.exists():
        try:
            ej = cargar_ejercicio(obj_path)
            dest_zip, clave, sha_h = empaquetar_starter_zip(
                ej, out_zip=salida, incluir_tests=not no_tests, incluir_pistas=not no_pistas
            )
            console.print(Panel(
                f"[bold green]✓ Starter ZIP empaquetado exitosamente:[/bold green]\n\n"
                f"• **Archivo:** [cyan]{dest_zip}[/cyan]\n"
                f"• **Clave de Entrega:** [bold yellow]{clave}[/bold yellow]\n"
                f"• **Integridad SHA-256:** [dim]{sha_h}[/dim]",
                title=f"Starter Kit: {ej.id}",
                border_style="green",
            ))
            return
        except Exception:
            try:
                dest_zip, clave, tot = empaquetar_guia_zip(obj_path, banco, out_zip=salida)
                console.print(Panel(
                    f"[bold green]✓ Bundle de Guía empaquetado exitosamente:[/bold green]\n\n"
                    f"• **Archivo:** [cyan]{dest_zip}[/cyan]\n"
                    f"• **Clave Maestra:** [bold yellow]{clave}[/bold yellow]\n"
                    f"• **Ejercicios incluidos:** {tot}",
                    title=f"Bundle de Guía",
                    border_style="green",
                ))
                return
            except Exception:
                pass

    matches = buscar_ejercicios(banco, patron=objetivo, recursivo=True)
    if not matches:
        console.print(f"[bold red]No se encontró el ejercicio o guía '{objetivo}' en {banco}.[/bold red]")
        raise typer.Exit(code=1)

    dir_p, ej = matches[0]
    dest_zip, clave, sha_h = empaquetar_starter_zip(
        ej, out_zip=salida, incluir_tests=not no_tests, incluir_pistas=not no_pistas
    )
    console.print(Panel(
        f"[bold green]✓ Starter ZIP empaquetado exitosamente:[/bold green]\n\n"
        f"• **Archivo:** [cyan]{dest_zip}[/cyan]\n"
        f"• **Clave de Entrega:** [bold yellow]{clave}[/bold yellow]\n"
        f"• **Integridad SHA-256:** [dim]{sha_h}[/dim]",
        title=f"Starter Kit: {ej.id}",
        border_style="green",
    ))


@app.command("check-ambiguity")
@app.command("audit-statements")
def cmd_check_ambiguity(
    objetivo: Optional[str] = typer.Argument(None, help="ID de ejercicio, ruta a archivo o guía a auditar."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    json_output: bool = typer.Option(False, "--json", help="Emitir reporte estructurado en formato JSON."),
    output_md: Optional[Path] = typer.Option(None, "--md", "--output-md", "-o", help="Generar reporte en Markdown."),
) -> None:
    """Audita ambigüedades, términos vagos y calidad pedagógica en los enunciados (QoL 12)."""
    from deckard.core.ambiguity_checker import auditar_banco_ambiguedades
    from deckard.core.guides import cargar_guia_con_ejercicios

    ejercicios = []
    if objetivo:
        obj_path = Path(objetivo)
        if obj_path.exists():
            try:
                ej = cargar_ejercicio(obj_path)
                ejercicios.append(ej)
            except Exception:
                try:
                    _, items = cargar_guia_con_ejercicios(obj_path, banco)
                    ejercicios = [ej for _, ej in items if ej is not None]
                except Exception:
                    pass
        if not ejercicios:
            matches = buscar_ejercicios(banco, patron=objetivo, recursivo=True)
            if matches:
                ejercicios = [matches[0][1]]
    else:
        ejercicios = listar_ejercicios(banco)

    if not ejercicios:
        console.print("[yellow]No se encontraron ejercicios para auditar.[/yellow]")
        raise typer.Exit(code=0)

    reporte = auditar_banco_ambiguedades(ejercicios)

    if output_md:
        lines = [
            "# Auditoría de Calidad y Ambigüedad de Enunciados (Deckard)\n",
            f"- **Ejercicios auditados:** {reporte['total_ejercicios']}",
            f"- **Ejercicios con observaciones:** {reporte['ejercicios_con_observaciones']}",
            f"- **Total de observaciones:** {reporte['total_observaciones']}\n",
        ]
        if reporte["total_observaciones"] == 0:
            lines.append("> [!TIP]\n> Todos los enunciados presentan formulaciones precisas y sin ambigüedades.")
        else:
            lines.append("| Ejercicio | Categoría | Severidad | Mensaje | Sugerencia |")
            lines.append("| :--- | :--- | :---: | :--- | :--- |")
            for obs in reporte["observaciones"]:
                lines.append(f"| `{obs.ejercicio_id}` | {obs.categoria} | `{obs.severidad}` | {obs.mensaje} | {obs.sugerencia} |")
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text("\n".join(lines), encoding="utf-8")
        console.print(f"[bold green]✓ Reporte Markdown generado en:[/bold green] [cyan]{output_md}[/cyan]")
        raise typer.Exit(code=0 if reporte["total_observaciones"] == 0 else 1)

    if json_output:
        res = {
            "total_ejercicios": reporte["total_ejercicios"],
            "ejercicios_con_observaciones": reporte["ejercicios_con_observaciones"],
            "total_observaciones": reporte["total_observaciones"],
            "observaciones": [obs.to_dict() for obs in reporte["observaciones"]],
        }
        print(json.dumps(res, indent=2, ensure_ascii=False))
        raise typer.Exit(code=0 if reporte["total_observaciones"] == 0 else 1)

    if reporte["total_observaciones"] == 0:
        console.print(Panel(
            f"[bold green]✓ Enunciados Impecables[/bold green]\n"
            f"Se auditaron {len(ejercicios)} ejercicios sin ambigüedades ni términos vagos detectados.",
            title="[bold green]Ambiguity Check OK[/bold green]",
            border_style="green",
        ))
        raise typer.Exit(code=0)

    tabla = Table(title=f"⚠️ Auditoría de Enunciados ({reporte['total_observaciones']} observaciones)", border_style="yellow")
    tabla.add_column("Ejercicio", style="bold cyan")
    tabla.add_column("Categoría", style="magenta")
    tabla.add_column("Severidad", justify="center")
    tabla.add_column("Problema", style="white")
    tabla.add_column("Sugerencia Pedagógica", style="dim green")

    for obs in reporte["observaciones"]:
        color_sev = "red" if obs.severidad == "alta" else ("yellow" if obs.severidad == "media" else "cyan")
        tabla.add_row(
            obs.ejercicio_id,
            obs.categoria,
            f"[{color_sev}]{obs.severidad.upper()}[/{color_sev}]",
            obs.mensaje,
            obs.sugerencia,
        )

    console.print(tabla)
    raise typer.Exit(code=1)


@app.command("diagram")
@app.command("ascii-diagram")
@app.command("diagram-ascii")
def cmd_diagram(
    tipo: str = typer.Argument("lista", help="Tipo de estructura: 'lista', 'lista-doble', 'arbol', 'matriz', 'pila', 'cola', 'punteros'."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Guardar el diagrama en un archivo."),
    formato: str = typer.Option("ascii", "--formato", "-F", help="Formato del diagrama: 'ascii', 'mermaid', 'plantuml'."),
    filas: int = typer.Option(3, "--filas", "-f", help="Filas para matrices o punteros."),
    columnas: int = typer.Option(3, "--columnas", "-c", help="Columnas para matrices."),
) -> None:
    """Genera diagramas y esquemas de estructuras de datos en formato ASCII, Mermaid o PlantUML para enunciados (QoL 14)."""
    from deckard.core.diagrams import (
        generar_diagrama_lista_enlazada,
        generar_diagrama_lista_doble,
        generar_diagrama_arbol_binario,
        generar_diagrama_pila,
        generar_diagrama_cola,
        generar_diagrama_matriz,
        generar_diagrama_punteros_dobles,
    )

    t = tipo.lower().strip().replace("-", "_")
    fmt = formato.lower().strip()

    if t in ("lista", "lista_simple", "linked_list"):
        diag = generar_diagrama_lista_enlazada(formato=fmt)
    elif t in ("lista_doble", "doubly_linked_list"):
        diag = generar_diagrama_lista_doble(formato=fmt)
    elif t in ("arbol", "tree", "bst"):
        diag = generar_diagrama_arbol_binario(formato=fmt)
    elif t in ("pila", "stack"):
        diag = generar_diagrama_pila(formato=fmt)
    elif t in ("cola", "queue"):
        diag = generar_diagrama_cola(formato=fmt)
    elif t in ("matriz", "matrix"):
        diag = generar_diagrama_matriz(filas=filas, columnas=columnas, formato=fmt)
    elif t in ("punteros", "punteros_dobles", "double_pointers"):
        diag = generar_diagrama_punteros_dobles(filas=filas, formato=fmt)
    else:
        diag = generar_diagrama_lista_enlazada(formato=fmt)

    if salida:
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(diag, encoding="utf-8")
        console.print(f"[bold green]✓ Diagrama ({fmt}) guardado en:[/bold green] [cyan]{salida}[/cyan]")
    else:
        print(diag)


@app.command("export-hints")
@app.command("hints")
def cmd_export_hints(
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio o ruta a ejercicio.yaml."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Ruta de salida (por defecto stdout o PISTAS.md)."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    ofuscar: bool = typer.Option(False, "--ofuscar", "--rot13", help="Ofuscar las pistas con ROT13 para prevenir spoilers."),
    formato_c: bool = typer.Option(False, "--c-comments", "-c", help="Generar en formato de bloque de comentarios C."),
    nivel_max: Optional[int] = typer.Option(None, "--nivel", "-n", help="Nivel máximo de pistas a exportar."),
) -> None:
    """Exporta o genera pistas escalonadas (Hints) progresivas para un ejercicio (QoL 15)."""
    from deckard.core.hints import generar_archivo_pistas_md, formatear_pistas_comentarios_c

    ej = None
    obj_path = Path(ejercicio_id)
    if obj_path.exists():
        try:
            ej = cargar_ejercicio(obj_path)
        except Exception:
            pass

    if not ej:
        matches = buscar_ejercicios(banco, patron=ejercicio_id, recursivo=True)
        if matches:
            ej = matches[0][1]

    if not ej:
        console.print(f"[bold red]No se encontró el ejercicio '{ejercicio_id}' en {banco}.[/bold red]")
        raise typer.Exit(code=1)

    if formato_c:
        contenido = formatear_pistas_comentarios_c(ej.pistas, nivel_maximo=nivel_max, ofuscar=ofuscar)
    else:
        contenido = generar_archivo_pistas_md(ej, ofuscar=ofuscar)

    if salida:
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(contenido, encoding="utf-8")
        console.print(f"[bold green]✓ Pistas generadas en:[/bold green] [cyan]{salida}[/cyan]")
    else:
        print(contenido)

