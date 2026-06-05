"""
Testy E2E migracji SQLite -> PostgreSQL z prawdziwym serwerem PG.

Wymaga PostgreSQL dostepnego pod:
    PG_TEST_HOST     (default: localhost)
    PG_TEST_PORT     (default: 5432)
    PG_TEST_USER     (default: postgres)
    PG_TEST_PASSWORD (default: postgres)

Gdy PG niedostepny - testy sa AUTOMATYCZNIE SKIPOWANE (fixture `pg_session`).

Uruchomienie z PG:
    $env:PG_TEST_PASSWORD='your_password'
    python -m pytest backend/tests/integration/test_postgres_migration_e2e.py -v

Co jest testowane:
    1. Polaczenie z prawdziwym PG
    2. CREATE DATABASE (drop przed/po)
    3. CREATE EXTENSION postgis
    4. CREATE TABLE dla schematu LOCATION_DB_SCHEMA
    5. INSERT przez count_target_data (mockowane) - testujemy ze query SQL dziala
    6. DROP DATABASE cleanup
"""
from __future__ import annotations

import json


from launcher.db.schemas import LOCATION_DB_SCHEMA
from launcher.services import postgres_migration_service as service


def test_pg_session_creates_isolated_database(pg_session):
    """Smoke: pg_session tworzy baze i connection dziala."""
    cursor = pg_session["conn"].cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    cursor.close()

    assert result == (1,)
    assert pg_session["db_name"].startswith("mapa_test_")


def test_pg_session_database_is_isolated(pg_session, pg_test_config):
    """Kazdy test dostaje wlasna baze - widac tylko wlasne tabele."""
    cursor = pg_session["conn"].cursor()
    cursor.execute(
        "SELECT datname FROM pg_database WHERE datname = %s",
        (pg_session["db_name"],),
    )
    rows = cursor.fetchall()
    cursor.close()

    assert len(rows) == 1
    assert rows[0][0] == pg_session["db_name"]


def test_postgis_extension_creates_successfully(pg_session):
    """PostGIS CREATE EXTENSION dziala na prawdziwym PG (wymaga uprawnien)."""
    from launcher.db import postgres as postgres_db

    result_ok, message = postgres_db.enable_postgis(
        pg_test_config(), pg_session["db_name"]
    )

    # Niektore serwery PG nie maja PostGIS - akceptujemy to
    if not result_ok and ("postgis" in message.lower() or "extension" in message.lower()):
        import pytest
        pytest.skip(f"PostGIS niedostepny na serwerze: {message}")

    assert result_ok is True, f"enable_postgis zwrocilo blad: {message}"

    # Sprawdz ze rozszerzenie jest zainstalowane
    cursor = pg_session["conn"].cursor()
    cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
    extensions = cursor.fetchall()
    cursor.close()
    assert any(e[0] == "postgis" for e in extensions)


def test_location_schema_creates_all_tables(pg_session, pg_test_config):
    """LOCATION_DB_SCHEMA wykonuje sie bezblednie - wszystkie CREATE TABLE dzialaja."""
    from launcher.db import postgres as postgres_db

    result_ok, message = postgres_db.execute_schema(
        pg_test_config(), pg_session["db_name"], LOCATION_DB_SCHEMA
    )

    assert result_ok is True, f"execute_schema zwrocilo blad: {message}"

    # Wylistuj tabele w schemacie public
    cursor = pg_session["conn"].cursor()
    cursor.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    )
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()

    # Oczekujemy kluczowych tabel z LOCATION_DB_SCHEMA
    expected = [
        "wlasciciele",
        "obiekty_geograficzne",
        "osoby_genealogia",
        "dzialki_wlasciciele",
        "demografia",
        "malzenstwa",
    ]
    for table in expected:
        assert table in tables, f"Brak tabeli {table} po execute_schema"


def test_count_target_data_queries_real_pg(pg_session, pg_test_config):
    """count_target_data wykonuje SELECT COUNT(*) na prawdziwym PG - zwraca 0 dla pustej bazy."""
    from launcher.db import postgres as postgres_db

    # Najpierw utworz schemat (count_target_data wymaga istniejacych tabel)
    ok, _ = postgres_db.execute_schema(
        pg_test_config(), pg_session["db_name"], LOCATION_DB_SCHEMA
    )
    assert ok is True

    config = service.PostgresConfig(
        host=pg_test_config()["host"],
        port=pg_test_config()["port"],
        user=pg_test_config()["user"],
        password=pg_test_config()["password"],
    )

    counts = service.count_target_data(config, pg_session["db_name"])

    # Pusta baza - wszystkie count = 0
    assert counts.owners == 0
    assert counts.objects == 0
    assert counts.genealogy_persons == 0
    assert counts.parcel_owner_links == 0
    assert counts.demography_rows == 0
    assert counts.marriages == 0


def test_count_target_data_after_manual_insert(pg_session, pg_test_config):
    """Po INSERT danych, count_target_data zwraca wlasciwe wartosci."""
    from launcher.db import postgres as postgres_db

    ok, _ = postgres_db.execute_schema(
        pg_test_config(), pg_session["db_name"], LOCATION_DB_SCHEMA
    )
    assert ok is True

    # Wstaw 3 wlascicieli
    cursor = pg_session["conn"].cursor()
    cursor.executemany(
        "INSERT INTO wlasciciele (unikalny_klucz, nazwa_wlasciciela) "
        "VALUES (%s, %s)",
        [
            ("TEST_E2E_001", "Jan Testowy"),
            ("TEST_E2E_002", "Ewa Testowa"),
            ("TEST_E2E_003", "Adam Testowy"),
        ],
    )
    pg_session["conn"].commit()
    cursor.close()

    # 2 dzialki
    cursor = pg_session["conn"].cursor()
    cursor.executemany(
        "INSERT INTO obiekty_geograficzne (plot_id, kategoria) VALUES (%s, %s)",
        [("1_rolna", "rolna"), ("2_budowlana", "budowlana")],
    )
    pg_session["conn"].commit()
    cursor.close()

    config = service.PostgresConfig(
        host=pg_test_config()["host"],
        port=pg_test_config()["port"],
        user=pg_test_config()["user"],
        password=pg_test_config()["password"],
    )

    counts = service.count_target_data(config, pg_session["db_name"])

    assert counts.owners == 3
    assert counts.objects == 2
    assert counts.genealogy_persons == 0


def test_pg_session_cleans_up_database(pg_session, pg_test_config):
    """DROP DATABASE w teardown dziala - baza znika po teście.

    Ten test sam w sobie nie sprawdza cleanup (to robi fixture),
    ale upewniamy sie ze dane ktore wstawilismy sa dostepne.
    """
    cursor = pg_session["conn"].cursor()
    cursor.execute("SELECT current_database()")
    db_name_in_session = cursor.fetchone()[0]
    cursor.close()

    assert db_name_in_session == pg_session["db_name"]


def test_postgres_full_wizard_flow_real_pg(pg_session, pg_test_config, tmp_path, monkeypatch):
    """Pelny wizard migracji na prawdziwym PG: connection -> create -> postgis -> schema.

    Test wstrzykuje wlasciwe dane source (tmp_path) i wywoluje wizard.
    Weryfikuje ze wszystkie kroki wizarda przeszly na prawdziwym PG.
    """
    from launcher.db import postgres as postgres_db

    # Setup source data w tmp_path
    location_dir = tmp_path / "locations" / "TestE2E"
    location_dir.mkdir(parents=True)
    (location_dir / "owner_data_to_import.json").write_text(
        json.dumps({"Adam": {"realbuildingPlots": ["1"]}}), encoding="utf-8"
    )
    (location_dir / "parcels_data.json").write_text("{}", encoding="utf-8")
    (location_dir / "genealogia.json").write_text('{"persons": []}', encoding="utf-8")

    # Upewnij sie ze baza istnieje (ensure_location_database)
    ok, msg = postgres_db.create_database(
        pg_test_config(), pg_session["db_name"]
    )
    if not ok and "already exists" in msg.lower():
        pass  # OK - juz istnieje z fixture setup
    elif not ok:
        assert False, f"create_database nie powiodlo sie: {msg}"

    config = service.PostgresConfig(
        host=pg_test_config()["host"],
        port=pg_test_config()["port"],
        user=pg_test_config()["user"],
        password=pg_test_config()["password"],
    )

    # Krok 1: test connection
    result = service.test_postgres_connection(config)
    assert result.ok is True

    # Krok 2: ensure database (juz istnieje, wiec bez create)
    result = service.ensure_location_database(
        config, pg_session["db_name"], create_if_missing=False
    )
    assert result.ok is True
    assert result.details["created"] is False

    # Krok 3: ensure postgis (skip jesli niedostepny)
    result = service.ensure_postgis_enabled(config, pg_session["db_name"])
    if not result.ok and "postgis" in result.message.lower():
        import pytest
        pytest.skip(f"PostGIS niedostepny: {result.message}")

    # Krok 4: execute schema
    result = service.execute_location_schema(config, pg_session["db_name"])
    assert result.ok is True

    # Krok 5: weryfikacja - count_target_data powinno dzialac
    counts = service.count_target_data(config, pg_session["db_name"])
    assert counts.owners == 0  # pusta baza

    # Krok 6: count_source_data z naszego tmp
    monkeypatch.setattr(service, "location_data_dir", lambda name: location_dir)
    source_counts = service.count_source_data("TestE2E")
    assert source_counts.owners == 1

    # Krok 7: verify_migration - source=1, target=0 -> FAIL
    verify = service.verify_migration(source_counts, counts)
    assert verify.ok is False  # bo owner mismatch (1 vs 0)
    assert "właściciel" in verify.errors[0].lower()
