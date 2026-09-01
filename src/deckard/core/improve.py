"""Módulo de curaduría y mejora pedagógica de consignas y bancos con OpenCode."""

from __future__ import annotations

import difflib
from enum import Enum
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import yaml

from deckard.core.bank import ARCHIVO_EJERCICIO, cargar_ejercicio, guardar_ejercicio
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.opencode import (
    DEFAULT_MODEL,
    ejecutar_opencode,
    extraer_bloque_codigo,
)


class AspectoMejora(str, Enum):
    """Aspectos puntuales de mejora sobre consignas de programación."""

    CLARITY = "clarity"          # Claridad, redacción, desambiguación y estilo
    EDGE_CASES = "edge-cases"    # Casos borde, precondiciones y postcondiciones
    EXAMPLES = "examples"        # Ejemplos de entrada/salida (I/O) y trazas
    HINTS = "hints"              # Pistas pedagógicas progresivas
    BLOOM = "bloom"              # Alineación con el nivel cognitivo de Bloom
    TESTCASES = "testcases"      # Generación de casos de prueba
    STARTER = "starter"          # Código esqueleto / starter code y prototipos
    ALL = "all"                  # Mejora holística e integral


NOMBRES_BLOOM = {
    NivelBloom.RECORDAR: "1. Recordar (conocimiento factual, sintaxis básica)",
    NivelBloom.COMPRENDER: "2. Comprender (interpretación de código, flujo y conceptos)",
    NivelBloom.APLICAR: "3. Aplicar (implementación de algoritmos y uso de estructuras)",
    NivelBloom.ANALIZAR: "4. Analizar (descomposición modular, optimización, invariantes)",
    NivelBloom.EVALUAR: "5. Evaluar (auditoría crítica, selección de alternativas, robustez)",
}


SYSTEM_PROMPT_DOCENTE = """Sos un profesor titular y curador pedagógico de la cátedra de Programación en C / Arquitectura de Computadores.
Tu objetivo es auditar, perfeccionar y elevar la calidad de consignas de ejercicios prácticos y preguntas de examen.
Criterios fundamentales de la cátedra:
1. Precisión técnica en C11: sin ambigüedades, con contratos explícitos de memoria y punteros.
2. Pedagogía estructurada: enunciados autoexplicativos, sin términos vagos ni trampas innecesarias.
3. Idioma: Español rioplatense riguroso y formal con voseo académico.
"""


def _obtener_instruccion_aspecto(aspecto: AspectoMejora, ej: Ejercicio) -> str:
    bloom_desc = NOMBRES_BLOOM.get(ej.bloom, str(ej.bloom))
    
    if aspecto == AspectoMejora.CLARITY:
        return f"""Reescribí el enunciado del ejercicio para maximizar su claridad, legibilidad y concisión.
- Eliminá términos vagos o subjetivos ('rápido', 'eficiente', 'adecuado', 'bueno', 'etc.').
- Reemplazá verbos no medibles ('saber', 'conocer', 'entender') por verbos de acción operativos acordes al nivel de Bloom ({bloom_desc}).
- Asegurá que los requisitos funcionales estén organizados lógicamente (ej. usando viñetas o secciones claras).
- Mantené el Markdown estricto y devolvé únicamente el texto completo del enunciado mejorado en Markdown.
"""

    if aspecto == AspectoMejora.EDGE_CASES:
        return f"""Auditá y explicitá exhaustivamente todos los casos borde y condiciones límite para el tema '{ej.tema}'.
- Punteros nulos (NULL) y fallos de asignación si aplica.
- Tamaños cero, arreglos vacíos o dimensiones no válidas.
- Cadenas vacías o caracteres de terminación '\\0'.
- Desbordes aritméticos, división por cero o fin de archivo (EOF).
- Definí con total exactitud el valor de retorno esperado o comportamiento del sistema ante cada caso borde.
- Integrá estos casos límite de forma clara en el enunciado (ej. en una sección '### Casos Límite y Precondiciones').
- Devolvé únicamente el texto completo del enunciado mejorado en Markdown.
"""

    if aspecto == AspectoMejora.EXAMPLES:
        return """Enriquecé el enunciado con ejemplos concretos y pedagógicos de entrada y salida (I/O).
- Incluí al menos 2-3 ejemplos representativos:
  1. Caso estándar / típico de uso.
  2. Caso límite o extremo (vector vacío, 1 elemento, valor borde).
  3. Caso de error o condición especial.
- Utilizá bloques de código o tablas claras que muestren: Entradas -> Salida / Estado resultante -> Breve explicación.
- Devolvé únicamente el texto completo del enunciado mejorado en Markdown con los nuevos ejemplos incorporados.
"""

    if aspecto == AspectoMejora.HINTS:
        return """Diseñá exactamente 3 pistas pedagógicas progresivas para este ejercicio:
- Pista 1 (Conceptual): Orientación teórica o enfoque algorítmico sin entrar en código C.
- Pista 2 (Estructuración): Sugerencia sobre el flujo de control, la modularización o el invariante de ciclo.
- Pista 3 (Técnica en C): Alerta técnica sobre tipos de datos, aritmética de punteros o manejo de memoria, sin revelar la solución completa.
- Formato de respuesta requerido: Bloque YAML con la lista de 3 pistas:
```yaml
pistas:
  - "Pista 1: ..."
  - "Pista 2: ..."
  - "Pista 3: ..."
```
"""

    if aspecto == AspectoMejora.BLOOM:
        return f"""Alineá con rigor la consigna al nivel cognitivo de Bloom asignado ({bloom_desc}).
- Si el nivel es 1 (Recordar) o 2 (Comprender): La consigna debe evaluar identificación conceptual, traza o terminología clara.
- Si el nivel es 3 (Aplicar): Debe requerir la implementación efectiva de algoritmos o manipulación directa de estructuras.
- Si el nivel es 4 (Analizar): Debe involucrar razonamiento sobre invariantes, complejidad algorítmica o descomposición no trivial.
- Si el nivel es 5 (Evaluar): Debe requerir justificación de diseño, robustez ante fallos o contraste de alternativas.
- Ajustá el enunciado para que el desafío intelectual corresponda con exactitud a dicho nivel.
- Devolvé únicamente el texto completo del enunciado mejorado en Markdown.
"""

    if aspecto == AspectoMejora.TESTCASES:
        return f"""Diseñá una suite de casos de prueba rigurosos para validar las soluciones de los estudiantes sobre '{ej.tema}'.
- Casos típicos de funcionamiento.
- Casos de borde (entradas mínimas, ceros, nulos).
- Casos de estrés o valores límites.
- Proveé los casos en formato estructurado:
```yaml
testcases:
  - nombre: "caso_basico"
    descripcion: "..."
    entrada: "..."
    salida_esperada: "..."
  - nombre: "caso_borde"
    descripcion: "..."
    entrada: "..."
    salida_esperada: "..."
```
"""

    if aspecto == AspectoMejora.STARTER:
        return """Generá o perfeccioná el código esqueleto inicial (starter_code) y la cabecera .h del ejercicio.
- Firmas de funciones canónicas con tipos precisos (size_t para longitudes, const para lecturas).
- Documentación Doxygen completa (@param, @return, @pre, @post).
- Prototipo limpio listo para compilar con gcc -Wall -Wextra -std=c11.
- Devolvé el código en un bloque C cercado (```c ... ```).
"""

    # AspectoMejora.ALL
    return f"""Realizá una curaduría integral y holística de la consigna de este ejercicio:
1. Redacción clara, fluida y sin ambigüedades.
2. Casos borde y precondiciones explícitamente detallados para '{ej.tema}'.
3. Ejemplos de ejecución (I/O) didácticos y bien formateados.
4. Alineación precisa con el nivel de Bloom ({bloom_desc}).
- Devolvé únicamente el texto completo del enunciado mejorado en Markdown.
"""


def construir_prompt_ejercicio(
    ejercicio: Ejercicio,
    aspecto: AspectoMejora,
    custom_prompt: Optional[str] = None,
    prompt_file: Optional[Path] = None,
) -> str:
    """Construye el prompt completo para invocar a OpenCode sobre un ejercicio."""
    instruccion_aspecto = _obtener_instruccion_aspecto(aspecto, ejercicio)

    partes = [
        f"Ejercicio ID: {ejercicio.id}",
        f"Título: {ejercicio.titulo}",
        f"Tema: {ejercicio.tema}",
        f"Nivel Bloom: {NOMBRES_BLOOM.get(ejercicio.bloom, str(ejercicio.bloom))}",
        f"Duración estimada: {ejercicio.minutos_estimados} minutos",
    ]

    if ejercicio.funciones:
        firmas = "\n".join(f"- `{f.firma}`: {f.descripcion or ''}" for f in ejercicio.funciones)
        partes.append(f"\nFunciones C requeridas:\n{firmas}")

    if ejercicio.pistas:
        pistas_txt = "\n".join(f"- {p}" for p in ejercicio.pistas)
        partes.append(f"\nPistas actuales:\n{pistas_txt}")

    if ejercicio.enunciado_md:
        partes.append(f"\n--- ENUNCIADO ACTUAL ---\n{ejercicio.enunciado_md}\n--- FIN ENUNCIADO ACTUAL ---")

    if ejercicio.solucion_c:
        partes.append(f"\n--- SOLUCIÓN MODELO (REFERENCIA) ---\n```c\n{ejercicio.solucion_c[:1500]}\n```\n--- FIN SOLUCIÓN ---")

    prompt_custom_txt = ""
    if prompt_file and prompt_file.is_file():
        prompt_custom_txt = prompt_file.read_text(encoding="utf-8").strip()
    elif custom_prompt:
        prompt_custom_txt = custom_prompt.strip()

    prompt_final = (
        f"### CONTEXTO DEL EJERCICIO:\n"
        + "\n".join(partes)
        + f"\n\n### INSTRUCCIONES ESPECÍFICAS ({aspecto.value.upper()}):\n"
        + instruccion_aspecto
    )

    if prompt_custom_txt:
        prompt_final += f"\n\n### AJUSTES Y DIRECTIVAS ADICIONALES DEL DOCENTE:\n{prompt_custom_txt}\n"

    return prompt_final


def construir_prompt_gift(
    texto_gift: str,
    aspecto: AspectoMejora,
    custom_prompt: Optional[str] = None,
    prompt_file: Optional[Path] = None,
) -> str:
    """Construye el prompt para mejorar preguntas en formato GIFT (Moodle)."""
    instrucciones = f"""Curá pedagógicamente las siguientes preguntas escritas en formato GIFT de Moodle.
Aspecto solicitado: '{aspecto.value}'.
- Mantené la sintaxis formal estricta de GIFT (claves {{ ... }}, opciones = / ~, feedback #).
- Mejorá la claridad de la consigna o enunciado eliminando ambigüedades.
- Asegurá que los distractores sean plausibles pero pedagógicamente incorrectos.
- Incorporá o enriquecé las explicaciones de retroalimentación (# feedback) para cada opción.
- Devolvé únicamente el contenido en formato GIFT listo para importar.
"""
    prompt_custom_txt = ""
    if prompt_file and prompt_file.is_file():
        prompt_custom_txt = prompt_file.read_text(encoding="utf-8").strip()
    elif custom_prompt:
        prompt_custom_txt = custom_prompt.strip()

    prompt = (
        f"### BANCO DE PREGUNTAS GIFT:\n```gift\n{texto_gift}\n```\n\n"
        f"### INSTRUCCIONES:\n{instrucciones}"
    )
    if prompt_custom_txt:
        prompt += f"\n\n### AJUSTES ADICIONALES DEL DOCENTE:\n{prompt_custom_txt}\n"
    return prompt


class ResultadoMejora:
    """Resultado del proceso de mejora sobre un ejercicio."""

    def __init__(
        self,
        ejercicio_id: str,
        aspecto: AspectoMejora,
        cambio_realizado: bool,
        diff: str,
        resumen: str,
        contenido_anterior: str,
        contenido_nuevo: str,
        pistas_nuevas: Optional[List[str]] = None,
    ):
        self.ejercicio_id = ejercicio_id
        self.aspecto = aspecto
        self.cambio_realizado = cambio_realizado
        self.diff = diff
        self.resumen = resumen
        self.contenido_anterior = contenido_anterior
        self.contenido_nuevo = contenido_nuevo
        self.pistas_nuevas = pistas_nuevas or []


def procesar_respuesta_ia(
    ej: Ejercicio,
    aspecto: AspectoMejora,
    respuesta_ia: str,
) -> Tuple[Ejercicio, str, str, Optional[List[str]]]:
    """Interpreta la respuesta de OpenCode y actualiza el modelo en memoria."""
    ej_mod = ej.model_copy(deep=True)
    anterior = ""
    nuevo = ""
    pistas_nuevas: Optional[List[str]] = None

    if aspecto in (
        AspectoMejora.CLARITY,
        AspectoMejora.EDGE_CASES,
        AspectoMejora.EXAMPLES,
        AspectoMejora.BLOOM,
        AspectoMejora.ALL,
    ):
        anterior = ej.enunciado_md
        # Extraer markdown cercado si lo envolvió
        nuevo = extraer_bloque_codigo(respuesta_ia, "markdown")
        if nuevo == respuesta_ia and respuesta_ia.startswith("```"):
            nuevo = extraer_bloque_codigo(respuesta_ia)
        ej_mod.enunciado_md = nuevo

    elif aspecto == AspectoMejora.HINTS:
        anterior = "\n".join(f"- {p}" for p in ej.pistas)
        raw_yaml = extraer_bloque_codigo(respuesta_ia, "yaml")
        try:
            parsed = yaml.safe_load(raw_yaml)
            if isinstance(parsed, dict) and "pistas" in parsed:
                pistas_nuevas = [str(p).strip() for p in parsed["pistas"] if p]
            elif isinstance(parsed, list):
                pistas_nuevas = [str(p).strip() for p in parsed if p]
        except Exception:
            pass

        if not pistas_nuevas:
            # Fallback a extracción por viñetas
            lineas = [l.strip().lstrip("-*0123456789. ") for l in respuesta_ia.splitlines() if l.strip().startswith(("-", "*", "1.", "2.", "3.", "Pista"))]
            pistas_nuevas = [l for l in lineas if len(l) > 10][:3]

        if pistas_nuevas:
            ej_mod.pistas = pistas_nuevas
            nuevo = "\n".join(f"- {p}" for p in pistas_nuevas)
        else:
            nuevo = anterior

    elif aspecto == AspectoMejora.STARTER:
        anterior = ej.starter_code
        nuevo = extraer_bloque_codigo(respuesta_ia, "c")
        ej_mod.starter_code = nuevo

    elif aspecto == AspectoMejora.TESTCASES:
        anterior = f"Tests actuales: {len(ej.tests_funciones)}"
        nuevo = respuesta_ia
        # Guarda descripción o deja los testcases propuestos

    return ej_mod, anterior, nuevo, pistas_nuevas


def generar_diff_texto(anterior: str, nuevo: str, etiqueta: str = "enunciado") -> str:
    """Genera un unified diff entre dos versiones de texto."""
    a_lines = anterior.splitlines(keepends=True)
    b_lines = nuevo.splitlines(keepends=True)
    diff = difflib.unified_diff(
        a_lines,
        b_lines,
        fromfile=f"a/{etiqueta}",
        tofile=f"b/{etiqueta}",
    )
    return "".join(diff)


def mejorar_ejercicio(
    dir_ejercicio: Path,
    aspecto: AspectoMejora,
    custom_prompt: Optional[str] = None,
    prompt_file: Optional[Path] = None,
    modelo: str = DEFAULT_MODEL,
    usar_sandbox: bool = True,
    aplicar: bool = False,
    timeout: int = 180,
    mock_respuesta: Optional[str] = None,
) -> ResultadoMejora:
    """Ejecuta el flujo de mejora con OpenCode sobre un ejercicio específico."""
    ej = cargar_ejercicio(dir_ejercicio)
    prompt = construir_prompt_ejercicio(
        ejercicio=ej,
        aspecto=aspecto,
        custom_prompt=custom_prompt,
        prompt_file=prompt_file,
    )

    if mock_respuesta is not None:
        respuesta = mock_respuesta
    else:
        respuesta = ejecutar_opencode(
            prompt=prompt,
            modelo=modelo,
            dir_trabajo=dir_ejercicio,
            timeout=timeout,
            usar_sandbox=usar_sandbox,
            system_prompt=SYSTEM_PROMPT_DOCENTE,
        )

    ej_mod, anterior, nuevo, pistas_nuevas = procesar_respuesta_ia(ej, aspecto, respuesta)
    cambio = anterior.strip() != nuevo.strip()
    diff = generar_diff_texto(anterior, nuevo, etiqueta=aspecto.value)

    if aplicar and cambio:
        guardar_ejercicio(ej_mod, dir_ejercicio.parent)

    resumen = (
        f"Mejora de '{aspecto.value}' completada para '{ej.id}'. "
        + ("Cambios aplicados en disco." if aplicar and cambio else ("Cambios detectados (previsualización)." if cambio else "Sin modificaciones detectadas."))
    )

    return ResultadoMejora(
        ejercicio_id=ej.id,
        aspecto=aspecto,
        cambio_realizado=cambio,
        diff=diff,
        resumen=resumen,
        contenido_anterior=anterior,
        contenido_nuevo=nuevo,
        pistas_nuevas=pistas_nuevas,
    )


def mejorar_archivo_gift(
    ruta_gift: Path,
    aspecto: AspectoMejora,
    custom_prompt: Optional[str] = None,
    prompt_file: Optional[Path] = None,
    modelo: str = DEFAULT_MODEL,
    usar_sandbox: bool = True,
    aplicar: bool = False,
    timeout: int = 180,
    mock_respuesta: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """Mejora un banco o archivo de preguntas en formato GIFT."""
    contenido_anterior = ruta_gift.read_text(encoding="utf-8")
    prompt = construir_prompt_gift(
        texto_gift=contenido_anterior,
        aspecto=aspecto,
        custom_prompt=custom_prompt,
        prompt_file=prompt_file,
    )

    if mock_respuesta is not None:
        respuesta = mock_respuesta
    else:
        respuesta = ejecutar_opencode(
            prompt=prompt,
            modelo=modelo,
            dir_trabajo=ruta_gift.parent,
            timeout=timeout,
            usar_sandbox=usar_sandbox,
            system_prompt=SYSTEM_PROMPT_DOCENTE,
        )

    contenido_nuevo = extraer_bloque_codigo(respuesta, "gift")
    if contenido_nuevo == respuesta and respuesta.startswith("```"):
        contenido_nuevo = extraer_bloque_codigo(respuesta)

    cambio = contenido_anterior.strip() != contenido_nuevo.strip()
    diff = generar_diff_texto(contenido_anterior, contenido_nuevo, etiqueta=ruta_gift.name)

    if aplicar and cambio:
        ruta_gift.write_text(contenido_nuevo, encoding="utf-8")

    return cambio, diff, contenido_nuevo
