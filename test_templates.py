#!/usr/bin/env python3
"""Test sprawdzający system szablonów strony głównej"""

import os
import sys
import sqlite3
import shutil

# Konfiguracja ścieżek
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAUNCHER_DIR = os.path.join(BASE_DIR, "launcher")
HOMEPAGE_DIR = os.path.join(BASE_DIR, "strona_glowna")
TEMPLATES_DIR = os.path.join(HOMEPAGE_DIR, "szablony")
BACKUP_FOLDER = os.path.join(BASE_DIR, "backup")
LOCATIONS_DB_PATH = os.path.join(LAUNCHER_DIR, "test_locations_templates.db")

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

def get_active_location():
    """Zwraca aktywną miejscowość."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM locations WHERE active = 1")
    result = cursor.fetchone()
    conn.close()
    return result

def set_active_location(location_id):
    """Ustawia miejscowość jako aktywną."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE locations SET active = 0")
    cursor.execute("UPDATE locations SET active = 1 WHERE id = ?", (location_id,))
    conn.commit()
    conn.close()

def add_location(name, full_name, powiat="", region=""):
    """Dodaje nową miejscowość."""
    init_locations_db()

    location_folder = os.path.join(BACKUP_FOLDER, name)
    os.makedirs(location_folder, exist_ok=True)

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

def get_available_templates():
    """Zwraca listę dostępnych szablonów."""
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
    """Aplikuje wybrany szablon."""
    template_path = os.path.join(TEMPLATES_DIR, template_name, "index.html")
    target_path = os.path.join(HOMEPAGE_DIR, "index_test.html")  # Zapisz jako test

    if not os.path.exists(template_path):
        print(f"❌ Szablon '{template_name}' nie istnieje")
        return False

    try:
        if template_name == "standardowy":
            active_location = get_active_location()
            if not active_location:
                print("❌ Brak aktywnej miejscowości")
                return False

            location_name = active_location[1]
            location_full_name = active_location[2] or location_name
            location_powiat = active_location[3] or "Powiat"
            location_region = active_location[4] or "Region"

            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()

            content = content.replace('{{MIEJSCOWOSC}}', location_name)
            content = content.replace('{{MIEJSCOWOSC_PELNA}}', location_full_name)
            content = content.replace('{{POWIAT}}', location_powiat)
            content = content.replace('{{REGION}}', location_region)

            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ Zastosowano szablon 'standardowy' dla miejscowości: {location_full_name}")
        else:
            shutil.copy2(template_path, target_path)
            print(f"✅ Zastosowano szablon: {template_name}")

        return True

    except Exception as e:
        print(f"❌ Błąd podczas aplikowania szablonu: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==================== Testy ====================

print("🧪 Test 1: Sprawdzenie dostępnych szablonów")
print("=" * 60)

templates = get_available_templates()
print(f"Znalezione szablony: {templates}")

if "standardowy" in templates:
    print("✅ Szablon 'standardowy' istnieje")
else:
    print("❌ BŁĄD: Brak szablonu 'standardowy'")
    exit(1)

if "praca_inzynierska" in templates:
    print("✅ Szablon 'praca_inzynierska' istnieje")
else:
    print("❌ BŁĄD: Brak szablonu 'praca_inzynierska'")
    exit(1)

print()
print("🧪 Test 2: Aplikowanie szablonu 'praca_inzynierska'")
print("=" * 60)

success = apply_homepage_template("praca_inzynierska")
if success:
    print("✅ Szablon 'praca_inzynierska' aplikowany pomyślnie")
else:
    print("❌ BŁĄD: Nie udało się zaaplikować szablonu")
    exit(1)

print()
print("🧪 Test 3: Aplikowanie szablonu 'standardowy' z miejscowością")
print("=" * 60)

# Dodaj testową miejscowość
location_id = add_location("Tarnow", "Tarnów", "Powiat Tarnowski", "Małopolska")
set_active_location(location_id)
print(f"✅ Dodano testową miejscowość: Tarnów")

success = apply_homepage_template("standardowy")
if success:
    print("✅ Szablon 'standardowy' aplikowany pomyślnie")

    # Sprawdź czy placeholdery zostały zastąpione
    with open(os.path.join(HOMEPAGE_DIR, "index_test.html"), 'r', encoding='utf-8') as f:
        content = f.read()

    if "Tarnów" in content and "Powiat Tarnowski" in content and "Małopolska" in content:
        print("✅ Placeholdery zostały poprawnie zastąpione")
    else:
        print("❌ BŁĄD: Placeholdery nie zostały zastąpione")
        exit(1)

    if "{{MIEJSCOWOSC}}" not in content and "{{POWIAT}}" not in content:
        print("✅ Brak pozostałych placeholderów")
    else:
        print("❌ BŁĄD: Pozostały niezastąpione placeholdery")
        exit(1)
else:
    print("❌ BŁĄD: Nie udało się zaaplikować szablonu")
    exit(1)

# Cleanup
print()
print("🧹 Czyszczenie...")
if os.path.exists(LOCATIONS_DB_PATH):
    os.remove(LOCATIONS_DB_PATH)
    print("✅ Usunięto testową bazę danych")

if os.path.exists(os.path.join(BACKUP_FOLDER, "Tarnow")):
    shutil.rmtree(os.path.join(BACKUP_FOLDER, "Tarnow"))
    print("✅ Usunięto testowy folder miejscowości")

if os.path.exists(os.path.join(HOMEPAGE_DIR, "index_test.html")):
    os.remove(os.path.join(HOMEPAGE_DIR, "index_test.html"))
    print("✅ Usunięto testowy plik index_test.html")

print()
print("=" * 60)
print("✅ ✅ ✅ WSZYSTKIE TESTY PRZESZŁY POMYŚLNIE! ✅ ✅ ✅")
print("=" * 60)
print()
print("System szablonów działa poprawnie:")
print("  - Szablon 'praca_inzynierska' - kopiuje oryginalną stronę")
print("  - Szablon 'standardowy' - dynamicznie podstawia dane miejscowości")
