"""Re-exporty autoryzacji dla wygodnych importów.

Użycie:
    from backend.auth import admin_required, verify_password, get_token, is_admin_authenticated
"""

from .routes import (
    admin_required,
    verify_password,
    get_token,
    is_admin_authenticated,
    _make_token,
)

__all__ = [
    "admin_required",
    "verify_password",
    "get_token",
    "is_admin_authenticated",
    "_make_token",
]
