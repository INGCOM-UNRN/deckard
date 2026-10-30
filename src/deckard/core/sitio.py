"""Sitio MyST del banco: páginas de ejercicios y guías, portada, grafo temático, TOC, .ripkg y catálogo JSON.

Reemplaza a `gestionar_consignas.py` del repositorio de enunciados. Todo lo que escribe es
generado (lo produce el CI): el banco y las guías son la única fuente. El contenido propio
de la cátedra (títulos de los temas, unidades, grafo de prerrequisitos y rutas) vive en el
`temas.yaml` del repositorio de enunciados, no acá.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from deckard.core.bank import ARCHIVO_EJERCICIO, cargar_ejercicio
from deckard.core.export import renderizar_ejercicio_md, renderizar_guia_md
from deckard.core.guides import cargar_yaml_guia
from deckard.core.models import Ejercicio

ARCHIVO_TEMAS = "temas.yaml"
ARCHIVO_CATALOGO = "catalogo.json"
FORMATO_CATALOGO = 1

DIR_CONSIGNAS = "consignas"
DIR_GUIAS = "guias"
DIR_PAQUETES = "paquetes"

BLOOM_NOMBRES: Dict[int, str] = {
    1: "Recordar",
    2: "Comprender",
    3: "Aplicar",
    4: "Analizar",
    5: "Evaluar / Crear",
}


class SitioError(Exception):
    """Configuración del sitio inválida (salida que pisaría las fuentes, temas.yaml roto…)."""


# ---------------------------------------------------------------------------
# Temario (temas.yaml)
# ---------------------------------------------------------------------------

@dataclass
class Unidad:
    id: str
    titulo: str
    temas: List[str]


@dataclass
class Temario:
    """Títulos, prerrequisitos y unidades de los temas; vacío si el repositorio no tiene temas.yaml."""

    titulos: Dict[str, str] = field(default_factory=dict)
    requisitos: Dict[str, List[str]] = field(default_factory=dict)
    unidades: List[Unidad] = field(default_factory=list)
    rutas: List[Dict[str, str]] = field(default_factory=list)

    def titulo(self, tema: str) -> str:
        return self.titulos.get(tema) or tema.replace("_", " ").capitalize()

    def unidad_de(self, tema: str) -> Optional[Unidad]:
        return next((u for u in self.unidades if tema in u.temas), None)


def cargar_temario(ruta: Optional[Path]) -> Temario:
    """Lee temas.yaml: `temas: {slug: {titulo, requiere}}`, `unidades: [{id, titulo, temas}]`, `rutas`."""
    if ruta is None or not ruta.is_file():
        return Temario()
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SitioError(f"{ruta}: no es YAML válido: {exc}") from None
    if not isinstance(datos, dict):
        raise SitioError(f"{ruta}: tiene que ser un mapa con `temas`, `unidades` y `rutas`.")

    temario = Temario()
    for slug, info in (datos.get("temas") or {}).items():
        info = info or {}
        if info.get("titulo"):
            temario.titulos[slug] = str(info["titulo"])
        temario.requisitos[slug] = [str(r) for r in info.get("requiere") or []]
    for u in datos.get("unidades") or []:
        temario.unidades.append(Unidad(id=str(u["id"]), titulo=str(u.get("titulo") or u["id"]), temas=list(u.get("temas") or [])))
    temario.rutas = [dict(r) for r in datos.get("rutas") or []]

    desconocidos = sorted({r for reqs in temario.requisitos.values() for r in reqs} - set(temario.requisitos))
    if desconocidos:
        raise SitioError(f"{ruta}: prerrequisitos que no son temas declarados: {', '.join(desconocidos)}")
    return temario


# ---------------------------------------------------------------------------
# Carga del banco y de las guías
# ---------------------------------------------------------------------------

@dataclass
class EjercicioSitio:
    dir: Path
    ejercicio: Ejercicio
    pagina: str          # relativa a la salida: consignas/<tema>/<id>.md
    ripkg: str           # relativa a la salida: paquetes/<id>.ripkg


@dataclass
class GuiaSitio:
    slug: str
    nombre: str
    origen: Path
    datos: Dict[str, Any]
    pagina: str          # relativa a la salida: guias/<slug>.md
    ejercicios: List[EjercicioSitio]
    faltantes: List[str]  # ids que no están en el banco o no se publican


@dataclass
class BancoSitio:
    publicables: List[EjercicioSitio]
    no_publicados: int
    invalidos: List[Tuple[Path, str]]


def cargar_banco_sitio(banco: Path) -> BancoSitio:
    """Todos los ejercicios del banco (sin repetir los enlazados), separando los que no se publican y los inválidos."""
    vistos: set[Path] = set()
    por_id: Dict[str, Path] = {}
    publicables: List[EjercicioSitio] = []
    invalidos: List[Tuple[Path, str]] = []
    no_publicados = 0

    for meta in sorted(banco.rglob(ARCHIVO_EJERCICIO)):
        dir_ej = meta.parent
        real = dir_ej.resolve()
        if real in vistos:
            continue
        vistos.add(real)
        try:
            ej = cargar_ejercicio(dir_ej)
        except Exception as exc:  # EjercicioInvalido, YAML roto, etc.: se informa, no se publica
            invalidos.append((dir_ej, str(exc)))
            continue
        if ej.id in por_id:
            invalidos.append((dir_ej, f"id repetido «{ej.id}» (también en {por_id[ej.id]})"))
            continue
        por_id[ej.id] = dir_ej
        if not ej.publicar:
            no_publicados += 1
            continue
        publicables.append(EjercicioSitio(
            dir=dir_ej,
            ejercicio=ej,
            pagina=f"{DIR_CONSIGNAS}/{ej.tema}/{ej.id}.md",
            ripkg=f"{DIR_PAQUETES}/{ej.id}.ripkg",
        ))

    publicables.sort(key=lambda e: e.ejercicio.id)
    return BancoSitio(publicables=publicables, no_publicados=no_publicados, invalidos=invalidos)


def slug_guia(texto: str) -> str:
    """`guía_1_—_arreglos` → `guia-1-arreglos`: nombre de archivo y de URL estable."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-") or "guia"


def _archivos_de_guias(dir_guias: Path) -> List[Path]:
    """Primero las carpetas (`guias/<nombre>/guia.yaml`), después los YAML sueltos."""
    if not dir_guias.is_dir():
        return []
    archivos: List[Path] = []
    for sub in sorted(p for p in dir_guias.iterdir() if p.is_dir()):
        for cand in (sub / "guia.yaml", sub / "guia.yml", sub / f"{sub.name}.yaml", sub / f"{sub.name}.yml"):
            if cand.is_file():
                archivos.append(cand)
                break
    archivos.extend(sorted(dir_guias.glob("*.yaml")) + sorted(dir_guias.glob("*.yml")))
    return archivos


def cargar_guias_sitio(dir_guias: Path, publicables: List[EjercicioSitio]) -> List[GuiaSitio]:
    """Las guías compuestas (con `ejercicios`); las specs de `compose` no son publicables y se saltean."""
    por_id = {e.ejercicio.id: e for e in publicables}
    guias: Dict[str, GuiaSitio] = {}
    for archivo in _archivos_de_guias(dir_guias):
        datos = cargar_yaml_guia(archivo)
        if not isinstance(datos, dict) or not datos.get("ejercicios"):
            continue
        en_carpeta = archivo.parent != dir_guias
        base = archivo.parent.name if en_carpeta else archivo.stem
        slug = slug_guia(str(datos.get("identificador") or datos.get("id") or base))
        if slug in guias:  # la misma guía como carpeta y como YAML suelto
            continue

        ejercicios: List[EjercicioSitio] = []
        faltantes: List[str] = []
        for item in datos["ejercicios"]:
            eid = str(item.get("id") or "") if isinstance(item, dict) else str(item)
            if eid in por_id:
                ejercicios.append(por_id[eid])
            else:
                faltantes.append(eid)
        guias[slug] = GuiaSitio(
            slug=slug,
            nombre=str(datos.get("nombre") or base),
            origen=archivo,
            datos=datos,
            pagina=f"{DIR_GUIAS}/{slug}.md",
            ejercicios=ejercicios,
            faltantes=faltantes,
        )
    return sorted(guias.values(), key=lambda g: g.slug)


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

def _rel(destino: str, desde_pagina: str) -> str:
    """Enlace relativo (POSIX) desde una página hacia otro archivo, ambos relativos a la salida."""
    return Path(os.path.relpath(destino, os.path.dirname(desde_pagina) or ".")).as_posix()


def _orden_en_tema(e: EjercicioSitio) -> Tuple[int, int, str]:
    return (int(e.ejercicio.bloom), e.ejercicio.minutos_estimados, e.ejercicio.id)


def _por_tema(ejercicios: List[EjercicioSitio]) -> Dict[str, List[EjercicioSitio]]:
    por_tema: Dict[str, List[EjercicioSitio]] = defaultdict(list)
    for e in ejercicios:
        por_tema[e.ejercicio.tema].append(e)
    for lista in por_tema.values():
        lista.sort(key=_orden_en_tema)
    return dict(sorted(por_tema.items()))


def generar_pagina_ejercicio(e: EjercicioSitio, salida: Path, banco: Path, incluir_solucion: bool) -> Path:
    md, _ = renderizar_ejercicio_md(
        e.ejercicio,
        dir_ejercicio=e.dir,
        incluir_meta=True,
        incluir_solucion=incluir_solucion,
        incluir_pistas=True,
        incluir_tests=True,
        dir_banco=banco,
        rel_ripkg_path=_rel(e.ripkg, e.pagina),
    )
    destino = salida / e.pagina
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(md, encoding="utf-8")
    return destino


def generar_pagina_guia(g: GuiaSitio, salida: Path, banco: Path) -> Path:
    meta = dict(g.datos)
    meta["id"] = g.slug
    meta.setdefault("nombre", g.nombre)
    md, _ = renderizar_guia_md(
        meta,
        [(e.dir, e.ejercicio) for e in g.ejercicios],
        incluir_soluciones=False,
        incluir_pistas=True,
        dir_banco=banco,
        rutas_ripkg={e.ejercicio.id: _rel(e.ripkg, g.pagina) for e in g.ejercicios},
    )
    destino = salida / g.pagina
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(md, encoding="utf-8")
    return destino


def generar_portada(
    ejercicios: List[EjercicioSitio], guias: List[GuiaSitio], temario: Temario, destino: Path
) -> None:
    total = len(ejercicios)
    minutos = sum(e.ejercicio.minutos_estimados for e in ejercicios)
    por_tema = _por_tema(ejercicios)
    conteo_bloom: Dict[int, int] = defaultdict(int)
    for e in ejercicios:
        conteo_bloom[int(e.ejercicio.bloom)] += 1

    lineas = [
        "# Banco de Consignas Prácticas — Programación 1",
        "",
        "Repositorio central de ejercicios prácticos y autoevaluaciones.",
        "",
        "## 📊 Métricas del banco",
        "",
        f"- **Ejercicios:** {total}",
        f"- **Carga de práctica acumulada:** ~{minutos} minutos ({round(minutos / 60, 1)} hs cátedra)",
        f"- **Ejes temáticos:** {len(por_tema)}",
        f"- **Guías:** {len(guias)}",
        "",
        "### Distribución taxonómica (Bloom)",
        "",
        "| Nivel | Dimensión cognitiva | Cantidad | Porcentaje |",
        "| :---: | :--- | :---: | :---: |",
    ]
    for b, nombre in BLOOM_NOMBRES.items():
        cant = conteo_bloom[b]
        pct = cant / total * 100 if total else 0
        lineas.append(f"| B{b} | {nombre} | {cant} | {pct:.1f}% |")

    lineas += [
        "",
        "## 🚀 Flujo de trabajo con Ripley",
        "",
        "Cada ejercicio tiene un paquete `.ripkg` descargable con los casos de prueba,",
        "las cabeceras C y las verificaciones pedagógicas.",
        "",
        "1. **Descargá** el paquete `.ripkg` del ejercicio que quieras resolver.",
        "2. **Ejecutá** la suite de pruebas local:",
        "   ```bash",
        "   ripley run <ejercicio>.ripkg",
        "   ```",
        "3. **Seguí** el ciclo rojo-verde-refactor hasta que pasen todas las pruebas.",
        "",
        f"El catálogo de ejercicios y guías en JSON (para herramientas) está en [`{DIR_PAQUETES}/{ARCHIVO_CATALOGO}`]({DIR_PAQUETES}/{ARCHIVO_CATALOGO}).",
        "",
    ]
    if guias:
        lineas += [
            "## 🗂️ Guías",
            "",
            "| Guía | Ejercicios | Carga |",
            "| :--- | :---: | :---: |",
        ]
        for g in guias:
            carga = sum(e.ejercicio.minutos_estimados for e in g.ejercicios)
            lineas.append(f"| [{g.nombre}]({g.pagina}) | {len(g.ejercicios)} | ~{carga} min |")
        lineas.append("")

    lineas += [
        "## 📑 Índice por ejes temáticos",
        "",
        "| Tema | Nombre | Ejercicios | Carga total |",
        "| :--- | :--- | :---: | :---: |",
    ]
    for tema, lista in por_tema.items():
        carga = sum(e.ejercicio.minutos_estimados for e in lista)
        lineas.append(f"| `{tema}` | {temario.titulo(tema)} | {len(lista)} | ~{carga} min |")
    lineas.append("")
    destino.write_text("\n".join(lineas), encoding="utf-8")


def generar_grafo_tematico(ejercicios: List[EjercicioSitio], temario: Temario, destino: Path) -> None:
    por_tema = _por_tema(ejercicios)
    lineas = [
        "# 🗺️ Grafo de dependencias temáticas",
        "",
        f"Mapa de los prerrequisitos entre los {len(temario.requisitos)} ejes temáticos de la materia.",
        "Los ejercicios declaran sus dependencias con las etiquetas `dep:<tema>`.",
        "",
        "::: {admonition} 🏷️ Etiquetas de dependencia",
        ":class: note",
        "- `dep:<tema>`: resolver el ejercicio requiere dominar antes el eje `<tema>` (p. ej. `dep:punteros`).",
        "- `req:<id>`: dependencia estricta de un ejercicio previo puntual.",
        ":::",
        "",
        "## 🧭 Diagrama",
        "",
        "```mermaid",
        "flowchart TD",
    ]

    def nodo(tema: str) -> str:
        lista = por_tema.get(tema, [])
        blooms = [int(e.ejercicio.bloom) for e in lista]
        prom = round(sum(blooms) / len(blooms), 1) if blooms else "—"
        return f'        {tema}["{temario.titulo(tema)}<br/><small>{len(lista)} ejs · B{prom}</small>"]'

    asignados: set[str] = set()
    for u in temario.unidades:
        lineas.append(f'    subgraph {u.id} ["{u.titulo}"]')
        for tema in u.temas:
            asignados.add(tema)
            lineas.append(nodo(tema))
        lineas.append("    end")
    extra = sorted(t for t in temario.requisitos if t not in asignados)
    if extra:
        lineas.append('    subgraph complementarios ["Ejes complementarios"]')
        lineas += [nodo(t) for t in extra]
        lineas.append("    end")
    for tema, reqs in temario.requisitos.items():
        lineas += [f"    {r} --> {tema}" for r in reqs]

    habilita: Dict[str, List[str]] = defaultdict(list)
    for tema, reqs in temario.requisitos.items():
        for r in reqs:
            habilita[r].append(tema)

    lineas += [
        "```",
        "",
        "## 📊 Prerrequisitos y habilitaciones",
        "",
        "| Eje temático | Unidad | Prerrequisitos (`dep:*`) | Habilita | Ejercicios | Carga total |",
        "| :--- | :---: | :--- | :--- | :---: | :---: |",
    ]
    for tema, reqs in sorted(temario.requisitos.items()):
        unidad = temario.unidad_de(tema)
        u_str = unidad.id.replace("unidad_", "U") if unidad else "Extra"
        reqs_str = ", ".join(f"`dep:{r}`" for r in reqs) or "_Raíz_"
        hab_str = ", ".join(f"`{h}`" for h in habilita.get(tema, [])) or "_Terminal_"
        lista = por_tema.get(tema, [])
        carga = sum(e.ejercicio.minutos_estimados for e in lista)
        lineas.append(f"| `{tema}`<br/>**{temario.titulo(tema)}** | {u_str} | {reqs_str} | {hab_str} | {len(lista)} | ~{carga} min |")

    if temario.rutas:
        lineas += ["", "## 🚀 Rutas de especialización", ""]
        for i, ruta in enumerate(temario.rutas, 1):
            lineas += [f"### {i}. {ruta.get('titulo', '')}"]
            if ruta.get("descripcion"):
                lineas.append(str(ruta["descripcion"]))
            lineas += ["```", str(ruta.get("camino", "")), "```", ""]
    lineas.append("")
    destino.write_text("\n".join(lineas), encoding="utf-8")


# ---------------------------------------------------------------------------
# TOC de myst.yml
# ---------------------------------------------------------------------------

def construir_toc(
    ejercicios: List[EjercicioSitio],
    guias: List[GuiaSitio],
    temario: Temario,
    prefijo: str,
    agrupar_por_unidad: bool = False,
) -> List[Dict[str, Any]]:
    """TOC de MyST; `prefijo` es la ruta de la salida relativa a myst.yml."""
    def f(rel: str) -> Dict[str, str]:
        return {"file": f"{prefijo}/{rel}" if prefijo not in ("", ".") else rel}

    def seccion_tema(tema: str, lista: List[EjercicioSitio]) -> Dict[str, Any]:
        return {"title": temario.titulo(tema), "children": [f(e.pagina) for e in lista]}

    toc: List[Dict[str, Any]] = [f("index.md"), f("grafo_tematico.md")]
    if guias:
        toc.append({"title": "Guías", "children": [f(g.pagina) for g in guias]})

    por_tema = _por_tema(ejercicios)
    if not agrupar_por_unidad or not temario.unidades:
        toc += [seccion_tema(t, lista) for t, lista in por_tema.items()]
        return toc

    asignados: set[str] = set()
    for u in temario.unidades:
        secciones = [seccion_tema(t, por_tema[t]) for t in u.temas if por_tema.get(t)]
        asignados.update(u.temas)
        if secciones:
            toc.append({"title": u.titulo, "children": secciones})
    resto = [seccion_tema(t, lista) for t, lista in por_tema.items() if t not in asignados]
    if resto:
        toc.append({"title": "Consignas complementarias", "children": resto})
    return toc


def actualizar_toc_myst(myst_yml: Path, toc: List[Dict[str, Any]]) -> None:
    """Reescribe `project.toc` de myst.yml (los comentarios se pierden: es un archivo del CI)."""
    config = yaml.safe_load(myst_yml.read_text(encoding="utf-8")) or {}
    if not isinstance(config.get("project"), dict):
        config["project"] = {}
    config["project"]["toc"] = toc
    myst_yml.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")


# ---------------------------------------------------------------------------
# Paquetes .ripkg y catálogo
# ---------------------------------------------------------------------------

def empaquetar_publicables(ejercicios: List[EjercicioSitio], salida: Path) -> Tuple[Dict[str, Path], List[Tuple[str, str]]]:
    """Un .ripkg por ejercicio, sin las pruebas ocultas (el sitio es público)."""
    from deckard.core.pack import empaquetar_ejercicio

    hechos: Dict[str, Path] = {}
    fallidos: List[Tuple[str, str]] = []
    for e in ejercicios:
        destino = salida / e.ripkg
        try:
            empaquetar_ejercicio(e.dir, out_path=destino, include_hidden=False)
        except Exception as exc:
            fallidos.append((e.ejercicio.id, str(exc)))
            continue
        hechos[e.ejercicio.id] = destino
    return hechos, fallidos


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _entrada_ejercicio(e: EjercicioSitio, banco: Path, temario: Temario, paquete: Optional[Path]) -> Dict[str, Any]:
    ej = e.ejercicio
    unidad = temario.unidad_de(ej.tema)
    entrada: Dict[str, Any] = {
        "id": ej.id,
        "titulo": ej.titulo,
        "tema": ej.tema,
        "tema_titulo": temario.titulo(ej.tema),
        "subtema": ej.subtema,
        "unidad": ej.unidad if ej.unidad is not None else (unidad.id if unidad else None),
        "bloom": int(ej.bloom),
        "bloom_nombre": BLOOM_NOMBRES[int(ej.bloom)],
        "dificultad": ej.dificultad,
        "tipo": ej.tipo,
        "minutos_estimados": ej.minutos_estimados,
        "tipo_entrega": ej.tipo_entrega,
        "verificado": ej.verificado,
        "tags": list(ej.tags),
        "prerrequisitos": list(ej.prerrequisitos),
        "siguiente_recomendado": list(ej.siguiente_recomendado),
        "funciones": [f.model_dump(exclude_none=True) for f in ej.funciones],
        "origen": e.dir.relative_to(banco).as_posix() if e.dir.is_relative_to(banco) else e.dir.name,
        "pagina": e.pagina,
        "ripkg": None,
    }
    if paquete is not None and paquete.is_file():
        entrada["ripkg"] = {
            "archivo": paquete.name,  # relativo al catálogo, que vive junto a los paquetes
            "sha256": _sha256(paquete),
            "bytes": paquete.stat().st_size,
        }
    return entrada


def escribir_catalogo(
    destino: Path,
    ejercicios: List[EjercicioSitio],
    guias: List[GuiaSitio],
    paquetes: Dict[str, Path],
    banco: Path,
    temario: Temario,
) -> Dict[str, Any]:
    """catalogo.json: ejercicios y guías publicados, con su paquete y hash, para ripley y otras herramientas."""
    catalogo = {
        "formato": FORMATO_CATALOGO,
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totales": {
            "ejercicios": len(ejercicios),
            "guias": len(guias),
            "minutos": sum(e.ejercicio.minutos_estimados for e in ejercicios),
        },
        "ejercicios": [_entrada_ejercicio(e, banco, temario, paquetes.get(e.ejercicio.id)) for e in ejercicios],
        "guias": [
            {
                "id": g.slug,
                "nombre": g.nombre,
                "minutos_totales": sum(e.ejercicio.minutos_estimados for e in g.ejercicios),
                "distribucion_bloom": g.datos.get("distribucion_bloom") or {},
                "pagina": g.pagina,
                "ejercicios": [e.ejercicio.id for e in g.ejercicios],
                "faltantes": list(g.faltantes),
            }
            for g in guias
        ],
    }
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return catalogo


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

@dataclass
class ResumenSitio:
    salida: Path
    ejercicios: int
    no_publicados: int
    invalidos: List[Tuple[Path, str]]
    guias: List[GuiaSitio]
    guias_vacias: List[GuiaSitio]  # ningún ejercicio publicado: no tienen página
    paquetes: int
    fallidos_pack: List[Tuple[str, str]]
    catalogo: Optional[Path]
    myst_yml: Optional[Path]


def _validar_salida(salida: Path, fuentes: List[Path]) -> None:
    """La salida se limpia entera en cada corrida: no puede contener ni pisar las fuentes."""
    sal = salida.resolve()
    for fuente in fuentes:
        f = fuente.resolve()
        if f == sal or f.is_relative_to(sal) or sal.is_relative_to(f):
            raise SitioError(f"La salida {salida} no puede contener ni estar dentro de {fuente}: se borra en cada corrida.")


def construir_sitio(
    banco: Path,
    salida: Path,
    dir_guias: Optional[Path] = None,
    temas: Optional[Path] = None,
    myst_yml: Optional[Path] = None,
    incluir_soluciones: bool = True,
    agrupar_por_unidad: bool = False,
    paquetes: bool = True,
) -> ResumenSitio:
    """Genera el sitio completo en `salida` (que se regenera desde cero) y actualiza el TOC de `myst_yml`."""
    if not banco.is_dir():
        raise SitioError(f"No existe el banco {banco}.")
    _validar_salida(salida, [p for p in (banco, dir_guias) if p is not None])
    temario = cargar_temario(temas)

    datos_banco = cargar_banco_sitio(banco)
    ejercicios = datos_banco.publicables
    todas = cargar_guias_sitio(dir_guias, ejercicios) if dir_guias else []
    guias = [g for g in todas if g.ejercicios]

    if salida.exists():
        shutil.rmtree(salida)
    salida.mkdir(parents=True)

    for e in ejercicios:
        generar_pagina_ejercicio(e, salida, banco, incluir_soluciones)
    for g in guias:
        generar_pagina_guia(g, salida, banco)
    generar_portada(ejercicios, guias, temario, salida / "index.md")
    generar_grafo_tematico(ejercicios, temario, salida / "grafo_tematico.md")

    hechos: Dict[str, Path] = {}
    fallidos: List[Tuple[str, str]] = []
    catalogo: Optional[Path] = None
    if paquetes:
        hechos, fallidos = empaquetar_publicables(ejercicios, salida)
        catalogo = salida / DIR_PAQUETES / ARCHIVO_CATALOGO
        escribir_catalogo(catalogo, ejercicios, guias, hechos, banco, temario)

    if myst_yml is not None:
        prefijo = Path(os.path.relpath(salida.resolve(), myst_yml.resolve().parent)).as_posix()
        actualizar_toc_myst(myst_yml, construir_toc(ejercicios, guias, temario, prefijo, agrupar_por_unidad))

    return ResumenSitio(
        salida=salida,
        ejercicios=len(ejercicios),
        no_publicados=datos_banco.no_publicados,
        invalidos=datos_banco.invalidos,
        guias=guias,
        guias_vacias=[g for g in todas if not g.ejercicios],
        paquetes=len(hechos),
        fallidos_pack=fallidos,
        catalogo=catalogo,
        myst_yml=myst_yml,
    )
