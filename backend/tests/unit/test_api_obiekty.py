"""
Plik: test_api_obiekty.py
Opis: Moduł testowy dla API obiektów geograficznych.
      Weryfikuje operacje odczytu, aktualizacji i usuwania obiektów.
"""

# ==========================================================================
# TESTY CRUD OBIEKTÓW
# ==========================================================================

def test_obiekty_list_and_update_and_delete(client, monkeypatch):
    """
    Test kompleksowy operacji na obiektach geograficznych.
    Sprawdza listowanie, aktualizację i usuwanie obiektów z bazy danych.
    
    Uwaga: POST nie jest testowany - dane inicjalne pochodzą z seedowania (conftest.py)
    """
    import app as backend_app
    
    # Konfiguracja autoryzacji administracyjnej
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    # === READ: Pobranie listy obiektów ===
    resp = client.get("/api/admin/obiekty")
    assert resp.status_code == 200
    
    # Weryfikacja struktury odpowiedzi
    items = resp.get_json()
    assert isinstance(items, list)
    assert len(items) >= 1  # Minimum 1 obiekt (seed daje 5)

    # Wybór pierwszego obiektu do testów modyfikacji
    first = items[0]
    oid = first["id"]

    # === UPDATE: Modyfikacja danych obiektu ===
    updated = {
        "nazwa_lub_numer": "1A", 
        "kategoria": "budowlana"
    }
    resp = client.put(f"/api/admin/obiekty/{oid}", json=updated)
    assert resp.status_code == 200
    assert resp.get_json().get("status") == "success"

    # === READ: Weryfikacja aktualizacji ===
    resp = client.get("/api/admin/obiekty")
    assert resp.status_code == 200
    
    # Sprawdzenie czy dane zostały zaktualizowane
    after = resp.get_json()
    changed = next((r for r in after if r["id"] == oid), None)
    assert changed is not None
    assert changed["nazwa_lub_numer"] == "1A"
    assert changed["kategoria"] == "budowlana"

    # === DELETE: Usunięcie obiektu ===
    resp = client.delete(f"/api/admin/obiekty/{oid}")
    assert resp.status_code == 200
    assert resp.get_json().get("status") == "success"

    # === READ: Weryfikacja usunięcia ===
    resp = client.get("/api/admin/obiekty")
    assert resp.status_code == 200
    
    # Upewnienie się, że obiekt został usunięty
    final = resp.get_json()
    assert all(r["id"] != oid for r in final)