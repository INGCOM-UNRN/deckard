"""Esquema de `ejercicio.yaml`: errores en español y JSON Schema (revisión 07, deckard).

Un `ejercicio.yaml` mal escrito se descubría tarde y con el mensaje de pydantic en inglés
(«Field required», «String should match pattern»). Ahora cada error dice el archivo, el campo y qué
se esperaba; y el JSON Schema publicado (`deckard bank schema`, `esquemas/ejercicio.schema.json`)
permite que el editor valide mientras se escribe:

    # yaml-language-server: $schema=../../esquemas/ejercicio.schema.json
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from pydantic import ValidationError

ID_ESQUEMA = "https://ingcom-unrn-p1.github.io/deckard/ejercicio.schema.json"


class EjercicioInvalido(ValueError):
    """`ejercicio.yaml` no cumple el esquema; el mensaje enumera los problemas en español."""

    def __init__(self, archivo: Path, problemas: List[str]):
        self.archivo = archivo
        self.problemas = problemas
        super().__init__(f"{archivo}: el ejercicio no es válido:\n" + "\n".join(f"  - {p}" for p in problemas))


def _campo(loc) -> str:
    partes: List[str] = []
    for p in loc:
        partes.append(f"[{p}]" if isinstance(p, int) else (("." if partes else "") + str(p)))
    return "".join(partes) or "(raíz)"


def traducir(error: Dict[str, Any]) -> str:
    campo = _campo(error.get("loc", ()))
    tipo = error.get("type", "")
    ctx = error.get("ctx") or {}
    entrada = error.get("input")
    if tipo == "missing":
        return f"falta el campo obligatorio «{campo}»."
    if tipo == "extra_forbidden":
        return f"«{campo}» no es un campo de ejercicio.yaml (¿un error de tipeo?)."
    if tipo == "string_pattern_mismatch":
        return f"«{campo}» = {entrada!r} no tiene el formato esperado ({ctx.get('pattern')}): minúsculas, números, - y _."
    if tipo in ("enum", "literal_error"):
        return f"«{campo}» = {entrada!r} no es un valor válido; opciones: {ctx.get('expected', '?')}."
    if tipo in ("int_parsing", "int_type", "int_from_float"):
        return f"«{campo}» tiene que ser un número entero (vino {entrada!r})."
    if tipo in ("float_parsing", "float_type"):
        return f"«{campo}» tiene que ser un número (vino {entrada!r})."
    if tipo in ("bool_parsing", "bool_type"):
        return f"«{campo}» tiene que ser true o false (vino {entrada!r})."
    if tipo in ("string_type",):
        return f"«{campo}» tiene que ser un texto (vino {type(entrada).__name__})."
    if tipo in ("list_type",):
        return f"«{campo}» tiene que ser una lista (- elemento por línea)."
    if tipo in ("dict_type", "model_type", "model_attributes_type"):
        return f"«{campo}» tiene que ser un mapa (clave: valor)."
    if tipo.startswith("greater_than") or tipo.startswith("less_than"):
        limite = ctx.get("gt", ctx.get("ge", ctx.get("lt", ctx.get("le"))))
        return f"«{campo}» = {entrada!r} está fuera de rango (límite {limite})."
    return f"«{campo}»: {error.get('msg', 'valor inválido')}."


def error_en_espanol(exc: ValidationError, archivo: Path) -> EjercicioInvalido:
    return EjercicioInvalido(archivo, [traducir(dict(e)) for e in exc.errors()])


def esquema_json() -> Dict[str, Any]:
    from deckard.core.models import Ejercicio

    esquema = Ejercicio.model_json_schema()
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": ID_ESQUEMA,
            "title": "ejercicio.yaml (deckard)", **{k: v for k, v in esquema.items() if k != "title"}}
