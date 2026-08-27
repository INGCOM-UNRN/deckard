"""Caché SQLite para indexación y búsqueda ultrarrápida en bancos de ejercicios."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

import yaml

from deckard.core.models import Ejercicio, NivelBloom

CACHE_DIR_DEFAULT = Path.home() / ".cache" / "deckard"
CACHE_DB_DEFAULT = CACHE_DIR_DEFAULT / "index.db"


def get_cache_db_path(custom_path: Optional[Path] = None) -> Path:
    """Devuelve la ruta al archivo SQLite de caché."""
    if custom_path:
        return custom_path
    CACHE_DIR_DEFAULT.mkdir(parents=True, exist_ok=True)
    return CACHE_DB_DEFAULT


def init_cache_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Inicializa la base de datos de índice SQLite."""
    p = get_cache_db_path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exercises_index (
            id TEXT PRIMARY KEY,
            banco_root TEXT NOT NULL,
            rel_path TEXT NOT NULL,
            full_path TEXT NOT NULL,
            titulo TEXT NOT NULL,
            tema TEXT NOT NULL,
            bloom INTEGER NOT NULL,
            minutos INTEGER NOT NULL,
            tags TEXT NOT NULL,
            verificado INTEGER NOT NULL,
            mtime REAL NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_banco_root ON exercises_index(banco_root)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tema ON exercises_index(tema)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bloom ON exercises_index(bloom)")
    conn.commit()
    return conn


def index_exercise_file(
    conn: sqlite3.Connection,
    banco_root: Path,
    yaml_path: Path,
    data: dict,
    mtime: float,
) -> None:
    """Inserta o actualiza un ejercicio en el índice SQLite."""
    eid = data.get("id", yaml_path.parent.name)
    titulo = data.get("titulo", eid.replace("-", " ").title())
    tema = data.get("tema", "general")
    
    bloom_raw = data.get("bloom", 1)
    if isinstance(bloom_raw, int):
        bloom_val = bloom_raw
    elif isinstance(bloom_raw, str) and bloom_raw.isdigit():
        bloom_val = int(bloom_raw)
    else:
        try:
            bloom_val = NivelBloom[str(bloom_raw).upper()].value
        except Exception:
            bloom_val = 1

    minutos = int(data.get("minutos", 15))
    tags_list = data.get("tags", [])
    tags_str = ",".join(tags_list) if isinstance(tags_list, list) else str(tags_list)
    verificado = 1 if data.get("verificado", False) else 0
    rel_p = str(yaml_path.parent.relative_to(banco_root))
    full_p = str(yaml_path.parent.resolve())

    meta_json = json.dumps(data, ensure_ascii=False)

    conn.execute(
        """
        INSERT OR REPLACE INTO exercises_index 
        (id, banco_root, rel_path, full_path, titulo, tema, bloom, minutos, tags, verificado, mtime, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            eid,
            str(banco_root.resolve()),
            rel_p,
            full_p,
            titulo,
            tema,
            bloom_val,
            minutos,
            tags_str,
            verificado,
            mtime,
            meta_json,
        ),
    )


def update_bank_cache(
    dir_banco: Path,
    db_path: Optional[Path] = None,
    force: bool = False,
) -> int:
    """Escanea el banco e indexa únicamente los archivos con mtime modificado."""
    if not dir_banco.is_dir():
        return 0

    conn = init_cache_db(db_path)
    banco_str = str(dir_banco.resolve())

    # Obtener mtimes actuales en caché
    cur = conn.execute("SELECT id, full_path, mtime FROM exercises_index WHERE banco_root = ?", (banco_str,))
    cached_mtimes = {row[1]: (row[0], row[2]) for row in cur.fetchall()}

    yaml_files = sorted(dir_banco.rglob("ejercicio.yaml")) + sorted(dir_banco.rglob("ejercicio.yml"))
    seen_paths = set()
    indexed_count = 0

    for y_file in yaml_files:
        try:
            p_dir = str(y_file.parent.resolve())
            seen_paths.add(p_dir)
            mtime = y_file.stat().st_mtime

            if not force and p_dir in cached_mtimes and cached_mtimes[p_dir][1] == mtime:
                continue

            content = y_file.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                index_exercise_file(conn, dir_banco, y_file, data, mtime)
                indexed_count += 1
        except Exception:
            continue

    # Eliminar entradas de ejercicios borrados del disco
    for old_path in set(cached_mtimes.keys()) - seen_paths:
        conn.execute("DELETE FROM exercises_index WHERE full_path = ?", (old_path,))

    conn.commit()
    conn.close()
    return indexed_count


def search_cached_exercises(
    dir_banco: Path,
    patron: Optional[str] = None,
    tema: Optional[str] = None,
    bloom: Optional[int] = None,
    tag: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Optional[List[Tuple[Path, Ejercicio]]]:
    """Busca ejercicios utilizando el índice SQLite ultrarrápido."""
    try:
        conn = init_cache_db(db_path)
        banco_str = str(dir_banco.resolve())

        query = "SELECT full_path, metadata_json FROM exercises_index WHERE banco_root = ?"
        params: List[Any] = [banco_str]

        if tema:
            query += " AND LOWER(tema) = LOWER(?)"
            params.append(tema)

        if bloom is not None:
            query += " AND bloom = ?"
            params.append(bloom)

        if tag:
            query += " AND (',' || tags || ',') LIKE ?"
            params.append(f"%,{tag},%")

        if patron:
            query += " AND (id LIKE ? OR titulo LIKE ? OR tags LIKE ?)"
            pat_like = f"%{patron}%"
            params.extend([pat_like, pat_like, pat_like])

        query += " ORDER BY id"
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return None

        results = []
        for full_p, meta_json in rows:
            p = Path(full_p)
            try:
                data = json.loads(meta_json)
                ej = Ejercicio.model_validate(data)
                results.append((p, ej))
            except Exception:
                continue

        return results
    except Exception:
        return None
