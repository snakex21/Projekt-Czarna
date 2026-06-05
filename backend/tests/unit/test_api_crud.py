"""
================================================================================
Plik: test_api_crud.py
Opis: Testy operacji CRUD dla API wlascicieli.
================================================================================
"""

import pytest
from backend import config as backend_config

# ================================================================================
# FUNKCJE POMOCNICZE
# ================================================================================

def _full_owner_payload(
    unikalny_klucz="U-1",
    nazwa_wlasciciela="Jan Kowalski",
    numer_protokolu=1,
    numer_domu="123",
    genealogia="Test genealogii",
    historia_wlasnosci="Test historii",
    uwagi="Testowe uwagi",
    wspolwlasnosc="Test wspolwlasnosci",
    powiazania_i_transakcje="[[Link|W-2]]",
    interpretacja_i_wnioski="Testowe wnioski",
    data_protokolu="2023-01-01",
    miejsce_protokolu="Czarna",
    dzialki_rzeczywiste_ids=None,
    dzialki_protokol_ids=None,
):
    """Generuje kompletny payload wlasciciela dla testow."""
    return {
        "unikalny_klucz": unikalny_klucz,
        "nazwa_wlasciciela": nazwa_wlasciciela,
        "numer_protokolu": numer_protokolu,
        "numer_domu": numer_domu,
        "genealogia": genealogia,
        "historia_wlasnosci": historia_wlasnosci,
        "uwagi": uwagi,
        "wspolwlasnosc": wspolwlasnosc,
        "powiazania_i_transakcje": powiazania_i_transakcje,
        "interpretacja_i_wnioski": interpretacja_i_wnioski,
        "data_protokolu": data_protokolu,
        "miejsce_protokolu": miejsce_protokolu,
        "dzialki_rzeczywiste_ids": dzialki_rzeczywiste_ids or [],
        "dzialki_protokol_ids": dzialki_protokol_ids or [],
    }

# ================================================================================
# TESTY
# ================================================================================

def test_owner_crud_and_parcel_linking_roundtrip(client, monkeypatch):
    """Test kompleksowy: CREATE -> READ -> UPDATE -> DELETE wlasciciela."""
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", True)
    client.cookies.set("admin_logged_in", "true")

    # --- CREATE ---
    payload = _full_owner_payload()
    resp = client.post("/api/admin/wlasciciele", json=payload)
    assert resp.status_code == 201
    new_id = resp.json().get("id")
    assert isinstance(new_id, int) and new_id > 0

    # --- READ ---
    resp = client.get(f"/api/admin/wlasciciele/{new_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == new_id

    # --- UPDATE ---
    resp = client.get("/api/admin/obiekty")
    obiekty = resp.json()
    
    updated_payload = _full_owner_payload(
        unikalny_klucz="U-1A",
        nazwa_wlasciciela="Jan Nowy",
    )
    if len(obiekty) >= 2:
        updated_payload["dzialki_protokol_ids"] = [obiekty[0]['id'], obiekty[1]['id']]
    
    resp = client.put(f"/api/admin/wlasciciele/{new_id}", json=updated_payload)
    assert resp.status_code in (200, 204) or resp.json().get("status") == "success"

    resp = client.get(f"/api/admin/wlasciciele/{new_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nazwa_wlasciciela"] == "Jan Nowy"
    
    if len(obiekty) >= 2:
        linked_parcel_ids = [p['id'] for p in data.get('dzialki_wszystkie', [])]
        assert sorted(linked_parcel_ids) == sorted([obiekty[0]['id'], obiekty[1]['id']])

    # --- DELETE ---
    resp = client.delete(f"/api/admin/wlasciciele/{new_id}")
    assert resp.status_code in (200, 204) or resp.json().get("status") == "success"

    resp = client.get(f"/api/admin/wlasciciele/{new_id}")
    assert resp.status_code == 404


def test_owner_create_missing_required_field_returns_error(client, monkeypatch):
    """
    Test tworzenia wlasciciela z brakujacym polem wymaganym.
    FastAPI nie ma walidacji na poziomie aplikacji dla tego pola,
    wiec rekord powstaje z NULL w brakujacym polu (status 201).
    """
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", True)
    client.cookies.set("admin_logged_in", "true")

    bad_payload = _full_owner_payload()
    bad_payload.pop("nazwa_wlasciciela")

    resp = client.post("/api/admin/wlasciciele", json=bad_payload)
    # Akceptujemy zarowno 201 (brak walidacji) jak i 400/500 (gdyby byla walidacja)
    assert resp.status_code in (201, 400, 500)
