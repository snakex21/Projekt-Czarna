"""Kontrakt UI modułu `static/admin/js/genealogy-details.js` (P2.5 Etap 8).

Moduł przejmuje prawy panel szczegółów osoby w sekcji genealogii.
Lista, filtrowanie i ładowanie genealogii pozostają w `admin.js`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GENEALOGY_DETAILS_JS = PROJECT_ROOT / "static" / "admin" / "js" / "genealogy-details.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


def _details_source() -> str:
    if not GENEALOGY_DETAILS_JS.exists():
        pytest.fail(
            f"Brak pliku {GENEALOGY_DETAILS_JS} - panel szczegółów genealogii nie został wydzielony"
        )
    return GENEALOGY_DETAILS_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def test_genealogy_details_file_exists():
    assert GENEALOGY_DETAILS_JS.exists()


def test_genealogy_details_registers_window_namespace():
    source = _details_source()
    assert "window.AdminGenealogyDetails" in source


def test_genealogy_details_uses_object_freeze_and_iife():
    source = _details_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source


def test_genealogy_details_public_api_has_only_show():
    source = _details_source()
    match = re.search(
        r"window\.AdminGenealogyDetails\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.AdminGenealogyDetails = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"show"}


def test_genealogy_details_contains_expected_helpers():
    source = _details_source()
    for token in (
        "showPersonDetails",
        "formatLifespan",
        "getPersonById",
        "findGrandparents",
        "findParents",
        "findSpouses",
        "findSiblings",
        "findChildren",
        "findCousins",
        "createRelationCard",
        "renderRelationSection",
    ):
        assert token in source


def test_genealogy_details_handles_expected_dom_and_actions():
    source = _details_source()
    for token in (
        "personDetailsPanel",
        "person-list-item",
        "relation-card",
        "tree-btn",
        "edit-btn",
        "delete-btn",
    ):
        assert token in source


def test_genealogy_details_renders_polish_labels():
    source = _details_source()
    for label in (
        "RODZINA",
        "Dziadkowie",
        "Rodzice",
        "Małżonkowie",
        "Rodzeństwo",
        "Dzieci",
        "Kuzynostwo",
        "Notatki",
        "Brak powiązań rodzinnych",
        "Protokół",
        "Drzewo",
    ):
        assert label in source


def test_genealogy_details_uses_callbacks_for_actions():
    source = _details_source()
    for token in ("onEdit", "onDelete", "onShowTree"):
        assert token in source
    source_no_comments = _source_no_comments(GENEALOGY_DETAILS_JS)
    assert "editGenealogy(" not in source_no_comments
    assert "deleteGenealogy(" not in source_no_comments
    assert "GEN_MINI" not in source_no_comments
    assert "window.AdminGenealogyMiniTree" not in source_no_comments


def test_genealogy_details_has_no_fetch_or_api_dependency():
    source = _source_no_comments(GENEALOGY_DETAILS_JS)
    assert "fetch(" not in source
    assert "window.AdminAPI" not in source


def test_genealogy_details_isolated_from_other_ui_files():
    source = _source_no_comments(GENEALOGY_DETAILS_JS)
    for forbidden in (
        "objects.js",
        "owners.js",
        "dashboard.js",
        "owner-modal.js",
        "demography.js",
        "tree-renderer.js",
        "admin.js",
        "genealogia_admin.js",
    ):
        assert forbidden not in source


def test_admin_html_loads_genealogy_details_after_mini_tree_before_admin_js():
    html = ADMIN_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)
    for script in ("js/genealogy-mini-tree.js", "js/genealogy-details.js", "admin.js"):
        assert script in scripts
    assert scripts.index("js/genealogy-mini-tree.js") < scripts.index("js/genealogy-details.js")
    assert scripts.index("js/genealogy-details.js") < scripts.index("admin.js")


def test_admin_js_requires_and_aliases_genealogy_details():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "window.AdminGenealogyDetails" in source
    assert "const GEN_DETAILS = window.AdminGenealogyDetails" in source


def test_admin_js_uses_genealogy_details_alias_with_data_and_callbacks():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "GEN_DETAILS.show(person, allGenealogy" in source
    for token in ("onEdit", "onDelete", "onShowTree"):
        assert token in source


def test_admin_js_no_longer_contains_genealogy_details_helpers():
    source = _source_no_comments(ADMIN_JS)
    for forbidden in (
        "const findGrandparents",
        "const findParents",
        "const findSpouses",
        "const findSiblings",
        "const findChildren",
        "const findCousins",
        "const createRelationCard",
        "const renderRelationSection",
    ):
        assert forbidden not in source


def test_admin_js_keeps_genealogy_list_filter_in_admin_but_not_modal():
    source = ADMIN_JS.read_text(encoding="utf-8")
    for token in ("const loadGenealogy", "const renderGenealogy", "const filterGenealogy"):
        assert token in source
    source_no_comments = _source_no_comments(ADMIN_JS)
    assert "const openGenealogyModal" not in source_no_comments
    assert "const setupPersonAutocomplete" not in source_no_comments
    assert "const saveGenealogy" not in source_no_comments


def test_api_header_documents_genealogy_details_load_order():
    source = API_JS.read_text(encoding="utf-8")
    assert "genealogy-details.js" in source
