"""Logika ustawień administratora i zapisu .env."""

from __future__ import annotations


def hash_admin_password(password: str) -> str:
    """Zwraca hash hasła administratora przy użyciu Werkzeug."""
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password)


def apply_admin_settings(env: dict, enabled: bool, username: str, password: str | None = None) -> tuple[str, str]:
    """Aktualizuje słownik env ustawieniami admina.

    Zwraca (old_auth, new_auth).
    """
    old_auth = env.get('ADMIN_AUTH_ENABLED', '0')
    env['ADMIN_AUTH_ENABLED'] = '1' if enabled else '0'
    env['ADMIN_USERNAME'] = username.strip()
    if password:
        env['ADMIN_PASSWORD_HASH'] = hash_admin_password(password)
    env.setdefault('FLASK_SECRET_KEY', 'change-me-once')
    env.setdefault('GENEALOGY_EDITOR_PORT', '5001')
    env.setdefault('PARCEL_EDITOR_PORT', '5003')
    return old_auth, env['ADMIN_AUTH_ENABLED']


def format_env_content(env: dict, *, sqlite_backend_env: bool, sqlite_mode: bool) -> str:
    """Formatuje .env dla backendu SQLite albo dla miejscowości."""
    db_name = env.get('DB_NAME', 'mapa_czarna_db')
    db_engine = env.get('DB_ENGINE', 'sqlite' if sqlite_mode else 'postgresql')
    db_path = env.get('DB_PATH', 'data/czarna.db')
    flask_host = env.get('FLASK_HOST', '127.0.0.1')
    flask_port = env.get('FLASK_PORT', '5000')
    flask_debug = env.get('FLASK_DEBUG', 'True')
    flask_secret = env.get('FLASK_SECRET_KEY', 'change-me-once')
    genealogy_editor_port = env.get('GENEALOGY_EDITOR_PORT', '5001')
    parcel_editor_port = env.get('PARCEL_EDITOR_PORT', '5003')
    admin_enabled = env.get('ADMIN_AUTH_ENABLED', '0')
    admin_user = env.get('ADMIN_USERNAME', 'admin')
    admin_hash = env.get('ADMIN_PASSWORD_HASH', '')
    location_name = env.get('LOCATION_NAME', '')
    location_code = env.get('LOCATION_CODE', '')

    if sqlite_backend_env:
        return f"""# Konfiguracja serwera (FastAPI)
FLASK_HOST={flask_host}
FLASK_PORT={flask_port}

# Porty edytorów pomocniczych
GENEALOGY_EDITOR_PORT={genealogy_editor_port}
PARCEL_EDITOR_PORT={parcel_editor_port}

# Silnik bazy danych: "postgresql" lub "sqlite"
DB_ENGINE={db_engine}
DB_PATH={db_path}

# PostgreSQL (używane gdy DB_ENGINE=postgresql)
DB_HOST={env.get('DB_HOST', 'localhost')}
DB_PORT={env.get('DB_PORT', '5432')}
DB_USER={env.get('DB_USER', 'postgres')}
DB_PASSWORD={env.get('DB_PASSWORD', '1234')}
DB_NAME={db_name}

# Bezpieczeństwo
FLASK_SECRET_KEY={flask_secret}
ADMIN_AUTH_ENABLED={admin_enabled}
ADMIN_USERNAME={admin_user}
ADMIN_PASSWORD_HASH={admin_hash}
"""

    content = f"""# =============================================================================
# KONFIGURACJA MIEJSCOWOŚCI
# =============================================================================
# Konfiguracja PostgreSQL (host, port, user, password) jest w backend/.postgres.env

# =============================================================================
# BAZA DANYCH
# =============================================================================
DB_NAME={db_name}

# =============================================================================
# SERWER FLASK (główny serwer)
# =============================================================================
FLASK_HOST={flask_host}
FLASK_PORT={flask_port}
FLASK_DEBUG={flask_debug}
FLASK_SECRET_KEY={flask_secret}

# =============================================================================
# PORTY EDYTORÓW
# =============================================================================
# Każdy port musi być unikalny! Nie można używać tego samego portu dla różnych serwerów.
GENEALOGY_EDITOR_PORT={genealogy_editor_port}
PARCEL_EDITOR_PORT={parcel_editor_port}

# =============================================================================
# AUTENTYKACJA ADMINISTRATORA
# =============================================================================
ADMIN_AUTH_ENABLED={admin_enabled}
ADMIN_USERNAME={admin_user}
ADMIN_PASSWORD_HASH={admin_hash}
"""

    if location_name:
        content += f"""
# =============================================================================
# INFORMACJE O MIEJSCOWOŚCI
# =============================================================================
LOCATION_NAME={location_name}
LOCATION_CODE={location_code}
"""
    return content


def save_env_file(env_path: str, env: dict, *, sqlite_backend_env: bool, sqlite_mode: bool) -> None:
    """Zapisuje .env z ujednoliconym formatem."""
    content = format_env_content(env, sqlite_backend_env=sqlite_backend_env, sqlite_mode=sqlite_mode)
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(content)


def save_admin_password_hash(env_path: str, new_hash: str) -> None:
    """Aktualizuje linię ``ADMIN_PASSWORD_HASH`` w pliku .env (Priorytet 6.4).

    Inne linie pozostają nienaruszone. Gdy linia nie istnieje - dodaje ją na końcu.
    Gdy nowy hash jest pusty - usuwa linię (przywraca fallback ``admin123``).
    """
    import os
    if not os.path.exists(env_path):
        # Utwórz pusty plik .env jeśli nie istnieje
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("")
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    found = False
    for line in lines:
        if line.strip().startswith("ADMIN_PASSWORD_HASH="):
            if new_hash:
                new_lines.append(f"ADMIN_PASSWORD_HASH={new_hash}\n")
            found = True
        else:
            new_lines.append(line)
    if not found and new_hash:
        new_lines.append(f"\nADMIN_PASSWORD_HASH={new_hash}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
