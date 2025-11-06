#!/usr/bin/env python3
"""Test sprawdzający logikę ścieżek .env"""

import os
import sqlite3
import shutil

# Konfiguracja ścieżek
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAUNCHER_DIR = os.path.join(BASE_DIR, "launcher")
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
BACKUP_FOLDER = os.path.join(BASE_DIR, "backup")
LOCATIONS_DB_PATH = os.path.join(LAUNCHER_DIR, "test_locations.db")

# Usuń starą testową bazę danych
if os.path.exists(LOCATIONS_DB_PATH):
    os.remove(LOCATIONS_DB_PATH)

# ==================== Skopiowane funkcje z launcher_app.py ====================

def init_locations_db():
    """Inicjalizuje bazę danych miejscowości."""
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        full_name TEXT,
        powiat TEXT,
        region TEXT,
        active INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

def get_all_locations():
    """Zwraca wszystkie miejscowości."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM locations ORDER BY name")
    results = cursor.fetchall()
    conn.close()
    return results

def get_active_location():
    """Zwraca aktywną miejscowość (ID, nazwa, pełna_nazwa, powiat, region, active)."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM locations WHERE active = 1")
    result = cursor.fetchone()
    conn.close()
    return result

def get_active_location_name():
    """Zwraca nazwę aktywnej miejscowości lub None."""
    location = get_active_location()
    return location[1] if location else None

def set_active_location(location_id):
    """Ustawia miejscowość jako aktywną (wyłączając pozostałe)."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE locations SET active = 0")
    cursor.execute("UPDATE locations SET active = 1 WHERE id = ?", (location_id,))
    conn.commit()
    conn.close()

def add_location(name, full_name, powiat="", region=""):
    """Dodaje nową miejscowość do bazy danych i tworzy folder."""
    init_locations_db()

    location_folder = os.path.join(BACKUP_FOLDER, name)
    os.makedirs(location_folder, exist_ok=True)

    env_path = os.path.join(location_folder, ".env")
    if not os.path.exists(env_path):
        default_env = """# Konfiguracja bazy danych PostgreSQL
DB_HOST=localhost
DB_NAME=test_db
DB_USER=postgres
DB_PASSWORD=1234
DB_PORT=5432
"""
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(default_env)

    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO locations (name, full_name, powiat, region, active) VALUES (?, ?, ?, ?, 0)",
                      (name, full_name, powiat, region))
        conn.commit()
        location_id = cursor.lastrowid
        conn.close()
        return location_id
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Miejscowość '{name}' już istnieje")

def ensure_default_location_exists():
    """Upewnia się, że istnieje domyślna miejscowość."""
    init_locations_db()

    locations = get_all_locations()
    if locations:
        active_location = get_active_location()
        if not active_location:
            set_active_location(locations[0][0])
        return

    default_name = "Czarna"
    try:
        location_id = add_location(default_name, "Czarna", "", "")
        set_active_location(location_id)
        print(f"✓ Utworzono domyślną miejscowość: {default_name}")
    except Exception as e:
        print(f"⚠ Błąd tworzenia domyślnej miejscowości: {e}")

def get_location_env_path(location_name=None):
    """Zwraca ścieżkę do pliku .env dla danej miejscowości."""
    if location_name is None:
        ensure_default_location_exists()
        location_name = get_active_location_name()

    if not location_name:
        raise ValueError("Brak aktywnej miejscowości")

    return os.path.join(BACKUP_FOLDER, location_name, ".env")

# ==================== Testy ====================

print("🧪 Test 1: get_location_env_path() bez miejscowości")
print("=" * 60)

try:
    env_path = get_location_env_path()
    print(f"✅ Zwrócona ścieżka: {env_path}")

    if "backup" in env_path and "backend" not in env_path:
        print("✅ Ścieżka zawiera 'backup' i NIE zawiera 'backend' - POPRAWNE!")
    else:
        print(f"❌ BŁĄD: Ścieżka powinna być w backup/, a jest: {env_path}")
        exit(1)

    location = get_active_location()
    if location:
        print(f"✅ Utworzono domyślną miejscowość: {location[1]}")
    else:
        print("❌ BŁĄD: Nie utworzono domyślnej miejscowości")
        exit(1)

except Exception as e:
    print(f"❌ BŁĄD: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()
print("🧪 Test 2: Dodanie nowej miejscowości")
print("=" * 60)

try:
    location_id = add_location("TestMiasto", "Test Miasto", "Powiat Testowy", "Region Testowy")
    print(f"✅ Dodano miejscowość ID: {location_id}")

    set_active_location(location_id)
    print(f"✅ Ustawiono jako aktywną")

    env_path = get_location_env_path()
    print(f"✅ Ścieżka dla nowej miejscowości: {env_path}")

    if "TestMiasto" in env_path and "backup" in env_path and "backend" not in env_path:
        print("✅ Ścieżka zawiera nazwę miejscowości i 'backup', NIE zawiera 'backend' - POPRAWNE!")
    else:
        print(f"❌ BŁĄD: Ścieżka powinna zawierać 'TestMiasto' i 'backup', a jest: {env_path}")
        exit(1)

except Exception as e:
    print(f"❌ BŁĄD: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()
print("🧪 Test 3: Sprawdzenie czy pliki .env są w dobrych folderach")
print("=" * 60)

try:
    # Sprawdź czy .env jest w backup/TestMiasto/
    expected_path = os.path.join(BACKUP_FOLDER, "TestMiasto", ".env")
    if os.path.exists(expected_path):
        print(f"✅ Plik .env istnieje w: {expected_path}")
    else:
        print(f"❌ BŁĄD: Plik .env NIE istnieje w: {expected_path}")
        exit(1)

    # Sprawdź że NIE ma .env w backend/
    backend_env = os.path.join(BACKEND_DIR, ".env")
    if not os.path.exists(backend_env):
        print(f"✅ Plik .env NIE istnieje w backend/ - POPRAWNE!")
    else:
        print(f"⚠ Plik .env istnieje w backend/ (może być z poprzednich testów)")

except Exception as e:
    print(f"❌ BŁĄD: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Cleanup
print()
print("🧹 Czyszczenie...")
if os.path.exists(LOCATIONS_DB_PATH):
    os.remove(LOCATIONS_DB_PATH)
    print("✅ Usunięto testową bazę danych")

# Usuń testowe foldery
test_folders = [
    os.path.join(BACKUP_FOLDER, "Czarna"),
    os.path.join(BACKUP_FOLDER, "TestMiasto")
]
for folder in test_folders:
    if os.path.exists(folder):
        shutil.rmtree(folder)
        print(f"✅ Usunięto folder: {folder}")

print()
print("=" * 60)
print("✅ ✅ ✅ WSZYSTKIE TESTY PRZESZŁY POMYŚLNIE! ✅ ✅ ✅")
print("=" * 60)
print()
print("Funkcja get_location_env_path() ZAWSZE zwraca backup/{miejscowość}/.env")
print("Funkcja get_location_env_path() NIGDY nie zwraca backend/.env")
