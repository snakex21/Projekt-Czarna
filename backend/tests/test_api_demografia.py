"""
================================================================================
Plik: test_api_demografia.py
Opis: Testy operacji CRUD dla API danych demograficznych
      Weryfikacja kompletnego cyklu zarządzania danymi historycznymi
================================================================================
"""

# ================================================================================
# TESTY CRUD DLA DEMOGRAFII
# ================================================================================

def test_demografia_crud(client, monkeypatch):
    """
    Test pełnego cyklu CRUD dla danych demograficznych.
    Weryfikuje CREATE → READ → UPDATE → DELETE.
    """
    # Konfiguracja autoryzacji
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    # --- READ: Początkowy stan (może być pusta lista) ---
    resp = client.get("/api/admin/demografia")
    assert resp.status_code == 200
    initial = resp.get_json()
    assert isinstance(initial, list)

    # --- CREATE: Dodanie nowego wpisu demograficznego ---
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

    # --- UPDATE: Modyfikacja istniejącego wpisu ---
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

    # --- READ: Weryfikacja zmian po aktualizacji ---
    resp = client.get("/api/admin/demografia")
    assert resp.status_code == 200
    arr = resp.get_json()
    # Sprawdzenie czy zaktualizowany rekord istnieje
    assert any(r["rok"] == 1860 and r.get("populacja_ogolem") == 120 for r in arr)

    # --- DELETE: Usunięcie wpisu ---
    resp = client.delete(f"/api/admin/demografia/{new_id}")
    assert resp.status_code in (200, 204) or resp.get_json().get("status") == "success"