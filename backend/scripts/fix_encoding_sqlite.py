"""
Naprawia kodowanie w kolumnie typ_posiadania oraz innych polach tekstowych
w SQLite, gdzie poprzedni import mógł użyć złego kodowania.

Wykrywa zniekształcone polskie znaki (zastąpione przez �) i zastępuje je
poprawnymi wartościami.

Bezpieczny: najpierw robi backup.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.shared import fix_windows_console_encoding

fix_windows_console_encoding()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = BASE_DIR / "data" / "czarna.db"


def fix_encoding(db_path: Path = DEFAULT_DB) -> dict:
    if not db_path.exists():
        raise FileNotFoundError(f"Brak pliku: {db_path}")

    backup = db_path.with_name(f"{db_path.name}.bak_encfix_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(db_path, backup)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")

    fixes = {}

    # typ_posiadania - dokładne dopasowanie po hex (bo tekst jest zniekształcony)
    # Szukamy wierszy, gdzie hex typ_posiadania pokazuje zepsute ł/ś
    cur = conn.execute(
        "SELECT COUNT(*) FROM dzialki_wlasciciele WHERE hex(typ_posiadania) NOT LIKE '77C582'"
    )
    bad_count = cur.fetchone()[0]
    
    # Szukamy obu zniekształconych wersji przez LIKE
    conn.execute("""
        UPDATE dzialki_wlasciciele
        SET typ_posiadania = 'wlasnosc rzeczywista'
        WHERE typ_posiadania LIKE '%rzeczywista%'
    """)
    conn.execute("""
        UPDATE dzialki_wlasciciele
        SET typ_posiadania = 'wlasnosc z protokolu'
        WHERE typ_posiadania LIKE '%protoko%'
    """)

    fixes["typ_posiadania_fixed"] = conn.total_changes

    # Sprawdź też czy tabele z polskimi znakami są OK
    samples = {}
    for table in ("wlasciciele", "osoby_genealogia", "obiekty_geograficzne"):
        row = conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
        if row:
            for col, val in zip(conn.execute(f"PRAGMA table_info({table})").fetchall(), row):
                if isinstance(val, str) and any(ord(c) > 127 for c in val):
                    if "\ufffd" in val:
                        samples[f"{table}.{col[1]}"] = repr(val)[:100]
    
    fixes["corrupted_samples"] = samples

    conn.commit()
    conn.close()

    fixes["backup_path"] = str(backup)
    return fixes


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    result = fix_encoding(db)
    print(f"Backup: {result['backup_path']}")
    print(f"Fixed rows: {result['typ_posiadania_fixed']}")
    if result.get("corrupted_samples"):
        print(f"WARNING - still corrupted: {result['corrupted_samples']}")
    else:
        print("OK - no more encoding issues detected")
