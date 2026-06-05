"""
launcher/config/paths.py — Ścieżki projektu.
Jedyne miejsce definiujące ścieżki. Importowane przez launcher i backend.
"""

import os
from pathlib import Path

# === Katalog główny projektu ===
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# === Dane aplikacji (wszystko co nie jest kodem) ===
DATA_DIR = BASE_DIR / "data"

# === Baza miejscowości (rejestr) ===
LOCATIONS_DB_PATH = DATA_DIR / "locations.db"

# === Lokalne ustawienia launchera ===
LAUNCHER_UI_SETTINGS_FILE = DATA_DIR / "launcher_ui_settings.json"

# === Dane źródłowe miejscowości (dawniej "backup/") ===
LOCATIONS_DATA_DIR = DATA_DIR / "locations"

# === Kod aplikacji ===
BACKEND_DIR = BASE_DIR / "backend"
LAUNCHER_DIR = BASE_DIR / "launcher"
TOOLS_DIR = BASE_DIR / "tools"

# === Dane per-miejscowość ===
def location_data_dir(name: str) -> Path:
    """Zwraca ścieżkę do folderu z danymi miejscowości."""
    return LOCATIONS_DATA_DIR / name

def location_env_path(name: str) -> Path:
    """Zwraca ścieżkę do pliku .env miejscowości."""
    return location_data_dir(name) / ".env"

def location_config_path(name: str) -> Path:
    """Zwraca ścieżkę do launcher_db_config.json miejscowości."""
    return location_data_dir(name) / "launcher_db_config.json"

# === Legacy ścieżki (kompatybilność) ===
ASSETS_FOLDER = BASE_DIR / "assets"
BACKUP_FOLDER = LOCATIONS_DATA_DIR  # alias — stara nazwa
PROTOKOLY_FOLDER = ASSETS_FOLDER / "protokoly"
SITE_ASSETS_FOLDER = ASSETS_FOLDER / "site"

# === Konfiguracja PostgreSQL ===
POSTGRES_CONFIG_FILE = BACKEND_DIR / ".postgres.env"

# === Ikony ===
ICONS_SCAN_FOLDERS = [
    BASE_DIR / "icons",
    ASSETS_FOLDER / "icons",
]

# === Strona główna (statyczna) ===
STATIC_DIR = BASE_DIR / "static"
HOMEPAGE_DIR = STATIC_DIR / "strona_glowna"
TEMPLATES_DIR = HOMEPAGE_DIR / "szablony"

# === Tymczasowe (kompatybilność wsteczna) ===
# Stara ścieżka, gdyby kod używał stringów zamiast Path
BACKUP_FOLDER_STR = str(LOCATIONS_DATA_DIR)
