"""Pomocnicza logika obserwowania zmian pliku .env launchera."""

import os


def get_env_mtime(sqlite_mode: bool, backend_dir: str, get_location_env_path) -> float | None:
    """Zwraca czas modyfikacji aktywnego pliku .env albo ``None``."""
    try:
        env_path = os.path.join(backend_dir, ".env") if sqlite_mode else get_location_env_path()
        return os.path.getmtime(env_path)
    except Exception:
        # PostgreSQL może zostać zatrzymany/odinstalowany w trakcie działania
        # launchera. W trybie PG ``get_location_env_path`` pobiera aktywną
        # miejscowość z DB, więc przy Connection refused nie wolno crashować
        # callbacka Tkinter -- watcher ma po prostu pominąć ten tick.
        return None


def should_handle_env_change(previous_mtime, current_mtime) -> tuple[object, bool]:
    """Aktualizuje stan mtime i mówi, czy wykryto realną zmianę pliku."""
    if previous_mtime is None:
        return current_mtime, False
    if current_mtime is not None and current_mtime != previous_mtime:
        return current_mtime, True
    return previous_mtime, False


def env_port_changed(old_port, new_port, was_running: bool) -> bool:
    """Czy zmiana .env wymaga pytania o restart backendu."""
    return bool(was_running and old_port and new_port and old_port != new_port)
