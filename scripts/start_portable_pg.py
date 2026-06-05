"""Uruchamia portable PG server (port 5444) w tle.

Użycie::

    python scripts/start_portable_pg.py

Sprawdza czy portable PG jest zainstalowany w <root>/.runtime/postgres/,
startuje serwer, czeka na ready, drukuje status.

Aby zatrzymać serwer::

    python scripts/stop_portable_pg.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from launcher.services import pg_portable_service as pps
    from launcher.services import pg_runtime as prt

    install_dir = project_root / ".runtime" / "postgres"

    if not pps.portable_pg_installed(install_dir=install_dir):
        print(f"  [ERROR] Portable PG nie zainstalowany w {install_dir}")
        print(f"          Uruchom: python scripts/install_portable_pg.py")
        return 1

    paths = pps.get_portable_pg_paths(install_dir=install_dir)
    config = prt.PgServerConfig(paths=paths, port=5444)

    # Sprawdź czy już działa
    print(f"  [CHECK] Czy serwer już działa na :5444...")
    try:
        # Spróbuj się połączyć
        import socket
        with socket.create_connection(("127.0.0.1", 5444), timeout=1.0):
            print(f"  [INFO] Serwer już działa na :5444")
            return 0
    except OSError:
        pass

    # Start
    print(f"  [START] Uruchamiam portable PG (port 5444)...")
    t0 = time.time()
    try:
        handle = prt.start_pg_server(config, ready_timeout=30.0)
    except Exception as exc:
        print(f"  [ERROR] start_pg_server: {exc}")
        return 1

    elapsed = time.time() - t0
    print(f"  [OK] Uruchomiony PID={handle.pid} w {elapsed:.1f}s")
    print(f"  [INFO] port: 5444")
    print(f"  [INFO] bin:  {paths.bin_dir}")
    print(f"  [INFO] data: {paths.data_dir}")
    print(f"  [INFO] Aby zatrzymać: python scripts/stop_portable_pg.py")
    print(f"\n  Teraz uruchom aplikację (launcher) — powinna się połączyć OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
