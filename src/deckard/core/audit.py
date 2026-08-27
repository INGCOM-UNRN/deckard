"""Módulo de auditoría, control de salud de especificaciones y análisis de redacción de enunciados."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from deckard.core.bank import buscar_ejercicios, cargar_ejercicio
from deckard.core.models import Ejercicio


@dataclass
class ReporteSaludEjercicio:
    """Diagnóstico detallado de calidad y completitud de un ejercicio."""

    id: str
    directorio: Path
    tema: str
    bloom: int
    minutos: int

    # Métricas de enunciado
    tiene_enunciado_md_file: bool
    longitud_enunciado_chars: int
    longitud_enunciado_words: int
    redaccion_pobre: bool
    diagnostico_redaccion: str  # "pobre", "breve", "completo"

    # Componentes de especificación
    tiene_solucion: bool
    cantidad_pistas: int
    cantidad_funciones: int
    cantidad_tests_funciones: int
    cantidad_testcases_io: int
    tags: List[str]
    verificado: bool

    # Alertas y faltantes
    faltantes: List[str] = field(default_factory=list)
    alertas: List[str] = field(default_factory=list)

    @property
    def total_tests(self) -> int:
        return self.cantidad_tests_funciones + self.cantidad_testcases_io

    @property
    def es_saludable(self) -> bool:
        return (
            not self.redaccion_pobre
            and self.tiene_solucion
            and self.total_tests > 0
            and len(self.faltantes) == 0
        )


def auditar_ejercicio(dir_ej: Path, min_chars: int = 100) -> ReporteSaludEjercicio:
    """Analiza la salud del enunciado y especificación de un ejercicio."""
    ej = cargar_ejercicio(dir_ej)

    enunciado_file = dir_ej / "enunciado.md"
    tiene_md_file = enunciado_file.is_file()

    texto = (ej.enunciado_md or "").strip()
    chars = len(texto)
    words = len(texto.split())

    faltantes: List[str] = []
    alertas: List[str] = []

    # 1. Análisis de redacción
    import re
    placeholder = "(completar enunciado)" in texto.lower() or bool(re.search(r"\b(TODO|FIXME|XXX)\b", texto)) or chars == 0
    if chars < 50 or placeholder or words < 10:
        redaccion_pobre = True
        diag_redaccion = "pobre"
        alertas.append("Enunciado muy breve o incompleto (<50 chars / placeholder)")
    elif chars < min_chars:
        redaccion_pobre = True
        diag_redaccion = "breve"
        alertas.append(f"Enunciado breve (<{min_chars} chars)")
    else:
        redaccion_pobre = False
        diag_redaccion = "completo"

    if not tiene_md_file:
        alertas.append("Enunciado embebido en ejercicio.yaml (sin archivo enunciado.md separado)")

    # 2. Solución modelo
    tiene_sol = bool(ej.solucion_c and ej.solucion_c.strip() and "/* TODO */" not in ej.solucion_c.strip())
    if not tiene_sol:
        faltantes.append("solucion.c")

    # 3. Pistas
    pistas_count = len(ej.pistas)
    if pistas_count == 0:
        faltantes.append("pistas")

    # 4. Tests I/O y funciones
    io_tests_count = 0
    tests_dir = dir_ej / "tests"
    if tests_dir.is_dir():
        io_tests_count = len(list(tests_dir.glob("*.in")))

    fn_tests_count = len(ej.tests_funciones)
    fn_count = len(ej.funciones)

    if io_tests_count == 0 and fn_tests_count == 0:
        faltantes.append("testcases")

    if not ej.tags:
        faltantes.append("tags")

    return ReporteSaludEjercicio(
        id=ej.id,
        directorio=dir_ej,
        tema=ej.tema,
        bloom=int(ej.bloom),
        minutos=ej.minutos_estimados,
        tiene_enunciado_md_file=tiene_md_file,
        longitud_enunciado_chars=chars,
        longitud_enunciado_words=words,
        redaccion_pobre=redaccion_pobre,
        diagnostico_redaccion=diag_redaccion,
        tiene_solucion=tiene_sol,
        cantidad_pistas=pistas_count,
        cantidad_funciones=fn_count,
        cantidad_tests_funciones=fn_tests_count,
        cantidad_testcases_io=io_tests_count,
        tags=ej.tags,
        verificado=ej.verificado,
        faltantes=faltantes,
        alertas=alertas,
    )


def auditar_banco(
    banco: Path,
    patron: Optional[str] = None,
    tema: Optional[str] = None,
    bloom: Optional[int] = None,
    tag: Optional[str] = None,
    min_chars: int = 100,
    solo_pobres: bool = False,
    solo_incompletos: bool = False,
    sin_tests: bool = False,
    sin_pistas: bool = False,
    sin_solucion: bool = False,
) -> List[ReporteSaludEjercicio]:
    """Audita todos los ejercicios del banco aplicando los filtros solicitados."""
    candidatos = buscar_ejercicios(banco, patron=patron, tema=tema, bloom=bloom, tag=tag, recursivo=True)
    reportes: List[ReporteSaludEjercicio] = []

    for dir_ej, _ in candidatos:
        rep = auditar_ejercicio(dir_ej, min_chars=min_chars)

        if solo_pobres and not rep.redaccion_pobre:
            continue
        if solo_incompletos and rep.es_saludable:
            continue
        if sin_tests and rep.total_tests > 0:
            continue
        if sin_pistas and rep.cantidad_pistas > 0:
            continue
        if sin_solucion and rep.tiene_solucion:
            continue

        reportes.append(rep)

    return reportes
