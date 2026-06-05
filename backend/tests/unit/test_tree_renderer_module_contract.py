"""Kontrakt UI modułu `static/admin/js/tree-renderer.js` (P2.5 Etap 4/11).

Wydzielamy tylko renderer drzewa genealogicznego z `admin.js` bez ruszania
formularzy/CRUD genealogii. To minimalizuje ryzyko: `admin.js` nadal przygotowuje
dane, a `AdminTreeRenderer.render(container, persons, rootId)` rysuje SVG/D3.

Od P2.5 Etapu 11 legacy adaptery drzewa w `admin.js` zostały uznane za martwe
i nie powinny już wymuszać ładowania renderera w panelu admina.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TREE_RENDERER_JS = PROJECT_ROOT / "static" / "admin" / "js" / "tree-renderer.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


def _tree_source() -> str:
    if not TREE_RENDERER_JS.exists():
        pytest.fail(f"Brak pliku {TREE_RENDERER_JS} - renderer drzewa nie został wydzielony")
    return TREE_RENDERER_JS.read_text(encoding="utf-8")


def _tree_source_no_comments() -> str:
    source = _tree_source()
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def _admin_source() -> str:
    return ADMIN_JS.read_text(encoding="utf-8")


def _admin_html() -> str:
    return ADMIN_HTML.read_text(encoding="utf-8")


def test_tree_renderer_registers_window_namespace():
    source = _tree_source()
    assert "window.AdminTreeRenderer" in source


def test_tree_renderer_uses_object_freeze_and_iife():
    source = _tree_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source


def test_tree_renderer_exposes_only_render_method():
    source = _tree_source()
    match = re.search(r"window\.AdminTreeRenderer\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)", source)
    assert match, "Brak Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"render"}
    assert re.search(r"render\s*:\s*render", match.group(1))


def test_tree_renderer_contains_tree_config_and_layout_helpers():
    source = _tree_source()
    for token in (
        "TREE_CONFIG",
        "NODE_HEIGHT",
        "NODE_MIN_W",
        "H_GAP",
        "V_GAP",
        "MARRIAGE_GAP",
        "positionTreeNodes",
        "findTreeConnections",
    ):
        assert token in source, f"Brak {token} w tree-renderer.js"


def test_tree_renderer_uses_d3_but_not_backend_api():
    source = _tree_source()
    assert "d3.create" in source
    assert "d3.zoom" in source
    assert "window.AdminAPI" not in source
    assert "fetch(" not in source


def test_tree_renderer_handles_empty_data():
    source = _tree_source()
    assert "Brak danych do wyświetlenia" in source
    assert re.search(r"!persons\s*\|\|\s*persons\.length\s*===\s*0", source)


def test_tree_renderer_validates_persons_before_rendering():
    source = _tree_source()
    assert "validPersons" in source
    assert "!p.name.includes('undefined')" in source or '!p.name.includes("undefined")' in source


def test_tree_renderer_isolated_from_other_ui_modules():
    source = _tree_source_no_comments()
    for forbidden in (
        "api.js",
        "utils.js",
        "notifications.js",
        "objects.js",
        "owners.js",
        "demography.js",
        "admin.js",
        "genealogia_admin.js",
    ):
        assert forbidden not in source


def test_admin_js_no_longer_depends_on_tree_renderer():
    source = _admin_source()
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    assert "window.AdminTreeRenderer" not in source
    assert "const TREE = window.AdminTreeRenderer" not in source
    assert "TREE.render(" not in source


def test_admin_js_no_longer_contains_legacy_tree_adapters():
    source = _admin_source()
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    for forbidden in (
        "showGenealogyTreeFromProtocol",
        "showLocalFamilyTree",
        "GenealogyTreeViewer",
        "showClientTree",
        "TREE.render(",
        "elements.treeModalTitle",
        "elements.treeModal",
        "elements.treeContainer",
        "fetch(`/api/genealogia/${protocolKey}`)",
    ):
        assert forbidden not in source
    assert "AdvancedTreeRenderer.render" not in source


def test_admin_js_no_longer_contains_renderer_implementation():
    source = _admin_source()
    for forbidden in (
        "const TREE_CONFIG",
        "const AdvancedTreeRenderer",
        "const findTreeConnections",
        "const positionTreeNodes",
    ):
        assert forbidden not in source


def test_admin_html_no_longer_loads_unused_tree_renderer():
    html = _admin_html()
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)
    assert "js/tree-renderer.js" not in scripts
    assert "admin.js" in scripts


def test_admin_html_keeps_genealogy_mini_tree_before_admin_js():
    html = _admin_html()
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)
    assert "js/genealogy-mini-tree.js" in scripts
    assert "admin.js" in scripts
    assert scripts.index("js/genealogy-mini-tree.js") < scripts.index("admin.js")


def test_api_header_no_longer_documents_tree_renderer_load_order():
    source = API_JS.read_text(encoding="utf-8")
    assert "tree-renderer.js" not in source
