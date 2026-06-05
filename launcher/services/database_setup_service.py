"""Operacje przygotowania i migracji baz danych miejscowości."""

from __future__ import annotations

from typing import Tuple

import psycopg2

from launcher.config.paths import POSTGRES_CONFIG_FILE, location_data_dir
from launcher.db.postgres import (
    create_database as postgres_create_database,
    enable_postgis as postgres_enable_postgis,
    execute_schema as postgres_execute_schema,
    get_launcher_postgres_connection,
    get_postgres_config,
    database_exists as postgres_database_exists,
)
from launcher.db.schemas import LOCATION_DB_SCHEMA, LAUNCHER_DB_SCHEMA


def postgres_config_exists() -> bool:
    """Sprawdza czy istnieje plik konfiguracji PostgreSQL launchera."""
    return POSTGRES_CONFIG_FILE.exists()


def ensure_sqlite_postgres_placeholder() -> None:
    """Tworzy placeholder .postgres.env dla trybu SQLite, jeśli go nie ma."""
    if POSTGRES_CONFIG_FILE.exists():
        return
    POSTGRES_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POSTGRES_CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("# SQLite mode - PostgreSQL not configured\n")
        f.write("DB_ENGINE=sqlite\n")


def test_postgres_connection_values(host: str, port: int, user: str, password: str) -> None:
    """Testuje bezpośrednie połączenie do serwera PostgreSQL."""
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        connect_timeout=3,
    )
    conn.close()


def save_launcher_postgres_config(host: str, port: int, user: str, password: str) -> None:
    """Zapisuje konfigurację połączenia PostgreSQL launchera."""
    config_content = f"""# =============================================================================
# KONFIGURACJA BAZY DANYCH POSTGRESQL DLA LAUNCHERA
# =============================================================================
LAUNCHER_DB_HOST={host}
LAUNCHER_DB_PORT={port}
LAUNCHER_DB_USER={user}
LAUNCHER_DB_PASSWORD={password}
"""
    POSTGRES_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POSTGRES_CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(config_content)
    print(f"✅ Utworzono plik konfiguracji: {POSTGRES_CONFIG_FILE}")


def ensure_postgres_database_with_postgis(
    host: str,
    port: int,
    user: str,
    password: str,
    db_name: str,
    schema_sql: str = LAUNCHER_DB_SCHEMA,
) -> Tuple[bool, str]:
    """Testuje połączenie i zapewnia istnienie bazy z PostGIS + schematem.

    Kolejność operacji (2026-06-05):
        1. Test połączenia (krótki timeout) — jeśli serwer nieosiągalny, przerwij
        2. Sprawdź czy baza istnieje
        3. Jeśli nie → utwórz
        4. Włącz PostGIS (idempotentne — jeśli już jest, zwraca "już istnieje")
        5. Zastosuj schemat (idempotentne — CREATE TABLE IF NOT EXISTS w schemacie)

    Używane w dialogu "Połącz z istniejącym PostgreSQL" po pierwszym
    uruchomieniu launchera, żeby user nie musiał ręcznie:
    - tworzyć bazy
    - włączać PostGIS
    - ładować schematu

    Args:
        host/port/user/password: parametry połączenia.
        db_name: nazwa bazy do utworzenia/zweryfikowania.
        schema_sql: treść schematu SQL (domyślnie LAUNCHER_DB_SCHEMA).

    Returns:
        (success: bool, message: str) — komunikat dla UI.
    """
    # 1. Test połączenia (krótki timeout, żeby nie zawiesić UI)
    try:
        test_postgres_connection_values(host, port, user, password)
    except Exception as exc:
        return False, f"Nie można połączyć się z {user}@{host}:{port}: {exc}"

    # 2-5. Operacje na bazie przez psycopg2
    config = {"host": host, "port": port, "user": user, "password": password}
    try:
        # 2+3. Sprawdź / utwórz bazę
        if not postgres_database_exists(config, db_name):
            ok, msg = postgres_create_database(config, db_name)
            if not ok:
                return False, f"Baza '{db_name}': {msg}"
        # 4. Włącz PostGIS (idempotentne)
        ok, msg = postgres_enable_postgis(config, db_name)
        if not ok:
            return False, f"PostGIS w '{db_name}': {msg}"
        # 5. Zastosuj schemat (idempotentne jeśli CREATE IF NOT EXISTS)
        ok, msg = postgres_execute_schema(config, db_name, schema_sql)
        if not ok:
            return False, f"Schemat w '{db_name}': {msg}"
    except Exception as exc:
        return False, f"Błąd konfiguracji bazy '{db_name}': {exc}"

    return True, f"Baza '{db_name}' jest gotowa (PostGIS włączony, schemat załadowany)"


def create_and_migrate_location_database(
    location_name,
    progress_callback=None,
    auto_migrate_data_function=None,
    auto_calibrate_map_from_backup=None,
):
    """Tworzy bazę danych dla miejscowości i migruje dane z data/locations."""
    try:
        config = get_postgres_config()
        if not config:
            return False, "Brak konfiguracji PostgreSQL"

        db_name = f"mapa_{location_name.lower()}"

        if progress_callback:
            progress_callback(f"📊 Tworzenie bazy danych: {db_name}")

        success, msg = postgres_create_database(config, db_name)
        if not success:
            return False, f"Błąd tworzenia bazy: {msg}"
        print(f"✅ {msg}")

        if progress_callback:
            progress_callback(f"🗺️ Włączanie PostGIS w bazie {db_name}")

        success, msg = postgres_enable_postgis(config, db_name)
        if not success:
            print(f"⚠️ Ostrzeżenie PostGIS: {msg}")
        else:
            print(f"✅ {msg}")

        if progress_callback:
            progress_callback(f"📋 Tworzenie tabel w bazie {db_name}")

        success, msg = postgres_execute_schema(config, db_name, LOCATION_DB_SCHEMA)
        if not success:
            return False, f"Błąd tworzenia tabel: {msg}"
        print(f"✅ {msg}")

        if progress_callback:
            progress_callback("💾 Zapisywanie nazwy bazy w konfiguracji")

        try:
            conn = get_launcher_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE locations
                SET postgres_db_name = %s
                WHERE name = %s
            """, (db_name, location_name))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"✅ Zapisano nazwę bazy danych: {db_name} dla {location_name}")
        except Exception as e:
            print(f"⚠️ Ostrzeżenie: Nie udało się zapisać nazwy bazy: {e}")

        location_folder = location_data_dir(location_name)
        env_path = location_folder / ".env"
        if location_folder.exists():
            env_content = f"""DB_HOST={config['host']}
DB_PORT={config['port']}
DB_NAME={db_name}
DB_USER={config['user']}
DB_PASSWORD={config['password']}
"""
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            print(f"✅ Zaktualizowano .env dla {location_name}")

        if progress_callback:
            progress_callback(f"🔄  Migracja danych z backup/{location_name}")

        print(f"🔄  Migracja danych dla miejscowości: {location_name}")
        if auto_migrate_data_function is not None:
            auto_migrate_data_function(str(location_folder), location_name)

        if progress_callback:
            progress_callback("📍 Kalibracja mapy z map_config.json")

        if auto_calibrate_map_from_backup is not None:
            auto_calibrate_map_from_backup(location_name=location_name, db_name=db_name)

        return True, f"Baza {db_name} utworzona i dane zmigrowane pomyślnie"

    except Exception as e:
        return False, f"Błąd: {str(e)}"
