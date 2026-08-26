"""Pruebas de tp-multiplexer: combinatoria, asignación determinista y empaquetado."""

from pathlib import Path
import csv
import json
import pytest
import yaml
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.multiplex import (
    MatrizSpec,
    asignar_variante_determinista,
    cargar_alumnos_csv,
    generar_variantes,
    multiplexar_tp,
    render_template,
)

runner = CliRunner()


def test_render_template():
    plantilla = "Hola {{ nombre }}, tu tipo es {{ tipo }} y valor {% if tipo == 'int' %}10{% else %}20{% endif %}."
    ctx = {"nombre": "Martin", "tipo": "int"}
    assert render_template(plantilla, ctx) == "Hola Martin, tu tipo es int y valor 10."

    ctx2 = {"nombre": "Ana", "tipo": "float"}
    assert render_template(plantilla, ctx2) == "Hola Ana, tu tipo es float y valor 20."


def test_generar_variantes_combinatorias():
    spec = MatrizSpec(
        ejercicio="lista_enlazada",
        titulo="Lista Enlazada",
        enunciado_template="Lista para tipo `{{ tipo_dato }}` con op `{{ operacion }}`.",
        solucion_template="/* Solución {{ tipo_dato }} {{ operacion }} */\nint main(void){return 0;}\n",
        parametrizaciones={
            "tipo_dato": ["int", "float", "char*"],
            "operacion": ["insertar", "eliminar"],
            "tamano": [10, 50],
        },
        tests_template=[
            {"in": "{{ tamano }}\n", "out": "{{ operacion }}_ok\n"},
        ],
        pistas_template=["Pista para {{ tipo_dato }}"],
    )

    variantes = generar_variantes(spec)
    # 3 * 2 * 2 = 12 combinaciones
    assert len(variantes) == 12

    ids = [v.id for v in variantes]
    assert len(set(ids)) == 12
    assert "lista_enlazada_v0" in ids
    assert "lista_enlazada_v11" in ids

    v0 = variantes[0]
    assert "int" in v0.enunciado_md or "float" in v0.enunciado_md or "char*" in v0.enunciado_md
    assert len(v0.tests) == 1
    assert len(v0.pistas) == 1


def test_asignacion_determinista_reproducible():
    alumnos = ["mrtin", "juan_perez", "maria_gomez", "ana_lopez"]
    ejercicio = "tp_arboles"
    total_variantes = 8

    # 1. Asignaciones son deterministas en múltiples corridas
    asig_1 = [asignar_variante_determinista(a, ejercicio, total_variantes) for a in alumnos]
    asig_2 = [asignar_variante_determinista(a, ejercicio, total_variantes) for a in alumnos]
    assert asig_1 == asig_2

    # 2. Varían según el ejercicio
    asig_otro_ej = [asignar_variante_determinista(a, "tp_grafos", total_variantes) for a in alumnos]
    assert asig_1 != asig_otro_ej or len(set(asig_1)) > 1


def test_cargar_alumnos_csv(tmp_path):
    csv_file = tmp_path / "students.csv"
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["username", "nombre", "email"])
        writer.writerow(["mperez", "Martin Perez", "mperez@unrn.edu.ar"])
        writer.writerow(["agarcia", "Ana Garcia", "agarcia@unrn.edu.ar"])

    alumnos = cargar_alumnos_csv(csv_file)
    assert len(alumnos) == 2
    assert alumnos[0].id == "mperez"
    assert alumnos[0].nombre == "Martin Perez"
    assert alumnos[1].id == "agarcia"


def test_multiplexar_tp_end_to_end(tmp_path):
    matriz_file = tmp_path / "matriz.yaml"
    with open(matriz_file, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "ejercicio": "pila_dinamica",
            "titulo": "Pila Dinámica",
            "enunciado_template": "# Pila para {{ tipo }}\nImplementar una pila de {{ tipo }}.",
            "solucion_template": "/* Solución {{ tipo }} */\n#include <stdio.h>\nint main(void){return 0;}\n",
            "parametrizaciones": {
                "tipo": ["int", "double", "char"],
                "capacidad": [10, 100],
            },
            "tests_template": [
                {"in": "{{ capacidad }}\n", "out": "ok\n"},
            ],
            "pistas_template": ["Cuidado con realloc para {{ tipo }}."],
        }, f)

    students_file = tmp_path / "students.csv"
    with open(students_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "nombre", "email"])
        writer.writerow(["alumno1", "Estudiante Uno", "e1@unrn.edu.ar"])
        writer.writerow(["alumno2", "Estudiante Dos", "e2@unrn.edu.ar"])
        writer.writerow(["alumno3", "Estudiante Tres", "e3@unrn.edu.ar"])

    out_dir = tmp_path / "salida_multiplex"
    res = multiplexar_tp(
        matriz_path=matriz_file,
        students_path=students_file,
        output_dir=out_dir,
        pack_ripkg=True,
        generar_starters=True,
    )

    assert res.total_variantes == 6
    assert len(res.asignaciones) == 3

    # Verificar paquetes de variantes
    assert (out_dir / "paquetes" / "pila_dinamica_v0.ripkg").is_file()

    # Verificar asignaciones y starters de alumnos
    assert (out_dir / "asignaciones.csv").is_file()
    assert (out_dir / "asignaciones.json").is_file()

    assert (out_dir / "alumnos" / "alumno1" / "README.md").is_file()
    assert (out_dir / "alumnos" / "alumno1" / "main.c").is_file()
    assert (out_dir / "alumnos" / "alumno1" / "Makefile").is_file()
    assert (out_dir / "alumnos" / "alumno1" / "tests" / "caso_01.in").is_file()


def test_cli_multiplex(tmp_path):
    matriz_file = tmp_path / "matriz.yaml"
    with open(matriz_file, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "ejercicio": "cola_circular",
            "titulo": "Cola Circular",
            "enunciado_template": "Cola para {{ tipo }}.",
            "parametrizaciones": {"tipo": ["int", "float"]},
        }, f)

    students_file = tmp_path / "students.csv"
    with open(students_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "nombre"])
        writer.writerow(["al1", "Alumno 1"])

    out_dir = tmp_path / "dist_cli"
    res = runner.invoke(app, [
        "multiplex",
        "--spec", str(matriz_file),
        "--students", str(students_file),
        "-o", str(out_dir),
    ])

    assert res.exit_code == 0
    assert "✓ Multiplexación completada para 'cola_circular'" in res.stdout
    assert "Total de variantes combinatorias: 2" in res.stdout
    assert (out_dir / "asignaciones.csv").is_file()
