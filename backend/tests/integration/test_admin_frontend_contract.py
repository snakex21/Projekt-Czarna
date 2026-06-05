"""
Kontrakt static/admin/admin.js ↔ backend.

Ten test istnieje po realnym bugu:
admin.js wywolywal /api/admin/dashboard-stats, a backend zwracal 200 text/html
z <!DOCTYPE html> (fallback statyczny), wiec response.json() crashowalo.

Regula: endpointy z const API w admin.js nie moga zwracac HTML fallbacku.

Od Etapu 1 refaktoryzacji (TODO 2.5) mapa API zyje w static/admin/js/api.js
jako ``window.AdminAPI`` (Object.freeze). admin.js trzyma tylko cienki alias
``const API = window.AdminAPI;`` — test czyta zrodlo prawdy z nowego pliku,
z fallbackiem do admin.js dla kompatybilnosci wstecznej.
"""
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_ROUTER_PY = PROJECT_ROOT / "backend" / "routers" / "admin.py"
ADMIN_OBJECTS_SERVICE_PY = PROJECT_ROOT / "backend" / "services" / "admin_objects_service.py"
ADMIN_API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"
ADMIN_DIAGNOSTICS_JS = PROJECT_ROOT / "static" / "admin" / "js" / "diagnostics.js"
ADMIN_NOTIFICATIONS_JS = PROJECT_ROOT / "static" / "admin" / "js" / "notifications.js"
ADMIN_OBJECTS_JS = PROJECT_ROOT / "static" / "admin" / "js" / "objects.js"
ADMIN_UTILS_JS = PROJECT_ROOT / "static" / "admin" / "js" / "utils.js"
ADMIN_GENEALOGY_LIST_JS = PROJECT_ROOT / "static" / "admin" / "js" / "genealogy-list.js"
ADMIN_AUTH_JS = PROJECT_ROOT / "static" / "admin" / "js" / "auth.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"


def _extract_admin_api_map():
    """Zwraca mape endpointow z nowego modulu js/api.js.

    Fallback: jezeli nowy plik nie istnieje, czyta stary admin.js.
    """
    if ADMIN_API_JS.exists():
        source = ADMIN_API_JS.read_text(encoding="utf-8")
        match = re.search(
            r"window\.AdminAPI\s*=\s*(?:Object\.freeze\()?\s*\{(?P<body>.*?)\}\s*\)?\s*;",
            source,
            re.S,
        )
        if match:
            return dict(re.findall(r"(\w+)\s*:\s*['\"]([^'\"]+)['\"]", match.group("body")))

    # Fallback do starego const API = {...} w admin.js
    source = ADMIN_JS.read_text(encoding="utf-8")
    match = re.search(r"const\s+API\s*=\s*\{(?P<body>.*?)\};", source, re.S)
    if match:
        return dict(re.findall(r"(\w+)\s*:\s*['\"]([^'\"]+)['\"]", match.group("body")))

    raise AssertionError(
        "Nie znaleziono mapy API ani w static/admin/js/api.js ani w static/admin/admin.js"
    )


def _assert_not_html_fallback(response, url):
    content_type = response.headers.get("content-type", "")
    body_start = response.text[:80].lstrip().lower()
    assert not (
        "text/html" in content_type or body_start.startswith("<!doctype")
    ), (
        f"Endpoint z admin.js zwrocil HTML fallback zamiast JSON/API response: {url}. "
        f"status={response.status_code}, content-type={content_type}, body={response.text[:120]!r}"
    )


def test_admin_js_api_endpoints_do_not_return_html_fallback(admin_client):
    """Kazdy endpoint z API mapy admin.js zwraca JSON/plik, nigdy index.html.

    To lapie dokladnie blad: response.json() na '<!DOCTYPE html>'.
    """
    api = _extract_admin_api_map()

    # Method-aware kontrakt. Dla login/logout uzywamy POST, reszta GET.
    requests = {
        "login": lambda url: admin_client.post(
            url, json={"username": "admin", "password": "wrong-password"}
        ),
        "logout": lambda url: admin_client.post(url),
    }

    for name, url in api.items():
        request = requests.get(name, lambda u: admin_client.get(u))
        response = request(url)
        _assert_not_html_fallback(response, url)
        # Nie kazdy endpoint musi zwracac 200 (np. login z blednym haslem -> 401),
        # ale musi byc realnym API response, nie statycznym HTML.
        assert response.status_code < 500, (
            f"Endpoint admin.js {name}={url} zwrocil server error: "
            f"{response.status_code} {response.text[:120]!r}"
        )


def test_admin_js_api_read_endpoints_return_json(admin_client):
    """GET endpointy z admin.js zwracaja application/json.

    export-backup jest wyjatkiem: tez JSON, ale z Content-Disposition attachment.
    """
    api = _extract_admin_api_map()
    get_endpoint_names = [
        "stats", "owners", "objects", "allObjects", "demography",
        "genealogy", "protocols", "backup", "authStatus",
    ]
    for name in get_endpoint_names:
        url = api[name]
        response = admin_client.get(url)
        _assert_not_html_fallback(response, url)
        assert "application/json" in response.headers.get("content-type", ""), (
            f"{name}={url} powinien zwracac JSON, dostal: "
            f"{response.status_code} {response.headers.get('content-type')}"
        )


def test_admin_js_show_notification_is_defined():
    """showNotification uzywane przy ladowaniu genealogii musi byc zdefiniowane.

    Regresja dla: ReferenceError: showNotification is not defined.
    Od Etapu 1 zyje w js/notifications.js (window.AdminNotifications.showNotification).
    Od P2.5 Etapu 10 wywolanie jest w js/genealogy-list.js.
    """
    source = ADMIN_JS.read_text(encoding="utf-8")
    genealogy_list_source = (
        ADMIN_GENEALOGY_LIST_JS.read_text(encoding="utf-8")
        if ADMIN_GENEALOGY_LIST_JS.exists()
        else ""
    )
    assert "showNotification(" in source or "showNotification(" in genealogy_list_source, (
        "Test bezprzedmiotowy: brak wywolania showNotification"
    )
    notifications_source = (
        ADMIN_NOTIFICATIONS_JS.read_text(encoding="utf-8")
        if ADMIN_NOTIFICATIONS_JS.exists()
        else ""
    )
    defined_in_module = (
        "function showNotification" in notifications_source
        or "showNotification:" in notifications_source
        or "showNotification =" in notifications_source
    )
    defined_in_admin = (
        "const showNotification" in source or "function showNotification" in source
    )
    assert defined_in_module or defined_in_admin, (
        "admin.js wywoluje showNotification, ale nie definiuje tej funkcji "
        "(ani w admin.js, ani w js/notifications.js)"
    )


# ─── Moduły Etapu 1 (Priorytet 2.5) ─────────────────────────────────────────


def test_admin_api_module_registers_window_admin_api():
    """Etap 1: api.js publikuje window.AdminAPI jako Object.freeze."""
    assert ADMIN_API_JS.exists(), "Brak pliku static/admin/js/api.js"
    source = ADMIN_API_JS.read_text(encoding="utf-8")
    assert "window.AdminAPI" in source
    assert "Object.freeze" in source, (
        "AdminAPI powinno byc zabezpieczone przed mutacja (Object.freeze)"
    )
    # Sanity: kazdy klucz z etapu 0 jest obecny
    api = _extract_admin_api_map()
    expected = {
        "login", "logout", "stats", "owners", "objects", "allObjects",
        "demography", "genealogy", "protocols", "backup", "authStatus",
    }
    missing = expected - set(api.keys())
    assert not missing, f"Brak kluczy w AdminAPI: {missing}"


def test_admin_utils_module_registers_helpers():
    """Etap 1: utils.js publikuje window.AdminUtils z escapeHtml + canonicalSurname."""
    assert ADMIN_UTILS_JS.exists(), "Brak pliku static/admin/js/utils.js"
    source = ADMIN_UTILS_JS.read_text(encoding="utf-8")
    assert "window.AdminUtils" in source
    assert "function escapeHtml" in source
    assert "function canonicalSurname" in source
    assert "escapeHtml:" in source
    assert "canonicalSurname:" in source


def test_admin_notifications_module_registers_toast_helpers():
    """Etap 1: notifications.js publikuje showToast + showNotification (alias)."""
    assert ADMIN_NOTIFICATIONS_JS.exists(), "Brak pliku static/admin/js/notifications.js"
    source = ADMIN_NOTIFICATIONS_JS.read_text(encoding="utf-8")
    assert "window.AdminNotifications" in source
    assert "function showToast" in source
    assert "function showNotification" in source, (
        "Brak aliasu showNotification (message, type) dla kompatybilnosci"
    )
    # showNotification musi delegowac do showToast
    assert "showToast(" in source


def test_admin_auth_module_registers_window_admin_auth():
    """Etap 12: auth.js publikuje window.AdminAuth."""
    assert ADMIN_AUTH_JS.exists(), "Brak pliku static/admin/js/auth.js"
    source = ADMIN_AUTH_JS.read_text(encoding="utf-8")
    assert "window.AdminAuth" in source
    assert "Object.freeze" in source
    for token in ("init", "checkAuth", "login", "logout"):
        assert token in source


def test_admin_html_loads_modules_before_admin_js():
    """admin.html musi ladowac api.js, utils.js, notifications.js PRZED admin.js.

    Kolejnosc ma znaczenie — admin.js rzuca Error jesli moduly nie sa gotowe.
    """
    assert ADMIN_HTML.exists()
    source = ADMIN_HTML.read_text(encoding="utf-8")

    pos_api = source.find('src="js/api.js"')
    pos_utils = source.find('src="js/utils.js"')
    pos_notif = source.find('src="js/notifications.js"')
    pos_auth = source.find('src="js/auth.js"')
    pos_admin = source.find('src="admin.js"')

    assert pos_api != -1, "admin.html nie laduje js/api.js"
    assert pos_utils != -1, "admin.html nie laduje js/utils.js"
    assert pos_notif != -1, "admin.html nie laduje js/notifications.js"
    assert pos_auth != -1, "admin.html nie laduje js/auth.js"
    assert pos_admin != -1, "admin.html nie laduje admin.js"
    assert pos_api < pos_admin, "js/api.js musi byc PRZED admin.js"
    assert pos_utils < pos_admin, "js/utils.js musi byc PRZED admin.js"
    assert pos_notif < pos_admin, "js/notifications.js musi byc PRZED admin.js"
    assert pos_api < pos_auth, "js/api.js musi byc PRZED js/auth.js"
    assert pos_notif < pos_auth, "js/notifications.js musi byc PRZED js/auth.js"
    assert pos_auth < pos_admin, "js/auth.js musi byc PRZED admin.js"


def test_admin_js_uses_module_aliases():
    """admin.js korzysta z modolow przez aliasy — nie definiuje API/utils/notifications lokalnie."""
    source = ADMIN_JS.read_text(encoding="utf-8")
    # Map API przeniesiona do js/api.js
    assert "const API = window.AdminAPI" in source, (
        "admin.js powinien uzywac `const API = window.AdminAPI;` zamiast lokalnej mapy"
    )
    # Stara in-place definicja mapy nie powinna juz istniec
    assert "login: '/api/admin/login'" not in source, (
        "Mapa login:/api/admin/login nie powinna juz byc definiowana w admin.js"
    )
    # canonicalSurname dostarczany przez modul
    assert "function canonicalSurname" not in source, (
        "admin.js nie powinien definiowac wlasnej canonicalSurname — uzywa z AdminUtils"
    )
    # showToast dostarczany przez modul
    assert "const showToast = (type, message)" not in source
    # showNotification dostarczany przez modul
    assert "const showNotification = (message, type" not in source


def test_admin_genealogy_payload_has_fields_used_by_frontend(admin_client):
    """GET /api/admin/genealogia zwraca pola wymagane przez widok genealogii.

    Regresja dla UI: "ID: undefined" w panelu osoby. admin.js uzywa:
    id_osoby, db_id, imie, nazwisko, name, rok_urodzenia, rok_smierci,
    id_ojca, id_matki, protokol_klucz.
    """
    response = admin_client.get("/api/admin/genealogia")
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    assert rows, "Testowa baza powinna miec osoby_genealogia"

    required = {
        "id_osoby", "db_id", "imie", "nazwisko", "name",
        "rok_urodzenia", "rok_smierci", "id_ojca", "id_matki", "protokol_klucz",
    }
    missing = required - set(rows[0].keys())
    assert not missing, f"/api/admin/genealogia brakuje pol dla admin.js: {missing}"

    # Kluczowy regression assert: UI nie moze renderowac 'ID: undefined'.
    assert all(row.get("id_osoby") not in (None, "") for row in rows[:50]), (
        "Pierwsze rekordy genealogii maja puste id_osoby - UI pokaze 'ID: undefined'"
    )


def test_admin_objects_payload_has_assignment_status_and_protocol_links(admin_client):
    """GET /api/admin/obiekty zwraca status przypisania uzywany przez admin.js.

    Regresja dla tabeli obiektow: UI pokazywalo niejasne "Wolny" mimo istnienia
    powiazan dzialka-wlasciciel. Backend ma zwracac assigned_owners z linkiem do
    protokolu, a frontend moze renderowac np. "Protokol 1 - Adam Kowalski".
    """
    response = admin_client.get("/api/admin/obiekty")
    assert response.status_code == 200
    rows = response.json()
    assert rows, "Testowa baza powinna miec obiekty_geograficzne"

    required = {"is_linked", "status", "assigned_count", "assigned_owners"}
    missing = required - set(rows[0].keys())
    assert not missing, f"/api/admin/obiekty brakuje pol statusu: {missing}"

    assigned = next((row for row in rows if row.get("assigned_owners")), None)
    assert assigned is not None, "Testowa baza powinna miec co najmniej jeden przypisany obiekt"
    assert assigned["is_linked"] is True
    assert assigned["status"] == "Przypisany"
    assert assigned["assigned_count"] == len(assigned["assigned_owners"])

    owner = assigned["assigned_owners"][0]
    owner_required = {
        "id", "owner_id", "unikalny_klucz", "name", "nazwa_wlasciciela",
        "protocol_number", "numer_protokolu", "typ_posiadania", "protocol_url",
    }
    owner_missing = owner_required - set(owner.keys())
    assert not owner_missing, f"assigned_owners brakuje pol: {owner_missing}"
    assert owner["name"], "Link statusu powinien miec nazwe wlasciciela/protokolu"
    assert owner["protocol_url"].startswith("../wlasciciele/protokol.html?ownerId=")


def test_admin_objects_listing_logic_is_in_service_layer():
    """Router admina deleguje listę obiektów do service layer.

    To utrzymuje zasadę projektu: router = cienkie I/O, SQL i agregacja w service.
    """
    router_source = ADMIN_ROUTER_PY.read_text(encoding="utf-8")
    service_source = ADMIN_OBJECTS_SERVICE_PY.read_text(encoding="utf-8")

    assert "from ..services import admin_objects_service" in router_source
    assert "admin_objects_service.list_objects_with_owner_links" in router_source
    assert "async def _list_obiekty_with_owner_links" not in router_source
    assert "async def list_objects_with_owner_links" in service_source
    assert "FROM obiekty_geograficzne" in service_source
    assert "assigned_owners" in service_source


def test_objects_module_renders_object_assignment_instead_of_wolny_label():
    """objects.js (P2.5 Etap 2) renderuje Nieprzypisany albo link do protokolu.

    Po wydzieleniu sekcji obiektów z admin.js do js/objects.js (P2.5 Etap 2)
    funkcja renderowania statusu zostala przeniesiona - test musi czytac
    z nowego pliku.
    """
    assert ADMIN_OBJECTS_JS.exists(), "Brak pliku static/admin/js/objects.js"
    source = ADMIN_OBJECTS_JS.read_text(encoding="utf-8")
    assert "assigned_owners" in source, "objects.js nie renderuje assigned_owners"
    assert "protocol_url" in source, "objects.js nie uzywa protocol_url (link do protokolu)"
    assert "Nieprzypisany" in source, "objects.js nie renderuje labelu 'Nieprzypisany'"


# ============================================================================
# Priorytet 4: moduł diagnostics + endpoint /api/admin/diagnostics
# ============================================================================


def test_diagnostics_module_registers_window_admin_diagnostics():
    """js/diagnostics.js publikuje ``window.AdminDiagnostics`` jako Object.freeze."""
    assert ADMIN_DIAGNOSTICS_JS.exists(), "Brak pliku static/admin/js/diagnostics.js"
    source = ADMIN_DIAGNOSTICS_JS.read_text(encoding="utf-8")
    assert "window.AdminDiagnostics" in source
    assert "Object.freeze" in source, (
        "AdminDiagnostics powinno byc zabezpieczone przed mutacja (Object.freeze)"
    )


def test_diagnostics_module_exposes_load_render_refresh():
    """Moduł udostępnia load/render/refresh jako publiczne API."""
    source = ADMIN_DIAGNOSTICS_JS.read_text(encoding="utf-8")
    for fn in ("load", "render", "refresh", "formatCount"):
        assert f"{fn}:" in source or f"function {fn}" in source, (
            f"AdminDiagnostics.{fn} powinno byc dostepne"
        )


def test_diagnostics_module_uses_admin_api_endpoint():
    """Moduł czyta URL z AdminAPI (nie hardkoduje ``/api/admin/diagnostics``)."""
    source = ADMIN_DIAGNOSTICS_JS.read_text(encoding="utf-8")
    assert "AdminAPI.diagnostics" in source, (
        "Moduł powinien korzystać z AdminAPI.diagnostics (nie hardcoded URL)"
    )


def test_diagnostics_module_uses_admin_utils_escapehtml():
    """Moduł używa AdminUtils.escapeHtml (z fallbackiem gdy brak)."""
    source = ADMIN_DIAGNOSTICS_JS.read_text(encoding="utf-8")
    assert "AdminUtils" in source
    assert "escapeHtml" in source


def test_admin_html_loads_diagnostics_module():
    """admin.html ładuje js/diagnostics.js PRZED admin.js."""
    assert ADMIN_HTML.exists()
    source = ADMIN_HTML.read_text(encoding="utf-8")
    pos_diag = source.find('src="js/diagnostics.js"')
    pos_admin = source.find('src="admin.js"')
    assert pos_diag != -1, "admin.html nie laduje js/diagnostics.js"
    assert pos_admin != -1, "admin.html nie laduje admin.js"
    assert pos_diag < pos_admin, "js/diagnostics.js musi byc PRZED admin.js"


def test_admin_html_has_diagnostics_section_in_sidebar():
    """Sidebar ma pozycję ``data-section="diagnostics"``."""
    source = ADMIN_HTML.read_text(encoding="utf-8")
    assert 'data-section="diagnostics"' in source, (
        "Sidebar musi miec pozycję data-section=diagnostics"
    )


def test_admin_html_has_diagnostics_section_block():
    """Treść ma sekcję ``<section id="diagnostics" class="section">``."""
    source = ADMIN_HTML.read_text(encoding="utf-8")
    assert 'id="diagnostics" class="section"' in source, (
        "Brak sekcji <section id=diagnostics>"
    )
    assert 'id="diagnosticsContent"' in source, (
        "Sekcja musi miec kontener #diagnosticsContent"
    )


def test_admin_api_map_has_diagnostics_endpoint():
    """api.js ma klucz ``diagnostics: '/api/admin/diagnostics'``."""
    api = _extract_admin_api_map()
    assert "diagnostics" in api, "AdminAPI.diagnostics brakuje w api.js"
    assert api["diagnostics"] == "/api/admin/diagnostics", (
        f"Endpoint diagnostics={api['diagnostics']!r}, "
        "oczekiwano '/api/admin/diagnostics'"
    )


def test_admin_js_loads_diagnostics_section():
    """admin.js ma case 'diagnostics' w loadSectionData i nazwę w getSectionName."""
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "case 'diagnostics'" in source, (
        "admin.js powinien obsługiwać case 'diagnostics' w loadSectionData"
    )
    assert "diagnostics:" in source, (
        "admin.js powinien mieć diagnostics w getSectionName"
    )
    assert "AdminDiagnostics.refresh" in source, (
        "admin.js powinien wywoływać AdminDiagnostics.refresh"
    )


def test_admin_js_binds_refresh_diagnostics_button():
    """admin.js podpina event listener na #refreshDiagnosticsBtn."""
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "refreshDiagnosticsBtn" in source, (
        "admin.js powinien podpinac event na #refreshDiagnosticsBtn"
    )
    assert ">Wolny<" not in source and "Wolny</span>" not in source


# ============================================================================
# Priorytet 4.1: kosmetyka panelu diagnostyki - puste karty
# ============================================================================
# Metryki ``parcel_owner_links`` (counter) i ``incomplete_records`` (agregat)
# mają puste ``sample: []``. Stara implementacja zostawiała pustą przestrzeń
# pod liczbą. Nowa: jeśli brak sampla, wyświetl jednolinijkowy opis.


def test_diagnostics_module_handles_empty_sample_with_placeholder():
    """``render`` wyświetla placeholder gdy ``sample.length === 0``.

    Licznik ``count`` nadal widoczny - tylko pusty obszar pod spodem
    jest zastępowany opisem typu 'sumaryczna liczba...'.
    """
    source = ADMIN_DIAGNOSTICS_JS.read_text(encoding="utf-8")
    # Musi istnieć ścieżka kodu dla pustego sampla
    assert "sample.length" in source, (
        "render() musi sprawdzac sample.length"
    )
    # Musi być placeholder class (np. metric-empty)
    assert "metric-empty" in source or "metric-empty-sample" in source or "empty-sample" in source, (
        "render() musi renderowac placeholder dla pustego sampla (np. .metric-empty)"
    )


def test_diagnostics_module_empty_sample_placeholder_has_text():
    """Placeholder dla pustego sampla ma polski tekst (nie jest pusty)."""
    source = ADMIN_DIAGNOSTICS_JS.read_text(encoding="utf-8")
    # Wymagamy polskiego opisu w kodzie render()
    # Akceptowalne: "agregat", "łączna", "sumaryczn", "kompletn", "powiąza"
    placeholders = ["agregat", "łączna", "sumaryczn", "kompletn", "powiąza", "rekordy"]
    found = any(word in source.lower() for word in placeholders)
    assert found, (
        f"render() powinien zawierac polski opis pustej karty. Szukam jednego z: {placeholders}"
    )


def test_diagnostics_module_handles_count_zero_with_placeholder():
    """Gdy ``count === 0`` i ``sample.length === 0`` → pozytywny komunikat."""
    source = ADMIN_DIAGNOSTICS_JS.read_text(encoding="utf-8")
    # Sprawdzamy że jest ścieżka dla count === 0
    # (render powinien rozróżniać count === 0 od count > 0)
    assert "count === 0" in source or "count == 0" in source or "value.count" in source, (
        "render() musi rozróżniac count === 0 od count > 0"
    )


def test_diagnostics_module_keeps_metric_card_for_counter_types():
    """``render`` zachowuje ``.metric-card`` dla metryk typu counter/aggregate.

    Nie chcemy usunąć karty - chcemy tylko wypełnić puste miejsce placeholderem.
    """
    source = ADMIN_DIAGNOSTICS_JS.read_text(encoding="utf-8")
    assert "metric-card" in source, (
        "render() nadal powinien renderowac .metric-card (karty nie sa usuwane)"
    )
    # Sprawdzamy też że sampleHtml jest warunkowy (nie pusty string dla wszystkich)
    assert "${sampleHtml}" in source or "{sampleHtml}" in source, (
        "sampleHtml musi byc interpolowany w template (nie zawsze pusty)"
    )
