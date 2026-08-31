"""Sincronización Git de bancos de ejercicios distribuidos en Deckard."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console


def sincronizar_banco_git(
    banco_dir: Path,
    remote_url: Optional[str] = None,
    branch: str = "main",
    console: Optional[Console] = None,
) -> Dict[str, Any]:
    """Sincroniza un directorio de banco con un repositorio Git remoto."""
    cons = console or Console()
    banco_path = Path(banco_dir).resolve()
    git_bin = shutil.which("git")

    if not git_bin:
        msg = "Git no se encuentra instalado en el sistema."
        cons.print(f"[bold red]✗ Error:[/bold red] {msg}")
        return {"ok": False, "error": msg}

    if not (banco_path / ".git").is_dir():
        if remote_url:
            cons.print(f"[bold cyan]Clonando banco remoto desde:[/bold cyan] {remote_url}...")
            res = subprocess.run([git_bin, "clone", remote_url, str(banco_path)], capture_output=True, text=True)
            if res.returncode != 0:
                cons.print(f"[bold red]Fallo al clonar:[/bold red] {res.stderr}")
                return {"ok": False, "error": res.stderr}
            cons.print(f"[bold green]✓ Banco clonado con éxito.[/bold green]")
            return {"ok": True, "action": "cloned"}
        else:
            cons.print(f"[bold yellow]Inicializando nuevo repositorio Git en:[/bold yellow] {banco_path}...")
            subprocess.run([git_bin, "init", "-b", branch, str(banco_path)], capture_output=True)
            return {"ok": True, "action": "initialized"}

    # Ya es un repositorio Git, hacer pull
    cons.print(f"[bold cyan]Sincronizando banco local con rama '{branch}'...[/bold cyan]")
    res = subprocess.run([git_bin, "-C", str(banco_path), "pull", "--ff-only"], capture_output=True, text=True)
    if res.returncode == 0:
        cons.print(f"[bold green]✓ Banco sincronizado con éxito.[/bold green]")
        return {"ok": True, "action": "pulled", "output": res.stdout}
    else:
        cons.print(f"[bold yellow]Nota en pull:[/bold yellow] {res.stderr.strip() or res.stdout.strip()}")
        return {"ok": True, "action": "checked", "detail": res.stderr}
