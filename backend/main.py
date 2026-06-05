"""
FastAPI Backend - Mapa Katastralna Czarna
==========================================
Główny plik aplikacji FastAPI. Zastępuje Flask app.py.
Obsługuje PostgreSQL (główna) i SQLite (opcjonalnie).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import DB_ENGINE, ACTIVE_LOCATION, SECRET_KEY
from .db import init_db, close_db
from .auth.security import assert_safe_secret_key, is_production_mode, get_cors_allowed_origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Uruchamianie serwera FastAPI...")
    # Walidacja bezpieczeństwa SECRET_KEY w trybie produkcyjnym (Priorytet 6.6).
    # W dev przechodzi bezwarunkowo.
    assert_safe_secret_key(is_production_mode(), SECRET_KEY)
    await init_db()
    yield
    await close_db()
    print("🛑 Serwer zatrzymany")


app = FastAPI(
    title="Mapa Katastralna Czarna API",
    description="REST API dla interaktywnej mapy katastralnej gminy Czarna z XIX wieku",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # CORS hardening (Priorytet 6.8): w produkcji lista originów z CORS_ALLOWED_ORIGINS,
    # w dev fallback ["*"].
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
app.include_router(static_files.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "db_engine": DB_ENGINE,
        "location": ACTIVE_LOCATION,
    }
