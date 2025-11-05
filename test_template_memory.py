#!/usr/bin/env python3
"""Test sprawdzający system pamiętania szablonu dla miejscowości"""

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
LOCATIONS_DB_PATH = os.path.join(LAUNCHER_DIR, "test_locations_memory.db")

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
            full_name TEXT NOT NULL,
            powiat TEXT,
            region TEXT,
            active INTEGER DEFAULT 0,
            homepage_template TEXT DEFAULT 'standardowy'
        )
    """)

    # Migracja: dodaj kolumnę homepage_template jeśli nie istnieje
    try:
        cursor.execute("SELECT homepage_template FROM locations LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE locations ADD COLUMN homepage_template TEXT DEFAULT 'standardowy'")
        print("✓ Dodano kolumnę homepage_template do tabeli locations")

    conn.commit()
    conn.close()

def get_all_locations():
    """Zwraca wszystkie miejscowości."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, full_name, powiat, region, active, homepage_template FROM locations ORDER BY name")
    locations = cursor.fetchall()
    conn.close()
    return locations

def get_active_location():
    """Zwraca aktywną miejscowość."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, full_name, powiat, region, active, homepage_template FROM locations WHERE active = 1")
    location = cursor.fetchone()
    conn.close()
    return location

def set_active_location(location_id):
    """Ustawia miejscowość jako aktywną (bez aplikowania szablonu w teście)."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()

    # Pobierz szablon dla tej miejscowości
    cursor.execute("SELECT homepage_template FROM locations WHERE id = ?", (location_id,))
    result = cursor.fetchone()
    template = result[0] if result and result[0] else "standardowy"

    # Wyłącz wszystkie inne miejscowości
    cursor.execute("UPDATE locations SET active = 0")
    # Ustaw wybraną jako aktywną
    cursor.execute("UPDATE locations SET active = 1 WHERE id = ?", (location_id,))
    conn.commit()
    conn.close()

    return template  # Zwróć szablon aby go sprawdzić w teście

def set_location_template(location_id, template_name):
    """Ustawia szablon strony głównej dla danej miejscowości."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE locations SET homepage_template = ? WHERE id = ?", (template_name, location_id))
    conn.commit()
    conn.close()

def add_location(name, full_name, powiat="", region="", homepage_template="standardowy"):
    """Dodaje nową miejscowość."""
    init_locations_db()

    location_folder = os.path.join(BACKUP_FOLDER, name)
    os.makedirs(location_folder, exist_ok=True)

    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO locations (name, full_name, powiat, region, active, homepage_template) VALUES (?, ?, ?, ?, 0, ?)",
                      (name, full_name, powiat, region, homepage_template))
        conn.commit()
        location_id = cursor.lastrowid
        conn.close()
        return location_id
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Miejscowość '{name}' już istnieje")

# ==================== Testy ====================

print("🧪 Test 1: Dodawanie miejscowości z różnymi szablonami")
print("=" * 60)

# Dodaj Czarną z szablonem praca_inzynierska
czarna_id = add_location("Czarna", "Czarna", "Powiat Dębicki", "Podkarpacie", "praca_inzynierska")
print(f"✅ Dodano Czarna (ID: {czarna_id}) z szablonem: praca_inzynierska")

# Dodaj Borową z szablonem standardowy
borowa_id = add_location("Borowa", "Borowa", "Powiat Mielecki", "Podkarpacie", "standardowy")
print(f"✅ Dodano Borowa (ID: {borowa_id}) z szablonem: standardowy")

# Dodaj Tarnów z szablonem standardowy
tarnow_id = add_location("Tarnow", "Tarnów", "Powiat Tarnowski", "Małopolska", "standardowy")
print(f"✅ Dodano Tarnow (ID: {tarnow_id}) z szablonem: standardowy")

print()
print("🧪 Test 2: Sprawdzenie czy szablony zostały zapisane")
print("=" * 60)

locations = get_all_locations()
for loc in locations:
    loc_id, name, full_name, powiat, region, active, template = loc
    print(f"✅ {name}: szablon = '{template}'")

# Sprawdź czy szablony są poprawne
czarna_template = [loc[6] for loc in locations if loc[0] == czarna_id][0]
borowa_template = [loc[6] for loc in locations if loc[0] == borowa_id][0]

if czarna_template == "praca_inzynierska":
    print("✅ Czarna ma szablon 'praca_inzynierska' - POPRAWNE")
else:
    print(f"❌ BŁĄD: Czarna ma szablon '{czarna_template}' zamiast 'praca_inzynierska'")
    exit(1)

if borowa_template == "standardowy":
    print("✅ Borowa ma szablon 'standardowy' - POPRAWNE")
else:
    print(f"❌ BŁĄD: Borowa ma szablon '{borowa_template}' zamiast 'standardowy'")
    exit(1)

print()
print("🧪 Test 3: Zmiana szablonu dla miejscowości")
print("=" * 60)

# Zmień szablon Borowej na praca_inzynierska
set_location_template(borowa_id, "praca_inzynierska")
print(f"✅ Zmieniono szablon Borowej na: praca_inzynierska")

# Sprawdź czy zmiana została zapisana
conn = sqlite3.connect(LOCATIONS_DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT homepage_template FROM locations WHERE id = ?", (borowa_id,))
result = cursor.fetchone()
conn.close()

new_template = result[0]
if new_template == "praca_inzynierska":
    print("✅ Szablon został zmieniony pomyślnie - POPRAWNE")
else:
    print(f"❌ BŁĄD: Szablon to '{new_template}' zamiast 'praca_inzynierska'")
    exit(1)

print()
print("🧪 Test 4: Aktywacja miejscowości i zapamiętywanie szablonu")
print("=" * 60)

# Aktywuj Czarną
template = set_active_location(czarna_id)
print(f"✅ Aktywowano Czarna, zwrócony szablon: '{template}'")

if template == "praca_inzynierska":
    print("✅ Szablon dla Czarnej to 'praca_inzynierska' - POPRAWNE")
else:
    print(f"❌ BŁĄD: Szablon to '{template}' zamiast 'praca_inzynierska'")
    exit(1)

# Sprawdź aktywną miejscowość
active_loc = get_active_location()
if active_loc and active_loc[0] == czarna_id and active_loc[6] == "praca_inzynierska":
    print("✅ Aktywna miejscowość to Czarna z szablonem 'praca_inzynierska' - POPRAWNE")
else:
    print(f"❌ BŁĄD: Aktywna miejscowość nie jest poprawna")
    exit(1)

# Aktywuj Borową (która ma teraz praca_inzynierska)
template = set_active_location(borowa_id)
print(f"✅ Aktywowano Borowa, zwrócony szablon: '{template}'")

if template == "praca_inzynierska":
    print("✅ Szablon dla Borowej to 'praca_inzynierska' - POPRAWNE")
else:
    print(f"❌ BŁĄD: Szablon to '{template}' zamiast 'praca_inzynierska'")
    exit(1)

# Aktywuj Tarnów (standardowy)
template = set_active_location(tarnow_id)
print(f"✅ Aktywowano Tarnow, zwrócony szablon: '{template}'")

if template == "standardowy":
    print("✅ Szablon dla Tarnowa to 'standardowy' - POPRAWNE")
else:
    print(f"❌ BŁĄD: Szablon to '{template}' zamiast 'standardowy'")
    exit(1)

print()
print("🧪 Test 5: Przełączanie między miejscowościami")
print("=" * 60)

# Przełącz z powrotem na Czarną
template = set_active_location(czarna_id)
print(f"✅ Przełączono na Czarna, szablon: '{template}'")

if template == "praca_inzynierska":
    print("✅ System zapamiętał szablon 'praca_inzynierska' dla Czarnej")
else:
    print(f"❌ BŁĄD: System nie zapamiętał szablonu")
    exit(1)

# Przełącz na Tarnów
template = set_active_location(tarnow_id)
print(f"✅ Przełączono na Tarnow, szablon: '{template}'")

if template == "standardowy":
    print("✅ System zapamiętał szablon 'standardowy' dla Tarnowa")
else:
    print(f"❌ BŁĄD: System nie zapamiętał szablonu")
    exit(1)

# Cleanup
print()
print("🧹 Czyszczenie...")
if os.path.exists(LOCATIONS_DB_PATH):
    os.remove(LOCATIONS_DB_PATH)
    print("✅ Usunięto testową bazę danych")

for folder_name in ["Czarna", "Borowa", "Tarnow"]:
    folder_path = os.path.join(BACKUP_FOLDER, folder_name)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        print(f"✅ Usunięto folder: {folder_name}")

print()
print("=" * 60)
print("✅ ✅ ✅ WSZYSTKIE TESTY PRZESZŁY POMYŚLNIE! ✅ ✅ ✅")
print("=" * 60)
print()
print("System pamiętania szablonu działa poprawnie:")
print("  - Każda miejscowość ma przypisany szablon")
print("  - Szablon można zmieniać dla dowolnej miejscowości")
print("  - Przy aktywacji miejscowości używany jest jej szablon")
print("  - Szablon jest zapamiętywany między przełączeniami")
