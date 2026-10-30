"""`export myst`: sitio MyST del banco (páginas, guías, TOC, .ripkg y catálogo JSON).

`export apunte`: los bloques «Ejercicios para practicar» en las páginas del apunte.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from deckard.core.sitio import ARCHIVO_TEMAS, SitioError, construir_sitio, planificar_apunte
from deckard.core.trazabilidad import EJERCICIOS_POR_BLOQUE, actualizar_paginas, quitar_bloque

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
    apunte: Optional[Path] = typer.Option(None, "--apunte", help="Repositorio del apunte: da los slugs exactos de sus páginas para los enlaces (sitios.apunte de temas.yaml)."),
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
            dir_apunte=apunte,
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
    for eid, error in res.paquetes_invalidos:
        console.print(f"[red]  ✗ paquete {eid} no pasó la verificación: {error}[/red]")
    for dir_ej, error in res.invalidos:
        console.print(f"[red]  ✗ {dir_ej}: {error}[/red]")
    if res.catalogo and not res.paquetes_invalidos:
        console.print(f"  [green]✓ {res.paquetes} paquetes verificados (hash, manifiesto y sin pruebas ocultas).[/green]")
    if res.fallidos_pack or res.paquetes_invalidos or (res.invalidos and not permitir_invalidos):
        console.print(f"[red]{len(res.invalidos)} ejercicios inválidos, {len(res.fallidos_pack)} paquetes fallidos y "
                      f"{len(res.paquetes_invalidos)} paquetes que no pasaron la verificación.[/red]")
        raise typer.Exit(code=1)


@export_app.command("apunte")
def exportar_apunte(
    apunte: Path = typer.Argument(..., exists=True, file_okay=False, help="Repositorio del apunte (con su myst.yml)."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    temas: Optional[Path] = typer.Option(None, "--temas", help=f"temas.yaml con `apunte` por tema y `sitios` (por omisión <banco>/../{ARCHIVO_TEMAS})."),
    ejercicios: int = typer.Option(EJERCICIOS_POR_BLOQUE, "--ejercicios", min=0, help="Ejercicios destacados por tema en cada bloque."),
    verificar: bool = typer.Option(False, "--verificar", help="No escribir: salir con 1 si algún bloque está desactualizado (para CI)."),
) -> None:
    """Escribe en las páginas del apunte el bloque «Ejercicios para practicar» de sus temas.

    Las páginas salen del `apunte` de cada tema en temas.yaml; el bloque va entre las marcas
    `% deckard export apunte: inicio` y `…: fin` (se agrega al final la primera vez) y enlaza al
    sitio publicado de enunciados (`sitios.enunciados`). Los bloques de páginas que ya no figuran
    en temas.yaml se quitan.
    """
    ruta_temas = temas if temas is not None else banco.parent / ARCHIVO_TEMAS
    try:
        plan = planificar_apunte(banco, ruta_temas, apunte, ejercicios)
    except SitioError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    cambiadas, faltantes = actualizar_paginas(apunte, plan.bloques, escribir=not verificar)
    for ruta in plan.sobrantes:
        archivo = apunte / ruta
        cambiadas.append(ruta)
        if not verificar:
            archivo.write_text(quitar_bloque(archivo.read_text(encoding="utf-8")), encoding="utf-8")
    for ruta in faltantes:
        console.print(f"[red]  ✗ {ruta}: figura en temas.yaml pero no existe en {apunte}[/red]")
    for tema in plan.temas_sin_apunte:
        console.print(f"[yellow]  ! tema {tema}: tiene ejercicios publicados pero ninguna página del apunte en temas.yaml[/yellow]")
    if verificar:
        for ruta in cambiadas:
            console.print(f"[red]  ✗ {ruta}: el bloque de ejercicios está desactualizado[/red]")
        if cambiadas or faltantes:
            console.print("[red]Correr `deckard export apunte` y commitear el apunte.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[green]✓ {len(plan.bloques)} páginas del apunte al día.[/green]")
        return
    console.print(f"[green]✓ {len(plan.bloques)} páginas del apunte con ejercicios ({len(cambiadas)} cambiaron).[/green]")
    if faltantes:
        raise typer.Exit(code=1)
