"""Install portable PG do <root>/.runtime/postgres/ (produkcyjna lokalizacja).

Robi:
  1. Download ZIP z EDB (323 MB)
  2. Extract do <root>/.runtime/postgres/
  3. initdb (klaster gotowy)
  4. Aktualizuje backend/.env (DB_PORT=5444, PGPASSWORD, etc.)
  5. NIE startuje serwera (to user robi ręcznie)
  6. NIE usuwa (prawdziwa instalacja)

Użycie::

    python scripts/install_portable_pg.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


DEFAULT_DOWNLOAD_URL = (
    "https://get.enterprisedb.com/postgresql/"
    "postgresql-16.4-1-windows-x64-binaries.zip"
)


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from launcher.services import pg_portable_service as pps
    from launcher.services import pg_runtime as prt

    install_dir = project_root / ".runtime" / "postgres"
    print(f"\n  [SETUP] install_dir={install_dir}")

    # Czy już zainstalowany?
    if pps.portable_pg_installed(install_dir=install_dir):
        print(f"  [INFO] Portable PG już zainstalowany w {install_dir}")
        print(f"         pg_version={pps.get_portable_pg_paths(install_dir).pg_version}")
        # Sprawdź czy dane zainicjalizowane
        if pps.is_pg_initialized(install_dir=install_dir):
            print(f"         data: zainicjalizowany")
        else:
            print(f"         data: NIE zainicjalizowany — initdb...")
            paths = pps.get_portable_pg_paths(install_dir=install_dir)
            config = prt.PgServerConfig(paths=paths, port=5444)
            t0 = time.time()
            result = prt.init_pg_data_dir(config)
            if not result.ok:
                print(f"  [ERROR] initdb: {result.message}")
                return 1
            print(f"  [OK] initdb in {time.time() - t0:.1f}s")
    else:
        install_dir.mkdir(parents=True, exist_ok=True)
        archive = project_root / "postgresql-16.4-1-windows-x64-binaries.zip"

        # Download jeśli trzeba
        if not archive.exists() or archive.stat().st_size < 100 * 1024 * 1024:
            print(f"  [1/3] DOWNLOAD {DEFAULT_DOWNLOAD_URL}")
            t0 = time.time()
            archive = pps.download_pg_binary(DEFAULT_DOWNLOAD_URL, project_root)
            size_mb = archive.stat().st_size / 1024 / 1024
            print(f"         {size_mb:.0f} MB in {time.time() - t0:.1f}s")
        else:
            size_mb = archive.stat().st_size / 1024 / 1024
            print(f"  [1/3] DOWNLOAD cache hit: {size_mb:.0f} MB")

        # Extract
        print(f"  [2/3] EXTRACT")
        t0 = time.time()
        bin_dir = pps.extract_pg_archive(archive, install_dir)
        print(f"         OK in {time.time() - t0:.1f}s -> {bin_dir}")

        # initdb
        paths = pps.get_portable_pg_paths(install_dir=install_dir)
        config = prt.PgServerConfig(paths=paths, port=5444)
        print(f"  [3/3] INITDB pg={paths.pg_version}")
        t0 = time.time()
        result = prt.init_pg_data_dir(config)
        if not result.ok:
            print(f"  [ERROR] initdb: {result.message}")
            return 1
        print(f"         OK in {time.time() - t0:.1f}s: {result.message[:80]}")

    # Aktualizuj .env (port 5432 → 5444, ścieżka do binarek)
    env_file = project_root / "backend" / ".env"
    if env_file.exists():
        text = env_file.read_text(encoding="utf-8")
        new_text = text
        # Zmień port
        if "DB_PORT=5432" in new_text:
            new_text = new_text.replace("DB_PORT=5432", "DB_PORT=5444")
            print(f"\n  [ENV] DB_PORT: 5432 → 5444 (portable PG)")
        if "DB_PORT=5444" not in new_text and "DB_PORT=" in new_text:
            # fallback: regex replace
            import re
            new_text = re.sub(r"DB_PORT=\d+", "DB_PORT=5444", new_text)

        if new_text != text:
            env_file.write_text(new_text, encoding="utf-8")
            print(f"  [ENV] zaktualizowano {env_file.name}")
        else:
            print(f"  [ENV] port już 5444 — bez zmian")
    else:
        print(f"  [WARN] {env_file} nie istnieje — nie aktualizuję .env")

    print(f"\n  [SUKCES] Portable PG zainstalowany w {install_dir}")
    print(f"  [INFO] Aby uruchomić serwer PG:")
    print(f"           python scripts/start_portable_pg.py")
    print(f"  [INFO] Aby odinstalować:")
    print(f"           python scripts/uninstall_portable_pg.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
