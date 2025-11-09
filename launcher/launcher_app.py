"""
================================================================================
Plik: launcher.py
System Mapy Katastralnej - Centrum Zarządzania
================================================================================
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
import subprocess
import threading
import os
import socket
import sys
import webbrowser
import signal
import platform
import queue
import zipfile
from datetime import datetime
import shutil
import tkinter.font as tkfont
import ctypes
import filecmp
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from functools import lru_cache
import time

try:
    from PIL import Image, ImageTk
except ImportError:
    messagebox.showerror("Brak zależności", "Biblioteka Pillow jest wymagana.\nZainstaluj: pip install Pillow")
    sys.exit(1)

# =============================================================================
# KONFIGURACJA DPI DLA WINDOWS
# =============================================================================
if platform.system() == "Windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass

# =============================================================================
# KONFIGURACJA ŚCIEŻEK I STAŁYCH
# =============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_FOLDER = os.path.join(BASE_DIR, "backup")
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
ASSETS_FOLDER = os.path.join(BASE_DIR, "assets")
PROTOKOLY_FOLDER = os.path.join(ASSETS_FOLDER, "protokoly")
SITE_ASSETS_FOLDER = os.path.join(ASSETS_FOLDER, "site")
LOCATIONS_DB_PATH = os.path.join(BASE_DIR, "launcher", "locations.db")
ICONS_SCAN_FOLDERS = [
    os.path.join(BASE_DIR, "icons"),
    os.path.join(ASSETS_FOLDER, "icons"),
]

# =============================================================================
# CACHE DLA OPTYMALIZACJI WYDAJNOŚCI
# =============================================================================
_locations_cache = None
_locations_cache_time = 0
_CACHE_TTL = 30  # Cache ważny przez 30 sekund

def invalidate_locations_cache():
    """Unieważnia cache miejscowości."""
    global _locations_cache, _locations_cache_time
    _locations_cache = None
    _locations_cache_time = 0

# =============================================================================
# POSTGRESQL - FUNKCJE POMOCNICZE I SCHEMA
# =============================================================================

# SQL Schema dla mapa_launcher_db (baza konfiguracyjna PostgreSQL)
LAUNCHER_DB_SCHEMA = """
-- Tabela miejscowości
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(200),
    powiat VARCHAR(100),
    region VARCHAR(100),
    active BOOLEAN DEFAULT FALSE,
    homepage_template VARCHAR(50) DEFAULT 'standardowy',
    year VARCHAR(10) DEFAULT '1882',
    century VARCHAR(20) DEFAULT 'XIX w.',
    homepage_description TEXT,
    history_paragraph1 TEXT,
    history_paragraph2 TEXT,
    history_paragraph3 TEXT,
    postgres_db_name VARCHAR(100),
    gmina_katastralna VARCHAR(100) DEFAULT 'Czarna',
    miejscowosc_protokolu VARCHAR(100) DEFAULT 'Pilzno',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela zdjęć historycznych
CREATE TABLE IF NOT EXISTS history_photos (
    id SERIAL PRIMARY KEY,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    caption TEXT,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indeksy
CREATE INDEX IF NOT EXISTS idx_location_active ON locations(active);
CREATE INDEX IF NOT EXISTS idx_location_name ON locations(name);
CREATE INDEX IF NOT EXISTS idx_photos_location ON history_photos(location_id);
CREATE INDEX IF NOT EXISTS idx_photos_order ON history_photos(location_id, order_index);

-- Trigger do aktualizacji updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_locations_updated_at ON locations;
CREATE TRIGGER update_locations_updated_at BEFORE UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Upewnij się że zawsze tylko jedna miejscowość jest aktywna
CREATE OR REPLACE FUNCTION ensure_single_active_location()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.active = TRUE THEN
        UPDATE locations SET active = FALSE WHERE id != NEW.id;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS single_active_location ON locations;
CREATE TRIGGER single_active_location BEFORE INSERT OR UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION ensure_single_active_location();
"""

# SQL do usuwania tabel w bazie launcher
LAUNCHER_DROP_TABLES = """
-- Usuń wyzwalacze
DROP TRIGGER IF EXISTS update_locations_updated_at ON locations;
DROP TRIGGER IF EXISTS single_active_location ON locations;

-- Usuń tabele
DROP TABLE IF EXISTS history_photos CASCADE;
DROP TABLE IF EXISTS locations CASCADE;

-- Usuń funkcje
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS ensure_single_active_location() CASCADE;
"""

# Schemat bazy danych dla miejscowości (mapa_*_db) - tabele mapy, właścicieli, genealogii, itp.
# SQL do usuwania tabel
LOCATION_DROP_TABLES = """
DROP TABLE IF EXISTS malzenstwa, osoby_genealogia, powiazania_protokolow, dzialki_wlasciciele,
                     wlasciciele, obiekty_geograficzne, demografia, login_attempts,
                     blocked_ips, konfiguracja_systemu CASCADE;
"""

# Pełny schemat z DROP + CREATE
LOCATION_DB_SCHEMA = """
-- Czyszczenie istniejących tabel (jeśli istnieją)
DROP TABLE IF EXISTS malzenstwa, osoby_genealogia, powiazania_protokolow, dzialki_wlasciciele,
                     wlasciciele, obiekty_geograficzne, demografia, login_attempts,
                     blocked_ips, konfiguracja_systemu CASCADE;

-- Tabela globalnej konfiguracji systemu
CREATE TABLE konfiguracja_systemu (
    klucz VARCHAR(50) PRIMARY KEY,
    wartosc JSONB NOT NULL,
    opis TEXT
);

-- Tabela obiektów geograficznych (działki, drogi, budynki)
CREATE TABLE obiekty_geograficzne (
    id SERIAL PRIMARY KEY,
    nazwa_lub_numer VARCHAR(50) NOT NULL,
    kategoria       VARCHAR(50) NOT NULL,
    geometria GEOMETRY(GEOMETRY, 4326),
    UNIQUE (nazwa_lub_numer, kategoria)
);

-- Tabela protokołów właścicieli
CREATE TABLE wlasciciele (
    id SERIAL PRIMARY KEY,
    unikalny_klucz VARCHAR(100) NOT NULL UNIQUE,
    nazwa_wlasciciela VARCHAR(255) NOT NULL,
    numer_protokolu INTEGER,
    numer_domu VARCHAR(50),
    data_protokolu DATE,
    miejsce_protokolu VARCHAR(100),
    genealogia TEXT,
    historia_wlasnosci TEXT,
    uwagi TEXT,
    wspolwlasnosc TEXT,
    powiazania_i_transakcje TEXT,
    interpretacja_i_wnioski TEXT
);

-- Tabela genealogii osób
CREATE TABLE osoby_genealogia (
    id SERIAL PRIMARY KEY,
    json_id INTEGER UNIQUE NOT NULL,
    imie_nazwisko VARCHAR(255) NOT NULL,
    plec VARCHAR(1),
    numer_domu VARCHAR(50),
    rok_urodzenia INTEGER,
    rok_smierci INTEGER,
    id_ojca INTEGER REFERENCES osoby_genealogia(id) ON DELETE SET NULL,
    id_matki INTEGER REFERENCES osoby_genealogia(id) ON DELETE SET NULL,
    id_protokolu INTEGER REFERENCES wlasciciele(id) ON DELETE SET NULL,
    uwagi TEXT
);

-- Tabela relacji małżeńskich
CREATE TABLE malzenstwa (
    malzonek1_id INTEGER NOT NULL REFERENCES osoby_genealogia(id) ON DELETE CASCADE,
    malzonek2_id INTEGER NOT NULL REFERENCES osoby_genealogia(id) ON DELETE CASCADE,
    PRIMARY KEY (malzonek1_id, malzonek2_id),
    CONSTRAINT rozne_osoby CHECK (malzonek1_id <> malzonek2_id)
);

-- Tabela łącząca właścicieli z obiektami
CREATE TABLE dzialki_wlasciciele (
    id SERIAL PRIMARY KEY,
    wlasciciel_id INTEGER NOT NULL REFERENCES wlasciciele(id) ON DELETE CASCADE,
    obiekt_id INTEGER NOT NULL REFERENCES obiekty_geograficzne(id) ON DELETE CASCADE,
    typ_posiadania VARCHAR(50),
    opis_udzialu TEXT,
    UNIQUE (wlasciciel_id, obiekt_id, typ_posiadania)
);

-- Tabela danych demograficznych
CREATE TABLE demografia (
    id SERIAL PRIMARY KEY,
    rok INTEGER NOT NULL UNIQUE,
    populacja_ogolem INTEGER,
    katolicy INTEGER,
    zydzi INTEGER,
    inni INTEGER,
    opis TEXT
);

-- Tabela powiązań między protokołami
CREATE TABLE powiazania_protokolow (
    id SERIAL PRIMARY KEY,
    wlasciciel_id_1 INTEGER NOT NULL REFERENCES wlasciciele(id) ON DELETE CASCADE,
    wlasciciel_id_2 INTEGER NOT NULL REFERENCES wlasciciele(id) ON DELETE CASCADE,
    typ_relacji VARCHAR(50),
    opis_relacji TEXT
);

-- Tabela logów prób logowania
CREATE TABLE login_attempts (
    id SERIAL PRIMARY KEY,
    ip_address VARCHAR(45) NOT NULL,
    username_attempt VARCHAR(255),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    successful BOOLEAN NOT NULL
);

-- Tabela zablokowanych adresów IP
CREATE TABLE blocked_ips (
    id SERIAL PRIMARY KEY,
    ip_address VARCHAR(45) NOT NULL UNIQUE,
    reason TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Indeksy dla optymalizacji zapytań
CREATE INDEX idx_obiekty_geometria ON obiekty_geograficzne USING GIST (geometria);
CREATE INDEX idx_wlasciciele_nazwa ON wlasciciele (nazwa_wlasciciela);
CREATE INDEX idx_osoby_genealogia_protokol ON osoby_genealogia (id_protokolu);
CREATE INDEX idx_login_attempts_ip ON login_attempts (ip_address);

-- Wstawienie domyślnej konfiguracji mapy
INSERT INTO konfiguracja_systemu (klucz, wartosc, opis) VALUES
('map_calibration', '{"sw": {"lat": 50.0414, "lng": 21.2261}, "ne": {"lat": 50.0814, "lng": 21.2661}}', 'Współrzędne kalibracji mapy historycznej (Południowy-Zachód i Północny-Wschód).'),
('map_defaults', '{"center": {"lat": 50.0614, "lng": 21.2461}, "zoom": 14}', 'Domyślny widok startowy mapy (centrum i poziom przybliżenia).')
ON CONFLICT (klucz) DO NOTHING;
"""


# Zmienne globalne
POSTGRES_AVAILABLE = None
POSTGRES_CONFIG_FILE = os.path.join(BASE_DIR, "backend", ".postgres.env")
LOCATIONS_DB_INITIALIZED = False  # Cache - czy baza została już zainicjalizowana


def get_postgres_config():
    """
    Zwraca konfigurację PostgreSQL z pliku .postgres.env lub domyślną.

    Plik .postgres.env powinien zawierać:
    LAUNCHER_DB_HOST=localhost
    LAUNCHER_DB_PORT=5432
    LAUNCHER_DB_USER=postgres
    LAUNCHER_DB_PASSWORD=twoje_haslo
    """
    config = {
        'host': 'localhost',
        'port': 5432,
        'user': 'postgres',
        'password': ''
    }

    # Spróbuj wczytać z pliku .postgres.env
    if os.path.exists(POSTGRES_CONFIG_FILE):
        try:
            from dotenv import dotenv_values
            env_config = dotenv_values(POSTGRES_CONFIG_FILE)
            config['host'] = env_config.get('LAUNCHER_DB_HOST', config['host'])
            config['port'] = int(env_config.get('LAUNCHER_DB_PORT', config['port']))
            config['user'] = env_config.get('LAUNCHER_DB_USER', config['user'])
            config['password'] = env_config.get('LAUNCHER_DB_PASSWORD', config['password'])
        except Exception as e:
            print(f"⚠️ Błąd wczytywania .postgres.env: {e}")

    return config


def save_postgres_config(host, port, user, password):
    """
    Zapisuje konfigurację PostgreSQL do pliku .postgres.env.

    Args:
        host: Host PostgreSQL
        port: Port PostgreSQL
        user: Użytkownik PostgreSQL
        password: Hasło PostgreSQL
    """
    config_content = f"""# Konfiguracja PostgreSQL dla launchera
LAUNCHER_DB_HOST={host}
LAUNCHER_DB_PORT={port}
LAUNCHER_DB_USER={user}
LAUNCHER_DB_PASSWORD={password}
"""

    try:
        with open(POSTGRES_CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write(config_content)
        print(f"✅ Zapisano konfigurację PostgreSQL do {POSTGRES_CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"❌ Błąd zapisu konfiguracji: {e}")
        return False


def check_postgres_available():
    """
    Sprawdza czy PostgreSQL jest dostępny i skonfigurowany.
    Ustawia globalną zmienną POSTGRES_AVAILABLE.
    """
    global POSTGRES_AVAILABLE

    if POSTGRES_AVAILABLE is not None:
        return POSTGRES_AVAILABLE

    config = get_postgres_config()

    # Jeśli brak hasła, PostgreSQL nie jest skonfigurowany
    if not config['password']:
        POSTGRES_AVAILABLE = False
        return False

    # Sprawdź czy można się połączyć
    success, _ = test_postgres_connection(
        config['host'], config['port'],
        config['user'], config['password']
    )

    POSTGRES_AVAILABLE = success
    return success


def test_postgres_connection(host, port, user, password):
    """
    Testuje połączenie z PostgreSQL.
    Zwraca (success: bool, message: str)
    """
    try:
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database='postgres'
        )
        conn.close()
        return True, "Połączenie udane"
    except psycopg2.OperationalError as e:
        return False, f"Błąd połączenia: {str(e)}"
    except Exception as e:
        return False, f"Nieznany błąd: {str(e)}"


def postgres_database_exists(host, port, user, password, db_name):
    """Sprawdza czy baza danych istnieje w PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password,
            database='postgres'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return exists
    except Exception as e:
        print(f"Błąd sprawdzania bazy: {e}")
        return False


def postgres_create_database(host, port, user, password, db_name):
    """
    Tworzy nową bazę PostgreSQL.
    Zwraca (success: bool, message: str)
    """
    try:
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password,
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        cursor.execute(f'CREATE DATABASE "{db_name}"')
        cursor.close()
        conn.close()
        return True, f"Baza '{db_name}' utworzona"
    except psycopg2.errors.DuplicateDatabase:
        return True, f"Baza '{db_name}' już istnieje"
    except Exception as e:
        return False, f"Błąd tworzenia bazy: {str(e)}"


def postgres_enable_postgis(host, port, user, password, db_name):
    """Włącza PostGIS w bazie"""
    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password,
            database=db_name
        )
        cursor = conn.cursor()
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        conn.commit()
        cursor.close()
        conn.close()
        return True, "PostGIS włączony"
    except Exception as e:
        return False, f"Błąd PostGIS: {str(e)}"


def postgres_enable_postgis(host, port, user, password, db_name):
    """Włącza rozszerzenie PostGIS w bazie danych"""
    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password,
            database=db_name, client_encoding='UTF8'
        )
        # Ustaw autocommit dla CREATE EXTENSION
        conn.autocommit = True
        cursor = conn.cursor()

        # Sprawdź czy PostGIS już istnieje
        cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis');")
        postgis_exists = cursor.fetchone()[0]

        if postgis_exists:
            cursor.close()
            conn.close()
            return True, "PostGIS już włączony"

        # Włącz PostGIS
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cursor.close()
        conn.close()
        return True, "PostGIS włączony pomyślnie"
    except Exception as e:
        return False, f"Błąd włączania PostGIS: {str(e)}"


def postgres_execute_schema(host, port, user, password, db_name, schema_sql):
    """Wykonuje SQL schema w bazie"""
    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password,
            database=db_name
        )
        cursor = conn.cursor()
        cursor.execute(schema_sql)
        conn.commit()
        cursor.close()
        conn.close()
        return True, "Schema wykonana pomyślnie"
    except Exception as e:
        return False, f"Błąd wykonywania schema: {str(e)}"


def postgres_list_databases(host, port, user, password):
    """Zwraca listę baz (bez systemowych)"""
    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password,
            database='postgres'
        )
        cursor = conn.cursor()
        cursor.execute("""
            SELECT datname FROM pg_database
            WHERE datistemplate = false
            AND datname NOT IN ('postgres', 'template0', 'template1')
            ORDER BY datname
        """)
        databases = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return databases
    except Exception:
        return []


def get_launcher_postgres_connection():
    """
    Zwraca połączenie do bazy danych mapa_launcher_db.
    Używa konfiguracji z get_postgres_config().

    Returns:
        psycopg2.connection: Połączenie do bazy danych

    Raises:
        Exception: Jeśli nie można połączyć się z bazą
    """
    config = get_postgres_config()
    try:
        conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            user=config['user'],
            password=config['password'],
            database='mapa_launcher_db'
        )
        return conn
    except psycopg2.OperationalError as e:
        raise Exception(f"Nie można połączyć się z bazą mapa_launcher_db: {str(e)}")


def init_postgres_locations_db():
    """
    Inicjalizuje bazę PostgreSQL mapa_launcher_db jeśli nie istnieje.
    Tworzy bazę i wykonuje schemat.

    Returns:
        bool: True jeśli sukces, False jeśli błąd
    """
    global LOCATIONS_DB_INITIALIZED

    config = get_postgres_config()

    # Sprawdź czy baza istnieje
    db_exists = postgres_database_exists(config['host'], config['port'], config['user'],
                                         config['password'], 'mapa_launcher_db')

    # Jeśli już zainicjalizowana i baza istnieje, tylko włącz PostGIS i zakończ
    if LOCATIONS_DB_INITIALIZED and db_exists:
        # Upewnij się, że PostGIS jest włączony (dla istniejących baz)
        postgres_enable_postgis(config['host'], config['port'],
                               config['user'], config['password'],
                               'mapa_launcher_db')
        return True

    if not db_exists:
        # Utwórz bazę
        success, msg = postgres_create_database(config['host'], config['port'],
                                                 config['user'], config['password'],
                                                 'mapa_launcher_db')
        if not success:
            print(f"❌ Błąd tworzenia bazy: {msg}")
            return False
        print(f"✓ {msg}")

    # Włącz PostGIS w bazie launcher (cicho, bez komunikatów)
    postgres_enable_postgis(config['host'], config['port'],
                           config['user'], config['password'],
                           'mapa_launcher_db')

    # Wykonaj schemat (tylko raz!)
    success, msg = postgres_execute_schema(config['host'], config['port'],
                                            config['user'], config['password'],
                                            'mapa_launcher_db', LAUNCHER_DB_SCHEMA)
    if not success:
        print(f"❌ Błąd wykonywania schematu: {msg}")
        return False

    # Migracja: Dodaj kolumny jeśli nie istnieją (dla istniejących baz)
    try:
        conn = get_launcher_postgres_connection()
        cursor = conn.cursor()

        # Sprawdź czy kolumna gmina_katastralna istnieje
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='locations' AND column_name='gmina_katastralna'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE locations ADD COLUMN gmina_katastralna VARCHAR(100) DEFAULT 'Czarna'")
            print("✓ Dodano kolumnę gmina_katastralna")

        # Sprawdź czy kolumna miejscowosc_protokolu istnieje
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='locations' AND column_name='miejscowosc_protokolu'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE locations ADD COLUMN miejscowosc_protokolu VARCHAR(100) DEFAULT 'Pilzno'")
            print("✓ Dodano kolumnę miejscowosc_protokolu")

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️  Błąd migracji kolumn protokołu: {e}")

    # Oznacz jako zainicjalizowane
    LOCATIONS_DB_INITIALIZED = True

    print(f"✓ Baza mapa_launcher_db jest gotowa")
    return True


def init_location_database(db_name):
    """
    Tworzy i inicjalizuje bazę danych dla miejscowości (np. mapa_czarna_db).
    Tworzy wszystkie tabele: obiekty_geograficzne, wlasciciele, osoby_genealogia,
    demografia, malzenstwa, login_attempts, blocked_ips, itd.

    Args:
        db_name: Nazwa bazy danych (np. 'mapa_czarna_db')

    Returns:
        tuple: (success: bool, message: str)
    """
    if not check_postgres_available():
        return (False, "PostgreSQL nie jest dostępny")

    config = get_postgres_config()

    # Sprawdź czy baza już istnieje
    db_exists = postgres_database_exists(config['host'], config['port'],
                                         config['user'], config['password'], db_name)

    if not db_exists:
        # Utwórz bazę
        success, msg = postgres_create_database(config['host'], config['port'],
                                                config['user'], config['password'], db_name)
        if not success:
            return (False, f"Błąd tworzenia bazy: {msg}")

    # Włącz PostGIS w bazie miejscowości (cicho)
    postgres_enable_postgis(config['host'], config['port'],
                           config['user'], config['password'], db_name)

    # Wykonaj schemat (DROP + CREATE wszystkie tabele)
    success, msg = postgres_execute_schema(config['host'], config['port'],
                                          config['user'], config['password'],
                                          db_name, LOCATION_DB_SCHEMA)
    if not success:
        return (False, f"Błąd inicjalizacji tabel: {msg}")

    return (True, f"✓ Baza {db_name} została utworzona i zainicjalizowana")


# =============================================================================
# ZARZĄDZANIE MIEJSCOWOŚCIAMI - definicje funkcji przed get_data_files()
# =============================================================================
def init_locations_db():
    """
    Inicjalizuje bazę danych miejscowości - TYLKO PostgreSQL.
    Jeśli PostgreSQL nie działa, program nie może działać.
    """
    # Sprawdź czy PostgreSQL jest dostępny
    if not check_postgres_available():
        print("❌ PostgreSQL nie jest dostępny!")
        print("ℹ️ Program wymaga PostgreSQL. Skonfiguruj plik backend/.postgres.env")
        return

    try:
        init_postgres_locations_db()
        return
    except Exception as e:
        print(f"❌ Błąd inicjalizacji PostgreSQL: {e}")
        print("ℹ️ Sprawdź czy serwer PostgreSQL jest uruchomiony i konfiguracja jest poprawna.")
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

    # Sprawdź cache
    current_time = time.time()
    if _locations_cache is not None and (current_time - _locations_cache_time) < _CACHE_TTL:
        return _locations_cache

    # Cache nieważny lub pusty - pobierz z bazy
    init_locations_db()

    if not check_postgres_available():
        print("❌ PostgreSQL nie jest dostępny!")
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

        # Zapisz w cache
        _locations_cache = locations
        _locations_cache_time = current_time

        return locations
    except Exception as e:
        print(f"❌ PostgreSQL błąd: {e}")
        return []

def get_active_location():
    """Zwraca aktywną miejscowość z PostgreSQL."""
    init_locations_db()

    if not check_postgres_available():
        print("❌ PostgreSQL nie jest dostępny!")
        return None

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
            return location[:13] + (None, None, None, None, location[13])
        return None
    except Exception as e:
        print(f"❌ PostgreSQL błąd: {e}")
        return None

def get_active_location_name():
    """Zwraca nazwę aktywnej miejscowości lub None."""
    location = get_active_location()
    return location[1] if location else None

def set_active_location(location_id):
    """Ustawia miejscowość jako aktywną w PostgreSQL."""
    init_locations_db()

    if not check_postgres_available():
        print("❌ PostgreSQL nie jest dostępny!")
        return

    template = "standardowy"

    try:
        conn = get_launcher_postgres_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT homepage_template FROM locations WHERE id = %s", (location_id,))
        result = cursor.fetchone()
        template = result[0] if result and result[0] else "standardowy"

        cursor.execute("UPDATE locations SET active = false")  # Wyłącz wszystkie
        cursor.execute("UPDATE locations SET active = true WHERE id = %s", (location_id,))
        conn.commit()
        cursor.close()
        conn.close()

        invalidate_locations_cache()  # Unieważnij cache po zmianie
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

    # Jeśli nie ma aktywnej miejscowości, spróbuj ustawić pierwszą dostępną
    if not active_location:
        all_locations = get_all_locations()
        if all_locations:
            print("⚠️ Brak aktywnej miejscowości - ustawiam pierwszą dostępną")
            # Ręcznie ustaw pierwszą miejscowość jako aktywną (bez wywoływania set_active_location, żeby uniknąć rekurencji)
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
        # Stwórz plik z domyślnymi wartościami
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
        # Pobierz dane miejscowości z wszystkimi polami
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

        # Pobierz history_photos jako JSON (indeks 17 po dodaniu history_photos)
        history_photos_json = active_location[17] if len(active_location) > 17 else None
        try:
            history_photos = json.loads(history_photos_json) if history_photos_json else []
        except (json.JSONDecodeError, TypeError):
            history_photos = []

    # Ścieżka do pliku JS - zapisz w folderze static/js/
    static_js_folder = os.path.join(BASE_DIR, "static", "js")
    js_path = os.path.join(static_js_folder, "location-config.js")

    # Debug - pokaż gdzie zapisujemy plik
    print(f"📁 Zapisuję location-config.js do: {js_path}")

    # Stwórz folder jeśli nie istnieje
    os.makedirs(static_js_folder, exist_ok=True)

    # Pomocnicza funkcja do escapowania cudzysłowów w JS
    def escape_js_string(s):
        if not s:
            return ""
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')

    # Przygotuj JSON dla history_photos (przekonwertuj na właściwy format JS)
    photos_json = json.dumps(history_photos, ensure_ascii=False, indent=4)

    # Wygeneruj zawartość pliku JS
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

    # Zapisz plik
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
    init_locations_db()

    if not check_postgres_available():
        print("❌ PostgreSQL nie jest dostępny!")
        return

    try:
        conn = get_launcher_postgres_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE locations SET homepage_template = %s WHERE id = %s", (template_name, location_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ PostgreSQL błąd: {e}")
        raise

def ensure_location_data_files(location_folder):
    """
    Tworzy wymagane pliki JSON dla miejscowości jeśli nie istnieją.

    Args:
        location_folder: Ścieżka do folderu miejscowości w backup/
    """
    # Słownik z nazwami plików i ich pustymi strukturami
    data_files = {
        'demografia.json': [],
        'genealogia.json': {
            "persons": []
        },
        'map_config.json': {
            "calibration": {
                "sw": {"lat": 0, "lng": 0},
                "ne": {"lat": 0, "lng": 0}
            },
            "defaults": {
                "center": {"lat": 0, "lng": 0},
                "zoom": 15
            }
        },
        'owner_data_to_import.json': {},
        'parcels_data.json': {}
    }

    # Twórz pliki jeśli nie istnieją
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
                history_photos=None, postgres_db_name="", gmina_katastralna="Czarna", miejscowosc_protokolu="Pilzno"):
    """
    Dodaje nową miejscowość do bazy danych PostgreSQL i tworzy folder.

    Args:
        name: Nazwa miejscowości (unikalna)
        full_name: Pełna nazwa
        powiat: Nazwa powiatu
        region: Nazwa regionu
        homepage_template: Szablon strony głównej
        year: Rok mapy katastralnej
        century: Wiek mapy
        homepage_description: Opis na stronie głównej
        history_paragraph1-3: Paragrafy historii
        history_photos: Lista zdjęć historycznych (max 20)

    Returns:
        int: ID nowej miejscowości

    Raises:
        ValueError: Jeśli miejscowość już istnieje
    """
    init_locations_db()

    # Obsłuż history_photos
    if history_photos is None:
        history_photos = []

    # Utwórz folder dla miejscowości
    location_folder = os.path.join(BACKUP_FOLDER, name)
    os.makedirs(location_folder, exist_ok=True)

    # Utwórz folder dla protokołów
    protokoly_folder = os.path.join(location_folder, "protokoly")
    os.makedirs(protokoly_folder, exist_ok=True)

    # Utwórz folder dla zdjęć historycznych
    history_photos_folder = os.path.join(location_folder, "history_photos")
    os.makedirs(history_photos_folder, exist_ok=True)

    # Utwórz wymagane pliki JSON jeśli nie istnieją
    ensure_location_data_files(location_folder)

    # Utwórz domyślny plik .env z nazwą bazy na podstawie postgres_db_name
    env_path = os.path.join(location_folder, ".env")
    if not os.path.exists(env_path):
        # Użyj podanej nazwy bazy lub domyślnej
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
# SERWER FLASK
# =============================================================================
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
FLASK_SECRET_KEY=change-me-{name.lower()}-secret

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

    # Dodaj do bazy danych PostgreSQL
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
                                  gmina_katastralna, miejscowosc_protokolu)
            VALUES (%s, %s, %s, %s, false, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, full_name, powiat, region, homepage_template, year, century,
              homepage_description, history_paragraph1, history_paragraph2, history_paragraph3, postgres_db_name,
              gmina_katastralna, miejscowosc_protokolu))

        location_id = cursor.fetchone()[0]

        # Wstaw zdjęcia historyczne
        for idx, photo in enumerate(history_photos):
            cursor.execute("""
                INSERT INTO history_photos (location_id, filename, caption, order_index)
                VALUES (%s, %s, %s, %s)
            """, (location_id, photo.get('filename', ''), photo.get('caption', ''), idx))

        conn.commit()
        cursor.close()
        conn.close()

        # Automatycznie utwórz bazę danych dla miejscowości (jeśli podano nazwę)
        if postgres_db_name:
            print(f"📦 Tworzę bazę danych: {postgres_db_name}...")
            success, msg = init_location_database(postgres_db_name)
            if success:
                print(msg)
            else:
                print(f"⚠️ {msg}")

        # Utwórz launcher_db_config.json dla nowej miejscowości
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
                    "homepage_description": homepage_description,
                    "history_paragraph1": history_paragraph1,
                    "history_paragraph2": history_paragraph2,
                    "history_paragraph3": history_paragraph3,
                    "history_photos": history_photos,
                    "favicon": "favicon.jpeg",
                    "postgres_db_name": postgres_db_name
                }
            }

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(launcher_config, f, ensure_ascii=False, indent=2)

            print(f"✅ Utworzono launcher_db_config.json dla miejscowości {name}")
        except Exception as e:
            print(f"⚠️ Nie udało się utworzyć launcher_db_config.json: {e}")

        invalidate_locations_cache()  # Unieważnij cache po dodaniu
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
                   gmina_katastralna="Czarna", miejscowosc_protokolu="Pilzno"):
    """
    Aktualizuje dane miejscowości w PostgreSQL.

    Args:
        location_id: ID miejscowości do zaktualizowania
        name: Nowa nazwa miejscowości
        full_name: Nowa pełna nazwa
        powiat: Nowy powiat
        region: Nowy region
        year: Rok mapy
        century: Wiek mapy
        homepage_description: Opis na stronie głównej
        history_paragraph1-3: Paragrafy historii
        history_photos: Lista zdjęć historycznych (max 20)

    Raises:
        ValueError: Jeśli miejscowość nie istnieje lub nazwa już istnieje
    """
    init_locations_db()

    # Obsłuż history_photos
    if history_photos is None:
        history_photos = []

    # PostgreSQL TYLKO
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

        # Zmień nazwę folderu jeśli nazwa się zmieniła
        if old_name != name:
            old_folder = os.path.join(BACKUP_FOLDER, old_name)
            new_folder = os.path.join(BACKUP_FOLDER, name)
            if os.path.exists(old_folder):
                os.rename(old_folder, new_folder)

        cursor.execute("""
            UPDATE locations SET
                name = %s, full_name = %s, powiat = %s, region = %s,
                year = %s, century = %s,
                homepage_description = %s, history_paragraph1 = %s,
                history_paragraph2 = %s, history_paragraph3 = %s,
                postgres_db_name = %s, homepage_template = %s,
                gmina_katastralna = %s, miejscowosc_protokolu = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (name, full_name, powiat, region, year, century,
              homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
              postgres_db_name, homepage_template, gmina_katastralna, miejscowosc_protokolu,
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

        # Zaktualizuj/utwórz launcher_db_config.json dla KAŻDEJ miejscowości
        try:
            location_folder = os.path.join(BASE_DIR, "backup", name)
            os.makedirs(location_folder, exist_ok=True)

            # Upewnij się że folder history_photos istnieje
            history_photos_folder = os.path.join(location_folder, "history_photos")
            os.makedirs(history_photos_folder, exist_ok=True)

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
                    "homepage_description": homepage_description,
                    "history_paragraph1": history_paragraph1,
                    "history_paragraph2": history_paragraph2,
                    "history_paragraph3": history_paragraph3,
                    "history_photos": history_photos,
                    "favicon": "favicon.jpeg",
                    "postgres_db_name": postgres_db_name
                }
            }

            # Zapisz
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(launcher_config, f, ensure_ascii=False, indent=2)

            print(f"✅ Zaktualizowano launcher_db_config.json dla miejscowości {name}")
        except Exception as e:
            print(f"⚠️ Nie udało się zaktualizować launcher_db_config.json: {e}")

        invalidate_locations_cache()  # Unieważnij cache po aktualizacji

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
    """
    Usuwa miejscowość z bazy danych PostgreSQL, folder i bazę danych miejscowości.

    Args:
        location_id: ID miejscowości do usunięcia

    Raises:
        ValueError: Jeśli miejscowość nie istnieje lub jest aktywna
    """
    init_locations_db()

    # PostgreSQL TYLKO
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

        # Usuń bazę danych PostgreSQL dla miejscowości (jeśli istnieje)
        # Jeśli postgres_db_name jest puste, użyj standardowej nazwy
        db_to_delete = postgres_db_name if postgres_db_name else f"mapa_{name.lower()}"

        try:
            print(f"🗑️ Usuwanie bazy danych: {db_to_delete}")
            config = get_postgres_config()

            # Połącz się do bazy postgres (nie do usuwanej bazy)
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            db_conn = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database='postgres'
            )
            db_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            db_cursor = db_conn.cursor()

            # Zakończ wszystkie połączenia do bazy przed usunięciem
            db_cursor.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_to_delete}'
                AND pid <> pg_backend_pid()
            """)

            # Usuń bazę danych
            db_cursor.execute(f'DROP DATABASE IF EXISTS "{db_to_delete}"')
            db_cursor.close()
            db_conn.close()
            print(f"✅ Usunięto bazę danych: {db_to_delete}")
        except Exception as db_err:
            print(f"⚠️ Ostrzeżenie: Nie udało się usunąć bazy danych {db_to_delete}: {db_err}")
            # Kontynuuj mimo błędu - folder i wpis w locations i tak zostaną usunięte

        # Usuń folder z danymi
        location_folder = os.path.join(BACKUP_FOLDER, name)
        if os.path.exists(location_folder):
            shutil.rmtree(location_folder)
            print(f"✅ Usunięto folder: {location_folder}")

        # Usuń wpis z tabeli locations
        cursor.execute("DELETE FROM locations WHERE id = %s", (location_id,))
        conn.commit()
        cursor.close()
        conn.close()

        invalidate_locations_cache()  # Unieważnij cache po usunięciu
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
    config_file = os.path.join(BASE_DIR, "backup", "Czarna", "launcher_db_config.json")
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
    init_locations_db()

    # Sprawdź czy są jakiekolwiek miejscowości
    locations = get_all_locations()
    if locations:
        # Jeśli są miejscowości, sprawdź czy któraś jest aktywna
        active_location = get_active_location()
        if not active_location:
            # Ustaw pierwszą miejscowość jako aktywną
            set_active_location(locations[0][0])
        return

    # Utwórz domyślną miejscowość używając konfiguracji z JSON
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
            postgres_db_name=default_loc.get('postgres_db_name', 'mapa_czarna_db')
        )
        set_active_location(location_id)
        print(f"✓ Utworzono domyślną miejscowość: {default_name}")
    except Exception as e:
        print(f"⚠ Błąd tworzenia domyślnej miejscowości: {e}")

def get_location_env_path(location_name=None):
    """Zwraca ścieżkę do pliku .env dla danej miejscowości."""
    if location_name is None:
        # Upewnij się, że istnieje domyślna miejscowość
        ensure_default_location_exists()
        location_name = get_active_location_name()

    if not location_name:
        raise ValueError("Brak aktywnej miejscowości")

    return os.path.join(BACKUP_FOLDER, location_name, ".env")

def migrate_old_backup_structure():
    """Migruje starą strukturę backup/ do nowej struktury z miejscowościami."""
    # NIE WYWOŁUJ init_locations_db() tutaj - dzieje się przed setup_postgres_config()!
    # init_locations_db() będzie wywołane później przez auto_initialize_on_startup()

    # Sprawdź czy już są miejscowości (jeśli PostgreSQL dostępny)
    if check_postgres_available():
        try:
            conn = get_launcher_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM locations")
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            if count > 0:
                # Już są miejscowości - nic nie rób
                return
        except:
            pass  # Baza jeszcze nie istnieje, to normalne

    print("🔄 Migracja struktury folderów backup...")

    # Sprawdź czy są stare pliki w backup/
    old_files = [
        "owner_data_to_import.json",
        "parcels_data.json",
        "demografia.json",
        "genealogia.json",
        "map_config.json"
    ]

    has_old_files = any(os.path.exists(os.path.join(BACKUP_FOLDER, f)) for f in old_files)

    if not has_old_files:
        print("ℹ️ Brak starych plików do migracji")
        return

    # Utwórz domyślną miejscowość "Czarna"
    default_location_name = "Czarna"
    default_location_folder = os.path.join(BACKUP_FOLDER, default_location_name)

    try:
        # Utwórz folder dla miejscowości
        os.makedirs(default_location_folder, exist_ok=True)

        # Przenieś stare pliki
        for filename in old_files:
            old_path = os.path.join(BACKUP_FOLDER, filename)
            if os.path.exists(old_path):
                new_path = os.path.join(default_location_folder, filename)
                shutil.move(old_path, new_path)
                print(f"✅ Przeniesiono: {filename}")

        # Przenieś plik .env jeśli istnieje
        old_env_path = os.path.join(BACKEND_DIR, ".env")
        if os.path.exists(old_env_path):
            new_env_path = os.path.join(default_location_folder, ".env")
            shutil.copy2(old_env_path, new_env_path)
            print(f"✅ Skopiowano: .env")

        # Dodaj miejscowość do bazy danych używając konfiguracji z JSON
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
            postgres_db_name=default_loc.get('postgres_db_name', 'mapa_czarna_db')
        )
        set_active_location(1)  # Ustaw jako aktywną (pierwsze ID to 1)

        print(f"✅ Migracja zakończona! Utworzono miejscowość: {default_location_name}")

    except Exception as e:
        print(f"❌ Błąd podczas migracji: {e}")
        import traceback
        traceback.print_exc()

# ==================== Funkcje zarządzania szablonami strony głównej ====================

HOMEPAGE_DIR = os.path.join(BASE_DIR, "strona_glowna")
TEMPLATES_DIR = os.path.join(HOMEPAGE_DIR, "szablony")

def get_available_templates():
    """Zwraca listę dostępnych szablonów strony głównej."""
    templates = []
    if os.path.exists(TEMPLATES_DIR):
        for item in os.listdir(TEMPLATES_DIR):
            template_path = os.path.join(TEMPLATES_DIR, item)
            if os.path.isdir(template_path):
                index_path = os.path.join(template_path, "index.html")
                if os.path.exists(index_path):
                    templates.append(item)
    return templates

def apply_homepage_template(template_name):
    """
    Aplikuje wybrany szablon strony głównej.

    Args:
        template_name: Nazwa szablonu (np. 'standardowy', 'praca_inzynierska')

    Returns:
        True jeśli sukces, False w przeciwnym razie
    """
    template_path = os.path.join(TEMPLATES_DIR, template_name, "index.html")
    target_path = os.path.join(HOMEPAGE_DIR, "index.html")

    if not os.path.exists(template_path):
        print(f"❌ Szablon '{template_name}' nie istnieje")
        return False

    try:
        # Dla szablonu standardowego - zastąp placeholdery danymi miejscowości
        if template_name == "standardowy":
            active_location = get_active_location()
            if not active_location:
                print("❌ Brak aktywnej miejscowości")
                return False

            # Pobierz dane miejscowości: (id, name, full_name, powiat, region, active, homepage_template, year, century)
            location_name = active_location[1]
            location_full_name = active_location[2] or location_name
            location_powiat = active_location[3] or "Powiat"
            location_region = active_location[4] or "Region"
            location_year = active_location[7] if len(active_location) > 7 else "1882"
            location_century = active_location[8] if len(active_location) > 8 else "XIX w."

            # Wczytaj szablon
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Zastąp placeholdery - tylko jeśli wartość nie jest pusta
            if location_name:
                content = content.replace('{{MIEJSCOWOSC}}', location_name)
            if location_full_name:
                content = content.replace('{{MIEJSCOWOSC_PELNA}}', location_full_name)
            if location_powiat:
                content = content.replace('{{POWIAT}}', location_powiat)
            if location_region:
                content = content.replace('{{REGION}}', location_region)
            if location_year:
                content = content.replace('{{YEAR}}', location_year)
            if location_century:
                content = content.replace('{{WIEK}}', location_century)

            # Zapisz
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ Zastosowano szablon 'standardowy' dla miejscowości: {location_full_name} ({location_year})")

        else:
            # Dla innych szablonów - po prostu skopiuj
            shutil.copy2(template_path, target_path)
            print(f"✅ Zastosowano szablon: {template_name}")

        return True

    except Exception as e:
        print(f"❌ Błąd podczas aplikowania szablonu: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==================== Koniec funkcji zarządzania szablonami ====================

def get_data_files(location_name=None):
    """Zwraca słownik ścieżek plików danych dla danej miejscowości."""
    if location_name is None:
        location_name = get_active_location_name()

    location_folder = os.path.join(BACKUP_FOLDER, location_name) if location_name else BACKUP_FOLDER

    return {
        "owners": {
            "path": os.path.join(location_folder, "owner_data_to_import.json"),
            "name": "Właściciele i Demografia",
            "related": [os.path.join(location_folder, "demografia.json")],
        },
        "parcels": {
            "path": os.path.join(location_folder, "parcels_data.json"),
            "name": "Działki (Geometria)",
            "related": [],
        },
        "genealogy": {
            "path": os.path.join(location_folder, "genealogia.json"),
            "name": "Genealogia",
            "related": [],
        },
    }

# Dla kompatybilności wstecznej
DATA_FILES = get_data_files()

URLS = {
    "strona_glowna": "http://127.0.0.1:5000/strona_glowna/index.html",
    "mapa": "http://127.0.0.1:5000/mapa/mapa.html",
    "admin": "http://127.0.0.1:5000/admin",
    "genealogy_editor": "http://127.0.0.1:5001/",
}

SCRIPTS = {
    "backend": {"path": os.path.join(BACKEND_DIR, "app.py"), "cwd": BACKEND_DIR},
    "migration": {"path": os.path.join(BACKEND_DIR, "migrate_data.py"), "cwd": BACKEND_DIR},
    "tests": {"path": "-m", "args": ["pytest", "tests", "-q"], "cwd": BACKEND_DIR},
    "owner_editor": {"path": os.path.join(TOOLS_DIR, "owner_editor.py"), "cwd": TOOLS_DIR},
    "parcel_editor": {"path": os.path.join(TOOLS_DIR, "parcel_editor", "parcel_editor_app.py"), "cwd": os.path.join(TOOLS_DIR, "parcel_editor")},
    "genealogy_editor": {"path": os.path.join(TOOLS_DIR, "genealogy_editor", "editor_app.py"), "cwd": os.path.join(TOOLS_DIR, "genealogy_editor")},
}

COLORS = {
    'primary': '#0d6efd', 'success': '#198754', 'danger': '#dc3545',
    'warning': '#ffc107', 'info': '#0dcaf0', 'secondary': '#6c757d',
    'dark': '#212529', 'light': '#f8f9fa',
}

# =============================================================================
# FUNKCJE POMOCNICZE
# =============================================================================
def get_local_ip():
    """Pobiera lokalny adres IP komputera."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def check_env_configuration():
    """Sprawdza i konfiguruje plik .env dla aktywnej miejscowości."""
    # Pobierz ścieżkę do .env aktywnej miejscowości
    try:
        env_path = get_location_env_path()
    except ValueError:
        # Brak aktywnej miejscowości - nie powinno się zdarzyć
        # ale obsłuż to dla bezpieczeństwa
        return False

    env_example_path = os.path.join(BACKEND_DIR, ".env.example")

    if os.path.exists(env_path):
        return True

    if os.path.exists(env_example_path):
        try:
            # Upewnij się, że folder istnieje
            os.makedirs(os.path.dirname(env_path), exist_ok=True)
            shutil.copy(env_example_path, env_path)
            print("✅ Utworzono plik .env z przykładowej konfiguracji")
            return True
        except Exception as e:
            print(f"⚠️ Nie można utworzyć pliku .env: {e}")
            return False

    try:
        default_env = """# =============================================================================
# KONFIGURACJA MIEJSCOWOŚCI
# =============================================================================
# Konfiguracja PostgreSQL (host, port, user, password) jest w backend/.postgres.env

# =============================================================================
# BAZA DANYCH
# =============================================================================
DB_NAME=mapa_czarna_db

# =============================================================================
# SERWER FLASK
# =============================================================================
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
FLASK_SECRET_KEY=change-me-once

# =============================================================================
# AUTENTYKACJA ADMINISTRATORA
# =============================================================================
ADMIN_AUTH_ENABLED=0
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=
"""
        # Upewnij się, że folder istnieje
        os.makedirs(os.path.dirname(env_path), exist_ok=True)
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(default_env)
        print("✅ Utworzono domyślny plik .env")
        return True
    except Exception as e:
        print(f"⚠️ Nie można utworzyć pliku .env: {e}")
        return False

def setup_postgres_config(parent=None):
    """
    Sprawdza czy plik .postgres.env istnieje.
    Jeśli nie - wyświetla okno z wymaganiem PostgreSQL i polem hasła z automatyczną walidacją.

    Args:
        parent: Okno rodzica (główne okno aplikacji). Jeśli None, utworzy własne.
    """
    # Sprawdź czy plik już istnieje
    if os.path.exists(POSTGRES_CONFIG_FILE):
        return True

    print("⚠️ Brak pliku konfiguracji PostgreSQL (.postgres.env)")
    print("ℹ️ Launcher potrzebuje danych dostępu do PostgreSQL aby działać prawidłowo.")

    # Jeśli nie ma parent, utwórz tymczasowe okno główne
    if parent is None:
        temp_root = tk.Tk()
        temp_root.withdraw()
        parent_window = temp_root
    else:
        parent_window = parent

    # Zmienna do przechowania wyniku
    config_result = {'success': False, 'password': None}

    # Utwórz dialog
    dialog = tk.Toplevel(parent_window)
    dialog.title("🔧 Konfiguracja PostgreSQL - WYMAGANE")
    dialog.geometry("700x680")
    dialog.resizable(False, False)

    # Wyśrodkuj okno
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (700 // 2)
    y = (dialog.winfo_screenheight() // 2) - (680 // 2)
    dialog.geometry(f"700x680+{x}+{y}")

    # Zablokuj interakcję z innymi oknami
    dialog.grab_set()
    dialog.focus_force()
    dialog.attributes('-topmost', True)  # Zawsze na wierzchu

    # Ramka główna z gradientem (symulacja przez ramki)
    main_frame = tk.Frame(dialog, bg='#f8f9fa', padx=40, pady=30)
    main_frame.pack(fill='both', expand=True)

    # Komunikat o wymaganiu PostgreSQL - większy i bardziej widoczny
    warning_frame = tk.Frame(main_frame, bg='#FFF3CD', relief='solid', borderwidth=2, padx=20, pady=15)
    warning_frame.pack(fill='x', pady=(0, 25))

    warning_icon = tk.Label(
        warning_frame,
        text="⚠️",
        font=('Segoe UI', 32),
        bg='#FFF3CD',
        fg='#856404'
    )
    warning_icon.pack(pady=(0, 5))

    warning_label = tk.Label(
        warning_frame,
        text="Program wymaga PostgreSQL do działania!",
        font=('Segoe UI', 14, 'bold'),
        bg='#FFF3CD',
        fg='#856404',
        justify='center'
    )
    warning_label.pack()

    warning_sublabel = tk.Label(
        warning_frame,
        text="Podaj dane połączenia z PostgreSQL",
        font=('Segoe UI', 10),
        bg='#FFF3CD',
        fg='#856404',
        justify='center'
    )
    warning_sublabel.pack(pady=(5, 0))

    # Formularz z polami konfiguracji
    form_frame = tk.Frame(main_frame, bg='#f8f9fa')
    form_frame.pack(fill='x', pady=(0, 20))

    # Host
    host_label = tk.Label(
        form_frame,
        text="Host:",
        font=('Segoe UI', 11, 'bold'),
        bg='#f8f9fa',
        anchor='w'
    )
    host_label.grid(row=0, column=0, sticky='w', pady=(0, 5), padx=(0, 10))

    host_entry = tk.Entry(
        form_frame,
        font=('Segoe UI', 12),
        relief='solid',
        borderwidth=2
    )
    host_entry.insert(0, 'localhost')
    host_entry.grid(row=0, column=1, sticky='ew', pady=(0, 5), ipady=6)

    # Port
    port_label = tk.Label(
        form_frame,
        text="Port:",
        font=('Segoe UI', 11, 'bold'),
        bg='#f8f9fa',
        anchor='w'
    )
    port_label.grid(row=1, column=0, sticky='w', pady=(0, 5), padx=(0, 10))

    port_entry = tk.Entry(
        form_frame,
        font=('Segoe UI', 12),
        relief='solid',
        borderwidth=2
    )
    port_entry.insert(0, '5432')
    port_entry.grid(row=1, column=1, sticky='ew', pady=(0, 5), ipady=6)

    # Użytkownik
    user_label = tk.Label(
        form_frame,
        text="Użytkownik:",
        font=('Segoe UI', 11, 'bold'),
        bg='#f8f9fa',
        anchor='w'
    )
    user_label.grid(row=2, column=0, sticky='w', pady=(0, 5), padx=(0, 10))

    user_entry = tk.Entry(
        form_frame,
        font=('Segoe UI', 12),
        relief='solid',
        borderwidth=2
    )
    user_entry.insert(0, 'postgres')
    user_entry.grid(row=2, column=1, sticky='ew', pady=(0, 5), ipady=6)

    # Hasło
    password_label = tk.Label(
        form_frame,
        text="Hasło:",
        font=('Segoe UI', 11, 'bold'),
        bg='#f8f9fa',
        anchor='w'
    )
    password_label.grid(row=3, column=0, sticky='w', pady=(0, 5), padx=(0, 10))

    password_entry = tk.Entry(
        form_frame,
        font=('Segoe UI', 12),
        show='*',
        relief='solid',
        borderwidth=2
    )
    password_entry.grid(row=3, column=1, sticky='ew', pady=(0, 5), ipady=6)
    password_entry.focus()

    # Konfiguracja kolumn - druga kolumna rozciągliwa
    form_frame.columnconfigure(1, weight=1)

    # Status label - większa ikona
    status_label = tk.Label(
        main_frame,
        text="",
        font=('Segoe UI', 56),
        bg='#f8f9fa',
        height=1
    )
    status_label.pack(pady=(15, 25))

    # Przycisk Kontynuuj
    ok_button = tk.Button(
        main_frame,
        text="KONTYNUUJ",
        font=('Segoe UI', 13, 'bold'),
        bg='#6c757d',
        fg='white',
        activebackground='#0056b3',
        activeforeground='white',
        relief='raised',
        borderwidth=2,
        cursor='hand2',
        state='disabled',
        padx=50,
        pady=15,
        command=lambda: dialog.destroy()
    )
    ok_button.pack(pady=(0, 10))

    # Timer do debounce
    test_timer = None

    def test_password():
        """Testuje hasło i wyświetla wynik"""
        nonlocal test_timer
        test_timer = None

        # Pobierz wartości ze wszystkich pól
        host = host_entry.get().strip()
        port = port_entry.get().strip()
        user = user_entry.get().strip()
        password = password_entry.get()

        # Walidacja podstawowa
        if not password:
            status_label.config(text="", fg='black')
            ok_button.config(state='disabled', bg='#6c757d')
            return

        if not host or not port or not user:
            status_label.config(text="✗", fg='#dc3545')
            ok_button.config(state='disabled', bg='#6c757d')
            return

        # Walidacja portu
        try:
            port_int = int(port)
            if port_int < 1 or port_int > 65535:
                raise ValueError("Port poza zakresem")
        except ValueError:
            status_label.config(text="✗", fg='#dc3545')
            ok_button.config(state='disabled', bg='#6c757d')
            return

        # Testuj połączenie
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=host,
                port=port_int,
                user=user,
                password=password,
                connect_timeout=3
            )
            conn.close()

            # Sukces - pokaż zieloną fajkę
            status_label.config(text="✓", fg='#28a745')
            ok_button.config(state='normal', bg='#28a745')

            # Zapisz konfigurację
            config_content = f"""# =============================================================================
# KONFIGURACJA BAZY DANYCH POSTGRESQL DLA LAUNCHERA
# =============================================================================
LAUNCHER_DB_HOST={host}
LAUNCHER_DB_PORT={port_int}
LAUNCHER_DB_USER={user}
LAUNCHER_DB_PASSWORD={password}
"""
            with open(POSTGRES_CONFIG_FILE, 'w', encoding='utf-8') as f:
                f.write(config_content)

            print(f"✅ Utworzono plik konfiguracji: {POSTGRES_CONFIG_FILE}")

            # Wyczyść cache sprawdzania dostępności PostgreSQL
            global POSTGRES_AVAILABLE
            POSTGRES_AVAILABLE = None

            config_result['success'] = True
            config_result['password'] = password

        except Exception as e:
            # Błąd - pokaż czerwony X
            status_label.config(text="✗", fg='#dc3545')
            ok_button.config(state='disabled', bg='#6c757d')

    def on_field_change(event=None):
        """Wywoływane gdy użytkownik zmienia wartość w jakimkolwiek polu"""
        nonlocal test_timer

        # Anuluj poprzedni timer
        if test_timer is not None:
            dialog.after_cancel(test_timer)

        # Sprawdź czy hasło jest wypełnione
        password = password_entry.get()
        if not password:
            status_label.config(text="", fg='black')
            ok_button.config(state='disabled', bg='#6c757d')
            return

        # Ustaw nowy timer (debouncing - 1 sekunda)
        test_timer = dialog.after(1000, test_password)

    # Bind event do automatycznego testowania dla wszystkich pól
    host_entry.bind('<KeyRelease>', on_field_change)
    port_entry.bind('<KeyRelease>', on_field_change)
    user_entry.bind('<KeyRelease>', on_field_change)
    password_entry.bind('<KeyRelease>', on_field_change)

    # Enter key obsługa - zamknij jeśli hasło jest poprawne
    def on_enter(event=None):
        if ok_button['state'] == 'normal':
            dialog.destroy()

    password_entry.bind('<Return>', on_enter)

    # Obsługa zamknięcia okna (X w prawym górnym rogu)
    def on_closing():
        print("❌ Anulowano konfigurację PostgreSQL. Program nie może działać bez PostgreSQL!")
        from tkinter import messagebox
        messagebox.showerror(
            "Błąd - PostgreSQL Wymagany",
            "Program wymaga PostgreSQL do działania.\n\n"
            "Bez konfiguracji bazy danych launcher nie może być uruchomiony.\n\n"
            "Zainstaluj PostgreSQL i uruchom program ponownie."
        )
        # Zamknij okno parent tylko jeśli stworzyliśmy je sami
        if parent is None:
            parent_window.destroy()
        sys.exit(1)

    dialog.protocol("WM_DELETE_WINDOW", on_closing)

    # Czekaj na zamknięcie okna
    dialog.wait_window()

    # Zamknij tymczasowe okno główne jeśli stworzyliśmy je sami
    if parent is None:
        parent_window.destroy()

    return config_result['success']

def _auto_sync_site_icon():
    """Sprawdza czy favicon istnieje w folderze backup aktywnej miejscowości.
    Favicon jest serwowany bezpośrednio z folderu backup przez endpoint /location_favicon,
    więc nie ma potrzeby kopiowania go do assets/site."""

    try:
        location_name = get_active_location_name()
        if not location_name:
            print("ℹ️ Brak aktywnej miejscowości dla favicon")
            return

        backup_location_folder = os.path.join(BACKUP_FOLDER, location_name)

        # Sprawdź czy istnieje favicon w różnych formatach
        favicon_extensions = ['.ico', '.png', '.jpg', '.jpeg']
        favicon_found = False

        for ext in favicon_extensions:
            favicon_path = os.path.join(backup_location_folder, f"favicon{ext}")
            if os.path.exists(favicon_path):
                print(f"✅ Favicon znaleziony w backup/{location_name}/favicon{ext}")
                favicon_found = True
                break

        if not favicon_found:
            print(f"ℹ️ Brak favicon w backup/{location_name}/ - favicon będzie używał domyślnej ikony")

    except Exception as e:
        print(f"⚠️ Błąd podczas sprawdzania favicon: {e}")

def check_backup_folder_files():
    """Sprawdza folder aktywnej miejscowości i tworzy brakujące pliki JSON."""
    location_name = get_active_location_name()
    if not location_name:
        print("ℹ️ Brak aktywnej miejscowości, pomijam tworzenie plików danych")
        return

    location_folder = os.path.join(BACKUP_FOLDER, location_name)

    files_to_check = {
        "map_config.json": {
            "calibration": {"sw": {"lat": 50.0414, "lng": 21.2261}, "ne": {"lat": 50.0814, "lng": 21.2661}},
            "defaults": {"center": {"lat": 50.0614, "lng": 21.2461}, "zoom": 14}
        },
        "owner_data_to_import.json": {},
        "parcels_data.json": {},
        "demografia.json": [],
        "genealogia.json": {"persons": []}
    }

    os.makedirs(location_folder, exist_ok=True)

    for filename, default_content in files_to_check.items():
        path = os.path.join(location_folder, filename)
        if not os.path.exists(path):
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(default_content, f, indent=4, ensure_ascii=False)
                print(f"✅ Utworzono domyślny plik: {filename}")
            except Exception as e:
                print(f"⚠️ Nie można utworzyć pliku {filename}: {e}")

def read_env_config(key_prefix=None):
    """Odczytuje konfigurację z pliku .env aktywnej miejscowości."""
    # Sprawdź czy jest aktywna miejscowość
    # Pobierz ścieżkę do .env aktywnej miejscowości
    try:
        env_path = get_location_env_path()
    except ValueError:
        # Brak aktywnej miejscowości
        return {}

    config = {}

    if not os.path.exists(env_path):
        return config

    # Spróbuj różnych kodowań (utf-8, cp1250, latin-1)
    for encoding in ['utf-8', 'cp1250', 'latin-1']:
        try:
            with open(env_path, 'r', encoding=encoding) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key, value = key.strip(), value.strip()
                        if not key_prefix or key.startswith(key_prefix):
                            config[key] = value
            break  # Jeśli udało się odczytać, przerwij pętlę
        except (UnicodeDecodeError, Exception) as e:
            if encoding == 'latin-1':  # latin-1 nigdy nie powinno rzucić UnicodeDecodeError
                print(f"Błąd odczytu .env: {e}")
            continue  # Spróbuj kolejnego kodowania

    return config

def get_db_config_from_env():
    """Odczytuje konfigurację bazy danych z pliku .env."""
    env_config = read_env_config('DB_')
    return {
        "host": env_config.get('DB_HOST', 'localhost'),
        "dbname": env_config.get('DB_NAME', 'mapa_czarna_db'),
        "user": env_config.get('DB_USER', 'postgres'),
        "password": env_config.get('DB_PASSWORD', '1234'),
        "port": env_config.get('DB_PORT', '5432')
    }

def get_flask_config():
    """Odczytuje konfigurację Flask z pliku .env."""
    env_config = read_env_config('FLASK_')
    return {
        'host': env_config.get('FLASK_HOST', '127.0.0.1'),
        'port': env_config.get('FLASK_PORT', '5000')
    }

# =============================================================================
# GŁÓWNA KLASA APLIKACJI
# =============================================================================
class AppLauncher(tk.Tk):
    """Główna klasa aplikacji centrum zarządzania."""
    
    def __init__(self):
        """Inicjalizacja głównego okna aplikacji."""
        super().__init__()
        self.title("🗺️ Centrum Zarządzania - System Mapy Katastralnej")
        self.setup_window_geometry()

        self.managed_processes = {}
        self.event_queue = queue.Queue()
        self._refresh_pending = False  # Debounce flag
        self._cached_locations = None  # Cache lokacji w pamięci
        self._displayed_processes = {}  # Cache wyświetlanych procesów (unikaj przebudowy UI)
        self._log_buffer = {}  # Buffer logów dla każdej konsoli (batching)
        self._log_flush_pending = False  # Flaga pending flush
        self.setup_styles()

        # UKRYJ główne okno przed konfiguracją PostgreSQL
        self.withdraw()

        # Migracja starych danych
        migrate_old_backup_structure()

        # Sprawdź konfigurację PostgreSQL (pyta o hasło jeśli potrzebne)
        # Przekazujemy self jako parent żeby dialog był przypisany do głównego okna
        setup_postgres_config(parent=self)

        # POKAŻ główne okno po konfiguracji PostgreSQL
        self.deiconify()

        # Zawsze tworzymy okno ładowania dla lepszej UX
        loading_dialog = LoadingDialog()
        loading_dialog.update_status("Inicjalizacja...", "Sprawdzanie konfiguracji")

        # Automatyczna inicjalizacja baz przy pierwszym uruchomieniu
        # Przekazujemy loading_dialog żeby funkcja mogła aktualizować postęp
        auto_initialize_on_startup(loading_dialog)

        # Kontynuuj inicjalizację z oknem ładowania
        loading_dialog.update_status("Konfiguracja plików...", "Sprawdzanie środowiska")

        check_env_configuration()
        check_backup_folder_files()

        loading_dialog.update_status("Synchronizacja ikon...", "Favicon i zasoby")

        _auto_sync_site_icon()

        # Automatycznie odśwież strony HTML z placeholderami (w tle aby nie blokować startu)
        loading_dialog.update_status("Aktualizacja stron HTML...", "Generowanie szablonów")

        def _async_refresh():
            try:
                self.refresh_html_pages()
                print("✅ Strony HTML i konfiguracja zaktualizowane w tle")
            except Exception as e:
                print(f"⚠️ Błąd podczas generowania plików: {e}")

        # Uruchom w tle - nie blokuj GUI
        threading.Thread(target=_async_refresh, daemon=True).start()

        # Zamknij okno ładowania i pokaż podsumowanie
        loading_dialog.update_status("System gotowy!", "Uruchamianie interfejsu...")
        import time
        time.sleep(0.5)
        loading_dialog.close()

        # Pokaż podsumowanie inicjalizacji
        if hasattr(loading_dialog, 'init_summary'):
            summary = loading_dialog.init_summary
            if summary['created_launcher'] or summary['created_czarna_location'] or \
               summary['created_czarna_db'] or summary['migrated_data']:

                message = "🎉 System jest gotowy do użycia!\n\n"

                if summary['created_launcher']:
                    message += "✅ Utworzono bazę mapa_launcher_db\n"
                else:
                    message += "✅ Baza mapa_launcher_db gotowa\n"

                if summary['created_czarna_location']:
                    message += "✅ Utworzono miejscowość 'Czarna'\n"
                else:
                    message += "✅ Miejscowość 'Czarna' gotowa\n"

                if summary['created_czarna_db']:
                    message += "✅ Utworzono bazę mapa_czarna_db\n"
                else:
                    message += "✅ Baza mapa_czarna_db gotowa\n"

                if summary['migrated_data']:
                    message += "✅ Dane zmigrowane z backup/Czarna\n"

                message += "\n💡 Możesz teraz:\n"
                message += "• Włączyć serwer i zobaczyć mapę\n"
                message += "• Edytować dane właścicieli\n"
                message += "• Kalibrować mapę\n"
                message += "• Zarządzać miejscowościami"

                messagebox.showinfo("System gotowy!", message)

        self.create_widgets()

        # Odroczone operacje I/O - wykonaj po pełnej inicjalizacji GUI (nie blokuj startu)
        self.after(10, self.refresh_locations)  # Załaduj lokacje asynchronicznie
        self.after(30, self.refresh_quick_links)  # Konfiguruj przyciski szybkiego dostępu
        self.after(40, self.start_env_watcher)  # Uruchom watcher pliku .env
        self.after(20, lambda: setattr(self, '_last_port', self.load_flask_config().get("port")))

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.process_queue()

    def setup_window_geometry(self):
        """Inteligentnie dostosowuje rozmiar okna do ekranu i DPI."""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        dpi = self.winfo_fpixels("1i")
        scale_factor = dpi / 96
        
        if sw <= 1920:
            w, h = min(int(sw * 0.85), 1400), min(int(sh * 0.85), 850)
        elif sw <= 2560:
            w, h = min(int(sw * 0.75), 1600), min(int(sh * 0.80), 900)
        else:
            w, h = min(int(sw * 0.65), 1800), min(int(sh * 0.75), 1000)
        
        if scale_factor > 1.25:
            w = int(w / scale_factor * 1.2)
            h = int(h / scale_factor * 1.2)
        
        min_w = max(1000, int(900 * scale_factor))
        min_h = max(700, int(650 * scale_factor))
        w, h = max(w, min_w), max(h, min_h)
        
        x = (sw - w) // 2
        y = (sh - h) // 2
        
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min_w, min_h)
        self.scale_factor = scale_factor
        self.is_high_dpi = scale_factor > 1.25

    def setup_styles(self):
        """Konfiguruje style i czcionki dla aplikacji."""
        dpi = self.winfo_fpixels("1i")
        scale = dpi / 96
        self.tk.call("tk", "scaling", scale)
        
        base_size = 10 if scale <= 1.25 else (11 if scale <= 1.5 else 12)
        
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=base_size)
        
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        
        button_padding = int(6 * scale) if scale > 1.25 else 8
        self.style.configure("TButton", padding=button_padding, relief="flat", font=("Segoe UI", base_size))
        
        # Konfiguracja kolorów przycisków
        for name, color in [("Primary", COLORS['primary']), ("Success", COLORS['success']), 
                            ("Danger", COLORS['danger']), ("Info", COLORS['info']), 
                            ("Warning", COLORS['warning'])]:
            fg = "white" if name != "Warning" else "black"
            self.style.configure(f"{name}.TButton", foreground=fg, background=color)
            darker = color.replace('f', 'd').replace('e', 'c')
            self.style.map(f"{name}.TButton", background=[('active', darker), ('pressed', darker)])
        
        self.style.configure("Link.TLabel", foreground=COLORS['primary'], font=("Segoe UI", base_size, "underline"))
        self.style.configure("Heading.TLabel", font=("Segoe UI", base_size + 2, "bold"))
        
        row_height = int(base_size * 2.2)
        self.style.configure("Treeview", rowheight=row_height, font=("Segoe UI", base_size))
        self.style.configure("Treeview.Heading", font=("Segoe UI", base_size, "bold"))
        
        self.base_font_size = base_size

    def create_console_widget(self, parent):
        """Tworzy widget konsoli z ciemnym motywem."""
        console = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, bg="#1e1e1e", fg="#e0e0e0",
            font=("Consolas", self.base_font_size),
            insertbackground="#ffffff", selectbackground="#3a3a3a",
            selectforeground="#ffffff", height=10
        )
        console.pack(fill=tk.BOTH, expand=True)
        console.configure(state="disabled")
        return console

    def process_queue(self):
        """Przetwarza zdarzenia z kolejki w pętli głównej."""
        try:
            while True:
                event = self.event_queue.get_nowait()

                # Obsługa różnych formatów eventów
                if len(event) == 2:
                    # Stary format: (key, event_type)
                    key, event_type = event
                    if event_type == "finished":
                        self.handle_process_finished(key)
                elif len(event) == 3:
                    # Nowy format: (event_type, data1, data2)
                    event_type, data1, data2 = event
                    if event_type == "location_changed":
                        messagebox.showinfo("✅ Zmieniono miejscowość",
                                          f"Aktywna miejscowość: {data1}\n\n"
                                          "Niektóre zmiany mogą wymagać ponownego uruchomienia serwera.")
                    elif event_type == "location_error":
                        messagebox.showerror("Błąd", f"Nie udało się zmienić miejscowości:\n{data2}")
        except queue.Empty:
            pass
        finally:
            self.after(150, self.process_queue)  # Zmniejszona częstotliwość (był 100ms)

    def handle_process_finished(self, key):
        """Obsługuje zdarzenie zakończenia procesu."""
        if key not in self.managed_processes:
            return
            
        info = self.managed_processes[key]
        name = info["name"]
        
        msg = f"--- Proces '{name}' zakończył działanie ---\n"
        self.log(msg, console=info["console"])
        self.log(msg)
        
        self.notebook.forget(info["tab_frame"])
        del self.managed_processes[key]
        self.update_processes_ui()
        
        if key == "backend":
            self.server_btn.config(text="🚀 Uruchom Serwer Backend", style="Success.TButton")
            self.network_server_btn.config(text="🌐 Uruchom Serwer Sieciowy", style="Info.TButton")
            
            if info.get("network_mode"):
                messagebox.showwarning(
                    "Serwer sieciowy się wyłączył",
                    "Proces zakończył się niespodziewanie.\n\n"
                    "Diagnostyka: uruchom ręcznie w folderze backend:\n"
                    "python _network_server_wrapper.py"
                )

    def create_widgets(self):
        """Tworzy kompletny interfejs użytkownika."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Nagłówek
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            header_frame, text="🗺️ System Zarządzania Mapą Katastralną",
            style="Heading.TLabel", font=("Segoe UI", self.base_font_size + 4, "bold")
        ).pack(side=tk.LEFT)
        
        ttk.Label(header_frame, text="Status: Gotowy", foreground=COLORS['success']).pack(side=tk.RIGHT, padx=10)

        # Sekcja wyboru miejscowości
        location_frame = ttk.LabelFrame(main_frame, text="📍 Miejscowość", padding="10")
        location_frame.pack(fill=tk.X, pady=5)

        location_controls = ttk.Frame(location_frame)
        location_controls.pack(fill=tk.X)

        ttk.Label(location_controls, text="Aktywna miejscowość:", font=("Segoe UI", self.base_font_size)).pack(side=tk.LEFT, padx=5)

        self.location_var = tk.StringVar()
        self.location_combo = ttk.Combobox(location_controls, textvariable=self.location_var, state="readonly", width=30)
        self.location_combo.pack(side=tk.LEFT, padx=5)
        self.location_combo.bind("<<ComboboxSelected>>", self.on_location_selected)

        ttk.Button(location_controls, text="🔄 Odśwież", command=self.refresh_locations,
                  style="Info.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(location_controls, text="⚙️ Zarządzaj Miejscowościami", command=self.open_location_manager,
                  style="Primary.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(location_controls, text="🔧 Zarządzanie Bazą Danych", command=self.open_database_wizard,
                  style="Info.TButton").pack(side=tk.LEFT, padx=5)

        # Odłóż refresh_locations() - wykonaj po pełnej inicjalizacji GUI
        # Usuń: self.refresh_locations() - zostanie wywołane w __init__ po create_widgets()

        # Sekcja operacji głównych
        operations_frame = ttk.LabelFrame(main_frame, text="⚙️ Operacje Główne", padding="10")
        operations_frame.pack(fill=tk.X, pady=5)
        
        # Pierwszy rząd przycisków
        row1 = ttk.Frame(operations_frame)
        row1.pack(fill=tk.X, pady=(0, 5))
        
        self.server_btn = ttk.Button(row1, text="🚀 Uruchom Serwer Backend", command=self.toggle_server, style="Success.TButton")
        self.server_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.network_server_btn = ttk.Button(row1, text="🌐 Uruchom Serwer Sieciowy", command=self.toggle_network_server, style="Info.TButton")
        self.network_server_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(row1, text="🔄 Migruj Dane do Bazy", 
                  command=lambda: self.run_script_in_thread(SCRIPTS["migration"], "Skrypt Migracyjny"),
                  style="Info.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Drugi rząd przycisków
        row2 = ttk.Frame(operations_frame)
        row2.pack(fill=tk.X)
        
        buttons = [
            ("💾 Menedżer Kopii", self.open_backup_manager, "Primary"),
            ("📍 Kalibracja Mapy", self.open_map_calibrator, "Primary"),
            ("⚙️ Konfiguracja DB", self.open_env_editor, "Secondary"),
            ("🔐 Ustawienia Administratora", self.open_admin_settings, "Warning"),
            ("🖼️ Ustawienia Witryny", self.open_site_settings, "Primary"),
            ("🛡️ Bezpieczeństwo", self.open_security_manager, "Primary")
        ]
        
        for text, cmd, style in buttons:
            ttk.Button(row2, text=text, command=cmd, style=f"{style}.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Sekcja narzędzi deweloperskich
        tools_frame = ttk.LabelFrame(main_frame, text="🛠️ Narzędzia Deweloperskie", padding="10")
        tools_frame.pack(fill=tk.X, pady=5)
        
        editors_container = ttk.Frame(tools_frame)
        editors_container.pack(fill=tk.X)
        
        editor_buttons = [
            ("👥 Edytor Właścicieli", "owner_editor"),
            ("🗺️ Edytor Działek", "parcel_editor"),
            ("🌳 Edytor Genealogii", "genealogy_editor"),
        ]
        
        for text, key in editor_buttons:
            ttk.Button(editors_container, text=text,
                      command=lambda k=key, n=text: self.start_managed_process(k, n),
                      style="Primary.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(editors_container, text="🧪 Uruchom Testy Jednostkowe",
                  command=self.run_pytest, style="Info.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Sekcja szybkiego dostępu
        links_frame = ttk.LabelFrame(main_frame, text="🌐 Szybki Dostęp (wymaga uruchomionego serwera)", padding="10")
        links_frame.pack(fill=tk.X, pady=5)
        
        links_container = ttk.Frame(links_frame)
        links_container.pack(fill=tk.X)
        
        self.quick_link_buttons = []
        link_defs = [
            ("🏠 Strona Główna", "/strona_glowna/index.html", "Success"),
            ("🗺️ Mapa Interaktywna", "/mapa/mapa.html", "Info"),
            ("⚙️ Panel Administracyjny", "/admin", "Warning"),
        ]
        
        for text, path, style in link_defs:
            btn = ttk.Button(links_container, text=text, style=f"{style}.TButton")
            btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            self.quick_link_buttons.append((btn, path))

        self._env_mtime = None
        # Odłóż refresh_quick_links() - zostanie wykonane asynchronicznie w __init__
        # Odłóż start_env_watcher() - zostanie wykonane asynchronicznie w __init__
        
        # Sekcja procesów
        self.processes_frame = ttk.LabelFrame(main_frame, text="📊 Uruchomione Procesy", padding="10")
        self.processes_frame.pack(fill=tk.X, pady=5)
        self.update_processes_ui()
        
        # Sekcja konsol
        console_container = ttk.LabelFrame(main_frame, text="💻 Konsole Wyjściowe", padding="10")
        console_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.notebook = ttk.Notebook(console_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.main_console_frame = ttk.Frame(self.notebook)
        self.main_console = self.create_console_widget(self.main_console_frame)
        self.notebook.add(self.main_console_frame, text="🏠 Launcher")
        
        # Wiadomość powitalna
        self.log("=" * 60 + "\n")
        self.log("🗺️ System Zarządzania Mapą Katastralną - Uruchomiony\n")
        self.log("=" * 60 + "\n")
        self.log("ℹ️ Witaj w centrum zarządzania projektem!\n")
        self.log("ℹ️ Użyj przycisków powyżej, aby uruchomić komponenty.\n\n")

    def log(self, message, console=None):
        """Wypisuje wiadomość do konsoli (zoptymalizowane z batchingiem)."""
        target_console = console or self.main_console

        # Dodaj do bufora zamiast natychmiastowego zapisu
        console_id = id(target_console)
        if console_id not in self._log_buffer:
            self._log_buffer[console_id] = {'console': target_console, 'messages': []}

        self._log_buffer[console_id]['messages'].append(message)

        # Zaplanuj flush jeśli jeszcze nie zaplanowano
        if not self._log_flush_pending:
            self._log_flush_pending = True
            self.after(50, self._flush_logs)  # Flush co 50ms (batching)

    def _flush_logs(self):
        """Flush wszystkich zabuforowanych logów na raz."""
        try:
            for console_id, data in self._log_buffer.items():
                console = data['console']
                messages = data['messages']

                if messages:
                    # Jeden update zamiast wielu
                    console.configure(state="normal")
                    console.insert(tk.END, ''.join(messages))
                    console.see(tk.END)
                    console.configure(state="disabled")

                    data['messages'].clear()
        finally:
            self._log_flush_pending = False

    def update_processes_ui(self):
        """Odświeża listę uruchomionych procesów (zoptymalizowane - bez przebudowy UI)."""
        # Sprawdź czy lista procesów się zmieniła
        current_keys = set(self.managed_processes.keys())
        displayed_keys = set(self._displayed_processes.keys())

        # Jeśli identyczne i UI już wyświetla poprawny stan - pomiń aktualizację
        # (przy pierwszym uruchomieniu winfo_children() == 0, więc kontynuuj aby wyświetlić "brak procesów")
        if current_keys == displayed_keys and len(self.processes_frame.winfo_children()) > 0:
            return

        # Jeśli przechodzimy z 0 na >0 procesów, usuń napis "brak procesów"
        if not displayed_keys and current_keys:
            for widget in self.processes_frame.winfo_children():
                widget.destroy()
            self._displayed_processes.clear()

        # Usuń procesy, które już nie istnieją
        for key in displayed_keys - current_keys:
            if key in self._displayed_processes:
                self._displayed_processes[key].destroy()
                del self._displayed_processes[key]

        # Dodaj nowe procesy
        for key in current_keys - displayed_keys:
            info = self.managed_processes[key]
            proc_frame = ttk.Frame(self.processes_frame)
            proc_frame.pack(fill=tk.X, pady=3, padx=5)

            ttk.Label(proc_frame, text=f"🟢 {info['name']} (PID: {info['process'].pid})",
                     font=("Segoe UI", 10)).pack(side=tk.LEFT)

            ttk.Button(proc_frame, text="⏹️ Zatrzymaj", style="Danger.TButton",
                      command=lambda k=key: self.stop_managed_process(k),
                      width=12).pack(side=tk.RIGHT, padx=5)

            self._displayed_processes[key] = proc_frame

        # Wyświetl "brak procesów" jeśli puste
        if not self.managed_processes:
            for widget in self.processes_frame.winfo_children():
                widget.destroy()
            self._displayed_processes.clear()
            ttk.Label(self.processes_frame, text="📭 Brak uruchomionych procesów",
                     foreground=COLORS['secondary']).pack(pady=10)

    def load_flask_config(self):
        """Czyta aktualny host/port z backend/.env."""
        cfg = get_flask_config()
        try:
            cfg['port'] = str(int(cfg.get('port', '5000')))
        except:
            cfg['port'] = '5000'
        cfg['host'] = cfg.get('host', '127.0.0.1')
        return cfg

    def refresh_quick_links(self):
        """Aktualizuje komendy przycisków Szybkiego Dostępu."""
        self.current_flask_config = self.load_flask_config()
        base_url = f"http://{self.current_flask_config['host']}:{self.current_flask_config['port']}"
        for btn, path in getattr(self, "quick_link_buttons", []):
            url = base_url + path
            btn.configure(command=lambda u=url: webbrowser.open_new_tab(u))

    def get_env_mtime(self):
        """Zwraca czas modyfikacji pliku .env aktywnej miejscowości."""
        try:
            env_path = get_location_env_path()
            return os.path.getmtime(env_path)
        except (OSError, ValueError):
            return None

    def start_env_watcher(self):
        """Cyklicznie sprawdza zmiany w pliku .env (zoptymalizowane - mniej częste sprawdzanie)."""
        def _tick():
            try:
                mtime = self.get_env_mtime()
                if self._env_mtime is None:
                    self._env_mtime = mtime
                elif mtime is not None and mtime != self._env_mtime:
                    self._env_mtime = mtime
                    self.on_env_changed()
            finally:
                self.after(5000, _tick)  # 5s zamiast 2s - zmniejsza obciążenie CPU
        _tick()

    def on_env_changed(self):
        """Reakcja na zmianę .env."""
        old_port = getattr(self, "_last_port", None)
        was_running = "backend" in self.managed_processes
        was_network = self.managed_processes.get("backend", {}).get("network_mode", False)
        
        self.refresh_quick_links()
        new_port = self.current_flask_config.get("port")
        self._last_port = new_port
        
        self.log(f"🔎 Wykryto zmianę .env – port {old_port} ➜ {new_port}\n")
        
        if not was_running or not old_port or not new_port or old_port == new_port:
            return
        
        if messagebox.askyesno("Wykryto zmianę portu",
                               f"Zmieniono port z {old_port} na {new_port}.\n\n"
                               "Zrestartować serwer backend?"):
            self.stop_managed_process("backend")
            
            try:
                self.setup_firewall_rule_for_port(int(new_port))
            except:
                pass
            
            def _restart():
                if was_network:
                    self.start_network_server()
                else:
                    self.start_managed_process("backend", "Serwer Backend (Lokalny)")
                    self.server_btn.config(text="⏹️ Zatrzymaj Serwer (Lokalny)", style="Danger.TButton")
            
            self.after(600, _restart)

    def setup_firewall_rule_for_port(self, port: int):
        """Konfiguruje regułę zapory Windows dla portu."""
        if platform.system() != "Windows":
            return
        
        rule_name = f"Flask Server Port {port}"
        check_cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return
        
        add_cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport={port} enable=yes profile=any'
        subprocess.run(add_cmd, shell=True)

    def refresh_html_pages(self):
        """Automatycznie odświeża dane miejscowości poprzez wygenerowanie pliku JS."""
        try:
            active_location = get_active_location()
            if active_location:
                # Wygeneruj plik JS z danymi miejscowości
                generate_location_config_js()

                # Pobierz aktualny szablon i zastosuj go (dla strony głównej)
                template = active_location[6] if len(active_location) > 6 else "standardowy"
                apply_homepage_template(template)

                print(f"✓ Automatycznie zaktualizowano dane miejscowości: {active_location[1]}")
        except Exception as e:
            print(f"⚠️ Nie udało się automatycznie zaktualizować danych miejscowości: {e}")

    def refresh_locations(self, force=False):
        """Odświeża listę miejscowości w menu rozwijanym (ultra zoptymalizowane)."""
        # Debounce - zapobiegaj wielokrotnemu odświeżaniu
        if self._refresh_pending and not force:
            return

        # Jeśli mamy cache i nie wymuszamy - użyj cache bez SQL
        if self._cached_locations and not force:
            try:
                self._refresh_pending = True
                locations = self._cached_locations
                location_names = [loc[1] for loc in locations]

                # Sprawdź czy dane się zmieniły
                current_values = self.location_combo['values']
                if tuple(current_values) == tuple(location_names):
                    # Dane identyczne - pomiń odświeżanie
                    return

                self.location_combo['values'] = location_names

                # Znajdź aktywną
                active_location = next((loc for loc in locations if loc[5]), None)
                if active_location:
                    self.location_var.set(active_location[1])
                elif location_names:
                    self.location_var.set(location_names[0])
                else:
                    self.location_var.set("(brak miejscowości)")
            finally:
                self._refresh_pending = False
            return

        # Pełne odświeżenie z bazy (tylko jeśli force=True lub brak cache)
        try:
            self._refresh_pending = True
            locations = get_all_locations()
            self._cached_locations = locations
            location_names = [loc[1] for loc in locations]
            self.location_combo['values'] = location_names

            # Znajdź aktywną lokację
            active_location = next((loc for loc in locations if loc[5]), None)
            if active_location:
                self.location_var.set(active_location[1])
            elif location_names:
                self.location_var.set(location_names[0])
                # Ustaw jako aktywną w tle
                threading.Thread(target=lambda: set_active_location(locations[0][0]), daemon=True).start()
            else:
                self.location_var.set("(brak miejscowości)")
        finally:
            self._refresh_pending = False

    def on_location_selected(self, event=None):
        """Obsługuje zmianę wybranej miejscowości (zoptymalizowana)."""
        selected_name = self.location_var.get()
        if not selected_name or selected_name == "(brak miejscowości)":
            return

        # Użyj cache zamiast ponownego pobierania
        locations = self._cached_locations if self._cached_locations else get_all_locations()

        for loc in locations:
            if loc[1] == selected_name:  # loc[1] to name
                # Zmień aktywną lokację w tle (nie blokuj UI)
                def _change_location():
                    try:
                        set_active_location(loc[0])  # loc[0] to id
                        # Odśwież DATA_FILES
                        global DATA_FILES
                        DATA_FILES = get_data_files()
                        # Dodaj do kolejki - będzie obsłużone w głównym wątku
                        self.event_queue.put(('location_changed', selected_name, None))
                    except Exception as e:
                        print(f"❌ Błąd zmiany lokacji: {e}")
                        self.event_queue.put(('location_error', None, str(e)))

                # Uruchom w tle natychmiast (bez update_idletasks - spowalnia)
                threading.Thread(target=_change_location, daemon=True).start()
                break

    def open_location_manager(self):
        """Otwiera okno zarządzania miejscowościami."""
        manager = LocationManager(self)
        self.wait_window(manager)
        # Opóźnione odświeżenie - nie blokuj GUI natychmiast
        self.after(50, lambda: self.refresh_locations(force=True))

    def open_database_wizard(self):
        """Otwiera narzędzie zarządzania bazą danych PostgreSQL."""
        wizard = DatabaseWizard(self)
        self.wait_window(wizard)
        # Opóźnione odświeżenie - nie blokuj GUI natychmiast
        self.after(50, lambda: self.refresh_locations(force=True))

    def open_backup_manager(self):
        """Otwiera okno menedżera kopii zapasowych."""
        if any(key.endswith("_editor") for key in self.managed_processes):
            messagebox.showwarning("⚠️ Uwaga",
                                 "Zamknij wszystkie aktywne edytory przed zarządzaniem kopiami zapasowymi,\n"
                                 "aby uniknąć konfliktów plików.")
            return
        
        manager = BackupManager(self)
        self.wait_window(manager)

    def open_map_calibrator(self):
        """Otwiera okno kalibracji mapy."""
        if "backend" in self.managed_processes:
            messagebox.showwarning("Serwer aktywny",
                                 "Zatrzymaj serwer backend przed zmianą kalibracji.\n"
                                 "Zmiany zostaną zastosowane po ponownym uruchomieniu serwera.",
                                 parent=self)
        
        MapCalibrator(self)

    def open_env_editor(self):
        """Otwiera edytor konfiguracji .env aktywnej miejscowości."""
        try:
            env_path = get_location_env_path()
        except ValueError:
            messagebox.showerror("❌ Błąd", "Brak aktywnej miejscowości")
            return

        if not os.path.exists(env_path):
            if not check_env_configuration():
                messagebox.showerror("❌ Błąd", "Nie można utworzyć pliku .env")
                return
        
        EnvEditor(self, env_path)

    def open_admin_settings(self):
        """Otwiera okno ustawień administratora."""
        AdminSettings(self)

    def open_site_settings(self):
        """Otwiera okno ustawień witryny."""
        if "backend" in self.managed_processes:
            messagebox.showwarning("Serwer aktywny",
                                 "Zatrzymaj serwer backend przed zmianą ustawień witryny.\n"
                                 "Zmiany zostaną zastosowane po ponownym uruchomieniu serwera.",
                                 parent=self)
        
        SiteSettingsManager(self)

    def open_security_manager(self):
        """Otwiera okno menedżera bezpieczeństwa."""
        if "backend" not in self.managed_processes:
            messagebox.showwarning("Serwer nieaktywny",
                                 "Uruchom serwer backend, aby zarządzać bezpieczeństwem.",
                                 parent=self)
            return
        
        SecurityManager(self)

    def start_managed_process(self, key, name):
        """Uruchamia zewnętrzny skrypt jako zarządzany proces."""
        if key in self.managed_processes:
            messagebox.showwarning("⚠️ Proces już działa", f"Proces '{name}' jest już uruchomiony.")
            return
        
        self.log(f"🚀 Uruchamianie: {name}...\n")
        script_info = SCRIPTS[key]
        
        # Tworzenie konsoli
        tab_frame = ttk.Frame(self.notebook)
        console = self.create_console_widget(tab_frame)
        self.notebook.add(tab_frame, text=f"📋 {name}")
        self.notebook.select(tab_frame)
        
        # Przygotowanie środowiska i komendy
        env = self._prepare_process_env()
        command = self._prepare_command(key, script_info)
        
        # Uruchomienie procesu
        creation_flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if platform.system() == "nt" else 0
        
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=script_info["cwd"], encoding="utf-8",
            errors="replace", creationflags=creation_flags, env=env
        )
        
        self.managed_processes[key] = {
            "process": process, "console": console,
            "tab_frame": tab_frame, "name": name
        }
        
        threading.Thread(target=self.read_process_output, args=(key,), daemon=True).start()
        
        if key in URLS:
            threading.Timer(1.5, lambda: webbrowser.open(URLS[key])).start()
        
        self.update_processes_ui()

    def stop_managed_process(self, key):
        """Zatrzymuje zarządzany proces."""
        if key not in self.managed_processes:
            return
        
        info = self.managed_processes[key]
        process = info["process"]
        name = info["name"]
        
        msg = f"\n⏹️ Zatrzymywanie procesu: {name}...\n"
        self.log(msg, console=info["console"])
        self.log(msg)
        
        try:
            if platform.system() == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            process.wait(timeout=2)
        except (subprocess.TimeoutExpired, ProcessLookupError, PermissionError):
            msg = f"⚠️ Proces '{name}' nie odpowiedział – wymuszam zatrzymanie.\n"
            self.log(msg, console=info["console"])
            self.log(msg)
            process.kill()
            process.wait()
        
        del self.managed_processes[key]
        self.notebook.forget(info["tab_frame"])
        self.update_processes_ui()
        
        if key == "backend":
            self.server_btn.config(text="🚀 Uruchom Serwer Backend", style="Success.TButton")

    def read_process_output(self, key):
        """Czyta wyjście z procesu."""
        if key not in self.managed_processes:
            return

        info = self.managed_processes.get(key)
        if not info:
            return

        process = info["process"]
        console = info["console"]

        for line in iter(process.stdout.readline, ""):
            self.after(0, self.log, line, console)

        # Poczekaj aż proces rzeczywiście się zakończy
        # (stdout może się zamknąć wcześniej niż proces)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Proces wciąż działa mimo zamkniętego stdout
            # Sprawdzaj co sekundę czy proces się zakończył
            import time
            for _ in range(60):  # Maksymalnie 60 sekund
                if process.poll() is not None:
                    break
                time.sleep(1)

        # Tylko jeśli proces rzeczywiście się zakończył, wyślij event
        if process.poll() is not None:
            self.event_queue.put((key, "finished"))

    def run_script_in_thread(self, script_info, script_name):
        """Uruchamia jednorazowy skrypt w wątku."""
        def target():
            self.log(f"⚡ Uruchamianie: {script_name}...\n")
            
            env = self._prepare_process_env()
            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "nt" else 0
            
            process = subprocess.Popen(
                [sys.executable, "-X", "utf8", "-u", script_info["path"]],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                cwd=script_info["cwd"], encoding="utf-8", errors="replace",
                creationflags=creation_flags, env=env
            )
            
            for line in iter(process.stdout.readline, ""):
                self.log(line)
            process.stdout.close()
            
            return_code = process.wait()
            status = "✅ Zakończono pomyślnie" if return_code == 0 else f"❌ Zakończono z błędem (kod: {return_code})"
            self.log(f"{status}: {script_name}\n")
        
        threading.Thread(target=target, daemon=True).start()

    def run_pytest(self):
        """Uruchamia testy jednostkowe."""
        def target():
            self.log("🧪 Start testów jednostkowych (pytest)...\n")
            try:
                env = self._prepare_process_env()
                cmd = [sys.executable, "-m", "pytest", "tests", "-q"]
                creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "nt" else 0
                
                proc = subprocess.Popen(cmd, cwd=BACKEND_DIR, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                      errors="replace", creationflags=creation_flags, env=env)
                
                for line in iter(proc.stdout.readline, ""):
                    self.log(line)
                proc.stdout.close()
                
                rc = proc.wait()
                status = "✅ Testy zakończone pomyślnie." if rc == 0 else f"❌ Testy zakończone błędem (kod: {rc})."
                self.log(f"{status}\n")
            except FileNotFoundError:
                self.log("❌ Nie znaleziono pytest. Zainstaluj: pip install pytest\n")
            except Exception as e:
                self.log(f"❌ Błąd uruchamiania testów: {e}\n")
        
        threading.Thread(target=target, daemon=True).start()

    def toggle_server(self, network_mode=False):
        """Przełącza stan serwera backend."""
        if "backend" in self.managed_processes:
            self.stop_managed_process("backend")
        else:
            if network_mode:
                self.start_network_server()
            else:
                self.start_managed_process("backend", "Serwer Backend (Lokalny)")
                self.server_btn.config(text="⏹️ Zatrzymaj Serwer (Lokalny)", style="Danger.TButton")

    def toggle_network_server(self):
        """Przełącza serwer sieciowy."""
        if "backend" in self.managed_processes:
            if self.managed_processes["backend"].get("network_mode"):
                self.stop_managed_process("backend")
                self.network_server_btn.config(text="🌐 Uruchom Serwer Sieciowy", style="Info.TButton")
            else:
                messagebox.showwarning("⚠️ Uwaga",
                                     "Lokalny serwer jest już uruchomiony.\n"
                                     "Zatrzymaj go najpierw, aby uruchomić serwer sieciowy.")
        else:
            self.toggle_server(network_mode=True)

    def start_network_server(self):
        """Uruchamia serwer Flask dostępny w sieci lokalnej."""
        if platform.system() == "Windows":
            self.setup_firewall_rule()
        
        local_ip = get_local_ip()
        flask_config = get_flask_config()
        port = int(flask_config['port'])
        
        self.log(f"🌐 Uruchamianie serwera w trybie SIECIOWYM...\n")
        self.log(f"📡 Serwer będzie dostępny pod adresami:\n")
        self.log(f"   • Lokalnie: http://127.0.0.1:{port}\n")
        self.log(f"   • W sieci LAN: http://{local_ip}:{port}\n")
        self.log(f"   • Alternatywnie: http://{socket.gethostname()}:{port}\n")
        self.log(f"⚠️ UWAGA: Upewnij się, że firewall nie blokuje portu {port}!\n\n")
        
        # Tworzenie konsoli
        tab_frame = ttk.Frame(self.notebook)
        console = self.create_console_widget(tab_frame)
        self.notebook.add(tab_frame, text=f"🌐 Serwer Sieciowy")
        self.notebook.select(tab_frame)
        
        # Tworzenie skryptu wrapper
        wrapper_code = f'''import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from app import app

if __name__ == '__main__':
    print('🚀 Uruchamianie serwera Flask w trybie sieciowym...')
    print('📡 Serwer nasłuchuje na wszystkich interfejsach (0.0.0.0)')
    print('=' * 60)
    app.run(host="0.0.0.0", port={port}, debug=True, use_reloader=False)
'''
        
        wrapper_path = os.path.join(BACKEND_DIR, "_network_server_wrapper.py")
        with open(wrapper_path, 'w', encoding='utf-8') as f:
            f.write(wrapper_code)
        
        # Uruchomienie procesu
        env = self._prepare_process_env()
        creation_flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if platform.system() == "nt" else 0
        
        process = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-u", wrapper_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            cwd=BACKEND_DIR, encoding="utf-8", errors="replace",
            creationflags=creation_flags, env=env
        )
        
        self.managed_processes["backend"] = {
            "process": process, "console": console, "tab_frame": tab_frame,
            "name": "Serwer Backend (Sieciowy)", "network_mode": True, "local_ip": local_ip
        }
        
        threading.Thread(target=self.read_process_output, args=("backend",), daemon=True).start()
        
        self.network_server_btn.config(text="⏹️ Zatrzymaj Serwer Sieciowy", style="Danger.TButton")
        
        self.show_network_info_dialog(local_ip)
        self.update_processes_ui()

    def setup_firewall_rule(self):
        """Konfiguruje regułę firewall Windows."""
        if platform.system() != "Windows":
            return True
        
        flask_config = get_flask_config()
        port = int(flask_config['port'])
        rule_name = f"Flask Server Port {port}"
        
        check_cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            self.log("✅ Reguła firewall już istnieje.\n")
            return True
        
        self.log("🔧 Konfigurowanie reguły firewall...\n")
        
        add_cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport={port} enable=yes profile=any'
        
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            
            if not is_admin:
                response = messagebox.askyesno(
                    "🔐 Wymagane uprawnienia administratora",
                    "Aby automatycznie skonfigurować firewall, aplikacja musi być uruchomiona jako Administrator.\n\n"
                    "• TAK - Uruchomić ponownie jako Administrator?\n"
                    "• NIE - Skonfigurować firewall ręcznie później?",
                    icon="warning"
                )
                
                if response:
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                    self.destroy()
                    sys.exit(0)
                else:
                    self.log("⚠️ Firewall nie został skonfigurowany. Skonfiguruj go ręcznie.\n")
                    self.show_firewall_instructions()
                    return False
            
            result = subprocess.run(add_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log("✅ Reguła firewall została dodana pomyślnie!\n")
                messagebox.showinfo("✅ Sukces", f"Reguła firewall została skonfigurowana.\nPort {port} jest teraz otwarty.")
                return True
            else:
                self.log(f"❌ Błąd dodawania reguły: {result.stderr}\n")
                return False
        except Exception as e:
            self.log(f"❌ Błąd konfiguracji firewall: {e}\n")
            return False

    def show_firewall_instructions(self):
        """Wyświetla instrukcje ręcznej konfiguracji firewall."""
        FirewallInstructions(self)

    def show_network_info_dialog(self, local_ip):
        """Wyświetla okno dialogowe z informacjami o dostępie sieciowym."""
        NetworkInfoDialog(self, local_ip)

    def on_closing(self):
        """Obsługuje zdarzenie zamknięcia głównego okna."""
        if self.managed_processes:
            network_server = any(p.get("network_mode") for p in self.managed_processes.values())
            
            warning_msg = f"Uruchomionych jest {len(self.managed_processes)} procesów."
            if network_server:
                warning_msg += "\n\n⚠️ UWAGA: Serwer sieciowy jest aktywny!"
            warning_msg += "\n\nCzy chcesz je wszystkie zatrzymać i zamknąć aplikację?"
            
            result = messagebox.askyesno(
                "🔒 Potwierdzenie zamknięcia", warning_msg,
                icon="warning" if network_server else "question"
            )
            
            if result:
                self.log("\n" + "=" * 60 + "\n")
                self.log("🔒 Zamykanie aplikacji - zatrzymywanie procesów...\n")
                
                for key in list(self.managed_processes.keys()):
                    self.stop_managed_process(key)
                
                self.cleanup_temp_files()
                self.destroy()
        else:
            self.cleanup_temp_files()
            self.destroy()

    def cleanup_temp_files(self):
        """Usuwa tymczasowe pliki utworzone przez launcher."""
        wrapper_path = os.path.join(BACKEND_DIR, "_network_server_wrapper.py")
        if os.path.exists(wrapper_path):
            try:
                os.remove(wrapper_path)
            except:
                pass

    def _prepare_process_env(self):
        """Przygotowuje środowisko dla procesu."""
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        
        env_config = read_env_config()
        env.update(env_config)
        
        return env

    def _prepare_command(self, key, script_info):
        """Przygotowuje komendę do uruchomienia."""
        if key == "tests":
            return [sys.executable, script_info["path"]] + script_info["args"]
        else:
            command = [sys.executable, "-X", "utf8", "-u", script_info["path"]]
            if key == "genealogy_editor":
                command.append("--launched-by-gui")
            return command

# =============================================================================
# KLASY OKIEN DIALOGOWYCH
# =============================================================================

class LocationManager(tk.Toplevel):
    """Okno dialogowe do zarządzania miejscowościami."""

    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("⚙️ Zarządzaj Miejscowościami")

        # Automatyczne dostosowanie do ekranu
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(int(sw * 0.6), 900), min(int(sh * 0.7), 600)
        x = (sw - w) // 2
        y = (sh - h) // 2

        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(700, 500)
        self.grab_set()

        self.create_widgets()
        self.refresh_table()

    def create_widgets(self):
        """Tworzy interfejs menedżera miejscowości."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Tabelka
        table_frame = ttk.LabelFrame(main_frame, text="📋 Lista Miejscowości", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Kolumny: ID, Nazwa, Pełna Nazwa, Powiat, Region, Szablon, Aktywna
        columns = ("id", "name", "full_name", "powiat", "region", "template", "active")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Nazwa")
        self.tree.heading("full_name", text="Pełna Nazwa")
        self.tree.heading("powiat", text="Powiat")
        self.tree.heading("region", text="Region")
        self.tree.heading("template", text="Szablon Strony")
        self.tree.heading("active", text="Aktywna")

        self.tree.column("id", width=40, anchor="center")
        self.tree.column("name", width=100)
        self.tree.column("full_name", width=150)
        self.tree.column("powiat", width=110)
        self.tree.column("region", width=100)
        self.tree.column("template", width=130)
        self.tree.column("active", width=70, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Przyciski akcji
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)

        ttk.Button(buttons_frame, text="➕ Dodaj Nową Miejscowość", command=self.add_location,
                  style="Success.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(buttons_frame, text="✏️ Edytuj", command=self.edit_location,
                  style="Primary.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(buttons_frame, text="🗑️ Usuń", command=self.delete_location,
                  style="Danger.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(buttons_frame, text="✅ Ustaw jako Aktywną", command=self.set_active,
                  style="Info.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(buttons_frame, text="🎨 Zmień Szablon", command=self.change_template,
                  style="Info.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(buttons_frame, text="🔄 Odśwież", command=self.refresh_table,
                  style="Secondary.TButton").pack(side=tk.LEFT, padx=5)

    def refresh_table(self):
        """Odświeża tabelkę z miejscowościami."""
        # Wyczyść tabelę
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Pobierz dane
        locations = get_all_locations()

        # Mapowanie nazw szablonów na bardziej czytelne
        template_names = {
            "standardowy": "📍 Standardowy",
            "praca_inzynierska": "🎓 Praca Inżynierska"
        }

        # Wypełnij tabelę
        for loc in locations:
            # Rozpakuj wszystkie pola (ignorujemy tekst content)
            loc_id, name, full_name, powiat, region, active, template, year, century = loc[:9]
            active_str = "✓" if active else ""
            template_display = template_names.get(template, template)
            self.tree.insert("", "end", values=(loc_id, name, full_name, powiat, region, template_display, active_str))

    def add_location(self):
        """Dodaje nową miejscowość."""
        dialog = AddEditLocationDialog(self, "Dodaj Nową Miejscowość")
        self.wait_window(dialog)

        if hasattr(dialog, 'result') and dialog.result:
            (name, full_name, powiat, region, year, century,
             homepage_desc, history_p1, history_p2, history_p3,
             history_photos, postgres_db_name, homepage_template,
             gmina_katastralna, miejscowosc_protokolu) = dialog.result
            try:
                add_location(name, full_name, powiat, region, year=year, century=century,
                           homepage_description=homepage_desc, history_paragraph1=history_p1,
                           history_paragraph2=history_p2, history_paragraph3=history_p3,
                           history_photos=history_photos, postgres_db_name=postgres_db_name,
                           homepage_template=homepage_template,
                           gmina_katastralna=gmina_katastralna, miejscowosc_protokolu=miejscowosc_protokolu)
                messagebox.showinfo("✅ Sukces", f"Dodano miejscowość: {name}", parent=self)
                self.refresh_table()
            except ValueError as e:
                messagebox.showerror("❌ Błąd", str(e), parent=self)

    def edit_location(self):
        """Edytuje wybraną miejscowość."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Wybierz miejscowość do edycji", parent=self)
            return

        # Pobierz wszystkie dane miejscowości z bazy danych
        values = self.tree.item(selected[0], "values")
        loc_id = values[0]

        # Pobierz pełne dane z bazy danych PostgreSQL
        name = full_name = powiat = region = year = century = ""
        homepage_desc = history_p1 = history_p2 = history_p3 = ""
        history_photos_json = "[]"
        postgres_db_name = ""
        homepage_template = "standardowy"
        gmina_katastralna = "Czarna"
        miejscowosc_protokolu = "Pilzno"

        if not check_postgres_available():
            messagebox.showerror("❌ Błąd", "PostgreSQL nie jest dostępny!", parent=self)
            return

        try:
            conn = get_launcher_postgres_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT name, full_name, powiat, region, year, century,
                       homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
                       postgres_db_name, homepage_template, gmina_katastralna, miejscowosc_protokolu
                FROM locations WHERE id = %s
            """, (loc_id,))
            result = cursor.fetchone()

            if result:
                (name, full_name, powiat, region, year, century,
                 homepage_desc, history_p1, history_p2, history_p3, postgres_db_name, homepage_template,
                 gmina_katastralna, miejscowosc_protokolu) = result
                postgres_db_name = postgres_db_name or ""
                homepage_template = homepage_template or "standardowy"
                gmina_katastralna = gmina_katastralna or "Czarna"
                miejscowosc_protokolu = miejscowosc_protokolu or "Pilzno"

                # Pobierz zdjęcia historyczne
                cursor.execute("""
                    SELECT filename, caption
                    FROM history_photos
                    WHERE location_id = %s
                    ORDER BY order_index
                """, (loc_id,))
                photos_rows = cursor.fetchall()
                history_photos_json = json.dumps([
                    {"filename": row[0], "caption": row[1]}
                    for row in photos_rows
                ], ensure_ascii=False)
            else:
                messagebox.showerror("❌ Błąd", "Nie znaleziono miejscowości", parent=self)
                cursor.close()
                conn.close()
                return

            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ PostgreSQL błąd: {e}")
            messagebox.showerror("❌ Błąd", f"Błąd podczas pobierania danych: {e}", parent=self)
            return

        # Ustaw domyślne wartości jeśli None
        year = year or "1882"
        century = century or "XIX w."
        homepage_desc = homepage_desc or "Odkryj historię zapisaną w ziemi."
        history_p1 = history_p1 or ""
        history_p2 = history_p2 or ""
        history_p3 = history_p3 or ""

        # Sparsuj history_photos z JSON
        try:
            history_photos = json.loads(history_photos_json) if history_photos_json else []
        except (json.JSONDecodeError, TypeError):
            history_photos = []

        dialog = AddEditLocationDialog(self, "Edytuj Miejscowość", name, full_name, powiat, region, year, century,
                                      homepage_desc, history_p1, history_p2, history_p3,
                                      history_photos, postgres_db_name, homepage_template,
                                      gmina_katastralna, miejscowosc_protokolu)
        self.wait_window(dialog)

        if hasattr(dialog, 'result') and dialog.result:
            (new_name, new_full_name, new_powiat, new_region, new_year, new_century,
             new_homepage_desc, new_history_p1, new_history_p2, new_history_p3,
             new_history_photos, new_postgres_db_name, new_homepage_template,
             new_gmina_katastralna, new_miejscowosc_protokolu) = dialog.result
            try:
                update_location(int(loc_id), new_name, new_full_name, new_powiat, new_region, new_year, new_century,
                              new_homepage_desc, new_history_p1, new_history_p2, new_history_p3,
                              new_history_photos, new_postgres_db_name, new_homepage_template,
                              new_gmina_katastralna, new_miejscowosc_protokolu)

                # Jeśli edytowana miejscowość jest aktywna, wygeneruj nowy plik JS
                active_location = get_active_location()
                if active_location and active_location[0] == int(loc_id):
                    generate_location_config_js()
                    # Zaktualizuj również stronę główną
                    template = active_location[6] if len(active_location) > 6 else "standardowy"
                    apply_homepage_template(template)

                messagebox.showinfo("✅ Sukces", f"Zaktualizowano miejscowość: {new_name}", parent=self)
                self.refresh_table()
            except ValueError as e:
                messagebox.showerror("❌ Błąd", str(e), parent=self)

    def delete_location(self):
        """Usuwa wybraną miejscowość."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Wybierz miejscowość do usunięcia", parent=self)
            return

        values = self.tree.item(selected[0], "values")
        loc_id, name = values[0], values[1]

        if not messagebox.askyesno("⚠️ Potwierdzenie",
                                   f"Czy na pewno chcesz usunąć miejscowość '{name}'?\n\n"
                                   "Zostanie usunięte:\n"
                                   "• Baza danych PostgreSQL\n"
                                   "• Cały folder z danymi\n"
                                   "• Konfiguracja miejscowości",
                                   parent=self):
            return

        try:
            delete_location(int(loc_id))
            messagebox.showinfo("✅ Sukces", f"Usunięto miejscowość: {name}", parent=self)
            self.refresh_table()
        except ValueError as e:
            messagebox.showerror("❌ Błąd", str(e), parent=self)

    def change_template(self):
        """Zmienia szablon strony dla wybranej miejscowości."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Wybierz miejscowość aby zmienić szablon", parent=self)
            return

        values = self.tree.item(selected[0], "values")
        loc_id, name = values[0], values[1]

        # Otwórz okno wyboru szablonu
        dialog = TemplateChangeDialog(self, int(loc_id), name)
        self.wait_window(dialog)

        # Odśwież tabelę
        self.refresh_table()

    def set_active(self):
        """Ustawia wybraną miejscowość jako aktywną."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Wybierz miejscowość do aktywacji", parent=self)
            return

        values = self.tree.item(selected[0], "values")
        loc_id, name = values[0], values[1]

        set_active_location(int(loc_id))
        messagebox.showinfo("✅ Sukces", f"Ustawiono jako aktywną: {name}\nZastosowano szablon strony dla tej miejscowości.", parent=self)
        self.refresh_table()



class TemplateChangeDialog(tk.Toplevel):
    """Dialog do zmiany szablonu strony dla miejscowości."""

    def __init__(self, parent, location_id, location_name):
        super().__init__(parent)
        self.transient(parent)
        self.title(f"🎨 Zmień Szablon - {location_name}")
        self.grab_set()

        self.location_id = location_id
        self.location_name = location_name

        self.geometry("500x350")
        self.minsize(450, 300)
        self.center_window()

        self.create_widgets()

    def center_window(self):
        """Centruje okno na ekranie."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def create_widgets(self):
        """Tworzy interfejs wyboru szablonu."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Nagłówek
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(header_frame, text=f"Wybierz szablon dla: {self.location_name}",
                 font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)

        # Pobierz aktualny szablon z PostgreSQL
        try:
            conn = get_launcher_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT homepage_template FROM locations WHERE id = %s", (self.location_id,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            current_template = result[0] if result and result[0] else "standardowy"
        except Exception as e:
            print(f"❌ Błąd pobierania szablonu: {e}")
            current_template = "standardowy"

        # Lista szablonów
        templates_frame = ttk.LabelFrame(main_frame, text="Dostępne szablony", padding="10")
        templates_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.template_var = tk.StringVar(value=current_template)

        # Szablon 1: Standardowy
        template1_frame = ttk.Frame(templates_frame)
        template1_frame.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(template1_frame, text="📍 Standardowy",
                       variable=self.template_var, value="standardowy").pack(anchor=tk.W)

        ttk.Label(template1_frame, text="Uniwersalny szablon dostosowany do różnych miejscowości.\n"
                                        "Automatycznie podstawia nazwę, powiat i region.",
                 foreground="#666666", wraplength=450).pack(anchor=tk.W, padx=(25, 0), pady=(2, 0))

        # Separator
        ttk.Separator(templates_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Szablon 2: Praca inżynierska
        template2_frame = ttk.Frame(templates_frame)
        template2_frame.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(template2_frame, text="🎓 Praca Inżynierska",
                       variable=self.template_var, value="praca_inzynierska").pack(anchor=tk.W)

        ttk.Label(template2_frame, text="Oryginalna strona dla projektu studenckiego o gminie Czarna.\n"
                                        "Zawiera informacje o Akademii Tarnowskiej.",
                 foreground="#666666", wraplength=450).pack(anchor=tk.W, padx=(25, 0), pady=(2, 0))

        # Przyciski
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)

        ttk.Button(buttons_frame, text="Anuluj", command=self.destroy,
                  style="Secondary.TButton").pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(buttons_frame, text="✅ Zapisz i Zastosuj", command=self.save_template,
                  style="Success.TButton").pack(side=tk.RIGHT)

    def save_template(self):
        """Zapisuje wybrany szablon dla miejscowości."""
        template_name = self.template_var.get()

        # Zapisz szablon w bazie danych
        set_location_template(self.location_id, template_name)

        # Jeśli to aktywna miejscowość, od razu zastosuj szablon
        active_location = get_active_location()
        if active_location and active_location[0] == self.location_id:
            success = apply_homepage_template(template_name)
            if success:
                messagebox.showinfo("✅ Sukces",
                                   f"Szablon '{template_name}' został zapisany i zastosowany!\n\n"
                                   f"Odśwież stronę w przeglądarce aby zobaczyć zmiany.",
                                   parent=self)
            else:
                messagebox.showwarning("⚠️ Zapisano",
                                      f"Szablon '{template_name}' został zapisany, ale nie udało się go zastosować.\n"
                                      f"Sprawdź logi aby uzyskać więcej informacji.",
                                      parent=self)
        else:
            messagebox.showinfo("✅ Sukces",
                               f"Szablon '{template_name}' został zapisany.\n\n"
                               f"Zostanie zastosowany gdy aktywujesz tę miejscowość.",
                               parent=self)

        self.destroy()


class LoadingDialog(tk.Toplevel):
    """Okno z animacją ładowania podczas inicjalizacji."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Inicjalizacja systemu")
        self.geometry("450x250")
        self.resizable(False, False)

        # Wycentruj okno
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (450 // 2)
        y = (self.winfo_screenheight() // 2) - (250 // 2)
        self.geometry(f"450x250+{x}+{y}")

        # Ukryj przyciski okna
        self.overrideredirect(False)
        if parent:
            self.transient(parent)

        # ZAWSZE NA WIERZCHU
        self.attributes('-topmost', True)

        # Główny frame
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Tytuł
        ttk.Label(main_frame, text="⚙️ Przygotowywanie systemu...",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Progress bar (animowany)
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=350)
        self.progress.pack(pady=10)
        self.progress.start(10)

        # Status text
        self.status_label = ttk.Label(main_frame, text="Sprawdzanie konfiguracji...",
                                      font=('Arial', 10), wraplength=400)
        self.status_label.pack(pady=20)

        # Szczegóły (mniejszym fontem)
        self.detail_label = ttk.Label(main_frame, text="",
                                      font=('Arial', 9), foreground='gray')
        self.detail_label.pack(pady=5)

        # Wymuś bycie na wierzchu i modal
        self.lift()
        self.focus_force()
        self.grab_set()  # Blokuj dostęp do innych okien

    def update_status(self, status, detail=""):
        """Aktualizuje tekst statusu."""
        self.status_label.config(text=status)
        self.detail_label.config(text=detail)
        self.lift()  # Zawsze wychodź na wierzch
        self.update()  # Odśwież GUI

    def close(self):
        """Zamyka okno."""
        self.progress.stop()
        try:
            self.grab_release()  # Zwolnij modal
        except:
            pass
        self.destroy()


def auto_initialize_on_startup(loading_dialog):
    """
    Automatyczna inicjalizacja przy pierwszym uruchomieniu programu.

    Sprawdza czy:
    1. Istnieje plik .postgres.env z hasłem
    2. Istnieje baza mapa_launcher_db
    3. Istnieje miejscowość Czarna
    4. Istnieje baza mapa_czarna_db
    5. Dane są zmigrowane

    Jeśli czegoś brakuje - automatycznie tworzy.

    Args:
        loading_dialog: Okno LoadingDialog do aktualizacji postępu
    """
    # Sprawdź czy .postgres.env istnieje i ma hasło
    if not os.path.exists(POSTGRES_CONFIG_FILE):
        print("⚠️ Brak pliku .postgres.env")
        return  # Brak konfiguracji - user musi najpierw wpisać hasło

    config = get_postgres_config()
    if not config.get('password'):
        print("⚠️ Brak hasła w konfiguracji")
        return  # Brak hasła - nie można się połączyć

    # Szybkie sprawdzenie czy jest coś do zrobienia
    try:
        success, msg = test_postgres_connection(**config)
        if not success:
            print(f"⚠️ Nie można połączyć się z PostgreSQL: {msg}")
            return

        # Sprawdź co trzeba zrobić
        needs_work = False
        db_exists = postgres_database_exists(**config, db_name='mapa_launcher_db')
        if not db_exists:
            needs_work = True
        else:
            # Sprawdź czy Czarna istnieje
            try:
                conn = get_launcher_postgres_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM locations WHERE name = 'Czarna'")
                czarna_exists = cursor.fetchone()[0] > 0
                cursor.close()
                conn.close()
                if not czarna_exists:
                    needs_work = True
            except:
                needs_work = True

            # Sprawdź czy baza Czarnej istnieje
            czarna_db_exists = postgres_database_exists(**config, db_name='mapa_czarna_db')
            if not czarna_db_exists:
                needs_work = True

        # Jeśli nie ma nic do zrobienia - wyjdź
        if not needs_work:
            print("ℹ️ System już jest skonfigurowany")
            return

    except Exception as e:
        print(f"⚠️ Błąd sprawdzania: {e}")
        return

    # Jeśli jest coś do zrobienia - wykonaj z aktualizacją loading_dialog

    try:
        loading_dialog.update_status("Sprawdzanie baz danych...", "Łączenie z PostgreSQL")

        print("✅ PostgreSQL dostępny, sprawdzam bazy...")

        # Flagi do śledzenia co zostało zrobione
        created_launcher = False
        created_czarna_location = False
        created_czarna_db = False
        migrated_data = False

        # 1. Sprawdź/utwórz bazę mapa_launcher_db
        db_exists = postgres_database_exists(**config, db_name='mapa_launcher_db')

        if not db_exists:
            loading_dialog.update_status("Tworzenie bazy mapa_launcher_db...",
                                        "Konfiguracja PostgreSQL")
            print("📦 Tworzę bazę mapa_launcher_db...")
            success_db, msg_db = postgres_create_database(**config, db_name='mapa_launcher_db')
            if not success_db:
                print(f"❌ Błąd tworzenia bazy launcher: {msg_db}")
                loading_dialog.close()
                return
            created_launcher = True
            print("✅ Baza mapa_launcher_db utworzona")

        # Włącz PostGIS (zawsze, nawet jeśli baza istniała)
        loading_dialog.update_status("Konfiguracja PostGIS...", "Rozszerzenia przestrzenne")
        postgres_enable_postgis(**config, db_name='mapa_launcher_db')

        # Wykonaj schemat (zawsze, bezpieczne z IF NOT EXISTS)
        postgres_execute_schema(**config, db_name='mapa_launcher_db', schema_sql=LAUNCHER_DB_SCHEMA)

        # 2. Sprawdź czy istnieje miejscowość "Czarna"
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
            loading_dialog.update_status("Tworzenie miejscowości 'Czarna'...",
                                        "Domyślna lokalizacja")
            print("📍 Tworzę domyślną miejscowość 'Czarna'...")

            # Wczytaj konfigurację z pliku JSON
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
                postgres_db_name=default_loc.get('postgres_db_name', 'mapa_czarna_db')
            )
            print("✅ Wczytano konfigurację z launcher_db_config.json")

            created_czarna_location = True

            # Ustaw jako aktywną
            conn = get_launcher_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE locations SET active = TRUE WHERE name = 'Czarna'")
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ Miejscowość 'Czarna' utworzona i ustawiona jako aktywna")

        # 3. Sprawdź czy baza Czarnej istnieje
        czarna_db_exists = postgres_database_exists(**config, db_name='mapa_czarna_db')

        if not czarna_db_exists:
            loading_dialog.update_status("Tworzenie bazy mapa_czarna_db...",
                                        "Baza danych dla miejscowości")
            print("📦 Tworzę bazę mapa_czarna_db...")
            success_db, msg_db = init_location_database('mapa_czarna_db')
            if success_db:
                created_czarna_db = True
                print("✅ Baza mapa_czarna_db utworzona")
            else:
                print(f"⚠️ Błąd tworzenia bazy mapa_czarna_db: {msg_db}")

        # 4. Migracja danych z backup/Czarna (jeśli folder istnieje)
        backup_czarna = os.path.join(BACKUP_FOLDER, "Czarna")
        if os.path.exists(backup_czarna):
            # Sprawdź czy dane już są w bazie (sprawdź tabelę wlasciciele)
            try:
                conn = psycopg2.connect(
                    host=config['host'],
                    port=config['port'],
                    user=config['user'],
                    password=config['password'],
                    dbname='mapa_czarna_db'
                )
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM wlasciciele")
                count = cursor.fetchone()[0]
                cursor.close()
                conn.close()

                # Jeśli baza jest pusta - migruj dane
                if count == 0:
                    loading_dialog.update_status("Migracja danych...",
                                                "Import z backup/Czarna - to może potrwać chwilę")
                    print("🔄 Automatyczna migracja danych z backup/Czarna...")
                    auto_migrate_data_function(backup_czarna, "Czarna")
                    migrated_data = True

                    # Automatyczna kalibracja mapy po migracji
                    loading_dialog.update_status("Kalibracja mapy...",
                                                "Wczytywanie konfiguracji z backup")
                    auto_calibrate_map_from_backup()
                else:
                    print(f"ℹ️ Baza mapa_czarna_db już zawiera dane ({count} właścicieli)")
            except Exception as e:
                print(f"⚠️ Nie można sprawdzić danych w bazie: {e}")

        # Kalibruj mapę jeśli była utworzona nowa baza (nawet jeśli dane nie były migrowane)
        if created_czarna_db and not migrated_data:
            loading_dialog.update_status("Kalibracja mapy...",
                                        "Wczytywanie konfiguracji z backup")
            auto_calibrate_map_from_backup()

        # Zapisz informacje o tym co zostało zrobione (do pokazania później)
        loading_dialog.init_summary = {
            'created_launcher': created_launcher,
            'created_czarna_location': created_czarna_location,
            'created_czarna_db': created_czarna_db,
            'migrated_data': migrated_data
        }

        print("✅ Automatyczna inicjalizacja zakończona pomyślnie")

    except Exception as e:
        print(f"⚠️ Błąd podczas automatycznej inicjalizacji: {e}")
        import traceback
        traceback.print_exc()


def auto_calibrate_map_from_backup(location_name=None, db_name=None):
    """
    Automatycznie wczytuje kalibrację mapy z pliku map_config.json
    z folderu backup miejscowości i zapisuje do bazy danych.

    Ta funkcja jest wywoływana automatycznie przy pierwszym uruchomieniu
    oraz przy wczytywaniu miejscowości z backupu.

    Args:
        location_name: Nazwa miejscowości (opcjonalne, domyślnie aktywna)
        db_name: Nazwa bazy danych (opcjonalne, domyślnie z .env)
    """
    try:
        # Pobierz nazwę miejscowości
        if not location_name:
            location_name = get_active_location_name()
        if not location_name:
            return

        # Ścieżka do pliku map_config.json w backupie
        map_config_path = os.path.join(BACKUP_FOLDER, location_name, "map_config.json")

        if not os.path.exists(map_config_path):
            print(f"ℹ️ Brak pliku map_config.json w backup/{location_name}")
            return

        # Wczytaj konfigurację z pliku
        with open(map_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        calibration = config.get('calibration')
        defaults = config.get('defaults')

        if not calibration:
            print("⚠️ Brak danych kalibracji w map_config.json")
            return

        # Połącz się z bazą danych miejscowości
        if db_name:
            # Podano konkretną bazę danych
            pg_config = get_postgres_config()
            conn = psycopg2.connect(
                host=pg_config['host'],
                port=pg_config['port'],
                user=pg_config['user'],
                password=pg_config['password'],
                dbname=db_name
            )
        else:
            # Użyj aktywnej miejscowości
            db_config = get_db_config_from_env()
            conn = psycopg2.connect(**db_config)

        cur = conn.cursor()

        # Zapisz kalibrację do bazy
        cur.execute(
            "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES ('map_calibration', %s) "
            "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
            (json.dumps(calibration),)
        )

        # Zapisz domyślne ustawienia mapy jeśli są
        if defaults:
            cur.execute(
                "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES ('map_defaults', %s) "
                "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
                (json.dumps(defaults),)
            )

        conn.commit()
        cur.close()
        conn.close()

        print(f"✅ Automatyczna kalibracja mapy z {map_config_path}")
        print(f"   SW: {calibration.get('sw')}, NE: {calibration.get('ne')}")

    except Exception as e:
        print(f"⚠️ Błąd podczas automatycznej kalibracji mapy: {e}")
        import traceback
        traceback.print_exc()


def auto_migrate_data_function(backup_folder, location_name=None):
    """
    Funkcja pomocnicza do migracji danych (standalone, nie metoda klasy).

    Args:
        backup_folder: Ścieżka do folderu z danymi (np. backup/Czarna)
        location_name: Nazwa miejscowości (opcjonalne, jeśli None to wyekstrahuje z backup_folder)
    """
    try:
        import subprocess
        import sys

        # Ścieżka do skryptu migracji
        migrate_script = os.path.join(BASE_DIR, "backend", "migrate_data.py")

        if not os.path.exists(migrate_script):
            print(f"⚠️ Brak skryptu migracji: {migrate_script}")
            return

        # Jeśli nie podano nazwy miejscowości, spróbuj wyekstrahować z folderu
        if not location_name:
            # backup_folder może być np. "C:/projekty/backup/Borowa" lub "backup/Borowa"
            location_name = os.path.basename(backup_folder)
            print(f"📍 Wykryta miejscowość: {location_name}")

        # Uruchom skrypt migracji z nazwą miejscowości jako argument
        print(f"🔄 Migracja danych z {backup_folder}...")
        result = subprocess.run(
            [sys.executable, migrate_script, location_name],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60
        )

        if result.returncode == 0:
            print("✅ Migracja zakończona pomyślnie")
            if result.stdout:
                print(result.stdout)
        else:
            print(f"⚠️ Migracja zakończona z błędami:")
            if result.stderr:
                print(result.stderr)

    except subprocess.TimeoutExpired:
        print("⚠️ Migracja przekroczyła limit czasu (60s)")
    except Exception as e:
        print(f"⚠️ Błąd podczas migracji: {e}")


class DatabaseWizard(tk.Toplevel):
    """Narzędzie do zarządzania bazą danych PostgreSQL"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔧 Zarządzanie Bazą Danych")

        # Ustawienie większego rozmiaru okna z możliwością zmiany rozmiaru
        width = 800
        height = 800
        self.geometry(f"{width}x{height}")
        self.minsize(width, height)  # Minimalne wymiary okna
        self.transient(parent)
        self.grab_set()

        # Wycentruj
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.result = None
        self.config = get_postgres_config()
        self.connection_tested = False

        # Notebook (kroki)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Kroki
        self.create_step1_connection()
        self.create_step3_action()
        self.create_step4_progress()

        # Nawigacja
        nav_frame = ttk.Frame(self)
        nav_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(nav_frame, text="◀ Wstecz", command=self.prev_step).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="Dalej ▶", command=self.next_step).pack(side=tk.RIGHT, padx=5)
        ttk.Button(nav_frame, text="Anuluj", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    def create_step1_connection(self):
        """Krok 1: Połączenie"""
        frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(frame, text="1. Połączenie")

        ttk.Label(frame, text="Konfiguracja PostgreSQL", font=('Arial', 16, 'bold')).pack(pady=(0, 10))

        # Informacja o wymaganiach
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill=tk.X, pady=(0, 20))

        info_text = ttk.Label(info_frame,
                             text="⚠️ Program wymaga PostgreSQL do działania\n\n"
                                  "Podaj parametry połączenia do serwera PostgreSQL.\n"
                                  "Po udanym połączeniu będziesz mógł wybrać źródło danych:\n"
                                  "• Import z pliku ZIP (backup)\n"
                                  "• Rozpocznij z szablonem Czarna",
                             foreground="gray", justify=tk.LEFT)
        info_text.pack(pady=(0, 10))

        form = ttk.Frame(frame)
        form.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form, text="Host:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.host_entry = ttk.Entry(form, width=30)
        self.host_entry.insert(0, self.config['host'])
        self.host_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(form, text="Port:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.port_entry = ttk.Entry(form, width=30)
        self.port_entry.insert(0, str(self.config['port']))
        self.port_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(form, text="Użytkownik:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
        self.user_entry = ttk.Entry(form, width=30)
        self.user_entry.insert(0, self.config['user'])
        self.user_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(form, text="Hasło:").grid(row=3, column=0, sticky="w", pady=5, padx=5)
        self.password_entry = ttk.Entry(form, width=30, show="*")
        self.password_entry.insert(0, self.config['password'])
        self.password_entry.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        # Automatyczne testowanie po wpisaniu hasła
        self.password_entry.bind('<KeyRelease>', self.auto_test_connection)
        self.password_entry.bind('<FocusOut>', self.auto_test_connection)

        form.columnconfigure(1, weight=1)

        # Status połączenia z większą czcionką
        self.connection_status = ttk.Label(form, text="⚠️ Wpisz hasło do PostgreSQL",
                                          foreground="#856404", font=('Arial', 12, 'bold'))
        self.connection_status.grid(row=4, column=0, columnspan=2, pady=20)

        # Test początkowy jeśli hasło już istnieje
        if self.config['password']:
            self.after(100, self.test_connection)

    def create_step3_action(self):
        """Krok 2: Akcja"""
        frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(frame, text="2. Akcja")

        ttk.Label(frame, text="Co chcesz zrobić?", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Status
        self.db_status_frame = ttk.LabelFrame(frame, text="Status", padding="10")
        self.db_status_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        self.db_status_text = scrolledtext.ScrolledText(self.db_status_frame, height=8, wrap=tk.WORD, font=('Courier', 9))
        self.db_status_text.pack(fill=tk.BOTH, expand=True)

        # Akcje
        actions_frame = ttk.LabelFrame(frame, text="Wybierz", padding="10")
        actions_frame.pack(fill=tk.X)

        self.action_var = tk.StringVar(value="recreate_launcher_tables")

        # Opcje dla bazy launcher (mapa_launcher_db)
        ttk.Label(actions_frame, text="Baza launcher:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(5,2))
        ttk.Radiobutton(actions_frame, text="❌ Usuń tabele launcher (DROP TABLES)",
                       variable=self.action_var, value="drop_launcher_tables").pack(anchor=tk.W, pady=2, padx=10)
        ttk.Radiobutton(actions_frame, text="♻️ Odtwórz tabele launcher (DROP + CREATE)",
                       variable=self.action_var, value="recreate_launcher_tables").pack(anchor=tk.W, pady=2, padx=10)

        ttk.Separator(actions_frame, orient='horizontal').pack(fill='x', pady=10)

        # Opcje dla bazy miejscowości
        ttk.Label(actions_frame, text="Baza miejscowości:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(5,2))
        ttk.Radiobutton(actions_frame, text="❌ Usuń tabele miejscowości (DROP TABLES)",
                       variable=self.action_var, value="drop_location_tables").pack(anchor=tk.W, pady=2, padx=10)
        ttk.Radiobutton(actions_frame, text="♻️ Odtwórz tabele miejscowości (DROP + CREATE)",
                       variable=self.action_var, value="recreate_location_tables").pack(anchor=tk.W, pady=2, padx=10)

        # Dropdown z wyborem miejscowości
        location_frame = ttk.Frame(actions_frame)
        location_frame.pack(anchor=tk.W, pady=5, padx=20)

        ttk.Label(location_frame, text="Wybierz miejscowość:").pack(side=tk.LEFT, padx=(0, 10))

        self.location_var = tk.StringVar()
        self.location_combo = ttk.Combobox(location_frame, textvariable=self.location_var, state="readonly", width=30)
        self.location_combo.pack(side=tk.LEFT)

        # Wypełnij listę miejscowości
        self.refresh_locations_list()

        ttk.Button(frame, text="🔄 Odśwież status", command=self.refresh_status).pack(pady=10)

    def create_step4_progress(self):
        """Krok 3: Wykonanie"""
        frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(frame, text="3. Wykonanie")

        ttk.Label(frame, text="Instalacja...", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        self.progress = ttk.Progressbar(frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=10)

        log_frame = ttk.LabelFrame(frame, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD, font=('Courier', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.finish_button = ttk.Button(frame, text="✅ Zakończ", command=self.finish, state=tk.DISABLED)
        self.finish_button.pack(pady=10)

    def auto_test_connection(self, event=None):
        """Automatyczne testowanie połączenia po wpisaniu hasła"""
        password = self.password_entry.get()

        # Testuj tylko jeśli hasło ma przynajmniej 1 znak
        if len(password) > 0:
            # Anuluj poprzedni timer jeśli istnieje
            if hasattr(self, '_test_timer'):
                self.after_cancel(self._test_timer)

            # Ustaw nowy timer - test po 1 sekundzie od ostatniego znaku
            self._test_timer = self.after(1000, self.test_connection)

    def test_connection(self):
        """Test połączenia z PostgreSQL"""
        self.connection_status.config(text="🔄 Testowanie połączenia...", foreground="blue")
        self.update_idletasks()

        self.config['host'] = self.host_entry.get().strip()
        self.config['port'] = int(self.port_entry.get().strip())
        self.config['user'] = self.user_entry.get().strip()
        self.config['password'] = self.password_entry.get()

        success, msg = test_postgres_connection(**self.config)

        if success:
            # Zielona fajka - połączenie OK
            self.connection_status.config(text="✓ Połączenie Udane!", foreground="green")

            # Zapisz hasło do .postgres.env
            save_postgres_config(self.config['host'], self.config['port'],
                               self.config['user'], self.config['password'])

            # Włącz możliwość przejścia dalej
            self.connection_tested = True
        else:
            # Czerwony krzyżyk - błąd
            self.connection_status.config(text=f"✗ Błąd: {msg}", foreground="red")
            self.connection_tested = False

    def auto_migrate_data(self, backup_folder):
        """
        Automatyczna migracja danych z folderu backup do PostgreSQL.

        Args:
            backup_folder: Ścieżka do folderu z danymi (np. backup/Czarna)
        """
        try:
            import subprocess
            import sys

            # Ścieżka do skryptu migracji
            migrate_script = os.path.join(BASE_DIR, "backend", "migrate_data.py")

            if not os.path.exists(migrate_script):
                print(f"⚠️ Brak skryptu migracji: {migrate_script}")
                return

            # Uruchom skrypt migracji w tle
            print(f"🔄 Migracja danych z {backup_folder}...")
            result = subprocess.run(
                [sys.executable, migrate_script],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Zamień niezrozumiałe znaki na ?
                timeout=60
            )

            if result.returncode == 0:
                print("✅ Migracja zakończona pomyślnie")
                print(result.stdout)
            else:
                print(f"⚠️ Migracja zakończona z błędami:")
                print(result.stderr)

        except subprocess.TimeoutExpired:
            print("⚠️ Migracja przekroczyła limit czasu (60s)")
        except Exception as e:
            print(f"⚠️ Błąd podczas migracji: {e}")

    def refresh_status(self):
        """Odśwież status baz"""
        self.db_status_text.delete('1.0', tk.END)

        databases = postgres_list_databases(**self.config)

        self.db_status_text.insert(tk.END, "=== Bazy danych ===\n\n")

        launcher_exists = postgres_database_exists(**self.config, db_name='mapa_launcher_db')
        if launcher_exists:
            self.db_status_text.insert(tk.END, "✓ mapa_launcher_db (konfiguracja)\n")
        else:
            self.db_status_text.insert(tk.END, "✗ mapa_launcher_db - BRAK\n")

        self.db_status_text.insert(tk.END, "\n=== Miejscowości ===\n\n")

        location_dbs = [db for db in databases if db.startswith('mapa_') and db != 'mapa_launcher_db']
        if location_dbs:
            for db in location_dbs:
                self.db_status_text.insert(tk.END, f"  • {db}\n")
        else:
            self.db_status_text.insert(tk.END, "  Brak\n")

    def refresh_locations_list(self):
        """Odśwież listę miejscowości w dropdownie"""
        try:
            locations = get_all_locations()
            if locations:
                # Format: (id, name, full_name, powiat, region, active, homepage_template, year, century,
                #          homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
                #          postgres_db_name, history_photos)
                location_items = []
                for loc in locations:
                    loc_id, name = loc[0], loc[1]
                    postgres_db_name = loc[13] if len(loc) > 13 and loc[13] else ""  # postgres_db_name jest na indeksie 13

                    # Pokaż nazwę miejscowości i nazwę bazy
                    if postgres_db_name:
                        display = f"{name} → {postgres_db_name}"
                        location_items.append((display, postgres_db_name))
                    else:
                        display = f"{name} (brak bazy)"
                        location_items.append((display, ""))

                # Ustaw wartości w combobox
                self.location_combo['values'] = [item[0] for item in location_items]
                self.location_data = location_items  # Przechowuj pełne dane

                if location_items:
                    self.location_combo.current(0)
            else:
                self.location_combo['values'] = ["Brak miejscowości"]
                self.location_data = []
        except Exception as e:
            print(f"⚠️ Błąd odświeżania listy miejscowości: {e}")
            import traceback
            traceback.print_exc()
            self.location_combo['values'] = ["Błąd wczytywania"]
            self.location_data = []

    def next_step(self):
        """Następny krok"""
        current = self.notebook.index(self.notebook.select())

        if current == 0:
            # Krok 1 -> 2: Sprawdź czy połączenie zostało przetestowane
            if not self.connection_tested:
                messagebox.showwarning("Uwaga", "Przetestuj połączenie z PostgreSQL!", parent=self)
                return
            # Przejdź do kroku 2 (Akcja) i odśwież status
            self.refresh_status()
            self.notebook.select(1)

        elif current == 1:
            # Krok 2 -> 3: Wykonaj akcję
            self.notebook.select(2)
            self.execute_action()

    def prev_step(self):
        """Poprzedni krok"""
        current = self.notebook.index(self.notebook.select())
        if current > 0:
            self.notebook.select(current - 1)

    def log(self, msg):
        """Log"""
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.update()

    def execute_action(self):
        """Wykonaj akcję"""
        action = self.action_var.get()
        self.progress.start()
        self.log("🚀 Rozpoczynam...\n")

        try:
            if action == "create_launcher_db":
                self.create_launcher_database()
            elif action == "drop_launcher_tables":
                self.drop_launcher_tables()
            elif action == "recreate_launcher_tables":
                self.recreate_launcher_tables()
            elif action == "create_location_db":
                self.create_location_database()
            elif action == "drop_location_tables":
                self.drop_location_tables()
            elif action == "recreate_location_tables":
                self.recreate_location_tables()
            elif action == "drop_location_database":
                self.drop_location_database()

            self.log("\n✅ Gotowe!")
            self.result = True
            self.finish_button.config(state=tk.NORMAL)
        except Exception as e:
            self.log(f"\n❌ Błąd: {e}")
            messagebox.showerror("Błąd", str(e), parent=self)
        finally:
            self.progress.stop()

    # === FUNKCJE DLA BAZY LAUNCHER ===

    def create_launcher_database(self):
        """Utwórz bazę launcher (CREATE DATABASE + tables)"""
        self.log("=== Tworzenie bazy launcher ===\n")

        self.log("1. Tworzę bazę mapa_launcher_db...")
        success, msg = postgres_create_database(**self.config, db_name='mapa_launcher_db')
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("2. Włączam rozszerzenie PostGIS...")
        success, msg = postgres_enable_postgis(**self.config, db_name='mapa_launcher_db')
        self.log(f"   {msg}")
        if not success:
            self.log(f"   ⚠️ Ostrzeżenie: {msg}")

        self.log("3. Tworzę tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name='mapa_launcher_db', schema_sql=LAUNCHER_DB_SCHEMA)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        global LOCATIONS_DB_INITIALIZED
        LOCATIONS_DB_INITIALIZED = False

    def drop_launcher_tables(self):
        """Usuń tabele launcher (DROP TABLES)"""
        self.log("=== Usuwanie tabel launcher ===\n")

        if not postgres_database_exists(**self.config, db_name='mapa_launcher_db'):
            raise Exception("Baza mapa_launcher_db nie istnieje!")

        self.log("Usuwam tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name='mapa_launcher_db', schema_sql=LAUNCHER_DROP_TABLES)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("\n⚠️ Wszystkie dane usunięte!")

        global LOCATIONS_DB_INITIALIZED
        LOCATIONS_DB_INITIALIZED = False

    def recreate_launcher_tables(self):
        """Odtwórz tabele launcher (DROP + CREATE)"""
        self.log("=== Odtwarzanie tabel launcher ===\n")

        if not postgres_database_exists(**self.config, db_name='mapa_launcher_db'):
            raise Exception("Baza mapa_launcher_db nie istnieje!")

        self.log("1. Usuwam stare tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name='mapa_launcher_db', schema_sql=LAUNCHER_DROP_TABLES)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("2. Włączam rozszerzenie PostGIS...")
        success, msg = postgres_enable_postgis(**self.config, db_name='mapa_launcher_db')
        self.log(f"   {msg}")
        if not success:
            self.log(f"   ⚠️ Ostrzeżenie: {msg}")

        self.log("3. Tworzę nowe tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name='mapa_launcher_db', schema_sql=LAUNCHER_DB_SCHEMA)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("\n⚠️ Wszystkie dane usunięte i tabele odtworzone!")

        global LOCATIONS_DB_INITIALIZED
        LOCATIONS_DB_INITIALIZED = False

    # === FUNKCJE DLA BAZY MIEJSCOWOŚCI ===

    def _get_selected_location_db(self):
        """Pobiera nazwę bazy wybranej miejscowości"""
        selected_index = self.location_combo.current()
        if selected_index < 0 or not hasattr(self, 'location_data') or not self.location_data:
            raise Exception("Wybierz miejscowość z listy!")

        display_name, db_name = self.location_data[selected_index]
        if not db_name:
            raise Exception("Wybrana miejscowość nie ma przypisanej bazy danych!")

        return db_name

    def create_location_database(self):
        """Utwórz bazę miejscowości (CREATE DATABASE + tables)"""
        self.log("=== Tworzenie bazy miejscowości ===\n")

        db_name = self._get_selected_location_db()
        self.log(f"Baza: {db_name}\n")

        self.log("1. Tworzę bazę...")
        success, msg = postgres_create_database(**self.config, db_name=db_name)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("2. Włączam rozszerzenie PostGIS...")
        success, msg = postgres_enable_postgis(**self.config, db_name=db_name)
        self.log(f"   {msg}")
        if not success:
            self.log(f"   ⚠️ Ostrzeżenie: {msg}")

        self.log("3. Tworzę tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name=db_name, schema_sql=LOCATION_DB_SCHEMA)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

    def drop_location_tables(self):
        """Usuń tabele miejscowości (DROP TABLES)"""
        self.log("=== Usuwanie tabel miejscowości ===\n")

        db_name = self._get_selected_location_db()
        self.log(f"Baza: {db_name}\n")

        if not postgres_database_exists(**self.config, db_name=db_name):
            raise Exception(f"Baza {db_name} nie istnieje!")

        self.log("Usuwam tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name=db_name, schema_sql=LOCATION_DROP_TABLES)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("\n⚠️ Wszystkie dane usunięte!")

    def recreate_location_tables(self):
        """Odtwórz tabele miejscowości (DROP + CREATE)"""
        self.log("=== Odtwarzanie tabel miejscowości ===\n")

        db_name = self._get_selected_location_db()
        self.log(f"Baza: {db_name}\n")

        if not postgres_database_exists(**self.config, db_name=db_name):
            raise Exception(f"Baza {db_name} nie istnieje!")

        self.log("1. Usuwam stare tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name=db_name, schema_sql=LOCATION_DROP_TABLES)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("2. Włączam rozszerzenie PostGIS...")
        success, msg = postgres_enable_postgis(**self.config, db_name=db_name)
        self.log(f"   {msg}")
        if not success:
            self.log(f"   ⚠️ Ostrzeżenie: {msg}")

        self.log("3. Tworzę nowe tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name=db_name, schema_sql=LOCATION_DB_SCHEMA)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("\n⚠️ Wszystkie dane usunięte i tabele odtworzone!")

    def drop_location_database(self):
        """Usuń całą bazę miejscowości (DROP DATABASE)"""
        self.log("=== Usuwanie całej bazy miejscowości ===\n")

        db_name = self._get_selected_location_db()
        self.log(f"Baza: {db_name}\n")

        if not postgres_database_exists(**self.config, db_name=db_name):
            raise Exception(f"Baza {db_name} nie istnieje!")

        # Potwierdzenie
        confirm = messagebox.askyesno(
            "⚠️ UWAGA",
            f"Czy na pewno chcesz CAŁKOWICIE USUNĄĆ bazę {db_name}?\n\n"
            "Wszystkie dane zostaną bezpowrotnie utracone!",
            icon='warning',
            parent=self
        )

        if not confirm:
            raise Exception("Anulowano przez użytkownika")

        self.log("Usuwam bazę danych...")

        # DROP DATABASE
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database='postgres'
            )
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(f"DROP DATABASE IF EXISTS {db_name}")
            cursor.close()
            conn.close()

            self.log(f"   ✓ Baza {db_name} została usunięta")
        except Exception as e:
            raise Exception(f"Błąd usuwania bazy: {e}")

        self.log("\n⚠️ Baza całkowicie usunięta!")

    def finish(self):
        """Zakończ"""
        self.destroy()


class PhotosManagerDialog(tk.Toplevel):
    """Dialog do zarządzania listą zdjęć historycznych (max 20)."""

    def __init__(self, parent, photos_list, base_dir, location_name="Czarna"):
        super().__init__(parent)
        self.title("📸 Zarządzaj zdjęciami historycznymi")
        self.geometry("700x500")
        self.transient(parent)
        self.grab_set()

        self.photos_list = photos_list.copy() if photos_list else []
        self.base_dir = base_dir
        self.location_name = location_name
        # Ścieżka do folderu history_photos w miejscowości
        self.assets_dir = os.path.join(base_dir, "backup", location_name, "history_photos")
        self.result = None

        # Główny frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Info o limicie
        info_label = ttk.Label(main_frame, text="Możesz dodać maksymalnie 20 zdjęć. Zarządzaj kolejnością i podpisami.",
                               foreground="gray")
        info_label.pack(anchor=tk.W, pady=(0, 10))

        # Frame z listą i scrollbarem
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.photos_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=15)
        self.photos_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.photos_listbox.yview)

        # Przyciski do zarządzania
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(buttons_frame, text="➕ Dodaj zdjęcie", command=self.add_photo).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="✏️ Edytuj", command=self.edit_photo).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="🗑️ Usuń", command=self.delete_photo).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="⬆️ W górę", command=self.move_up).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="⬇️ W dół", command=self.move_down).pack(side=tk.LEFT, padx=5)

        # Przyciski OK/Cancel
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(bottom_frame, text="✅ OK", command=self.on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom_frame, text="❌ Anuluj", command=self.destroy).pack(side=tk.RIGHT)

        # Załaduj listę
        self.refresh_list()

    def refresh_list(self):
        """Odśwież listę zdjęć."""
        self.photos_listbox.delete(0, tk.END)
        for i, photo in enumerate(self.photos_list, 1):
            self.photos_listbox.insert(tk.END, f"{i}. {photo['filename']} - {photo['caption'][:50]}")

    def add_photo(self):
        """Dodaj nowe zdjęcie."""
        if len(self.photos_list) >= 20:
            messagebox.showwarning("Limit zdjęć", "Możesz dodać maksymalnie 20 zdjęć.", parent=self)
            return

        # Wybierz plik
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Wybierz zdjęcie",
            filetypes=[
                ("Pliki graficzne", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("Wszystkie pliki", "*.*")
            ]
        )

        if not file_path:
            return

        # Pobierz nazwę bez rozszerzenia
        original_filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(original_filename)[0]
        extension = os.path.splitext(original_filename)[1]

        # Zapytaj o nazwę pliku
        new_filename = tk.simpledialog.askstring(
            "Nazwa pliku",
            f"Podaj nazwę dla tego zdjęcia (bez rozszerzenia):",
            initialvalue=name_without_ext,
            parent=self
        )

        if not new_filename:
            return

        # Dodaj rozszerzenie
        new_filename = new_filename + extension

        # Zapytaj o podpis
        caption = tk.simpledialog.askstring(
            "Podpis zdjęcia",
            "Podaj podpis do zdjęcia:",
            parent=self
        )

        if not caption:
            caption = "Zdjęcie historyczne"

        # Sprawdź czy plik o tej nazwie już istnieje
        dest_path = os.path.join(self.assets_dir, new_filename)
        if os.path.exists(dest_path):
            if not messagebox.askyesno("Plik istnieje",
                                       f"Plik {new_filename} już istnieje. Czy nadpisać?",
                                       parent=self):
                return

        # Skopiuj plik
        try:
            os.makedirs(self.assets_dir, exist_ok=True)
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się skopiować pliku:\n{e}", parent=self)
            return

        # Dodaj do listy
        self.photos_list.append({
            "filename": new_filename,
            "caption": caption
        })

        self.refresh_list()
        self.photos_listbox.selection_clear(0, tk.END)
        self.photos_listbox.selection_set(tk.END)
        self.photos_listbox.see(tk.END)

    def edit_photo(self):
        """Edytuj wybrany."""
        selection = self.photos_listbox.curselection()
        if not selection:
            messagebox.showinfo("Brak wyboru", "Wybierz zdjęcie do edycji.", parent=self)
            return

        idx = selection[0]
        photo = self.photos_list[idx]

        # Edytuj podpis
        new_caption = tk.simpledialog.askstring(
            "Edytuj podpis",
            "Podaj nowy podpis:",
            initialvalue=photo['caption'],
            parent=self
        )

        if new_caption is not None:
            photo['caption'] = new_caption
            self.refresh_list()
            self.photos_listbox.selection_set(idx)

    def delete_photo(self):
        """Usuń wybrane zdjęcie."""
        selection = self.photos_listbox.curselection()
        if not selection:
            messagebox.showinfo("Brak wyboru", "Wybierz zdjęcie do usunięcia.", parent=self)
            return

        idx = selection[0]
        photo = self.photos_list[idx]

        if messagebox.askyesno("Potwierdź usunięcie",
                               f"Czy na pewno usunąć zdjęcie:\n{photo['filename']}?\n\nPlik zostanie trwale usunięty z folderu.",
                               parent=self):
            # Usuń fizyczny plik z dysku
            file_path = os.path.join(self.assets_dir, photo['filename'])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"✓ Usunięto plik: {file_path}")
                else:
                    print(f"⚠️ Plik nie istnieje: {file_path}")
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie udało się usunąć pliku:\n{e}", parent=self)
                return

            # Usuń z listy
            del self.photos_list[idx]
            self.refresh_list()

    def move_up(self):
        """Przesuń zdjęcie w górę."""
        selection = self.photos_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx == 0:
            return  # Już na górze

        # Zamień miejscami
        self.photos_list[idx], self.photos_list[idx-1] = self.photos_list[idx-1], self.photos_list[idx]
        self.refresh_list()
        self.photos_listbox.selection_set(idx-1)
        self.photos_listbox.see(idx-1)

    def move_down(self):
        """Przesuń zdjęcie w dół."""
        selection = self.photos_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx >= len(self.photos_list) - 1:
            return  # Już na dole

        # Zamień miejscami
        self.photos_list[idx], self.photos_list[idx+1] = self.photos_list[idx+1], self.photos_list[idx]
        self.refresh_list()
        self.photos_listbox.selection_set(idx+1)
        self.photos_listbox.see(idx+1)

    def on_ok(self):
        """Zatwierdź zmiany."""
        self.result = self.photos_list
        self.destroy()


class AddEditLocationDialog(tk.Toplevel):
    """Dialog do dodawania/edytowania miejscowości z zakładkami."""

    def __init__(self, parent, title, name="", full_name="", powiat="", region="", year="1882", century="XIX w.",
                 homepage_description="", history_paragraph1="", history_paragraph2="", history_paragraph3="",
                 history_photos=None, postgres_db_name="", homepage_template="standardowy",
                 gmina_katastralna="Czarna", miejscowosc_protokolu="Pilzno"):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.grab_set()

        self.result = None
        self.history_photos = history_photos if history_photos else []

        # Rozmiar większy dla zakładek
        w, h = 700, 650  # Zwiększam wysokość dla nowego pola
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(True, True)

        # Główny kontener
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Notebook (zakładki)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # === ZAKŁADKA 1: Podstawowe dane ===
        basic_frame = ttk.Frame(notebook, padding="20")
        notebook.add(basic_frame, text="Podstawowe dane")

        ttk.Label(basic_frame, text="Nazwa (folder):").grid(row=0, column=0, sticky="w", pady=5)
        self.name_entry = ttk.Entry(basic_frame, width=50)
        self.name_entry.insert(0, name)
        self.name_entry.grid(row=0, column=1, pady=5, padx=10, sticky="ew")

        ttk.Label(basic_frame, text="Pełna nazwa:").grid(row=1, column=0, sticky="w", pady=5)
        self.full_name_entry = ttk.Entry(basic_frame, width=50)
        self.full_name_entry.insert(0, full_name)
        self.full_name_entry.grid(row=1, column=1, pady=5, padx=10, sticky="ew")

        ttk.Label(basic_frame, text="Powiat:").grid(row=2, column=0, sticky="w", pady=5)
        self.powiat_entry = ttk.Entry(basic_frame, width=50)
        self.powiat_entry.insert(0, powiat)
        self.powiat_entry.grid(row=2, column=1, pady=5, padx=10, sticky="ew")

        ttk.Label(basic_frame, text="Region:").grid(row=3, column=0, sticky="w", pady=5)
        self.region_entry = ttk.Entry(basic_frame, width=50)
        self.region_entry.insert(0, region)
        self.region_entry.grid(row=3, column=1, pady=5, padx=10, sticky="ew")

        # NOWE POLE: Baza danych PostgreSQL
        ttk.Label(basic_frame, text="Baza danych:").grid(row=4, column=0, sticky="w", pady=5)

        # Pobierz listę dostępnych baz PostgreSQL
        available_dbs = self.get_available_databases()

        # Jeśli postgres_db_name jest podane ale nie ma go w liście, dodaj do listy
        # (może być sytuacja gdy baza istnieje ale nie została wykryta)
        if postgres_db_name and postgres_db_name not in available_dbs:
            # Wstaw przed opcją "(nowa baza...)"
            available_dbs.insert(-1, postgres_db_name)

        self.db_combo = ttk.Combobox(basic_frame, width=47, state="readonly")
        self.db_combo['values'] = available_dbs

        # Ustaw domyślną wartość
        if postgres_db_name:
            # Jeśli jest postgres_db_name, użyj go
            self.db_combo.set(postgres_db_name)
        elif available_dbs:
            # Jeśli brak wartości, zaproponuj bazę na podstawie nazwy miejscowości
            if name:
                suggested_db = f"mapa_{name.lower()}_db"
                if suggested_db in available_dbs:
                    self.db_combo.set(suggested_db)
                else:
                    self.db_combo.set(available_dbs[0])
            else:
                self.db_combo.set(available_dbs[0])

        self.db_combo.grid(row=4, column=1, pady=5, padx=10, sticky="ew")

        # Dodaj przycisk odświeżania listy baz
        refresh_btn = ttk.Button(basic_frame, text="🔄", width=3,
                                command=self.refresh_databases)
        refresh_btn.grid(row=4, column=2, pady=5, padx=(0, 10))

        ttk.Label(basic_frame, text="Rok mapy:").grid(row=5, column=0, sticky="w", pady=5)
        self.year_entry = ttk.Entry(basic_frame, width=50)
        self.year_entry.insert(0, year)
        self.year_entry.grid(row=5, column=1, pady=5, padx=10, sticky="ew")

        ttk.Label(basic_frame, text="Wiek (np. XIX w.):").grid(row=6, column=0, sticky="w", pady=5)
        self.century_entry = ttk.Entry(basic_frame, width=50)
        self.century_entry.insert(0, century)
        self.century_entry.grid(row=6, column=1, pady=5, padx=10, sticky="ew")

        basic_frame.columnconfigure(1, weight=1)

        # === ZAKŁADKA 2: Protokół ===
        protokol_frame = ttk.Frame(notebook, padding="20")
        notebook.add(protokol_frame, text="Protokół")

        ttk.Label(protokol_frame, text="Gmina katastralna:").grid(row=0, column=0, sticky="w", pady=5)
        self.gmina_katastralna_entry = ttk.Entry(protokol_frame, width=50)
        self.gmina_katastralna_entry.insert(0, gmina_katastralna)
        self.gmina_katastralna_entry.grid(row=0, column=1, pady=5, padx=10, sticky="ew")

        ttk.Label(protokol_frame, text="Miejscowość protokołu:").grid(row=1, column=0, sticky="w", pady=5)
        self.miejscowosc_protokolu_entry = ttk.Entry(protokol_frame, width=50)
        self.miejscowosc_protokolu_entry.insert(0, miejscowosc_protokolu)
        self.miejscowosc_protokolu_entry.grid(row=1, column=1, pady=5, padx=10, sticky="ew")

        # Info
        info_label = ttk.Label(protokol_frame,
                               text="Te wartości będą używane w protokołach katastralnych.\n"
                                    "Gmina katastralna: używana w tytule protokołu.\n"
                                    "Miejscowość protokołu: używana jako lokalizacja protokołu.",
                               foreground="gray", wraplength=500)
        info_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=15)

        protokol_frame.columnconfigure(1, weight=1)

        # === ZAKŁADKA 3: Strona główna ===
        homepage_frame = ttk.Frame(notebook, padding="20")
        notebook.add(homepage_frame, text="Strona główna")

        # Wybór szablonu
        template_selection_frame = ttk.Frame(homepage_frame)
        template_selection_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(template_selection_frame, text="Szablon strony głównej:").pack(side=tk.LEFT, padx=(0, 10))

        self.homepage_template_var = tk.StringVar(value=homepage_template)
        self.template_combo = ttk.Combobox(template_selection_frame,
                                          textvariable=self.homepage_template_var,
                                          values=["standardowy", "praca_inzynierska"],
                                          state="readonly", width=30)
        self.template_combo.pack(side=tk.LEFT)
        self.template_combo.bind("<<ComboboxSelected>>", self.on_template_change)

        # Frame dla opisu (pokazywany/ukrywany w zależności od szablonu)
        self.homepage_desc_frame = ttk.Frame(homepage_frame)
        self.homepage_desc_frame.pack(fill=tk.BOTH, expand=True)

        self.homepage_desc_label = ttk.Label(self.homepage_desc_frame, text="Opis strony głównej:")
        self.homepage_desc_label.pack(anchor="w", pady=(0, 5))

        self.homepage_desc_text = scrolledtext.ScrolledText(self.homepage_desc_frame, width=60, height=8, wrap=tk.WORD)
        self.homepage_desc_text.insert("1.0", homepage_description)
        self.homepage_desc_text.pack(fill=tk.BOTH, expand=True)

        # Info o szablonie inżynierskim
        self.template_info_label = ttk.Label(homepage_frame,
                                            text="Szablon 'praca inżynierska' ma stały wygląd i nie jest modyfikowalny.",
                                            foreground="gray", wraplength=500)

        # Pokaż/ukryj opis w zależności od szablonu
        self.update_template_visibility()

        # === ZAKŁADKA 4: Historia ===
        history_frame = ttk.Frame(notebook, padding="20")
        notebook.add(history_frame, text="Historia")

        ttk.Label(history_frame, text="Akapit 1 (pochodzenie miejscowości):").pack(anchor="w", pady=(0, 5))
        self.history_p1_text = scrolledtext.ScrolledText(history_frame, width=60, height=5, wrap=tk.WORD)
        self.history_p1_text.insert("1.0", history_paragraph1)
        self.history_p1_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ttk.Label(history_frame, text="Akapit 2 (rozwój, kolej):").pack(anchor="w", pady=(0, 5))
        self.history_p2_text = scrolledtext.ScrolledText(history_frame, width=60, height=5, wrap=tk.WORD)
        self.history_p2_text.insert("1.0", history_paragraph2)
        self.history_p2_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ttk.Label(history_frame, text="Akapit 3 (statystyki 1882):").pack(anchor="w", pady=(0, 5))
        self.history_p3_text = scrolledtext.ScrolledText(history_frame, width=60, height=4, wrap=tk.WORD)
        self.history_p3_text.insert("1.0", history_paragraph3)
        self.history_p3_text.pack(fill=tk.BOTH, expand=True)

        # === ZAKŁADKA 5: Historia - Zdjęcia ===
        photos_frame = ttk.Frame(notebook, padding="20")
        notebook.add(photos_frame, text="Historia - Zdjęcia")

        # Info
        info_label = ttk.Label(photos_frame,
                               text="Zarządzaj zdjęciami historycznymi wyświetlanymi na stronie historia.\n"
                                    "Możesz dodać maksymalnie 20 zdjęć.",
                               foreground="gray")
        info_label.pack(anchor=tk.W, pady=(0, 10))

        # Liczba zdjęć
        count_label = ttk.Label(photos_frame, text=f"Obecnie: {len(self.history_photos)} zdjęć")
        count_label.pack(anchor=tk.W, pady=(0, 10))
        self.photos_count_label = count_label

        # Przycisk zarządzania
        manage_btn = ttk.Button(photos_frame, text="🖼️ Zarządzaj zdjęciami",
                                command=self.manage_photos)
        manage_btn.pack(anchor=tk.W)

        # Przyciski
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(buttons_frame, text="✅ Zapisz", command=self.save,
                  style="Success.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="❌ Anuluj", command=self.destroy,
                  style="Danger.TButton").pack(side=tk.LEFT, padx=5)

    def get_available_databases(self):
        """
        Pobiera listę dostępnych baz danych PostgreSQL (mapa_*_db).
        """
        databases = []

        # Sprawdź czy PostgreSQL jest dostępny
        if check_postgres_available():
            try:
                config = get_postgres_config()
                pg_dbs = postgres_list_databases(config['host'], config['port'],
                                                 config['user'], config['password'])

                # Filtruj tylko bazy zaczynające się od "mapa_"
                map_dbs = [db for db in pg_dbs if db.startswith('mapa_') and db != 'mapa_launcher_db']
                databases.extend(sorted(map_dbs))
            except Exception as e:
                print(f"❌ Błąd pobierania listy baz: {e}")

        # Dodaj opcję tworzenia nowej bazy
        databases.append("(nowa baza - wpisz nazwę)")
        return databases

    def refresh_databases(self):
        """Odświeża listę dostępnych baz danych."""
        current_value = self.db_combo.get()
        available_dbs = self.get_available_databases()
        self.db_combo['values'] = available_dbs

        # Przywróć wartość jeśli istnieje
        if current_value in available_dbs:
            self.db_combo.set(current_value)
        elif available_dbs:
            self.db_combo.set(available_dbs[0])

    def on_template_change(self, event=None):
        """Wywoływana gdy zmieni się wybór szablonu."""
        self.update_template_visibility()

    def update_template_visibility(self):
        """Pokazuje/ukrywa pole opisu w zależności od wybranego szablonu."""
        template = self.homepage_template_var.get()

        if template == "standardowy":
            # Pokaż pole opisu
            self.homepage_desc_frame.pack(fill=tk.BOTH, expand=True)
            self.template_info_label.pack_forget()
        else:
            # Ukryj pole opisu, pokaż info
            self.homepage_desc_frame.pack_forget()
            self.template_info_label.pack(anchor="w", pady=(0, 10))

    def manage_photos(self):
        """Otwiera dialog zarządzania zdjęciami."""
        # Pobierz nazwę miejscowości z pola
        location_name = self.name_entry.get().strip() or "Czarna"
        dialog = PhotosManagerDialog(self, self.history_photos, BASE_DIR, location_name)
        self.wait_window(dialog)

        if dialog.result is not None:
            self.history_photos = dialog.result
            # Zaktualizuj licznik
            self.photos_count_label.config(text=f"Obecnie: {len(self.history_photos)} zdjęć")

    def save(self):
        """Zapisuje dane i zamyka okno."""
        name = self.name_entry.get().strip()
        full_name = self.full_name_entry.get().strip()
        powiat = self.powiat_entry.get().strip()
        region = self.region_entry.get().strip()
        year = self.year_entry.get().strip()
        century = self.century_entry.get().strip()
        postgres_db_name = self.db_combo.get().strip()

        # Pobierz teksty z ScrolledText
        homepage_desc = self.homepage_desc_text.get("1.0", tk.END).strip()
        history_p1 = self.history_p1_text.get("1.0", tk.END).strip()
        history_p2 = self.history_p2_text.get("1.0", tk.END).strip()
        history_p3 = self.history_p3_text.get("1.0", tk.END).strip()

        if not name:
            messagebox.showerror("❌ Błąd", "Nazwa jest wymagana!", parent=self)
            return

        if not full_name:
            messagebox.showerror("❌ Błąd", "Pełna nazwa jest wymagana!", parent=self)
            return

        if not year:
            year = "1882"  # Domyślna wartość

        if not century:
            century = "XIX w."  # Domyślna wartość

        # Obsłuż specjalne wartości bazy danych
        if postgres_db_name == "(nowa baza - wpisz nazwę)":
            # Zaproponuj domyślną nazwę
            suggested_name = f"mapa_{name.lower()}_db"
            new_db_name = simpledialog.askstring(
                "Nazwa bazy danych",
                f"Podaj nazwę nowej bazy danych PostgreSQL:",
                initialvalue=suggested_name,
                parent=self
            )
            if not new_db_name:
                messagebox.showerror("❌ Błąd", "Musisz podać nazwę bazy danych!", parent=self)
                return
            else:
                postgres_db_name = new_db_name.strip()

        # Walidacja - baza danych jest teraz wymagana
        if not postgres_db_name:
            messagebox.showerror("❌ Błąd", "Musisz wybrać lub utworzyć bazę danych PostgreSQL!", parent=self)
            return

        # Pobierz wybrany szablon
        homepage_template = self.homepage_template_var.get()

        # Pobierz wartości protokołu
        gmina_katastralna = self.gmina_katastralna_entry.get().strip()
        miejscowosc_protokolu = self.miejscowosc_protokolu_entry.get().strip()

        # Ustaw domyślne wartości jeśli puste
        if not gmina_katastralna:
            gmina_katastralna = "Czarna"
        if not miejscowosc_protokolu:
            miejscowosc_protokolu = "Pilzno"

        self.result = (name, full_name, powiat, region, year, century,
                      homepage_desc, history_p1, history_p2, history_p3,
                      self.history_photos, postgres_db_name, homepage_template,
                      gmina_katastralna, miejscowosc_protokolu)
        self.destroy()


class MapCalibrator(tk.Toplevel):
    """Okno do kalibracji współrzędnych mapy."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📍 Konfigurator Mapy")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.parent_app = parent

        # Użyj folderu aktywnej miejscowości
        active_location_name = get_active_location_name()
        if active_location_name:
            location_folder = os.path.join(BACKUP_FOLDER, active_location_name)
        else:
            location_folder = BACKUP_FOLDER

        self.config_path = os.path.join(location_folder, "map_config.json")
        self.vars = {
            'sw_lat': tk.StringVar(), 'sw_lng': tk.StringVar(),
            'ne_lat': tk.StringVar(), 'ne_lng': tk.StringVar(),
            'center_lat': tk.StringVar(), 'center_lng': tk.StringVar(),
            'zoom': tk.StringVar()
        }
        
        self.create_widgets()
        self.load_config_from_file()
        self.check_current_map_status()
        self.center_window()

    def create_widgets(self):
        """Tworzy interfejs konfiguracji mapy."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Nagłówek z przyciskiem instrukcji
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_frame, text="Konfiguracja Mapy Historycznej", style="Heading.TLabel").pack(side=tk.LEFT)
        ttk.Button(header_frame, text="📘 Instrukcja", command=self.show_instructions, style="Info.TButton").pack(side=tk.RIGHT)
        
        # Kontener na podgląd i status
        preview_container = ttk.Frame(main_frame)
        preview_container.pack(fill=tk.X, pady=5)
        preview_container.columnconfigure(1, weight=1)
        
        # Podgląd mapy
        self.map_preview_canvas = tk.Canvas(preview_container, width=200, height=120, bg="grey", highlightthickness=1)
        self.map_preview_canvas.grid(row=0, column=0, rowspan=2, padx=(0, 10), sticky="ns")
        self.map_preview_label = ttk.Label(self.map_preview_canvas, text="Podgląd mapy", foreground="white")
        self.map_preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Status mapy
        status_frame = ttk.Frame(preview_container, relief="sunken", borderwidth=1, padding=5)
        status_frame.grid(row=0, column=1, sticky="ew")
        self.map_status_label = ttk.Label(status_frame, text="Sprawdzanie statusu mapy...")
        self.map_status_label.pack()
        
        ttk.Label(preview_container, text="Podgląd jest generowany z pliku w folderze /mapa/.",
                 wraplength=400).grid(row=1, column=1, sticky="w", pady=(5,0))
        
        # Współrzędne graniczne
        frame_cal = ttk.LabelFrame(main_frame, text="1. Współrzędne graniczne (z GIS)", padding="15")
        frame_cal.pack(fill=tk.X, pady=5)
        
        self._create_coord_inputs(frame_cal)
        
        # Domyślny widok
        frame_def = ttk.LabelFrame(main_frame, text="2. Domyślny widok mapy", padding="15")
        frame_def.pack(fill=tk.X, pady=5)
        
        self._create_default_view_inputs(frame_def)
        
        # Wybór pliku mapy
        frame_map_file = ttk.LabelFrame(main_frame, text="3. Plik mapy tła", padding="15")
        frame_map_file.pack(fill=tk.X, pady=5)
        ttk.Button(frame_map_file, text="Wybierz Plik Mapy (.jpg, .png)",
                  command=self.select_map_file, style="Primary.TButton").pack(fill=tk.X, expand=True)
        ttk.Label(frame_map_file, text="Spowoduje to nadpisanie pliku 'mapa.jpg' dla aplikacji.",
                 wraplength=500).pack(pady=(5,0))
        
        # Przyciski akcji
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(button_frame, text="💾 Zapisz Konfigurację",
                  command=self.save_and_update, style="Success.TButton").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(button_frame, text="Anuluj", command=self.destroy).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    def _create_coord_inputs(self, parent):
        """Tworzy pola wprowadzania współrzędnych."""
        ttk.Label(parent, text="Narożnik Południowo-Zachodni (SW):").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(parent, text="Szerokość (Lat):").grid(row=1, column=0, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['sw_lat']).grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(parent, text="Długość (Lng):").grid(row=1, column=2, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['sw_lng']).grid(row=1, column=3, padx=5, pady=2, sticky="ew")
        
        ttk.Label(parent, text="Narożnik Północno-Wschodni (NE):").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(8, 2))
        ttk.Label(parent, text="Szerokość (Lat):").grid(row=3, column=0, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['ne_lat']).grid(row=3, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(parent, text="Długość (Lng):").grid(row=3, column=2, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['ne_lng']).grid(row=3, column=3, padx=5, pady=2, sticky="ew")
        
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)

    def _create_default_view_inputs(self, parent):
        """Tworzy pola dla domyślnego widoku mapy."""
        ttk.Label(parent, text="Centrum mapy:").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(parent, text="Szerokość (Lat):").grid(row=1, column=0, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['center_lat']).grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(parent, text="Długość (Lng):").grid(row=1, column=2, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['center_lng']).grid(row=1, column=3, padx=5, pady=2, sticky="ew")
        
        ttk.Label(parent, text="Domyślny zoom:").grid(row=2, column=0, padx=5, pady=(8, 2), sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['zoom'], width=10).grid(row=2, column=1, sticky=tk.W, padx=5, pady=(8, 2))
        
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)

    def show_instructions(self):
        """Wyświetla instrukcję kalibracji."""
        CalibrationInstructions(self)

    def load_config_from_file(self):
        """Wczytuje konfigurację z pliku JSON."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            cal = config.get('calibration', {})
            defs = config.get('defaults', {})
            
            self.vars['sw_lat'].set(cal.get('sw', {}).get('lat', ''))
            self.vars['sw_lng'].set(cal.get('sw', {}).get('lng', ''))
            self.vars['ne_lat'].set(cal.get('ne', {}).get('lat', ''))
            self.vars['ne_lng'].set(cal.get('ne', {}).get('lng', ''))
            self.vars['center_lat'].set(defs.get('center', {}).get('lat', ''))
            self.vars['center_lng'].set(defs.get('center', {}).get('lng', ''))
            self.vars['zoom'].set(defs.get('zoom', ''))
            
            self.parent_app.log("📍 Wczytano konfigurację mapy z pliku.\n")
        except Exception as e:
            messagebox.showerror("Błąd Pliku", f"Nie można wczytać pliku: {e}", parent=self)
            self.destroy()

    def save_and_update(self):
        """Zapisuje konfigurację do pliku i bazy danych."""
        try:
            new_config = {
                "calibration": {
                    "sw": {"lat": float(self.vars['sw_lat'].get()), "lng": float(self.vars['sw_lng'].get())},
                    "ne": {"lat": float(self.vars['ne_lat'].get()), "lng": float(self.vars['ne_lng'].get())}
                },
                "defaults": {
                    "center": {"lat": float(self.vars['center_lat'].get()), "lng": float(self.vars['center_lng'].get())},
                    "zoom": int(self.vars['zoom'].get())
                }
            }
        except ValueError:
            messagebox.showerror("Błąd Walidacji", "Wszystkie pola muszą zawierać poprawne liczby.", parent=self)
            return
        
        # Zapis do pliku
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4)
            self.parent_app.log(f"📍 Zapisano konfigurację mapy: {self.config_path}\n")
        except Exception as e:
            messagebox.showerror("Błąd Zapisu", f"Nie można zapisać pliku: {e}", parent=self)
            return
        
        # Aktualizacja bazy danych
        conn = None
        try:
            db_config = get_db_config_from_env()
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            
            cur.execute(
                "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES ('map_calibration', %s) "
                "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
                (json.dumps(new_config['calibration']),)
            )
            cur.execute(
                "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES ('map_defaults', %s) "
                "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
                (json.dumps(new_config['defaults']),)
            )
            conn.commit()
            
            self.parent_app.log("📍 Zaktualizowano konfigurację mapy w bazie danych.\n")
            messagebox.showinfo("Sukces", "Konfiguracja mapy została zapisana.", parent=self)
            self.destroy()
        except Exception as e:
            if conn:
                conn.rollback()
            messagebox.showerror("Błąd Bazy", f"Nie można zaktualizować bazy: {e}", parent=self)
        finally:
            if conn:
                conn.close()

    def check_current_map_status(self):
        """Sprawdza status pliku mapy w backup aktywnej miejscowości."""
        location_name = get_active_location_name()

        if not location_name:
            self.map_status_label.config(text="❌ Brak aktywnej miejscowości!", foreground="red")
            self.map_preview_canvas.delete("all")
            self.map_preview_label.config(text="Brak\nmiejscowości")
            self.map_preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            return

        backup_map_path = os.path.join(BASE_DIR, "backup", location_name, "mapa.jpg")
        map_exists = os.path.exists(backup_map_path)

        if map_exists:
            self.map_status_label.config(text=f"✅ Status mapy: OK ({location_name})", foreground="green")
        else:
            self.map_status_label.config(text=f"❌ Brak mapy dla {location_name}", foreground="red")

        # Aktualizacja podglądu
        if map_exists:
            try:
                img = Image.open(backup_map_path)
                w, h = img.size
                ratio = min(200/w, 120/h)
                new_w, new_h = int(w * ratio), int(h * ratio)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                self.map_image_preview = ImageTk.PhotoImage(img)
                self.map_preview_canvas.delete("all")
                self.map_preview_canvas.create_image(100, 60, image=self.map_image_preview)
                self.map_preview_label.place_forget()
            except:
                self.map_preview_canvas.delete("all")
                self.map_preview_label.config(text="Błąd\npodglądu")
                self.map_preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        else:
            self.map_preview_canvas.delete("all")
            self.map_preview_label.config(text="Brak mapy")
            self.map_preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def select_map_file(self):
        """Wybiera i kopiuje plik mapy."""
        filepath = filedialog.askopenfilename(
            title="Wybierz plik mapy tła",
            filetypes=[("Obrazy", "*.jpg *.jpeg *.png"), ("Wszystkie pliki", "*.*")]
        )

        if not filepath:
            return

        # Zapisz mapę tylko do backup aktywnej miejscowości
        location_name = get_active_location_name()
        if not location_name:
            messagebox.showerror("Błąd",
                              "Brak aktywnej miejscowości!\n\n"
                              "Proszę wybrać miejscowość przed dodaniem mapy.",
                              parent=self)
            return

        backup_map_path = os.path.join(BASE_DIR, "backup", location_name, "mapa.jpg")

        try:
            os.makedirs(os.path.dirname(backup_map_path), exist_ok=True)
            shutil.copy(filepath, backup_map_path)

            messagebox.showinfo("Sukces",
                              f"Plik mapy został zapisany dla miejscowości: {location_name}\n\n"
                              "WAŻNE: Upewnij się, że współrzędne odpowiadają nowej mapie!",
                              parent=self)

            self.parent_app.log(f"🗺️ Zapisano mapę do backup/{location_name}/mapa.jpg: {os.path.basename(filepath)}\n")
            self.check_current_map_status()
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się skopiować pliku: {e}", parent=self)

    def center_window(self):
        """Wyśrodkowuje okno względem rodzica."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f'+{x}+{y}')

class CalibrationInstructions(tk.Toplevel):
    """Okno z instrukcją kalibracji mapy."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📘 Instrukcja Kalibracji Mapy")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        
        frame = ttk.Frame(self, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20, width=80, font=("Segoe UI", 10))
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        instruction_text = """
Krok 1: Praca w Programie GIS (np. darmowy QGIS)
==============================================
Georeferencja to proces "przypinania" starej mapy do prawdziwych współrzędnych.

1. Wczytaj warstwy w GIS.
2. Znajdź punkty wspólne (GCP) - użyj co najmniej 10-15 punktów.
3. Wykonaj transformację (warping).
4. Odczytaj współrzędne graniczne z właściwości warstwy GeoTIFF:
   - Południowo-Zachodni narożnik (lewy dolny)
   - Północno-Wschodni narożnik (prawy górny)
5. Eksportuj obraz do JPG/PNG.

Krok 2: Konfiguracja w Launcherze
==================================
1. Podmień plik mapy przyciskiem "Wybierz Plik Mapy...".
2. Wprowadź współrzędne odczytane w kroku 1.
3. Zapisz konfigurację.

Po restarcie serwera mapa będzie używać nowej kalibracji.
"""
        text_widget.insert(tk.END, instruction_text.strip())
        text_widget.config(state="disabled")
        
        ttk.Button(frame, text="Zamknij", command=self.destroy).pack(pady=(10, 0))
        
        # Wyśrodkowanie
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f'+{x}+{y}')

class EnvEditor(tk.Toplevel):
    """Edytor pliku konfiguracyjnego .env."""
    
    def __init__(self, parent, env_path):
        super().__init__(parent)
        self.title("⚙️ Edytor Konfiguracji Bazy Danych")
        self.parent_app = parent
        self.env_path = env_path
        
        self.geometry("700x500")
        self.minsize(600, 420)
        self.center_window()
        
        self.create_widgets()
        self.load_content()

    def create_widgets(self):
        """Tworzy interfejs edytora."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="📝 Edycja pliku konfiguracyjnego .env",
                 font=("Segoe UI", 12, "bold")).pack(pady=(0, 10))
        
        ttk.Label(main_frame,
                 text="Ten plik zawiera konfigurację połączenia z bazą danych PostgreSQL.\n"
                      "Po wprowadzeniu zmian zapisz plik i zrestartuj serwer backend.",
                 wraplength=650, foreground="#666666").pack(pady=(0, 10))
        
        # Edytor tekstu
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.text_editor = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD,
                                                     font=("Consolas", 10), height=15)
        self.text_editor.pack(fill=tk.BOTH, expand=True)
        
        # Przyciski
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="💾 Zapisz zmiany", command=self.save_env,
                  style="Success.TButton").pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="🔄 Przywróć domyślne", command=self.reset_defaults,
                  style="Warning.TButton").pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="❌ Zamknij", command=self.destroy,
                  style="Secondary.TButton").pack(side=tk.RIGHT, padx=5)

    def load_content(self):
        """Wczytuje zawartość pliku .env."""
        try:
            with open(self.env_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.text_editor.insert('1.0', content)
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Nie można wczytać pliku .env:\n{e}", parent=self)
            self.destroy()

    def save_env(self):
        """Zapisuje zmiany do pliku .env."""
        try:
            content = self.text_editor.get('1.0', 'end-1c')
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.parent_app.on_env_changed()
            
            messagebox.showinfo("✅ Sukces",
                              "Konfiguracja została zapisana.\n"
                              "Jeśli zmieniłeś port – pojawi się pytanie o restart serwera.",
                              parent=self)
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Nie można zapisać pliku:\n{e}", parent=self)

    def reset_defaults(self):
        """Przywraca domyślną konfigurację."""
        if messagebox.askyesno("⚠️ Potwierdzenie",
                               "Czy na pewno chcesz przywrócić domyślną konfigurację?",
                               parent=self):
            default_content = """# =============================================================================
# KONFIGURACJA MIEJSCOWOŚCI
# =============================================================================
# Konfiguracja PostgreSQL (host, port, user, password) jest w backend/.postgres.env

# =============================================================================
# BAZA DANYCH - NAZWA BAZY
# =============================================================================
DB_NAME=mapa_czarna_db

# =============================================================================
# KONFIGURACJA FLASK
# =============================================================================
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
FLASK_SECRET_KEY=change-me-once

# =============================================================================
# AUTENTYKACJA ADMINISTRATORA
# =============================================================================
ADMIN_AUTH_ENABLED=0
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=
"""
            self.text_editor.delete('1.0', tk.END)
            self.text_editor.insert('1.0', default_content)

    def center_window(self):
        """Wyśrodkowuje okno."""
        self.update_idletasks()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

class AdminSettings(tk.Toplevel):
    """Okno ustawień administratora."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔐 Ustawienia Administratora")
        self.transient(parent)
        self.grab_set()
        self.parent_app = parent
        
        self.geometry("500x300")
        self.minsize(460, 260)
        self.center_window()
        
        self.load_current_settings()
        self.create_widgets()

    def load_current_settings(self):
        """Wczytuje obecne ustawienia z .env."""
        env_config = read_env_config()
        
        self.enabled = tk.BooleanVar(value=(env_config.get('ADMIN_AUTH_ENABLED', '0') == '1'))
        self.username = tk.StringVar(value=env_config.get('ADMIN_USERNAME', 'admin'))
        self.password = tk.StringVar(value='')
        self.env = env_config

    def create_widgets(self):
        """Tworzy interfejs ustawień."""
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)
        
        ttk.Checkbutton(frm, text="Włącz wymaganie logowania do Panelu Admina",
                       variable=self.enabled).pack(anchor=tk.W, pady=(0,8))
        
        row1 = ttk.Frame(frm)
        row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="Login administratora:", width=22).pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.username).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        row2 = ttk.Frame(frm)
        row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="Nowe hasło (opcjonalnie):", width=22).pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.password, show="•").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(frm, foreground="#6c757d",
                 text="Zostanie zapisane w .env jako hash. Pozostaw puste, by nie zmieniać.",
                 wraplength=480).pack(anchor=tk.W, pady=(6,10), fill=tk.X)
        
        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(10,0))
        
        ttk.Button(btns, text="💾 Zapisz", command=self.save, style="Success.TButton").pack(side=tk.RIGHT)
        ttk.Button(btns, text="Anuluj", command=self.destroy, style="Secondary.TButton").pack(side=tk.RIGHT, padx=(0,8))

    def save(self):
        """Zapisuje ustawienia administratora."""
        try:
            from werkzeug.security import generate_password_hash
        except:
            messagebox.showerror("Brak zależności", "Brakuje pakietu Werkzeug.", parent=self)
            return
        
        if not self.username.get().strip():
            messagebox.showwarning("Walidacja", "Login nie może być pusty.", parent=self)
            return
        
        old_auth = self.env.get('ADMIN_AUTH_ENABLED', '0')
        
        self.env['ADMIN_AUTH_ENABLED'] = '1' if self.enabled.get() else '0'
        self.env['ADMIN_USERNAME'] = self.username.get().strip()
        
        if self.password.get():
            try:
                self.env['ADMIN_PASSWORD_HASH'] = generate_password_hash(self.password.get())
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie udało się utworzyć hasha: {e}", parent=self)
                return
        
        self.env.setdefault('FLASK_SECRET_KEY', 'change-me-' + str(os.getpid()))

        # Zapisz .env do aktywnej miejscowości
        try:
            env_path = get_location_env_path()
        except ValueError:
            messagebox.showerror("❌ Błąd", "Brak aktywnej miejscowości", parent=self)
            return

        self._save_env_file(env_path)
        
        self.parent_app.on_env_changed()
        
        # Auto-restart przy zmianie autoryzacji
        new_auth = self.env['ADMIN_AUTH_ENABLED']
        
        if old_auth != new_auth and "backend" in self.parent_app.managed_processes:
            was_network = self.parent_app.managed_processes["backend"].get("network_mode", False)
            
            messagebox.showinfo("🔄 Restart serwera",
                              f"{'Włączono' if new_auth == '1' else 'Wyłączono'} autoryzację admina.\n\n"
                              "Serwer backend zostanie automatycznie zrestartowany.",
                              parent=self)
            self.destroy()
            
            self.parent_app.log(f"\n{'='*60}\n")
            self.parent_app.log(f"🔄 Restartowanie serwera - zmiana ustawień autoryzacji...\n")
            self.parent_app.log(f"   • Autoryzacja: {'WŁĄCZONA ✅' if new_auth == '1' else 'WYŁĄCZONA ❌'}\n")
            if new_auth == '1':
                self.parent_app.log(f"   • Login: {self.env['ADMIN_USERNAME']}\n")
            self.parent_app.log(f"{'='*60}\n\n")
            
            self.parent_app.stop_managed_process("backend")
            
            def restart():
                if was_network:
                    self.parent_app.start_network_server()
                else:
                    self.parent_app.start_managed_process("backend", "Serwer Backend (Lokalny)")
                    self.parent_app.server_btn.config(text="⏹️ Zatrzymaj Serwer (Lokalny)", style="Danger.TButton")
            
            self.parent_app.after(800, restart)
        else:
            messagebox.showinfo("✅ Zapisano", "Ustawienia administratora zapisane.", parent=self)
            self.destroy()

    def _save_env_file(self, env_path):
        """Zapisuje plik .env z ładnym, jednolitym formatem."""
        # Pobierz wartości
        db_name = self.env.get('DB_NAME', 'mapa_czarna_db')
        flask_host = self.env.get('FLASK_HOST', '127.0.0.1')
        flask_port = self.env.get('FLASK_PORT', '5000')
        flask_debug = self.env.get('FLASK_DEBUG', 'True')
        flask_secret = self.env.get('FLASK_SECRET_KEY', 'change-me-once')
        admin_enabled = self.env.get('ADMIN_AUTH_ENABLED', '0')
        admin_user = self.env.get('ADMIN_USERNAME', 'admin')
        admin_hash = self.env.get('ADMIN_PASSWORD_HASH', '')
        location_name = self.env.get('LOCATION_NAME', '')
        location_code = self.env.get('LOCATION_CODE', '')

        # Jednolity szablon
        content = f"""# =============================================================================
# KONFIGURACJA MIEJSCOWOŚCI
# =============================================================================
# Konfiguracja PostgreSQL (host, port, user, password) jest w backend/.postgres.env

# =============================================================================
# BAZA DANYCH
# =============================================================================
DB_NAME={db_name}

# =============================================================================
# SERWER FLASK
# =============================================================================
FLASK_HOST={flask_host}
FLASK_PORT={flask_port}
FLASK_DEBUG={flask_debug}
FLASK_SECRET_KEY={flask_secret}

# =============================================================================
# AUTENTYKACJA ADMINISTRATORA
# =============================================================================
ADMIN_AUTH_ENABLED={admin_enabled}
ADMIN_USERNAME={admin_user}
ADMIN_PASSWORD_HASH={admin_hash}
"""

        # Dodaj sekcję miejscowości jeśli istnieje
        if location_name:
            content += f"""
# =============================================================================
# INFORMACJE O MIEJSCOWOŚCI
# =============================================================================
LOCATION_NAME={location_name}
LOCATION_CODE={location_code}
"""

        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def center_window(self):
        """Wyśrodkowuje okno."""
        self.update_idletasks()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        x = px + (pw - 500) // 2
        y = py + (ph - 300) // 2
        self.geometry(f"+{x}+{y}")

class FirewallInstructions(tk.Toplevel):
    """Okno z instrukcjami konfiguracji firewall."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📋 Instrukcja konfiguracji Firewall")
        self.geometry("600x500")
        self.transient(parent)
        
        flask_config = get_flask_config()
        port = int(flask_config['port'])
        
        frame = ttk.Frame(self, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True)
        
        content = f"""INSTRUKCJA RĘCZNEJ KONFIGURACJI FIREWALL WINDOWS
================================================

METODA 1 - Przez interfejs graficzny:
-------------------------------------
1. Naciśnij Win + R
2. Wpisz: wf.msc
3. Kliknij "Reguły przychodzące" → "Nowa reguła..."
4. Wybierz "Port" → TCP → "{port}" → "Zezwalaj"
5. Nazwa: "Flask Server Port {port}"

METODA 2 - PowerShell (jako Administrator):
-----------------------------------------
New-NetFirewallRule -DisplayName "Flask Server Port {port}" -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow

METODA 3 - Wiersz poleceń (jako Administrator):
--------------------------------------------
netsh advfirewall firewall add rule name="Flask Server Port {port}" dir=in action=allow protocol=TCP localport={port}

TESTOWANIE:
-----------
1. Uruchom serwer sieciowy
2. Na innym urządzeniu wpisz adres IP:{port}
3. Jeśli strona się ładuje - wszystko działa!
"""
        
        text.insert("1.0", content)
        text.config(state="disabled")
        
        ttk.Button(frame, text="Zamknij", command=self.destroy,
                  style="Primary.TButton").pack(pady=10)

class NetworkInfoDialog(tk.Toplevel):
    """Okno z informacjami o dostępie sieciowym."""
    
    def __init__(self, parent, local_ip):
        super().__init__(parent)
        self.title("Informacje o Dostępie Sieciowym")
        self.transient(parent)
        self.grab_set()
        
        self.parent_app = parent
        parent._net_info_win = self
        
        flask_config = get_flask_config()
        port = flask_config['port']
        
        w, h = 600, 400
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.resizable(False, False)
        
        self.create_widgets(local_ip, port)

    def create_widgets(self, local_ip, port):
        """Tworzy interfejs z informacjami."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="✅ Serwer uruchomiony w trybie sieciowym!",
                 font=("Segoe UI", 14, "bold"),
                 foreground=COLORS['success']).pack(pady=(0, 20))
        
        # Adresy dostępu
        info_frame = ttk.LabelFrame(main_frame, text="📡 Adresy dostępu", padding="15")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        addresses = [
            ("Ten komputer:", f"http://127.0.0.1:{port}"),
            ("Inne urządzenia w sieci:", f"http://{local_ip}:{port}"),
            ("Alternatywny adres:", f"http://{socket.gethostname()}:{port}"),
        ]
        
        for label, address in addresses:
            addr_frame = ttk.Frame(info_frame)
            addr_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(addr_frame, text=label, width=25).pack(side=tk.LEFT)
            
            addr_entry = ttk.Entry(addr_frame, width=40)
            addr_entry.insert(0, address)
            addr_entry.config(state="readonly")
            addr_entry.pack(side=tk.LEFT, padx=10)
            
            def copy_addr(addr=address):
                self.clipboard_clear()
                self.clipboard_append(addr)
                messagebox.showinfo("✅ Skopiowano", f"Adres został skopiowany:\n{addr}", parent=self)
            
            ttk.Button(addr_frame, text="📋 Kopiuj", command=copy_addr, width=10).pack(side=tk.LEFT)
        
        # Komenda PowerShell
        ps_frame = ttk.LabelFrame(main_frame, text="⚡ Konfiguracja Firewall (PowerShell)", padding="15")
        ps_frame.pack(fill=tk.X, pady=10)
        
        ps_command = f'New-NetFirewallRule -DisplayName "CzarnaMapa" -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow -Profile Any'
        
        ps_entry = ttk.Entry(ps_frame, width=80)
        ps_entry.insert(0, ps_command)
        ps_entry.config(state="readonly")
        ps_entry.pack(side=tk.LEFT, padx=(0,10), fill=tk.X, expand=True)
        
        def copy_ps():
            self.clipboard_clear()
            self.clipboard_append(ps_command)
            messagebox.showinfo("✅ Skopiowano", "Komenda PowerShell została skopiowana.\nUruchom PowerShell jako Administrator i wklej komendę.", parent=self)
        
        ttk.Button(ps_frame, text="📋 Kopiuj", command=copy_ps, style="Primary.TButton").pack(side=tk.LEFT)
        
        # Instrukcja
        instr_row = ttk.Frame(main_frame)
        instr_row.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(instr_row, text="ℹ️").pack(side=tk.LEFT, padx=(0, 8))
        
        ttk.Button(instr_row, text="📘 Pokaż instrukcję (firewall / port 5000)",
                  command=self.open_network_instructions_centered,
                  style="Primary.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        
        ttk.Button(main_frame, text="OK, rozumiem", command=self.destroy,
                  style="Primary.TButton").pack(pady=10)
        
        # Dostosowanie rozmiaru
        self.update_idletasks()
        req_w = self.winfo_reqwidth()
        req_h = self.winfo_reqheight()
        self.geometry(f"{req_w}x{req_h}")
        self.minsize(req_w, req_h)

    def open_network_instructions_centered(self):
        """Otwiera wyskakujące okno z instrukcją dostępu sieciowego."""
        parent = getattr(self, "_net_info_win", self)
        
        win = tk.Toplevel(parent)
        win.title("Instrukcja – dostęp sieciowy / port 5000")
        win.resizable(False, False)
        win.transient(parent)
        win.grab_set()
        
        body = ttk.Frame(win, padding=14)
        body.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(body, text="Jak udostępnić aplikację w sieci lokalnej:",
                 font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 6))
        
        ttk.Label(body, justify=tk.LEFT, text=(
            "1) Upewnij się, że serwer działa (zielony status w oknie sieciowym).\n"
            "2) Komputer-serwer i urządzenie-klient muszą być w tej samej sieci Wi-Fi/LAN.\n"
            "3) Na innym urządzeniu wpisz adres IP z listy (np. http://192.168.x.x:5000).\n"
            "4) Jeśli nie działa – dodaj regułę Zapory Windows: TCP 5000, wszystkie profile.\n"
            "5) Sprawdzenie nasłuchu:\n"
            "   • PowerShell: Get-NetTCPConnection -LocalPort 5000\n"
            "   • CMD:       netstat -ano | findstr :5000\n"
        )).pack(anchor=tk.W)
        
        ttk.Button(body, text="Zamknij", command=win.destroy,
                  style="Secondary.TButton").pack(anchor=tk.E, pady=(10, 0))
        
        # Wyśrodkowanie
        parent.update_idletasks()
        win.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")
        win.focus_set()

class InstructionsWindow(tk.Toplevel):
    """Okno z instrukcjami dostępu sieciowego."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Instrukcja – dostęp sieciowy")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        body = ttk.Frame(self, padding=14)
        body.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(body, text="Jak udostępnić aplikację w sieci lokalnej:",
                 font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 6))
        
        ttk.Label(body, justify=tk.LEFT, text=(
            "1) Upewnij się, że serwer działa (zielony status).\n"
            "2) Komputer i urządzenie muszą być w tej samej sieci.\n"
            "3) Na innym urządzeniu wpisz adres IP z listy.\n"
            "4) Jeśli nie działa – dodaj regułę Zapory Windows.\n"
            "5) Sprawdzenie nasłuchu:\n"
            "   • PowerShell: Get-NetTCPConnection -LocalPort 5000\n"
            "   • CMD: netstat -ano | findstr :5000\n"
        )).pack(anchor=tk.W)
        
        ttk.Button(body, text="Zamknij", command=self.destroy,
                  style="Secondary.TButton").pack(anchor=tk.E, pady=(10, 0))
        
        # Wyśrodkowanie
        parent.update_idletasks()
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        self.focus_set()

def create_and_migrate_location_database(location_name, progress_callback=None):
    """
    Tworzy bazę danych dla miejscowości i migruje dane z backup/.

    Args:
        location_name: Nazwa miejscowości (np. "Borowa")
        progress_callback: Funkcja callback do raportowania postępu

    Returns:
        (success: bool, message: str)
    """
    try:
        # Pobierz konfigurację PostgreSQL
        config = get_postgres_config()
        if not config:
            return False, "Brak konfiguracji PostgreSQL"

        # Określ nazwę bazy danych
        db_name = f"mapa_{location_name.lower()}"

        if progress_callback:
            progress_callback(f"📊 Tworzenie bazy danych: {db_name}")

        # 1. Utwórz bazę danych (jeśli nie istnieje)
        success, msg = postgres_create_database(
            config['host'], config['port'], config['user'], config['password'], db_name
        )
        if not success:
            return False, f"Błąd tworzenia bazy: {msg}"

        print(f"✅ {msg}")

        # 2. Włącz PostGIS
        if progress_callback:
            progress_callback(f"🗺️ Włączanie PostGIS w bazie {db_name}")

        success, msg = postgres_enable_postgis(
            config['host'], config['port'], config['user'], config['password'], db_name
        )
        if not success:
            print(f"⚠️ Ostrzeżenie PostGIS: {msg}")
        else:
            print(f"✅ {msg}")

        # 3. Utwórz schemat tabel
        if progress_callback:
            progress_callback(f"📋 Tworzenie tabel w bazie {db_name}")

        success, msg = postgres_execute_schema(
            config['host'], config['port'], config['user'], config['password'],
            db_name, LOCATION_DB_SCHEMA
        )
        if not success:
            return False, f"Błąd tworzenia tabel: {msg}"

        print(f"✅ {msg}")

        # 4. Zaktualizuj nazwę bazy danych w tabeli locations
        if progress_callback:
            progress_callback(f"💾 Zapisywanie nazwy bazy w konfiguracji")

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

        # 5. Zaktualizuj .env dla miejscowości
        location_folder = os.path.join(BACKUP_FOLDER, location_name)
        env_path = os.path.join(location_folder, ".env")

        if os.path.exists(location_folder):
            # Utwórz/zaktualizuj plik .env
            env_content = f"""DB_HOST={config['host']}
DB_PORT={config['port']}
DB_NAME={db_name}
DB_USER={config['user']}
DB_PASSWORD={config['password']}
"""
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(env_content)
            print(f"✅ Zaktualizowano .env dla {location_name}")

        # 6. Wywołaj migrację danych
        if progress_callback:
            progress_callback(f"🔄 Migracja danych z backup/{location_name}")

        print(f"🔄 Migracja danych dla miejscowości: {location_name}")
        auto_migrate_data_function(location_folder, location_name)

        # 7. Automatyczna kalibracja mapy z map_config.json
        if progress_callback:
            progress_callback(f"📍 Kalibracja mapy z map_config.json")

        auto_calibrate_map_from_backup(location_name=location_name, db_name=db_name)

        return True, f"Baza {db_name} utworzona i dane zmigrowane pomyślnie"

    except Exception as e:
        return False, f"Błąd: {str(e)}"


class BackupManager(tk.Toplevel):
    """Okno dialogowe do zarządzania kopiami zapasowymi projektu."""

    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("💾 Uniwersalny Menedżer Kopii Zapasowych")
        
        # Automatyczne dostosowanie do ekranu
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        dpi = self.winfo_fpixels("1i")
        scale_factor = dpi / 96
        
        if sw <= 1920:
            w, h = min(int(sw * 0.75), 1100), min(int(sh * 0.80), 700)
        else:
            w, h = min(int(sw * 0.60), 1200), min(int(sh * 0.75), 800)
        
        if scale_factor > 1.25:
            w = int(w / scale_factor * 1.3)
            h = int(h / scale_factor * 1.3)
        
        x = (sw - w) // 2
        y = (sh - h) // 2
        
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(800, 600)
        self.grab_set()
        
        # Konfiguracja stylów
        base_size = 10 if scale_factor <= 1.25 else (11 if scale_factor <= 1.5 else 12)
        self.base_font_size = base_size
        
        self.style = ttk.Style(self)
        row_height = int(base_size * 2.5)
        self.style.configure("Treeview", rowheight=row_height, font=("Segoe UI", base_size))
        self.style.configure("Treeview.Heading", font=("Segoe UI", base_size, "bold"))
        
        self.create_widgets()
        self.populate_backup_list()

    def create_widgets(self):
        """Tworzy interfejs menedżera kopii."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Sekcja tworzenia kopii
        create_frame = ttk.LabelFrame(main_frame, text="➕ Stwórz Nową Kopię Zapasową", padding="10")
        create_frame.pack(fill=tk.X, pady=(0, 10))

        # Wybór miejscowości
        location_select_frame = ttk.Frame(create_frame)
        location_select_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(location_select_frame, text="Miejscowość do skopiowania:").pack(side=tk.LEFT, padx=5)

        self.location_backup_var = tk.StringVar(value="Aktywna miejscowość")
        self.location_backup_combo = ttk.Combobox(location_select_frame, textvariable=self.location_backup_var,
                                                  state="readonly", width=30)
        self.location_backup_combo.pack(side=tk.LEFT, padx=5)

        # Wypełnij listę miejscowości
        locations = get_all_locations()
        location_choices = ["Aktywna miejscowość", "Wszystkie miejscowości"] + [loc[1] for loc in locations]
        self.location_backup_combo['values'] = location_choices

        # Checkboxy
        self.backup_vars = {key: tk.BooleanVar(value=True) for key in DATA_FILES}
        self.backup_vars["scans"] = tk.BooleanVar(value=True)
        self.backup_vars["config"] = tk.BooleanVar(value=True)
        self.backup_vars["launcher_db"] = tk.BooleanVar(value=True)

        content_frame = ttk.Frame(create_frame)
        content_frame.pack(fill=tk.X)

        checkbox_frame = ttk.Frame(content_frame)
        checkbox_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        col1 = ttk.Frame(checkbox_frame)
        col1.pack(side=tk.LEFT, padx=10)

        checkboxes = [
            ("📋 Właściciele i Demografia", "owners"),
            ("🗺️ Działki (geometria)", "parcels"),
            ("📍 Konfiguracja Mapy", "config")
        ]

        for text, var_key in checkboxes:
            ttk.Checkbutton(col1, text=text, variable=self.backup_vars[var_key]).pack(anchor="w", pady=2)

        col2 = ttk.Frame(checkbox_frame)
        col2.pack(side=tk.LEFT, padx=10)

        ttk.Checkbutton(col2, text="🌳 Genealogia", variable=self.backup_vars["genealogy"]).pack(anchor="w", pady=2)
        ttk.Checkbutton(col2, text="📄 Skany Protokołów", variable=self.backup_vars["scans"]).pack(anchor="w", pady=2)
        ttk.Checkbutton(col2, text="🗄️ Baza Launcher (konfiguracja stron)", variable=self.backup_vars["launcher_db"]).pack(anchor="w", pady=2)

        ttk.Button(content_frame, text="🎯 Stwórz Kopię ZIP", command=self.create_backup,
                  style="Success.TButton").pack(side=tk.RIGHT, padx=10)
        
        # Sekcja zarządzania kopiami
        restore_frame = ttk.LabelFrame(main_frame, text="📦 Istniejące Kopie Zapasowe", padding="10")
        restore_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Tabela kopii
        self.tree = ttk.Treeview(restore_frame, columns=("filename",), show="headings")
        self.tree.heading("filename", text="📁 Nazwa Pliku (od najnowszej)")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        
        # Pasek akcji
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.selected_label = ttk.Label(action_frame, text="📭 Nic nie zaznaczono",
                                       foreground=COLORS['secondary'],
                                       font=("Segoe UI", self.base_font_size))
        self.selected_label.pack(side=tk.LEFT, padx=5)
        
        buttons_frame = ttk.Frame(action_frame)
        buttons_frame.pack(side=tk.RIGHT)
        
        self.delete_btn = ttk.Button(buttons_frame, text="🗑️ Usuń", style="Danger.TButton",
                                     command=self.delete_backup, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.LEFT, padx=2)
        
        self.restore_btn = ttk.Button(buttons_frame, text="♻️ Przywróć", command=self.restore_backup,
                                      state=tk.DISABLED, style="Warning.TButton")
        self.restore_btn.pack(side=tk.LEFT, padx=2)
        
        self.export_btn = ttk.Button(buttons_frame, text="📤 Eksportuj", command=self.export_backup,
                                     state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=2)
        
        self.import_btn = ttk.Button(buttons_frame, text="📥 Importuj z dysku",
                                     command=self.import_backup, style="Primary.TButton")
        self.import_btn.pack(side=tk.LEFT, padx=2)

    def populate_backup_list(self):
        """Wczytuje listę plików kopii zapasowych."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            files = [f for f in os.listdir(BACKUP_FOLDER)
                    if f.startswith("backup_") and f.endswith(".zip")]
            # Dodaj również stare kopie dla kompatybilności wstecznej
            old_backups = [f for f in os.listdir(BACKUP_FOLDER)
                          if f.startswith("pelny_backup_projektu_") and f.endswith(".zip")]
            files.extend(old_backups)
            files.sort(reverse=True)

            for filename in files:
                self.tree.insert("", "end", iid=filename, values=(filename,))
        except FileNotFoundError:
            pass

        self.on_select()

    def on_select(self, event=None):
        """Aktualizuje stan przycisków w zależności od zaznaczenia."""
        selected = self.tree.selection()
        
        if selected:
            self.selected_backup_file = selected[0]
            display_name = self.selected_backup_file[:37] + "..." if len(self.selected_backup_file) > 40 else self.selected_backup_file
            self.selected_label.config(text=f"📂 {display_name}", foreground=COLORS['primary'])
            
            for btn in [self.restore_btn, self.delete_btn, self.export_btn]:
                btn.config(state=tk.NORMAL)
        else:
            self.selected_backup_file = None
            self.selected_label.config(text="📭 Nic nie zaznaczono", foreground=COLORS['secondary'])
            
            for btn in [self.restore_btn, self.delete_btn, self.export_btn]:
                btn.config(state=tk.DISABLED)

    def export_backup(self):
        """Eksportuje zaznaczoną kopię zapasową."""
        if not self.selected_backup_file:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Najpierw zaznacz plik.", parent=self)
            return
        
        source_path = os.path.join(BACKUP_FOLDER, self.selected_backup_file)
        destination_path = filedialog.asksaveasfilename(
            initialfile=self.selected_backup_file, defaultextension=".zip",
            filetypes=[("Archiwum ZIP", "*.zip")], title="Wybierz, gdzie zapisać"
        )
        
        if destination_path:
            try:
                shutil.copy2(source_path, destination_path)
                messagebox.showinfo("✅ Sukces", "Kopia zapasowa została wyeksportowana.", parent=self)
            except Exception as e:
                messagebox.showerror("❌ Błąd", f"Nie udało się zapisać:\n{e}", parent=self)

    def import_backup(self):
        """Importuje kopię zapasową z zewnętrznej lokalizacji."""
        source_path = filedialog.askopenfilename(
            filetypes=[("Archiwum ZIP", "*.zip")], title="Wybierz plik kopii zapasowej"
        )
        
        if not source_path:
            return
        
        filename = os.path.basename(source_path)
        destination_path = os.path.join(BACKUP_FOLDER, filename)
        
        if os.path.exists(destination_path):
            if not messagebox.askyesno("⚠️ Plik istnieje", f"Plik '{filename}' już istnieje.\nNadpisać?", parent=self):
                return
        
        try:
            shutil.copy2(source_path, destination_path)
            messagebox.showinfo("✅ Sukces", f"Plik '{filename}' został zaimportowany.", parent=self)
            self.populate_backup_list()
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Nie udało się skopiować:\n{e}", parent=self)

    def create_backup(self):
        """Tworzy nową kopię zapasową."""
        components = [key for key, var in self.backup_vars.items() if var.get()]

        if not components:
            messagebox.showwarning("⚠️ Nic nie wybrano", "Zaznacz co najmniej jeden element.", parent=self)
            return

        ProgressDialog(self, self._perform_backup, components)

    def _perform_backup(self, progress_callback, components):
        """Wykonuje tworzenie kopii zapasowej."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        location_choice = self.location_backup_var.get()

        # Określ jakie miejscowości kopiować
        locations_to_backup = []
        if location_choice == "Aktywna miejscowość":
            active_loc = get_active_location()
            if active_loc:
                locations_to_backup = [active_loc[1]]  # nazwa miejscowości
            backup_filename = f"backup_{timestamp}.zip"
        elif location_choice == "Wszystkie miejscowości":
            all_locs = get_all_locations()
            locations_to_backup = [loc[1] for loc in all_locs]
            backup_filename = f"backup_wszystkie_{timestamp}.zip"
        else:
            # Konkretna miejscowość
            locations_to_backup = [location_choice]
            backup_filename = f"backup_{location_choice}_{timestamp}.zip"

        if not locations_to_backup:
            raise Exception("Brak miejscowości do skopiowania")

        backup_path = os.path.join(BACKUP_FOLDER, backup_filename)

        files_to_zip = []

        # Zbieranie plików dla każdej miejscowości
        for location_name in locations_to_backup:
            location_folder = os.path.join(BACKUP_FOLDER, location_name)

            if not os.path.exists(location_folder):
                continue

            # Dodaj plik .env
            env_path = os.path.join(location_folder, ".env")
            if os.path.exists(env_path):
                arcname = os.path.join(location_name, ".env")
                files_to_zip.append((env_path, arcname))

            # Zbieranie plików danych
            data_files_for_location = get_data_files(location_name)

            if self.backup_vars["config"].get():
                map_config_path = os.path.join(location_folder, "map_config.json")
                if os.path.exists(map_config_path):
                    arcname = os.path.join(location_name, "map_config.json")
                    files_to_zip.append((map_config_path, arcname))

            for key in ["owners", "parcels", "genealogy"]:
                if self.backup_vars[key].get():
                    file_path = data_files_for_location[key]["path"]
                    if os.path.exists(file_path):
                        arcname = os.path.join(location_name, os.path.basename(file_path))
                        files_to_zip.append((file_path, arcname))
                    for related_path in data_files_for_location[key].get("related", []):
                        if os.path.exists(related_path):
                            arcname = os.path.join(location_name, os.path.basename(related_path))
                            files_to_zip.append((related_path, arcname))

        # Skany protokołów (wspólne dla wszystkich miejscowości)
        if self.backup_vars["scans"].get() and os.path.exists(PROTOKOLY_FOLDER):
            for root, _, files in os.walk(PROTOKOLY_FOLDER):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, BASE_DIR)
                    files_to_zip.append((file_path, arcname))

        # Eksport danych z bazy launcher (tabele konfiguracyjne stron)
        if self.backup_vars["launcher_db"].get():
            try:
                db_cfg = get_db_config_from_env()
                # Połącz się z bazą launcher
                launcher_db_cfg = db_cfg.copy()
                launcher_db_cfg['dbname'] = 'mapa_launcher_db'
                launcher_db_cfg['client_encoding'] = 'UTF8'

                with psycopg2.connect(**launcher_db_cfg) as conn, conn.cursor() as cur:
                    # Eksportuj dane dla każdej miejscowości
                    for location_name in locations_to_backup:
                        # Pobierz rekord miejscowości
                        cur.execute("""
                            SELECT id, name, full_name, powiat, region, active,
                                   homepage_template, year, century, homepage_description,
                                   history_paragraph1, history_paragraph2, history_paragraph3,
                                   postgres_db_name, created_at, updated_at
                            FROM locations
                            WHERE name = %s
                        """, (location_name,))

                        location_row = cur.fetchone()
                        if location_row:
                            location_data = {
                                "id": location_row[0],
                                "name": location_row[1],
                                "full_name": location_row[2],
                                "powiat": location_row[3],
                                "region": location_row[4],
                                "active": location_row[5],
                                "homepage_template": location_row[6],
                                "year": location_row[7],
                                "century": location_row[8],
                                "homepage_description": location_row[9],
                                "history_paragraph1": location_row[10],
                                "history_paragraph2": location_row[11],
                                "history_paragraph3": location_row[12],
                                "postgres_db_name": location_row[13],
                                "created_at": str(location_row[14]) if location_row[14] else None,
                                "updated_at": str(location_row[15]) if location_row[15] else None
                            }

                            # Pobierz zdjęcia historyczne dla tej miejscowości
                            cur.execute("""
                                SELECT id, filename, caption, order_index, created_at
                                FROM history_photos
                                WHERE location_id = %s
                                ORDER BY order_index
                            """, (location_row[0],))

                            photos = []
                            for photo_row in cur.fetchall():
                                photos.append({
                                    "id": photo_row[0],
                                    "filename": photo_row[1],
                                    "caption": photo_row[2],
                                    "order_index": photo_row[3],
                                    "created_at": str(photo_row[4]) if photo_row[4] else None
                                })

                            location_data["history_photos"] = photos

                            # Zapisz do pliku JSON
                            temp_json_path = os.path.join(BACKUP_FOLDER, f"_temp_launcher_db_{location_name}.json")
                            with open(temp_json_path, 'w', encoding='utf-8') as f:
                                json.dump(location_data, f, ensure_ascii=False, indent=2)

                            # Dodaj do archiwum
                            arcname = os.path.join(location_name, "launcher_db_config.json")
                            files_to_zip.append((temp_json_path, arcname))
            except Exception as e:
                print(f"⚠️ Nie udało się wyeksportować danych z bazy launcher: {e}")

        # Tworzenie archiwum
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, (file_path, arcname) in enumerate(files_to_zip):
                progress_callback(i + 1, len(files_to_zip), f"Pakowanie: {os.path.basename(arcname)}")
                zf.write(file_path, arcname)

        # Usuń pliki tymczasowe launcher_db
        if self.backup_vars["launcher_db"].get():
            for location_name in locations_to_backup:
                temp_json_path = os.path.join(BACKUP_FOLDER, f"_temp_launcher_db_{location_name}.json")
                if os.path.exists(temp_json_path):
                    try:
                        os.remove(temp_json_path)
                    except:
                        pass

        return backup_filename

    def delete_backup(self):
        """Usuwa zaznaczony plik kopii zapasowej."""
        if not hasattr(self, "selected_backup_file") or not self.selected_backup_file:
            return
        
        if messagebox.askyesno("🗑️ Potwierdzenie", f"Czy na pewno usunąć:\n\n{self.selected_backup_file}?",
                               parent=self, icon="warning"):
            backup_path = os.path.join(BACKUP_FOLDER, self.selected_backup_file)
            try:
                os.remove(backup_path)
                messagebox.showinfo("✅ Sukces", f"Usunięto: {self.selected_backup_file}", parent=self)
                self.populate_backup_list()
            except Exception as e:
                messagebox.showerror("❌ Błąd", f"Nie udało się usunąć:\n{e}", parent=self)

    def restore_backup(self):
        """Przywraca dane z wybranej kopii zapasowej."""
        selected = self.tree.selection()
        if not selected:
            return

        filename = selected[0]

        msg = (f"⚠️ UWAGA! Ta operacja jest NIEODWRACALNA.\n\n"
               f"Czy na pewno przywrócić dane z:\n'{filename}'?\n\n"
               "Spowoduje to:\n"
               "• NADPISANIE wszystkich istniejących danych\n"
               "• ZASTĄPIENIE folderu ze skanami\n"
               "• UTRATĘ wszystkich niezapisanych zmian")

        if not messagebox.askyesno("⚠️ POTWIERDZENIE KRYTYCZNEJ OPERACJI", msg, icon="warning", parent=self):
            return

        backup_path = os.path.join(BACKUP_FOLDER, filename)

        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                archive_contents = zf.namelist()

                # Sprawdź czy to nowy format (z folderami miejscowości) czy stary
                has_location_folders = any('/' in f and not f.startswith('assets/') for f in archive_contents)

                # Lista przywróconych miejscowości (do późniejszej migracji)
                restored_locations = []

                # Przywracanie skanów
                scan_files = [f for f in archive_contents if f.startswith("assets/protokoly/")]
                if scan_files:
                    if os.path.exists(PROTOKOLY_FOLDER):
                        shutil.rmtree(PROTOKOLY_FOLDER)
                    for file_info in zf.infolist():
                        if file_info.filename.startswith("assets/protokoly/"):
                            zf.extract(file_info, path=BASE_DIR)

                if has_location_folders:
                    # Nowy format - wyodrębnij bezpośrednio do backup/
                    # Struktura w ZIP: {miejscowość}/*.json
                    for file_info in zf.infolist():
                        if not file_info.filename.startswith('assets/'):
                            # Wyodrębnij pliki miejscowości zachowując strukturę folderów
                            zf.extract(file_info, path=BACKUP_FOLDER)

                    # Przywróć dane z bazy launcher (jeśli istnieją)
                    launcher_db_files = [f for f in archive_contents if f.endswith('launcher_db_config.json')]
                    if launcher_db_files:
                        try:
                            db_cfg = get_db_config_from_env()
                            launcher_db_cfg = db_cfg.copy()
                            launcher_db_cfg['dbname'] = 'mapa_launcher_db'
                            launcher_db_cfg['client_encoding'] = 'UTF8'

                            with psycopg2.connect(**launcher_db_cfg) as conn, conn.cursor() as cur:
                                for launcher_file in launcher_db_files:
                                    # Odczytaj plik JSON z archiwum
                                    with zf.open(launcher_file) as json_file:
                                        location_data = json.load(json_file)

                                    # Sprawdź czy miejscowość istnieje
                                    cur.execute("SELECT id FROM locations WHERE name = %s", (location_data['name'],))
                                    existing = cur.fetchone()

                                    if existing:
                                        # Aktualizuj istniejącą miejscowość
                                        location_id = existing[0]
                                        cur.execute("""
                                            UPDATE locations SET
                                                full_name = %s,
                                                powiat = %s,
                                                region = %s,
                                                homepage_template = %s,
                                                year = %s,
                                                century = %s,
                                                homepage_description = %s,
                                                history_paragraph1 = %s,
                                                history_paragraph2 = %s,
                                                history_paragraph3 = %s,
                                                postgres_db_name = %s
                                            WHERE id = %s
                                        """, (
                                            location_data.get('full_name'),
                                            location_data.get('powiat'),
                                            location_data.get('region'),
                                            location_data.get('homepage_template'),
                                            location_data.get('year'),
                                            location_data.get('century'),
                                            location_data.get('homepage_description'),
                                            location_data.get('history_paragraph1'),
                                            location_data.get('history_paragraph2'),
                                            location_data.get('history_paragraph3'),
                                            location_data.get('postgres_db_name'),
                                            location_id
                                        ))
                                    else:
                                        # Wstaw nową miejscowość
                                        cur.execute("""
                                            INSERT INTO locations (
                                                name, full_name, powiat, region,
                                                homepage_template, year, century, homepage_description,
                                                history_paragraph1, history_paragraph2, history_paragraph3,
                                                postgres_db_name
                                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            RETURNING id
                                        """, (
                                            location_data['name'],
                                            location_data.get('full_name'),
                                            location_data.get('powiat'),
                                            location_data.get('region'),
                                            location_data.get('homepage_template'),
                                            location_data.get('year'),
                                            location_data.get('century'),
                                            location_data.get('homepage_description'),
                                            location_data.get('history_paragraph1'),
                                            location_data.get('history_paragraph2'),
                                            location_data.get('history_paragraph3'),
                                            location_data.get('postgres_db_name')
                                        ))
                                        location_id = cur.fetchone()[0]

                                    # Usuń stare zdjęcia
                                    cur.execute("DELETE FROM history_photos WHERE location_id = %s", (location_id,))

                                    # Wstaw zdjęcia historyczne
                                    for photo in location_data.get('history_photos', []):
                                        cur.execute("""
                                            INSERT INTO history_photos (location_id, filename, caption, order_index)
                                            VALUES (%s, %s, %s, %s)
                                        """, (
                                            location_id,
                                            photo['filename'],
                                            photo.get('caption'),
                                            photo.get('order_index', 0)
                                        ))

                                conn.commit()
                                print(f"✅ Przywrócono dane launcher dla {len(launcher_db_files)} miejscowości")

                                # Dodaj przywrócone miejscowości do listy
                                for launcher_file in launcher_db_files:
                                    with zf.open(launcher_file) as json_file:
                                        location_data = json.load(json_file)
                                    restored_locations.append(location_data['name'])

                        except Exception as e:
                            print(f"⚠️ Nie udało się przywrócić danych z bazy launcher: {e}")

                    # Jeśli nie było launcher_db_files, ale są foldery miejscowości - zbierz je z ZIP
                    if not launcher_db_files and has_location_folders:
                        # Wykryj miejscowości z struktury folderów w ZIP
                        location_folders = set()
                        for filename in archive_contents:
                            if '/' in filename and not filename.startswith('assets/'):
                                location_name = filename.split('/')[0]
                                if location_name:
                                    location_folders.add(location_name)
                        restored_locations.extend(list(location_folders))
                else:
                    # Stary format - pliki bezpośrednio w root ZIP
                    # Wyodrębnij do aktywnej miejscowości
                    active_location_name = get_active_location_name()
                    if active_location_name:
                        target_folder = os.path.join(BACKUP_FOLDER, active_location_name)
                        restored_locations.append(active_location_name)
                    else:
                        target_folder = BACKUP_FOLDER

                    # Przywracanie plików JSON
                    if "map_config.json" in archive_contents:
                        zf.extract("map_config.json", path=target_folder)

                    for key in ["owners", "parcels", "genealogy"]:
                        json_filename = os.path.basename(DATA_FILES[key]["path"])
                        if json_filename in archive_contents:
                            zf.extract(json_filename, path=target_folder)

                        for related_path in DATA_FILES[key].get("related", []):
                            related_filename = os.path.basename(related_path)
                            if related_filename in archive_contents:
                                zf.extract(related_filename, path=target_folder)

            # Zapytaj użytkownika czy chce zmigrować dane do PostgreSQL
            migration_success = []
            migration_errors = []

            if restored_locations:
                locations_list = "\n".join([f"  • {loc}" for loc in restored_locations])
                migrate_msg = (
                    f"✅ Kopia zapasowa została przywrócona.\n\n"
                    f"Znaleziono dane dla miejscowości:\n{locations_list}\n\n"
                    f"Czy chcesz automatycznie utworzyć bazy danych i zmigrować dane do PostgreSQL?"
                )

                if messagebox.askyesno("🔄 Migracja Danych", migrate_msg, icon="question", parent=self):
                    # Stwórz okno z postępem migracji
                    progress_window = tk.Toplevel(self)
                    progress_window.title("🔄 Migracja Danych")
                    progress_window.transient(self)
                    progress_window.grab_set()

                    x = self.winfo_x() + (self.winfo_width() - 600) // 2
                    y = self.winfo_y() + (self.winfo_height() - 400) // 2
                    progress_window.geometry(f"600x400+{x}+{y}")

                    ttk.Label(progress_window, text="Migracja danych do PostgreSQL",
                             font=("Segoe UI", 12, "bold")).pack(pady=10)

                    progress_text = scrolledtext.ScrolledText(progress_window, height=15, width=70)
                    progress_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

                    def log_progress(message):
                        progress_text.insert(tk.END, message + "\n")
                        progress_text.see(tk.END)
                        progress_text.update()

                    # Migruj każdą miejscowość
                    for location_name in restored_locations:
                        log_progress(f"\n{'='*50}")
                        log_progress(f"📍 Miejscowość: {location_name}")
                        log_progress(f"{'='*50}")

                        success, msg = create_and_migrate_location_database(
                            location_name,
                            progress_callback=log_progress
                        )

                        if success:
                            migration_success.append(location_name)
                            log_progress(f"✅ {msg}")
                        else:
                            migration_errors.append((location_name, msg))
                            log_progress(f"❌ {msg}")

                    log_progress(f"\n{'='*50}")
                    log_progress("📊 Podsumowanie migracji:")
                    log_progress(f"  ✅ Sukces: {len(migration_success)}/{len(restored_locations)}")
                    if migration_errors:
                        log_progress(f"  ❌ Błędy: {len(migration_errors)}")
                    log_progress(f"{'='*50}")

                    # Ramka na przycisk
                    button_frame = ttk.Frame(progress_window)
                    button_frame.pack(pady=15)

                    # Przycisk zamknięcia
                    close_btn = ttk.Button(button_frame, text="✅ Zamknij",
                                          command=progress_window.destroy,
                                          style="Primary.TButton")
                    close_btn.pack()

                    progress_window.wait_window()

            # Pokaż końcowy komunikat
            final_msg = "Kopia zapasowa została przywrócona.\n\n"
            if migration_success:
                final_msg += f"✅ Zmigrowano dane dla: {', '.join(migration_success)}\n"
            if migration_errors:
                final_msg += f"\n⚠️ Błędy migracji dla: {', '.join([loc for loc, _ in migration_errors])}\n"
            final_msg += "\nUruchom ponownie edytory, aby zobaczyć zmiany."

            messagebox.showinfo("✅ Sukces", final_msg, parent=self)
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Wystąpił błąd:\n{e}", parent=self)

class ProgressDialog(tk.Toplevel):
    """Okno dialogowe postępu operacji."""
    
    def __init__(self, parent, task_func, task_args):
        super().__init__(parent)
        self.title("💾 Tworzenie Kopii Zapasowej")
        self.transient(parent)
        self.grab_set()
        
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 180) // 2
        self.geometry(f"400x180+{x}+{y}")
        self.resizable(False, False)
        
        ttk.Label(self, text="📦 Przygotowywanie plików...",
                 font=("Segoe UI", 11), padding=10).pack(pady=(15, 5))
        
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", length=360, mode="determinate")
        self.progress_bar.pack(pady=5, padx=20)
        
        self.status_label = ttk.Label(self, text="", padding=5, wraplength=350)
        self.status_label.pack(pady=(5, 10))
        
        self.success = None
        self.result = None
        self.error_message = None
        
        threading.Thread(target=self._run_task, args=(task_func, task_args), daemon=True).start()

    def _run_task(self, task_func, task_args):
        """Wykonuje zadanie w osobnym wątku."""
        try:
            def progress_callback(current, total, message):
                self.progress_bar["maximum"] = total
                self.progress_bar["value"] = current
                self.status_label.config(text=message)
                self.update_idletasks()
            
            self.result = task_func(progress_callback, task_args)
            self.success = True
        except Exception as e:
            self.success = False
            self.error_message = str(e)
        finally:
            self.after(100, self._finish)

    def _finish(self):
        """Kończy operację i wyświetla wynik."""
        self.destroy()
        
        if self.success:
            messagebox.showinfo("✅ Sukces", f"Utworzono kopię zapasową:\n{self.result}", parent=self.master)
            self.master.populate_backup_list()
        else:
            messagebox.showerror("❌ Błąd", f"Nie udało się utworzyć kopii:\n{self.error_message}", parent=self.master)

class SiteSettingsManager(tk.Toplevel):
    """Okno dialogowe do zarządzania ustawieniami witryny."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("🖼️ Ustawienia Witryny")
        self.grab_set()
        self.resizable(False, False)
        
        self.parent_app = parent
        self.db_config = get_db_config_from_env()
        self.current_favicon_path = None
        self.image_preview = None
        
        self.create_widgets()
        self.load_current_settings()
        self.center_window()

    def create_widgets(self):
        """Tworzy interfejs ustawień."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        frame_favicon = ttk.LabelFrame(main_frame, text="Ikona Witryny (Favicon)", padding="15")
        frame_favicon.pack(fill=tk.X)
        
        top_row = ttk.Frame(frame_favicon)
        top_row.pack(fill=tk.X)
        
        # Podgląd ikony
        self.preview_canvas = tk.Canvas(top_row, width=64, height=64, bg=self.cget("background"), highlightthickness=0)
        self.preview_canvas.pack(side=tk.LEFT, padx=(0, 15))
        self.preview_label = ttk.Label(self.preview_canvas, text="Brak\nikony", foreground="grey")
        self.preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Informacje i przycisk
        info_frame = ttk.Frame(top_row)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.path_label = ttk.Label(info_frame, text="Obecna ikona: Brak", wraplength=350)
        self.path_label.pack(anchor="w")
        
        ttk.Button(info_frame, text="Wybierz Ikonę (.png, .ico, .jpg)",
                  command=self.select_favicon, style="Primary.TButton").pack(pady=(10,0), anchor="w")
        
        ttk.Label(main_frame, text="Zmiany będą widoczne po restarcie serwera.",
                 foreground="grey", wraplength=450).pack(pady=(15,0))
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(button_frame, text="Zamknij", command=self.destroy).pack(side=tk.RIGHT)

    def load_current_settings(self):
        """Wczytuje aktualny favicon z folderu backup aktywnej miejscowości."""
        try:
            location_name = get_active_location_name()
            if not location_name:
                self.path_label.config(text="Obecna ikona: Brak aktywnej miejscowości")
                return

            backup_location_folder = os.path.join(BACKUP_FOLDER, location_name)

            # Sprawdź różne rozszerzenia favicon
            favicon_extensions = ['.ico', '.png', '.jpg', '.jpeg']
            for ext in favicon_extensions:
                favicon_path = os.path.join(backup_location_folder, f"favicon{ext}")
                if os.path.exists(favicon_path):
                    self.current_favicon_path = favicon_path
                    self.update_preview()
                    return

            self.path_label.config(text="Obecna ikona: Brak (używana domyślna)")
        except Exception as e:
            self.path_label.config(text=f"Błąd: {e}")

    def update_preview(self):
        """Aktualizuje podgląd ikony."""
        if not self.current_favicon_path:
            self.path_label.config(text="Obecna ikona: Brak (używana domyślna)")
            return

        if os.path.exists(self.current_favicon_path):
            try:
                # Pokaż ścieżkę relatywną do backup
                rel_path = os.path.relpath(self.current_favicon_path, BACKUP_FOLDER)
                self.path_label.config(text=f"Obecna ikona: backup/{rel_path}")
                img = Image.open(self.current_favicon_path)
                img.thumbnail((64, 64), Image.Resampling.LANCZOS)
                self.image_preview = ImageTk.PhotoImage(img)
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(32, 32, image=self.image_preview)
                self.preview_label.place_forget()
            except Exception as e:
                self.path_label.config(text=f"Błąd podglądu: {e}")
                self.preview_canvas.delete("all")
                self.preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        else:
            self.path_label.config(text=f"❌ Błąd: Plik nie istnieje")
            self.preview_canvas.delete("all")
            self.preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def select_favicon(self):
        """Otwiera dialog wyboru pliku i kopiuje go do folderu backup aktywnej miejscowości."""
        filepath = filedialog.askopenfilename(
            title="Wybierz plik ikony",
            filetypes=[("Obrazy", "*.png *.ico *.jpg *.jpeg"), ("Wszystkie pliki", "*.*")]
        )

        if not filepath:
            return

        # Pobierz nazwę aktywnej miejscowości
        try:
            location_name = get_active_location_name()
            if not location_name:
                messagebox.showerror("Błąd", "Brak aktywnej miejscowości.", parent=self)
                return
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można pobrać aktywnej miejscowości: {e}", parent=self)
            return

        # Ścieżka do folderu backup miejscowości
        backup_location_folder = os.path.join(BACKUP_FOLDER, location_name)
        os.makedirs(backup_location_folder, exist_ok=True)

        file_extension = os.path.splitext(filepath)[1]
        dest_filename = f"favicon{file_extension}"
        dest_path = os.path.join(backup_location_folder, dest_filename)

        try:
            shutil.copy(filepath, dest_path)
            self.parent_app.log(f"🖼️ Ustawiono nowy favicon w backup/{location_name}/{dest_filename}\n")
            messagebox.showinfo("Sukces",
                              f"Nowa ikona została zapisana w backup/{location_name}/\n"
                              "Zmiany będą widoczne po odświeżeniu strony.",
                              parent=self)
            self.current_favicon_path = dest_path
            self.update_preview()
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się przetworzyć pliku: {e}", parent=self)

    def center_window(self):
        """Wyśrodkowuje okno."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

class SecurityManager(tk.Toplevel):
    """Okno dialogowe do zarządzania bezpieczeństwem systemu."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("🛡️ Menedżer Bezpieczeństwa")
        
        self.geometry("900x600")
        self.minsize(700, 500)
        self.grab_set()
        
        self.parent_app = parent
        self.base_url = f"http://127.0.0.1:{self.parent_app.load_flask_config()['port']}/api/admin/security"
        
        self.create_widgets()
        self.load_data()
        self.center_window()

    def create_widgets(self):
        """Tworzy interfejs menedżera bezpieczeństwa."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Zakładka: Logi Logowania
        logs_frame = ttk.Frame(notebook, padding="10")
        notebook.add(logs_frame, text="📜 Logi Logowania")
        self.create_logs_tab(logs_frame)
        
        # Zakładka: Zablokowane IP
        blocked_frame = ttk.Frame(notebook, padding="10")
        notebook.add(blocked_frame, text="🚫 Zablokowane Adresy IP")
        self.create_blocked_ips_tab(blocked_frame)
        
        ttk.Button(main_frame, text="Zamknij", command=self.destroy, 
                  style="Secondary.TButton").pack(side=tk.RIGHT)

    def create_logs_tab(self, parent):
        """Tworzy zakładkę z logami logowania."""
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(action_frame, text="Ostatnie 100 prób logowania do panelu admina",
                 style="Heading.TLabel").pack(side=tk.LEFT, anchor=tk.W)
        
        ttk.Button(action_frame, text="🗑️ Wyczyść Wszystkie Logi",
                  command=self.clear_login_logs, style="Warning.TButton").pack(side=tk.RIGHT)
        
        # Tabela logów
        cols = ("ip", "user", "time", "status")
        self.logs_tree = ttk.Treeview(parent, columns=cols, show="headings")
        self.logs_tree.heading("ip", text="Adres IP")
        self.logs_tree.heading("user", text="Użyty login")
        self.logs_tree.heading("time", text="Czas")
        self.logs_tree.heading("status", text="Status")
        self.logs_tree.column("ip", width=120)
        self.logs_tree.column("user", width=150)
        self.logs_tree.column("time", width=160)
        self.logs_tree.column("status", width=100, anchor=tk.CENTER)
        
        self.logs_tree.tag_configure("success", foreground="green")
        self.logs_tree.tag_configure("failure", foreground="red")
        
        self.logs_tree.pack(fill=tk.BOTH, expand=True)

    def create_blocked_ips_tab(self, parent):
        """Tworzy zakładkę z zablokowanymi adresami IP."""
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(action_frame, text="🚨 Odblokuj Localhost (127.0.0.1)",
                  command=self.unblock_localhost, style="Warning.TButton").pack(side=tk.LEFT)
        
        right_buttons = ttk.Frame(action_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="🔓 Odblokuj Zaznaczone",
                  command=self.unblock_selected_ip, style="Success.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(right_buttons, text="➕ Zablokuj IP",
                  command=self.manually_block_ip, style="Danger.TButton").pack(side=tk.LEFT)
        
        # Tabela zablokowanych IP
        cols = ("ip", "reason", "time")
        self.blocked_tree = ttk.Treeview(parent, columns=cols, show="headings")
        self.blocked_tree.heading("ip", text="Adres IP")
        self.blocked_tree.heading("reason", text="Powód blokady")
        self.blocked_tree.heading("time", text="Czas blokady")
        self.blocked_tree.column("ip", width=120)
        self.blocked_tree.column("reason", width=400)
        self.blocked_tree.column("time", width=160)
        self.blocked_tree.pack(fill=tk.BOTH, expand=True)

    def load_data(self):
        """Ładuje dane logów i zablokowanych IP."""
        self.load_logs()
        self.load_blocked_ips()

    def api_request(self, endpoint, method="GET", data=None):
        """Wykonuje żądanie do API bezpieczeństwa."""
        import requests
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {"Content-Type": "application/json"}
            
            if method.upper() == "GET":
                response = requests.get(url, timeout=5)
            else:
                response = requests.post(url, data=json.dumps(data), headers=headers, timeout=5)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Błąd API", f"Nie można połączyć się z serwerem:\n{e}", parent=self)
            return None

    def load_logs(self):
        """Ładuje logi logowania z serwera."""
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)
        
        logs = self.api_request("/logs")
        if logs:
            for log in logs:
                status_text = "✅ Powodzenie" if log['successful'] else "❌ Błąd"
                tag = "success" if log['successful'] else "failure"
                self.logs_tree.insert("", "end", 
                                     values=(log['ip_address'], log['username_attempt'], 
                                           log['timestamp'], status_text),
                                     tags=(tag,))

    def clear_login_logs(self):
        """Czyści wszystkie logi logowania."""
        if messagebox.askyesno(
            "🗑️ Potwierdzenie",
            "Czy na pewno chcesz trwale usunąć WSZYSTKIE logi prób logowania?\n\n"
            "Tej operacji nie można cofnąć.",
            parent=self,
            icon="warning"
        ):
            response = self.api_request("/clear-logs", method="POST")
            if response and response.get("status") == "success":
                messagebox.showinfo("✅ Sukces", "Wszystkie logi logowania zostały usunięte.", parent=self)
                self.parent_app.log("🛡️ Wyczyszczono wszystkie logi logowania.\n")
                self.load_logs()
            else:
                messagebox.showerror("❌ Błąd", "Nie udało się wyczyścić logów.", parent=self)

    def load_blocked_ips(self):
        """Ładuje listę zablokowanych adresów IP."""
        for item in self.blocked_tree.get_children():
            self.blocked_tree.delete(item)
        
        ips = self.api_request("/blocked-ips")
        if ips:
            for ip in ips:
                self.blocked_tree.insert("", "end",
                                        values=(ip['ip_address'], ip['reason'], ip['timestamp']))

    def unblock_selected_ip(self):
        """Odblokowuje zaznaczone adresy IP."""
        selected_items = self.blocked_tree.selection()
        
        if not selected_items:
            messagebox.showwarning("Brak zaznaczenia", "Zaznacz adres IP do odblokowania.", parent=self)
            return
        
        for item_id in selected_items:
            ip_to_unblock = self.blocked_tree.item(item_id)['values'][0]
            
            if messagebox.askyesno("Potwierdzenie", 
                                  f"Czy na pewno chcesz odblokować adres IP: {ip_to_unblock}?", 
                                  parent=self):
                response = self.api_request("/unblock-ip", method="POST", 
                                          data={"ip_address": ip_to_unblock})
                
                if response and response.get("status") == "success":
                    self.parent_app.log(f"🛡️ Odblokowano adres IP: {ip_to_unblock}\n")
                else:
                    messagebox.showerror("Błąd", f"Nie udało się odblokować {ip_to_unblock}.", parent=self)
        
        self.load_blocked_ips()

    def unblock_localhost(self):
        """Odblokowuje adres localhost (127.0.0.1)."""
        ip_to_unblock = "127.0.0.1"
        
        if messagebox.askyesno(
            "Potwierdzenie",
            f"Czy na pewno chcesz odblokować adres {ip_to_unblock}?\n\n"
            "Użyj tej opcji, jeśli przypadkowo zablokowałeś dostęp z lokalnego komputera.",
            parent=self
        ):
            response = self.api_request("/unblock-ip", method="POST", 
                                      data={"ip_address": ip_to_unblock})
            
            if response and response.get("status") == "success":
                messagebox.showinfo("Sukces", 
                                  f"Wysłano żądanie odblokowania dla adresu {ip_to_unblock}.", 
                                  parent=self)
                self.parent_app.log(f"🛡️ Wysłano awaryjne odblokowanie dla: {ip_to_unblock}\n")
                self.load_blocked_ips()
            else:
                messagebox.showerror("Błąd", 
                                   f"Nie udało się odblokować {ip_to_unblock}. Sprawdź czy serwer działa.", 
                                   parent=self)

    def manually_block_ip(self):
        """Ręcznie blokuje podany adres IP."""
        from tkinter import simpledialog
        
        ip = simpledialog.askstring("Blokada IP", "Wprowadź adres IP do zablokowania:", parent=self)
        if not ip:
            return
        
        reason = simpledialog.askstring("Powód blokady", "Podaj powód blokady (opcjonalnie):", parent=self)
        
        response = self.api_request("/block-ip", method="POST",
                                  data={"ip_address": ip, "reason": reason or "Ręczna blokada."})
        
        if response and response.get("status") == "success":
            self.parent_app.log(f"🛡️ Ręcznie zablokowano adres IP: {ip}\n")
            self.load_blocked_ips()
        else:
            messagebox.showerror("Błąd", f"Nie udało się zablokować {ip}.", parent=self)

    def center_window(self):
        """Wyśrodkowuje okno."""
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

# =============================================================================
# PUNKT WEJŚCIA APLIKACJI
# =============================================================================
if __name__ == "__main__":
    """Główny punkt wejścia aplikacji."""
    app = AppLauncher()
    app.mainloop()
