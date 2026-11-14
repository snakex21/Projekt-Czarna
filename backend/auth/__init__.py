"""Re-exporty autoryzacji dla wygodnych importów.

Użycie:
    from backend.auth import admin_required, verify_password, is_admin_authenticated
"""

from .routes import (
    COOKIE_NAME,
    SETUP_INSTRUCTIONS,
    admin_required,
    clear_revoked_sessions,
    create_session_token,
    decode_session_token,
    get_token,
    is_admin_authenticated,
    is_admin_configured,
    revoke_session_token,
    verify_password,
)

__all__ = [
    "COOKIE_NAME",
    "SETUP_INSTRUCTIONS",
    "admin_required",
    "clear_revoked_sessions",
    "create_session_token",
    "decode_session_token",
    "get_token",
    "is_admin_authenticated",
    "is_admin_configured",
    "revoke_session_token",
    "verify_password",
]
