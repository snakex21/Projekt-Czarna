"""Kontrakt UI modułu `static/admin/js/genealogy-mini-tree.js` (P2.5 Etap 7).

Moduł przejmuje wyłącznie kompaktowe 3-generacyjne mini-drzewo z profilu
osoby. Pełne ładowanie/renderowanie/filtrowanie genealogii zostaje w `admin.js`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GENEALOGY_MINI_TREE_JS = PROJECT_ROOT / "static" / "admin" / "js" / "genealogy-mini-tree.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


def _mini_tree_source() -> str:
    if not GENEALOGY_MINI_TREE_JS.exists():
        pytest.fail(
            f"Brak pliku {GENEALOGY_MINI_TREE_JS} - mini-drzewo genealogii nie zostało wydzielone"
        )
    return GENEALOGY_MINI_TREE_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def test_genealogy_mini_tree_file_exists():
    assert GENEALOGY_MINI_TREE_JS.exists()


def test_genealogy_mini_tree_registers_window_namespace():
    source = _mini_tree_source()
    assert "window.AdminGenealogyMiniTree" in source


def test_genealogy_mini_tree_uses_object_freeze_and_iife():
    source = _mini_tree_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source


def test_genealogy_mini_tree_public_api_has_only_show():
    source = _mini_tree_source()
    match = re.search(
        r"window\.AdminGenealogyMiniTree\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.AdminGenealogyMiniTree = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"show"}


def test_genealogy_mini_tree_contains_expected_functions():
    source = _mini_tree_source()
    for token in (
        "showMiniTree",
        "renderTreeNode",
        "getNodeClass",
        "formatYears",
        "getPersonById",
    ):
        assert token in source


def test_genealogy_mini_tree_has_no_fetch_or_api_dependency():
    source = _source_no_comments(GENEALOGY_MINI_TREE_JS)
    assert "fetch(" not in source
    assert "window.AdminAPI" not in source


def test_genealogy_mini_tree_isolated_from_other_ui_files():
    source = _source_no_comments(GENEALOGY_MINI_TREE_JS)
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


def test_genealogy_mini_tree_handles_expected_dom_elements():
    source = _mini_tree_source()
    for token in ("treeModal", "treeModalTitle", "treeContainer", "treeModalClose"):
        assert token in source


def test_genealogy_mini_tree_renders_polish_labels():
    source = _mini_tree_source()
    for label in ("Dziadkowie", "Rodzice", "Rodzeństwo", "Główna osoba", "Dzieci"):
        assert label in source


def test_genealogy_mini_tree_sets_global_click_handler():
    source = _mini_tree_source()
    assert "window.showMiniTreeForPerson" in source


def test_admin_html_loads_genealogy_mini_tree_before_admin_js():
    html = ADMIN_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)
    for script in ("js/genealogy-mini-tree.js", "admin.js"):
        assert script in scripts
    assert scripts.index("js/genealogy-mini-tree.js") < scripts.index("admin.js")


def test_admin_js_requires_and_aliases_genealogy_mini_tree():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "window.AdminGenealogyMiniTree" in source
    assert "const GEN_MINI = window.AdminGenealogyMiniTree" in source


def test_admin_js_uses_genealogy_mini_tree_alias_with_data():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "GEN_MINI.show(person, allGenealogy)" in source


def test_admin_js_no_longer_contains_mini_tree_implementation():
    source = _source_no_comments(ADMIN_JS)
    assert "const showMiniTree" not in source
    assert "const renderTreeNode" not in source


def test_api_header_documents_genealogy_mini_tree_load_order():
    source = API_JS.read_text(encoding="utf-8")
    assert "genealogy-mini-tree.js" in source
