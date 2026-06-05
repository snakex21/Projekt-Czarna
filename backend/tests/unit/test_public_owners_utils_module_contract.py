"""Kontrakt UI modułu `static/wlasciciele/js/utils.js` (P2.7 Etap 2).

Moduł `OwnersUtils` wydziela helpery formatowania i sanityzacji z `protokol.js`.
Na tym etapie realnie przepinany jest `protokol.js`, a `compare.html` i
`stats.html` dostają właściwą kolejność ładowania pod kolejne etapy.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OWNERS_UTILS_JS = PROJECT_ROOT / "static" / "wlasciciele" / "js" / "utils.js"
PROTOKOL_JS = PROJECT_ROOT / "static" / "wlasciciele" / "protokol.js"
PROTOKOL_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "protokol.html"
COMPARE_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "compare.html"
STATS_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "stats.html"


def _utils_source() -> str:
    if not OWNERS_UTILS_JS.exists():
        pytest.fail(f"Brak pliku {OWNERS_UTILS_JS} - OwnersUtils nie zostało wydzielone")
    return OWNERS_UTILS_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def _scripts(path: Path) -> list[str]:
    html = path.read_text(encoding="utf-8")
    return re.findall(r'<script\s+src="([^"]+)"', html)


def test_owners_utils_file_exists():
    assert OWNERS_UTILS_JS.exists()


def test_owners_utils_registers_window_namespace():
    source = _utils_source()
    assert "window.OwnersUtils" in source
    assert "window.AdminUtils" not in source


def test_owners_utils_uses_object_freeze_and_iife():
    source = _utils_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_owners_utils_public_api_has_expected_helpers():
    source = _utils_source()
    match = re.search(
        r"window\.OwnersUtils\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.OwnersUtils = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {
        "escapeHtml",
        "normalizeText",
        "generateFractionHTML",
        "formatArea",
        "formatLength",
        "formatDate",
    }


def test_owners_utils_contains_expected_logic_tokens():
    source = _utils_source()
    for token in (
        "function escapeHtml",
        "function normalizeText",
        "function generateFractionHTML",
        "function formatArea",
        "function formatLength",
        "function formatDate",
        "&amp;",
        "fraction",
        "whole-number",
        "m²",
        "ha",
        "km",
        "toLocaleDateString('pl-PL')",
    ):
        assert token in source


def test_owners_utils_has_no_fetch_or_dom_side_effects():
    source = _source_no_comments(OWNERS_UTILS_JS)
    for forbidden in (
        "fetch(",
        "new Image(",
        "document.",
        "addEventListener",
        "querySelector",
        "getElementById",
        "innerHTML",
    ):
        assert forbidden not in source


def test_public_owner_pages_load_utils_after_api_before_main_scripts():
    pages = [
        (PROTOKOL_HTML, "protokol.js"),
        (COMPARE_HTML, "compare.js"),
        (STATS_HTML, "stats-script.js"),
    ]
    for html_path, main_script in pages:
        scripts = _scripts(html_path)
        assert "js/api.js" in scripts, f"{html_path.name} nie ładuje js/api.js"
        assert "js/utils.js" in scripts, f"{html_path.name} nie ładuje js/utils.js"
        assert main_script in scripts, f"{html_path.name} nie ładuje {main_script}"
        assert scripts.index("js/api.js") < scripts.index("js/utils.js")
        assert scripts.index("js/utils.js") < scripts.index(main_script)


def test_protokol_js_requires_aliases_owners_utils():
    source = PROTOKOL_JS.read_text(encoding="utf-8")
    assert "window.OwnersUtils" in source
    assert "const UTILS = window.OwnersUtils" in source
    assert "protokol.js wymaga js/utils.js załadowanego wcześniej" in source
    for token in (
        "UTILS.escapeHtml",
        "UTILS.normalizeText",
        "UTILS.generateFractionHTML",
        "UTILS.formatArea",
        "UTILS.formatLength",
        "UTILS.formatDate",
    ):
        assert token in source


def test_protokol_js_no_longer_defines_moved_helpers():
    source = _source_no_comments(PROTOKOL_JS)
    for forbidden in (
        "const formatArea",
        "const formatLength",
        "const formatDate",
        "const generateFractionHTML",
        "const normalizeText",
        "const escapeHtml",
    ):
        assert forbidden not in source


def test_owners_utils_header_documents_load_order():
    source = _utils_source()
    assert "OwnersUtils" in source
    for token in ("js/api.js", "protokol.js", "compare.js", "stats-script.js"):
        assert token in source
