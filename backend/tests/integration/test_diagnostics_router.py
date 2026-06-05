"""Testy integracyjne routera diagnostyki.

Weryfikujemy:
- Endpoint zwraca 9 metryk
- Endpoint jest chroniony przez admin auth
- Payload ma poprawny kształt (count: int, sample: list)
- Kolejność routerów: diagnostics PRZED static_files (nie łapany przez catch-all)
"""
from __future__ import annotations


def test_diagnostics_endpoint_returns_9_metrics(admin_client):
    """``GET /api/admin/diagnostics`` zwraca 9 metryk + sample."""
    resp = admin_client.get("/api/admin/diagnostics")
    assert resp.status_code == 200, (
        f"Oczekiwano 200, mamy {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, dict)
    expected_keys = {
        "parcels_without_owners",
        "owners_without_parcels",
        "protocols_without_genealogy",
        "people_without_parents",
        "people_without_birth_date",
        "people_without_death_date",
        "parcels_without_category",
        "owners_without_house_number",
        "parcel_owner_links",
        "incomplete_records",
    }
    assert expected_keys.issubset(set(data.keys())), (
        f"Brak metryk: {expected_keys - set(data.keys())}"
    )


def test_diagnostics_requires_admin_auth():
    """Endpoint wymaga zalogowania admina - bez logowania zwraca 401/403.

    Używamy świeżego TestClient (nie conftest fixture) bo ``client`` jest
    module-scoped i cookies z wcześniejszych logowań by persistowały.
    """
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as fresh_client:
        resp = fresh_client.get("/api/admin/diagnostics")
    # admin_required może zwracać 401 (unauthorized) lub 403 (forbidden)
    # zależnie od implementacji - akceptujemy oba
    assert resp.status_code in (401, 403), (
        f"Oczekiwano 401/403 bez logowania, mamy {resp.status_code}"
    )


def test_diagnostics_parcel_owner_links_is_positive_int(admin_client):
    """``parcel_owner_links.count`` jest > 0 (baza ma 3903 powiązań)."""
    resp = admin_client.get("/api/admin/diagnostics")
    data = resp.json()
    assert data["parcel_owner_links"]["count"] > 0


def test_diagnostics_samples_have_id_and_name(admin_client):
    """Każdy sample ma pola ``id`` i ``name``."""
    resp = admin_client.get("/api/admin/diagnostics")
    data = resp.json()
    for key in [
        "parcels_without_owners",
        "owners_without_parcels",
        "protocols_without_genealogy",
        "people_without_parents",
        "people_without_birth_date",
        "people_without_death_date",
        "parcels_without_category",
        "owners_without_house_number",
    ]:
        sample = data[key]["sample"]
        if sample:
            first = sample[0]
            assert "id" in first
            assert "name" in first


def test_diagnostics_endpoint_not_caught_by_static_catchall(admin_client):
    """``/api/admin/diagnostics`` nie może być przechwycony przez ``/{filename:path}``.

    Gdyby router był zarejestrowany PO static_files, zwróciłby HTML 404 zamiast JSON.
    """
    resp = admin_client.get("/api/admin/diagnostics")
    content_type = resp.headers.get("content-type", "")
    assert "json" in content_type, (
        f"Diagnostics powinien zwracać JSON, content-type={content_type}"
    )
