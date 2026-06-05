"""Kontrakt UI modułu `static/admin/js/auth.js` (P2.5 Etap 12).

Moduł przejmuje sprawdzanie statusu auth, logowanie i wylogowanie z `admin.js`.
Shell panelu (`showLoginScreen`, `showAdminPanel`, dashboard) pozostaje w `admin.js`
i jest wywoływany przez callbacki.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
AUTH_JS = PROJECT_ROOT / "static" / "admin" / "js" / "auth.js"
ADMIN_JS = PROJECT_ROOT / "static" / "admin" / "admin.js"
ADMIN_HTML = PROJECT_ROOT / "static" / "admin" / "admin.html"
API_JS = PROJECT_ROOT / "static" / "admin" / "js" / "api.js"


def _auth_source() -> str:
    if not AUTH_JS.exists():
        pytest.fail(f"Brak pliku {AUTH_JS} - moduł auth nie został wydzielony")
    return AUTH_JS.read_text(encoding="utf-8")


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def test_auth_file_exists():
    assert AUTH_JS.exists()


def test_auth_registers_window_namespace():
    source = _auth_source()
    assert "window.AdminAuth" in source


def test_auth_uses_object_freeze_and_iife():
    source = _auth_source()
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source


def test_auth_public_api_has_init_check_login_logout():
    source = _auth_source()
    match = re.search(r"window\.AdminAuth\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)", source)
    assert match, "Brak window.AdminAuth = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "checkAuth", "login", "logout"}


def test_auth_uses_expected_dependencies_and_endpoints():
    source = _auth_source()
    assert "window.AdminAPI" in source
    assert "window.AdminNotifications" in source
    assert "API.authStatus" in source
    assert "API.login" in source
    assert "API.logout" in source
    assert "showToast" in source
    assert "/api/admin/auth-status" not in source
    assert "/api/admin/login" not in source
    assert "/api/admin/logout" not in source


def test_auth_preserves_local_storage_contract():
    source = _auth_source()
    for token in (
        "localStorage.getItem('adminLoggedIn')",
        "localStorage.setItem('adminLoggedIn', 'true')",
        "localStorage.removeItem('adminLoggedIn')",
    ):
        assert token in source


def test_auth_handles_expected_dom_and_callbacks():
    source = _auth_source()
    for token in (
        "loginForm",
        "loginError",
        "logoutBtn",
        "login",
        "password",
        "showLoginScreen",
        "showAdminPanel",
    ):
        assert token in source
    source_no_comments = _source_no_comments(AUTH_JS)
    assert "DASH" not in source_no_comments
    assert "window.AdminDashboard" not in source_no_comments


def test_auth_login_posts_expected_payload_and_logout_clears_state():
    source = _auth_source()
    assert "method: 'POST'" in source or 'method: "POST"' in source
    assert "Content-Type" in source
    assert "application/json" in source
    assert "JSON.stringify" in source
    assert "username" in source
    assert "password" in source
    assert "data.status === 'ok'" in source or 'data.status === "ok"' in source
    assert "confirm(" in source


def test_admin_html_loads_auth_after_dependencies_before_admin_js():
    html = ADMIN_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r'<script\s+src="([^"]+)"', html)
    for script in ("js/api.js", "js/notifications.js", "js/auth.js", "admin.js"):
        assert script in scripts
    assert scripts.index("js/api.js") < scripts.index("js/auth.js")
    assert scripts.index("js/notifications.js") < scripts.index("js/auth.js")
    assert scripts.index("js/auth.js") < scripts.index("admin.js")


def test_admin_js_requires_aliases_and_uses_auth_module():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "window.AdminAuth" in source
    assert "const AUTH = window.AdminAuth" in source
    assert "admin.js wymaga js/auth.js załadowanego wcześniej" in source
    assert "AUTH.init" in source
    assert "AUTH.checkAuth()" in source
    assert "AUTH.login" in source
    assert "AUTH.logout()" in source


def test_admin_js_no_longer_contains_auth_implementation():
    source = _source_no_comments(ADMIN_JS)
    for forbidden in (
        "let currentUser",
        "const checkAuth",
        "const handleLogin",
        "const handleLogout",
        "localStorage.getItem('adminLoggedIn')",
        "localStorage.setItem('adminLoggedIn'",
        "localStorage.removeItem('adminLoggedIn')",
        "fetch(API.authStatus",
        "fetch(API.login",
        "fetch(API.logout",
    ):
        assert forbidden not in source


def test_admin_js_keeps_shell_callbacks_for_auth():
    source = ADMIN_JS.read_text(encoding="utf-8")
    assert "const showLoginScreen" in source
    assert "const showAdminPanel" in source
    assert "DASH.load()" in source


def test_api_header_documents_auth_load_order():
    source = API_JS.read_text(encoding="utf-8")
    assert "auth.js" in source
