"""Kontrakt UI modułu `static/admin/js/genealogy-modal.js` (P2.5 Etap 9).

Moduł przejmuje formularz dodawania/edycji osoby genealogicznej z `admin.js`.
Lista, filtrowanie, ładowanie, panel szczegółów i mini-drzewo pozostają poza nim.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GENEALOGY_MODAL_JS = PROJECT_ROOT / "static" / "admin" / "js" / "genealogy-modal.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


def _modal_source() -> str:
    if not GENEALOGY_MODAL_JS.exists():
        pytest.fail(f"Brak pliku {GENEALOGY_MODAL_JS} - modal genealogii nie został wydzielony")
    return GENEALOGY_MODAL_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def test_genealogy_modal_file_exists():
    assert GENEALOGY_MODAL_JS.exists()


def test_genealogy_modal_registers_window_namespace():
    source = _modal_source()
    assert "window.AdminGenealogyModal" in source


def test_genealogy_modal_uses_object_freeze_and_iife():
    source = _modal_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source


def test_genealogy_modal_public_api_has_open_and_save():
    source = _modal_source()
    match = re.search(
        r"window\.AdminGenealogyModal\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.AdminGenealogyModal = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"open", "save"}


def test_genealogy_modal_uses_expected_dependencies():
    source = _modal_source()
    assert "window.AdminAPI" in source
    assert "window.AdminNotifications" in source
    assert "API.genealogy" in source
    assert "showToast" in source


def test_genealogy_modal_contains_expected_form_and_helpers():
    source = _modal_source()
    for token in (
        "openGenealogyModal",
        "saveGenealogy",
        "setupPersonAutocomplete",
        "genealogyForm",
        "fatherAutocomplete",
        "motherAutocomplete",
        "protocolAutocomplete",
        "spousesContainer",
        "addSpouseRow",
        "spouse-row",
        "marriages",
    ):
        assert token in source


def test_genealogy_modal_contains_expected_fields():
    source = _modal_source()
    for token in (
        "id_osoby",
        "imie",
        "nazwisko",
        "plec",
        "rok_urodzenia",
        "rok_smierci",
        "id_ojca",
        "id_matki",
        "protokol_klucz",
        "uwagi",
    ):
        assert token in source


def test_genealogy_modal_handles_post_and_put():
    source = _modal_source()
    assert "method = id ? 'PUT' : 'POST'" in source or 'method = id ? "PUT" : "POST"' in source
    assert "JSON.stringify(data)" in source


def test_genealogy_modal_uses_callbacks_for_after_save():
    source = _modal_source()
    assert "onSaved" in source
    source_no_comments = _source_no_comments(GENEALOGY_MODAL_JS)
    assert "loadGenealogy(" not in source_no_comments
    assert "showPersonDetails(" not in source_no_comments
    assert "GEN_DETAILS" not in source_no_comments
    assert "GEN_MINI" not in source_no_comments


def test_genealogy_modal_does_not_contain_list_filter_delete_logic():
    source = _source_no_comments(GENEALOGY_MODAL_JS)
    for forbidden in (
        "personsListContainer",
        "personDetailsPanel",
        "genPersonCount",
        "searchGenealogy",
        "filterHouse",
        "sortFilter",
        "deleteGenealogy",
        "renderGenealogy",
        "filterGenealogy",
        "loadGenealogy",
    ):
        assert forbidden not in source


def test_genealogy_modal_isolated_from_other_ui_files():
    source = _source_no_comments(GENEALOGY_MODAL_JS)
    for forbidden in (
        "objects.js",
        "owners.js",
        "dashboard.js",
        "owner-modal.js",
        "demography.js",
        "tree-renderer.js",
        "genealogy-details.js",
        "genealogy-mini-tree.js",
        "admin.js",
        "genealogia_admin.js",
    ):
        assert forbidden not in source


def test_admin_html_loads_genealogy_modal_after_genealogy_modules_before_admin_js():
    html = ADMIN_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)
    for script in ("js/genealogy-mini-tree.js", "js/genealogy-details.js", "js/genealogy-modal.js", "admin.js"):
        assert script in scripts
    assert scripts.index("js/genealogy-mini-tree.js") < scripts.index("js/genealogy-modal.js")
    assert scripts.index("js/genealogy-details.js") < scripts.index("js/genealogy-modal.js")
    assert scripts.index("js/genealogy-modal.js") < scripts.index("admin.js")


def test_admin_js_requires_and_aliases_genealogy_modal():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "window.AdminGenealogyModal" in source
    assert "const GEN_MODAL = window.AdminGenealogyModal" in source


def test_admin_js_uses_genealogy_modal_alias_for_add_and_edit():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "GEN_MODAL.open(null, genealogyModalOptions())" in source
    assert "GEN_MODAL.open(person, genealogyModalOptions())" in source
    assert "openGenealogyModal(" not in _source_no_comments(ADMIN_JS)


def test_admin_js_no_longer_contains_genealogy_modal_implementation():
    source = _source_no_comments(ADMIN_JS)
    for forbidden in (
        "const openGenealogyModal",
        "const setupPersonAutocomplete",
        "const saveGenealogy",
        "genealogyForm",
        "fatherAutocomplete",
        "motherAutocomplete",
        "protocolAutocomplete",
        "spousesContainer",
        "addSpouseRow",
    ):
        assert forbidden not in source


def test_admin_js_keeps_genealogy_list_filter_load_edit_delete_in_admin():
    source = ADMIN_JS.read_text(encoding="utf-8")
    for token in (
        "const loadGenealogy",
        "const renderGenealogy",
        "const filterGenealogy",
        "const editGenealogy",
        "const deleteGenealogy",
    ):
        assert token in source


def test_api_header_documents_genealogy_modal_load_order():
    source = API_JS.read_text(encoding="utf-8")
    assert "genealogy-modal.js" in source
