"""
Import danych z backup/{miejscowosc} do lokalnej bazy SQLite.

Ten importer jest niezależny od starej migracji PostgreSQL i zapisuje geometrię
bezpośrednio jako GeoJSON TEXT, czyli w formacie używanym przez FastAPI SQLite.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.shared import extract_year, parse_polish_date, fix_windows_console_encoding

fix_windows_console_encoding()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "czarna.db"


def norm(value) -> str:
    """Normalizuje numer działki do postaci tekstowej, np. {'numerator':810,'denominator':2} -> 810/2."""
    if isinstance(value, dict):
        numerator = str(value.get("numerator") or value.get("numarator") or "").strip()
        denominator = str(value.get("denominator") or "").strip()
        return f"{numerator}/{denominator}" if numerator and denominator else numerator
    return str(value or "").strip()


def date_to_text(value) -> str | None:
    if isinstance(value, dict):
        year = value.get("year")
        month = value.get("month")
        day = value.get("day")
        if year and month and day:
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        return str(year) if year else None
    return str(value) if value is not None else None


def geometry_to_geojson(geom_data, category: str) -> dict | None:
    """Konwertuje backupowy format [lat,lng] na GeoJSON [lng,lat]."""
    if not geom_data:
        return None

    point_categories = {"dom", "kapliczka", "budynek", "dworzec", "obiekt_specjalny"}
    line_categories = {"droga", "rzeka"}

    try:
        if category in point_categories:
            lat, lng = geom_data
            return {"type": "Point", "coordinates": [float(lng), float(lat)]}

        coords = [[float(lng), float(lat)] for lat, lng in geom_data]
        if category in line_categories:
            if len(coords) < 2:
                return None
            return {"type": "LineString", "coordinates": coords}

        if len(coords) > 2:
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            return {"type": "Polygon", "coordinates": [coords]}
    except Exception:
        return None

    return None


def ensure_schema(conn: sqlite3.Connection) -> None:
    schema_path = BASE_DIR / "backend" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    lines = [line for line in schema_sql.splitlines() if not line.strip().startswith("--")]
    for statement in "\n".join(lines).split(";"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(demografia)").fetchall()]
    if "populacja_ogolem" not in cols:
        conn.execute("ALTER TABLE demografia ADD COLUMN populacja_ogolem INTEGER DEFAULT 0")
    conn.commit()


def ensure_object(conn: sqlite3.Connection, object_id_map: dict, plot_number: str, hint_building: bool) -> int | None:
    if not plot_number:
        return None

    if hint_building:
        wanted_categories = ["budowlana"]
        fallback_category = "budowlana"
    else:
        wanted_categories = ["pastwisko", "las", "droga", "rzeka", "gruntowa", "rolna"]
        fallback_category = "rolna"

    for category in wanted_categories:
        object_id = object_id_map.get((plot_number, category))
        if object_id:
            return object_id

    if not hint_building:
        excluded = {"budynek", "dom", "budowlana", "kapliczka", "obiekt_specjalny"}
        for (number, category), object_id in object_id_map.items():
            if number == plot_number and category not in excluded:
                return object_id

    cur = conn.execute(
        "INSERT INTO obiekty_geograficzne (nazwa_lub_numer, kategoria, geometria) VALUES (?, ?, NULL)",
        (plot_number, fallback_category),
    )
    object_id = cur.lastrowid
    object_id_map[(plot_number, fallback_category)] = object_id
    return object_id


def import_location(location_name: str = "Czarna", db_path: Path = DEFAULT_DB_PATH) -> None:
    backup_dir = BASE_DIR / "data" / "locations" / location_name
    owner_file = backup_dir / "owner_data_to_import.json"
    parcel_file = backup_dir / "parcels_data.json"
    map_config_file = backup_dir / "map_config.json"
    demografia_file = backup_dir / "demografia.json"
    genealogia_file = backup_dir / "genealogia.json"

    if not owner_file.exists() or not parcel_file.exists():
        locations_dir = BASE_DIR / "data" / "locations"
        available = []
        if locations_dir.is_dir():
            available = [
                d.name for d in locations_dir.iterdir()
                if d.is_dir() and (d / "owner_data_to_import.json").exists()
            ]
        hint = ""
        if available:
            hint = f"\nDostępne lokalizacje: {', '.join(available)}"
        raise FileNotFoundError(
            f"Brak plików danych w {backup_dir}\n"
            f"Sprawdź czy podałeś poprawną nazwę miejscowości.{hint}"
        )

    owner_data = json.loads(owner_file.read_text(encoding="utf-8"))
    parcel_data = json.loads(parcel_file.read_text(encoding="utf-8"))

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    ensure_schema(conn)

    try:
        conn.execute("BEGIN")
        for table in ["malzenstwa", "osoby_genealogia", "demografia", "dzialki_wlasciciele", "obiekty_geograficzne", "wlasciciele", "konfiguracja_systemu"]:
            conn.execute(f"DELETE FROM {table}")

        owner_id_map: dict[str, int] = {}
        for owner_key, data in owner_data.items():
            cur = conn.execute(
                """
                INSERT INTO wlasciciele (
                    unikalny_klucz, nazwa_wlasciciela, numer_protokolu, numer_domu,
                    genealogia, historia_wlasnosci, uwagi, wspolwlasnosc,
                    powiazania_i_transakcje, interpretacja_i_wnioski,
                    data_protokolu, miejsce_protokolu
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    owner_key,
                    data.get("ownerName", ""),
                    str(data.get("orderNumber", "") or ""),
                    str(data.get("houseNumber", "") or ""),
                    data.get("genealogy", ""),
                    data.get("ownershipHistory", ""),
                    data.get("remarks", ""),
                    data.get("wspolwlasnosc", ""),
                    data.get("powiazania_i_transakcje", data.get("relacje_rodzinne", "")),
                    data.get("interpretacja_i_wnioski", ""),
                    parse_polish_date(data.get("protocolDate")),
                    data.get("protocolLocation", ""),
                ),
            )
            owner_id_map[owner_key] = cur.lastrowid

        object_id_map: dict[tuple[str, str], int] = {}
        for raw_key, data in parcel_data.items():
            if "_" in raw_key:
                raw_number, category_from_key = raw_key.split("_", 1)
                category = category_from_key or data.get("kategoria", "rolna")
            else:
                raw_number = raw_key
                category = data.get("kategoria", "rolna")
            number = norm(raw_number)
            geojson = geometry_to_geojson(data.get("geometria"), category)
            cur = conn.execute(
                "INSERT INTO obiekty_geograficzne (nazwa_lub_numer, kategoria, geometria) VALUES (?, ?, ?)",
                (number, category, json.dumps(geojson, ensure_ascii=False) if geojson else None),
            )
            object_id_map[(number, category)] = cur.lastrowid

        seen_links: set[tuple[int, int, str]] = set()

        def add_link(owner_id: int, object_id: int | None, ownership_type: str) -> None:
            if not object_id:
                return
            key = (owner_id, object_id, ownership_type)
            if key in seen_links:
                return
            conn.execute(
                "INSERT INTO dzialki_wlasciciele (wlasciciel_id, obiekt_id, typ_posiadania) VALUES (?, ?, ?)",
                (owner_id, object_id, ownership_type),
            )
            seen_links.add(key)

        for owner_key, data in owner_data.items():
            owner_id = owner_id_map.get(owner_key)
            if not owner_id:
                continue

            for field in ("realbuildingPlots", "realagriculturalPlots"):
                for plot in data.get(field, []) or []:
                    add_link(owner_id, ensure_object(conn, object_id_map, norm(plot), field.startswith("realbuilding")), "wlasnosc rzeczywista")

            for field in ("buildingPlots", "agriculturalPlots"):
                for plot in data.get(field, []) or []:
                    add_link(owner_id, ensure_object(conn, object_id_map, norm(plot), field.startswith("building")), "wlasnosc z protokolu")

            house_number = str(data.get("houseNumber", "") or "").strip()
            if house_number:
                for category in ("dom", "budynek"):
                    house_object_id = object_id_map.get((house_number, category))
                    if house_object_id:
                        add_link(owner_id, house_object_id, "wlasnosc rzeczywista")

        if map_config_file.exists():
            map_config = json.loads(map_config_file.read_text(encoding="utf-8"))
            for key, value in map_config.items():
                conn.execute(
                    "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES (?, ?)",
                    (f"map_{key}" if key in {"calibration", "defaults"} else key, json.dumps(value, ensure_ascii=False)),
                )

        if demografia_file.exists():
            demografia = json.loads(demografia_file.read_text(encoding="utf-8"))
            for item in demografia if isinstance(demografia, list) else []:
                conn.execute(
                    "INSERT INTO demografia (rok, populacja_ogolem, katolicy, zydzi, inni, opis) VALUES (?, ?, ?, ?, ?, ?)",
                    (item.get("rok"), item.get("populacja_ogolem", 0), item.get("katolicy", 0), item.get("zydzi", 0), item.get("inni", 0), item.get("opis", "")),
                )

        if genealogia_file.exists():
            genealogia_raw = json.loads(genealogia_file.read_text(encoding="utf-8"))
            persons = genealogia_raw.get("persons", []) if isinstance(genealogia_raw, dict) else []
            person_id_map: dict[str, int] = {}
            for person in persons:
                protocol_id = None
                protocol_key = person.get("protokolKey") or person.get("protocolKey")
                if protocol_key:
                    protocol_id = owner_id_map.get(str(protocol_key))
                if protocol_id is None:
                    try:
                        protocol_number = int(person.get("protocolNumber") or person.get("id_protokolu") or 0)
                        protocol_id = next((oid for key, oid in owner_id_map.items() if str(owner_data[key].get("orderNumber")) == str(protocol_number)), None)
                    except Exception:
                        protocol_id = None
                cur = conn.execute(
                    """
                    INSERT INTO osoby_genealogia (json_id, imie_nazwisko, plec, rok_urodzenia, rok_smierci, uwagi, numer_domu, id_protokolu)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(person.get("id", "")),
                        person.get("name") or person.get("imie_nazwisko", ""),
                        person.get("gender") or person.get("plec", ""),
                        extract_year(person.get("birthDate") or person.get("birthYear") or person.get("rok_urodzenia")),
                        extract_year(person.get("deathDate") or person.get("deathYear") or person.get("rok_smierci")),
                        person.get("notes") or person.get("uwagi", ""),
                        person.get("houseNumber") or person.get("numer_domu", ""),
                        protocol_id,
                    ),
                )
                person_id_map[str(person.get("id", ""))] = cur.lastrowid

            for person in persons:
                local_id = person_id_map.get(str(person.get("id", "")))
                if not local_id:
                    continue
                father_id = person_id_map.get(str(person.get("fatherId"))) if person.get("fatherId") else None
                mother_id = person_id_map.get(str(person.get("motherId"))) if person.get("motherId") else None
                conn.execute("UPDATE osoby_genealogia SET id_ojca=?, id_matki=? WHERE id=?", (father_id, mother_id, local_id))

            seen_marriages: set[tuple[int, int]] = set()
            for person in persons:
                local_id = person_id_map.get(str(person.get("id", "")))
                if not local_id:
                    continue
                for marriage in person.get("marriages", []) or []:
                    spouse_id = person_id_map.get(str(marriage.get("spouseId")))
                    if not spouse_id or spouse_id == local_id:
                        continue
                    a, b = sorted((local_id, spouse_id))
                    if (a, b) in seen_marriages:
                        continue
                    seen_marriages.add((a, b))
                    date_value = marriage.get("date")
                    conn.execute(
                        "INSERT INTO malzenstwa (malzonek1_id, malzonek2_id, rok_slubu, data_slubu) VALUES (?, ?, ?, ?)",
                        (a, b, extract_year(date_value), date_to_text(date_value)),
                    )

        conn.commit()

        counts = {
            "owners": conn.execute("SELECT COUNT(*) FROM wlasciciele").fetchone()[0],
            "objects": conn.execute("SELECT COUNT(*) FROM obiekty_geograficzne").fetchone()[0],
            "links": conn.execute("SELECT COUNT(*) FROM dzialki_wlasciciele").fetchone()[0],
        }
        print(f"✅ Import SQLite zakończony: {counts['owners']} właścicieli, {counts['objects']} obiektów, {counts['links']} powiązań")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    location = sys.argv[1] if len(sys.argv) > 1 else "Czarna"
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB_PATH
    import_location(location, db_path)
