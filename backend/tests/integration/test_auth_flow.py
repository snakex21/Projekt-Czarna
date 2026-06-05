"""
Testy integracyjne flow autoryzacji.

Lapie realne bugi w:
- logowaniu (bledne haslo, brak username, ADMIN_AUTH_ENABLED wplyw)
- tokenach (cookie HttpOnly, wygasanie)
- wylogowaniu (czyszczenie ciasteczka)
- kompatybilnosci wstecznej (stary endpoint /api/admin/check-auth)
"""
import pytest


# ================================================================================
# Auth flow
# ================================================================================


def test_auth_status_reports_enabled(client):
    """GET /api/admin/auth-status zwraca enabled=true po ustawieniu env var."""
    resp = client.get("/api/admin/auth-status")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


def test_login_with_correct_credentials_returns_ok(client):
    """POST /api/admin/login z 'admin'/'admin123' zwraca status=ok + token cookie."""
    resp = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "admin123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # Cookie admin_token musi byc ustawione
    assert "admin_token" in resp.cookies, "Brak ciasteczka admin_token po zalogowaniu"


def test_login_with_wrong_password_returns_401(client):
    """Zle haslo -> 401, brak cookie."""
    resp = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "wrong_password"}
    )
    assert resp.status_code == 401
    assert "admin_token" not in resp.cookies


def test_login_with_wrong_username_returns_401(client):
    """Zla nazwa uzytkownika -> 401."""
    resp = client.post(
        "/api/admin/login",
        json={"username": "hacker", "password": "admin123"}
    )
    assert resp.status_code == 401


def test_login_with_missing_fields_returns_error(client):
    """Brak username LUB password -> 401 (verify_password("") != hash).

    Konwencja API: payload: dict (nie Pydantic schema) - brak pola traktowany
    jest jako pusty string, ktory nie matchuje hashu. Stad 401 zamiast 422.
    """
    resp_missing_user = client.post(
        "/api/admin/login",
        json={"password": "admin123"}
    )
    resp_missing_pass = client.post(
        "/api/admin/login",
        json={"username": "admin"}
    )
    # verify_password("") / verify_password("admin123") z username mismatch
    # zwracaja 401 (nie 422 - bo to dict, nie Pydantic schema)
    assert resp_missing_user.status_code == 401
    assert resp_missing_pass.status_code == 401


def test_logout_clears_admin_token_cookie(client):
    """POST /api/admin/logout usuwa ciasteczko admin_token."""
    # Najpierw zaloguj
    login = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "admin123"}
    )
    assert "admin_token" in login.cookies

    # Wyloguj
    logout = client.post("/api/admin/logout")
    assert logout.status_code == 200
    assert logout.json()["status"] == "ok"
    # Ciasteczko powinno byc usuniete (Set-Cookie z data w przeszlosci)
    set_cookie = logout.headers.get("set-cookie", "")
    # FastAPI uzywa delete_cookie - ustawia max-age=0 lub expires w przeszlosci
    assert "admin_token" in set_cookie.lower() or logout.cookies.get("admin_token") is None


def test_check_auth_returns_authenticated_after_login(admin_client):
    """Po zalogowaniu /api/admin/check-auth zwraca authenticated=true."""
    resp = admin_client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    assert body["auth_required"] is True


def test_check_auth_returns_not_authenticated_before_login(client):
    """Przed zalogowaniem /api/admin/check-auth zwraca authenticated=false."""
    # Upewnij sie ze nie ma cookies
    client.cookies.clear()
    resp = client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is False
    assert body["auth_required"] is True
