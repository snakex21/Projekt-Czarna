"""Kontrakt UI modułu `static/admin/js/genealogy-list.js` (P2.5 Etap 10).

Moduł przejmuje ładowanie, renderowanie i filtrowanie listy osób genealogicznych.
Panel szczegółów, mini-drzewo, modal CRUD oraz usuwanie/edycja są obsługiwane
przez callbacki z `admin.js` i wyspecjalizowane moduły genealogii.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GENEALOGY_LIST_JS = PROJECT_ROOT / "static" / "admin" / "js" / "genealogy-list.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


def _list_source() -> str:
    if not GENEALOGY_LIST_JS.exists():
        pytest.fail(f"Brak pliku {GENEALOGY_LIST_JS} - lista genealogii nie została wydzielona")
    return GENEALOGY_LIST_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def test_genealogy_list_file_exists():
    assert GENEALOGY_LIST_JS.exists()


def test_genealogy_list_registers_window_namespace():
    source = _list_source()
    assert "window.AdminGenealogyList" in source


def test_genealogy_list_uses_object_freeze_and_iife():
    source = _list_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source


def test_genealogy_list_public_api_has_load_render_filter():
    source = _list_source()
    match = re.search(
        r"window\.AdminGenealogyList\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.AdminGenealogyList = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"load", "render", "filter"}


def test_genealogy_list_uses_expected_dependencies():
    source = _list_source()
    assert "window.AdminAPI" in source
    assert "window.AdminNotifications" in source
    assert "API.genealogy" in source
    assert "API.protocols" in source
    assert "showNotification" in source


def test_genealogy_list_contains_expected_functions():
    source = _list_source()
    for token in ("loadGenealogy", "renderGenealogy", "filterGenealogy", "formatLifespan"):
        assert token in source


def test_genealogy_list_handles_expected_dom_elements():
    source = _list_source()
    for token in (
        "personsListContainer",
        "genPersonCount",
        "searchGenealogy",
        "filterHouse",
        "sortFilter",
        "genealogy-filters",
        "filter-btn",
        "person-list-item",
        "person-list-icon",
        "person-list-info",
        "person-list-name",
        "person-list-dates",
        "person-list-arrow",
    ):
        assert token in source


def test_genealogy_list_renders_empty_state_and_items():
    source = _list_source()
    for token in ("Nie znaleziono osób", "person-list-item", "fa-search", "fa-calendar"):
        assert token in source


def test_genealogy_list_handles_expected_filters_and_sorting():
    source = _list_source()
    for token in (
        "id_asc",
        "id_desc",
        "az",
        "za",
        "male",
        "female",
        "localeCompare",
        "numer_domu",
        "rok_urodzenia",
    ):
        assert token in source


def test_genealogy_list_uses_callbacks_for_state_and_selection():
    source = _list_source()
    for token in ("onDataLoaded", "onSelect"):
        assert token in source
    source_no_comments = _source_no_comments(GENEALOGY_LIST_JS)
    for forbidden in (
        "GEN_DETAILS",
        "GEN_MINI",
        "GEN_MODAL",
        "window.AdminGenealogyDetails",
        "window.AdminGenealogyMiniTree",
        "window.AdminGenealogyModal",
    ):
        assert forbidden not in source_no_comments


def test_genealogy_list_does_not_contain_details_modal_tree_or_delete_logic():
    source = _source_no_comments(GENEALOGY_LIST_JS)
    for forbidden in (
        "openGenealogyModal",
        "saveGenealogy",
        "setupPersonAutocomplete",
        "genealogyForm",
        "fatherAutocomplete",
        "motherAutocomplete",
        "protocolAutocomplete",
        "spousesContainer",
        "addSpouseRow",
        "editGenealogy(",
        "deleteGenealogy(",
        "showMiniTree",
        "renderTreeNode",
        "createRelationCard",
        "renderRelationSection",
        "findGrandparents",
        "findParents",
        "findSpouses",
        "findSiblings",
        "findChildren",
        "findCousins",
    ):
        assert forbidden not in source


def test_genealogy_list_isolated_from_other_ui_files():
    source = _source_no_comments(GENEALOGY_LIST_JS)
    for forbidden in (
        "objects.js",
        "owners.js",
        "dashboard.js",
        "owner-modal.js",
        "demography.js",
        "tree-renderer.js",
        "admin.js",
        "genealogia_admin.js",
        "genealogy-details.js",
        "genealogy-mini-tree.js",
        "genealogy-modal.js",
    ):
        assert forbidden not in source


def test_admin_html_loads_genealogy_list_after_genealogy_modules_before_admin_js():
    html = ADMIN_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)
    for script in (
        "js/genealogy-mini-tree.js",
        "js/genealogy-details.js",
        "js/genealogy-modal.js",
        "js/genealogy-list.js",
        "admin.js",
    ):
        assert script in scripts
    assert scripts.index("js/genealogy-mini-tree.js") < scripts.index("js/genealogy-list.js")
    assert scripts.index("js/genealogy-details.js") < scripts.index("js/genealogy-list.js")
    assert scripts.index("js/genealogy-modal.js") < scripts.index("js/genealogy-list.js")
    assert scripts.index("js/genealogy-list.js") < scripts.index("admin.js")


def test_admin_js_requires_and_aliases_genealogy_list():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "window.AdminGenealogyList" in source
    assert "const GEN_LIST = window.AdminGenealogyList" in source
    assert "admin.js wymaga js/genealogy-list.js załadowanego wcześniej" in source


def test_admin_js_uses_genealogy_list_alias_for_load_render_and_filter():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "GEN_LIST.load(genealogyListOptions())" in source
    assert "GEN_LIST.render(data, genealogyListOptions())" in source
    assert "GEN_LIST.filter(genealogyListOptions())" in source
    assert "genealogyListOptions" in source


def test_admin_js_no_longer_contains_genealogy_list_implementation():
    source = _source_no_comments(ADMIN_JS)
    for forbidden in (
        "const formatLifespan",
        "Nie znaleziono osób",
        "person-list-icon",
        "person-list-arrow",
        "const getSurnameStatus",
    ):
        assert forbidden not in source


def test_admin_js_keeps_genealogy_edit_delete_modal_and_tree_orchestration():
    source = ADMIN_JS.read_text(encoding="utf-8")
    for token in (
        "const loadGenealogy",
        "const renderGenealogy",
        "const filterGenealogy",
        "const editGenealogy",
        "const deleteGenealogy",
        "GEN_MODAL.open(person, genealogyModalOptions())",
        "GEN_MODAL.open(null, genealogyModalOptions())",
        "GEN_DETAILS.show(person, allGenealogy",
        "GEN_MINI.show(person, allGenealogy)",
    ):
        assert token in source


def test_api_header_documents_genealogy_list_load_order():
    source = API_JS.read_text(encoding="utf-8")
    assert "genealogy-list.js" in source
