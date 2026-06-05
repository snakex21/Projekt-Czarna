"""Odczyt i przygotowanie plików .env launchera."""

import os
import shutil

from ..config.paths import BACKEND_DIR
from .location_context import get_location_env_path


__all__ = [
    "check_env_configuration",
    "read_env_config",
    "get_db_config_from_env",
    "get_flask_config",
    "_read_backend_env_value",
    "_detect_sqlite_mode",
]


SQLITE_MODE = False


def check_env_configuration():

    """Sprawdza i konfiguruje plik .env dla aktywnej miejscowości."""

    # Pobierz ścieżkę do .env aktywnej miejscowości

    try:

        env_path = get_location_env_path()

    except ValueError:

        # Brak aktywnej miejscowości - nie powinno się zdarzyć

        # ale obsłuż to dla bezpieczeństwa

        return False

    env_example_path = os.path.join(BACKEND_DIR, ".env.example")

    if os.path.exists(env_path):

        return True

    if os.path.exists(env_example_path):

        try:

            # Upewnij się, że folder istnieje

            os.makedirs(os.path.dirname(env_path), exist_ok=True)

            shutil.copy(env_example_path, env_path)

            print("✅ Utworzono plik .env z przykładowej konfiguracji")

            return True

        except Exception as e:

            print(f"⚠️ Nie można utworzyć pliku .env: {e}")

            return False

    try:

        default_env = """# =============================================================================

# KONFIGURACJA MIEJSCOWOŚCI

# =============================================================================

# Konfiguracja PostgreSQL (host, port, user, password) jest w backend/.postgres.env

# =============================================================================

# BAZA DANYCH

# =============================================================================

DB_NAME=mapa_czarna_db

# =============================================================================

# SERWER FLASK (główny serwer)

# =============================================================================

FLASK_HOST=127.0.0.1

FLASK_PORT=5000

FLASK_DEBUG=True

FLASK_SECRET_KEY=change-me-once

# =============================================================================

# PORTY EDYTORÓW

# =============================================================================

# Każdy port musi być unikalny! Nie można używać tego samego portu dla różnych serwerów.

GENEALOGY_EDITOR_PORT=5001

PARCEL_EDITOR_PORT=5003

# =============================================================================

# AUTENTYKACJA ADMINISTRATORA

# =============================================================================

ADMIN_AUTH_ENABLED=0

ADMIN_USERNAME=admin

ADMIN_PASSWORD_HASH=

"""

        # Upewnij się, że folder istnieje

        os.makedirs(os.path.dirname(env_path), exist_ok=True)

        with open(env_path, 'w', encoding='utf-8') as f:

            f.write(default_env)

        print("✅ Utworzono domyślny plik .env")

        return True

    except Exception as e:

        print(f"⚠️ Nie można utworzyć pliku .env: {e}")

        return False


def read_env_config(key_prefix=None):

    """Odczytuje konfigurację z właściwego .env.

    W trybie SQLite głównym plikiem konfiguracji aplikacji jest backend/.env
    (zawiera port backendu, porty edytorów, DB_ENGINE i DB_PATH). W trybie
    PostgreSQL pozostaje legacy plik .env aktywnej miejscowości.
    """

    # Sprawdź czy jest aktywna miejscowość

    # Pobierz ścieżkę do .env aktywnej miejscowości

    if _detect_sqlite_mode():

        env_path = os.path.join(str(BACKEND_DIR), ".env")

    else:

        try:

            env_path = get_location_env_path()

        except ValueError:

            # Brak aktywnej miejscowości

            return {}

    config = {}

    if not os.path.exists(env_path):

        return config

    # Spróbuj różnych kodowań (utf-8, cp1250, latin-1)

    for encoding in ['utf-8', 'cp1250', 'latin-1']:

        try:

            with open(env_path, 'r', encoding=encoding) as f:

                for line in f:

                    line = line.strip()

                    if line and not line.startswith('#') and '=' in line:

                        key, value = line.split('=', 1)

                        key, value = key.strip(), value.strip()

                        if not key_prefix or key.startswith(key_prefix):

                            config[key] = value

            break  # Jeśli udało się odczytać, przerwij pętlę

        except (UnicodeDecodeError, Exception) as e:

            if encoding == 'latin-1':  # latin-1 nigdy nie powinno rzucić UnicodeDecodeError

                print(f"Błąd odczytu .env: {e}")

            continue  # Spróbuj kolejnego kodowania

    return config


def get_db_config_from_env():

    """Odczytuje konfigurację bazy danych z pliku .env."""

    env_config = read_env_config('DB_')

    return {

        "host": env_config.get('DB_HOST', 'localhost'),

        "dbname": env_config.get('DB_NAME', 'mapa_czarna_db'),

        "user": env_config.get('DB_USER', 'postgres'),

        "password": env_config.get('DB_PASSWORD', '1234'),

        "port": env_config.get('DB_PORT', '5432')

    }


def get_flask_config():

    """Odczytuje konfigurację serwera z pliku .env (FastAPI/Flask)."""

    if SQLITE_MODE:

        return {

            'host': _read_backend_env_value('FLASK_HOST', '127.0.0.1'),

            'port': _read_backend_env_value('FLASK_PORT', '5000'),

            'db_engine': 'sqlite',

        }

    env_config = read_env_config('FLASK_')

    return {

        'host': env_config.get('FLASK_HOST', '127.0.0.1'),

        'port': env_config.get('FLASK_PORT', '5000'),

        'db_engine': env_config.get('DB_ENGINE', 'postgresql'),

    }


def _read_backend_env_value(key: str, default: str = "") -> str:

    """Czyta pojedynczą wartość z backend/.env."""

    env_path = os.path.join(str(BACKEND_DIR), ".env")

    if os.path.exists(env_path):

        try:

            with open(env_path, "r", encoding="utf-8") as f:

                for line in f:

                    line = line.strip()

                    if line.startswith(f"{key}="):

                        return line.split("=", 1)[1].strip().strip('"').strip("'")

        except Exception:

            pass

    return os.getenv(key, default)


def _detect_sqlite_mode() -> bool:

    """Sprawdza czy backend/.env ma DB_ENGINE=sqlite."""

    # Najpierw sprawdź zmienną środowiskową

    env_val = os.getenv("DB_ENGINE", "")

    if env_val.lower() == "sqlite":

        return True

    # Potem sprawdź plik .env

    env_path = os.path.join(str(BACKEND_DIR), ".env")

    if os.path.exists(env_path):

        try:

            with open(env_path, "r", encoding="utf-8") as f:

                for line in f:

                    line = line.strip()

                    if line.startswith("DB_ENGINE="):

                        val = line.split("=", 1)[1].strip().strip('"').strip("'")

                        return val.lower() == "sqlite"

        except Exception:

            pass

    return False
