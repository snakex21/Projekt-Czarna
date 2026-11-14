"""Router autoryzacji administratora — logowanie, wylogowanie, status."""
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from .. import config
from ..auth import (
    COOKIE_NAME,
    SETUP_INSTRUCTIONS,
    admin_required,
    create_session_token,
    is_admin_authenticated,
    is_admin_configured,
    revoke_session_token,
    verify_password,
)
from ..auth.rate_limit import get_login_limiter
from ..auth.security import get_admin_security_status
from ..core.schemas import ChangePasswordRequest, LoginRequest

router = APIRouter(prefix="/api/admin", tags=["admin_auth"])


# Minimalna długość nowego hasła.
MIN_PASSWORD_LENGTH = 8


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        secure=config.COOKIE_SECURE,
        max_age=config.ADMIN_SESSION_TTL_SECONDS,
        path="/",
    )


@router.get("/auth-status")
async def auth_status():
    """Publiczny status autoryzacji admina (frontend sprawdza przed logowaniem).

    - ``enabled`` / ``auth_enabled`` (bool): czy autoryzacja jest włączona,
    - ``setup_required`` (bool): brak skonfigurowanego hasła admina,
    - ``setup_instructions`` (str|None): co zrobić, gdy ``setup_required``,
    - ``using_default_password``, ``using_default_secret_key``, ``is_production``,
    - ``warnings`` (list[str]).
    """
    status = get_admin_security_status()
    return {
        "enabled": status["auth_enabled"],
        "auth_enabled": status["auth_enabled"],
        "setup_required": status["setup_required"],
        "setup_instructions": SETUP_INSTRUCTIONS if status["setup_required"] else None,
        "using_default_password": status["using_default_password"],
        "using_default_secret_key": status["using_default_secret_key"],
        "is_production": status["is_production"],
        "warnings": status["warnings"],
    }


@router.get("/check-auth")
async def check_auth(request: Request):
    """Sprawdza, czy bieżąca sesja jest zalogowana."""
    if not config.ADMIN_AUTH_ENABLED:
        return {"authenticated": True, "auth_required": False}

    return {
        "authenticated": is_admin_authenticated(request),
        "auth_required": True,
    }


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    """Logowanie administratora. Ustawia podpisane, wygasające ciasteczko sesji.

    Nieudane próby są limitowane per IP (``LOGIN_MAX_ATTEMPTS`` w
    ``LOGIN_WINDOW_SECONDS``); po przekroczeniu zwracane jest 429.
    """
    if not config.ADMIN_AUTH_ENABLED:
        return JSONResponse({"status": "ok", "message": "Autoryzacja wylaczona"})

    if not is_admin_configured():
        return JSONResponse(
            {"status": "error", "setup_required": True, "message": SETUP_INSTRUCTIONS},
            status_code=403,
        )

    limiter = get_login_limiter()
    key = _client_key(request)
    retry_after = limiter.retry_after(key)
    if retry_after is not None:
        return JSONResponse(
            {"status": "error", "message": "Zbyt wiele nieudanych prób logowania. Spróbuj później."},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    # Jeden ogólny komunikat - nie zdradzamy, czy istnieje dany login.
    username_ok = body.username == config.ADMIN_USERNAME
    password_ok = verify_password(body.password)
    if not (username_ok and password_ok):
        limiter.record_failure(key)
        return JSONResponse(
            {"status": "error", "message": "Nieprawidlowa nazwa uzytkownika lub haslo"},
            status_code=401,
        )

    limiter.reset(key)
    _set_session_cookie(response, create_session_token())
    return {"status": "ok"}


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Wylogowanie: unieważnia token po stronie serwera i usuwa ciasteczko."""
    revoke_session_token(request.cookies.get(COOKIE_NAME, ""))
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="strict",
        secure=config.COOKIE_SECURE,
    )
    return {"status": "ok"}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    _=Depends(admin_required),
):
    """Zmiana hasła admina z poziomu panelu web.

    Wymaga ``current_password`` i ``new_password`` (min. 8 znaków, inne niż
    obecne). Zapisuje hash Werkzeug do ``backend/.env``. Zmiana hasła
    unieważnia wszystkie istniejące sesje; bieżąca dostaje nowy token.
    """
    if not config.ADMIN_AUTH_ENABLED:
        return JSONResponse(
            {"status": "error", "message": "Autoryzacja jest wyłączona"},
            status_code=400,
        )

    current = body.current_password
    new_pw = body.new_password

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
            {"status": "error", "message": "Nowe hasło musi być inne niż obecne"},
            status_code=400,
        )

    from werkzeug.security import generate_password_hash
    new_hash = generate_password_hash(new_pw)

    try:
        from launcher.services.admin_config_service import save_admin_password_hash
        env_path = str(config.BASE_DIR / "backend" / ".env")
        save_admin_password_hash(env_path, new_hash)
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": f"Nie udało się zapisać hasła: {type(exc).__name__}"},
            status_code=500,
        )

    config.ADMIN_PASSWORD_HASH = new_hash
    _set_session_cookie(response, create_session_token())

    return {
        "status": "ok",
        "message": "Hasło zostało zmienione. Inne sesje zostały wylogowane.",
    }
