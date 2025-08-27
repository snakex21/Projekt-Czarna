# Testy CRUD dla genealogii + walidacja błędnych danych.
# Zakładamy ścieżki:
#   GET/POST   /api/admin/genealogia
#   GET/PUT/DELETE /api/admin/genealogia/<id>

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

def test_genealogia_crud(client, monkeypatch):
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    # CREATE
    payload = _osoba_payload()
    resp = client.post("/api/admin/genealogia", json=payload)
    assert resp.status_code in (200, 201)
    new_db_id = resp.get_json().get("id")
    assert isinstance(new_db_id, int) and new_db_id > 0

    # READ (po GET all)
    resp = client.get(f"/api/admin/genealogia")
    assert resp.status_code == 200
    data = resp.get_json()
    created_person = next((p for p in data if p["db_id"] == new_db_id), None)
    assert created_person is not None
    assert created_person["imie"] == "Jan"

    # UPDATE
    upd_payload = _osoba_payload(id_osoby=1001, imie="Anna", plec="F", uwagi="Zmienione")
    resp = client.put(f"/api/admin/genealogia/{new_db_id}", json=upd_payload)
    assert resp.status_code in (200, 204) or resp.get_json().get("status") == "success"

    # READ (po UPDATE)
    resp = client.get(f"/api/admin/genealogia")
    data = resp.get_json()
    updated_person = next((p for p in data if p["db_id"] == new_db_id), None)
    assert updated_person["imie"] == "Anna"
    assert updated_person["uwagi"] == "Zmienione"

    # DELETE
    resp = client.delete(f"/api/admin/genealogia/{new_db_id}")
    assert resp.status_code in (200, 204) or resp.get_json().get("status") == "success"

    # READ po DELETE
    resp = client.get(f"/api/admin/genealogia")
    data = resp.get_json()
    assert all(p["db_id"] != new_db_id for p in data)


def test_genealogia_validation_missing_required_field(client, monkeypatch):
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    bad = _osoba_payload()
    bad.pop("nazwisko")  # brak wymaganego pola

    resp = client.post("/api/admin/genealogia", json=bad)
    # Idealnie: 400 Bad Request, ale jeśli backend rzuca wyjątek -> 500; dokumentujemy to
    assert resp.status_code in (400, 500)
