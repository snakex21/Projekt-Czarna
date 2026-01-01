"""
================================================================================
Plik: test_admin.py
Opis: Testy jednostkowe panelu administracyjnego
      Weryfikacja autoryzacji i dostępności interfejsu
================================================================================
"""

import pytest

# ================================================================================
# TESTY PRZEKIEROWAŃ I ROUTINGU
# ================================================================================

def test_admin_redirects_to_main_admin_html(client):
    """
    Weryfikuje przekierowanie z /admin na /admin/admin.html.
    Panel administracyjny ma teraz jedną główną stronę.
    """
    resp = client.get("/admin", follow_redirects=False)
    # Akceptujemy różne kody przekierowań HTTP
    assert resp.status_code in (301, 302, 303, 307, 308)
    # Sprawdzamy końcową lokalizację
    assert resp.headers.get("Location", "").endswith("/admin/admin.html")

# ================================================================================
# TESTY DOSTĘPNOŚCI STRONY ADMINISTRACYJNEJ
# ================================================================================

def test_admin_html_serves_ok_when_auth_enabled(client, monkeypatch):
    """
    Sprawdza dostępność strony admin.html przy włączonej autoryzacji.
    Strona powinna być zawsze dostępna - kontrola dostępu odbywa się w JS.
    """
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    
    resp = client.get("/admin/admin.html")
    assert resp.status_code == 200
    # Weryfikacja zawartości strony
    assert b"Panel Administracyjny" in resp.data

def test_admin_html_serves_ok_when_auth_disabled(client, monkeypatch):
    """
    Sprawdza dostępność strony admin.html przy wyłączonej autoryzacji.
    """
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", False)
    
    resp = client.get("/admin/admin.html")
    assert resp.status_code == 200
    assert b"Panel Administracyjny" in resp.data

# ================================================================================
# TESTY API AUTORYZACJI
# ================================================================================

def test_check_auth_when_enabled_and_logged_out(client, monkeypatch):
    """
    Test API autoryzacji: logowanie włączone, użytkownik niezalogowany.
    Endpoint kluczowy dla kontroli dostępu w warstwie frontend.
    """
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    
    # Upewniamy się, że sesja jest pusta
    with client.session_transaction() as sess:
        sess.pop("admin_logged_in", None)

    resp = client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"authenticated": False, "auth_required": True}

def test_check_auth_when_enabled_and_logged_in(client, monkeypatch):
    """
    Test API autoryzacji: logowanie włączone, użytkownik zalogowany.
    """
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    
    # Ustawiamy flagę zalogowania w sesji
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    resp = client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"authenticated": True, "auth_required": True}