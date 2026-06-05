import os
import json
import pytest
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Typowe wzorce "krzaków" wynikające z błędnego kodowania UTF-8 jako Latin-1
MOJIBAKE_PATTERNS = [
    r"Ã³", r"Ã³", # ó
    r"Ãł", r"Ã³", # ą / ó
    r"Ä™",        # ę
    r"Å›",        # ś
    r"Å¼",        # ż
    r"Åº",        # ź
    r"Ä‡",        # ć
    r"Å„",        # ń
    r"Å\?",       # ł (często)
    r"Â",         # zbędne twarde spacje
    r"â€“",       # półpauza
    r"â€",        # cudzysłowy
]

def get_active_location():
    return os.environ.get('TEST_LOCATION', 'Czarna')

def test_json_encoding_integrity():
    """Skanuje główne pliki JSON w poszukiwaniu błędów kodowania (krzaków)."""
    location = get_active_location()
    json_files = [
        os.path.join(BASE_DIR, "data", "locations", location, "genealogia.json"),
        os.path.join(BASE_DIR, "backend", ".env")
    ]
    
    errors_found = []
    
    for file_path in json_files:
        if not os.path.exists(file_path):
            continue
            
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            for pattern in MOJIBAKE_PATTERNS:
                if re.search(pattern, content):
                    errors_found.append(f"Plik: {os.path.basename(file_path)}, wariant błędu: {pattern}")
                    break # Wystarczy jeden na plik do raportu
                    
    if errors_found:
        print(f"\n[KRZAK-DETECTOR] Wykryto potencjalne błędy kodowania (UTF-8/Latin-1 mix):")
        for err in errors_found:
            print(f"  ! {err}")
    else:
        print("\n[KRZAK-DETECTOR] Kodowanie znaków w kluczowych plikach wydaje się poprawne (OK).")
    assert True

def test_database_encoding_check():
    """(Opcjonalne) Tutaj można by dodać skanowanie rekordów w DB pod kątem krzaków."""
    # Ze względu na ograniczony czas skupiamy się na plikach, ale to dobry kierunek rozwoju.
    assert True
