"""Helpery diagnostyczne i DB dla launchera."""

from __future__ import annotations

import os
import shutil

from ..config.paths import BACKEND_DIR, BASE_DIR
from ..config.settings import COLORS, DEFAULT_LOCATION_NAME
from ..db.engine import get_engine
from ..db.postgres import (
    create_database as postgres_create_database,
    database_exists as postgres_database_exists,
    enable_postgis as postgres_enable_postgis,
    execute_schema as postgres_execute_schema,
    get_postgres_config,
    has_postgis_extension as postgres_has_postgis_extension,
    list_databases as postgres_list_databases,
    test_connection as test_postgres_connection,
)
from ..db.schemas import LOCATION_DB_SCHEMA


def init_location_database(db_name):
    """Tworzy i inicjalizuje bazę danych miejscowości w PostgreSQL."""
    try:
        config = get_postgres_config()
        if not config:
            return False, "Brak konfiguracji PostgreSQL"

        ok, msg = postgres_create_database(config, db_name)
        if not ok:
            return False, msg

        postgis_ok, postgis_msg = postgres_enable_postgis(config, db_name)
        schema_ok, schema_msg = postgres_execute_schema(config, db_name, LOCATION_DB_SCHEMA)
        if not schema_ok:
            return False, schema_msg

        details = [msg]
        if postgis_ok:
            details.append(postgis_msg)
        elif postgis_msg:
            details.append(f"Ostrzeżenie PostGIS: {postgis_msg}")
        details.append(schema_msg)
        return True, " | ".join(details)
    except Exception as e:
        return False, f"Błąd inicjalizacji bazy '{db_name}': {e}"


def detect_pgadmin_path():
    """Próbuje wykryć lokalizację pgAdmin na Windows i z PATH."""
    candidates = []
    which_path = shutil.which("pgAdmin4") or shutil.which("pgadmin4") or shutil.which("pgadmin")
    if which_path:
        candidates.append(which_path)

    for env_key in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        base = os.environ.get(env_key)
        if not base:
            continue
        candidates.extend([
            os.path.join(base, "pgAdmin 4", "bin", "pgAdmin4.exe"),
            os.path.join(base, "pgAdmin 4", "runtime", "pgAdmin4.exe"),
            os.path.join(base, "pgAdmin 4", "pgAdmin4.exe"),
        ])

    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            if os.path.exists(candidate):
                return candidate
    return ""


def get_guardian_status_snapshot(app):
    """Zwraca aktualny stan Strażnika do wykorzystania w panelach ustawień."""
    enabled = bool(app.guardian_enabled.get()) if hasattr(app, "guardian_enabled") else app.load_guardian_config()
    return {
        "enabled": enabled,
        "text": app.guardian_status_text.get() if hasattr(app, "guardian_status_text") else ("✅ System OK" if enabled else "⚪ Strażnik wyłączony"),
        "color": str(app.guardian_status_label.cget("foreground")) if hasattr(app, "guardian_status_label") else (COLORS['success'] if enabled else "gray"),
        "last_check_at": app._guardian_last_check_at,
        "last_issues": app._guardian_last_issues,
        "last_duration": app._guardian_last_duration,
    }


def get_database_diagnostics(app, get_active_location, read_env_config):
    """Zbiera podstawową diagnostykę aktywnego silnika bazy danych."""
    engine = get_engine()
    active_location = get_active_location()
    active_location_name = active_location[1] if active_location else DEFAULT_LOCATION_NAME

    diagnostics = {
        "engine_name": engine.name,
        "engine_label": engine.label,
        "engine_description": getattr(engine, "description", ""),
        "active_location": active_location_name,
        "backend_env_path": os.path.join(BACKEND_DIR, ".env"),
        "backend_running": "backend" in app.process_mgr.get_running_processes_info(),
        "backend_health": None,
    }

    if engine.name == "sqlite":
        sqlite_path = os.path.join(BASE_DIR, "data", "czarna.db")
        env_cfg = read_env_config()
        if env_cfg.get("DB_PATH"):
            sqlite_path = env_cfg.get("DB_PATH")
            if not os.path.isabs(sqlite_path):
                sqlite_path = os.path.join(BASE_DIR, sqlite_path)
        diagnostics.update({
            "mode": "sqlite",
            "sqlite_path": sqlite_path,
            "sqlite_exists": os.path.exists(sqlite_path),
            "sqlite_size": os.path.getsize(sqlite_path) if os.path.exists(sqlite_path) else 0,
        })
    else:
        config = get_postgres_config()
        location_env = read_env_config()
        location_db_name = location_env.get("DB_NAME") or (
            active_location[13] if active_location and len(active_location) > 13 else f"mapa_{active_location_name.lower()}_db"
        )

        conn_ok, conn_msg = test_postgres_connection(config)
        launcher_exists = postgres_database_exists(config, 'mapa_launcher_db') if conn_ok else False
        location_exists = postgres_database_exists(config, location_db_name) if conn_ok and location_db_name else False
        databases = postgres_list_databases(config) if conn_ok else []
        launcher_postgis = postgres_has_postgis_extension(config, 'mapa_launcher_db') if launcher_exists else False
        location_postgis = postgres_has_postgis_extension(config, location_db_name) if location_exists and location_db_name else False
        pgadmin_path = detect_pgadmin_path()

        diagnostics.update({
            "mode": "postgresql",
            "postgres_config": config,
            "connection_ok": conn_ok,
            "connection_msg": conn_msg,
            "launcher_db_name": "mapa_launcher_db",
            "launcher_db_exists": launcher_exists,
            "launcher_postgis": launcher_postgis,
            "location_db_name": location_db_name,
            "location_db_exists": location_exists,
            "location_postgis": location_postgis,
            "databases": databases,
            "pgadmin_path": pgadmin_path,
            "pgadmin_available": bool(pgadmin_path),
        })

    try:
        if diagnostics["backend_running"]:
            import requests
            port = int(app.load_flask_config().get("port", "5000"))
            url = f"http://127.0.0.1:{port}/api/health"
            response = requests.get(url, timeout=1.0)
            diagnostics["backend_health"] = {
                "ok": response.status_code == 200,
                "status_code": response.status_code,
                "payload": response.json() if response.headers.get("content-type", "").startswith("application/json") else None,
                "url": url,
            }
    except Exception as e:
        diagnostics["backend_health"] = {
            "ok": False,
            "status_code": None,
            "payload": None,
            "error": str(e),
        }

    return diagnostics
