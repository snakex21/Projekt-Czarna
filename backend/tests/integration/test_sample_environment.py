"""Backend i podproces E2E korzystają z jawnie wybranego środowiska."""
import os
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app
from backend import config


def test_app_database_matches_shared_test_environment():
    assert Path(config.DB_PATH) == Path(os.environ["DB_PATH"])
    assert config.BACKUP_DIR == Path(os.environ["BACKUP_DIR"])
    assert config.BACKUP_DIR != config.BASE_DIR / "data" / "locations"


def test_homepage_background_and_favicon_are_available():
    with TestClient(app) as client:
        for url in ("/mapa/mapa.jpg", "/location_favicon"):
            response = client.get(url)
            assert response.status_code == 200, url
            assert response.headers["content-type"].startswith("image/")
