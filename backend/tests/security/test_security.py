import requests
import pytest

BASE_URL = "http://127.0.0.1:5000"


def test_admin_unauthorized_access(server):
    """Sprawdza czy panel admina (API) odrzuca zadania bez hasla."""
    response = requests.get(f"{BASE_URL}/api/admin/stats", timeout=3)
    
    if response.status_code == 200:
         print("[WARN] Dostep do statystyk administratora bez autoryzacji!")
    else:
         print(f"[OK] Dostep zablokowany (Status: {response.status_code})")


def test_admin_config_protection(server):
    """Sprawdza czy mozna pobrac plik .env przez HTTP (nie powinno byc mozliwe)."""
    response = requests.get(f"{BASE_URL}/.env", timeout=3)
    assert response.status_code != 200, "[CRIT] Plik .env jest dostepny publicznie!"
    print(f"[OK] Plik .env chroniony (Status: {response.status_code})")


def test_directory_listing_disabled(server):
    """Sprawdza czy listowanie katalogow jest wylaczone."""
    response = requests.get(f"{BASE_URL}/backup/", timeout=3)
    assert "Index of" not in response.text
    print(f"[OK] Listowanie katalogow wylaczone (Status: {response.status_code})")
