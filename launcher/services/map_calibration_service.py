"""Operacje na pliku map_config.json i zapisie kalibracji w bazie."""

from __future__ import annotations

import json

import psycopg2

from launcher.config.paths import location_data_dir
from launcher.utils import get_db_config_from_env


def get_map_config_path(location_name: str):
    """Zwraca ścieżkę do map_config.json dla miejscowości."""
    return location_data_dir(location_name) / "map_config.json"


def load_map_config(location_name: str) -> dict:
    """Wczytuje map_config.json dla miejscowości."""
    with open(get_map_config_path(location_name), "r", encoding="utf-8") as f:
        return json.load(f)


def save_map_config(location_name: str, config: dict) -> str:
    """Zapisuje map_config.json dla miejscowości."""
    path = get_map_config_path(location_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    return str(path)


def save_map_calibration_to_db(new_config: dict) -> None:
    """Aktualizuje ustawienia kalibracji i domyślny widok w bazie danych."""
    db_config = get_db_config_from_env()
    conn = psycopg2.connect(**db_config)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES ('map_calibration', %s) "
            "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
            (json.dumps(new_config['calibration']),)
        )
        cur.execute(
            "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES ('map_defaults', %s) "
            "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
            (json.dumps(new_config['defaults']),)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
