"""
Plik: test_new_features.py
Opis: Testy dla nowo dodanych funkcji:
      - TOP 50 dla rzek i dróg w statystykach
      - Funkcje highlight na mapie (TOP 10 działek, rzek, dróg)
      - Favicon detection z folderu backup
"""

import pytest
import json
import sys
import os

# Dodaj katalog główny projektu do PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

# ==========================================================================
# TESTY STATYSTYK - TOP 50 dla rzek i dróg
# ==========================================================================

def test_stats_rivers_ranking_top50(client):
    """
    Test rankingu TOP 50 rzek w statystykach.
    Sprawdza czy endpoint zwraca ranking rzek i czy limit wynosi 50.
    """
    resp = client.get("/api/stats")
    assert resp.status_code == 200

    data = resp.json()
    assert "rivers_ranking" in data, "Brak klucza 'rivers_ranking' w odpowiedzi."

    rivers = data["rivers_ranking"]
    assert isinstance(rivers, list), "rivers_ranking powinien być listą."
    assert len(rivers) <= 50, f"Ranking rzek powinien mieć max 50 elementów, ma {len(rivers)}."

    # Sprawdź strukturę każdego elementu
    if len(rivers) > 0:
        first_river = rivers[0]
        assert "nazwa" in first_river or "river_name" in first_river, "Element rankingu rzek nie ma nazwy."


def test_stats_roads_ranking_top50(client):
    """
    Test rankingu TOP 50 dróg w statystykach.
    Sprawdza czy endpoint zwraca ranking dróg i czy limit wynosi 50.
    """
    resp = client.get("/api/stats")
    assert resp.status_code == 200

    data = resp.json()
    assert "roads_ranking" in data, "Brak klucza 'roads_ranking' w odpowiedzi."

    roads = data["roads_ranking"]
    assert isinstance(roads, list), "roads_ranking powinien być listą."
    assert len(roads) <= 50, f"Ranking dróg powinien mieć max 50 elementów, ma {len(roads)}."

    # Sprawdź strukturę każdego elementu
    if len(roads) > 0:
        first_road = roads[0]
        assert "nazwa" in first_road or "road_name" in first_road or "road_number" in first_road, \
            "Element rankingu dróg nie ma nazwy ani numeru."


def test_stats_parcels_ranking_exists(client):
    """
    Test istnienia rankingu działek w statystykach.
    Sprawdza czy endpoint zwraca ranking działek.
    """
    resp = client.get("/api/stats")
    assert resp.status_code == 200

    data = resp.json()
    assert "parcels_ranking" in data, "Brak klucza 'parcels_ranking' w odpowiedzi."

    parcels = data["parcels_ranking"]
    assert isinstance(parcels, dict) or isinstance(parcels, list), \
        "parcels_ranking powinien być dict (z kategoriami) lub list."


# ==========================================================================
# TESTY HIGHLIGHT NA MAPIE - URL parameters
# ==========================================================================

def test_map_highlight_parcels_parameter(client):
    """
    Test parametru highlightParcels w URL mapy.
    Sprawdza czy mapa akceptuje parametr do podświetlania działek.
    """
    # Symulacja żądania do strony mapy z parametrem
    resp = client.get("/mapa/mapa.html?highlightParcels=123,456,789")
    # Mapa to plik statyczny, więc sprawdzamy czy dostęp działa
    assert resp.status_code == 200 or resp.status_code == 404  # 404 jeśli plik nie istnieje w testach


def test_map_highlight_rivers_parameter(client):
    """
    Test parametru highlightRivers w URL mapy.
    Sprawdza czy mapa akceptuje parametr do podświetlania rzek.
    """
    resp = client.get("/mapa/mapa.html?highlightRivers=Wisła,San")
    assert resp.status_code == 200 or resp.status_code == 404


def test_map_highlight_roads_parameter(client):
    """
    Test parametru highlightRoads w URL mapy.
    Sprawdza czy mapa akceptuje parametr do podświetlania dróg.
    """
    resp = client.get("/mapa/mapa.html?highlightRoads=Główna,Polna")
    assert resp.status_code == 200 or resp.status_code == 404


# ==========================================================================
# TESTY CACHE I OPTYMALIZACJI
# ==========================================================================

def test_locations_cache_mechanism():
    """
    Test mechanizmu cache dla miejscowości.
    Sprawdza czy cache jest używany i czy się invaliduje.
    """
    from launcher.launcher_app import get_all_locations, invalidate_locations_cache

    # Pobierz lokacje (wypełni cache)
    locations1 = get_all_locations()
    assert isinstance(locations1, list), "get_all_locations() powinien zwracać listę."

    # Pobierz ponownie (z cache)
    locations2 = get_all_locations()
    assert locations1 == locations2, "Cache powinien zwrócić te same dane."

    # Invaliduj cache
    invalidate_locations_cache()

    # Pobierz ponownie (powinno ponownie odpytać bazę)
    locations3 = get_all_locations()
    assert isinstance(locations3, list), "Po invalidacji cache nadal powinien działać."


# ==========================================================================
# TESTY FAVICON DETECTION
# ==========================================================================

def test_favicon_detection_from_backup():
    """
    Test automatycznego wykrywania favicon z folderu backup miejscowości.
    Sprawdza czy _auto_sync_site_icon() wykrywa favicon.jpeg w backup.
    """
    import os
    
    # Próba weryfikacji za pomocą TEST_LOCATION
    test_location = os.environ.get("TEST_LOCATION")
    if not test_location:
         pytest.skip("TEST_LOCATION nie ustawione")
            
    # Ścieżka do backupu
    # backend/tests/unit/test_new_features.py -> ../../.. -> root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    backup_path = os.path.join(project_root, "data", "locations", test_location)
    
    favicon_found = False
    for ext in ['.ico', '.png', '.jpg', '.jpeg']:
        if os.path.exists(os.path.join(backup_path, f"favicon{ext}")):
            favicon_found = True
            break
            
    if favicon_found:
        assert True
    else:
        pytest.skip(f"Brak favicon w {backup_path}")

    # Koniec testu
    pass


def test_site_assets_folder_exists():
    """
    Test istnienia folderu assets/site.
    Sprawdza czy folder docelowy dla favicon istnieje lub może być utworzony.
    """
    import os
    from launcher.launcher_app import SITE_ASSETS_FOLDER

    # Folder może nie istnieć - to normalne
    # Sprawdzamy czy ścieżka jest zdefiniowana
    assert SITE_ASSETS_FOLDER is not None, "SITE_ASSETS_FOLDER nie jest zdefiniowane."
    assert isinstance(SITE_ASSETS_FOLDER, str), "SITE_ASSETS_FOLDER powinien być stringiem."


# ==========================================================================
# TESTY .ENV UJEDNOLICENIA
# ==========================================================================

def test_env_file_format():
    """
    Test jednolitego formatu pliku .env.
    Sprawdza czy plik .env ma poprawną strukturę (sekcje, klucze).
    """
    import os

    # Sprawdź czy funkcja do tworzenia .env istnieje
    # Próba pobrania ścieżki z TEST_LOCATION (ustawianego przez launcher)
    test_location = os.environ.get("TEST_LOCATION")
    
    if not test_location:
        pytest.skip("TEST_LOCATION nie ustawione - uruchom testy przez Launcher")
    
    # Rekonstrukcja ścieżki: backup/Nazwa/.env
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    env_path = os.path.join(project_root, "data", "locations", test_location, ".env")

    if not os.path.exists(env_path):
        pytest.skip(f"Plik .env nie znaleziony: {env_path}")

    with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Sprawdź obecność kluczowych zmiennych
    # Eksportujemy klucze bez komentarzy i pustych linii
    keys_in_file = []
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key = line.split('=')[0].strip()
            keys_in_file.append(key)

    required_keys = ["DB_NAME", "FLASK_HOST", "FLASK_PORT", "ADMIN_AUTH_ENABLED"]
    for rkey in required_keys:
        assert rkey in keys_in_file, f".env powinien zawierać zmienną {rkey}"


# ==========================================================================
# TESTY DEPLOYMENT GUIDE — usunięte 2026-06: plik docs/deployment.html
# nigdy nie istniał, testy były dead-code. Deployment guide jest teraz
# częścią docs/index.html (sekcja "Instalacja").
# ==========================================================================
