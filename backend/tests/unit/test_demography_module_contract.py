"""
Kontrakt UI modułu `static/admin/js/demography.js` (P2.5 Etap 3).

Weryfikuje strukturę kodu źródłowego modułu JS bez uruchamiania przeglądarki
(wzorzec projektu - testy UI to testy kontraktu regex/AST).

Co jest testowane:
- Moduł rejestruje `window.AdminDemography` jako `Object.freeze({...})`.
- Publiczne API: `load`, `add`, `save`, `remove` (4 metody).
- Moduł NIE importuje innych modułów UI (izolowany).
- Moduł NIE ma top-level kodu który tworzy DOM (tylko definicje).
- Moduł współpracuje z `window.AdminAPI.demography` (endpoint).
- Moduł używa `window.AdminUtils.escapeHtml` (sanityzacja).
- Moduł używa `window.AdminNotifications.showToast` (komunikaty).
- `admin.html` ładuje `demography.js` w odpowiedniej kolejności
  (po owners.js, przed admin.js).
- `admin.js` NIE zawiera już sekcji demografii
  (loadDemography, renderDemography, openDemographyModal, saveDemographyEntry,
  window.saveDemography, window.deleteDemography, `let allDemography`)
  - to anti-regresja po wydzieleniu.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEMOGRAPHY_JS = PROJECT_ROOT / "static" / "admin" / "js" / "demography.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


# ============================================================================
# Helpery
# ============================================================================


def _demography_source() -> str:
    if not DEMOGRAPHY_JS.exists():
        pytest.fail(f"Brak pliku {DEMOGRAPHY_JS} - moduł nie został wydzielony")
    return DEMOGRAPHY_JS.read_text(encoding="utf-8")


def _demography_source_no_comments() -> str:
    """Źródło demography.js z usuniętymi komentarzami (/* */ i //)."""
    import re as _re
    source = _demography_source()
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


def test_demography_module_registers_window_namespace():
    """Moduł musi eksportować `window.AdminDemography`."""
    source = _demography_source()
    assert "window.AdminDemography" in source, (
        "Brak eksportu window.AdminDemography w demography.js"
    )


def test_demography_module_uses_object_freeze():
    """Moduł używa `Object.freeze({...})` - wzorzec projektu (niemutowalny API)."""
    source = _demography_source()
    assert "Object.freeze" in source, (
        "Brak Object.freeze w demography.js (wymagany wzorzec projektu)"
    )


def test_demography_module_uses_iife_pattern():
    """Moduł zamknięty w IIFE: `(function () { ... })();` - wzorzec projektu."""
    source = _demography_source()
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source), (
        "Brak IIFE wrapper w demography.js (wymagany wzorzec projektu)"
    )
    assert "'use strict'" in source, (
        "Brak 'use strict' w demography.js (wymagane przez wzorzec)"
    )


# ============================================================================
# Publiczne API
# ============================================================================


def test_demography_module_exposes_load_function():
    """`load` - pobiera dane demograficzne z API i renderuje tabelę."""
    source = _demography_source()
    assert re.search(r"load\s*:\s*loadDemography", source), (
        "Brak `load: loadDemography` w publicznym API"
    )


def test_demography_module_exposes_add_function():
    """`add` - otwiera modal z formularzem nowego wpisu demograficznego."""
    source = _demography_source()
    assert re.search(r"add\s*:\s*openDemographyModal", source), (
        "Brak `add: openDemographyModal` w publicznym API"
    )


def test_demography_module_exposes_save_function():
    """`save` - zapisuje wpis (POST dla nowego, PUT dla edycji inline)."""
    source = _demography_source()
    # save musi mieć co najmniej saveDemographyEntry (nowy wpis)
    assert "saveDemographyEntry" in source, (
        "Brak `saveDemographyEntry` w demography.js (zapis nowego wpisu)"
    )
    # oraz save inline (edycja istniejącego)
    assert "saveDemography" in source, (
        "Brak `saveDemography` w demography.js (zapis inline edycji)"
    )


def test_demography_module_exposes_remove_function():
    """`remove` - DELETE wpisu demograficznego (z potwierdzeniem)."""
    source = _demography_source()
    assert re.search(r"remove\s*:\s*deleteDemography", source), (
        "Brak `remove: deleteDemography` w publicznym API (alias dla delete)"
    )


def test_demography_module_has_exactly_four_public_methods():
    """Publiczne API = load, add, save, remove (4 metody)."""
    source = _demography_source()
    # Wyciagnij blok `Object.freeze({ ... })`
    match = re.search(r"Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)", source)
    assert match, "Brak bloku Object.freeze w demography.js"
    block = match.group(1)
    # Policz klucze (linie typu `name: functionName,`)
    keys = re.findall(r"(\w+)\s*:\s*\w+", block)
    assert set(keys) == {"load", "add", "save", "remove"}, (
        f"Publiczne API ma niespodziewane klucze: {set(keys)} "
        f"(oczekiwane: load, add, save, remove)"
    )


# ============================================================================
# Zależności (współpraca z innymi modułami)
# ============================================================================


def test_demography_module_uses_admin_api():
    """Moduł korzysta z `window.AdminAPI.demography` (URL endpointu)."""
    source = _demography_source()
    assert "window.AdminAPI" in source or "AdminAPI.demography" in source, (
        "Brak użycia window.AdminAPI w demography.js (endpointy)"
    )
    assert "API.demography" in source, (
        "Moduł nie korzysta z API.demography - fetch URL nie jest z AdminAPI"
    )


def test_demography_module_uses_admin_utils_escapehtml():
    """Moduł korzysta z `window.AdminUtils.escapeHtml` (sanityzacja)."""
    source = _demography_source()
    assert "escapeHtml" in source, (
        "Brak użycia escapeHtml w demography.js (wymagana sanityzacja danych)"
    )
    assert re.search(r"window\.AdminUtils", source), (
        "Moduł nie pobiera helperów z window.AdminUtils (izolacja)"
    )


def test_demography_module_uses_admin_notifications():
    """Moduł korzysta z `window.AdminNotifications.showToast` (komunikaty)."""
    source = _demography_source()
    assert "showToast" in source, (
        "Brak użycia showToast w demography.js (komunikaty błędów/sukcesu)"
    )
    assert re.search(r"window\.AdminNotifications", source), (
        "Moduł nie pobiera helperów z window.AdminNotifications (izolacja)"
    )


# ============================================================================
# Stan i funkcjonalność
# ============================================================================


def test_demography_module_has_private_state_all_demography():
    """Prywatny stan `allDemography` (lista wpisów) - NIE eksponowany na window."""
    source = _demography_source()
    assert "allDemography" in source, (
        "Brak stanu allDemography w demography.js (potrzebny do cache'a)"
    )
    # Prywatny - nie może być na window
    assert "window.allDemography" not in source, (
        "allDemography wyciekło na window - powinno być prywatne (let wewnątrz IIFE)"
    )


def test_demography_module_renders_table_with_required_fields():
    """`renderDemography` musi renderować pola: rok, populacja, katolicy, żydzi, inni, opis."""
    source = _demography_source()
    for field in ("rok", "populacja_ogolem", "katolicy", "zydzi", "inni", "opis"):
        assert field in source, (
            f"renderDemography nie zawiera pola `{field}`"
        )


def test_demography_module_remove_uses_confirm():
    """`deleteDemography` musi pytać użytkownika o potwierdzenie."""
    source = _demography_source()
    assert re.search(r"confirm\s*\(", source), (
        "deleteDemography nie używa confirm() - usuwanie bez potwierdzenia"
    )


# ============================================================================
# Izolacja modułu
# ============================================================================


def test_demography_module_isolated_from_other_ui():
    """Moduł NIE importuje innych modułów UI (self-contained).

    Sprawdzamy tylko AKTYWNY kod (bez komentarzy) - w nagłówku modułu
    dokumentowana jest kolejność ładowania i nazwy innych plików.
    """
    source = _demography_source_no_comments()
    forbidden_imports = [
        "diagnostics.js",
        "notifications.js",
        "utils.js",
        "api.js",
        "admin.js",
        "genealogia_admin.js",
        "objects.js",
        "owners.js",
    ]
    for forbidden in forbidden_imports:
        assert forbidden not in source, (
            f"demography.js importuje {forbidden} - moduł nie powinien importować innych UI"
        )


def test_demography_module_no_top_level_side_effects():
    """Moduł nie wykonuje fetch/DOM przy imporcie (czysta definicja)."""
    source = _demography_source()
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
# Anti-regresja: admin.js NIE zawiera już sekcji demografii
# ============================================================================


def test_admin_js_no_longer_contains_load_demography():
    """`loadDemography` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "const loadDemography" not in source, (
        "admin.js nadal zawiera `const loadDemography` - nie został wydzielony"
    )


def test_admin_js_no_longer_contains_render_demography():
    """`renderDemography` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "const renderDemography" not in source, (
        "admin.js nadal zawiera `const renderDemography` - nie został wydzielony"
    )


def test_admin_js_no_longer_contains_open_demography_modal():
    """`openDemographyModal` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "const openDemographyModal" not in source, (
        "admin.js nadal zawiera `const openDemographyModal` - nie został wydzielony"
    )


def test_admin_js_no_longer_contains_save_demography_entry():
    """`saveDemographyEntry` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "const saveDemographyEntry" not in source, (
        "admin.js nadal zawiera `const saveDemographyEntry` - nie został wydzielony"
    )


def test_admin_js_no_longer_contains_window_save_demography():
    """`window.saveDemography` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "window.saveDemography" not in source, (
        "admin.js nadal zawiera `window.saveDemography` - inline onclick nie został zaktualizowany"
    )


def test_admin_js_no_longer_contains_window_delete_demography():
    """`window.deleteDemography` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "window.deleteDemography" not in source, (
        "admin.js nadal zawiera `window.deleteDemography` - inline onclick nie został zaktualizowany"
    )


def test_admin_js_no_longer_has_all_demography_state():
    """`let allDemography` zostało wydzielone - admin.js nie powinien go mieć."""
    source = _admin_source()
    assert "let allDemography" not in source, (
        "admin.js nadal zawiera `let allDemography` - nie został wydzielony"
    )


# ============================================================================
# Kolejność ładowania w admin.html
# ============================================================================


def test_admin_html_loads_demography_js_before_admin_js():
    """`demography.js` musi być załadowany PRZED `admin.js` w tagach <script>.

    Szukamy konkretnie `<script src="...">` (nie w komentarzach HTML).
    """
    import re as _re
    html = _admin_html()
    scripts = _re.findall(r'<script\s+src="([^"]+)"', html)
    assert "js/demography.js" in scripts, "admin.html nie ładuje js/demography.js (w <script>)"
    assert "admin.js" in scripts, "admin.html nie ładuje admin.js (w <script>)"
    demo_idx = scripts.index("js/demography.js")
    admin_idx = scripts.index("admin.js")
    assert demo_idx < admin_idx, (
        f"demography.js (idx {demo_idx}) musi być PRZED admin.js (idx {admin_idx}); "
        f"kolejnosc: {scripts}"
    )


def test_admin_html_loads_demography_js_after_dependencies():
    """`demography.js` musi być PO api/utils/notifications/objects/owners (potrzebuje ich)."""
    html = _admin_html()
    demo_pos = html.find('js/demography.js')
    assert demo_pos > 0, "admin.html nie ładuje js/demography.js"
    for dep in ("js/api.js", "js/utils.js", "js/notifications.js", "js/objects.js", "js/owners.js"):
        dep_pos = html.find(dep)
        assert dep_pos > 0, f"admin.html nie ładuje {dep}"
        assert dep_pos < demo_pos, (
            f"{dep} (pozycja {dep_pos}) musi być PRZED demography.js ({demo_pos})"
        )


def test_admin_html_documents_demography_js_in_api_header_comment():
    """Komentarz w api.js wymienia demography.js - sanityzacja po wydzieleniu."""
    api_source = _api_js()
    assert "demography.js" in api_source, (
        "Komentarz w api.js nie wymienia demography.js (pozycja w kolejności ładowania)"
    )
