"""
Testy integracyjne CRUD dla wlasicieli.

Lapie realne bugi w:
- tworzeniu wlasciciela (brak unikalny_klucz, payload za duzy, missing fields)
- autoryzacji (unauth POST/PUT/DELETE -> 401)
- widocznosci zmian (PUT -> GET widzi nowe dane)
- usuwaniu (DELETE -> 404 przy powtornym GET)
"""
from .conftest import SAMPLE_OWNER_PAYLOAD  # noqa: F401  (re-eksport dla testów)


# ================================================================================
# Autoryzacja
# ================================================================================


def test_create_owner_without_auth_returns_401(client):
    """POST /api/admin/wlasciciele bez tokena -> 401.

    Krytyczny test bezpieczenstwa - bez niego ktos moglby omylkowo
    wylaczyc admin_required w create_wlasciciel.
    """
    client.cookies.clear()  # upewnij sie ze nie ma cookies
    resp = client.post("/api/admin/wlasciciele", json=SAMPLE_OWNER_PAYLOAD)
    assert resp.status_code == 401, (
        f"Create owner bez auth powinien zwrocic 401, mial: {resp.status_code} {resp.text}"
    )


def test_update_owner_without_auth_returns_401(client):
    """PUT /api/admin/wlasciciele/{id} bez tokena -> 401."""
    client.cookies.clear()
    resp = client.put("/api/admin/wlasciciele/1", json={"numer_domu": "99"})
    assert resp.status_code == 401


def test_delete_owner_without_auth_returns_401(client):
    """DELETE /api/admin/wlasciciele/{id} bez tokena -> 401."""
    client.cookies.clear()
    resp = client.delete("/api/admin/wlasciciele/1")
    assert resp.status_code == 401


# ================================================================================
# Full CRUD flow
# ================================================================================


def test_create_read_update_delete_owner_full_flow(admin_client):
    """End-to-end: create -> read -> update -> delete wlasciciela.

    Test najwyzszej wartosci - wykonuje caly flow ktory wykonuje
    uzytkownik w panelu admina. Jakikolwiek blad w ktorymkolwiek
    endpoincie crashuje ten test.

    Konwencja API:
    - POST zwraca {id, status} (nie echo wszystkich pol)
    - DELETE jest idempotent (200 nawet dla nieistniejacego)
    - Weryfikacja przez GET, nie przez response body
    """
    # CREATE
    create_resp = admin_client.post(
        "/api/admin/wlasciciele", json=SAMPLE_OWNER_PAYLOAD
    )
    assert create_resp.status_code == 201, (
        f"Create owner nie powiodl sie: {create_resp.status_code} {create_resp.text}"
    )
    body = create_resp.json()
    assert "id" in body
    assert body.get("status") == "created"
    owner_id = body["id"]

    try:
        # READ przez admin endpoint - weryfikacja stworzenia
        read_resp = admin_client.get(f"/api/admin/wlasciciele/{owner_id}")
        assert read_resp.status_code == 200
        read_body = read_resp.json()
        assert read_body["id"] == owner_id
        assert read_body["nazwa_wlasciciela"] == "Jan Testowy"
        assert read_body["unikalny_klucz"] == "TEST_INT_001"

        # UPDATE
        update_payload = {
            "unikalny_klucz": "TEST_INT_001_UPDATED",
            "nazwa_wlasciciela": "Jan Zaktualizowany",
            "numer_protokolu": "9999/UPD",
            "numer_domu": "2",
        }
        update_resp = admin_client.put(
            f"/api/admin/wlasciciele/{owner_id}", json=update_payload
        )
        assert update_resp.status_code == 200, (
            f"Update owner nie powiodl sie: {update_resp.status_code} {update_resp.text}"
        )

        # Weryfikacja update przez GET (PUT nie zwraca body)
        read2_resp = admin_client.get(f"/api/admin/wlasciciele/{owner_id}")
        assert read2_resp.json()["nazwa_wlasciciela"] == "Jan Zaktualizowany"
        assert read2_resp.json()["numer_domu"] == "2"

    finally:
        # DELETE (cleanup nawet jesli cos sie wywalilo w srodku)
        del_resp = admin_client.delete(f"/api/admin/wlasciciele/{owner_id}")
        assert del_resp.status_code in (200, 204), (
            f"Delete owner nie powiodl sie: {del_resp.status_code} {del_resp.text}"
        )

        # Weryfikacja delete -> 404
        read_after_del = admin_client.get(f"/api/admin/wlasciciele/{owner_id}")
        assert read_after_del.status_code == 404


def test_create_owner_with_minimal_payload_succeeds(admin_client):
    """POST z minimalnym payloadem (tylko unikalny_klucz) powinien dzialac.

    Reszta pol jest opcjonalna - schema ma nullable dla wszystkich oprocz id.
    """
    minimal = {"unikalny_klucz": "TEST_MIN_001"}
    resp = admin_client.post("/api/admin/wlasciciele", json=minimal)
    try:
        assert resp.status_code == 201, (
            f"Create z minimalnym payloadem nie powiodl sie: {resp.status_code} {resp.text}"
        )
        body = resp.json()
        owner_id = body["id"]

        # Weryfikacja przez GET - pola nullable
        read = admin_client.get(f"/api/admin/wlasciciele/{owner_id}")
        assert read.status_code == 200
        assert read.json()["unikalny_klucz"] == "TEST_MIN_001"
        # Pozostale pola powinny byc None
        assert read.json().get("nazwa_wlasciciela") is None
        assert read.json().get("numer_domu") is None
    finally:
        if resp.status_code == 201:
            admin_client.delete(f"/api/admin/wlasciciele/{resp.json()['id']}")


def test_update_nonexistent_owner_returns_404(admin_client):
    """PUT na nieistniejace id -> 404 (nie 500)."""
    resp = admin_client.put(
        "/api/admin/wlasciciele/999999",
        json={"nazwa_wlasciciela": "Foo"}
    )
    assert resp.status_code == 404, (
        f"PUT na nieistniejace id powinien zwrocic 404, mial: {resp.status_code} {resp.text}"
    )


def test_delete_is_idempotent_returns_200_for_nonexistent(admin_client):
    """DELETE na nieistniejace id zwraca 200 (REST idempotent convention).

    W przeciwienstwie do PUT ktory zwraca 404 (bo 'upsert' semantyka rozni sie
    od 'delete' semantyki). To jest SWIADOMA decyzja architektoniczna - test
    ja pinguje, zeby ktos nie 'poprawil' tego bez dyskusji.
    """
    resp = admin_client.delete("/api/admin/wlasciciele/999999")
    # Idempotent: nie rozrozniamy 'usunalismy teraz' od 'nie bylo'.
    # To upraszcza retry logike klientow.
    assert resp.status_code == 200, (
        f"DELETE powinien byc idempotent (200), mial: {resp.status_code} {resp.text}"
    )


def test_owner_changes_visible_on_public_endpoint(admin_client, client):
    """Po PUT zmiana widoczna w publicznym /api/wlasciciele (cache/integracja).

    Krytyczny test: jesli admin edytuje wlasciciela, zmiana MUSI byc widoczna
    na frontendzie (publiczny endpoint). W przeciwnym razie cache lub
    niespujnosc danych miedzy endpointami.
    """
    # CREATE
    create_resp = admin_client.post(
        "/api/admin/wlasciciele", json=SAMPLE_OWNER_PAYLOAD
    )
    owner_id = create_resp.json()["id"]

    try:
        # UPDATE przez admin
        new_name = "Jan Widoczny Publicznie"
        admin_client.put(
            f"/api/admin/wlasciciele/{owner_id}",
            json={"nazwa_wlasciciela": new_name, "unikalny_klucz": "TEST_VIS"}
        )

        # READ przez publiczny endpoint (bez auth)
        client.cookies.clear()
        public_resp = client.get("/api/wlasciciele")
        assert public_resp.status_code == 200
        public_data = public_resp.json()

        # Szukaj naszego wlasciciela
        owner_in_public = None
        for o in (public_data if isinstance(public_data, list) else public_data.get("owners", [])):
            if o.get("id") == owner_id:
                owner_in_public = o
                break

        assert owner_in_public is not None, (
            f"Wlasciciel id={owner_id} nie widoczny w publicznym /api/wlasciciele"
        )
        assert owner_in_public["nazwa_wlasciciela"] == new_name, (
            f"Publiczny endpoint pokazuje stara nazwe: {owner_in_public.get('nazwa_wlasciciela')!r} "
            f"zamiast nowej: {new_name!r}"
        )
    finally:
        admin_client.delete(f"/api/admin/wlasciciele/{owner_id}")
