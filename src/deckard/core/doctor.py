"""Diagnóstico de dependencias externas del sistema para Deckard."""

from __future__ import annotations

import shutil
import subprocess
from typing import Dict, Any, List

from rich.console import Console
from rich.table import Table


def chequear_herramienta(comando: str, args_version: str = "--version") -> Dict[str, Any]:
    """Verifica si un comando está disponible en $PATH y obtiene su versión."""
    path = shutil.which(comando)
    if not path:
        return {"disponible": False, "version": None, "ruta": None}
    
    try:
        res = subprocess.run(
            [comando, args_version],
            capture_output=True,
            text=True,
            timeout=3,
        )
        salida = (res.stdout or res.stderr).strip().splitlines()
        version = salida[0] if salida else "Desconocida"
    except Exception:
        version = "Detectada"
        
    return {"disponible": True, "version": version, "ruta": path}


def ejecutar_diagnostico_doctor(console: Optional[Console] = None) -> bool:
    """Ejecuta y muestra el diagnóstico integral de herramientas requeridas y opcionales."""
    cons = console or Console()
    
    herramientas = [
        ("gcc", "Compilador GNU C (necesario para verificar ejercicios)", True, "sudo apt install build-essential"),
        ("typst", "Compilador Typst para PDFs de alta calidad", False, "cargo install typst-cli o descargar de github.com/typst/typst"),
        ("daedalus", "Compilador pedagógico con explicaciones en español", False, "pip install -e ./daedalus"),
        ("ripley", "Linter pedagógico de cátedra", False, "pip install -e ./ripley"),
        ("git", "Control de versiones para gestión de bancos descentralizados", False, "sudo apt install git"),
    ]
    
    tabla = Table(title="🏥 Diagnóstico del Entorno de Deckard (doctor)", border_style="cyan")
    tabla.add_column("Herramienta", style="bold white")
    tabla.add_column("Estado", justify="center")
    tabla.add_column("Versión / Ruta", style="dim")
    tabla.add_column("Propósito / Acción sugerida", style="yellow")
    
    todo_ok = True
    for cmd, desc, obligatorio, fix in herramientas:
        info = chequear_herramienta(cmd)
        if info["disponible"]:
            estado = "[bold green]✓ OK[/bold green]"
            detalles = f"{info['version']} ([cyan]{info['ruta']}[/cyan])"
            accion = desc
        else:
            if obligatorio:
                estado = "[bold red]✗ Faltante (Crítico)[/bold red]"
                todo_ok = False
            else:
                estado = "[yellow]! Opcional[/yellow]"
            detalles = "[dim]No encontrado en $PATH[/dim]"
            accion = f"{desc} ↳ Instalar: {fix}"
            
        tabla.add_row(cmd, estado, detalles, accion)
        
    cons.print(tabla)
    return todo_ok
