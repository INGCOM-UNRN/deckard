"""Nota final con la rúbrica de deckard sobre lo que evaluó dredd (Ola 8, Decisión 3 del 07/10).

La rúbrica es de deckard; dredd evalúa y no pondera. Por cada revisión, dredd deja en `rNi/`:

- `auditoria.json`: el estado de la corrida y `resultado` (si compiló y cada prueba, con fugas).
- `hallazgos.json`: lo que encontraron ripley y sus satélites en la forma común de `yutani.hallazgos`.

`deckard exercise rubric <ejercicio> --eval-results <dir>` toma la última revisión de cada estudiante
y calcula, por criterio, un logro entre 0 y 1:

- `tests_unitarios`: pruebas aprobadas / total (sin pruebas, 1 si compiló).
- `test:<nombre>`: 1 si esa prueba del ejercicio pasó, 0 si no (o si no se corrió).
- Los criterios de hallazgos parten de 1 y descuentan por cada hallazgo según su severidad
  (`DESCUENTOS`), sin bajar de 0. Cada hallazgo cuenta para un solo criterio: el primero de la
  rúbrica, en el orden de `CRITERIOS_DE_HALLAZGOS`, que lo reclama (un criterio con el nombre de una
  categoría de yutani, como `memoria`, reclama los de esa categoría antes que los generales).
  `sanitizers_memoria` descuenta además cada prueba con fuga de memoria.
- Si la entrega no compila, todos los criterios valen 0 (nivel «Insuficiente» de la rúbrica).

La nota (0–10) es la suma de logro × peso. Un criterio sin evidencia (un `auditoria.json` anterior al
cursor de dredd, o un criterio que no se califica automáticamente) no entra: los demás se
reescalan y la nota queda marcada como provisoria, para que el docente la complete.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from yutani.hallazgos import CATEGORIAS
except ImportError:  # pragma: no cover - yutani es dependencia; por si se usa suelto
    CATEGORIAS = {}

DESCUENTOS = {"error": 0.25, "advertencia": 0.10, "estilo": 0.05, "info": 0.0}
DESCUENTO_FUGA = 0.25
PREFIJO_TEST = "test:"

# Criterio general → (categorías, herramientas) de los hallazgos que reclama, en este orden.
CRITERIOS_DE_HALLAZGOS: Dict[str, Tuple[frozenset, frozenset]] = {
    "antipatrones_spunkmeyer": (frozenset(), frozenset({"spunkmeyer"})),
    "sanitizers_memoria": (frozenset({"memoria", "punteros", "arreglos"}),
                           frozenset({"tetsuo", "valgrind", "hal", "asan", "ubsan"})),
    "modularidad_y_diseño": (frozenset({"funciones", "tad", "estructuras", "documentacion", "declaraciones"}),
                             frozenset({"motoko", "corbel", "callahan"})),
    "estilo_gaff": (frozenset({"estilo"}), frozenset({"gaff"})),
}
CRITERIOS_DE_PRUEBAS = ("tests_unitarios",)


@dataclass
class Revision:
    """Lo que dredd dejó de la última revisión evaluada de un estudiante."""

    alumno: str
    revision: str
    directorio: Path
    hallazgos: List[Dict[str, Any]] = field(default_factory=list)
    resultado: Optional[Dict[str, Any]] = None
    estado: Optional[str] = None


@dataclass
class Calificacion:
    alumno: str
    revision: str
    nota: float
    provisoria: bool
    logros: Dict[str, Optional[float]]
    detalle: Dict[str, List[str]]
    sin_criterio: List[Dict[str, Any]]
    pesos: Dict[str, float]
    motivo: Optional[str] = None
    enlaces: List[str] = field(default_factory=list)


def es_criterio_conocido(criterio: str) -> bool:
    return (criterio in CRITERIOS_DE_HALLAZGOS or criterio in CRITERIOS_DE_PRUEBAS
            or criterio in CATEGORIAS or criterio.startswith(PREFIJO_TEST))


def nombre_de_prueba(criterio: str) -> Optional[str]:
    return criterio[len(PREFIJO_TEST):].strip() if criterio.startswith(PREFIJO_TEST) else None


# ---------------------------------------------------------------------------
# Lectura de los resultados de dredd
# ---------------------------------------------------------------------------

def _leer_json(ruta: Path) -> Optional[Dict[str, Any]]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def _numero(nombre: str) -> int:
    m = re.match(r"^r(\d+)i$", nombre)
    return int(m.group(1)) if m else 0


def leer_revision(directorio: Path) -> Revision:
    auditoria = _leer_json(directorio / "auditoria.json") or {}
    hallazgos = (_leer_json(directorio / "hallazgos.json") or {}).get("hallazgos") or []
    return Revision(
        alumno=str(auditoria.get("alumno") or directorio.parent.name),
        revision=str(auditoria.get("revision") or directorio.name),
        directorio=directorio,
        hallazgos=[h for h in hallazgos if isinstance(h, dict)],
        resultado=auditoria.get("resultado") if isinstance(auditoria.get("resultado"), dict) else None,
        estado=auditoria.get("estado"),
    )


def leer_resultados(ruta: Path) -> List[Revision]:
    """La última revisión de cada estudiante bajo `ruta` (un directorio del curso, el de un
    estudiante, un `rNi/` o uno de sus `hallazgos.json`/`auditoria.json`)."""
    ruta = Path(ruta)
    if ruta.is_file():
        return [leer_revision(ruta.parent)]
    directorios = {p.parent for nombre in ("auditoria.json", "hallazgos.json") for p in ruta.rglob(nombre)}
    ultimas: Dict[str, Tuple[Tuple[str, int], Revision]] = {}
    for d in sorted(directorios):
        rev = leer_revision(d)
        fecha = str((_leer_json(d / "auditoria.json") or {}).get("fecha") or "")
        clave = (fecha, _numero(d.name))
        if rev.alumno not in ultimas or clave > ultimas[rev.alumno][0]:
            ultimas[rev.alumno] = (clave, rev)
    return [rev for _, rev in sorted(ultimas.values(), key=lambda par: par[1].alumno)]


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------

def _reclamante(h: Dict[str, Any], criterios: Iterable[str]) -> Optional[str]:
    criterios = list(criterios)
    categoria = str(h.get("categoria") or "")
    herramienta = str(h.get("herramienta") or "")
    if categoria in criterios:
        return categoria
    for criterio, (categorias, herramientas) in CRITERIOS_DE_HALLAZGOS.items():
        if criterio in criterios and (categoria in categorias or herramienta in herramientas):
            return criterio
    return None


def _caso(casos: List[Dict[str, Any]], nombre: str) -> Optional[Dict[str, Any]]:
    for c in casos:
        n = str(c.get("nombre") or "")
        if n == nombre or n.split("/")[-1].strip() == nombre:
            return c
    return None


def calificar(rev: Revision, pesos: Dict[str, float]) -> Calificacion:
    """La nota de una revisión con la rúbrica `pesos` (porcentajes que suman 100)."""
    logros: Dict[str, Optional[float]] = {}
    detalle: Dict[str, List[str]] = {c: [] for c in pesos}
    resultado = rev.resultado
    tests = (resultado or {}).get("tests") or {}
    casos = [c for c in tests.get("casos") or [] if isinstance(c, dict)]

    enlaces = sorted({str(h["enlace"]) for h in rev.hallazgos if h.get("enlace")})
    if resultado is not None and not resultado.get("compilacion", False):
        logros = {c: 0.0 for c in pesos}
        return Calificacion(rev.alumno, rev.revision, 0.0, False, logros, detalle, [], dict(pesos),
                            motivo="La entrega no compila: todos los criterios valen 0.", enlaces=enlaces)

    sin_criterio = []
    puntaje = {c: 1.0 for c in pesos if c in CRITERIOS_DE_HALLAZGOS or c in CATEGORIAS}
    for h in rev.hallazgos:
        criterio = _reclamante(h, pesos)
        if criterio is None:
            sin_criterio.append(h)
            continue
        descuento = DESCUENTOS.get(str(h.get("severidad") or "advertencia"), DESCUENTOS["advertencia"])
        puntaje[criterio] = max(0.0, puntaje[criterio] - descuento)
        lugar = ":".join(str(x) for x in (h.get("archivo"), h.get("linea")) if x)
        detalle[criterio].append(f"{h.get('id') or h.get('codigo')}: {h.get('mensaje', '')}" + (f" ({lugar})" if lugar else ""))

    for criterio in pesos:
        prueba = nombre_de_prueba(criterio)
        if criterio in puntaje:
            if criterio == "sanitizers_memoria":
                if resultado is None:
                    logros[criterio] = None
                    continue
                fugas = [c for c in casos if c.get("fuga_memoria")]
                for c in fugas:
                    detalle[criterio].append(f"Fuga de memoria en la prueba «{c.get('nombre')}»")
                puntaje[criterio] = max(0.0, puntaje[criterio] - DESCUENTO_FUGA * len(fugas))
            logros[criterio] = round(puntaje[criterio], 4)
        elif criterio in CRITERIOS_DE_PRUEBAS:
            if resultado is None:
                logros[criterio] = None
                continue
            total = int(tests.get("total") or 0)
            aprobados = int(tests.get("aprobados") or 0)
            logros[criterio] = round(aprobados / total, 4) if total else 1.0
            detalle[criterio] += [f"Falló la prueba «{c.get('nombre')}»" for c in casos if not c.get("aprobado")]
        elif prueba is not None:
            caso = _caso(casos, prueba) if resultado is not None else None
            if resultado is None:
                logros[criterio] = None
            elif caso is None:
                logros[criterio] = 0.0
                detalle[criterio].append(f"La prueba «{prueba}» no se corrió.")
            else:
                logros[criterio] = 1.0 if caso.get("aprobado") else 0.0
                if not caso.get("aprobado"):
                    detalle[criterio].append(f"Falló la prueba «{prueba}».")
        else:
            logros[criterio] = None
            detalle[criterio].append("Este criterio no se califica automáticamente: completalo a mano.")

    evaluados = {c: p for c, p in pesos.items() if logros.get(c) is not None}
    total_pesos = sum(evaluados.values())
    nota = 10.0 * sum(p * (logros[c] or 0.0) for c, p in evaluados.items()) / total_pesos if total_pesos else 0.0
    provisoria = len(evaluados) < len(pesos) or rev.estado not in (None, "completa")
    motivo = None
    if rev.estado not in (None, "completa"):
        motivo = f"La evaluación de dredd quedó «{rev.estado}»: volvé a correrla (dredd eval --failed-only)."
    elif provisoria:
        motivo = "Hay criterios sin evidencia automática: la nota se calculó con los demás."
    return Calificacion(rev.alumno, rev.revision, round(nota, 2), provisoria, logros, detalle, sin_criterio,
                        dict(pesos), motivo=motivo, enlaces=enlaces)


# ---------------------------------------------------------------------------
# Salidas: calificaciones.csv (Moodle) y devoluciones en Markdown
# ---------------------------------------------------------------------------

def _titulo(criterio: str) -> str:
    prueba = nombre_de_prueba(criterio)
    if prueba is not None:
        return f"Prueba {prueba}"
    if criterio in CATEGORIAS:
        return CATEGORIAS[criterio][0]
    return criterio.replace("_", " ").capitalize()


def devolucion_markdown(c: Calificacion, titulo: str) -> str:
    lineas = [
        f"# Devolución: {titulo}",
        "",
        f"**Estudiante:** {c.alumno} · **Revisión:** {c.revision} · "
        f"**Nota:** {c.nota:.2f} / 10" + (" (provisoria)" if c.provisoria else ""),
        "",
    ]
    if c.motivo:
        lineas += [f"> {c.motivo}", ""]
    lineas += ["| Criterio | Peso | Logro |", "| :--- | ---: | ---: |"]
    for criterio, peso in c.pesos.items():
        logro = c.logros.get(criterio)
        lineas.append(f"| {_titulo(criterio)} | {peso:g} % | {'—' if logro is None else f'{logro * 100:.0f} %'} |")
    lineas.append("")
    for criterio in c.pesos:
        if c.detalle.get(criterio):
            lineas.append(f"## {_titulo(criterio)}\n")
            lineas += [f"- {d}" for d in c.detalle[criterio][:30]]
            if len(c.detalle[criterio]) > 30:
                lineas.append(f"- … y {len(c.detalle[criterio]) - 30} más.")
            lineas.append("")
    if c.sin_criterio:
        lineas.append("## Otras observaciones (no descuentan)\n")
        lineas += [f"- {h.get('id') or h.get('codigo')}: {h.get('mensaje', '')}" for h in c.sin_criterio[:30]]
        lineas.append("")
    if c.enlaces:
        lineas += ["## Para repasar\n"] + [f"- <{e}>" for e in c.enlaces[:10]] + [""]
    return "\n".join(lineas)


def _resumen(c: Calificacion) -> str:
    partes = [f"{_titulo(k)}: {'—' if v is None else f'{v * 100:.0f} %'}" for k, v in c.logros.items()]
    texto = f"Revisión {c.revision} | " + " | ".join(partes)
    return texto + (" | Nota provisoria" if c.provisoria else "")


def escribir_calificaciones(calificaciones: List[Calificacion], salida: Path, titulo: str) -> Tuple[Path, Path]:
    """`calificaciones.csv` para importar en el libro de calificaciones de Moodle (columna `Usuario`
    para vincular y `Calificación` 0–10) y `devoluciones/<alumno>.md`."""
    salida.mkdir(parents=True, exist_ok=True)
    devoluciones = salida / "devoluciones"
    devoluciones.mkdir(exist_ok=True)
    criterios = list(calificaciones[0].pesos) if calificaciones else []
    csv_path = salida / "calificaciones.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.writer(f)
        escritor.writerow(["Usuario", "Calificación", "Provisoria", "Revisión", *[_titulo(k) + " (%)" for k in criterios],
                           "Comentarios de retroalimentación"])
        for c in calificaciones:
            escritor.writerow([c.alumno, f"{c.nota:.2f}", "sí" if c.provisoria else "no", c.revision,
                               *["" if c.logros.get(k) is None else f"{(c.logros[k] or 0) * 100:.0f}" for k in criterios],
                               _resumen(c)])
            (devoluciones / f"{c.alumno}.md").write_text(devolucion_markdown(c, titulo), encoding="utf-8")
    return csv_path, devoluciones


# ---------------------------------------------------------------------------
# Coherencia de la rúbrica de un ejercicio (deckard verify --rubric)
# ---------------------------------------------------------------------------

def validar_rubrica(rubrica: Optional[Dict[str, Any]], pruebas: Iterable[str]) -> Tuple[List[str], List[str]]:
    """(errores, avisos) de una rúbrica: los pesos tienen que ser números no negativos que sumen
    100 % y cada `test:<nombre>` tiene que ser una prueba del ejercicio."""
    if not rubrica:
        return [], ["Sin rúbrica propia: se califica con la de la cátedra."]
    errores, avisos = [], []
    nombres = set(pruebas)
    total = 0.0
    for criterio, peso in rubrica.items():
        if isinstance(peso, bool) or not isinstance(peso, (int, float)):
            errores.append(f"«{criterio}»: el peso tiene que ser un número (es {peso!r}).")
            continue
        if peso < 0:
            errores.append(f"«{criterio}»: el peso no puede ser negativo ({peso:g}).")
        total += float(peso)
        prueba = nombre_de_prueba(str(criterio))
        if prueba is not None and prueba not in nombres:
            disponibles = ", ".join(sorted(nombres)) or "el ejercicio no tiene pruebas"
            errores.append(f"«{criterio}»: no existe la prueba «{prueba}» ({disponibles}).")
        elif not es_criterio_conocido(str(criterio)):
            avisos.append(f"«{criterio}» no se califica automáticamente: la nota va a quedar provisoria.")
    if abs(total - 100.0) > 0.01:
        errores.append(f"Los pesos suman {total:g} %, no 100 %.")
    return errores, avisos
