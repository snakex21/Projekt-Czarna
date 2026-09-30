import pytest
import os
import sys

# Dodajemy katalog projektu do sys.path, aby testy mogły importować pakiet backend
# backend/tests/unit/conftest.py -> ../../.. -> project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Syntetyczna baza i konfiguracja powstają w backend/tests/conftest.py.

# Importujemy aplikację FastAPI (po migracji z Flask — app.py → backend/main.py)
from backend.main import app
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    """Fixture udostępniająca testowego klienta FastAPI."""
    with TestClient(app) as client:
        yield client
