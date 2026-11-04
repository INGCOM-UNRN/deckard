"""Lint del banco: lo que rompe el sitio, los paquetes o los enlaces, antes de publicar.

Revisa cada ejercicio (que cargue, id único y coherente con su carpeta, tema del temario,
dependencias `dep:<tema>` declaradas, enunciado y solución) y, sin patrón, todo el banco: las
guías (que sus ejercicios existan y se publiquen) y la trazabilidad con el apunte (que cada
página citada en temas.yaml exista y esté en el TOC del apunte, que cada tema publicado tenga
teoría y que los bloques de `export apunte` estén al día).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from deckard.core.bank import ARCHIVO_EJERCICIO, cargar_ejercicio
from deckard.core.diagramas_sitio import svgs_faltantes
from deckard.core.models import Ejercicio
from deckard.core.signature_checker import verificar_firmas_ejercicio

ERROR = "error"
AVISO = "aviso"

# Regla → qué revisa (para --reglas y la documentación).
REGLAS: Dict[str, str] = {
    "yaml-invalido": "el ejercicio.yaml no carga o no valida",
    "id-repetido": "dos ejercicios con el mismo id",
    "id-carpeta": "la carpeta no se llama como el id",
    "tema-carpeta": "el ejercicio no está en banco/<tema>/",
    "esquema": "falta el título o los minutos estimados",
    "tema-desconocido": "el tema no está en temas.yaml",
    "dep-desconocida": "una etiqueta dep:<tema> no es un tema de temas.yaml",
    "falta-enunciado": "un ejercicio publicable sin enunciado",
    "falta-solucion": "un ejercicio publicable sin solución de la cátedra",
    "firmas": "una función declarada falta en la solución o tiene otro tipo de retorno",
    "sin-pruebas": "un ejercicio publicable sin casos de prueba (tests/*.in ni tests_funciones)",
    "solucion": "con --verificar-soluciones, ripley check rechaza la solución de la cátedra",
    "guia-faltante": "una guía cita un ejercicio que no está en el banco",
    "guia-no-publicado": "una guía cita un ejercicio con publicar: false",
    "apunte-inexistente": "temas.yaml cita una página del apunte (de un tema o de una regla de estilo) que no existe",
    "apunte-fuera-del-toc": "temas.yaml cita una página que no está en el TOC del apunte (no se publica)",
    "tema-sin-apunte": "un tema con ejercicios publicados no cita ninguna página del apunte",
    "apunte-desactualizado": "el bloque de ejercicios de una página del apunte no está al día (export apunte)",
    "starter": "el starter_code no compila",
}


@dataclass
class Hallazgo:
    nivel: str
    regla: str
    donde: str
    mensaje: str


@dataclass
class ResultadoLint:
    ejercicios: int
    hallazgos: List[Hallazgo]

    @property
    def errores(self) -> List[Hallazgo]:
        return [h for h in self.hallazgos if h.nivel == ERROR]

    @property
    def avisos(self) -> List[Hallazgo]:
        return [h for h in self.hallazgos if h.nivel == AVISO]

    def a_dict(self) -> Dict[str, object]:
        conteo: Dict[str, int] = {}
        for h in self.hallazgos:
            conteo[h.regla] = conteo.get(h.regla, 0) + 1
        return {
            "ejercicios": self.ejercicios,
            "errores": len(self.errores),
            "avisos": len(self.avisos),
            "por_regla": dict(sorted(conteo.items())),
            "hallazgos": [asdict(h) for h in self.hallazgos],
        }


def _revisar_ejercicio(ej: Ejercicio, dir_ej: Path, banco: Path, temas: Optional[Dict[str, List[str]]]) -> List[Hallazgo]:
    donde = dir_ej.relative_to(banco).as_posix() if dir_ej.is_relative_to(banco) else str(dir_ej)
    out: List[Hallazgo] = []

    def h(nivel: str, regla: str, mensaje: str) -> None:
        out.append(Hallazgo(nivel, regla, donde, mensaje))

    if dir_ej.name != ej.id:
        h(AVISO, "id-carpeta", f"la carpeta {dir_ej.name} no se llama como el id {ej.id}")
    if dir_ej.parent != banco and dir_ej.parent.name != ej.tema:
        h(AVISO, "tema-carpeta", f"tema {ej.tema} pero está en {dir_ej.parent.name}/")
    if not ej.titulo:
        h(ERROR, "esquema", "falta el título")
    if ej.minutos_estimados <= 0:
        h(ERROR, "esquema", "minutos_estimados tiene que ser positivo")
    if temas is not None:
        # En un prototipo (publicar: false) no rompe nada todavía: es aviso.
        nivel = ERROR if ej.publicar else AVISO
        if ej.tema not in temas:
            h(nivel, "tema-desconocido", f"el tema {ej.tema} no está en temas.yaml")
        for tag in ej.tags:
            if tag.startswith("dep:") and tag[4:] not in temas:
                h(nivel, "dep-desconocida", f"{tag} no es un tema de temas.yaml")
    if ej.publicar:
        if not (ej.enunciado_md or "").strip():
            h(ERROR, "falta-enunciado", "se publica pero no tiene enunciado")
        if not (ej.solucion_c or "").strip():
            h(AVISO, "falta-solucion", "se publica sin solución de la cátedra")
        for d in verificar_firmas_ejercicio(ej):
            h(ERROR, "firmas", d.detalle)
        pruebas = dir_ej / "tests"
        if not (pruebas.is_dir() and any(pruebas.rglob("*.in"))) and not ej.tests_funciones:
            h(AVISO, "sin-pruebas", "se publica sin casos de prueba")
        faltan = svgs_faltantes(ej.enunciado_md or "", dir_ej)
        if faltan:
            h(ERROR, "diagrama-sin-svg", f"{len(faltan)} bloque(s) ```estructura sin su SVG en diagramas/ "
              f"({', '.join(faltan)}): corré `alucard diagramas-md` (hook alucard-diagramas)")
    return out


def revisar_banco(
    banco: Path,
    temas: Optional[Path] = None,
    dir_guias: Optional[Path] = None,
    dir_apunte: Optional[Path] = None,
    patron: Optional[str] = None,
    verificar_soluciones: bool = False,
    ruta_ripley: Optional[str] = None,
) -> ResultadoLint:
    """Todos los hallazgos del banco; con `patron`, sólo los de los ejercicios cuyo id lo contiene.

    Con `verificar_soluciones`, cada solución publicable pasa por `ripley check` (deckard no compila
    por su cuenta; ver `deckard verify`).
    """
    from deckard.core.sitio import _archivos_de_guias, cargar_temario, planificar_apunte, _por_tema, EjercicioSitio
    from deckard.core.guides import cargar_yaml_guia
    from deckard.core.trazabilidad import actualizar_paginas, archivos_del_toc, paginas_con_bloque

    temario = cargar_temario(temas) if temas is not None and temas.is_file() else None
    requisitos = temario.requisitos if temario is not None else None
    hallazgos: List[Hallazgo] = []
    por_id: Dict[str, Path] = {}
    publicados: Dict[str, bool] = {}
    publicables: List[EjercicioSitio] = []
    vistos: set[Path] = set()
    no_cargan: set[str] = set()  # carpetas de ejercicios cuyo YAML no carga (las guías los citan por id)
    revisados = 0

    for meta in sorted(banco.rglob(ARCHIVO_EJERCICIO)):
        dir_ej = meta.parent
        if dir_ej.resolve() in vistos:
            continue
        vistos.add(dir_ej.resolve())
        rel = dir_ej.relative_to(banco).as_posix()
        try:
            ej = cargar_ejercicio(dir_ej)
        except Exception as exc:
            no_cargan.add(dir_ej.name)
            if patron is None or patron in rel:
                detalle = " ".join(linea.strip(" -") for linea in str(exc).splitlines()[1:]) or str(exc)
                hallazgos.append(Hallazgo(ERROR, "yaml-invalido", rel, detalle[:300]))
            continue
        if ej.id in por_id:
            if patron is None or patron in ej.id:
                hallazgos.append(Hallazgo(ERROR, "id-repetido", rel, f"el id {ej.id} también está en {por_id[ej.id].relative_to(banco)}"))
            continue
        por_id[ej.id] = dir_ej
        publicados[ej.id] = ej.publicar
        if ej.publicar:
            publicables.append(EjercicioSitio(dir=dir_ej, ejercicio=ej, pagina=f"consignas/{ej.tema}/{ej.id}.md", ripkg=""))
        if patron is not None and patron not in ej.id:
            continue
        revisados += 1
        hallazgos += _revisar_ejercicio(ej, dir_ej, banco, requisitos)
        if verificar_soluciones and ej.publicar and (ej.solucion_c or "").strip():
            from deckard.core.verify import verificar_ejercicio

            resultado = verificar_ejercicio(dir_ej, ruta_ripley=ruta_ripley)
            if not resultado.ok:
                hallazgos.append(Hallazgo(ERROR, "solucion", rel, resultado.detalle[:300]))

    if patron is not None:
        return ResultadoLint(revisados, hallazgos)

    # Guías
    for archivo in _archivos_de_guias(dir_guias) if dir_guias is not None else []:
        datos = cargar_yaml_guia(archivo)
        if not isinstance(datos, dict):
            continue
        donde = archivo.relative_to(dir_guias.parent).as_posix() if dir_guias is not None else str(archivo)
        for item in datos.get("ejercicios") or []:
            eid = str(item.get("id") or "") if isinstance(item, dict) else str(item)
            if eid not in publicados:
                motivo = "existe pero su ejercicio.yaml no carga" if eid in no_cargan else "no está en el banco"
                hallazgos.append(Hallazgo(ERROR, "guia-faltante", donde, f"cita {eid}, que {motivo}"))
            elif not publicados[eid]:
                hallazgos.append(Hallazgo(AVISO, "guia-no-publicado", donde, f"cita {eid}, que tiene publicar: false"))

    # Trazabilidad con el apunte
    if temario is not None:
        con_ejercicios = set(_por_tema(publicables))
        for tema in sorted(con_ejercicios):
            if not temario.apunte.get(tema):
                hallazgos.append(Hallazgo(AVISO, "tema-sin-apunte", f"temas.yaml:{tema}",
                                          "tiene ejercicios publicados y ninguna página del apunte"))
        if dir_apunte is not None:
            myst = dir_apunte / "myst.yml"
            en_toc = set(archivos_del_toc(myst)) if myst.is_file() else None
            citadas = [(f"temas.yaml:{tema}", ruta) for tema, paginas in sorted(temario.apunte.items()) for ruta in paginas]
            citadas += [(f"temas.yaml:reglas.{regla}", str(info.get("apunte")))
                        for regla, info in sorted(temario.reglas.items()) if info.get("apunte")]
            for donde_tema, ruta in citadas:
                pagina = ruta.partition("#")[0]
                if not (dir_apunte / pagina).is_file():
                    hallazgos.append(Hallazgo(ERROR, "apunte-inexistente", donde_tema, f"{pagina} no existe en el apunte"))
                elif en_toc is not None and pagina not in en_toc:
                    hallazgos.append(Hallazgo(ERROR, "apunte-fuera-del-toc", donde_tema,
                                              f"{pagina} no está en el TOC del apunte: el enlace no se publica"))
            if temario.sitios.get("enunciados") and temas is not None:
                plan = planificar_apunte(banco, temas, dir_apunte)
                cambiadas, _ = actualizar_paginas(dir_apunte, plan.bloques, escribir=False)
                for ruta in [*cambiadas, *(r for r in paginas_con_bloque(dir_apunte) if r not in plan.bloques)]:
                    hallazgos.append(Hallazgo(AVISO, "apunte-desactualizado", ruta,
                                              "el bloque de ejercicios no está al día: correr deckard export apunte"))
    return ResultadoLint(revisados, hallazgos)
