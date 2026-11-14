"""Testy integracyjne endpointu ``GET /api/admin/auth-status``.

Weryfikujemy:
- Publiczny endpoint (bez logowania) — frontend sprawdza przed wyświetleniem panelu,
- Wsteczna kompatybilność pola ``enabled``,
- Pełny status bezpieczeństwa (Priorytet 6.2): ``auth_enabled``,
  ``using_default_password``, ``using_default_secret_key``, ``is_production``,
  ``warnings``.
- JSON content-type (nie HTML fallback).
"""
from __future__ import annotations


def test_auth_status_is_public(admin_client):
    """Endpoint jest publiczny - nie wymaga logowania."""
    # Upewnij się że brak cookies sesji
    admin_client.cookies.clear()
    resp = admin_client.get("/api/admin/auth-status")
    assert resp.status_code == 200, (
        f"Endpoint powinien być publiczny, mamy {resp.status_code}: {resp.text}"
    )


def test_auth_status_returns_backward_compatible_enabled_field(admin_client):
    """Pole ``enabled`` jest zachowane (kompatybilność z frontendem)."""
    resp = admin_client.get("/api/admin/auth-status")
    data = resp.json()
    assert "enabled" in data, "Brak wstecznie kompatybilnego pola 'enabled'"
    assert isinstance(data["enabled"], bool)


def test_auth_status_returns_security_fields(admin_client):
    """Zwraca pełny status bezpieczeństwa z Priorytetu 6.2."""
    resp = admin_client.get("/api/admin/auth-status")
    data = resp.json()
    assert "auth_enabled" in data
    assert "using_default_password" in data
    assert "using_default_secret_key" in data
    assert "is_production" in data
    assert "warnings" in data
    assert isinstance(data["warnings"], list)
    # auth_enabled i enabled są aliasami
    assert data["auth_enabled"] == data["enabled"]


def test_auth_status_returns_json_content_type(admin_client):
    """Content-Type: application/json (nie HTML fallback)."""
    resp = admin_client.get("/api/admin/auth-status")
    ct = resp.headers.get("content-type", "")
    assert "application/json" in ct, f"Oczekiwano JSON, mamy: {ct}"


def test_auth_status_reports_setup_required_without_password(admin_client, monkeypatch):
    """Brak hasła admina → setup_required + instrukcja konfiguracji (bez hasła domyślnego)."""
    from backend import config
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")
    monkeypatch.setattr(config, "ADMIN_AUTH_ENABLED", True)
    resp = admin_client.get("/api/admin/auth-status")
    data = resp.json()
    assert data["using_default_password"] is True
    assert data["setup_required"] is True
    assert "set_admin_password" in data["setup_instructions"]
    assert any("set_admin_password" in w for w in data["warnings"])


def test_auth_status_treats_admin123_hash_as_not_configured(admin_client, monkeypatch):
    """Hash hasła 'admin123' nie liczy się jako konfiguracja."""
    from backend import config
    from werkzeug.security import generate_password_hash
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", generate_password_hash("admin123", method="pbkdf2:sha256:1000"))
    data = admin_client.get("/api/admin/auth-status").json()
    assert data["setup_required"] is True


def test_auth_status_ok_with_configured_password(admin_client):
    data = admin_client.get("/api/admin/auth-status").json()
    assert data["setup_required"] is False
    assert data["setup_instructions"] is None
    assert data["warnings"] == []


# ============================================================================
# POST /api/admin/change-password
# ============================================================================


def _use_password(client, monkeypatch, password):
    """Ustawia hash hasła admina i loguje klienta tym hasłem."""
    from backend import config
    from werkzeug.security import generate_password_hash
    monkeypatch.setattr(config, "ADMIN_AUTH_ENABLED", True)
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", generate_password_hash(password, method="pbkdf2:sha256:1000"))
    client.cookies.clear()
    resp = client.post("/api/admin/login", json={"username": "admin", "password": password})
    assert resp.status_code == 200, resp.text


def test_change_password_requires_auth(admin_client, monkeypatch):
    """Endpoint wymaga auth (admin_required)."""
    from backend import config
    monkeypatch.setattr(config, "ADMIN_AUTH_ENABLED", True)
    admin_client.cookies.clear()
    resp = admin_client.post(
        "/api/admin/change-password",
        json={"current_password": "x", "new_password": "y"},
    )
    assert resp.status_code == 401, (
        f"Oczekiwano 401 bez auth, mamy {resp.status_code}"
    )


def test_change_password_rejects_wrong_current(admin_client, monkeypatch):
    """Błędne obecne hasło → 401."""
    _use_password(admin_client, monkeypatch, "StareHaslo123")
    resp = admin_client.post(
        "/api/admin/change-password",
        json={"current_password": "WRONG", "new_password": "NoweSilne123"},
    )
    assert resp.status_code == 401


def test_change_password_rejects_short_new_password(admin_client, monkeypatch):
    """Nowe hasło < 8 znaków → 400."""
    _use_password(admin_client, monkeypatch, "StareHaslo123")
    resp = admin_client.post(
        "/api/admin/change-password",
        json={"current_password": "StareHaslo123", "new_password": "krot"},
    )
    assert resp.status_code == 400, resp.text


def test_change_password_rejects_same_as_current(admin_client, monkeypatch):
    """Nowe hasło == stare → 400."""
    _use_password(admin_client, monkeypatch, "StareHaslo123")
    resp = admin_client.post(
        "/api/admin/change-password",
        json={"current_password": "StareHaslo123", "new_password": "StareHaslo123"},
    )
    assert resp.status_code == 400


def test_change_password_rejected_when_auth_disabled(admin_client, monkeypatch):
    """Gdy autoryzacja jawnie wyłączona → 400 (nie ma sensu zmieniać hasła)."""
    from backend import config
    monkeypatch.setattr(config, "ADMIN_AUTH_ENABLED", False)
    resp = admin_client.post(
        "/api/admin/change-password",
        json={"current_password": "x", "new_password": "NoweSilne123"},
    )
    assert resp.status_code == 400


def test_change_password_succeeds_writes_env_and_invalidates_other_sessions(admin_client, monkeypatch, tmp_path):
    """Sukces: hash zapisany do .env (w tmp), stare sesje unieważnione, bieżąca dostaje nowy token."""
    from backend import config
    from backend.auth import create_session_token
    _use_password(admin_client, monkeypatch, "StareHaslo123")
    other_session = create_session_token()

    env_file = tmp_path / ".env"
    env_file.write_text("ADMIN_USERNAME=admin\nADMIN_PASSWORD_HASH=old\n", encoding="utf-8")
    import launcher.services.admin_config_service as acs_mod
    original = acs_mod.save_admin_password_hash
    monkeypatch.setattr(acs_mod, "save_admin_password_hash", lambda _path, new_hash: original(str(env_file), new_hash))

    resp = admin_client.post(
        "/api/admin/change-password",
        json={"current_password": "StareHaslo123", "new_password": "NoweSilneHaslo2026"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"
    assert config.ADMIN_PASSWORD_HASH.split(":", 1)[0] in ("scrypt", "pbkdf2")
    assert config.ADMIN_PASSWORD_HASH in env_file.read_text(encoding="utf-8")

    # bieżący klient nadal zalogowany (nowy token), inna sesja - nie
    assert admin_client.get("/api/admin/check-auth").json()["authenticated"] is True
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as other:
        other.cookies.set("admin_token", other_session)
        assert other.get("/api/admin/check-auth").json()["authenticated"] is False
