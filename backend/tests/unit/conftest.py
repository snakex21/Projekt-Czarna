import pytest
import os
import sys

# Dodajemy katalog 'backend' do sys.path, aby testy mogły robić 'import app'
# backend/tests/unit/conftest.py -> ../.. -> backend/
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Importujemy aplikację Flask
from app import app

@pytest.fixture
def client():
    """Fixture udostępniająca testowego klienta Flask."""
    app.config['TESTING'] = True
    # Wyłączamy autoryzację dla prostych testów, jeśli potrzebne (ale testy same to robią monkeypatchem)
    with app.test_client() as client:
        yield client
