"""Helpers de `deckard export run`: resolución de destino y exportación por formato (guías, compendios, ejercicios)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from rich.table import Table
import typer

from deckard.core.export import (
    compilar_pdf,
    compilar_typst_a_pdf,
    renderizar_ejercicio_html,
    renderizar_ejercicio_md,
    renderizar_ejercicio_typst,
    renderizar_guia_html,
    renderizar_guia_md,
    renderizar_guia_typst,
)

from deckard.cli._shared import console


@dataclass
class OpcionesExport:
    """Opciones de exportación compartidas por todos los caminos de `export run`."""

    tipos: List[str]
    banco: Path
    template: Optional[str] = None
    pipeline_md: bool = False
    solucion: bool = False
    pistas: bool = False
    tests: bool = False
    extra_css: Optional[str] = None
    dos_columnas: bool = False
    archivos_generados: List[str] = field(default_factory=list)


def emitir_json(opts: OpcionesExport) -> None:
    console.print_json(data={"status": "ok", "total": len(opts.archivos_generados), "archivos": opts.archivos_generados})


def resolver_destino(salida: Optional[Path], tipos: List[str], fmt: str, nombre_base: str) -> Path:
    """Ruta destino de un formato según `--salida` (archivo, directorio o ausente)."""
    if salida is None:
        return Path(f"{nombre_base}.{fmt}")
    if len(tipos) == 1 and not salida.is_dir() and salida.suffix:
        return salida
    if salida.is_dir() or not salida.suffix or str(salida).endswith(("/", "\\")):
        return salida / f"{nombre_base}.{fmt}"
    return salida.with_suffix(f".{fmt}")


def _pdf_con_fallback(
    opts: OpcionesExport,
    dest: Path,
    a_typst,
    a_html,
    prefijo: str,
    tolerante: bool = False,
) -> Optional[Path]:
    """PDF vía Typst y, si falla, vía HTML. Con `tolerante` no imprime ni registra (modo tabla)."""
    try:
        typst_salida, base_p = a_typst()
        pdf_path = compilar_typst_a_pdf(typst_salida, dest, root_dir=base_p)
        if not tolerante:
            opts.archivos_generados.append(str(pdf_path))
            console.print(f"[green]✓ {prefijo} a PDF (Typst):[/green] {pdf_path}")
        return pdf_path
    except Exception as e_typst:
        if tolerante:
            html_salida, base_p = a_html()
            return compilar_pdf(html_salida, dest, base_url=str(base_p) if base_p else ".")
        try:
            html_salida, base_p = a_html()
            pdf_path = compilar_pdf(html_salida, dest, base_url=str(base_p) if base_p else ".")
            opts.archivos_generados.append(str(pdf_path))
            console.print(f"[green]✓ {prefijo} a PDF:[/green] {pdf_path}")
            return pdf_path
        except Exception as e:
            console.print(f"[red]Error exportando PDF: {e_typst or e}[/red]")
            raise typer.Exit(code=1)


def exportar_guia(opts: OpcionesExport, guia_meta: dict, items: List[Any], salida: Optional[Path], nombre_base: str, prefijo: str) -> None:
    """Exporta una guía (o compendio) ya armada a cada formato pedido."""
    def kw_guia() -> dict:
        return dict(
            guia_meta=guia_meta,
            ejercicios_con_dir=items,
            template_nombre_o_ruta=opts.template,
            incluir_soluciones=opts.solucion,
            incluir_pistas=opts.pistas,
            dir_banco=opts.banco,
        )

    def guia_html():
        return renderizar_guia_html(**kw_guia(), extra_css=opts.extra_css, via_markdown_pipeline=opts.pipeline_md)

    def guia_typst():
        return renderizar_guia_typst(**kw_guia(), dos_columnas=opts.dos_columnas)

    for fmt in opts.tipos:
        dest = resolver_destino(salida, opts.tipos, fmt, nombre_base)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "md":
            md_salida, _ = renderizar_guia_md(**kw_guia())
            dest.write_text(md_salida, encoding="utf-8")
            opts.archivos_generados.append(str(dest))
            console.print(f"[green]✓ {prefijo} a Markdown:[/green] {dest}")
        elif fmt in ("typ", "typst"):
            typ_salida, _ = guia_typst()
            dest.write_text(typ_salida, encoding="utf-8")
            opts.archivos_generados.append(str(dest))
            console.print(f"[green]✓ {prefijo} a Typst:[/green] {dest}")
        elif fmt == "html":
            html_salida, _ = guia_html()
            dest.write_text(html_salida, encoding="utf-8")
            opts.archivos_generados.append(str(dest))
            console.print(f"[green]✓ {prefijo} a HTML:[/green] {dest}")
        elif fmt == "pdf":
            _pdf_con_fallback(opts, dest, guia_typst, guia_html, prefijo)


def _kw_ejercicio(opts: OpcionesExport, dir_ej: Optional[Path], ej: Any) -> dict:
    return dict(
        ejercicio=ej,
        dir_ejercicio=dir_ej,
        template_nombre_o_ruta=opts.template,
        incluir_solucion=opts.solucion,
        incluir_pistas=opts.pistas,
        dir_banco=opts.banco,
    )


def _ejercicio_html(opts: OpcionesExport, dir_ej: Optional[Path], ej: Any):
    return renderizar_ejercicio_html(
        **_kw_ejercicio(opts, dir_ej, ej),
        incluir_tests=opts.tests,
        extra_css=opts.extra_css,
        via_markdown_pipeline=opts.pipeline_md,
    )


def _ejercicio_typst(opts: OpcionesExport, dir_ej: Optional[Path], ej: Any):
    return renderizar_ejercicio_typst(**_kw_ejercicio(opts, dir_ej, ej))


def _ejercicio_md(opts: OpcionesExport, dir_ej: Optional[Path], ej: Any):
    return renderizar_ejercicio_md(**_kw_ejercicio(opts, dir_ej, ej), incluir_meta=True, incluir_tests=opts.tests)


def exportar_un_ejercicio(opts: OpcionesExport, dir_ej: Optional[Path], ej: Any, salida: Optional[Path]) -> None:
    """Exporta un único ejercicio a cada formato pedido."""
    for fmt in opts.tipos:
        dest = resolver_destino(salida, opts.tipos, fmt, ej.id)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "md":
            md_salida, _ = _ejercicio_md(opts, dir_ej, ej)
            dest.write_text(md_salida, encoding="utf-8")
            opts.archivos_generados.append(str(dest))
            console.print(f"[green]✓ Ejercicio exportado a Markdown:[/green] {dest}")
        elif fmt in ("typ", "typst"):
            typ_salida, _ = _ejercicio_typst(opts, dir_ej, ej)
            dest.write_text(typ_salida, encoding="utf-8")
            opts.archivos_generados.append(str(dest))
            console.print(f"[green]✓ Ejercicio exportado a Typst:[/green] {dest}")
        elif fmt == "html":
            html_salida, _ = _ejercicio_html(opts, dir_ej, ej)
            dest.write_text(html_salida, encoding="utf-8")
            opts.archivos_generados.append(str(dest))
            console.print(f"[green]✓ Ejercicio exportado a HTML:[/green] {dest}")
        elif fmt == "pdf":
            _pdf_con_fallback(
                opts, dest,
                lambda: _ejercicio_typst(opts, dir_ej, ej),
                lambda: _ejercicio_html(opts, dir_ej, ej),
                "Ejercicio exportado",
            )


def exportar_varios_ejercicios(opts: OpcionesExport, candidatos: List[Any], salida: Optional[Path], as_json: bool) -> None:
    """Exporta muchos ejercicios a un directorio, uno por archivo, con tabla resumen."""
    out_dir = salida or Path("dist")
    out_dir.mkdir(parents=True, exist_ok=True)
    tipos_str = ", ".join(t.upper() for t in opts.tipos)
    console.print(f"[bold]Exportando {len(candidatos)} ejercicios a [{tipos_str}] en {out_dir}...[/bold]")

    tabla = Table(title=f"Exportación ({tipos_str})")
    tabla.add_column("Ejercicio", style="cyan")
    tabla.add_column("Formato", justify="center")
    tabla.add_column("Archivo generado", style="green")

    for dir_ej, ej in candidatos:
        for fmt in opts.tipos:
            file_dest = out_dir / f"{ej.id}.{fmt}"
            if fmt == "md":
                md_salida, _ = _ejercicio_md(opts, dir_ej, ej)
                file_dest.write_text(md_salida, encoding="utf-8")
            elif fmt in ("typ", "typst"):
                typ_salida, _ = _ejercicio_typst(opts, dir_ej, ej)
                file_dest.write_text(typ_salida, encoding="utf-8")
            elif fmt == "html":
                html_salida, _ = _ejercicio_html(opts, dir_ej, ej)
                file_dest.write_text(html_salida, encoding="utf-8")
            elif fmt == "pdf":
                _pdf_con_fallback(
                    opts, file_dest,
                    lambda: _ejercicio_typst(opts, dir_ej, ej),
                    lambda: _ejercicio_html(opts, dir_ej, ej),
                    "",
                    tolerante=True,
                )

            tabla.add_row(ej.id, fmt.upper(), str(file_dest))
            opts.archivos_generados.append(str(file_dest))

    if as_json:
        emitir_json(opts)
        return

    console.print(tabla)
    console.print(f"[green]✓ Archivos generados en {out_dir}[/green]")
