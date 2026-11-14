"""Zasilanie pustej bazy SQLite danymi demo z ``data/locations/<miejscowość>/``.

Świeży klon repozytorium ma pustą bazę, więc mapa jest pusta. Ten moduł
importuje commitowane pliki JSON (obiekty mapy, genealogia, demografia,
konfiguracja mapy) do SQLite.

Uruchomienie:
    python -m backend.scripts.seed_demo            # tylko gdy baza jest pusta
    python -m backend.scripts.seed_demo --force    # nadpisuje istniejące dane
albo automatycznie przy starcie serwera: ``SEED_DEMO_DATA=1``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from .. import config


def database_is_empty(db_path: Path) -> bool:
    """``True`` gdy baza nie istnieje albo nie ma żadnych obiektów mapy."""
    db_path = Path(db_path)
    if not db_path.exists() or db_path.stat().st_size == 0:
        return True
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM obiekty_geograficzne").fetchone()
    except sqlite3.OperationalError:
        return True
    return not row or row[0] == 0


def seed_if_empty(
    db_path: Optional[Path] = None,
    location: Optional[str] = None,
    locations_dir: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Importuje dane demo, gdy baza jest pusta (albo zawsze przy ``force``).

    Zwraca ``{"status": "seeded"|"skipped", "counts": {...}, ...}``.
    """
    if config.DB_ENGINE != "sqlite":
        raise RuntimeError("Seed danych demo obsługuje tylko DB_ENGINE=sqlite.")
    db_path = Path(db_path or config.DB_PATH)
    location = location or config.ACTIVE_LOCATION
    locations_dir = Path(locations_dir or config.BACKUP_DIR)

    if not force and not database_is_empty(db_path):
        return {"status": "skipped", "reason": "baza zawiera już dane", "db_path": str(db_path)}

    from ..scripts.import_sqlite_backup import import_location

    counts = import_location(location, db_path, locations_dir=locations_dir)
    return {"status": "seeded", "counts": counts, "db_path": str(db_path), "location": location}
