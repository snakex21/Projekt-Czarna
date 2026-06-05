"""
Kontrakt UI modułu `static/admin/js/owners.js` (P2.5 Etap 3).

Weryfikuje strukturę kodu źródłowego modułu JS bez uruchamiania przeglądarki
(wzorzec projektu - testy UI to testy kontraktu regex/AST).

Co jest testowane:
- Moduł rejestruje `window.AdminOwners` jako `Object.freeze({...})`.
- Publiczne API: `load`, `filter`, `edit`, `remove` (4 metody - bez `save`,
  bo zapis właściciela odbywa się przez modal `openOwnerModal` w admin.js).
- Moduł NIE importuje innych modułów UI (izolowany).
- Moduł NIE ma top-level kodu który tworzy DOM (tylko definicje).
- Moduł współpracuje z `window.AdminAPI.owners` (endpoint).
- Moduł używa `window.AdminUtils.escapeHtml` (sanityzacja).
- Moduł używa `window.AdminNotifications.showToast` (komunikaty).
- `admin.html` ładuje `owners.js` w odpowiedniej kolejności
  (po objects.js, przed admin.js).
- `admin.js` NIE zawiera już sekcji właścicieli
  (loadOwners, renderOwners, filterOwners, window.editOwner, window.deleteOwner,
  `let allOwners`) - to anti-regresja po wydzieleniu.
- Brak wycieków: stare wywołania inline `onclick="editOwner(...)"`/`deleteOwner(...)`
  są zastąpione przez `AdminOwners.edit(id)` / `AdminOwners.remove(id)`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OWNERS_JS = PROJECT_ROOT / "static" / "admin" / "js" / "owners.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


# ============================================================================
# Helpery
# ============================================================================


def _owners_source() -> str:
    if not OWNERS_JS.exists():
        pytest.fail(f"Brak pliku {OWNERS_JS} - moduł nie został wydzielony")
    return OWNERS_JS.read_text(encoding="utf-8")


def _owners_source_no_comments() -> str:
    """Źródło owners.js z usuniętymi komentarzami (/* */ i //)."""
    import re as _re
    source = _owners_source()
    # Usuń komentarze blokowe /* ... */
    source = _re.sub(r"/\*[\s\S]*?\*/", "", source)
    # Usuń komentarze liniowe //
    source = _re.sub(r"//[^\n]*", "", source)
    return source


def _admin_source() -> str:
    return ADMIN_JS.read_text(encoding="utf-8")


def _admin_html() -> str:
    return ADMIN_HTML.read_text(encoding="utf-8")


def _api_js() -> str:
    return API_JS.read_text(encoding="utf-8")


# ============================================================================
# Rejestracja modułu
# ============================================================================


def test_owners_module_registers_window_namespace():
    """Moduł musi eksportować `window.AdminOwners`."""
    source = _owners_source()
    assert "window.AdminOwners" in source, (
        "Brak eksportu window.AdminOwners w owners.js"
    )


def test_owners_module_uses_object_freeze():
    """Moduł używa `Object.freeze({...})` - wzorzec projektu (niemutowalny API)."""
    source = _owners_source()
    assert "Object.freeze" in source, (
        "Brak Object.freeze w owners.js (wymagany wzorzec projektu)"
    )


def test_owners_module_uses_iife_pattern():
    """Moduł zamknięty w IIFE: `(function () { ... })();` - wzorzec projektu."""
    source = _owners_source()
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source), (
        "Brak IIFE wrapper w owners.js (wymagany wzorzec projektu)"
    )
    assert "'use strict'" in source, (
        "Brak 'use strict' w owners.js (wymagane przez wzorzec)"
    )


# ============================================================================
# Publiczne API
# ============================================================================


def test_owners_module_exposes_load_function():
    """`load` - pobiera właścicieli z API i renderuje listę kart."""
    source = _owners_source()
    assert re.search(r"load\s*:\s*loadOwners", source), (
        "Brak `load: loadOwners` w publicznym API"
    )


def test_owners_module_exposes_filter_function():
    """`filter` - filtruje właścicieli po nazwie/kluczu."""
    source = _owners_source()
    assert re.search(r"filter\s*:\s*filterOwners", source), (
        "Brak `filter: filterOwners` w publicznym API"
    )


def test_owners_module_exposes_edit_function():
    """`edit` - pobiera pełne dane właściciela i otwiera modal edycji."""
    source = _owners_source()
    assert re.search(r"edit\s*:\s*editOwner", source), (
        "Brak `edit: editOwner` w publicznym API"
    )


def test_owners_module_exposes_remove_function():
    """`remove` - DELETE właściciela (z potwierdzeniem)."""
    source = _owners_source()
    assert re.search(r"remove\s*:\s*deleteOwner", source), (
        "Brak `remove: deleteOwner` w publicznym API (alias dla delete)"
    )


def test_owners_module_has_exactly_four_public_methods():
    """Publiczne API = load, filter, edit, remove (4 metody, BEZ save)."""
    source = _owners_source()
    # Wyciagnij blok `Object.freeze({ ... })`
    match = re.search(r"Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)", source)
    assert match, "Brak bloku Object.freeze w owners.js"
    block = match.group(1)
    # Policz klucze (linie typu `name: functionName,`)
    keys = re.findall(r"(\w+)\s*:\s*\w+", block)
    assert set(keys) == {"load", "filter", "edit", "remove"}, (
        f"Publiczne API ma niespodziewane klucze: {set(keys)} "
        f"(oczekiwane: load, filter, edit, remove - zapis jest w openOwnerModal w admin.js)"
    )


# ============================================================================
# Zależności (współpraca z innymi modułami)
# ============================================================================


def test_owners_module_uses_admin_api():
    """Moduł korzysta z `window.AdminAPI.owners` (URL endpointu)."""
    source = _owners_source()
    assert "window.AdminAPI" in source or "AdminAPI.owners" in source, (
        "Brak użycia window.AdminAPI w owners.js (endpointy)"
    )
    assert "API.owners" in source, (
        "Moduł nie korzysta z API.owners - fetch URL nie jest z AdminAPI"
    )


def test_owners_module_uses_admin_utils_escapehtml():
    """Moduł korzysta z `window.AdminUtils.escapeHtml` (sanityzacja nazw)."""
    source = _owners_source()
    assert "escapeHtml" in source, (
        "Brak użycia escapeHtml w owners.js (wymagana sanityzacja danych)"
    )
    assert re.search(r"window\.AdminUtils", source), (
        "Moduł nie pobiera helperów z window.AdminUtils (izolacja)"
    )


def test_owners_module_uses_admin_notifications():
    """Moduł korzysta z `window.AdminNotifications.showToast` (komunikaty)."""
    source = _owners_source()
    assert "showToast" in source, (
        "Brak użycia showToast w owners.js (komunikaty błędów/sukcesu)"
    )
    assert re.search(r"window\.AdminNotifications", source), (
        "Moduł nie pobiera helperów z window.AdminNotifications (izolacja)"
    )


# ============================================================================
# Stan i funkcjonalność
# ============================================================================


def test_owners_module_has_private_state_all_owners():
    """Prywatny stan `allOwners` (lista właścicieli) - NIE eksponowany na window."""
    source = _owners_source()
    assert "allOwners" in source, (
        "Brak stanu allOwners w owners.js (potrzebny do filtrowania)"
    )
    # Prywatny - nie może być na window
    assert "window.allOwners" not in source, (
        "allOwners wyciekło na window - powinno być prywatne (let wewnątrz IIFE)"
    )


def test_owners_module_filter_searches_by_nazwa_wlasciciela():
    """`filterOwners` musi filtrować po `nazwa_wlasciciela`."""
    source = _owners_source()
    assert "nazwa_wlasciciela" in source, (
        "filterOwners nie sprawdza pola nazwa_wlasciciela"
    )


def test_owners_module_filter_searches_by_unikalny_klucz():
    """`filterOwners` musi filtrować po `unikalny_klucz`."""
    source = _owners_source()
    assert "unikalny_klucz" in source, (
        "filterOwners nie sprawdza pola unikalny_klucz"
    )


def test_owners_module_remove_uses_confirm():
    """`deleteOwner` musi pytać użytkownika o potwierdzenie."""
    source = _owners_source()
    # Sprawdź czy deleteOwner ma confirm()
    assert re.search(r"confirm\s*\(", source), (
        "deleteOwner nie używa confirm() - usuwanie bez potwierdzenia"
    )


# ============================================================================
# Izolacja modułu
# ============================================================================


def test_owners_module_isolated_from_other_ui():
    """Moduł NIE importuje innych modułów UI (self-contained).

    Sprawdzamy tylko AKTYWNY kod (bez komentarzy) - w nagłówku modułu
    dokumentowana jest kolejność ładowania i nazwy innych plików.
    """
    source = _owners_source_no_comments()
    forbidden_imports = [
        "diagnostics.js",
        "notifications.js",
        "utils.js",
        "api.js",
        "admin.js",
        "genealogia_admin.js",
        "objects.js",
    ]
    for forbidden in forbidden_imports:
        assert forbidden not in source, (
            f"owners.js importuje {forbidden} - moduł nie powinien importować innych UI"
        )


def test_owners_module_no_top_level_side_effects():
    """Moduł nie wykonuje fetch/DOM przy imporcie (czysta definicja)."""
    source = _owners_source()
    lines = [l for l in source.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        stripped = line.strip()
        # fetch powinien być wcięty (wewnątrz funkcji)
        if "fetch(" in stripped and not stripped.startswith("//"):
            indent = len(line) - len(line.lstrip())
            assert indent >= 4, (
                f"Linia {i+1}: fetch() na top-level (indent={indent}): {stripped}"
            )


# ============================================================================
# Anti-regresja: admin.js NIE zawiera już sekcji właścicieli
# ============================================================================


def test_admin_js_no_longer_contains_load_owners():
    """`loadOwners` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "const loadOwners" not in source, (
        "admin.js nadal zawiera `const loadOwners` - nie został wydzielony"
    )


def test_admin_js_no_longer_contains_render_owners():
    """`renderOwners` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "const renderOwners" not in source, (
        "admin.js nadal zawiera `const renderOwners` - nie został wydzielony"
    )


def test_admin_js_no_longer_contains_filter_owners():
    """`filterOwners` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "const filterOwners" not in source, (
        "admin.js nadal zawiera `const filterOwners` - nie został wydzielony"
    )


def test_admin_js_no_longer_contains_window_edit_owner():
    """`window.editOwner` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "window.editOwner" not in source, (
        "admin.js nadal zawiera `window.editOwner` - inline onclick nie został zaktualizowany"
    )


def test_admin_js_no_longer_contains_window_delete_owner():
    """`window.deleteOwner` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "window.deleteOwner" not in source, (
        "admin.js nadal zawiera `window.deleteOwner` - inline onclick nie został zaktualizowany"
    )


def test_admin_js_no_longer_has_all_owners_state():
    """`let allOwners` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "let allOwners" not in source, (
        "admin.js nadal zawiera `let allOwners` - nie został wydzielony"
    )


# ============================================================================
# Kolejność ładowania w admin.html
# ============================================================================


def test_admin_html_loads_owners_js_before_admin_js():
    """`owners.js` musi być załadowany PRZED `admin.js` w tagach <script>.

    Szukamy konkretnie `<script src="...">` (nie w komentarzach HTML).
    """
    import re as _re
    html = _admin_html()
    scripts = _re.findall(r'<script\s+src="([^"]+)"', html)
    assert "js/owners.js" in scripts, "admin.html nie ładuje js/owners.js (w <script>)"
    assert "admin.js" in scripts, "admin.html nie ładuje admin.js (w <script>)"
    owners_idx = scripts.index("js/owners.js")
    admin_idx = scripts.index("admin.js")
    assert owners_idx < admin_idx, (
        f"owners.js (idx {owners_idx}) musi być PRZED admin.js (idx {admin_idx}); "
        f"kolejnosc: {scripts}"
    )


def test_admin_html_loads_owners_js_after_dependencies():
    """`owners.js` musi być PO api/utils/notifications/diagnostics/objects (potrzebuje ich)."""
    html = _admin_html()
    owners_pos = html.find('js/owners.js')
    assert owners_pos > 0, "admin.html nie ładuje js/owners.js"
    for dep in ("js/api.js", "js/utils.js", "js/notifications.js", "js/objects.js"):
        dep_pos = html.find(dep)
        assert dep_pos > 0, f"admin.html nie ładuje {dep}"
        assert dep_pos < owners_pos, (
            f"{dep} (pozycja {dep_pos}) musi być PRZED owners.js ({owners_pos})"
        )


def test_admin_html_documents_owners_js_in_api_header_comment():
    """Komentarz w api.js wymienia owners.js - sanityzacja po wydzieleniu."""
    api_source = _api_js()
    assert "owners.js" in api_source, (
        "Komentarz w api.js nie wymienia owners.js (pozycja w kolejności ładowania)"
    )
