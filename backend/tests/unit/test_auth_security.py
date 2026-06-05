"""Testy utility ``backend/auth/security.py`` - diagnostyka bezpieczeństwa admina.

Funkcje:
- ``is_default_admin_password()`` → czy hash to pusty/sha256("admin123")?
- ``is_default_secret_key()`` → czy SECRET_KEY to fallback?
- ``is_production_mode()`` → czy ENVIRONMENT/PRODUCTION=1?
- ``get_admin_security_status()`` → słownik z całością + lista ostrzeżeń.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from unittest import mock

import pytest

from backend.auth import security as sec
from backend.config import ADMIN_PASSWORD_HASH, SECRET_KEY
from backend.auth.security import assert_safe_secret_key


# ============================================================================
# Stałe pomocnicze
# ============================================================================

# Hash SHA-256("admin123") - referencyjna wartość dla testu fallbacku
DEFAULT_ADMIN_HASH = hashlib.sha256(b"admin123").hexdigest()
# Domyślny SECRET_KEY (z backend/config.py)
DEFAULT_SECRET_KEY = "dev-secret-change-me"


# ============================================================================
# is_default_admin_password
# ============================================================================


class TestIsDefaultAdminPassword:
    def test_empty_hash_returns_true(self, monkeypatch):
        """Gdy ``ADMIN_PASSWORD_HASH`` puste → hasło domyślne aktywne."""
        monkeypatch.setattr(sec.config, "ADMIN_PASSWORD_HASH", "")
        assert sec.is_default_admin_password() is True

    def test_sha256_admin123_returns_true(self, monkeypatch):
        """Hash ``sha256('admin123')`` to nadal hasło domyślne."""
        monkeypatch.setattr(sec.config, "ADMIN_PASSWORD_HASH", DEFAULT_ADMIN_HASH)
        assert sec.is_default_admin_password() is True

    def test_werkzeug_hash_returns_false(self, monkeypatch):
        """Werkzeug hash (``scrypt:...$...``) to NIE hasło domyślne."""
        werkzeug = "scrypt:32768:8:1$abc$def"
        monkeypatch.setattr(sec.config, "ADMIN_PASSWORD_HASH", werkzeug)
        assert sec.is_default_admin_password() is False


# ============================================================================
# is_default_secret_key
# ============================================================================


class TestIsDefaultSecretKey:
    def test_default_secret_key_returns_true(self, monkeypatch):
        monkeypatch.setattr(sec.config, "SECRET_KEY", DEFAULT_SECRET_KEY)
        assert sec.is_default_secret_key() is True

    def test_changed_secret_key_returns_false(self, monkeypatch):
        monkeypatch.setattr(sec.config, "SECRET_KEY", "x" * 64)
        assert sec.is_default_secret_key() is False


# ============================================================================
# is_production_mode
# ============================================================================


class TestIsProductionMode:
    def test_production_env_var_true(self, monkeypatch):
        monkeypatch.setattr(sec.config, "PRODUCTION", True)
        assert sec.is_production_mode() is True

    def test_production_env_var_false(self, monkeypatch):
        monkeypatch.setattr(sec.config, "PRODUCTION", False)
        assert sec.is_production_mode() is False

    def test_production_env_var_default_false(self):
        """Domyślnie (gdy brak env var) NIE jesteśmy w produkcji."""
        assert sec.is_production_mode() is False


# ============================================================================
# get_admin_security_status
# ============================================================================


class TestGetAdminSecurityStatus:
    def test_returns_expected_keys(self, monkeypatch):
        """Zwraca dict z ``auth_enabled``, ``using_default_password``,
        ``using_default_secret_key``, ``is_production``, ``warnings``."""
        monkeypatch.setattr(sec.config, "ADMIN_AUTH_ENABLED", True)
        monkeypatch.setattr(sec.config, "ADMIN_PASSWORD_HASH", "scrypt:abc$def")
        monkeypatch.setattr(sec.config, "SECRET_KEY", "x" * 64)
        monkeypatch.setattr(sec.config, "PRODUCTION", False)
        status = sec.get_admin_security_status()
        assert "auth_enabled" in status
        assert "using_default_password" in status
        assert "using_default_secret_key" in status
        assert "is_production" in status
        assert "warnings" in status
        assert isinstance(status["warnings"], list)

    def test_warnings_for_default_password(self, monkeypatch):
        """Domyślne hasło → ostrzeżenie na liście."""
        monkeypatch.setattr(sec.config, "ADMIN_AUTH_ENABLED", True)
        monkeypatch.setattr(sec.config, "ADMIN_PASSWORD_HASH", "")
        monkeypatch.setattr(sec.config, "SECRET_KEY", "x" * 64)
        monkeypatch.setattr(sec.config, "PRODUCTION", False)
        status = sec.get_admin_security_status()
        assert any("admin123" in w for w in status["warnings"])

    def test_warnings_for_default_secret_key(self, monkeypatch):
        """Domyślny SECRET_KEY → ostrzeżenie."""
        monkeypatch.setattr(sec.config, "ADMIN_AUTH_ENABLED", True)
        monkeypatch.setattr(sec.config, "ADMIN_PASSWORD_HASH", "scrypt:abc$def")
        monkeypatch.setattr(sec.config, "SECRET_KEY", DEFAULT_SECRET_KEY)
        monkeypatch.setattr(sec.config, "PRODUCTION", False)
        status = sec.get_admin_security_status()
        assert any("SECRET_KEY" in w for w in status["warnings"])

    def test_warnings_for_auth_disabled(self, monkeypatch):
        """Auth wyłączony → ostrzeżenie (nawet w dev)."""
        monkeypatch.setattr(sec.config, "ADMIN_AUTH_ENABLED", False)
        monkeypatch.setattr(sec.config, "ADMIN_PASSWORD_HASH", "")
        monkeypatch.setattr(sec.config, "SECRET_KEY", "x" * 64)
        monkeypatch.setattr(sec.config, "PRODUCTION", False)
        status = sec.get_admin_security_status()
        assert any("autoryzacja" in w.lower() or "auth" in w.lower() for w in status["warnings"])

    def test_no_warnings_when_all_ok(self, monkeypatch):
        """Gdy wszystko OK → pusta lista ostrzeżeń."""
        monkeypatch.setattr(sec.config, "ADMIN_AUTH_ENABLED", True)
        monkeypatch.setattr(sec.config, "ADMIN_PASSWORD_HASH", "scrypt:abc$def")
        monkeypatch.setattr(sec.config, "SECRET_KEY", "x" * 64)
        monkeypatch.setattr(sec.config, "PRODUCTION", False)
        status = sec.get_admin_security_status()
        assert status["warnings"] == []


# ============================================================================
# Priorytet 6.6: assert_safe_secret_key (walidacja na starcie backendu)
# ============================================================================


def test_assert_safe_secret_key_passes_in_dev_with_default():
    """W dev (PRODUCTION=False) nawet fallback SECRET_KEY przechodzi."""
    # is_production=False, key=DEFAULT → brak wyjątku
    assert_safe_secret_key(is_production=False, secret_key=sec.DEFAULT_SECRET_KEY)


def test_assert_safe_secret_key_passes_in_dev_with_custom():
    """Dev + custom SECRET_KEY → brak wyjątku."""
    assert_safe_secret_key(is_production=False, secret_key="x" * 64)


def test_assert_safe_secret_key_raises_in_prod_with_default():
    """PRODUKCJA + fallback SECRET_KEY → ValueError (Priorytet 6.6)."""
    with pytest.raises(ValueError) as exc_info:
        assert_safe_secret_key(
            is_production=True,
            secret_key=sec.DEFAULT_SECRET_KEY,
        )
    # Komunikat musi wspominać o SECRET_KEY i .env
    msg = str(exc_info.value)
    assert "SECRET_KEY" in msg
    assert ".env" in msg or "FLASK_SECRET_KEY" in msg


def test_assert_safe_secret_key_passes_in_prod_with_custom():
    """PRODUKCJA + custom SECRET_KEY → brak wyjątku."""
    assert_safe_secret_key(is_production=True, secret_key="super-bezpieczny-klucz-2026")


# ============================================================================
# Priorytet 6.7: get_network_security_warnings() - ostrzeżenie dla trybu sieciowego
# ============================================================================
# Gdy ADMIN_AUTH_ENABLED=False i użytkownik udostępnia backend w sieci LAN
# (start_network_server), każdy w sieci może zmieniać dane. Funkcja zwraca
# listę ostrzeżeń, którą network_runtime powinien wyświetlić użytkownikowi.


def test_network_warnings_present_when_auth_disabled(monkeypatch):
    """ADMIN_AUTH_ENABLED=False → ostrzeżenie zwrócone."""
    monkeypatch.setattr(sec.config, "ADMIN_AUTH_ENABLED", False)
    warnings = sec.get_network_security_warnings()
    assert len(warnings) >= 1
    # Ostrzeżenie musi wspominać o uwierzytelnianiu i .env
    joined = " ".join(warnings).lower()
    assert "uwierzytelnian" in joined or "auth" in joined
    assert ".env" in joined or "admin_auth" in joined


def test_network_warnings_empty_when_auth_enabled(monkeypatch):
    """ADMIN_AUTH_ENABLED=True → brak ostrzeżeń (konfiguracja bezpieczna)."""
    monkeypatch.setattr(sec.config, "ADMIN_AUTH_ENABLED", True)
    warnings = sec.get_network_security_warnings()
    assert warnings == []


def test_network_warnings_safe_when_config_missing(monkeypatch):
    """Gdy config nie ma atrybutu → bez wyjątku, ostrzeżenie zwrócone (bezpieczne)."""
    # Usuwamy atrybut
    monkeypatch.delattr(sec.config, "ADMIN_AUTH_ENABLED", raising=False)
    warnings = sec.get_network_security_warnings()
    # Domyślnie uznajemy za niebezpieczne (gdy nie wiemy) → ostrzeżenie
    assert len(warnings) >= 1


# ============================================================================
# Priorytet 6.8: get_cors_allowed_origins() - CORS hardening
# ============================================================================
# Domyślnie ``allow_origins=["*"]`` z ``allow_credentials=True`` jest niebezpieczne
# (przeglądarka odrzuca, ale świadczy o braku świadomości). W produkcji
# CORS_ALLOWED_ORIGINS musi być ustawione. W dev fallback ["*"] z ostrzeżeniem.


def test_cors_origins_wildcard_in_dev_without_env(monkeypatch):
    """Dev (PRODUCTION=False) + brak CORS_ALLOWED_ORIGINS → ['*']."""
    monkeypatch.setattr(sec.config, "PRODUCTION", False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    origins = sec.get_cors_allowed_origins()
    assert origins == ["*"]


def test_cors_origins_custom_list_when_env_set(monkeypatch):
    """CORS_ALLOWED_ORIGINS=http://a,http://b → ['http://a', 'http://b']."""
    monkeypatch.setattr(sec.config, "PRODUCTION", False)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000, http://192.168.1.5")
    try:
        origins = sec.get_cors_allowed_origins()
        assert origins == ["http://localhost:3000", "http://192.168.1.5"]
    finally:
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)


def test_cors_origins_raises_in_prod_without_env(monkeypatch):
    """PRODUKCJA + brak CORS_ALLOWED_ORIGINS → ValueError (bezpieczeństwo)."""
    monkeypatch.setattr(sec.config, "PRODUCTION", True)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    with pytest.raises(ValueError) as exc_info:
        sec.get_cors_allowed_origins()
    msg = str(exc_info.value)
    assert "CORS_ALLOWED_ORIGINS" in msg
