"""CLI de deckard: banco de ejercicios, verificación y composición de guías."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from deckard.core.bank import (
    componer_guia,
    cargar_ejercicio,
    guardar_ejercicio,
    listar_ejercicios,
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


# ---------------------------------------------------------------------------
# init / new / bank
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


bank_app = typer.Typer(name="bank", help="Inspección del banco.", no_args_is_help=True)
app.add_typer(bank_app, name="bank")


@bank_app.command("list")
def bank_list(banco: Path = typer.Option(Path("banco"), "--banco")) -> None:
    """Lista los ejercicios del banco con su nivel y carga."""
    tabla = Table(title="Banco de ejercicios")
    tabla.add_column("id", style="cyan")
    tabla.add_column("tema")
    tabla.add_column("bloom", justify="center")
    tabla.add_column("min", justify="right")
    tabla.add_column("verificado", justify="center")
    total_min = 0
    for e in listar_ejercicios(banco):
        total_min += e.minutos_estimados
        tabla.add_row(e.id, e.tema, f"B{int(e.bloom)} {e.bloom.name.lower()}",
                      str(e.minutos_estimados), "✓" if e.verificado else "—")
    console.print(tabla)
    console.print(f"[dim]{total_min} minutos totales de banco[/dim]")


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


@app.command()
def verify(
    ejercicio_id: str = typer.Argument(..., help="Id del ejercicio en el banco."),
    banco: Path = typer.Option(Path("banco"), "--banco"),
    ripley: Optional[str] = typer.Option(None, "--ripley", help="Ruta al binario/zipapp de ripley."),
) -> None:
    """Verifica la solución modelo del ejercicio usando ripley check."""
    dir_ej = banco / ejercicio_id
    try:
        cargar_ejercicio(dir_ej)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    resultado = verificar_ejercicio(dir_ej, ruta_ripley=ripley)
    color = "green" if resultado.ok else "red"
    console.print(f"[{color}]{resultado.marca} {resultado.ejercicio}[/{color}] — {resultado.detalle}")
    raise typer.Exit(code=0 if resultado.ok else 1)


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


def _ejecutar_herramienta(comando: str) -> int:
    """Corre un comando externo heredando consola; avisa si no está instalado."""
    import shutil as _shutil
    binario = comando.split()[0]
    if _shutil.which(binario) is None:
        console.print(f"[red]'{binario}' no está instalado.[/red]")
        return 127
    return subprocess.call(comando, shell=True)


@app.command("fuzz")
def fuzz(
    ejercicio_id: str = typer.Argument(..., help="Id del ejercicio en el banco."),
    banco: Path = typer.Option(Path("banco"), "--banco"),
    cantidad: int = typer.Option(8, "--cantidad", "-n"),
    segundos: int = typer.Option(15, "--segundos"),
) -> None:
    """Endurece los tests del ejercicio usando `dredd fuzz-gen` (requiere dredd)."""
    dir_ej = banco / ejercicio_id
    if not dir_ej.is_dir():
        console.print(f"[red]No existe el ejercicio '{ejercicio_id}'.[/red]")
        raise typer.Exit(code=1)

    modelo = dir_ej / "solucion.c"
    if not modelo.is_file():
        console.print("[red]El ejercicio no tiene solucion.c[/red]")
        raise typer.Exit(code=1)

    destino = dir_ej / "tests"
    cmd = (f"dredd fuzz-gen {modelo} -o {destino} --cantidad {cantidad} "
           f"--segundos {segundos}")
    console.print(f"[dim]$ {cmd}[/dim]")
    rc = _ejecutar_herramienta(cmd)
    if rc == 0:
        console.print("[green]✓ Testcases endurecidos. Recordá marcar 'verificado' "
                      "tras re-correr deckard verify.[/green]")
    raise typer.Exit(code=rc)


@app.command("test-harness")
def test_harness(
    ejercicio_id: str = typer.Argument(..., help="Id del ejercicio en el banco."),
    spec: Path = typer.Argument(..., exists=True, help="spec.yaml del arnés."),
    ripley: Optional[str] = typer.Option(None, "--ripley"),
) -> None:
    """Corre el arnés de prueba con inyección de malloc vía `ripley harness`."""
    dir_ej = banco / ejercicio_id
    ruta = f"--ripley {ripley} " if ripley else ""
    # ripley harness espera cwd del spec para resolver archivo_fuente relativo
    import os
    os.chdir(spec.parent.parent if len(spec.parent.parts) > 1 else Path("."))
    cmd = f"ripley harness {spec.name} {ruta.strip()}"
    console.print(f"[dim]$ {cmd}[/dim]")
    rc = _ejecutar_herramienta(cmd)
    raise typer.Exit(code=rc)


import subprocess  # noqa: E402
