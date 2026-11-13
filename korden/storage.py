"""Durable, versioned SQLite archive for local experiments.

The optimization engine remains entirely independent of persistence.
A database write is atomic; a failed archive write is reported, not silently ignored.
No user scenario is stored by the publicly hosted demonstration.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


class StorageVersionError(RuntimeError):
    """A newer database version needs a compatible application upgrade."""


def default_data_dir() -> Path:
    configured = os.getenv("KORDEN_DATA_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".korden"


def canonical_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else default_data_dir() / "experiments.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=15000")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        connection.close()
        raise StorageVersionError(f"Database version {version} is newer than supported {SCHEMA_VERSION}; refusing to modify it")
    if version == 0:
        # Explicit transaction makes both DDL and version marker atomic.
        connection.execute("BEGIN IMMEDIATE")
        with connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                scenario_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at)")
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    return connection


def save_experiment(scenario: dict, result: dict, db_path: Path | None = None) -> str:
    scenario_text = canonical_json(scenario)
    result_text = canonical_json(result)
    digest = hashlib.sha256((scenario_text + "\n" + result_text).encode("utf-8")).hexdigest()
    run_id = uuid.uuid4().hex
    con = connect(db_path)
    try:
        with con:
            con.execute("""INSERT INTO experiments
                (id, created_at, schema_version, scenario_json, result_json, payload_sha256)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, datetime.now(timezone.utc).isoformat(), SCHEMA_VERSION,
                 scenario_text, result_text, digest))
    finally:
        con.close()
    return run_id


def get_experiment(run_id: str, db_path: Path | None = None) -> dict | None:
    if not isinstance(run_id, str) or len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        return None
    con = connect(db_path)
    try:
        row = con.execute("SELECT * FROM experiments WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        digest = hashlib.sha256((row["scenario_json"] + "\n" + row["result_json"]).encode("utf-8")).hexdigest()
        if digest != row["payload_sha256"]:
            raise ValueError("Experiment checksum mismatch: stored record may be corrupted")
        return {"id": row["id"], "created_at": row["created_at"],
                "schema_version": row["schema_version"],
                "scenario": json.loads(row["scenario_json"]),
                "result": json.loads(row["result_json"])}
    finally:
        con.close()


def list_experiments(limit: int = 20, db_path: Path | None = None) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    con = connect(db_path)
    try:
        rows = con.execute("""SELECT id, created_at, schema_version, payload_sha256
                              FROM experiments ORDER BY created_at DESC LIMIT ?""", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def backup_database(destination: Path, db_path: Path | None = None) -> Path:
    """Use SQLite's consistent online backup API, refusing to overwrite an existing backup."""
    destination = Path(destination).expanduser()
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing backup: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = connect(db_path)
    try:
        # Exclusive create avoids accidental overwrite. Online backup captures concurrent WAL data.
        destination.touch(exist_ok=False)
        try:
            with sqlite3.connect(destination) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup integrity check failed")
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    finally:
        source.close()
    return destination
