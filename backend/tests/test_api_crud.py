# Testy CRUD dla /api/admin/wlasciciele + edge‑case dla brakujących pól.
# Działają na rozbudowanym mocku z conftest.py (in‑memory DB).

def _full_owner_payload(
    unikalny_klucz="U-1",
    nazwa_wlasciciela="Jan Kowalski",
    numer_protokolu=1,
    numer_domu="123",
    genealogia="Test genealogii",
    historia_wlasnosci="Test historii",
    uwagi="Testowe uwagi",
    wspolwlasnosc="Test współwłasności",
    powiazania_i_transakcje="[[Link|W-2]]",
    interpretacja_i_wnioski="Testowe wnioski",
    data_protokolu="2023-01-01",
    miejsce_protokolu="Czarna",
    dzialki_rzeczywiste_ids=None,
    dzialki_protokol_ids=None,
):
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

def test_owner_crud_and_parcel_linking_roundtrip(client, monkeypatch):
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    # CREATE
    payload = _full_owner_payload()
    resp = client.post("/api/admin/wlasciciele", json=payload)
    assert resp.status_code == 201
    new_id = resp.get_json().get("id")
    assert isinstance(new_id, int) and new_id > 0

    # READ pojedynczy
    resp = client.get(f"/api/admin/wlasciciele/{new_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == new_id

    # Pobierz ID obiektów do podlinkowania z mock bazy
    resp = client.get("/api/admin/obiekty")
    obiekty = resp.get_json()
    parcel_ids_to_link = [obiekty[0]['id'], obiekty[1]['id']]

    updated_payload = _full_owner_payload(
        unikalny_klucz="U-1A",
        nazwa_wlasciciela="Jan Nowy",
        dzialki_protokol_ids=parcel_ids_to_link
    )
    
    # Wywołaj PUT, który obsługuje zarówno update, jak i linkowanie
    resp = client.put(f"/api/admin/wlasciciele/{new_id}", json=updated_payload)
    assert resp.status_code in (200, 204) or resp.get_json().get("status") == "success"

    # READ sprawdzenie po UPDATE
    resp = client.get(f"/api/admin/wlasciciele/{new_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["nazwa_wlasciciela"] == "Jan Nowy"
    
    # Sprawdź, czy działki zostały poprawnie podlinkowane
    linked_parcel_ids = [p['id'] for p in data.get('dzialki_wszystkie', [])]
    assert sorted(linked_parcel_ids) == sorted(parcel_ids_to_link)

    # DELETE
    resp = client.delete(f"/api/admin/wlasciciele/{new_id}")
    assert resp.status_code in (200, 204) or resp.get_json().get("status") == "success"

    # READ po DELETE → 404
    resp = client.get(f"/api/admin/wlasciciele/{new_id}")
    assert resp.status_code == 404

def test_owner_create_missing_required_field_returns_error(client, monkeypatch):
    # Backend zwraca 500 przy braku obowiązkowych pól (wyjątek → 500).
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    bad_payload = _full_owner_payload()
    bad_payload.pop("nazwa_wlasciciela")  # wywola KeyError w backendzie

    resp = client.post("/api/admin/wlasciciele", json=bad_payload)
    # W idealnym świecie byłoby 400, ale realny kod zwraca 500 — test to dokumentuje.
    assert resp.status_code == 500
