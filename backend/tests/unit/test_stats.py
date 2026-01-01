"""
Plik: test_stats.py
Opis: Moduł testowy dla endpointu statystyk API.
      Weryfikuje poprawność działania i zawartość odpowiedzi /api/stats.
"""

# ==========================================================================
# TESTY ENDPOINTU STATYSTYK
# ==========================================================================

def test_stats_status_ok(client):
    """
    Test dostępności endpointu statystyk.
    Sprawdza czy API zwraca kod sukcesu HTTP 200.
    """
    resp = client.get("/api/stats")
    assert resp.status_code == 200, f"Spodziewano 200, a jest {resp.status_code}"


def test_stats_contains_general_stats_key(client):
    """
    Test zawartości odpowiedzi statystyk.
    Weryfikuje strukturę i wartości zwracanych danych.
    """
    # Pobranie odpowiedzi z API
    resp = client.get("/api/stats")
    data = resp.get_json()
    
    # Weryfikacja struktury JSON
    assert isinstance(data, dict), "Odpowiedź nie jest JSON-em (dict)."
    assert "general_stats" in data, "Brak klucza 'general_stats' w odpowiedzi."
    
    # Weryfikacja wartości - sprawdzamy czy są jakiekolwiek dane (zależnie od DB)
    assert data["general_stats"].get("total_owners") >= 0
    assert data["general_stats"].get("total_plots") >= 0