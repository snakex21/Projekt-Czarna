"""Install PostgreSQL 16 + PostGIS + schemat aplikacji (P2.2 unattended, full).

Co robi (wszystko bez klikania):
  1. Sprawdza uprawnienia admina (Windows: Security.Principal)
  2. Jeśli nie admin → UAC prompt (ShellExecuteW "runas") i re-run
  3. Download PostgreSQL installer EDB (357 MB) do <root>/cache/
  4. Uruchamia w trybie unattended (port 5432, hasło 1234, --enable-components)
  5. Czeka na Windows Service "postgresql-x64-16" (max 5 min)
  6. Download PostGIS bundle z OSGeo (100 MB)
  7. Install PostGIS (NSIS /S flag, instaluje się do wykrytego PG 16)
  8. CREATE DATABASE mapa_czarna_db
  9. CREATE EXTENSION postgis
  10. Wykonuje LOCATION_DB_SCHEMA (tworzy 10 tabel + PostGIS geometry type)
  11. Aktualizuje backend/.env (DB_ENGINE=postgresql, DB_PORT=5432)
  12. Aktualizuje backend/.postgres.env (LAUNCHER_DB_PASSWORD=1234)

Użycie::

    python scripts/install_pg_unattended.py

Wymaga: Windows + uprawnienia admina (UAC prompt na początku).

Po zakończeniu zrestartuj aplikację — powinna się łączyć z PG 16.4
+ PostGIS na localhost:5432, baza mapa_czarna_db z pełnym schematem.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
import urllib.request
import shutil
from pathlib import Path


# === Konfiguracja ===
PG_INSTALLER_URL = (
    "https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64.exe"
)
POSTGIS_INSTALLER_URL = (
    "https://download.osgeo.org/postgis/windows/pg16/"
    "postgis-bundle-pg16x64-setup-3.6.2-1.exe"
)
PG_INSTALLER_SIZE_MB = 357
POSTGIS_INSTALLER_SIZE_MB = 100
PG_PASSWORD = "1234"
PG_PORT = 5432
PG_DB_NAME = "mapa_czarna_db"
PG_SERVICE_NAME = "postgresql-x64-16"
PG_INSTALL_DIR = r"C:\Program Files\PostgreSQL\16"
# EDB installer 16.4: allowed = server pgAdmin stackbuilder commandlinetools
# (PostGIS NIE jest w tej liście — instalujemy OSOBNO z OSGeo w kroku 6)
INSTALL_COMPONENTS = "server,pgAdmin,commandlinetools"
SERVICE_START_TIMEOUT = 300  # 5 min
SCHEMA_TIMEOUT = 30


def _no_window_flags() -> int:
    """Flagi subprocess ukrywające migające okna konsoli na Windows."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def _run_text(cmd, **kwargs):
    """Uruchom subprocess z bezpiecznym dekodowaniem outputu na Windows.

    Narzędzia PostgreSQL potrafią wypisywać komunikaty w lokalnym kodowaniu
    Windows (np. CP1250), a ``text=True`` bez ``errors=replace`` potrafi
    przerwać instalację przez ``UnicodeDecodeError``. Instalator nie może
    wywracać GUI tylko dlatego, że psql wypisał polski komunikat.
    """
    kwargs.setdefault("creationflags", _no_window_flags())
    return subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )


def is_pg_service_registered() -> bool:
    """Czy usługa PostgreSQL 16 istnieje w Windows SCM."""
    try:
        result = _run_text(
            ["sc", "query", PG_SERVICE_NAME],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0 and PG_SERVICE_NAME in (result.stdout or "")
    except Exception:
        return False


def is_pg_install_healthy() -> bool:
    """Czy instalacja PG wygląda kompletnie: psql.exe + usługa Windows."""
    psql = Path(PG_INSTALL_DIR) / "bin" / "psql.exe"
    return psql.exists() and is_pg_service_registered()


def prepare_stale_pg_install_dir() -> bool:
    r"""Obsłuż katalog po niepełnej deinstalacji PostgreSQL.

    EDB uninstaller potrafi zostawić ``C:\Program Files\PostgreSQL\16`` mimo
    braku usługi ``postgresql-x64-16``. Samo istnienie katalogu NIE oznacza
    działającej instalacji. Gdy katalog jest osierocony, przenosimy go na bok,
    żeby fresh installer mógł wykonać pełną instalację.
    """
    install_dir = Path(PG_INSTALL_DIR)
    if not install_dir.exists() or is_pg_install_healthy():
        return True

    backup_dir = install_dir.with_name(f"{install_dir.name}_old_{int(time.time())}")
    print(
        f"  [INFO] Wykryto osierocony katalog PG bez działającej usługi: {install_dir}"
    )
    print(f"         Przenoszę na bok: {backup_dir}")
    try:
        shutil.move(str(install_dir), str(backup_dir))
        return True
    except Exception as exc:
        print(f"  [ERROR] Nie mogę przenieść starego katalogu PG: {exc}")
        print("          Zamknij programy używające tego katalogu albo usuń go ręcznie jako administrator.")
        return False


# === Admin check + self-elevation ===
def is_admin() -> bool:
    if sys.platform != "win32":
        return os.geteuid() == 0
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def request_admin_elevation():
    if sys.platform != "win32":
        print("  [ERROR] Ten skrypt wymaga Windows + admina")
        sys.exit(1)
    print("  [UAC] Brak uprawnień admina — proszę o elevation...")
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{__file__}"', None, 1,
    )
    rc = int(rc)
    if rc <= 32:
        print(f"  [ERROR] UAC odrzucony (rc={rc})")
        sys.exit(1)
    sys.exit(0)


# === Download helper ===
def _download(url: str, dest: Path, label: str) -> None:
    print(f"  [DOWNLOAD] {label}")
    print(f"             {url}")
    print(f"             → {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    response = urllib.request.urlopen(req, timeout=60)
    total = int(response.headers.get("Content-Length", 0))
    chunk = 1024 * 1024
    downloaded = 0
    last_mb = 0

    with open(dest, "wb") as f:
        t0 = time.time()
        while True:
            buf = response.read(chunk)
            if not buf:
                break
            f.write(buf)
            downloaded += len(buf)
            mb = downloaded // (1024 * 1024)
            if mb - last_mb >= 25 or downloaded == total:
                pct = downloaded * 100 // total if total else 0
                speed = downloaded / (time.time() - t0) / (1024 * 1024)
                print(f"             {mb}/{total // (1024 * 1024)} MB ({pct}%) "
                      f"@ {speed:.1f} MB/s", flush=True)
                last_mb = mb

    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"             OK {size_mb:.0f} MB in {time.time() - t0:.1f}s")


def download_or_skip(url: str, dest: Path, label: str) -> None:
    if dest.exists() and dest.stat().st_size > 50 * 1024 * 1024:
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"  [CACHE] {label} już ściągnięty: {size_mb:.0f} MB")
    else:
        _download(url, dest, label)


# === 1. PG install ===
def run_pg_installer(installer: Path) -> int:
    print(f"  [1/7] INSTALL PostgreSQL 16 (unattended)")
    print(f"          komponenty: {INSTALL_COMPONENTS}")
    print(f"          port: {PG_PORT}, hasło: {'*' * len(PG_PASSWORD)}")
    print(f"          katalog: {PG_INSTALL_DIR}")
    print(f"          To może potrwać 3-5 min...")

    cmd = [
        str(installer),
        "--mode", "unattended",
        "--unattendedmodeui", "none",
        "--superpassword", PG_PASSWORD,
        "--serverport", str(PG_PORT),
        "--prefix", PG_INSTALL_DIR,
        "--datadir", os.path.join(PG_INSTALL_DIR, "data"),
        "--enable-components", INSTALL_COMPONENTS,
        "--install_runtimes", "1",
    ]
    t0 = time.time()
    proc = _run_text(cmd, capture_output=True, timeout=900)
    elapsed = time.time() - t0
    if proc.returncode != 0:
        print(f"  [ERROR] PG installer rc={proc.returncode} po {elapsed:.1f}s")
        if proc.stderr:
            print(f"  STDERR: {proc.stderr[:300]}")
        return proc.returncode
    print(f"          OK w {elapsed:.1f}s")
    return 0


# === 2. Wait for service ===
def wait_for_pg_service(timeout: int) -> bool:
    print(f"  [2/7] WAIT FOR SERVICE '{PG_SERVICE_NAME}' (max {timeout}s)")
    if not is_pg_service_registered():
        print(f"  [ERROR] Usługa {PG_SERVICE_NAME} nie istnieje — instalacja PG jest niepełna")
        return False
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = _run_text(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Service -Name '{PG_SERVICE_NAME}' -ErrorAction SilentlyContinue).Status"],
            capture_output=True, timeout=5,
        )
        status = r.stdout.strip()
        if status == "Running":
            print(f"          OK Running po {time.time() - t0:.1f}s")
            return True
        elif status:
            print(f"          [{time.time()-t0:5.0f}s] status={status}", flush=True)
        time.sleep(3)
    print(f"  [ERROR] Timeout {timeout}s")
    return False


# === 3. PostGIS install (NSIS) ===
def run_postgis_installer(installer: Path) -> bool:
    print(f"  [3/7] INSTALL PostGIS bundle (NSIS /S)")
    print(f"          Bundle wykrywa PG automatycznie (registry)")
    t0 = time.time()
    proc = _run_text(
        [str(installer), "/S"],
        capture_output=True, timeout=600,
    )
    elapsed = time.time() - t0
    if proc.returncode != 0:
        print(f"  [ERROR] PostGIS rc={proc.returncode} po {elapsed:.1f}s")
        if proc.stderr:
            print(f"  STDERR: {proc.stderr[:300]}")
        return False
    control_file = Path(PG_INSTALL_DIR) / "share" / "extension" / "postgis.control"
    for _ in range(60):
        if control_file.exists():
            break
        time.sleep(1)
    else:
        print(f"  [ERROR] Brak pliku PostGIS extension: {control_file}")
        return False
    print(f"          OK w {elapsed:.1f}s")
    return True


# === 4. Create database ===
def create_database() -> bool:
    print(f"  [4/7] CREATE DATABASE '{PG_DB_NAME}'")
    psql = os.path.join(PG_INSTALL_DIR, "bin", "psql.exe")
    if not os.path.exists(psql):
        print(f"  [ERROR] Brak {psql}")
        return False
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_PASSWORD
    env["PATH"] = os.path.join(PG_INSTALL_DIR, "bin") + os.pathsep + env.get("PATH", "")
    r = _run_text(
        [psql, "-h", "127.0.0.1", "-p", str(PG_PORT),
         "-U", "postgres", "-d", "postgres",
         "-c", f"CREATE DATABASE {PG_DB_NAME};"],
        capture_output=True, env=env, timeout=30,
    )
    if r.returncode == 0:
        print(f"          OK")
        return True

    stderr = r.stderr or ""
    stdout = r.stdout or ""
    combined = f"{stdout}\n{stderr}".lower()
    if "already exists" in combined or "już istnieje" in combined or "juz istnieje" in combined:
        print(f"          INFO: baza już istnieje")
        return True
    print(f"  [ERROR] create db: {stderr[:200] or stdout[:200] or f'rc={r.returncode}'}")
    return False


# === 5. PostGIS extension + schema ===
def apply_postgis_and_schema() -> bool:
    print(f"  [5/7] POSTGIS EXTENSION + LOCATION_DB_SCHEMA")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from launcher.db.postgres import (
            enable_postgis, execute_schema,
        )
        from launcher.db.schemas import LOCATION_DB_SCHEMA
    except Exception as exc:
        print(f"  [ERROR] Import: {exc}")
        return False

    # Nie czytaj .postgres.env w trakcie instalacji: może jeszcze nie istnieć
    # albo zawierać stare hasło. Instalator zna hasło nadane EDB installerowi.
    cfg = {
        "host": "127.0.0.1",
        "port": PG_PORT,
        "user": "postgres",
        "password": PG_PASSWORD,
    }
    print(f"          config: host={cfg['host']} port={cfg['port']} user={cfg['user']}")

    ok, msg = enable_postgis(cfg, PG_DB_NAME)
    print(f"          enable_postgis: {ok} → {msg[:80]}")
    if not ok:
        return False

    ok, msg = execute_schema(cfg, PG_DB_NAME, LOCATION_DB_SCHEMA)
    print(f"          execute_schema: {ok} → {str(msg)[:80]}")
    return ok


# === 6. Update .env ===
def update_env_files(project_root: Path) -> None:
    print(f"  [6/7] UPDATE backend/.env + backend/.postgres.env")

    # main .env
    env_file = project_root / "backend" / ".env"
    if env_file.exists():
        text = env_file.read_text(encoding="utf-8")
        updates = {
            "DB_ENGINE": "postgresql",
            "DB_HOST": "localhost",
            "DB_PORT": str(PG_PORT),
            "DB_USER": "postgres",
            "DB_PASSWORD": PG_PASSWORD,
            "DB_NAME": PG_DB_NAME,
        }
        new_text = text
        import re
        for key, value in updates.items():
            pattern = rf"^{re.escape(key)}=.*$"
            replacement = f"{key}={value}"
            if re.search(pattern, new_text, flags=re.MULTILINE):
                new_text = re.sub(pattern, replacement, new_text, flags=re.MULTILINE)
            else:
                if new_text and not new_text.endswith("\n"):
                    new_text += "\n"
                new_text += f"{replacement}\n"
        if new_text != text:
            env_file.write_text(new_text, encoding="utf-8")
            print(
                f"          {env_file.name}: DB_ENGINE=postgresql, "
                f"DB_HOST=localhost, DB_PORT={PG_PORT}, DB_NAME={PG_DB_NAME}"
            )
    else:
        print(f"  [WARN] {env_file} nie istnieje")

    # launcher .postgres.env
    pg_env = project_root / "backend" / ".postgres.env"
    new_lines = [
        "# PostgreSQL configuration for launcher (mirrors backend/.env:DB_*)",
        f"LAUNCHER_DB_HOST=localhost",
        f"LAUNCHER_DB_PORT={PG_PORT}",
        f"LAUNCHER_DB_USER=postgres",
        f"LAUNCHER_DB_PASSWORD={PG_PASSWORD}",
    ]
    pg_env.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"          {pg_env.name}: LAUNCHER_DB_PASSWORD={'*' * len(PG_PASSWORD)}")


# === 7. Verify ===
def verify_installation() -> bool:
    print(f"  [7/7] VERIFY")
    psql = os.path.join(PG_INSTALL_DIR, "bin", "psql.exe")
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_PASSWORD
    env["PATH"] = os.path.join(PG_INSTALL_DIR, "bin") + os.pathsep + env.get("PATH", "")

    r = _run_text(
        [psql, "-h", "127.0.0.1", "-p", str(PG_PORT),
         "-U", "postgres", "-d", PG_DB_NAME,
         "-c", "SELECT version(); SELECT PostGIS_Version();"],
        capture_output=True, env=env, timeout=10,
    )
    if r.returncode != 0:
        stderr = r.stderr or ""
        stdout = r.stdout or ""
        print(f"  [ERROR] verify: {stderr[:200] or stdout[:200] or f'rc={r.returncode}'}")
        return False
    print(r.stdout.strip())
    return True


# === 8. Cleanup instalatorów ===
# Po udanej instalacji PG + PostGIS pliki .exe w cache/ są zbędne (457 MB).
# Reinstall automatycznie ściągnie je z download_or_skip(). User nie musi
# ręcznie sprzątać cache/ po każdej instalacji.
INSTALLER_FILES = (
    "postgresql-16.4-1-windows-x64.exe",
    "postgis-bundle-pg16x64-setup-3.6.2-1.exe",
)


def cleanup_installer_cache(cache_dir: Path) -> tuple[int, int]:
    """Usuwa instalatory PG + PostGIS z katalogu cache.

    Returns: (num_removed, bytes_freed)
    """
    removed = 0
    bytes_freed = 0
    for name in INSTALLER_FILES:
        f = Path(cache_dir) / name
        if not f.exists() or not f.is_file():
            continue
        try:
            size = f.stat().st_size
            f.unlink()
            removed += 1
            bytes_freed += size
        except OSError as exc:
            print(f"  [WARN] Nie mogę usunąć {f.name}: {exc}")
    return removed, bytes_freed


# === Main ===
def main() -> int:
    if sys.platform != "win32":
        print("  [ERROR] Ten skrypt działa TYLKO na Windows")
        return 1
    if not is_admin():
        print("  [CHECK] Nie jesteś adminem — proszę o UAC elevation...")
        request_admin_elevation()
        return 0

    project_root = Path(__file__).resolve().parent.parent
    cache_dir = project_root / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pg_installer = cache_dir / "postgresql-16.4-1-windows-x64.exe"
    postgis_installer = cache_dir / "postgis-bundle-pg16x64-setup-3.6.2-1.exe"

    print(f"\n  [SETUP] project_root={project_root}\n")

    # 0. Downloads
    download_or_skip(PG_INSTALLER_URL, pg_installer, "PostgreSQL installer (357 MB)")
    download_or_skip(POSTGIS_INSTALLER_URL, postgis_installer, "PostGIS bundle (100 MB)")

    # 1. PG install
    if os.path.exists(PG_INSTALL_DIR):
        print(f"\n  [INFO] {PG_INSTALL_DIR} już istnieje — pomijam PG install")
        print(f"         (jeśli chcesz reinstalować, odinstaluj przez Panel Sterowania)")
    else:
        rc = run_pg_installer(pg_installer)
        if rc != 0:
            return rc

    # 2. Wait for service
    if not wait_for_pg_service(SERVICE_START_TIMEOUT):
        return 1

    # 3. PostGIS
    if run_postgis_installer(postgis_installer) is False:
        return 1

    # 4. Database
    if not create_database():
        return 1

    # 5. PostGIS + schema
    if not apply_postgis_and_schema():
        return 1

    # 6. Update .env
    update_env_files(project_root)

    # 7. Verify
    if not verify_installation():
        return 1

    # 8. Cleanup instalatorów (457 MB zwolnione po udanej instalacji)
    removed, bytes_freed = cleanup_installer_cache(cache_dir)
    if removed:
        print(f"  [CLEANUP] Usunięto {removed} instalator(y) ({bytes_freed / 1024 / 1024:.1f} MB)")

    print(f"\n  [SUKCES] PG 16.4 + PostGIS 3.6 + schemat gotowe!")
    print(f"  [INFO]  Port: {PG_PORT}, user: postgres, hasło: {'*' * len(PG_PASSWORD)}")
    print(f"  [INFO]  Baza: {PG_DB_NAME}")
    print(f"  [INFO]  Zrestartuj aplikację — powinna się łączyć OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
