"""CLI de deckard: banco de ejercicios, guías, verificación, fuzzing y exportación multiformato."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import List, Optional

from rich.console import Console
from rich.markdown import Markdown
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
import yaml

from deckard.core.bank import (
    actualizar_verificacion,
    buscar_ejercicios,
    componer_guia,
    cargar_ejercicio,
    guardar_ejercicio,
    listar_ejercicios,
)
from deckard.core.export import (
    FormatoExport,
    buscar_plantilla,
    cargar_tests_ejercicio,
    compilar_pdf,
    inicializar_plantillas,
    renderizar_ejercicio_html,
    renderizar_ejercicio_md,
    renderizar_guia_html,
    renderizar_guia_md,
)
from deckard.core.guides import (
    InfoGuia,
    agregar_ejercicio_a_guia,
    cargar_guia_con_ejercicios,
    cargar_spec,
    cargar_yaml_guia,
    guardar_spec,
    guardar_yaml_guia,
    inspeccionar_guia,
    listar_guias,
    listar_specs,
    remover_ejercicio_de_guia,
    validar_spec,
)
from deckard.core.models import Ejercicio, GuiaSpec, NivelBloom
from deckard.core.verify import verificar_ejercicio

app = typer.Typer(
    name="deckard",
    help="Gestor de bancos de ejercicios prácticos, guías y graduación (Programación 1).",
    no_args_is_help=True,
)
console = Console()


def _leer_yaml(ruta: Path) -> dict:
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _ejecutar_herramienta(comando: str) -> int:
    """Corre un comando externo heredando consola; avisa si no está instalado."""
    import shutil as _shutil
    binario = comando.split()[0]
    if _shutil.which(binario) is None:
        console.print(f"[red]'{binario}' no está instalado.[/red]")
        return 127
    return subprocess.call(comando, shell=True)


# ---------------------------------------------------------------------------
# init / new
# ---------------------------------------------------------------------------


@app.command()
def init(banco: Path = typer.Argument(Path("."), help="Directorio raíz del banco.")) -> None:
    """Inicializa la estructura del banco (banco/, guias/)."""
    (banco / "banco").mkdir(parents=True, exist_ok=True)
    (banco / "guias").mkdir(parents=True, exist_ok=True)
    ejemplo = banco / "banco" / "ejemplo-invertir"
    if not ejemplo.exists():
        guardar_ejercicio(Ejercicio(
            id="ejemplo-invertir", titulo="Invertir un arreglo",
            tema="arreglos", bloom=NivelBloom.APLICAR, minutos_estimados=20,
            enunciado_md="Leer N y N enteros; imprimirlos en orden inverso.",
            solucion_c=(
                "#include <stdio.h>\nint main(void){\n"
                "    long n; if(scanf(\"%ld\",&n)!=1||n<1||n>100000) return 1;\n"
                "    long v[100000];\n"
                "    for(long i=0;i<n;i++) scanf(\"%ld\", &v[i]);\n"
                "    for(long i=n-1;i>=0;i--) printf(\"%ld%c\", v[i], i? ' ':'\\n');\n"
                "    return 0;\n}\n"
            ),
            pistas=["Pensá qué índice corresponde al último elemento.",
                    "Un solo ciclo de impresión alcanza."],
            tags=["arreglos", "basico"],
        ), banco / "banco")
    console.print(f"[green]✓ Banco inicializado[/green] en {banco.resolve()}")


@app.command("new")
def nuevo_ejercicio(
    eid: str = typer.Argument(..., help="Identificador corto (a-z0-9-)."),
    titulo: str = typer.Option(..., "--titulo"),
    tema: str = typer.Option(..., "--tema"),
    bloom: int = typer.Option(3, "--bloom", min=1, max=5),
    minutos: int = typer.Option(20, "--minutos", min=1),
    banco: Path = typer.Option(Path("banco"), "--banco"),
) -> None:
    """Crea un ejercicio nuevo con esqueleto de metadata y solución."""
    ejercicio = Ejercicio(
        id=eid, titulo=titulo, tema=tema,
        bloom=NivelBloom(bloom), minutos_estimados=minutos,
        enunciado_md=f"# {titulo}\n\n(Completar enunciado)\n",
        solucion_c="#include <stdio.h>\n\nint main(void) {\n    /* TODO */\n    return 0;\n}\n",
    )
    destino = guardar_ejercicio(ejercicio, banco)
    console.print(f"[green]✓ Ejercicio creado[/green] en {destino}")
    console.print("Editá [bold]ejercicio.yaml[/bold] y [bold]solucion.c[/bold], luego corré [bold]deckard verify[/bold].")


# ---------------------------------------------------------------------------
# bank app (list / show)
# ---------------------------------------------------------------------------

bank_app = typer.Typer(name="bank", help="Inspección del banco de ejercicios.", no_args_is_help=True)
app.add_typer(bank_app, name="bank")


@bank_app.command("list")
def bank_list(
    patron: Optional[str] = typer.Argument(None, help="Filtro o comodín (ej: 'invertir-*', 'punteros/*')."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-t", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", min=1, max=5, help="Filtrar por nivel de Bloom (1-5)."),
    verificado: Optional[bool] = typer.Option(None, "--verificado/--no-verificado", help="Filtrar por estado de verificación."),
) -> None:
    """Lista los ejercicios del banco con su nivel, carga y filtros."""
    items = buscar_ejercicios(banco, patron=patron, tema=tema, bloom=bloom, verificado=verificado)
    tabla = Table(title=f"Banco de ejercicios ({len(items)} encontrados)")
    tabla.add_column("id", style="cyan")
    tabla.add_column("tema")
    tabla.add_column("bloom", justify="center")
    tabla.add_column("min", justify="right")
    tabla.add_column("verificado", justify="center")
    total_min = 0
    verificados_count = 0
    for _, e in items:
        total_min += e.minutos_estimados
        if e.verificado:
            verificados_count += 1
        tabla.add_row(e.id, e.tema, f"B{int(e.bloom)} {e.bloom.name.lower()}",
                      str(e.minutos_estimados), "✓" if e.verificado else "—")
    console.print(tabla)
    pct = (verificados_count / len(items) * 100) if items else 0
    console.print(f"[dim]{total_min} minutos totales ({total_min/60:.1f}h) · Verificados: {verificados_count}/{len(items)} ({pct:.0f}%)[/dim]")


# ---------------------------------------------------------------------------
# show (Ver enunciado y secciones)
# ---------------------------------------------------------------------------


@app.command("show")
@bank_app.command("show")
def show_ejercicio(
    ejercicio_id: str = typer.Argument(..., help="Id del ejercicio o ruta al directorio del ejercicio."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    enunciado: bool = typer.Option(True, "--enunciado/--no-enunciado", "-e", help="Mostrar enunciado."),
    solucion: bool = typer.Option(False, "--solucion", "-s", help="Mostrar solución modelo en C."),
    pistas: bool = typer.Option(False, "--pistas", "-p", help="Mostrar pistas progresivas."),
    meta: bool = typer.Option(True, "--meta/--no-meta", "-m", help="Mostrar panel de metadatos."),
    tests: bool = typer.Option(False, "--tests", "-t", help="Mostrar casos de prueba tests/."),
    todos: bool = typer.Option(False, "--todos", "-a", help="Mostrar todas las secciones."),
    raw: bool = typer.Option(False, "--raw", help="Salida en texto plano sin formato Rich."),
) -> None:
    """Muestra el enunciado y detalles de un ejercicio con control de secciones."""
    if todos:
        enunciado = solucion = pistas = meta = tests = True

    matches = buscar_ejercicios(banco, patron=ejercicio_id, recursivo=True)
    if not matches:
        p = Path(ejercicio_id)
        if (p / "ejercicio.yaml").is_file():
            dir_ej = p
            ej = cargar_ejercicio(p)
        else:
            console.print(f"[red]No se encontró el ejercicio '{ejercicio_id}'.[/red]")
            raise typer.Exit(code=1)
    else:
        dir_ej, ej = matches[0]

    if raw:
        if meta:
            print(f"ID: {ej.id}\nTitulo: {ej.titulo}\nTema: {ej.tema}\nBloom: B{int(ej.bloom)}\nMinutos: {ej.minutos_estimados}\nVerificado: {ej.verificado}")
        if enunciado:
            print(f"\n--- ENUNCIADO ---\n{ej.enunciado_md}")
        if pistas and ej.pistas:
            print("\n--- PISTAS ---")
            for i, p in enumerate(ej.pistas, 1):
                print(f"{i}. {p}")
        if tests:
            casos = cargar_tests_ejercicio(dir_ej)
            if casos:
                print("\n--- TESTS ---")
                for c in casos:
                    print(f"[{c['nombre']}]\nIN:\n{c['entrada']}\nOUT:\n{c['salida']}\n")
        if solucion and ej.solucion_c:
            print(f"\n--- SOLUCION ---\n{ej.solucion_c}")
        return

    if meta:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold")
        grid.add_column()
        grid.add_row("Tema:", ej.tema)
        grid.add_row("Bloom:", f"B{int(ej.bloom)} {ej.bloom.name.lower()}")
        grid.add_row("Carga estimada:", f"~{ej.minutos_estimados} min")
        grid.add_row("Verificado:", "[green]✓ Sí[/green]" if ej.verificado else "[dim]— No[/dim]")
        if ej.tags:
            grid.add_row("Tags:", ", ".join(ej.tags))
        console.print(Panel(grid, title=f"[bold cyan]{ej.id}[/bold cyan] — {ej.titulo}", border_style="blue"))

    if enunciado:
        console.print(Markdown(ej.enunciado_md))

    if pistas and ej.pistas:
        texto_pistas = "\n".join(f"[bold]{i}.[/bold] {p}" for i, p in enumerate(ej.pistas, 1))
        console.print(Panel(texto_pistas, title="💡 Pistas Progresivas", border_style="yellow"))

    if tests:
        casos = cargar_tests_ejercicio(dir_ej)
        if casos:
            tabla_t = Table(title="🧪 Casos de Prueba (tests/)")
            tabla_t.add_column("Caso", style="cyan")
            tabla_t.add_column("Entrada (.in)")
            tabla_t.add_column("Salida (.out)")
            for c in casos:
                tabla_t.add_row(c["nombre"], c["entrada"].strip(), c["salida"].strip())
            console.print(tabla_t)
        else:
            console.print("[dim]No se encontraron casos de prueba en tests/.[/dim]")

    if solucion and ej.solucion_c:
        console.print(Panel(
            Syntax(ej.solucion_c, "c", theme="monokai", line_numbers=True),
            title="✓ Solución Modelo de Cátedra",
            border_style="green",
        ))


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


@app.command()
def verify(
    ejercicio_id: Optional[str] = typer.Argument(None, help="Id del ejercicio o patrón comodín (ej: '*', 'invertir-*')."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    all_exercises: bool = typer.Option(False, "--all", "-a", help="Verificar todos los ejercicios del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-t", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", min=1, max=5, help="Filtrar por nivel de Bloom (1-5)."),
    pendientes: bool = typer.Option(False, "--pendientes", "-p", help="Verificar solo ejercicios pendientes."),
    guardar: bool = typer.Option(True, "--guardar/--no-guardar", help="Persistir veredicto en ejercicio.yaml."),
    ripley: Optional[str] = typer.Option(None, "--ripley", help="Ruta al binario/zipapp de ripley."),
) -> None:
    """Verifica la solución modelo de ejercicios usando ripley check."""
    if ejercicio_id is None and not all_exercises and not tema and not bloom and not pendientes:
        console.print("[yellow]Especificá un id de ejercicio, un patrón comodín (ej: '*') o usá --all para verificar todo el banco.[/yellow]")
        raise typer.Exit(code=1)

    pat = "*" if (all_exercises and not ejercicio_id) else ejercicio_id
    verif_filtro = False if pendientes else None
    candidatos = buscar_ejercicios(banco, patron=pat, tema=tema, bloom=bloom, verificado=verif_filtro)

    if not candidatos:
        console.print(f"[red]No se encontraron ejercicios en '{banco}' con el criterio especificado.[/red]")
        raise typer.Exit(code=1)

    es_unico_puntual = len(candidatos) == 1 and pat and not any(c in pat for c in "*?[]") and not all_exercises
    if es_unico_puntual:
        dir_ej, _ = candidatos[0]
        resultado = verificar_ejercicio(dir_ej, ruta_ripley=ripley)
        if guardar and (dir_ej / "ejercicio.yaml").is_file():
            actualizar_verificacion(dir_ej, resultado.ok)
        color = "green" if resultado.ok else "red"
        console.print(f"[{color}]{resultado.marca} {resultado.ejercicio}[/{color}] — {resultado.detalle}")
        raise typer.Exit(code=0 if resultado.ok else 1)

    console.print(f"[bold]Verificando {len(candidatos)} ejercicios con ripley...[/bold]")
    tabla = Table(title="Resultados de verificación")
    tabla.add_column("Ejercicio", style="cyan")
    tabla.add_column("Tema")
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Veredicto", justify="center")
    tabla.add_column("Detalle")

    total_ok = 0
    for dir_ej, ej in candidatos:
        res = verificar_ejercicio(dir_ej, ruta_ripley=ripley)
        if guardar and (dir_ej / "ejercicio.yaml").is_file():
            actualizar_verificacion(dir_ej, res.ok)
        if res.ok:
            total_ok += 1
            veredicto_str = "[green]✓ OK[/green]"
        else:
            veredicto_str = "[red]✗ Fallo[/red]"
        tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", veredicto_str, res.detalle)

    console.print(tabla)
    color_resumen = "green" if total_ok == len(candidatos) else "yellow" if total_ok > 0 else "red"
    console.print(f"[{color_resumen}]Verificación completada: {total_ok}/{len(candidatos)} exitosos[/{color_resumen}]")
    raise typer.Exit(code=0 if total_ok == len(candidatos) else 1)


# ---------------------------------------------------------------------------
# compose
# ---------------------------------------------------------------------------


@app.command()
def compose(
    spec_file: Path = typer.Argument(..., exists=True, help="guia.yaml con nombre/duración/temas."),
    banco: Path = typer.Option(Path("banco"), "--banco"),
) -> None:
    """Compone una guía balanceada por carga cognitiva y taxonomía de Bloom."""
    spec = GuiaSpec(**_leer_yaml(spec_file))
    seleccion = componer_guia(banco, spec)

    tabla = Table(title=f"{seleccion.guia} — {len(seleccion.ejercicios)} ejercicios · "
                        f"{seleccion.minutos_totales}/{int(spec.duracion_min * spec.margen_carga)} min útiles")
    tabla.add_column("#", justify="right")
    tabla.add_column("ejercicio", style="cyan")
    tabla.add_column("tema")
    tabla.add_column("bloom", justify="center")
    tabla.add_column("min", justify="right")
    for i, e in enumerate(seleccion.ejercicios, 1):
        tabla.add_row(str(i), e.id, e.tema, f"B{int(e.bloom)}", str(e.minutos_estimados))
    console.print(tabla)
    console.print(f"Distribución Bloom: {seleccion.distribucion_bloom}")

    salida = Path("guias") / f"{spec.nombre.replace(' ', '_').lower()}.yaml"
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "nombre": seleccion.guia,
            "minutos_totales": seleccion.minutos_totales,
            "distribucion_bloom": seleccion.distribucion_bloom,
            "ejercicios": [{"id": e.id, "minutos": e.minutos_estimados,
                            "bloom": int(e.bloom), "tema": e.tema}
                           for e in seleccion.ejercicios],
        }, f, allow_unicode=True, sort_keys=False)
    console.print(f"[green]✓ Guía escrita[/green] en {salida}")


# ---------------------------------------------------------------------------
# fuzz
# ---------------------------------------------------------------------------


def _escribir_log_fallos(
    ruta_log: Path,
    fallos: List[dict],
    total_analizados: int,
    total_exitos: int,
    total_omitidos: int,
    total_fallos: int,
) -> None:
    from datetime import datetime
    ruta_log = Path(ruta_log)
    ruta_log.parent.mkdir(parents=True, exist_ok=True)

    lineas = [
        "# Reporte de Fallos de Fuzzing — Deckard",
        f"- **Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Total analizados:** {total_analizados}",
        f"- **Exitosos:** {total_exitos}",
        f"- **Omitidos:** {total_omitidos}",
        f"- **Fallidos:** {total_fallos}",
        "",
        "---",
        "",
    ]
    if not fallos:
        lineas.append("No se registraron fallos durante la ejecución.\n")
    else:
        lineas.append("## Detalle de Ejercicios Afectados\n")
        for f in fallos:
            lineas.append(f"### `{f['id']}` ({f.get('tipo', 'Fallo')})")
            lineas.append(f"- **Tema:** {f.get('tema', '—')}")
            lineas.append(f"- **Directorio:** `{f['dir']}`")
            lineas.append(f"- **Estado en banco:** Marcado como no-verificado (`verificado: false`)")
            lineas.append("- **Detalle del error / salida:**")
            lineas.append("```")
            lineas.append(f.get("error", "Error no especificado"))
            lineas.append("```\n")

    ruta_log.write_text("\n".join(lineas), encoding="utf-8")


@app.command("fuzz")
def fuzz(
    ejercicio_id: Optional[str] = typer.Argument(None, help="Id del ejercicio o patrón comodín (ej: '*', 'invertir-*', 'punteros/*')."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    all_exercises: bool = typer.Option(False, "--all", "-a", help="Ejecutar fuzzing sobre todos los ejercicios del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-t", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", min=1, max=5, help="Filtrar por nivel de Bloom (1-5)."),
    cantidad: int = typer.Option(8, "--cantidad", "-n", help="Cantidad de testcases a generar por ejercicio."),
    segundos: int = typer.Option(15, "--segundos", help="Segundos de fuzzing si libFuzzer está disponible."),
    sin_libfuzzer: bool = typer.Option(False, "--sin-libfuzzer", help="Forzar modo determinista sin libFuzzer."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Detenerse inmediatamente ante el primer error."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Solo listar ejercicios que se procesarían sin ejecutar."),
    log_fallos: Optional[Path] = typer.Option(None, "--log-fallos", "-l", help="Ruta de archivo para guardar el reporte de ejercicios fallidos u omitidos."),
) -> None:
    """Endurece los tests de ejercicios usando `dredd fuzz-gen` (soporta wildcards, batch y tracking de progreso)."""
    import shutil as _shutil
    if _shutil.which("dredd") is None:
        console.print("[red]'dredd' no está instalado en el PATH.[/red]")
        raise typer.Exit(code=127)

    if ejercicio_id is None and not all_exercises and not tema and not bloom:
        console.print("[yellow]Especificá un id de ejercicio, un patrón comodín (ej: '*') o usá --all para todo el banco.[/yellow]")
        raise typer.Exit(code=1)

    pat = "*" if (all_exercises and not ejercicio_id) else ejercicio_id
    candidatos = buscar_ejercicios(banco, patron=pat, tema=tema, bloom=bloom)

    if not candidatos:
        console.print(f"[red]No se encontraron ejercicios en '{banco}' con el criterio especificado.[/red]")
        raise typer.Exit(code=1)

    if dry_run:
        tabla = Table(title=f"Ejercicios seleccionados para fuzz ({len(candidatos)})")
        tabla.add_column("id", style="cyan")
        tabla.add_column("tema")
        tabla.add_column("bloom", justify="center")
        tabla.add_column("solucion.c", justify="center")
        for dir_ej, ej in candidatos:
            tiene_sol = (dir_ej / "solucion.c").is_file()
            tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", "✓" if tiene_sol else "[red]✗[/red]")
        console.print(tabla)
        return

    es_unico_puntual = len(candidatos) == 1 and pat and not any(c in pat for c in "*?[]") and not all_exercises
    if es_unico_puntual:
        dir_ej, ej = candidatos[0]
        modelo = dir_ej / "solucion.c"
        if not modelo.is_file():
            actualizar_verificacion(dir_ej, False)
            if log_fallos:
                _escribir_log_fallos(
                    log_fallos,
                    [{"id": ej.id, "tema": ej.tema, "dir": dir_ej, "tipo": "Omitido", "error": "No tiene solucion.c"}],
                    1, 0, 1, 0
                )
            console.print(f"[red]El ejercicio '{ej.id}' no tiene solucion.c en {dir_ej}[/red] (marcado como no-verificado)")
            raise typer.Exit(code=1)

        destino = dir_ej / "tests"
        flag_libfuzzer = " --sin-libfuzzer" if sin_libfuzzer else ""
        cmd = (f"dredd fuzz-gen {modelo} -o {destino} --cantidad {cantidad} "
               f"--segundos {segundos}{flag_libfuzzer}")
        console.print(f"[dim]$ {cmd}[/dim]")
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        rc = proc.returncode
        if rc == 0:
            console.print("[green]✓ Testcases endurecidos. Recordá marcar 'verificado' tras re-correr deckard verify.[/green]")
        else:
            actualizar_verificacion(dir_ej, False)
            console.print(f"[red]✗ Fallo en fuzzing para '{ej.id}'. Marcado como no-verificado.[/red]")
            if proc.stderr:
                console.print(f"[dim]{proc.stderr.strip()}[/dim]")
            if log_fallos:
                _escribir_log_fallos(
                    log_fallos,
                    [{"id": ej.id, "tema": ej.tema, "dir": dir_ej, "tipo": "Fallo", "error": proc.stderr.strip() or f"Código {rc}"}],
                    1, 0, 0, 1
                )
        raise typer.Exit(code=rc)

    # Modo masivo / wildcard con barra de progreso
    console.print(f"[bold]Ejecutando fuzz-gen sobre {len(candidatos)} ejercicios...[/bold]")
    tabla = Table(title="Resultados de fuzzing")
    tabla.add_column("Ejercicio", style="cyan")
    tabla.add_column("Tema")
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Estado", justify="center")
    tabla.add_column("Testcases / Detalle")

    total_exitos = 0
    total_omitidos = 0
    total_fallos = 0
    fallos_info = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Fuzzing ejercicios...", total=len(candidatos))

        for dir_ej, ej in candidatos:
            progress.update(task, description=f"[cyan]Fuzzing: [bold]{ej.id}[/bold]")
            modelo = dir_ej / "solucion.c"

            if not modelo.is_file():
                actualizar_verificacion(dir_ej, False)
                tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", "[yellow]⚠ Omitido[/yellow]", "Sin solucion.c (no-verificado)")
                total_omitidos += 1
                fallos_info.append({
                    "id": ej.id,
                    "tema": ej.tema,
                    "dir": dir_ej,
                    "tipo": "Omitido",
                    "error": "No tiene archivo solucion.c",
                })
                progress.advance(task)
                if fail_fast:
                    break
                continue

            destino = dir_ej / "tests"
            flag_libfuzzer = " --sin-libfuzzer" if sin_libfuzzer else ""
            cmd = (f"dredd fuzz-gen {modelo} -o {destino} --cantidad {cantidad} "
                   f"--segundos {segundos}{flag_libfuzzer}")

            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if proc.returncode == 0:
                total_exitos += 1
                casos_in = list(destino.glob("*.in")) if destino.is_dir() else []
                tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", "[green]✓ Generado[/green]", f"{len(casos_in)} testcases en tests/")
            else:
                total_fallos += 1
                actualizar_verificacion(dir_ej, False)
                err_line = next((l for l in reversed(proc.stderr.strip().splitlines()) if l.strip()), "Error de ejecución")
                tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", "[red]✗ Fallo[/red]", f"{err_line[:60]} (no-verificado)")
                fallos_info.append({
                    "id": ej.id,
                    "tema": ej.tema,
                    "dir": dir_ej,
                    "tipo": "Fallo",
                    "error": proc.stderr.strip() or f"Código de retorno {proc.returncode}",
                })
                if fail_fast:
                    progress.advance(task)
                    break

            progress.advance(task)

    console.print(tabla)
    console.print(f"\n[bold]Resumen:[/bold] [green]{total_exitos} completados[/green] · "
                  f"[yellow]{total_omitidos} omitidos[/yellow] · [red]{total_fallos} fallidos[/red]")

    if log_fallos:
        _escribir_log_fallos(log_fallos, fallos_info, len(candidatos), total_exitos, total_omitidos, total_fallos)
        console.print(f"[yellow]📝 Reporte de fallos guardado en:[/yellow] {log_fallos}")

    raise typer.Exit(code=0 if total_fallos == 0 else 1)



# ---------------------------------------------------------------------------
# export (Exportación multiformato: PDF, MD, HTML) + init-templates
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# export (Exportación multiformato: PDF, MD, HTML) + init-templates
# ---------------------------------------------------------------------------


class ExportGroup(typer.core.TyperGroup):
    """Permite ejecutar 'deckard export <objetivo>' directamente o subcomandos como 'deckard export init-templates'."""

    def resolve_command(self, ctx, args):
        cmd_name = args[0] if args else None
        if cmd_name:
            cmd = self.get_command(ctx, cmd_name)
            if cmd is not None:
                return super().resolve_command(ctx, args)
        return super().resolve_command(ctx, ["run"] + args)


export_app = typer.Typer(
    cls=ExportGroup,
    name="export",
    help="Exportación multiformato (PDF, Markdown, HTML) y gestión de plantillas.",
    no_args_is_help=True,
)
app.add_typer(export_app, name="export")


@export_app.command("init-templates")
@export_app.command("init")
def export_init_templates(
    destino: Path = typer.Argument(Path("templates"), help="Directorio destino para las plantillas."),
    global_config: bool = typer.Option(False, "--global", "-g", help="Instalar en la configuración global de usuario (~/.config/deckard/templates)."),
    sobrescribir: bool = typer.Option(False, "--force", "-f", help="Sobrescribir plantillas existentes."),
) -> None:
    """Inicializa y copia las plantillas (HTML, Markdown y CSS) para personalizarlas."""
    target_dir = Path.home() / ".config" / "deckard" / "templates" if global_config else destino
    creados = inicializar_plantillas(target_dir, sobrescribir=sobrescribir)

    console.print(f"[bold green]✓ Plantillas inicializadas en:[/bold green] {target_dir.resolve()}")
    for p in creados:
        console.print(f"  • [cyan]{p.name}[/cyan] ({p.suffix.upper()})")
    if not creados:
        console.print("  [yellow]Las plantillas ya existían. Usá --force para sobrescribir.[/yellow]")
    console.print("\nPodés editar [bold]estilos.css[/bold], [bold]ejercicio.html[/bold], [bold]ejercicio.md[/bold] o agregar imágenes en este directorio.")


@export_app.command("run", hidden=True)
def exportar_contenido(
    objetivo: str = typer.Argument(..., help="Id de ejercicio, comodín ('*'), o ruta a guía (.yaml)."),
    formato: str = typer.Option("pdf", "--formato", "-f", help="Formato de salida: pdf, md (markdown), html."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Archivo de salida o directorio destino."),
    template: Optional[str] = typer.Option(None, "--template", "-T", help="Nombre o ruta de plantilla personalizada."),
    pipeline_md: bool = typer.Option(False, "--pipeline-md", help="Generar Markdown intermedio antes de compilar PDF."),
    solucion: bool = typer.Option(False, "--solucion", "-s", help="Incluir solución modelo."),
    pistas: bool = typer.Option(False, "--pistas", "-p", help="Incluir pistas progresivas."),
    tests: bool = typer.Option(False, "--tests", "-t", help="Incluir casos de prueba."),
    css: Optional[Path] = typer.Option(None, "--css", exists=True, help="Archivo CSS adicional para PDF/HTML."),
    html_only: bool = typer.Option(False, "--html", help="Atajo para --formato html."),
) -> None:
    """Exporta ejercicios o guías a Markdown, HTML o PDF con plantillas personalizables."""
    fmt = "html" if html_only else formato.lower()
    extra_css_str = css.read_text(encoding="utf-8") if css else None
    ruta_obj = Path(objetivo)

    # Caso 1: Archivo de guía YAML
    if ruta_obj.is_file() and (ruta_obj.suffix in (".yaml", ".yml") or "guia" in ruta_obj.name):
        guia_meta, items = cargar_guia_con_ejercicios(ruta_obj, banco)
        validos = [(d, e) for d, e in items if e is not None]
        if not validos:
            console.print(f"[red]La guía '{objetivo}' no tiene ejercicios válidos en el banco.[/red]")
            raise typer.Exit(code=1)

        if fmt in ("md", "markdown"):
            md_salida, _ = renderizar_guia_md(
                guia_meta=guia_meta,
                ejercicios_con_dir=validos,
                template_nombre_o_ruta=template,
                incluir_soluciones=solucion,
                incluir_pistas=pistas,
                dir_banco=banco,
            )
            dest = salida or Path(f"{ruta_obj.stem}.md")
            dest.write_text(md_salida, encoding="utf-8")
            console.print(f"[green]✓ Guía exportada a Markdown:[/green] {dest}")
            return

        html_salida, base_p = renderizar_guia_html(
            guia_meta=guia_meta,
            ejercicios_con_dir=validos,
            template_nombre_o_ruta=template,
            incluir_soluciones=solucion,
            incluir_pistas=pistas,
            extra_css=extra_css_str,
            dir_banco=banco,
            via_markdown_pipeline=pipeline_md,
        )

        dest = salida or Path(f"{ruta_obj.stem}.{'html' if fmt == 'html' else 'pdf'}")
        if fmt == "html":
            dest.write_text(html_salida, encoding="utf-8")
            console.print(f"[green]✓ Guía exportada a HTML:[/green] {dest}")
            return

        try:
            pdf_path = compilar_pdf(html_salida, dest, base_url=str(base_p) if base_p else ".")
            console.print(f"[green]✓ Guía exportada a PDF:[/green] {pdf_path}")
        except Exception as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1)
        return

    # Caso 2: Ejercicio o comodín de ejercicios
    candidatos = buscar_ejercicios(banco, patron=objetivo, recursivo=True)
    if not candidatos:
        if (ruta_obj / "ejercicio.yaml").is_file():
            candidatos = [(ruta_obj, cargar_ejercicio(ruta_obj))]
        else:
            console.print(f"[red]No se encontró ningún ejercicio que coincida con '{objetivo}'.[/red]")
            raise typer.Exit(code=1)

    if len(candidatos) == 1:
        dir_ej, ej = candidatos[0]

        if fmt in ("md", "markdown"):
            md_salida, _ = renderizar_ejercicio_md(
                ejercicio=ej,
                dir_ejercicio=dir_ej,
                template_nombre_o_ruta=template,
                incluir_meta=True,
                incluir_solucion=solucion,
                incluir_pistas=pistas,
                incluir_tests=tests,
                dir_banco=banco,
            )
            dest = salida or Path(f"{ej.id}.md")
            dest.write_text(md_salida, encoding="utf-8")
            console.print(f"[green]✓ Ejercicio exportado a Markdown:[/green] {dest}")
            return

        html_salida, base_p = renderizar_ejercicio_html(
            ejercicio=ej,
            dir_ejercicio=dir_ej,
            template_nombre_o_ruta=template,
            incluir_solucion=solucion,
            incluir_pistas=pistas,
            incluir_tests=tests,
            extra_css=extra_css_str,
            dir_banco=banco,
            via_markdown_pipeline=pipeline_md,
        )

        dest = salida or Path(f"{ej.id}.{'html' if fmt == 'html' else 'pdf'}")
        if fmt == "html":
            dest.write_text(html_salida, encoding="utf-8")
            console.print(f"[green]✓ Ejercicio exportado a HTML:[/green] {dest}")
            return

        try:
            pdf_path = compilar_pdf(html_salida, dest, base_url=str(base_p) if base_p else ".")
            console.print(f"[green]✓ Ejercicio exportado a PDF:[/green] {pdf_path}")
        except Exception as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1)
    else:
        out_dir = salida or Path(f"dist/{fmt}")
        out_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[bold]Exportando {len(candidatos)} ejercicios a {fmt.upper()} en {out_dir}...[/bold]")

        tabla = Table(title=f"Exportación ({fmt.upper()})")
        tabla.add_column("Ejercicio", style="cyan")
        tabla.add_column("Archivo generado", style="green")

        for dir_ej, ej in candidatos:
            if fmt in ("md", "markdown"):
                md_salida, _ = renderizar_ejercicio_md(
                    ejercicio=ej,
                    dir_ejercicio=dir_ej,
                    template_nombre_o_ruta=template,
                    incluir_meta=True,
                    incluir_solucion=solucion,
                    incluir_pistas=pistas,
                    incluir_tests=tests,
                    dir_banco=banco,
                )
                file_dest = out_dir / f"{ej.id}.md"
                file_dest.write_text(md_salida, encoding="utf-8")
            else:
                html_salida, base_p = renderizar_ejercicio_html(
                    ejercicio=ej,
                    dir_ejercicio=dir_ej,
                    template_nombre_o_ruta=template,
                    incluir_solucion=solucion,
                    incluir_pistas=pistas,
                    incluir_tests=tests,
                    extra_css=extra_css_str,
                    dir_banco=banco,
                    via_markdown_pipeline=pipeline_md,
                )
                if fmt == "html":
                    file_dest = out_dir / f"{ej.id}.html"
                    file_dest.write_text(html_salida, encoding="utf-8")
                else:
                    file_dest = out_dir / f"{ej.id}.pdf"
                    compilar_pdf(html_salida, file_dest, base_url=str(base_p) if base_p else ".")

            tabla.add_row(ej.id, str(file_dest))

        console.print(tabla)
        console.print(f"[green]✓ {len(candidatos)} archivos generados en {out_dir}[/green]")


# ---------------------------------------------------------------------------
# guide app (list, show, new, add, remove, verify, export, pdf)
# ---------------------------------------------------------------------------

guide_app = typer.Typer(name="guide", help="Gestión, inspección y exportación de guías.", no_args_is_help=True)
app.add_typer(guide_app, name="guide")


@guide_app.command("list")
def guide_list(
    guias_dir: Path = typer.Option(Path("guias"), "--guias", "-g", help="Directorio de guías."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
) -> None:
    """Lista las guías existentes en guias/ con métricas y estado de verificación."""
    guias = listar_guias(guias_dir, dir_banco=banco)
    if not guias:
        console.print(f"[yellow]No se encontraron guías en '{guias_dir}'. Creá una con 'deckard compose' o 'deckard guide new'.[/yellow]")
        return

    tabla = Table(title=f"Catálogo de Guías ({len(guias)} encontradas)")
    tabla.add_column("Archivo", style="cyan")
    tabla.add_column("Nombre de Guía")
    tabla.add_column("Tipo", justify="center")
    tabla.add_column("Ejercicios", justify="right")
    tabla.add_column("Duración", justify="right")
    tabla.add_column("Bloom", style="dim")
    tabla.add_column("Verificados", justify="center")

    for g in guias:
        tipo_str = "[dim]spec[/dim]" if g.es_spec else "[blue]compuesta[/blue]"
        cant_str = "—" if g.es_spec else str(g.cantidad_ejercicios)
        dur_str = f"~{g.duracion_minutos} min"
        bloom_str = ", ".join(f"{k}:{v}" for k, v in g.distribucion_bloom.items()) if g.distribucion_bloom else "—"
        verif_str = "—" if g.es_spec else (f"{g.verificados_count}/{g.cantidad_ejercicios} ✓" if g.verificados_count == g.cantidad_ejercicios else f"[yellow]{g.verificados_count}/{g.cantidad_ejercicios}[/yellow]")
        tabla.add_row(g.archivo.name, g.nombre, tipo_str, cant_str, dur_str, bloom_str, verif_str)

    console.print(tabla)


@guide_app.command("show")
def guide_show(
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo YAML de la guía."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
    enunciados: bool = typer.Option(False, "--enunciados", "-e", help="Mostrar enunciados completos."),
    soluciones: bool = typer.Option(False, "--soluciones", "-s", help="Mostrar soluciones modelo."),
    pistas: bool = typer.Option(False, "--pistas", "-p", help="Mostrar pistas progresivas."),
) -> None:
    """Muestra el detalle estructurado de una guía y sus ejercicios."""
    ruta = Path(guia_archivo)
    if not ruta.is_file():
        ruta = guias_dir / guia_archivo
    if not ruta.is_file() and not ruta.suffix:
        ruta = guias_dir / f"{guia_archivo}.yaml"
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    info = inspeccionar_guia(ruta, dir_banco=banco)
    guia_meta, items = cargar_guia_con_ejercicios(ruta, banco)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("Archivo:", str(ruta))
    grid.add_row("Tipo:", "Especificación (spec)" if info.es_spec else "Guía Compuesta")
    grid.add_row("Carga estimada:", f"~{info.duracion_minutos} minutos ({info.duracion_minutos/60:.1f}h)")
    if info.distribucion_bloom:
        grid.add_row("Distribución Bloom:", ", ".join(f"{k}: {v}" for k, v in info.distribucion_bloom.items()))
    if info.temas:
        grid.add_row("Temas:", ", ".join(info.temas))

    console.print(Panel(grid, title=f"[bold blue]{info.nombre}[/bold blue]", border_style="blue"))

    if not info.es_spec and items:
        tabla = Table(title=f"Ejercicios de la guía ({len(items)})")
        tabla.add_column("#", justify="right")
        tabla.add_column("ID", style="cyan")
        tabla.add_column("Título")
        tabla.add_column("Tema")
        tabla.add_column("Bloom", justify="center")
        tabla.add_column("Min", justify="right")
        tabla.add_column("Verificado", justify="center")

        for i, (dir_ej, ej) in enumerate(items, 1):
            if ej:
                tabla.add_row(
                    str(i), ej.id, ej.titulo, ej.tema,
                    f"B{int(ej.bloom)}", str(ej.minutos_estimados),
                    "[green]✓[/green]" if ej.verificado else "[dim]—[/dim]"
                )
            else:
                tabla.add_row(str(i), "[red](no encontrado)[/red]", "—", "—", "—", "—", "✗")
        console.print(tabla)

        if enunciados or soluciones or pistas:
            for i, (dir_ej, ej) in enumerate(items, 1):
                if not ej:
                    continue
                console.print(f"\n[bold underline]Ejercicio {i}: {ej.titulo}[/bold underline] ([cyan]{ej.id}[/cyan])")
                if enunciados:
                    console.print(Markdown(ej.enunciado_md))
                if pistas and ej.pistas:
                    pistas_txt = "\n".join(f"{idx}. {p}" for idx, p in enumerate(ej.pistas, 1))
                    console.print(Panel(pistas_txt, title="💡 Pistas", border_style="yellow"))
                if soluciones and ej.solucion_c:
                    console.print(Panel(
                        Syntax(ej.solucion_c, "c", theme="monokai", line_numbers=True),
                        title="Solución Modelo",
                        border_style="green",
                    ))


@guide_app.command("new")
def guide_new(
    archivo: str = typer.Argument(..., help="Nombre del archivo YAML (ej: 'guia_punteros.yaml')."),
    titulo: str = typer.Option(..., "--titulo", "-t", help="Título descriptivo de la guía."),
    duracion: int = typer.Option(90, "--duracion", "-d", help="Duración estimada en minutos."),
    margen: float = typer.Option(0.8, "--margen", "-m", help="Margen de carga (0.3 - 1.0)."),
    temas: Optional[str] = typer.Option(None, "--temas", help="Temas separados por comas."),
    bloom_min: int = typer.Option(1, "--bloom-min", min=1, max=5),
    bloom_max: int = typer.Option(5, "--bloom-max", min=1, max=5),
    cantidad_max: Optional[int] = typer.Option(None, "--max-ejercicios", "-n"),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Crea una nueva especificación de guía (GuiaSpec) en guias/."""
    guias_dir.mkdir(parents=True, exist_ok=True)
    nombre_f = archivo if archivo.endswith(".yaml") or archivo.endswith(".yml") else f"{archivo}.yaml"
    dest = guias_dir / nombre_f

    lista_temas = [t.strip() for t in temas.split(",") if t.strip()] if temas else []
    datos = {
        "nombre": titulo,
        "duracion_min": duracion,
        "margen_carga": margen,
        "temas": lista_temas,
        "bloom_min": bloom_min,
        "bloom_max": bloom_max,
    }
    if cantidad_max:
        datos["cantidad_maxima"] = cantidad_max

    guardar_yaml_guia(dest, datos)
    console.print(f"[green]✓ Especificación de guía creada en:[/green] {dest}")
    console.print(f"Para componerla automáticamente con el banco: [bold]deckard guide compose {dest}[/bold]")


@guide_app.command("compose")
def guide_compose_cmd(
    spec_file: Path = typer.Argument(..., exists=True, help="guia.yaml con nombre/duración/temas."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
) -> None:
    """Compone una guía balanceada por carga cognitiva y taxonomía de Bloom."""
    compose(spec_file=spec_file, banco=banco)


@guide_app.command("add")
def guide_add(
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo de la guía."),
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio a agregar."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Agrega un ejercicio del banco a una guía compuesta."""
    ruta = Path(guia_archivo)
    if not ruta.is_file():
        ruta = guias_dir / guia_archivo
    if not ruta.is_file() and not ruta.suffix:
        ruta = guias_dir / f"{guia_archivo}.yaml"
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    try:
        datos = agregar_ejercicio_a_guia(ruta, banco, ejercicio_id)
        console.print(f"[green]✓ Ejercicio '{ejercicio_id}' agregado a {ruta}.[/green]")
        console.print(f"  Total ejercicios: {len(datos.get('ejercicios', []))} · Carga total: ~{datos.get('minutos_totales', 0)} min")
    except Exception as e:
        console.print(f"[red]Error al agregar ejercicio: {e}[/red]")
        raise typer.Exit(code=1)


@guide_app.command("remove")
def guide_remove(
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo de la guía."),
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio a remover."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Remueve un ejercicio de una guía compuesta."""
    ruta = Path(guia_archivo)
    if not ruta.is_file():
        ruta = guias_dir / guia_archivo
    if not ruta.is_file() and not ruta.suffix:
        ruta = guias_dir / f"{guia_archivo}.yaml"
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    try:
        datos = remover_ejercicio_de_guia(ruta, ejercicio_id)
        console.print(f"[green]✓ Ejercicio '{ejercicio_id}' removido de {ruta}.[/green]")
        console.print(f"  Total ejercicios: {len(datos.get('ejercicios', []))} · Carga total: ~{datos.get('minutos_totales', 0)} min")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@guide_app.command("verify")
def guide_verify(
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo de la guía."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
    ripley: Optional[str] = typer.Option(None, "--ripley", help="Ruta a ripley."),
) -> None:
    """Verifica con ripley todas las soluciones modelo de los ejercicios de la guía."""
    ruta = Path(guia_archivo)
    if not ruta.is_file():
        ruta = guias_dir / guia_archivo
    if not ruta.is_file() and not ruta.suffix:
        ruta = guias_dir / f"{guia_archivo}.yaml"
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    _, items = cargar_guia_con_ejercicios(ruta, banco)
    if not items:
        console.print(f"[yellow]La guía no contiene ejercicios.[/yellow]")
        return

    tabla = Table(title=f"Verificación de ejercicios: {ruta.name}")
    tabla.add_column("Ejercicio", style="cyan")
    tabla.add_column("Veredicto", justify="center")
    tabla.add_column("Detalle")

    total_ok = 0
    for dir_ej, ej in items:
        if not ej or not dir_ej:
            tabla.add_row("(no encontrado)", "[red]✗ Error[/red]", "Ejercicio faltante en el banco")
            continue
        res = verificar_ejercicio(dir_ej, ruta_ripley=ripley)
        if res.ok:
            total_ok += 1
            v_str = "[green]✓ OK[/green]"
        else:
            v_str = "[red]✗ Fallo[/red]"
        tabla.add_row(ej.id, v_str, res.detalle)

    console.print(tabla)
    color = "green" if total_ok == len(items) else "red"
    console.print(f"[{color}]Verificación de guía finalizada: {total_ok}/{len(items)} exitosos[/{color}]")
    raise typer.Exit(code=0 if total_ok == len(items) else 1)


@guide_app.command("export")
@guide_app.command("pdf")
def guide_export_cmd(
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo de la guía."),
    formato: str = typer.Option("pdf", "--formato", "-f", help="Formato: pdf, md (markdown), html."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Archivo de salida."),
    template: Optional[str] = typer.Option(None, "--template", "-T", help="Plantilla personalizada."),
    pipeline_md: bool = typer.Option(False, "--pipeline-md", help="Generar Markdown intermedio antes de compilar PDF."),
    soluciones: bool = typer.Option(False, "--soluciones", "-s", help="Incluir apéndice de soluciones."),
    pistas: bool = typer.Option(False, "--pistas", "-p", help="Incluir pistas progresivas."),
    css: Optional[Path] = typer.Option(None, "--css", exists=True, help="Archivo CSS adicional."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Exporta la guía completa a PDF, Markdown o HTML."""
    ruta = Path(guia_archivo)
    if not ruta.is_file():
        ruta = guias_dir / guia_archivo
    if not ruta.is_file() and not ruta.suffix:
        ruta = guias_dir / f"{guia_archivo}.yaml"
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    exportar_contenido(
        objetivo=str(ruta),
        formato=formato,
        banco=banco,
        salida=salida,
        template=template,
        pipeline_md=pipeline_md,
        solucion=soluciones,
        pistas=pistas,
        tests=False,
        css=css,
        html_only=False,
    )


# ---------------------------------------------------------------------------
# spec app (list, show, new, edit, validate, compose)
# ---------------------------------------------------------------------------

spec_app = typer.Typer(
    name="spec",
    help="Gestión, validación y composición de especificaciones de guías (GuiaSpec).",
    no_args_is_help=True,
)
app.add_typer(spec_app, name="spec")


def _resolver_ruta_spec(spec_archivo: str, guias_dir: Path) -> Path:
    ruta = Path(spec_archivo)
    if not ruta.is_file():
        ruta = guias_dir / spec_archivo
    if not ruta.is_file() and not ruta.suffix:
        ruta = guias_dir / f"{spec_archivo}.yaml"
    if not ruta.is_file():
        console.print(f"[red]No se encontró el archivo spec '{spec_archivo}'.[/red]")
        raise typer.Exit(code=1)
    return ruta


@spec_app.command("list")
def spec_list(
    guias_dir: Path = typer.Option(Path("guias"), "--guias", "-g", help="Directorio donde se ubican los specs."),
) -> None:
    """Lista todas las especificaciones de guías (GuiaSpec) disponibles."""
    specs = listar_specs(guias_dir)
    if not specs:
        console.print(f"[yellow]No se encontraron specs en '{guias_dir}'. Creá una con 'deckard spec new'.[/yellow]")
        return
    tabla = Table(title=f"Especificaciones de Guías ({len(specs)} encontradas)")
    tabla.add_column("Archivo", style="cyan")
    tabla.add_column("Título")
    tabla.add_column("Duración", justify="right")
    tabla.add_column("Carga Útil", justify="right")
    tabla.add_column("Temas")
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Max Ej.", justify="center")
    for ruta, s in specs:
        util = int(s.duracion_min * s.margen_carga)
        temas_str = ", ".join(s.temas) if s.temas else "(todos)"
        max_ej = str(s.cantidad_maxima) if s.cantidad_maxima else "—"
        tabla.add_row(
            ruta.name,
            s.nombre,
            f"{s.duracion_min} min",
            f"~{util} min ({int(s.margen_carga*100)}%)",
            temas_str,
            f"B{s.bloom_min}..B{s.bloom_max}",
            max_ej,
        )
    console.print(tabla)


@spec_app.command("new")
def spec_new(
    archivo: str = typer.Argument(..., help="Nombre del archivo (ej: 'guia_parcial1.yaml')."),
    titulo: str = typer.Option(..., "--titulo", "-t", help="Título pedagógico de la especificación."),
    duracion: int = typer.Option(90, "--duracion", "-d", help="Duración estimada total en minutos."),
    margen: float = typer.Option(0.8, "--margen", "-m", help="Margen de carga útil (0.1 a 1.0)."),
    temas: Optional[str] = typer.Option(None, "--temas", help="Temas obligatorios separados por comas."),
    bloom_min: int = typer.Option(1, "--bloom-min", min=1, max=5),
    bloom_max: int = typer.Option(5, "--bloom-max", min=1, max=5),
    cantidad_max: Optional[int] = typer.Option(None, "--max-ejercicios", "-n"),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", "-g"),
) -> None:
    """Crea una nueva especificación de guía (GuiaSpec)."""
    guias_dir.mkdir(parents=True, exist_ok=True)
    nombre_f = archivo if archivo.endswith((".yaml", ".yml")) else f"{archivo}.yaml"
    dest = guias_dir / nombre_f
    lista_temas = [t.strip() for t in temas.split(",") if t.strip()] if temas else []
    spec = GuiaSpec(
        nombre=titulo,
        duracion_min=duracion,
        margen_carga=margen,
        temas=lista_temas,
        bloom_min=bloom_min,
        bloom_max=bloom_max,
        cantidad_maxima=cantidad_max,
    )
    guardar_spec(dest, spec)
    console.print(f"[green]✓ Spec creada exitosamente en:[/green] {dest}")
    console.print(f"Podés validarla con [bold]deckard spec validate {dest}[/bold] o componerla con [bold]deckard spec compose {dest}[/bold].")


@spec_app.command("show")
def spec_show(
    spec_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo spec YAML."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Muestra los detalles de una especificación y su universo de ejercicios candidatos en el banco."""
    ruta = _resolver_ruta_spec(spec_archivo, guias_dir)
    spec = cargar_spec(ruta)
    diag = validar_spec(spec, banco)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("Archivo:", str(ruta))
    grid.add_row("Título:", spec.nombre)
    grid.add_row("Duración nominal:", f"{spec.duracion_min} minutos")
    grid.add_row("Presupuesto útil:", f"~{diag['minutos_requeridos']} min (margen: {int(spec.margen_carga*100)}%)")
    grid.add_row("Temas requeridos:", ", ".join(spec.temas) if spec.temas else "(cualquiera)")
    grid.add_row("Rango Bloom:", f"B{spec.bloom_min} a B{spec.bloom_max}")
    if spec.cantidad_maxima:
        grid.add_row("Límite ejercicios:", str(spec.cantidad_maxima))

    console.print(Panel(grid, title=f"[bold cyan]Spec: {spec.nombre}[/bold cyan]", border_style="cyan"))

    candidatos = diag["candidatos"]
    tabla_c = Table(title=f"Candidatos elegibles en el banco ({len(candidatos)} ejercicios · ~{diag['minutos_disponibles']} min disponibles)")
    tabla_c.add_column("ID", style="cyan")
    tabla_c.add_column("Título")
    tabla_c.add_column("Tema")
    tabla_c.add_column("Bloom", justify="center")
    tabla_c.add_column("Min", justify="right")
    tabla_c.add_column("Verificado", justify="center")

    for _, e in candidatos:
        tabla_c.add_row(e.id, e.titulo, e.tema, f"B{int(e.bloom)}", str(e.minutos_estimados), "[green]✓[/green]" if e.verificado else "[dim]—[/dim]")
    console.print(tabla_c)


@spec_app.command("validate")
def spec_validate(
    spec_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo spec YAML."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Verifica si el banco de ejercicios tiene suficientes candidatos para satisfacer el spec."""
    ruta = _resolver_ruta_spec(spec_archivo, guias_dir)
    spec = cargar_spec(ruta)
    diag = validar_spec(spec, banco)

    if diag["satisfactible"]:
        console.print(f"[bold green]✓ Spec satisfactible[/bold green]: {diag['candidatos_total']} ejercicios disponibles (~{diag['minutos_disponibles']} min para cubrir ~{diag['minutos_requeridos']} min requeridos).")
        if diag["verificados_count"] < diag["candidatos_total"]:
            console.print(f"[yellow]Nota:[/yellow] Solo {diag['verificados_count']}/{diag['candidatos_total']} candidatos están verificados.")
    else:
        console.print(f"[bold red]✗ Spec NO satisfactible con el banco actual[/bold red]")
        if diag["minutos_disponibles"] < diag["minutos_requeridos"]:
            console.print(f"  • Minutos disponibles ({diag['minutos_disponibles']} min) < requeridos ({diag['minutos_requeridos']} min).")
        if diag["temas_faltantes"]:
            console.print(f"  • Temas sin ejercicios en el banco: [red]{', '.join(diag['temas_faltantes'])}[/red]")
        raise typer.Exit(code=1)


@spec_app.command("edit")
def spec_edit(
    spec_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo spec YAML."),
    titulo: Optional[str] = typer.Option(None, "--titulo", "-t"),
    duracion: Optional[int] = typer.Option(None, "--duracion", "-d"),
    margen: Optional[float] = typer.Option(None, "--margen", "-m"),
    temas: Optional[str] = typer.Option(None, "--temas"),
    bloom_min: Optional[int] = typer.Option(None, "--bloom-min", min=1, max=5),
    bloom_max: Optional[int] = typer.Option(None, "--bloom-max", min=1, max=5),
    cantidad_max: Optional[int] = typer.Option(None, "--max-ejercicios", "-n"),
    guias_dir: Path = typer.Option(Path("guias"), "--guias"),
) -> None:
    """Modifica parámetros de una especificación existente."""
    ruta = _resolver_ruta_spec(spec_archivo, guias_dir)
    spec = cargar_spec(ruta)

    if titulo is not None:
        spec.nombre = titulo
    if duracion is not None:
        spec.duracion_min = duracion
    if margen is not None:
        spec.margen_carga = margen
    if temas is not None:
        spec.temas = [t.strip() for t in temas.split(",") if t.strip()]
    if bloom_min is not None:
        spec.bloom_min = bloom_min
    if bloom_max is not None:
        spec.bloom_max = bloom_max
    if cantidad_max is not None:
        spec.cantidad_maxima = cantidad_max

    guardar_spec(ruta, spec)
    console.print(f"[green]✓ Spec actualizada:[/green] {ruta}")


@spec_app.command("compose")
def spec_compose_cmd(
    spec_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo spec YAML."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Compone una guía a partir de esta especificación."""
    ruta = _resolver_ruta_spec(spec_archivo, guias_dir)
    compose(spec_file=ruta, banco=banco)


# ---------------------------------------------------------------------------
# test-harness / pack / multiplex
# ---------------------------------------------------------------------------


@app.command("test-harness")
def test_harness(
    ejercicio_id: str = typer.Argument(..., help="Id del ejercicio en el banco."),
    spec: Path = typer.Argument(..., exists=True, help="spec.yaml del arnés."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    ripley: Optional[str] = typer.Option(None, "--ripley"),
) -> None:
    """Corre el arnés de prueba con inyección de malloc vía `ripley harness`."""
    dir_ej = banco / ejercicio_id
    ruta = f"--ripley {ripley} " if ripley else ""
    os.chdir(spec.parent.parent if len(spec.parent.parts) > 1 else Path("."))
    cmd = f"ripley harness {spec.name} {ruta.strip()}"
    console.print(f"[dim]$ {cmd}[/dim]")
    rc = _ejecutar_herramienta(cmd)
    raise typer.Exit(code=rc)


@app.command("pack")
def pack(
    objetivo: str = typer.Argument(
        ...,
        help="Id del ejercicio en el banco, o ruta a guia.yaml / carpeta de ejercicio.",
    ),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco de ejercicios."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Archivo .ripkg o directorio de salida."),
    sign_key: Optional[str] = typer.Option(None, "--sign-key", help="Clave GPG para firmar el paquete."),
    starter: bool = typer.Option(False, "--starter", help="Generar también estructura starter repo para GitHub Classroom."),
) -> None:
    """Empaqueta ejercicios o guías como .ripkg para Ripley y starter repos."""
    from deckard.core.pack import PackError, empaquetar_ejercicio, empaquetar_guia

    ruta_obj = Path(objetivo)
    try:
        if ruta_obj.is_file() and (ruta_obj.suffix in (".yaml", ".yml") or "guia" in ruta_obj.name):
            resultados = empaquetar_guia(
                guia_spec_file=ruta_obj,
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

        dir_ej = ruta_obj if ruta_obj.is_dir() else (banco / objetivo)
        if not dir_ej.is_dir():
            console.print(f"[red]No se encontró el ejercicio o guía: '{objetivo}' (buscado en {dir_ej})[/red]")
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
