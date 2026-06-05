"""
Testy integracyjne realnych edycji w panelu admina.

Pokrywaja najwazniejsze flow uzytkownika bez kruchego klikania w UI:
- edycja obiektu/dzialki,
- edycja osoby genealogicznej,
- przypisanie dzialki do wlasciciela.

Testy ida przez FastAPI TestClient + testowa kopie bazy, wiec sa szybkie,
powtarzalne i bezpieczne dla prawdziwych danych.
"""
import json

from .conftest import SAMPLE_OWNER_PAYLOAD


def _find_by_id(rows, row_id):
    for row in rows:
        if row.get("id") == row_id:
            return row
    return None


def test_admin_can_edit_geo_object_full_flow(admin_client):
    """Admin moze edytowac obiekt/dzialke i zmiana jest widoczna na liscie.

    Lapie regresje w PUT /api/admin/obiekty/{id}: brak update, zly payload,
    problemy z geometria jako tekst JSON.
    """
    list_resp = admin_client.get("/api/admin/obiekty")
    assert list_resp.status_code == 200
    objects = list_resp.json()
    assert objects, "Testowa baza musi miec co najmniej jeden obiekt"

    original = objects[0]
    object_id = original["id"]

    updated = {
        "nazwa_lub_numer": "TEST_DZIALKA_ADMIN_EDIT",
        "kategoria": "testowa",
        "geometria": json.dumps({"type": "Point", "coordinates": [20.0, 50.0]}),
    }

    try:
        update_resp = admin_client.put(f"/api/admin/obiekty/{object_id}", json=updated)
        assert update_resp.status_code == 200, update_resp.text

        after = admin_client.get("/api/admin/obiekty").json()
        row = _find_by_id(after, object_id)
        assert row is not None
        assert row["nazwa_lub_numer"] == updated["nazwa_lub_numer"]
        assert row["kategoria"] == updated["kategoria"]
        assert row["geometria"] == updated["geometria"]
    finally:
        restore = {
            "nazwa_lub_numer": original.get("nazwa_lub_numer"),
            "kategoria": original.get("kategoria"),
            "geometria": original.get("geometria"),
        }
        admin_client.put(f"/api/admin/obiekty/{object_id}", json=restore)


def test_admin_can_edit_genealogy_person_full_flow(admin_client):
    """Admin moze edytowac osobe genealogiczna i zmiana wraca z listy.

    Lapie regresje id_osoby/db_id oraz update imienia, lat, domu i notatek.
    """
    list_resp = admin_client.get("/api/admin/genealogia")
    assert list_resp.status_code == 200
    people = list_resp.json()
    assert people, "Testowa baza musi miec osoby genealogiczne"

    original = people[0]
    db_id = original["db_id"]
    original_name = original.get("imie_nazwisko") or original.get("name") or ""
    original_parts = original_name.split(" ", 1)

    update_payload = {
        "id_osoby": original["id_osoby"],
        "imie": "Testowy",
        "nazwisko": "Genealog",
        "plec": "M",
        "rok_urodzenia": 1901,
        "rok_smierci": 1977,
        "uwagi": "edytowane przez test integracyjny",
        "numer_domu": "TEST-DOM",
        "id_ojca": original.get("id_ojca"),
        "id_matki": original.get("id_matki"),
    }

    try:
        update_resp = admin_client.put(f"/api/admin/genealogia/{db_id}", json=update_payload)
        assert update_resp.status_code == 200, update_resp.text

        after = admin_client.get("/api/admin/genealogia").json()
        row = next((p for p in after if p.get("db_id") == db_id), None)
        assert row is not None
        assert row["id_osoby"] == original["id_osoby"]
        assert row["imie"] == "Testowy"
        assert row["nazwisko"] == "Genealog"
        assert row["name"] == "Testowy Genealog"
        assert row["rok_urodzenia"] == 1901
        assert row["rok_smierci"] == 1977
        assert row["numer_domu"] == "TEST-DOM"
        assert row["uwagi"] == "edytowane przez test integracyjny"
    finally:
        restore_payload = {
            "id_osoby": original["id_osoby"],
            "imie": original_parts[0] if original_parts else "",
            "nazwisko": original_parts[1] if len(original_parts) > 1 else "",
            "plec": original.get("plec"),
            "rok_urodzenia": original.get("rok_urodzenia"),
            "rok_smierci": original.get("rok_smierci"),
            "uwagi": original.get("uwagi"),
            "numer_domu": original.get("numer_domu"),
            "id_ojca": original.get("id_ojca"),
            "id_matki": original.get("id_matki"),
        }
        admin_client.put(f"/api/admin/genealogia/{db_id}", json=restore_payload)


def test_admin_can_assign_parcel_to_owner_full_flow(admin_client):
    """Admin moze przypisac dzialke do wlasciciela.

    Flow: wybierz obiekt -> utworz wlasciciela z dzialka -> GET wlasciciela
    pokazuje dzialki_wszystkie z id obiektu -> cleanup.
    """
    objects_resp = admin_client.get("/api/admin/obiekty")
    assert objects_resp.status_code == 200
    objects = objects_resp.json()
    assert objects, "Testowa baza musi miec obiekty do przypisania"
    parcel_id = objects[0]["id"]

    payload = dict(SAMPLE_OWNER_PAYLOAD)
    payload.update({
        "unikalny_klucz": "TEST_OWNER_WITH_PARCEL",
        "nazwa_wlasciciela": "Wlasciciel Z Dzialka",
        "dzialki_protokol_ids": [parcel_id],
    })

    create_resp = admin_client.post("/api/admin/wlasciciele", json=payload)
    assert create_resp.status_code == 201, create_resp.text
    owner_id = create_resp.json()["id"]

    try:
        owner_resp = admin_client.get(f"/api/admin/wlasciciele/{owner_id}")
        assert owner_resp.status_code == 200
        owner = owner_resp.json()
        assigned = owner.get("dzialki_wszystkie", [])
        assert any(item.get("id") == parcel_id for item in assigned), (
            f"Dzialka {parcel_id} nie zostala przypisana do wlasciciela: {assigned}"
        )
    finally:
        admin_client.delete(f"/api/admin/wlasciciele/{owner_id}")
