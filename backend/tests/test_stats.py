# Testy jednostkowe endpointu /api/stats z użyciem klienta testowego Flask.

def test_stats_status_ok(client):
    # Sprawdzamy, że endpoint odpowiada 200 OK
    resp = client.get("/api/stats")
    assert resp.status_code == 200, f"Spodziewano 200, a jest {resp.status_code}"


def test_stats_contains_general_stats_key(client):
    # Sprawdzamy, że w zwrotce jest klucz 'general_stats'
    resp = client.get("/api/stats")
    data = resp.get_json()
    assert isinstance(data, dict), "Odpowiedź nie jest JSON-em (dict)."
    assert "general_stats" in data, "Brak klucza 'general_stats' w odpowiedzi."
    # Prosty sanity-check wartości, które przygotowaliśmy w fejkowej bazie
    assert data["general_stats"].get("total_owners") == 2
    assert data["general_stats"].get("total_plots") == 5
