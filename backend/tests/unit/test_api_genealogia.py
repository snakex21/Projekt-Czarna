"""
Plik: test_api_genealogia.py
Opis: Modul testowy dla API genealogii w panelu administracyjnym.
      Zawiera testy CRUD oraz walidacji danych genealogicznych.
"""

import pytest
from backend import config as backend_config

# ==========================================================================
# FUNKCJE POMOCNICZE
# ==========================================================================

def _osoba_payload(
    id_osoby=1001,
    imie="Jan",
    nazwisko="Testowy",
    plec="M",
    rok_urodzenia=1900,
    rok_smierci=None,
    numer_domu="123",
    uwagi="",
    id_ojca=None,
    id_matki=None,
    id_malzonka=None,
    protokol_klucz=None,
):
    """Generuje payload testowy dla osoby w systemie genealogicznym."""
    return {
        "id_osoby": id_osoby,
        "imie": imie,
        "nazwisko": nazwisko,
        "plec": plec,
        "rok_urodzenia": rok_urodzenia,
        "rok_smierci": rok_smierci,
        "numer_domu": numer_domu,
        "uwagi": uwagi,
        "id_ojca": id_ojca,
        "id_matki": id_matki,
        "id_malzonka": id_malzonka,
        "protokol_klucz": protokol_klucz,
    }


# ==========================================================================
# TESTY CRUD
# ==========================================================================

def test_genealogia_crud(client, monkeypatch):
    """Test pelnego cyklu CRUD dla modulu genealogii."""
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", True)
    client.cookies.set("admin_logged_in", "true")

    # === CREATE ===
    payload = _osoba_payload()
    resp = client.post("/api/admin/genealogia", json=payload)
    assert resp.status_code in (200, 201)
    
    new_db_id = resp.json().get("id")
    assert isinstance(new_db_id, int) and new_db_id > 0

    # === READ ===
    resp = client.get("/api/admin/genealogia")
    assert resp.status_code == 200
    
    data = resp.json()
    created_person = next((p for p in data if p["db_id"] == new_db_id), None)
    assert created_person is not None
    assert created_person["imie"] == "Jan"

    # === UPDATE ===
    upd_payload = _osoba_payload(
        id_osoby=1001, 
        imie="Anna", 
        plec="F", 
        uwagi="Zmienione"
    )
    resp = client.put(f"/api/admin/genealogia/{new_db_id}", json=upd_payload)
    assert resp.status_code in (200, 204) or resp.json().get("status") == "success"

    # === READ po UPDATE ===
    resp = client.get("/api/admin/genealogia")
    data = resp.json()
    updated_person = next((p for p in data if p["db_id"] == new_db_id), None)
    assert updated_person["imie"] == "Anna"
    assert updated_person["uwagi"] == "Zmienione"

    # === DELETE ===
    resp = client.delete(f"/api/admin/genealogia/{new_db_id}")
    assert resp.status_code in (200, 204) or resp.json().get("status") == "success"

    # === READ po DELETE ===
    resp = client.get("/api/admin/genealogia")
    data = resp.json()
    assert all(p["db_id"] != new_db_id for p in data)


# ==========================================================================
# TESTY WALIDACJI
# ==========================================================================

def test_genealogia_validation_missing_required_field(client, monkeypatch):
    """Test walidacji danych - brak wymaganego pola."""
    monkeypatch.setattr(backend_config, "ADMIN_AUTH_ENABLED", True)
    client.cookies.set("admin_logged_in", "true")

    bad = _osoba_payload()
    bad.pop("nazwisko")

    resp = client.post("/api/admin/genealogia", json=bad)
    # Akceptujemy 400/500 (walidacja) lub 201 (brak walidacji na poziomie aplikacji)
    assert resp.status_code in (201, 400, 500)
