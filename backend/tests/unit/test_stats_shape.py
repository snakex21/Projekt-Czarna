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

    # Sprawdzenie obu typów rankingów
    assert_rankings_dict(data["rankings_real"])
    assert_rankings_dict(data["rankings_protocol"])