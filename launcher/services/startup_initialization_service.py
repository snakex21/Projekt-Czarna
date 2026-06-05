"""Automatyczna inicjalizacja systemu przy starcie launchera.

Moduł nie importuje Tkintera ani warstwy ``launcher.ui``. UI przekazuje
opcjonalny callback statusu, a serwis zwraca jawny wynik inicjalizacji.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import traceback

import psycopg2

from launcher.config.paths import BACKUP_FOLDER, POSTGRES_CONFIG_FILE
from launcher.db.postgres import (
    create_database as postgres_create_database,
    database_exists as postgres_database_exists,
    enable_postgis as postgres_enable_postgis,
    execute_schema as postgres_execute_schema,
    get_launcher_postgres_connection,
    get_postgres_config,
    test_connection as test_postgres_connection,
)
from launcher.db.schemas import LAUNCHER_DB_SCHEMA
from launcher.services.location_migration_service import (
    auto_calibrate_map_from_backup,
    auto_migrate_data_function,
)
from launcher.services.location_service import add_location, load_default_location_config
from launcher.services.system_diagnostics import init_location_database


@dataclass
class StartupInitializationResult:
    skipped: bool = False
    success: bool = True
    reason: str = ""
    created_launcher: bool = False
    created_czarna_location: bool = False
    created_czarna_db: bool = False
    migrated_data: bool = False
    error: str = ""
    summary: dict = field(default_factory=dict)


def _notify(status_callback, status, detail=""):
    if status_callback:
        status_callback(status, detail)


def _build_summary(result: StartupInitializationResult) -> dict:
    return {
        "created_launcher": result.created_launcher,
        "created_czarna_location": result.created_czarna_location,
        "created_czarna_db": result.created_czarna_db,
        "migrated_data": result.migrated_data,
    }


def _finish(result: StartupInitializationResult) -> StartupInitializationResult:
    result.summary = _build_summary(result)
    return result


def auto_initialize_on_startup(status_callback=None) -> StartupInitializationResult:
    """Wykonuje automatyczną inicjalizację baz i danych przy starcie."""
    if not POSTGRES_CONFIG_FILE.exists():
        print("⚠️ Brak pliku .postgres.env")
        return _finish(StartupInitializationResult(skipped=True, reason="Brak pliku .postgres.env"))

    config = get_postgres_config()
    if not config.get("password"):
        print("⚠️ Brak hasła w konfiguracji")
        return _finish(StartupInitializationResult(skipped=True, reason="Brak hasła w konfiguracji"))

    try:
        success, msg = test_postgres_connection(config)
        if not success:
            print(f"⚠️ Nie można połączyć się z PostgreSQL: {msg}")
            return _finish(StartupInitializationResult(skipped=True, reason=msg))

        needs_work = False
        db_exists = postgres_database_exists(config, "mapa_launcher_db")
        if not db_exists:
            needs_work = True
        else:
            try:
                conn = get_launcher_postgres_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM locations WHERE name = 'Czarna'")
                czarna_exists = cursor.fetchone()[0] > 0
                cursor.close()
                conn.close()
                if not czarna_exists:
                    needs_work = True
            except Exception:
                needs_work = True

            czarna_db_exists = postgres_database_exists(config, "mapa_czarna_db")
            if not czarna_db_exists:
                needs_work = True

        if not needs_work:
            print("ℹ️ System już jest skonfigurowany")
            return _finish(StartupInitializationResult(reason="System już jest skonfigurowany"))

    except Exception as e:
        print(f"⚠️ Błąd sprawdzania: {e}")
        return _finish(StartupInitializationResult(skipped=True, success=False, error=str(e)))

    result = StartupInitializationResult()

    try:
        _notify(status_callback, "Sprawdzanie baz danych...", "Łączenie z PostgreSQL")
        print("✅ PostgreSQL dostępny, sprawdzam bazy...")

        db_exists = postgres_database_exists(config, "mapa_launcher_db")
        if not db_exists:
            _notify(status_callback, "Tworzenie bazy mapa_launcher_db...", "Konfiguracja PostgreSQL")
            print("📦 Tworzę bazę mapa_launcher_db...")
            success_db, msg_db = postgres_create_database(config, "mapa_launcher_db")
            if not success_db:
                print(f"❌ Błąd tworzenia bazy launcher: {msg_db}")
                result.success = False
                result.error = msg_db
                return _finish(result)
            result.created_launcher = True
            print("✅ Baza mapa_launcher_db utworzona")

        _notify(status_callback, "Konfiguracja PostGIS...", "Rozszerzenia przestrzenne")
        postgres_enable_postgis(config, "mapa_launcher_db")

        postgres_execute_schema(config, "mapa_launcher_db", LAUNCHER_DB_SCHEMA)

        try:
            conn = get_launcher_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM locations WHERE name = 'Czarna'")
            czarna_exists = cursor.fetchone()[0] > 0
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"⚠️ Nie można sprawdzić miejscowości: {e}")
            czarna_exists = False

        if not czarna_exists:
            _notify(status_callback, "Tworzenie miejscowości 'Czarna'...", "Domyślna lokalizacja")
            print("📍 Tworzę domyślną miejscowość 'Czarna'...")

            default_loc = load_default_location_config()
            add_location(
                name=default_loc.get("name", "Czarna"),
                full_name=default_loc.get("full_name", "Czarna"),
                powiat=default_loc.get("powiat", ""),
                region=default_loc.get("region", ""),
                homepage_template=default_loc.get("homepage_template", "standardowy"),
                year=default_loc.get("year", "1882"),
                century=default_loc.get("century", "XIX w."),
                homepage_description=default_loc.get("homepage_description", ""),
                history_paragraph1=default_loc.get("history_paragraph1", ""),
                history_paragraph2=default_loc.get("history_paragraph2", ""),
                history_paragraph3=default_loc.get("history_paragraph3", ""),
                history_photos=default_loc.get("history_photos", []),
                postgres_db_name=default_loc.get("postgres_db_name", "mapa_czarna_db"),
                gmina_katastralna=default_loc.get("gmina_katastralna", "Czarna"),
                jewish_protocol_numbers=default_loc.get("jewish_protocol_numbers", ""),
                custom_icon=default_loc.get("custom_icon", "custom_icon.png"),
            )
            print("✅ Wczytano konfigurację z launcher_db_config.json")
            result.created_czarna_location = True

            conn = get_launcher_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE locations SET active = TRUE WHERE name = 'Czarna'")
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ Miejscowość 'Czarna' utworzona i ustawiona jako aktywna")

        czarna_db_exists = postgres_database_exists(config, "mapa_czarna_db")
        if not czarna_db_exists:
            _notify(status_callback, "Tworzenie bazy mapa_czarna_db...", "Baza danych dla miejscowości")
            print("📦 Tworzę bazę mapa_czarna_db...")
            success_db, msg_db = init_location_database("mapa_czarna_db")
            if success_db:
                result.created_czarna_db = True
                print("✅ Baza mapa_czarna_db utworzona")
            else:
                print(f"⚠️ Błąd tworzenia bazy mapa_czarna_db: {msg_db}")

        backup_czarna = BACKUP_FOLDER / "Czarna"
        if backup_czarna.exists():
            try:
                conn = psycopg2.connect(
                    host=config["host"],
                    port=config["port"],
                    user=config["user"],
                    password=config["password"],
                    dbname="mapa_czarna_db",
                )
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM wlasciciele")
                count = cursor.fetchone()[0]
                cursor.close()
                conn.close()

                if count == 0:
                    _notify(status_callback, "Migracja danych...", "Import z backup/Czarna - to może potrwać chwilę")
                    print("🔄  Automatyczna migracja danych z backup/Czarna...")
                    auto_migrate_data_function(str(backup_czarna), "Czarna")
                    result.migrated_data = True

                    _notify(status_callback, "Kalibracja mapy...", "Wczytywanie konfiguracji z backup")
                    auto_calibrate_map_from_backup()
                else:
                    print(f"ℹ️ Baza mapa_czarna_db już zawiera dane ({count} właścicieli)")
            except Exception as e:
                print(f"⚠️ Nie można sprawdzić danych w bazie: {e}")

        if result.created_czarna_db and not result.migrated_data:
            _notify(status_callback, "Kalibracja mapy...", "Wczytywanie konfiguracji z backup")
            auto_calibrate_map_from_backup()

        print("✅ Automatyczna inicjalizacja zakończona pomyślnie")
        return _finish(result)

    except Exception as e:
        print(f"⚠️ Błąd podczas automatycznej inicjalizacji: {e}")
        traceback.print_exc()
        result.success = False
        result.error = str(e)
        return _finish(result)
