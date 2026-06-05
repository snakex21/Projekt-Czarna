"""Zatrzymuje portable PG server (graceful stop).

Użycie::

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
        print(f"  [INFO] Portable PG nie zainstalowany w {install_dir} — nic do roboty")
        return 0

    paths = pps.get_portable_pg_paths(install_dir=install_dir)
    config = prt.PgServerConfig(paths=paths, port=5444)

    # Sprawdź PID
    pid_file = paths.data_dir / "postmaster.pid"
    pid = None
    if pid_file.exists():
        first_line = pid_file.read_text(encoding="utf-8").splitlines()[0].strip()
        if first_line.isdigit():
            pid = int(first_line)

    if pid is None:
        print(f"  [INFO] Brak postmaster.pid — serwer nie działa")
        return 0

    # Stop z 4-etapowym fallback
    handle = prt.ServerHandle(
        pid=pid, port=5444, config=config, proc=None,
    )

    print(f"  [STOP] PID={pid}...")
    t0 = time.time()
    try:
        result = prt.stop_pg_server(handle, mode="fast", timeout=10.0)
    except Exception as exc:
        print(f"  [ERROR] stop_pg_server: {exc}")
        # Awaryjny taskkill
        if sys.platform == "win32":
            os.system(f'taskkill /F /PID {pid} /T 2>nul')
        return 1

    elapsed = time.time() - t0
    method = result.details.get("method", "?")
    print(f"  [OK] Zatrzymany method={method} w {elapsed:.1f}s: {result.message[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
