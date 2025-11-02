"""
Plik: test_stats_shape.py
Opis: Moduł testowy weryfikujący strukturę danych statystycznych.
      Sprawdza kompletność i typy zwracanych danych z API statystyk.
"""

# ==========================================================================
# TESTY STRUKTURY DANYCH STATYSTYCZNYCH
# ==========================================================================

def test_stats_has_expected_keys_and_types(client):
    """
    Test kompleksowy struktury odpowiedzi /api/stats.
    Weryfikuje obecność wszystkich wymaganych kluczy i typów danych.
    """
    # Pobranie danych statystycznych
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)

    # === Weryfikacja głównych kluczy ===
    required_keys = [
        "general_stats",
        "area_stats",
        "parcels_ranking",
        "rivers_stats",
        "rivers_ranking",
        "roads_stats",
        "roads_ranking",
        "protocols_per_day",
        "rankings_real",
        "rankings_protocol",
        "demografia",
    ]
    for key in required_keys:
        assert key in data, f"Brak klucza {key}"

    # === Weryfikacja struktury general_stats ===
    assert isinstance(data["general_stats"], dict)
    assert "total_owners" in data["general_stats"]
    assert "total_plots" in data["general_stats"]

    # === Weryfikacja struktury area_stats ===
    assert isinstance(data["area_stats"], dict)
    required_area_keys = [
        "total_area_m2",
        "total_area_ha",
        "total_area_ares",
        "avg_area_m2",
        "avg_area_ha",
        "avg_area_ares",
        "min_area_m2",
        "max_area_m2"
    ]
    for key in required_area_keys:
        assert key in data["area_stats"], f"Brak klucza {key} w area_stats"
        assert isinstance(data["area_stats"][key], (int, float)), f"Wartość {key} nie jest liczbą"

    # === Weryfikacja typów pozostałych kluczy ===
    assert isinstance(data["protocols_per_day"], list)
    assert isinstance(data["rankings_real"], dict)
    assert isinstance(data["rankings_protocol"], dict)
    assert isinstance(data["demografia"], list)

    # === Weryfikacja struktury rankingów ===
    def assert_rankings_dict(d):
        """Pomocnicza funkcja sprawdzająca strukturę rankingu."""
        expected_categories = [
            "all_plots",
            "rolna",
            "budowlana",
            "las",
            "pastwisko",
            "droga",
            "rzeka",
            "budynek",
            "kapliczka",
        ]
        for category in expected_categories:
            assert category in d, f"Brak listy {category} w rankingu"
            assert isinstance(d[category], list)
            
            if len(d[category]) > 0:
                owner = d[category][0]
                assert "nazwa_wlasciciela" in owner
                assert "unikalny_klucz" in owner
                assert "plot_count" in owner
                assert "total_area_m2" in owner
                assert "plot_numbers" in owner
                assert isinstance(owner["plot_numbers"], list)

    # Sprawdzenie obu typów rankingów
    assert_rankings_dict(data["rankings_real"])
    assert_rankings_dict(data["rankings_protocol"])

    # === Weryfikacja rivers_stats i roads_stats ===
    assert isinstance(data["rivers_stats"], dict)
    assert "total_count" in data["rivers_stats"]
    assert "max_length_m" in data["rivers_stats"]
    
    assert isinstance(data["roads_stats"], dict)
    assert "total_count" in data["roads_stats"]
    assert "max_length_m" in data["roads_stats"]
    
    # === Weryfikacja rivers_ranking i roads_ranking ===
    assert isinstance(data["rivers_ranking"], list)
    assert isinstance(data["roads_ranking"], list)

    # === Weryfikacja struktury parcels_ranking ===
    assert isinstance(data["parcels_ranking"], dict)
    parcel_categories = ["all", "rolna", "budowlana", "las", "pastwisko"]
    for category in parcel_categories:
        assert category in data["parcels_ranking"], f"Brak kategorii {category} w parcels_ranking"
        assert isinstance(data["parcels_ranking"][category], list)
        
        if len(data["parcels_ranking"][category]) > 0:
            parcel = data["parcels_ranking"][category][0]
            assert "parcel_number" in parcel
            assert "area_m2" in parcel
            assert isinstance(parcel["area_m2"], (int, float))
