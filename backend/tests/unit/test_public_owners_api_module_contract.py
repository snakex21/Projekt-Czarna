"""Kontrakt UI modułu `static/wlasciciele/js/api.js` (P2.7 Etap 1).

Moduł `OwnersAPI` jest publiczną mapą/builderem URL-i dla stron właścicieli:
protokół, porównanie protokołów i centrum statystyk. Etap 1 realnie przepina
`protokol.js`, a `compare.html` i `stats.html` przygotowuje pod kolejne etapy.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OWNERS_API_JS = PROJECT_ROOT / "static" / "wlasciciele" / "js" / "api.js"
PROTOKOL_JS = PROJECT_ROOT / "static" / "wlasciciele" / "protokol.js"
PROTOCOL_IMAGES_JS = PROJECT_ROOT / "static" / "wlasciciele" / "js" / "protocol" / "protocol-images.js"
PROTOCOL_GENEALOGY_TREE_JS = PROJECT_ROOT / "static" / "wlasciciele" / "js" / "protocol" / "protocol-genealogy-tree.js"
PROTOKOL_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "protokol.html"
COMPARE_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "compare.html"
STATS_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "stats.html"


def _api_source() -> str:
    if not OWNERS_API_JS.exists():
        pytest.fail(f"Brak pliku {OWNERS_API_JS} - OwnersAPI nie zostało wydzielone")
    return OWNERS_API_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def _scripts(path: Path) -> list[str]:
    html = path.read_text(encoding="utf-8")
    return re.findall(r'<script\s+src="([^"]+)"', html)


def test_owners_api_file_exists():
    assert OWNERS_API_JS.exists()


def test_owners_api_registers_window_namespace():
    source = _api_source()
    assert "window.OwnersAPI" in source
    assert "window.AdminAPI" not in source


def test_owners_api_uses_object_freeze_and_iife():
    source = _api_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_owners_api_public_api_has_expected_endpoint_builders():
    source = _api_source()
    match = re.search(
        r"window\.OwnersAPI\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.OwnersAPI = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"owner", "genealogy", "stats", "protocolScan", "protocolScanSingle", "mapPage"}


def test_owners_api_contains_expected_public_routes():
    source = _api_source()
    assert "/api/wlasciciel/" in source
    assert "/api/genealogia/" in source
    assert "/api/stats" in source
    assert "/protokoly/" in source
    assert "../mapa/mapa.html" in source
    assert ".jpg" in source


def test_owners_api_encodes_dynamic_owner_key():
    source = _api_source()
    assert "encodeURIComponent" in source
    assert re.search(r"encodeURIComponent\s*\(\s*ownerKey\s*\)", source)


def test_owners_api_has_no_fetch_or_dom_side_effects():
    source = _source_no_comments(OWNERS_API_JS)
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


def test_owners_api_header_documents_load_order():
    source = _api_source()
    assert "OwnersAPI" in source
    for token in ("protokol.js", "compare.js", "stats-script.js"):
        assert token in source


def test_public_owner_pages_load_owners_api_before_main_scripts():
    pages = [
        (PROTOKOL_HTML, "protokol.js"),
        (COMPARE_HTML, "compare.js"),
        (STATS_HTML, "stats-script.js"),
    ]
    for html_path, main_script in pages:
        scripts = _scripts(html_path)
        assert "js/api.js" in scripts, f"{html_path.name} nie ładuje js/api.js"
        assert main_script in scripts, f"{html_path.name} nie ładuje {main_script}"
        assert scripts.index("js/api.js") < scripts.index(main_script)


def test_protokol_js_requires_and_aliases_owners_api():
    source = PROTOKOL_JS.read_text(encoding="utf-8")
    assert "window.OwnersAPI" in source
    assert "const API = window.OwnersAPI" in source
    assert "protokol.js wymaga js/api.js załadowanego wcześniej" in source


def test_protokol_js_uses_owners_api_for_owner_fetch():
    source = _source_no_comments(PROTOKOL_JS)
    assert "API.owner(ownerKey)" in source
    assert "fetch(API.owner(ownerKey))" in source
    assert "fetch(`/api/wlasciciel/${ownerKey}`)" not in source
    assert 'fetch("/api/wlasciciel/' not in source
    assert "fetch('/api/wlasciciel/" not in source


def test_protokol_js_uses_owners_api_for_genealogy_fetch():
    source = _source_no_comments(PROTOCOL_GENEALOGY_TREE_JS if PROTOCOL_GENEALOGY_TREE_JS.exists() else PROTOKOL_JS)
    assert "API.genealogy(ownerKey)" in source
    assert "fetch(API.genealogy(ownerKey))" in source
    assert "fetch(`/api/genealogia/${ownerKey}`)" not in source
    assert 'fetch("/api/genealogia/' not in source
    assert "fetch('/api/genealogia/" not in source


def test_protokol_js_uses_owners_api_for_protocol_scan_pages():
    source = _source_no_comments(PROTOCOL_IMAGES_JS if PROTOCOL_IMAGES_JS.exists() else PROTOKOL_JS)
    assert "API.protocolScan(ownerKey, i)" in source
    assert re.search(r"img\.src\s*=\s*API\.protocolScan\s*\(\s*ownerKey\s*,\s*i\s*\)", source)
    assert "const basePath = `/protokoly/${ownerKey}/`" not in source
    assert "`${basePath}${i}.jpg`" not in source


def test_protokol_js_uses_owners_api_for_single_protocol_scan():
    source = _source_no_comments(PROTOCOL_IMAGES_JS if PROTOCOL_IMAGES_JS.exists() else PROTOKOL_JS)
    assert "API.protocolScanSingle(ownerKey)" in source
    assert re.search(r"singleImg\.src\s*=\s*API\.protocolScanSingle\s*\(\s*ownerKey\s*\)", source)
    assert "singleImg.src = `/protokoly/${ownerKey}.jpg`" not in source


def test_protokol_js_no_longer_has_hardcoded_dynamic_endpoints():
    source = _source_no_comments(PROTOKOL_JS)
    for forbidden in (
        "`/api/wlasciciel/${ownerKey}`",
        "`/api/genealogia/${ownerKey}`",
        "`/protokoly/${ownerKey}/`",
        "`/protokoly/${ownerKey}.jpg`",
    ):
        assert forbidden not in source
