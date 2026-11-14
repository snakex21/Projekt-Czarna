"""
Testy jednostkowe backend/auth/routes.py: tokeny sesji, hasła, brak furtek.
"""
import hashlib
import inspect
import time

import pytest
from werkzeug.security import generate_password_hash

from backend import config as backend_config
from backend.auth import (
    admin_required,
    create_session_token,
    decode_session_token,
    get_token,
    is_admin_authenticated,
    is_admin_configured,
    revoke_session_token,
    verify_password,
)
from backend.auth import routes as auth_routes


def _fast_hash(password):
    return generate_password_hash(password, method="pbkdf2:sha256:1000")


def _fake_request(token="", extra_cookies=None, user_agent="Mozilla/5.0"):
    """Obiekt udający fastapi.Request z .cookies i .headers."""
    class _Req:
        def __init__(self):
            self.cookies = {"admin_token": token} if token else {}
            self.cookies.update(extra_cookies or {})
            self.headers = {"user-agent": user_agent}
    return _Req()


# ================================================================================
# Tokeny sesji
# ================================================================================


def test_tokens_are_unique_per_login():
    """Każde logowanie dostaje inny token (losowy jti), a nie stałą sha256(SECRET_KEY)."""
    t1 = create_session_token()
    t2 = create_session_token()
    assert t1 != t2
    assert decode_session_token(t1) is not None
    assert decode_session_token(t2) is not None


def test_token_is_not_derivable_from_secret_key_alone():
    """Dawny token sha256('admin:'+SECRET_KEY) nie jest akceptowany."""
    legacy = hashlib.sha256(f"admin:{backend_config.SECRET_KEY}".encode()).hexdigest()
    assert decode_session_token(legacy) is None


def test_token_expires():
    token = create_session_token(ttl_seconds=60, now=time.time() - 120)
    assert decode_session_token(token) is None


def test_token_rejected_after_secret_key_change(monkeypatch):
    token = create_session_token()
    monkeypatch.setattr(backend_config, "SECRET_KEY", "inny-klucz-" + "x" * 40)
    assert decode_session_token(token) is None


def test_token_rejected_after_password_change(monkeypatch):
    token = create_session_token()
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", _fast_hash("ZupelnieNoweHaslo1"))
    assert decode_session_token(token) is None


def test_token_rejected_after_username_change(monkeypatch):
    token = create_session_token()
    monkeypatch.setattr(backend_config, "ADMIN_USERNAME", "ktos-inny")
    assert decode_session_token(token) is None


@pytest.mark.parametrize("bad", ["", "abc", "a.b", "a.b.c", "x" * 5000, None, "true"])
def test_malformed_tokens_rejected(bad):
    assert decode_session_token(bad) is None


def test_tampered_payload_rejected():
    token = create_session_token()
    body, sig = token.split(".")
    tampered = body[:-2] + ("AA" if body[-2:] != "AA" else "BB")
    assert decode_session_token(f"{tampered}.{sig}") is None


def test_revoked_token_rejected():
    token = create_session_token()
    assert revoke_session_token(token) is True
    assert decode_session_token(token) is None
    # Ponowne odwołanie nieaktywnego tokena
    assert revoke_session_token(token) is False


def test_get_token_returns_valid_session_token():
    assert decode_session_token(get_token()) is not None


# ================================================================================
# verify_password / konfiguracja
# ================================================================================


def test_no_default_password_when_hash_missing(monkeypatch):
    """Brak ADMIN_PASSWORD_HASH → żadne hasło (w tym 'admin123') nie działa."""
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", "")
    assert is_admin_configured() is False
    for pw in ("admin123", "", "admin"):
        assert verify_password(pw) is False


def test_none_hash_is_not_configured(monkeypatch):
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", None)
    assert is_admin_configured() is False
    assert verify_password("admin123") is False


@pytest.mark.parametrize("weak", ["admin123", "admin", "password"])
def test_weak_password_hashes_are_not_configuration(monkeypatch, weak):
    """Hash znanego domyślnego hasła (SHA-256 lub Werkzeug) = brak konfiguracji."""
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", hashlib.sha256(weak.encode()).hexdigest())
    assert is_admin_configured() is False
    assert verify_password(weak) is False
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", _fast_hash(weak))
    assert is_admin_configured() is False
    assert verify_password(weak) is False


def test_legacy_sha256_hash_still_supported(monkeypatch):
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", hashlib.sha256(b"my-secret-123").hexdigest())
    assert verify_password("my-secret-123") is True
    assert verify_password("admin123") is False
    assert verify_password("") is False


def test_werkzeug_hash(monkeypatch):
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", _fast_hash("SuperTajne123!"))
    assert verify_password("SuperTajne123!") is True
    assert verify_password("wrong") is False
    assert verify_password("") is False


# ================================================================================
# is_admin_authenticated - brak furtek
# ================================================================================


def test_is_admin_authenticated_true_with_valid_token():
    assert is_admin_authenticated(_fake_request(token=create_session_token())) is True


def test_is_admin_authenticated_false_without_token():
    assert is_admin_authenticated(_fake_request()) is False


def test_is_admin_authenticated_false_when_not_configured(monkeypatch):
    token = create_session_token()
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", "")
    assert is_admin_authenticated(_fake_request(token=token)) is False


@pytest.mark.parametrize("ua", ["testclient", "Mozilla/5.0", "curl/8.0"])
def test_legacy_admin_logged_in_cookie_never_authenticates(ua):
    """Dawna furtka: User-Agent=testclient + admin_logged_in=true. Musi być martwa."""
    req = _fake_request(extra_cookies={"admin_logged_in": "true"}, user_agent=ua)
    assert is_admin_authenticated(req) is False


def test_auth_decision_does_not_read_headers():
    """Decyzja o autoryzacji opiera się wyłącznie na podpisanym ciasteczku sesji."""
    for fn in (auth_routes.is_admin_authenticated, auth_routes.admin_required):
        src = inspect.getsource(fn).split('"""')[-1]  # bez docstringa
        assert "headers" not in src
        assert "admin_logged_in" not in src


# ================================================================================
# admin_required
# ================================================================================


def test_admin_required_is_coroutine_function():
    assert inspect.iscoroutinefunction(admin_required)


def test_auth_enabled_by_default_in_config():
    """Domyślnie (bez dwóch jawnych flag) autoryzacja jest włączona."""
    assert backend_config.ADMIN_AUTH_ENABLED is True
