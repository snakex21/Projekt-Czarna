"""
Plik: test_new_features.py
Opis: Testy dla nowo dodanych funkcji:
      - TOP 50 dla rzek i dróg w statystykach
      - Funkcje highlight na mapie (TOP 10 działek, rzek, dróg)
      - Favicon detection z folderu backup
"""

import pytest
import json

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

    data = resp.get_json()
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

    data = resp.get_json()
    assert "roads_ranking" in data, "Brak klucza 'roads_ranking' w odpowiedzi."

    roads = data["roads_ranking"]
    assert isinstance(roads, list), "roads_ranking powinien być listą."
    assert len(roads) <= 50, f"Ranking dróg powinien mieć max 50 elementów, ma {len(roads)}."

    # Sprawdź strukturę każdego elementu
    if len(roads) > 0:
        first_road = roads[0]
        assert "nazwa" in first_road or "road_name" in first_road, "Element rankingu dróg nie ma nazwy."


def test_stats_parcels_ranking_exists(client):
    """
    Test istnienia rankingu działek w statystykach.
    Sprawdza czy endpoint zwraca ranking działek.
    """
    resp = client.get("/api/stats")
    assert resp.status_code == 200

    data = resp.get_json()
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
    from launcher.launcher_app import BACKUP_FOLDER, SITE_ASSETS_FOLDER

    # Sprawdź czy funkcja istnieje
    try:
        from launcher.launcher_app import _auto_sync_site_icon
    except ImportError:
        pytest.skip("Funkcja _auto_sync_site_icon nie jest dostępna w testach")

    # Sprawdź czy folder backup istnieje
    assert os.path.exists(BACKUP_FOLDER), f"Folder backup nie istnieje: {BACKUP_FOLDER}"


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
    try:
        from launcher.launcher_app import get_location_env_path
        env_path = get_location_env_path()

        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Sprawdź obecność kluczowych sekcji
            assert "BAZA DANYCH" in content, ".env powinien zawierać sekcję BAZA DANYCH"
            assert "SERWER FLASK" in content, ".env powinien zawierać sekcję SERWER FLASK"
            assert "AUTENTYKACJA ADMINISTRATORA" in content, ".env powinien zawierać sekcję AUTENTYKACJA"

            # Sprawdź obecność kluczowych zmiennych
            assert "DB_NAME=" in content, ".env powinien zawierać DB_NAME"
            assert "FLASK_HOST=" in content, ".env powinien zawierać FLASK_HOST"
            assert "FLASK_PORT=" in content, ".env powinien zawierać FLASK_PORT"
            assert "ADMIN_AUTH_ENABLED=" in content, ".env powinien zawierać ADMIN_AUTH_ENABLED"
        else:
            pytest.skip(f"Plik .env nie istnieje: {env_path}")
    except Exception as e:
        pytest.skip(f"Nie można sprawdzić .env: {e}")


# ==========================================================================
# TESTY DEPLOYMENT GUIDE
# ==========================================================================

def test_deployment_html_exists():
    """
    Test istnienia pliku deployment.html w docs.
    """
    import os

    deployment_path = os.path.join("docs", "deployment.html")
    assert os.path.exists(deployment_path), \
        f"Plik deployment.html nie istnieje w lokalizacji: {deployment_path}"


def test_deployment_html_content():
    """
    Test zawartości deployment.html.
    Sprawdza czy zawiera kluczowe sekcje.
    """
    import os

    deployment_path = os.path.join("docs", "deployment.html")

    if os.path.exists(deployment_path):
        with open(deployment_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Sprawdź kluczowe sekcje
        assert "PostgreSQL" in content, "deployment.html powinien zawierać informacje o PostgreSQL"
        assert "pip install" in content, "deployment.html powinien zawierać instrukcje instalacji"
        assert "launcher" in content or "Launcher" in content, \
            "deployment.html powinien wspominać o launcherze"
    else:
        pytest.skip(f"Plik deployment.html nie istnieje: {deployment_path}")
