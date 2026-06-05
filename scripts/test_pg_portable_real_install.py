"""Real-install E2E P2.1 — pełen flow z prawdziwymi binariami PostgreSQL 16.4.

Ten skrypt jest **standalone mirrorem** pytest testu
``backend/tests/integration/test_pg_portable_real_install.py``, ale z
**pełnym runtime E2E** (start → psql SELECT 1 → createdb → stop), podczas
gdy pytest test został uproszczony do install + initdb only (z powodu
race condition startu PG z Windows Defender scanning na długich ścieżkach).

Po co to dwa podejścia:

- **pytest test** (domyślnie skipped, odpala się z ``RUN_REAL_INSTALL=1``):
  waliduje **instalację** (download + extract + initdb + cleanup) i
  może być wpięty do CI matrix dla smoke testu (~35s z cache ZIP).
- **ten skrypt**: waliduje **pełen runtime P2.1** (start + psql + createdb
  + stop z 4-etapowym fallback chain). Mirroruje logikę z MCP temp
  ``pg_real_install_v2.py``, ale z auto-cleanup i czytelnym outputem.

Użycie::

    # PowerShell
    python scripts/test_pg_portable_real_install.py

    # z nadpisaniem domyślnych
    python scripts/test_pg_portable_real_install.py --port 5446 --workdir D:\\pg_test

Co sprawdza (7/7 kroków, ~24s warm cache):

    1. Download archiwum EDB ZIP (323 MB @ 18 MB/s ≈ 18s cold, <1s warm)
    2. Extract (920 MB, 22 649 plików, ≈ 11s)
    3. initdb (5s, klaster PG 16.4 gotowy)
    4. start_pg_server + wait_for_pg_ready (FIX 1.1.3 dwuetapowy, 1-3s)
    5. psql "SELECT 1" — faktyczne połączenie z bazą
    6. createdb test_p2_1 + SELECT current_database() → "test_p2_1"
    7. stop_pg_server (FIX 1.1.3 4-etapowy fallback chain, 0-10s)
    + uninstall + taskkill cleanup

Odkrył 3 krytyczne bugi w ``pg_runtime.py`` (1.1.3):
- ``wait_for_pg_ready`` kłamał na "starting up" (teraz 2-etapowy: socket + psql)
- ``start_pg_server`` nie wykrywał natychmiastowej śmierci ``pg_ctl`` (FIX: proc.poll())
- ``stop_pg_server`` wieszał się na fast timeout (FIX: 4-etapowy fallback)
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_DOWNLOAD_URL = (
    "https://get.enterprisedb.com/postgresql/"
    "postgresql-16.4-1-windows-x64-binaries.zip"
)
DEFAULT_PORT = 5445
DEFAULT_WORKDIR = "C:/pg_real_install_test"


def _is_port_free(port: int) -> bool:
    """True jeśli nikt nie nasłuchuje na 127.0.0.1:port."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return False
    except OSError:
        return True


def _kill_postgres() -> None:
    """Awaryjne zabicie wszystkich procesów postgres (best-effort)."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/IM", "postgres.exe", "/T"],
            capture_output=True, timeout=5,
        )
    else:
        subprocess.run(
            ["pkill", "-9", "-f", "postgres"],
            capture_output=True, timeout=5,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Real-install E2E test P2.1 (download + extract + initdb + "
        "start + psql + createdb + stop).",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"Port dla PG (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--workdir", default=DEFAULT_WORKDIR,
        help=f"Katalog roboczy (default: {DEFAULT_WORKDIR})",
    )
    parser.add_argument(
        "--url", default=DEFAULT_DOWNLOAD_URL,
        help="URL do archiwum EDB ZIP (default: Windows binaries 16.4)",
    )
    parser.add_argument(
        "--skip-start-stop", action="store_true",
        help="Pomiń runtime E2E (tylko install + initdb) — szybsze (~35s)",
    )
    args = parser.parse_args()

    # Sprawdź port
    if not _is_port_free(args.port):
        print(f"  [ERROR] Port {args.port} jest zajęty — użyj --port inny")
        return 2

    # Setup workspace
    work = Path(args.workdir)
    if work.exists():
        print(f"  [SETUP] czyszczę stary workspace {work}...")
        _kill_postgres()
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    install_dir = work / "postgres"
    install_dir.mkdir(parents=True, exist_ok=True)

    # Dodaj root projektu do sys.path (bo skrypt może być odpalany z różnych CWD)
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from launcher.services import pg_portable_service as pps
    from launcher.services import pg_runtime as prt

    print(f"\n  [SETUP] workspace={work}")
    print(f"  [SETUP] install_dir={install_dir}")
    print(f"  [SETUP] port={args.port}")
    print(f"  [SETUP] url={args.url}\n")

    success = True
    handle = None  # for cleanup

    try:
        # === 1. DOWNLOAD ===
        t0 = time.time()
        archive = pps.download_pg_binary(args.url, work)
        if not archive.exists():
            raise RuntimeError(f"archive not found: {archive}")
        size_mb = archive.stat().st_size / 1024 / 1024
        if size_mb < 100:
            raise RuntimeError(f"archive za mały ({size_mb:.0f} MB) — partial?")
        t_download = time.time() - t0
        print(f"  [KROK 1/7] DOWNLOAD OK {size_mb:.0f} MB in {t_download:.1f}s")

        # === 2. EXTRACT ===
        t0 = time.time()
        bin_dir = pps.extract_pg_archive(archive, install_dir)
        is_win = sys.platform == "win32"
        pg_ctl = bin_dir / ("pg_ctl.exe" if is_win else "pg_ctl")
        initdb = bin_dir / ("initdb.exe" if is_win else "initdb")
        psql_exe = bin_dir / ("psql.exe" if is_win else "psql")
        createdb = bin_dir / ("createdb.exe" if is_win else "createdb")
        for exe in (pg_ctl, initdb, psql_exe, createdb):
            if not exe.exists():
                raise RuntimeError(f"brak {exe} (extract niekompletny?)")
        t_extract = time.time() - t0
        print(f"  [KROK 2/7] EXTRACT OK ({t_extract:.1f}s) -> {bin_dir}")

        # === 3. INITDB ===
        paths = pps.get_portable_pg_paths(install_dir=install_dir)
        config = prt.PgServerConfig(paths=paths, port=args.port)
        if not paths.pg_version:
            raise RuntimeError("pg_version puste — extract się nie udał?")
        print(f"  [KROK 3/7] INITDB pg={paths.pg_version}")

        t0 = time.time()
        result = prt.init_pg_data_dir(config)
        if not result.ok:
            raise RuntimeError(f"init_pg_data_dir failed: {result.message}")
        t_init = time.time() - t0
        print(f"  [KROK 3/7] INITDB OK ({t_init:.1f}s): {result.message[:80]}")

        if args.skip_start_stop:
            print("\n  [SUKCES] Install + initdb OK (--skip-start-stop)")
            return 0

        # === 4. START + WAIT_READY (FIX 1.1.3) ===
        t0 = time.time()
        handle = prt.start_pg_server(config, ready_timeout=30.0)
        if handle.pid <= 0:
            raise RuntimeError(f"nieprawidłowy PID: {handle.pid}")
        if not prt.is_pg_server_running(handle):
            raise RuntimeError(
                f"PG nie nasłuchuje po starcie (pg_ctl pid={handle.pid})"
            )
        t_start = time.time() - t0
        print(f"  [KROK 4/7] START OK PID={handle.pid} ({t_start:.1f}s)")

        # === 5. PSQL "SELECT 1" ===
        env = os.environ.copy()
        env["PGPASSWORD"] = config.password or ""
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

        t0 = time.time()
        r = subprocess.run(
            [
                str(psql_exe), "-h", "127.0.0.1", "-p", str(args.port),
                "-U", config.username, "-d", "postgres", "-c", "SELECT 1",
            ],
            capture_output=True, text=True, env=env, timeout=10,
        )
        if r.returncode != 0 or "1" not in r.stdout:
            raise RuntimeError(
                f"psql SELECT 1 failed (rc={r.returncode}):\n"
                f"  stdout: {r.stdout!r}\n  stderr: {r.stderr!r}"
            )
        t_psql = time.time() - t0
        print(f"  [KROK 5/7] PSQL 'SELECT 1' OK ({t_psql:.1f}s): "
              f"{r.stdout.strip()!r}")

        # === 6. CREATEDB test_p2_1 + walidacja ===
        r = subprocess.run(
            [
                str(createdb), "-h", "127.0.0.1", "-p", str(args.port),
                "-U", config.username, "test_p2_1",
            ],
            capture_output=True, text=True, env=env, timeout=10,
        )
        if r.returncode != 0:
            raise RuntimeError(
                f"createdb failed (rc={r.returncode}):\n"
                f"  stdout: {r.stdout!r}\n  stderr: {r.stderr!r}"
            )
        r = subprocess.run(
            [
                str(psql_exe), "-h", "127.0.0.1", "-p", str(args.port),
                "-U", config.username, "-d", "test_p2_1",
                "-c", "SELECT current_database()",
            ],
            capture_output=True, text=True, env=env, timeout=10,
        )
        if r.returncode != 0 or "test_p2_1" not in r.stdout:
            raise RuntimeError(
                f"psql test_p2_1 failed:\n  stdout: {r.stdout!r}\n"
                f"  stderr: {r.stderr!r}"
            )
        print(f"  [KROK 6/7] CREATEDB test_p2_1 OK: {r.stdout.strip()!r}")

        # === 7. STOP (FIX 1.1.3 — 4-etapowy fallback chain) ===
        t0 = time.time()
        result = prt.stop_pg_server(handle, mode="fast", timeout=10.0)
        if not result.ok:
            raise RuntimeError(f"stop_pg_server failed: {result.message}")
        method = result.details.get("method", "?")
        t_stop = time.time() - t0
        print(f"  [KROK 7/7] STOP OK method={method} ({t_stop:.1f}s): "
              f"{result.message[:80]}")
        handle = None  # already stopped

        # Asercja końcowa
        time.sleep(1.0)
        if not _is_port_free(args.port):
            raise RuntimeError(
                f"port {args.port} nadal zajęty po stop — coś nie doczyściło"
            )

        total = t_download + t_extract + t_init + t_start + t_psql + t_stop
        print(f"\n  [SUKCES] Real install OK w {total:.1f}s (7/7 kroków)")
        return 0

    except Exception as exc:
        success = False
        print(f"\n  [FAIL] {type(exc).__name__}: {exc}")
        return 1

    finally:
        # === Cleanup: stop + uninstall + kill + rmtree ===
        if handle is not None:
            try:
                prt.stop_pg_server(handle, mode="immediate", timeout=5.0)
            except Exception:
                pass
        try:
            if install_dir.exists():
                pps.uninstall_portable_pg(install_dir=install_dir)
                print(f"  [CLEANUP] uninstalled {install_dir}")
        except Exception as exc:
            print(f"  [CLEANUP] uninstall failed: {exc}")
        _kill_postgres()
        shutil.rmtree(work, ignore_errors=True)
        if success:
            print(f"  [CLEANUP] cleaned {work}")


if __name__ == "__main__":
    sys.exit(main())
