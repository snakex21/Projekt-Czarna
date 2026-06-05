"""Graficzna deinstalacja PostgreSQL 16 używanego przez launcher.

Skrypt uruchamiany z panelu ustawień. Wymaga UAC, zatrzymuje usługę
``postgresql-x64-16``, uruchamia uninstaller EDB w trybie unattended,
**czyści katalog ``C:\\Program Files\\PostgreSQL\\16``** (jeśli EDB
zostawił resztki) i **wszystkie ``*_old_*`` katalogi** z poprzednich
deinstalacji. Na końcu przełącza launcher z powrotem na SQLite.
"""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
LOG_PATH = PROJECT_ROOT / "cache" / "pg_uninstall.log"
PG_INSTALL_DIR = Path(r"C:\Program Files\PostgreSQL\16")
PG_SERVICE_NAME = "postgresql-x64-16"
WINDOW_WIDTH = 520
WINDOW_HEIGHT = 220


def _no_window_flags() -> int:
    """Flagi subprocess ukrywające migające okna konsoli na Windows."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def _pythonw_path() -> str:
    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    return str(pythonw if pythonw.exists() else executable)


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _ensure_admin_or_relaunch() -> None:
    if _is_admin():
        return
    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        _pythonw_path(),
        f'"{Path(__file__).resolve()}"',
        None,
        1,
    )
    if int(rc) <= 32:
        messagebox.showerror("Deinstalacja PostgreSQL", "Odrzucono uprawnienia administratora (UAC).")
        sys.exit(1)
    sys.exit(0)


def _run(cmd: list[str], log) -> subprocess.CompletedProcess[str]:
    log.write(f"$ {' '.join(cmd)}\n")
    log.flush()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        creationflags=_no_window_flags(),
    )
    if result.stdout:
        log.write(result.stdout + "\n")
    if result.stderr:
        log.write(result.stderr + "\n")
    log.write(f"rc={result.returncode}\n\n")
    log.flush()
    return result


def _set_env_key(content: str, key: str, value: str) -> str:
    lines = content.splitlines()
    replaced = False
    output: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            output.append(f"{key}={value}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(f"{key}={value}")
    return "\n".join(output) + "\n"


def _reset_launcher_to_sqlite(log) -> None:
    env_path = BACKEND_DIR / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        content = _set_env_key(content, "DB_ENGINE", "sqlite")
        env_path.write_text(content, encoding="utf-8")
        log.write("backend/.env: DB_ENGINE=sqlite\n")
    pg_env = BACKEND_DIR / ".postgres.env"
    if pg_env.exists():
        pg_env.unlink()
        log.write("backend/.postgres.env: usunięty\n")
    os.environ["DB_ENGINE"] = "sqlite"


def _find_uninstaller() -> Path | None:
    candidates = [
        PG_INSTALL_DIR / "uninstall-postgresql.exe",
        PG_INSTALL_DIR / "uninstall-postgresql.dat",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.suffix.lower() == ".exe":
            return candidate
    for pattern in ("uninstall-postgresql*.exe", "uninstall*.exe"):
        matches = list(PG_INSTALL_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None


def _dir_size(path: Path) -> int:
    """Rekurencyjnie sumuje rozmiar plików w katalogu (w bajtach)."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _human_size(num_bytes: int) -> str:
    """Formatuje bajty jako czytelny string (B/KB/MB/GB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def _cleanup_pg_dirs(log) -> tuple[int, int]:
    """Usuń katalog PG + wszystkie ``*_old_*`` zostawione przez poprzednie deinstalacje.

    User kliknął "Odinstaluj" — explicit consent na usunięcie. EDB uninstaller
    potrafi zostawić pusty katalog ``16`` albo pojedyńcze pliki, a nasz własny
    flow z poprzednich wersji zostawiał ``16_old_<timestamp>`` jako backup.
    Wszystko to jest śmietnikiem po deinstalacji — usuwamy.

    Returns:
        (num_removed, bytes_freed) — ile katalogów poszło i ile bajtów zwolniono.
    """
    parent = PG_INSTALL_DIR.parent
    removed = 0
    bytes_freed = 0

    # 1. Najpierw _old_* (posortowane chronologicznie — najstarsze pierwsze)
    for old_dir in sorted(parent.glob("16_old_*")):
        if not old_dir.is_dir():
            continue
        size = _dir_size(old_dir)
        try:
            shutil.rmtree(str(old_dir))
            removed += 1
            bytes_freed += size
            log.write(f"[CLEANUP] Usunięto: {old_dir} ({_human_size(size)})\n")
        except OSError as exc:
            log.write(f"[ERROR] Nie mogę usunąć {old_dir}: {exc}\n")

    # 2. Potem katalog bieżącej instalacji (jeśli EDB coś zostawił)
    if PG_INSTALL_DIR.exists():
        size = _dir_size(PG_INSTALL_DIR)
        try:
            shutil.rmtree(str(PG_INSTALL_DIR))
            removed += 1
            bytes_freed += size
            log.write(f"[CLEANUP] Usunięto: {PG_INSTALL_DIR} ({_human_size(size)})\n")
        except OSError as exc:
            log.write(f"[ERROR] Nie mogę usunąć {PG_INSTALL_DIR}: {exc}\n")

    log.flush()
    return removed, bytes_freed


def _center_window(window: tk.Tk, width: int = WINDOW_WIDTH, height: int = WINDOW_HEIGHT) -> None:
    """Wyśrodkuj okno deinstalatora na głównym ekranie."""
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = max((screen_w - width) // 2, 0)
    y = max((screen_h - height) // 2, 0)
    window.geometry(f"{width}x{height}+{x}+{y}")


def uninstall() -> tuple[bool, str]:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as log:
        log.write(f"[UNINSTALL] project_root={PROJECT_ROOT}\n")

        _run(["sc", "stop", PG_SERVICE_NAME], log)
        uninstaller = _find_uninstaller()
        if uninstaller is None:
            log.write(f"[INFO] Brak uninstallera w {PG_INSTALL_DIR}; resetuję tylko launcher.\n")
            _reset_launcher_to_sqlite(log)
            # Cleanup _old_* nawet gdy nie było uninstallera (śmieci z poprzednich prób)
            removed, bytes_freed = _cleanup_pg_dirs(log)
            extra = f" Usunięto {removed} katalog(ów) ({_human_size(bytes_freed)})." if removed else ""
            return True, (
                "Nie znaleziono uninstallera PostgreSQL 16. "
                f"Launcher przełączony na SQLite.{extra} Uruchom program ponownie."
            )

        result = _run([str(uninstaller), "--mode", "unattended"], log)
        _reset_launcher_to_sqlite(log)
        if result.returncode != 0:
            return False, f"Uninstaller zakończył się kodem {result.returncode}. Log: {LOG_PATH}"

        # Sukces: posprzątaj katalogi zostawione przez EDB + stare _old_*
        removed, bytes_freed = _cleanup_pg_dirs(log)
        extra = f" Usunięto {removed} katalog(ów) ({_human_size(bytes_freed)})." if removed else ""
        return True, (
            f"PostgreSQL odinstalowany.{extra} "
            "Launcher przełączony na SQLite. Uruchom program ponownie."
        )


def main() -> int:
    _ensure_admin_or_relaunch()
    root = tk.Tk()
    root.title("Odinstaluj PostgreSQL")
    _center_window(root)
    root.resizable(False, False)
    tk.Label(root, text="Odinstalowywanie PostgreSQL 16...", font=("Segoe UI", 13, "bold")).pack(pady=(28, 8))
    tk.Label(root, text="To może potrwać kilka minut. Nie zamykaj okna.", font=("Segoe UI", 10)).pack()
    bar = ttk.Progressbar(root, mode="indeterminate")
    bar.pack(fill="x", padx=40, pady=24)
    bar.start(10)

    def finish(ok: bool, msg: str):
        bar.stop()
        if ok:
            messagebox.showinfo("Gotowe", msg, parent=root)
        else:
            messagebox.showerror("Błąd deinstalacji", msg, parent=root)
        root.destroy()

    def work():
        ok, msg = uninstall()
        root.after(0, lambda: finish(ok, msg))

    root.after(200, lambda: threading.Thread(target=work, daemon=True).start())
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
