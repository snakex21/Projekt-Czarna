"""Runtime helpers for AppLauncher Guardian UI/status handling.

This module intentionally operates on an ``app`` object passed by the main
launcher module. It must not import the main application module: the main
application owns Tk widgets and delegates Guardian runtime behavior here.
"""

from __future__ import annotations

import platform
import subprocess
import threading
import time
from datetime import datetime
from typing import Callable, Mapping

from launcher.services import guardian_service


def load_guardian_config() -> bool:
    """Load Guardian enabled/disabled state from its compatibility service."""
    return guardian_service.load_guardian_config()


def save_guardian_config(app) -> None:
    """Save Guardian enabled/disabled state and update AppLauncher UI."""
    try:
        enabled = bool(app.guardian_enabled.get())
        guardian_service.save_guardian_config(enabled)
        status = "aktywny" if enabled else "wyłączony"
        app.log(f"🛡️ Status Strażnika: {status}\n")
        if enabled:
            app.run_proactive_health_check()
        else:
            app._guardian_check_generation = getattr(app, "_guardian_check_generation", 0) + 1
            app.guardian_status_text.set("⚪ Strażnik wyłączony")
            app.guardian_status_label.configure(foreground="gray")
    except Exception:
        pass


def run_proactive_health_check(
    app,
    get_active_location_name: Callable[[], str | None],
    *,
    base_dir: str,
    colors: Mapping[str, str],
) -> None:
    """Run a background Guardian health check for critical modules."""
    if not app.guardian_enabled.get():
        return

    app._guardian_check_generation = getattr(app, "_guardian_check_generation", 0) + 1
    check_generation = app._guardian_check_generation

    def _is_current_check():
        return app.guardian_enabled.get() and getattr(app, "_guardian_check_generation", 0) == check_generation

    def _set_checking_status():
        if _is_current_check():
            app.guardian_status_text.set("🔍 Sprawdzanie...")
            app.guardian_status_label.configure(foreground=colors["info"])

    def check_task():
        started_at = time.time()
        app.after(0, _set_checking_status)

        env = app._prepare_process_env()
        try:
            active_loc = get_active_location_name()
            if active_loc:
                env["TEST_LOCATION"] = active_loc
        except Exception:
            pass

        issues_found = 0
        for mod in guardian_service.CRITICAL_MODULES:
            cmd = guardian_service.health_check_command(mod)
            try:
                res = subprocess.run(
                    cmd,
                    cwd=base_dir,
                    capture_output=True,
                    text=True,
                    env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "nt" else 0,
                )
                if res.returncode != 0:
                    issues_found += 1
            except Exception:
                pass

        def _apply_result():
            if not _is_current_check():
                return
            if issues_found > 0:
                app.guardian_status_text.set(f"⚠️ Uwagi ({issues_found})")
                app.guardian_status_label.configure(foreground=colors["warning"])
            else:
                app.guardian_status_text.set("✅ System OK")
                app.guardian_status_label.configure(foreground=colors["success"])
            app._guardian_last_check_at = datetime.now()
            app._guardian_last_issues = issues_found
            app._guardian_last_duration = round(time.time() - started_at, 2)

        app.after(0, _apply_result)

        # Harmonogram: Następne sprawdzenie za godzinę.
        app.after(3600000, app.run_proactive_health_check)

    threading.Thread(target=check_task, daemon=True).start()


def get_guardian_status_snapshot(app, *, colors: Mapping[str, str]) -> dict:
    """Return the current Guardian state for settings/status panels."""
    enabled = (
        bool(app.guardian_enabled.get())
        if hasattr(app, "guardian_enabled")
        else load_guardian_config()
    )
    return {
        "enabled": enabled,
        "text": (
            app.guardian_status_text.get()
            if hasattr(app, "guardian_status_text")
            else ("✅ System OK" if enabled else "⚪ Strażnik wyłączony")
        ),
        "color": (
            str(app.guardian_status_label.cget("foreground"))
            if hasattr(app, "guardian_status_label")
            else (colors["success"] if enabled else "gray")
        ),
        "last_check_at": getattr(app, "_guardian_last_check_at", None),
        "last_issues": getattr(app, "_guardian_last_issues", None),
        "last_duration": getattr(app, "_guardian_last_duration", None),
    }
