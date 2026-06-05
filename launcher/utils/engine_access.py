"""Lazy dostęp do silnika bazy danych i dostępności PostgreSQL."""

import os

from ..db.engine import get_engine
from ..config.paths import BACKEND_DIR


__all__ = ["_ensure_engine", "check_postgres_available"]


_DB_ENGINE = None
POSTGRES_AVAILABLE = None


def _load_db_env_to_environ():
    """Ładuje DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME z backend/.env
    do ``os.environ`` (potrzebne dla check_postgres_available które używa
    ``os.getenv('DB_PASSWORD')`` itd.). Bez tego launcher nie wie jakie
    hasło podać do PG mimo że ``.env`` ma poprawne wartości.
    """
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for key in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"):
                if line.startswith(f"{key}="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    os.environ.setdefault(key, value)
                    break
    except Exception:
        pass


def _ensure_engine():

    global _DB_ENGINE

    if _DB_ENGINE is None:

        _load_db_env_to_environ()

        _DB_ENGINE = get_engine()

    return _DB_ENGINE


def check_postgres_available():

    """Sprawdza czy PostgreSQL jest dostępny."""

    global POSTGRES_AVAILABLE

    eng = _ensure_engine()

    if eng.name == "sqlite":

        POSTGRES_AVAILABLE = False

        return False

    if POSTGRES_AVAILABLE is not None:

        return POSTGRES_AVAILABLE

    try:

        from ..db.postgres import get_launcher_conn

        conn = get_launcher_conn({'host': os.getenv('DB_HOST','localhost'),

            'port': int(os.getenv('DB_PORT','5432')), 'user': os.getenv('DB_USER','postgres'),

            'password': os.getenv('DB_PASSWORD','')})

        conn.close()

        POSTGRES_AVAILABLE = True

        return True

    except Exception:

        POSTGRES_AVAILABLE = False

        return False
