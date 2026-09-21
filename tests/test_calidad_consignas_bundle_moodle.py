"""Tests automatizados para las 8 mejoras QoL de Deckard:
1. check-terms (consistencia terminológica)
2. diagram-memory (diagramas Stack/Heap)
3. export-moodle (exportador Moodle XML)
4. find-duplicates (detección de ejercicios duplicados)
5. lint-consigna (linter de precondiciones y casos borde)
6. scaffold --steps (esqueletos con pasos TODO)
7. bundle-offline (paquete ZIP con visor web HTML/CSS)
8. check-tone (auditoría de tono y ambigüedades)
"""

from pathlib import Path
import pytest
from typer.testing import CliRunner
import xml.etree.ElementTree as ET
import zipfile

from deckard.cli import app
from deckard.core.bank import guardar_ejercicio
from deckard.core.bundle_offline import empaquetar_bundle_offline
from deckard.core.consigna_linter import lint_consigna_ejercicio, lint_consigna_banco
from deckard.core.duplicates import buscar_ejercicios_duplicados
from deckard.core.memory_diagram import inferir_diagrama_desde_ejercicio, MarcoPila, BloqueHeap, generar_diagrama_memoria_ascii, generar_diagrama_memoria_mermaid
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.moodle_export import generar_moodle_xml_cuestionario, exportar_moodle_archivo
from deckard.core.scaffold_steps import generar_esqueleto_con_pasos
from deckard.core.terminology import verificar_consistencia_terminologica, auditar_terminologia_ejercicios
from deckard.core.tone_checker import auditar_tono_consigna, auditar_tono_banco

runner = CliRunner()


def _crear_ejercicio_base(tmp_path: Path, ej_id: str = "test-ej", titulo: str = "Ejercicio de Prueba", enunciado: str = "Consigna clara.") -> Ejercicio:
    ej = Ejercicio(
        id=ej_id,
        titulo=titulo,
        enunciado_md=enunciado,
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=25,
        starter_code="int resolver(int* vec, int n) {\n    return 0;\n}\n",
        solucion_c="int resolver(int* vec, int n) {\n    return n * 2;\n}\n",
    )
    guardar_ejercicio(ej, tmp_path)
    return ej


def test_terminology_consistency(tmp_path: Path):
    texto_inadecuado = "Implementá el método sumar() que recibe un objeto vector y otro arreglo."
    findings = verificar_consistencia_terminologica(texto_inadecuado, preferencia_coleccion="vector")
    reglas = {f.regla for f in findings}

    assert "TERM_PARADIGMA_INVALIDO" in reglas  # por 'método'
    assert "TERM_MEZCLA_SINONIMOS" in reglas     # por 'vector' y 'arreglo'
    assert "TERM_VIOLACION_CONVENCION" in reglas # por violar preferencia 'vector' al usar 'arreglo'

    # Test CLI
    ej = _crear_ejercicio_base(tmp_path, "ej-terms", "Prueba Términos", texto_inadecuado)
    res = runner.invoke(app, ["check-terms", "ej-terms", "--banco", str(tmp_path)])
    assert res.exit_code == 0
    assert "Auditoría Terminológica" in res.stdout


def test_memory_diagram(tmp_path: Path):
    ej = _crear_ejercicio_base(
        tmp_path,
        "ej-mem",
        "Manejo Dinámico de Memoria",
        "Reservar memoria con malloc para un vector de punteros en el Heap."
    )
    # ASCII
    diag_ascii = inferir_diagrama_desde_ejercicio(ej, formato="ascii")
    assert "STACK (Memoria Automática)" in diag_ascii
    assert "HEAP (Memoria Dinámica)" in diag_ascii
    assert "0x55a1b0" in diag_ascii

    # Mermaid
    diag_mermaid = inferir_diagrama_desde_ejercicio(ej, formato="mermaid")
    assert "graph LR" in diag_mermaid
    assert 'subgraph STACK["Stack (Memoria Automática)"]' in diag_mermaid
    assert 'subgraph HEAP["Heap (Memoria Dinámica)"]' in diag_mermaid

    # Test CLI
    salida_txt = tmp_path / "diagrama.txt"
    res = runner.invoke(app, ["diagram-memory", "ej-mem", "--banco", str(tmp_path), "-o", str(salida_txt)])
    assert res.exit_code == 0
    assert salida_txt.is_file()
    assert "STACK" in salida_txt.read_text(encoding="utf-8")


def test_export_moodle(tmp_path: Path):
    ej = _crear_ejercicio_base(tmp_path, "ej-moodle", "Multiplicar Vector", "Dado un vector de enteros, duplicar sus valores.")
    xml_str = generar_moodle_xml_cuestionario([ej], categoria="Programacion1/Vectores", tipo_pregunta="multichoice")
    
    # Validar XML sintáctico
    root = ET.fromstring(xml_str)
    assert root.tag == "quiz"
    preguntas = root.findall("question")
    assert len(preguntas) >= 2  # categoría + pregunta

    # Test CLI
    out_xml = tmp_path / "banco_moodle.xml"
    res = runner.invoke(app, ["export-moodle", "ej-moodle", "-o", str(out_xml), "--banco", str(tmp_path)])
    assert res.exit_code == 0
    assert out_xml.is_file()
    assert "<quiz>" in out_xml.read_text(encoding="utf-8")


def test_find_duplicates(tmp_path: Path):
    ej1 = _crear_ejercicio_base(tmp_path, "ej1", "Invertir Cadena", "Dada una cadena de texto, invertir sus caracteres.")
    ej2 = _crear_ejercicio_base(tmp_path, "ej2", "Invertir Cadena de Texto", "Dada una cadena de texto, invertir todos sus caracteres in-place.")
    ej3 = _crear_ejercicio_base(tmp_path, "ej3", "Calcular Factorial", "Calcular el factorial recursivo de un entero no negativo N.")

    dups = buscar_ejercicios_duplicados([ej1, ej2, ej3], umbral=0.60)
    assert len(dups) >= 1
    par = dups[0]
    assert {par.ejercicio_a_id, par.ejercicio_b_id} == {"ej1", "ej2"}

    # Test CLI
    res = runner.invoke(app, ["find-duplicates", "--banco", str(tmp_path), "--umbral", "0.50"])
    assert res.exit_code == 0
    assert "ej1" in res.stdout
    assert "ej2" in res.stdout


def test_consigna_linter(tmp_path: Path):
    # Consigna con omisión de puntero NULL y sin definir comportamiento de vector vacío
    ej = _crear_ejercicio_base(
        tmp_path,
        "ej-lint",
        "Procesar Arreglo",
        "Función que recibe un vector de enteros y calcula el promedio sin aclarar nada más."
    )
    obs = lint_consigna_ejercicio(ej)
    reglas = {o.regla for o in obs}
    assert "LINT_NULL_PTR" in reglas
    assert "LINT_EMPTY_ARRAY" in reglas

    # Test CLI
    res = runner.invoke(app, ["lint-consigna", "ej-lint", "--banco", str(tmp_path)])
    assert res.exit_code == 0
    assert "LINT_NULL_PTR" in res.stdout


def test_scaffold_steps(tmp_path: Path):
    ej = _crear_ejercicio_base(tmp_path, "ej-scaffold", "Contar Pares", "Contar cantidad de elementos pares en un arreglo.")
    out_c = tmp_path / "esqueleto_pasos.c"
    codigo = generar_esqueleto_con_pasos(ej, ruta_salida=out_c)

    assert "PASO 1 [Precondiciones y Validación de Entrada]" in codigo
    assert "PASO 2 [Casos Base y Casos Borde]" in codigo
    assert "PASO 3 [Lógica Algorítmica Principal]" in codigo
    assert "PASO 4 [Limpieza de Recursos y Retorno]" in codigo
    assert out_c.is_file()

    # Test CLI
    res = runner.invoke(app, ["scaffold", "ej-scaffold", "--steps", "--banco", str(tmp_path)])
    assert res.exit_code == 0
    assert "PASO 1" in res.stdout


def test_bundle_offline(tmp_path: Path):
    ej = _crear_ejercicio_base(tmp_path, "ej-bundle", "Guía Completa", "Consigna para visor offline.")
    zip_path = tmp_path / "bundle.zip"
    empaquetar_bundle_offline([ej], zip_path, titulo="Prueba Offline", incluir_soluciones=True)

    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path, "r") as zf:
        nombres = zf.namelist()
        assert "index.html" in nombres
        assert "estilos.css" in nombres
        assert "ejercicios/ej-bundle/consigna.md" in nombres
        assert "ejercicios/ej-bundle/main.c" in nombres
        assert "ejercicios/ej-bundle/solucion.c" in nombres

        index_html = zf.read("index.html").decode("utf-8")
        assert "Prueba Offline" in index_html
        assert "Visor offline interactivo" in index_html

    # Test CLI
    out_cli_zip = tmp_path / "bundle_cli.zip"
    res = runner.invoke(app, ["bundle-offline", str(tmp_path), "--banco", str(tmp_path), "-o", str(out_cli_zip)])
    assert res.exit_code == 0
    assert out_cli_zip.is_file()


def test_tone_checker(tmp_path: Path):
    texto_tono = "Podrías hacer algo si te parece. No dejes de no validar el coso. Hacé tu parte y luego haz el test."
    ej = _crear_ejercicio_base(tmp_path, "ej-tono", "Consigna Dubitativa", texto_tono)
    findings = auditar_tono_consigna(ej)
    reglas = {f.regla for f in findings}

    assert "TONE_MODAL_UNCERTAINTY" in reglas
    assert "TONE_DOUBLE_NEGATIVE" in reglas
    assert "TONE_COLLOQUIALISM" in reglas
    assert "TONE_PRONOUN_MIX" in reglas  # mezcla hacé (voseo) con haz (tuteo)

    # Test CLI
    res = runner.invoke(app, ["check-tone", "ej-tono", "--banco", str(tmp_path)])
    assert res.exit_code == 0
    assert "Auditoría de Tono" in res.stdout
