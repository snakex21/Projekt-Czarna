"""Zasila bazę SQLite danymi demo, aby świeży klon pokazywał mapę.

Użycie (z katalogu głównego repozytorium):
    python -m backend.scripts.seed_demo              # tylko gdy baza jest pusta
    python -m backend.scripts.seed_demo --force      # nadpisz istniejące dane
    python -m backend.scripts.seed_demo --location Czarna --db data/czarna.db
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed danych demo do SQLite")
    parser.add_argument("--force", action="store_true", help="nadpisz dane, nawet gdy baza nie jest pusta")
    parser.add_argument("--location", default=None, help="nazwa miejscowości (domyślnie ACTIVE_LOCATION)")
    parser.add_argument("--db", default=None, help="ścieżka bazy SQLite (domyślnie DB_PATH)")
    args = parser.parse_args(argv)

    from backend import config
    from backend.services.demo_seed import seed_if_empty

    if config.DB_ENGINE != "sqlite":
        print("Seed obsługuje tylko DB_ENGINE=sqlite (ustaw DB_ENGINE=sqlite w backend/.env).")
        return 2
    try:
        result = seed_if_empty(
            db_path=Path(args.db).resolve() if args.db else None,
            location=args.location,
            force=args.force,
        )
    except FileNotFoundError as exc:
        print(f"Błąd: {exc}")
        return 1
    if result["status"] == "skipped":
        print(f"Pominięto: {result['reason']} ({result['db_path']}). Użyj --force, aby nadpisać.")
    else:
        print(f"Zasilono bazę {result['db_path']} danymi miejscowości {result['location']}: {result['counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
