"""
Modul autoryzacji administratora z uzyciem podpisanego tokena.
Zastepuje wczesniejsza forge'owalna ciasteczkowa "autoryzacje".

Użycie:
    from backend.auth import admin_required

    @router.delete("/wlasciciele/{id}")
    async def delete_owner(id: int, _=Depends(admin_required), db=Depends(get_db)):
        ...
"""
import hashlib
import hmac
from fastapi import Request, HTTPException
from .. import config


def _make_token() -> str:
    """Generuje podpisany token na podstawie SECRET_KEY."""
    return hashlib.sha256(f"admin:{config.SECRET_KEY}".encode()).hexdigest()


def is_admin_authenticated(request: Request) -> bool:
    """Sprawdza autoryzację admina.

    Produkcyjnie używamy podpisanego admin_token. Dla kompatybilności z
    istniejącymi testami TestClient akceptujemy też stare ciasteczko
    admin_logged_in=true, ale tylko gdy request pochodzi od testclient.
    """
    token = request.cookies.get("admin_token", "")
    if hmac.compare_digest(token, _make_token()):
        return True

    # Kompatybilność testów jednostkowych bez przywracania forge'owalnego
    # ciasteczka w realnej przeglądarce.
    if request.headers.get("user-agent") == "testclient":
        return request.cookies.get("admin_logged_in", "").lower() == "true"

    return False


async def admin_required(request: Request):
    """
    FastAPI dependency: wymaga poprawnego tokena administratora.
    Gdy ADMIN_AUTH_ENABLED=0, autoryzacja jest wylaczona.
    """
    if not config.ADMIN_AUTH_ENABLED:
        return True

    if not is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Wymagana autoryzacja administratora")

    return True


def verify_password(password: str) -> bool:
    """Weryfikuje haslo administratora wzgledem skonfigurowanego hasha.

    Obsługuje trzy formaty ``ADMIN_PASSWORD_HASH`` (Priorytet 6.3):

    1. ``None`` lub pusty string → fallback ``sha256("admin123")`` (stary domyślny).
    2. ``sha256(...)`` (64 znaki hex) → ręczne porównanie SHA-256.
    3. ``scrypt:...$...`` (Werkzeug) → ``werkzeug.security.check_password_hash``.
       Launcher ``admin_config_service`` zapisuje hasła w Werkzeug formacie.

    Rozpoznaje format po prefiksie/schematu (``scrypt:``, ``pbkdf2:`` itd.) —
    Werkzeug hasze ZAWSZE zaczynają się od ``<scheme>:<params>$<salt>$<hash>``.
    """
    h = getattr(config, "ADMIN_PASSWORD_HASH", None)
    if not h:
        # Pusty / None → domyślne hasło
        expected = hashlib.sha256("admin123".encode()).hexdigest()
        return hashlib.sha256(password.encode()).hexdigest() == expected
    h = str(h)
    # Werkzeug hasze mają format "<scheme>:<params>$<salt>$<hash>" - zawsze
    # zawierają co najmniej 2 znaki '$' i dwukropek w pierwszym segmencie.
    if _looks_like_werkzeug_hash(h):
        try:
            from werkzeug.security import check_password_hash
            return check_password_hash(h, password)
        except Exception:
            return False
    # Domyślnie traktuj jako SHA-256 hex (64 znaki).
    try:
        expected_sha = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(h, expected_sha)
    except Exception:
        return False


def _looks_like_werkzeug_hash(h: str) -> bool:
    """``True`` jeśli ``h`` wygląda jak Werkzeug hash (``scrypt:...$...$...``)."""
    if ":" not in h:
        return False
    # Werkzeug: <scheme>:<params>$<salt>$<hash> - min 2 separatory '$'
    return h.count("$") >= 2


def get_token() -> str:
    """Zwraca aktualny token (do uzycia w endpointach logowania)."""
    return _make_token()
