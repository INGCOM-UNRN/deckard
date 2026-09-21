"""Comandos de exportación e integración adicionales: export-classroom, export-notebook, check-load, variant, sync."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.table import Table
import typer

from deckard.core.bank import (
    buscar_ejercicios,
    cargar_ejercicio,
)
from deckard.core.guides import (
    cargar_guia_con_ejercicios,
    guardar_yaml_guia,
)
from deckard.core.models import Ejercicio, GuiaSpec, NivelBloom

from deckard.cli._shared import (
    app,
    console,
)

@app.command("export-classroom")
@app.command("publish-classroom")
def cmd_export_classroom(
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio a exportar como asignación."),
    salida: Path = typer.Option(Path("classroom_assignments"), "--salida", "-o", help="Directorio de salida para la asignación."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    nombre_repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Nombre personalizado para el repositorio."),
) -> None:
    """Genera la estructura completa de un repositorio para GitHub Classroom (README, starter code, Makefile, CI)."""
    from deckard.core.classroom import exportar_github_classroom

    matches = buscar_ejercicios(banco, patron=ejercicio_id, recursivo=True)
    if not matches:
        console.print(f"[bold red]No se encontró el ejercicio '{ejercicio_id}' en {banco}.[/bold red]")
        raise typer.Exit(code=1)

    dir_p, ej = matches[0]
    res_dir = exportar_github_classroom(ej, dir_p, salida, nombre_repo=nombre_repo)
    console.print(f"[bold green]✓ Asignación de GitHub Classroom generada exitosamente:[/bold green]")
    console.print(f"  • Directorio: [cyan]{res_dir}[/cyan]")
    console.print(f"  • Workflow CI: [dim]{res_dir / '.github' / 'workflows' / 'classroom.yml'}[/dim]")


@app.command("export-notebook")
def cmd_export_notebook(
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio o ruta al directorio del ejercicio."),
    salida: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de destino del archivo .ipynb."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Exporta un ejercicio en formato interactivo Jupyter Notebook (.ipynb) con kernel C."""
    from deckard.core.notebook import exportar_ejercicio_notebook

    ej = None
    if Path(ejercicio_id).is_dir():
        ej = cargar_ejercicio(Path(ejercicio_id))
    else:
        matches = buscar_ejercicios(banco, patron=ejercicio_id, recursivo=True)
        if matches:
            ej = matches[0][1]

    if not ej:
        console.print(f"[bold red]No se encontró el ejercicio '{ejercicio_id}'.[/bold red]")
        raise typer.Exit(code=1)

    out_file = salida or Path(f"{ej.id}.ipynb")
    exportar_ejercicio_notebook(ej, out_file)
    console.print(f"[bold green]✓ Jupyter Notebook C generado con éxito en:[/bold green] [cyan]{out_file}[/cyan]")


@app.command("check-load")
def cmd_check_load(
    guia: Path = typer.Argument(..., help="Ruta a la guía YAML o spec a auditar."),
    max_horas: float = typer.Option(6.0, "--max-horas", "-m", help="Carga horaria pedagógica máxima sugerida en horas."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Audita la carga horaria acumulada y el balance Bloom de una guía."""
    from deckard.core.load_checker import auditar_carga_horaria

    if not guia.exists():
        console.print(f"[bold red]No se encontró la guía '{guia}'.[/bold red]")
        raise typer.Exit(code=1)

    datos, items = cargar_guia_con_ejercicios(guia, banco)
    ejercicios = [ej for _, ej in items if ej is not None]

    if not ejercicios and "tiempo_total_estimado" in datos:
        # Fallback si no hay banco físico: evaluar con base en metadata declarada
        mins_tot = int(datos.get("tiempo_total_estimado", 0))
        # Generar bloques de hasta 300 min por ejercicio para no violar restricciones de esquema
        ejercicios = []
        restante = mins_tot
        idx = 1
        while restante > 0:
            m = min(restante, 300)
            ejercicios.append(Ejercicio(id=f"ej_{idx}", titulo=f"Ejercicio {idx}", tema="general", bloom=NivelBloom.APLICAR, minutos=m, enunciado="..."))
            restante -= m
            idx += 1

    ok, _ = auditar_carga_horaria(ejercicios, max_horas_semanales=max_horas, console=console)
    if not ok:
        raise typer.Exit(code=1)


@app.command("variant")
@app.command("compose-variant")
def cmd_variant(
    guia: Path = typer.Argument(..., help="Ruta a la guía YAML original."),
    salida: Path = typer.Option(Path("guias/guia_recuperatorio.yaml"), "--salida", "-o", help="Ruta de la nueva guía variante."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    semilla: Optional[int] = typer.Option(None, "--seed", "-s", help="Semilla para selección pseudoaleatoria."),
) -> None:
    """Genera automáticamente una variante homóloga para recuperatorios respetando niveles Bloom."""
    from deckard.core.variant import seleccionar_variantes_homologas

    if not guia.exists():
        console.print(f"[bold red]No se encontró la guía '{guia}'.[/bold red]")
        raise typer.Exit(code=1)

    datos, items = cargar_guia_con_ejercicios(guia, banco)
    ejercicios = [ej for _, ej in items if ej is not None]
    variantes, mapeo = seleccionar_variantes_homologas(banco, ejercicios, semilla=semilla)

    tabla = Table(title="🔄 Mapeo de Ejercicios Homólogos para Recuperatorio", border_style="cyan")
    tabla.add_column("Original ID", style="bold white")
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Variante Seleccionada", style="green")

    for orig, var in mapeo:
        var_str = f"{var.id} ({var.titulo})" if var else "[dim](Mismo ejercicio)[/dim]"
        tabla.add_row(orig.id, orig.bloom.name, var_str)

    console.print(tabla)

    nueva_spec = GuiaSpec(
        id=f"{datos.get('id', 'guia')}_recuperatorio",
        nombre=f"{datos.get('nombre', 'Guía')} (Variante Recuperatorio)",
        materia=datos.get("materia", "Programación 1"),
        ejercicios=[v.id for v in variantes],
        tiempo_total_estimado=sum(v.minutos_estimados for v in variantes),
    )
    guardar_yaml_guia(nueva_spec, salida)
    console.print(f"\n[bold green]✓ Guía variante guardada en:[/bold green] [cyan]{salida}[/cyan]")


@app.command("sync")
def cmd_sync(
    remote_url: Optional[str] = typer.Argument(None, help="URL del repositorio Git remoto a clonar o vincular."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    branch: str = typer.Option("main", "--branch", help="Rama a sincronizar."),
) -> None:
    """Sincroniza el banco de ejercicios con un repositorio Git descentralizado."""
    from deckard.core.sync import sincronizar_banco_git
    res = sincronizar_banco_git(banco, remote_url=remote_url, branch=branch, console=console)
    if not res.get("ok", False):
        raise typer.Exit(code=1)


