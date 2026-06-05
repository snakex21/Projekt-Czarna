"""Real-install E2E test P2.1 (install + initdb only).

Instaluje prawdziwe binaria PostgreSQL 16.4 z EDB ZIP
(323 MB download → 920 MB extract, 22 649 plików)
i waliduje: download → extract → initdb → uninstall.

Ten test jest **domyślnie SKIPPED** w zwykłej regresji, bo:

- trwa 1-2 minuty (download 323 MB + extract 920 MB + initdb)
- wymaga ~1 GB wolnego dysku
- ściąga archiwum z internetu (zależność od EDB + sieci)

Dlaczego tylko install + initdb (nie pełen flow P2.1 ze start/stop)?

    Real-install bug 1.1.3 #6: extract EDB ZIP w ścieżkach dłuższych niż
    ok. 100 znaków (np. pytest ``tmp_path``) powoduje ``0xC0000135``
    (DLL not found) dla ``initdb``/``postgres``. Krótka ścieżka
    ``C:\\pg_real_install_test`` inicjalizuje klaster OK, ale start PG
    ma nadal race condition z Windows Defender scanning. Dlatego test
    waliduje **instalację** (dostarczenie binariów + extract + initdb),
    a pełen runtime E2E (start/psql/stop) jest w standalone skrypcie
    ``scripts/test_pg_portable_real_install.py``.

Uruchomienie::

    # Linux / macOS / Git Bash
    RUN_REAL_INSTALL=1 python -m pytest \\
        backend/tests/integration/test_pg_portable_real_install.py -v -s

    # PowerShell
    $env:RUN_REAL_INSTALL=1; python -m pytest \\
        backend/tests/integration/test_pg_portable_real_install.py -v -s

Wynik (cold start, 4.06.2026)::

    backend/tests/integration/test_pg_portable_real_install.py::test_install PASSED
    ================= 1 passed in ~40s ==================

Waliduje źródłowe funkcje ``launcher.services.pg_portable_service`` i
``launcher.services.pg_runtime`` — zero mocków, zero duplikacji logiki.
Odkrył 3 krytyczne bugi w ``pg_runtime.py`` (1.1.3): ``wait_for_pg_ready``
kłamał na "starting up", ``start_pg_server`` nie wykrywał natychmiastowej
śmierci ``pg_ctl``, ``stop_pg_server`` wieszał się na fast timeout.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

# === Skip gate ===
_RUN_REAL = (
    os.environ.get("RUN_REAL_INSTALL") == "1"
    or os.environ.get("PYTEST_RUN_REAL_INSTALL") == "1"
)
if not _RUN_REAL:
    pytest.skip(
        reason="Real-install test skipped (ustaw RUN_REAL_INSTALL=1 by odpalić)",
        allow_module_level=True,
    )

# === Konfiguracja ===
# Domyślny URL EDB dla Windows. Na Linux/macOS trzeba nadpisać env var.
PG_DOWNLOAD_URL = os.environ.get(
    "PG_TEST_DOWNLOAD_URL",
    "https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip",
)


def _is_port_free(port: int) -> bool:
    """True jeśli nikt nie nasłuchuje na 127.0.0.1:port."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return False
    except OSError:
        return True


@pytest.fixture
def pg_test_workspace():
    """Czysty workspace z automatycznym uninstall na końcu.

    Real-install bug 1.1.3 #6: ``initdb`` z EDB ZIP rzuca 0xC0000135
    (DLL not found) gdy ścieżka extractu jest zbyt długa. Używamy
    krótkiej ścieżki ``C:\\pg_real_install_test\\`` by tego uniknąć.
    """
    work = Path(os.environ.get("PG_TEST_WORKDIR", "C:/pg_real_install_test"))
    if work.exists():
        try:
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
            shutil.rmtree(work, ignore_errors=True)
        except Exception:
            pass
    work.mkdir(parents=True, exist_ok=True)
    install_dir = work / "postgres"
    install_dir.mkdir(parents=True, exist_ok=True)

    yield work, install_dir

    # === Cleanup: uninstall + kill ===
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        from launcher.services import pg_portable_service as pps
    except Exception as exc:
        print(f"  [CLEANUP] cannot import pps: {exc}")
        pps = None  # type: ignore

    try:
        if pps is not None and install_dir.exists():
            pps.uninstall_portable_pg(install_dir=install_dir)
            print(f"  [CLEANUP] uninstalled {install_dir}")
    except Exception as exc:
        print(f"  [CLEANUP] uninstall failed: {exc}")

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

    shutil.rmtree(work, ignore_errors=True)


def test_pg_portable_real_install(pg_test_workspace) -> None:
    """Real install P2.1: download → extract → initdb → uninstall.

    Waliduje instalację (delivery binariów) i inicjalizację klastra PG.
    Runtime E2E (start/psql/stop) jest testowany w
    ``scripts/test_pg_portable_real_install.py``.
    """
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from launcher.services import pg_portable_service as pps
    from launcher.services import pg_runtime as prt

    work, install_dir = pg_test_workspace

    print(f"\n  [SETUP] workspace={work}")
    print(f"  [SETUP] install_dir={install_dir}")
    print(f"  [SETUP] url={PG_DOWNLOAD_URL}")

    # === 1. DOWNLOAD ===
    t0 = time.time()
    archive = pps.download_pg_binary(PG_DOWNLOAD_URL, work)
    assert archive.exists(), f"archive not found: {archive}"
    size_mb = archive.stat().st_size / 1024 / 1024
    assert size_mb > 100, f"archive za mały ({size_mb:.0f} MB) — może partial?"
    t_download = time.time() - t0
    print(f"  [KROK 1/3] DOWNLOAD OK {size_mb:.0f} MB in {t_download:.1f}s")

    # === 2. EXTRACT ===
    t0 = time.time()
    bin_dir = pps.extract_pg_archive(archive, install_dir)
    # Windows: pg_ctl.exe; Unix: pg_ctl
    pg_ctl = bin_dir / ("pg_ctl.exe" if sys.platform == "win32" else "pg_ctl")
    initdb = bin_dir / ("initdb.exe" if sys.platform == "win32" else "initdb")
    assert pg_ctl.exists(), f"brak {pg_ctl}"
    assert initdb.exists(), f"brak {initdb}"
    t_extract = time.time() - t0
    print(f"  [KROK 2/3] EXTRACT OK ({t_extract:.1f}s) -> {bin_dir}")

    # === 3. INITDB ===
    paths = pps.get_portable_pg_paths(install_dir=install_dir)
    config = prt.PgServerConfig(paths=paths, port=5444)
    assert paths.pg_version, "pg_version puste — extract się nie udał?"
    print(f"  [KROK 3/3] INITDB pg={paths.pg_version}")

    t0 = time.time()
    result = prt.init_pg_data_dir(config)
    assert result.ok, f"init_pg_data_dir failed: {result.message}"
    t_init = time.time() - t0
    print(f"  [KROK 3/3] INITDB OK ({t_init:.1f}s): {result.message[:80]}")

    # Walidacja: PG_VERSION + klastra
    pg_version_file = paths.data_dir / "PG_VERSION"
    assert pg_version_file.exists(), f"brak {pg_version_file}"
    pg_ver = pg_version_file.read_text(encoding="utf-8").strip()
    # PG_VERSION zawiera TYLKO major version (np. "16"),
    # a paths.pg_version ma full semver ("16.4"). Sprawdź że major się zgadza.
    pg_major = pg_ver.split(".")[0]
    paths_major = paths.pg_version.split(".")[0]
    assert pg_major == paths_major, (
        f"PG_VERSION major={pg_major} != paths.pg_version major={paths_major} "
        f"(pg_ver={pg_ver!r}, paths.pg_version={paths.pg_version!r})"
    )
    pg_hba = paths.data_dir / "pg_hba.conf"
    assert pg_hba.exists(), f"brak {pg_hba}"
    assert pg_hba.stat().st_size > 100, f"pg_hba.conf za mały: {pg_hba.stat().st_size}"
    print(f"  [VERIFY] PG_VERSION={pg_ver} (major={pg_major}), pg_hba.conf={pg_hba.stat().st_size}B")

    # Podsumowanie
    total = t_download + t_extract + t_init
    print(f"\n  [SUKCES] Real install OK w {total:.1f}s (3/3 kroków)")
