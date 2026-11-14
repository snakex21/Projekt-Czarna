"""Domyślna konfiguracja bezpieczeństwa (backend/config.py) w czystym procesie.

Każdy przypadek importuje ``backend.config`` w osobnym procesie z kontrolowanym
środowiskiem, bo konfiguracja jest czytana raz przy imporcie.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

PROBE = (
    "import json; from backend import config as c; "
    "print('@@' + json.dumps({'auth': c.ADMIN_AUTH_ENABLED, 'key': c.SECRET_KEY, "
    "'src': c.SECRET_KEY_SOURCE, 'engine': c.DB_ENGINE, 'dbpw': c.DB_PASSWORD, "
    "'hash': c.ADMIN_PASSWORD_HASH}))"
)

CLEARED = (
    "SECRET_KEY", "FLASK_SECRET_KEY", "ADMIN_AUTH_ENABLED", "ADMIN_AUTH_INSECURE_DISABLE",
    "ADMIN_PASSWORD_HASH", "DB_ENGINE", "DB_PASSWORD", "PRODUCTION", "ENVIRONMENT",
    "LAUNCHER_DB_PASSWORD", "SECRET_KEY_FILE", "DB_PATH",
)


def _probe(tmp_path, **env_overrides):
    env = {k: v for k, v in os.environ.items() if k not in CLEARED}
    env["SECRET_KEY_FILE"] = str(tmp_path / "secret_key")
    env["DB_PATH"] = str(tmp_path / "probe.db")
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(env_overrides)
    # Proces startuje w katalogu tmp; repozytorium jest dostępne przez PYTHONPATH.
    # Lokalny backend/.env wpływałby na wynik - wtedy test jest pomijany (fixture niżej).
    env["PYTHONPATH"] = str(ROOT)
    out = subprocess.run(
        [sys.executable, "-c", PROBE], cwd=tmp_path, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert out.returncode == 0, out.stderr
    line = [l for l in out.stdout.splitlines() if l.startswith("@@")][-1]
    return json.loads(line[2:])


@pytest.fixture(autouse=True)
def _no_dev_env_file():
    if (ROOT / "backend" / ".env").exists() or (ROOT / "backend" / ".postgres.env").exists():
        pytest.skip("backend/.env istnieje lokalnie - test domyślnej konfiguracji pominięty")


def test_defaults_are_secure(tmp_path):
    cfg = _probe(tmp_path)
    assert cfg["auth"] is True
    assert cfg["hash"] == ""          # brak domyślnego hasła admina
    assert cfg["dbpw"] == ""          # brak domyślnego hasła bazy
    assert cfg["engine"] == "sqlite"  # świeży klon działa bez PostgreSQL


def test_secret_key_generated_outside_repo_and_reused(tmp_path):
    first = _probe(tmp_path)
    key_file = tmp_path / "secret_key"
    assert key_file.is_file()
    assert first["src"].startswith("generated:")
    assert len(first["key"]) >= 32
    assert not key_file.resolve().is_relative_to(ROOT.resolve())
    second = _probe(tmp_path)
    assert second["key"] == first["key"]
    assert second["src"].startswith("file:")


@pytest.mark.parametrize("weak", ["dev-secret-change-me", "change-me-once", "wygeneruj-losowy-sekretny-klucz"])
def test_placeholder_secret_keys_are_ignored(tmp_path, weak):
    cfg = _probe(tmp_path, FLASK_SECRET_KEY=weak)
    assert cfg["key"] != weak
    assert cfg["src"].startswith("generated:")


def test_env_secret_key_takes_precedence(tmp_path):
    cfg = _probe(tmp_path, FLASK_SECRET_KEY="k" * 48)
    assert cfg["key"] == "k" * 48
    assert not (tmp_path / "secret_key").exists()


def test_secret_key_file_inside_repo_is_refused(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in CLEARED}
    env.update(SECRET_KEY_FILE=str(ROOT / "data" / "secret_key"), DB_PATH=str(tmp_path / "x.db"), PYTHONPATH=str(ROOT))
    out = subprocess.run([sys.executable, "-c", PROBE], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode != 0
    assert "repozytorium" in out.stderr
    assert not (ROOT / "data" / "secret_key").exists()


def test_legacy_auth_disabled_flag_alone_does_not_disable_auth(tmp_path):
    """Stare .env z launchera miały ADMIN_AUTH_ENABLED=0 - to już nie wyłącza auth."""
    assert _probe(tmp_path, ADMIN_AUTH_ENABLED="0")["auth"] is True


def test_auth_can_be_disabled_only_with_explicit_insecure_flag(tmp_path):
    assert _probe(tmp_path, ADMIN_AUTH_ENABLED="0", ADMIN_AUTH_INSECURE_DISABLE="1")["auth"] is False


def test_auth_cannot_be_disabled_in_production(tmp_path):
    cfg = _probe(tmp_path, ADMIN_AUTH_ENABLED="0", ADMIN_AUTH_INSECURE_DISABLE="1", PRODUCTION="1")
    assert cfg["auth"] is True
