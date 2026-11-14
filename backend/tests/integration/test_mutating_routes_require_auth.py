"""Negatywne testy autoryzacji: KAŻDY endpoint zmieniający dane wymaga logowania.

Lista tras jest budowana automatycznie z ``app.routes`` - nowy endpoint
POST/PUT/PATCH/DELETE bez ``admin_required`` spowoduje błąd testu, chyba że
zostanie świadomie dopisany do ``PUBLIC_MUTATING_ROUTES``.
"""
from __future__ import annotations

import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.auth import admin_required, create_session_token
from backend.main import app

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Endpointy celowo publiczne (logowanie/wylogowanie).
PUBLIC_MUTATING_ROUTES = {
    ("POST", "/api/admin/login"),
    ("POST", "/api/admin/logout"),
}

# Endpointy GET, które też wymagają admina (eksport danych, diagnostyka).
ADMIN_ONLY_GET_ROUTES = {
    "/api/admin/export-backup",
    "/api/admin/diagnostics",
}


def _iter_api_routes(routes, prefix="", extra_deps=()):
    """Spłaszcza trasy aplikacji (także routery dołączone przez include_router).

    Nowsze FastAPI trzyma dołączone routery jako osobne obiekty zamiast
    kopiować trasy do ``app.routes``, więc schodzimy rekurencyjnie.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route, tuple(extra_deps)
        elif hasattr(route, "original_router"):
            ctx = getattr(route, "include_context", None)
            yield from _iter_api_routes(
                route.original_router.routes,
                prefix + (getattr(ctx, "prefix", "") or ""),
                tuple(extra_deps) + tuple(getattr(ctx, "dependencies", None) or ()),
            )


def _depends_on_admin(route: APIRoute, extra_deps=()) -> bool:
    if any(getattr(d, "dependency", None) is admin_required for d in extra_deps):
        return True
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if dep.call is admin_required:
            return True
        stack.extend(dep.dependencies)
    return False


def _concrete_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def _mutating_routes():
    routes = []
    for path, route, extra in _iter_api_routes(app.routes):
        for method in sorted(route.methods & MUTATING_METHODS):
            if (method, path) in PUBLIC_MUTATING_ROUTES:
                continue
            routes.append((method, path, (route, extra)))
    return routes


MUTATING_ROUTES = _mutating_routes()
ROUTE_IDS = [f"{m} {p}" for m, p, _ in MUTATING_ROUTES]


def test_route_enumeration_found_the_admin_api():
    """Bezpiecznik: enumeracja musi znaleźć znane trasy (inaczej test byłby pusty)."""
    paths = {(m, p) for m, p, _ in MUTATING_ROUTES}
    # Spójność z publicznym schematem OpenAPI: nic nie umknęło enumeracji.
    openapi_mutating = {
        (m.upper(), p)
        for p, ops in app.openapi()["paths"].items()
        for m in ops
        if m.upper() in MUTATING_METHODS and (m.upper(), p) not in PUBLIC_MUTATING_ROUTES
    }
    assert openapi_mutating <= paths
    assert len(paths) >= 12
    assert ("DELETE", "/api/admin/demografia/{entry_id}") in paths
    assert ("POST", "/api/dzialki/save") in paths
    assert ("POST", "/api/admin/change-password") in paths


@pytest.mark.parametrize("method,path,route", MUTATING_ROUTES, ids=ROUTE_IDS)
def test_mutating_route_declares_admin_dependency(method, path, route):
    api_route, extra = route
    assert _depends_on_admin(api_route, extra), f"{method} {path} nie ma zależności admin_required"


@pytest.fixture(scope="module")
def anon_client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("method,path,route", MUTATING_ROUTES, ids=ROUTE_IDS)
def test_mutating_route_rejects_anonymous(anon_client, method, path, route):
    anon_client.cookies.clear()
    resp = anon_client.request(method, _concrete_path(path), json={})
    assert resp.status_code in (401, 403), f"{method} {path} → {resp.status_code}: {resp.text[:200]}"


@pytest.mark.parametrize("method,path,route", MUTATING_ROUTES, ids=ROUTE_IDS)
def test_mutating_route_rejects_legacy_testclient_backdoor(anon_client, method, path, route):
    """Dawna furtka (User-Agent: testclient + admin_logged_in=true) nie działa."""
    anon_client.cookies.clear()
    anon_client.cookies.set("admin_logged_in", "true")
    resp = anon_client.request(
        method, _concrete_path(path), json={}, headers={"User-Agent": "testclient"}
    )
    anon_client.cookies.clear()
    assert resp.status_code in (401, 403)


@pytest.mark.parametrize("method,path,route", MUTATING_ROUTES, ids=ROUTE_IDS)
def test_mutating_route_rejects_forged_token(anon_client, method, path, route):
    anon_client.cookies.clear()
    token = create_session_token()
    body, sig = token.split(".")
    anon_client.cookies.set("admin_token", body + "." + sig[::-1])
    resp = anon_client.request(method, _concrete_path(path), json={})
    anon_client.cookies.clear()
    assert resp.status_code in (401, 403)


@pytest.mark.parametrize("method,path,route", MUTATING_ROUTES, ids=ROUTE_IDS)
def test_mutating_route_refused_when_admin_not_configured(anon_client, monkeypatch, method, path, route):
    """Bez skonfigurowanego hasła admina akcje są odrzucane nawet z ważnym tokenem."""
    token = create_session_token()
    from backend import config
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")
    anon_client.cookies.clear()
    anon_client.cookies.set("admin_token", token)
    resp = anon_client.request(method, _concrete_path(path), json={})
    anon_client.cookies.clear()
    assert resp.status_code == 403
    assert "set_admin_password" in resp.text


@pytest.mark.parametrize("path", sorted(ADMIN_ONLY_GET_ROUTES))
def test_admin_only_get_routes_reject_anonymous(anon_client, path):
    anon_client.cookies.clear()
    assert anon_client.get(path).status_code == 401


def test_delete_without_login_does_not_delete(anon_client, admin_client):
    """Scenariusz z przeglądu: DELETE bez logowania nie może usunąć rekordu."""
    created = admin_client.post("/api/admin/demografia", json={"rok": 1901, "populacja_ogolem": 10})
    assert created.status_code == 201
    entry_id = created.json()["id"]
    anon_client.cookies.clear()
    assert anon_client.delete(f"/api/admin/demografia/{entry_id}").status_code == 401
    ids = [row["id"] for row in admin_client.get("/api/admin/demografia").json()]
    assert entry_id in ids
    assert admin_client.delete(f"/api/admin/demografia/{entry_id}").status_code == 200
