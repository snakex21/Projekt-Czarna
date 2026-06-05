"""Helpery budowania URL-i launchera.

Funkcje są celowo małe i bez zależności od Tkintera, żeby dało się ich używać
zarówno z ``launcher_app.py``, jak i z ``launcher.config.settings``.
"""

import os
import time


DEFAULT_PORTS = {
    "FLASK_PORT": 5000,
    "GENEALOGY_EDITOR_PORT": 5001,
    "PARCEL_EDITOR_PORT": 5003,
}


def normalize_browser_host(host: str) -> str:
    """Zamienia adres nasłuchu serwera na adres otwierany w przeglądarce."""
    return "127.0.0.1" if host in ("0.0.0.0", "::", "") else host


def read_env_values(env_path, defaults=None):
    """Czyta proste pary KEY=VALUE z pliku .env, z wartościami domyślnymi."""
    values = dict(defaults or {})
    if not env_path or not os.path.exists(env_path):
        return values

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        return values
    return values


def read_port_values(env_path, defaults=None):
    """Czyta porty z .env jako liczby całkowite z fallbackiem."""
    defaults = dict(defaults or DEFAULT_PORTS)
    raw = read_env_values(env_path, defaults={k: str(v) for k, v in defaults.items()})
    ports = dict(defaults)
    for key in defaults:
        try:
            ports[key] = int(raw.get(key, defaults[key]))
        except (TypeError, ValueError):
            ports[key] = defaults[key]
    return ports


def build_launcher_urls(
    browser_host,
    main_port,
    genealogy_port,
    parcel_port,
    *,
    parcel_template=True,
    cache_buster=None,
):
    """Buduje pełny słownik URL-i używany przez launcher."""
    if cache_buster is None:
        cache_buster = int(time.time())
    parcel_suffix = "/template.html" if parcel_template else "/"
    return {
        "strona_glowna": f"http://{browser_host}:{main_port}/strona_glowna/index.html",
        "mapa": f"http://{browser_host}:{main_port}/mapa/mapa.html?v={cache_buster}",
        "mapa_v2": f"http://{browser_host}:{main_port}/mapa/mapa.html?v={cache_buster}",
        "admin": f"http://{browser_host}:{main_port}/admin",
        "genealogy_editor": f"http://127.0.0.1:{genealogy_port}/",
        "parcel_editor": f"http://127.0.0.1:{parcel_port}{parcel_suffix}",
    }


def build_tool_urls(browser_host, backend_port, genealogy_port, parcel_port):
    """Buduje skrócony słownik URL-i używany przez process_manager/settings."""
    return {
        "backend": f"http://{browser_host}:{backend_port}/",
        "genealogy_editor": f"http://127.0.0.1:{genealogy_port}/",
        "parcel_editor": f"http://127.0.0.1:{parcel_port}/template.html",
    }
