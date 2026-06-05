import os
import json
import pytest
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def get_active_location():
    return os.environ.get('TEST_LOCATION', 'Czarna')

def test_backup_folder_exists():
    """Sprawdza czy katalog backup w ogóle istnieje."""
    backup_path = os.path.join(BASE_DIR, "data", "locations")
    if not os.path.exists(backup_path):
        pytest.fail(f"❌ Katalog BACKUP nie istnieje w lokalizacji: {backup_path}")
    print(f"\n🏰 Katalog backup znaleziony: {backup_path}")

def test_location_data_files_present():
    """Sprawdza czy kluczowe pliki dla aktywnej lokacji są obecne."""
    location = get_active_location()
    loc_path = os.path.join(BASE_DIR, "data", "locations", location)
    
    if not os.path.exists(loc_path):
        pytest.fail(f"❌ Brak folderu danych dla miejscowości: {location}")
        
    required_files = ["genealogia.json", ".env"] # Podstawowe pliki które MUSZĄ być
    missing = []
    for f in required_files:
        if not os.path.exists(os.path.join(loc_path, f)):
            missing.append(f)
            
    if missing:
        pytest.fail(f"❌ W folderze {location} brakuje plików: {', '.join(missing)}")
    
    print(f"\n🏰 Wszystkie wymagane pliki dla {location} są na miejscu.")

def test_backup_file_integrity():
    """Weryfikuje czy pliki danych nie są uszkodzone (czy można je sparsować)."""
    location = get_active_location()
    path = os.path.join(BASE_DIR, "data", "locations", location, "genealogia.json")
    
    # 1. Sprawdzenie rozmiaru
    size = os.path.getsize(path)
    if size < 100: # Za mały na sensowne dane
        print(f"\n🏰 ⚠️ OSTRZEŻENIE: Plik genealogia.json jest podejrzanie mały ({size} bajtów).")
    
    # 2. Sprawdzenie struktury JSON
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                 pytest.fail("❌ Struktura genealogia.json jest niepoprawna (oczekiwano słownika).")
            print(f"🏰 Struktura JSON poprawna. Liczba osób: {len(data.get('persons', []))}")
    except json.JSONDecodeError as e:
        pytest.fail(f"❌ Plik genealogia.json jest USZKODZONY: {e}")
    except UnicodeDecodeError:
        pytest.fail("❌ Błąd kodowania w genealogia.json (nie jest to poprawny UTF-8).")

def test_recent_modification():
    """Sprawdza czy dane były ostatnio modyfikowane (czy backup jest 'żywy')."""
    location = get_active_location()
    path = os.path.join(BASE_DIR, "data", "locations", location, "genealogia.json")
    
    mtime = os.path.getmtime(path)
    diff_days = (time.time() - mtime) / (24 * 3600)
    
    if diff_days > 30:
        print(f"\n🏰 ⚠️ OSTRZEŻENIE: Dane nie były zmieniane od {int(diff_days)} dni.")
    else:
        print(f"\n🏰 Dane są aktualne (ostatnia zmiana {int(diff_days)} dni temu).")
    assert True
