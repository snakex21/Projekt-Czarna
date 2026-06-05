"""
launcher/config/settings.py — Stałe konfiguracyjne launchera.
Kolory, skrypty, URLe, definicje procesów.
"""

import os
import sys
from .paths import BASE_DIR, BACKEND_DIR, TOOLS_DIR, LOCATIONS_DATA_DIR
from .urls import build_tool_urls, normalize_browser_host, read_env_values

# === Kolory ===
COLORS = {
    'primary': '#0d6efd', 'success': '#198754', 'danger': '#dc3545',
    'warning': '#ffc107', 'info': '#0dcaf0', 'secondary': '#6c757d',
    'dark': '#212529', 'light': '#f8f9fa',
}

# === Definicje procesów (skryptów do uruchomienia) ===
SCRIPTS = {
    "backend": {
        "path": "-m",
        # Port/host backendu są czytane z .env w launcher.utils.prepare_command().
        # Nie wpisujemy ich tutaj na sztywno.
        "args": ["uvicorn", "backend.main:app"],
        "cwd": str(BASE_DIR),
    },
    "migration": {
        "path": str(BACKEND_DIR / "scripts" / "migrate_data.py"),
        "cwd": str(BACKEND_DIR),
    },
    "tests": {
        "path": "-m",
        "args": ["pytest", "tests", "-q"],
        "cwd": str(BACKEND_DIR),
    },
    "owner_editor": {
        "path": str(TOOLS_DIR / "owner_editor.py"),
        "cwd": str(TOOLS_DIR),
    },
    "parcel_editor": {
        "path": str(TOOLS_DIR / "parcel_editor" / "app.py"),
        "cwd": str(TOOLS_DIR / "parcel_editor"),
    },
    "genealogy_editor": {
        "path": str(TOOLS_DIR / "genealogy_editor" / "editor_app.py"),
        "cwd": str(TOOLS_DIR / "genealogy_editor"),
    },
}

# === URL's do aplikacji (obliczane dynamicznie w runtime) ===
def get_urls():
    """Zwraca słownik URL-i do aplikacji na podstawie portów z .env."""
    backend_env = BACKEND_DIR / ".env"
    values = read_env_values(backend_env, defaults={
        "FLASK_HOST": os.getenv("FLASK_HOST", "127.0.0.1"),
        "FLASK_PORT": os.getenv("FLASK_PORT", "5000"),
        "GENEALOGY_EDITOR_PORT": os.getenv("GENEALOGY_EDITOR_PORT", "5001"),
        "PARCEL_EDITOR_PORT": os.getenv("PARCEL_EDITOR_PORT", "5003"),
    })
    browser_host = normalize_browser_host(values.get("FLASK_HOST", "127.0.0.1"))
    return build_tool_urls(
        browser_host,
        values.get("FLASK_PORT", "5000"),
        values.get("GENEALOGY_EDITOR_PORT", "5001"),
        values.get("PARCEL_EDITOR_PORT", "5003"),
    )

URLS = get_urls()

# === Cache TTL ===
LOCATIONS_CACHE_TTL = 30  # sekund

# === Domyślna miejscowość (fallback dla nowych instalacji) ===
DEFAULT_LOCATION_NAME = "Czarna"
