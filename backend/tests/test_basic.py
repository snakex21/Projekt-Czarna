"""
Plik: test_basic.py
Opis: Podstawowe testy funkcjonalności aplikacji publicznej.
      Weryfikuje przekierowania i autoryzację systemu.
"""

# ==========================================================================
# TESTY PODSTAWOWEJ FUNKCJONALNOŚCI
# ==========================================================================

def test_root_redirects_to_main(client):
    """
    Test przekierowania z głównej ścieżki do strony głównej.
    Weryfikuje poprawność routingu aplikacji.
    """
    # Sprawdzenie przekierowania bez podążania za nim
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302, 303)
    
    # Weryfikacja docelowej lokalizacji
    loc = resp.headers.get("Location", "")
    assert "/strona_glowna/index.html" in loc


def test_check_auth_when_disabled(client, monkeypatch):
    """
    Test sprawdzania autoryzacji przy wyłączonym mechanizmie.
    Symuluje działanie systemu bez wymogów autoryzacji.
    """
    # Wyłączenie autoryzacji niezależnie od konfiguracji
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", False)

    # Weryfikacja odpowiedzi API
    resp = client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    
    # Sprawdzenie zwracanej struktury danych
    data = resp.get_json()
    assert data == {"authenticated": True, "auth_required": False}