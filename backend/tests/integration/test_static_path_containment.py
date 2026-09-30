"""Pliki publiczne nie mogą ujawniać danych spoza swojego katalogu."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.routers import static_files


@pytest.fixture
def static_client(tmp_path, monkeypatch):
    monkeypatch.setattr(static_files, 'BASE_DIR', tmp_path)
    monkeypatch.setattr(static_files, 'BACKUP_DIR', tmp_path / 'locations')
    monkeypatch.setattr(static_files, 'ACTIVE_LOCATION', 'Test')
    monkeypatch.setattr(static_files, 'FRONTEND_DIR', tmp_path / 'static')
    roots = {
        'history_photos': tmp_path / 'locations/Test/history_photos',
        'point_photos': tmp_path / 'locations/Test/point_photos',
        'dokumentacja': tmp_path / 'dokumentacja',
        'assets': tmp_path / 'static/assets',
    }
    for root in roots.values():
        root.mkdir(parents=True)
        (root / 'public.txt').write_text('public fixture')
        (root.parent / 'private.txt').write_text('private fixture')

    app = FastAPI()
    app.include_router(static_files.router)
    return TestClient(app)


@pytest.mark.parametrize('route', ['history_photos', 'point_photos', 'dokumentacja', 'assets'])
def test_public_files_still_work(static_client, route):
    response = static_client.get(f'/{route}/public.txt')
    assert response.status_code == 200
    assert response.text == 'public fixture'


@pytest.mark.parametrize('route', ['history_photos', 'point_photos', 'dokumentacja'])
def test_file_routes_reject_escape(static_client, route):
    response = static_client.get(f'/{route}/%2e%2e/private.txt')
    assert response.status_code == 404
    assert 'private fixture' not in response.text


def test_static_catch_all_rejects_escape(static_client):
    response = static_client.get('/%2e%2e/private.txt')
    assert response.status_code == 404


def test_static_catch_all_rejects_symlink_escape(tmp_path, static_client):
    (tmp_path / 'private.txt').write_text('private fixture')
    _symlink_or_skip(tmp_path / 'static/outside.txt', tmp_path / 'private.txt')
    assert static_client.get('/outside.txt').status_code == 404


def test_health_is_json_not_frontend_fallback():
    from backend.main import app
    response = TestClient(app).get('/api/health')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/json')
    assert response.json()['status'] == 'ok'


def _symlink_or_skip(link, target):
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip('Tworzenie dowiązań nie jest dostępne na tym systemie')


@pytest.mark.parametrize('route', ['history_photos', 'point_photos', 'dokumentacja'])
def test_file_routes_reject_symlink(tmp_path, static_client, route):
    root = tmp_path / ('dokumentacja' if route == 'dokumentacja' else f'locations/Test/{route}')
    _symlink_or_skip(root / 'outside.txt', root.parent / 'private.txt')
    assert static_client.get(f'/{route}/outside.txt').status_code == 404


def test_protocol_scan_rejects_symlink(tmp_path, static_client):
    root = tmp_path / 'locations/Test/protokoly/Owner'
    root.mkdir(parents=True)
    outside = tmp_path / 'private.jpg'
    outside.write_text('private fixture')
    _symlink_or_skip(root / '1.jpg', outside)
    assert static_client.get('/protokoly/Owner/1.jpg').status_code == 404
