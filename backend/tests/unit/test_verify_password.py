"""Testy unit dla ``backend/auth/routes.py:verify_password``.

Priorytet 6.3 - bug-fix: Werkzeug hash (z ``launcher/services/admin_config_service``)
musi być akceptowany. Obecna implementacja porównywała tylko ``sha256(plain)``,
co powodowało że hasła ustawione w launcherze były cicho nieaktywne.
"""
from __future__ import annotations

import hashlib

import pytest
from werkzeug.security import generate_password_hash

from backend import config
from backend.auth.routes import verify_password


# ============================================================================
# Sha-256 hasła (stary format)
# ============================================================================


def test_verify_password_with_sha256_default(monkeypatch):
    """Hash ``sha256('admin123')`` akceptuje hasło ``admin123`` (stary fallback)."""
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")
    assert verify_password("admin123") is True


def test_verify_password_rejects_wrong_password(monkeypatch):
    """Zły plaintext odrzucany (nawet przy domyślnym haśle)."""
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")
    assert verify_password("wrong_password") is False


def test_verify_password_rejects_empty_password(monkeypatch):
    """Puste hasło odrzucane."""
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")
    assert verify_password("") is False


# ============================================================================
# Werkzeug hasła (nowy format z launchera)
# ============================================================================


def test_verify_password_with_werkzeug_hash(monkeypatch):
    """Werkzeug hash (``scrypt:...$...``) akceptuje hasło weryfikowane przez ``check_password_hash``."""
    werkzeug_hash = generate_password_hash("SuperTajne123!")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", werkzeug_hash)
    assert verify_password("SuperTajne123!") is True


def test_verify_password_with_werkzeug_hash_rejects_wrong(monkeypatch):
    """Werkzeug hash odrzuca błędne hasło."""
    werkzeug_hash = generate_password_hash("SuperTajne123!")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", werkzeug_hash)
    assert verify_password("wrong") is False


def test_verify_password_werkzeug_priority_over_sha256(monkeypatch):
    """Gdy hash wygląda jak Werkzeug → użyj Werkzeug, NIE sha256."""
    werkzeug_hash = generate_password_hash("NoweHaslo2026")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", werkzeug_hash)
    # sha256("NoweHaslo2026") byłby inny - ważne że Werkzeug wygrywa
    sha256_of_new = hashlib.sha256(b"NoweHaslo2026").hexdigest()
    assert werkzeug_hash != sha256_of_new  # sanity check
    assert verify_password("NoweHaslo2026") is True
    assert verify_password("admin123") is False  # stare hasło nie działa


# ============================================================================
# Anty-regresja
# ============================================================================


def test_verify_password_handles_none_hash(monkeypatch):
    """Gdyby ``ADMIN_PASSWORD_HASH`` to ``None`` → traktuj jak pusty."""
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", None)
    assert verify_password("admin123") is True
    assert verify_password("wrong") is False
