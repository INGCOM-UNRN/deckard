"""Empaquetado de ejercicios y guías en formato .ripkg compatible con Ripley y starter repos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
from typing import Dict, List, Optional
import zipfile
import yaml

from deckard.core.bank import cargar_ejercicio, listar_ejercicios
from deckard.core.models import Ejercicio

MANIFEST_NAME = "manifest.toml"
SIGNATURE_NAME = "manifest.sig"
PAYLOAD_PREFIX = "payload/"
FORMAT_VERSION = 1

DEFAULT_CHECKS = [
    "compiler.warnings",
    "dynamic.testcases",
    "sanitizers.asan",
    "sanitizers.ubsan",
    "antipattern.malloc_cast",
    "antipattern.strlen_allocation",
    "antipattern.loop_control_mutation",
    "antipattern.god_function",
    "style.allman",
]

DEFAULT_COMPILER_FLAGS = [
    "-std=c11",
    "-Wall",
    "-Wextra",
    "-Werror",
    "-pedantic",
]


class PackError(Exception):
    """Error durante el empaquetado de un .ripkg o starter repo."""
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _q(k: str) -> str:
    return '"' + str(k).replace("\\", "\\\\").replace('"', '\\"') + '"'


def serialize_manifest(manifest: dict) -> bytes:
    """Serializa a TOML con claves entrecomilladas para preservar rutas y nombres con puntos."""
    def fmt(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list):
            inner = ", ".join(fmt(x) for x in v)
            return f"[{inner}]"
        if isinstance(v, dict):
            inline = ", ".join(f'{_q(k)} = {fmt(x)}' for k, x in sorted(v.items()))
            return "{ " + inline + " }"
        s = str(v).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    out: List[str] = []

    def emit(table: dict, prefix_parts: List[str]) -> None:
        for key, value in table.items():
            parts = [*prefix_parts, str(key)]
            if isinstance(value, dict):
                emit(value, parts)
            else:
                dotted = ".".join(_q(p) for p in parts)
                out.append(f"{dotted} = {fmt(value)}")

    emit(manifest, [])
    out.append("")
    return "\n".join(out).encode("utf-8")


def build_manifest(
    practica_slug: str,
    enabled_check_ids: List[str],
    compiler_executable: str,
    compiler_flags: List[str],
    payload_files: Dict[str, bytes],
    makefile_cfg: Optional[dict] = None,
    tipo_entrega: str = "archivos_individuales",
) -> dict:
    """Construye el manifiesto con los metadatos y hashes de integridad SHA-256."""
    manifest = {
        "meta": {
            "format_version": FORMAT_VERSION,
            "practica": practica_slug,
            "tipo_entrega": tipo_entrega,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "tipo_entrega": tipo_entrega,
        "checks": {cid: True for cid in sorted(enabled_check_ids)},
        "compiler": {
            "executable": compiler_executable,
            "flags": list(compiler_flags),
        },
        "integrity": {
            "unsigned": True,
            "sha256": {name: _sha256(payload_files[name]) for name in sorted(payload_files)},
        },
    }
    if makefile_cfg:
        manifest["makefile"] = dict(makefile_cfg)
    return manifest


def write_bundle(
    output_path: Path,
    manifest: dict,
    payload_files: Dict[str, bytes],
    sign_key: Optional[str] = None,
) -> Path:
    """Escribe el archivo .ripkg como un ZIP con manifest.toml y payload/."""
    manifest_bytes = serialize_manifest(manifest)
    signature_bytes: Optional[bytes] = None

    if sign_key:
        gpg = shutil.which("gpg")
        if not gpg:
            raise PackError("gpg no está disponible en el sistema para firmar el paquete.")
        with tempfile.TemporaryDirectory() as td:
            m_path = Path(td) / MANIFEST_NAME
            s_path = Path(td) / SIGNATURE_NAME
            m_path.write_bytes(manifest_bytes)
            proc = subprocess.run(
                [
                    gpg, "--batch", "--yes", "--detach-sign", "--local-user", sign_key,
                    "--output", str(s_path), str(m_path)
                ],
                capture_output=True,
                timeout=30,
            )
            if proc.returncode != 0:
                raise PackError(f"Firma GPG fallida: {proc.stderr.decode(errors='replace')[:200]}")
            signature_bytes = s_path.read_bytes()
            manifest.setdefault("integrity", {})["unsigned"] = False
            manifest_bytes = serialize_manifest(manifest)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, manifest_bytes)
        if signature_bytes is not None:
            zf.writestr(SIGNATURE_NAME, signature_bytes)
        for name, data in payload_files.items():
            safe = f"{PAYLOAD_PREFIX}{name}"
            if safe.startswith("/") or ".." in Path(safe).parts:
                raise PackError(f"Nombre de archivo inseguro en payload: {name}")
            zf.writestr(safe, data)
    return out


@dataclass
class ResultadoEmpaquetado:
    output_path: Path
    checks_habilitados: int
    archivos_payload: int
    firmado: bool
    starter_path: Optional[Path] = None


def empaquetar_ejercicio(
    dir_ejercicio: Path,
    out_path: Optional[Path] = None,
    compiler_flags: Optional[List[str]] = None,
    enabled_checks: Optional[List[str]] = None,
    sign_key: Optional[str] = None,
    generar_starter: bool = False,
    starter_out_dir: Optional[Path] = None,
) -> ResultadoEmpaquetado:
    """Empaqueta un ejercicio individual como .ripkg compatible con Ripley."""
    if not dir_ejercicio.is_dir():
        raise PackError(f"Directorio de ejercicio inexistente: {dir_ejercicio}")

    ejercicio = cargar_ejercicio(dir_ejercicio)
    flags = compiler_flags or DEFAULT_COMPILER_FLAGS
    checks = enabled_checks or DEFAULT_CHECKS

    payload: Dict[str, bytes] = {}

    # 1. Enunciado
    if ejercicio.enunciado_md:
        payload["enunciado.md"] = ejercicio.enunciado_md.encode("utf-8")
        payload["README.md"] = ejercicio.enunciado_md.encode("utf-8")

    # 2. Pistas progresivas si existen
    if ejercicio.pistas:
        texto_pistas = "\n".join(f"{i}. {p}" for i, p in enumerate(ejercicio.pistas, 1))
        payload["pistas.txt"] = texto_pistas.encode("utf-8")

    # 3. Cabecera C si existen funciones declaradas
    if ejercicio.funciones:
        header_content = ejercicio.generar_cabecera_c().encode("utf-8")
        payload[f"{ejercicio.id}.h"] = header_content
        payload["ejercicio.h"] = header_content

    # 4. Testcases y recursos
    tests_dir = dir_ejercicio / "tests"
    if tests_dir.is_dir():
        for f in sorted(tests_dir.rglob("*")):
            if f.is_file():
                rel_name = str(f.relative_to(tests_dir))
                payload[rel_name] = f.read_bytes()

    # 5. Manifiesto y bundle .ripkg
    manifest = build_manifest(
        practica_slug=ejercicio.id,
        enabled_check_ids=checks,
        compiler_executable="gcc",
        compiler_flags=flags,
        payload_files=payload,
        tipo_entrega=ejercicio.tipo_entrega,
    )

    destino = out_path or (dir_ejercicio.parent / f"{ejercicio.id}.ripkg")
    write_bundle(destino, manifest, payload, sign_key=sign_key)

    starter_path: Optional[Path] = None
    if generar_starter:
        s_dir = starter_out_dir or (destino.parent / f"starter_{ejercicio.id}")
        starter_path = exportar_starter_repo(ejercicio, s_dir, tests_dir if tests_dir.is_dir() else None)

    return ResultadoEmpaquetado(
        output_path=destino,
        checks_habilitados=len(manifest["checks"]),
        archivos_payload=len(payload),
        firmado=bool(sign_key),
        starter_path=starter_path,
    )


def exportar_starter_repo(
    ejercicio: Ejercicio | Path,
    destino: Path,
    tests_dir: Optional[Path] = None,
) -> Path:
    """Genera la estructura de un starter repo para GitHub Classroom."""
    if isinstance(ejercicio, Path):
        ej = cargar_ejercicio(ejercicio)
        if tests_dir is None and (ejercicio / "tests").is_dir():
            tests_dir = ejercicio / "tests"
    else:
        ej = ejercicio

    destino.mkdir(parents=True, exist_ok=True)

    # 1. README.md con consigna
    readme_content = f"# {ej.titulo}\n\n{ej.enunciado_md}\n"
    if ej.funciones:
        readme_content += "\n## Funciones a Implementar\n"
        for fn in ej.funciones:
            readme_content += f"- `{fn.firma}`\n"
    if ej.pistas:
        readme_content += "\n## Pistas\n"
        for i, p in enumerate(ej.pistas, 1):
            readme_content += f"{i}. {p}\n"
    readme_content += "\n## Verificación\n\nPodés verificar tu solución corriendo:\n```bash\nripley check .\n```\no usando `make test`.\n"
    (destino / "README.md").write_text(readme_content, encoding="utf-8")

    # 2. Archivos fuente / cabeceras
    if ej.funciones:
        (destino / f"{ej.id}.h").write_text(ej.generar_cabecera_c(), encoding="utf-8")
        main_c = ej.generar_esqueleto_c()
    else:
        main_c = (
            f"/* {ej.titulo} */\n"
            "#include <stdio.h>\n\n"
            "int main(void) {\n"
            "    /* TODO: implementá tu solución aquí */\n"
            "    return 0;\n"
            "}\n"
        )
    (destino / "main.c").write_text(main_c, encoding="utf-8")

    # 3. Makefile básico
    makefile = (
        "CC = gcc\n"
        "CFLAGS = -std=c11 -Wall -Wextra -Werror -pedantic\n\n"
        "all: main\n\n"
        "main: main.c\n"
        "\t$(CC) $(CFLAGS) main.c -o main\n\n"
        "clean:\n"
        "\trm -f main\n\n"
        ".PHONY: all clean\n"
    )
    (destino / "Makefile").write_text(makefile, encoding="utf-8")

    # 4. ripley.toml
    ripley_toml = (
        f'# Configuración de evaluación Ripley para {ej.id}\n'
        f'[meta]\n'
        f'practica = "{ej.id}"\n\n'
        f'[compiler]\n'
        f'executable = "gcc"\n'
        f'flags = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic"]\n\n'
        f'[checks]\n'
        f'compiler_warnings = true\n'
        f'testcases = true\n'
        f'asan = true\n'
        f'ubsan = true\n'
    )
    (destino / "ripley.toml").write_text(ripley_toml, encoding="utf-8")

    # 5. Copia testcases si existen
    if tests_dir and tests_dir.is_dir():
        dest_tests = destino / "tests"
        dest_tests.mkdir(exist_ok=True)
        for t in tests_dir.glob("*.in"):
            shutil.copy2(t, dest_tests / t.name)
        for t in tests_dir.glob("*.out"):
            shutil.copy2(t, dest_tests / t.name)

    return destino


def empaquetar_guia(
    guia_spec_file: Path,
    banco: Path,
    out_dir: Optional[Path] = None,
    sign_key: Optional[str] = None,
    generar_starter: bool = False,
) -> List[ResultadoEmpaquetado]:
    """Empaqueta todos los ejercicios referenciados en una guía YAML junto a su definición."""
    from deckard.core.bank import buscar_ejercicios
    from deckard.core.guides import resolver_ruta_guia

    ruta_yaml = resolver_ruta_guia(guia_spec_file)
    if not ruta_yaml.is_file():
        raise PackError(f"Archivo de guía inexistente: {guia_spec_file}")

    with open(ruta_yaml, "r", encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}

    ejercicios_spec = datos.get("ejercicios", [])
    if not ejercicios_spec:
        raise PackError(f"La guía {ruta_yaml} no contiene ejercicios.")

    # Si out_dir es explícito se usa; sino:
    # Si la guía ya está en su propia carpeta (guias/<nombre>/guia.yaml), la salida es esa misma carpeta.
    # Si es un archivo plano (guias/<nombre>.yaml), se crea guias/<nombre>/ y se guarda allí junto a guia.yaml.
    if out_dir:
        salida_base = Path(out_dir)
    else:
        if ruta_yaml.name in ("guia.yaml", "guia.yml"):
            salida_base = ruta_yaml.parent
        else:
            salida_base = ruta_yaml.parent / ruta_yaml.stem

    salida_base.mkdir(parents=True, exist_ok=True)

    # Asegurar que el YAML de la guía resida dentro del directorio junto a los paquetes .ripkg
    dest_yaml = salida_base / "guia.yaml"
    if ruta_yaml.resolve() != dest_yaml.resolve():
        shutil.copy2(ruta_yaml, dest_yaml)

    resultados: List[ResultadoEmpaquetado] = []
    for item in ejercicios_spec:
        eid = item.get("id") if isinstance(item, dict) else str(item)
        matches = buscar_ejercicios(banco, patron=eid, recursivo=True)
        if not matches:
            raise PackError(f"Ejercicio '{eid}' de la guía no encontrado en el banco {banco}.")
        dir_ej, _ = matches[0]

        dest_ripkg = salida_base / f"{eid}.ripkg"
        starter_dir = (salida_base / "starters" / eid) if generar_starter else None

        res = empaquetar_ejercicio(
            dir_ejercicio=dir_ej,
            out_path=dest_ripkg,
            sign_key=sign_key,
            generar_starter=generar_starter,
            starter_out_dir=starter_dir,
        )
        resultados.append(res)

    return resultados


def empaquetar_bundle_deckard(ruta_origen: Path, salida_tar: Optional[Path] = None) -> Path:
    """Empaqueta una carpeta de ejercicios o guía en un bundle .deckard.tar.gz."""
    import tarfile

    origen = Path(ruta_origen).resolve()
    if not origen.exists():
        raise PackError(f"Ruta de origen inexistente: {origen}")

    if salida_tar:
        dest = Path(salida_tar).resolve()
    else:
        dest = origen.parent / f"{origen.name}.deckard.tar.gz"

    dest.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(dest, "w:gz") as tar:
        if origen.is_dir():
            for item in origen.rglob("*"):
                if any(part.startswith(".") for part in item.parts):
                    continue
                arcname = item.relative_to(origen)
                tar.add(item, arcname=str(arcname))
        else:
            tar.add(origen, arcname=origen.name)

    return dest


def desempaquetar_bundle_deckard(tar_path: Path, destino_dir: Path) -> Path:
    """Extrae un bundle .deckard.tar.gz o .tar.gz en el directorio destino."""
    import tarfile

    src = Path(tar_path).resolve()
    if not src.is_file():
        raise PackError(f"Archivo de paquete inexistente: {src}")

    dest = Path(destino_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    with tarfile.open(src, "r:*") as tar:
        tar.extractall(path=dest)

    return dest


