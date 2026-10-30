"""`export myst`: sitio MyST del banco (páginas, guías, TOC, .ripkg y catálogo JSON)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from deckard.core.sitio import ARCHIVO_TEMAS, SitioError, construir_sitio

from deckard.cli._shared import console, export_app


@export_app.command("myst")
def exportar_myst(
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    guias: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías (las specs sin `ejercicios` se saltean)."),
    salida: Path = typer.Option(Path("sitio"), "--salida", "-o", help="Directorio generado; se borra y regenera en cada corrida."),
    temas: Optional[Path] = typer.Option(None, "--temas", help=f"Títulos, unidades y prerrequisitos de los temas (por omisión <banco>/../{ARCHIVO_TEMAS})."),
    myst_yml: Optional[Path] = typer.Option(Path("myst.yml"), "--myst-yml", help="myst.yml cuyo `project.toc` se reescribe; se omite si no existe."),
    sin_soluciones: bool = typer.Option(False, "--sin-soluciones", help="No incluir la solución modelo en las páginas."),
    agrupar_unidades: bool = typer.Option(False, "--agrupar-unidades", help="Agrupar el TOC por unidades en lugar de temas."),
    sin_paquetes: bool = typer.Option(False, "--sin-paquetes", help="No generar los .ripkg ni el catálogo JSON."),
    permitir_invalidos: bool = typer.Option(False, "--permitir-invalidos", help="Terminar bien aunque haya ejercicios inválidos (se omiten del sitio)."),
) -> None:
    """Genera el sitio MyST del banco: una página por ejercicio y por guía, portada, grafo temático, TOC, .ripkg y catálogo JSON."""
    ruta_temas = temas if temas is not None else banco.parent / ARCHIVO_TEMAS
    ruta_myst = myst_yml if myst_yml is not None and myst_yml.is_file() else None
    try:
        res = construir_sitio(
            banco=banco,
            salida=salida,
            dir_guias=guias,
            temas=ruta_temas,
            myst_yml=ruta_myst,
            incluir_soluciones=not sin_soluciones,
            agrupar_por_unidad=agrupar_unidades,
            paquetes=not sin_paquetes,
        )
    except SitioError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]✓ Sitio en {res.salida}:[/green] {res.ejercicios} ejercicios, {len(res.guias)} guías"
                  f" ({res.no_publicados} ejercicios con `publicar: false` quedaron afuera).")
    for g in res.guias:
        if g.faltantes:
            console.print(f"[yellow]  ! guía {g.slug}: ejercicios que no están publicados en el banco: {', '.join(g.faltantes)}[/yellow]")
    for g in res.guias_vacias:
        console.print(f"[yellow]  ! guía {g.slug} sin página: ninguno de sus ejercicios está publicado ({', '.join(g.faltantes)}).[/yellow]")
    if res.catalogo:
        console.print(f"  Paquetes .ripkg: {res.paquetes} · catálogo: {res.catalogo}")
    if res.myst_yml:
        console.print(f"  TOC actualizado en {res.myst_yml}")
    elif myst_yml is not None:
        console.print(f"[dim]  {myst_yml} no existe: no se tocó ningún TOC.[/dim]")

    for eid, error in res.fallidos_pack:
        console.print(f"[red]  ✗ paquete {eid}: {error}[/red]")
    for dir_ej, error in res.invalidos:
        console.print(f"[red]  ✗ {dir_ej}: {error}[/red]")
    if res.fallidos_pack or (res.invalidos and not permitir_invalidos):
        console.print(f"[red]{len(res.invalidos)} ejercicios inválidos y {len(res.fallidos_pack)} paquetes fallidos.[/red]")
        raise typer.Exit(code=1)
