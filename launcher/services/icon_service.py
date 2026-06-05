"""Obsługa ikon launchera i faviconów witryny.

Logika wydzielona z ``launcher_app.py``. Funkcje w tym module nie tworzą UI,
tylko wykonują operacje plikowe/konfiguracyjne związane z ikonami.
"""

from __future__ import annotations

import json
import os
import shutil

from launcher.config.paths import LAUNCHER_DIR, LOCATIONS_DATA_DIR, location_data_dir
from launcher.db.postgres import get_launcher_postgres_connection
from launcher.services import location_service


def migrate_custom_icon_to_backup():
    """Migruje stare custom_icon z launcher/assets do data/locations/{aktywna_miejscowość}/."""
    try:
        # Zachowujemy legacy źródło: dawny folder launcher/assets.
        icon_dir = os.path.join(LAUNCHER_DIR, "assets")
        old_custom_png = os.path.join(icon_dir, "custom_icon.png")
        old_custom_ico = os.path.join(icon_dir, "custom_icon.ico")

        has_old_icons = os.path.exists(old_custom_png) or os.path.exists(old_custom_ico)
        if not has_old_icons:
            return

        try:
            active_location = location_service.get_active_location()
        except NameError:
            from launcher.db.sqlite import sqlite_get_active_location as _gal
            active_location = _gal()

        if not active_location:
            print("ℹ️ Brak aktywnej miejscowości - pominięto migrację custom_icon")
            return

        location_name = active_location[1]
        location_id = active_location[0]
        backup_icon_dir = str(location_data_dir(location_name))
        os.makedirs(backup_icon_dir, exist_ok=True)

        print(f"🔄  Migracja custom_icon do backup/{location_name}/...")

        migrated = False
        if os.path.exists(old_custom_png):
            new_path = os.path.join(backup_icon_dir, "custom_icon.png")
            if not os.path.exists(new_path):
                shutil.copy2(old_custom_png, new_path)
                print(f"✅ Skopiowano custom_icon.png do backup/{location_name}/")
                migrated = True

        if os.path.exists(old_custom_ico):
            new_path = os.path.join(backup_icon_dir, "custom_icon.ico")
            if not os.path.exists(new_path):
                shutil.copy2(old_custom_ico, new_path)
                print(f"✅ Skopiowano custom_icon.ico do backup/{location_name}/")
                migrated = True

        if migrated:
            try:
                conn = get_launcher_postgres_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE locations SET custom_icon = %s WHERE id = %s", ("custom_icon.png", location_id))
                conn.commit()
                cursor.close()
                conn.close()
                print("✅ Zaktualizowano custom_icon w bazie danych")
            except Exception as db_error:
                print(f"⚠️ Błąd aktualizacji bazy danych: {db_error}")

            config_file = os.path.join(backup_icon_dir, "launcher_db_config.json")
            if os.path.exists(config_file):
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                    config_data["default_location"]["custom_icon"] = "custom_icon.png"
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(config_data, f, ensure_ascii=False, indent=2)
                    print("✅ Zaktualizowano launcher_db_config.json")
                except Exception as json_error:
                    print(f"⚠️ Błąd aktualizacji JSON: {json_error}")

    except Exception as e:
        print(f"⚠️ Błąd podczas migracji custom_icon: {e}")


def auto_sync_site_icon():
    """Sprawdza czy favicon istnieje w folderze aktywnej miejscowości.

    Favicon jest serwowany bezpośrednio z folderu miejscowości przez endpoint
    ``/location_favicon``, więc nie ma potrzeby kopiowania go do assets/site.
    """
    try:
        location_name = location_service.get_active_location_name()
        if not location_name:
            print("ℹ️ Brak aktywnej miejscowości dla favicon")
            return

        backup_location_folder = os.path.normpath(os.path.join(LOCATIONS_DATA_DIR, location_name))
        favicon_extensions = [".ico", ".png", ".jpg", ".jpeg"]
        favicon_found = False

        for ext in favicon_extensions:
            favicon_path = os.path.join(backup_location_folder, f"favicon{ext}")
            if os.path.exists(favicon_path):
                print(f"✅ Favicon znaleziony: {favicon_path}")
                favicon_found = True
                break

        if not favicon_found:
            if os.path.exists(backup_location_folder):
                existing_files = [
                    f for f in os.listdir(backup_location_folder)
                    if "favicon" in f.lower() or f.endswith((".ico", ".png", ".jpg", ".jpeg"))
                ]
                if existing_files:
                    print(f"ℹ️ Znaleziono potencjalne pliki ikon: {existing_files}")
                    for f in existing_files:
                        if "favicon" in f.lower():
                            print(f"✅ Używam znalezionego faviconu: {f}")
                            favicon_found = True
                            break
            if not favicon_found:
                print(f"ℹ️ Brak niestandardowego faviconu w {backup_location_folder}")

    except Exception as e:
        print(f"⚠️ Błąd podczas sprawdzania favicon: {e}")
