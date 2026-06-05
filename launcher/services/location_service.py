"""Logika zarządzania miejscowościami dla launchera.

Moduł wydzielony z ``launcher_app.py`` bez zmiany zachowania publicznych
funkcji. ``launcher_app.py`` utrzymuje cienkie wrappery dla kompatybilności
z dotychczasowymi importami z testów i dialogów.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time

import psycopg2

from launcher.config.paths import BACKEND_DIR, BASE_DIR, LOCATIONS_DATA_DIR, LOCATIONS_DB_PATH
from launcher.config.settings import DEFAULT_LOCATION_NAME
from launcher.db.engine import detect_engine
from launcher.db.postgres import (
    get_launcher_postgres_connection,
    get_postgres_config,
    init_postgres_locations_db,
)
from launcher.db.sqlite import (
    invalidate_locations_cache as sqlite_invalidate_locations_cache,
    sqlite_add_location,
    sqlite_delete_location,
    sqlite_get_active_location,
    sqlite_get_all_locations,
    sqlite_init_locations_db,
    sqlite_set_active_location,
    sqlite_update_location,
)
from launcher.services.system_diagnostics import init_location_database
from launcher.utils import apply_homepage_template, check_postgres_available


_DB_ENGINE = detect_engine()
SQLITE_MODE = _DB_ENGINE is not None and _DB_ENGINE.name == "sqlite"

_locations_cache = None
_locations_cache_time = 0
_CACHE_TTL = 30


def invalidate_locations_cache():
    """Unieważnia cache miejscowości w service oraz cache backendu SQLite."""
    global _locations_cache, _locations_cache_time
    _locations_cache = None
    _locations_cache_time = 0
    sqlite_invalidate_locations_cache()


def init_locations_db():
    """
    Inicjalizuje bazę danych miejscowości.
    W trybie SQLite - używa pliku locations.json.
    W trybie PostgreSQL - używa bazy PostgreSQL.
    """
    if SQLITE_MODE:
        sqlite_init_locations_db()
        return

    if not check_postgres_available():
        return  # cicho, bez komunikatów

    try:
        init_postgres_locations_db(get_postgres_config())
        return
    except Exception as e:
        print(f"⚠️ Blad inicjalizacji PostgreSQL: {e}")
        raise


def get_all_locations():
    """
    Zwraca wszystkie miejscowości z bazy danych PostgreSQL (z cache).

    Returns:
        list of tuples: Lista miejscowości posortowana po nazwie
        Format tuple: (id, name, full_name, powiat, region, active, homepage_template, year, century,
                      homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
                      postgres_db_name, history_photos)
    """
    global _locations_cache, _locations_cache_time

    current_time = time.time()
    if _locations_cache is not None and (current_time - _locations_cache_time) < _CACHE_TTL:
        return _locations_cache

    init_locations_db()

    if SQLITE_MODE:
        _locations_cache = sqlite_get_all_locations()
        _locations_cache_time = time.time()
        return _locations_cache

    if not check_postgres_available():
        return []

    try:
        conn = get_launcher_postgres_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                l.id, l.name, l.full_name, l.powiat, l.region, l.active,
                l.homepage_template, l.year, l.century,
                l.homepage_description, l.history_paragraph1, l.history_paragraph2, l.history_paragraph3,
                l.postgres_db_name,
                l.gmina_katastralna, l.miejscowosc_protokolu,
                COALESCE(
                    (SELECT json_agg(json_build_object('filename', filename, 'caption', caption) ORDER BY order_index)
                     FROM history_photos WHERE location_id = l.id),
                    '[]'::json
                )::text as history_photos
            FROM locations l
            ORDER BY l.name
        """)
        locations = cursor.fetchall()
        cursor.close()
        conn.close()

        _locations_cache = locations
        _locations_cache_time = current_time

        return locations
    except Exception as e:
        print(f"❌ PostgreSQL błąd: {e}")
        return []


def get_active_location():
    """Zwraca aktywną miejscowość (PostgreSQL lub SQLite fallback)."""
    init_locations_db()

    if SQLITE_MODE:
        return sqlite_get_active_location()

    if not check_postgres_available():
        return _get_active_location_from_json()

    try:
        conn = get_launcher_postgres_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                l.id, l.name, l.full_name, l.powiat, l.region, l.active,
                l.homepage_template, l.year, l.century,
                l.homepage_description, l.history_paragraph1, l.history_paragraph2, l.history_paragraph3,
                l.postgres_db_name,
                l.gmina_katastralna, l.miejscowosc_protokolu,
                COALESCE(
                    (SELECT json_agg(json_build_object('filename', filename, 'caption', caption) ORDER BY order_index)
                     FROM history_photos WHERE location_id = l.id),
                    '[]'::json
                )::text as history_photos
            FROM locations l
            WHERE l.active = true
        """)
        location = cursor.fetchone()
        cursor.close()
        conn.close()

        if location:
            return location[:13] + (location[13], location[14], location[15], None, location[16])
        return None
    except Exception as e:
        print(f"⚠️ PostgreSQL blad: {e}")
        return _get_active_location_from_json()


def _get_active_location_from_json():
    """Fallback: odczytuje aktywną miejscowość z pliku launcher_db_config.json."""
    json_path = os.path.join(LOCATIONS_DATA_DIR, DEFAULT_LOCATION_NAME, "launcher_db_config.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name", DEFAULT_LOCATION_NAME)
            full_name = data.get("full_name", name)
            return (1, name, full_name, "", "", True, "standardowy", "1882", "XIX w.", "", "", "", "", name, name, name, None, "")
        except Exception:
            pass
    return (1, DEFAULT_LOCATION_NAME, DEFAULT_LOCATION_NAME, "", "", True, "standardowy", "1882", "XIX w.", "", "", "", "", DEFAULT_LOCATION_NAME.lower(), DEFAULT_LOCATION_NAME, DEFAULT_LOCATION_NAME, None, "")


def get_active_location_name():
    """Zwraca nazwę aktywnej miejscowości lub None."""
    location = get_active_location()
    return location[1] if location else None


def set_active_location(location_id):
    """Ustawia miejscowość jako aktywną (PostgreSQL lub SQLite)."""
    if SQLITE_MODE:
        sqlite_set_active_location(location_id)
        invalidate_locations_cache()
        return

    init_locations_db()

    if not check_postgres_available():
        return

    template = "standardowy"

    try:
        conn = get_launcher_postgres_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT homepage_template FROM locations WHERE id = %s", (location_id,))
        result = cursor.fetchone()
        template = result[0] if result and result[0] else "standardowy"

        cursor.execute("UPDATE locations SET active = false")
        cursor.execute("UPDATE locations SET active = true WHERE id = %s", (location_id,))
        conn.commit()
        cursor.close()
        conn.close()

        invalidate_locations_cache()
        apply_homepage_template(template)
        generate_location_config_js()
    except Exception as e:
        print(f"❌ PostgreSQL błąd: {e}")
        raise


def generate_location_config_js():
    """
    Generuje plik JavaScript z konfiguracją aktywnej miejscowości.
    Ten plik jest ładowany przez strony HTML i dynamicznie wstawia dane.
    """
    active_location = get_active_location()

    if not active_location:
        all_locations = get_all_locations()
        if all_locations:
            print("⚠️ Brak aktywnej miejscowości - ustawiam pierwszą dostępną")
            init_locations_db()
            try:
                conn = get_launcher_postgres_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE locations SET active = false")
                cursor.execute("UPDATE locations SET active = true WHERE id = %s", (all_locations[0][0],))
                conn.commit()
                cursor.close()
                conn.close()
                active_location = get_active_location()
            except Exception as e:
                print(f"❌ Błąd ustawiania pierwszej miejscowości: {e}")

    if not active_location:
        print("⚠️ Brak miejscowości w bazie danych - tworzę plik JS z domyślnymi wartościami")
        location_name = "Miejscowość"
        location_full_name = "Miejscowość"
        location_powiat = "Powiat"
        location_region = "Region"
        location_year = "1882"
        location_century = "XIX"
        homepage_description = "Odkryj historię zapisaną w ziemi."
        history_p1 = ""
        history_p2 = ""
        history_p3 = ""
        history_photos = []
    else:
        location_name = active_location[1] or "Miejscowość"
        location_full_name = active_location[2] or location_name
        location_powiat = active_location[3] or "Powiat"
        location_region = active_location[4] or "Region"
        location_year = active_location[7] if len(active_location) > 7 else "1882"
        location_century = active_location[8] if len(active_location) > 8 else "XIX"
        homepage_description = active_location[9] if len(active_location) > 9 else "Odkryj historię zapisaną w ziemi."
        history_p1 = active_location[10] if len(active_location) > 10 else ""
        history_p2 = active_location[11] if len(active_location) > 11 else ""
        history_p3 = active_location[12] if len(active_location) > 12 else ""

        history_photos_json = active_location[17] if len(active_location) > 17 else None
        try:
            history_photos = json.loads(history_photos_json) if history_photos_json else []
        except (json.JSONDecodeError, TypeError):
            history_photos = []

    static_js_folder = os.path.join(BASE_DIR, "static", "js")
    js_path = os.path.join(static_js_folder, "location-config.js")

    print(f"📁 Zapisuję location-config.js do: {js_path}")
    os.makedirs(static_js_folder, exist_ok=True)

    def escape_js_string(s):
        if not s:
            return ""
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')

    photos_json = json.dumps(history_photos, ensure_ascii=False, indent=4)
    js_content = f"""// Konfiguracja aktualnej miejscowości
// Ten plik jest automatycznie generowany przez launcher
window.LOCATION_CONFIG = {{
    name: "{escape_js_string(location_name)}",
    fullName: "{escape_js_string(location_full_name)}",
    powiat: "{escape_js_string(location_powiat)}",
    region: "{escape_js_string(location_region)}",
    year: "{escape_js_string(location_year)}",
    century: "{escape_js_string(location_century)}",
    homepageDescription: "{escape_js_string(homepage_description)}",
    historyParagraph1: "{escape_js_string(history_p1)}",
    historyParagraph2: "{escape_js_string(history_p2)}",
    historyParagraph3: "{escape_js_string(history_p3)}",
    historyPhotos: {photos_json}
}};
"""

    try:
        with open(js_path, 'w', encoding='utf-8') as f:
            f.write(js_content)
        print(f"✓ Wygenerowano location-config.js dla miejscowości: {location_full_name}")
        print(f"✓ Plik zapisany pomyślnie: {os.path.exists(js_path)}")
        return True
    except Exception as e:
        print(f"❌ Błąd podczas generowania location-config.js: {e}")
        print(f"❌ Próbowano zapisać do: {js_path}")
        import traceback
        traceback.print_exc()
        return False


def set_location_template(location_id, template_name):
    """Ustawia szablon strony głównej dla danej miejscowości w PostgreSQL."""
    if SQLITE_MODE:
        sqlite_init_locations_db()
        conn = sqlite3.connect(LOCATIONS_DB_PATH)
        conn.execute("UPDATE locations SET homepage_template = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (template_name, location_id))
        conn.commit()
        conn.close()
        invalidate_locations_cache()
        return

    init_locations_db()

    if not check_postgres_available():
        return

    try:
        conn = get_launcher_postgres_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE locations SET homepage_template = %s WHERE id = %s", (template_name, location_id))
        conn.commit()
        cursor.close()
        conn.close()
        invalidate_locations_cache()
    except Exception as e:
        print(f"❌ PostgreSQL błąd: {e}")
        raise


def ensure_location_data_files(location_folder):
    """Tworzy wymagane pliki JSON dla miejscowości jeśli nie istnieją."""
    data_files = {
        'demografia.json': [],
        'genealogia.json': {"persons": []},
        'map_config.json': {
            "calibration": {"sw": {"lat": 0, "lng": 0}, "ne": {"lat": 0, "lng": 0}},
            "defaults": {"center": {"lat": 0, "lng": 0}, "zoom": 15},
        },
        'owner_data_to_import.json': {},
        'parcels_data.json': {},
    }

    created_files = []
    for filename, structure in data_files.items():
        file_path = os.path.join(location_folder, filename)
        if not os.path.exists(file_path):
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(structure, f, ensure_ascii=False, indent=4)
                created_files.append(filename)
            except Exception as e:
                print(f"⚠️ Błąd tworzenia {filename}: {e}")

    if created_files:
        print(f"✅ Utworzono pliki danych: {', '.join(created_files)}")

    return created_files


def add_location(name, full_name, powiat="", region="", homepage_template="standardowy", year="1882", century="XIX w.",
                homepage_description="Odkryj historię zapisaną w ziemi. Przeglądaj historyczne działki katastralne, poznaj dawnych właścicieli i zgłębiaj genealogiczne powiązania mieszkańców z 1882 roku.",
                history_paragraph1="", history_paragraph2="", history_paragraph3="",
                history_photos=None, postgres_db_name="", gmina_katastralna=DEFAULT_LOCATION_NAME,
                jewish_protocol_numbers="", custom_icon="custom_icon.png"):
    """Dodaje nową miejscowość do bazy danych PostgreSQL i tworzy folder."""
    if SQLITE_MODE:
        location_id = sqlite_add_location(name, full_name, powiat, region, homepage_template, year, century,
                                          homepage_description, history_paragraph1, history_paragraph2,
                                          history_paragraph3, history_photos, postgres_db_name,
                                          gmina_katastralna, jewish_protocol_numbers, custom_icon)
        invalidate_locations_cache()
        return location_id

    init_locations_db()
    if history_photos is None:
        history_photos = []

    location_folder = os.path.join(LOCATIONS_DATA_DIR, name)
    os.makedirs(location_folder, exist_ok=True)
    os.makedirs(os.path.join(location_folder, "protokoly"), exist_ok=True)
    os.makedirs(os.path.join(location_folder, "history_photos"), exist_ok=True)
    ensure_location_data_files(location_folder)

    env_path = os.path.join(location_folder, ".env")
    if not os.path.exists(env_path):
        db_name_for_env = postgres_db_name if postgres_db_name else f"mapa_{name.lower()}_db"
        default_env = f"""# =============================================================================
# KONFIGURACJA MIEJSCOWOŚCI
# =============================================================================
# Konfiguracja PostgreSQL (host, port, user, password) jest w backend/.postgres.env

# =============================================================================
# BAZA DANYCH
# =============================================================================
DB_NAME={db_name_for_env}

# =============================================================================
# SERWER FLASK (główny serwer)
# =============================================================================
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
FLASK_SECRET_KEY=change-me-{name.lower()}-secret

# =============================================================================
# PORTY EDYTORÓW
# =============================================================================
# Każdy port musi być unikalny! Nie można używać tego samego portu dla różnych serwerów.
GENEALOGY_EDITOR_PORT=5001
PARCEL_EDITOR_PORT=5003

# =============================================================================
# AUTENTYKACJA ADMINISTRATORA
# =============================================================================
ADMIN_AUTH_ENABLED=0
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=

# =============================================================================
# INFORMACJE O MIEJSCOWOŚCI
# =============================================================================
LOCATION_NAME={name}
LOCATION_CODE={name[:2].upper()}
"""
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(default_env)

    if not check_postgres_available():
        print("❌ PostgreSQL nie jest dostępny!")
        raise RuntimeError("PostgreSQL jest wymagany do działania programu")

    try:
        conn = get_launcher_postgres_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO locations (name, full_name, powiat, region, active,
                                  homepage_template, year, century,
                                  homepage_description, history_paragraph1,
                                  history_paragraph2, history_paragraph3, postgres_db_name,
                                  gmina_katastralna, jewish_protocol_numbers, custom_icon)
            VALUES (%s, %s, %s, %s, false, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, full_name, powiat, region, homepage_template, year, century,
              homepage_description, history_paragraph1, history_paragraph2, history_paragraph3, postgres_db_name,
              gmina_katastralna, jewish_protocol_numbers, custom_icon))

        location_id = cursor.fetchone()[0]

        for idx, photo in enumerate(history_photos):
            cursor.execute("""
                INSERT INTO history_photos (location_id, filename, caption, order_index)
                VALUES (%s, %s, %s, %s)
            """, (location_id, photo.get('filename', ''), photo.get('caption', ''), idx))

        conn.commit()
        cursor.close()
        conn.close()

        if postgres_db_name:
            print(f"📦 Tworzę bazę danych: {postgres_db_name}...")
            success, msg = init_location_database(postgres_db_name)
            print(msg if success else f"⚠️ {msg}")

        try:
            config_file = os.path.join(location_folder, "launcher_db_config.json")
            launcher_config = {
                "default_location": {
                    "name": name,
                    "full_name": full_name,
                    "powiat": powiat,
                    "region": region,
                    "homepage_template": homepage_template,
                    "year": year,
                    "century": century,
                    "gmina_katastralna": gmina_katastralna,
                    "jewish_protocol_numbers": jewish_protocol_numbers,
                    "homepage_description": homepage_description,
                    "history_paragraph1": history_paragraph1,
                    "history_paragraph2": history_paragraph2,
                    "history_paragraph3": history_paragraph3,
                    "history_photos": history_photos,
                    "favicon": "favicon.jpeg",
                    "custom_icon": "custom_icon.png",
                    "postgres_db_name": postgres_db_name,
                }
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(launcher_config, f, ensure_ascii=False, indent=2)
            print(f"✅ Utworzono launcher_db_config.json dla miejscowości {name}")
        except Exception as e:
            print(f"⚠️ Nie udało się utworzyć launcher_db_config.json: {e}")

        invalidate_locations_cache()
        return location_id

    except psycopg2.IntegrityError:
        if 'conn' in locals():
            conn.close()
        raise ValueError(f"Miejscowość '{name}' już istnieje")
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"❌ PostgreSQL błąd: {e}")
        raise


def update_location(location_id, name, full_name, powiat, region, year, century,
                    homepage_description="", history_paragraph1="", history_paragraph2="", history_paragraph3="",
                    history_photos=None, postgres_db_name="", homepage_template="standardowy",
                    gmina_katastralna=DEFAULT_LOCATION_NAME, jewish_protocol_numbers="", custom_icon="custom_icon.png"):
    """Aktualizuje dane miejscowości w PostgreSQL."""
    if SQLITE_MODE:
        result = sqlite_update_location(location_id, name, full_name, powiat, region, year, century,
                                        homepage_description, history_paragraph1, history_paragraph2,
                                        history_paragraph3, history_photos, postgres_db_name,
                                        homepage_template, gmina_katastralna, jewish_protocol_numbers,
                                        custom_icon)
        invalidate_locations_cache()
        return result

    init_locations_db()
    if history_photos is None:
        history_photos = []

    if not check_postgres_available():
        print("❌ PostgreSQL nie jest dostępny!")
        raise RuntimeError("PostgreSQL jest wymagany do działania programu")

    try:
        conn = get_launcher_postgres_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM locations WHERE id = %s", (location_id,))
        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            raise ValueError("Miejscowość nie istnieje")

        old_name = result[0]
        if old_name != name:
            old_folder = os.path.join(LOCATIONS_DATA_DIR, old_name)
            new_folder = os.path.join(LOCATIONS_DATA_DIR, name)
            if os.path.exists(old_folder):
                os.rename(old_folder, new_folder)

        cursor.execute("""
            UPDATE locations SET
                name = %s, full_name = %s, powiat = %s, region = %s,
                year = %s, century = %s,
                homepage_description = %s, history_paragraph1 = %s,
                history_paragraph2 = %s, history_paragraph3 = %s,
                postgres_db_name = %s, homepage_template = %s,
                gmina_katastralna = %s,
                jewish_protocol_numbers = %s,
                custom_icon = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (name, full_name, powiat, region, year, century,
              homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
              postgres_db_name, homepage_template, gmina_katastralna,
              jewish_protocol_numbers, custom_icon,
              location_id))

        cursor.execute("DELETE FROM history_photos WHERE location_id = %s", (location_id,))
        for idx, photo in enumerate(history_photos):
            cursor.execute("""
                INSERT INTO history_photos (location_id, filename, caption, order_index)
                VALUES (%s, %s, %s, %s)
            """, (location_id, photo.get('filename', ''), photo.get('caption', ''), idx))

        conn.commit()
        cursor.close()
        conn.close()

        try:
            location_folder = os.path.join(LOCATIONS_DATA_DIR, name)
            os.makedirs(location_folder, exist_ok=True)
            os.makedirs(os.path.join(location_folder, "history_photos"), exist_ok=True)
            config_file = os.path.join(location_folder, "launcher_db_config.json")
            launcher_config = {
                "default_location": {
                    "name": name,
                    "full_name": full_name,
                    "powiat": powiat,
                    "region": region,
                    "homepage_template": homepage_template,
                    "year": year,
                    "century": century,
                    "gmina_katastralna": gmina_katastralna,
                    "jewish_protocol_numbers": jewish_protocol_numbers,
                    "homepage_description": homepage_description,
                    "history_paragraph1": history_paragraph1,
                    "history_paragraph2": history_paragraph2,
                    "history_paragraph3": history_paragraph3,
                    "history_photos": history_photos,
                    "favicon": "favicon.jpeg",
                    "custom_icon": "custom_icon.png",
                    "postgres_db_name": postgres_db_name,
                }
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(launcher_config, f, ensure_ascii=False, indent=2)
            print(f"✅ Zaktualizowano launcher_db_config.json dla miejscowości {name}")
        except Exception as e:
            print(f"⚠️ Nie udało się zaktualizować launcher_db_config.json: {e}")

        invalidate_locations_cache()

    except psycopg2.IntegrityError:
        if 'conn' in locals():
            conn.close()
        raise ValueError(f"Miejscowość '{name}' już istnieje")
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"❌ PostgreSQL błąd: {e}")
        raise


def delete_location(location_id):
    """Usuwa miejscowość z bazy danych PostgreSQL, folder i bazę danych miejscowości."""
    if SQLITE_MODE:
        result = sqlite_delete_location(location_id)
        invalidate_locations_cache()
        return result

    init_locations_db()

    if not check_postgres_available():
        print("❌ PostgreSQL nie jest dostępny!")
        raise RuntimeError("PostgreSQL jest wymagany do działania programu")

    try:
        conn = get_launcher_postgres_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name, active, postgres_db_name FROM locations WHERE id = %s", (location_id,))
        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            raise ValueError("Miejscowość nie istnieje")

        name, active, postgres_db_name = result
        if active:
            cursor.close()
            conn.close()
            raise ValueError("Nie można usunąć aktywnej miejscowości")

        db_to_delete = postgres_db_name if postgres_db_name else f"mapa_{name.lower()}"
        try:
            print(f"🗑️ Usuwanie bazy danych: {db_to_delete}")
            config = get_postgres_config()
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            db_conn = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database='postgres',
            )
            db_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            db_cursor = db_conn.cursor()
            db_cursor.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_to_delete}'
                AND pid <> pg_backend_pid()
            """)
            db_cursor.execute(f'DROP DATABASE IF EXISTS "{db_to_delete}"')
            db_cursor.close()
            db_conn.close()
            print(f"✅ Usunięto bazę danych: {db_to_delete}")
        except Exception as db_err:
            print(f"⚠️ Ostrzeżenie: Nie udało się usunąć bazy danych {db_to_delete}: {db_err}")

        location_folder = os.path.join(LOCATIONS_DATA_DIR, name)
        if os.path.exists(location_folder):
            shutil.rmtree(location_folder)
            print(f"✅ Usunięto folder: {location_folder}")

        cursor.execute("DELETE FROM locations WHERE id = %s", (location_id,))
        conn.commit()
        cursor.close()
        conn.close()

        invalidate_locations_cache()
        print(f"✅ Usunięto miejscowość: {name}")

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        if isinstance(e, ValueError):
            raise
        print(f"❌ PostgreSQL błąd: {e}")
        raise


def load_default_location_config():
    """Wczytuje konfigurację domyślnej lokalizacji z pliku JSON."""
    config_file = os.path.join(LOCATIONS_DATA_DIR, DEFAULT_LOCATION_NAME, "launcher_db_config.json")
    try:
        print(f"📄 Próba wczytania konfiguracji z: {config_file}")
        if not os.path.exists(config_file):
            print(f"⚠️ Plik nie istnieje: {config_file}")
            return {}
        with open(config_file, 'r', encoding='utf-8') as f:
            launcher_config = json.load(f)
            print("✅ Konfiguracja wczytana pomyślnie z JSON")
            return launcher_config.get('default_location', {})
    except FileNotFoundError:
        print(f"⚠️ Brak pliku launcher_db_config.json w: {config_file}")
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️ Błąd parsowania JSON: {e}")
        print(f"   Plik: {config_file}")
        print(f"   Wiersz: {e.lineno}, Kolumna: {e.colno}, Pozycja: {e.pos}")
        return {}
    except Exception as e:
        print(f"⚠️ Nieoczekiwany błąd wczytywania konfiguracji: {e}")
        print(f"   Plik: {config_file}")
        import traceback
        traceback.print_exc()
        return {}


def ensure_default_location_exists():
    """Upewnia się, że istnieje domyślna miejscowość."""
    if SQLITE_MODE:
        return

    init_locations_db()
    locations = get_all_locations()
    if locations:
        active_location = get_active_location()
        if not active_location:
            set_active_location(locations[0][0])
        return

    default_loc = load_default_location_config()
    default_name = default_loc.get('name', 'Czarna')
    try:
        location_id = add_location(
            name=default_loc.get('name', 'Czarna'),
            full_name=default_loc.get('full_name', 'Czarna'),
            powiat=default_loc.get('powiat', ''),
            region=default_loc.get('region', ''),
            homepage_template=default_loc.get('homepage_template', 'standardowy'),
            year=default_loc.get('year', '1882'),
            century=default_loc.get('century', 'XIX w.'),
            homepage_description=default_loc.get('homepage_description', ''),
            history_paragraph1=default_loc.get('history_paragraph1', ''),
            history_paragraph2=default_loc.get('history_paragraph2', ''),
            history_paragraph3=default_loc.get('history_paragraph3', ''),
            history_photos=default_loc.get('history_photos', []),
            postgres_db_name=default_loc.get('postgres_db_name', 'mapa_czarna_db'),
            gmina_katastralna=default_loc.get('gmina_katastralna', 'Czarna'),
            jewish_protocol_numbers=default_loc.get('jewish_protocol_numbers', ''),
            custom_icon=default_loc.get('custom_icon', 'custom_icon.png'),
        )
        set_active_location(location_id)
        print(f"✓ Utworzono domyślną miejscowość: {default_name}")
    except Exception as e:
        print(f"⚠️ Błąd tworzenia domyślnej miejscowości: {e}")


def migrate_old_backup_structure():
    """Migruje starą strukturę backup/ do nowej struktury z miejscowościami."""
    if check_postgres_available():
        try:
            conn = get_launcher_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM locations")
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            if count > 0:
                return
        except Exception:
            pass

    print("🔄  Migracja struktury folderów backup...")

    old_files = [
        "owner_data_to_import.json",
        "parcels_data.json",
        "demografia.json",
        "genealogia.json",
        "map_config.json",
    ]

    has_old_files = any(os.path.exists(os.path.join(LOCATIONS_DATA_DIR, f)) for f in old_files)
    if not has_old_files:
        print("ℹ️ Brak starych plików do migracji")
        return

    default_location_name = DEFAULT_LOCATION_NAME
    default_location_folder = os.path.join(LOCATIONS_DATA_DIR, default_location_name)

    try:
        os.makedirs(default_location_folder, exist_ok=True)
        for filename in old_files:
            old_path = os.path.join(LOCATIONS_DATA_DIR, filename)
            if os.path.exists(old_path):
                new_path = os.path.join(default_location_folder, filename)
                shutil.move(old_path, new_path)
                print(f"✅ Przeniesiono: {filename}")

        old_env_path = os.path.join(BACKEND_DIR, ".env")
        if os.path.exists(old_env_path):
            new_env_path = os.path.join(default_location_folder, ".env")
            shutil.copy2(old_env_path, new_env_path)
            print("✅ Skopiowano: .env")

        default_loc = load_default_location_config()
        add_location(
            name=default_loc.get('name', 'Czarna'),
            full_name=default_loc.get('full_name', 'Czarna'),
            powiat=default_loc.get('powiat', ''),
            region=default_loc.get('region', ''),
            homepage_template=default_loc.get('homepage_template', 'standardowy'),
            year=default_loc.get('year', '1882'),
            century=default_loc.get('century', 'XIX w.'),
            homepage_description=default_loc.get('homepage_description', ''),
            history_paragraph1=default_loc.get('history_paragraph1', ''),
            history_paragraph2=default_loc.get('history_paragraph2', ''),
            history_paragraph3=default_loc.get('history_paragraph3', ''),
            history_photos=default_loc.get('history_photos', []),
            postgres_db_name=default_loc.get('postgres_db_name', 'mapa_czarna_db'),
            gmina_katastralna=default_loc.get('gmina_katastralna', 'Czarna'),
            jewish_protocol_numbers=default_loc.get('jewish_protocol_numbers', ''),
            custom_icon=default_loc.get('custom_icon', 'custom_icon.png'),
        )
        set_active_location(1)
        print(f"✅ Migracja zakończona! Utworzono miejscowość: {default_location_name}")

    except Exception as e:
        print(f"❌ Błąd podczas migracji: {e}")
        import traceback
        traceback.print_exc()
