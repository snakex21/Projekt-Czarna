"""
================================================================================
Plik: test_admin.py
Opis: Testy jednostkowe panelu administracyjnego
      Weryfikacja autoryzacji i dostepnosci interfejsu
================================================================================
"""

import pytest
from backend import config as backend_config

# ================================================================================
# TESTY PRZEKIEROWAN I ROUTINGU
# ================================================================================

def test_admin_redirects_to_main_admin_html(client):
    """
    Weryfikuje przekierowanie z /admin na /admin/admin.html.
    """
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code in (301, 302, 303, 307, 308)
    assert resp.headers.get("Location", "").endswith("/admin/admin.html")

# ================================================================================
# TESTY DOSTEPNOSCI STRONY ADMINISTRACYJNEJ
# ================================================================================

def test_admin_html_serves_ok_when_auth_enabled(client, monkeypatch):
    """
    Sprawdza dostepnosc strony admin.html przy wlaczonej autoryzacji.
    """
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", True)
    
    resp = client.get("/admin/admin.html")
    assert resp.status_code == 200
    assert "Panel Administracyjny" in resp.text

def test_admin_html_serves_ok_when_auth_disabled(client, monkeypatch):
    """
    Sprawdza dostepnosc strony admin.html przy wylaczonej autoryzacji.
    """
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", False)
    
    resp = client.get("/admin/admin.html")
    assert resp.status_code == 200
    assert "Panel Administracyjny" in resp.text

# ================================================================================
# TESTY API AUTORYZACJI
# ================================================================================

def test_check_auth_when_enabled_and_logged_out(client, monkeypatch):
    """
    Test API autoryzacji: logowanie wlaczone, uzytkownik niezalogowany.
    """
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", True)
    
    # FastAPI: brak ciasteczka = niezalogowany
    resp = client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"authenticated": False, "auth_required": True}

def test_check_auth_when_enabled_and_logged_in(client, monkeypatch):
    """
    Test API autoryzacji: logowanie wlaczone, uzytkownik zalogowany.
    """
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", True)
    
    # FastAPI: ustawiamy ciasteczko zamiast sesji Flask
    client.cookies.set("admin_logged_in", "true")
    
    resp = client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"authenticated": True, "auth_required": True}
