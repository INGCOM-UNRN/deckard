"""Mejoras QoL (grupo A): init-tests, to-md, from-md, export-web, sanitizers, acsl-tests, export-anki, rubric, init-io-files, select-prereqs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.table import Table
import typer

from deckard.core.bank import (
    buscar_ejercicios,
    cargar_ejercicio,
    listar_ejercicios,
)
from deckard.core.guides import (
    cargar_guia_con_ejercicios,
    resolver_ruta_guia,
)

from deckard.cli._shared import (
    app,
    console,
    _resolver_dir_ejercicio,
)

# ---------------------------------------------------------------------------
# Nuevas Mejoras QoL: init-tests, to-md, from-md, export-web, sanitizers,
# acsl-tests, anki, rubric, io-files, select-prereqs
# ---------------------------------------------------------------------------



@app.command("init-tests")
def cmd_init_tests(
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio o ruta al directorio del ejercicio."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    framework: str = typer.Option("p1_test", "--framework", "-f", help="Framework de aserciones: 'p1_test' o 'assert'."),
    force: bool = typer.Option(False, "--force", help="Sobrescribir archivos existentes."),
) -> None:
    """Genera plantillas de tests unitarios embebidas en C utilizando p1_test o assert."""
    from deckard.core.init_tests import inicializar_tests_ejercicio
    dir_ej = _resolver_dir_ejercicio(ejercicio_id, banco)
    test_file = inicializar_tests_ejercicio(dir_ej, framework=framework, sobrescribir=force)
    console.print(f"[bold green]✓ Tests ({framework}) generados en:[/bold green] [cyan]{test_file}[/cyan]")


@app.command("to-md")
def cmd_to_md(
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio o ruta."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Ruta de salida del archivo .md interactivo."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Convierte un ejercicio estructurado en un único Markdown interactivo con YAML frontmatter."""
    from deckard.core.markdown_sync import exportar_ejercicio_md_interactivo
    dir_ej = _resolver_dir_ejercicio(ejercicio_id, banco)
    out = exportar_ejercicio_md_interactivo(dir_ej, salida)
    console.print(f"[bold green]✓ Ejercicio exportado a Markdown interactivo:[/bold green] [cyan]{out}[/cyan]")


@app.command("from-md")
def cmd_from_md(
    archivo_md: Path = typer.Argument(..., help="Ruta al archivo Markdown interactivo con frontmatter."),
    destino: Path = typer.Option(Path("banco"), "--destino", "-d", help="Directorio destino del banco."),
    force: bool = typer.Option(False, "--force", help="Sobrescribir directorio si ya existe."),
) -> None:
    """Importa un Markdown interactivo y reconstruye la estructura canónica de Deckard."""
    from deckard.core.markdown_sync import importar_ejercicio_desde_md
    if not archivo_md.is_file():
        console.print(f"[bold red]Archivo Markdown inexistente:[/bold red] {archivo_md}")
        raise typer.Exit(code=1)
    res = importar_ejercicio_desde_md(archivo_md, destino, sobrescribir=force)
    console.print(f"[bold green]✓ Ejercicio importado exitosamente en:[/bold green] [cyan]{res}[/cyan]")


@app.command("export-web")
def cmd_export_web(
    target: str = typer.Argument(..., help="ID de ejercicio, 'all' o ruta a archivo de guía YAML."),
    salida: Path = typer.Option(Path("dist/web"), "--salida", "-o", help="Directorio destino del sitio web."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    myst: bool = typer.Option(False, "--myst", help="Generar formato MyST Markdown en lugar de HTML."),
) -> None:
    """Genera páginas Web estáticas o MyST Markdown con soluciones desplegables."""
    from deckard.core.web_export import exportar_web_estatica

    ejercicios = []
    titulo = "Guía de Ejercicios Prácticos"

    p_guia = resolver_ruta_guia(Path(target)) if Path(target).exists() or target.endswith(".yaml") else None
    if p_guia and p_guia.is_file():
        info = cargar_guia_con_ejercicios(p_guia, banco)
        ejercicios = info.ejercicios
        titulo = info.guia.nombre or p_guia.stem
    elif target.lower() == "all":
        ejercicios = listar_ejercicios(banco)
    else:
        dir_ej = _resolver_dir_ejercicio(target, banco)
        ejercicios = [cargar_ejercicio(dir_ej)]
        titulo = ejercicios[0].titulo

    if not ejercicios:
        console.print("[bold red]No se encontraron ejercicios para exportar a web.[/bold red]")
        raise typer.Exit(code=1)

    res = exportar_web_estatica(ejercicios, salida, titulo_guia=titulo, formato_myst=myst)
    fmt = "MyST Markdown" if myst else "HTML Estático"
    console.print(f"[bold green]✓ Sitio ({fmt}) generado en:[/bold green] [cyan]{res}[/cyan]")


@app.command("audit-sanitizers")
@app.command("sanitizers")
def cmd_audit_sanitizers(
    target: str = typer.Argument(..., help="ID de ejercicio o directorio."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Audita la solución modelo contra fugas de memoria (ASan) y comportamientos indefinidos (UBSan)."""
    import json as _json
    import shutil as _shutil
    import subprocess as _subprocess

    from deckard.core.sanitizer_audit import ResultadoSanitizer, auditar_solucion_sanitizers
    dir_ej = _resolver_dir_ejercicio(target, banco)
    console.print("[yellow]Aviso:[/yellow] `deckard sanitizers` pasa a tetsuo (`tetsuo check solucion.c`), "
                  "el dueño de los sanitizers (N-ECO-12); este comando se va a retirar.")
    tetsuo = _shutil.which("tetsuo")
    solucion = dir_ej / "solucion.c"
    if tetsuo and solucion.is_file():
        proc = _subprocess.run([tetsuo, "check", str(solucion), "--json"], capture_output=True, text=True)
        try:
            datos = _json.loads(proc.stdout)
        except ValueError:
            datos = None
        # Sin instrumentar (no hay libasan, o la solución no compila sola) tetsuo no dice nada de la
        # solución: se usa la auditoría propia, que sabe compilar el ejercicio con su main de prueba.
        if datos is not None and datos.get("instrumented") is not False:
            titulos = [d.get("title_es", "") for d in datos.get("diagnoses", [])]
            res = ResultadoSanitizer(
                ejercicio=dir_ej.name, ok=bool(datos.get("ok")),
                leak_detected=any(d.get("error_tag") == "memory-leak" for d in datos.get("diagnoses", [])),
                ub_detected=any(d.get("sanitizer_type") == "UndefinedBehaviorSanitizer" for d in datos.get("diagnoses", [])),
                detalle="tetsuo: sin violaciones" if datos.get("ok") else ("tetsuo: " + "; ".join(titulos) if titulos
                                                                           else datos.get("raw_output", "")[:300]))
        else:
            res = auditar_solucion_sanitizers(dir_ej)
    else:
        res = auditar_solucion_sanitizers(dir_ej)
    if res.ok:
        console.print(f"[bold green]{res.marca} {res.ejercicio}:[/bold green] {res.detalle}")
    else:
        console.print(f"[bold red]{res.marca} {res.ejercicio}:[/bold red] {res.detalle}")
        raise typer.Exit(code=1)


@app.command("acsl-tests")
def cmd_acsl_tests(
    ejercicio_id: str = typer.Argument(..., help="ID de ejercicio o directorio."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    apply: bool = typer.Option(False, "--apply", "-a", help="Guardar los tests sintetizados en ejercicio.yaml."),
) -> None:
    """Sintetiza casos de prueba a partir de contratos formales ACSL (requires/ensures)."""
    from deckard.core.acsl_synth import sintetizar_tests_de_acsl, actualizar_ejercicio_con_tests_acsl
    dir_ej = _resolver_dir_ejercicio(ejercicio_id, banco)
    ej = cargar_ejercicio(dir_ej)
    tests = sintetizar_tests_de_acsl(ej)
    if not tests:
        console.print(f"[yellow]No se encontraron contratos ACSL en la solución de '{ej.id}'.[/yellow]")
        return

    console.print(f"[bold cyan]Se sintetizaron {len(tests)} casos de prueba ACSL para '{ej.id}':[/bold cyan]")
    for t in tests:
        console.print(f"  • [bold]{t.nombre}[/bold] ({t.funcion}): {t.descripcion}")

    if apply:
        agregados = actualizar_ejercicio_con_tests_acsl(dir_ej)
        console.print(f"[bold green]✓ Se incorporaron {agregados} tests a ejercicio.yaml.[/bold green]")
    else:
        console.print("[dim]Ejecutá con --apply para agregarlos permanentemente al ejercicio.[/dim]")


@app.command("export-anki")
@app.command("anki")
def cmd_export_anki(
    target: str = typer.Argument(..., help="ID de ejercicio, 'all' o ruta a guía YAML."),
    salida: Path = typer.Option(Path("dist/flashcards.tsv"), "--salida", "-o", help="Ruta de exportación TSV."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Exporta ejercicios y firmas a tarjetas mnemotécnicas Anki / Flashcards en formato TSV."""
    from deckard.core.anki import exportar_mazo_anki_tsv

    ejercicios = []
    p_guia = resolver_ruta_guia(Path(target)) if Path(target).exists() or target.endswith(".yaml") else None
    if p_guia and p_guia.is_file():
        info = cargar_guia_con_ejercicios(p_guia, banco)
        ejercicios = info.ejercicios
    elif target.lower() == "all":
        ejercicios = listar_ejercicios(banco)
    else:
        dir_ej = _resolver_dir_ejercicio(target, banco)
        ejercicios = [cargar_ejercicio(dir_ej)]

    if not ejercicios:
        console.print("[bold red]No se encontraron ejercicios para generar flashcards Anki.[/bold red]")
        raise typer.Exit(code=1)

    n_cards = exportar_mazo_anki_tsv(ejercicios, salida)
    console.print(f"[bold green]✓ Se exportaron {n_cards} flashcards Anki en:[/bold green] [cyan]{salida}[/cyan]")


@app.command("rubric")
def cmd_rubric(
    target: str = typer.Argument(..., help="ID de ejercicio o ruta a guía YAML."),
    salida_md: Optional[Path] = typer.Option(None, "--md", help="Ruta para exportar rúbrica en Markdown."),
    salida_dredd: Optional[Path] = typer.Option(None, "--dredd", help="Ruta para exportar configuración JSON para Dredd."),
    pesos: Optional[str] = typer.Option(None, "--pesos", help="Ponderaciones clave=valor separadas por coma."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Calibra pesos de evaluación y genera especificaciones de rúbricas para Dredd y Markdown."""
    from deckard.core.rubric import calibrar_pesos_rubrica, generar_rubrica_markdown, exportar_rubrica_dredd_json

    pesos_dict = None
    if pesos:
        pesos_dict = {}
        for token in pesos.split(","):
            if "=" in token:
                k, v = token.split("=", 1)
                try:
                    pesos_dict[k.strip()] = float(v.strip())
                except ValueError:
                    pass

    ejercicios = []
    p_guia = resolver_ruta_guia(Path(target)) if Path(target).exists() or target.endswith(".yaml") else None
    if p_guia and p_guia.is_file():
        info = cargar_guia_con_ejercicios(p_guia, banco)
        ejercicios = info.ejercicios
    else:
        dir_ej = _resolver_dir_ejercicio(target, banco)
        ejercicios = [cargar_ejercicio(dir_ej)]

    if not ejercicios:
        console.print("[bold red]No se encontraron ejercicios.[/bold red]")
        raise typer.Exit(code=1)

    pesos_cal = calibrar_pesos_rubrica(pesos_dict)
    tabla = Table(title=f"Rúbrica Calibrada ({ejercicios[0].id if len(ejercicios) == 1 else 'Guía'})")
    tabla.add_column("Criterio", style="bold")
    tabla.add_column("Ponderación", justify="right", style="cyan")
    for crit, p in pesos_cal.items():
        tabla.add_row(crit.replace("_", " ").capitalize(), f"{p}%")
    console.print(tabla)

    if salida_md:
        md_text = "\n\n---\n\n".join(generar_rubrica_markdown(ej, pesos=pesos_cal) for ej in ejercicios)
        salida_md.parent.mkdir(parents=True, exist_ok=True)
        salida_md.write_text(md_text, encoding="utf-8")
        console.print(f"[bold green]✓ Rúbrica Markdown guardada en:[/bold green] [cyan]{salida_md}[/cyan]")

    if salida_dredd:
        exportar_rubrica_dredd_json(ejercicios, salida_dredd, pesos=pesos_cal)
        console.print(f"[bold green]✓ Configuración Dredd exportada en:[/bold green] [cyan]{salida_dredd}[/cyan]")


@app.command("init-io-files")
def cmd_init_io_files(
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio."),
    modo: str = typer.Option("binario", "--modo", "-m", help="Tipo de archivo: 'binario' o 'texto'/'csv'."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Inicializa plantillas y fixtures para ejercicios basados en flujos de archivos."""
    from deckard.core.io_files import scaffolding_ejercicio_archivos
    dir_ej = _resolver_dir_ejercicio(ejercicio_id, banco)
    scaffolding_ejercicio_archivos(dir_ej, modo=modo)
    console.print(f"[bold green]✓ Scaffolding de archivos ({modo}) generado en:[/bold green] [cyan]{dir_ej}[/cyan]")


@app.command("select-prereqs")
def cmd_select_prereqs(
    temas: str = typer.Argument(..., help="Temas dominados separados por coma (ej: 'variables,control_flujo,arreglos')."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    bloom_max: Optional[int] = typer.Option(None, "--bloom-max", help="Nivel máximo de Bloom."),
    topologico: bool = typer.Option(False, "--topologico", help="Listar en orden topológico estricto."),
) -> None:
    """Selecciona y filtra ejercicios del banco cuyos prerrequisitos temáticos estén satisfechos."""
    from deckard.core.deps import build_dependency_graph, ordenar_topologicamente, seleccionar_por_prerrequisitos
    todos = buscar_ejercicios(banco, recursivo=True)
    if not todos:
        console.print("[yellow]No se encontraron ejercicios en el banco.[/yellow]")
        return

    temas_list = [t.strip() for t in temas.split(",") if t.strip()]
    candidatos = seleccionar_por_prerrequisitos(todos, temas_conocidos=temas_list, max_bloom=bloom_max)

    if topologico and candidatos:
        cand_map = {ej.id: ej for ej in candidatos}
        cand_tuples = [(Path(), ej) for ej in candidatos]
        graph = build_dependency_graph(cand_tuples)
        orden = ordenar_topologicamente(graph)
        candidatos = [cand_map[oid] for oid in orden if oid in cand_map]

    tabla = Table(title=f"Ejercicios Habilitados por Prerrequisitos (Temas: {', '.join(temas_list)})")
    tabla.add_column("ID", style="bold")
    tabla.add_column("Título")
    tabla.add_column("Tema", style="cyan")
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Minutos", justify="right")

    for ej in candidatos:
        tabla.add_row(ej.id, ej.titulo, ej.tema, str(int(ej.bloom)), f"{ej.minutos_estimados} min")

    console.print(tabla)
    console.print(f"[bold green]Total elegibles:[/bold green] {len(candidatos)} ejercicios.")




