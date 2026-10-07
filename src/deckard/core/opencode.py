"""Integración de Deckard con OpenCode (Plan Go) y sandbox bwrap."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import List, Optional, Tuple


DEFAULT_MODEL = "opencode-go/qwen3.8-max"


def buscar_ejecutable_opencode(usar_sandbox: bool = True) -> Tuple[Optional[str], bool]:
    """Descubre el binario o wrapper de OpenCode en el sistema.

    Retorna una tupla (ruta_ejecutable, es_sandboxed).
    """
    if usar_sandbox:
        cand_sandboxed = shutil.which("opencode-sandboxed") or os.path.expanduser("~/bin/opencode-sandboxed")
        if cand_sandboxed and os.path.exists(cand_sandboxed) and os.access(cand_sandboxed, os.X_OK):
            return str(cand_sandboxed), True

    cand_direct = (
        shutil.which("opencode")
        or os.path.expanduser("~/.opencode/bin/opencode")
    )
    if cand_direct and os.path.exists(cand_direct) and os.access(cand_direct, os.X_OK):
        return str(cand_direct), False

    return None, False


def listar_modelos_opencode(provider: Optional[str] = None, timeout: int = 15) -> List[str]:
    """Interroga al CLI de OpenCode para obtener la lista de modelos disponibles."""
    # Para listar modelos usamos directamente el binario opencode
    cand_direct: Optional[str] = (
        shutil.which("opencode")
        or os.path.expanduser("~/.opencode/bin/opencode")
    )
    if not (cand_direct and os.path.exists(cand_direct) and os.access(cand_direct, os.X_OK)):
        ejecutable, _ = buscar_ejecutable_opencode(usar_sandbox=False)
        cand_direct = ejecutable

    if not cand_direct:
        raise RuntimeError(
            "No se encontró el ejecutable 'opencode' para consultar los modelos disponibles."
        )

    cmd = [cand_direct, "models"]
    if provider:
        cmd.append(provider)

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"La consulta de modelos a OpenCode excedió el tiempo límite de {timeout}s.") from e
    except Exception as e:
        raise RuntimeError(f"Error al consultar modelos de OpenCode: {e}") from e

    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"OpenCode models finalizó con código {proc.returncode}: {err_msg}")

    modelos = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Ignorar mensajes informativos como 'Models cache refreshed'
        if line.startswith("Models cache") or line.startswith("opencode models") or " " in line:
            continue
        modelos.append(line)

    return modelos


def ejecutar_opencode(
    prompt: str,
    modelo: str = DEFAULT_MODEL,
    dir_trabajo: Optional[Path] = None,
    timeout: int = 180,
    usar_sandbox: bool = True,
    system_prompt: Optional[str] = None,
) -> str:
    """Ejecuta una consulta a OpenCode vía CLI (sandboxed si está disponible).

    Lanza RuntimeError si no se encuentra el binario o si la ejecución falla.
    """
    ejecutable, es_sandboxed = buscar_ejecutable_opencode(usar_sandbox=usar_sandbox)
    if not ejecutable:
        raise RuntimeError(
            "No se encontró el binario de OpenCode ni el wrapper 'opencode-sandboxed'. "
            "Asegurate de que 'opencode' esté instalado en el PATH o en ~/.opencode/bin/opencode."
        )

    cwd = str(dir_trabajo.resolve()) if dir_trabajo else str(Path.cwd())

    prompt_final = prompt
    if system_prompt:
        prompt_final = f"### DIRECTIVA DEL SISTEMA:\n{system_prompt}\n\n### TAREA:\n{prompt}"

    if es_sandboxed:
        cmd = [
            ejecutable,
            "-m", modelo,
            "--dir", cwd,
            prompt_final,
        ]
    else:
        cmd = [
            ejecutable,
            "run",
            "-m", modelo,
            "--dir", cwd,
            prompt_final,
        ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"La llamada a OpenCode excedió el tiempo límite de {timeout} segundos.") from e
    except Exception as e:
        raise RuntimeError(f"Error al invocar OpenCode: {e}") from e

    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"OpenCode finalizó con código {proc.returncode}: {err_msg}")

    return proc.stdout.strip()


def extraer_bloque_codigo(texto: str, lenguaje: Optional[str] = None) -> str:
    """Extrae el contenido de un bloque cercado de markdown (```lang ... ```).

    Si no se encuentra un bloque cercado, devuelve el texto limpio original.
    """
    if lenguaje:
        patron = rf"```(?:{lenguaje})\s*\n(.*?)\n```"
        match = re.search(patron, texto, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Búsqueda genérica de bloque cercado
    match_gen = re.search(r"```[a-zA-Z0-9_-]*\s*\n(.*?)\n```", texto, re.DOTALL)
    if match_gen:
        return match_gen.group(1).strip()

    return texto.strip()
