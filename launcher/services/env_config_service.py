"""Operacje tekstowe i plikowe dla konfiguracji .env."""

from __future__ import annotations


PORT_KEYS = ["FLASK_PORT", "GENEALOGY_EDITOR_PORT", "PARCEL_EDITOR_PORT"]
PORT_NAMES = {
    "FLASK_PORT": "Główny serwer",
    "GENEALOGY_EDITOR_PORT": "Edytor genealogii",
    "PARCEL_EDITOR_PORT": "Edytor działek",
}

FORM_DEFAULTS = {
    "FLASK_HOST": "127.0.0.1",
    "FLASK_PORT": "5000",
    "GENEALOGY_EDITOR_PORT": "5001",
    "PARCEL_EDITOR_PORT": "5003",
    "DB_PATH": "data/czarna.db",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_USER": "postgres",
    "DB_PASSWORD": "1234",
    "DB_NAME": "mapa_czarna_db",
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD_HASH": "",
    "FLASK_SECRET_KEY": "dev-secret-change-me",
}


def parse_env_content(content: str) -> dict[str, str]:
    """Parsuje zawartość .env do słownika."""
    config = {}
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key, value = stripped.split('=', 1)
            config[key.strip()] = value.strip().strip('"').strip("'")
    return config


def update_env_content(content: str, updates: dict[str, str]) -> str:
    """Aktualizuje znane klucze .env, zachowując komentarze i nieznane wpisy."""
    lines = content.splitlines()
    seen = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key = stripped.split('=', 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        new_lines.append(line)

    missing = [k for k in updates.keys() if k not in seen]
    if missing:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append("# Ustawienia dodane przez edytor GUI")
        for key in missing:
            new_lines.append(f"{key}={updates[key]}")
    return "\n".join(new_lines).rstrip() + "\n"


def validate_env_content(content: str) -> tuple[bool, str]:
    """Waliduje porty w .env. Zwraca (ok, komunikat_bledu)."""
    ports = {}
    for line in content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key in PORT_KEYS:
                try:
                    port_value = int(value)
                except ValueError:
                    return False, f"{PORT_NAMES[key]} musi mieć port jako liczbę, a wpisano: {value}"
                if not (1 <= port_value <= 65535):
                    return False, f"{PORT_NAMES[key]} ma niepoprawny port {port_value}. Dozwolony zakres: 1-65535."
                if port_value in ports.values():
                    duplicate_key = [k for k, v in ports.items() if v == port_value][0]
                    return False, (
                        f"Port {port_value} jest używany zarówno dla:\n"
                        f"• {PORT_NAMES[duplicate_key]}\n"
                        f"• {PORT_NAMES[key]}\n\n"
                        f"Każdy serwer musi mieć unikalny port!"
                    )
                ports[key] = port_value
    return True, ""


def read_text_file(path: str) -> str:
    """Czyta plik tekstowy UTF-8."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text_file(path: str, content: str) -> None:
    """Zapisuje plik tekstowy UTF-8."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def form_defaults(sqlite_mode: bool) -> dict[str, str]:
    """Domyślne wartości formularza .env dla aktualnego trybu DB."""
    defaults = dict(FORM_DEFAULTS)
    defaults["DB_ENGINE"] = "sqlite" if sqlite_mode else "postgresql"
    return defaults


def default_env_content(sqlite_backend_env: bool) -> str:
    """Zwraca domyślną zawartość .env dla backendu SQLite lub miejscowości."""
    if sqlite_backend_env:
        return """# Konfiguracja serwera (FastAPI)
FLASK_HOST=127.0.0.1
FLASK_PORT=5000

# Porty edytorów pomocniczych
GENEALOGY_EDITOR_PORT=5001
PARCEL_EDITOR_PORT=5003

# Silnik bazy danych: "postgresql" lub "sqlite"
DB_ENGINE=sqlite
DB_PATH=data/czarna.db

# PostgreSQL (używane gdy DB_ENGINE=postgresql)
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=1234
DB_NAME=mapa_czarna_db

# Bezpieczeństwo
FLASK_SECRET_KEY=dev-secret-change-me
ADMIN_AUTH_ENABLED=0
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=
"""
    return """# =============================================================================
# KONFIGURACJA MIEJSCOWOŚCI
# =============================================================================
# Konfiguracja PostgreSQL (host, port, user, password) jest w backend/.postgres.env

# =============================================================================
# BAZA DANYCH - NAZWA BAZY
# =============================================================================
DB_NAME=mapa_czarna_db

# =============================================================================
# KONFIGURACJA FLASK (główny serwer)
# =============================================================================
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
FLASK_SECRET_KEY=change-me-once

# =============================================================================
# PORTY EDYTORÓW
# =============================================================================
# Każdy port musi być unikalny! Nie można używać tego samego portu dla różnych serwerów.
GENEALOGY_EDITOR_PORT=5001
PARCEL_EDITOR_PORT=5003

# =============================================================================
# AUTENTYKACJA ADMINISTRATORA
# =============================================================================
ADMIN_AUTH_ENABLED=0
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=
"""
