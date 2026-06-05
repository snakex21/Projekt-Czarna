"""Diagnostyka bezpieczeństwa admina (Priorytet 6.1).

Dostarcza funkcje sprawdzające czy aplikacja używa domyślnych/niebezpiecznych
wartości konfiguracji (``SECRET_KEY``, hasło ``admin123`` itp.).

Używane przez:
- endpoint ``GET /api/admin/auth-status`` (6.2),
- walidację startup (6.6),
- launcher UI karta "Bezpieczeństwo admina" (6.5).

Domyślne wartości w ``backend/config.py`` to znane sentinelle —
``is_default_*`` wykrywa je przez porównanie i przez rozpoznanie formatu hasha.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from backend import config


# Domyślna wartość SECRET_KEY w kodzie (musi zgadzać się z backend/config.py).
# Sentinel wykrywany przez ``is_default_secret_key()``.
DEFAULT_SECRET_KEY = "dev-secret-change-me"
# Domyślne hasło admina (musi zgadzać się z auth/routes.py fallback).
DEFAULT_ADMIN_PASSWORD = "admin123"
# SHA-256("admin123") - rozpoznawane jako "domyślne" nawet jeśli zapisane jawnie.
DEFAULT_ADMIN_PASSWORD_SHA256 = hashlib.sha256(b"admin123").hexdigest()


def is_default_admin_password() -> bool:
    """``True`` jeśli ``ADMIN_PASSWORD_HASH`` to pusty/hash domyślnego hasła.

    Trzy przypadki traktowane jako "domyślne":
    - pusty string (fallback w ``auth/routes.py`` → ``admin123``),
    - ``sha256("admin123")`` (jawne wpisanie domyślnego hasła w SHA-256),
    - ``None`` (gdyby ktoś ustawił w env na ``null``).

    Werkzeug hash (``scrypt:...$...``) traktowany jest jako "własne hasło".
    """
    h = getattr(config, "ADMIN_PASSWORD_HASH", "") or ""
    if not h:
        return True
    if h == DEFAULT_ADMIN_PASSWORD_SHA256:
        return True
    return False


def is_default_secret_key() -> bool:
    """``True`` jeśli ``SECRET_KEY`` to fallback z kodu (``dev-secret-change-me``)."""
    return getattr(config, "SECRET_KEY", "") == DEFAULT_SECRET_KEY


def is_production_mode() -> bool:
    """``True`` jeśli ``PRODUCTION=1`` lub ``ENVIRONMENT=production`` w env."""
    return bool(getattr(config, "PRODUCTION", False))


def get_admin_security_status() -> Dict[str, Any]:
    """Zwraca słownik z aktualnym stanem bezpieczeństwa admina.

    Struktura:
    - ``auth_enabled`` (bool): czy ``ADMIN_AUTH_ENABLED=1``,
    - ``using_default_password`` (bool): ``is_default_admin_password()``,
    - ``using_default_secret_key`` (bool): ``is_default_secret_key()``,
    - ``is_production`` (bool): ``is_production_mode()``,
    - ``warnings`` (list[str]): lista komunikatów do wyświetlenia w UI.
    """
    auth_enabled = bool(getattr(config, "ADMIN_AUTH_ENABLED", False))
    using_default_pw = is_default_admin_password()
    using_default_key = is_default_secret_key()
    is_prod = is_production_mode()

    warnings: List[str] = []
    if not auth_enabled:
        warnings.append(
            "Autoryzacja admina jest wyłączona (ADMIN_AUTH_ENABLED=0). "
            "Każdy ma dostęp do panelu admina."
        )
    if auth_enabled and using_default_pw:
        warnings.append(
            "Działa domyślne hasło admina 'admin123'. "
            "Zmień hasło w Ustawieniach Administratora."
        )
    if using_default_key:
        if is_prod:
            warnings.append(
                "KRYTYCZNE: SECRET_KEY ma wartość domyślną w trybie produkcyjnym. "
                "Ustaw FLASK_SECRET_KEY w .env na losowy ciąg (>=32 znaki)."
            )
        else:
            warnings.append(
                "SECRET_KEY ma wartość domyślną (dev-secret-change-me). "
                "Przed publikacją ustaw FLASK_SECRET_KEY w .env."
            )
    if auth_enabled and using_default_pw and is_prod:
        warnings.append(
            "KRYTYCZNE: Domyślne hasło admina 'admin123' w trybie produkcyjnym!"
        )

    return {
        "auth_enabled": auth_enabled,
        "using_default_password": using_default_pw,
        "using_default_secret_key": using_default_key,
        "is_production": is_prod,
        "warnings": warnings,
    }


def assert_safe_secret_key(is_production: bool, secret_key: str) -> None:
    """Walidacja bezpieczeństwa na starcie backendu (Priorytet 6.6).

    W trybie produkcyjnym (``is_production=True``) rzuca ``ValueError`` gdy
    ``SECRET_KEY`` to fallback (``dev-secret-change-me``). W dev przechodzi
    bezwarunkowo - bo developerzy często testują z domyślnym kluczem.

    Args:
        is_production: wynik ``is_production_mode()``.
        secret_key: aktualna wartość ``config.SECRET_KEY``.

    Raises:
        ValueError: gdy produkcja + fallback.
    """
    if not is_production:
        return  # dev - nie blokujemy startu
    if secret_key == DEFAULT_SECRET_KEY:
        raise ValueError(
            "KRYTYCZNE: SECRET_KEY ma wartość domyślną w trybie produkcyjnym. "
            "Ustaw FLASK_SECRET_KEY w backend/.env na losowy ciąg (>=32 znaki). "
            "Wygeneruj np. komendą: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )


def get_network_security_warnings() -> list:
    """Ostrzeżenia dla trybu sieciowego (Priorytet 6.7).

    Gdy administrator uruchamia backend w trybie sieciowym (LAN, ``--host 0.0.0.0``),
    a ``ADMIN_AUTH_ENABLED`` jest wyłączone - każdy w sieci może zmieniać dane.

    Returns:
        Lista ostrzeżeń po polsku. Pusta lista = konfiguracja bezpieczna.
    """
    warnings: list = []
    # Domyślnie uznajemy za niebezpieczne (gdy nie wiemy) → ostrzeżenie
    auth_enabled = getattr(config, "ADMIN_AUTH_ENABLED", False)
    if not auth_enabled:
        warnings.append(
            "🚨 Backend udostępniony w sieci BEZ uwierzytelniania admina. "
            "Każdy w sieci LAN może modyfikować dane przez /api/admin/*. "
            "Ustaw ADMIN_AUTH_ENABLED=1 i skonfiguruj hasło w backend/.env."
        )
    return warnings


def get_cors_allowed_origins() -> list:
    """Lista originów dla CORS middleware (Priorytet 6.8).

    Czyta env ``CORS_ALLOWED_ORIGINS`` (lista po przecinku).
    - W dev (PRODUCTION=False) + brak env → ``["*"]`` (developer convenience).
    - W dev z env → lista z env.
    - W produkcji + brak env → ``ValueError`` (bezpieczeństwo).
    - W produkcji z env → lista z env.

    Returns:
        Lista originów (np. ``["http://localhost:3000", "https://app.example.com"]``).

    Raises:
        ValueError: gdy produkcja i brak ``CORS_ALLOWED_ORIGINS``.
    """
    import os
    env_value = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    is_prod = getattr(config, "PRODUCTION", False)
    if not env_value:
        if is_prod:
            raise ValueError(
                "KRYTYCZNE: CORS_ALLOWED_ORIGINS nie jest ustawione w produkcji. "
                "Ustaw w backend/.env listę originów po przecinku, np. "
                "CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com"
            )
        return ["*"]  # dev fallback
    # Parsuj listę po przecinku, strip whitespace, odrzucaj puste
    return [o.strip() for o in env_value.split(",") if o.strip()]
