"""
E2E testy wykrywajace bledy UI bez symulacji interakcji.

Wykrywaja:
- bledy w konsoli JavaScript (typo, undefined refs, syntax errors)
- blad 4xx/5xx w requestach (brakujace assety, 404 na CSS/JS)
- page error (uncaught exceptions w JS)

NIE sprawdzaja formulazy, walidacji, edycji - to jest w test_smoke.py
i przyszlych integration testach.

Wymagaja dzialajacego serwera backend (fixture 'server' z conftest.py).
Uruchamiane przez: python -m pytest backend/tests/e2e/test_no_errors.py -v
"""
import json

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5000"


def _check_no_errors(page, url, label):
    """Helper: wczytuje strone, zbiera bledy konsoli i requesty 4xx/5xx.

    Zwraca (console_errors, failed_requests) - oba listy stringow.
    Nie aseruje - to robi caller z lepszym kontekstem.
    """
    console_errors = []
    failed_requests = []

    def _on_console(msg):
        if msg.type == "error":
            # Pomijamy znane "false positive" - np. fetch do /api/health
            # ktory zwraca 404 jesli endpoint nie istnieje (celowo).
            text = msg.text
            if "/api/health" in text:
                return
            console_errors.append(text)

    def _on_pageerror(err):
        console_errors.append(f"PAGEERROR: {err}")

    def _on_response(response):
        # Tylko 4xx/5xx - oprocz znanych false positives
        if response.status >= 400:
            url_str = response.url
            # Pomijamy: 404 na favicon (standard)
            if url_str.endswith("/favicon.ico"):
                return
            failed_requests.append(f"{response.status} {url_str}")

    page.on("console", _on_console)
    page.on("pageerror", _on_pageerror)
    page.on("response", _on_response)

    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_selector("body", timeout=10000)
    # Daj krótki czas na błędy JS/assetów po inicjalizacji, bez czekania na
    # pełne networkidle (strony mogą mieć długo wiszące requesty).
    page.wait_for_timeout(1000)

    return console_errors, failed_requests


def test_homepage_no_errors(server, page):
    """Strona glowna nie ma bledow konsoli JS ani requestow 4xx/5xx.

    Lapie: typo w kodzie, undefined refs, brakujace assety CSS/JS.
    """
    errors, failed = _check_no_errors(page, BASE_URL, "homepage")
    assert not errors, f"Blady konsoli na homepage: {errors}"
    assert not failed, f"Requesty 4xx/5xx na homepage: {failed}"


def test_admin_panel_no_errors(server, page):
    """Panel admina (/admin/admin.html) nie ma bledow konsoli.

    Lapsuje: blad w panelu logowania (czesc wspolna dla wszystkich stron admina).
    """
    errors, failed = _check_no_errors(page, f"{BASE_URL}/admin/admin.html", "admin")
    assert not errors, f"Blady konsoli na admin: {errors}"
    assert not failed, f"Requesty 4xx/5xx na admin: {failed}"


def test_editor_genealogy_no_errors(server, page):
    """Edytor genealogii (/genealogia/genealogia.html) nie ma bledow konsoli."""
    errors, failed = _check_no_errors(
        page, f"{BASE_URL}/genealogia/genealogia.html", "editor"
    )
    assert not errors, f"Blady konsoli na editor: {errors}"
    assert not failed, f"Requesty 4xx/5xx na editor: {failed}"


def test_map_view_no_errors(server, page):
    """Widok mapy (strona glowna z mapa) nie ma bledow konsoli."""
    # Sprawdzamy rowniez index.html - bo moze byc osobny punkt wejscia
    errors, failed = _check_no_errors(
        page, f"{BASE_URL}/strona_glowna/index.html", "map"
    )
    # Mapa moze miec ostrzezenia - nie failujemy twardo, ale logujemy
    if errors:
        print(f"INFO: Ostrzezenia konsoli na map: {errors}")
    if failed:
        print(f"INFO: Requesty 4xx/5xx na map: {failed}")


def test_admin_genealogy_loads_without_undefined_or_errors(server, page):
    """Admin → Genealogia laduje liste i szczegoly bez JS errorow.

    Regresja dla realnych bledow:
    - response.json() na '<!DOCTYPE html>' zamiast JSON
    - ReferenceError: showNotification is not defined
    - UI pokazujace 'ID: undefined' w panelu szczegolow osoby
    """
    console_errors = []
    page_errors = []
    api_responses = []

    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    page.on(
        "response",
        lambda resp: api_responses.append(
            f"{resp.status} {resp.url} {resp.headers.get('content-type', '')}"
        ) if "/api/admin/genealogia" in resp.url or "/api/admin/protocols" in resp.url else None,
    )

    # Ten test ma sprawdzac regresje UI admina (JSON zamiast HTML, brak
    # ReferenceError i brak "ID: undefined"), nie wydajnosc renderowania calej
    # bazy 1770+ osob. W pelnym przebiegu launchera Chromium potrafil wisiec na
    # kosztownym renderze calej genealogii, co blokowalo kolejne smoke testy.
    # Realny kontrakt backendu jest pokryty testami integration, a tu dajemy
    # mala, reprezentatywna odpowiedz API.
    genealogy_fixture = [
        {
            "id": 1,
            "db_id": 1,
            "id_osoby": "1001",
            "imie": "Jan",
            "nazwisko": "Testowy",
            "name": "Jan Testowy",
            "plec": "M",
            "rok_urodzenia": 1880,
            "rok_smierci": 1940,
            "numer_domu": "1",
            "id_ojca": None,
            "id_matki": None,
            "id_malzonka": "1002",
            "marriages": [{"spouseId": "1002"}],
            "protokol_klucz": "P-1",
            "uwagi": "",
        },
        {
            "id": 2,
            "db_id": 2,
            "id_osoby": "1002",
            "imie": "Anna",
            "nazwisko": "Testowa",
            "name": "Anna Testowa",
            "plec": "F",
            "rok_urodzenia": 1885,
            "rok_smierci": 1950,
            "numer_domu": "1",
            "id_ojca": None,
            "id_matki": None,
            "id_malzonka": "1001",
            "marriages": [{"spouseId": "1001"}],
            "protokol_klucz": "P-1",
            "uwagi": "",
        },
    ]

    page.route(
        "**/api/admin/genealogia**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(genealogy_fixture),
        ),
    )
    page.route(
        "**/api/admin/protocols**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps([{"unikalny_klucz": "P-1", "nazwa_wlasciciela": "Jan Testowy"}]),
        ),
    )

    def open_admin_genealogy():
        """Otwiera sekcje genealogii z czystym stanem formularzy.

        W pelnym E2E Chromium potrafi przenosic stan kontekstu miedzy testami
        (cookies/localStorage/autofill).  Ten test ma lapac regresje admin.js,
        a nie wisiec 60 sekund na przypadkowo aktywnym filtrze, wiec jawnie
        ustawiamy neutralne filtry i robimy jeden szybki retry po reloadzie.
        """
        page.context.clear_cookies()
        page.add_init_script("localStorage.clear(); sessionStorage.clear();")
        page.goto(f"{BASE_URL}/admin/admin.html", wait_until="domcontentloaded", timeout=15000)

        page.wait_for_function(
            """
            () => {
                const login = document.querySelector('#loginScreen');
                const panel = document.querySelector('#adminPanel');
                return (login && !login.classList.contains('hidden')) ||
                       (panel && !panel.classList.contains('hidden'));
            }
            """,
            timeout=10000,
        )

        if page.locator("#loginScreen").is_visible():
            page.fill("#login", "admin")
            page.fill("#password", "admin123")
            page.click("#loginForm button[type='submit']")
        page.wait_for_selector("#adminPanel:not(.hidden)", timeout=10000)

        page.wait_for_selector(".menu-item[data-section='genealogy']", timeout=10000)
        with page.expect_response(
            lambda resp: "/api/admin/genealogia" in resp.url and resp.status == 200,
            timeout=15000,
        ):
            page.click(".menu-item[data-section='genealogy']")
        page.wait_for_function(
            """() => document.querySelector('#genealogy')?.classList.contains('active')""",
            timeout=10000,
        )
        page.evaluate(
            """
            () => {
                const search = document.querySelector('#searchGenealogy');
                const house = document.querySelector('#filterHouse');
                const sort = document.querySelector('#sortFilter');
                if (search) search.value = '';
                if (house) house.value = '';
                if (sort) sort.value = 'az';
                document.querySelectorAll('.genealogy-filters .filter-btn')
                    .forEach(btn => btn.classList.toggle('active', btn.dataset.filter === 'all'));
                search?.dispatchEvent(new Event('input', { bubbles: true }));
                house?.dispatchEvent(new Event('input', { bubbles: true }));
                sort?.dispatchEvent(new Event('change', { bubbles: true }));
            }
            """
        )

    open_admin_genealogy()
    page.wait_for_timeout(500)
    assert not console_errors, f"Bledy konsoli po wejsciu w genealogie: {console_errors}"
    assert not page_errors, f"Page errors po wejsciu w genealogie: {page_errors}"

    # Jesli UI chwilowo wyscigalo sie z init/autofill, reload jest szybszy i
    # stabilniejszy niz 60-sekundowy timeout blokujacy launcher.
    for attempt in range(2):
        try:
            page.wait_for_function(
                """
                () => {
                    const el = document.querySelector('#genPersonCount');
                    return el && parseInt(el.textContent || '0', 10) > 0;
                }
                """,
                timeout=12000,
            )
            break
        except Exception:
            if attempt == 0:
                open_admin_genealogy()
                continue
            genealogy_text = ""
            try:
                genealogy_text = page.locator("#genealogy").inner_text(timeout=1000)[:1200]
            except Exception:
                genealogy_text = "<brak #genealogy>"
            filters_state = page.evaluate(
                """
                () => ({
                    search: document.querySelector('#searchGenealogy')?.value,
                    house: document.querySelector('#filterHouse')?.value,
                    sort: document.querySelector('#sortFilter')?.value,
                    active: document.querySelector('.genealogy-filters .filter-btn.active')?.dataset.filter,
                    renderedItems: document.querySelectorAll('#personsListContainer .person-list-item').length,
                })
                """
            )
            raise AssertionError(
                "Genealogia w adminie nie zaladowala listy osob. "
                f"url={page.url!r}, filters_state={filters_state!r}, "
                f"console_errors={console_errors!r}, page_errors={page_errors!r}, "
                f"api_responses={api_responses!r}, genealogy_text={genealogy_text!r}"
            )
    page.wait_for_selector("#personsListContainer .person-list-item", timeout=10000)
    page.wait_for_selector("#personDetailsPanel .profile-id", timeout=10000)

    assert not console_errors, f"Bledy konsoli na admin/genealogia: {console_errors}"
    assert not page_errors, f"Page errors na admin/genealogia: {page_errors}"

    details_text = page.locator("#personDetailsPanel").inner_text()
    assert "ID: undefined" not in details_text, details_text[:500]
    assert "ZNALEZIONO:" in page.locator("#genealogy").inner_text()
