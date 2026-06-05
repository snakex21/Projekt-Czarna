"""Kontrakt UI migracji `compare.js` do publicznych modułów (P2.7 Etap 5A).

Etap 5A nie przebudowuje całej porównywarki. Wymaga, aby `compare.js`
korzystał z istniejących `OwnersAPI` i `OwnersUtils` dla URL-i oraz helperów
już wydzielonych z `protokol.js`.
"""
from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMPARE_JS = PROJECT_ROOT / "static" / "wlasciciele" / "compare.js"
COMPARE_RENDERER_JS = PROJECT_ROOT / "static" / "wlasciciele" / "js" / "compare" / "compare-renderer.js"
COMPARE_INTERACTIONS_JS = PROJECT_ROOT / "static" / "wlasciciele" / "js" / "compare" / "compare-interactions.js"
COMPARE_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "compare.html"


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def _scripts(path: Path) -> list[str]:
    html = path.read_text(encoding="utf-8")
    return re.findall(r'<script\s+src="([^"]+)"', html)


def test_compare_html_loads_public_modules_before_compare_js():
    scripts = _scripts(COMPARE_HTML)
    for script in (
        "js/api.js",
        "js/utils.js",
        "js/protocol/protocol-images.js",
        "js/protocol/protocol-genealogy-tree.js",
        "js/compare/compare-renderer.js",
        "js/compare/compare-interactions.js",
        "compare.js",
    ):
        assert script in scripts
    assert scripts.index("js/api.js") < scripts.index("js/utils.js")
    assert scripts.index("js/utils.js") < scripts.index("js/protocol/protocol-images.js")
    assert scripts.index("js/protocol/protocol-images.js") < scripts.index("js/protocol/protocol-genealogy-tree.js")
    assert scripts.index("js/protocol/protocol-genealogy-tree.js") < scripts.index("js/compare/compare-renderer.js")
    assert scripts.index("js/compare/compare-renderer.js") < scripts.index("js/compare/compare-interactions.js")
    assert scripts.index("js/compare/compare-interactions.js") < scripts.index("compare.js")


def test_compare_renderer_file_exists_and_registers_namespace():
    assert COMPARE_RENDERER_JS.exists()
    source = COMPARE_RENDERER_JS.read_text(encoding="utf-8")
    assert "window.CompareRenderer" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_compare_renderer_public_api_and_dependencies():
    source = COMPARE_RENDERER_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.CompareRenderer\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.CompareRenderer = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"columnTemplate", "fillPlotSection", "alignCardHeights"}
    assert "window.OwnersUtils" in source
    assert "UTILS.generateFractionHTML" in source


def test_compare_interactions_file_exists_and_registers_namespace():
    assert COMPARE_INTERACTIONS_JS.exists()
    source = COMPARE_INTERACTIONS_JS.read_text(encoding="utf-8")
    assert "window.CompareInteractions" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_compare_interactions_public_api_and_dependencies():
    source = COMPARE_INTERACTIONS_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.CompareInteractions\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.CompareInteractions = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"setupHeaderMapLinks", "bindColumnMapLinks", "createPDF"}
    assert "window.OwnersAPI" in source
    assert "API.mapPage()" in source
    assert "html2pdf" in source


def test_compare_js_requires_alias_and_uses_compare_renderer():
    source = COMPARE_JS.read_text(encoding="utf-8")
    assert "window.CompareRenderer" in source
    assert "const RENDERER = window.CompareRenderer" in source
    assert "compare.js wymaga js/compare-renderer.js załadowanego wcześniej" in source
    for token in (
        "RENDERER.columnTemplate",
        "RENDERER.fillPlotSection",
        "RENDERER.alignCardHeights",
    ):
        assert token in source


def test_compare_js_requires_alias_and_uses_compare_interactions():
    source = COMPARE_JS.read_text(encoding="utf-8")
    assert "window.CompareInteractions" in source
    assert "const INTERACTIONS = window.CompareInteractions" in source
    assert "compare.js wymaga js/compare-interactions.js załadowanego wcześniej" in source
    for token in (
        "INTERACTIONS.setupHeaderMapLinks",
        "INTERACTIONS.bindColumnMapLinks",
        "INTERACTIONS.createPDF",
    ):
        assert token in source


def test_compare_js_no_longer_contains_renderer_implementation():
    source = _source_no_comments(COMPARE_JS)
    for forbidden in (
        "const columnTemplate",
        "const fillPlotSection",
        "const alignCardHeights",
        "generateFractionHTML(d.numer_domu)",
        "generateFractionHTML(p.nazwa_lub_numer)",
    ):
        assert forbidden not in source


def test_compare_js_no_longer_contains_interactions_implementation():
    source = _source_no_comments(COMPARE_JS)
    for forbidden in (
        "const ensureHtml2Pdf",
        "const createPDF",
        "highlightTopOwners",
        "highlightByIds",
        "html2pdf().from",
        "window.location.href = `${mapUrl}",
    ):
        assert forbidden not in source


def test_compare_js_requires_and_aliases_public_modules():
    source = COMPARE_JS.read_text(encoding="utf-8")
    assert "window.OwnersAPI" in source
    assert "window.OwnersUtils" in source
    assert "window.ProtocolImages" in source
    assert "window.ProtocolGenealogyTree" in source
    assert "window.CompareRenderer" in source
    assert "window.CompareInteractions" in source
    assert "const API = window.OwnersAPI" in source
    assert "const UTILS = window.OwnersUtils" in source
    assert "const IMAGES = window.ProtocolImages" in source
    assert "const TREE = window.ProtocolGenealogyTree" in source
    assert "const RENDERER = window.CompareRenderer" in source
    assert "const INTERACTIONS = window.CompareInteractions" in source
    assert "compare.js wymaga js/api.js załadowanego wcześniej" in source
    assert "compare.js wymaga js/utils.js załadowanego wcześniej" in source
    assert "compare.js wymaga js/protocol-images.js załadowanego wcześniej" in source
    assert "compare.js wymaga js/protocol-genealogy-tree.js załadowanego wcześniej" in source
    assert "compare.js wymaga js/compare-renderer.js załadowanego wcześniej" in source
    assert "compare.js wymaga js/compare-interactions.js załadowanego wcześniej" in source


def test_compare_js_uses_owners_api_for_dynamic_urls():
    source = _source_no_comments(COMPARE_JS)
    interactions_source = _source_no_comments(COMPARE_INTERACTIONS_JS)
    assert "API.owner(key)" in source
    assert "API.mapPage()" in interactions_source


def test_compare_js_uses_owners_utils_for_fraction_helper():
    source = _source_no_comments(COMPARE_RENDERER_JS)
    assert "UTILS.generateFractionHTML" in source
    assert "const generateFractionHTML = UTILS.generateFractionHTML" in source
    assert "const generateFractionHTML = (txt)" not in source


def test_compare_js_no_longer_hardcodes_migrated_dynamic_urls():
    source = _source_no_comments(COMPARE_JS)
    for forbidden in (
        "../mapa/mapa.html",
        "`/protokoly/${key}/`",
        "`/protokoly/${key}.jpg`",
        "`/api/genealogia/${data.unikalny_klucz}`",
        "`/api/wlasciciel/${key}`",
    ):
        assert forbidden not in source


def test_compare_js_delegates_genealogy_tree_to_protocol_genealogy_tree():
    source = _source_no_comments(COMPARE_JS)
    assert "TREE.init" in source
    assert "showTreeBtn: treeBtn" in source
    assert "ownerKey: data.unikalny_klucz" in source
    for forbidden in (
        "const drawGenealogyTree",
        "const renderTreeNode",
        "const getParentRole",
        "const getGrandparentRole",
        "fetch(API.genealogy(data.unikalny_klucz))",
    ):
        assert forbidden not in source


def test_compare_js_delegates_protocol_images_to_protocol_images_module():
    source = _source_no_comments(COMPARE_JS)
    assert "IMAGES.init" in source
    assert "showOriginalBtn: origBtn" in source
    assert "ownerKey: data.unikalny_klucz" in source
    for forbidden in (
        "let panzoomInst",
        "let imgs",
        "let idx",
        "const openModal",
        "const closeModal =",
        "const updateModal",
        "const findProtocolImages",
        "new Image()",
        "Panzoom(modalImg",
        "API.protocolScan(key, i)",
        "API.protocolScanSingle(key)",
    ):
        assert forbidden not in source
