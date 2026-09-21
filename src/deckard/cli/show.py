"""Comando `show`: visualización de enunciado y secciones de un ejercicio."""

from __future__ import annotations

from pathlib import Path

from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
import typer

from deckard.core.bank import (
    buscar_ejercicios,
    cargar_ejercicio,
)
from deckard.core.export import (
    cargar_tests_ejercicio,
)

from deckard.cli._shared import (
    app,
    console,
    bank_app,
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


