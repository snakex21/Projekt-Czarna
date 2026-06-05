"""
Konfiguracja aplikacji - PostgreSQL (główna) + SQLite (opcjonalna).
Odczytuje ustawienia z plików .env i zmiennych środowiskowych.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _safe_print(*args, **kwargs):
    """Bezpieczny print - zamienia znaki spoza ASCII gdy kodowanie stdout to cp1250."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        safe_args = [str(a).encode('ascii', errors='replace').decode('ascii') for a in args]
        print(*safe_args, **kwargs)


# === Ładowanie .env ===
def load_env_with_fallback():
    """Wczytuje .env z obsługą wielu kodowań."""
    env_paths = [
        BASE_DIR / "backend" / ".env",
        BASE_DIR / "backend" / ".postgres.env",
    ]
    for env_path in env_paths:
        if not env_path.exists():
            continue
        for encoding in ['utf-8', 'cp1250', 'latin-1']:
            try:
                with open(env_path, 'r', encoding=encoding) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key, value = key.strip(), value.strip()
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            elif value.startswith("'") and value.endswith("'"):
                                value = value[1:-1]
                            if key not in os.environ:
                                os.environ[key] = value
                _safe_print(f"✅ Załadowano .env ({encoding}): {env_path}")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                _safe_print(f"⚠️ Błąd ładowania {env_path}: {e}")

load_env_with_fallback()

# Mapowanie LAUNCHER_DB_* na DB_* (kompatybilność z launcherem)
for var in ['HOST', 'PORT', 'USER', 'PASSWORD']:
    launcher_val = os.getenv(f'LAUNCHER_DB_{var}')
    if launcher_val:
        os.environ[f'DB_{var}'] = launcher_val


# === Konfiguracja silnika bazy danych ===
DB_ENGINE = os.getenv("DB_ENGINE", "postgresql").lower()  # "postgresql" lub "sqlite"

# PostgreSQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
DB_NAME = os.getenv("DB_NAME", "mapa_czarna_db")

# SQLite (opcjonalnie)
_DB_PATH_RAW = os.getenv("DB_PATH", str(BASE_DIR / "data" / "czarna.db"))
# Ensure absolute path
DB_PATH = str(Path(_DB_PATH_RAW).resolve()) if not Path(_DB_PATH_RAW).is_absolute() else _DB_PATH_RAW

# URL połączenia
if DB_ENGINE == "sqlite":
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else '.', exist_ok=True)
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    ASYNC_DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
else:
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    ASYNC_DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# === Pozostałe ustawienia ===
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
ADMIN_AUTH_ENABLED = os.getenv("ADMIN_AUTH_ENABLED", "0") == "1"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
# Tryb produkcyjny: gdy True, backend odmawia startu z domyślnym SECRET_KEY
# (Priorytet 6.6). Domyślnie False (dev). W produkcji ustawić ENVIRONMENT=production
# albo PRODUCTION=1.
PRODUCTION = os.getenv("PRODUCTION", "0") == "1" or os.getenv("ENVIRONMENT", "").lower() == "production"
ACTIVE_LOCATION = os.getenv("ACTIVE_LOCATION") or os.getenv("TEST_LOCATION", "Czarna")
BACKUP_DIR = BASE_DIR / "data" / "locations"
DATA_DIR = BASE_DIR / "data"

# Ścieżki
os.makedirs(DATA_DIR, exist_ok=True)

_safe_print(f"🗄️ Silnik bazy: {DB_ENGINE}")
_safe_print(f"📁 Baza danych: {DATABASE_URL}")
_safe_print(f"📍 Aktywna lokalizacja: {ACTIVE_LOCATION}")
