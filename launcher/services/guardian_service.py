"""Logika Strażnika systemu launchera."""

from __future__ import annotations

import os
import sys

from launcher.config.paths import BACKEND_DIR, BASE_DIR


GUARDIAN_CONFIG_PATH = BASE_DIR / ".guardian.env"
CRITICAL_MODULES = ["sql", "logic", "backups", "encoding"]


def load_guardian_config() -> bool:
    """Ładuje ustawienie Strażnika z pliku .guardian.env."""
    if not GUARDIAN_CONFIG_PATH.exists():
        return True
    try:
        with open(GUARDIAN_CONFIG_PATH, "r", encoding="utf-8") as f:
            return f.read().strip() == "1"
    except Exception:
        return True


def save_guardian_config(enabled: bool) -> None:
    """Zapisuje ustawienie Strażnika do pliku .guardian.env."""
    with open(GUARDIAN_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write("1" if enabled else "0")


def health_check_command(module_name: str):
    """Zwraca komendę testu dla modułu Strażnika."""
    if module_name == "sql":
        script = os.path.join(BACKEND_DIR, "tests", "unit", "test_data_integrity.py")
        return [sys.executable, script]

    path_map = {
        "logic": "backend/tests/logic",
        "backups": "backend/tests/health/test_backups.py",
        "encoding": "backend/tests/health/test_encoding.py",
    }
    return [sys.executable, "-m", "pytest", path_map[module_name], "-q"]
