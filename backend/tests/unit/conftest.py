import pytest
import os
import sys
import shutil
import tempfile
import atexit

# Dodajemy katalog projektu do sys.path, aby testy mogły importować pakiet backend
# backend/tests/unit/conftest.py -> ../../.. -> project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Testy jednostkowe CRUD nie mogą pisać do prawdziwej bazy data/czarna.db.
# Tworzymy kopię roboczą przed importem backend.main, bo konfiguracja DB jest
# ładowana przy imporcie modułów backend.config/backend.database.
_test_tmp_dir = tempfile.mkdtemp(prefix="mapa_unit_db_")
_source_db = os.path.join(project_root, "data", "czarna.db")
_test_db = os.path.join(_test_tmp_dir, "czarna-unit.db")
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

# Importujemy aplikację FastAPI (po migracji z Flask — app.py → backend/main.py)
from backend.main import app
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    """Fixture udostępniająca testowego klienta FastAPI."""
    with TestClient(app) as client:
        yield client
