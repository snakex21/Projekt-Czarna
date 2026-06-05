"""
Plik: test_basic.py
Opis: Podstawowe testy funkcjonalnosci aplikacji publicznej.
      Weryfikuje przekierowania i autoryzacje systemu.
"""

import pytest
from backend import config as backend_config

# ==========================================================================
# TESTY PODSTAWOWEJ FUNKCJONALNOSCI
# ==========================================================================

def test_root_redirects_to_main(client):
    """
    Test przekierowania z glownej sciezki do strony glownej.
    Weryfikuje poprawnosc routingu aplikacji (FastAPI).
    """
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302, 303, 307, 308)
    
    loc = resp.headers.get("Location", "")
    assert "/strona_glowna/index.html" in loc


def test_check_auth_when_disabled(client, monkeypatch):
    """
    Test sprawdzania autoryzacji przy wylaczonym mechanizmie.
    """
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", False)

    resp = client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    
    data = resp.json()
    assert data == {"authenticated": True, "auth_required": False}
