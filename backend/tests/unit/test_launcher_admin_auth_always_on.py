"""Launcher: logowanie admina jest zawsze włączone (v2.0.0).

Dawny przełącznik "Włącz wymaganie logowania" nie działał, bo backend
wymaga do wyłączenia także ADMIN_AUTH_INSECURE_DISABLE=1. Launcher nie
zmienia już ADMIN_AUTH_ENABLED, tylko pokazuje stan i instrukcję.
"""

from launcher.services import admin_config_service as svc


def test_apply_admin_settings_never_touches_auth_flag():
    env = {"ADMIN_AUTH_ENABLED": "1", "ADMIN_USERNAME": "admin"}
    changed = svc.apply_admin_settings(env, "admin", "")
    assert changed is False
    assert env["ADMIN_AUTH_ENABLED"] == "1"

    env = {"ADMIN_AUTH_ENABLED": "1", "ADMIN_USERNAME": "admin"}
    assert svc.apply_admin_settings(env, "kustosz", "") is True
    assert env["ADMIN_USERNAME"] == "kustosz"
    assert env["ADMIN_AUTH_ENABLED"] == "1"


def test_password_is_stored_only_as_hash():
    env = {}
    assert svc.apply_admin_settings(env, "admin", "Bardzo-Dlugie-Haslo-123") is True
    assert env["ADMIN_PASSWORD_HASH"]
    assert "Bardzo-Dlugie-Haslo-123" not in env["ADMIN_PASSWORD_HASH"]
    assert "ADMIN_AUTH_ENABLED" not in env


def test_status_reflects_backend_rule():
    assert not svc.auth_insecurely_disabled({})
    # Samo ADMIN_AUTH_ENABLED=0 nie wyłącza logowania (tak jak w backend/config.py).
    assert not svc.auth_insecurely_disabled({"ADMIN_AUTH_ENABLED": "0"})
    assert svc.auth_insecurely_disabled({"ADMIN_AUTH_ENABLED": "0", "ADMIN_AUTH_INSECURE_DISABLE": "1"})
    assert "zawsze włączone" in svc.auth_status_text({"ADMIN_AUTH_ENABLED": "0"})
    assert "WYŁĄCZONE" in svc.auth_status_text({"ADMIN_AUTH_ENABLED": "0", "ADMIN_AUTH_INSECURE_DISABLE": "1"})


def test_hint_names_both_required_variables():
    assert "ADMIN_AUTH_ENABLED=0" in svc.INSECURE_DISABLE_HINT
    assert "ADMIN_AUTH_INSECURE_DISABLE=1" in svc.INSECURE_DISABLE_HINT


def test_env_file_keeps_manual_insecure_flag_and_defaults_to_enabled():
    plain = svc.format_env_content({}, sqlite_backend_env=True, sqlite_mode=True)
    assert "ADMIN_AUTH_ENABLED=1" in plain
    assert "ADMIN_AUTH_INSECURE_DISABLE" not in plain

    manual = {"ADMIN_AUTH_ENABLED": "0", "ADMIN_AUTH_INSECURE_DISABLE": "1"}
    for sqlite_backend_env in (True, False):
        text = svc.format_env_content(manual, sqlite_backend_env=sqlite_backend_env, sqlite_mode=True)
        assert "ADMIN_AUTH_ENABLED=0" in text
        assert "ADMIN_AUTH_INSECURE_DISABLE=1\n" in text


def test_ui_has_no_auth_toggle():
    import inspect

    from launcher.ui import admin_settings, env_editor

    for module in (admin_settings, env_editor):
        src = inspect.getsource(module)
        assert "Włącz wymaganie logowania" not in src
        assert "Włącz logowanie administratora" not in src
        assert 'updates["ADMIN_AUTH_ENABLED"]' not in src
