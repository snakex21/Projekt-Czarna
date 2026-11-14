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
# Domyślnie SQLite: świeży klon działa bez serwera PostgreSQL.
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").lower()  # "postgresql" lub "sqlite"

# PostgreSQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
# Brak domyślnego hasła w kodzie: dla PostgreSQL ustaw DB_PASSWORD w backend/.env.
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
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
# Tryb produkcyjny: gdy True, backend odmawia startu z niebezpieczną konfiguracją.
# W produkcji ustaw ENVIRONMENT=production albo PRODUCTION=1.
PRODUCTION = os.getenv("PRODUCTION", "0") == "1" or os.getenv("ENVIRONMENT", "").lower() == "production"

# Wartości-zaślepki z dawnych szablonów .env. Traktujemy je jak brak klucza.
WEAK_SECRET_KEYS = frozenset({
    "",
    "dev-secret-change-me",
    "change-me-once",
    "wygeneruj-losowy-sekretny-klucz",
    "change-me",
    "secret",
})
MIN_SECRET_KEY_LENGTH = 32


def default_secret_key_file() -> Path:
    """Plik z wygenerowanym SECRET_KEY, poza repozytorium (katalog użytkownika)."""
    override = os.getenv("SECRET_KEY_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "MapaCzarna" / "secret_key"
    base = Path(os.getenv("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "mapa-czarna" / "secret_key"


def load_or_create_secret_key(key_file: Path | None = None) -> tuple[str, str]:
    """Zwraca ``(secret_key, źródło)``.

    Kolejność: ``SECRET_KEY`` / ``FLASK_SECRET_KEY`` z env (o ile nie jest
    znaną zaślepką), potem plik poza repozytorium, a gdy go brak, generuje
    nowy losowy klucz i zapisuje go w tym pliku (uprawnienia 0600).
    """
    import secrets

    for var in ("SECRET_KEY", "FLASK_SECRET_KEY"):
        value = os.getenv(var, "").strip()
        if value and value not in WEAK_SECRET_KEYS:
            return value, f"env:{var}"

    key_file = key_file or default_secret_key_file()
    try:
        if key_file.resolve().is_relative_to(BASE_DIR.resolve()):
            raise ValueError(
                f"SECRET_KEY_FILE ({key_file}) leży w repozytorium; wskaż ścieżkę poza projektem."
            )
    except OSError:
        pass
    if key_file.is_file():
        value = key_file.read_text(encoding="utf-8").strip()
        if value and value not in WEAK_SECRET_KEYS:
            return value, f"file:{key_file}"

    value = secrets.token_urlsafe(48)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(key_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(value + "\n")
    _safe_print(f"🔑 Wygenerowano nowy SECRET_KEY i zapisano poza repozytorium: {key_file}")
    return value, f"generated:{key_file}"


SECRET_KEY, SECRET_KEY_SOURCE = load_or_create_secret_key()

# Autoryzacja admina jest ZAWSZE włączona. Wyłączenie wymaga dwóch jawnych
# flag (ADMIN_AUTH_ENABLED=0 oraz ADMIN_AUTH_INSECURE_DISABLE=1) i jest
# niedozwolone w trybie produkcyjnym. Stare pliki .env z launchera miały
# ADMIN_AUTH_ENABLED=0 jako wartość domyślną, więc sama ta flaga nie wystarcza.
ADMIN_AUTH_INSECURE_DISABLE = os.getenv("ADMIN_AUTH_INSECURE_DISABLE", "0") == "1"
ADMIN_AUTH_ENABLED = not (
    os.getenv("ADMIN_AUTH_ENABLED", "1").strip() == "0"
    and ADMIN_AUTH_INSECURE_DISABLE
    and not PRODUCTION
)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
# Hash hasła admina (Werkzeug). Brak hasha = akcje admina są zablokowane do czasu
# konfiguracji: python -m backend.scripts.set_admin_password
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
# Czas życia sesji admina (sekundy).
ADMIN_SESSION_TTL_SECONDS = int(os.getenv("ADMIN_SESSION_TTL_SECONDS", str(8 * 3600)))
# Flaga Secure ciasteczka sesji (domyślnie w produkcji, gdzie zakładamy HTTPS).
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1" if PRODUCTION else "0") == "1"
# Rate limit logowania: maks. nieudanych prób z jednego IP w oknie czasowym.
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))
# Maksymalny rozmiar ciała żądania (bajty) - chroni przed zbyt dużymi uploadami.
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(16 * 1024 * 1024)))
# Opcjonalne zasilenie pustej bazy SQLite danymi demo przy starcie.
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "0") == "1"
ACTIVE_LOCATION = os.getenv("ACTIVE_LOCATION") or os.getenv("TEST_LOCATION", "Czarna")
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", str(BASE_DIR / "data" / "locations"))).resolve()
DATA_DIR = BASE_DIR / "data"

# Ścieżki
os.makedirs(DATA_DIR, exist_ok=True)

_safe_print(f"🗄️ Silnik bazy: {DB_ENGINE}")
def masked_database_url(url: str | None = None) -> str:
    """URL bazy bez hasła (do logów)."""
    url = url or DATABASE_URL
    if DB_PASSWORD:
        url = url.replace(f":{DB_PASSWORD}@", ":***@")
    return url


_safe_print(f"📁 Baza danych: {masked_database_url()}")
_safe_print(f"📍 Aktywna lokalizacja: {ACTIVE_LOCATION}")
