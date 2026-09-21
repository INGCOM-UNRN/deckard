"""Sub-app `improve`: mejora y curaduría pedagógica de consignas con OpenCode."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.syntax import Syntax
from rich.table import Table
import typer

from deckard.core.bank import (
    buscar_ejercicios,
    cargar_ejercicio,
)

from deckard.cli._shared import (
    console,
    improve_app,
)

# ---------------------------------------------------------------------------
# Mejora de Consignas y Bancos con OpenCode (improve / ai)
# ---------------------------------------------------------------------------

def _ejecutar_mejora_cli(
    aspecto,
    target: Optional[str] = None,
    banco: Path = Path("."),
    prompt: Optional[str] = None,
    prompt_file: Optional[Path] = None,
    model: str = "opencode-go/qwen3.8-max",
    apply: bool = False,
    diff: bool = True,
    show_prompt: bool = False,
    sandbox: bool = True,
    all_exercises: bool = False,
    patron: Optional[str] = None,
    tema: Optional[str] = None,
    bloom: Optional[int] = None,
    tag: Optional[str] = None,
    output: Optional[Path] = None,
) -> None:
    from deckard.core.bank import ARCHIVO_EJERCICIO
    from deckard.core.improve import (
        construir_prompt_ejercicio,
        construir_prompt_gift,
        mejorar_ejercicio,
        mejorar_archivo_gift,
    )

    # Caso 1: Archivo GIFT de preguntas (Moodle)
    if target and (target.lower().endswith(".gift") or (Path(target).is_file() and Path(target).suffix.lower() == ".gift")):
        path_gift = Path(target)
        if not path_gift.is_file():
            console.print(f"[bold red]No se encontró el archivo GIFT '{target}'.[/bold red]")
            raise typer.Exit(code=1)

        if show_prompt:
            p_txt = construir_prompt_gift(path_gift.read_text(encoding="utf-8"), aspecto, prompt, prompt_file)
            console.print(Panel(p_txt, title=f"Prompt generado para {path_gift.name} [{aspecto.value}]", border_style="cyan"))
            return

        with console.status(f"[cyan]Curando banco GIFT '{path_gift.name}' con OpenCode ({model})...[/cyan]"):
            try:
                cambio, diff_txt, nuevo_contenido = mejorar_archivo_gift(
                    ruta_gift=path_gift,
                    aspecto=aspecto,
                    custom_prompt=prompt,
                    prompt_file=prompt_file,
                    modelo=model,
                    usar_sandbox=sandbox,
                    aplicar=apply,
                )
            except Exception as e:
                console.print(f"[bold red]Error al invocar OpenCode:[/bold red] {e}")
                raise typer.Exit(code=1)

        if diff and diff_txt:
            console.print(Syntax(diff_txt, "diff", theme="monokai", line_numbers=True))

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(nuevo_contenido, encoding="utf-8")
            console.print(f"[bold green]✓ Banco GIFT mejorado guardado en:[/bold green] [cyan]{output}[/cyan]")
        elif apply:
            console.print(f"[bold green]✓ Banco GIFT '{path_gift.name}' actualizado en disco.[/bold green]")
        else:
            console.print(f"[yellow]Simulación completada. Usá --apply para escribir cambios en {path_gift.name}.[/yellow]")
        return

    # Caso 2: Verificar si es un ejercicio individual
    dir_candidato: Optional[Path] = None
    if target and not all_exercises:
        p_candidato = Path(target)
        if (p_candidato / ARCHIVO_EJERCICIO).is_file():
            dir_candidato = p_candidato
        elif p_candidato.is_file() and p_candidato.name == ARCHIVO_EJERCICIO:
            dir_candidato = p_candidato.parent
        else:
            # Buscar en banco por id exacto o primer match
            candidatos = buscar_ejercicios(banco, patron=target)
            if candidatos:
                dir_candidato = candidatos[0][0]

    if dir_candidato is not None:
        # Mejora de ejercicio individual
        ej = cargar_ejercicio(dir_candidato)
        if show_prompt:
            p_txt = construir_prompt_ejercicio(ej, aspecto, prompt, prompt_file)
            console.print(Panel(p_txt, title=f"Prompt generado para '{ej.id}' [{aspecto.value}]", border_style="cyan"))
            return

        with console.status(f"[cyan]Mejorando aspecto '{aspecto.value}' en '{ej.id}' con OpenCode ({model})...[/cyan]"):
            try:
                res = mejorar_ejercicio(
                    dir_ejercicio=dir_candidato,
                    aspecto=aspecto,
                    custom_prompt=prompt,
                    prompt_file=prompt_file,
                    modelo=model,
                    usar_sandbox=sandbox,
                    aplicar=apply,
                )
            except Exception as e:
                console.print(f"[bold red]Error al ejecutar OpenCode:[/bold red] {e}")
                raise typer.Exit(code=1)

        if diff and res.diff:
            console.print(Syntax(res.diff, "diff", theme="monokai", line_numbers=True))

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(res.contenido_nuevo, encoding="utf-8")
            console.print(f"[bold green]✓ Contenido mejorado exportado a:[/bold green] [cyan]{output}[/cyan]")
        elif apply:
            console.print(f"[bold green]✓ {res.resumen}[/bold green]")
        else:
            console.print(f"[yellow]{res.resumen}[/yellow]")
        return

    # Caso 3: Banco completo o lote de ejercicios
    banco_dir = Path(target) if (target and Path(target).is_dir()) else Path(banco)
    filtro_patron = patron
    if target and ("*" in target or "?" in target):
        filtro_patron = target

    ejercicios_encontrados = buscar_ejercicios(
        banco=banco_dir,
        patron=filtro_patron,
        tema=tema,
        bloom=bloom,
        tag=tag,
    )

    if not ejercicios_encontrados:
        console.print(f"[bold yellow]No se encontraron ejercicios en '{banco_dir}' que coincidan con los filtros.[/bold yellow]")
        raise typer.Exit(code=0)

    if show_prompt:
        primer_ej = ejercicios_encontrados[0][1]
        p_txt = construir_prompt_ejercicio(primer_ej, aspecto, prompt, prompt_file)
        console.print(Panel(p_txt, title=f"Prompt de muestra para primer ejercicio '{primer_ej.id}' [{aspecto.value}]", border_style="cyan"))
        return

    console.print(f"[bold cyan]Iniciando mejora de aspecto '{aspecto.value}' sobre {len(ejercicios_encontrados)} ejercicios con {model}...[/bold cyan]")

    tabla = Table(title=f"Resultados de Mejora con OpenCode ({aspecto.value})")
    tabla.add_column("Ejercicio ID", style="bold")
    tabla.add_column("Tema", style="cyan")
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Cambios", justify="center")
    tabla.add_column("Estado")

    modificados = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Mejorando {aspecto.value}...", total=len(ejercicios_encontrados))
        for dir_ej, ej in ejercicios_encontrados:
            progress.update(task, description=f"Procesando {ej.id}...")
            try:
                res = mejorar_ejercicio(
                    dir_ejercicio=dir_ej,
                    aspecto=aspecto,
                    custom_prompt=prompt,
                    prompt_file=prompt_file,
                    modelo=model,
                    usar_sandbox=sandbox,
                    aplicar=apply,
                )
                if res.cambio_realizado:
                    modificados += 1
                    estado_str = "[bold green]Aplicado[/bold green]" if apply else "[yellow]Propuesto[/yellow]"
                    tabla.add_row(ej.id, ej.tema, str(ej.bloom), "[green]Sí[/green]", estado_str)
                    if diff and res.diff and not apply:
                        console.print(f"\n[bold underline]Diff para {ej.id}:[/bold underline]")
                        console.print(Syntax(res.diff, "diff", theme="monokai", line_numbers=True))
                else:
                    tabla.add_row(ej.id, ej.tema, str(ej.bloom), "[dim]No[/dim]", "[dim]Sin cambios[/dim]")
            except Exception as e:
                tabla.add_row(ej.id, ej.tema, str(ej.bloom), "[red]Error[/red]", f"[red]{str(e)[:35]}[/red]")
            progress.advance(task)

    console.print(tabla)
    if apply:
        console.print(f"\n[bold green]✓ Se aplicaron mejoras sobre {modificados} de {len(ejercicios_encontrados)} ejercicios.[/bold green]")
    else:
        console.print(f"\n[yellow]Simulación finalizada. {modificados} ejercicios tienen mejoras propuestas. Ejecutá con --apply para guardarlas.[/yellow]")


@improve_app.command("clarity")
def improve_clarity(
    target: Optional[str] = typer.Argument(None, help="ID de ejercicio, ruta a directorio, banco o archivo .gift."),
    banco: Path = typer.Option(Path("."), "--banco", "-b", help="Directorio raíz del banco de ejercicios."),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Instrucciones adicionales para ajustar el prompt."),
    prompt_file: Optional[Path] = typer.Option(None, "--prompt-file", "-P", help="Archivo con directivas personalizadas."),
    model: str = typer.Option("opencode-go/qwen3.8-max", "--model", "-m", help="Modelo de OpenCode a utilizar."),
    apply: bool = typer.Option(False, "--apply", "-a", help="Aplica y guarda los cambios en los archivos."),
    diff: bool = typer.Option(True, "--diff/--no-diff", "-d", help="Muestra diff unificado de los cambios."),
    show_prompt: bool = typer.Option(False, "--show-prompt", help="Imprime el prompt generado sin invocar a OpenCode."),
    sandbox: bool = typer.Option(True, "--sandbox/--no-sandbox", help="Usa ejecución aislada bwrap si está disponible."),
    all_exercises: bool = typer.Option(False, "--all", help="Procesar todos los ejercicios del banco."),
    patron: Optional[str] = typer.Option(None, "--patron", help="Filtro comodín para IDs de ejercicios."),
    tema: Optional[str] = typer.Option(None, "--tema", help="Filtra por tema pedagógico."),
    bloom: Optional[int] = typer.Option(None, "--bloom", help="Filtra por nivel de Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtra por etiqueta."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de exportación alternativa."),
) -> None:
    """Mejora la claridad, concisión y desambiguación del enunciado con verbos operativos de Bloom."""
    from deckard.core.improve import AspectoMejora
    _ejecutar_mejora_cli(
        aspecto=AspectoMejora.CLARITY,
        target=target, banco=banco, prompt=prompt, prompt_file=prompt_file,
        model=model, apply=apply, diff=diff, show_prompt=show_prompt,
        sandbox=sandbox, all_exercises=all_exercises, patron=patron,
        tema=tema, bloom=bloom, tag=tag, output=output,
    )


@improve_app.command("edge-cases")
def improve_edge_cases(
    target: Optional[str] = typer.Argument(None, help="ID de ejercicio, ruta a directorio, banco o archivo .gift."),
    banco: Path = typer.Option(Path("."), "--banco", "-b", help="Directorio raíz del banco de ejercicios."),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Instrucciones adicionales para ajustar el prompt."),
    prompt_file: Optional[Path] = typer.Option(None, "--prompt-file", "-P", help="Archivo con directivas personalizadas."),
    model: str = typer.Option("opencode-go/qwen3.8-max", "--model", "-m", help="Modelo de OpenCode a utilizar."),
    apply: bool = typer.Option(False, "--apply", "-a", help="Aplica y guarda los cambios en los archivos."),
    diff: bool = typer.Option(True, "--diff/--no-diff", "-d", help="Muestra diff unificado de los cambios."),
    show_prompt: bool = typer.Option(False, "--show-prompt", help="Imprime el prompt generado sin invocar a OpenCode."),
    sandbox: bool = typer.Option(True, "--sandbox/--no-sandbox", help="Usa ejecución aislada bwrap si está disponible."),
    all_exercises: bool = typer.Option(False, "--all", help="Procesar todos los ejercicios del banco."),
    patron: Optional[str] = typer.Option(None, "--patron", help="Filtro comodín para IDs de ejercicios."),
    tema: Optional[str] = typer.Option(None, "--tema", help="Filtra por tema pedagógico."),
    bloom: Optional[int] = typer.Option(None, "--bloom", help="Filtra por nivel de Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtra por etiqueta."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de exportación alternativa."),
) -> None:
    """Especifica exhaustivamente casos borde, precondiciones y postcondiciones según el tema."""
    from deckard.core.improve import AspectoMejora
    _ejecutar_mejora_cli(
        aspecto=AspectoMejora.EDGE_CASES,
        target=target, banco=banco, prompt=prompt, prompt_file=prompt_file,
        model=model, apply=apply, diff=diff, show_prompt=show_prompt,
        sandbox=sandbox, all_exercises=all_exercises, patron=patron,
        tema=tema, bloom=bloom, tag=tag, output=output,
    )


@improve_app.command("examples")
def improve_examples(
    target: Optional[str] = typer.Argument(None, help="ID de ejercicio, ruta a directorio, banco o archivo .gift."),
    banco: Path = typer.Option(Path("."), "--banco", "-b", help="Directorio raíz del banco de ejercicios."),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Instrucciones adicionales para ajustar el prompt."),
    prompt_file: Optional[Path] = typer.Option(None, "--prompt-file", "-P", help="Archivo con directivas personalizadas."),
    model: str = typer.Option("opencode-go/qwen3.8-max", "--model", "-m", help="Modelo de OpenCode a utilizar."),
    apply: bool = typer.Option(False, "--apply", "-a", help="Aplica y guarda los cambios en los archivos."),
    diff: bool = typer.Option(True, "--diff/--no-diff", "-d", help="Muestra diff unificado de los cambios."),
    show_prompt: bool = typer.Option(False, "--show-prompt", help="Imprime el prompt generado sin invocar a OpenCode."),
    sandbox: bool = typer.Option(True, "--sandbox/--no-sandbox", help="Usa ejecución aislada bwrap si está disponible."),
    all_exercises: bool = typer.Option(False, "--all", help="Procesar todos los ejercicios del banco."),
    patron: Optional[str] = typer.Option(None, "--patron", help="Filtro comodín para IDs de ejercicios."),
    tema: Optional[str] = typer.Option(None, "--tema", help="Filtra por tema pedagógico."),
    bloom: Optional[int] = typer.Option(None, "--bloom", help="Filtra por nivel de Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtra por etiqueta."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de exportación alternativa."),
) -> None:
    """Enriquece la consigna con ejemplos de entrada/salida (I/O) claros y trazas de ejecución."""
    from deckard.core.improve import AspectoMejora
    _ejecutar_mejora_cli(
        aspecto=AspectoMejora.EXAMPLES,
        target=target, banco=banco, prompt=prompt, prompt_file=prompt_file,
        model=model, apply=apply, diff=diff, show_prompt=show_prompt,
        sandbox=sandbox, all_exercises=all_exercises, patron=patron,
        tema=tema, bloom=bloom, tag=tag, output=output,
    )


@improve_app.command("hints")
def improve_hints(
    target: Optional[str] = typer.Argument(None, help="ID de ejercicio, ruta a directorio, banco o archivo .gift."),
    banco: Path = typer.Option(Path("."), "--banco", "-b", help="Directorio raíz del banco de ejercicios."),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Instrucciones adicionales para ajustar el prompt."),
    prompt_file: Optional[Path] = typer.Option(None, "--prompt-file", "-P", help="Archivo con directivas personalizadas."),
    model: str = typer.Option("opencode-go/qwen3.8-max", "--model", "-m", help="Modelo de OpenCode a utilizar."),
    apply: bool = typer.Option(False, "--apply", "-a", help="Aplica y guarda los cambios en los archivos."),
    diff: bool = typer.Option(True, "--diff/--no-diff", "-d", help="Muestra diff unificado de los cambios."),
    show_prompt: bool = typer.Option(False, "--show-prompt", help="Imprime el prompt generado sin invocar a OpenCode."),
    sandbox: bool = typer.Option(True, "--sandbox/--no-sandbox", help="Usa ejecución aislada bwrap si está disponible."),
    all_exercises: bool = typer.Option(False, "--all", help="Procesar todos los ejercicios del banco."),
    patron: Optional[str] = typer.Option(None, "--patron", help="Filtro comodín para IDs de ejercicios."),
    tema: Optional[str] = typer.Option(None, "--tema", help="Filtra por tema pedagógico."),
    bloom: Optional[int] = typer.Option(None, "--bloom", help="Filtra por nivel de Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtra por etiqueta."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de exportación alternativa."),
) -> None:
    """Genera o mejora pistas pedagógicas progresivas de 3 niveles sin revelar la solución."""
    from deckard.core.improve import AspectoMejora
    _ejecutar_mejora_cli(
        aspecto=AspectoMejora.HINTS,
        target=target, banco=banco, prompt=prompt, prompt_file=prompt_file,
        model=model, apply=apply, diff=diff, show_prompt=show_prompt,
        sandbox=sandbox, all_exercises=all_exercises, patron=patron,
        tema=tema, bloom=bloom, tag=tag, output=output,
    )


@improve_app.command("bloom")
def improve_bloom(
    target: Optional[str] = typer.Argument(None, help="ID de ejercicio, ruta a directorio, banco o archivo .gift."),
    banco: Path = typer.Option(Path("."), "--banco", "-b", help="Directorio raíz del banco de ejercicios."),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Instrucciones adicionales para ajustar el prompt."),
    prompt_file: Optional[Path] = typer.Option(None, "--prompt-file", "-P", help="Archivo con directivas personalizadas."),
    model: str = typer.Option("opencode-go/qwen3.8-max", "--model", "-m", help="Modelo de OpenCode a utilizar."),
    apply: bool = typer.Option(False, "--apply", "-a", help="Aplica y guarda los cambios en los archivos."),
    diff: bool = typer.Option(True, "--diff/--no-diff", "-d", help="Muestra diff unificado de los cambios."),
    show_prompt: bool = typer.Option(False, "--show-prompt", help="Imprime el prompt generado sin invocar a OpenCode."),
    sandbox: bool = typer.Option(True, "--sandbox/--no-sandbox", help="Usa ejecución aislada bwrap si está disponible."),
    all_exercises: bool = typer.Option(False, "--all", help="Procesar todos los ejercicios del banco."),
    patron: Optional[str] = typer.Option(None, "--patron", help="Filtro comodín para IDs de ejercicios."),
    tema: Optional[str] = typer.Option(None, "--tema", help="Filtra por tema pedagógico."),
    bloom: Optional[int] = typer.Option(None, "--bloom", help="Filtra por nivel de Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtra por etiqueta."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de exportación alternativa."),
) -> None:
    """Alinea la exigencia y rigor de la consigna con su nivel asignado de la taxonomía de Bloom."""
    from deckard.core.improve import AspectoMejora
    _ejecutar_mejora_cli(
        aspecto=AspectoMejora.BLOOM,
        target=target, banco=banco, prompt=prompt, prompt_file=prompt_file,
        model=model, apply=apply, diff=diff, show_prompt=show_prompt,
        sandbox=sandbox, all_exercises=all_exercises, patron=patron,
        tema=tema, bloom=bloom, tag=tag, output=output,
    )


@improve_app.command("testcases")
def improve_testcases(
    target: Optional[str] = typer.Argument(None, help="ID de ejercicio, ruta a directorio, banco o archivo .gift."),
    banco: Path = typer.Option(Path("."), "--banco", "-b", help="Directorio raíz del banco de ejercicios."),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Instrucciones adicionales para ajustar el prompt."),
    prompt_file: Optional[Path] = typer.Option(None, "--prompt-file", "-P", help="Archivo con directivas personalizadas."),
    model: str = typer.Option("opencode-go/qwen3.8-max", "--model", "-m", help="Modelo de OpenCode a utilizar."),
    apply: bool = typer.Option(False, "--apply", "-a", help="Aplica y guarda los cambios en los archivos."),
    diff: bool = typer.Option(True, "--diff/--no-diff", "-d", help="Muestra diff unificado de los cambios."),
    show_prompt: bool = typer.Option(False, "--show-prompt", help="Imprime el prompt generado sin invocar a OpenCode."),
    sandbox: bool = typer.Option(True, "--sandbox/--no-sandbox", help="Usa ejecución aislada bwrap si está disponible."),
    all_exercises: bool = typer.Option(False, "--all", help="Procesar todos los ejercicios del banco."),
    patron: Optional[str] = typer.Option(None, "--patron", help="Filtro comodín para IDs de ejercicios."),
    tema: Optional[str] = typer.Option(None, "--tema", help="Filtra por tema pedagógico."),
    bloom: Optional[int] = typer.Option(None, "--bloom", help="Filtra por nivel de Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtra por etiqueta."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de exportación alternativa."),
) -> None:
    """Diseña casos de prueba rigurosos (.in/.out y tests de función) cubriendo casos típicos y borde."""
    from deckard.core.improve import AspectoMejora
    _ejecutar_mejora_cli(
        aspecto=AspectoMejora.TESTCASES,
        target=target, banco=banco, prompt=prompt, prompt_file=prompt_file,
        model=model, apply=apply, diff=diff, show_prompt=show_prompt,
        sandbox=sandbox, all_exercises=all_exercises, patron=patron,
        tema=tema, bloom=bloom, tag=tag, output=output,
    )


@improve_app.command("starter")
def improve_starter(
    target: Optional[str] = typer.Argument(None, help="ID de ejercicio, ruta a directorio, banco o archivo .gift."),
    banco: Path = typer.Option(Path("."), "--banco", "-b", help="Directorio raíz del banco de ejercicios."),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Instrucciones adicionales para ajustar el prompt."),
    prompt_file: Optional[Path] = typer.Option(None, "--prompt-file", "-P", help="Archivo con directivas personalizadas."),
    model: str = typer.Option("opencode-go/qwen3.8-max", "--model", "-m", help="Modelo de OpenCode a utilizar."),
    apply: bool = typer.Option(False, "--apply", "-a", help="Aplica y guarda los cambios en los archivos."),
    diff: bool = typer.Option(True, "--diff/--no-diff", "-d", help="Muestra diff unificado de los cambios."),
    show_prompt: bool = typer.Option(False, "--show-prompt", help="Imprime el prompt generado sin invocar a OpenCode."),
    sandbox: bool = typer.Option(True, "--sandbox/--no-sandbox", help="Usa ejecución aislada bwrap si está disponible."),
    all_exercises: bool = typer.Option(False, "--all", help="Procesar todos los ejercicios del banco."),
    patron: Optional[str] = typer.Option(None, "--patron", help="Filtro comodín para IDs de ejercicios."),
    tema: Optional[str] = typer.Option(None, "--tema", help="Filtra por tema pedagógico."),
    bloom: Optional[int] = typer.Option(None, "--bloom", help="Filtra por nivel de Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtra por etiqueta."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de exportación alternativa."),
) -> None:
    """Genera o perfecciona el código esqueleto inicial (starter_code) y cabeceras .h con Doxygen."""
    from deckard.core.improve import AspectoMejora
    _ejecutar_mejora_cli(
        aspecto=AspectoMejora.STARTER,
        target=target, banco=banco, prompt=prompt, prompt_file=prompt_file,
        model=model, apply=apply, diff=diff, show_prompt=show_prompt,
        sandbox=sandbox, all_exercises=all_exercises, patron=patron,
        tema=tema, bloom=bloom, tag=tag, output=output,
    )


@improve_app.command("all")
@improve_app.command("full", hidden=True)
def improve_all(
    target: Optional[str] = typer.Argument(None, help="ID de ejercicio, ruta a directorio, banco o archivo .gift."),
    banco: Path = typer.Option(Path("."), "--banco", "-b", help="Directorio raíz del banco de ejercicios."),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Instrucciones adicionales para ajustar el prompt."),
    prompt_file: Optional[Path] = typer.Option(None, "--prompt-file", "-P", help="Archivo con directivas personalizadas."),
    model: str = typer.Option("opencode-go/qwen3.8-max", "--model", "-m", help="Modelo de OpenCode a utilizar."),
    apply: bool = typer.Option(False, "--apply", "-a", help="Aplica y guarda los cambios en los archivos."),
    diff: bool = typer.Option(True, "--diff/--no-diff", "-d", help="Muestra diff unificado de los cambios."),
    show_prompt: bool = typer.Option(False, "--show-prompt", help="Imprime el prompt generado sin invocar a OpenCode."),
    sandbox: bool = typer.Option(True, "--sandbox/--no-sandbox", help="Usa ejecución aislada bwrap si está disponible."),
    all_exercises: bool = typer.Option(False, "--all", help="Procesar todos los ejercicios del banco."),
    patron: Optional[str] = typer.Option(None, "--patron", help="Filtro comodín para IDs de ejercicios."),
    tema: Optional[str] = typer.Option(None, "--tema", help="Filtra por tema pedagógico."),
    bloom: Optional[int] = typer.Option(None, "--bloom", help="Filtra por nivel de Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtra por etiqueta."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de exportación alternativa."),
) -> None:
    """Mejora integral y holística de todos los aspectos de la consigna en una única pasada."""
    from deckard.core.improve import AspectoMejora
    _ejecutar_mejora_cli(
        aspecto=AspectoMejora.ALL,
        target=target, banco=banco, prompt=prompt, prompt_file=prompt_file,
        model=model, apply=apply, diff=diff, show_prompt=show_prompt,
        sandbox=sandbox, all_exercises=all_exercises, patron=patron,
        tema=tema, bloom=bloom, tag=tag, output=output,
    )


@improve_app.command("models")
def improve_models(
    provider: Optional[str] = typer.Argument(None, help="Proveedor opcional para filtrar modelos (ej: opencode-go)."),
    raw: bool = typer.Option(False, "--raw", "-r", help="Imprimir únicamente la lista plana de identificadores de modelos."),
) -> None:
    """Interroga a OpenCode por los modelos de lenguaje disponibles para curaduría."""
    from deckard.core.opencode import DEFAULT_MODEL, listar_modelos_opencode

    try:
        modelos = listar_modelos_opencode(provider=provider)
    except Exception as e:
        console.print(f"[bold red]Error al interrogar modelos de OpenCode:[/bold red] {e}")
        raise typer.Exit(code=1)

    if not modelos:
        console.print("[yellow]No se obtuvieron modelos desde OpenCode.[/yellow]")
        return

    if raw:
        for m in modelos:
            print(m)
        return

    tabla = Table(title="🤖 Modelos Disponibles en OpenCode", border_style="cyan")
    tabla.add_column("Identificador de Modelo", style="bold white")
    tabla.add_column("Proveedor", style="cyan")
    tabla.add_column("Por Defecto", justify="center")

    for m in modelos:
        prov = m.split("/")[0] if "/" in m else "local"
        es_default = "[bold green]★ Sí[/bold green]" if m == DEFAULT_MODEL else "[dim]No[/dim]"
        tabla.add_row(m, prov, es_default)

    console.print(tabla)
    console.print(f"\n[dim]Total: {len(modelos)} modelos disponibles. Modelo predeterminado: [bold cyan]{DEFAULT_MODEL}[/bold cyan][/dim]")
    console.print("[dim]Uso: deckard improve <comando> [target] -m <modelo>[/dim]")




