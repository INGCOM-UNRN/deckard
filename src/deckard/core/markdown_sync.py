"""Conversor bidireccional entre YAML/directorio de ejercicio y Markdown interactivo con frontmatter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
import yaml

from deckard.core.models import Ejercicio, FuncionSpec, CasoTestFuncion, NivelBloom


def ejercicio_a_markdown(ej: Ejercicio) -> str:
    """Convierte un objeto Ejercicio a un archivo Markdown único con YAML frontmatter."""
    metadata = {
        "id": ej.id,
        "titulo": ej.titulo,
        "tema": ej.tema,
        "bloom": int(ej.bloom),
        "minutos": ej.minutos_estimados,
        "tags": ej.tags,
        "verificado": ej.verificado,
        "tipo_entrega": ej.tipo_entrega,
    }
    if ej.dependencias:
        metadata["dependencias"] = ej.dependencias
    if ej.funciones:
        metadata["funciones"] = [
            {"nombre": f.nombre, "retorno": f.retorno, "parametros": f.parametros}
            for f in ej.funciones
        ]
    if ej.rubrica:
        metadata["rubrica"] = ej.rubrica
    if ej.benchmarks:
        metadata["benchmarks"] = ej.benchmarks

    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()

    partes: list[str] = [
        "---",
        frontmatter,
        "---",
        "",
        f"# {ej.titulo}",
        "",
        "## Enunciado",
        "",
        ej.enunciado_md.strip() if ej.enunciado_md else "_Sin enunciado especificado._",
        "",
    ]

    if ej.starter_code.strip():
        partes.extend([
            "## Starter Code",
            "",
            "```c",
            ej.starter_code.strip(),
            "```",
            "",
        ])

    if ej.solucion_c.strip():
        partes.extend([
            "## Solución Modelo",
            "",
            "```c",
            ej.solucion_c.strip(),
            "```",
            "",
        ])

    if ej.pistas:
        partes.extend([
            "## Pistas",
            "",
        ])
        for i, pista in enumerate(ej.pistas, 1):
            partes.append(f"{i}. {pista}")
        partes.append("")

    if ej.tests_funciones:
        partes.extend([
            "## Casos de Prueba de Funciones",
            "",
        ])
        for tf in ej.tests_funciones:
            partes.append(f"### Test: {tf.nombre}")
            partes.append(f"- **Función**: `{tf.funcion}`")
            if tf.descripcion:
                partes.append(f"- **Descripción**: {tf.descripcion}")
            if tf.args:
                partes.append(f"- **Argumentos**: `{tf.args}`")
            if tf.retorno_esperado:
                partes.append(f"- **Retorno esperado**: `{tf.retorno_esperado}`")
            if tf.postcondiciones:
                partes.append(f"- **Postcondición**: `{tf.postcondiciones}`")
            if tf.codigo:
                partes.extend(["```c", tf.codigo.strip(), "```"])
            partes.append("")

    return "\n".join(partes)


def markdown_a_ejercicio(contenido_md: str) -> Ejercicio:
    """Parsea un Markdown con frontmatter y secciones hacia un objeto Ejercicio."""
    # Extraer frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", contenido_md, re.DOTALL)
    if not fm_match:
        raise ValueError("El archivo Markdown no contiene un frontmatter YAML delimitado por '---'.")

    fm_txt, cuerpo = fm_match.groups()
    meta = yaml.safe_load(fm_txt) or {}

    ej_id = meta.get("id", "ejercicio-importado")
    titulo = meta.get("titulo", "Ejercicio Importado")
    tema = meta.get("tema", "general")
    bloom_val = meta.get("bloom", 2)
    minutos = meta.get("minutos", meta.get("minutos_estimados", 20))
    tags = meta.get("tags", [])
    verificado = meta.get("verificado", False)
    tipo_entrega = meta.get("tipo_entrega", "archivos_individuales")
    dependencias = meta.get("dependencias", [])
    rubrica = meta.get("rubrica")
    benchmarks = meta.get("benchmarks", {})

    funciones: list[FuncionSpec] = []
    for f in meta.get("funciones", []):
        if isinstance(f, dict):
            funciones.append(FuncionSpec(
                nombre=f.get("nombre", ""),
                retorno=f.get("retorno", "void"),
                parametros=f.get("parametros", ""),
                descripcion=f.get("descripcion"),
            ))
        elif isinstance(f, str):
            funciones.append(FuncionSpec.parse(f))

    # Parsear secciones del cuerpo
    secciones = re.split(r"\n(?=##\s+)", cuerpo)

    enunciado_md = ""
    starter_code = ""
    solucion_c = ""
    pistas: list[str] = []

    def _extraer_codigo_bloque(texto: str) -> str:
        m = re.search(r"```(?:c|cpp)?\s*\n(.*?)\n```", texto, re.DOTALL)
        return m.group(1).strip() if m else ""

    for sec in secciones:
        sec = sec.strip()
        if sec.startswith("## Enunciado"):
            lineas = sec.splitlines()[1:]
            enunciado_md = "\n".join(lineas).strip()
        elif sec.startswith("## Starter Code") or sec.startswith("## Esqueleto"):
            starter_code = _extraer_codigo_bloque(sec)
        elif sec.startswith("## Solución Modelo") or sec.startswith("## Solución"):
            solucion_c = _extraer_codigo_bloque(sec)
        elif sec.startswith("## Pistas"):
            lineas = sec.splitlines()[1:]
            for l in lineas:
                l_strip = l.strip()
                m = re.match(r"^\d+\.\s*(.+)$", l_strip)
                if m:
                    pistas.append(m.group(1).strip())
                elif l_strip.startswith("- "):
                    pistas.append(l_strip[2:].strip())

    if not enunciado_md and not starter_code and not solucion_c:
        enunciado_md = cuerpo.strip()

    return Ejercicio(
        id=ej_id,
        titulo=titulo,
        tema=tema,
        bloom=NivelBloom(int(bloom_val)),
        minutos_estimados=int(minutos),
        enunciado_md=enunciado_md,
        starter_code=starter_code,
        solucion_c=solucion_c,
        pistas=pistas,
        tags=tags,
        verificado=verificado,
        tipo_entrega=tipo_entrega,
        dependencias=dependencias,
        funciones=funciones,
        rubrica=rubrica,
        benchmarks=benchmarks,
    )


def exportar_ejercicio_md_interactivo(
    dir_ejercicio: Path,
    ruta_salida: Optional[Path] = None,
) -> Path:
    """Exporta el ejercicio a un archivo .md interactivo con frontmatter."""
    from deckard.core.bank import cargar_ejercicio
    ej = cargar_ejercicio(dir_ejercicio)
    md_text = ejercicio_a_markdown(ej)

    if ruta_salida is None:
        ruta_salida = dir_ejercicio / f"{ej.id}.interactive.md"

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_text(md_text, encoding="utf-8")
    return ruta_salida


def importar_ejercicio_desde_md(
    ruta_md: Path,
    dir_destino: Path,
    sobrescribir: bool = False,
) -> Path:
    """Importa un archivo .md interactivo y recrea la estructura de directorio canónica de Deckard."""
    from deckard.core.bank import guardar_ejercicio
    contenido = ruta_md.read_text(encoding="utf-8")
    ej = markdown_a_ejercicio(contenido)

    dir_final = dir_destino / ej.id
    if dir_final.exists() and not sobrescribir:
        raise FileExistsError(f"El directorio '{dir_final}' ya existe. Usá sobrescribir para reemplazarlo.")

    guardar_ejercicio(ej, dir_destino)
    return dir_final
