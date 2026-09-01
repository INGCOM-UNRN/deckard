"""Tests unitarios e integrales para el comando deckard improve (OpenCode)."""

from pathlib import Path
import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import cargar_ejercicio, guardar_ejercicio
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.improve import (
    AspectoMejora,
    construir_prompt_ejercicio,
    construir_prompt_gift,
    procesar_respuesta_ia,
    mejorar_ejercicio,
    mejorar_archivo_gift,
)
from deckard.core.opencode import (
    buscar_ejecutable_opencode,
    extraer_bloque_codigo,
)

runner = CliRunner()


@pytest.fixture
def ejercicio_muestra(tmp_path: Path):
    banco = tmp_path / "banco"
    banco.mkdir()
    ej = Ejercicio(
        id="invertir-vector",
        titulo="Invertir Vector en Memoria",
        tema="punteros",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=30,
        enunciado_md="Hacer una funcion rapida que invierta un vector.",
        solucion_c="void invertir(int *v, size_t n) { ... }",
        pistas=["Pensar en dos punteros"],
        tags=["punteros", "arreglos"],
    )
    dir_ej = guardar_ejercicio(ej, banco)
    return dir_ej, ej


def test_extraer_bloque_codigo():
    raw_md = "Texto antes\n```markdown\n# Enunciado Mejorado\nContenido claro.\n```\nTexto despues"
    assert extraer_bloque_codigo(raw_md, "markdown") == "# Enunciado Mejorado\nContenido claro."

    raw_c = "```c\nvoid foo(void);\n```"
    assert extraer_bloque_codigo(raw_c, "c") == "void foo(void);"

    plano = "Sin bloques de codigo"
    assert extraer_bloque_codigo(plano) == "Sin bloques de codigo"


def test_construir_prompt_con_ajuste_personalizado(ejercicio_muestra):
    dir_ej, ej = ejercicio_muestra
    prompt = construir_prompt_ejercicio(
        ejercicio=ej,
        aspecto=AspectoMejora.CLARITY,
        custom_prompt="Prohibir expresamente variables de una letra salvo indices canonicos.",
    )
    assert "invertir-vector" in prompt
    assert "Invertir Vector en Memoria" in prompt
    assert "3. Aplicar" in prompt
    assert "CLARITY" in prompt
    assert "Prohibir expresamente variables de una letra" in prompt


def test_construir_prompt_con_archivo_de_prompt(ejercicio_muestra, tmp_path):
    dir_ej, ej = ejercicio_muestra
    archivo_prompt = tmp_path / "custom_prompt.txt"
    archivo_prompt.write_text("Exigir manejo estricto de punteros nulos.", encoding="utf-8")

    prompt = construir_prompt_ejercicio(
        ejercicio=ej,
        aspecto=AspectoMejora.EDGE_CASES,
        prompt_file=archivo_prompt,
    )
    assert "EDGE-CASES" in prompt
    assert "Exigir manejo estricto de punteros nulos." in prompt


def test_construir_prompt_gift():
    gift_texto = "::P1:: ¿Cuál es la complejidad? {=O(1) ~O(n) ~O(n^2)}"
    prompt = construir_prompt_gift(
        texto_gift=gift_texto,
        aspecto=AspectoMejora.CLARITY,
        custom_prompt="Agregar feedback explicativo a cada opcion.",
    )
    assert "BANCO DE PREGUNTAS GIFT" in prompt
    assert "GIFT de Moodle" in prompt
    assert "Agregar feedback explicativo" in prompt


def test_procesar_respuesta_ia_hints(ejercicio_muestra):
    dir_ej, ej = ejercicio_muestra
    respuesta_yaml = """```yaml
pistas:
  - "Pista 1: Pensar en indices opuestos (inicio y fin)."
  - "Pista 2: Avanzar el puntero izquierdo y retroceder el derecho."
  - "Pista 3: Usar una variable auxiliar de tipo entero para el swap."
```"""
    ej_mod, anterior, nuevo, pistas_nuevas = procesar_respuesta_ia(
        ej, AspectoMejora.HINTS, respuesta_yaml
    )
    assert len(pistas_nuevas) == 3
    assert "Pista 1" in pistas_nuevas[0]
    assert ej_mod.pistas == pistas_nuevas


def test_mejorar_ejercicio_dry_run_y_apply(ejercicio_muestra):
    dir_ej, ej = ejercicio_muestra
    mock_respuesta = """```markdown
## Invertir Vector en Memoria

Implementá la función `invertir_vector` que invierta los elementos de un arreglo de enteros `v` de longitud `n` modificándolo *in-place*.

### Casos Límite y Validaciones
- Si `v == NULL` o `n <= 1`, la función no debe realizar operaciones.
```"""

    # 1. Simulación (dry-run): no debe modificar archivos en disco
    res_dry = mejorar_ejercicio(
        dir_ejercicio=dir_ej,
        aspecto=AspectoMejora.CLARITY,
        aplicar=False,
        mock_respuesta=mock_respuesta,
    )
    assert res_dry.cambio_realizado is True
    assert "Casos Límite" in res_dry.contenido_nuevo
    assert len(res_dry.diff) > 0
    # En disco el archivo original no cambió
    ej_sin_cambio = cargar_ejercicio(dir_ej)
    assert "Hacer una funcion rapida" in ej_sin_cambio.enunciado_md

    # 2. Aplicar (apply=True): debe persistir en disco
    res_apply = mejorar_ejercicio(
        dir_ejercicio=dir_ej,
        aspecto=AspectoMejora.CLARITY,
        aplicar=True,
        mock_respuesta=mock_respuesta,
    )
    assert res_apply.cambio_realizado is True
    ej_actualizado = cargar_ejercicio(dir_ej)
    assert "Casos Límite y Validaciones" in ej_actualizado.enunciado_md


def test_mejorar_archivo_gift(tmp_path):
    gift_file = tmp_path / "preguntas.gift"
    gift_file.write_text("::P1:: Punteros en C {=Correcto ~Falso}\n", encoding="utf-8")

    mock_resp = """::P1:: [html]¿Cuál es el valor inicial de un puntero local no inicializado? {
    =Indeterminado (basura en el stack) #¡Correcto! Las variables automáticas no se limpian automáticamente.
    ~NULL #Incorrecto, no se inicializa en NULL por defecto.
}"""
    cambio, diff, nuevo = mejorar_archivo_gift(
        ruta_gift=gift_file,
        aspecto=AspectoMejora.CLARITY,
        aplicar=True,
        mock_respuesta=mock_resp,
    )
    assert cambio is True
    assert "Indeterminado" in nuevo
    assert "Indeterminado" in gift_file.read_text(encoding="utf-8")


def test_cli_improve_show_prompt(ejercicio_muestra):
    dir_ej, ej = ejercicio_muestra
    # Test subcomando clarity con --show-prompt y ajuste personalizado
    res = runner.invoke(app, [
        "improve", "clarity", str(dir_ej),
        "--show-prompt",
        "-p", "Hacer hincapie en uso de const en argumentos de solo lectura.",
    ])
    assert res.exit_code == 0
    assert "invertir-vector" in res.stdout
    assert "Hacer hincapie en uso de const" in res.stdout


def test_cli_improve_subcomandos_show_prompt(ejercicio_muestra):
    dir_ej, _ = ejercicio_muestra
    subcomandos = [
        "edge-cases",
        "examples",
        "hints",
        "bloom",
        "testcases",
        "starter",
        "all",
    ]
    for sc in subcomandos:
        res = runner.invoke(app, ["improve", sc, str(dir_ej), "--show-prompt"])
        assert res.exit_code == 0, f"Fallo en subcomando {sc}: {res.stdout}"
        assert "invertir-vector" in res.stdout


def test_cli_improve_gift_show_prompt(tmp_path):
    gift_file = tmp_path / "banco_tracing.gift"
    gift_file.write_text("::P1:: Tracing C {=A ~B}", encoding="utf-8")

    res = runner.invoke(app, [
        "improve", "clarity", str(gift_file),
        "--show-prompt",
        "-p", "Reforzar feedback explicativo.",
    ])
    assert res.exit_code == 0
    assert "banco_tracing.gift" in res.stdout
    assert "Reforzar feedback explicativo" in res.stdout


def test_cli_improve_banco_show_prompt(tmp_path, ejercicio_muestra):
    dir_ej, ej = ejercicio_muestra
    banco_dir = dir_ej.parent
    res = runner.invoke(app, [
        "improve", "all",
        "--banco", str(banco_dir),
        "--all",
        "--show-prompt",
    ])
    assert res.exit_code == 0
    assert "Prompt de muestra" in res.stdout
    assert "invertir-vector" in res.stdout


def test_cli_improve_mock_execution(monkeypatch, ejercicio_muestra):
    dir_ej, ej = ejercicio_muestra

    def mock_ejecutar(prompt, **kwargs):
        return """```markdown
# Enunciado Mejorado por OpenCode Mock

Implementá la función solicitada de manera segura.
```"""

    monkeypatch.setattr("deckard.core.improve.ejecutar_opencode", mock_ejecutar)

    # Invocar CLI con --apply
    res = runner.invoke(app, [
        "improve", "clarity", str(dir_ej),
        "--apply",
    ])
    assert res.exit_code == 0
    assert "Mejora de 'clarity' completada" in res.stdout

    ej_actualizado = cargar_ejercicio(dir_ej)
    assert "Enunciado Mejorado por OpenCode Mock" in ej_actualizado.enunciado_md


def test_cli_alias_ai_y_opencode(ejercicio_muestra):
    dir_ej, _ = ejercicio_muestra
    res_ai = runner.invoke(app, ["ai", "hints", str(dir_ej), "--show-prompt"])
    assert res_ai.exit_code == 0
    assert "Pista 1" in res_ai.stdout or "HINTS" in res_ai.stdout

    res_opencode = runner.invoke(app, ["opencode", "examples", str(dir_ej), "--show-prompt"])
    assert res_opencode.exit_code == 0
    assert "EXAMPLES" in res_opencode.stdout
