from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from launcher.services import location_migration_service as service


def test_migrate_location_data_sqlite_uses_import_sqlite_backup_script(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend"
    scripts_dir = backend_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    sqlite_script = scripts_dir / "import_sqlite_backup.py"
    sqlite_script.write_text("# test sqlite import script\n", encoding="utf-8")

    base_dir = tmp_path / "project"
    base_dir.mkdir()
    backup_folder = tmp_path / "data" / "locations" / "Czarna"
    backup_folder.mkdir(parents=True)

    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="sqlite ok", stderr="")

    monkeypatch.setattr(service, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(service, "BASE_DIR", base_dir)
    monkeypatch.setattr(service, "is_sqlite_mode", lambda: True)
    monkeypatch.setattr(service.subprocess, "run", fake_run)

    service.migrate_location_data(backup_folder, location_name="Czarna")

    assert len(calls) == 1
    args, kwargs = calls[0]
    expected_db_path = base_dir / "data" / "czarna.db"

    assert args == ([sys.executable, str(sqlite_script), "Czarna", str(expected_db_path)],)
    assert kwargs["cwd"] == str(base_dir)
    assert kwargs["timeout"] == 120


def test_migrate_location_data_postgresql_uses_migrate_data_script_and_infers_name(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend"
    scripts_dir = backend_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    migrate_script = scripts_dir / "migrate_data.py"
    migrate_script.write_text("# test pg migration script\n", encoding="utf-8")

    base_dir = tmp_path / "project"
    base_dir.mkdir()
    backup_folder = tmp_path / "data" / "locations" / "Testowa"
    backup_folder.mkdir(parents=True)

    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="pg ok", stderr="")

    monkeypatch.setattr(service, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(service, "BASE_DIR", base_dir)
    monkeypatch.setattr(service, "is_sqlite_mode", lambda: False)
    monkeypatch.setattr(service.subprocess, "run", fake_run)

    service.migrate_location_data(backup_folder)

    assert len(calls) == 1
    args, kwargs = calls[0]

    assert args == ([sys.executable, str(migrate_script), "Testowa"],)
    assert kwargs["cwd"] == str(base_dir)
    assert kwargs["timeout"] == 60


def test_calibrate_map_from_location_backup_returns_when_map_config_missing(tmp_path, monkeypatch, capsys):
    location_dir = tmp_path / "locations" / "Czarna"
    location_dir.mkdir(parents=True)

    def fail_connect(*args, **kwargs):
        raise AssertionError("psycopg2.connect must not be called without map_config.json")

    monkeypatch.setattr(service, "LOCATIONS_DATA_DIR", tmp_path / "locations")
    monkeypatch.setattr(service, "location_data_dir", lambda location_name: location_dir)
    monkeypatch.setattr(service.psycopg2, "connect", fail_connect)

    service.calibrate_map_from_location_backup(location_name="Czarna", db_name="czarna_db")

    assert "Brak pliku map_config.json" in capsys.readouterr().out


def test_calibrate_map_from_location_backup_saves_calibration_and_defaults_with_db_name(tmp_path, monkeypatch):
    location_dir = tmp_path / "locations" / "Czarna"
    location_dir.mkdir(parents=True)
    calibration = {"sw": [49.1, 21.1], "ne": [49.2, 21.2]}
    defaults = {"center": [49.15, 21.15], "zoom": 14}

    (location_dir / "map_config.json").write_text(
        json.dumps({"calibration": calibration, "defaults": defaults}),
        encoding="utf-8",
    )

    executed = []

    class FakeCursor:
        def execute(self, sql, params):
            executed.append((sql, params))

        def close(self):
            executed.append(("cursor.close", None))

    class FakeConnection:
        def __init__(self):
            self.committed = False
            self.closed = False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.committed = True

        def close(self):
            self.closed = True

    fake_connection = FakeConnection()
    connect_calls = []

    def fake_connect(**kwargs):
        connect_calls.append(kwargs)
        return fake_connection

    monkeypatch.setattr(service, "LOCATIONS_DATA_DIR", tmp_path / "locations")
    monkeypatch.setattr(service, "location_data_dir", lambda location_name: location_dir)
    monkeypatch.setattr(service, "get_postgres_config", lambda: {
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
    })
    monkeypatch.setattr(service.psycopg2, "connect", fake_connect)

    service.calibrate_map_from_location_backup(location_name="Czarna", db_name="czarna_db")

    assert connect_calls == [{
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
        "dbname": "czarna_db",
    }]
    assert len([item for item in executed if item[0] != "cursor.close"]) == 2
    assert "map_calibration" in executed[0][0]
    assert json.loads(executed[0][1][0]) == calibration
    assert "map_defaults" in executed[1][0]
    assert json.loads(executed[1][1][0]) == defaults
    assert fake_connection.committed is True
    assert fake_connection.closed is True


def test_create_and_migrate_location_database_passes_service_callbacks(monkeypatch):
    calls = []

    def fake_create_and_migrate_location_database(
        location_name,
        progress_callback=None,
        auto_migrate_data_function=None,
        auto_calibrate_map_from_backup=None,
    ):
        calls.append({
            "location_name": location_name,
            "progress_callback": progress_callback,
            "auto_migrate_data_function": auto_migrate_data_function,
            "auto_calibrate_map_from_backup": auto_calibrate_map_from_backup,
        })
        return "created"

    callback = object()
    monkeypatch.setattr(
        service.database_setup_service,
        "create_and_migrate_location_database",
        fake_create_and_migrate_location_database,
    )

    result = service.create_and_migrate_location_database("Czarna", progress_callback=callback)

    assert result == "created"
    assert calls == [{
        "location_name": "Czarna",
        "progress_callback": callback,
        "auto_migrate_data_function": service.auto_migrate_data_function,
        "auto_calibrate_map_from_backup": service.auto_calibrate_map_from_backup,
    }]
