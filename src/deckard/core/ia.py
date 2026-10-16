"""Consultas de deckard a un modelo de lenguaje, con el proveedor que configure el docente.

El proveedor y el modelo los resuelve `yutani.ia` igual que en el resto del ecosistema
(`--proveedor`/`--model`, `P1_IA_PROVEEDOR`, `~/.config/p1/ia.toml`): Gemini, un servidor
local con la API de OpenAI (Ollama, llama.cpp…), OpenCode o Claude. Sin nada configurado,
deckard sigue usando OpenCode, como antes.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import List, Optional

from yutani import ia

PROVEEDOR_POR_DEFECTO = "opencode"
DEFAULT_MODEL = ia.MODELOS_POR_DEFECTO[PROVEEDOR_POR_DEFECTO]
ErrorIA = ia.ErrorIA


def configuracion(proveedor: Optional[str] = None, modelo: Optional[str] = None) -> ia.ConfigIA:
    return ia.configuracion("deckard", proveedor=proveedor, modelo=modelo,
                            proveedor_por_defecto=PROVEEDOR_POR_DEFECTO)


def consultar_ia(
    prompt: str,
    *,
    proveedor: Optional[str] = None,
    modelo: Optional[str] = None,
    dir_trabajo: Optional[Path] = None,
    timeout: int = 180,
    usar_sandbox: bool = True,
    system_prompt: Optional[str] = None,
) -> str:
    """El texto que devuelve el modelo (ErrorIA, que es un RuntimeError, si falla)."""
    config = replace(configuracion(proveedor, modelo), timeout=float(timeout), sandbox=usar_sandbox)
    cliente = ia.cliente(config, directorio=dir_trabajo)
    return cliente.generar(prompt, sistema=system_prompt).strip()


def listar_modelos(proveedor: Optional[str] = None, filtro: Optional[str] = None) -> List[str]:
    """Modelos del proveedor; con `filtro` (p. ej. opencode-go), solo los de ese prefijo."""
    modelos = ia.cliente(configuracion(proveedor)).modelos()
    return [m for m in modelos if not filtro or m.startswith(filtro.rstrip("/") + "/")]


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
