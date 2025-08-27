# Dodatkowe asercje na kształt danych z /api/stats

def test_stats_has_expected_keys_and_types(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)

    # Klucze zgodne z app.py
    for key in [
        "general_stats",
        "protocols_per_day",
        "rankings_real",
        "rankings_protocol",
        "demografia",
    ]:
        assert key in data, f"Brak klucza {key}"

    assert isinstance(data["general_stats"], dict)
    assert "total_owners" in data["general_stats"]
    assert "total_plots" in data["general_stats"]

    # Reszta to listy/dict zgodnie z implementacją
    assert isinstance(data["protocols_per_day"], list)
    assert isinstance(data["rankings_real"], dict)
    assert isinstance(data["rankings_protocol"], dict)
    assert isinstance(data["demografia"], list)

    # Struktura rankingów wg app.py
    def assert_rankings_dict(d):
        for k in [
            "all_plots",
            "rolna",
            "budowlana",
            "las",
            "pastwisko",
            "droga",
            "rzeka",
            "budynek",
            "kapliczka",
        ]:
            assert k in d, f"Brak listy {k} w rankingu"
            assert isinstance(d[k], list)

    assert_rankings_dict(data["rankings_real"])
    assert_rankings_dict(data["rankings_protocol"])