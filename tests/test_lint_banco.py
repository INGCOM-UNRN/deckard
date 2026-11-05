"""Pruebas de `deckard lint` sobre el banco: reglas de ejercicios, guías y trazabilidad con el apunte."""

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import guardar_ejercicio
from deckard.core.lint_banco import ERROR, revisar_banco
from deckard.core.models import Ejercicio, NivelBloom

runner = CliRunner()


def _ej(banco: Path, eid: str, tema: str, carpeta: str | None = None, pruebas: bool = True, **extra) -> Path:
    ej = Ejercicio(id=eid, titulo=eid.title(), tema=tema, bloom=NivelBloom.APLICAR, minutos_estimados=20,
                   enunciado_md=f"Consigna de {eid}.", solucion_c="int main(void) { return 0; }\n", **extra)
    dir_ej = guardar_ejercicio(ej, banco / (carpeta or tema))
    if pruebas:
        (dir_ej / "tests").mkdir(exist_ok=True)
        (dir_ej / "tests" / "caso.in").write_text("1\n", encoding="utf-8")
    return dir_ej


@pytest.fixture()
def repo(tmp_path) -> Path:
    banco = tmp_path / "banco"
    _ej(banco, "sumar", "aritmetica")
    _ej(banco, "contar", "lazos", tags=["dep:aritmetica"])
    (tmp_path / "temas.yaml").write_text(yaml.safe_dump({
        "sitios": {"apunte": "https://a.example", "enunciados": "https://a.example/enunciados"},
        "temas": {
            "aritmetica": {"titulo": "Aritmética", "requiere": [], "apunte": ["apunte/1_base.md"]},
            "lazos": {"titulo": "Lazos", "requiere": ["aritmetica"], "apunte": ["apunte/2_lazos.md"]},
        },
    }), encoding="utf-8")
    (tmp_path / "guias" / "g1").mkdir(parents=True)
    (tmp_path / "guias" / "g1" / "guia.yaml").write_text(yaml.safe_dump({"nombre": "G1", "ejercicios": ["sumar"]}),
                                                         encoding="utf-8")
    apunte = tmp_path / "apunte_repo" / "apunte"
    apunte.mkdir(parents=True)
    (apunte / "1_base.md").write_text("# Base\n", encoding="utf-8")
    (apunte / "2_lazos.md").write_text("# Lazos\n", encoding="utf-8")
    (tmp_path / "apunte_repo" / "myst.yml").write_text(yaml.safe_dump({"project": {"toc": [
        {"file": "apunte/1_base.md"}, {"file": "apunte/2_lazos.md"}]}}), encoding="utf-8")
    return tmp_path


def _reglas(res) -> dict:
    return {(h.regla, h.nivel) for h in res.hallazgos}


def _revisar(repo: Path, **kw):
    return revisar_banco(repo / "banco", temas=repo / "temas.yaml", dir_guias=repo / "guias",
                         dir_apunte=repo / "apunte_repo", **kw)


def test_banco_conforme_salvo_el_apunte_sin_bloques(repo):
    res = _revisar(repo)
    assert res.ejercicios == 2 and not res.errores
    assert _reglas(res) == {("apunte-desactualizado", "aviso")}
    assert runner.invoke(app, ["export", "apunte", str(repo / "apunte_repo"), "--banco", str(repo / "banco")]).exit_code == 0
    assert _revisar(repo).hallazgos == []


def test_reglas_de_ejercicio(repo):
    banco = repo / "banco"
    _ej(banco, "huerfano", "inventado", tags=["dep:nada"])
    _ej(banco, "prototipo", "otro_inventado", publicar=False)
    _ej(banco, "mal-ubicado", "lazos", carpeta="aritmetica")
    copia = banco / "lazos" / "contar-copia"
    copia.mkdir()
    (copia / "ejercicio.yaml").write_text((banco / "lazos" / "contar" / "ejercicio.yaml").read_text(encoding="utf-8"),
                                          encoding="utf-8")
    roto = banco / "lazos" / "roto"
    roto.mkdir()
    (roto / "ejercicio.yaml").write_text("id: roto\ntitulo: Roto\ntema: lazos\nbloom: 3\nminutos_estimados: 20\n"
                                         "tipo: ejercicio_individual\n", encoding="utf-8")
    reglas = _reglas(_revisar(repo))
    assert {("tema-desconocido", "error"), ("dep-desconocida", "error"), ("tema-desconocido", "aviso"),
            ("tema-carpeta", "aviso"), ("id-repetido", "error"), ("yaml-invalido", "error")} <= reglas
    invalido = next(h for h in _revisar(repo).hallazgos if h.regla == "yaml-invalido")
    assert "ejercicio_individual" in invalido.mensaje


def test_reglas_de_guias_y_apunte(repo):
    (repo / "guias" / "g1" / "guia.yaml").write_text(yaml.safe_dump({"nombre": "G1", "ejercicios": [
        "sumar", "no-existe", "proto"]}), encoding="utf-8")
    _ej(repo / "banco", "proto", "lazos", publicar=False)
    temas = yaml.safe_load((repo / "temas.yaml").read_text(encoding="utf-8"))
    temas["temas"]["aritmetica"]["apunte"] = ["apunte/9_no_existe.md"]
    temas["temas"]["lazos"]["apunte"] = []
    (repo / "temas.yaml").write_text(yaml.safe_dump(temas), encoding="utf-8")
    (repo / "apunte_repo" / "apunte" / "fuera.md").write_text("# Fuera\n", encoding="utf-8")
    temas["temas"]["lazos"]["apunte"] = ["apunte/fuera.md"]
    (repo / "temas.yaml").write_text(yaml.safe_dump(temas), encoding="utf-8")

    res = _revisar(repo)
    mensajes = {h.regla: h.mensaje for h in res.hallazgos}
    assert "no-existe, que no está en el banco" in mensajes["guia-faltante"]
    assert "proto" in mensajes["guia-no-publicado"]
    assert "9_no_existe.md" in mensajes["apunte-inexistente"]
    assert "fuera.md" in mensajes["apunte-fuera-del-toc"]


def test_patron_revisa_solo_esos_ejercicios(repo):
    _ej(repo / "banco", "huerfano", "inventado")
    res = _revisar(repo, patron="sumar")
    assert res.ejercicios == 1 and res.hallazgos == []


def test_cli_lint_json_y_codigo_de_salida(repo):
    base = ["lint", "--banco", str(repo / "banco")]
    res = runner.invoke(app, [*base, "--json"])
    assert res.exit_code == 0
    datos = json.loads(res.stdout)
    assert datos["errores"] == 0 and datos["ejercicios"] == 2
    assert runner.invoke(app, [*base, "--apunte", str(repo / "apunte_repo"), "--estricto"]).exit_code == 1

    _ej(repo / "banco", "huerfano", "inventado")
    res = runner.invoke(app, base)
    assert res.exit_code == 1 and "tema-desconocido" in res.stdout and "1 error(es)" in res.stdout
    assert all(h["nivel"] in (ERROR, "aviso") for h in json.loads(runner.invoke(app, [*base, "--json"]).stdout)["hallazgos"])


def test_firmas_y_pruebas(repo):
    from deckard.core.models import FuncionSpec

    _ej(repo / "banco", "firma-rota", "lazos", pruebas=False,
        funciones=[FuncionSpec(nombre="contar_pares", retorno="int", parametros="const int v[], size_t n")])
    hallazgos = {(h.regla, h.donde) for h in _revisar(repo).hallazgos}
    assert ("firmas", "lazos/firma-rota") in hallazgos
    assert ("sin-pruebas", "lazos/firma-rota") in hallazgos  # ni tests/*.in ni tests_funciones


def test_verificar_soluciones_con_ripley(repo, tmp_path):
    ripley = tmp_path / "ripley_falso.py"
    ripley.write_text("import json, sys\nok = 'sumar' not in sys.argv[2]\n"
                      "print(json.dumps({'ok': ok, 'summary': 'falla el caso 2'}))\nsys.exit(0 if ok else 1)\n",
                      encoding="utf-8")
    # con casos de E/S (los tiene el fixture), verify delega en ripley check
    res = _revisar(repo, verificar_soluciones=True, ruta_ripley=f"python3 {ripley}")
    solucion = [h for h in res.hallazgos if h.regla == "solucion"]
    assert [(h.donde, h.mensaje) for h in solucion] == [("aritmetica/sumar", "falla el caso 2")]


def test_diagrama_sin_svg(repo):
    from deckard.core.diagramas_sitio import nombre_svg

    from deckard.core.bank import cargar_ejercicio

    dir_ej = _ej(repo / "banco", "pila", "lazos")
    ej = cargar_ejercicio(dir_ej)
    ej.enunciado_md = "Mirá:\n\n```estructura\ntype: stack\nvalues: [1]\n```\n"
    guardar_ejercicio(ej, repo / "banco" / "lazos")
    (falta,) = [h for h in _revisar(repo).hallazgos if h.regla == "diagrama-sin-svg"]
    assert falta.nivel == ERROR and "alucard diagramas-md" in falta.mensaje
    (dir_ej / "diagramas").mkdir()
    (dir_ej / "diagramas" / nombre_svg("type: stack\nvalues: [1]")).write_text("<svg/>", encoding="utf-8")
    assert not [h for h in _revisar(repo).hallazgos if h.regla == "diagrama-sin-svg"]


def test_lint_avisa_la_solucion_de_relleno(tmp_path):
    banco = tmp_path / "banco"
    dir_ej = _ej(banco, "con-relleno", "funciones")
    (dir_ej / "solucion.c").write_text("int ejecutar_x(int val)\n{\n    if (val <= 0) return 0;\n    return val * 2;\n}\n",
                                       encoding="utf-8")
    hallazgos = [h for h in revisar_banco(banco).hallazgos if h.regla == "solucion-relleno"]
    assert len(hallazgos) == 1 and "ejecutar_x" in hallazgos[0].mensaje and hallazgos[0].nivel != ERROR
