"""Testy utwardzenia HTTP: nagłówki, limit rozmiaru, Origin/CORS, walidacja wejścia, 404 API."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def http():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Nagłówki bezpieczeństwa
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/health", "/strona_glowna/index.html", "/api/nie-istnieje"])
def test_security_headers_present(http, path):
    resp = http.get(path)
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "SAMEORIGIN"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'self'" in resp.headers["content-security-policy"]
    assert "permissions-policy" in resp.headers


# ---------------------------------------------------------------------------
# Nieznane /api/* → 404 JSON, nie HTML z fallbacku
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/parcels", "/api/admin/nope", "/api"])
def test_unknown_api_path_is_404_json(http, path):
    resp = http.get(path)
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


# ---------------------------------------------------------------------------
# Limit rozmiaru żądania
# ---------------------------------------------------------------------------


def test_oversized_body_rejected_by_content_length(http, admin_client, monkeypatch):
    from backend import config
    monkeypatch.setattr(config, "MAX_REQUEST_BODY_BYTES", 1024)
    resp = admin_client.post("/api/admin/demografia", content=b"x" * 2048, headers={"Content-Type": "application/json"})
    assert resp.status_code == 413


def test_oversized_chunked_body_rejected(http, admin_client, monkeypatch):
    from backend import config
    monkeypatch.setattr(config, "MAX_REQUEST_BODY_BYTES", 1024)

    def gen():
        for _ in range(8):
            yield b"x" * 512

    resp = admin_client.post("/api/dzialki/save", content=gen(), headers={"Content-Type": "application/json"})
    assert resp.status_code == 413


def test_oversized_login_body_rejected_before_auth(http, monkeypatch):
    from backend import config
    monkeypatch.setattr(config, "MAX_REQUEST_BODY_BYTES", 256)
    resp = http.post("/api/admin/login", json={"username": "admin", "password": "x" * 1000})
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Origin / CORS
# ---------------------------------------------------------------------------


def test_cross_origin_mutation_rejected(http, admin_client):
    resp = admin_client.post(
        "/api/admin/demografia", json={"rok": 1900}, headers={"Origin": "https://evil.example"}
    )
    assert resp.status_code == 403


def test_cross_origin_login_rejected(http):
    resp = http.post(
        "/api/admin/login", json={"username": "admin", "password": "x"}, headers={"Origin": "https://evil.example"}
    )
    assert resp.status_code == 403


def test_same_origin_mutation_allowed(http, admin_client):
    resp = admin_client.post(
        "/api/admin/demografia", json={"rok": 1900}, headers={"Origin": "http://testserver"}
    )
    assert resp.status_code == 201
    admin_client.delete(f"/api/admin/demografia/{resp.json()['id']}")


def test_cors_does_not_reflect_arbitrary_origin(http):
    resp = http.get("/api/health", headers={"Origin": "https://evil.example"})
    assert resp.headers.get("access-control-allow-origin") is None
    pre = http.options(
        "/api/admin/demografia",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert pre.headers.get("access-control-allow-origin") is None


# ---------------------------------------------------------------------------
# Walidacja wejścia (Pydantic)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("POST", "/api/admin/wlasciciele", {"nazwa_wlasciciela": {"x": 1}}),
        ("POST", "/api/admin/wlasciciele", {"nazwa_wlasciciela": "x" * 300}),
        ("POST", "/api/admin/wlasciciele", {"dzialki_protokol_ids": ["abc"]}),
        ("POST", "/api/admin/demografia", {"rok": "tysiac"}),
        ("POST", "/api/admin/demografia", {"rok": 1900, "katolicy": -5}),
        ("POST", "/api/admin/genealogia", {"rok_urodzenia": 99999}),
        ("POST", "/api/admin/genealogia", {"imie": ["a"]}),
        ("PUT", "/api/admin/obiekty/1", {"kategoria": "x" * 100}),
        ("POST", "/api/dzialki/save", {"features": "nie-lista"}),
        ("POST", "/api/dzialki/save", {"features": [{"geometry": "nie-obiekt"}]}),
    ],
)
def test_invalid_payloads_rejected_with_422(admin_client, method, path, payload):
    resp = admin_client.request(method, path, json=payload)
    assert resp.status_code == 422, resp.text


def test_form_style_strings_are_accepted(admin_client):
    """Frontend wysyła liczby jako tekst i puste pola jako "" - to musi działać."""
    resp = admin_client.post(
        "/api/admin/demografia",
        json={"rok": "1882", "populacja_ogolem": "555", "katolicy": "", "zydzi": "50", "inni": "0", "opis": "x"},
    )
    assert resp.status_code == 201, resp.text
    admin_client.delete(f"/api/admin/demografia/{resp.json()['id']}")


def test_invalid_json_body_rejected(admin_client):
    resp = admin_client.post(
        "/api/admin/demografia", content=b"{nie json", headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 422


def test_server_errors_do_not_leak_exception_text(admin_client, monkeypatch):
    from backend.routers import admin as admin_router

    async def boom(*_a, **_k):
        raise RuntimeError("SELECT * FROM sekretna_tabela")

    monkeypatch.setattr(admin_router, "execute", boom)
    resp = admin_client.post("/api/admin/demografia", json={"rok": 1900})
    assert resp.status_code == 500
    assert "sekretna_tabela" not in resp.text
