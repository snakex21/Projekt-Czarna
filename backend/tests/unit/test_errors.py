"""
Plik: test_errors.py
Opis: Moduł testowy weryfikujący obsługę błędów HTTP.
      Sprawdza poprawność kodów odpowiedzi dla nieistniejących zasobów.

UWAGA: FastAPI używa catch-all /{filename:path} który serwuje index.html
jako fallback dla wszystkich nieznanych ścieżek (SPA-like behavior).
Dlatego nieznane ścieżki zwracają 200 zamiast 404.
"""

# ==========================================================================
# TESTY OBSŁUGI BŁĘDÓW
# ==========================================================================

def test_unknown_path_returns_fallback(client):
    """
    Test obsługi nieistniejących ścieżek.
    FastAPI serwuje index.html jako fallback (zamiast 404),
    co zapewnia poprawne działanie SPA routingu po stronie frontendu.
    """
    resp = client.get("/to/na/pewno/nie/istnieje")
    # Fallback do index.html daje 200 (a nie 404)
    assert resp.status_code == 200
    # Sprawdzamy, że faktycznie dostajemy treść HTML
    assert "text/html" in resp.headers.get("content-type", "")
