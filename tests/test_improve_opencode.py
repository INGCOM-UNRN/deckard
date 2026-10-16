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
from deckard.core.ia import extraer_bloque_codigo

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
    assert "invertir-vector" not in prompt  # el ID no lo usa ningún aspecto: no viaja
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
    assert "--- PREGUNTA 1 ---" in prompt
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

    monkeypatch.setattr("deckard.core.improve.consultar_ia", mock_ejecutar)

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


def test_cli_improve_models(monkeypatch):
    def mock_listar(proveedor=None, filtro=None):
        return [
            "opencode-go/qwen3.8-max",
            "opencode-go/deepseek-v4-pro",
            "opencode-go/kimi-k3",
        ]

    monkeypatch.setattr("deckard.core.ia.listar_modelos", mock_listar)

    res = runner.invoke(app, ["improve", "models"])
    assert res.exit_code == 0
    assert "opencode-go/qwen3.8-max" in res.stdout
    assert "deepseek-v4-pro" in res.stdout
    assert "kimi-k3" in res.stdout

    res_raw = runner.invoke(app, ["improve", "models", "--raw"])
    assert res_raw.exit_code == 0
    lineas = [line.strip() for line in res_raw.stdout.splitlines() if line.strip()]
    assert lineas == ["opencode-go/qwen3.8-max", "opencode-go/deepseek-v4-pro", "opencode-go/kimi-k3"]


def test_cli_improve_custom_model_flag(monkeypatch, ejercicio_muestra):
    dir_ej, _ = ejercicio_muestra
    capturado = {}

    def mock_ejecutar(prompt, modelo=None, **kwargs):
        capturado["modelo"] = modelo
        return """```markdown
# Enunciado con Modelo Custom
```"""

    monkeypatch.setattr("deckard.core.improve.consultar_ia", mock_ejecutar)

    res = runner.invoke(app, [
        "improve", "clarity", str(dir_ej),
        "-m", "opencode-go/deepseek-v4-pro",
        "--apply",
    ])
    assert res.exit_code == 0
    assert capturado.get("modelo") == "opencode-go/deepseek-v4-pro"



@pytest.fixture
def sin_config_ia(monkeypatch, tmp_path):
    for var in ("P1_IA_PROVEEDOR", "P1_IA_MODELO", "P1_IA_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("P1_IA_CONFIG", str(tmp_path / "ia.toml"))


def test_cli_improve_proveedor_y_modelo_llegan_a_yutani(monkeypatch, ejercicio_muestra, sin_config_ia):
    """--proveedor elige el proveedor de yutani.ia (N-ECO-26); sin nada, deckard sigue con OpenCode."""
    import types

    from yutani import ia

    pedidos = []

    def cliente(config, directorio=None):
        pedidos.append((config, directorio))
        return types.SimpleNamespace(generar=lambda prompt, sistema=None: "```markdown\n# Nuevo enunciado\n```")

    monkeypatch.setattr(ia, "cliente", cliente)
    dir_ej, _ = ejercicio_muestra
    res = runner.invoke(app, ["improve", "clarity", str(dir_ej), "--proveedor", "ollama", "-m", "qwen2.5-coder:7b"])
    assert res.exit_code == 0, res.stdout
    config, directorio = pedidos[-1]
    assert (config.proveedor, config.modelo, directorio) == ("local", "qwen2.5-coder:7b", dir_ej)
    runner.invoke(app, ["improve", "clarity", str(dir_ej)])
    assert (pedidos[-1][0].proveedor, pedidos[-1][0].modelo) == ("opencode", "opencode-go/qwen3.8-max")


def test_cli_improve_proveedor_desconocido(ejercicio_muestra, sin_config_ia):
    dir_ej, _ = ejercicio_muestra
    res = runner.invoke(app, ["improve", "clarity", str(dir_ej), "--proveedor", "watson"])
    assert res.exit_code == 1 and "desconocido" in res.stdout


def test_doctor_incluye_el_proveedor_de_ia(sin_config_ia):
    from deckard.core.doctor import diagnosticar

    nombres = {c["nombre"]: c for c in diagnosticar()}
    assert "opencode" in nombres["ia: proveedor"]["detalle"] and not nombres["ia: proveedor"]["requerido"]


# ── Sólo lo que cada aspecto necesita (menos tokens) ──────────────────────────

def _ejercicio_completo():
    from deckard.core.models import FuncionSpec

    return Ejercicio(
        id="suma", titulo="Sumar", tema="arreglos", bloom=NivelBloom.APLICAR, minutos_estimados=15,
        enunciado_md="Sumá los elementos.",
        solucion_c='/* solución */\nint suma(const int *v, size_t n)\n{\n    // acumulador\n    int s = 0;   \n\n'
                   '    for (size_t i = 0; i < n; i++) s += v[i];\n    puts("// no es comentario");\n    return s;\n}\n',
        starter_code="int suma(const int *v, size_t n);",
        pistas=["PISTA VIEJA"],
        funciones=[FuncionSpec(nombre="suma", retorno="int", parametros="const int *v, size_t n")],
    )


@pytest.mark.parametrize("aspecto, esta, no_esta", [
    (AspectoMejora.CLARITY, ["Sumá los elementos.", "Sumar"], ["int s = 0", "PISTA VIEJA", "Funciones C", "15 minutos"]),
    (AspectoMejora.BLOOM, ["Sumá los elementos.", "3. Aplicar"], ["int s = 0", "PISTA VIEJA", "Título"]),
    (AspectoMejora.HINTS, ["int s = 0;", "suma(const int *v"], ["PISTA VIEJA", "acumulador", "/* solución */"]),
    (AspectoMejora.STARTER, ["CÓDIGO INICIAL ACTUAL", "suma(const int *v"], ["int s = 0", "PISTA VIEJA"]),
    (AspectoMejora.TESTCASES, ["int s = 0;", "Tema: arreglos"], ["PISTA VIEJA"]),
])
def test_cada_aspecto_envia_solo_lo_que_usa(aspecto, esta, no_esta):
    prompt = construir_prompt_ejercicio(_ejercicio_completo(), aspecto)
    for texto in esta:
        assert texto in prompt, texto
    for texto in no_esta:
        assert texto not in prompt, texto


def test_compactar_c_saca_comentarios_y_blancos_pero_no_las_cadenas():
    from deckard.core.contexto_ia import compactar_c

    c = compactar_c(_ejercicio_completo().solucion_c)
    assert "acumulador" not in c and "/* solución */" not in c and "\n\n" not in c
    assert 'puts("// no es comentario");' in c and "int s = 0;\n" in c
    assert compactar_c("int x;\n" * 2000, maximo=100).endswith("/* … recortado */")


GIFT_CON_METADATOS = """$CATEGORY: $course$/P1

// [tag:complejidad]
::P1:: ¿Cuál es la complejidad? {=O(1) ~O(n)}

// otra
::P2:: ¿Y esta? {=O(n) ~O(1)}
"""


def test_gift_no_envia_comentarios_ni_categorias():
    prompt = construir_prompt_gift(GIFT_CON_METADATOS, AspectoMejora.CLARITY)
    assert "$CATEGORY" not in prompt and "[tag:complejidad]" not in prompt and "// otra" not in prompt
    assert "--- PREGUNTA 2 ---\n::P2::" in prompt


def test_gift_se_rearma_con_lo_devuelto_y_conserva_lo_demas(tmp_path):
    archivo = tmp_path / "b.gift"
    archivo.write_text(GIFT_CON_METADATOS, encoding="utf-8")
    respuesta = "--- PREGUNTA 2 ---\n::P2:: ¿Cuál es la complejidad de recorrer el arreglo? {=O(n) ~O(1)}"
    cambio, _, nuevo = mejorar_archivo_gift(archivo, AspectoMejora.CLARITY, mock_respuesta=respuesta)
    assert cambio
    assert nuevo.startswith("$CATEGORY: $course$/P1\n\n// [tag:complejidad]\n::P1:: ¿Cuál es la complejidad?")
    assert "// otra\n::P2:: ¿Cuál es la complejidad de recorrer el arreglo?" in nuevo


ENUNCIADO_MYST = """(ejercicio_5_12)=
# Fibonacci

Implementá `int fibonacci(int n);`.

### Ejemplos

viejo

## Entrega

Subí el archivo.

---
(ejercicio_5_13)=
"""


def test_las_marcas_myst_no_viajan_y_se_reponen():
    from deckard.core.contexto_ia import separar_marcas

    prefijo, cuerpo, sufijo = separar_marcas(ENUNCIADO_MYST)
    assert prefijo == "(ejercicio_5_12)=" and sufijo.strip() == "---\n(ejercicio_5_13)="
    ej = _ejercicio_completo().model_copy(update={"enunciado_md": ENUNCIADO_MYST})
    prompt = construir_prompt_ejercicio(ej, AspectoMejora.CLARITY)
    assert "(ejercicio_5_13)=" not in prompt and "(ejercicio_5_12)=" not in prompt
    ej_mod, _, nuevo, _ = procesar_respuesta_ia(ej, AspectoMejora.CLARITY, "# Fibonacci\n\nImplementá la función.")
    assert nuevo.startswith("(ejercicio_5_12)=\n# Fibonacci") and nuevo.endswith("---\n(ejercicio_5_13)=")


def test_examples_devuelve_solo_su_seccion_y_reemplaza_la_existente():
    ej = _ejercicio_completo().model_copy(update={"enunciado_md": ENUNCIADO_MYST})
    _, _, nuevo, _ = procesar_respuesta_ia(ej, AspectoMejora.EXAMPLES, "### Ejemplos\n\n| n | fib |\n|--|--|\n| 5 | 5 |")
    assert "viejo" not in nuevo and "| 5 | 5 |" in nuevo
    assert nuevo.index("| 5 | 5 |") < nuevo.index("## Entrega")  # en su lugar, no al final
    assert nuevo.endswith("---\n(ejercicio_5_13)=")


def test_edge_cases_sin_seccion_previa_se_agrega_al_final_del_cuerpo():
    ej = _ejercicio_completo()
    _, _, nuevo, _ = procesar_respuesta_ia(ej, AspectoMejora.EDGE_CASES, "- `n == 0`: retorna 0.")
    assert nuevo.startswith("Sumá los elementos.") and "### Casos Límite y Precondiciones\n\n- `n == 0`" in nuevo


def test_si_el_modelo_devuelve_el_enunciado_entero_se_toma_tal_cual():
    ej = _ejercicio_completo()
    _, _, nuevo, _ = procesar_respuesta_ia(ej, AspectoMejora.EXAMPLES, "Sumá los elementos.\n\n### Ejemplos\n\nx")
    assert nuevo == "Sumá los elementos.\n\n### Ejemplos\n\nx"
