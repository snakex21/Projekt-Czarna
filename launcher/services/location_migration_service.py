"""Serwis migracji danych i kalibracji map dla miejscowości.

Ten moduł celowo nie importuje warstwy UI. Funkcje zostały wydzielone
z ``launcher.ui.dialogs`` tak, aby ``backup_manager`` i ``launcher_app`` nie
musieli zależeć od dużego modułu dialogów dla operacji serwisowych.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import psycopg2

from launcher.config.paths import BACKEND_DIR, BASE_DIR, LOCATIONS_DATA_DIR, location_data_dir
from launcher.db.engine import get_engine
from launcher.db.postgres import get_postgres_config
from launcher.services import database_setup_service, location_service
from launcher.utils import get_db_config_from_env


def is_sqlite_mode() -> bool:
    """Zwraca aktualny tryb silnika DB bez utrwalania wartości globalnej."""
    return get_engine().name == "sqlite"


def migrate_location_data(backup_folder, location_name=None):
    """Migruje dane miejscowości z folderu ``data/locations/<name>``."""
    try:
        backup_path = Path(backup_folder)

        if not location_name:
            location_name = backup_path.name
            print(f"📍 Wykryta miejscowość: {location_name}")

        if is_sqlite_mode():
            sqlite_import = Path(BACKEND_DIR) / "scripts" / "import_sqlite_backup.py"
            if not sqlite_import.exists():
                print(f"⚠️ Brak skryptu SQLite: {sqlite_import}")
                return

            db_path = Path(BASE_DIR) / "data" / "czarna.db"
            print(f"🔄 Import danych z {backup_path} do SQLite ({db_path})...")
            result = subprocess.run(
                [sys.executable, str(sqlite_import), location_name, str(db_path)],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if result.returncode == 0:
                print("✅ Import SQLite zakończony pomyślnie")
                if result.stdout:
                    print(result.stdout)
            else:
                print("⚠️ Import SQLite zakończony z błędami:")
                if result.stderr:
                    print(result.stderr)
            return

        migrate_script = Path(BACKEND_DIR) / "scripts" / "migrate_data.py"
        if not migrate_script.exists():
            print(f"⚠️ Brak skryptu migracji: {migrate_script}")
            return

        print(f"🔄  Migracja danych z {backup_path}...")
        result = subprocess.run(
            [sys.executable, str(migrate_script), location_name],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )

        if result.returncode == 0:
            print("✅ Migracja zakończona pomyślnie")
            if result.stdout:
                print(result.stdout)
        else:
            print("⚠️ Migracja zakończona z błędami:")
            if result.stderr:
                print(result.stderr)

    except subprocess.TimeoutExpired:
        print("⚠️ Migracja przekroczyła limit czasu (60s)")
    except Exception as e:
        print(f"⚠️ Błąd podczas migracji: {e}")


def calibrate_map_from_location_backup(location_name=None, db_name=None):
    """Wczytuje kalibrację mapy z ``map_config.json`` i zapisuje ją do DB."""
    try:
        if not location_name:
            location_name = location_service.get_active_location_name()
        if not location_name:
            return

        map_config_path = location_data_dir(location_name) / "map_config.json"

        if not map_config_path.exists():
            try:
                rel_path = map_config_path.relative_to(LOCATIONS_DATA_DIR)
                print(f"ℹ️ Brak pliku map_config.json w backup/{rel_path.parent}")
            except ValueError:
                print(f"ℹ️ Brak pliku map_config.json w {map_config_path}")
            return

        with open(map_config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        calibration = config.get("calibration")
        defaults = config.get("defaults")

        if not calibration:
            print("⚠️ Brak danych kalibracji w map_config.json")
            return

        if db_name:
            pg_config = get_postgres_config()
            conn = psycopg2.connect(
                host=pg_config["host"],
                port=pg_config["port"],
                user=pg_config["user"],
                password=pg_config["password"],
                dbname=db_name,
            )
        else:
            db_config = get_db_config_from_env()
            conn = psycopg2.connect(**db_config)

        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES ('map_calibration', %s) "
                "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
                (json.dumps(calibration),),
            )

            if defaults:
                cur.execute(
                    "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES ('map_defaults', %s) "
                    "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
                    (json.dumps(defaults),),
                )

            conn.commit()
            cur.close()
        finally:
            conn.close()

        print(f"✅ Automatyczna kalibracja mapy z {map_config_path}")
        print(f"   SW: {calibration.get('sw')}, NE: {calibration.get('ne')}")

    except Exception as e:
        print(f"⚠️ Błąd podczas automatycznej kalibracji mapy: {e}")
        traceback.print_exc()


def auto_migrate_data_function(backup_folder, location_name=None):
    """Kompatybilnościowa nazwa dla starego API launchera."""
    return migrate_location_data(backup_folder, location_name)


def auto_calibrate_map_from_backup(location_name=None, db_name=None):
    """Kompatybilnościowa nazwa dla starego API launchera."""
    return calibrate_map_from_location_backup(location_name=location_name, db_name=db_name)


def create_and_migrate_location_database(location_name, progress_callback=None):
    """Tworzy bazę miejscowości i przekazuje callbacki migracji z serwisu."""
    return database_setup_service.create_and_migrate_location_database(
        location_name,
        progress_callback=progress_callback,
        auto_migrate_data_function=auto_migrate_data_function,
        auto_calibrate_map_from_backup=auto_calibrate_map_from_backup,
    )
