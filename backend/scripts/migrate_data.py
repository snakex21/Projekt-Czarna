"""
================================================================================
Skrypt: migrate_data.py
Opis: Migracja danych katastralnych z plików JSON do bazy (PostgreSQL lub SQLite).
      Obsługuje import właścicieli, obiektów geograficznych, demografii i genealogii.
================================================================================
"""

import json
import os
import sys
import re
from datetime import date

# Import psycopg2 na górze, bo poza klasą DB (linie 242, 488) jest używany
# bezpośrednio jako ``psycopg2.connect(...)``. Klasa ``DB`` sama w sobie używa
# lazy ``_ensure_psycopg2()``, ale ten skrypt ma też ścieżki "gołe" — bez tego
# importu dostajemy ``NameError: name 'psycopg2' is not defined``.
import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.shared import parse_polish_date, fix_windows_console_encoding

fix_windows_console_encoding()

# Lazy imports — załadujemy odpowiedni sterownik dopiero przy łączeniu.
_psycopg2 = None
_psycopg2_execute_values = None
_sqlite3 = None

def _ensure_psycopg2():
    global _psycopg2, _psycopg2_execute_values
    if _psycopg2 is None:
        import psycopg2 as _pg
        from psycopg2.extras import execute_values as _ev
        _psycopg2 = _pg
        _psycopg2_execute_values = _ev

def _ensure_sqlite3():
    global _sqlite3
    if _sqlite3 is None:
        import sqlite3 as _sq
        _sqlite3 = _sq

# ================================================================================
# KONFIGURACJA ŚRODOWISKA
# ================================================================================

# Abstrakcja bazy danych — wspólna dla PostgreSQL i SQLite.
class DB:
    """Cienka warstwa abstrakcji nad psycopg2 / sqlite3."""
    def __init__(self, engine: str, db_config: dict, sqlite_path: str = ""):
        self.engine = engine.lower()
        self._conn = None
        self._cur = None
        self._db_config = db_config
        self._sqlite_path = sqlite_path

    def connect(self):
        if self.engine == "sqlite":
            _ensure_sqlite3()
            self._conn = _sqlite3.connect(self._sqlite_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._cur = self._conn.cursor()
        else:
            _ensure_psycopg2()
            self._conn = _psycopg2.connect(**self._db_config)
            self._conn.set_client_encoding("UTF8")
            self._cur = self._conn.cursor()
        return self

    @property
    def cur(self):
        return self._cur

    @property
    def ph(self):
        """Placeholder: %s dla PG, ? dla SQLite."""
        return "?" if self.engine == "sqlite" else "%s"

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if self._cur:
            self._cur.close()
        if self._conn:
            self._conn.close()

    def truncate(self, tables: list):
        for t in tables:
            if self.engine == "sqlite":
                self._cur.execute(f"DELETE FROM {t}")
            else:
                self._cur.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")

    def execute(self, sql: str, params=None, fetch=False):
        if self.engine == "sqlite":
            sql = sql.replace("%s", "?")
        self._cur.execute(sql, params)
        if fetch:
            return self._cur.fetchall()
        return self._cur.rowcount

    def executemany(self, sql: str, rows: list):
        if self.engine == "sqlite":
            sql = sql.replace("%s", "?")
            self._cur.executemany(sql, rows)
        else:
            _psycopg2_execute_values(self._cur, sql, rows)

    def last_id(self) -> int:
        if self.engine == "sqlite":
            return self._cur.lastrowid
        row = self._cur.fetchone()
        return row[0] if row else None

    def insert_returning(self, sql: str, params) -> int:
        """Wstawia wiersz i zwraca id."""
        if self.engine == "sqlite":
            sql = sql.replace("%s", "?")
            self._cur.execute(sql, params)
            return self._cur.lastrowid
        else:
            self._cur.execute(sql, params)
            return self._cur.fetchone()[0]

    def insert_on_conflict(self, table: str, cols: list, values: tuple,
                           conflict_cols: list, update_cols: list = None):
        """UPSERT: wstawia lub aktualizuje."""
        placeholders = ", ".join([self.ph] * len(values))
        col_list = ", ".join(cols)
        if self.engine == "sqlite":
            conflict = ", ".join(conflict_cols)
            if update_cols:
                updates = ", ".join(f"{c}=excluded.{c}" for c in update_cols)
                sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT({conflict}) DO UPDATE SET {updates}"
            else:
                sql = f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})"
            sql = sql.replace("excluded.", "")  # SQLite nie ma EXCLUDED
            self._cur.execute(sql, values)
            return self._cur.lastrowid
        else:
            conflict = ", ".join(conflict_cols)
            if update_cols:
                updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols)
                sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT ({conflict}) DO UPDATE SET {updates} RETURNING id"
            else:
                sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT ({conflict}) DO NOTHING RETURNING id"
            self._cur.execute(sql, values)
            row = self._cur.fetchone()
            return row[0] if row else None

# Wczytaj konfigurację PostgreSQL z launcher/.postgres.env
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
launcher_postgres_env = os.path.join(base_dir, "launcher", ".postgres.env")
if os.path.exists(launcher_postgres_env):
    try:
        from dotenv import dotenv_values
        pg_config = dotenv_values(launcher_postgres_env)
        if pg_config.get('LAUNCHER_DB_PASSWORD'):
            os.environ['DB_HOST'] = pg_config.get('LAUNCHER_DB_HOST', 'localhost')
            os.environ['DB_PORT'] = str(pg_config.get('LAUNCHER_DB_PORT', '5432'))
            os.environ['DB_USER'] = pg_config.get('LAUNCHER_DB_USER', 'postgres')
            os.environ['DB_PASSWORD'] = pg_config.get('LAUNCHER_DB_PASSWORD', '')
            print(f"✅ Wczytano konfigurację PostgreSQL z launcher/.postgres.env")
    except Exception as e:
        print(f"⚠️ Błąd wczytywania launcher/.postgres.env: {e}")

# Funkcja do określenia miejscowości do migracji
def get_location_info_for_migration(location_name=None):
    """
    Zwraca informacje o miejscowości do migracji.

    Args:
        location_name: Nazwa miejscowości (opcjonalne). Jeśli None, użyje aktywnej miejscowości.

    Returns:
        dict: Informacje o miejscowości (nazwa, ścieżka do .env, folder backup)
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Jeśli podano konkretną miejscowość, użyj jej
    if location_name:
        backup_folder = os.path.join(base_dir, "data", "locations", location_name)
        env_path = os.path.join(backup_folder, ".env")

        if os.path.exists(env_path):
            print(f"✅ Używam danych z miejscowości: {location_name}")
            return {
                'name': location_name,
                'env_path': env_path,
                'backup_dir': backup_folder
            }
        else:
            print(f"⚠️ Brak pliku .env dla miejscowości {location_name}: {env_path}")
            print(f"⚠️ Próbuję pobrać aktywną miejscowość...")

    # Jeśli nie podano miejscowości lub nie ma .env, pobierz aktywną miejscowość
    # Sprawdź najpierw DB_ENGINE - SQLite vs PostgreSQL
    db_engine = os.getenv("DB_ENGINE", "")
    if not db_engine:
        env_check = os.path.join(base_dir, "backend", ".env")
        if os.path.exists(env_check):
            try:
                with open(env_check, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("DB_ENGINE="):
                            db_engine = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception: pass

    if db_engine.lower() == "sqlite":
        # SQLite — pomiń PostgreSQL
        locations_db_path = os.path.join(base_dir, "data", "locations.db")
        if os.path.exists(locations_db_path):
            try:
                _ensure_sqlite3()
                conn = _sqlite3.connect(locations_db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM locations WHERE active = 1")
                result = cursor.fetchone()
                conn.close()
                if result:
                    location_name = result[0]
                    backup_folder = os.path.join(base_dir, "data", "locations", location_name)
                    env_path = os.path.join(backup_folder, ".env")
                    if os.path.exists(env_path):
                        print(f"✅ Używam danych z miejscowości (SQLite): {location_name}")
                        return {'name': location_name, 'env_path': env_path, 'backup_dir': backup_folder}
            except Exception as e:
                print(f"⚠️ Błąd podczas odczytu SQLite: {e}")
    else:
        # PostgreSQL
        try:
            launcher_db_config = {
                "host": os.getenv("DB_HOST", "localhost"),
                "dbname": "mapa_launcher_db",
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "1234"),
                "port": os.getenv("DB_PORT", "5432"),
                "client_encoding": "UTF8"
            }
            conn = psycopg2.connect(**launcher_db_config)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM locations WHERE active = TRUE LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            if result:
                location_name = result[0]
                backup_folder = os.path.join(base_dir, "data", "locations", location_name)
                env_path = os.path.join(backup_folder, ".env")
                if os.path.exists(env_path):
                    print(f"✅ Używam danych z miejscowości (PostgreSQL): {location_name}")
                    return {'name': location_name, 'env_path': env_path, 'backup_dir': backup_folder}
        except Exception as e:
            print(f"⚠️ PostgreSQL niedostępny: {e}")

    # Fallback — spróbuj auto-wykryć dostępną lokalizację
    locations_dir = os.path.join(base_dir, "data", "locations")
    if os.path.isdir(locations_dir):
        subdirs = sorted([
            d for d in os.listdir(locations_dir)
            if os.path.isdir(os.path.join(locations_dir, d))
            and os.path.exists(os.path.join(locations_dir, d, "owner_data_to_import.json"))
        ])
        if subdirs:
            location_name = subdirs[0]  # pierwsza dostępna
            backup_folder = os.path.join(locations_dir, location_name)
            env_path = os.path.join(backup_folder, ".env")
            if not os.path.exists(env_path):
                env_path = os.path.join(base_dir, "backend", ".env")
            print(f"⚠️ Używam auto-wykrytej lokalizacji: {location_name}")
            return {'name': location_name, 'env_path': env_path, 'backup_dir': backup_folder}

    # Ostateczny fallback
    print(f"⚠️ Używam domyślnej lokalizacji danych (Czarna)")
    return {
        'name': "Czarna",
        'env_path': os.path.join(base_dir, "backend", ".env"),
        'backup_dir': os.path.join(base_dir, "data", "locations", "Czarna")
    }

# Sprawdź czy podano nazwę miejscowości jako argument wiersza poleceń
location_name_arg = sys.argv[1] if len(sys.argv) > 1 else None

# Pobierz informacje o miejscowości do migracji
location_info = get_location_info_for_migration(location_name_arg)

# Własna funkcja do wczytania .env z obsługą różnych kodowań
def load_env_with_encoding(env_path):
    """Wczytuje .env z obsługą różnych kodowań (utf-8, cp1250, latin-1)."""
    if not os.path.exists(env_path):
        print(f"⚠️ Plik .env nie istnieje: {env_path}")
        return

    # Spróbuj różnych kodowań
    for encoding in ['utf-8', 'cp1250', 'latin-1']:
        try:
            with open(env_path, 'r', encoding=encoding) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key, value = key.strip(), value.strip()
                        # Usuń cudzysłowy jeśli są
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        os.environ[key] = value
            print(f"✅ Załadowano .env ({encoding})")
            return
        except UnicodeDecodeError:
            if encoding == 'latin-1':  # latin-1 nie powinno rzucić UnicodeDecodeError
                print(f"❌ Błąd odczytu .env: {env_path}")
            continue
        except Exception as e:
            print(f"❌ Błąd wczytywania .env: {e}")
            return

# Załadowanie zmiennych środowiskowych z odpowiedniego pliku .env
load_env_with_encoding(location_info['env_path'])

def get_env_variable(var_name, default_value=None):
    """
    Pobiera wartość zmiennej środowiskowej z opcjonalną wartością domyślną.

    Args:
        var_name: Nazwa zmiennej środowiskowej
        default_value: Wartość domyślna jeśli zmienna nie istnieje

    Returns:
        Wartość zmiennej lub wartość domyślna
    """
    value = os.getenv(var_name, default_value)
    if value is None:
        print(f"⚠️  Uwaga: Zmienna środowiskowa {var_name} nie jest ustawiona!")
    return value

print("\n" + "=" * 50)
print("      SKRYPT MIGRACJI DANYCH KATASTRALNYCH")
print("=" * 50)

# ================================================================================
# ŚCIEŻKI I PARAMETRY POŁĄCZENIA
# ================================================================================

# Lokalizacje plików źródłowych - używamy folderu aktywnej miejscowości
BACKUP_DIR = location_info['backup_dir']
OWNER_DATA_FILE = os.path.join(BACKUP_DIR, "owner_data_to_import.json")
PARCEL_DATA_FILE = os.path.join(BACKUP_DIR, "parcels_data.json")
DEMOGRAFIA_DATA_FILE = os.path.join(BACKUP_DIR, "demografia.json")
GENEALOGIA_DATA_FILE = os.path.join(BACKUP_DIR, "genealogia.json")

# Konfiguracja bazy danych PostgreSQL
# DB_ENGINE może być w backend/.env (SQLite) lub w .env miejscowości (PostgreSQL).
# Jawnie sprawdzamy oba.
_backend_env = os.path.join(base_dir, ".env")
if os.path.exists(_backend_env):
    try:
        with open(_backend_env, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line.startswith("DB_ENGINE="):
                    os.environ.setdefault("DB_ENGINE", _line.split("=", 1)[1].strip().strip('"').strip("'"))
    except Exception:
        pass

tenant_db_engine = get_env_variable("DB_ENGINE", "")

if tenant_db_engine.lower() == "sqlite":
    print("🔄 DB_ENGINE=sqlite — uruchamiam import dla SQLite...")
    sqlite_import = os.path.join(os.path.dirname(__file__), "import_sqlite_backup.py")
    location = location_info.get("name") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not location:
        location = os.path.basename(location_info['backup_dir'])
    db_path = os.path.join(base_dir, "..", "data", "czarna.db")
    db_path = os.path.abspath(db_path)
    import subprocess as _sp
    result = _sp.run(
        [sys.executable, sqlite_import, location, db_path],
        cwd=os.path.dirname(base_dir),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=300,
    )
    if result.returncode == 0:
        print(result.stdout.strip())
        print("✅ Migracja SQLite zakończona.")
        sys.exit(0)
    else:
        print(result.stderr or result.stdout)
        sys.exit(1)

DB_CONFIG = {
    "host": get_env_variable("DB_HOST", "localhost"),
    "dbname": get_env_variable("DB_NAME", "mapa_czarna_db"),
    "user": get_env_variable("DB_USER", "postgres"),
    "password": get_env_variable("DB_PASSWORD", "1234"),
    "port": get_env_variable("DB_PORT", "5432"),
    "client_encoding": "UTF8"  # Wymuszenie kodowania UTF-8
}

print("\n📊 Konfiguracja połączenia:")
print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
print(f"   Baza: {DB_CONFIG['dbname']}")
print(f"   Użytkownik: {DB_CONFIG['user']}")
print("=" * 50)

# ================================================================================
# FUNKCJE POMOCNICZE
# ================================================================================

def get_wkt_from_geometry(geom_data, kategoria):
    """
    Konwertuje dane geometryczne na format WKT (Well-Known Text).
    Obsługuje punkty, linie i poligony w zależności od kategorii obiektu.
    """
    if not geom_data:
        return None
    
    # Obiekty punktowe
    if kategoria in ["dom", "kapliczka", "budynek", "dworzec", "obiekt_specjalny"]:
        lat, lng = geom_data
        return f"POINT({lng} {lat})"
    
    # Obiekty liniowe    
    if kategoria in ["droga", "rzeka"]:
        if len(geom_data) < 2: 
            return None
        coords_str = ", ".join([f"{lng} {lat}" for lat, lng in geom_data])
        return f"LINESTRING({coords_str})"
    
    # Poligony    
    if len(geom_data) > 2 and isinstance(geom_data[0], list):
        if geom_data[0] != geom_data[-1]:
            geom_data.append(geom_data[0])
        coords_str = ", ".join([f"{lng} {lat}" for lat, lng in geom_data])
        return f"POLYGON(({coords_str}))"
        
    return None

def norm(num):
    """Normalizuje numer działki do formatu string (np. '800/23')."""
    if isinstance(num, dict):
        a = str(num.get("numerator") or num.get("numarator") or "").strip()
        b = str(num.get("denominator") or "").strip()
        return f"{a}/{b}" if a and b else a
    return str(num).strip()

# ================================================================================
# GŁÓWNA LOGIKA MIGRACJI
# ================================================================================

conn = None
try:
    # --- ETAP 1: WCZYTYWANIE DANYCH ---
    print("\n--- Etap 1: Wczytywanie danych źródłowych ---")
    
    with open(OWNER_DATA_FILE, "r", encoding="utf-8") as f:
        owner_data = json.load(f)
    print(f"✔️ Załadowano {len(owner_data)} właścicieli")

    with open(PARCEL_DATA_FILE, "r", encoding="utf-8") as f:
        parcel_data = json.load(f)
    print(f"✔️ Załadowano {len(parcel_data)} obiektów geograficznych")

    # Opcjonalne pliki
    demografia_data = []
    if os.path.exists(DEMOGRAFIA_DATA_FILE):
        with open(DEMOGRAFIA_DATA_FILE, "r", encoding="utf-8") as f:
            demografia_data = json.load(f)
        print(f"✔️ Załadowano {len(demografia_data)} wpisów demograficznych")
    else:
        print(f"⚠️  Plik demografii nie znaleziony - pomijam")

    genealogia_data = []
    if os.path.exists(GENEALOGIA_DATA_FILE):
        with open(GENEALOGIA_DATA_FILE, "r", encoding="utf-8") as f:
            genealogia_data = json.load(f).get("persons", [])
        print(f"✔️ Załadowano {len(genealogia_data)} osób genealogicznych")
    else:
        print(f"⚠️  Plik genealogii nie znaleziony - pomijam")

    # --- ETAP 2: INICJALIZACJA BAZY ---
    print("\n--- Etap 2: Przygotowanie bazy danych ---")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding("UTF8")
    cur = conn.cursor()
    print("✔️ Połączono z bazą danych")
    
    # Czyszczenie tabel
    cur.execute("""
        TRUNCATE TABLE malzenstwa, osoby_genealogia, demografia, 
                      dzialki_wlasciciele, powiazania_protokolow, 
                      obiekty_geograficzne, wlasciciele 
        RESTART IDENTITY CASCADE
    """)
    print("✔️ Tabele wyczyszczone")
    
    # --- ETAP 3: IMPORT WŁAŚCICIELI ---
    print("\n--- Etap 3: Import właścicieli ---")
    owner_id_map = {}
    
    for key, v in owner_data.items():
        try:
            protocol_date = parse_polish_date(v.get("protocolDate"))
            protocol_location = v.get("protocolLocation", "")
            order_number_str = str(v.get("orderNumber", "")).strip()
            order_number = int(order_number_str) if order_number_str.isdigit() else None

            cur.execute(
                """
                INSERT INTO wlasciciele (
                    unikalny_klucz, nazwa_wlasciciela, numer_protokolu, numer_domu, 
                    genealogia, historia_wlasnosci, uwagi, wspolwlasnosc, 
                    powiazania_i_transakcje, interpretacja_i_wnioski, 
                    data_protokolu, miejsce_protokolu
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
                RETURNING id
                """,
                (
                    key, v.get("ownerName", ""), order_number, v.get("houseNumber", ""),
                    v.get("genealogy", ""), v.get("ownershipHistory", ""), 
                    v.get("remarks", ""), v.get("wspolwlasnosc", ""), 
                    v.get("powiazania_i_transakcje", v.get("relacje_rodzinne", "")),
                    v.get("interpretacja_i_wnioski", ""), protocol_date, protocol_location,
                ),
            )
            owner_id = cur.fetchone()[0]
            owner_id_map[key] = owner_id
        except Exception as e:
            print(f"❌ Błąd przy właścicielu '{key}': {e}")
            conn.rollback()

    print(f"✔️ Wstawiono {len(owner_id_map)} właścicieli")

    # --- ETAP 4: IMPORT OBIEKTÓW GEOGRAFICZNYCH ---
    print("\n--- Etap 4: Import obiektów geograficznych ---")

    # Deduplikacja - jeśli są duplikaty (numer, kategoria), weź ostatni
    objects_dict = {}
    for raw_key, data in parcel_data.items():
        # Parsowanie klucza: numer_kategoria (np. "50_budowlana") -> numer="50", kategoria="budowlana"
        # Lub stary format: numer (np. "50") -> numer="50", kategoria z data
        if '_' in raw_key:
            # Nowy format: numer_kategoria
            parts = raw_key.split('_', 1)  # Split tylko na pierwszym _
            raw_num = parts[0]
            kategoria = parts[1] if len(parts) > 1 else data.get("kategoria", "rolna")
        else:
            # Stary format: tylko numer
            raw_num = raw_key
            kategoria = data.get("kategoria") or "rolna"

        num_norm = norm(raw_num)
        wkt = get_wkt_from_geometry(data.get("geometria"), kategoria)

        # Klucz deduplikacji: (numer, kategoria)
        key = (num_norm, kategoria)
        objects_dict[key] = (num_norm, kategoria, wkt)

    # Konwersja słownika na listę
    objects_to_insert = list(objects_dict.values())
    total_objects = len(objects_to_insert)
    print(f"  Obiektów do przetworzenia: {total_objects}")

    # Masowe wstawianie z nadpisywaniem
    query = """
        INSERT INTO obiekty_geograficzne (nazwa_lub_numer, kategoria, geometria)
        VALUES %s
        ON CONFLICT (nazwa_lub_numer, kategoria)
        DO UPDATE SET geometria = EXCLUDED.geometria
        RETURNING id, nazwa_lub_numer, kategoria
    """
    # execute_values z fetch=True ZWRACA wyniki bezpośrednio
    results = execute_values(cur, query, objects_to_insert, fetch=True)

    object_id_map = {(num, kat): obj_id for obj_id, num, kat in results}
    print(f"✔️ Przetworzono wszystkie obiekty: {total_objects}")

    # --- ETAP 5: POWIĄZANIA WŁAŚCICIEL-DZIAŁKA ---
    print("\n--- Etap 5: Tworzenie powiązań ---")
    link_rows, seen = [], set()

    def add_link(owner_id, object_id, typ):
        """Dodaje unikalne powiązanie do listy."""
        key = (owner_id, object_id, typ)
        if key not in seen:
            link_rows.append((owner_id, object_id, typ, ""))
            seen.add(key)

    def ensure_object(num_norm: str, hint_building: bool):
        """
        Zapewnia istnienie obiektu w bazie, tworzy jeśli brak.

        WAŻNE: hint_building=True -> działka BUDOWLANA (nie dom!)
               Dom to osobna kategoria obsługiwana w sekcji powiązań domów.
        """
        if not num_norm:
            return None

        if hint_building:
            # hint_building=True -> szukamy DZIAŁKI BUDOWLANEJ
            # NIE mieszamy z domami - dom to osobna kategoria!
            wanted_cat = "budowlana"
            wanted_key = (num_norm, wanted_cat)

            # Sprawdź czy działka budowlana istnieje
            if wanted_key in object_id_map:
                return object_id_map[wanted_key]

            # Nie ma działki budowlanej - utwórz nową
        else:
            # hint_building=False -> szukamy działki GRUNTOWEJ (rolna, las, pastwisko, etc)
            # Priorytet: szczegółowe kategorie przed ogólnymi
            priority_categories = ['pastwisko', 'las', 'droga', 'rzeka', 'gruntowa']
            generic_categories = ['rolna']

            # Najpierw szukaj szczegółowych kategorii
            for cat in priority_categories:
                key = (num_norm, cat)
                if key in object_id_map:
                    return object_id_map[key]

            # Potem szukaj ogólnych kategorii
            for cat in generic_categories:
                key = (num_norm, cat)
                if key in object_id_map:
                    return object_id_map[key]

            # W ostateczności szukaj JAKIEJKOLWIEK kategorii gruntowej
            # (NIE budynek, NIE dom, NIE budowlana - to są osobne rzeczy)
            for (num, cat), obj_id in object_id_map.items():
                if num == num_norm and cat not in ['budynek', 'dom', 'budowlana', 'kapliczka', 'obiekt_specjalny']:
                    return obj_id

            wanted_cat = "rolna"

        # Utwórz nowy obiekt lub pobierz istniejący
        wanted_key = (num_norm, wanted_cat)
        cur.execute(
            """INSERT INTO obiekty_geograficzne
               (nazwa_lub_numer, kategoria, geometria)
               VALUES (%s, %s, NULL)
               ON CONFLICT (nazwa_lub_numer, kategoria) DO NOTHING
               RETURNING id""",
            (num_norm, wanted_cat),
        )
        result = cur.fetchone()

        if result:
            # Nowy obiekt został utworzony
            new_id = result[0]
        else:
            # Obiekt już istniał, pobierz jego ID
            cur.execute(
                """SELECT id FROM obiekty_geograficzne
                   WHERE nazwa_lub_numer = %s AND kategoria = %s""",
                (num_norm, wanted_cat)
            )
            new_id = cur.fetchone()[0]

        object_id_map[wanted_key] = new_id
        return new_id

    # Przetwarzanie własności
    for owner_key, details in owner_data.items():
        owner_id = owner_id_map.get(owner_key)
        if not owner_id:
            continue

        # Własność rzeczywista
        for key in ("realbuildingPlots", "realagriculturalPlots"):
            plots_list = details.get(key, [])
            for p in plots_list:
                plot_num = norm(p)
                obj_id = ensure_object(plot_num, key.startswith("realbuilding"))
                if obj_id:
                    add_link(owner_id, obj_id, "własność rzeczywista")

        # Własność z protokołu
        for key in ("buildingPlots", "agriculturalPlots"):
            for p in details.get(key, []):
                obj_id = ensure_object(norm(p), key.startswith("building"))
                if obj_id:
                    add_link(owner_id, obj_id, "własność z protokołu")
    
    # Wstaw powiązania
    if link_rows:
        execute_values(
            cur,
            """INSERT INTO dzialki_wlasciciele 
               (wlasciciel_id, obiekt_id, typ_posiadania, opis_udzialu) 
               VALUES %s
               ON CONFLICT (wlasciciel_id, obiekt_id, typ_posiadania) DO NOTHING""",
            link_rows
        )
        print(f"✔️ Utworzono {cur.rowcount} powiązań właściciel-działka")

    # --- ETAP 5.5: POWIĄZANIA DOMÓW ---
    print("\n--- Etap 5.5: Powiązania właściciel-dom ---")
    house_links = []
    
    # Mapa domów i budynków
    house_objects_map = {
        num: obj_id for (num, cat), obj_id in object_id_map.items() 
        if cat in ['dom', 'budynek']
    }

    for owner_key, details in owner_data.items():
        owner_id = owner_id_map.get(owner_key)
        house_number = details.get("houseNumber")

        if owner_id and house_number:
            house_object_id = house_objects_map.get(house_number)
            if house_object_id:
                key = (owner_id, house_object_id, "własność rzeczywista")
                if key not in seen:
                    house_links.append((owner_id, house_object_id, "własność rzeczywista", ""))
                    seen.add(key)

    if house_links:
        execute_values(
            cur,
            """INSERT INTO dzialki_wlasciciele 
               (wlasciciel_id, obiekt_id, typ_posiadania, opis_udzialu) 
               VALUES %s
               ON CONFLICT (wlasciciel_id, obiekt_id, typ_posiadania) DO NOTHING""",
            house_links
        )
        print(f"✔️ Utworzono {cur.rowcount} powiązań właściciel-dom")

    # --- ETAP 6: IMPORT DEMOGRAFII ---
    if demografia_data:
        print("\n--- Etap 6: Import danych demograficznych ---")
        demografia_to_insert = [
            (e.get("rok"), e.get("populacja_ogolem"), e.get("katolicy"), 
             e.get("zydzi"), e.get("inni"), e.get("opis"))
            for e in demografia_data
        ]
        execute_values(
            cur, 
            """INSERT INTO demografia 
               (rok, populacja_ogolem, katolicy, zydzi, inni, opis) 
               VALUES %s""", 
            demografia_to_insert
        )
        print(f"✔️ Wstawiono {len(demografia_to_insert)} wpisów")
        
    # --- ETAP 7: IMPORT DANYCH GENEALOGICZNYCH ---
    if genealogia_data:
        print("\n--- Etap 7: Import danych genealogicznych ---")

        # 7.1) Wstawianie osób + mapowanie json_id -> id w bazie
        json_id_to_db_id = {}

        # Zbuduj mapę numer_protokołu -> id_właściciela
        protocol_num_map = {}
        for key, v in owner_data.items():
            order_num = v.get("orderNumber")
            if order_num is not None:
                try:
                    protocol_num_map[int(order_num)] = owner_id_map.get(key)
                except (ValueError, TypeError):
                    pass

        print("  → Wstawianie osób...")
        for osoba in genealogia_data:
            # powiązanie z protokołem - obsługa różnych formatów:
            # 1) protokolKey jako tekst (np. "Adam_Sak") - nowy główny format
            # 2) protokolKey jako numer (np. 12) - stary numeryczny format
            # 3) protokol_klucz (stary format) - fallback dla kompatybilności wstecznej
            id_protokolu = None
            protokol_key = osoba.get("protokolKey")
            if protokol_key is not None:
                # Obsługa listy
                if isinstance(protokol_key, list):
                    protokol_key = protokol_key[0] if protokol_key else None
                if protokol_key is not None:
                    # Najpierw próbuj jako klucz tekstowy (np. "Adam_Sak")
                    id_protokolu = owner_id_map.get(str(protokol_key))
                    # Jeśli nie znaleziono, spróbuj jako numer
                    if id_protokolu is None:
                        try:
                            id_protokolu = protocol_num_map.get(int(protokol_key))
                        except (ValueError, TypeError):
                            pass
            
            # Fallback do starego formatu protokol_klucz (numeryczny)
            if id_protokolu is None:
                old_key = osoba.get("protokol_klucz")
                if old_key is not None:
                    if isinstance(old_key, list):
                        old_key = old_key[0] if old_key else None
                    if old_key is not None:
                        try:
                            id_protokolu = protocol_num_map.get(int(old_key))
                        except (ValueError, TypeError):
                            pass
            
            # Ostatni fallback do protocolKey jako klucz tekstowy (bardzo stary format)
            if id_protokolu is None:
                id_protokolu = owner_id_map.get(osoba.get("protocolKey"))

            # bezpieczne pobranie lat (rok może nie istnieć)
            birth = osoba.get("birthDate") or {}
            death = osoba.get("deathDate") or {}
            rok_urodzenia = birth.get("year")
            rok_smierci   = death.get("year")

            # INSERT osoby do tabeli osoby_genealogia
            cur.execute(
                """
                INSERT INTO osoby_genealogia
                    (json_id, imie_nazwisko, plec, numer_domu,
                    rok_urodzenia, rok_smierci, id_protokolu, uwagi)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    osoba.get("id"),
                    osoba.get("name"),
                    osoba.get("gender"),
                    osoba.get("houseNumber"),
                    rok_urodzenia,
                    rok_smierci,
                    id_protokolu,
                    osoba.get("notes"),
                ),
            )
            db_id = cur.fetchone()[0]
            json_id_to_db_id[osoba.get("id")] = db_id

        print(f"  ✔️ Wstawiono {len(json_id_to_db_id)} osób")

        # 7.2) Uzupełnienie relacji rodzicielskich (id_ojca / id_matki)
        print("  → Tworzenie relacji rodzicielskich...")
        for osoba in genealogia_data:
            db_id    = json_id_to_db_id.get(osoba.get("id"))
            id_ojca  = json_id_to_db_id.get(osoba.get("fatherId"))
            id_matki = json_id_to_db_id.get(osoba.get("motherId"))

            if db_id and (id_ojca or id_matki):
                cur.execute(
                    """
                    UPDATE osoby_genealogia
                    SET id_ojca = %s,
                        id_matki = %s
                    WHERE id = %s
                    """,
                    (id_ojca, id_matki, db_id),
                )

        # 7.3) Relacje małżeńskie (hybrydowo: rok/miesiąc/dzień lub pełna data, jeśli istnieją kolumny)
        print("  → Tworzenie relacji małżeńskich (hybrydowo)...")

        # 7.3.1) NAPRAWA STRUKTURY: Dodaj kolumny dat, jeśli nie istnieją
        print("  → Weryfikacja struktury tabeli malzenstwa...")
        cur.execute("""
            ALTER TABLE malzenstwa ADD COLUMN IF NOT EXISTS rok_slubu INT;
            ALTER TABLE malzenstwa ADD COLUMN IF NOT EXISTS miesiac_slubu INT;
            ALTER TABLE malzenstwa ADD COLUMN IF NOT EXISTS dzien_slubu INT;
            ALTER TABLE malzenstwa ADD COLUMN IF NOT EXISTS data_slubu TEXT;
        """)
        conn.commit()

        # Odśwież listę kolumn po aktualizacji
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name   = 'malzenstwa';
        """)
        _mcols     = {r[0] for r in cur.fetchall()}
        _HAS_YMD   = {'rok_slubu', 'miesiac_slubu', 'dzien_slubu'}.issubset(_mcols)
        _HAS_DATE  = 'data_slubu' in _mcols

        # 7.3.2) Słowniki pomocnicze
        persons_by_json_id = {}
        for o in genealogia_data:
            # zachowaj klucz jako str i int (na wszelki wypadek różnic typów)
            if 'id' in o:
                persons_by_json_id[str(o['id'])] = o
                try:
                    persons_by_json_id[int(o['id'])] = o
                except Exception:
                    pass

        # 7.3.3) Pomocnicze funkcje dat
        def _extract_marriage_date(source_person: dict, spouse_json_id):
            """
            Szuka daty ślubu w typowych polach:
            - source_person['marriages'] = [{spouseId, date}, ...]
            - source_person['marriageDates'] = {<spouseId>: <date>}
            - source_person['marriageDate'] = <date>
            Fallback: rok z 'notes'/'uwagi' (np. 'ślub 1844').
            Zwraca: dict|str|int|None (różne warianty; normalizuje _normalize_date_fields).
            """
            if not source_person:
                return None

            marriages = source_person.get('marriages', [])
            if isinstance(marriages, list):
                for m in marriages:
                    sid = m.get('spouseId') or m.get('spouse_id') or m.get('id')
                    if str(sid) == str(spouse_json_id):
                        # Priorytet dla weddingDate, potem date
                        val = m.get('weddingDate') or m.get('date')
                        if val is not None:
                            return val

            # Obsługa weddingDate bezpośrednio na obiekcie
            if source_person.get('weddingDate') is not None:
                return source_person.get('weddingDate')

            mdict = source_person.get('marriageDates')
            if isinstance(mdict, dict):
                val = mdict.get(str(spouse_json_id)) or mdict.get(spouse_json_id)
                if val is not None:
                    return val

            if source_person.get('marriageDate') is not None:
                return source_person.get('marriageDate')

            # Fallback: rok w treści notatek (TYLKO lata historyczne 1700-1882!)
            # WAŻNE: Pomijamy numery ID (np. "ID: # 20225" nie powinno dać roku 2022!)
            notes = source_person.get('notes') or source_person.get('uwagi') or ''
            if isinstance(notes, str):
                # Szukamy wzorców "ślub XXXX" lub "Ślub XXXX lp" - najpierw konkretne
                m = re.search(r'[Śś]lub\s+(1[78]\d{2})', notes, re.IGNORECASE)
                if m:
                    year = int(m.group(1))
                    if 1700 <= year <= 1882:
                        return year
                
                # Ogólny fallback - tylko lata 1700-1882, NIE pasujące do wzorca ID
                # Pomijamy jeśli przed rokiem jest "#" lub "ID" (oznacza numer ID osoby)
                for match in re.finditer(r'(?<![#])\b(1[78]\d{2})\b', notes):
                    year = int(match.group(1))
                    # Sprawdź czy przed liczbą nie ma "ID" lub "#"
                    start = match.start()
                    prefix = notes[max(0, start-5):start].lower()
                    if 'id' not in prefix and '#' not in prefix:
                        if 1700 <= year <= 1882:
                            return year

            return None

        def _normalize_date_fields(val):
            """
            Normalizuje wartość daty do (rok, miesiac, dzien, iso_date).
            Obsługiwane formaty:
            - dict {year, month?, day?}
            - int lub 'YYYY'
            - 'YYYY-MM'
            - 'YYYY-MM-DD'
            iso_date zwracamy tylko, gdy data jest kompletna i poprawna.
            """
            if val is None:
                return (None, None, None, None)

            y = m = d = None
            iso = None

            if isinstance(val, dict):
                y = val.get('year'); m = val.get('month'); d = val.get('day')
            elif isinstance(val, int):
                y = val
            elif isinstance(val, str):
                s = val.strip()
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
                    y, m, d = map(int, s.split('-')); iso = s
                elif re.fullmatch(r'\d{4}-\d{2}', s):
                    y, m = map(int, s.split('-'))
                elif re.fullmatch(r'\d{4}', s):
                    y = int(s)

            # bezpieczne zrzutowanie
            try:    y = int(y) if y is not None else None
            except: y = None
            try:    m = int(m) if m is not None else None
            except: m = None
            try:    d = int(d) if d is not None else None
            except: d = None

            if iso is None and y and m and d:
                try:
                    iso = date(y, m, d).isoformat()  # walidacja kalendarzowa
                except Exception:
                    iso = None

            return (y, m, d, iso)

        # 7.3.4) Zbierz unikalne pary małżeństw i przygotuj dane do INSERT
        seen_pairs = set()
        values = []

        for osoba in genealogia_data:
            json_id_1 = osoba.get('id')
            db_id_1   = json_id_to_db_id.get(json_id_1) \
                    or json_id_to_db_id.get(str(json_id_1))

            if not db_id_1:
                continue

            for spouse_json_id in osoba.get('spouseIds', []):
                db_id_2 = json_id_to_db_id.get(spouse_json_id) \
                    or json_id_to_db_id.get(str(spouse_json_id))
                if not db_id_2:
                    continue

                # para uporządkowana → brak duplikatów (A,B) vs (B,A)
                pair = tuple(sorted((int(db_id_1), int(db_id_2))))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                # Spróbuj znaleźć datę ślubu: najpierw po stronie 'osoba', potem po stronie małżonka
                dval = _extract_marriage_date(osoba, spouse_json_id)
                if not dval:
                    other = persons_by_json_id.get(spouse_json_id) or persons_by_json_id.get(str(spouse_json_id))
                    dval = _extract_marriage_date(other, json_id_1)

                y, m, d, iso = _normalize_date_fields(dval)

                if _HAS_YMD and _HAS_DATE:
                    values.append((pair[0], pair[1], y, m, d, iso))
                elif _HAS_YMD:
                    values.append((pair[0], pair[1], y, m, d))
                elif _HAS_DATE:
                    values.append((pair[0], pair[1], iso))
                else:
                    values.append((pair[0], pair[1]))

        # 7.3.5) INSERT do 'malzenstwa' – wariant zależny od dostępnych kolumn
        if not values:
            print("  (brak małżeństw do wstawienia)")
        else:
            if _HAS_YMD and _HAS_DATE:
                sql = """
                    INSERT INTO malzenstwa
                        (malzonek1_id, malzonek2_id, rok_slubu, miesiac_slubu, dzien_slubu, data_slubu)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                """
            elif _HAS_YMD:
                sql = """
                    INSERT INTO malzenstwa
                        (malzonek1_id, malzonek2_id, rok_slubu, miesiac_slubu, dzien_slubu)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                """
            elif _HAS_DATE:
                sql = """
                    INSERT INTO malzenstwa
                        (malzonek1_id, malzonek2_id, data_slubu)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                """
            else:
                sql = """
                    INSERT INTO malzenstwa
                        (malzonek1_id, malzonek2_id)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                """

            execute_values(cur, sql, values)
            print(f"  ✔️ Wstawiono {len(values)} małżeństw")

    # Zatwierdź transakcję
    conn.commit()
    print("\n" + "=" * 50)
    print("✅  MIGRACJA ZAKOŃCZONA POMYŚLNIE")
    print("=" * 50)

except FileNotFoundError as e:
    print(f"\n❌ BŁĄD: Nie znaleziono pliku!")
    print(f"   Brakujący plik: {e.filename}")
    print(f"   Upewnij się, że pliki JSON są w folderze 'backup'")
except Exception as e:
    print(f"\n❌ BŁĄD: {e}")
    if conn:
        conn.rollback()
        print("   → Zmiany wycofane")
finally:
    # Zamknij połączenie
    if conn:
        cur.close()
        conn.close()
        print("\nPołączenie z bazą zamknięte")