"""
launcher/db/sqlite.py — Funkcje bazy danych SQLite.
Obsługa rejestru miejscowości w pliku locations.db.
"""

import json
import os
import sqlite3
import shutil
from pathlib import Path
from typing import Optional

from ..config.paths import LOCATIONS_DB_PATH, LOCATIONS_DATA_DIR
from ..config.settings import DEFAULT_LOCATION_NAME


def _sqlite_location_tuple(row: dict) -> tuple:
    """Konwertuje rekord sqlite na tuple zgodne z formatem PostgreSQL."""
    history_photos = row.get("history_photos") or "[]"
    name = row.get("name") or DEFAULT_LOCATION_NAME
    return (
        row.get("id"),
        name,
        row.get("full_name") or name,
        row.get("powiat") or "",
        row.get("region") or "",
        bool(row.get("active")),
        row.get("homepage_template") or "standardowy",
        row.get("year") or "1882",
        row.get("century") or "XIX w.",
        row.get("homepage_description") or "",
        row.get("history_paragraph1") or "",
        row.get("history_paragraph2") or "",
        row.get("history_paragraph3") or "",
        row.get("postgres_db_name") or row.get("sqlite_db_path") or "czarna.db",
        row.get("gmina_katastralna") or name,
        row.get("miejscowosc_protokolu") or name,
        None,
        history_photos,
        row.get("jewish_protocol_numbers") or "",
        row.get("custom_icon") or "custom_icon.png",
    )


def _sqlite_location_defaults() -> dict:
    """Domyślna miejscowość z data/locations/{DEFAULT}/launcher_db_config.json albo fallback."""
    cfg_path = LOCATIONS_DATA_DIR / DEFAULT_LOCATION_NAME / "launcher_db_config.json"
    data = {}
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            data = raw.get("default_location", raw)
        except Exception:
            data = {}
    name = data.get("name", DEFAULT_LOCATION_NAME)
    return {
        "name": name,
        "full_name": data.get("full_name", name),
        "powiat": data.get("powiat", ""),
        "region": data.get("region", ""),
        "active": 1,
        "homepage_template": data.get("homepage_template", "standardowy"),
        "year": data.get("year", "1882"),
        "century": data.get("century", "XIX w."),
        "homepage_description": data.get("homepage_description", ""),
        "history_paragraph1": data.get("history_paragraph1", ""),
        "history_paragraph2": data.get("history_paragraph2", ""),
        "history_paragraph3": data.get("history_paragraph3", ""),
        "postgres_db_name": data.get("postgres_db_name", ""),
        "sqlite_db_path": data.get("sqlite_db_path", "czarna.db"),
        "gmina_katastralna": data.get("gmina_katastralna", name),
        "miejscowosc_protokolu": data.get("miejscowosc_protokolu", name),
        "jewish_protocol_numbers": data.get("jewish_protocol_numbers", ""),
        "custom_icon": data.get("custom_icon", "custom_icon.png"),
        "history_photos": json.dumps(data.get("history_photos", []), ensure_ascii=False),
    }


def _ensure_location_data_files(location_folder: Path) -> list:
    """Tworzy wymagane pliki JSON dla miejscowości jeśli nie istnieją."""
    data_files = {
        'demografia.json': [],
        'genealogia.json': {"persons": []},
        'map_config.json': {
            "calibration": {"sw": {"lat": 0, "lng": 0}, "ne": {"lat": 0, "lng": 0}},
            "defaults": {"center": {"lat": 0, "lng": 0}, "zoom": 15}
        },
        'owner_data_to_import.json': {},
        'parcels_data.json': {}
    }
    created = []
    for filename, structure in data_files.items():
        file_path = location_folder / filename
        if not file_path.exists():
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(structure, f, ensure_ascii=False, indent=4)
                created.append(filename)
            except Exception as e:
                print(f"WARN: Blad tworzenia {filename}: {e}")
    if created:
        print(f"✅ Utworzono pliki danych: {', '.join(created)}")
    return created


def _write_sqlite_location_config(name, full_name, powiat, region, homepage_template, year, century,
                                  homepage_description, history_paragraph1, history_paragraph2,
                                  history_paragraph3, history_photos, postgres_db_name,
                                  gmina_katastralna, jewish_protocol_numbers, custom_icon="custom_icon.png"):
    """Zapisuje data/locations/{name}/launcher_db_config.json."""
    location_folder = LOCATIONS_DATA_DIR / name
    location_folder.mkdir(parents=True, exist_ok=True)
    (location_folder / "protokoly").mkdir(exist_ok=True)
    (location_folder / "history_photos").mkdir(exist_ok=True)
    _ensure_location_data_files(location_folder)

    config_file = location_folder / "launcher_db_config.json"
    launcher_config = {
        "default_location": {
            "name": name, "full_name": full_name, "powiat": powiat, "region": region,
            "homepage_template": homepage_template, "year": year, "century": century,
            "gmina_katastralna": gmina_katastralna,
            "jewish_protocol_numbers": jewish_protocol_numbers,
            "homepage_description": homepage_description,
            "history_paragraph1": history_paragraph1,
            "history_paragraph2": history_paragraph2,
            "history_paragraph3": history_paragraph3,
            "history_photos": history_photos or [],
            "favicon": "favicon.jpeg",
            "custom_icon": custom_icon or "custom_icon.png",
            "postgres_db_name": postgres_db_name or "",
            "sqlite_db_path": f"{name.lower()}.db"
        }
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(launcher_config, f, ensure_ascii=False, indent=2)


# Cache dla miejscowości
_locations_cache = None
_locations_cache_time = 0


def invalidate_locations_cache():
    global _locations_cache, _locations_cache_time
    _locations_cache = None
    _locations_cache_time = 0


def sqlite_init_locations_db():
    """Tworzy lokalny rejestr miejscowości w data/locations.db."""
    os.makedirs(str(LOCATIONS_DB_PATH.parent), exist_ok=True)
    conn = sqlite3.connect(str(LOCATIONS_DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            full_name TEXT, powiat TEXT, region TEXT,
            active INTEGER DEFAULT 0,
            homepage_template TEXT DEFAULT 'standardowy',
            year TEXT DEFAULT '1882', century TEXT DEFAULT 'XIX w.',
            homepage_description TEXT,
            history_paragraph1 TEXT, history_paragraph2 TEXT, history_paragraph3 TEXT,
            postgres_db_name TEXT, sqlite_db_path TEXT,
            gmina_katastralna TEXT, miejscowosc_protokolu TEXT,
            jewish_protocol_numbers TEXT, custom_icon TEXT,
            history_photos TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("SELECT COUNT(*) FROM locations")
    if cur.fetchone()[0] == 0:
        d = _sqlite_location_defaults()
        cur.execute("""
            INSERT INTO locations (
                name, full_name, powiat, region, active, homepage_template, year, century,
                homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
                postgres_db_name, sqlite_db_path, gmina_katastralna, miejscowosc_protokolu,
                jewish_protocol_numbers, custom_icon, history_photos
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            d["name"], d["full_name"], d["powiat"], d["region"], d["active"],
            d["homepage_template"], d["year"], d["century"], d["homepage_description"],
            d["history_paragraph1"], d["history_paragraph2"], d["history_paragraph3"],
            d["postgres_db_name"], d["sqlite_db_path"], d["gmina_katastralna"],
            d["miejscowosc_protokolu"], d["jewish_protocol_numbers"], d["custom_icon"],
            d["history_photos"]
        ))
    else:
        # Migracja pól dla starszych wpisów
        rows = cur.execute(
            "SELECT id, name, jewish_protocol_numbers, gmina_katastralna, homepage_template FROM locations"
        ).fetchall()
        for r in rows:
            cfg_path = LOCATIONS_DATA_DIR / r["name"] / "launcher_db_config.json"
            if not cfg_path.exists():
                continue
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                data = raw.get("default_location", raw)
                updates = {}
                if not r["jewish_protocol_numbers"] and data.get("jewish_protocol_numbers"):
                    updates["jewish_protocol_numbers"] = data.get("jewish_protocol_numbers")
                if not r["gmina_katastralna"] and data.get("gmina_katastralna"):
                    updates["gmina_katastralna"] = data.get("gmina_katastralna")
                if (not r["homepage_template"] or r["homepage_template"] == "standardowy") and data.get("homepage_template"):
                    updates["homepage_template"] = data.get("homepage_template")
                if updates:
                    set_clause = ", ".join([f"{k} = ?" for k in updates])
                    cur.execute(
                        f"UPDATE locations SET {set_clause}, updated_at=CURRENT_TIMESTAMP WHERE id = ?",
                        (*updates.values(), r["id"])
                    )
            except Exception:
                pass
    conn.commit()
    conn.close()


def sqlite_get_all_locations() -> list:
    sqlite_init_locations_db()
    conn = sqlite3.connect(str(LOCATIONS_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM locations ORDER BY name").fetchall()
    conn.close()
    return [_sqlite_location_tuple(dict(r)) for r in rows]


def sqlite_get_active_location() -> Optional[tuple]:
    sqlite_init_locations_db()
    conn = sqlite3.connect(str(LOCATIONS_DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM locations WHERE active = 1 LIMIT 1").fetchone()
    if not row:
        row = conn.execute("SELECT * FROM locations ORDER BY id LIMIT 1").fetchone()
        if row:
            conn.execute("UPDATE locations SET active = 0")
            conn.execute("UPDATE locations SET active = 1 WHERE id = ?", (row["id"],))
            conn.commit()
    conn.close()
    return _sqlite_location_tuple(dict(row)) if row else None


def sqlite_get_location_by_id(location_id) -> Optional[dict]:
    sqlite_init_locations_db()
    conn = sqlite3.connect(str(LOCATIONS_DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def sqlite_add_location(name, full_name, powiat="", region="", homepage_template="standardowy",
                        year="1882", century="XIX w.", homepage_description="",
                        history_paragraph1="", history_paragraph2="", history_paragraph3="",
                        history_photos=None, postgres_db_name="", gmina_katastralna=DEFAULT_LOCATION_NAME,
                        jewish_protocol_numbers="", custom_icon="custom_icon.png") -> int:
    sqlite_init_locations_db()
    history_photos = history_photos or []
    conn = sqlite3.connect(str(LOCATIONS_DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO locations (name, full_name, powiat, region, active, homepage_template, year, century,
                homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
                postgres_db_name, sqlite_db_path, gmina_katastralna, miejscowosc_protokolu,
                jewish_protocol_numbers, custom_icon, history_photos)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, full_name, powiat, region, homepage_template, year, century,
              homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
              postgres_db_name, f"{name.lower()}.db", gmina_katastralna, gmina_katastralna,
              jewish_protocol_numbers, custom_icon, json.dumps(history_photos, ensure_ascii=False)))
        location_id = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"Miejscowość '{name}' już istnieje")
    finally:
        conn.close()
    _write_sqlite_location_config(name, full_name, powiat, region, homepage_template, year, century,
                                  homepage_description, history_paragraph1, history_paragraph2,
                                  history_paragraph3, history_photos, postgres_db_name,
                                  gmina_katastralna, jewish_protocol_numbers, custom_icon)
    invalidate_locations_cache()
    return location_id


def sqlite_update_location(location_id, name, full_name, powiat, region, year, century,
                           homepage_description="", history_paragraph1="", history_paragraph2="",
                           history_paragraph3="", history_photos=None, postgres_db_name="",
                           homepage_template="standardowy", gmina_katastralna=DEFAULT_LOCATION_NAME,
                           jewish_protocol_numbers="", custom_icon="custom_icon.png"):
    sqlite_init_locations_db()
    history_photos = history_photos or []
    conn = sqlite3.connect(str(LOCATIONS_DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    old = cur.execute("SELECT name FROM locations WHERE id = ?", (location_id,)).fetchone()
    if not old:
        conn.close()
        raise ValueError("Miejscowość nie istnieje")
    old_name = old["name"]
    if old_name != name:
        old_folder = LOCATIONS_DATA_DIR / old_name
        new_folder = LOCATIONS_DATA_DIR / name
        if old_folder.exists() and not new_folder.exists():
            os.rename(str(old_folder), str(new_folder))
    try:
        cur.execute("""
            UPDATE locations SET name=?, full_name=?, powiat=?, region=?, year=?, century=?,
                homepage_description=?, history_paragraph1=?, history_paragraph2=?, history_paragraph3=?,
                postgres_db_name=?, sqlite_db_path=?, homepage_template=?, gmina_katastralna=?,
                miejscowosc_protokolu=?, jewish_protocol_numbers=?, custom_icon=?, history_photos=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (name, full_name, powiat, region, year, century, homepage_description,
              history_paragraph1, history_paragraph2, history_paragraph3, postgres_db_name,
              f"{name.lower()}.db", homepage_template, gmina_katastralna, gmina_katastralna,
              jewish_protocol_numbers, custom_icon, json.dumps(history_photos, ensure_ascii=False),
              location_id))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"Miejscowość '{name}' już istnieje")
    finally:
        conn.close()
    _write_sqlite_location_config(name, full_name, powiat, region, homepage_template, year, century,
                                  homepage_description, history_paragraph1, history_paragraph2,
                                  history_paragraph3, history_photos, postgres_db_name,
                                  gmina_katastralna, jewish_protocol_numbers, custom_icon)
    invalidate_locations_cache()


def sqlite_delete_location(location_id):
    sqlite_init_locations_db()
    conn = sqlite3.connect(str(LOCATIONS_DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    row = cur.execute("SELECT name, active FROM locations WHERE id = ?", (location_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("Miejscowość nie istnieje")
    if row["active"]:
        conn.close()
        raise ValueError("Nie można usunąć aktywnej miejscowości")
    cur.execute("DELETE FROM locations WHERE id = ?", (location_id,))
    conn.commit()
    conn.close()
    folder = LOCATIONS_DATA_DIR / row["name"]
    if folder.exists():
        shutil.rmtree(str(folder))
    invalidate_locations_cache()


def sqlite_set_active_location(location_id):
    sqlite_init_locations_db()
    conn = sqlite3.connect(str(LOCATIONS_DB_PATH))
    cur = conn.cursor()
    cur.execute("UPDATE locations SET active = 0")
    cur.execute("UPDATE locations SET active = 1 WHERE id = ?", (location_id,))
    conn.commit()
    conn.close()
    invalidate_locations_cache()
