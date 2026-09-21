"""Comandos de inicialización de banco y creación de ejercicios (init, new)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

from deckard.core.bank import (
    guardar_ejercicio,
)
from deckard.core.models import Ejercicio, NivelBloom

from deckard.cli._shared import (
    app,
    console,
)

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


