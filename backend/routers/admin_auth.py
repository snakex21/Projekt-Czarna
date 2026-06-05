"""Router autoryzacji administratora — logowanie, wylogowanie, status."""
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from .. import config
from ..auth import verify_password, get_token, is_admin_authenticated, admin_required
from ..auth.security import get_admin_security_status

router = APIRouter(prefix="/api/admin", tags=["admin_auth"])


# Minimalna długość nowego hasła (Priorytet 6.4).
MIN_PASSWORD_LENGTH = 8


@router.get("/auth-status")
async def auth_status():
    """Status autoryzacji admina (Priorytet 6.2).

    Publiczny endpoint (nie wymaga auth) — frontend sprawdza przed wyświetleniem
    panelu logowania. Zwraca:
    - ``enabled`` (bool): wsteczna kompatybilność — czy auth w ogóle włączony,
    - ``auth_enabled`` (bool): alias dla ``enabled``,
    - ``using_default_password`` (bool): czy aktywne domyślne ``admin123``,
    - ``using_default_secret_key`` (bool): czy ``SECRET_KEY`` to fallback,
    - ``is_production`` (bool): czy tryb produkcyjny,
    - ``warnings`` (list[str]): lista ostrzeżeń do wyświetlenia w UI.
    """
    status = get_admin_security_status()
    return {
        # Wsteczna kompatybilność
        "enabled": status["auth_enabled"],
        # Priorytet 6.2
        "auth_enabled": status["auth_enabled"],
        "using_default_password": status["using_default_password"],
        "using_default_secret_key": status["using_default_secret_key"],
        "is_production": status["is_production"],
        "warnings": status["warnings"],
    }


@router.get("/check-auth")
async def check_auth(request: Request):
    """Sprawdza stan autoryzacji (kompatybilnosc wsteczna)."""
    if not config.ADMIN_AUTH_ENABLED:
        return {"authenticated": True, "auth_required": False}

    authenticated = is_admin_authenticated(request)

    return {
        "authenticated": authenticated,
        "auth_required": True
    }


@router.post("/login")
async def login(payload: dict, response: Response):
    """Logowanie administratora. Ustawia podpisane ciasteczko."""
    username = payload.get("username", "")
    password = payload.get("password", "")

    if not config.ADMIN_AUTH_ENABLED:
        return JSONResponse({"status": "ok", "message": "Autoryzacja wylaczona"})

    if username != config.ADMIN_USERNAME:
        return JSONResponse(
            {"status": "error", "message": "Nieprawidlowa nazwa uzytkownika"},
            status_code=401
        )

    if not verify_password(password):
        return JSONResponse(
            {"status": "error", "message": "Nieprawidlowe haslo"},
            status_code=401
        )

    token = get_token()
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
        path="/"
    )
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response):
    """Wylogowanie administratora. Usuwa ciasteczko."""
    response.delete_cookie(
        key="admin_token",
        path="/",
        httponly=True,
        samesite="lax"
    )
    return {"status": "ok"}


@router.post("/change-password")
async def change_password(
    payload: dict,
    request: Request,
    _=Depends(admin_required),
):
    """Zmiana hasła admina z poziomu panelu web (Priorytet 6.4).

    Wymaga podania:
    - ``current_password`` (weryfikacja starego hasła),
    - ``new_password`` (min. 8 znaków, nie może być równe staremu).

    Używa ``werkzeug.security.generate_password_hash`` (ten sam format co
    launcher ``admin_config_service``). Zapisuje hash do ``.env`` przez
    ``launcher.services.admin_config_service``.
    """
    if not config.ADMIN_AUTH_ENABLED:
        return JSONResponse(
            {"status": "error", "message": "Autoryzacja jest wyłączona"},
            status_code=400,
        )

    current = payload.get("current_password", "") or ""
    new_pw = payload.get("new_password", "") or ""

    if not verify_password(current):
        return JSONResponse(
            {"status": "error", "message": "Nieprawidłowe obecne hasło"},
            status_code=401,
        )

    if len(new_pw) < MIN_PASSWORD_LENGTH:
        return JSONResponse(
            {
                "status": "error",
                "message": f"Nowe hasło musi mieć co najmniej {MIN_PASSWORD_LENGTH} znaków",
            },
            status_code=400,
        )

    if new_pw == current:
        return JSONResponse(
            {
                "status": "error",
                "message": "Nowe hasło musi być inne niż obecne",
            },
            status_code=400,
        )

    # Wygeneruj Werkzeug hash (ten sam format co launcher)
    from werkzeug.security import generate_password_hash
    new_hash = generate_password_hash(new_pw)

    # Zapisz do .env przez launcher service
    try:
        from launcher.services.admin_config_service import save_admin_password_hash
        env_path = str(config.BASE_DIR / "backend" / ".env")
        save_admin_password_hash(env_path, new_hash)
    except Exception as exc:
        return JSONResponse(
            {
                "status": "error",
                "message": f"Nie udało się zapisać hasła: {exc}",
            },
            status_code=500,
        )

    # Zaktualizuj in-memory config dla bieżącego procesu
    config.ADMIN_PASSWORD_HASH = new_hash

    return {
        "status": "ok",
        "message": "Hasło zostało zmienione. Zaloguj się ponownie.",
    }
