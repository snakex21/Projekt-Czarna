"""Graficzny instalator PostgreSQL 16 + PostGIS dla launchera.

Uruchamiany z launchera bez okna konsoli. Jeśli proces nie ma uprawnień
administratora, prosi Windows o UAC i startuje ponownie jako ``pythonw.exe``.
Szczegóły techniczne trafiają do ``cache/pg_install_gui.log``.
"""
from __future__ import annotations

import contextlib
import ctypes
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import install_pg_unattended as core


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "cache" / "pg_install_gui.log"
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 760
WINDOW_MIN_WIDTH = 820
WINDOW_MIN_HEIGHT = 700


STEPS = [
    "Pliki instalacyjne",
    "Instalacja PostgreSQL 16",
    "Uruchomienie usługi PostgreSQL",
    "Instalacja PostGIS",
    "Tworzenie bazy aplikacji",
    "Schemat i rozszerzenie PostGIS",
    "Zapis konfiguracji i weryfikacja",
]


def _pythonw_path() -> str:
    """Zwróć ścieżkę do pythonw.exe, jeśli jest dostępny."""
    executable = Path(sys.executable)
    if executable.name.lower() != "pythonw.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return str(executable)


def _ensure_admin_or_relaunch() -> None:
    """Poproś o UAC i zamknij bieżący proces, jeśli brakuje admina."""
    if core.is_admin():
        return
    if sys.platform != "win32":
        messagebox.showerror("PostgreSQL", "Ten instalator działa tylko na Windows.")
        sys.exit(1)

    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        _pythonw_path(),
        f'"{Path(__file__).resolve()}"',
        None,
        1,
    )
    if int(rc) <= 32:
        messagebox.showerror(
            "Nie uruchomiono instalatora",
            "Anulowano lub odrzucono uprawnienia administratora (UAC).",
        )
        sys.exit(1)
    sys.exit(0)


class _QueueWriter:
    """Przekierowuje print() z instalatora do GUI i pliku logu."""

    def __init__(self, events: queue.Queue[tuple[str, object]], log_file):
        self.events = events
        self.log_file = log_file

    def write(self, text: str) -> int:
        if not text:
            return 0
        self.log_file.write(text)
        self.log_file.flush()
        for line in text.splitlines():
            if line.strip():
                self.events.put(("log", line.rstrip()))
        return len(text)

    def flush(self) -> None:
        self.log_file.flush()


class PostgresInstallWindow:
    """Okno postępu instalacji PostgreSQL + PostGIS."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Instalacja PostgreSQL + PostGIS")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.configure(bg="#f8f9fa")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._center_window()

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.finished = False
        self.step_labels: list[tk.Label] = []

        self._build_ui()

    def _center_window(self) -> None:
        """Wyśrodkuj okno na aktywnym monitorze (z obsługą multi-monitor)."""
        self.root.update_idletasks()
        # winfo_screenwidth/height zwraca rozmiary CAŁEJ wirtualnej przestrzeni
        # ekranów. Na Windows z wieloma monitorami okno może wylądować poza
        # widocznym obszarem jeśli użyjemy (sw - w) // 2 na ślepo.
        # Bezpieczniej: wycentruj na oknie-rodzicu, jeśli jest, albo na 0,0.
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        window_w = self.root.winfo_width() or WINDOW_WIDTH
        window_h = self.root.winfo_height() or WINDOW_HEIGHT
        x = max((screen_w - window_w) // 2, 0)
        y = max((screen_h - window_h) // 2, 0)
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        main = tk.Frame(self.root, bg="#f8f9fa", padx=28, pady=24)
        main.pack(fill="both", expand=True)

        tk.Label(
            main,
            text="Instalacja PostgreSQL + PostGIS",
            font=("Segoe UI", 20, "bold"),
            bg="#f8f9fa",
            fg="#212529",
        ).pack(anchor="w")

        tk.Label(
            main,
            text=(
                "Instalator przygotuje serwer PostgreSQL 16, PostGIS oraz bazę "
                "aplikacji. Może to potrwać kilka minut."
            ),
            font=("Segoe UI", 10),
            bg="#f8f9fa",
            fg="#495057",
            wraplength=690,
            justify="left",
        ).pack(anchor="w", pady=(8, 18))

        self.status_label = tk.Label(
            main,
            text="Przygotowanie instalatora...",
            font=("Segoe UI", 12, "bold"),
            bg="#f8f9fa",
            fg="#0d6efd",
        )
        self.status_label.pack(anchor="w", pady=(0, 8))

        self.progress = ttk.Progressbar(main, mode="determinate", maximum=len(STEPS), value=0)
        self.progress.pack(fill="x", pady=(0, 18))

        steps_frame = tk.Frame(main, bg="white", bd=1, relief="solid", padx=18, pady=14)
        steps_frame.pack(fill="x")
        for index, step in enumerate(STEPS, start=1):
            label = tk.Label(
                steps_frame,
                text=f"○  {index}. {step}",
                font=("Segoe UI", 10),
                bg="white",
                fg="#6c757d",
                anchor="w",
            )
            label.pack(fill="x", pady=2)
            self.step_labels.append(label)

        buttons = tk.Frame(main, bg="#f8f9fa")
        buttons.pack(fill="x", pady=(16, 10))
        self.open_log_button = tk.Button(
            buttons,
            text="Otwórz log",
            font=("Segoe UI", 10),
            bg="#0d6efd",
            fg="white",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=8,
            command=self._open_log,
        )
        self.open_log_button.pack(side="left")
        self.close_button = tk.Button(
            buttons,
            text="Zamknij po zakończeniu",
            font=("Segoe UI", 10),
            bg="#6c757d",
            fg="white",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=8,
            state="disabled",
            command=self.root.destroy,
        )
        self.close_button.pack(side="right")

        details_frame = tk.LabelFrame(
            main,
            text="Szczegóły techniczne",
            font=("Segoe UI", 9, "bold"),
            bg="#f8f9fa",
            fg="#495057",
            padx=10,
            pady=8,
        )
        details_frame.pack(fill="both", expand=True, pady=(0, 0))

        self.log_text = tk.Text(
            details_frame,
            height=6,
            font=("Consolas", 9),
            bg="#111827",
            fg="#d1d5db",
            insertbackground="#d1d5db",
            relief="flat",
            wrap="word",
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.insert("end", f"Log: {LOG_PATH}\n")
        self.log_text.configure(state="disabled")

    def start(self) -> None:
        worker = threading.Thread(target=self._worker, daemon=True)
        worker.start()
        self.root.after(100, self._drain_events)
        self.root.mainloop()

    def _set_step(self, index: int, state: str) -> None:
        icons = {"running": "⏳", "done": "✅", "error": "❌", "pending": "○"}
        colors = {"running": "#0d6efd", "done": "#198754", "error": "#dc3545", "pending": "#6c757d"}
        label = self.step_labels[index - 1]
        label.configure(text=f"{icons[state]}  {index}. {STEPS[index - 1]}", fg=colors[state])

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _open_log(self) -> None:
        """Otwórz plik logu instalatora w domyślnej aplikacji."""
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not LOG_PATH.exists():
            LOG_PATH.write_text("Log instalatora nie został jeszcze utworzony.\n", encoding="utf-8")
        try:
            os.startfile(str(LOG_PATH))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Nie można otworzyć logu", str(exc), parent=self.root)

    def _drain_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if event == "log":
                self._append_log(str(payload))
            elif event == "status":
                self.status_label.configure(text=str(payload), fg="#0d6efd")
            elif event == "step":
                index, state = payload  # type: ignore[misc]
                self._set_step(int(index), str(state))
                if state == "done":
                    self.progress.configure(value=max(float(self.progress["value"]), int(index)))
            elif event == "success":
                self.finished = True
                self.status_label.configure(text="Gotowe — PostgreSQL + PostGIS skonfigurowane", fg="#198754")
                self.close_button.configure(state="normal", text="Zamknij")
                messagebox.showinfo(
                    "Instalacja zakończona",
                    "PostgreSQL + PostGIS są gotowe. Uruchom launcher ponownie.",
                    parent=self.root,
                )
                self.root.destroy()
            elif event == "error":
                self.finished = True
                self.status_label.configure(text="Instalacja przerwana — sprawdź szczegóły", fg="#dc3545")
                self.close_button.configure(state="normal", text="Zamknij")
                messagebox.showerror(
                    "Błąd instalacji",
                    f"Instalacja nie zakończyła się poprawnie.\n\nSzczegóły: {LOG_PATH}",
                    parent=self.root,
                )

        if not self.finished:
            self.root.after(100, self._drain_events)

    def _run_step(self, index: int, label: str, func) -> bool:
        self.events.put(("status", label))
        self.events.put(("step", (index, "running")))
        ok = func()
        if ok:
            self.events.put(("step", (index, "done")))
            return True
        self.events.put(("step", (index, "error")))
        return False

    def _worker(self) -> None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(LOG_PATH, "w", encoding="utf-8") as log_file:
                writer = _QueueWriter(self.events, log_file)
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    success = self._install_all()
            self.events.put(("success" if success else "error", None))
        except Exception as exc:
            self.events.put(("log", f"[ERROR] {exc}"))
            self.events.put(("error", None))

    def _install_all(self) -> bool:
        cache_dir = PROJECT_ROOT / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        pg_installer = cache_dir / "postgresql-16.4-1-windows-x64.exe"
        postgis_installer = cache_dir / "postgis-bundle-pg16x64-setup-3.6.2-1.exe"

        print(f"[SETUP] project_root={PROJECT_ROOT}")
        print(f"[LOG] {LOG_PATH}")

        if not self._run_step(
            1,
            "Sprawdzam pliki instalacyjne...",
            lambda: (
                core.download_or_skip(core.PG_INSTALLER_URL, pg_installer, "PostgreSQL installer"),
                core.download_or_skip(core.POSTGIS_INSTALLER_URL, postgis_installer, "PostGIS bundle"),
                True,
            )[-1],
        ):
            return False

        if core.is_pg_install_healthy():
            print(f"[INFO] {core.PG_INSTALL_DIR} działa — pomijam instalację PostgreSQL")
            self.events.put(("step", (2, "done")))
        else:
            if not core.prepare_stale_pg_install_dir():
                self.events.put(("step", (2, "error")))
                return False
            if not self._run_step(
                2,
                "Instaluję PostgreSQL 16...",
                lambda: core.run_pg_installer(pg_installer) == 0,
            ):
                return False

        if not self._run_step(
            3,
            "Czekam na uruchomienie usługi PostgreSQL...",
            lambda: core.wait_for_pg_service(core.SERVICE_START_TIMEOUT),
        ):
            return False

        if not self._run_step(
            4,
            "Instaluję PostGIS...",
            lambda: core.run_postgis_installer(postgis_installer),
        ):
            return False

        if not self._run_step(5, "Tworzę bazę aplikacji...", core.create_database):
            return False

        if not self._run_step(6, "Włączam PostGIS i tworzę schemat...", core.apply_postgis_and_schema):
            return False

        if not self._run_step(
            7,
            "Zapisuję konfigurację i weryfikuję instalację...",
            lambda: (core.update_env_files(PROJECT_ROOT), core.verify_installation())[-1],
        ):
            return False

        # Cleanup instalatorów z cache/ (457 MB zwolnione po udanej instalacji)
        cache_dir = PROJECT_ROOT / "cache"
        removed, bytes_freed = core.cleanup_installer_cache(cache_dir)
        if removed:
            print(f"  [CLEANUP] Usunięto {removed} instalator(y) ({bytes_freed / 1024 / 1024:.1f} MB)")

        print("[SUKCES] PG 16 + PostGIS + schemat gotowe")
        return True

    def _on_close(self) -> None:
        if self.finished:
            self.root.destroy()
            return
        messagebox.showwarning(
            "Instalacja trwa",
            "Nie zamykaj okna w trakcie instalacji. Poczekaj na zakończenie procesu.",
            parent=self.root,
        )


def main() -> int:
    _ensure_admin_or_relaunch()
    PostgresInstallWindow().start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
