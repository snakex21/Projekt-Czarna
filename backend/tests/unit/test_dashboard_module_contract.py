"""Kontrakt UI modułu `static/admin/js/dashboard.js` (P2.5 Etap 5).

Moduł pulpitu przejmuje statystyki, zegar, backup i szybkie akcje z `admin.js`.
Nie dotyka CRUD genealogii ani właścicieli; akcja `add-owner` korzysta z
`window.AdminOwnerModal.open` (Etap 6).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_JS = PROJECT_ROOT / "static" / "admin" / "js" / "dashboard.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


def _dashboard_source() -> str:
    if not DASHBOARD_JS.exists():
        pytest.fail(f"Brak pliku {DASHBOARD_JS} - moduł pulpitu nie został wydzielony")
    return DASHBOARD_JS.read_text(encoding="utf-8")


def _dashboard_source_no_comments() -> str:
    source = _dashboard_source()
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def _admin_source() -> str:
    return ADMIN_JS.read_text(encoding="utf-8")


def _admin_html() -> str:
    return ADMIN_HTML.read_text(encoding="utf-8")


def test_dashboard_module_registers_window_namespace():
    source = _dashboard_source()
    assert "window.AdminDashboard" in source


def test_dashboard_module_uses_object_freeze_and_iife():
    source = _dashboard_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source


def test_dashboard_module_public_api_has_five_methods():
    source = _dashboard_source()
    match = re.search(r"window\.AdminDashboard\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)", source)
    assert match, "Brak window.AdminDashboard = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"load", "tick", "startClock", "downloadBackup", "handleQuickAction"}


def test_dashboard_module_uses_admin_api_and_notifications():
    source = _dashboard_source()
    assert "window.AdminAPI" in source
    assert "window.AdminNotifications" in source
    assert "API.stats" in source
    assert "API.genealogy" in source
    assert "API.demography" in source
    assert "API.backup" in source
    assert "showToast" in source


def test_dashboard_module_updates_expected_dom_ids():
    source = _dashboard_source()
    for element_id in (
        "statOwners",
        "statObjects",
        "statGenealogy",
        "statDemography",
        "currentDate",
        "currentTime",
        "modalTitle",
        "modalBody",
        "modalSave",
        "modalOverlay",
    ):
        assert element_id in source


def test_dashboard_module_handles_quick_actions():
    source = _dashboard_source()
    for action in ("add-owner", "view-map", "export-data", "system-info"):
        assert action in source
    assert "window.AdminOwnerModal.open" in source


def test_dashboard_module_has_system_info_modal_content():
    source = _dashboard_source()
    assert "Informacje o Systemie" in source
    assert "System Zarządzania Mapą Katastralną" in source
    assert "Maksymilian Augustyn" in source


def test_dashboard_module_isolated_from_other_ui_modules():
    source = _dashboard_source_no_comments()
    for forbidden in (
        "objects.js",
        "owners.js",
        "demography.js",
        "tree-renderer.js",
        "admin.js",
        "genealogia_admin.js",
    ):
        assert forbidden not in source


def test_admin_js_requires_and_aliases_dashboard_module():
    source = _admin_source()
    assert "window.AdminDashboard" in source
    assert "const DASH = window.AdminDashboard" in source


def test_admin_js_uses_dashboard_alias():
    source = _admin_source()
    assert "DASH.startClock()" in source
    assert "DASH.load()" in source
    assert "DASH.downloadBackup()" in source
    assert "DASH.handleQuickAction(action" in source


def test_admin_js_no_longer_contains_dashboard_implementation():
    source = _admin_source()
    for forbidden in (
        "const loadDashboardData",
        "const updateDateTime",
        "const downloadBackup",
        "const handleQuickAction",
        "const showSystemInfo",
    ):
        assert forbidden not in source


def test_admin_html_loads_dashboard_before_admin_js():
    html = _admin_html()
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)
    assert "js/dashboard.js" in scripts
    assert "admin.js" in scripts
    assert scripts.index("js/dashboard.js") < scripts.index("admin.js")


def test_admin_html_loads_dashboard_after_dependencies():
    html = _admin_html()
    dash_pos = html.find("js/dashboard.js")
    assert dash_pos > 0
    for dep in ("js/api.js", "js/notifications.js"):
        dep_pos = html.find(dep)
        assert dep_pos > 0
        assert dep_pos < dash_pos


def test_api_header_documents_dashboard_load_order():
    source = API_JS.read_text(encoding="utf-8")
    assert "dashboard.js" in source
