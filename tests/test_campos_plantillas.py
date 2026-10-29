"""Campos de las plantillas de enunciados en el modelo de ejercicio (unidad, rúbrica en lista, itinerario…)."""

from pathlib import Path

from deckard.core.audit import auditar_banco
from deckard.core.bank import cargar_ejercicio, guardar_ejercicio
from deckard.core.deps import build_dependency_graph
from deckard.core.export import renderizar_ejercicio_html, renderizar_ejercicio_md
from deckard.core.models import Ejercicio

BASE = """id: {id}
titulo: Ejercicio {id}
tema: punteros
bloom: 3
minutos_estimados: 20
"""


def _ej(banco: Path, eid: str, extra: str = "", solucion: str = "int main(void) { return 0; } /* SOLUCION */\n") -> Path:
    d = banco / eid
    d.mkdir(parents=True)
    (d / "ejercicio.yaml").write_text(BASE.format(id=eid) + extra, encoding="utf-8")
    (d / "enunciado.md").write_text("Consigna.\n", encoding="utf-8")
    (d / "solucion.c").write_text(solucion, encoding="utf-8")
    return d


COMPLETO = """unidad: 3
modulo: Punteros y memoria
subtema: aritmetica
dificultad: intermedia
esfuerzo_lineas_codigo: 30
tipo: practica_guiada
obligatorio: true
prerrequisitos: [variables, b]
siguiente_recomendado: [c]
referencias_teoria: {apunte: https://apunte/punteros, seccion: Aritmética, bibliografia: [K&R cap. 5]}
visibilidad_solucion: oculta
rubrica:
- {criterio: tests_unitarios, peso: 80}
- {criterio: estilo_gaff, peso: 20}
"""


def test_campos_nuevos_ida_y_vuelta(tmp_path):
    d = _ej(tmp_path / "banco", "a", COMPLETO)
    (d / "a.h").write_text("int f(void);\n", encoding="utf-8")
    ej = cargar_ejercicio(d)
    assert (ej.unidad, ej.dificultad, ej.tipo, ej.obligatorio) == (3, "intermedia", "practica_guiada", True)
    assert ej.referencias_teoria.seccion == "Aritmética"
    assert ej.pesos_rubrica == {"tests_unitarios": 80, "estilo_gaff": 20}
    assert (ej.header_name, ej.header_c) == ("a.h", "int f(void);\n")
    assert not ej.solucion_publicable
    guardar_ejercicio(ej, tmp_path / "copia")
    texto = (tmp_path / "copia" / "a" / "ejercicio.yaml").read_text(encoding="utf-8")
    assert "header_c" not in texto and "criterio: tests_unitarios" in texto
    assert cargar_ejercicio(tmp_path / "copia" / "a").model_dump() == ej.model_dump()   # la cabecera no entra


def test_rubrica_en_mapa_sigue_valiendo():
    ej = Ejercicio(id="x", titulo="X", tema="t", bloom=1, minutos_estimados=5, rubrica={"tests_unitarios": 100})
    assert ej.rubrica[0].criterio == "tests_unitarios" and ej.pesos_rubrica == {"tests_unitarios": 100}


def test_plantillas_muestran_los_campos_y_respetan_la_solucion_oculta(tmp_path):
    d = _ej(tmp_path / "banco", "a", COMPLETO)
    ej = cargar_ejercicio(d)
    md, _ = renderizar_ejercicio_md(ej, d, incluir_solucion=True, incluir_pistas=True, incluir_tests=True)
    assert "**Unidad:** 3" in md and "Aritmética" in md and "tests_unitarios | **80" in md and "SOLUCION" not in md
    html, _ = renderizar_ejercicio_html(ej, d, incluir_solucion=True)
    assert "SOLUCION" not in html
    visible = ej.model_copy(update={"visibilidad_solucion": "desplegable"})
    assert "SOLUCION" in renderizar_ejercicio_md(visible, d, incluir_solucion=True)[0]


def test_itinerario_en_el_grafo_y_referencias_rotas(tmp_path):
    banco = tmp_path / "banco"
    _ej(banco, "a", "prerrequisitos: [b, variables_que_no]\nsiguiente_recomendado: [c, fantasma]\n")
    _ej(banco, "b")
    _ej(banco, "c")
    grafo = build_dependency_graph([(banco / e, cargar_ejercicio(banco / e)) for e in "abc"])
    assert "b" in grafo.nodes["a"].prerequisites and "c" in grafo.nodes["a"].dependents
    alertas = next(r for r in auditar_banco(banco) if r.id == "a").alertas
    assert "prerrequisitos: «variables_que_no» no es ni ejercicio ni tema del banco" in alertas
    assert "siguiente_recomendado: «fantasma» no es ejercicio del banco" in alertas
    assert not any("«b»" in a or "«c»" in a for a in alertas)
