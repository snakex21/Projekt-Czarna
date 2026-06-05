"""Środowisko i komendy subprocess dla narzędzi launchera."""

import os
import sys
from typing import Any, Dict

from ..config.paths import BACKEND_DIR
from .env_config import _detect_sqlite_mode, _read_backend_env_value, read_env_config


__all__ = ["prepare_process_env", "prepare_command"]


def prepare_process_env(active_location_name: str = None, read_env_config_func=None) -> Dict[str, str]:

    """

    Przygotowuje słownik zmiennych środowiskowych dla procesu.

    Args:

        active_location_name: Nazwa aktywnej miejscowości

        read_env_config_func: Opcjonalna funkcja do odczytu konfiguracji .env

    """

    env = os.environ.copy()

    env["PYTHONIOENCODING"] = "utf-8"

    env["PYTHONUTF8"] = "1"

    env["LAUNCHED_BY_GUI"] = "1"

    sqlite_mode = _detect_sqlite_mode()

    env["DB_ENGINE"] = "sqlite" if sqlite_mode else os.getenv("DB_ENGINE", "postgresql")

    if active_location_name:

        env["ACTIVE_LOCATION"] = active_location_name

    if read_env_config_func:

        try:

            env_config = read_env_config_func()

            env.update(env_config)

        except Exception:

            pass

    if sqlite_mode:

        env["DB_ENGINE"] = "sqlite"

        backend_env = os.path.join(str(BACKEND_DIR), ".env")

        if os.path.exists(backend_env):

            try:

                with open(backend_env, "r", encoding="utf-8") as f:

                    for line in f:

                        line = line.strip()

                        if line.startswith("DB_PATH="):

                            env["DB_PATH"] = line.split("=", 1)[1].strip().strip('"').strip("'")

                        elif line.startswith(("FLASK_HOST=", "FLASK_PORT=", "GENEALOGY_EDITOR_PORT=", "PARCEL_EDITOR_PORT=")):

                            key, value = line.split("=", 1)

                            env[key.strip()] = value.strip().strip('"').strip("'")

            except Exception:

                pass

    return env


def prepare_command(key: str, script_info: Dict[str, Any]) -> list:

    """

    Przygotowuje listę argumentów dla subprocess.

    Args:

        key: Klucz procesu (np. "backend", "owner_editor")

        script_info: Informacje o skrypcie z SCRIPTS

    """

    if key == "tests":

        return [sys.executable, script_info["path"]] + script_info.get("args", [])

    elif key == "backend":

        args = script_info.get("args", [])

        # Jedno źródło prawdy dla portu backendu to .env/zmienne środowiskowe.
        # Wcześniej wartość z .env była nadpisywana twardym "--port 57200" z
        # SCRIPTS, przez co launcher otwierał inny URL niż uruchomiony uvicorn.
        if _detect_sqlite_mode():

            host = _read_backend_env_value("FLASK_HOST", os.getenv("FLASK_HOST", "127.0.0.1"))

            port = _read_backend_env_value("FLASK_PORT", os.getenv("FLASK_PORT", "5000"))

        else:

            flask_env = read_env_config("FLASK_")

            host = flask_env.get("FLASK_HOST", os.getenv("FLASK_HOST", "127.0.0.1"))

            port = flask_env.get("FLASK_PORT", os.getenv("FLASK_PORT", "5000"))

        if "--host" in args and not host:

            try:

                host = args[args.index("--host") + 1]

            except Exception:

                pass

        if "--port" in args and not port:

            try:

                port = args[args.index("--port") + 1]

            except Exception:

                pass

        return [sys.executable, "-X", "utf8", "-u", "-m", "uvicorn",

                "backend.main:app", "--host", str(host), "--port", str(port)]

    else:

        command = [sys.executable, "-X", "utf8", "-u", script_info["path"]]

        if key in ("genealogy_editor", "parcel_editor"):

            command.append("--launched-by-gui")

        return command
