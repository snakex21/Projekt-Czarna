"""Kontrakt UI modułu `static/admin/js/genealogy-tree.js` (P2.5 Etap 13).

Moduł zastępuje legacy `static/admin/genealogia_admin.js` i odpowiada za
pełne drzewo genealogiczne w panelu admina. Mini-drzewo pozostaje w
`genealogy-mini-tree.js`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GENEALOGY_TREE_JS = PROJECT_ROOT / "static" / "admin" / "js" / "genealogy-tree.js"
LEGACY_GENEALOGIA_ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "genealogia_admin.js"
GENEALOGY_DETAILS_JS = PROJECT_ROOT / "static" / "admin" / "js" / "genealogy-details.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


def _tree_source() -> str:
    if not GENEALOGY_TREE_JS.exists():
        pytest.fail(
            f"Brak pliku {GENEALOGY_TREE_JS} - pełne drzewo genealogii nie zostało wydzielone"
        )
    return GENEALOGY_TREE_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def test_genealogy_tree_file_exists():
    assert GENEALOGY_TREE_JS.exists()


def test_genealogy_tree_registers_window_namespace():
    source = _tree_source()
    assert "window.AdminGenealogyTree" in source
    assert "window.GenealogyAdmin" not in _source_no_comments(GENEALOGY_TREE_JS)


def test_genealogy_tree_uses_object_freeze_and_iife():
    source = _tree_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source


def test_genealogy_tree_public_api():
    source = _tree_source()
    match = re.search(
        r"window\.AdminGenealogyTree\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.AdminGenealogyTree = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"show", "showFromData", "render", "setContainer"}


def test_genealogy_tree_uses_existing_tree_modal_and_polish_labels():
    source = _tree_source()
    for token in (
        "treeModal",
        "treeModalTitle",
        "treeContainer",
        "treeModalClose",
        "Pełne drzewo",
        "Brak danych genealogicznych",
        "Kliknij osobę",
    ):
        assert token in source
    assert "genealogyModal" not in _source_no_comments(GENEALOGY_TREE_JS)
    assert "genealogy-chart" not in _source_no_comments(GENEALOGY_TREE_JS)


def test_genealogy_tree_uses_loaded_data_not_legacy_protocol_fetch():
    source = _source_no_comments(GENEALOGY_TREE_JS)
    assert "showFromData" in source
    assert "fetch(`/api/genealogia/${protocolKey}`)" not in source
    assert "fetch('/api/genealogia/" not in source
    assert 'fetch("/api/genealogia/' not in source


def test_genealogy_details_adds_full_tree_callback_and_button():
    source = GENEALOGY_DETAILS_JS.read_text(encoding="utf-8")
    assert "onShowFullTree" in source
    assert "full-tree-btn" in source
    assert "Pełne drzewo" in source


def test_admin_html_loads_genealogy_tree_before_details_and_admin_without_legacy():
    html = ADMIN_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)
    for script in ("js/genealogy-tree.js", "js/genealogy-details.js", "admin.js"):
        assert script in scripts
    assert "genealogia_admin.js" not in scripts
    assert scripts.index("js/genealogy-tree.js") < scripts.index("js/genealogy-details.js")
    assert scripts.index("js/genealogy-tree.js") < scripts.index("admin.js")


def test_admin_js_requires_aliases_and_uses_genealogy_tree():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "window.AdminGenealogyTree" in source
    assert "const GEN_TREE = window.AdminGenealogyTree" in source
    assert "admin.js wymaga js/genealogy-tree.js załadowanego wcześniej" in source
    assert "onShowFullTree" in source
    assert "GEN_TREE.showFromData(person, allGenealogy)" in source


def test_legacy_genealogia_admin_is_removed_from_admin_contract():
    html = ADMIN_HTML.read_text(encoding="utf-8")
    api_source = API_JS.read_text(encoding="utf-8")
    assert "genealogia_admin.js" not in html
    assert "genealogia_admin.js" not in api_source
    assert not LEGACY_GENEALOGIA_ADMIN_JS.exists()


def test_api_header_documents_genealogy_tree_load_order():
    source = API_JS.read_text(encoding="utf-8")
    assert "genealogy-tree.js" in source
