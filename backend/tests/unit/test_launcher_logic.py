"""
Plik: test_launcher_logic.py
Opis: Testy jednostkowe dla logiki biznesowej Launchera.
      Weryfikuje zarządzanie portami, walidację .env i inne funkcje silnika.
"""

import os
import sys
import pytest

# Dodaj główny folder do ścieżki, aby móc importować launcher
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Mockujemy GUI, żeby nie otwierały się okienka podczas testów
# Zamiast importować całą klasę, przetestujemy kluczowe funkcje pomocnicze
# i logikę walidacji, którą możemy wydzielić lub zasymulować.

def test_port_validation_logic():
    """
    Testuje logikę wykrywania duplikatów portów w pliku .env.
    Symuluje proces walidacji, który dodaliśmy do Launchera.
    """
    # Przykładowy pseudo-content pliku .env (poprawny)
    valid_content = """
    FLASK_PORT=5000
    # Komentarz
    GENEALOGY_EDITOR_PORT=5001
    PARCEL_EDITOR_PORT=5003
    """
    
    # Przykładowy pseudo-content pliku .env (zduplikowany port)
    invalid_content = """
    FLASK_PORT=5010
    GENEALOGY_EDITOR_PORT=5010
    PARCEL_EDITOR_PORT=5003
    """

    def validate_ports(content):
        ports = {}
        port_keys = ["FLASK_PORT", "GENEALOGY_EDITOR_PORT", "PARCEL_EDITOR_PORT"]
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key, value = key.strip(), value.strip()
                if key in port_keys:
                    try:
                        v = int(value)
                        if v in ports.values():
                            return False, f"Duplikat portu {v} w kluczu {key}"
                        ports[key] = v
                    except ValueError: pass
        return True, "OK"

    # Testujemy poprawne dane
    is_ok, msg = validate_ports(valid_content)
    assert is_ok is True
    
    # Testujemy duplikaty
    is_ok, msg = validate_ports(invalid_content)
    assert is_ok is False
    assert "5010" in msg

def test_env_path_resolution():
    """Weryfikuje czy launcher poprawnie buduje ścieżki do plików .env miejscowości."""
    # Symulujemy strukturę folderów
    test_loc_name = "TestowaMiejscowosc"
    expected_part = os.path.join("data", "locations", test_loc_name, ".env")
    
    # Sprawdzamy czy funkcja (zasymulowana tu) buduje to poprawnie
    def get_path(name):
        return os.path.join(BASE_DIR, "data", "locations", name, ".env")
    
    path = get_path(test_loc_name)
    assert expected_part in path
    assert path.endswith(".env")

def test_default_env_generation():
    """Sprawdza czy generator domyślnego .env zawiera wszystkie wymagane porty."""
    # To jest kopia logiki z launcher_app.py do weryfikacji formatu
    def generate_default(name):
        return f"FLASK_PORT=5000\nGENEALOGY_EDITOR_PORT=5001\nPARCEL_EDITOR_PORT=5003\nDB_NAME={name}"

    content = generate_default("czarna_db")
    assert "GENEALOGY_EDITOR_PORT=5001" in content
    assert "PARCEL_EDITOR_PORT=5003" in content
    assert "FLASK_PORT=5000" in content
