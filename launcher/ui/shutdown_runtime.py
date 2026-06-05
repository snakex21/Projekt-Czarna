"""Shutdown runtime - orkiestracja zamykania aplikacji.

Ten moduł dostarcza czyste funkcje obsługujące zamykanie głównego okna
launchera. Publiczne API ``AppLauncher.on_closing``, ``_force_exit``,
``_on_root_destroy``, ``_close_console_window`` i ``cleanup_temp_files``
zostaje zachowane - metody klasy są jednolinijkowymi delegacjami.

Sekwencja zamykania:

  1. request_graceful_close (z potwierdzeniem jeśli są procesy)
  2. force_close_application
       - mark_exiting
       - cleanup_temp_files
       - app.quit / app.destroy
       - close_console_window
       - os._exit(0)
"""

from __future__ import annotations

import os
import platform
from tkinter import messagebox


# ─── Czyste funkcje pomocnicze ───────────────────────────────────────────────

def mark_exiting(app) -> None:
    """Ustawia flage ``app._exiting = True`` (idempotentnie)."""
    app._exiting = True


def is_exiting(app) -> bool:
    """Czy aplikacja jest w trakcie zamykania."""
    return bool(getattr(app, "_exiting", False))


def stop_all_managed_processes(app) -> None:
    """Wymusza zatrzymanie wszystkich zarządzanych procesów."""
    try:
        for key in list(getattr(app.process_mgr, "managed_processes", {}).keys()):
            app.stop_managed_process(key, force=True)
    except Exception:
        pass


def cleanup_temp_files(backend_dir) -> None:
    """Usuwa tymczasowe pliki utworzone przez launcher.

    W szczególności ``backend/_network_server_wrapper.py`` generowany
    przez ``network_runtime``. Nie rzuca wyjątków - housekeeping nie
    powinien blokować zamykania.
    """
    wrapper_path = os.path.join(backend_dir, "_network_server_wrapper.py")
    if os.path.exists(wrapper_path):
        try:
            os.remove(wrapper_path)
        except Exception:
            pass


def close_console_window() -> None:
    """Zamyka dedykowane okno konsoli py.exe na Windows.

    Samo ``os._exit(0)`` powinno kończyć proces, ale przy uruchamianiu
    przez Windows Python Launcher (py.exe) okno konsoli potrafi zostać
    chwilę widoczne. ``WM_CLOSE`` do okna konsoli zamyka je natychmiast.
    """
    if platform.system() != "Windows":
        return
    try:
        import ctypes as _ctypes

        hwnd = _ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            WM_CLOSE = 0x0010
            _ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    except Exception:
        pass


# ─── Wejscia zamykania (entry points) ────────────────────────────────────────

def request_graceful_close(app) -> None:
    """Obsługa ``WM_DELETE_WINDOW`` - pytanie o potwierdzenie + force exit.

    Jeśli są uruchomione procesy, pytamy użytkownika czy na pewno chce
    zatrzymać i zamknąć. Jeśli nie ma procesów lub user potwierdzi,
    przechodzi do ``force_close_application`` (bez pytania).
    """
    if app.process_mgr.managed_processes:
        network_server = any(
            p.get("network_mode")
            for p in app.process_mgr.managed_processes.values()
        )

        warning_msg = f"Uruchomionych jest {len(app.process_mgr.managed_processes)} procesów."
        if network_server:
            warning_msg += "\n\n⚠️ UWAGA: Serwer sieciowy jest aktywny!"
        warning_msg += "\n\nCzy chcesz je wszystkie zatrzymać i zamknąć aplikację?"

        result = messagebox.askyesno(
            "🔒 Potwierdzenie zamknięcia",
            warning_msg,
            icon="warning" if network_server else "question",
        )

        if not result:
            return

        app.log("\n" + "=" * 60 + "\n")
        app.log("🔒 Zamykanie aplikacji - zatrzymywanie procesów...\n")

        stop_all_managed_processes(app)

    force_close_application(app)


def force_close_application(app) -> None:
    """Natychmiast kończy proces launchera i zamyka konsolę.

    Tkinter + daemonowe wątki odczytu stdout potrafią opóźniać normalne
    zamknięcie po ``self.destroy()``. Ten helper najpierw czyści zasoby,
    potem zamyka GUI i wymusza zakończenie procesu Pythona.
    """
    mark_exiting(app)
    # Ścieżka backend_dir brana z module-level - stałej launcher_app.py
    # albo z atrybutu instancji (gdyby przyszłościowo został dodany).
    backend_dir = getattr(app, "backend_dir", None)
    if not backend_dir:
        try:
            from launcher.config.paths import BACKEND_DIR
            backend_dir = str(BACKEND_DIR)
        except Exception:
            backend_dir = ""
    cleanup_temp_files(backend_dir)
    try:
        app.quit()
    except Exception:
        pass
    try:
        app.destroy()
    except Exception:
        pass
    close_console_window()
    os._exit(0)


def handle_destroy_event(app, event=None) -> None:
    """Awaryjne zakończenie procesu, gdy znika główne okno Tk.

    To łapie przypadki, gdzie ktoś wywołał ``self.destroy()`` bez
    ``on_closing()``. Nie reaguje na niszczenie okien dialogowych
    / widgetów potomnych. Idempotentne (sprawdza ``_exiting``).
    """
    try:
        if event is not None and event.widget is not app:
            return
    except Exception:
        return

    if is_exiting(app):
        return

    mark_exiting(app)
    stop_all_managed_processes(app)
    try:
        from launcher.config.paths import BACKEND_DIR
        cleanup_temp_files(str(BACKEND_DIR))
    except Exception:
        pass
    close_console_window()
    os._exit(0)


def shutdown_after_mainloop(app) -> None:
    """Fallback po powrocie z ``app.mainloop()`` bez ``on_closing``.

    Domyślnie ``mainloop`` kończy się przez ``WM_DELETE_WINDOW``, ale
    jeśli ktoś wywoła ``app.quit()`` bez ``destroy()`` (np. z testu),
    ta ścieżka powinna defensywnie sprzątnąć procesy i wrapper.
    """
    if is_exiting(app):
        close_console_window()
        return
    stop_all_managed_processes(app)
    try:
        from launcher.config.paths import BACKEND_DIR
        cleanup_temp_files(str(BACKEND_DIR))
    except Exception:
        pass
    close_console_window()


__all__ = [
    "cleanup_temp_files",
    "close_console_window",
    "force_close_application",
    "handle_destroy_event",
    "is_exiting",
    "mark_exiting",
    "request_graceful_close",
    "shutdown_after_mainloop",
    "stop_all_managed_processes",
]
