"""
Plik: test_api_genealogia.py
Opis: Moduł testowy dla API genealogii w panelu administracyjnym.
      Zawiera testy CRUD oraz walidacji danych genealogicznych.
"""

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
    """
    Generuje payload testowy dla osoby w systemie genealogicznym.
    
    Returns:
        dict: Słownik z danymi osoby gotowy do wysłania w żądaniu API
    """
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
    """
    Test pełnego cyklu CRUD dla modułu genealogii.
    Weryfikuje tworzenie, odczyt, aktualizację i usuwanie osoby.
    """
    # Konfiguracja autoryzacji dla testów
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    # === CREATE: Dodanie nowej osoby ===
    payload = _osoba_payload()
    resp = client.post("/api/admin/genealogia", json=payload)
    assert resp.status_code in (200, 201)
    
    # Pobranie ID nowo utworzonego rekordu
    new_db_id = resp.get_json().get("id")
    assert isinstance(new_db_id, int) and new_db_id > 0

    # === READ: Weryfikacja dodania osoby ===
    resp = client.get("/api/admin/genealogia")
    assert resp.status_code == 200
    
    # Szukanie utworzonej osoby w odpowiedzi
    data = resp.get_json()
    created_person = next((p for p in data if p["db_id"] == new_db_id), None)
    assert created_person is not None
    assert created_person["imie"] == "Jan"

    # === UPDATE: Modyfikacja danych osoby ===
    upd_payload = _osoba_payload(
        id_osoby=1001, 
        imie="Anna", 
        plec="F", 
        uwagi="Zmienione"
    )
    resp = client.put(f"/api/admin/genealogia/{new_db_id}", json=upd_payload)
    assert resp.status_code in (200, 204) or resp.get_json().get("status") == "success"

    # === READ: Weryfikacja aktualizacji ===
    resp = client.get("/api/admin/genealogia")
    data = resp.get_json()
    updated_person = next((p for p in data if p["db_id"] == new_db_id), None)
    assert updated_person["imie"] == "Anna"
    assert updated_person["uwagi"] == "Zmienione"

    # === DELETE: Usunięcie osoby ===
    resp = client.delete(f"/api/admin/genealogia/{new_db_id}")
    assert resp.status_code in (200, 204) or resp.get_json().get("status") == "success"

    # === READ: Weryfikacja usunięcia ===
    resp = client.get("/api/admin/genealogia")
    data = resp.get_json()
    assert all(p["db_id"] != new_db_id for p in data)


# ==========================================================================
# TESTY WALIDACJI
# ==========================================================================

def test_genealogia_validation_missing_required_field(client, monkeypatch):
    """
    Test walidacji danych - brak wymaganego pola.
    Sprawdza reakcję API na niepełne dane osoby.
    """
    # Konfiguracja autoryzacji
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", True)
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    # Przygotowanie nieprawidłowego payload'u - brak nazwiska
    bad = _osoba_payload()
    bad.pop("nazwisko")

    # Wysłanie żądania z brakującym polem
    resp = client.post("/api/admin/genealogia", json=bad)
    
    # Oczekiwana odpowiedź: 400 (błąd walidacji) lub 500 (błąd serwera)
    assert resp.status_code in (400, 500)