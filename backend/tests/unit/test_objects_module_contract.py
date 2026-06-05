"""
Kontrakt UI modułu `static/admin/js/objects.js` (P2.5 Etap 2).

Weryfikuje strukturę kodu źródłowego modułu JS bez uruchamiania przeglądarki
(wzorzec projektu - testy UI to testy kontraktu regex/AST).

Co jest testowane:
- Moduł rejestruje `window.AdminObjects` jako `Object.freeze({...})`.
- Publiczne API: `load`, `filter`, `edit`, `save`, `remove`.
- Moduł NIE importuje innych modułów UI (izolowany).
- Moduł NIE ma top-level kodu który tworzy DOM (tylko definicje).
- Moduł współpracuje z `window.AdminAPI` (endpoint `objects`).
- Moduł używa `window.AdminUtils.escapeHtml` (sanityzacja).
- Moduł używa `window.AdminNotifications.showToast` (komunikaty).
- Moduł zachowuje kategorie: `areaCategories` + `pointCategories`.
- `admin.html` ładuje `objects.js` w odpowiedniej kolejności (po utils/notifications/diagnostics, przed admin.js).
- `admin.js` NIE zawiera już sekcji obiektów (loadObjects, renderObjects, filterObjects,
  editObject, saveObject, deleteObject) - to anti-regresja po wydzieleniu.
- Brak wycieków: stare wywołania `loadObjects()`/`filterObjects()`/`editObject()` z
  admin.js są zastąpione przez `AdminObjects.load()` itd.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OBJECTS_JS = PROJECT_ROOT / "static" / "admin" / "js" / "objects.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"


# ============================================================================
# Helpery
# ============================================================================


def _objects_source() -> str:
    if not OBJECTS_JS.exists():
        pytest.fail(f"Brak pliku {OBJECTS_JS} - moduł nie został wydzielony")
    return OBJECTS_JS.read_text(encoding="utf-8")


def _objects_source_no_comments() -> str:
    """Źródło objects.js z usuniętymi komentarzami (/* */ i //)."""
    import re as _re
    source = _objects_source()
    # Usuń komentarze blokowe /* ... */
    source = _re.sub(r"/\*[\s\S]*?\*/", "", source)
    # Usuń komentarze liniowe //
    source = _re.sub(r"//[^\n]*", "", source)
    return source


def _admin_source() -> str:
    return ADMIN_JS.read_text(encoding="utf-8")


def _admin_html() -> str:
    return ADMIN_HTML.read_text(encoding="utf-8")


# ============================================================================
# Rejestracja modułu
# ============================================================================


def test_objects_module_registers_window_namespace():
    """Moduł musi eksportować `window.AdminObjects`."""
    source = _objects_source()
    assert "window.AdminObjects" in source, (
        "Brak eksportu window.AdminObjects w objects.js"
    )


def test_objects_module_uses_object_freeze():
    """Moduł używa `Object.freeze({...})` - wzorzec projektu (niemutowalny API)."""
    source = _objects_source()
    assert "Object.freeze" in source, (
        "Brak Object.freeze w objects.js (wymagany wzorzec projektu)"
    )


def test_objects_module_uses_iife_pattern():
    """Moduł zamknięty w IIFE: `(function () { ... })();` - wzorzec projektu."""
    source = _objects_source()
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source), (
        "Brak IIFE wrapper w objects.js (wymagany wzorzec projektu)"
    )
    assert "'use strict'" in source, (
        "Brak 'use strict' w objects.js (wymagane przez wzorzec)"
    )


# ============================================================================
# Publiczne API
# ============================================================================


def test_objects_module_exposes_load_function():
    """`load` - pobiera obiekty z API i renderuje tabelę."""
    source = _objects_source()
    assert re.search(r"load\s*:\s*loadObjects", source), (
        "Brak `load: loadObjects` w publicznym API"
    )


def test_objects_module_exposes_filter_function():
    """`filter` - filtruje obiekty po nazwie/kategorii/właścicielu."""
    source = _objects_source()
    assert re.search(r"filter\s*:\s*filterObjects", source), (
        "Brak `filter: filterObjects` w publicznym API"
    )


def test_objects_module_exposes_edit_function():
    """`edit` - tryb edycji wiersza (zamienia komórki na input/select)."""
    source = _objects_source()
    assert re.search(r"edit\s*:\s*editObject", source), (
        "Brak `edit: editObject` w publicznym API"
    )


def test_objects_module_exposes_save_function():
    """`save` - PUT na API z nową nazwą/kategorią."""
    source = _objects_source()
    assert re.search(r"save\s*:\s*saveObject", source), (
        "Brak `save: saveObject` w publicznym API"
    )


def test_objects_module_exposes_remove_function():
    """`remove` - DELETE na API."""
    source = _objects_source()
    assert re.search(r"remove\s*:\s*deleteObject", source), (
        "Brak `remove: deleteObject` w publicznym API (alias dla delete)"
    )


def test_objects_module_has_exactly_five_public_methods():
    """Publiczne API = load, filter, edit, save, remove (5 metod)."""
    source = _objects_source()
    # Wyciagnij blok `Object.freeze({ ... })`
    match = re.search(r"Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)", source)
    assert match, "Brak bloku Object.freeze w objects.js"
    block = match.group(1)
    # Policz klucze (linie typu `name: functionName,`)
    keys = re.findall(r"(\w+)\s*:\s*\w+", block)
    assert set(keys) == {"load", "filter", "edit", "save", "remove"}, (
        f"Publiczne API ma niespodziewane klucze: {set(keys)}"
    )


# ============================================================================
# Zależności (współpraca z innymi modułami)
# ============================================================================


def test_objects_module_uses_admin_api():
    """Moduł korzysta z `window.AdminAPI.objects` (URL endpointu)."""
    source = _objects_source()
    assert "window.AdminAPI" in source or "AdminAPI.objects" in source, (
        "Brak użycia window.AdminAPI w objects.js (endpointy)"
    )
    assert "API.objects" in source, (
        "Moduł nie korzysta z API.objects - fetch URL nie jest z AdminAPI"
    )


def test_objects_module_uses_admin_utils_escapehtml():
    """Moduł korzysta z `window.AdminUtils.escapeHtml` (sanityzacja)."""
    source = _objects_source()
    assert "escapeHtml" in source, (
        "Brak użycia escapeHtml w objects.js (wymagana sanityzacja danych)"
    )
    # Preferowane: pobranie z AdminUtils (nie redefiniowanie)
    assert re.search(r"window\.AdminUtils", source), (
        "Moduł nie pobiera helperów z window.AdminUtils (izolacja)"
    )


def test_objects_module_uses_admin_notifications():
    """Moduł korzysta z `window.AdminNotifications.showToast` (komunikaty)."""
    source = _objects_source()
    assert "showToast" in source, (
        "Brak użycia showToast w objects.js (komunikaty błędów/sukcesu)"
    )
    assert re.search(r"window\.AdminNotifications", source), (
        "Moduł nie pobiera helperów z window.AdminNotifications (izolacja)"
    )


# ============================================================================
# Kategorie (prywatne dane modułu)
# ============================================================================


def test_objects_module_has_area_categories():
    """`areaCategories` - długie kategorie (rolna, budowlana, ...)."""
    source = _objects_source()
    assert "areaCategories" in source, (
        "Brak areaCategories w objects.js (kategorie działek)"
    )
    # Sprawdź że zawiera kluczowe kategorie
    assert "'rolna'" in source, "Brak 'rolna' w areaCategories"
    assert "'budowlana'" in source, "Brak 'budowlana' w areaCategories"


def test_objects_module_has_point_categories():
    """`pointCategories` - krótkie kategorie (budynek, kapliczka, obiekt_specjalny)."""
    source = _objects_source()
    assert "pointCategories" in source, (
        "Brak pointCategories w objects.js (kategorie punktów)"
    )
    assert "'budynek'" in source, "Brak 'budynek' w pointCategories"
    assert "'kapliczka'" in source, "Brak 'kapliczka' w pointCategories"
    assert "'obiekt_specjalny'" in source, "Brak 'obiekt_specjalny' w pointCategories"


def test_objects_module_categories_kept_in_sync():
    """area + point = kategoryzacja obiektów (spójność)."""
    source = _objects_source()
    # Edycja musi rozróżniać area od point (kluczowe dla UX)
    assert "pointCategories.includes" in source or "pointCategories.indexOf" in source, (
        "editObject nie sprawdza pointCategories - logika podziału area/point"
    )


# ============================================================================
# Izolacja modułu
# ============================================================================


def test_objects_module_isolated_from_other_ui():
    """Moduł NIE importuje innych modułów UI (self-contained).

    Sprawdzamy tylko AKTYWNY kod (bez komentarzy) - w nagłówku modułu
    dokumentowana jest kolejność ładowania i nazwy innych plików.
    """
    source = _objects_source_no_comments()
    forbidden_imports = [
        "diagnostics.js",
        "notifications.js",
        "utils.js",
        "api.js",
        "admin.js",
        "genealogia_admin.js",
    ]
    for forbidden in forbidden_imports:
        assert forbidden not in source, (
            f"objects.js importuje {forbidden} - moduł nie powinien importować innych UI"
        )


def test_objects_module_no_top_level_side_effects():
    """Moduł nie wykonuje fetch/DOM przy imporcie (czysta definicja)."""
    source = _objects_source()
    # Brak fetch poza funkcjami
    # Szukamy fetch na top-level (nie w ciele funkcji - uproszczone sprawdzenie)
    lines = [l for l in source.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        stripped = line.strip()
        # fetch powinien być wcięty (wewnątrz funkcji)
        if "fetch(" in stripped and not stripped.startswith("//"):
            # Sprawdź wcięcie: fetch w funkcji ma 4+ spacji
            indent = len(line) - len(line.lstrip())
            assert indent >= 4, (
                f"Linia {i+1}: fetch() na top-level (indent={indent}): {stripped}"
            )


# ============================================================================
# Anti-regresja: admin.js NIE zawiera już sekcji obiektów
# ============================================================================


def test_admin_js_no_longer_contains_load_objects():
    """`loadObjects` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "const loadObjects" not in source, (
        "admin.js nadal zawiera `const loadObjects` - nie został wydzielony"
    )


def test_admin_js_no_longer_contains_render_objects():
    """`renderObjects` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "const renderObjects" not in source, (
        "admin.js nadal zawiera `const renderObjects` - nie został wydzielony"
    )


def test_admin_js_no_longer_contains_filter_objects():
    """`filterObjects` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "const filterObjects" not in source, (
        "admin.js nadal zawiera `const filterObjects` - nie został wydzielony"
    )


def test_admin_js_no_longer_contains_edit_save_delete_object():
    """`editObject`/`saveObject`/`deleteObject` zostały wydzielone."""
    source = _admin_source()
    for fn in ("const editObject", "const saveObject", "const deleteObject"):
        assert fn not in source, (
            f"admin.js nadal zawiera `{fn}` - nie został wydzielony"
        )


def test_admin_js_no_longer_contains_area_point_categories():
    """Kategorie obiektów są teraz w objects.js."""
    source = _admin_source()
    assert "const areaCategories" not in source, (
        "admin.js nadal zawiera `const areaCategories` - nie został wydzielony"
    )
    assert "const pointCategories" not in source, (
        "admin.js nadal zawiera `const pointCategories` - nie został wydzielony"
    )


def test_admin_js_no_longer_has_all_objects_state():
    """`let allObjects` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "let allObjects" not in source, (
        "admin.js nadal zawiera `let allObjects` - nie został wydzielony"
    )


# ============================================================================
# Kolejność ładowania w admin.html
# ============================================================================


def test_admin_html_loads_objects_js_before_admin_js():
    """`objects.js` musi być załadowany PRZED `admin.js` w tagach <script>.

    Szukamy konkretnie `<script src="...">` (nie w komentarzach HTML).
    """
    import re as _re
    html = _admin_html()
    # Wyciagnij tagi <script src="..."> w kolejności
    scripts = _re.findall(r'<script\s+src="([^"]+)"', html)
    assert "js/objects.js" in scripts, "admin.html nie ładuje js/objects.js (w <script>)"
    assert "admin.js" in scripts, "admin.html nie ładuje admin.js (w <script>)"
    objects_idx = scripts.index("js/objects.js")
    admin_idx = scripts.index("admin.js")
    assert objects_idx < admin_idx, (
        f"objects.js (idx {objects_idx}) musi być PRZED admin.js (idx {admin_idx}); "
        f"kolejnosc: {scripts}"
    )


def test_admin_html_loads_objects_js_after_dependencies():
    """`objects.js` musi być PO api/utils/notifications/diagnostics (potrzebuje ich)."""
    html = _admin_html()
    objects_pos = html.find('js/objects.js')
    for dep in ("js/api.js", "js/utils.js", "js/notifications.js"):
        dep_pos = html.find(dep)
        assert dep_pos > 0, f"admin.html nie ładuje {dep}"
        assert dep_pos < objects_pos, (
            f"{dep} (pozycja {dep_pos}) musi być PRZED objects.js ({objects_pos})"
        )


def test_admin_html_documents_objects_js_in_header_comment():
    """Komentarz w api.js wymienia objects.js - sanityzacja po wydzieleniu."""
    api_js = (PROJECT_ROOT / "static" / "admin" / "js" / "api.js").read_text(encoding="utf-8")
    assert "objects.js" in api_js, (
        "Komentarz w api.js nie wymienia objects.js (pozycja 4 w kolejności ładowania)"
    )
