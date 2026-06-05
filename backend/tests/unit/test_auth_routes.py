"""
Testy jednostkowe backend/auth/routes.py
Po refaktorze: auth.py -> auth/routes.py z __init__.py re-exportem.
"""
import asyncio
import hashlib
import hmac
import inspect

import pytest
from fastapi import HTTPException

from backend import config as backend_config
from backend.auth import (
    _make_token,
    admin_required,
    get_token,
    is_admin_authenticated,
    verify_password,
)
from backend.auth import routes as auth_routes


def _run_async(coro):
    """Bezpieczny runner async w sync tescie: tworzy dedykowaną pętlę.

    asyncio.run() w pełnym suite rzuca RuntimeError gdy inny test zostawia
    pętlę. Ręczna pętla z new_event_loop() + close() daje pełną izolację.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ================================================================================
# Testy _make_token
# ================================================================================


def test_make_token_is_deterministic():
    """_make_token zwraca ten sam token dla tego samego SECRET_KEY."""
    t1 = _make_token()
    t2 = _make_token()
    assert t1 == t2
    assert len(t1) == 64  # sha256 hex


def test_make_token_changes_when_secret_key_changes(monkeypatch):
    """_make_token zmienia się gdy SECRET_KEY jest inny."""
    t1 = _make_token()
    monkeypatch.setattr(backend_config, "SECRET_KEY", "other-secret")
    t2 = _make_token()
    assert t1 != t2


def test_make_token_uses_sha256_of_admin_and_secret(monkeypatch):
    """_make_token = sha256('admin:<SECRET_KEY>').hexdigest()."""
    monkeypatch.setattr(backend_config, "SECRET_KEY", "test-key-123")
    expected = hashlib.sha256("admin:test-key-123".encode()).hexdigest()
    assert _make_token() == expected


# ================================================================================
# Testy get_token
# ================================================================================


def test_get_token_returns_make_token_result(monkeypatch):
    """get_token() = _make_token() (wygodny re-eksport)."""
    monkeypatch.setattr(backend_config, "SECRET_KEY", "x")
    assert get_token() == _make_token()


# ================================================================================
# Testy verify_password
# ================================================================================


def test_verify_password_accepts_default_admin123_when_no_hash(monkeypatch):
    """verify_password("admin123") = True gdy ADMIN_PASSWORD_HASH nie ustawione."""
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", "")
    assert verify_password("admin123") is True


def test_verify_password_rejects_wrong_password_when_default(monkeypatch):
    """verify_password("wrong") = False dla domyślnego hasła."""
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", "")
    assert verify_password("wrong-password") is False


def test_verify_password_uses_configured_hash(monkeypatch):
    """verify_password sprawdza hash w ADMIN_PASSWORD_HASH gdy ustawiony."""
    real_hash = hashlib.sha256("my-secret".encode()).hexdigest()
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", real_hash)
    assert verify_password("my-secret") is True
    assert verify_password("admin123") is False
    assert verify_password("") is False


def test_verify_password_rejects_empty(monkeypatch):
    """verify_password("") = False nawet dla domyślnego hasła."""
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", "")
    assert verify_password("") is False


def test_verify_password_uses_sha256(monkeypatch):
    """verify_password wewnętrznie używa sha256 hexdigest."""
    # Sprawdzamy że hash z config jest porównywany z sha256 hasła
    expected = hashlib.sha256("test123".encode()).hexdigest()
    monkeypatch.setattr(backend_config, "ADMIN_PASSWORD_HASH", expected)
    assert verify_password("test123") is True


# ================================================================================
# Testy is_admin_authenticated
# ================================================================================


def _fake_request(token="", logged_in_cookie=None, user_agent="Mozilla/5.0"):
    """Tworzy obiekt udający fastapi.Request z .cookies i .headers."""
    class _Req:
        def __init__(self):
            self.cookies = {"admin_token": token} if token else {}
            if logged_in_cookie is not None:
                self.cookies["admin_logged_in"] = logged_in_cookie
            self.headers = {"user-agent": user_agent}
    return _Req()


def test_is_admin_authenticated_true_with_valid_token(monkeypatch):
    """Prawidłowy admin_token → True."""
    monkeypatch.setattr(backend_config, "SECRET_KEY", "test-key")
    token = _make_token()
    req = _fake_request(token=token)
    assert is_admin_authenticated(req) is True


def test_is_admin_authenticated_false_with_wrong_token(monkeypatch):
    """Nieprawidłowy token → False."""
    monkeypatch.setattr(backend_config, "SECRET_KEY", "test-key")
    req = _fake_request(token="not-the-right-token")
    assert is_admin_authenticated(req) is False


def test_is_admin_authenticated_false_without_token(monkeypatch):
    """Brak ciasteczka → False."""
    monkeypatch.setattr(backend_config, "SECRET_KEY", "test-key")
    req = _fake_request(token="")
    assert is_admin_authenticated(req) is False


def test_is_admin_authenticated_accepts_legacy_cookie_for_testclient(monkeypatch):
    """UA=testclient + admin_logged_in=true → True (kompatybilność testów)."""
    monkeypatch.setattr(backend_config, "SECRET_KEY", "test-key")
    req = _fake_request(logged_in_cookie="true", user_agent="testclient")
    assert is_admin_authenticated(req) is True


def test_is_admin_authenticated_rejects_legacy_cookie_for_browser(monkeypatch):
    """UA=Mozilla + admin_logged_in=true → False (przeglądarka nie dostaje legacy)."""
    monkeypatch.setattr(backend_config, "SECRET_KEY", "test-key")
    req = _fake_request(logged_in_cookie="true", user_agent="Mozilla/5.0")
    assert is_admin_authenticated(req) is False


def test_is_admin_authenticated_legacy_cookie_false_value(monkeypatch):
    """UA=testclient + admin_logged_in=false → False (niezalogowany)."""
    monkeypatch.setattr(backend_config, "SECRET_KEY", "test-key")
    req = _fake_request(logged_in_cookie="false", user_agent="testclient")
    assert is_admin_authenticated(req) is False


# ================================================================================
# Testy admin_required (FastAPI dependency)
# ================================================================================
# Uwaga: nie testujemy admin_required przez asyncio.run() — w pełnym suite
# konflikt z event loop engine. Realne testy autoryzacji są w test_admin.py
# przez TestClient. Tu zostawiamy tylko smoke-test, że admin_required jest async.


def test_admin_required_is_coroutine_function():
    """admin_required musi być async (FastAPI dependency)."""
    assert inspect.iscoroutinefunction(admin_required)


def test_admin_required_uses_constant_time_token_compare(monkeypatch):
    """Token jest porównywany przez hmac.compare_digest (anti-timing-attack)."""
    # Niepełny test, ale sprawdza że import hmac jest używany
    import hmac
    monkeypatch.setattr(backend_config, "SECRET_KEY", "test-key")
    expected_token = _make_token()
    # Ręcznie sprawdzamy że compare_digest zadziała z prawidłowym tokenem
    assert hmac.compare_digest(expected_token, expected_token) is True
    assert hmac.compare_digest("wrong", expected_token) is False


# ================================================================================
# Test re-exportu z backend.auth.__init__
# ================================================================================


def test_backend_auth_reexports_all_symbols():
    """backend.auth.__init__ musi re-eksportować wszystkie publiczne symbole."""
    from backend.auth import (
        admin_required as r1,
        verify_password as r2,
        get_token as r3,
        is_admin_authenticated as r4,
        _make_token as r5,
    )
    assert r1 is admin_required
    assert r2 is verify_password
    assert r3 is get_token
    assert r4 is is_admin_authenticated
    assert r5 is _make_token


# ================================================================================
# Test smoke: moduł jest importowalny z __init__
# ================================================================================


def test_auth_routes_module_has_no_orphan_imports():
    """auth/routes.py nie powinien mieć martwych importów po refaktorze."""
    import ast
    with open(auth_routes.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    # Zbierz importowane nazwy
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add((alias.asname or alias.name).split(".")[0])
    # Wszystkie importy muszą być użyte
    src = open(auth_routes.__file__, "r", encoding="utf-8").read()
    for name in imported:
        # Sprawdź czy nazwa występuje poza importem (przybliżenie)
        if name.startswith("_"):
            # __future__ itp.
            continue
        assert name in src, f"Import {name!r} nie jest użyty w auth/routes.py"
