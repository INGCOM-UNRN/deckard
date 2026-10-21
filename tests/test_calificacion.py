"""Nota con la rúbrica sobre los resultados de dredd y coherencia de las rúbricas (Ola 8)."""

import csv
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import guardar_ejercicio
from deckard.core.calificacion import Revision, calificar, leer_resultados, validar_rubrica
from deckard.core.models import CasoTestFuncion, Ejercicio, NivelBloom

runner = CliRunner()

PESOS = {"tests_unitarios": 50.0, "estilo_gaff": 20.0, "sanitizers_memoria": 20.0, "test:caso_cero": 10.0}


def _hallazgo(herramienta, codigo, categoria, severidad="advertencia"):
    return {"id": f"{herramienta}:{codigo}", "herramienta": herramienta, "codigo": codigo, "categoria": categoria,
            "severidad": severidad, "mensaje": f"falla {codigo}", "archivo": "src/main.c", "linea": 3, "columna": None,
            "enlace": f"https://apunte/{categoria}"}


def _revision(directorio: Path, alumno: str, *, compila=True, casos=(), hallazgos=(), estado="completa",
              fecha="2026-10-21T10:00:00+00:00", con_resultado=True):
    """Lo que deja dredd en `rNi/` (auditoria.json 1.1.0 y hallazgos.json)."""
    directorio.mkdir(parents=True, exist_ok=True)
    auditoria = {"schema_version": "1.1.0", "fecha": fecha, "actividad": "tp1", "alumno": alumno,
                 "revision": directorio.name.rstrip("i"), "commit": None, "estado": estado, "versiones": {}}
    if con_resultado:
        auditoria["resultado"] = {
            "compilacion": compila,
            "tests": {"aprobados": sum(1 for c in casos if c[1]), "total": len(casos),
                      "casos": [{"nombre": n, "aprobado": a, "fuga_memoria": f} for n, a, f in casos]},
        }
    (directorio / "auditoria.json").write_text(json.dumps(auditoria))
    (directorio / "hallazgos.json").write_text(json.dumps({"schema_version": "1.0.0", "hallazgos": list(hallazgos)}))
    return directorio


@pytest.fixture
def curso(tmp_path: Path) -> Path:
    raiz = tmp_path / "entregas"
    # ana: todo bien en r2 (r1 tenía una prueba fallida y no tiene que contar)
    _revision(raiz / "ana" / "r1i", "ana", casos=[("tp1 / caso_cero", False, False)], fecha="2026-10-20T10:00:00+00:00")
    _revision(raiz / "ana" / "r2i", "ana", casos=[("tp1 / caso_cero", True, False), ("tp1 / caso_uno", True, False)])
    # beto: una prueba fallida, una fuga y dos hallazgos de estilo y uno de memoria
    _revision(raiz / "beto" / "r1i", "beto",
              casos=[("tp1 / caso_cero", True, True), ("tp1 / caso_uno", False, False)],
              hallazgos=[_hallazgo("gaff", "0x0001h", "estilo"), _hallazgo("gaff", "0x0002h", "estilo", "error"),
                         _hallazgo("gaff", "0x3001h", "memoria", "error"), _hallazgo("ripley", "X1", "recursion")])
    # caro: no compila
    _revision(raiz / "caro" / "r1i", "caro", compila=False, hallazgos=[_hallazgo("gaff", "0x0001h", "estilo")])
    # dani: registro anterior al cursor de dredd (sin resultado)
    _revision(raiz / "dani" / "r1i", "dani", con_resultado=False, estado=None)
    return raiz


def test_lee_la_ultima_revision_de_cada_estudiante(curso):
    revisiones = {r.alumno: r for r in leer_resultados(curso)}
    assert sorted(revisiones) == ["ana", "beto", "caro", "dani"]
    assert revisiones["ana"].directorio.name == "r2i"
    assert [r.alumno for r in leer_resultados(curso / "beto" / "r1i" / "hallazgos.json")] == ["beto"]


def test_calcula_la_nota(curso):
    notas = {r.alumno: calificar(r, PESOS) for r in leer_resultados(curso)}
    assert notas["ana"].nota == 10.0 and not notas["ana"].provisoria

    beto = notas["beto"]
    # tests 1/2, estilo 1 - 0.10 - 0.25, memoria 1 - 0.25 (hallazgo) - 0.25 (fuga), caso_cero aprobado
    assert beto.logros == {"tests_unitarios": 0.5, "estilo_gaff": 0.65, "sanitizers_memoria": 0.5, "test:caso_cero": 1.0}
    assert beto.nota == pytest.approx(10 * (0.5 * 50 + 0.65 * 20 + 0.5 * 20 + 1.0 * 10) / 100, abs=0.01)
    assert [h["codigo"] for h in beto.sin_criterio] == ["X1"]  # recursión: ningún criterio la reclama
    assert any("caso_uno" in d for d in beto.detalle["tests_unitarios"])
    assert any("Fuga de memoria" in d for d in beto.detalle["sanitizers_memoria"])

    assert notas["caro"].nota == 0.0 and "no compila" in notas["caro"].motivo

    dani = notas["dani"]
    assert dani.provisoria and dani.logros["tests_unitarios"] is None and dani.logros["estilo_gaff"] == 1.0
    assert dani.nota == 10.0  # sólo con el criterio que tiene evidencia


def test_un_criterio_con_nombre_de_categoria_reclama_primero():
    rev = Revision("ana", "r1", Path("."), hallazgos=[_hallazgo("gaff", "0x3001h", "memoria", "error")],
                   resultado={"compilacion": True, "tests": {"aprobados": 0, "total": 0, "casos": []}}, estado="completa")
    calif = calificar(rev, {"memoria": 30.0, "sanitizers_memoria": 30.0, "estilo_gaff": 40.0})
    assert calif.logros == {"memoria": 0.75, "sanitizers_memoria": 1.0, "estilo_gaff": 1.0}


def test_criterio_desconocido_y_evaluacion_sin_terminar():
    rev = Revision("ana", "r1", Path("."), resultado={"compilacion": True, "tests": {"aprobados": 1, "total": 1, "casos": []}},
                   estado="en_curso")
    calif = calificar(rev, {"tests_unitarios": 60.0, "defensa_oral": 40.0})
    assert calif.provisoria and calif.logros["defensa_oral"] is None and calif.nota == 10.0
    assert "dredd eval --failed-only" in calif.motivo


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    banco = tmp_path / "banco"
    ej = Ejercicio(id="potencia", titulo="Potencia", tema="funciones", bloom=NivelBloom.APLICAR, minutos=20,
                   tests_funciones=[CasoTestFuncion(nombre="caso_cero", funcion="potencia", args="2, 0", retorno_esperado="1")],
                   tests_ocultos=[CasoTestFuncion(nombre="caso_uno", funcion="potencia", args="2, 1", retorno_esperado="2")],
                   rubrica=PESOS)
    guardar_ejercicio(ej, banco)
    return banco


def test_cli_eval_results(banco, curso, tmp_path):
    salida = tmp_path / "notas"
    res = runner.invoke(app, ["exercise", "rubric", "potencia", "--banco", str(banco), "--eval-results", str(curso),
                              "--salida", str(salida)])
    assert res.exit_code == 0, res.output
    with open(salida / "calificaciones.csv", encoding="utf-8-sig", newline="") as f:
        filas = {f["Usuario"]: f for f in csv.DictReader(f)}
    assert filas["ana"]["Calificación"] == "10.00" and filas["ana"]["Provisoria"] == "no"
    assert filas["caro"]["Calificación"] == "0.00"
    assert filas["dani"]["Provisoria"] == "sí"
    assert "Comentarios de retroalimentación" in filas["beto"]
    devolucion = (salida / "devoluciones" / "beto.md").read_text(encoding="utf-8")
    assert "**Nota:**" in devolucion and "| Prueba caso_cero | 10 % | 100 % |" in devolucion
    assert "## Para repasar" in devolucion and "https://apunte/memoria" in devolucion

    vacio = tmp_path / "vacio"
    vacio.mkdir()
    res = runner.invoke(app, ["exercise", "rubric", "potencia", "--banco", str(banco), "--eval-results", str(vacio)])
    assert res.exit_code == 1


def test_validar_rubrica():
    assert validar_rubrica(PESOS, ["caso_cero"]) == ([], [])
    errores, _ = validar_rubrica({"tests_unitarios": 60, "estilo_gaff": 30}, [])
    assert errores == ["Los pesos suman 90 %, no 100 %."]
    errores, _ = validar_rubrica({"tests_unitarios": 90, "test:caso_dos": 10}, ["caso_cero"])
    assert len(errores) == 1 and "caso_dos" in errores[0] and "caso_cero" in errores[0]
    errores, _ = validar_rubrica({"tests_unitarios": 110, "estilo_gaff": -10}, [])
    assert errores == ["«estilo_gaff»: el peso no puede ser negativo (-10)."]
    _, avisos = validar_rubrica({"tests_unitarios": 50, "defensa_oral": 50}, [])
    assert "defensa_oral" in avisos[0]
    assert validar_rubrica(None, [])[0] == []


def test_cli_verify_rubric(banco):
    res = runner.invoke(app, ["verify", "--rubric", "potencia", "--banco", str(banco)])
    assert res.exit_code == 0, res.output

    yaml_path = banco / "potencia" / "ejercicio.yaml"
    if not yaml_path.is_file():
        yaml_path = next(banco.rglob("ejercicio.yaml"))
    texto = yaml_path.read_text(encoding="utf-8").replace("test:caso_cero", "test:caso_inexistente")
    yaml_path.write_text(texto, encoding="utf-8")
    res = runner.invoke(app, ["verify", "--rubric", "potencia", "--banco", str(banco), "--json"])
    assert res.exit_code == 2, res.output
    datos = json.loads(res.output)
    assert datos["fallidos"] == 1 and "caso_inexistente" in datos["ejercicios"][0]["errores"][0]
