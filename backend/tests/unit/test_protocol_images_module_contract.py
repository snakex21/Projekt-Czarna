"""Kontrakt UI modułu `static/wlasciciele/js/protocol-images.js` (P2.7 Etap 3).

Moduł `ProtocolImages` wydziela z `protokol.js` wyszukiwanie skanów protokołu,
modal obrazu, Panzoom i nawigację między skanami.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_IMAGES_JS = PROJECT_ROOT / "static" / "wlasciciele" / "js" / "protocol" / "protocol-images.js"
PROTOKOL_JS = PROJECT_ROOT / "static" / "wlasciciele" / "protokol.js"
PROTOKOL_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "protokol.html"
COMPARE_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "compare.html"


def _images_source() -> str:
    if not PROTOCOL_IMAGES_JS.exists():
        pytest.fail(f"Brak pliku {PROTOCOL_IMAGES_JS} - ProtocolImages nie został wydzielony")
    return PROTOCOL_IMAGES_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def _scripts(path: Path) -> list[str]:
    html = path.read_text(encoding="utf-8")
    return re.findall(r'<script\s+src="([^"]+)"', html)


def test_protocol_images_file_exists():
    assert PROTOCOL_IMAGES_JS.exists()


def test_protocol_images_registers_window_namespace():
    source = _images_source()
    assert "window.ProtocolImages" in source


def test_protocol_images_uses_object_freeze_and_iife():
    source = _images_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_protocol_images_public_api():
    source = _images_source()
    match = re.search(
        r"window\.ProtocolImages\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.ProtocolImages = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "find", "open", "close", "next", "prev"}


def test_protocol_images_uses_expected_dependencies_and_dom_tokens():
    source = _images_source()
    for token in (
        "window.OwnersAPI",
        "Panzoom",
        "new Image",
        "showOriginalBtn",
        "imageModal",
        "modalImage",
        "closeModalBtn",
        "prevBtn",
        "nextBtn",
        "pageCounter",
    ):
        assert token in source


def test_protocol_images_uses_owners_api_not_hardcoded_protocol_paths():
    source = _source_no_comments(PROTOCOL_IMAGES_JS)
    assert "API.protocolScan(ownerKey, i)" in source
    assert "API.protocolScanSingle(ownerKey)" in source
    for forbidden in (
        "`/protokoly/${ownerKey}/`",
        "`/protokoly/${ownerKey}.jpg`",
    ):
        assert forbidden not in source


def test_protocol_images_renders_polish_ui_labels():
    source = _images_source()
    for token in ("Brak skanów protokołu", "Oczekiwane pliki", "Strona"):
        assert token in source


def test_protokol_and_compare_load_protocol_images_before_main_scripts():
    for html_path, main_script in ((PROTOKOL_HTML, "protokol.js"), (COMPARE_HTML, "compare.js")):
        scripts = _scripts(html_path)
        assert "js/api.js" in scripts
        assert "js/protocol/protocol-images.js" in scripts
        assert scripts.index("js/api.js") < scripts.index("js/protocol/protocol-images.js")
        assert scripts.index("js/protocol/protocol-images.js") < scripts.index(main_script)



def test_protokol_js_requires_aliases_and_uses_protocol_images():
    source = PROTOKOL_JS.read_text(encoding="utf-8")
    assert "window.ProtocolImages" in source
    assert "const IMAGES = window.ProtocolImages" in source
    assert "protokol.js wymaga js/protocol-images.js załadowanego wcześniej" in source
    assert "IMAGES.init" in source
    assert "IMAGES.find()" in source


def test_protokol_js_no_longer_contains_protocol_images_implementation():
    source = _source_no_comments(PROTOKOL_JS)
    for forbidden in (
        "let panzoomInstance",
        "let imageUrls",
        "let currentImageIndex",
        "const findProtocolImages",
        "const finishImageSearch",
        "const openImageModal",
        "const closeImageModal",
        "const updateModalContent",
        "const showNextImage",
        "const showPrevImage",
        "Panzoom(modalImage",
        "new Image()",
    ):
        assert forbidden not in source
