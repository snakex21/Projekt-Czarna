"""
Plik: test_errors.py
Opis: Moduł testowy weryfikujący obsługę błędów HTTP.
      Sprawdza poprawność kodów odpowiedzi dla nieistniejących zasobów.
"""

# ==========================================================================
# TESTY OBSŁUGI BŁĘDÓW
# ==========================================================================

def test_404_for_unknown_path(client):
    """
    Test obsługi nieistniejących ścieżek.
    Weryfikuje zwracanie kodu 404 dla nieznanych adresów URL.
    """
    resp = client.get("/to/na/pewno/nie/istnieje")
    assert resp.status_code == 404