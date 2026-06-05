"""Kontrakt UI modułu `static/wlasciciele/js/protocol-genealogy-tree.js` (P2.7 Etap 4).

Moduł `ProtocolGenealogyTree` wydziela z `protokol.js` pobieranie,
renderowanie i obsługę dialogu drzewa genealogicznego protokołu.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TREE_JS = PROJECT_ROOT / "static" / "wlasciciele" / "js" / "protocol" / "protocol-genealogy-tree.js"
PROTOKOL_JS = PROJECT_ROOT / "static" / "wlasciciele" / "protokol.js"
PROTOKOL_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "protokol.html"
COMPARE_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "compare.html"


def _tree_source() -> str:
    if not TREE_JS.exists():
        pytest.fail(f"Brak pliku {TREE_JS} - ProtocolGenealogyTree nie został wydzielony")
    return TREE_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def _scripts(path: Path) -> list[str]:
    html = path.read_text(encoding="utf-8")
    return re.findall(r'<script\s+src="([^"]+)"', html)


def test_protocol_genealogy_tree_file_exists():
    assert TREE_JS.exists()


def test_protocol_genealogy_tree_registers_window_namespace():
    source = _tree_source()
    assert "window.ProtocolGenealogyTree" in source


def test_protocol_genealogy_tree_uses_object_freeze_and_iife():
    source = _tree_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_protocol_genealogy_tree_public_api():
    source = _tree_source()
    match = re.search(
        r"window\.ProtocolGenealogyTree\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.ProtocolGenealogyTree = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "load", "render", "open", "close"}


def test_protocol_genealogy_tree_uses_expected_dependencies_and_dom_tokens():
    source = _tree_source()
    for token in (
        "window.OwnersAPI",
        "showTreeBtn",
        "treeDialog",
        "closeTreeBtn",
        "treeContainer",
    ):
        assert token in source


def test_protocol_genealogy_tree_uses_owners_api_not_hardcoded_genealogy_path():
    source = _source_no_comments(TREE_JS)
    assert "API.genealogy(ownerKey)" in source
    assert "/api/genealogia" not in source


def test_protocol_genealogy_tree_renders_polish_ui_labels():
    source = _tree_source()
    for token in (
        "Ładowanie...",
        "Pokaż drzewo genealogiczne",
        "Nie udało się załadować drzewa genealogicznego",
        "Brak danych genealogicznych do wyświetlenia",
    ):
        assert token in source


def test_protokol_and_compare_load_protocol_genealogy_tree_before_main_scripts():
    for html_path, main_script in ((PROTOKOL_HTML, "protokol.js"), (COMPARE_HTML, "compare.js")):
        scripts = _scripts(html_path)
        assert "js/api.js" in scripts
        assert "js/protocol/protocol-images.js" in scripts
        assert "js/protocol/protocol-genealogy-tree.js" in scripts
        assert main_script in scripts
        assert scripts.index("js/api.js") < scripts.index("js/protocol/protocol-genealogy-tree.js")
        assert scripts.index("js/protocol/protocol-images.js") < scripts.index("js/protocol/protocol-genealogy-tree.js")
        assert scripts.index("js/protocol/protocol-genealogy-tree.js") < scripts.index(main_script)


def test_protokol_js_requires_alias_and_uses_protocol_genealogy_tree():
    source = PROTOKOL_JS.read_text(encoding="utf-8")
    assert "window.ProtocolGenealogyTree" in source
    assert "const TREE = window.ProtocolGenealogyTree" in source
    assert "protokol.js wymaga js/protocol-genealogy-tree.js załadowanego wcześniej" in source
    assert "TREE.init" in source


def test_protokol_js_no_longer_contains_genealogy_tree_implementation():
    source = _source_no_comments(PROTOKOL_JS)
    for forbidden in (
        "const loadGenealogyTree",
        "const drawGenealogyTree",
        "fetch(API.genealogy(ownerKey))",
        "const renderTreeNode",
        "const getParentRole",
        "const getGrandparentRole",
    ):
        assert forbidden not in source
