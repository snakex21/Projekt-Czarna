"""
Synchronizacja genealogii z backup/{miejscowosc}/genealogia.json do SQLite.

Użycie:
    python backend/sync_genealogy_sqlite.py Czarna data/czarna.db

Skrypt uzupełnia w bazie pola, których brak powodował puste statystyki:
- rok_urodzenia / rok_smierci,
- id_ojca / id_matki jako lokalne ID z tabeli osoby_genealogia,
- id_protokolu na podstawie protokolKey,
- tabela malzenstwa.

Domyślnie robi kopię .db przed zapisem.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.shared import extract_year, fix_windows_console_encoding

fix_windows_console_encoding()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "czarna.db"


def date_to_text(value: Any) -> str | None:
    if isinstance(value, dict):
        year = value.get("year")
        month = value.get("month")
        day = value.get("day")
        if year and month and day:
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        if year:
            return str(year)
    if value is None:
        return None
    return str(value)


def load_people(location: str) -> list[dict[str, Any]]:
    path = BASE_DIR / "data" / "locations" / location / "genealogia.json"
    if not path.exists():
        raise FileNotFoundError(f"Brak pliku genealogii: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    people = raw.get("persons", []) if isinstance(raw, dict) else []
    if not people:
        raise ValueError(f"Brak osób w {path}")
    return people


def backup_database(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.bak_genealogy_{timestamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def sync_genealogy(location: str = "Czarna", db_path: Path = DEFAULT_DB_PATH, make_backup: bool = True) -> dict[str, int | str]:
    db_path = db_path.resolve()
    people = load_people(location)

    backup_path = ""
    if make_backup and db_path.exists():
        backup_path = str(backup_database(db_path))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")

    try:
        conn.execute("BEGIN")

        owner_by_key = {
            str(row["unikalny_klucz"]): row["id"]
            for row in conn.execute("SELECT id, unikalny_klucz FROM wlasciciele WHERE unikalny_klucz IS NOT NULL")
        }
        owner_by_protocol = {
            str(row["numer_protokolu"]): row["id"]
            for row in conn.execute("SELECT id, numer_protokolu FROM wlasciciele WHERE numer_protokolu IS NOT NULL")
        }

        db_id_by_json = {
            str(row["json_id"]): row["id"]
            for row in conn.execute("SELECT id, json_id FROM osoby_genealogia WHERE json_id IS NOT NULL AND json_id != ''")
        }

        inserted = 0
        updated = 0

        # Etap 1: osoby bez relacji rodzicielskich (relacje potrzebują lokalnych ID po stronie SQLite).
        for person in people:
            json_id = str(person.get("id") or "").strip()
            if not json_id:
                continue

            protocol_id = None
            protocol_key = person.get("protokolKey") or person.get("protocolKey")
            if protocol_key:
                protocol_id = owner_by_key.get(str(protocol_key))
            if protocol_id is None:
                protocol_number = person.get("protocolNumber") or person.get("id_protokolu")
                if protocol_number is not None:
                    protocol_id = owner_by_protocol.get(str(protocol_number))

            values = (
                json_id,
                person.get("name") or person.get("imie_nazwisko") or "",
                person.get("gender") or person.get("plec") or "",
                extract_year(person.get("birthDate") or person.get("birthYear") or person.get("rok_urodzenia")),
                extract_year(person.get("deathDate") or person.get("deathYear") or person.get("rok_smierci")),
                person.get("notes") or person.get("uwagi") or "",
                str(person.get("houseNumber") or person.get("numer_domu") or ""),
                protocol_id,
            )

            if json_id in db_id_by_json:
                conn.execute(
                    """
                    UPDATE osoby_genealogia
                    SET imie_nazwisko=?, plec=?, rok_urodzenia=?, rok_smierci=?,
                        uwagi=?, numer_domu=?, id_protokolu=?
                    WHERE json_id=?
                    """,
                    (values[1], values[2], values[3], values[4], values[5], values[6], values[7], json_id),
                )
                updated += 1
            else:
                cur = conn.execute(
                    """
                    INSERT INTO osoby_genealogia
                    (json_id, imie_nazwisko, plec, rok_urodzenia, rok_smierci, uwagi, numer_domu, id_protokolu)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                db_id_by_json[json_id] = cur.lastrowid
                inserted += 1

        # Etap 2: relacje rodzicielskie po zbudowaniu pełnej mapy json_id -> id.
        parent_updates = 0
        for person in people:
            json_id = str(person.get("id") or "").strip()
            local_id = db_id_by_json.get(json_id)
            if not local_id:
                continue
            father_json = person.get("fatherId") or person.get("id_ojca")
            mother_json = person.get("motherId") or person.get("id_matki")
            father_id = db_id_by_json.get(str(father_json)) if father_json else None
            mother_id = db_id_by_json.get(str(mother_json)) if mother_json else None
            conn.execute(
                "UPDATE osoby_genealogia SET id_ojca=?, id_matki=? WHERE id=?",
                (father_id, mother_id, local_id),
            )
            if father_id or mother_id:
                parent_updates += 1

        # Etap 3: małżeństwa. Czyścimy tabelę, bo wcześniej była pusta albo niepełna.
        conn.execute("DELETE FROM malzenstwa")
        marriages_seen: set[tuple[int, int]] = set()
        marriages_inserted = 0
        for person in people:
            person_json = person.get("id")
            person_local = db_id_by_json.get(str(person_json))
            if not person_local:
                continue
            for marriage in person.get("marriages") or []:
                spouse_json = marriage.get("spouseId")
                spouse_local = db_id_by_json.get(str(spouse_json)) if spouse_json is not None else None
                if not spouse_local or spouse_local == person_local:
                    continue
                a, b = sorted((person_local, spouse_local))
                if (a, b) in marriages_seen:
                    continue
                marriages_seen.add((a, b))
                date_value = marriage.get("date")
                conn.execute(
                    "INSERT INTO malzenstwa (malzonek1_id, malzonek2_id, rok_slubu, data_slubu) VALUES (?, ?, ?, ?)",
                    (a, b, extract_year(date_value), date_to_text(date_value)),
                )
                marriages_inserted += 1

        conn.commit()
        return {
            "backup": backup_path,
            "persons_json": len(people),
            "inserted": inserted,
            "updated": updated,
            "parent_updates": parent_updates,
            "marriages": marriages_inserted,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()


if __name__ == "__main__":
    location = sys.argv[1] if len(sys.argv) > 1 else "Czarna"
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB_PATH
    result = sync_genealogy(location, db_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
