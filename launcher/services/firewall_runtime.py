"""Windows Firewall runtime helpers for launcher network mode.

The functions here preserve the historical launcher behavior while keeping
``launcher_app.py`` and ``process_manager.py`` free of direct ``netsh`` logic.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from tkinter import messagebox
from typing import Callable

from launcher.ui.network_dialogs import FirewallInstructions


def setup_firewall_rule(app, get_flask_config: Callable[[], dict]) -> bool:
    """Configure the interactive Windows Firewall rule for the active port."""
    if platform.system() != "Windows":
        return True

    flask_config = get_flask_config()
    port = int(flask_config["port"])
    rule_name = f"Flask Server Port {port}"
    check_cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        app.log("✅ Reguła firewall już istnieje.\n")
        return True

    app.log("🔧 Konfigurowanie reguły firewall...\n")
    add_cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport={port} enable=yes profile=any'

    try:
        import ctypes

        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        if not is_admin:
            response = messagebox.askyesno(
                "🔐 Wymagane uprawnienia administratora",
                "Aby automatycznie skonfigurować firewall, aplikacja musi być uruchomiona jako Administrator.\n\n"
                "• TAK - Uruchomić ponownie jako Administrator?\n"
                "• NIE - Skonfigurować firewall ręcznie później?",
                icon="warning",
            )
            if response:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                app.destroy()
                sys.exit(0)
            app.log("⚠️ Firewall nie został skonfigurowany. Skonfiguruj go ręcznie.\n")
            show_firewall_instructions(app)
            return False

        result = subprocess.run(add_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            app.log("✅ Reguła firewall została dodana pomyślnie!\n")
            messagebox.showinfo("✅ Sukces", f"Reguła firewall została skonfigurowana.\nPort {port} jest teraz otwarty.")
            return True

        app.log(f"❌ Błąd dodawania reguły: {result.stderr}\n")
        return False
    except Exception as e:
        app.log(f"❌ Błąd konfiguracji firewall: {e}\n")
        return False


def setup_firewall_rule_for_port(port: int) -> None:
    """Configure a quiet Windows Firewall rule for an explicit port."""
    if platform.system() != "Windows":
        return

    rule_name = f"Flask Server Port {port}"
    check_cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        return

    add_cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport={port} enable=yes profile=any'
    subprocess.run(add_cmd, shell=True)


def show_firewall_instructions(app) -> None:
    """Show the manual firewall configuration instructions dialog."""
    FirewallInstructions(app)
