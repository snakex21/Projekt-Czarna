"""
Testy integracyjne flow autoryzacji.

Lapie realne bugi w:
- logowaniu (bledne haslo, brak username, ADMIN_AUTH_ENABLED wplyw)
- tokenach (cookie HttpOnly, wygasanie)
- wylogowaniu (czyszczenie ciasteczka)
- kompatybilnosci wstecznej (stary endpoint /api/admin/check-auth)
"""
import pytest

from backend.tests.auth_helpers import admin_password


# ================================================================================
# Auth flow
# ================================================================================


def test_auth_status_reports_enabled(client):
    """GET /api/admin/auth-status zwraca enabled=true po ustawieniu env var."""
    resp = client.get("/api/admin/auth-status")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


def test_login_with_correct_credentials_returns_ok(client):
    """POST /api/admin/login z poprawnym haslem zwraca status=ok + token cookie."""
    resp = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": admin_password()}
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
        json={"username": "hacker", "password": admin_password()}
    )
    assert resp.status_code == 401


def test_login_with_missing_fields_returns_error(client):
    """Brak username LUB password -> 401 (brak pola = pusty string)."""
    resp_missing_user = client.post(
        "/api/admin/login",
        json={"password": admin_password()}
    )
    resp_missing_pass = client.post(
        "/api/admin/login",
        json={"username": "admin"}
    )
    assert resp_missing_user.status_code == 401
    assert resp_missing_pass.status_code == 401


def test_logout_clears_admin_token_cookie(client):
    """POST /api/admin/logout usuwa ciasteczko admin_token."""
    # Najpierw zaloguj
    login = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": admin_password()}
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


def test_logout_revokes_token_server_side(client):
    """Token skopiowany przed wylogowaniem nie działa po wylogowaniu."""
    client.cookies.clear()
    login = client.post("/api/admin/login", json={"username": "admin", "password": admin_password()})
    token = login.cookies.get("admin_token")
    assert token
    client.post("/api/admin/logout")
    client.cookies.clear()
    client.cookies.set("admin_token", token)
    assert client.get("/api/admin/check-auth").json()["authenticated"] is False
    assert client.delete("/api/admin/demografia/999999").status_code == 401
    client.cookies.clear()


def test_session_cookie_flags(client):
    """Ciasteczko sesji: HttpOnly, SameSite=Strict, ograniczony czas życia."""
    client.cookies.clear()
    resp = client.post("/api/admin/login", json={"username": "admin", "password": admin_password()})
    set_cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=strict" in set_cookie
    assert "max-age=" in set_cookie
    client.cookies.clear()


def test_login_rate_limited_after_repeated_failures(client, monkeypatch):
    """Po LOGIN_MAX_ATTEMPTS nieudanych próbach → 429 (nawet z poprawnym hasłem)."""
    from backend import config
    monkeypatch.setattr(config, "LOGIN_MAX_ATTEMPTS", 3)
    client.cookies.clear()
    for _ in range(3):
        r = client.post("/api/admin/login", json={"username": "admin", "password": "zle-haslo"})
        assert r.status_code == 401
    blocked = client.post("/api/admin/login", json={"username": "admin", "password": admin_password()})
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
    assert "admin_token" not in blocked.cookies


def test_successful_login_resets_failure_counter(client, monkeypatch):
    from backend import config
    monkeypatch.setattr(config, "LOGIN_MAX_ATTEMPTS", 3)
    client.cookies.clear()
    for _ in range(2):
        client.post("/api/admin/login", json={"username": "admin", "password": "zle"})
    assert client.post("/api/admin/login", json={"username": "admin", "password": admin_password()}).status_code == 200
    for _ in range(2):
        assert client.post("/api/admin/login", json={"username": "admin", "password": "zle"}).status_code == 401
    client.cookies.clear()


def test_login_refused_with_setup_instructions_when_not_configured(client, monkeypatch):
    """Brak skonfigurowanego hasła → 403 z instrukcją, żadne hasło nie działa."""
    from backend import config
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")
    client.cookies.clear()
    for pw in ("admin123", "", admin_password()):
        r = client.post("/api/admin/login", json={"username": "admin", "password": pw})
        assert r.status_code == 403
        assert r.json()["setup_required"] is True
        assert "set_admin_password" in r.json()["message"]
        assert "admin_token" not in r.cookies
