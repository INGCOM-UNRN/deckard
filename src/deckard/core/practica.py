"""Prácticas generadas desde una guía compuesta sobre plantilla-TP (Ola 30).

La guía compuesta (`guias/<guía>/guia.yaml`) es la fuente: los ejercicios del banco, las
librerías (`librerias`: de la cátedra, a crear o reutilizadas de una guía anterior) y los
targets de la corrección (`targets_docente`). De ahí salen:

- el repositorio de la práctica, armado sobre plantilla-TP con su `tp.sh` (así los Makefiles
  son los de la plantilla): `libs/` y `ejercicios/<id del banco>/` con enunciado, cabeceras,
  código inicial, `prueba.c` (p1_test) y los casos públicos; nunca la solución ni los casos
  ocultos;
- del lado del docente, el `dredd.mk` con los targets `dredd-…`, sus fuentes (pruebas ocultas)
  en `.dredd/` y `targets.json`, que describe para dredd qué corre y qué lee de cada uno.

Cada ejercicio de la guía puede declarar `librerias: [cadenas, arreglos]` (lo mismo que
`./tp.sh add-ex ejercicio4 cadenas,arreglos`); p1_test viene siempre con la plantilla.
"""

from __future__ import annotations

import filecmp
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from deckard.core.bank import buscar_ejercicios
from deckard.core.guides import cargar_yaml_guia, resolver_ruta_guia
from deckard.core.models import PLANTILLA_LIBRERIA, Ejercicio, LibreriaGuia, TargetDocente

PLANTILLA_TP = "https://github.com/INGCOM-UNRN-P1/plantilla-TP"
IMPLICITAS = {"p1_test"}  # vienen siempre con la plantilla
NO_SE_COPIAN = {"solucion.c", "ejercicio.yaml"}  # del banco a la práctica


Indice = Dict[str, Tuple[Path, Ejercicio]]


def indice(banco: Path) -> Indice:
    """Los ejercicios del banco por id (se lee una vez: el banco real tiene cientos)."""
    return {ej.id: (Path(d), ej) for d, ej in buscar_ejercicios(banco, recursivo=True)}


class PracticaInvalida(Exception):
    def __init__(self, errores: Sequence[str]):
        super().__init__("\n".join(errores))
        self.errores = list(errores)


@dataclass
class GuiaPractica:
    """La guía compuesta leída para generar la práctica."""

    ruta: Path
    nombre: str
    ejercicios: List[Tuple[str, List[str]]]          # (id, librerías que usa)
    librerias: List[LibreriaGuia] = field(default_factory=list)
    targets: List[TargetDocente] = field(default_factory=list)


def leer_guia(ruta: Path) -> GuiaPractica:
    datos = cargar_yaml_guia(ruta)
    errores: List[str] = []
    ejercicios: List[Tuple[str, List[str]]] = []
    for item in datos.get("ejercicios", []) or []:
        if isinstance(item, str):
            ejercicios.append((item, []))
        elif isinstance(item, dict) and item.get("id"):
            ejercicios.append((str(item["id"]), [str(x) for x in item.get("librerias", []) or []]))
    if not ejercicios:
        errores.append(f"{ruta}: no es una guía compuesta (falta `ejercicios`); compóngala con `deckard guide compose`")
    librerias, targets = [], []
    for n, crudo in enumerate(datos.get("librerias", []) or [], start=1):
        try:
            librerias.append(LibreriaGuia(**crudo))
        except Exception as exc:  # pydantic: se informa en el formato de la guía
            errores.append(f"librerias[{n}]: {_motivo(exc)}")
    for n, crudo in enumerate(datos.get("targets_docente", []) or [], start=1):
        try:
            targets.append(TargetDocente(**crudo))
        except Exception as exc:
            errores.append(f"targets_docente[{n}]: {_motivo(exc)}")
    if errores:
        raise PracticaInvalida(errores)
    nombre = str(datos.get("nombre") or ruta.parent.name)
    return GuiaPractica(ruta, nombre, ejercicios, librerias, targets)


def _motivo(exc: Exception) -> str:
    errores = getattr(exc, "errors", None)
    if callable(errores):
        return "; ".join(str(e.get("msg", "")).removeprefix("Value error, ") for e in errores())
    return str(exc)


# --------------------------------------------------------------------------------- validación


def validar(guia: GuiaPractica, banco: Path, dir_guias: Optional[Path] = None,
            idx: Optional[Indice] = None) -> Tuple[List[str], List[str]]:
    """(errores, avisos) de la guía como fuente de una práctica."""
    idx = indice(banco) if idx is None else idx
    errores: List[str] = []
    avisos: List[str] = []
    nombres = [lib.nombre for lib in guia.librerias]
    repetidas = {n for n in nombres if nombres.count(n) > 1}
    if repetidas:
        errores.append(f"librerías repetidas: {', '.join(sorted(repetidas))}")
    declaradas = set(nombres) | IMPLICITAS
    ids = [eid for eid, _ in guia.ejercicios]
    for eid, usadas in guia.ejercicios:
        if eid not in idx:
            errores.append(f"el ejercicio «{eid}» no está en el banco {banco}")
        for usada in usadas:
            if usada not in declaradas:
                errores.append(f"el ejercicio «{eid}» usa la librería «{usada}», que la guía no declara "
                               "(ni de la cátedra, ni a crear, ni reutilizada)")
    for lib in guia.librerias:
        if lib.origen == "crear" and lib.ejercicio:
            if lib.ejercicio not in idx:
                errores.append(f"la librería «{lib.nombre}» sale del ejercicio «{lib.ejercicio}», que no está en el banco")
            elif idx[lib.ejercicio][1].rol_familia != "libreria":
                avisos.append(f"el ejercicio «{lib.ejercicio}» de la librería «{lib.nombre}» no tiene rol_familia = libreria")
        if lib.origen == "reutilizar":
            errores += _reutilizada_existe(lib, dir_guias or guia.ruta.parent.parent)
    vistos = [t.nombre for t in guia.targets]
    for nombre in {n for n in vistos if vistos.count(n) > 1}:
        errores.append(f"target del docente repetido: {nombre}")
    for t in guia.targets:
        for eid in t.ejercicios:
            if eid not in ids:
                errores.append(f"el target «{t.nombre}» nombra el ejercicio «{eid}», que no está en la guía")
        if t.tipo == "pruebas_ocultas":
            for eid in t.ejercicios or ids:
                ej = idx[eid][1] if eid in idx else None
                if ej is not None and not ej.tests_ocultos:
                    avisos.append(f"el target «{t.nombre}»: el ejercicio «{eid}» no tiene tests_ocultos")
    if sum(t.peso for t in guia.targets) > 100:
        errores.append("los pesos de los targets del docente suman más de 100")
    return errores, avisos


def _reutilizada_existe(lib: LibreriaGuia, dir_guias: Path) -> List[str]:
    try:
        ruta = resolver_ruta_guia(str(lib.guia), dir_guias=dir_guias)
    except Exception:  # noqa: BLE001 - cualquier forma de «no está»
        ruta = None
    if ruta is None or not ruta.is_file():
        return [f"la librería «{lib.nombre}» se reutiliza de la guía «{lib.guia}», que no existe en {dir_guias}"]
    anteriores = cargar_yaml_guia(ruta).get("librerias", []) or []
    if not any(isinstance(x, dict) and x.get("nombre") == lib.nombre and x.get("origen") in ("crear", "reutilizar")
               for x in anteriores):
        return [f"la librería «{lib.nombre}» se reutiliza de «{lib.guia}», pero esa guía no la crea"]
    return []


def catedra_desactualizadas(guia: GuiaPractica,
                            consultar: Callable[[str], Optional[str]] | None = None) -> List[str]:
    """Librerías de la cátedra fijadas a un commit que no es el último de su repositorio."""
    consultar = consultar or _ultimo_commit
    avisos = []
    for lib in guia.librerias:
        if lib.origen != "catedra" or not lib.commit or lib.commit.startswith("v"):
            continue
        ultimo = consultar(str(lib.repositorio))
        if ultimo and ultimo != lib.commit:
            avisos.append(f"«{lib.nombre}» está fijada a {lib.commit[:12]} y {lib.repositorio} ya va por {ultimo[:12]}")
    return avisos


def _ultimo_commit(repositorio: str) -> Optional[str]:
    res = subprocess.run(["git", "ls-remote", repositorio, "HEAD"], capture_output=True, text=True, timeout=60)
    return res.stdout.split()[0] if res.returncode == 0 and res.stdout.strip() else None


# ------------------------------------------------------------------------------------ dredd.mk


def generar_dredd(guia: GuiaPractica, banco: Path,
                  idx: Optional[Indice] = None) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """(dredd.mk, fuentes extra relativas a la raíz de la práctica, targets.json)."""
    from deckard.core.init_tests import generar_suite_tests_c

    idx = indice(banco) if idx is None else idx

    ids = [eid for eid, _ in guia.ejercicios]
    fuentes: Dict[str, str] = {}
    lineas = [
        f"# dredd.mk — generado por deckard desde la guía «{guia.nombre}»: no editar a mano.",
        "# Lo agrega dredd al corregir; los Makefiles de la práctica lo incluyen al final.",
        "DREDD_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))",
        "DREDD_EJERCICIO := $(notdir $(CURDIR))",
        "",
    ]
    for t in guia.targets:
        aplica = t.ejercicios or ids
        lineas += [f"# {t.descripcion}", f".PHONY: {t.target_make}", f"{t.target_make}:",
                   f"ifneq ($(filter $(DREDD_EJERCICIO),{' '.join(aplica)}),)"]
        if t.tipo == "comando":
            lineas += [f"\t{paso}" for paso in t.receta]
        elif t.tipo in ("memcheck", "fallos"):
            lineas.append(f"\t$(MAKE) --no-print-directory {t.tipo}")
        elif t.tipo == "bench":
            lineas.append(f"\tripley check . --bench '{t.cota}' --quiet")
        else:  # pruebas_ocultas: una suite por ejercicio, compilada contra el código del alumno
            for eid in aplica:
                ej = idx[eid][1] if eid in idx else None
                if ej is None or not ej.tests_ocultos:
                    continue
                oculto = ej.model_copy(update={"tests_funciones": ej.tests_ocultos})
                fuentes[f".dredd/ocultas/{eid}.c"] = generar_suite_tests_c(oculto, framework="p1_test")
            lineas += [
                "\t@test -f $(DREDD_DIR)/.dredd/ocultas/$(DREDD_EJERCICIO).c || "
                "{ echo \"sin pruebas ocultas para $(DREDD_EJERCICIO)\"; exit 0; }",
                "\t@mkdir -p .dredd",
                "\t$(CC) $(CFLAGS) $(INCLUDE_DIRS) $(TEST_INCLUDE_DIRS) -I. -o .dredd/ocultas "
                "$(DREDD_DIR)/.dredd/ocultas/$(DREDD_EJERCICIO).c $(SRCS) $(LIBRARY_DIRS) $(TEST_LIBRARY_DIRS) "
                "$(LIBRARY) $(TEST_LIBRARY)",
                "\t./.dredd/ocultas",
            ]
        lineas += ["else", f"\t@echo \"{t.target_make}: no aplica a $(DREDD_EJERCICIO)\"", "endif", ""]
    descripcion = {
        "schema_version": "1.0.0",
        "guia": guia.nombre,
        "ejercicios": ids,
        "targets": [{
            "nombre": t.nombre, "target": t.target_make, "descripcion": t.descripcion, "tipo": t.tipo,
            "ejercicios": t.ejercicios or ids, "produce": t.produce, "archivo": t.archivo,
            "peso": t.peso, "visible": t.visible,
        } for t in guia.targets],
    }
    return "\n".join(lineas), fuentes, descripcion


# ----------------------------------------------------------------------------- la práctica


def _bash(destino: Path, *args: str) -> None:
    res = subprocess.run(["bash", "tp.sh", *args], cwd=destino, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"tp.sh {' '.join(args)} falló: {(res.stderr or res.stdout).strip()[-400:]}")


def _plantilla(origen: str, tmp: Path) -> Path:
    ruta = Path(origen)
    if ruta.is_dir():
        return ruta
    destino = tmp / "plantilla"
    res = subprocess.run(["git", "clone", "--depth", "1", origen, str(destino)], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"no se pudo clonar la plantilla {origen}: {res.stderr.strip()}")
    return destino


def _copiar_base(plantilla: Path, destino: Path) -> None:
    """La plantilla sin sus ejemplos: sin .git, sin ejercicios y sólo las librerías de la cátedra."""
    def ignorar(carpeta: str, nombres: List[str]) -> List[str]:
        actual = Path(carpeta)
        fuera = [n for n in nombres if n in (".git", "build") or n.endswith((".o", ".a")) or n == "test_bin"]
        if actual == plantilla / "ejercicios":
            fuera += nombres
        if actual == plantilla / "libs":
            fuera += [n for n in nombres if not (actual / n / ".catedra").is_file()]
        return fuera
    shutil.copytree(plantilla, destino, ignore=ignorar)
    (destino / "ejercicios").mkdir(exist_ok=True)
    (destino / "libs").mkdir(exist_ok=True)


def _copiar_catedra(lib: LibreriaGuia, destino: Path, tmp: Path) -> None:
    carpeta = destino / "libs" / lib.nombre
    marca = carpeta / ".catedra"
    if marca.is_file() and f'commit = "{lib.commit}"' in marca.read_text(encoding="utf-8"):
        return  # la plantilla ya la trae en ese commit
    clon = tmp / f"catedra-{lib.nombre}"
    for cmd in (["git", "clone", "--quiet", str(lib.repositorio), str(clon)],
                ["git", "-C", str(clon), "checkout", "--quiet", str(lib.commit)]):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"librería de la cátedra «{lib.nombre}»: {res.stderr.strip()}")
    shutil.rmtree(carpeta, ignore_errors=True)
    shutil.copytree(clon, carpeta, ignore=shutil.ignore_patterns(".git", ".github", "build", "tests", "ejemplos", "docs"))
    marca.write_text(f'repositorio = "{lib.repositorio}"\ncommit = "{lib.commit}"\n', encoding="utf-8")


def _copiar_del_banco(dir_ej: Path, destino: Path, ej: Ejercicio, renombrar_h: Optional[str] = None) -> None:
    for archivo in sorted(dir_ej.iterdir()):
        if archivo.name in NO_SE_COPIAN or archivo.name.startswith("."):
            continue
        if archivo.is_dir():
            if archivo.name == "tests":
                shutil.copytree(archivo, destino / "tests", dirs_exist_ok=True)
            continue
        nombre = archivo.name
        if renombrar_h and archivo.suffix == ".h" and archivo.stem == ej.id:
            nombre = f"{renombrar_h}.h"
        shutil.copy2(archivo, destino / nombre)
    if ej.starter_code.strip() and not (dir_ej / "main.c").is_file():
        (destino / "main.c").write_text(ej.starter_code, encoding="utf-8")
    if not (dir_ej / "prueba.c").is_file() and ej.tests_funciones:
        from deckard.core.init_tests import generar_suite_tests_c
        (destino / "prueba.c").write_text(generar_suite_tests_c(ej, framework="p1_test"), encoding="utf-8")


def _leeme(guia: GuiaPractica) -> str:
    partes = [f"# {guia.nombre}", "",
              "Práctica generada por deckard desde su guía: los ejercicios y las librerías salen del banco",
              "de la cátedra. `make test` corre las pruebas; `./tp.sh` agrega librerías o ejercicios.", "",
              "## Ejercicios", ""]
    partes += [f"- `ejercicios/{eid}/`" + (f" (usa {', '.join(libs)})" if libs else "") for eid, libs in guia.ejercicios]
    if guia.librerias:
        partes += ["", "## Librerías", ""]
        for lib in guia.librerias:
            como = {"catedra": "de la cátedra, no se edita",
                    "crear": f"la escribís en esta práctica ({lib.forma})",
                    "reutilizar": f"la escribiste en «{lib.guia}»: traela con "
                                  f"`./tp.sh add-lib {lib.nombre} <url de tu repositorio>` o copiá su carpeta a `libs/`"}
            partes.append(f"- `{lib.nombre}`: {como[lib.origen]}" + (f". {lib.descripcion}" if lib.descripcion else ""))
    visibles = [t for t in guia.targets if t.visible]
    if visibles:
        partes += ["", "## Lo que se revisa al corregir", ""]
        partes += [f"- {t.descripcion}" for t in visibles]
    return "\n".join(partes) + "\n"


def armar_practica(guia: GuiaPractica, banco: Path, plantilla: str, destino: Path,
                   idx: Optional[Indice] = None) -> None:
    """Arma la práctica en `destino` (que no tiene que existir)."""
    idx = indice(banco) if idx is None else idx
    with tempfile.TemporaryDirectory() as tmp_txt:
        tmp = Path(tmp_txt)
        _copiar_base(_plantilla(plantilla, tmp), destino)
        for lib in guia.librerias:
            if lib.origen == "catedra":
                _copiar_catedra(lib, destino, tmp)
            elif lib.origen == "crear":
                if lib.forma == "estructurada":
                    _bash(destino, "add-lib", lib.nombre, lib.repositorio or PLANTILLA_LIBRERIA)
                else:
                    _bash(destino, "add-lib", lib.nombre)
                if lib.ejercicio and lib.ejercicio in idx:
                    dir_ej, ej = idx[lib.ejercicio]
                    _copiar_del_banco(dir_ej, destino / "libs" / lib.nombre, ej, renombrar_h=lib.nombre)
        for eid, usadas in guia.ejercicios:
            _bash(destino, "add-ex", eid, *([",".join(usadas)] if usadas else []))
            dir_ej, ej = idx[eid]
            _copiar_del_banco(dir_ej, destino / "ejercicios" / eid, ej)
        (destino / "PRACTICA.md").write_text(_leeme(guia), encoding="utf-8")


def escribir_dredd(guia: GuiaPractica, banco: Path, salida: Path, idx: Optional[Indice] = None) -> List[Path]:
    """Lo del docente: dredd.mk, .dredd/ (pruebas ocultas) y targets.json, fuera de la práctica."""
    mk, fuentes, descripcion = generar_dredd(guia, banco, idx)
    salida.mkdir(parents=True, exist_ok=True)
    escritos = [salida / "dredd.mk", salida / "targets.json"]
    escritos[0].write_text(mk, encoding="utf-8")
    escritos[1].write_text(json.dumps(descripcion, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for rel, texto in fuentes.items():
        (salida / rel).parent.mkdir(parents=True, exist_ok=True)
        (salida / rel).write_text(texto, encoding="utf-8")
        escritos.append(salida / rel)
    return escritos


@dataclass
class Diferencias:
    agregados: List[str] = field(default_factory=list)
    cambiados: List[str] = field(default_factory=list)
    quitados: List[str] = field(default_factory=list)

    @property
    def vacias(self) -> bool:
        return not (self.agregados or self.cambiados or self.quitados)


def comparar(nueva: Path, existente: Path) -> Diferencias:
    """Qué cambiaría en `existente` si se reemplazara por `nueva` (sin .git ni compilados)."""
    def archivos(raiz: Path) -> Dict[str, Path]:
        return {p.relative_to(raiz).as_posix(): p for p in raiz.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(raiz).parts
                and p.suffix not in (".o", ".a") and p.name != "test_bin" and "build" not in p.relative_to(raiz).parts}
    a, b = archivos(nueva), archivos(existente)
    return Diferencias(
        agregados=sorted(set(a) - set(b)),
        cambiados=sorted(k for k in set(a) & set(b) if not filecmp.cmp(a[k], b[k], shallow=False)),
        quitados=sorted(set(b) - set(a)),
    )


def aplicar(nueva: Path, existente: Path, dif: Diferencias) -> None:
    """Copia lo agregado y lo cambiado; lo quitado se informa pero no se borra."""
    for rel in dif.agregados + dif.cambiados:
        (existente / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nueva / rel, existente / rel)
