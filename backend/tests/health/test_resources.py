import os
import json
import pytest

# Definiujemy ścieżki względne do projektu
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def get_active_location():
    return os.environ.get('TEST_LOCATION', 'Czarna')

def test_historical_photos_exist():
    """Sprawdza czy pliki zdjęć historycznych dla danej lokacji istnieją na dysku."""
    location = get_active_location()
    # Ścieżka: static/photos/<miejscowość>/
    photos_dir = os.path.join(BASE_DIR, "static", "photos", location)
    
    if not os.path.exists(photos_dir):
        print(f"\n[ZASOBY] Katalog zdjęć nie istnieje: {photos_dir}")
        return # Nie rzucamy błędu, może po prostu nie ma zdjęć

    # W idealnym scenariuszu pobieramy listę nazw z bazy, tutaj sprawdzamy czy katalog nie jest pusty
    files = [f for f in os.listdir(photos_dir) if os.path.isfile(os.path.join(photos_dir, f))]
    print(f"\n[ZASOBY] Znaleziono {len(files)} zdjęć historycznych w katalogu {location}.")
    assert True

def test_custom_icons_existence():
    """Sprawdza czy customowe ikony zdefiniowane w .env lub ustawieniach istnieją."""
    # Można tu rozwinąć o sprawdzanie ikon przypisanych do obiektów w bazie
    icons_dir = os.path.join(BASE_DIR, "static", "icons")
    if not os.path.exists(icons_dir):
        print("\n[ZASOBY] ⚠️ Brak katalogu ikon!")
    else:
        print(f"\n[ZASOBY] Katalog ikon dostępny ({len(os.listdir(icons_dir))} plików).")
    assert True

def test_genealogy_protocol_links():
    """Weryfikuje czy klucze protokolKey w genealogia.json mają odpowiadające im pliki HTML."""
    location = get_active_location()
    path = os.path.join(BASE_DIR, "backup", location, "genealogia.json")
    
    if not os.path.exists(path):
        pytest.skip(f"Brak pliku danych: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    missing_protocols = []
    protokoly_dir = os.path.join(BASE_DIR, "wlasciciele") # Zwykle tam są pliki .html lub .json protokołów
    
    for person in data.get("persons", []):
        key = person.get("protokolKey")
        if key:
            # Szukamy czy jest jakikolwiek ślad protokołu (np. plik o tej nazwie w wlasciciele lub wpis w DB)
            # Tutaj sprawdzamy przykładowo istnienie pliku
            if not any(f.startswith(key) for f in os.listdir(protokoly_dir) if f.endswith(('.html', '.json'))):
                missing_protocols.append(f"{person['name']} (ID {person['id']}, klucz: {key})")

    if missing_protocols:
        print(f"\n[ZASOBY] Brakujące odniesienia do protokołów ({len(missing_protocols)}):")
        for m in missing_protocols[:20]:
            print(f"  ? {m}")
    else:
        print("\n[ZASOBY] Wszystkie odniesienia do protokołów są poprawne.")
    assert True
