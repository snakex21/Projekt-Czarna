"""Runtime helpery URL-i i konfiguracji host/port dla launchera."""

import os

from launcher.config.urls import build_launcher_urls, normalize_browser_host, read_env_values, read_port_values


def get_launcher_urls(sqlite_mode: bool, backend_dir: str, get_location_env_path, read_backend_env_value) -> dict:
    """Buduje URL-e szybkiego dostępu zgodnie z aktywnym trybem DB."""
    if sqlite_mode:
        main_host = read_backend_env_value("FLASK_HOST", "127.0.0.1")
        browser_host = normalize_browser_host(main_host)
        main_port = int(read_backend_env_value("FLASK_PORT", "5000"))
        env_path = os.path.join(backend_dir, ".env")
        editor_ports = read_port_values(env_path, {
            "GENEALOGY_EDITOR_PORT": 5001,
            "PARCEL_EDITOR_PORT": 5003,
        })
        return build_launcher_urls(
            browser_host,
            main_port,
            editor_ports["GENEALOGY_EDITOR_PORT"],
            editor_ports["PARCEL_EDITOR_PORT"],
            parcel_template=False,
        )

    try:
        env_path = get_location_env_path()
        values = read_env_values(env_path, defaults={"FLASK_HOST": "127.0.0.1"})
        main_host = values.get("FLASK_HOST", "127.0.0.1")
        ports = read_port_values(env_path)
    except Exception:
        main_host = "127.0.0.1"
        ports = {
            "FLASK_PORT": 5000,
            "GENEALOGY_EDITOR_PORT": 5001,
            "PARCEL_EDITOR_PORT": 5003,
        }

    return build_launcher_urls(
        normalize_browser_host(main_host),
        ports["FLASK_PORT"],
        ports["GENEALOGY_EDITOR_PORT"],
        ports["PARCEL_EDITOR_PORT"],
        parcel_template=True,
    )


def load_flask_config(sqlite_mode: bool, backend_dir: str, get_location_env_path) -> dict:
    """Czyta host/port backendu z właściwego pliku .env i normalizuje wynik."""
    if sqlite_mode:
        env_path = os.path.join(backend_dir, ".env")
    else:
        try:
            env_path = get_location_env_path()
        except ValueError:
            env_path = None

    values = read_env_values(env_path, defaults={"FLASK_HOST": "127.0.0.1", "FLASK_PORT": "5000"})
    try:
        port = str(int(values.get("FLASK_PORT", "5000")))
    except (TypeError, ValueError):
        port = "5000"
    return {
        "host": values.get("FLASK_HOST", "127.0.0.1"),
        "port": port,
        "db_engine": "sqlite" if sqlite_mode else "postgresql",
    }
