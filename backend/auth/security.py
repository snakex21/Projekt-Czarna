"""Diagnostyka bezpieczeństwa admina.

Dostarcza funkcje sprawdzające konfigurację bezpieczeństwa:

- czy skonfigurowano własne hasło administratora (nie ma hasła domyślnego),
- czy ``SECRET_KEY`` nie jest znaną zaślepką,
- listę originów CORS.

Używane przez:
- endpoint ``GET /api/admin/auth-status``,
- walidację przy starcie (``backend/main.py``),
- launcher UI (karta "Bezpieczeństwo admina", ostrzeżenia trybu sieciowego).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from backend import config

from .routes import SETUP_INSTRUCTIONS, is_admin_configured


def is_default_admin_password() -> bool:
    """``True`` gdy hasło admina NIE jest skonfigurowane (pusty hash albo hash
    znanego domyślnego hasła, np. ``admin123``)."""
    return not is_admin_configured()


def is_default_secret_key() -> bool:
    """``True`` jeśli ``SECRET_KEY`` to znana zaślepka z dawnych szablonów."""
    return str(getattr(config, "SECRET_KEY", "") or "") in config.WEAK_SECRET_KEYS


def is_production_mode() -> bool:
    """``True`` jeśli ``PRODUCTION=1`` lub ``ENVIRONMENT=production`` w env."""
    return bool(getattr(config, "PRODUCTION", False))


def get_admin_security_status() -> Dict[str, Any]:
    """Zwraca słownik z aktualnym stanem bezpieczeństwa admina.

    - ``auth_enabled`` (bool),
    - ``admin_configured`` (bool): czy ustawiono własne hasło admina,
    - ``setup_required`` (bool): ``auth_enabled and not admin_configured``,
    - ``using_default_password`` (bool): alias ``not admin_configured``,
    - ``using_default_secret_key`` (bool),
    - ``is_production`` (bool),
    - ``warnings`` (list[str]).
    """
    auth_enabled = bool(getattr(config, "ADMIN_AUTH_ENABLED", True))
    configured = is_admin_configured()
    using_default_key = is_default_secret_key()
    is_prod = is_production_mode()

    warnings: List[str] = []
    if not auth_enabled:
        warnings.append(
            "Autoryzacja admina jest wyłączona (ADMIN_AUTH_INSECURE_DISABLE=1). "
            "Każdy ma dostęp do panelu admina."
        )
    if auth_enabled and not configured:
        warnings.append(SETUP_INSTRUCTIONS)
    if using_default_key:
        warnings.append(
            "SECRET_KEY ma wartość-zaślepkę. Usuń FLASK_SECRET_KEY z .env "
            "(klucz zostanie wygenerowany automatycznie) albo ustaw losowy ciąg >= 32 znaki."
        )

    return {
        "auth_enabled": auth_enabled,
        "admin_configured": configured,
        "setup_required": auth_enabled and not configured,
        "using_default_password": not configured,
        "using_default_secret_key": using_default_key,
        "is_production": is_prod,
        "warnings": warnings,
    }


def assert_safe_secret_key(is_production: bool, secret_key: str) -> None:
    """Walidacja ``SECRET_KEY`` na starcie backendu.

    W trybie produkcyjnym odrzuca zaślepki i klucze krótsze niż
    ``config.MIN_SECRET_KEY_LENGTH``. W dev przechodzi (klucz i tak jest
    generowany automatycznie, gdy go brak).

    Raises:
        ValueError: gdy produkcja i słaby klucz.
    """
    if not is_production:
        return
    if secret_key in config.WEAK_SECRET_KEYS or len(secret_key) < config.MIN_SECRET_KEY_LENGTH:
        raise ValueError(
            "KRYTYCZNE: SECRET_KEY jest pusty, domyślny albo za krótki w trybie produkcyjnym. "
            "Usuń FLASK_SECRET_KEY z backend/.env (zostanie wygenerowany poza repozytorium) "
            "albo ustaw losowy ciąg >= 32 znaki, np.: "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )


def assert_safe_auth_config(is_production: bool, auth_enabled: bool) -> None:
    """W produkcji autoryzacja admina musi być włączona."""
    if is_production and not auth_enabled:
        raise ValueError("KRYTYCZNE: nie wolno wyłączać autoryzacji admina w trybie produkcyjnym.")


def get_network_security_warnings() -> list:
    """Ostrzeżenia dla trybu sieciowego (LAN, ``--host 0.0.0.0``).

    Returns:
        Lista ostrzeżeń po polsku. Pusta lista = konfiguracja bezpieczna.
    """
    warnings: list = []
    auth_enabled = getattr(config, "ADMIN_AUTH_ENABLED", False)
    if not auth_enabled:
        warnings.append(
            "🚨 Backend udostępniony w sieci BEZ uwierzytelniania admina. "
            "Każdy w sieci LAN może modyfikować dane przez /api/admin/*. "
            "Usuń ADMIN_AUTH_INSECURE_DISABLE z backend/.env."
        )
    elif not is_admin_configured():
        warnings.append(
            "Hasło admina nie jest skonfigurowane - edycja danych jest zablokowana. "
            + SETUP_INSTRUCTIONS
        )
    return warnings


def get_cors_allowed_origins() -> list:
    """Lista originów dla CORS middleware.

    Czyta env ``CORS_ALLOWED_ORIGINS`` (lista po przecinku).

    - brak env w dev → ``[]`` (tylko same-origin; frontend jest serwowany
      przez ten sam serwer, więc CORS nie jest potrzebny),
    - brak env w produkcji → ``ValueError`` (wymuszamy świadomą decyzję),
    - z env → lista z env. ``*`` jest dozwolone, ale wtedy ciasteczka
      (``allow_credentials``) są wyłączane w ``backend/main.py``.

    Raises:
        ValueError: gdy produkcja i brak ``CORS_ALLOWED_ORIGINS``.
    """
    env_value = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    is_prod = getattr(config, "PRODUCTION", False)
    if not env_value:
        if is_prod:
            raise ValueError(
                "KRYTYCZNE: CORS_ALLOWED_ORIGINS nie jest ustawione w produkcji. "
                "Ustaw w backend/.env listę originów po przecinku, np. "
                "CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com"
            )
        return []
    return [o.strip() for o in env_value.split(",") if o.strip()]
