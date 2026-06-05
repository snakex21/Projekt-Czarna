"""Test pierwszego uruchomienia launchera (auto-inicjalizacja PG).

Symuluje ścieżkę ``first run``: z pustym serwerem PG launcher powinien
automatycznie utworzyć obie bazy, lokalizację Czarna, zmigrować dane z
backup/Czarna i być gotowy do użycia.

Użycie::

    # Standalone (CLI):
    python backend/scripts/test_first_run.py
    python backend/scripts/test_first_run.py --no-backup
    python backend/scripts/test_first_run.py --verbose

    # Jako moduł (np. w pytest):
    from test_first_run import run_first_run_test
    report = run_first_run_test(verbose=True)
    assert report["success"] is True

Bezpieczeństwo:
    Domyślnie PRZED testem robi :func:`pg_dump` obu baz do ``backups/``.
    PO teście NIE przywraca automatycznie (zostawia świeży system).
    Użyj :func:`restore_from_backup` jeśli chcesz cofnąć zmiany.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable

# === Ścieżki (działają standalone + jako moduł) ===
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
BACKUPS_DIR = PROJECT_DIR / "backups"
PG_BIN = Path(r"C:\Program Files\PostgreSQL\16\bin")

# Dodaj backend do sys.path (dla importów launcher.*)
sys.path.insert(0, str(PROJECT_DIR))

# Domyślne wartości z backend/.env (fallback gdyby nie dało się odczytać)
DEFAULT_PG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "12345",  # fallback
    "super_db": "postgres",  # baza do CREATE/DROP DATABASE
    "launcher_db": "mapa_launcher_db",
    "location_db": "mapa_czarna_db",
}


@dataclass
class StepReport:
    """Raport pojedynczego kroku testu."""
    name: str
    duration_ms: float
    success: bool
    details: str = ""
    error: str = ""


@dataclass
class FirstRunReport:
    """Pełen raport testu first-run."""
    started_at: str
    finished_at: str
    total_duration_ms: float
    success: bool
    steps: list[StepReport] = field(default_factory=list)
    backup_files: list[str] = field(default_factory=list)
    final_db_state: dict[str, Any] = field(default_factory=dict)
    expected_counts: dict[str, int] = field(default_factory=dict)
    actual_counts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "steps": [asdict(s) for s in self.steps],
        }


# === Pomocnicze: parsowanie backend/.env ===

def _load_pg_credentials() -> dict[str, Any]:
    """Wczytuje host/port/user/password z ``backend/.env``."""
    cfg = dict(DEFAULT_PG)
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return cfg
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            mapping = {
                "DB_HOST": "host",
                "DB_PORT": "port",
                "DB_USER": "user",
                "DB_PASSWORD": "password",
                "DB_NAME": "location_db",
            }
            if key in mapping:
                if key == "DB_PORT":
                    try:
                        cfg[mapping[key]] = int(value)
                    except ValueError:
                        cfg[mapping[key]] = value
                else:
                    cfg[mapping[key]] = value
    except Exception as e:  # pragma: no cover
        print(f"⚠️ Nie udało się wczytać {env_file}: {e}")
    return cfg


# === Pomocnicze: pg_dump / DROP / CREATE / psql ===

def _set_pg_password_env() -> None:
    """Ustawia PGPASSWORD dla podprocesów psql/pg_dump."""
    creds = _load_pg_credentials()
    os.environ["PGPASSWORD"] = str(creds["password"])


def _pg_tool_path(name: str) -> Path:
    """Pełna ścieżka do narzędzia PG (psql, pg_dump, dropdb)."""
    return PG_BIN / f"{name}.exe"


def _run_pg(args: list[str], tool: str = "psql", timeout: int = 60) -> tuple[int, str, str]:
    """Uruchamia narzędzie PG i zwraca (returncode, stdout, stderr)."""
    binary = _pg_tool_path(tool)
    if not binary.exists():
        return 127, "", f"Brak narzędzia: {binary}"
    try:
        proc = subprocess.run(
            [str(binary), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"Timeout po {timeout}s"
    except Exception as e:  # pragma: no cover
        return 1, "", f"{type(e).__name__}: {e}"


def _db_exists(db_name: str) -> bool:
    creds = _load_pg_credentials()
    code, out, err = _run_pg([
        "-U", creds["user"], "-h", creds["host"],
        "-d", creds["super_db"],
        "-tAc", f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'",
    ])
    return code == 0 and out.strip() == "1"


def _terminate_connections(db_name: str) -> None:
    """Wymusza zakończenie aktywnych połączeń do bazy (potrzebne przed DROP)."""
    creds = _load_pg_credentials()
    _run_pg([
        "-U", creds["user"], "-h", creds["host"],
        "-d", creds["super_db"],
        "-c", f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
              f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()",
    ])


def _drop_database(db_name: str) -> tuple[bool, str]:
    """DROP DATABASE z obsługą aktywnych połączeń."""
    if not _db_exists(db_name):
        return True, "Baza nie istniała (OK)"
    _terminate_connections(db_name)
    creds = _load_pg_credentials()
    code, out, err = _run_pg([
        "-U", creds["user"], "-h", creds["host"],
        "-d", creds["super_db"],
        "-c", f"DROP DATABASE {db_name}",
    ])
    if code == 0:
        return True, "Usunięto"
    return False, err.strip() or out.strip() or f"exit={code}"


def _backup_database(db_name: str, backups_dir: Path) -> tuple[bool, str]:
    """pg_dump bazy do katalogu backupów. Zwraca (success, path)."""
    if not _db_exists(db_name):
        return True, ""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUPS_DIR / f"{db_name}-{ts}.backup"
    creds = _load_pg_credentials()
    code, out, err = _run_pg([
        "-U", creds["user"], "-h", creds["host"],
        "-d", db_name, "-F", "c", "-f", str(backup_path),
    ], tool="pg_dump", timeout=120)
    if code == 0 and backup_path.exists():
        size_kb = backup_path.stat().st_size // 1024
        return True, f"{backup_path} ({size_kb} KB)"
    return False, err.strip() or f"exit={code}"


def _count_tables(db_name: str) -> dict[str, int]:
    """Zwraca dict {table: count} dla bazy."""
    creds = _load_pg_credentials()
    expected_tables = [
        ("wlasciciele", "wlasciciele"),
        ("obiekty_geograficzne", "obiekty_geograficzne"),
        ("dzialki_wlasciciele", "dzialki_wlasciciele"),
        ("osoby_genealogia", "osoby_genealogia"),
        ("demografia", "demografia"),
    ]
    counts: dict[str, int] = {}
    for display_name, table_name in expected_tables:
        code, out, err = _run_pg([
            "-U", creds["user"], "-h", creds["host"],
            "-d", db_name, "-tAc",
            f"SELECT COUNT(*) FROM {table_name}",
        ])
        if code == 0 and out.strip():
            counts[display_name] = int(out.strip())
        else:
            counts[display_name] = -1  # błąd / tabela nie istnieje
    return counts


# === Właściwy test ===

# Oczekiwane liczby w bazie po migracji z backup/Czarna.
# Musi odpowiadać danym w data/locations/Czarna/.
EXPECTED_COUNTS: dict[str, int] = {
    "wlasciciele": 130,
    "obiekty_geograficzne": 2518,
    "dzialki_wlasciciele": 3903,
    "osoby_genealogia": 1770,
    "demografia": 2,
}


def run_first_run_test(
    *,
    backup: bool = True,
    verbose: bool = False,
    skip_restore: bool = True,
    status_callback: Callable[[str, str], None] | None = None,
) -> FirstRunReport:
    """Wykonuje pełen test first-run i zwraca raport.

    Args:
        backup: czy zrobić pg_dump PRZED usunięciem baz.
        verbose: czy drukować postępy na stdout.
        skip_restore: czy pominąć restore (zawsze True dla testu).
        status_callback: opcjonalny ``callable(step_name, status)`` do
            raportowania w czasie rzeczywistym (np. dla GUI).

    Returns:
        :class:`FirstRunReport` z wynikami każdego kroku.
    """
    started = time.time()
    started_iso = time.strftime("%Y-%m-%d %H:%M:%S")
    report = FirstRunReport(
        started_at=started_iso,
        finished_at="",
        total_duration_ms=0.0,
        success=False,
        expected_counts=dict(EXPECTED_COUNTS),
    )
    _set_pg_password_env()
    creds = _load_pg_credentials()

    def _notify(name: str, status: str) -> None:
        if status_callback:
            try:
                status_callback(name, status)
            except Exception:
                pass

    def _step(name: str, fn: Callable[[], tuple[bool, str]]) -> bool:
        """Wykonuje krok i dopisuje go do raportu."""
        _notify(name, "start")
        if verbose:
            print(f"⏳ {name}...", end=" ", flush=True)
        t0 = time.perf_counter()
        try:
            success, details = fn()
        except Exception as e:
            success, details = False, f"{type(e).__name__}: {e}"
        dur_ms = (time.perf_counter() - t0) * 1000
        step = StepReport(
            name=name,
            duration_ms=round(dur_ms, 1),
            success=success,
            details=details,
        )
        report.steps.append(step)
        _notify(name, "ok" if success else "fail")
        if verbose:
            mark = "✅" if success else "❌"
            extra = f" — {details}" if details else ""
            print(f"{mark} ({dur_ms:.0f}ms){extra}")
        return success

    # === KROK 1: Backup (opcjonalny) ===
    if backup:
        def _do_backup() -> tuple[bool, str]:
            ok_l, msg_l = _backup_database(creds["launcher_db"], BACKUPS_DIR)
            ok_c, msg_c = _backup_database(creds["location_db"], BACKUPS_DIR)
            backups = []
            for msg in (msg_l, msg_c):
                if msg and msg.endswith(".backup") or " KB" in msg:
                    backups.append(msg)
                elif msg:
                    # "Baza nie istniała" - OK, nie ma pliku
                    pass
            report.backup_files = [b for b in backups if Path(b).exists()]
            return ok_l and ok_c, "; ".join(filter(None, [msg_l, msg_c]))
        _step("Backup obu baz (pg_dump)", _do_backup)

    # === KROK 2: DROP baz ===
    def _drop_launcher() -> tuple[bool, str]:
        return _drop_database(creds["launcher_db"])
    _step(f"DROP {creds['launcher_db']}", _drop_launcher)

    def _drop_location() -> tuple[bool, str]:
        return _drop_database(creds["location_db"])
    _step(f"DROP {creds['location_db']}", _drop_location)

    # === KROK 3: Wymuszenie lc_messages=C na czas testu ===
    def _set_lc_messages_c() -> tuple[bool, str]:
        code, out, err = _run_pg([
            "-U", creds["user"], "-h", creds["host"],
            "-d", creds["super_db"],
            "-c", "ALTER ROLE postgres SET lc_messages TO 'C'",
        ])
        return code == 0, "ALTER ROLE lc_messages=C" if code == 0 else err.strip()
    _step("Ustaw lc_messages='C' (obejście polskiego locale)", _set_lc_messages_c)

    # === KROK 4: Auto-inicjalizacja (serce testu) ===
    def _auto_init() -> tuple[bool, str]:
        # Import leniwy - ładujemy dopiero po ustawieniu środowiska
        from launcher.services import startup_initialization_service
        result = startup_initialization_service.auto_initialize_on_startup()
        if not result.success:
            return False, result.error or f"reason={result.reason!r}"
        summary = result.summary
        flags = [k for k, v in summary.items() if v]
        details = ", ".join(flags) if flags else "system already configured"
        return True, details
    _step("auto_initialize_on_startup()", _auto_init)

    # === KROK 5: Weryfikacja stanu końcowego ===
    def _verify_launcher_db() -> tuple[bool, str]:
        if not _db_exists(creds["launcher_db"]):
            return False, "Baza nie istnieje po auto_init"
        return True, "Baza istnieje"
    _step(f"Weryfikacja: {creds['launcher_db']} istnieje", _verify_launcher_db)

    def _verify_location_db() -> tuple[bool, str]:
        if not _db_exists(creds["location_db"]):
            return False, "Baza nie istnieje po auto_init"
        return True, "Baza istnieje"
    _step(f"Weryfikacja: {creds['location_db']} istnieje", _verify_location_db)

    # === KROK 6: Weryfikacja liczby rekordów ===
    def _verify_counts() -> tuple[bool, str]:
        counts = _count_tables(creds["location_db"])
        report.actual_counts = counts
        mismatches = []
        for table, expected in EXPECTED_COUNTS.items():
            actual = counts.get(table, -1)
            if actual != expected:
                mismatches.append(f"{table}: got {actual}, expected {expected}")
        if mismatches:
            return False, "; ".join(mismatches)
        return True, f"counts match: {counts}"
    _step("Weryfikacja liczby rekordów", _verify_counts)

    # === KROK 7: Weryfikacja lokalizacji Czarna w launcher DB ===
    def _verify_location() -> tuple[bool, str]:
        code, out, err = _run_pg([
            "-U", creds["user"], "-h", creds["host"],
            "-d", creds["launcher_db"], "-tAc",
            "SELECT name, active FROM locations WHERE name = 'Czarna'",
        ])
        if code != 0:
            return False, err.strip()
        if "Czarna" not in out:
            return False, f"Brak 'Czarna' w locations. out={out!r}"
        return True, out.strip().replace("|", " active=")
    _step("Weryfikacja lokalizacji 'Czarna' w launcher DB", _verify_location)

    # === KROK 8: Przywrócenie lc_messages ===
    def _restore_lc_messages() -> tuple[bool, str]:
        code, out, err = _run_pg([
            "-U", creds["user"], "-h", creds["host"],
            "-d", creds["super_db"],
            "-c", "ALTER ROLE postgres SET lc_messages TO 'Polish_Poland.1250'",
        ])
        return code == 0, "przywrócono lc_messages=Polish_Poland.1250" if code == 0 else err.strip()
    _step("Przywróć lc_messages='Polish_Poland.1250'", _restore_lc_messages)

    # === Finalizacja ===
    finished = time.time()
    report.finished_at = time.strftime("%Y-%m-%d %H:%M:%S")
    report.total_duration_ms = round((finished - started) * 1000, 1)
    report.success = all(s.success for s in report.steps)
    report.notes.append(
        "auto_initialize_on_startup wykonał się w pełni — "
        "bazy utworzone, dane zmigrowane z backup/Czarna."
    )
    return report


def restore_from_backup(backup_path: str | None = None) -> bool:
    """Przywraca bazy z pliku backup (opcjonalnie interaktywnie).

    Jeśli ``backup_path`` to None, pokaże listę dostępnych backupów.
    """
    if not BACKUPS_DIR.exists():
        print(f"❌ Brak katalogu {BACKUPS_DIR}")
        return False

    backups = sorted(BACKUPS_DIR.glob("*.backup"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        print(f"❌ Brak plików .backup w {BACKUPS_DIR}")
        return False

    creds = _load_pg_credentials()

    if backup_path is None:
        print(f"📦 Dostępne backupy w {BACKUPS_DIR}:")
        for i, b in enumerate(backups[:10], 1):
            size_kb = b.stat().st_size // 1024
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(b.stat().st_mtime))
            print(f"  [{i:2}] {b.name} ({size_kb} KB, {mtime})")
        print()
        try:
            choice = input(f"Który przywrócić? [1-{min(10, len(backups))}]: ").strip()
        except EOFError:
            return False
        if not choice.isdigit():
            return False
        idx = int(choice) - 1
        if not (0 <= idx < len(backups)):
            return False
        backup_path = str(backups[idx])

    bp = Path(backup_path)
    if not bp.exists():
        print(f"❌ Nie ma takiego pliku: {bp}")
        return False

    # Określ bazę po nazwie pliku
    db_name = creds["launcher_db"] if "launcher" in bp.name else creds["location_db"]
    if "czarna" in bp.name:
        db_name = creds["location_db"]
    elif "launcher" in bp.name:
        db_name = creds["launcher_db"]
    else:
        print(f"❌ Nie rozpoznaję bazy z nazwy {bp.name}")
        return False

    print(f"⏳ Przywracam {db_name} z {bp.name}...")
    _drop_database(db_name)
    _run_pg([
        "-U", creds["user"], "-h", creds["host"],
        "-d", creds["super_db"],
        "-c", f"CREATE DATABASE {db_name}",
    ])
    code, out, err = _run_pg([
        "-U", creds["user"], "-h", creds["host"],
        "-d", db_name, str(bp),
    ], tool="pg_restore", timeout=120)
    if code == 0:
        print(f"✅ Przywrócono {db_name}")
        return True
    print(f"❌ Błąd pg_restore: {err.strip()}")
    return False


def _format_report(report: FirstRunReport) -> str:
    """Czytelny raport tekstowy (do druku)."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"🧪 TEST PIERWSZEGO URUCHOMIENIA — {report.started_at}")
    lines.append("=" * 70)
    for i, step in enumerate(report.steps, 1):
        mark = "✅" if step.success else "❌"
        lines.append(f"  [{i:2}] {mark} {step.name:<55} {step.duration_ms:>7.0f} ms")
        if step.details and (not step.success or len(step.details) < 80):
            lines.append(f"        {step.details}")
    lines.append("-" * 70)
    lines.append(f"Łączny czas: {report.total_duration_ms:.0f} ms "
                 f"({report.total_duration_ms / 1000:.1f}s)")
    if report.backup_files:
        lines.append(f"Backupy: {len(report.backup_files)} plik(ów)")
        for b in report.backup_files:
            lines.append(f"  • {b}")
    if report.actual_counts:
        lines.append("Liczby w bazie:")
        for table, count in report.actual_counts.items():
            expected = report.expected_counts.get(table)
            mark = "✓" if count == expected else "✗"
            exp_str = f" (expected {expected})" if count != expected else ""
            lines.append(f"  {mark} {table:<25} = {count}{exp_str}")
    lines.append("=" * 70)
    lines.append("🎉 SUCCESS" if report.success else "💥 FAILURE")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Test pierwszego uruchomienia launchera (auto-init PG)",
    )
    parser.add_argument("--no-backup", action="store_true",
                        help="Pomiń pg_dump PRZED usunięciem baz (ryzykowne)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Drukuj postęp krok po kroku")
    parser.add_argument("--json", action="store_true",
                        help="Raport w formacie JSON (do parsowania)")
    parser.add_argument("--restore", metavar="PATH", default=None,
                        help="Zamiast testu: przywróć z podanego backupu")
    args = parser.parse_args(argv)

    if args.restore is not None:
        ok = restore_from_backup(args.restore)
        return 0 if ok else 1

    report = run_first_run_test(
        backup=not args.no_backup,
        verbose=args.verbose,
    )
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_format_report(report))
    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())
