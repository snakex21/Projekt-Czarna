"""Ustawienia runtime launchera niezależne od Tkintera.

Moduł wydzielony z ``launcher_app.py`` jako pierwszy, bezpieczny krok
refaktoryzacji. Zachowuje dotychczasowe kontrakty funkcji, ale używa
``launcher.config.paths`` jako jednego źródła prawdy dla ścieżek.
"""

import json
import os

from launcher.config.paths import BACKEND_DIR, LAUNCHER_UI_SETTINGS_FILE
from launcher.utils import get_launcher_setting, set_launcher_setting


def _backend_env_path():
    """Zwraca ścieżkę do backend/.env jako string dla kompatybilności."""
    return str(BACKEND_DIR / ".env")


def _load_local_launcher_ui_settings():
    """Wczytuje lokalne ustawienia UI launchera z pliku JSON."""
    settings_path = str(LAUNCHER_UI_SETTINGS_FILE)
    try:
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"⚠️ Nie udało się wczytać ustawień UI: {e}")
    return {}


def _save_local_launcher_ui_settings(data):
    """Zapisuje lokalne ustawienia UI launchera do pliku JSON."""
    settings_path = str(LAUNCHER_UI_SETTINGS_FILE)
    try:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ Nie udało się zapisać ustawień UI: {e}")
        return False


def get_ui_scale_setting(default=1.0):
    """Pobiera skalę UI z lokalnego pliku lub ustawień launchera."""
    local_settings = _load_local_launcher_ui_settings()
    value = local_settings.get("ui_scale")
    if value is None:
        value = get_launcher_setting("ui_scale", default)

    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(default)

    return max(0.85, min(value, 2.0))


def set_ui_scale_setting(value):
    """Zapisuje skalę UI lokalnie i opcjonalnie do bazy ustawień launchera."""
    try:
        scale = max(0.85, min(float(value), 2.0))
    except (TypeError, ValueError):
        scale = 1.0

    local_settings = _load_local_launcher_ui_settings()
    local_settings["ui_scale"] = scale
    local_ok = _save_local_launcher_ui_settings(local_settings)

    db_ok = set_launcher_setting("ui_scale", str(scale))
    return local_ok or db_ok


def _read_db_engine_from_env():
    """Odczytuje DB_ENGINE z backend/.env lub środowiska."""
    env_path = _backend_env_path()
    db_engine = os.getenv("DB_ENGINE", "").strip().lower()
    if db_engine:
        return db_engine

    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DB_ENGINE="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'").lower()
        except Exception:
            pass

    return ""
