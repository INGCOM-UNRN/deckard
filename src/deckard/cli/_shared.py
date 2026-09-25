"""Base compartida del CLI de deckard: imports comunes, la app raíz, los
sub-apps de typer y los helpers usados por más de un módulo de comandos.

Cada módulo temático de `deckard.cli.*` importa de acá lo que necesita y
registra sus propios comandos sobre `app` o el sub-app correspondiente. El
registro efectivo ocurre al importarse cada módulo desde
`deckard/cli/__init__.py`.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import shlex
import shutil
from typing import List, Optional

from rich.console import Console
import typer
import yaml

from deckard.core.bank import (
    buscar_ejercicios,
    cargar_ejercicio,
)
from deckard.core.guides import (
    cargar_guia_con_ejercicios,
    resolver_ruta_guia,
)
from deckard import __version__
from deckard.core.models import Ejercicio

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    name="deckard",
    help="Gestor de bancos de ejercicios prácticos, guías y graduación (Programación 1).",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"deckard {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Muestra la versión de deckard y sale.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Gestor de bancos de ejercicios prácticos, guías y graduación (Programación 1)."""
    pass


def _leer_yaml(ruta: Path) -> dict:
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _ejecutar_herramienta(comando: str) -> int:
    """Corre un comando externo heredando consola; avisa si no está instalado."""
    partes = shlex.split(comando) if isinstance(comando, str) else list(comando)
    if not partes:
        return 0
    binario = partes[0]
    if shutil.which(binario) is None:
        console.print(f"[red]'{binario}' no está instalado.[/red]")
        return 127
    return subprocess.call(partes)


class DefaultCommandGroup(typer.core.TyperGroup):
    """Permite ejecutar subcomandos o delegar al comando por defecto 'run'."""

    def parse_args(self, ctx, args):
        if not args:
            return super().parse_args(ctx, args)
        cmd_name = args[0]
        if cmd_name not in ["--help", "-h"] and self.get_command(ctx, cmd_name) is None:
            args = ["run"] + list(args)
        return super().parse_args(ctx, args)


bank_app = typer.Typer(name="bank", help="Inspección del banco de ejercicios.", no_args_is_help=True)
app.add_typer(bank_app, name="bank")

verify_app = typer.Typer(
    cls=DefaultCommandGroup,
    name="verify",
    help="Verificación pedagógica (ripley check), fuzzing (dredd) y arnés de pruebas (vasquez inject).",
    no_args_is_help=False,
)
app.add_typer(verify_app, name="verify")

tag_app = typer.Typer(name="tag", help="Gestión y consulta de etiquetas (tags) en el banco.", no_args_is_help=True)
app.add_typer(tag_app, name="tag")

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

guide_app = typer.Typer(name="guide", help="Gestión, inspección y exportación de guías.", no_args_is_help=True)
app.add_typer(guide_app, name="guide")

spec_app = typer.Typer(
    name="spec",
    help="Gestión, validación y composición de especificaciones de guías (GuiaSpec).",
    no_args_is_help=True,
)
app.add_typer(spec_app, name="spec")

improve_app = typer.Typer(
    name="improve",
    help="Mejora y curaduría pedagógica de consignas y bancos de ejercicios con OpenCode.",
    no_args_is_help=True,
)
app.add_typer(improve_app, name="improve")
app.add_typer(improve_app, name="ai", hidden=True)
app.add_typer(improve_app, name="opencode", hidden=True)


def _resolver_dir_ejercicio(ejercicio_id: str, banco: Path) -> Path:
    p = Path(ejercicio_id)
    if p.is_dir() and (p / "ejercicio.yaml").is_file():
        return p
    if p.is_file() and p.name == "ejercicio.yaml":
        return p.parent
    candidatos = buscar_ejercicios(banco, patron=ejercicio_id, recursivo=True)
    if candidatos:
        return candidatos[0][0]
    if (banco / ejercicio_id).is_dir():
        return banco / ejercicio_id
    raise typer.BadParameter(f"No se encontró el ejercicio '{ejercicio_id}' en {banco}.")


def _cargar_ejercicios_target(target: str, banco: Path) -> List[Ejercicio]:
    p = Path(target)
    if p.is_file() and p.suffix in (".yaml", ".yml"):
        info = cargar_guia_con_ejercicios(p, banco)
        return info.ejercicios
    if (banco / target).is_file() or (banco / f"{target}.yaml").is_file():
        p_guia = resolver_ruta_guia(Path(target))
        if p_guia.is_file():
            info = cargar_guia_con_ejercicios(p_guia, banco)
            return info.ejercicios
    if p.is_dir() and (p == banco or p.resolve() == banco.resolve()):
        tuplas = buscar_ejercicios(banco, recursivo=True)
        return [cargar_ejercicio(t[0]) for t in tuplas]
    dir_ej = _resolver_dir_ejercicio(target, banco)
    return [cargar_ejercicio(dir_ej)]
