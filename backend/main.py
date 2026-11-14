"""
FastAPI Backend - Mapa Katastralna Czarna
==========================================
Główny plik aplikacji FastAPI. Zastępuje Flask app.py.
Obsługuje PostgreSQL (główna) i SQLite (opcjonalnie).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .config import DB_ENGINE, ACTIVE_LOCATION
from .db import init_db, close_db
from .auth import SETUP_INSTRUCTIONS, is_admin_configured
from .auth.security import (
    assert_safe_auth_config,
    assert_safe_secret_key,
    get_cors_allowed_origins,
    is_production_mode,
)
from .core.middleware import BodySizeLimitMiddleware, OriginCheckMiddleware, SecurityHeadersMiddleware


def _print_security_banner() -> None:
    if not config.ADMIN_AUTH_ENABLED:
        print("⚠️  UWAGA: autoryzacja admina WYŁĄCZONA (ADMIN_AUTH_INSECURE_DISABLE=1). "
              "Każdy klient może zmieniać dane.")
    elif not is_admin_configured():
        print("🔒 Hasło administratora nie jest skonfigurowane - akcje admina są zablokowane.")
        print("   " + SETUP_INSTRUCTIONS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Uruchamianie serwera FastAPI...")
    # W produkcji odmawiamy startu z niebezpieczną konfiguracją.
    assert_safe_secret_key(is_production_mode(), config.SECRET_KEY)
    assert_safe_auth_config(is_production_mode(), config.ADMIN_AUTH_ENABLED)
    _print_security_banner()
    await init_db()
    if config.SEED_DEMO_DATA and DB_ENGINE == "sqlite":
        from .services.demo_seed import seed_if_empty
        result = seed_if_empty()
        print(f"🌱 Dane demo: {result['status']} ({result.get('counts', {})})")
    yield
    await close_db()
    print("🛑 Serwer zatrzymany")


app = FastAPI(
    title="Mapa Katastralna Czarna API",
    description="REST API dla interaktywnej mapy katastralnej gminy Czarna z XIX wieku",
    version="2.0.0",
    lifespan=lifespan,
)

_CORS_ORIGINS = get_cors_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    # Domyślnie brak originów (frontend jest serwowany z tego samego hosta).
    # Lista z CORS_ALLOWED_ORIGINS; "*" wyłącza wysyłanie ciasteczek.
    allow_origins=_CORS_ORIGINS,
    allow_credentials="*" not in _CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.add_middleware(OriginCheckMiddleware, allowed_origins_getter=lambda: _CORS_ORIGINS)
app.add_middleware(BodySizeLimitMiddleware, max_bytes_getter=lambda: config.MAX_REQUEST_BODY_BYTES)
app.add_middleware(SecurityHeadersMiddleware)


@app.middleware("http")
async def no_cache_for_frontend(request, call_next):
    """Unika serwowania starej mapy/JS z cache przeglądarki podczas pracy z launcherem."""
    response = await call_next(request)
    path = request.url.path
    if path.endswith(('.html', '.js', '.css')) or path.startswith('/mapa/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


from .routers import (
    map,
    owners,
    genealogy,
    stats,
    editor,
    admin,
    admin_auth,
    historical_points,
    diagnostics,
    static_files,
)
# Kolejność ma znaczenie: historyczne_punkty i diagnostyka muszą być PRZED static_files,
# bo ten ostatni ma catch-all /{filename:path} który by je przechwycił.
app.include_router(map.router)
app.include_router(owners.router)
app.include_router(genealogy.router)
app.include_router(stats.router)
app.include_router(editor.router)
app.include_router(admin.router)
app.include_router(admin_auth.router)
app.include_router(historical_points.router)
app.include_router(diagnostics.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "db_engine": DB_ENGINE,
        "location": ACTIVE_LOCATION,
    }


# Catch-all musi być ostatni, również po endpointach aplikacji.
app.include_router(static_files.router)
