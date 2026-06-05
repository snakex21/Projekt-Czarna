"""Runtime for .env watcher, quick links and EnvEditor orchestration."""

from __future__ import annotations

import os
import webbrowser
from tkinter import messagebox
from typing import Callable

from launcher.services import env_watcher_service, launcher_url_service


def get_urls(sqlite_mode: bool, backend_dir: str, get_location_env_path: Callable[[], str], read_backend_env_value) -> dict:
    """Build launcher quick-link URLs from the active environment configuration."""
    return launcher_url_service.get_launcher_urls(sqlite_mode, backend_dir, get_location_env_path, read_backend_env_value)


def load_flask_config(sqlite_mode: bool, backend_dir: str, get_location_env_path: Callable[[], str]) -> dict:
    """Read the active backend host/port configuration."""
    return launcher_url_service.load_flask_config(sqlite_mode, backend_dir, get_location_env_path)


def refresh_quick_links(app, get_urls_func: Callable[[], dict]) -> None:
    """Update quick-link button commands from the current .env URLs."""
    app.current_flask_config = app.load_flask_config()
    urls = get_urls_func()
    for btn, url_key in getattr(app, "quick_link_buttons", []):
        url = urls[url_key]
        btn.configure(command=lambda u=url: webbrowser.open_new_tab(u))


def get_env_mtime(sqlite_mode: bool, backend_dir: str, get_location_env_path: Callable[[], str]):
    """Return mtime for the .env file watched by quick links."""
    return env_watcher_service.get_env_mtime(sqlite_mode, backend_dir, get_location_env_path)


def start_env_watcher(app, interval_ms: int = 5000) -> None:
    """Start periodic .env watcher using Tk ``after`` callbacks."""
    def _tick():
        try:
            mtime = app.get_env_mtime()
            app._env_mtime, changed = env_watcher_service.should_handle_env_change(app._env_mtime, mtime)
            if changed:
                app.on_env_changed()
        finally:
            app.after(interval_ms, _tick)  # 5s zamiast 2s - zmniejsza obciążenie CPU

    _tick()


def on_env_changed(app) -> None:
    """Handle .env updates and preserve current backend restart behavior."""
    old_port = getattr(app, "_last_port", None)
    was_running = "backend" in app.process_mgr.managed_processes
    was_network = app.process_mgr.managed_processes.get("backend", {}).get("network_mode", False)

    app.refresh_quick_links()
    new_port = app.current_flask_config.get("port")
    app._last_port = new_port

    app.log(f"🔎 Wykryto zmianę .env – port {old_port} ➜ {new_port}\n")

    if not env_watcher_service.env_port_changed(old_port, new_port, was_running):
        return

    if messagebox.askyesno(
        "Wykryto zmianę portu",
        f"Zmieniono port z {old_port} na {new_port}.\n\n"
        "Zrestartować serwer backend?",
    ):
        app.stop_managed_process("backend")

        try:
            app.setup_firewall_rule_for_port(int(new_port))
        except Exception:
            pass

        def _restart():
            if was_network:
                app.start_network_server()
            else:
                app.start_managed_process("backend", "Serwer Backend (Lokalny)")
                app.server_btn.config(text="⏹️ Zatrzymaj Serwer (Lokalny)", style="Danger.TButton")

        app.after(600, _restart)


def open_env_editor(
    app,
    *,
    sqlite_mode: bool,
    backend_dir: str,
    get_location_env_path: Callable[[], str],
    check_env_configuration: Callable[[], bool],
    env_editor_cls,
) -> None:
    """Open EnvEditor for backend .env or active-location .env."""
    # W trybie SQLite backend czyta konfigurację z backend/.env
    # (tam jest FLASK_PORT=5000). Plik data/locations/<miejscowość>/.env
    # może mieć legacy FLASK_PORT=5000 i nie wpływa na uruchomiony serwer.
    if sqlite_mode:
        env_path = os.path.join(backend_dir, ".env")
    else:
        try:
            env_path = get_location_env_path()
        except ValueError:
            messagebox.showerror("❌ Błąd", "Brak aktywnej miejscowości")
            return

        if not os.path.exists(env_path):
            if not check_env_configuration():
                messagebox.showerror("❌ Błąd", "Nie można utworzyć pliku .env")
                return

    if not os.path.exists(env_path):
        messagebox.showerror("❌ Błąd", f"Nie znaleziono pliku konfiguracji:\n{env_path}")
        return

    env_editor_cls(app, env_path)
