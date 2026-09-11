"""Gestor de licencias, autoría y créditos pedagógicos por ejercicio (QoL 30)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from deckard.core.models import Ejercicio

LICENCIAS_VALIDAS = {
    "CC-BY-4.0": "Creative Commons Attribution 4.0 International",
    "CC-BY-SA-4.0": "Creative Commons Attribution-ShareAlike 4.0 International",
    "MIT": "MIT License",
    "GPL-3.0": "GNU General Public License v3.0",
    "Catedra-P1": "Licencia Educativa de Uso Interno - Cátedra Programación 1",
}


@dataclass
class MetadatosLicencia:
    ejercicio_id: str
    autor: str
    licencia: str
    anio: int
    institucion: str = "Facultad de Ingeniería - Universidad de Buenos Aires"

    def generar_header_c(self) -> str:
        return (
            "/*\n"
            f" * Ejercicio: {self.ejercicio_id}\n"
            f" * Autoría: {self.autor} ({self.anio})\n"
            f" * Institución: {self.institucion}\n"
            f" * Licencia: {self.licencia} ({LICENCIAS_VALIDAS.get(self.licencia, '')})\n"
            " */\n"
        )


def obtener_creditos_ejercicio(
    ejercicio: Ejercicio,
    dir_ejercicio: Optional[Path] = None,
    autor_defecto: str = "Cátedra Programación 1",
) -> MetadatosLicencia:
    """Extrae o deduce los metadatos de autoría y licencia de un ejercicio."""
    meta_str = ejercicio.archivos.get("creditos.yaml")
    if not meta_str and dir_ejercicio and (dir_ejercicio / "creditos.yaml").is_file():
        meta_str = (dir_ejercicio / "creditos.yaml").read_text(encoding="utf-8")

    if meta_str:
        try:
            data = yaml.safe_load(meta_str) or {}
            return MetadatosLicencia(
                ejercicio_id=ejercicio.id,
                autor=data.get("autor", autor_defecto),
                licencia=data.get("licencia", "CC-BY-SA-4.0"),
                anio=int(data.get("anio", 2026)),
                institucion=data.get("institucion", "Facultad de Ingeniería"),
            )
        except Exception:
            pass

    return MetadatosLicencia(
        ejercicio_id=ejercicio.id,
        autor=autor_defecto,
        licencia="CC-BY-SA-4.0",
        anio=2026,
    )


def inyectar_creditos_ejercicio(
    ejercicio: Ejercicio,
    dir_ejercicio: Path,
    autor: str,
    licencia: str = "CC-BY-SA-4.0",
    anio: int = 2026,
) -> MetadatosLicencia:
    """Aplica y persiste la información de licencia en el directorio del ejercicio."""
    meta = MetadatosLicencia(
        ejercicio_id=ejercicio.id,
        autor=autor,
        licencia=licencia,
        anio=anio,
    )
    datos_yaml = {
        "ejercicio_id": meta.ejercicio_id,
        "autor": meta.autor,
        "licencia": meta.licencia,
        "anio": meta.anio,
        "institucion": meta.institucion,
    }
    ruta_creditos = dir_ejercicio / "creditos.yaml"
    ruta_creditos.write_text(yaml.dump(datos_yaml, sort_keys=False), encoding="utf-8")

    # Inyectar header en main.c o solucion.c si existen
    for nom_f in ("main.c", "solucion.c"):
        p_c = dir_ejercicio / nom_f
        if p_c.is_file():
            contenido = p_c.read_text(encoding="utf-8")
            if not contenido.startswith("/*"):
                p_c.write_text(meta.generar_header_c() + "\n" + contenido, encoding="utf-8")

    return meta
