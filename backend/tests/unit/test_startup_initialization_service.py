from __future__ import annotations

from launcher.services import startup_initialization_service as service


def test_auto_initialize_on_startup_skips_when_postgres_config_missing(tmp_path, monkeypatch):
    missing_config = tmp_path / ".postgres.env"
    monkeypatch.setattr(service, "POSTGRES_CONFIG_FILE", missing_config)

    result = service.auto_initialize_on_startup()

    assert result.skipped is True
    assert result.success is True
    assert "Brak pliku" in result.reason
    assert result.summary == {
        "created_launcher": False,
        "created_czarna_location": False,
        "created_czarna_db": False,
        "migrated_data": False,
    }


def test_auto_initialize_on_startup_skips_when_password_missing(tmp_path, monkeypatch):
    config_file = tmp_path / ".postgres.env"
    config_file.write_text("LAUNCHER_DB_HOST=localhost\n", encoding="utf-8")
    monkeypatch.setattr(service, "POSTGRES_CONFIG_FILE", config_file)
    monkeypatch.setattr(service, "get_postgres_config", lambda: {
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "",
    })

    result = service.auto_initialize_on_startup()

    assert result.skipped is True
    assert result.success is True
    assert "Brak hasła" in result.reason


def test_auto_initialize_on_startup_returns_existing_system_without_status_callback(tmp_path, monkeypatch):
    config_file = tmp_path / ".postgres.env"
    config_file.write_text("LAUNCHER_DB_PASSWORD=secret\n", encoding="utf-8")
    config = {
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
    }

    class FakeCursor:
        def execute(self, sql):
            pass

        def fetchone(self):
            return (1,)

        def close(self):
            pass

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(service, "POSTGRES_CONFIG_FILE", config_file)
    monkeypatch.setattr(service, "get_postgres_config", lambda: config)
    monkeypatch.setattr(service, "test_postgres_connection", lambda cfg: (True, "ok"))
    monkeypatch.setattr(service, "postgres_database_exists", lambda cfg, db_name: True)
    monkeypatch.setattr(service, "get_launcher_postgres_connection", lambda: FakeConnection())

    status_calls = []
    result = service.auto_initialize_on_startup(status_callback=lambda *args: status_calls.append(args))

    assert result.success is True
    assert result.skipped is False
    assert result.reason == "System już jest skonfigurowany"
    assert status_calls == []
