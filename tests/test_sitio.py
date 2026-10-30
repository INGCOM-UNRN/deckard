"""Pruebas del sitio MyST del banco (`deckard export myst`): páginas, guías, TOC, .ripkg y catálogo."""

import json
from pathlib import Path
import zipfile

import pytest
import yaml
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import guardar_ejercicio
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.sitio import SitioError, cargar_temario, construir_sitio, slug_guia
from deckard.core.trazabilidad import MARCA_FIN, MARCA_INICIO, slug_myst, slugs_de_toc

runner = CliRunner()


def _ejercicio(banco: Path, eid: str, tema: str, bloom: NivelBloom, **extra) -> Path:
    ej = Ejercicio(
        id=eid,
        titulo=eid.replace("-", " ").title(),
        tema=tema,
        bloom=bloom,
        minutos_estimados=20,
        enunciado_md=f"Consigna de {eid}.",
        solucion_c="int main(void) { return 0; }\n",
        pistas=["Primera pista."],
        **extra,
    )
    return guardar_ejercicio(ej, banco / tema)


@pytest.fixture()
def repo(tmp_path) -> Path:
    """Repositorio de enunciados mínimo: banco/<tema>/<id>, guías, temas.yaml y myst.yml."""
    banco = tmp_path / "banco"
    _ejercicio(banco, "sumar", "aritmetica", NivelBloom.APLICAR, tags=["dep:sintaxis"])
    dir_contar = _ejercicio(banco, "contar", "lazos", NivelBloom.COMPRENDER)
    (dir_contar / "tests" / "hidden").mkdir(parents=True)
    (dir_contar / "tests" / "caso_01.in").write_text("3\n", encoding="utf-8")
    (dir_contar / "tests" / "caso_01.out").write_text("1 2 3\n", encoding="utf-8")
    (dir_contar / "tests" / "hidden" / "secreto.in").write_text("99\n", encoding="utf-8")
    _ejercicio(banco, "prototipo-arbol", "arboles", NivelBloom.ANALIZAR, publicar=False)

    guias = tmp_path / "guias"
    (guias / "guía_1_—_lazos").mkdir(parents=True)
    (guias / "guía_1_—_lazos" / "guia.yaml").write_text(yaml.safe_dump(
        {"nombre": "Guía 1 — Lazos", "ejercicios": [{"id": "contar"}, {"id": "sumar"}, {"id": "prototipo-arbol"}]},
        allow_unicode=True), encoding="utf-8")
    (guias / "spec.yaml").write_text(yaml.safe_dump({"nombre": "Spec", "duracion_min": 60}), encoding="utf-8")
    (guias / "vacia.yaml").write_text(yaml.safe_dump({"nombre": "Vacía", "ejercicios": ["no-existe"]}), encoding="utf-8")

    (tmp_path / "temas.yaml").write_text(yaml.safe_dump({
        "temas": {
            "sintaxis": {"titulo": "Sintaxis", "requiere": []},
            "aritmetica": {"titulo": "Aritmética", "requiere": ["sintaxis"]},
            "lazos": {"titulo": "Lazos", "requiere": ["aritmetica"]},
        },
        "unidades": [{"id": "unidad_1", "titulo": "Unidad 1", "temas": ["sintaxis", "aritmetica", "lazos"]}],
    }, allow_unicode=True), encoding="utf-8")
    (tmp_path / "myst.yml").write_text(
        "version: 1\nproject:\n  title: Banco\n"
        "  # deckard export myst: inicio (lo de abajo es generado)\n"
        "  # deckard export myst: fin\n"
        "site:\n  template: book-theme  # tema del sitio\n",
        encoding="utf-8")
    return tmp_path


def _construir(repo: Path, **kw):
    return construir_sitio(
        banco=repo / "banco",
        salida=repo / "sitio",
        dir_guias=repo / "guias",
        temas=repo / "temas.yaml",
        myst_yml=repo / "myst.yml",
        **kw,
    )


def test_genera_paginas_de_publicables_y_omite_no_publicados(repo):
    res = _construir(repo)
    sitio = repo / "sitio"

    assert res.ejercicios == 2 and res.no_publicados == 1 and not res.invalidos
    assert (sitio / "consignas" / "aritmetica" / "sumar.md").is_file()
    assert not (sitio / "consignas" / "arboles").exists()
    pagina = (sitio / "consignas" / "lazos" / "contar.md").read_text(encoding="utf-8")
    assert "Consigna de contar." in pagina
    assert "(../../paquetes/contar.ripkg)" in pagina
    assert "Solución Modelo" in pagina
    assert "Aritmética" in (sitio / "index.md").read_text(encoding="utf-8")
    assert "sintaxis --> aritmetica" in (sitio / "grafo_tematico.md").read_text(encoding="utf-8")


def test_sin_soluciones(repo):
    _construir(repo, incluir_soluciones=False)
    assert "Solución Modelo" not in (repo / "sitio" / "consignas" / "lazos" / "contar.md").read_text(encoding="utf-8")


def test_guias_publicables_con_enlaces_a_paquetes(repo):
    res = _construir(repo)

    assert [g.slug for g in res.guias] == ["guia-1-lazos"]
    assert res.guias[0].faltantes == ["prototipo-arbol"]
    assert [g.slug for g in res.guias_vacias] == ["vacia"]
    guia = (repo / "sitio" / "guias" / "guia-1-lazos.md").read_text(encoding="utf-8")
    assert "# Guía 1 — Lazos" in guia
    assert "(../paquetes/contar.ripkg)" in guia
    assert "Consigna de prototipo-arbol" not in guia
    assert not (repo / "sitio" / "guias" / "vacia.md").exists()


def test_paquetes_sin_pruebas_ocultas_y_catalogo(repo):
    _construir(repo)
    paquetes = repo / "sitio" / "paquetes"

    assert sorted(p.name for p in paquetes.glob("*.ripkg")) == ["contar.ripkg", "sumar.ripkg"]
    with zipfile.ZipFile(paquetes / "contar.ripkg") as zf:
        nombres = zf.namelist()
    assert "payload/caso_01.in" in nombres
    assert not any("secreto" in n for n in nombres)

    catalogo = json.loads((paquetes / "catalogo.json").read_text(encoding="utf-8"))
    assert catalogo["formato"] == 1
    assert catalogo["totales"]["ejercicios"] == 2
    por_id = {e["id"]: e for e in catalogo["ejercicios"]}
    assert set(por_id) == {"contar", "sumar"}
    assert por_id["sumar"]["tema_titulo"] == "Aritmética"
    assert por_id["sumar"]["unidad"] == "unidad_1"
    assert por_id["sumar"]["origen"] == "aritmetica/sumar"
    assert por_id["contar"]["ripkg"]["archivo"] == "contar.ripkg"
    assert len(por_id["contar"]["ripkg"]["sha256"]) == 64
    assert catalogo["guias"] == [{
        "id": "guia-1-lazos",
        "nombre": "Guía 1 — Lazos",
        "minutos_totales": 40,
        "distribucion_bloom": {},
        "pagina": "guias/guia-1-lazos.md",
        "ejercicios": ["contar", "sumar"],
        "faltantes": ["prototipo-arbol"],
    }]


def test_toc_de_myst_por_tema_y_por_unidad(repo):
    _construir(repo)
    config = yaml.safe_load((repo / "myst.yml").read_text(encoding="utf-8"))
    toc = config["project"]["toc"]
    assert config["site"]["template"] == "book-theme"
    assert toc[0] == {"file": "sitio/index.md"}
    assert toc[2] == {"title": "Guías", "children": [{"file": "sitio/guias/guia-1-lazos.md"}]}
    assert {"title": "Lazos", "file": "sitio/consignas/lazos/tema-lazos.md",
            "children": [{"file": "sitio/consignas/lazos/contar.md"}]} in toc

    _construir(repo, agrupar_por_unidad=True)
    toc = yaml.safe_load((repo / "myst.yml").read_text(encoding="utf-8"))["project"]["toc"]
    assert toc[3]["title"] == "Unidad 1"
    assert [s["title"] for s in toc[3]["children"]] == ["Aritmética", "Lazos"]


def test_toc_entre_las_marcas_conserva_el_resto(repo):
    _construir(repo)
    _construir(repo)  # idempotente: reemplaza lo generado, no lo duplica
    texto = (repo / "myst.yml").read_text(encoding="utf-8")
    assert texto.count("toc:") == 1
    assert "  # deckard export myst: inicio (lo de abajo es generado)\n  toc:\n  - file: sitio/index.md\n" in texto
    assert texto.endswith("  # deckard export myst: fin\nsite:\n  template: book-theme  # tema del sitio\n")


def test_myst_yml_sin_marcas_se_rechaza(repo):
    (repo / "myst.yml").write_text("version: 1\nproject:\n  title: Banco\n", encoding="utf-8")
    with pytest.raises(SitioError, match="deckard export myst: inicio"):
        _construir(repo)


def test_regenera_desde_cero(repo):
    (repo / "sitio" / "consignas" / "borrado").mkdir(parents=True)
    _construir(repo)
    assert not (repo / "sitio" / "consignas" / "borrado").exists()


def test_salida_que_contiene_las_fuentes_se_rechaza(repo):
    with pytest.raises(SitioError):
        construir_sitio(banco=repo / "banco", salida=repo, dir_guias=repo / "guias")
    assert (repo / "banco").is_dir()


def test_ejercicio_invalido_se_informa(repo):
    roto = repo / "banco" / "lazos" / "roto"
    roto.mkdir()
    (roto / "ejercicio.yaml").write_text("id: roto\ntitulo: Roto\ntema: lazos\nbloom: 9\nminutos: 10\n", encoding="utf-8")
    res = _construir(repo)
    assert [d.name for d, _ in res.invalidos] == ["roto"]
    assert res.ejercicios == 2


def test_temario_con_requisito_desconocido(tmp_path):
    ruta = tmp_path / "temas.yaml"
    ruta.write_text(yaml.safe_dump({"temas": {"lazos": {"requiere": ["fantasma"]}}}), encoding="utf-8")
    with pytest.raises(SitioError, match="fantasma"):
        cargar_temario(ruta)
    assert cargar_temario(tmp_path / "no-existe.yaml").titulo("memoria_dinamica") == "Memoria dinamica"


def test_tipo_laboratorio_es_valido(tmp_path):
    dir_ej = _ejercicio(tmp_path, "lab", "testing", NivelBloom.APLICAR, tipo="laboratorio")
    assert "tipo: laboratorio" in (dir_ej / "ejercicio.yaml").read_text(encoding="utf-8")


def test_slug_guia():
    assert slug_guia("guía_1_—_arreglos") == "guia-1-arreglos"
    assert slug_guia("entrega-3_1238305") == "entrega-3-1238305"


def test_publicar_true_no_se_escribe_en_el_yaml(tmp_path):
    dir_ej = _ejercicio(tmp_path, "a", "lazos", NivelBloom.RECORDAR)
    assert "publicar" not in (dir_ej / "ejercicio.yaml").read_text(encoding="utf-8")
    dir_ej = _ejercicio(tmp_path, "b", "lazos", NivelBloom.RECORDAR, publicar=False)
    assert "publicar: false" in (dir_ej / "ejercicio.yaml").read_text(encoding="utf-8")


def test_cli_export_myst(repo, monkeypatch):
    monkeypatch.chdir(repo)
    res = runner.invoke(app, ["export", "myst"])
    assert res.exit_code == 0, res.output
    assert "2 ejercicios" in res.output
    assert (repo / "sitio" / "paquetes" / "catalogo.json").is_file()

    roto = repo / "banco" / "lazos" / "roto"
    roto.mkdir()
    (roto / "ejercicio.yaml").write_text("id: roto\n", encoding="utf-8")
    assert runner.invoke(app, ["export", "myst"]).exit_code == 1
    assert runner.invoke(app, ["export", "myst", "--permitir-invalidos"]).exit_code == 0


def test_contrato_desplegable_y_no_se_envuelve_dos_veces():
    from deckard.core.export_plantillas import desplegar_contratos

    md = "Consigna.\n\n### 📋 Contrato de las Funciones\n\n```c\nint f(void);\n```\n\n### 🧪 Ejemplos\n\nx\n"
    salida = desplegar_contratos(md)
    assert "### 📋 Contrato de las Funciones\n\n::::{dropdown} Ver el contrato de las funciones\n```c\nint f(void);\n```\n::::" in salida
    assert salida.endswith("### 🧪 Ejemplos\n\nx\n")
    assert desplegar_contratos(salida) == salida
    assert desplegar_contratos("Sin contrato.") == "Sin contrato."


def test_pagina_escalonada_pistas_antes_de_prototipos_desplegables(repo):
    from deckard.core.models import FuncionSpec

    dir_ej = repo / "banco" / "lazos" / "contar"
    datos = yaml.safe_load((dir_ej / "ejercicio.yaml").read_text(encoding="utf-8"))
    datos["funciones"] = [FuncionSpec.parse("int contar(int n)").model_dump(), FuncionSpec.parse("void listar(int n)").model_dump()]
    (dir_ej / "ejercicio.yaml").write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
    (dir_ej / "contar.h").write_text("int contar(int n);\nvoid listar(int n);\n", encoding="utf-8")
    _construir(repo)
    pagina = (repo / "sitio" / "consignas" / "lazos" / "contar.md").read_text(encoding="utf-8")

    assert "Pistas Progresivas" not in pagina
    assert pagina.index("## 💡 Pistas") < pagina.index("## ⚙️ Especificación") < pagina.index("## 📋 Prototipos")
    assert "::::{dropdown} Ver la especificación de las funciones" in pagina
    assert "::::{dropdown} Ver los prototipos\n\n```c\nint contar(int n);" in pagina
    # filas de la tabla seguidas, sin líneas en blanco que la corten
    assert "| :--- | :--- | :--- | :--- |\n| `contar` | `int` | `int n` |" in pagina
    assert "|\n| `listar`" in pagina


# ---------------------------------------------------------------------------
# Trazabilidad con el apunte (Ola 34)
# ---------------------------------------------------------------------------

APUNTE = "https://apunte.example"
ENUNCIADOS = "https://apunte.example/enunciados"


@pytest.fixture()
def repo_apunte(repo) -> Path:
    """El repo de enunciados con `apunte` por tema y `sitios`, más un apunte con dos páginas."""
    temas = yaml.safe_load((repo / "temas.yaml").read_text(encoding="utf-8"))
    temas["temas"]["lazos"]["apunte"] = ["apunte/bloque_1/3_control_flujo.md"]
    temas["temas"]["aritmetica"]["apunte"] = "apunte/bloque_1/1_base.md#operadores"
    temas["sitios"] = {"apunte": APUNTE, "enunciados": ENUNCIADOS}
    (repo / "temas.yaml").write_text(yaml.safe_dump(temas, allow_unicode=True), encoding="utf-8")

    apunte = repo / "apunte_repo"
    (apunte / "apunte" / "bloque_1").mkdir(parents=True)
    (apunte / "apunte" / "bloque_1" / "1_base.md").write_text("# Base\n\nTexto.\n", encoding="utf-8")
    (apunte / "apunte" / "bloque_1" / "3_control_flujo.md").write_text("# Control\n\nTexto.\n", encoding="utf-8")
    (apunte / "myst.yml").write_text(yaml.safe_dump({"version": 1, "project": {"toc": [
        {"file": "readme.md"},
        {"file": "apunte/bloque_1/1_base.md"},
        {"file": "apunte/bloque_1/3_control_flujo.md"},
    ]}}), encoding="utf-8")
    return repo


def test_slug_myst_como_lo_arma_myst():
    assert slug_myst("apunte/bloque_2_memoria/2_punteros.md") == "punteros"
    assert slug_myst("apunte/bloque_3/1A_matrices_dinamicas.md") == "a-matrices-dinamicas"
    assert slug_myst("consignas/cadenas/ej-11-35-b35-convertir-a-snake_case.md") == "ej-11-35-b35-convertir-a-snake-case"
    assert slugs_de_toc(["a/1D_frag.md", "b/6D_frag.md"]) == {"a/1D_frag.md": "d-frag", "b/6D_frag.md": "d-frag-1"}


def test_temas_y_ejercicios_enlazan_al_apunte(repo_apunte):
    _construir(repo_apunte, dir_apunte=repo_apunte / "apunte_repo")
    sitio = repo_apunte / "sitio"

    tema = (sitio / "consignas" / "lazos" / "tema-lazos.md").read_text(encoding="utf-8")
    assert tema.startswith("# Lazos")
    assert f"]({APUNTE}/control-flujo)" in tema
    assert "[Aritmética](../aritmetica/tema-aritmetica.md)" in tema  # prerrequisito
    assert "[Contar](contar.md)" in tema

    ejercicio = (sitio / "consignas" / "aritmetica" / "sumar.md").read_text(encoding="utf-8")
    assert ":::{seealso}" in ejercicio
    assert "(tema-aritmetica.md)" in ejercicio
    assert f"]({APUNTE}/base#operadores)" in ejercicio
    assert "[Lazos](consignas/lazos/tema-lazos.md)" in (sitio / "index.md").read_text(encoding="utf-8")


def test_catalogo_con_temas_y_urls(repo_apunte):
    _construir(repo_apunte)
    catalogo = json.loads((repo_apunte / "sitio" / "paquetes" / "catalogo.json").read_text(encoding="utf-8"))
    sumar = next(e for e in catalogo["ejercicios"] if e["id"] == "sumar")
    assert sumar["url"] == f"{ENUNCIADOS}/sumar"
    assert sumar["apunte"] == [f"{APUNTE}/base#operadores"]
    lazos = next(t for t in catalogo["temas"] if t["id"] == "lazos")
    assert lazos["url"] == f"{ENUNCIADOS}/tema-lazos"
    assert lazos["apunte"] == [{"ruta": "apunte/bloque_1/3_control_flujo.md", "url": f"{APUNTE}/control-flujo"}]
    assert lazos["ejercicios"] == ["contar"]


def test_export_apunte_escribe_y_verifica_bloques(repo_apunte):
    apunte = repo_apunte / "apunte_repo"
    base = ["export", "apunte", str(apunte), "--banco", str(repo_apunte / "banco")]

    res = runner.invoke(app, [*base, "--verificar"])
    assert res.exit_code == 1 and "desactualizado" in res.stdout

    res = runner.invoke(app, base)
    assert res.exit_code == 0, res.stdout
    control = (apunte / "apunte" / "bloque_1" / "3_control_flujo.md").read_text(encoding="utf-8")
    assert control.startswith("# Control\n\nTexto.\n\n" + MARCA_INICIO)
    assert ":::{seealso} Ejercicios para practicar" in control
    assert f"[Lazos]({ENUNCIADOS}/tema-lazos)" in control
    assert f"[Contar]({ENUNCIADOS}/contar) · B2 · ~20 min" in control
    assert control.rstrip().endswith(MARCA_FIN)

    assert runner.invoke(app, base).exit_code == 0  # idempotente
    assert (apunte / "apunte" / "bloque_1" / "3_control_flujo.md").read_text(encoding="utf-8") == control
    assert runner.invoke(app, [*base, "--verificar"]).exit_code == 0

    # un tema deja de apuntar a esa página: el bloque se quita
    temas = yaml.safe_load((repo_apunte / "temas.yaml").read_text(encoding="utf-8"))
    temas["temas"]["lazos"]["apunte"] = []
    (repo_apunte / "temas.yaml").write_text(yaml.safe_dump(temas, allow_unicode=True), encoding="utf-8")
    res = runner.invoke(app, base)
    assert res.exit_code == 0 and "lazos" in res.stdout  # avisa: tema con ejercicios y sin apunte
    assert MARCA_INICIO not in (apunte / "apunte" / "bloque_1" / "3_control_flujo.md").read_text(encoding="utf-8")


def test_export_apunte_sin_url_de_enunciados(repo):
    (repo / "apunte_repo").mkdir()
    res = runner.invoke(app, ["export", "apunte", str(repo / "apunte_repo"), "--banco", str(repo / "banco")])
    assert res.exit_code == 1 and "sitios.enunciados" in res.stdout
