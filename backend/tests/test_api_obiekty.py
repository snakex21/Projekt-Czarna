# Testy CRUD dla obiektów geograficznych.
# Backend ma GET listę, PUT update i DELETE. POST nie ma — dane seedujemy w conftest.py.

def test_obiekty_list_and_update_and_delete(client, monkeypatch):
    import app as backend_app
    # Wymuś autoryzację i „zaloguj” admina dla ścieżek admina
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    # GET lista – powinna być >= 1 (seed w conftest.py daje 5)
    resp = client.get("/api/admin/obiekty")
    assert resp.status_code == 200
    items = resp.get_json()
    assert isinstance(items, list)
    assert len(items) >= 1

    # Weź pierwszy obiekt do modyfikacji
    first = items[0]
    oid = first["id"]

    # UPDATE: zmiana nazwy i kategorii
    updated = {"nazwa_lub_numer": "1A", "kategoria": "budowlana"}
    resp = client.put(f"/api/admin/obiekty/{oid}", json=updated)
    assert resp.status_code == 200
    assert resp.get_json().get("status") == "success"

    # GET lista – obiekt powinien mieć zaktualizowane pola
    resp = client.get("/api/admin/obiekty")
    assert resp.status_code == 200
    after = resp.get_json()
    changed = next((r for r in after if r["id"] == oid), None)
    assert changed is not None
    assert changed["nazwa_lub_numer"] == "1A"
    assert changed["kategoria"] == "budowlana"

    # DELETE
    resp = client.delete(f"/api/admin/obiekty/{oid}")
    assert resp.status_code == 200
    assert resp.get_json().get("status") == "success"

    # GET lista – obiekt powinien zniknąć
    resp = client.get("/api/admin/obiekty")
    assert resp.status_code == 200
    final = resp.get_json()
    assert all(r["id"] != oid for r in final)
