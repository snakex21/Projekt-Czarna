"""
================================================================================
Plik: test_api_demografia.py
Opis: Testy operacji CRUD dla API danych demograficznych.
================================================================================
"""

import pytest
from backend import config as backend_config

# ================================================================================
# TESTY CRUD DLA DEMOGRAFII
# ================================================================================

def test_demografia_crud(client, monkeypatch):
    """Test pelnego cyklu CRUD dla danych demograficznych."""
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", True)
    client.cookies.set("admin_logged_in", "true")

    # --- READ: Poczatkowy stan ---
    resp = client.get("/api/admin/demografia")
    assert resp.status_code == 200
    initial = resp.json()
    assert isinstance(initial, list)

    # --- CREATE ---
    payload = {
        "rok": 1850,
        "populacja_ogolem": 100,
        "katolicy": 80,
        "zydzi": 15,
        "inni": 5,
        "opis": "Testowy wpis"
    }
    resp = client.post("/api/admin/demografia", json=payload)
    assert resp.status_code in (200, 201)
    created = resp.json()
    new_id = created.get("id")
    assert isinstance(new_id, int)

    # --- UPDATE ---
    update_payload = {
        "rok": 1860,
        "populacja_ogolem": 120,
        "katolicy": 90,
        "zydzi": 20,
        "inni": 10,
        "opis": "Zmieniony opis"
    }
    resp = client.put(f"/api/admin/demografia/{new_id}", json=update_payload)
    assert resp.status_code in (200, 204) or resp.json().get("status") == "success"

    # --- READ po UPDATE ---
    resp = client.get("/api/admin/demografia")
    assert resp.status_code == 200
    arr = resp.json()
    assert any(r["rok"] == 1860 and r.get("populacja_ogolem") == 120 for r in arr)

    # --- DELETE ---
    resp = client.delete(f"/api/admin/demografia/{new_id}")
    assert resp.status_code in (200, 204) or resp.json().get("status") == "success"
