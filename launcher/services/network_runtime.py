"""Network backend runtime helpers delegated from ProcessManager."""

from __future__ import annotations

import platform
import socket
import sys
from tkinter import messagebox

from launcher.ui.network_dialogs import NetworkInfoDialog
from launcher.utils import get_flask_config, get_local_ip


def _log_network_security_warnings(process_mgr) -> None:
    """Loguje ostrzeżenia bezpieczeństwa dla trybu sieciowego (Priorytet 6.7).

    Gdy admin_auth wyłączony a backend udostępniony w LAN - ryzyko.
    Importujemy lokalnie (bez hard importu) żeby uniknąć cykliczności.
    """
    try:
        from backend.auth.security import get_network_security_warnings
        warnings = get_network_security_warnings()
        for w in warnings:
            process_mgr.app.log(w + "\n")
    except Exception as exc:
        # Nigdy nie blokuj startu z powodu ostrzeżenia - tylko log
        try:
            process_mgr.app.log(
                f"⚠️ Nie udało się sprawdzić bezpieczeństwa sieciowego: {exc}\n"
            )
        except Exception:
            pass


def toggle_network_server(process_mgr) -> None:
    """Toggle the backend network server using the existing ProcessManager API."""
    if "backend" in process_mgr.managed_processes:
        if process_mgr.managed_processes["backend"].get("network_mode"):
            process_mgr.stop_managed_process("backend")
            process_mgr.app.network_server_btn.config(text="🌐 Uruchom Serwer Sieciowy", style="Info.TButton")
        else:
            messagebox.showwarning(
                "⚠️ Uwaga",
                "Lokalny serwer jest już uruchomiony.\n"
                "Zatrzymaj go najpierw, aby uruchomić serwer sieciowy.",
            )
    else:
        process_mgr.toggle_server(network_mode=True)


def start_network_server(process_mgr) -> None:
    """Start FastAPI backend bound to all interfaces for LAN access."""
    if platform.system() == "Windows":
        process_mgr.setup_firewall_rule()

    local_ip = get_local_ip()
    flask_config = get_flask_config()
    port = int(flask_config["port"])

    process_mgr.app.log("🌐 Uruchamianie serwera w trybie SIECIOWYM...\n")
    process_mgr.app.log("📡 Serwer będzie dostępny pod adresami:\n")
    process_mgr.app.log(f"   • Lokalnie: http://127.0.0.1:{port}\n")
    process_mgr.app.log(f"   • W sieci LAN: http://{local_ip}:{port}\n")
    process_mgr.app.log(f"   • Alternatywnie: http://{socket.gethostname()}:{port}\n")
    process_mgr.app.log(f"⚠️ UWAGA: Upewnij się, że firewall nie blokuje portu {port}!\n\n")

    cmd = [sys.executable, "-X", "utf8", "-u", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", str(port)]
    extra_info = {"network_mode": True, "local_ip": local_ip}
    pre_spawn_log = [
        ("🚀 Uruchamianie serwera web FastAPI w trybie sieciowym...\n", True),
        ("📡 Serwer nasłuchuje na wszystkich interfejsach (0.0.0.0)\n", True),
        ("=" * 60 + "\n", True),
    ]

    process_mgr.start_managed_process(
        "backend",
        "Serwer Backend (Sieciowy)",
        cmd_override=cmd,
        extra_info=extra_info,
        pre_spawn_log=pre_spawn_log,
        tab_title="🌐 Serwer Sieciowy",
    )

    process_mgr.app.network_server_btn.config(text="⏹️ Zatrzymaj Serwer Sieciowy", style="Danger.TButton")
    # Priorytet 6.7: ostrzeżenie gdy ADMIN_AUTH_ENABLED=False w trybie sieciowym
    _log_network_security_warnings(process_mgr)
    process_mgr.show_network_info_dialog(local_ip)


def show_network_info_dialog(app, local_ip: str) -> None:
    """Show the LAN access information dialog."""
    NetworkInfoDialog(app, local_ip)
