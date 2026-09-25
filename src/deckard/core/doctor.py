"""Diagnóstico de dependencias externas del sistema para Deckard."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table


from pathlib import Path


def chequear_herramienta(comando: str, args_version: str = "--version") -> Dict[str, Any]:
    """Verifica si un comando está disponible en $PATH y obtiene su versión."""
    path = shutil.which(comando)
    if not path:
        return {"disponible": False, "version": None, "ruta": None}
    
    version = "Instalado"
    try:
        res = subprocess.run(
            [comando, args_version],
            capture_output=True,
            text=True,
            timeout=3,
        )
        salida = (res.stdout or res.stderr).strip().splitlines()
        if res.returncode == 0 and salida and not salida[0].startswith("Usage:"):
            version = salida[0]
        else:
            # Si el comando es un script de Python con shebang, intentar leer __version__
            try:
                p = Path(path)
                lineas = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                if lineas and lineas[0].startswith("#!"):
                    shebang_py = lineas[0].lstrip("#!").strip()
                    if shutil.which(shebang_py):
                        proc_ver = subprocess.run(
                            [shebang_py, "-c", f"import {comando}; print(getattr({comando}, '__version__', 'Instalado'))"],
                            capture_output=True,
                            text=True,
                            timeout=2,
                        )
                        if proc_ver.returncode == 0 and proc_ver.stdout.strip():
                            version = proc_ver.stdout.strip()
            except Exception:
                pass
            if version == "Instalado" and salida and not salida[0].startswith("Usage:"):
                version = salida[0]
    except Exception:
        version = "Detectada"
        
    return {"disponible": True, "version": version, "ruta": path}


HERRAMIENTAS = [
    ("gcc", "Compilador GNU C (necesario para verificar ejercicios)", True, "sudo apt install build-essential"),
    ("typst", "Compilador Typst para PDFs de alta calidad", False, "cargo install typst-cli o descargar de github.com/typst/typst"),
    ("daedalus", "Compilador pedagógico con explicaciones en español", False, "uv tool install git+https://github.com/INGCOM-UNRN-P1/daedalus"),
    ("ripley", "Linter pedagógico de cátedra", False, "uv tool install git+https://github.com/INGCOM-UNRN-P1/ripley"),
    ("git", "Control de versiones para gestión de bancos descentralizados", False, "sudo apt install git"),
]


def diagnosticar() -> List[Dict[str, Any]]:
    """Estado de cada herramienta externa (sin imprimir nada)."""
    chequeos = []
    for cmd, desc, obligatorio, fix in HERRAMIENTAS:
        info = chequear_herramienta(cmd)
        chequeos.append({
            "nombre": cmd,
            "requerido": obligatorio,
            "ok": info["disponible"],
            "detalle": f"{info['version']} ({info['ruta']})" if info["disponible"] else "No encontrado en $PATH",
            "proposito": desc,
            "sugerencia": "" if info["disponible"] else fix,
        })
    return chequeos


def informe_json(chequeos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sobre JSON común de `doctor --json` (schema_version 1.0.0)."""
    from deckard import __version__

    return {
        "schema_version": "1.0.0",
        "herramienta": "deckard",
        "version": __version__,
        "ok": all(c["ok"] for c in chequeos if c["requerido"]),
        "chequeos": chequeos,
    }


def ejecutar_diagnostico_doctor(console: Optional[Console] = None) -> bool:
    """Ejecuta y muestra el diagnóstico integral de herramientas requeridas y opcionales."""
    cons = console or Console()
    tabla = Table(title="🏥 Diagnóstico del Entorno de Deckard (doctor)", border_style="cyan")
    tabla.add_column("Herramienta", style="bold white")
    tabla.add_column("Estado", justify="center")
    tabla.add_column("Versión / Ruta", style="dim")
    tabla.add_column("Propósito / Acción sugerida", style="yellow")

    todo_ok = True
    for chequeo in diagnosticar():
        if chequeo["ok"]:
            estado = "[bold green]✓ OK[/bold green]"
            detalles = chequeo["detalle"]
            accion = chequeo["proposito"]
        else:
            if chequeo["requerido"]:
                estado = "[bold red]✗ Faltante (Crítico)[/bold red]"
                todo_ok = False
            else:
                estado = "[yellow]! Opcional[/yellow]"
            detalles = "[dim]No encontrado en $PATH[/dim]"
            accion = f"{chequeo['proposito']} ↳ Instalar: {chequeo['sugerencia']}"
        tabla.add_row(chequeo["nombre"], estado, detalles, accion)

    cons.print(tabla)
    return todo_ok
