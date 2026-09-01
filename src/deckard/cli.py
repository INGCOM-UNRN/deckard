"""CLI de deckard: banco de ejercicios, guías, verificación, fuzzing y exportación multiformato."""

from __future__ import annotations

import json
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
    compilar_typst_a_pdf,
    inicializar_plantillas,
    renderizar_ejercicio_html,
    renderizar_ejercicio_md,
    renderizar_ejercicio_typst,
    renderizar_guia_html,
    renderizar_guia_md,
    renderizar_guia_typst,
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
    resolver_ruta_guia,
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
    tags: Optional[str] = typer.Option(None, "--tags", "-T", help="Etiquetas separadas por comas (ej: 'punteros,memoria,facil')."),
    banco: Path = typer.Option(Path("banco"), "--banco"),
    funcion: Optional[List[str]] = typer.Option(None, "--funcion", "-F", help="Firmas de funciones requeridas (ej: 'void invertir_vector(int* vec, size_t n)')."),
) -> None:
    """Crea un ejercicio nuevo con esqueleto de metadata, funciones, enunciado.md y solución."""
    from deckard.core.models import FuncionSpec

    funciones_specs = []
    if funcion:
        for f_item in funcion:
            for part in f_item.split(";"):
                if part.strip():
                    funciones_specs.append(FuncionSpec.parse(part.strip()))

    tags_lista = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    ejercicio = Ejercicio(
        id=eid,
        titulo=titulo,
        tema=tema,
        bloom=NivelBloom(bloom),
        minutos_estimados=minutos,
        enunciado_md=f"# {titulo}\n\n(Completar enunciado)\n",
        solucion_c="",
        tags=tags_lista,
        funciones=funciones_specs,
    )
    if funciones_specs:
        ejercicio.solucion_c = ejercicio.generar_esqueleto_c()
    else:
        ejercicio.solucion_c = "#include <stdio.h>\n\nint main(void) {\n    /* TODO */\n    return 0;\n}\n"

    destino = guardar_ejercicio(ejercicio, banco)
    console.print(f"[green]✓ Ejercicio creado[/green] en {destino}")
    console.print(f"  • Enunciado: [cyan]{destino}/enunciado.md[/cyan]")
    if funciones_specs:
        console.print(f"  • Cabecera generada: [cyan]{eid}.h[/cyan] ({len(funciones_specs)} funciones declaradas)")
    if tags_lista:
        console.print(f"  • Tags: [dim]{', '.join(tags_lista)}[/dim]")
    console.print("Editá [bold]enunciado.md[/bold], [bold]ejercicio.yaml[/bold] y [bold]solucion.c[/bold], luego corré [bold]deckard verify[/bold].")


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
    tag: Optional[str] = typer.Option(None, "--tag", "-T", help="Filtrar por etiqueta/tag."),
    verificado: Optional[bool] = typer.Option(None, "--verificado/--no-verificado", help="Filtrar por estado de verificación."),
) -> None:
    """Lista los ejercicios del banco con su nivel, carga, tags y filtros."""
    items = buscar_ejercicios(banco, patron=patron, tema=tema, bloom=bloom, tag=tag, verificado=verificado)
    tabla = Table(title=f"Banco de ejercicios ({len(items)} encontrados)")
    tabla.add_column("id", style="cyan")
    tabla.add_column("tema")
    tabla.add_column("bloom", justify="center")
    tabla.add_column("min", justify="right")
    tabla.add_column("tags", style="dim")
    tabla.add_column("verificado", justify="center")
    total_min = 0
    verificados_count = 0
    for _, e in items:
        total_min += e.minutos_estimados
        if e.verificado:
            verificados_count += 1
        tags_str = ", ".join(e.tags) if e.tags else "—"
        tabla.add_row(e.id, e.tema, f"B{int(e.bloom)} {e.bloom.name.lower()}",
                      str(e.minutos_estimados), tags_str, "✓" if e.verificado else "—")
    console.print(tabla)
    pct = (verificados_count / len(items) * 100) if items else 0
    console.print(f"[dim]{total_min} minutos totales ({total_min/60:.1f}h) · Verificados: {verificados_count}/{len(items)} ({pct:.0f}%)[/dim]")


@bank_app.command("organize")
@bank_app.command("reorganize")
@app.command("organize")
def bank_organize(
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco de ejercicios."),
    criterio: str = typer.Option(
        "bloom/tipo",
        "--by",
        "-b",
        "--criterio",
        help="Criterio de reorganización: 'bloom', 'tipo', 'bloom/tipo', 'tipo/bloom', 'tema/bloom', 'bloom/tema', 'tema/tipo', 'plano'.",
    ),
    destino: Optional[Path] = typer.Option(
        None,
        "--destino",
        "-d",
        help="Directorio de destino (por defecto, reorganiza dentro del mismo banco).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Simula la reorganización y muestra los movimientos sin modificar el disco.",
    ),
    copy: bool = typer.Option(
        False,
        "--copy",
        "-c",
        help="Copia los ejercicios al nuevo esquema en vez de moverlos.",
    ),
) -> None:
    """Reorganiza los ejercicios en carpetas según nivel de Bloom, tipo (funciones vs io) y/o tema."""
    from deckard.core.bank import reorganizar_banco

    if not banco.is_dir():
        console.print(f"[bold red]El directorio del banco no existe:[/bold red] {banco}")
        raise typer.Exit(code=1)

    movimientos = reorganizar_banco(
        banco=banco,
        criterio=criterio,
        dir_destino=destino,
        dry_run=dry_run,
        copy=copy,
    )

    if not movimientos:
        console.print(f"[yellow]No se encontraron ejercicios en '{banco}'.[/yellow]")
        return

    accion_verbo = "Copiado" if copy else "Movido"
    sim_tag = "[yellow](Simulación / Dry-run)[/yellow] " if dry_run else ""

    tabla = Table(title=f"{sim_tag}Reorganización del Banco (Criterio: {criterio})")
    tabla.add_column("Ejercicio", style="cyan")
    tabla.add_column("Bloom")
    tabla.add_column("Tipo")
    tabla.add_column("Origen", style="dim")
    tabla.add_column("Destino", style="green")
    tabla.add_column("Estado", justify="center")

    total_movidos = 0
    total_sin_cambio = 0

    for mov in movimientos:
        try:
            rel_orig = mov.origen.relative_to(banco).as_posix()
        except Exception:
            rel_orig = str(mov.origen)
        try:
            target_base = destino or banco
            rel_dest = mov.destino.relative_to(target_base).as_posix()
        except Exception:
            rel_dest = str(mov.destino)

        if mov.cambio:
            total_movidos += 1
            estado = f"[green]✓ {accion_verbo}[/green]" if not dry_run else "[yellow]→ Pendiente[/yellow]"
        else:
            total_sin_cambio += 1
            estado = "[dim]— En lugar[/dim]"

        tabla.add_row(
            mov.id,
            mov.bloom,
            f"[magenta]{mov.tipo}[/magenta]",
            rel_orig,
            rel_dest,
            estado,
        )

    console.print(tabla)
    console.print(
        f"\n[bold]Resumen:[/bold] [green]{total_movidos} {'a mover/copiar' if dry_run else 'reorganizados'}[/green] · "
        f"[dim]{total_sin_cambio} sin cambios[/dim] (Total: {len(movimientos)})"
    )


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
        if ej.funciones:
            print("\n--- FUNCIONES REQUERIDAS ---")
            for fn in ej.funciones:
                desc = f" ({fn.descripcion})" if fn.descripcion else ""
                print(f"* {fn.firma}{desc}")
        if enunciado:
            print(f"\n--- ENUNCIADO ---\n{ej.enunciado_md}")
        if pistas and ej.pistas:
            print("\n--- PISTAS ---")
            for i, p in enumerate(ej.pistas, 1):
                print(f"{i}. {p}")
        if tests:
            if ej.tests_funciones:
                print("\n--- TESTS DE FUNCIONES ---")
                for tf in ej.tests_funciones:
                    detalle = tf.codigo.strip() if tf.codigo else f"{tf.funcion}({tf.args or ''}) == {tf.retorno_esperado or 'void'}"
                    print(f"[{tf.nombre}] (fn: {tf.funcion})\n{detalle}\n")
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
        grid.add_row("Tipo entrega:", ej.tipo_entrega)
        grid.add_row("Verificado:", "[green]✓ Sí[/green]" if ej.verificado else "[dim]— No[/dim]")
        if ej.funciones:
            grid.add_row("Funciones C:", f"{len(ej.funciones)} requeridas")
        if ej.tests_funciones:
            grid.add_row("Tests de función:", f"{len(ej.tests_funciones)} declarados")
        if ej.tags:
            grid.add_row("Tags:", ", ".join(ej.tags))
        console.print(Panel(grid, title=f"[bold cyan]{ej.id}[/bold cyan] — {ej.titulo}", border_style="blue"))

    if ej.funciones:
        tabla_fn = Table(title="🛠️ Funciones / Interfaz C Requerida")
        tabla_fn.add_column("Firma / Prototipo", style="green")
        tabla_fn.add_column("Descripción", style="dim")
        for fn in ej.funciones:
            tabla_fn.add_row(fn.firma, fn.descripcion or "—")
        console.print(tabla_fn)

    if enunciado:
        console.print(Markdown(ej.enunciado_md))

    if pistas and ej.pistas:
        texto_pistas = "\n".join(f"[bold]{i}.[/bold] {p}" for i, p in enumerate(ej.pistas, 1))
        console.print(Panel(texto_pistas, title="💡 Pistas Progresivas", border_style="yellow"))

    if tests:
        if ej.tests_funciones:
            tabla_tf = Table(title="🧪 Tests de Funciones (Invocación Directa)")
            tabla_tf.add_column("Test", style="cyan")
            tabla_tf.add_column("Función")
            tabla_tf.add_column("Invocación / Aserción")
            for tf in ej.tests_funciones:
                c_str = tf.codigo.strip() if tf.codigo else f"{tf.funcion}({tf.args or ''}) == {tf.retorno_esperado or 'void'}"
                tabla_tf.add_row(tf.nombre, f"[bold]{tf.funcion}[/bold]", c_str)
            console.print(tabla_tf)

        casos = cargar_tests_ejercicio(dir_ej)
        if casos:
            tabla_t = Table(title="🧪 Casos de Prueba I/O (tests/)")
            tabla_t.add_column("Caso", style="cyan")
            tabla_t.add_column("Entrada (.in)")
            tabla_t.add_column("Salida (.out)")
            for c in casos:
                tabla_t.add_row(c["nombre"], c["entrada"].strip(), c["salida"].strip())
            console.print(tabla_t)
        elif not ej.tests_funciones:
            console.print("[dim]No se encontraron casos de prueba en tests/ ni tests de funciones.[/dim]")

    if solucion and ej.solucion_c:
        console.print(Panel(
            Syntax(ej.solucion_c, "c", theme="monokai", line_numbers=True),
            title="✓ Solución Modelo de Cátedra",
            border_style="green",
        ))


# ---------------------------------------------------------------------------
# DefaultCommandGroup helper
# ---------------------------------------------------------------------------


class DefaultCommandGroup(typer.core.TyperGroup):
    """Permite ejecutar subcomandos o delegar al comando por defecto 'run'."""

    def parse_args(self, ctx, args):
        if not args:
            return super().parse_args(ctx, args)
        cmd_name = args[0]
        if cmd_name not in ["--help", "-h"] and self.get_command(ctx, cmd_name) is None:
            args = ["run"] + list(args)
        return super().parse_args(ctx, args)


# ---------------------------------------------------------------------------
# verify app (verify, fuzz, test-harness)
# ---------------------------------------------------------------------------

verify_app = typer.Typer(
    cls=DefaultCommandGroup,
    name="verify",
    help="Verificación pedagógica (ripley check), fuzzing (dredd) y arnés de pruebas (ripley harness).",
    no_args_is_help=False,
)
app.add_typer(verify_app, name="verify")


def _escribir_log_fallos_verificacion(
    ruta_log: Path,
    fallos: List[dict],
    total_analizados: int,
    total_exitos: int,
    total_fallos: int,
) -> None:
    from datetime import datetime
    ruta_log = Path(ruta_log)
    ruta_log.parent.mkdir(parents=True, exist_ok=True)

    lineas = [
        "# Reporte de Fallos de Verificación — Deckard",
        f"- **Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Total analizados:** {total_analizados}",
        f"- **Exitosos:** {total_exitos}",
        f"- **Fallidos:** {total_fallos}",
        "",
        "---",
        "",
    ]
    if not fallos:
        lineas.append("No se registraron fallos durante la verificación.\n")
    else:
        lineas.append("## Detalle de Ejercicios con Fallas\n")
        for f in fallos:
            lineas.append(f"### `{f['id']}` (Fallo de Verificación)")
            lineas.append(f"- **Tema:** {f.get('tema', '—')}")
            lineas.append(f"- **Directorio:** `{f['dir']}`")
            lineas.append(f"- **Estado en banco:** Marcado como no-verificado (`verificado: false`)")
            lineas.append("- **Detalle del fallo:**")
            lineas.append("```")
            lineas.append(f.get("error", "Error no especificado"))
            lineas.append("```\n")

    ruta_log.write_text("\n".join(lineas), encoding="utf-8")


@verify_app.command("run", hidden=True)
def verify(
    ejercicio_id: Optional[str] = typer.Argument(None, help="Id del ejercicio o patrón comodín (ej: '*', 'invertir-*')."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    all_exercises: bool = typer.Option(False, "--all", "-a", help="Verificar todos los ejercicios del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-t", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", min=1, max=5, help="Filtrar por nivel de Bloom (1-5)."),
    pendientes: bool = typer.Option(False, "--pendientes", "-p", help="Verificar solo ejercicios pendientes."),
    guardar: bool = typer.Option(True, "--guardar/--no-guardar", help="Persistir veredicto en ejercicio.yaml."),
    log_fallos: Optional[Path] = typer.Option(None, "--log-fallos", "-l", help="Ruta de archivo para guardar el reporte de ejercicios fallidos."),
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
        dir_ej, ej = candidatos[0]
        resultado = verificar_ejercicio(dir_ej, ruta_ripley=ripley)
        if (dir_ej / "ejercicio.yaml").is_file():
            if not resultado.ok or guardar:
                actualizar_verificacion(dir_ej, resultado.ok)

        color = "green" if resultado.ok else "red"
        console.print(f"[{color}]{resultado.marca} {resultado.ejercicio}[/{color}] — {resultado.detalle}")
        if not resultado.ok:
            console.print(f"[dim]Marcado como no-verificado (verificado: false).[/dim]")
            if log_fallos:
                _escribir_log_fallos_verificacion(
                    log_fallos,
                    [{"id": ej.id, "tema": ej.tema, "dir": dir_ej, "error": resultado.detalle}],
                    1, 0, 1
                )
                console.print(f"[yellow]📝 Reporte de fallos guardado en:[/yellow] {log_fallos}")
        raise typer.Exit(code=0 if resultado.ok else 1)

    console.print(f"[bold]Verificando {len(candidatos)} ejercicios con ripley...[/bold]")
    tabla = Table(title="Resultados de verificación")
    tabla.add_column("Ejercicio", style="cyan")
    tabla.add_column("Tema")
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Veredicto", justify="center")
    tabla.add_column("Detalle")

    total_ok = 0
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
        task = progress.add_task("[cyan]Verificando ejercicios...", total=len(candidatos))

        for dir_ej, ej in candidatos:
            progress.update(task, description=f"[cyan]Verificando: [bold]{ej.id}[/bold]")
            res = verificar_ejercicio(dir_ej, ruta_ripley=ripley)

            if (dir_ej / "ejercicio.yaml").is_file():
                if not res.ok or guardar:
                    actualizar_verificacion(dir_ej, res.ok)

            if res.ok:
                total_ok += 1
                veredicto_str = "[green]✓ OK[/green]"
            else:
                total_fallos += 1
                veredicto_str = "[red]✗ Fallo[/red]"
                fallos_info.append({
                    "id": ej.id,
                    "tema": ej.tema,
                    "dir": dir_ej,
                    "error": res.detalle,
                })

            tabla.add_row(ej.id, ej.tema, f"B{int(ej.bloom)}", veredicto_str, res.detalle)
            progress.advance(task)

    console.print(tabla)
    color_resumen = "green" if total_ok == len(candidatos) else "yellow" if total_ok > 0 else "red"
    console.print(f"[{color_resumen}]Verificación completada: {total_ok}/{len(candidatos)} exitosos[/{color_resumen}]")

    if log_fallos:
        _escribir_log_fallos_verificacion(
            log_fallos,
            fallos_info,
            len(candidatos),
            total_ok,
            total_fallos,
        )
        console.print(f"[yellow]📝 Reporte de fallos guardado en:[/yellow] {log_fallos}")

    raise typer.Exit(code=0 if total_ok == len(candidatos) else 1)


@verify_app.command("audit")
@verify_app.command("health")
@app.command("audit")
def audit_cmd(
    patron: Optional[str] = typer.Argument(None, help="ID o patrón comodín de ejercicios a auditar."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-t", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", min=1, max=5, help="Filtrar por nivel de Bloom."),
    tag: Optional[str] = typer.Option(None, "--tag", "-T", help="Filtrar por etiqueta/tag."),
    min_chars: int = typer.Option(100, "--min-chars", "-m", help="Largo mínimo de caracteres en enunciado para considerar redacción suficiente."),
    solo_pobres: bool = typer.Option(False, "--pobres", "--short", "-p", help="Mostrar únicamente ejercicios con redacción pobre o incompleta."),
    solo_incompletos: bool = typer.Option(False, "--incompletos", "-i", help="Mostrar solo ejercicios con componentes faltantes."),
    sin_tests: bool = typer.Option(False, "--sin-tests", help="Filtrar ejercicios sin casos de prueba (I/O ni funciones)."),
    sin_pistas: bool = typer.Option(False, "--sin-pistas", help="Filtrar ejercicios sin pistas progresivas."),
    sin_solucion: bool = typer.Option(False, "--sin-solucion", help="Filtrar ejercicios sin solución modelo."),
    json_output: bool = typer.Option(False, "--json", help="Emitir reporte estructurado en formato JSON."),
) -> None:
    """Audita la salud del banco: longitud y calidad de redacción del enunciado, y completitud de especificación."""
    import json
    from deckard.core.audit import auditar_banco

    reportes = auditar_banco(
        banco=banco,
        patron=patron,
        tema=tema,
        bloom=bloom,
        tag=tag,
        min_chars=min_chars,
        solo_pobres=solo_pobres,
        solo_incompletos=solo_incompletos,
        sin_tests=sin_tests,
        sin_pistas=sin_pistas,
        sin_solucion=sin_solucion,
    )

    if json_output:
        data = [
            {
                "id": r.id,
                "tema": r.tema,
                "bloom": r.bloom,
                "minutos": r.minutos,
                "longitud_enunciado_chars": r.longitud_enunciado_chars,
                "longitud_enunciado_words": r.longitud_enunciado_words,
                "redaccion_pobre": r.redaccion_pobre,
                "diagnostico_redaccion": r.diagnostico_redaccion,
                "tiene_enunciado_md": r.tiene_enunciado_md_file,
                "tiene_solucion": r.tiene_solucion,
                "pistas_count": r.cantidad_pistas,
                "tests_io_count": r.cantidad_testcases_io,
                "tests_fn_count": r.cantidad_tests_funciones,
                "tags": r.tags,
                "verificado": r.verificado,
                "faltantes": r.faltantes,
                "alertas": r.alertas,
            }
            for r in reportes
        ]
        console.print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not reportes:
        console.print(f"[yellow]No se encontraron ejercicios en '{banco}' con los filtros especificados.[/yellow]")
        return

    tabla = Table(title=f"Auditoría de Salud del Banco ({len(reportes)} ejercicios)")
    tabla.add_column("Ejercicio", style="cyan", no_wrap=True)
    tabla.add_column("Bloom", justify="center")
    tabla.add_column("Enunciado", justify="right")
    tabla.add_column("Redac.", justify="center")
    tabla.add_column("MD", justify="center")
    tabla.add_column("Sol.", justify="center")
    tabla.add_column("Pistas", justify="center")
    tabla.add_column("Tests", justify="center")
    tabla.add_column("Tags", style="dim")
    tabla.add_column("Faltantes / Alertas", style="yellow")

    total_chars = 0
    total_words = 0
    pobres_count = 0
    sin_tests_count = 0
    sin_sol_count = 0
    sin_pistas_count = 0

    for r in reportes:
        total_chars += r.longitud_enunciado_chars
        total_words += r.longitud_enunciado_words

        if r.redaccion_pobre:
            pobres_count += 1
            if r.diagnostico_redaccion == "pobre":
                redac_str = "[bold red]Pobre[/bold red]"
            else:
                redac_str = "[yellow]Breve[/yellow]"
        else:
            redac_str = "[green]Completo[/green]"

        md_str = "[green]enunciado.md[/green]" if r.tiene_enunciado_md_file else "[yellow]en yaml[/yellow]"
        sol_str = "[green]✓[/green]" if r.tiene_solucion else "[red]✗[/red]"
        if not r.tiene_solucion:
            sin_sol_count += 1

        pistas_str = f"{r.cantidad_pistas}" if r.cantidad_pistas > 0 else "[yellow]0[/yellow]"
        if r.cantidad_pistas == 0:
            sin_pistas_count += 1

        if r.total_tests > 0:
            tests_str = f"{r.total_tests} ({r.cantidad_testcases_io} io, {r.cantidad_tests_funciones} fn)"
        else:
            tests_str = "[red]0[/red]"
            sin_tests_count += 1

        tags_str = ", ".join(r.tags) if r.tags else "[dim]—[/dim]"
        obs = ", ".join(r.faltantes) if r.faltantes else "[green]✓ Completo[/green]"

        largo_str = f"{r.longitud_enunciado_chars} ch ({r.longitud_enunciado_words} w)"
        tabla.add_row(
            r.id,
            f"B{r.bloom}",
            largo_str,
            redac_str,
            md_str,
            sol_str,
            pistas_str,
            tests_str,
            tags_str,
            obs,
        )

    console.print(tabla)

    avg_chars = total_chars / len(reportes) if reportes else 0
    avg_words = total_words / len(reportes) if reportes else 0
    console.print(f"[bold]Resumen de Auditoría:[/bold]")
    console.print(f"  • Total analizados: [cyan]{len(reportes)}[/cyan]")
    console.print(f"  • Longitud media de enunciado: [bold]{avg_chars:.0f} caracteres[/bold] (~{avg_words:.0f} palabras)")
    if pobres_count > 0:
        console.print(f"  • [red]⚠️  {pobres_count} ejercicio(s) con redacción pobre o breve (<{min_chars} chars)[/red]")
    if sin_tests_count > 0:
        console.print(f"  • [red]⚠️  {sin_tests_count} ejercicio(s) sin casos de prueba (I/O o funciones)[/red]")
    if sin_sol_count > 0:
        console.print(f"  • [red]⚠️  {sin_sol_count} ejercicio(s) sin solución modelo[/red]")
    if sin_pistas_count > 0:
        console.print(f"  • [yellow]💡 {sin_pistas_count} ejercicio(s) sin pistas progresivas[/yellow]")
    if pobres_count == 0 and sin_tests_count == 0 and sin_sol_count == 0:
        console.print(f"[green]✓ Todos los ejercicios analizados cuentan con especificación completa y saludable.[/green]")


# ---------------------------------------------------------------------------
# tag app
# ---------------------------------------------------------------------------

tag_app = typer.Typer(name="tag", help="Gestión y consulta de etiquetas (tags) en el banco.", no_args_is_help=True)
app.add_typer(tag_app, name="tag")


@tag_app.command("list")
def tag_list_cmd(
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
) -> None:
    """Lista todas las etiquetas presentes en el banco de ejercicios."""
    from deckard.core.tags import listar_tags_banco

    tag_map = listar_tags_banco(banco)
    if not tag_map:
        console.print(f"[yellow]No se encontraron etiquetas en '{banco}'.[/yellow]")
        return

    tabla = Table(title=f"Etiquetas del Banco ({len(tag_map)} encontradas)")
    tabla.add_column("Tag / Etiqueta", style="bold cyan")
    tabla.add_column("Ejercicios", justify="right")
    tabla.add_column("IDs de Ejemplo", style="dim")

    for tag_name, eids in tag_map.items():
        ejemplos = ", ".join(eids[:6]) + ("..." if len(eids) > 6 else "")
        tabla.add_row(tag_name, str(len(eids)), ejemplos)

    console.print(tabla)


@tag_app.command("add")
def tag_add_cmd(
    patron: str = typer.Argument(..., help="ID o patrón comodín de ejercicios (ej: 'invertir-*', '*')."),
    tags: List[str] = typer.Argument(..., help="Etiquetas a agregar."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
) -> None:
    """Agrega una o más etiquetas a ejercicios del banco."""
    from deckard.core.tags import agregar_tags_a_ejercicios

    tags_flat: List[str] = []
    for t in tags:
        tags_flat.extend([x.strip() for x in t.split(",") if x.strip()])

    modificados = agregar_tags_a_ejercicios(banco, patron, tags_flat)
    if not modificados:
        console.print(f"[yellow]No se modificaron ejercicios para '{patron}'.[/yellow]")
        return

    console.print(f"[green]✓ Tags agregados a {len(modificados)} ejercicio(s):[/green]")
    for eid, t_list in modificados:
        console.print(f"  • [cyan]{eid}[/cyan] -> tags: [dim]{', '.join(t_list)}[/dim]")


@tag_app.command("remove")
def tag_remove_cmd(
    patron: str = typer.Argument(..., help="ID o patrón comodín de ejercicios."),
    tags: List[str] = typer.Argument(..., help="Etiquetas a remover."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
) -> None:
    """Remueve una o más etiquetas de ejercicios del banco."""
    from deckard.core.tags import remover_tags_de_ejercicios

    tags_flat: List[str] = []
    for t in tags:
        tags_flat.extend([x.strip() for x in t.split(",") if x.strip()])

    modificados = remover_tags_de_ejercicios(banco, patron, tags_flat)
    if not modificados:
        console.print(f"[yellow]No se modificaron ejercicios para '{patron}'.[/yellow]")
        return

    console.print(f"[green]✓ Tags removidos de {len(modificados)} ejercicio(s):[/green]")
    for eid, t_list in modificados:
        console.print(f"  • [cyan]{eid}[/cyan] -> tags: [dim]{', '.join(t_list)}[/dim]")


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

    slug = spec.nombre.replace(' ', '_').lower()
    dir_guia = Path("guias") / slug
    dir_guia.mkdir(parents=True, exist_ok=True)
    salida = dir_guia / "guia.yaml"
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


@verify_app.command("fuzz")
@app.command("fuzz", hidden=True)
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
# export (Exportación multiformato: PDF, MD, HTML) + templates
# ---------------------------------------------------------------------------


export_app = typer.Typer(
    cls=DefaultCommandGroup,
    name="export",
    help="Exportación multiformato (PDF, Markdown, HTML) y gestión de plantillas.",
    no_args_is_help=True,
)
app.add_typer(export_app, name="export")

templates_sub_app = typer.Typer(
    name="templates",
    help="Gestión y personalización de plantillas y CSS para exportación.",
    no_args_is_help=True,
)
export_app.add_typer(templates_sub_app, name="templates")


@templates_sub_app.command("init")
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


@templates_sub_app.command("list")
def export_templates_list() -> None:
    """Lista las plantillas disponibles (locales, globales y built-in)."""
    tabla = Table(title="Plantillas y Estilos Disponibles")
    tabla.add_column("Tipo", style="cyan")
    tabla.add_column("Ubicación / Archivo", style="green")
    tabla.add_column("Existe", justify="center")

    builtin_dir = Path(__file__).parent / "templates"
    global_dir = Path.home() / ".config" / "deckard" / "templates"
    local_dir = Path("templates")

    rutas = [
        ("Local (./templates)", local_dir),
        ("Global (~/.config/deckard/templates)", global_dir),
        ("Built-in (deckard/templates)", builtin_dir),
    ]
    for tipo, d in rutas:
        if d.is_dir():
            archivos = [f.name for f in sorted(d.iterdir()) if f.is_file()]
            tabla.add_row(tipo, f"{d} ({', '.join(archivos)})", "[green]✓[/green]")
        else:
            tabla.add_row(tipo, str(d), "[dim]—[/dim]")
    console.print(tabla)


def _parse_output_types(tipo_str: str) -> List[str]:
    raw_list = [t.strip().lower() for t in tipo_str.split(",") if t.strip()]
    res = []
    for r in raw_list:
        val = "md" if r == "markdown" else ("typ" if r == "typst" else r)
        if val not in ("pdf", "md", "html", "typ", "typst"):
            console.print(f"[red]Formato de salida no válido: '{r}'. Opciones permitidas: pdf, md, html, typ, typst.[/red]")
            raise typer.Exit(code=1)
        if val not in res:
            res.append(val)
    return res or ["pdf"]


@export_app.command("run", hidden=True)
def exportar_contenido(
    objetivo: Optional[str] = typer.Argument(None, help="Id de ejercicio, comodín/wildcard ('*', 'invertir-*'), o ruta a guía (.yaml)."),
    type: str = typer.Option("pdf", "--type", "-t", help="Formatos de salida (ej: --type=pdf,md o --type=typst). Separar por comas."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Archivo de salida o directorio destino."),
    template: Optional[str] = typer.Option(None, "--template", "-T", help="Nombre o ruta de plantilla personalizada (.typ.j2, .html, .md)."),
    pipeline_md: bool = typer.Option(False, "--pipeline-md", help="Generar Markdown intermedio antes de compilar PDF."),
    solucion: bool = typer.Option(False, "--solucion", "-s", help="Incluir solución modelo."),
    pistas: bool = typer.Option(False, "--pistas", "-p", help="Incluir pistas progresivas."),
    tests: bool = typer.Option(False, "--tests", help="Incluir casos de prueba."),
    css: Optional[Path] = typer.Option(None, "--css", exists=True, help="Archivo CSS adicional para PDF/HTML."),
    todos: bool = typer.Option(False, "--all", "-a", help="Exportar todos los ejercicios del banco."),
    tema: Optional[str] = typer.Option(None, "--tema", "-m", help="Filtrar por tema."),
    bloom: Optional[int] = typer.Option(None, "--bloom", "-b", help="Filtrar por nivel Bloom (1-5)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtrar por etiqueta/tag."),
    verificado: Optional[bool] = typer.Option(None, "--verificado/--no-verificado", help="Filtrar por estado de verificación."),
    single_pdf: bool = typer.Option(False, "--single-pdf", "--combined", "-c", help="Generar un único PDF consolidado cuando hay múltiples ejercicios para exportar."),
    titulo: Optional[str] = typer.Option(None, "--titulo", help="Título del compendio consolidado (usado con --single-pdf)."),
    dos_columnas: bool = typer.Option(False, "--dos-columnas", "--two-columns", "-2", help="Diseño compacto en 2 columnas para exámenes de laboratorio (ahorro de papel)."),
) -> None:
    """Exporta ejercicios o guías a Typst, PDF, Markdown o HTML con plantillas personalizables, comodines y filtros."""
    tipos = _parse_output_types(type)
    extra_css_str = css.read_text(encoding="utf-8") if css else None

    # Determinar patrón efectivo
    patron = objetivo
    if todos:
        patron = objetivo or "*"
    elif not objetivo:
        if tema or bloom or tag or verificado is not None:
            patron = "*"
        else:
            console.print("[red]Debe especificar un objetivo (ID, comodín '*'), ruta a guía (.yaml), '--all' o al menos un filtro (--tema, --bloom, --tag).[/red]")
            raise typer.Exit(code=1)

    # Caso 1: Archivo de guía YAML
    if objetivo:
        ruta_obj = Path(objetivo)
        if ruta_obj.is_file() and (ruta_obj.suffix in (".yaml", ".yml") or "guia" in ruta_obj.name):
            guia_meta, items = cargar_guia_con_ejercicios(ruta_obj, banco)
            validos = [(d, e) for d, e in items if e is not None]
            if not validos:
                console.print(f"[red]La guía '{objetivo}' no tiene ejercicios válidos en el banco.[/red]")
                raise typer.Exit(code=1)

            for fmt in tipos:
                if salida is not None:
                    if len(tipos) == 1 and not salida.is_dir() and salida.suffix:
                        dest = salida
                    elif salida.is_dir() or not salida.suffix or str(salida).endswith(("/", "\\")):
                        dest = salida / f"{ruta_obj.stem}.{fmt}"
                    else:
                        dest = salida.with_suffix(f".{fmt}")
                else:
                    dest = Path(f"{ruta_obj.stem}.{fmt}")

                dest.parent.mkdir(parents=True, exist_ok=True)

                if fmt == "md":
                    md_salida, _ = renderizar_guia_md(
                        guia_meta=guia_meta,
                        ejercicios_con_dir=validos,
                        template_nombre_o_ruta=template,
                        incluir_soluciones=solucion,
                        incluir_pistas=pistas,
                        dir_banco=banco,
                    )
                    dest.write_text(md_salida, encoding="utf-8")
                    console.print(f"[green]✓ Guía exportada a Markdown:[/green] {dest}")
                elif fmt in ("typ", "typst"):
                    typ_salida, _ = renderizar_guia_typst(
                        guia_meta=guia_meta,
                        ejercicios_con_dir=validos,
                        template_nombre_o_ruta=template,
                        incluir_soluciones=solucion,
                        incluir_pistas=pistas,
                        dir_banco=banco,
                        dos_columnas=dos_columnas,
                    )
                    dest.write_text(typ_salida, encoding="utf-8")
                    console.print(f"[green]✓ Guía exportada a Typst:[/green] {dest}")
                elif fmt == "html":
                    html_salida, _ = renderizar_guia_html(
                        guia_meta=guia_meta,
                        ejercicios_con_dir=validos,
                        template_nombre_o_ruta=template,
                        incluir_soluciones=solucion,
                        incluir_pistas=pistas,
                        extra_css=extra_css_str,
                        dir_banco=banco,
                        via_markdown_pipeline=pipeline_md,
                    )
                    dest.write_text(html_salida, encoding="utf-8")
                    console.print(f"[green]✓ Guía exportada a HTML:[/green] {dest}")
                elif fmt == "pdf":
                    try:
                        typst_salida, base_p = renderizar_guia_typst(
                            guia_meta=guia_meta,
                            ejercicios_con_dir=validos,
                            template_nombre_o_ruta=template,
                            incluir_soluciones=solucion,
                            incluir_pistas=pistas,
                            dir_banco=banco,
                            dos_columnas=dos_columnas,
                        )
                        pdf_path = compilar_typst_a_pdf(typst_salida, dest, root_dir=base_p)
                        console.print(f"[green]✓ Guía exportada a PDF (Typst):[/green] {pdf_path}")
                    except Exception as e_typst:
                        # Fallback a HTML si la plantilla era HTML
                        try:
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
                            pdf_path = compilar_pdf(html_salida, dest, base_url=str(base_p) if base_p else ".")
                            console.print(f"[green]✓ Guía exportada a PDF:[/green] {pdf_path}")
                        except Exception as e:
                            console.print(f"[red]Error exportando PDF: {e_typst or e}[/red]")
                            raise typer.Exit(code=1)
            return

    # Caso 2: Ejercicio(s) en el banco (wildcards, filtros, --all)
    candidatos = buscar_ejercicios(
        banco,
        patron=patron,
        tema=tema,
        bloom=bloom,
        tag=tag,
        verificado=verificado,
        recursivo=True,
    )
    if not candidatos and objetivo:
        ruta_dir = Path(objetivo)
        if (ruta_dir / "ejercicio.yaml").is_file():
            ej_cand = cargar_ejercicio(ruta_dir)
            pasa = True
            if tema and ej_cand.tema != tema:
                pasa = False
            if bloom and int(ej_cand.bloom) != int(bloom):
                pasa = False
            if tag and tag not in ej_cand.tags:
                pasa = False
            if verificado is not None and ej_cand.verificado != verificado:
                pasa = False
            if pasa:
                candidatos = [(ruta_dir, ej_cand)]

    if not candidatos:
        criterios = []
        if patron and patron != "*":
            criterios.append(f"patrón='{patron}'")
        if tema:
            criterios.append(f"tema='{tema}'")
        if bloom:
            criterios.append(f"bloom={bloom}")
        if tag:
            criterios.append(f"tag='{tag}'")
        if verificado is not None:
            criterios.append(f"verificado={verificado}")
        crit_str = f" ({', '.join(criterios)})" if criterios else ""
        console.print(f"[red]No se encontró ningún ejercicio que coincida con los criterios especificados{crit_str}.[/red]")
        raise typer.Exit(code=1)

    es_multiple = len(candidatos) > 1 or todos or bool(patron and ("*" in patron or "?" in patron))

    if single_pdf or (len(candidatos) > 1 and salida and not salida.is_dir() and salida.suffix.lower() == ".pdf" and len(tipos) == 1 and tipos[0] == "pdf"):
        # Exportar todos los candidatos consolidados en un único documento / PDF
        titulo_compendio = titulo or (
            f"Guía de Ejercicios — Tema: {tema.capitalize()}" if tema else
            f"Compendio de Ejercicios ({len(candidatos)} ejercicios)"
        )
        guia_meta = {
            "titulo": titulo_compendio,
            "materia": "Programación 1",
            "descripcion": f"Compendio generado automáticamente con {len(candidatos)} ejercicios del banco.",
        }
        for fmt in tipos:
            if salida is not None:
                if len(tipos) == 1 and not salida.is_dir() and salida.suffix:
                    dest = salida
                elif salida.is_dir() or not salida.suffix or str(salida).endswith(("/", "\\")):
                    nombre_base = Path(objetivo).stem if objetivo and "*" not in objetivo else (f"compendio_{tema}" if tema else "compendio")
                    dest = salida / f"{nombre_base}.{fmt}"
                else:
                    dest = salida.with_suffix(f".{fmt}")
            else:
                nombre_base = Path(objetivo).stem if objetivo and "*" not in objetivo else (f"compendio_{tema}" if tema else "compendio")
                dest = Path(f"{nombre_base}.{fmt}")

            dest.parent.mkdir(parents=True, exist_ok=True)

            if fmt == "md":
                md_salida, _ = renderizar_guia_md(
                    guia_meta=guia_meta,
                    ejercicios_con_dir=candidatos,
                    template_nombre_o_ruta=template,
                    incluir_soluciones=solucion,
                    incluir_pistas=pistas,
                    dir_banco=banco,
                )
                dest.write_text(md_salida, encoding="utf-8")
                console.print(f"[green]✓ Compendio consolidado ({len(candidatos)} ejercicios) exportado a Markdown:[/green] {dest}")
            elif fmt in ("typ", "typst"):
                typ_salida, _ = renderizar_guia_typst(
                    guia_meta=guia_meta,
                    ejercicios_con_dir=candidatos,
                    template_nombre_o_ruta=template,
                    incluir_soluciones=solucion,
                    incluir_pistas=pistas,
                    dir_banco=banco,
                    dos_columnas=dos_columnas,
                )
                dest.write_text(typ_salida, encoding="utf-8")
                console.print(f"[green]✓ Compendio consolidado ({len(candidatos)} ejercicios) exportado a Typst:[/green] {dest}")
            elif fmt == "html":
                html_salida, _ = renderizar_guia_html(
                    guia_meta=guia_meta,
                    ejercicios_con_dir=candidatos,
                    template_nombre_o_ruta=template,
                    incluir_soluciones=solucion,
                    incluir_pistas=pistas,
                    extra_css=extra_css_str,
                    dir_banco=banco,
                    via_markdown_pipeline=pipeline_md,
                )
                dest.write_text(html_salida, encoding="utf-8")
                console.print(f"[green]✓ Compendio consolidado ({len(candidatos)} ejercicios) exportado a HTML:[/green] {dest}")
            elif fmt == "pdf":
                try:
                    typst_salida, base_p = renderizar_guia_typst(
                        guia_meta=guia_meta,
                        ejercicios_con_dir=candidatos,
                        template_nombre_o_ruta=template,
                        incluir_soluciones=solucion,
                        incluir_pistas=pistas,
                        dir_banco=banco,
                        dos_columnas=dos_columnas,
                    )
                    pdf_path = compilar_typst_a_pdf(typst_salida, dest, root_dir=base_p)
                    console.print(f"[green]✓ Compendio consolidado ({len(candidatos)} ejercicios) exportado a PDF (Typst):[/green] {pdf_path}")
                except Exception as e_typst:
                    try:
                        html_salida, base_p = renderizar_guia_html(
                            guia_meta=guia_meta,
                            ejercicios_con_dir=candidatos,
                            template_nombre_o_ruta=template,
                            incluir_soluciones=solucion,
                            incluir_pistas=pistas,
                            extra_css=extra_css_str,
                            dir_banco=banco,
                            via_markdown_pipeline=pipeline_md,
                        )
                        pdf_path = compilar_pdf(html_salida, dest, base_url=str(base_p) if base_p else ".")
                        console.print(f"[green]✓ Compendio consolidado ({len(candidatos)} ejercicios) exportado a PDF:[/green] {pdf_path}")
                    except Exception as e:
                        console.print(f"[red]Error exportando PDF: {e_typst or e}[/red]")
                        raise typer.Exit(code=1)
        return

    if len(candidatos) == 1 and not es_multiple:
        dir_ej, ej = candidatos[0]

        for fmt in tipos:
            if salida is not None:
                if len(tipos) == 1 and not salida.is_dir() and salida.suffix:
                    dest = salida
                elif salida.is_dir() or not salida.suffix or str(salida).endswith(("/", "\\")):
                    dest = salida / f"{ej.id}.{fmt}"
                else:
                    dest = salida.with_suffix(f".{fmt}")
            else:
                dest = Path(f"{ej.id}.{fmt}")

            dest.parent.mkdir(parents=True, exist_ok=True)

            if fmt == "md":
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
                dest.write_text(md_salida, encoding="utf-8")
                console.print(f"[green]✓ Ejercicio exportado a Markdown:[/green] {dest}")
            elif fmt in ("typ", "typst"):
                typ_salida, _ = renderizar_ejercicio_typst(
                    ejercicio=ej,
                    dir_ejercicio=dir_ej,
                    template_nombre_o_ruta=template,
                    incluir_solucion=solucion,
                    incluir_pistas=pistas,
                    dir_banco=banco,
                )
                dest.write_text(typ_salida, encoding="utf-8")
                console.print(f"[green]✓ Ejercicio exportado a Typst:[/green] {dest}")
            elif fmt == "html":
                html_salida, _ = renderizar_ejercicio_html(
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
                dest.write_text(html_salida, encoding="utf-8")
                console.print(f"[green]✓ Ejercicio exportado a HTML:[/green] {dest}")
            elif fmt == "pdf":
                try:
                    typst_salida, base_p = renderizar_ejercicio_typst(
                        ejercicio=ej,
                        dir_ejercicio=dir_ej,
                        template_nombre_o_ruta=template,
                        incluir_solucion=solucion,
                        incluir_pistas=pistas,
                        dir_banco=banco,
                    )
                    pdf_path = compilar_typst_a_pdf(typst_salida, dest, root_dir=base_p)
                    console.print(f"[green]✓ Ejercicio exportado a PDF (Typst):[/green] {pdf_path}")
                except Exception as e_typst:
                    try:
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
                        pdf_path = compilar_pdf(html_salida, dest, base_url=str(base_p) if base_p else ".")
                        console.print(f"[green]✓ Ejercicio exportado a PDF:[/green] {pdf_path}")
                    except Exception as e:
                        console.print(f"[red]Error exportando PDF: {e_typst or e}[/red]")
                        raise typer.Exit(code=1)
        return
    else:
        out_dir = salida or Path("dist")
        out_dir.mkdir(parents=True, exist_ok=True)
        tipos_str = ", ".join(t.upper() for t in tipos)
        console.print(f"[bold]Exportando {len(candidatos)} ejercicios a [{tipos_str}] en {out_dir}...[/bold]")

        tabla = Table(title=f"Exportación ({tipos_str})")
        tabla.add_column("Ejercicio", style="cyan")
        tabla.add_column("Formato", justify="center")
        tabla.add_column("Archivo generado", style="green")

        for dir_ej, ej in candidatos:
            for fmt in tipos:
                file_dest = out_dir / f"{ej.id}.{fmt}"
                if fmt == "md":
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
                    file_dest.write_text(md_salida, encoding="utf-8")
                elif fmt in ("typ", "typst"):
                    typ_salida, _ = renderizar_ejercicio_typst(
                        ejercicio=ej,
                        dir_ejercicio=dir_ej,
                        template_nombre_o_ruta=template,
                        incluir_solucion=solucion,
                        incluir_pistas=pistas,
                        dir_banco=banco,
                    )
                    file_dest.write_text(typ_salida, encoding="utf-8")
                elif fmt == "html":
                    html_salida, _ = renderizar_ejercicio_html(
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
                    file_dest.write_text(html_salida, encoding="utf-8")
                elif fmt == "pdf":
                    try:
                        typst_salida, base_p = renderizar_ejercicio_typst(
                            ejercicio=ej,
                            dir_ejercicio=dir_ej,
                            template_nombre_o_ruta=template,
                            incluir_solucion=solucion,
                            incluir_pistas=pistas,
                            dir_banco=banco,
                        )
                        compilar_typst_a_pdf(typst_salida, file_dest, root_dir=base_p)
                    except Exception:
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
                        compilar_pdf(html_salida, file_dest, base_url=str(base_p) if base_p else ".")

                tabla.add_row(ej.id, fmt.upper(), str(file_dest))

        console.print(tabla)
        console.print(f"[green]✓ Archivos generados en {out_dir}[/green]")


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
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo YAML o carpeta de la guía."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
    enunciados: bool = typer.Option(False, "--enunciados", "-e", help="Mostrar enunciados completos."),
    soluciones: bool = typer.Option(False, "--soluciones", "-s", help="Mostrar soluciones modelo."),
    pistas: bool = typer.Option(False, "--pistas", "-p", help="Mostrar pistas progresivas."),
) -> None:
    """Muestra el detalle estructurado de una guía y sus ejercicios."""
    ruta = resolver_ruta_guia(guia_archivo, dir_guias=guias_dir)
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
    archivo: str = typer.Argument(..., help="Nombre del archivo YAML o carpeta (ej: 'guia_punteros.yaml' o 'guia_punteros')."),
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
    if archivo.endswith(".yaml") or archivo.endswith(".yml"):
        dest = guias_dir / archivo
    else:
        # Carpeta unificada
        dest = guias_dir / archivo / "guia.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)

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
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo/carpeta de la guía."),
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio a agregar."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Agrega un ejercicio del banco a una guía compuesta."""
    ruta = resolver_ruta_guia(guia_archivo, dir_guias=guias_dir)
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
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo/carpeta de la guía."),
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio a remover."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Remueve un ejercicio de una guía compuesta."""
    ruta = resolver_ruta_guia(guia_archivo, dir_guias=guias_dir)
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
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo/carpeta de la guía."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
    ripley: Optional[str] = typer.Option(None, "--ripley", help="Ruta a ripley."),
) -> None:
    """Verifica con ripley todas las soluciones modelo de los ejercicios de la guía."""
    ruta = resolver_ruta_guia(guia_archivo, dir_guias=guias_dir)
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
    guia_archivo: str = typer.Argument(..., help="Ruta o nombre del archivo/carpeta de la guía."),
    type: str = typer.Option("pdf", "--type", "-t", help="Formatos de salida separados por comas: pdf, md, html (ej: --type=pdf,md)."),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Archivo de salida o directorio destino."),
    template: Optional[str] = typer.Option(None, "--template", "-T", help="Plantilla personalizada."),
    pipeline_md: bool = typer.Option(False, "--pipeline-md", help="Generar Markdown intermedio antes de compilar PDF."),
    soluciones: bool = typer.Option(False, "--soluciones", "-s", help="Incluir apéndice de soluciones."),
    pistas: bool = typer.Option(False, "--pistas", "-p", help="Incluir pistas progresivas."),
    css: Optional[Path] = typer.Option(None, "--css", exists=True, help="Archivo CSS adicional."),
    guias_dir: Path = typer.Option(Path("guias"), "--guias", help="Directorio de guías."),
) -> None:
    """Exporta la guía completa a PDF, Markdown o HTML."""
    ruta = resolver_ruta_guia(guia_archivo, dir_guias=guias_dir)
    if not ruta.is_file():
        console.print(f"[red]No se encontró la guía '{guia_archivo}'.[/red]")
        raise typer.Exit(code=1)

    exportar_contenido(
        objetivo=str(ruta),
        type=type,
        banco=banco,
        salida=salida,
        template=template,
        pipeline_md=pipeline_md,
        solucion=soluciones,
        pistas=pistas,
        tests=False,
        css=css,
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


@verify_app.command("test-harness")
@verify_app.command("harness")
@app.command("test-harness", hidden=True)
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
        help="Id del ejercicio en el banco, o ruta a guia.yaml / carpeta de guía / carpeta de ejercicio.",
    ),
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio del banco de ejercicios."),
    salida: Optional[Path] = typer.Option(None, "--salida", "-o", help="Archivo .ripkg o directorio de salida."),
    sign_key: Optional[str] = typer.Option(None, "--sign-key", help="Clave GPG para firmar el paquete."),
    starter: bool = typer.Option(False, "--starter", help="Generar también estructura starter repo para GitHub Classroom."),
) -> None:
    """Empaqueta ejercicios o guías como .ripkg para Ripley y starter repos."""
    from deckard.core.bank import buscar_ejercicios
    from deckard.core.guides import resolver_ruta_guia
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


@app.command("stats")
@bank_app.command("stats")
def cmd_stats(
    banco: Path = typer.Option(Path("banco"), "--banco", help="Directorio raíz del banco a analizar."),
) -> None:
    """Grafica la distribución de Bloom y tiempos acumulados con histogramas ASCII en terminal."""
    from deckard.core.bank import buscar_ejercicios
    from deckard.core.cache import update_bank_cache

    if banco.is_dir():
        update_bank_cache(banco)
    ejs = buscar_ejercicios(banco, recursivo=True)
    if not ejs:
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
    from deckard.core.bank import buscar_ejercicios
    import shutil
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
    from deckard.core.bank import buscar_ejercicios
    import shutil

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
    from deckard.core.bank import buscar_ejercicios
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
def cmd_doctor() -> None:
    """Verifica dependencias externas del sistema (GCC, Typst, Daedalus, Git)."""
    from deckard.core.doctor import ejecutar_diagnostico_doctor
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
    from deckard.core.bank import buscar_ejercicios, cargar_ejercicio
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


@app.command("export-classroom")
@app.command("publish-classroom")
def cmd_export_classroom(
    ejercicio_id: str = typer.Argument(..., help="ID del ejercicio a exportar como asignación."),
    salida: Path = typer.Option(Path("classroom_assignments"), "--salida", "-o", help="Directorio de salida para la asignación."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
    nombre_repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Nombre personalizado para el repositorio."),
) -> None:
    """Genera la estructura completa de un repositorio para GitHub Classroom (README, starter code, Makefile, CI)."""
    from deckard.core.bank import buscar_ejercicios
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
    from deckard.core.bank import buscar_ejercicios, cargar_ejercicio
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
    from deckard.core.guides import cargar_guia_con_ejercicios
    from deckard.core.load_checker import auditar_carga_horaria
    from deckard.core.models import Ejercicio, NivelBloom

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
    from deckard.core.guides import cargar_guia_con_ejercicios, guardar_yaml_guia
    from deckard.core.variant import seleccionar_variantes_homologas
    from deckard.core.models import GuiaSpec

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


@app.command("audit-guide")
def cmd_audit_guide(
    guia: Path = typer.Argument(..., help="Ruta a la guía YAML a auditar."),
    banco: Path = typer.Option(Path("banco"), "--banco", "-b", help="Directorio raíz del banco."),
) -> None:
    """Audita la completitud y calidad técnica de todos los ejercicios de una guía."""
    from deckard.core.guides import cargar_guia_con_ejercicios
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
    from deckard.core.bank import cargar_ejercicio, listar_ejercicios, guardar_ejercicio
    from deckard.core.guides import cargar_guia_con_ejercicios
    from deckard.core.languagetool_checker import (
        analizar_ejercicio_languagetool,
        aplicar_autofix_ejercicio,
        generar_reporte_markdown_languagetool,
    )

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
    from deckard.core.bank import buscar_ejercicios, cargar_ejercicio
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
    from deckard.core.bank import buscar_ejercicios, cargar_ejercicio, listar_ejercicios
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
    from deckard.core.bank import buscar_ejercicios, cargar_ejercicio
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

# ---------------------------------------------------------------------------
# Mejora de Consignas y Bancos con OpenCode (improve / ai)
# ---------------------------------------------------------------------------

improve_app = typer.Typer(
    name="improve",
    help="Mejora y curaduría pedagógica de consignas y bancos de ejercicios con OpenCode.",
    no_args_is_help=True,
)


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
        AspectoMejora,
        construir_prompt_ejercicio,
        construir_prompt_gift,
        mejorar_ejercicio,
        mejorar_archivo_gift,
    )
    from deckard.core.opencode import DEFAULT_MODEL

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


app.add_typer(improve_app, name="improve")
app.add_typer(improve_app, name="ai", hidden=True)
app.add_typer(improve_app, name="opencode", hidden=True)

