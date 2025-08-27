# Testy panelu admin – tryb z logowaniem i bez logowania.
import pytest

def test_admin_redirects_to_main_admin_html(client):
    """
    Testuje, czy żądanie do /admin przekierowuje na /admin/admin.html.
    To jest teraz główna i jedyna strona panelu.
    """
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code in (301, 302, 303, 307, 308) # Dopuszczamy różne kody przekierowań
    # Sprawdzamy, czy lokalizacja kończy się na /admin/admin.html
    assert resp.headers.get("Location", "").endswith("/admin/admin.html")

def test_admin_html_serves_ok_when_auth_enabled(client, monkeypatch):
    """
    Testuje, czy serwer ZAWSZE zwraca stronę admin.html (status 200 OK),
    nawet gdy autoryzacja jest włączona. Logikę blokady przenieśliśmy do frontendu.
    """
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    
    resp = client.get("/admin/admin.html")
    assert resp.status_code == 200
    assert b"Panel Administracyjny" in resp.data # Prosty sanity check, czy to na pewno ten plik

def test_admin_html_serves_ok_when_auth_disabled(client, monkeypatch):
    """
    Testuje, czy strona admin.html jest serwowana, gdy autoryzacja jest wyłączona.
    """
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", False)
    
    resp = client.get("/admin/admin.html")
    assert resp.status_code == 200
    assert b"Panel Administracyjny" in resp.data

def test_check_auth_when_enabled_and_logged_out(client, monkeypatch):
    """
    Testuje API autoryzacji: włączone logowanie, użytkownik niezalogowany.
    Ten test pozostaje kluczowy dla nowej logiki frontendowej.
    """
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess.pop("admin_logged_in", None)

    resp = client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"authenticated": False, "auth_required": True}

def test_check_auth_when_enabled_and_logged_in(client, monkeypatch):
    """
    Testuje API autoryzacji: włączone logowanie, użytkownik zalogowany.
    """
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    resp = client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"authenticated": True, "auth_required": True}
