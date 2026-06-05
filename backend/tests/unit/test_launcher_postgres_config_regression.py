from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_postgresql_engine_reads_password_from_backend_env_when_postgres_env_missing(monkeypatch, tmp_path):
    """Launcher PG engine ma brać hasło z backend/.env, gdy .postgres.env brak."""
    from launcher.config import paths as launcher_paths
    from launcher.db import engine as db_engine

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / ".env").write_text(
        "DB_ENGINE=postgresql\n"
        "DB_HOST=localhost\n"
        "DB_PORT=5432\n"
        "DB_USER=postgres\n"
        "DB_PASSWORD=1234\n"
        "DB_NAME=mapa_czarna_db\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(launcher_paths, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(launcher_paths, "POSTGRES_CONFIG_FILE", backend_dir / ".postgres.env")
    monkeypatch.setattr(launcher_paths, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(launcher_paths, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(db_engine, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(db_engine, "_engine", None)
    for key in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)

    pg = db_engine.PostgreSQLEngine()
    config = pg.config

    assert config["host"] == "localhost"
    assert config["port"] == 5432
    assert config["user"] == "postgres"
    assert config["password"] == "1234"


def test_postgresql_engine_ignores_empty_postgres_env_password_fallbacks_to_backend_env(monkeypatch, tmp_path):
    """Puste LAUNCHER_DB_PASSWORD nie może nadpisać dobrego DB_PASSWORD."""
    from launcher.config import paths as launcher_paths
    from launcher.db import engine as db_engine

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / ".env").write_text(
        "DB_ENGINE=postgresql\nDB_PASSWORD=1234\nDB_PORT=5432\n",
        encoding="utf-8",
    )
    postgres_env = backend_dir / ".postgres.env"
    postgres_env.write_text(
        "LAUNCHER_DB_HOST=localhost\n"
        "LAUNCHER_DB_PORT=5432\n"
        "LAUNCHER_DB_USER=postgres\n"
        "LAUNCHER_DB_PASSWORD=\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(launcher_paths, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(db_engine, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(launcher_paths, "POSTGRES_CONFIG_FILE", postgres_env)
    for key in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)

    config = db_engine.PostgreSQLEngine().config

    assert config["password"] == "1234"


def test_get_data_files_does_not_crash_when_active_location_lookup_fails(monkeypatch):
    """UI import nie może crashować, gdy PG config jest niepełny przy starcie."""
    from launcher.utils import data_files

    monkeypatch.setattr(
        data_files,
        "get_active_location_name",
        lambda: (_ for _ in ()).throw(RuntimeError("fe_sendauth: no password supplied")),
    )

    result = data_files.get_data_files()

    assert set(result) == {"owners", "parcels", "genealogy"}
    assert "owner_data_to_import.json" in result["owners"]["path"]


def test_env_watcher_does_not_crash_when_postgres_location_lookup_fails(tmp_path):
    """Watcher .env nie może crashować, gdy PG padnie podczas pracy launchera."""
    from launcher.services import env_watcher_service

    def broken_location_env_path():
        raise RuntimeError("connection refused")

    assert env_watcher_service.get_env_mtime(False, str(tmp_path), broken_location_env_path) is None
