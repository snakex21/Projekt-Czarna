"""Kontrakt UI modułu `static/admin/js/owner-modal.js` (P2.5 Etap 6).

Moduł przejmuje formularz dodawania/edycji właściciela oraz edytor działek
z `admin.js`. Lista/karty właścicieli zostają w `owners.js`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OWNER_MODAL_JS = PROJECT_ROOT / "static" / "admin" / "js" / "owner-modal.js"
OWNERS_JS = PROJECT_ROOT / "static" / "admin" / "js" / "owners.js"
DASHBOARD_JS = PROJECT_ROOT / "static" / "admin" / "js" / "dashboard.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


def _owner_modal_source() -> str:
    if not OWNER_MODAL_JS.exists():
        pytest.fail(f"Brak pliku {OWNER_MODAL_JS} - modal właściciela nie został wydzielony")
    return OWNER_MODAL_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def test_owner_modal_registers_window_namespace():
    source = _owner_modal_source()
    assert "window.AdminOwnerModal" in source


def test_owner_modal_uses_object_freeze_and_iife():
    source = _owner_modal_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source


def test_owner_modal_public_api_has_three_methods():
    source = _owner_modal_source()
    match = re.search(r"window\.AdminOwnerModal\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)", source)
    assert match, "Brak window.AdminOwnerModal = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"open", "save", "populate"}


def test_owner_modal_uses_expected_dependencies():
    source = _owner_modal_source()
    assert "window.AdminAPI" in source
    assert "window.AdminNotifications" in source
    assert "window.AdminOwners" in source
    assert "window.AdminDashboard" in source
    assert "API.owners" in source
    assert "API.allObjects" in source
    assert "showToast" in source


def test_owner_modal_contains_owner_form_and_parcel_editor():
    source = _owner_modal_source()
    for token in (
        "ownerForm",
        "parcelEditorContainer",
        "assigned-real",
        "available-real",
        "assigned-protocol",
        "available-protocol",
        "dzialki_rzeczywiste_ids",
        "dzialki_protokol_ids",
    ):
        assert token in source


def test_owner_modal_filters_non_parcel_categories():
    source = _owner_modal_source()
    for category in ("budynek", "kapliczka", "obiekt_specjalny"):
        assert category in source


def test_owner_modal_handles_post_and_put():
    source = _owner_modal_source()
    assert "method = id ? 'PUT' : 'POST'" in source or 'method = id ? "PUT" : "POST"' in source
    assert "JSON.stringify(data)" in source


def test_owner_modal_isolated_from_other_ui_files():
    source = _source_no_comments(OWNER_MODAL_JS)
    for forbidden in (
        "objects.js",
        "owners.js",
        "dashboard.js",
        "admin.js",
        "genealogia_admin.js",
    ):
        assert forbidden not in source


def test_owners_js_uses_owner_modal_module_for_edit():
    source = OWNERS_JS.read_text(encoding="utf-8")
    assert "window.AdminOwnerModal.open" in source
    assert "window.openOwnerModal" not in source


def test_dashboard_js_uses_owner_modal_module_for_quick_action():
    source = DASHBOARD_JS.read_text(encoding="utf-8")
    assert "window.AdminOwnerModal.open" in source
    assert "window.openOwnerModal" not in source


def test_admin_js_requires_and_aliases_owner_modal():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "window.AdminOwnerModal" in source
    assert "const OWNER_MODAL = window.AdminOwnerModal" in source


def test_admin_js_no_longer_contains_owner_modal_implementation():
    source = ADMIN_JS.read_text(encoding="utf-8")
    for forbidden in (
        "window.openOwnerModal",
        "const populateAndSetupParcelEditor",
        "const createOptions",
        "const saveOwner",
        "ownerForm",
        "parcelEditorContainer",
    ):
        assert forbidden not in source


def test_admin_js_uses_owner_modal_alias_for_add_button():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "OWNER_MODAL.open()" in source


def test_admin_html_loads_owner_modal_before_owners_dashboard_and_admin():
    html = ADMIN_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)
    for script in ("js/owner-modal.js", "js/owners.js", "js/dashboard.js", "admin.js"):
        assert script in scripts
    assert scripts.index("js/owner-modal.js") < scripts.index("js/owners.js")
    assert scripts.index("js/owner-modal.js") < scripts.index("js/dashboard.js")
    assert scripts.index("js/owner-modal.js") < scripts.index("admin.js")


def test_api_header_documents_owner_modal_load_order():
    source = API_JS.read_text(encoding="utf-8")
    assert "owner-modal.js" in source
