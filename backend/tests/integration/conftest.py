"""
Wspoldzielone fixtures dla testow integracyjnych.

Integracja = prawdziwe flow HTTP przez FastAPI TestClient, z testowa baza
(kopia data/czarna.db do tmp). Auth jest WYMUSZONY (ADMIN_AUTH_ENABLED=true)
zeby testowac sciezke logowania.

NIE koliduje z unit suite - ma wlasny TestClient i wlasna baze w tmp.
Uruchamiane przez: python -m pytest backend/tests/integration -v
"""
import os
import sys
import shutil
import tempfile
import atexit
import uuid
import pytest


# 1. Setup bazy ZANIM zaimportujemy backend.main (env vars musza byc ustawione)
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..')
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Wymuszamy auth zeby testowac sciezke logowania
os.environ["ADMIN_AUTH_ENABLED"] = "1"
os.environ["ADMIN_USERNAME"] = "admin"

# Kopia bazy do tmp
_test_tmp_dir = tempfile.mkdtemp(prefix="mapa_int_db_")
_source_db = os.path.join(project_root, "data", "czarna.db")
_test_db = os.path.join(_test_tmp_dir, "czarna-integration.db")
if os.path.exists(_source_db):
    shutil.copy2(_source_db, _test_db)
else:
    open(_test_db, "a", encoding="utf-8").close()

os.environ["DB_ENGINE"] = "sqlite"
os.environ["DB_PATH"] = _test_db
os.environ.setdefault("TEST_LOCATION", "Czarna")


def _cleanup_test_db():
    shutil.rmtree(_test_tmp_dir, ignore_errors=True)


atexit.register(_cleanup_test_db)


# 2. Import aplikacji (po env setup)
from backend.main import app
from fastapi.testclient import TestClient
from backend import config as backend_config


@pytest.fixture(scope="module", autouse=True)
def enable_admin_auth():
    """Wymusza ADMIN_AUTH_ENABLED=True dla calej sesji integration.

    Uzywamy monkeypatch zamiast os.environ bo backend.main jest juz
    zaimportowany (przez unit/conftest.py przy wspolnym pytest run).
    Bez tego config.ADMIN_AUTH_ENABLED czytane byloby raz przy starcie.
    """
    backend_config.ADMIN_AUTH_ENABLED = True
    yield
    # Nie przywracamy - bo scope=module, konczy sie z modulem


@pytest.fixture(scope="module")
def client():
    """Klient TestClient - module scope bo baza jest izolowana w tmp."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_client(client):
    """Klient z zalogowanym adminem (token w cookies).

    Realny flow: POST /api/admin/login -> token -> cookies.
    Dla TestClient znamy default: 'admin' / 'admin123'.
    """
    resp = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "admin123"}
    )
    assert resp.status_code == 200, (
        f"Logowanie nie powiodlo sie: {resp.status_code} {resp.text}"
    )
    assert resp.json()["status"] == "ok"
    # Cookies sa automatycznie przechowywane w `client` miedzy requestami
    return client


# Wzorzec wlasciciela do testow CRUD
SAMPLE_OWNER_PAYLOAD = {
    "unikalny_klucz": "TEST_INT_001",
    "nazwa_wlasciciela": "Jan Testowy",
    "numer_protokolu": "9999/TEST",
    "numer_domu": "1",
    "historia_wlasnosci": "wlasnosc rzeczywista",
    "uwagi": "wlasciciel z testow integracyjnych",
    "wspolwlasnosc": "brak",
    "data_protokolu": "1930-01-15",
    "miejsce_protokolu": "Czarna",
}


# ============================================================================
# Fixture: pg_session - prawdziwy PostgreSQL dla testow E2E migracji
# ============================================================================
#
# Wymaga zmiennych srodowiskowych:
#   PG_TEST_HOST     - host PostgreSQL (default: localhost)
#   PG_TEST_PORT     - port (default: 5432)
#   PG_TEST_USER     - user (default: postgres)
#   PG_TEST_PASSWORD - haslo (default: postgres)
#
# Gdy brak PG (np. CI bez kontenera, sandbox) - test sa SKIPOWANE.
# To pozwala trzymac testy w suite bez blokowania developersow bez PG.
#
# Zakres: function (kazdy test dostaje swieza, izolowana baza).
# Po teście: DROP DATABASE + zamkniecie polaczenia.


def _pg_test_config() -> dict:
    return {
        "host": os.environ.get("PG_TEST_HOST", "localhost"),
        "port": int(os.environ.get("PG_TEST_PORT", "5432")),
        "user": os.environ.get("PG_TEST_USER", "postgres"),
        "password": os.environ.get("PG_TEST_PASSWORD", "postgres"),
        "connect_timeout": 5,
    }


def _pg_reachable(config: dict) -> bool:
    try:
        import psycopg2
        conn = psycopg2.connect(database="postgres", **config)
        conn.close()
        return True
    except Exception:
        return False


# Cache wynik reachability - zeby nie blokowac suite na 5s timeout per test
# gdy PG niedostepny. Sprawdzamy raz per proces pytest.
_pg_reachable_cache: dict | None = None


def _pg_reachable_cached() -> bool:
    global _pg_reachable_cache
    if _pg_reachable_cache is None:
        _pg_reachable_cache = _pg_reachable(_pg_test_config())
    return _pg_reachable_cache["reachable"]


def _get_pg_reachable_cache() -> dict:
    global _pg_reachable_cache
    if _pg_reachable_cache is None:
        config = _pg_test_config()
        reachable = _pg_reachable(config)
        _pg_reachable_cache = {"config": config, "reachable": reachable}
    return _pg_reachable_cache


@pytest.fixture
def pg_session():
    """Prawdziwy PostgreSQL dla testow E2E migracji.

    Skipuje automatycznie gdy PG_TEST_HOST nieosiagalny.
    Tworzy izolowana baze `mapa_test_<uuid>` przed testem,
    dropuje po teście (nawet przy failure).
    """
    cache = _get_pg_reachable_cache()
    if not cache["reachable"]:
        pytest.skip(
            f"PostgreSQL niedostepny pod {cache['config']['host']}:{cache['config']['port']} - "
            f"ustaw PG_TEST_HOST/PG_TEST_PORT/PG_TEST_USER/PG_TEST_PASSWORD "
            f"aby uruchomic testy E2E migracji."
        )

    import psycopg2
    config = cache["config"]

    db_name = f"mapa_test_{uuid.uuid4().hex[:12]}"
    server_conn = psycopg2.connect(database="postgres", **config)
    server_conn.autocommit = True
    server_cursor = server_conn.cursor()
    server_cursor.execute(f'CREATE DATABASE "{db_name}"')
    server_cursor.close()
    server_conn.close()

    conn = psycopg2.connect(database=db_name, **config)
    conn.autocommit = False

    yield {"config": config, "db_name": db_name, "conn": conn}

    # Teardown: rollback pending tx, drop db, close
    try:
        conn.rollback()
    except Exception:
        pass
    conn.close()

    server_conn = psycopg2.connect(database="postgres", **config)
    server_conn.autocommit = True
    try:
        # Wymus rozlaczenie aktywnych sesji (drop database z aktywnymi conn wymaga)
        server_conn.cursor().execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (db_name,),
        )
        server_conn.cursor().execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    finally:
        server_conn.close()


@pytest.fixture
def pg_test_config():
    """Zwraca konfiguracje PG do testow (bez laczenia sie).

    Skipuje automatycznie gdy PG niedostepny.
    """
    cache = _get_pg_reachable_cache()
    if not cache["reachable"]:
        pytest.skip(
            f"PostgreSQL niedostepny pod {cache['config']['host']}:{cache['config']['port']}"
        )
    return cache["config"]

