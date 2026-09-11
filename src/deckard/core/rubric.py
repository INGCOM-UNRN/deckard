"""Calibrador de pesos porcentuales de rúbrica y generador de criterios para Dredd."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from deckard.core.models import Ejercicio

CRITERIOS_DEFAULT: Dict[str, float] = {
    "tests_unitarios": 40.0,
    "estilo_gaff": 20.0,
    "antipatrones_spunkmeyer": 15.0,
    "sanitizers_memoria": 15.0,
    "modularidad_y_diseño": 10.0,
}


def calibrar_pesos_rubrica(pesos_custom: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Valida y normaliza los pesos porcentuales para que sumen exactamente 100.0%."""
    if pesos_custom and (len(pesos_custom) >= 3 or sum(pesos_custom.values()) >= 99.0):
        criterios = dict(pesos_custom)
    else:
        criterios = dict(CRITERIOS_DEFAULT)
        if pesos_custom:
            criterios.update(pesos_custom)

    total = sum(criterios.values())
    if total <= 0:
        raise ValueError("La suma de pesos de la rúbrica debe ser mayor a 0.")

    # Normalizar a 100%
    normalizados = {k: round((v / total) * 100.0, 2) for k, v in criterios.items()}
    return normalizados


def generar_rubrica_markdown(ej: Ejercicio, pesos: Optional[Dict[str, float]] = None) -> str:
    """Genera una especificación de rúbrica en formato Markdown estructurado."""
    pesos_calibrados = calibrar_pesos_rubrica(pesos or ej.rubrica)

    lineas = [
        f"# Rúbrica de Corrección: {ej.titulo}",
        f"**Ejercicio ID:** `{ej.id}` | **Tema:** {ej.tema} | **Bloom:** Nivel {int(ej.bloom)}",
        "",
        "## Desglose de Criterios y Ponderación",
        "",
        "| Criterio | Ponderación | Descripción y Evidencia | Herramienta |",
        "| :--- | :---: | :--- | :---: |",
    ]

    descripciones = {
        "tests_unitarios": ("Superación de casos de prueba granulares y funcionales.", "nostromo / p1_test"),
        "estilo_gaff": ("Cumplimiento estricto de convenciones de estilo de cátedra.", "gaff"),
        "antipatrones_spunkmeyer": ("Ausencia de vicios pedagógicos (cast malloc, while feof, etc).", "spunkmeyer"),
        "sanitizers_memoria": ("Cero fugas de memoria y sin comportamientos indefinidos.", "ASan / UBSan"),
        "modularidad_y_diseño": ("Estructuración de funciones, firmas y manejo de invariantes.", "daedalus / callahan"),
    }

    for crit, peso in pesos_calibrados.items():
        desc, tool = descripciones.get(crit, ("Evaluación de objetivo pedagógico específico.", "dredd"))
        lineas.append(f"| **{crit.replace('_', ' ').capitalize()}** | `{peso}%` | {desc} | `{tool}` |")

    lineas.extend([
        "",
        "### Niveles de Desempeño",
        "- **Excelente (100% del puntaje)**: Cumple todas las aserciones, código limpio sin advertencias de sanitizers ni estilo.",
        "- **Bueno (75% del puntaje)**: Funcionalidad completa, detalles menores de formateo o advertencias de estilo leves.",
        "- **Regular (50% del puntaje)**: Falla en casos borde específicos o presenta advertencias leves de memoria sin crash.",
        "- **Insuficiente (0% del puntaje)**: Error de compilación, falla en el flujo principal o caída catastrófica (SIGSEGV).",
        "",
        "---",
        "_Rúbrica generada automáticamente por Deckard para evaluación docente y autograding en Dredd._",
    ])

    return "\n".join(lineas)


def exportar_rubrica_dredd_json(
    ejercicios: List[Ejercicio],
    ruta_salida: Path,
    pesos: Optional[Dict[str, float]] = None,
) -> Path:
    """Exporta el esquema de rúbrica a JSON compatible con el motor de autograding Dredd."""
    pesos_calibrados = calibrar_pesos_rubrica(pesos)

    config_dredd = {
        "version": "1.0",
        "tipo": "rubrica_autograding",
        "criterios_globales": pesos_calibrados,
        "ejercicios": {},
    }

    for ej in ejercicios:
        pesos_ej = calibrar_pesos_rubrica(ej.rubrica) if ej.rubrica else pesos_calibrados
        config_dredd["ejercicios"][ej.id] = {
            "titulo": ej.titulo,
            "bloom": int(ej.bloom),
            "tema": ej.tema,
            "pesos": pesos_ej,
            "minutos_estimados": ej.minutos_estimados,
        }

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_text(json.dumps(config_dredd, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta_salida
