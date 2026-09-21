"""Comandos test-harness, pack y multiplex."""

from __future__ import annotations

from pathlib import Path
import subprocess
import shutil
from typing import Optional

from rich.table import Table
import typer
import yaml

from deckard.core.bank import (
    buscar_ejercicios,
)
from deckard.core.guides import (
    resolver_ruta_guia,
)

from deckard.cli._shared import (
    app,
    console,
    verify_app,
)

# ---------------------------------------------------------------------------
# test-harness / pack / multiplex
# ---------------------------------------------------------------------------


@verify_app.command("test-harness")
@verify_app.command("harness")
@app.command("test-harness", hidden=True)
def test_harness(
    ejercicio_id: str = typer.Argument(..., help="Id del ejercicio en el banco."),
    spec: Path = typer.Argument(..., exists=True, help="spec.yaml del arnés."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    herramienta: Optional[str] = typer.Option(None, "--herramienta", help="Binario de inyección (por defecto vasquez)."),
    ripley: Optional[str] = typer.Option(None, "--ripley", hidden=True),
) -> None:
    """Corre el arnés de prueba con inyección de fallos de memoria vía `vasquez inject`."""
    binario = herramienta or shutil.which("vasquez") or "vasquez"
    if shutil.which(binario) is None:
        console.print(f"[red]'{binario}' no está instalado en el PATH.[/red]")
        raise typer.Exit(code=127)
    cmd_args = [binario, "inject", str(spec)]
    cmd_str = " ".join(cmd_args)
    console.print(f"[dim]$ {cmd_str}[/dim]")
    proc = subprocess.run(cmd_args)
    raise typer.Exit(code=proc.returncode)


@app.command("pack")
def pack(
    objetivo: str = typer.Argument(
        ...,
        help="Id del ejercicio en el banco, o ruta a guia.yaml / carpeta de guía / carpeta de ejercicio.",
    ),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco de ejercicios."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Archivo .ripkg o directorio de salida."),
    sign_key: Optional[str] = typer.Option(None, "--sign-key", help="Clave GPG para firmar el paquete."),
    starter: bool = typer.Option(False, "--starter", help="Generar también estructura starter repo para GitHub Classroom."),
) -> None:
    """Empaqueta ejercicios o guías como .ripkg para Ripley y starter repos."""
    from deckard.core.pack import PackError, empaquetar_ejercicio, empaquetar_guia

    try:
        # 1. Intentar resolver como guía (carpeta de guía o archivo YAML)
        ruta_yaml = resolver_ruta_guia(objetivo, dir_guias=Path("guias"))
        if ruta_yaml.is_file() and (ruta_yaml.suffix in (".yaml", ".yml") or "guia" in ruta_yaml.name):
            try:
                with open(ruta_yaml, "r", encoding="utf-8") as f:
                    datos = yaml.safe_load(f) or {}
                if "ejercicios" in datos:
                    resultados = empaquetar_guia(
                        guia_spec_file=ruta_yaml,
                        banco=banco,
                        out_dir=salida,
                        sign_key=sign_key,
                        generar_starter=starter,
                    )
                    console.print(f"[green]✓ Guía empaquetada: {len(resultados)} paquetes generados.[/green]")
                    for r in resultados:
                        console.print(f"  • [bold]{r.output_path.name}[/bold] ({r.archivos_payload} archivos, {r.checks_habilitados} checks)")
                        if r.starter_path:
                            console.print(f"    ↳ Starter repo: [dim]{r.starter_path}[/dim]")
                    return
            except Exception:
                pass

        # 2. Si no es guía, resolver como ejercicio en el banco (búsqueda recursiva)
        matches = buscar_ejercicios(banco, patron=objetivo, recursivo=True)
        if matches:
            dir_ej, _ = matches[0]
        else:
            dir_ej = Path(objetivo)
            if not dir_ej.is_dir():
                console.print(f"[red]No se encontró el ejercicio o guía: '{objetivo}'[/red]")
                raise typer.Exit(code=1)

        res = empaquetar_ejercicio(
            dir_ejercicio=dir_ej,
            out_path=salida,
            sign_key=sign_key,
            generar_starter=starter,
        )
        console.print(f"[green]✓ Paquete creado:[/green] {res.output_path}")
        console.print(f"  Checks habilitados: {res.checks_habilitados} · Archivos: {res.archivos_payload} · Firmado: {'sí' if res.firmado else 'no'}")
        if res.starter_path:
            console.print(f"  [green]✓ Starter repo:[/green] {res.starter_path}")

    except PackError as e:
        console.print(f"[red]Error de empaquetado: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("multiplex")
def multiplex(
    spec: Path = typer.Option(..., "--spec", "-s", exists=True, help="Ruta al archivo matriz.yaml."),
    students: Optional[Path] = typer.Option(None, "--students", exists=True, help="CSV con lista de alumnos."),
    salida: Path = typer.Option(Path("dist/multiplex"), "--salida", "-o", help="Directorio destino de la multiplexación."),
    pack: bool = typer.Option(True, "--pack/--no-pack", help="Generar paquetes .ripkg para cada variante."),
    starters: bool = typer.Option(True, "--starters/--no-starters", help="Generar starter repos por alumno."),
) -> None:
    """tp-multiplexer: Genera variantes combinatorias y asignación determinista por alumno."""
    from deckard.core.multiplex import multiplexar_tp

    try:
        resultado = multiplexar_tp(
            matriz_path=spec,
            students_path=students,
            output_dir=salida,
            pack_ripkg=pack,
            generar_starters=starters,
        )

        console.print(f"[bold green]✓ Multiplexación completada para '{resultado.ejercicio}'[/bold green]")
        console.print(f"  • Total de variantes combinatorias: [cyan]{resultado.total_variantes}[/cyan]")
        console.print(f"  • Directorio de salida: [dim]{resultado.output_dir}[/dim]")

        if resultado.asignaciones:
            console.print(f"  • Estudiantes asignados: [green]{len(resultado.asignaciones)}[/green]")
            tabla = Table(title="Muestra de asignaciones deterministas (primeros 5)")
            tabla.add_column("Alumno ID", style="cyan")
            tabla.add_column("Nombre")
            tabla.add_column("Variante", style="green")
            tabla.add_column("Parámetros", style="dim")

            for asig in resultado.asignaciones[:5]:
                tabla.add_row(
                    asig.alumno.id,
                    asig.alumno.nombre or "—",
                    asig.variante.id,
                    str(asig.variante.parametros),
                )
            console.print(tabla)
            console.print(f"  ↳ Planilla completa en: [bold]{resultado.output_dir / 'asignaciones.csv'}[/bold]")

    except Exception as e:
        console.print(f"[red]Error durante la multiplexación: {e}[/red]")
        raise typer.Exit(code=1)


