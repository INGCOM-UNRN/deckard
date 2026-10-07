"""tp-multiplexer: Generador de variantes combinatorias de TPs y asignación determinista por alumno."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import hashlib
import itertools
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import yaml

from pydantic import BaseModel, Field

from deckard.core.bank import guardar_ejercicio
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.pack import empaquetar_ejercicio, exportar_starter_repo, ResultadoEmpaquetado


@dataclass
class MatrizSpec:
    """Especificación declarativa de una matriz combinatoria de TP."""
    ejercicio: str
    titulo: str
    enunciado_template: str
    solucion_template: Optional[str] = None
    starter_template: Optional[str] = None
    parametrizaciones: Dict[str, List[Any]] = field(default_factory=dict)
    tests_template: List[Dict[str, str]] = field(default_factory=list)
    pistas_template: List[str] = field(default_factory=list)
    bloom: int = 3
    tema: str = "tps"
    minutos_estimados: int = 30
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "MatrizSpec":
        d = dict(data)
        return cls(
            ejercicio=str(d.get("ejercicio", "")),
            titulo=str(d.get("titulo", "")),
            enunciado_template=str(d.get("enunciado_template", "")),
            solucion_template=d.get("solucion_template"),
            starter_template=d.get("starter_template"),
            parametrizaciones=d.get("parametrizaciones") or {},
            tests_template=d.get("tests_template") or [],
            pistas_template=d.get("pistas_template") or [],
            bloom=int(d.get("bloom", 3)),
            tema=str(d.get("tema", "tps")),
            minutos_estimados=int(d.get("minutos_estimados", 30)),
            tags=d.get("tags") or [],
        )


@dataclass
class Variante:
    id: str
    index: int
    parametros: Dict[str, Any]
    enunciado_md: str
    solucion_c: str
    starter_c: str
    tests: List[Tuple[str, str]]  # [(caso_NN.in, caso_NN.out), ...]
    pistas: List[str]


@dataclass
class Alumno:
    id: str
    nombre: str = ""
    email: str = ""


@dataclass
class Asignacion:
    alumno: Alumno
    variante: Variante
    ripkg_path: Optional[Path] = None
    starter_path: Optional[Path] = None


def render_template(template_str: str, context: Dict[str, Any]) -> str:
    """Renderiza variables {{ clave }} y bloques condicionales simples {% if k == 'v' %}."""
    if not template_str:
        return ""

    texto = template_str

    # 1. Bloques condicionales {% if var == 'val' %} ... {% else %} ... {% endif %}
    def _eval_condition(match: re.Match) -> str:
        var_name = match.group(1).strip()
        op = match.group(2).strip()
        expected = match.group(3).strip().strip("'\"")
        content_if = match.group(4)
        content_else = match.group(5) if match.group(5) is not None else ""

        val = str(context.get(var_name, ""))
        is_true = (val == expected) if op in ("==", "is") else (val != expected)
        return content_if if is_true else content_else

    cond_pattern = re.compile(
        r"{%\s*if\s+([a-zA-Z0-9_]+)\s*(==|!=)\s*['\"]?([^%]+?)['\"]?\s*%}(.*?)(?:{%\s*else\s*%}(.*?))?{%\s*endif\s*%}",
        re.DOTALL,
    )
    texto = cond_pattern.sub(_eval_condition, texto)

    # 2. Reemplazo de variables {{ clave }}
    for k, v in context.items():
        pattern = re.compile(r"{{\s*" + re.escape(k) + r"\s*}}")
        texto = pattern.sub(str(v), texto)

    return texto


def generar_variantes(spec: MatrizSpec) -> List[Variante]:
    """Genera el producto cartesiano de todas las parametrizaciones declaradas."""
    keys = sorted(spec.parametrizaciones.keys())
    if not keys:
        # Sin parámetros: 1 sola variante base
        vals_list = [()]
    else:
        vals_list = list(itertools.product(*[spec.parametrizaciones[k] for k in keys]))

    variantes: List[Variante] = []
    for idx, vals in enumerate(vals_list):
        ctx: Dict[str, Any] = dict(zip(keys, vals, strict=False))
        ctx["titulo"] = spec.titulo
        ctx["ejercicio"] = spec.ejercicio
        ctx["variante_idx"] = idx
        ctx["variante_num"] = idx + 1

        var_id = f"{spec.ejercicio}_v{idx}"

        # Enunciado
        enunciado = render_template(spec.enunciado_template, ctx)

        # Solución
        sol_c = render_template(
            spec.solucion_template
            or (
                f"/* Solución modelo {var_id} */\n"
                "#include <stdio.h>\n\n"
                "int main(void) {\n"
                "    return 0;\n"
                "}\n"
            ),
            ctx,
        )

        # Starter / plantilla
        starter_c = render_template(
            spec.starter_template
            or (
                f"/* {spec.titulo} - Variante {idx+1} */\n"
                "#include <stdio.h>\n\n"
                "int main(void) {\n"
                "    /* TODO: Completá tu solución aquí */\n"
                "    return 0;\n"
                "}\n"
            ),
            ctx,
        )

        # Tests
        rendered_tests: List[Tuple[str, str]] = []
        for _t_idx, t in enumerate(spec.tests_template, 1):
            in_raw = t.get("in", t.get("entrada", ""))
            out_raw = t.get("out", t.get("salida", ""))
            rendered_tests.append((
                render_template(in_raw, ctx),
                render_template(out_raw, ctx),
            ))

        # Pistas
        rendered_pistas = [render_template(p, ctx) for p in spec.pistas_template]

        variantes.append(Variante(
            id=var_id,
            index=idx,
            parametros=ctx,
            enunciado_md=enunciado,
            solucion_c=sol_c,
            starter_c=starter_c,
            tests=rendered_tests,
            pistas=rendered_pistas,
        ))

    return variantes


def asignar_variante_determinista(alumno_id: str, ejercicio_id: str, total_variantes: int) -> int:
    """Asignación determinista por hash SHA-256 (estable y reproducible)."""
    if total_variantes <= 1:
        return 0
    token = f"{alumno_id.strip().lower()}:{ejercicio_id.strip().lower()}".encode("utf-8")
    digest = hashlib.sha256(token).hexdigest()
    return int(digest, 16) % total_variantes


def cargar_alumnos_csv(csv_path: Path) -> List[Alumno]:
    """Carga estudiantes desde un archivo CSV soportando múltiples encabezados estándar."""
    alumnos: List[Alumno] = []
    if not csv_path.is_file():
        raise FileNotFoundError(f"Archivo de alumnos inexistente: {csv_path}")

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []

        # Buscar nombres de columnas
        headers_lower = {h.strip().lower(): h for h in reader.fieldnames if h}

        id_key = (
            headers_lower.get("id")
            or headers_lower.get("username")
            or headers_lower.get("usuario")
            or headers_lower.get("padron")
            or headers_lower.get("legajo")
            or headers_lower.get("github")
            or headers_lower.get("student_id")
            or list(reader.fieldnames)[0]
        )

        nombre_key = (
            headers_lower.get("nombre")
            or headers_lower.get("name")
            or headers_lower.get("alumno")
            or headers_lower.get("estudiante")
        )

        email_key = (
            headers_lower.get("email")
            or headers_lower.get("correo")
            or headers_lower.get("mail")
        )

        for row in reader:
            val_id = (row.get(id_key) or "").strip()
            if not val_id:
                continue
            val_nombre = (row.get(nombre_key) or "").strip() if nombre_key else ""
            val_email = (row.get(email_key) or "").strip() if email_key else ""
            alumnos.append(Alumno(id=val_id, nombre=val_nombre, email=val_email))

    return alumnos


def materializar_variante_en_banco(variante: Variante, spec: MatrizSpec, base_dir: Path) -> Path:
    """Crea la estructura de directorio de ejercicio en disco para una variante."""
    dir_ej = base_dir / variante.id
    dir_ej.mkdir(parents=True, exist_ok=True)

    ej = Ejercicio(
        id=variante.id,
        titulo=f"{spec.titulo} (Variante {variante.index + 1})",
        tema=spec.tema,
        bloom=NivelBloom(spec.bloom),
        minutos_estimados=spec.minutos_estimados,
        enunciado_md=variante.enunciado_md,
        solucion_c=variante.solucion_c,
        pistas=variante.pistas,
        tags=[*spec.tags, f"variante:{variante.index}"],
    )
    guardar_ejercicio(ej, base_dir)

    # Testcases
    tests_dir = dir_ej / "tests"
    tests_dir.mkdir(exist_ok=True)
    for idx, (in_c, out_c) in enumerate(variante.tests, 1):
        (tests_dir / f"caso_{idx:02d}.in").write_text(in_c, encoding="utf-8")
        (tests_dir / f"caso_{idx:02d}.out").write_text(out_c, encoding="utf-8")

    return dir_ej


@dataclass
class ResultadoMultiplex:
    ejercicio: str
    total_variantes: int
    variantes: List[Variante]
    asignaciones: List[Asignacion] = field(default_factory=list)
    output_dir: Optional[Path] = None


def multiplexar_tp(
    matriz_path: Path,
    students_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    pack_ripkg: bool = True,
    generar_starters: bool = True,
) -> ResultadoMultiplex:
    """Ejecuta el pipeline completo de multiplexación combinatoria."""
    if not matriz_path.is_file():
        raise FileNotFoundError(f"Archivo de matriz inexistente: {matriz_path}")

    with open(matriz_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f) or {}

    spec = MatrizSpec.from_dict(raw_data)
    variantes = generar_variantes(spec)

    out_base = output_dir or (matriz_path.parent / "dist" / spec.ejercicio)
    out_base.mkdir(parents=True, exist_ok=True)

    banco_variantes = out_base / "banco_variantes"
    banco_variantes.mkdir(parents=True, exist_ok=True)

    # Materializar cada variante y opcionalmente empaquetar su .ripkg
    packs_variantes: Dict[int, Path] = {}
    for var in variantes:
        dir_ej = materializar_variante_en_banco(var, spec, banco_variantes)
        if pack_ripkg:
            res_pack = empaquetar_ejercicio(
                dir_ejercicio=dir_ej,
                out_path=out_base / "paquetes" / f"{var.id}.ripkg",
            )
            packs_variantes[var.index] = res_pack.output_path

    asignaciones: List[Asignacion] = []

    # Asignación de estudiantes si se provee CSV
    if students_path and students_path.is_file():
        alumnos = cargar_alumnos_csv(students_path)
        alumnos_dir = out_base / "alumnos"
        alumnos_dir.mkdir(parents=True, exist_ok=True)

        for al in alumnos:
            var_idx = asignar_variante_determinista(al.id, spec.ejercicio, len(variantes))
            var_elegida = variantes[var_idx]

            starter_path: Optional[Path] = None
            if generar_starters:
                st_dir = alumnos_dir / al.id
                st_dir.mkdir(parents=True, exist_ok=True)

                # Starter repo
                (st_dir / "README.md").write_text(var_elegida.enunciado_md, encoding="utf-8")
                (st_dir / "main.c").write_text(var_elegida.starter_c, encoding="utf-8")

                makefile_txt = (
                    "CC = gcc\n"
                    "CFLAGS = -std=c11 -Wall -Wextra -Werror -pedantic\n\n"
                    "all: main\n\n"
                    "main: main.c\n"
                    "\t$(CC) $(CFLAGS) main.c -o main\n\n"
                    "clean:\n"
                    "\trm -f main\n\n"
                    ".PHONY: all clean\n"
                )
                (st_dir / "Makefile").write_text(makefile_txt, encoding="utf-8")

                tests_dest = st_dir / "tests"
                tests_dest.mkdir(exist_ok=True)
                for idx, (in_c, out_c) in enumerate(var_elegida.tests, 1):
                    (tests_dest / f"caso_{idx:02d}.in").write_text(in_c, encoding="utf-8")
                    (tests_dest / f"caso_{idx:02d}.out").write_text(out_c, encoding="utf-8")

                starter_path = st_dir

            asignaciones.append(Asignacion(
                alumno=al,
                variante=var_elegida,
                ripkg_path=packs_variantes.get(var_idx),
                starter_path=starter_path,
            ))

        # Escribir asignaciones CSV y JSON
        asign_csv = out_base / "asignaciones.csv"
        with open(asign_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["alumno_id", "nombre", "email", "variante_id", "variante_idx", "parametros"])
            for asig in asignaciones:
                writer.writerow([
                    asig.alumno.id,
                    asig.alumno.nombre,
                    asig.alumno.email,
                    asig.variante.id,
                    asig.variante.index,
                    json.dumps(asig.variante.parametros, ensure_ascii=False),
                ])

        asign_json = out_base / "asignaciones.json"
        with open(asign_json, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "alumno_id": asig.alumno.id,
                        "nombre": asig.alumno.nombre,
                        "email": asig.alumno.email,
                        "variante_id": asig.variante.id,
                        "variante_idx": asig.variante.index,
                        "parametros": asig.variante.parametros,
                    }
                    for asig in asignaciones
                ],
                f,
                indent=2,
                ensure_ascii=False,
            )

    return ResultadoMultiplex(
        ejercicio=spec.ejercicio,
        total_variantes=len(variantes),
        variantes=variantes,
        asignaciones=asignaciones,
        output_dir=out_base,
    )
