"""Seed danych demo: świeży klon ma pokazywać mapę z danymi.

Testy używają kopii commitowanych plików ``data/locations/Czarna/*.json``
w katalogu tymczasowym - nie dotykają bazy dewelopera.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from backend.services.demo_seed import database_is_empty, seed_if_empty

ROOT = Path(__file__).resolve().parents[3]
REPO_LOCATION = ROOT / "data" / "locations" / "Czarna"


@pytest.fixture
def demo_location(tmp_path):
    if not (REPO_LOCATION / "parcels_data.json").exists():
        pytest.skip("Brak commitowanych danych data/locations/Czarna")
    locations = tmp_path / "locations"
    target = locations / "Czarna"
    target.mkdir(parents=True)
    for name in ("parcels_data.json", "genealogia.json", "demografia.json", "map_config.json"):
        if (REPO_LOCATION / name).exists():
            shutil.copy2(REPO_LOCATION / name, target / name)
    return locations


def _count(db, table):
    with sqlite3.connect(db) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_seed_fills_empty_database(tmp_path, demo_location):
    db = tmp_path / "fresh.db"
    assert database_is_empty(db)
    result = seed_if_empty(db_path=db, location="Czarna", locations_dir=demo_location)
    assert result["status"] == "seeded"
    parcels = json.loads((demo_location / "Czarna" / "parcels_data.json").read_text(encoding="utf-8"))
    assert _count(db, "obiekty_geograficzne") == len(parcels)
    assert _count(db, "osoby_genealogia") > 0
    assert _count(db, "demografia") > 0
    assert not database_is_empty(db)


def test_seed_is_idempotent_without_force(tmp_path, demo_location):
    db = tmp_path / "fresh.db"
    seed_if_empty(db_path=db, location="Czarna", locations_dir=demo_location)
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO demografia (rok, opis) VALUES (2000, 'reczna edycja')")
    again = seed_if_empty(db_path=db, location="Czarna", locations_dir=demo_location)
    assert again["status"] == "skipped"
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM demografia WHERE opis='reczna edycja'").fetchone()[0] == 1


def test_seed_force_overwrites(tmp_path, demo_location):
    db = tmp_path / "fresh.db"
    seed_if_empty(db_path=db, location="Czarna", locations_dir=demo_location)
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO demografia (rok, opis) VALUES (2000, 'reczna edycja')")
    forced = seed_if_empty(db_path=db, location="Czarna", locations_dir=demo_location, force=True)
    assert forced["status"] == "seeded"
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM demografia WHERE opis='reczna edycja'").fetchone()[0] == 0


def test_seed_missing_location_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        seed_if_empty(db_path=tmp_path / "x.db", location="Nieistniejaca", locations_dir=tmp_path)


def test_seed_cli_then_api_returns_parcels(tmp_path, demo_location):
    """Ścieżka z README: seed skryptem, potem /api/dzialki zwraca dane."""
    db = tmp_path / "cli.db"
    env = {k: v for k, v in os.environ.items()}
    env.update(DB_ENGINE="sqlite", DB_PATH=str(db), BACKUP_DIR=str(demo_location),
               ACTIVE_LOCATION="Czarna", PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    out = subprocess.run(
        [sys.executable, "-m", "backend.scripts.seed_demo"], cwd=ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "Zasilono" in out.stdout
    second = subprocess.run(
        [sys.executable, "-m", "backend.scripts.seed_demo"], cwd=ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert second.returncode == 0 and "Pominięto" in second.stdout

    probe = (
        "from fastapi.testclient import TestClient; from backend.main import app\n"
        "with TestClient(app) as c:\n"
        "    r = c.get('/api/dzialki'); print('@@', r.status_code, len(r.json().get('features', r.json())))\n"
    )
    api = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, env=env,
                         capture_output=True, text=True, encoding="utf-8", timeout=120)
    line = [l for l in api.stdout.splitlines() if l.startswith("@@")]
    assert line, api.stdout + api.stderr
    _, status, count = line[-1].split()
    assert status == "200" and int(count) > 100
