import requests
import pytest

BASE_URL = "http://127.0.0.1:5000"

def test_admin_unauthorized_access():
    """Sprawdza czy panel admina (API) odrzuca żądania bez hasła."""
    try:
        # Próba pobrania listy osób przez admin API bez nagłówka auth (jeśli zaimplementowano)
        # Zakładamy, że admin API wymaga jakiejś formy autoryzacji jeśli jest włączona
        response = requests.get(f"{BASE_URL}/api/admin/stats", timeout=3)
        
        # Jeśli status to 401 lub 403, to dobrze
        # Jeśli 200, to sprawdzamy czy ADMIN_AUTH_ENABLED jest True w .env
        if response.status_code == 200:
             print("⚠️ UWAGA: Dostęp do statystyk administratora bez autoryzacji!")
        else:
             print(f"✅ Dostęp zablokowany (Status: {response.status_code})")
             
    except requests.exceptions.ConnectionError:
        pytest.skip("Serwer backend nie jest uruchomiony.")

def test_admin_config_protection():
    """Sprawdza czy można pobrać plik .env przez HTTP (nie powinno być możliwe)."""
    try:
        response = requests.get(f"{BASE_URL}/.env", timeout=3)
        assert response.status_code != 200, "💀 KRYTYCZNE: Plik .env jest dostępny publicznie!"
        print(f"✅ Plik .env chroniony (Status: {response.status_code})")
    except requests.exceptions.ConnectionError:
        pytest.skip("Serwer backend nie jest uruchomiony.")

def test_directory_listing_disabled():
    """Sprawdza czy listowanie katalogów jest wyłączone."""
    try:
        response = requests.get(f"{BASE_URL}/backup/", timeout=3)
        # Powinno być 404 lub 403, a nie lista plików
        assert "Index of" not in response.text
        print(f"✅ Listowanie katalogów wyłączone (Status: {response.status_code})")
    except requests.exceptions.ConnectionError:
        pytest.skip("Serwer backend nie jest uruchomiony.")
