"""Módulo de exportación de asignaciones para GitHub Classroom en Deckard."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Optional

from deckard.core.models import Ejercicio


def exportar_github_classroom(
    ejercicio: Ejercicio,
    dir_ejercicio: Path,
    directorio_salida: Path,
    nombre_repo: Optional[str] = None,
) -> Path:
    """Genera la estructura de un repositorio listo para GitHub Classroom.
    
    Incluye:
    - README.md con el enunciado del ejercicio
    - src/ con starter_code o archivos base
    - Makefile pedagógico
    - .github/workflows/classroom.yml con workflow de GitHub Actions
    """
    repo_name = nombre_repo or f"assignment-{ejercicio.id}"
    target_dir = directorio_salida / repo_name
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. README.md
    readme_content = f"""# {ejercicio.titulo}

**ID:** `{ejercicio.id}`  
**Nivel:** `{ejercicio.nivel.value}`  
**Tiempo estimado:** {ejercicio.tiempo_estimado} minutos  
**Temas:** {", ".join(ejercicio.tags)}

---

## Enunciado

{ejercicio.enunciado}

---

## Instrucciones de compilación y ejecución

Para compilar y ejecutar las pruebas localmente:
```bash
make test
```
"""
    (target_dir / "README.md").write_text(readme_content, encoding="utf-8")
    
    # 2. Archivos de código (src/)
    src_dir = target_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    
    if ejercicio.starter_code:
        (src_dir / "solution.c").write_text(ejercicio.starter_code, encoding="utf-8")
    elif (dir_ejercicio / "starter_code.c").exists():
        shutil.copy2(dir_ejercicio / "starter_code.c", src_dir / "solution.c")
    elif (dir_ejercicio / "solution.c").exists():
        shutil.copy2(dir_ejercicio / "solution.c", src_dir / "solution.c")
    else:
        (src_dir / "solution.c").write_text("/* Implementá tu solución aquí */\n#include <stdio.h>\n", encoding="utf-8")
        
    for h in dir_ejercicio.glob("*.h"):
        shutil.copy2(h, src_dir / h.name)
        
    # 3. Makefile
    makefile_content = """CC ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Wpedantic -Werror -g
TARGET = app

all: $(TARGET)

$(TARGET): src/solution.c
\t$(CC) $(CFLAGS) $< -o $@

test: $(TARGET)
\t@echo "Ejecutando pruebas..."
\t@./$(TARGET) || echo "Ejecución finalizada."

clean:
\trm -f $(TARGET) *.o

.PHONY: all test clean
"""
    (target_dir / "Makefile").write_text(makefile_content, encoding="utf-8")
    
    # 4. GitHub Actions Workflow
    workflow_dir = target_dir / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    
    workflow_content = f"""name: GitHub Classroom Autograding

on:
  push:
    branches: [ "main", "master" ]
  pull_request:
    branches: [ "main", "master" ]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout del repositorio
        uses: actions/checkout@v4

      - name: Instalar dependencias de compilación
        run: sudo apt-get update && sudo apt-get install -y gcc make

      - name: Compilar solución del estudiante
        run: make all

      - name: Ejecutar verificación
        run: make test
"""
    (workflow_dir / "classroom.yml").write_text(workflow_content, encoding="utf-8")
    
    return target_dir
