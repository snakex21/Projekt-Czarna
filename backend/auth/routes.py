"""
Autoryzacja administratora: podpisane (HMAC-SHA256), wygasające tokeny sesji.

- Token ma postać ``<payload_b64>.<podpis_b64>``; payload zawiera nazwę
  użytkownika, czas wydania i wygaśnięcia, losowy identyfikator (``jti``)
  oraz odcisk aktualnego hasha hasła. Zmiana hasła unieważnia wszystkie sesje.
- Wylogowanie unieważnia token (lista odwołanych ``jti`` w pamięci procesu).
- Nie ma żadnych tylnych furtek (np. dla ``User-Agent: testclient``): testy
  logują się przez ``/api/admin/login`` albo używają ``create_session_token()``.
- Bez skonfigurowanego ``ADMIN_PASSWORD_HASH`` wszystkie akcje admina są
  odrzucane (403) z instrukcją konfiguracji.

Użycie:
    from backend.auth import admin_required

    @router.delete("/wlasciciele/{id}")
    async def delete_owner(id: int, _=Depends(admin_required), db=Depends(get_db)):
        ...
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import threading
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

from .. import config

COOKIE_NAME = "admin_token"

SETUP_INSTRUCTIONS = (
    "Hasło administratora nie jest skonfigurowane - akcje admina są zablokowane. "
    "Ustaw je poleceniem: python -m backend.scripts.set_admin_password "
    "(zapisuje ADMIN_PASSWORD_HASH w backend/.env) albo ustaw zmienną "
    "środowiskową ADMIN_PASSWORD_HASH (hash Werkzeug), a następnie zrestartuj serwer."
)

# Hasła uznawane za domyślne / trywialne - ich hash nie liczy się jako konfiguracja.
WEAK_PASSWORDS = ("admin123", "admin", "password", "1234", "12345678")
_WEAK_SHA256 = frozenset(hashlib.sha256(p.encode()).hexdigest() for p in WEAK_PASSWORDS)

_revoked_lock = threading.Lock()
_revoked_jti: Dict[str, float] = {}
_weak_hash_cache: Dict[str, bool] = {}


# ---------------------------------------------------------------------------
# Hasło
# ---------------------------------------------------------------------------


def _looks_like_werkzeug_hash(h: str) -> bool:
    """``True`` jeśli ``h`` wygląda jak hash Werkzeug (``scrypt:...$salt$hash``)."""
    if ":" not in h:
        return False
    return h.count("$") >= 2


def _check_hash(h: str, password: str) -> bool:
    if not password:
        return False
    if _looks_like_werkzeug_hash(h):
        try:
            from werkzeug.security import check_password_hash
            return check_password_hash(h, password)
        except Exception:
            return False
    # Starszy format: SHA-256 hex (bez soli). Obsługiwany dla zgodności.
    expected = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(h.lower(), expected)


def is_weak_password_hash(h: Optional[str]) -> bool:
    """``True`` gdy hash jest pusty albo pasuje do znanego domyślnego hasła."""
    if not h:
        return True
    h = str(h)
    if h.lower() in _WEAK_SHA256:
        return True
    if h not in _weak_hash_cache:
        _weak_hash_cache[h] = any(_check_hash(h, p) for p in WEAK_PASSWORDS)
    return _weak_hash_cache[h]


def is_admin_configured() -> bool:
    """Czy skonfigurowano własne (niedomyślne) hasło admina."""
    return not is_weak_password_hash(getattr(config, "ADMIN_PASSWORD_HASH", "") or "")


def verify_password(password: str) -> bool:
    """Weryfikuje hasło względem ``ADMIN_PASSWORD_HASH``.

    Obsługiwane formaty: hash Werkzeug (``scrypt:``/``pbkdf2:``) oraz starszy
    SHA-256 hex. Gdy hash nie jest skonfigurowany (albo jest hashem domyślnego
    hasła) - zawsze ``False``. Nie ma hasła domyślnego.
    """
    h = getattr(config, "ADMIN_PASSWORD_HASH", "") or ""
    if not is_admin_configured():
        return False
    return _check_hash(str(h), password or "")


# ---------------------------------------------------------------------------
# Tokeny sesji
# ---------------------------------------------------------------------------


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(body: str) -> str:
    key = str(config.SECRET_KEY).encode()
    return _b64e(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())


def _password_fingerprint() -> str:
    """Odcisk hasha hasła - zmiana hasła unieważnia wszystkie istniejące sesje."""
    key = str(config.SECRET_KEY).encode()
    h = str(getattr(config, "ADMIN_PASSWORD_HASH", "") or "").encode()
    return _b64e(hmac.new(key, b"pw:" + h, hashlib.sha256).digest()[:12])


def create_session_token(ttl_seconds: Optional[int] = None, *, now: Optional[float] = None) -> str:
    """Tworzy nowy podpisany token sesji administratora."""
    issued = int(now if now is not None else time.time())
    ttl = int(ttl_seconds if ttl_seconds is not None else config.ADMIN_SESSION_TTL_SECONDS)
    payload = {
        "sub": config.ADMIN_USERNAME,
        "iat": issued,
        "exp": issued + ttl,
        "jti": secrets.token_urlsafe(16),
        "pwf": _password_fingerprint(),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    return f"{body}.{_sign(body)}"


def decode_session_token(token: Optional[str], *, now: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Zwraca payload poprawnego, aktywnego tokena albo ``None``."""
    if not token or not isinstance(token, str) or token.count(".") != 1 or len(token) > 4096:
        return None
    body, signature = token.split(".", 1)
    if not hmac.compare_digest(signature, _sign(body)):
        return None
    try:
        payload = json.loads(_b64d(body))
    except (ValueError, binascii.Error):
        return None
    if not isinstance(payload, dict):
        return None
    current = now if now is not None else time.time()
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or exp <= current:
        return None
    if payload.get("sub") != config.ADMIN_USERNAME:
        return None
    if not hmac.compare_digest(str(payload.get("pwf", "")), _password_fingerprint()):
        return None
    jti = str(payload.get("jti", ""))
    with _revoked_lock:
        if jti in _revoked_jti:
            return None
    return payload


def revoke_session_token(token: Optional[str]) -> bool:
    """Unieważnia token (wylogowanie). Zwraca ``True`` gdy token był aktywny."""
    payload = decode_session_token(token)
    if payload is None:
        return False
    now = time.time()
    with _revoked_lock:
        for jti, exp in list(_revoked_jti.items()):
            if exp <= now:
                del _revoked_jti[jti]
        _revoked_jti[str(payload["jti"])] = float(payload["exp"])
    return True


def clear_revoked_sessions() -> None:
    """Czyści listę odwołanych tokenów (używane w testach)."""
    with _revoked_lock:
        _revoked_jti.clear()


def get_token() -> str:
    """Nowy token sesji (alias zachowany dla zgodności importów)."""
    return create_session_token()


def is_admin_authenticated(request: Request) -> bool:
    """Sprawdza, czy żądanie niesie ważny token sesji administratora."""
    if not is_admin_configured():
        return False
    return decode_session_token(request.cookies.get(COOKIE_NAME, "")) is not None


async def admin_required(request: Request):
    """FastAPI dependency: wymaga zalogowanego administratora.

    - brak skonfigurowanego hasła admina → 403 z instrukcją konfiguracji,
    - brak / nieważny token → 401.

    Autoryzację można wyłączyć wyłącznie jawnie (patrz ``config.ADMIN_AUTH_ENABLED``).
    """
    if not config.ADMIN_AUTH_ENABLED:
        return True

    if not is_admin_configured():
        raise HTTPException(status_code=403, detail=SETUP_INSTRUCTIONS)

    if not is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Wymagana autoryzacja administratora")

    return True
