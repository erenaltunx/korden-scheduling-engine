"""Upgrade-proof invariants: history, checksums, schema, engine registry, data safety."""
from __future__ import annotations
import copy
import json
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from korden.model import validate_scenario
from korden.service import compare
from korden.storage import (
    StorageVersionError, backup_database, connect, get_experiment, list_experiments, save_experiment,
)
import korden.api as api

ROOT = Path(__file__).resolve().parent.parent


def example():
    return json.loads((ROOT / "samples" / "assembly_cell.json").read_text(encoding="utf-8"))


def test_legacy_scenario_is_supported_but_future_schema_is_rejected():
    old = example()
    old.pop("schema_version")
    assert validate_scenario(old) == old
    new = example()
    new["schema_version"] = 999
    with pytest.raises(ValueError, match="Unsupported scenario schema_version"):
        validate_scenario(new)


def test_unregistered_engine_is_rejected():
    with pytest.raises(ValueError, match="Unsupported optimizer engine"):
        compare(example(), 1, engine="import:untrusted")


def test_versioned_database_roundtrip_checksum_and_backup(tmp_path):
    db = tmp_path / "data" / "runs.sqlite3"
    scenario, result = example(), {"outcome": "validated", "score": 15}
    run_id = save_experiment(scenario, result, db)
    assert get_experiment(run_id, db)["result"] == result
    assert len(list_experiments(db_path=db)) == 1
    copy_path = backup_database(tmp_path / "backups" / "recovery.sqlite3", db)
    assert get_experiment(run_id, copy_path)["scenario"] == scenario
    with pytest.raises(FileExistsError):
        backup_database(copy_path, db)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE experiments SET result_json='{}' WHERE id=?", (run_id,))
    with pytest.raises(ValueError, match="checksum"):
        get_experiment(run_id, db)


def test_future_database_version_blocks_old_application(tmp_path):
    db = tmp_path / "future.sqlite3"
    with sqlite3.connect(db) as con:
        con.execute("PRAGMA user_version=55")
    with pytest.raises(StorageVersionError, match="newer"):
        connect(db)


def test_public_demo_never_archives_or_exposes_history(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "PUBLIC_DEMO", True)
    monkeypatch.setenv("KORDEN_DATA_DIR", str(tmp_path / "no-storage"))
    client = TestClient(api.app)
    result = client.post("/api/run", json={"scenario": example(), "time_limit": 2})
    assert result.status_code == 200
    assert result.json()["persisted"] is False
    assert client.get("/api/history").status_code == 404
    assert client.get("/api/history/" + "0" * 32).status_code == 404
    assert not (tmp_path / "no-storage").exists()


def test_local_api_keeps_run_history(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "PUBLIC_DEMO", False)
    monkeypatch.setenv("KORDEN_DATA_DIR", str(tmp_path))
    client = TestClient(api.app)
    response = client.post("/api/run", json={"scenario": example(), "time_limit": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted"] is True
    assert client.get("/api/history").json()[0]["id"] == payload["run_id"]
    detail = client.get("/api/history/" + payload["run_id"]).json()
    assert detail["result"]["optimized"]["metrics"]["weighted_tardiness"] == 15


def test_request_size_limit_and_web_security_headers():
    client = TestClient(api.app)
    response = client.post("/api/run", content=b"x" * (128 * 1024 + 1))
    assert response.status_code == 413
    page = client.get("/")
    assert "Content-Security-Policy" in page.headers
    assert page.headers["X-Content-Type-Options"] == "nosniff"
