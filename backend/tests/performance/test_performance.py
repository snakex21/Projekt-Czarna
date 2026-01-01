import requests
import time
import pytest
import os

BASE_URL = "http://127.0.0.1:5000"

def test_api_genealogia_list_performance():
    """Sprawdza czy lista osób ładuje się w rozsądnym czasie (< 500ms)."""
    start_time = time.time()
    try:
        response = requests.get(f"{BASE_URL}/api/genealogia/list", timeout=5)
        duration = (time.time() - start_time) * 1000
        
        assert response.status_code == 200
        print(f"\nUrodzenia/Lista: {duration:.2f} ms")
        
        # Norma: < 500ms dla średnich zbiorów
        if duration > 500:
             print(f"⚠️ OSTRZEŻENIE: Wolne ładowanie list: {duration:.2f} ms")
        
        assert duration < 2000, "API jest zbyt wolne! (> 2s)"
    except requests.exceptions.ConnectionError:
        pytest.skip("Serwer backend nie jest uruchomiony.")

def test_api_persons_format_performance():
    """Sprawdza czas ładowania pełnego formatu dla edytora (< 800ms)."""
    start_time = time.time()
    try:
        response = requests.get(f"{BASE_URL}/api/genealogia/persons-format", timeout=5)
        duration = (time.time() - start_time) * 1000
        
        assert response.status_code == 200
        print(f"Pełny format (Edytor): {duration:.2f} ms")
        
        if duration > 800:
            print(f"⚠️ OSTRZEŻENIE: Wolne ładowanie edytora: {duration:.2f} ms")
            
        assert duration < 3000, "API edytora jest zbyt wolne! (> 3s)"
    except requests.exceptions.ConnectionError:
        pytest.skip("Serwer backend nie jest uruchomiony.")

def test_static_files_speed():
    """Sprawdza czas ładowania statycznych plików (np. mapa)."""
    start_time = time.time()
    try:
        response = requests.get(f"{BASE_URL}/mapa/mapa.html", timeout=5)
        duration = (time.time() - start_time) * 1000
        assert response.status_code == 200
        print(f"Mapa HTML: {duration:.2f} ms")
    except requests.exceptions.ConnectionError:
        pytest.skip("Serwer backend nie jest uruchomiony.")
