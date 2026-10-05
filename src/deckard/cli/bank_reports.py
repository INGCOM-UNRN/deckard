"""Comandos de reportes e inspección del banco: stats, lint, duplicate, deps, cache, unpack, doctor, browse."""

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

from deckard.cli._shared import (
    app,
    console,
    bank_app,
)

@app.command("stats")
@bank_app.command("stats")
def cmd_stats(
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco a analizar."),
    as_json: bool = typer.Option(False, "--json", help="Salida en formato JSON estructurado."),
) -> None:
    """Grafica la distribución de Bloom y tiempos acumulados con histogramas ASCII en terminal."""
    from deckard.core.cache import update_bank_cache

    if banco.is_dir():
        update_bank_cache(banco)
    ejs = buscar_ejercicios(banco, recursivo=True)
    if not ejs:
        if as_json:
            console.print_json(data={"total_ejercicios": 0, "verificados": 0, "tiempo_acumulado_min": 0, "promedio_min": 0, "distribucion_bloom": {}, "distribucion_temas": {}})
            return
        console.print(f"[yellow]No se encontraron ejercicios en {banco}[/yellow]")
        return

    total = len(ejs)
    total_min = sum(e.minutos_estimados for _, e in ejs)
    verificados = sum(1 for _, e in ejs if e.verificado)

    bloom_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    theme_counts: dict[str, int] = {}

    for _, ej in ejs:
        b_val = ej.bloom.value if hasattr(ej.bloom, "value") else int(ej.bloom)
        bloom_counts[b_val] = bloom_counts.get(b_val, 0) + 1
        t = ej.tema or "general"
        theme_counts[t] = theme_counts.get(t, 0) + 1

    if as_json:
        data = {
            "total_ejercicios": total,
            "verificados": verificados,
            "tiempo_acumulado_min": total_min,
            "promedio_min": round(total_min / total, 2) if total else 0,
            "distribucion_bloom": bloom_counts,
            "distribucion_temas": theme_counts,
        }
        console.print_json(data=data)
        return

    console.print(f"\n[bold green]📊 Estadísticas del Banco Deckard[/bold green] ([dim]{banco}[/dim])")
    console.print(f"  • [bold]Total ejercicios:[/bold] {total}")
    console.print(f"  • [bold]Verificados:[/bold] {verificados}/{total} ({verificados/total*100:.1f}%)")
    console.print(f"  • [bold]Tiempo acumulado:[/bold] {total_min} min (~{total_min/60:.1f} horas)")
    console.print(f"  • [bold]Promedio por ejercicio:[/bold] {total_min/total:.1f} min\n")

    console.print("[bold cyan]Distribución Taxonomía de Bloom (Histograma):[/bold cyan]")
    bloom_labels = {
        1: "Recordar     (B1)",
        2: "Comprender   (B2)",
        3: "Aplicar      (B3)",
        4: "Analizar     (B4)",
        5: "Evaluar      (B5)",
        6: "Crear        (B6)",
    }
    max_count = max(bloom_counts.values()) or 1
    max_bar_width = 30

    for level in range(1, 7):
        cnt = bloom_counts.get(level, 0)
        pct = (cnt / total) * 100 if total else 0
        bar_len = int((cnt / max_count) * max_bar_width) if max_count else 0
        bar = "█" * bar_len + "░" * (max_bar_width - bar_len)
        console.print(f"  {bloom_labels[level]}: [bold yellow]{bar}[/bold yellow] ({cnt:2d}) {pct:5.1f}%")

    console.print("\n[bold cyan]Distribución por Temas:[/bold cyan]")
    sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
    max_t_count = max(theme_counts.values()) or 1
    for t_name, cnt in sorted_themes[:8]:
        pct = (cnt / total) * 100 if total else 0
        bar_len = int((cnt / max_t_count) * 20)
        bar = "■" * bar_len
        console.print(f"  {t_name:20s}: [cyan]{bar}[/cyan] ({cnt:2d}) {pct:5.1f}%")
    console.print("")


@app.command("lint")
@bank_app.command("lint")
def cmd_lint(
    patron: Optional[str] = typer.Argument(None, help="Patrón o ID de ejercicio específico a auditar."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
) -> None:
    """Verifica que los metadatos y el starter_code de los ejercicios compilen limpiamente antes de exportar."""
    import tempfile

    ejs = buscar_ejercicios(banco, patron=patron, recursivo=True)
    if not ejs:
        console.print(f"[yellow]No se encontraron ejercicios para auditar en {banco}[/yellow]")
        return

    tabla = Table(title=f"Deckard Linter — {len(ejs)} ejercicio(s)")
    tabla.add_column("ID", style="cyan")
    tabla.add_column("Esquema", justify="center")
    tabla.add_column("Starter Code", justify="center")
    tabla.add_column("Tests", justify="center")
    tabla.add_column("Diagnóstico / Observaciones")

    errores = 0
    for dir_ej, ej in ejs:
        issues = []
        esquema_ok = True
        if not ej.titulo:
            issues.append("Falta título")
            esquema_ok = False
        if not ej.tema:
            issues.append("Falta tema")
            esquema_ok = False
        if ej.minutos_estimados <= 0:
            issues.append("Minutos inválidos")
            esquema_ok = False

        # Verificación de compilación de starter_code
        starter_ok = True
        starter_code = ej.starter_code or ""
        if starter_code.strip():
            with tempfile.NamedTemporaryFile(suffix=".c", mode="w", encoding="utf-8", delete=False) as tmp:
                code = starter_code
                tmp.write(code)
                tmp_p = Path(tmp.name)

            try:
                gcc_bin = shutil.which("gcc")
                daedalus_bin = shutil.which("daedalus")
                if daedalus_bin:
                    p = subprocess.run(
                        [daedalus_bin, "compile", str(tmp_p), "--flags", "-c -Wno-unused-parameter -Wno-unused-variable"],
                        capture_output=True,
                        text=True,
                    )
                    starter_ok = (p.returncode == 0)
                    if not starter_ok:
                        issues.append(f"Starter code (daedalus): {p.stderr.strip()[:60] or p.stdout.strip()[:60]}")
                elif gcc_bin:
                    p = subprocess.run(
                        [gcc_bin, "-std=c11", "-Wall", "-Wextra", "-Wno-unused-parameter", "-Wno-unused-variable", "-c", str(tmp_p), "-o", "/dev/null"],
                        capture_output=True,
                        text=True,
                    )
                    starter_ok = (p.returncode == 0)
                    if not starter_ok:
                        issues.append(f"Starter code (gcc): {p.stderr.strip()[:60]}")
            finally:
                if tmp_p.exists():
                    tmp_p.unlink()

        tests_dir = dir_ej / "tests"
        has_tests = tests_dir.is_dir() and any(tests_dir.glob("*.in"))
        tests_str = "[green]✓[/green]" if has_tests else "[dim]—[/dim]"

        if not esquema_ok or not starter_ok:
            errores += 1

        esquema_str = "[green]OK[/green]" if esquema_ok else "[red]FALLÓ[/red]"
        starter_str = "[green]OK[/green]" if starter_ok else "[red]FALLÓ[/red]"
        diag_str = "; ".join(issues) if issues else "[green]Conforme[/green]"

        tabla.add_row(ej.id, esquema_str, starter_str, tests_str, diag_str)

    console.print(tabla)
    if errores > 0:
        console.print(f"\n[bold red]✖ Se detectaron problemas en {errores} ejercicio(s).[/bold red]\n")
        raise typer.Exit(code=1)
    else:
        console.print(f"\n[bold green]✓ Todos los ejercicios auditaron limpiamente sin errores.[/bold green]\n")


@app.command("duplicate")
@bank_app.command("duplicate")
def cmd_duplicate(
    origen_id: str = typer.Argument(..., help="ID o slug del ejercicio original a clonar."),
    nuevo_id: str = typer.Argument(..., help="Nuevo ID o slug para la copia."),
    titulo: Optional[str] = typer.Option(None, "--titulo", "-t", help="Nuevo título para el ejercicio clonado."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
) -> None:
    """Clona y versiona variantes de ejercicios conservando enunciados, solución y tests."""

    matches = buscar_ejercicios(banco, patron=origen_id, recursivo=True)
    if not matches:
        console.print(f"[bold red]No se encontró el ejercicio '{origen_id}' en {banco}[/bold red]")
        raise typer.Exit(code=1)

    dir_orig, ej_orig = matches[0]
    dir_dest = dir_orig.parent / nuevo_id
    if dir_dest.exists():
        console.print(f"[bold red]El directorio destino '{dir_dest}' ya existe.[/bold red]")
        raise typer.Exit(code=1)

    shutil.copytree(dir_orig, dir_dest)
    yaml_file = dir_dest / "ejercicio.yaml"
    if not yaml_file.exists():
        yaml_file = dir_dest / "ejercicio.yml"

    data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
    data["id"] = nuevo_id
    if titulo:
        data["titulo"] = titulo
    else:
        data["titulo"] = f"{data.get('titulo', origen_id)} (Variante)"
    data["verificado"] = False

    yaml_file.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    console.print(f"[bold green]✓ Ejercicio clonado exitosamente:[/bold green] [cyan]{nuevo_id}[/cyan]")
    console.print(f"  • Origen:  [dim]{dir_orig}[/dim]")
    console.print(f"  • Destino: [bold]{dir_dest}[/bold]")


@app.command("deps")
@app.command("graph")
@bank_app.command("deps")
def cmd_deps(
    patron: Optional[str] = typer.Argument(None, help="Filtrar por ID o patrón de ejercicios."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    mermaid: bool = typer.Option(False, "--mermaid", "-m", help="Emitir salida en formato Mermaid para documentación."),
) -> None:
    """Detecta y grafica dependencias conceptuales y grafo de prerrequisitos entre ejercicios."""
    from deckard.core.deps import build_dependency_graph
    from rich.markup import escape

    ejs = buscar_ejercicios(banco, patron=patron, recursivo=True)
    if not ejs:
        console.print(f"[yellow]No se encontraron ejercicios en {banco}[/yellow]")
        return

    graph = build_dependency_graph(ejs)
    if mermaid:
        console.print(graph.to_mermaid())
    else:
        console.print(f"\n[bold green]🌲 Grafo de Dependencias Conceptuales ({len(graph.nodes)} ejercicios)[/bold green]\n")
        console.print(escape(graph.to_ascii()))
        console.print("\n[dim]Para emitir formato Mermaid: deckard deps --mermaid[/dim]\n")


@app.command("cache")
@app.command("index")
@bank_app.command("index")
def cmd_cache_index(
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco a indexar."),
    force: bool = typer.Option(False, "--force", "-f", help="Reconstruir la base de datos de índice desde cero."),
) -> None:
    """Actualiza o reconstruye el índice SQLite (~/.cache/deckard/index.db) para acelerar búsquedas en bancos masivos."""
    from deckard.core.cache import update_bank_cache, get_cache_db_path
    count = update_bank_cache(banco, force=force)
    db_p = get_cache_db_path()
    console.print(f"[bold green]✓ Caché SQLite actualizado:[/bold green] {count} ejercicio(s) indexados/actualizados.")
    console.print(f"  ↳ Base de datos: [dim]{db_p}[/dim]")


@app.command("unpack")
def cmd_unpack(
    paquete: Path = typer.Argument(..., help="Ruta al archivo .deckard.tar.gz o .tar.gz a desempaquetar."),
    destino: Path = typer.Option(Path("banco"), "--destino", "-d", help="Directorio destino donde extraer los ejercicios."),
) -> None:
    """Extrae un bundle .deckard.tar.gz en el banco o directorio especificado."""
    from deckard.core.pack import desempaquetar_bundle_deckard
    try:
        out = desempaquetar_bundle_deckard(paquete, destino)
        console.print(f"[bold green]✓ Paquete extraído con éxito en:[/bold green] {out}")
    except Exception as e:
        console.print(f"[bold red]Error al desempaquetar:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("doctor")
def cmd_doctor(
    json_output: bool = typer.Option(False, "--json", help="Emitir el diagnóstico como JSON (schema_version 1.0.0)."),
) -> None:
    """Verifica dependencias externas del sistema (GCC, Typst, Daedalus, Git)."""
    from deckard.core.doctor import diagnosticar, ejecutar_diagnostico_doctor, informe_json
    if json_output:
        import json

        informe = informe_json(diagnosticar())
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        if not informe["ok"]:
            raise typer.Exit(code=1)
        return
    ok = ejecutar_diagnostico_doctor(console=console)
    if not ok:
        raise typer.Exit(code=1)


@app.command("browse")
@bank_app.command("browse")
def cmd_browse(
    patron: Optional[str] = typer.Argument(None, help="Filtro de búsqueda por ID o tema."),
    ejercicio_id: Optional[str] = typer.Option(None, "--id", "-i", help="Mostrar ficha detallada de un ejercicio específico."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Navega y visualiza interactivamente ejercicios del banco con Rich."""
    from deckard.core.browser import mostrar_vista_resumen_ejercicios, mostrar_detalle_ejercicio

    if ejercicio_id:
        matches = buscar_ejercicios(banco, patron=ejercicio_id, recursivo=True)
        if not matches:
            console.print(f"[bold red]No se encontró el ejercicio '{ejercicio_id}'.[/bold red]")
            raise typer.Exit(code=1)
        dir_p, ej = matches[0]
        mostrar_detalle_ejercicio(ej, dir_p, console=console)
        return

    ejs = buscar_ejercicios(banco, patron=patron, recursivo=True)
    if not ejs:
        console.print(f"[yellow]No se encontraron ejercicios en '{banco}'.[/yellow]")
        return
    mostrar_vista_resumen_ejercicios(ejs, console=console)




@bank_app.command("schema")
def cmd_bank_schema(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Archivo donde guardar el JSON Schema (si no, se imprime)."),
) -> None:
    """JSON Schema de ejercicio.yaml, para que el editor valide mientras se escribe."""
    import json as _json

    from deckard.core.esquema import esquema_json

    texto = _json.dumps(esquema_json(), indent=2, ensure_ascii=False) + "\n"
    if output:
        output.write_text(texto, encoding="utf-8")
        console.print(f"[green]✓ Esquema guardado en {output}[/green]")
    else:
        print(texto, end="")
