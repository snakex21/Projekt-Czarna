from __future__ import annotations

from launcher.services import postgres_adapter_service as service


def test_postgres_adapter_accepts_config_dict(monkeypatch):
    calls = []

    monkeypatch.setattr(
        service,
        "_postgres_database_exists",
        lambda config, db_name: calls.append((config, db_name)) or True,
    )

    config = {"host": "localhost", "port": 5432, "user": "postgres", "password": "secret"}

    assert service.postgres_database_exists(config, "mapa_launcher_db") is True
    assert calls == [(config, "mapa_launcher_db")]


def test_postgres_adapter_accepts_legacy_host_port_user_password(monkeypatch):
    calls = []

    monkeypatch.setattr(
        service,
        "_postgres_database_exists",
        lambda config, db_name: calls.append((config, db_name)) or True,
    )

    assert service.postgres_database_exists(
        "localhost",
        5432,
        "postgres",
        "secret",
        "mapa_launcher_db",
    ) is True
    assert calls == [
        (
            {"host": "localhost", "port": 5432, "user": "postgres", "password": "secret"},
            "mapa_launcher_db",
        )
    ]


def test_postgres_adapter_accepts_keyword_config(monkeypatch):
    calls = []

    monkeypatch.setattr(
        service,
        "_postgres_execute_schema",
        lambda config, db_name, schema_sql: calls.append((config, db_name, schema_sql)) or (True, "ok"),
    )

    result = service.postgres_execute_schema(
        host="localhost",
        port=5432,
        user="postgres",
        password="secret",
        db_name="mapa_launcher_db",
        schema_sql="SELECT 1",
    )

    assert result == (True, "ok")
    assert calls == [
        (
            {"host": "localhost", "port": 5432, "user": "postgres", "password": "secret"},
            "mapa_launcher_db",
            "SELECT 1",
        )
    ]
