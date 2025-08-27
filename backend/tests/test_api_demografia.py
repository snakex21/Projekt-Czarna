# Prosty CRUD dla demografii, żeby pokazać testy POST/PUT/DELETE na innej tabeli.

def test_demografia_crud(client, monkeypatch):
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    # Na starcie GET może być puste
    resp = client.get("/api/admin/demografia")
    assert resp.status_code == 200
    initial = resp.get_json()
    assert isinstance(initial, list)

    # CREATE – pełny payload 
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
    created = resp.get_json()
    new_id = created.get("id")
    assert isinstance(new_id, int)

    # UPDATE – pełny zestaw, jak w UPDATE w app.py
    update_payload = {
        "rok": 1860,
        "populacja_ogolem": 120,
        "katolicy": 90,
        "zydzi": 20,
        "inni": 10,
        "opis": "Zmieniony opis"
    }
    resp = client.put(f"/api/admin/demografia/{new_id}", json=update_payload)
    assert resp.status_code in (200, 204) or resp.get_json().get("status") == "success"

    # GET po UPDATE (lista)
    resp = client.get("/api/admin/demografia")
    assert resp.status_code == 200
    arr = resp.get_json()
    assert any(r["rok"] == 1860 and r.get("populacja_ogolem") == 120 for r in arr)

    # DELETE
    resp = client.delete(f"/api/admin/demografia/{new_id}")
    assert resp.status_code in (200, 204) or resp.get_json().get("status") == "success"
