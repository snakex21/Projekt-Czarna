"""
Plik: test_api_obiekty.py
Opis: Modul testowy dla API obiektow geograficznych.
      Weryfikuje operacje odczytu, aktualizacji i usuwania obiektow.
"""

import pytest
from backend import config as backend_config

# ==========================================================================
# TESTY CRUD OBIEKTOW
# ==========================================================================

def test_obiekty_list_and_update_and_delete(client, monkeypatch):
    """Test kompleksowy operacji na obiektach geograficznych."""
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", True)
    client.cookies.set("admin_logged_in", "true")

    # === READ ===
    resp = client.get("/api/admin/obiekty")
    assert resp.status_code == 200
    
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1

    first = items[0]
    oid = first["id"]

    # === UPDATE ===
    updated = {
        "nazwa_lub_numer": "1A", 
        "kategoria": "budowlana"
    }
    resp = client.put(f"/api/admin/obiekty/{oid}", json=updated)
    assert resp.status_code == 200
    assert resp.json().get("status") == "success"

    # === READ po UPDATE ===
    resp = client.get("/api/admin/obiekty")
    assert resp.status_code == 200
    
    after = resp.json()
    changed = next((r for r in after if r["id"] == oid), None)
    assert changed is not None
    assert changed["nazwa_lub_numer"] == "1A"
    assert changed["kategoria"] == "budowlana"

    # === DELETE ===
    resp = client.delete(f"/api/admin/obiekty/{oid}")
    assert resp.status_code == 200
    assert resp.json().get("status") == "success"

    # === READ po DELETE ===
    resp = client.get("/api/admin/obiekty")
    assert resp.status_code == 200
    
    final = resp.json()
    assert all(r["id"] != oid for r in final)
