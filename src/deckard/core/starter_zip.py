"""Módulo de empaquetado de starter kits en archivos ZIP con clave de entrega y verificación de integridad (QoL 11)."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import zipfile

from deckard.core.bank import cargar_ejercicio, listar_ejercicios
from deckard.core.guides import cargar_guia_con_ejercicios
from deckard.core.models import Ejercicio


def _calcular_hash(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def generar_clave_entrega(ejercicio_id: str, timestamp_iso: str, salt: str = "deckard_catedra_c") -> str:
    """Genera una clave de entrega alfanumérica determinista para validación docente."""
    raw = f"{ejercicio_id}:{timestamp_iso}:{salt}".encode("utf-8")
    h = hashlib.sha256(raw).hexdigest().upper()
    return f"DKD-{h[:4]}-{h[4:8]}-{h[8:12]}"


def generar_makefile_starter(ejercicio: Ejercicio) -> str:
    """Genera un Makefile canónico de cátedra para el starter kit."""
    return f"""# Makefile generado automáticamente por Deckard para el ejercicio '{ejercicio.id}'
CC ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror -pedantic -g

SRC = {ejercicio.id}.c
TARGET = test_{ejercicio.id}

all: build test

build:
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)

test: build
	./$(TARGET)

clean:
	rm -f $(TARGET) *.o

.PHONY: all build test clean
"""


def empaquetar_starter_zip(
    ejercicio: Ejercicio,
    out_zip: Optional[Path] = None,
    incluir_tests: bool = True,
    incluir_pistas: bool = True,
) -> Tuple[Path, str, str]:
    """
    Empaqueta el starter kit de un ejercicio en un archivo ZIP con clave de entrega.
    Retorna (ruta_zip, clave_entrega, sha256_zip).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    clave_entrega = generar_clave_entrega(ejercicio.id, now_iso)

    if out_zip:
        dest_zip = Path(out_zip).resolve()
    else:
        dest_zip = Path(f"starter_{ejercicio.id}.zip").resolve()

    dest_zip.parent.mkdir(parents=True, exist_ok=True)

    metadata = {
        "ejercicio_id": ejercicio.id,
        "titulo": ejercicio.titulo,
        "tema": ejercicio.tema,
        "bloom": ejercicio.bloom.name,
        "minutos_estimados": ejercicio.minutos_estimados,
        "fecha_empaquetado": now_iso,
        "clave_entrega": clave_entrega,
        "generator": "Deckard Cátedra Toolchain",
    }

    # Starter code o esqueleto
    starter_code = ejercicio.archivos.get("starter.c") or ejercicio.archivos.get(f"{ejercicio.id}.c")
    if not starter_code:
        starter_code = (
            f"/*\n * Starter kit: {ejercicio.titulo}\n * Tema: {ejercicio.tema} (Nivel Bloom: {ejercicio.bloom.name})\n */\n\n"
            f"#include <stdio.h>\n#include <stdlib.h>\n#include <assert.h>\n\n"
            f"// TODO: Implementar la solución solicitada en el enunciado.\n\n"
            f"int main(void) {{\n    printf(\"Ejecutando pruebas para '{ejercicio.id}'...\\n\");\n    // assert(1 == 1);\n    printf(\"Completado.\\n\");\n    return 0;\n}}\n"
        )

    # README del ejercicio
    readme_content = [
        f"# {ejercicio.titulo}",
        f"",
        f"- **ID de Ejercicio:** `{ejercicio.id}`",
        f"- **Tema:** `{ejercicio.tema}`",
        f"- **Nivel Bloom:** `{ejercicio.bloom.name}`",
        f"- **Tiempo Estimado:** {ejercicio.minutos_estimados} minutos",
        f"- **Clave de Entrega:** `{clave_entrega}`",
        f"",
        f"## Enunciado",
        f"",
        ejercicio.enunciado_md,
        f"",
    ]

    if incluir_pistas and ejercicio.pistas:
        readme_content.append("## Pistas de Resolución")
        readme_content.append("")
        for idx, pista in enumerate(ejercicio.pistas, 1):
            readme_content.append(f"<details><summary>Pista {idx}</summary>")
            readme_content.append(f"")
            readme_content.append(pista)
            readme_content.append(f"</details>")
        readme_content.append("")

    readme_content.append("## Instrucciones de Compilación y Entrega")
    readme_content.append("")
    readme_content.append("```bash")
    readme_content.append("make build   # Compila con flags estrictos de cátedra")
    readme_content.append("make test    # Ejecuta la suite de pruebas")
    readme_content.append("```")
    readme_content.append("")

    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. README.md
        zf.writestr(f"{ejercicio.id}/README.md", "\n".join(readme_content))

        # 2. Starter code
        zf.writestr(f"{ejercicio.id}/{ejercicio.id}.c", starter_code)

        # 3. Makefile
        zf.writestr(f"{ejercicio.id}/Makefile", generar_makefile_starter(ejercicio))

        # 4. Clave y metadatos de entrega
        zf.writestr(f"{ejercicio.id}/ENTREGA_KEY.txt", f"{clave_entrega}\n")
        zf.writestr(f"{ejercicio.id}/metadata.json", json.dumps(metadata, indent=2, ensure_ascii=False))

        # 5. Archivos auxiliares del ejercicio (tests, headers, testcases)
        for nombre, contenido in ejercicio.archivos.items():
            if nombre not in ("starter.c", f"{ejercicio.id}.c"):
                if not incluir_tests and ("test" in nombre.lower() or nombre.endswith(".in") or nombre.endswith(".out")):
                    continue
                zf.writestr(f"{ejercicio.id}/{nombre}", contenido)

    zip_bytes = dest_zip.read_bytes()
    sha256_zip = _calcular_hash(zip_bytes)

    return dest_zip, clave_entrega, sha256_zip


def empaquetar_guia_zip(
    guia_path: Path,
    banco_dir: Path,
    out_zip: Optional[Path] = None,
) -> Tuple[Path, str, int]:
    """Empaqueta todos los ejercicios de una guía en un bundle ZIP multi-ejercicio."""
    datos, items = cargar_guia_con_ejercicios(guia_path, banco_dir)
    ejercicios = [ej for _, ej in items if ej is not None]

    if not ejercicios:
        raise ValueError("La guía no contiene ejercicios válidos para empaquetar.")

    guia_id = datos.get("id", guia_path.stem)
    dest_zip = out_zip or (guia_path.parent / f"bundle_{guia_id}.zip")
    dest_zip.parent.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    clave_maestra = generar_clave_entrega(guia_id, now_iso)

    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest_guia = {
            "guia_id": guia_id,
            "nombre": datos.get("nombre", "Guía de Ejercicios"),
            "materia": datos.get("materia", "Programación 1"),
            "clave_maestra": clave_maestra,
            "fecha": now_iso,
            "total_ejercicios": len(ejercicios),
            "ejercicios": [ej.id for ej in ejercicios],
        }
        zf.writestr("GUIA_METADATA.json", json.dumps(manifest_guia, indent=2, ensure_ascii=False))
        zf.writestr("CLAVE_ENTREGA.txt", f"{clave_maestra}\n")

        for ej in ejercicios:
            # Empaquetar cada ejercicio en su subcarpeta
            _, clave_ej, _ = empaquetar_starter_zip(ej)
            # Leer starter code
            starter_code = ej.archivos.get("starter.c") or ej.archivos.get(f"{ej.id}.c") or f"// Starter {ej.id}\n"
            zf.writestr(f"{ej.id}/{ej.id}.c", starter_code)
            zf.writestr(f"{ej.id}/Makefile", generar_makefile_starter(ej))
            zf.writestr(f"{ej.id}/README.md", f"# {ej.titulo}\n\n{ej.enunciado_md}\n")
            zf.writestr(f"{ej.id}/ENTREGA_KEY.txt", f"{clave_ej}\n")

    return dest_zip, clave_maestra, len(ejercicios)
