import requests
import time
import pytest
import os

BASE_URL = "http://127.0.0.1:5000"


def test_api_genealogia_list_performance(server):
    """Sprawdza czy lista osob laduje sie w rozsadnym czasie (< 500ms)."""
    start_time = time.time()
    response = requests.get(f"{BASE_URL}/api/genealogia/list", timeout=5)
    duration = (time.time() - start_time) * 1000
    
    assert response.status_code == 200
    print(f"\nUrodzenia/Lista: {duration:.2f} ms")
    
    if duration > 500:
         print(f"[WARN] Wolne ladowanie list: {duration:.2f} ms")
    
    assert duration < 2000, "API jest zbyt wolne! (> 2s)"


def test_api_persons_format_performance(server):
    """Sprawdza czas ladowania pelnego formatu dla edytora (< 800ms)."""
    start_time = time.time()
    response = requests.get(f"{BASE_URL}/api/genealogia/persons-format", timeout=5)
    duration = (time.time() - start_time) * 1000
    
    assert response.status_code == 200
    print(f"Pelny format (Edytor): {duration:.2f} ms")
    
    if duration > 800:
        print(f"[WARN] Wolne ladowanie edytora: {duration:.2f} ms")
        
    assert duration < 3000, "API edytora jest zbyt wolne! (> 3s)"


def test_static_files_speed(server):
    """Sprawdza czas ladowania statycznych plikow (np. mapa)."""
    start_time = time.time()
    response = requests.get(f"{BASE_URL}/mapa/mapa.html", timeout=5)
    duration = (time.time() - start_time) * 1000
    assert response.status_code == 200
    print(f"Mapa HTML: {duration:.2f} ms")
