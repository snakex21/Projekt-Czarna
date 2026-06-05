from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

from launcher.services import postgres_migration_service as service


def test_validate_postgres_config_accepts_valid_config():
    result = service.validate_postgres_config({
        "host": "localhost",
        "port": "5432",
        "user": "postgres",
        "password": "secret",
    })

    assert result.ok is True
    assert result.issues == []


def test_validate_postgres_config_rejects_empty_host_and_invalid_port():
    result = service.validate_postgres_config({
        "host": "",
        "port": "bad",
        "user": "",
        "password": "secret",
    })

    assert result.ok is False
    assert {issue.field for issue in result.issues} == {"host", "port", "user"}


def test_build_location_db_name_defaults_to_safe_name():
    assert service.build_location_db_name("Czarna") == "mapa_czarna_db"


def test_build_location_db_name_sanitizes_polish_and_spaced_name():
    assert service.build_location_db_name("Łęki Dolne") == "mapa_leki_dolne_db"


def test_ensure_location_database_returns_existing_without_create(monkeypatch):
    create_calls = []

    monkeypatch.setattr(service.postgres_db, "database_exists", lambda config, db_name: True)
    monkeypatch.setattr(service.postgres_db, "create_database", lambda config, db_name: create_calls.append(db_name))

    result = service.ensure_location_database(_config(), "mapa_czarna_db")

    assert result.ok is True
    assert result.details["created"] is False
    assert create_calls == []


def test_ensure_location_database_creates_when_missing(monkeypatch):
    monkeypatch.setattr(service.postgres_db, "database_exists", lambda config, db_name: False)
    monkeypatch.setattr(service.postgres_db, "create_database", lambda config, db_name: (True, f"created {db_name}"))

    result = service.ensure_location_database(_config(), "mapa_czarna_db")

    assert result.ok is True
    assert result.message == "created mapa_czarna_db"
    assert result.details["created"] is True


def test_ensure_location_database_fails_when_missing_and_create_disabled(monkeypatch):
    monkeypatch.setattr(service.postgres_db, "database_exists", lambda config, db_name: False)

    result = service.ensure_location_database(_config(), "mapa_czarna_db", create_if_missing=False)

    assert result.ok is False
    assert "nie istnieje" in result.message


def test_ensure_postgis_enabled_delegates_and_confirms(monkeypatch):
    calls = []

    def fake_enable(config, db_name):
        calls.append((config, db_name))
        return True, "enabled"

    monkeypatch.setattr(service.postgres_db, "enable_postgis", fake_enable)
    monkeypatch.setattr(service.postgres_db, "has_postgis_extension", lambda config, db_name: True)

    result = service.ensure_postgis_enabled(_config(), "mapa_czarna_db")

    assert result.ok is True
    assert calls[0][1] == "mapa_czarna_db"


def test_execute_location_schema_uses_location_schema(monkeypatch):
    captured = {}

    def fake_execute(config, db_name, schema_sql):
        captured["db_name"] = db_name
        captured["schema_sql"] = schema_sql
        return True, "schema ok"

    monkeypatch.setattr(service.postgres_db, "execute_schema", fake_execute)

    result = service.execute_location_schema(_config(), "mapa_czarna_db")

    assert result.ok is True
    assert captured["db_name"] == "mapa_czarna_db"
    assert "CREATE TABLE obiekty_geograficzne" in captured["schema_sql"]


def test_count_source_data_counts_json_and_deduplicates_objects(tmp_path, monkeypatch):
    location_dir = tmp_path / "Czarna"
    location_dir.mkdir()
    (location_dir / "owner_data_to_import.json").write_text(json.dumps({
        "Adam": {"realbuildingPlots": ["1"], "agriculturalPlots": [{"numerator": 2, "denominator": 3}], "houseNumber": "5"},
        "Ewa": {"realagriculturalPlots": ["4"]},
    }), encoding="utf-8")
    (location_dir / "parcels_data.json").write_text(json.dumps({
        "1_rolna": {"kategoria": "rolna"},
        "1_rolna_duplicate": {"kategoria": "rolna"},
        "2_budowlana": {"kategoria": "budowlana"},
    }), encoding="utf-8")
    (location_dir / "genealogia.json").write_text(json.dumps({"persons": [
        {"id": 1, "spouseIds": [2]},
        {"id": 2, "spouseIds": [1]},
    ]}), encoding="utf-8")
    (location_dir / "demografia.json").write_text(json.dumps([{"rok": 1880}]), encoding="utf-8")
    monkeypatch.setattr(service, "location_data_dir", lambda location_name: location_dir)

    counts = service.count_source_data("Czarna")

    assert counts.owners == 2
    assert counts.objects == 3
    assert counts.genealogy_persons == 2
    assert counts.demography_rows == 1
    assert counts.marriages == 1
    assert counts.parcel_owner_links == 4


def test_count_source_data_handles_missing_optional_files(tmp_path, monkeypatch):
    location_dir = tmp_path / "Czarna"
    location_dir.mkdir()
    (location_dir / "owner_data_to_import.json").write_text("{}", encoding="utf-8")
    (location_dir / "parcels_data.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(service, "location_data_dir", lambda location_name: location_dir)

    counts = service.count_source_data("Czarna")

    assert counts == service.DataCounts()


def test_count_target_data_queries_expected_tables(monkeypatch):
    executed = []
    values = iter([10, 20, 30, 40, 50, 60])

    class FakeCursor:
        def execute(self, sql):
            executed.append(sql)

        def fetchone(self):
            return [next(values)]

        def close(self):
            pass

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    fake_psycopg2 = SimpleNamespace(connect=lambda **kwargs: FakeConnection())
    monkeypatch.setitem(sys.modules, "psycopg2", fake_psycopg2)

    counts = service.count_target_data(_config(), "mapa_czarna_db")

    assert counts == service.DataCounts(10, 20, 30, 40, 50, 60)
    assert executed == [
        "SELECT COUNT(*) FROM wlasciciele",
        "SELECT COUNT(*) FROM obiekty_geograficzne",
        "SELECT COUNT(*) FROM osoby_genealogia",
        "SELECT COUNT(*) FROM dzialki_wlasciciele",
        "SELECT COUNT(*) FROM demografia",
        "SELECT COUNT(*) FROM malzenstwa",
    ]


def test_verify_migration_accepts_extra_objects_warning():
    result = service.verify_migration(
        service.DataCounts(owners=2, objects=2, genealogy_persons=1, parcel_owner_links=1),
        service.DataCounts(owners=2, objects=3, genealogy_persons=1, parcel_owner_links=5),
    )

    assert result.ok is True
    assert result.warnings


def test_verify_migration_rejects_owner_mismatch():
    result = service.verify_migration(
        service.DataCounts(owners=2, objects=2),
        service.DataCounts(owners=1, objects=2),
    )

    assert result.ok is False
    assert "Liczba właścicieli" in result.errors[0]


def test_run_json_to_postgres_migration_forces_postgresql_env(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend"
    scripts_dir = backend_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    script = scripts_dir / "migrate_data.py"
    script.write_text("# migration", encoding="utf-8")
    base_dir = tmp_path / "project"
    base_dir.mkdir()
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setenv("DB_ENGINE", "sqlite")
    monkeypatch.setattr(service, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(service, "BASE_DIR", base_dir)
    monkeypatch.setattr(service.subprocess, "run", fake_run)

    result = service.run_json_to_postgres_migration(_config(), "Czarna", "mapa_czarna_db")

    assert result.ok is True
    args, kwargs = calls[0]
    assert args == ([sys.executable, str(script), "Czarna"],)
    assert kwargs["cwd"] == str(base_dir)
    assert kwargs["env"]["DB_ENGINE"] == "postgresql"
    assert kwargs["env"]["DB_NAME"] == "mapa_czarna_db"


def test_run_json_to_postgres_migration_returns_failure_on_nonzero_exit(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend"
    scripts_dir = backend_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "migrate_data.py").write_text("# migration", encoding="utf-8")
    monkeypatch.setattr(service, "BACKEND_DIR", backend_dir)
    monkeypatch.setattr(service.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="boom"))

    result = service.run_json_to_postgres_migration(_config(), "Czarna", "mapa_czarna_db")

    assert result.ok is False
    assert result.message == "boom"


def test_update_backend_env_for_postgres_preserves_existing_content(tmp_path, monkeypatch):
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    env_path = backend_dir / ".env"
    env_path.write_text("# comment\nDB_ENGINE=sqlite\nFLASK_PORT=5000\n", encoding="utf-8")
    monkeypatch.setattr(service, "BACKEND_DIR", backend_dir)

    result = service.update_backend_env_for_postgres(_config(), "mapa_czarna_db")

    content = env_path.read_text(encoding="utf-8")
    assert result.ok is True
    assert "# comment" in content
    assert "DB_ENGINE=postgresql" in content
    assert "DB_NAME=mapa_czarna_db" in content
    assert "FLASK_PORT=5000" in content


def test_run_postgres_migration_wizard_does_not_switch_when_verification_fails(tmp_path, monkeypatch):
    calls = []
    location_dir = tmp_path / "locations" / "Czarna"
    location_dir.mkdir(parents=True)
    monkeypatch.setattr(service, "location_data_dir", lambda location_name: location_dir)
    monkeypatch.setattr(service, "test_postgres_connection", lambda config: service.StepResult("test_connection", True, "ok"))
    monkeypatch.setattr(service, "ensure_location_database", lambda config, db_name, create_if_missing=True: service.StepResult("ensure_database", True, "ok"))
    monkeypatch.setattr(service, "ensure_postgis_enabled", lambda config, db_name: service.StepResult("ensure_postgis", True, "ok"))
    monkeypatch.setattr(service, "execute_location_schema", lambda config, db_name: service.StepResult("execute_schema", True, "ok"))
    monkeypatch.setattr(service, "count_source_data", lambda location_name: service.DataCounts(owners=2, objects=1))
    monkeypatch.setattr(service, "run_json_to_postgres_migration", lambda *args, **kwargs: service.StepResult("run_migration", True, "ok"))
    monkeypatch.setattr(service, "count_target_data", lambda config, db_name: service.DataCounts(owners=1, objects=1))
    monkeypatch.setattr(service, "update_backend_env_for_postgres", lambda *args, **kwargs: calls.append("switch"))
    monkeypatch.setattr(service, "update_location_env_for_postgres", lambda *args, **kwargs: calls.append("location"))

    result = service.run_postgres_migration_wizard(_config(), service.MigrationOptions(location_name="Czarna"))

    assert result.ok is False
    assert calls == []


def test_run_postgres_migration_wizard_switches_only_after_success(tmp_path, monkeypatch):
    calls = []
    location_dir = tmp_path / "locations" / "Czarna"
    location_dir.mkdir(parents=True)
    monkeypatch.setattr(service, "location_data_dir", lambda location_name: location_dir)
    monkeypatch.setattr(service, "test_postgres_connection", lambda config: _step(calls, "test_connection"))
    monkeypatch.setattr(service, "ensure_location_database", lambda config, db_name, create_if_missing=True: _step(calls, "ensure_database"))
    monkeypatch.setattr(service, "ensure_postgis_enabled", lambda config, db_name: _step(calls, "ensure_postgis"))
    monkeypatch.setattr(service, "execute_location_schema", lambda config, db_name: _step(calls, "execute_schema"))
    monkeypatch.setattr(service, "count_source_data", lambda location_name: _counts(calls, "count_source"))
    monkeypatch.setattr(service, "run_json_to_postgres_migration", lambda *args, **kwargs: _step(calls, "run_migration"))
    monkeypatch.setattr(service, "count_target_data", lambda config, db_name: _counts(calls, "count_target"))
    monkeypatch.setattr(service, "update_location_env_for_postgres", lambda *args, **kwargs: _step(calls, "update_location_env"))
    monkeypatch.setattr(service, "update_backend_env_for_postgres", lambda *args, **kwargs: _step(calls, "switch_engine"))

    result = service.run_postgres_migration_wizard(_config(), service.MigrationOptions(location_name="Czarna"))

    assert result.ok is True
    assert calls == [
        "test_connection",
        "ensure_database",
        "ensure_postgis",
        "execute_schema",
        "count_source",
        "run_migration",
        "count_target",
        "update_location_env",
        "switch_engine",
    ]
    assert result.log_path and result.log_path.exists()


def _config():
    return service.PostgresConfig(host="localhost", port=5432, user="postgres", password="secret")


def _step(calls, name):
    calls.append(name)
    return service.StepResult(name, True, "ok")


def _counts(calls, name):
    calls.append(name)
    return service.DataCounts(owners=2, objects=1)
