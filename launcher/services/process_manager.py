"""Zarządzanie cyklem życia procesów — scentralizowana klasa."""

import platform
import queue
import signal
import socket
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from ..config.settings import COLORS, SCRIPTS, get_urls
from . import firewall_runtime, network_runtime


class ProcessManager:
    """Centralizuje zarządzanie procesami, kolejką zdarzeń i UI procesów."""

    def __init__(self, app):
        self.app = app
        self.managed_processes = {}
        self.event_queue = queue.Queue()
        self._displayed_processes = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def has_running_process(self, key):
        return key in self.managed_processes

    def has_network_server(self):
        return "backend" in self.managed_processes and self.managed_processes["backend"].get("network_mode", False)

    def enqueue_event(self, event_type, *args):
        """Public API for other modules to post events."""
        self.event_queue.put((event_type, *args))

    def get_running_processes_info(self):
        """Returns a safe copy of managed_processes info for diagnostics."""
        return {k: {"name": v["name"], "pid": v["process"].pid} for k, v in self.managed_processes.items()}

    # ------------------------------------------------------------------
    # Console tab creation (was _create_process_tab in process_runtime)
    # ------------------------------------------------------------------

    def _create_process_tab(self, name, tab_title=None):
        tab_frame = ttk.Frame(self.app.notebook)
        console = self.app.create_console_widget(tab_frame)
        title = tab_title if tab_title else f"\U0001f4cb {name}"
        self.app.notebook.add(tab_frame, text=title)
        self.app.notebook.select(tab_frame)
        return tab_frame, console

    # ------------------------------------------------------------------
    # Event queue processing (was process_queue in process_runtime)
    # ------------------------------------------------------------------

    def process_queue(self):
        """Uruchamia w\u0105tek nas\u0142uchuj\u0105cy na zdarzenia z kolejki (event-driven)."""
        def _event_listener():
            while True:
                event = self.event_queue.get()
                self.app.after(0, lambda e=event: self._dispatch_event(e))

        threading.Thread(target=_event_listener, daemon=True).start()

    def _dispatch_event(self, event):
        """Obs\u0142uguje pojedyncze zdarzenie z kolejki."""
        try:
            if len(event) == 2:
                key, event_type = event
                if event_type == "finished":
                    self.handle_process_finished(key)
            elif len(event) == 3:
                event_type, data1, data2 = event
                if event_type == "location_changed":
                    self.app.set_window_icon()
                    messagebox.showinfo(
                        "\u2705 Zmieniono miejscowo\u015b\u0107",
                        f"Aktywna miejscowo\u015b\u0107: {data1}\n\n"
                        "Niekt\u00f3re zmiany mog\u0105 wymaga\u0107 ponownego uruchomienia serwera.",
                    )
                elif event_type == "location_error":
                    messagebox.showerror("B\u0142\u0105d", f"Nie uda\u0142o si\u0119 zmieni\u0107 miejscowo\u015bci:\n{data2}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Process finished handler (was handle_process_finished in process_runtime)
    # ------------------------------------------------------------------

    def handle_process_finished(self, key):
        """Obs\u0142uguje zdarzenie zako\u0144czenia procesu."""
        if key not in self.managed_processes:
            return

        info = self.managed_processes[key]
        try:
            self.app.notebook.index(info["tab_frame"])
        except tk.TclError:
            return

        name = info["name"]

        msg = f"--- Proces '{name}' zako\u0144czy\u0142 dzia\u0142anie ---\n"
        self.app.log(msg, console=info["console"])
        self.app.log(msg)

        self.app.notebook.forget(info["tab_frame"])
        del self.managed_processes[key]
        self.update_processes_ui()

        if key == "backend":
            self.app.server_btn.config(text="\U0001f680 Uruchom Serwer Backend", style="Success.TButton")
            self.app.network_server_btn.config(text="\U0001f310 Uruchom Serwer Sieciowy", style="Info.TButton")

            if info.get("network_mode"):
                messagebox.showwarning(
                    "Serwer sieciowy si\u0119 wy\u0142\u0105czy\u0142",
                    "Proces zako\u0144czy\u0142 si\u0119 niespodziewanie.\n\n"
                    "Diagnostyka: uruchom r\u0119cznie w folderze backend:\n"
                    "python _network_server_wrapper.py",
                )

    # ------------------------------------------------------------------
    # UI refresh (was update_processes_ui in process_runtime)
    # ------------------------------------------------------------------

    def update_processes_ui(self):
        """Od\u015bwie\u017ca list\u0119 uruchomionych proces\u00f3w."""
        current_keys = set(self.managed_processes.keys())
        displayed_keys = set(self._displayed_processes.keys())

        if current_keys == displayed_keys and len(self.app.processes_frame.winfo_children()) > 0:
            return

        if not displayed_keys and current_keys:
            for widget in self.app.processes_frame.winfo_children():
                widget.destroy()
            self._displayed_processes.clear()

        for key in displayed_keys - current_keys:
            if key in self._displayed_processes:
                self._displayed_processes[key].destroy()
                del self._displayed_processes[key]

        for key in current_keys - displayed_keys:
            info = self.managed_processes[key]
            proc_frame = ttk.Frame(self.app.processes_frame)
            proc_frame.pack(fill=tk.X, pady=3, padx=5)

            ttk.Label(proc_frame, text=f"\U0001f7e2 {info['name']} (PID: {info['process'].pid})", font=("Segoe UI", 10)).pack(side=tk.LEFT)
            ttk.Button(proc_frame, text="\u23f9\ufe0f Zatrzymaj", style="Danger.TButton", command=lambda k=key: self.stop_managed_process(k), width=12).pack(side=tk.RIGHT, padx=5)
            self._displayed_processes[key] = proc_frame

        if not self.managed_processes:
            for widget in self.app.processes_frame.winfo_children():
                widget.destroy()
            self._displayed_processes.clear()
            ttk.Label(self.app.processes_frame, text="\U0001f4ed Brak uruchomionych proces\u00f3w", foreground=COLORS['secondary']).pack(pady=10)

    # ------------------------------------------------------------------
    # Start managed process (was start_managed_process in process_runtime)
    # ------------------------------------------------------------------

    def start_managed_process(self, key, name, cmd_override=None, extra_info=None, pre_spawn_log=None, tab_title=None):
        """Uruchamia zewn\u0119trzny skrypt jako zarz\u0105dzany proces."""
        if key in self.managed_processes:
            messagebox.showwarning("\u26a0\ufe0f Proces ju\u017c dzia\u0142a", f"Proces '{name}' jest ju\u017c uruchomiony.")
            return

        self.app.log(f"\U0001f680 Uruchamianie: {name}...\n")

        tab_frame, console = self._create_process_tab(name, tab_title)

        if pre_spawn_log:
            for msg, use_tab in pre_spawn_log:
                if use_tab:
                    self.app.log(msg, console=console)
                else:
                    self.app.log(msg)
        elif key == "backend":
            self.app.log("\U0001f680 Uruchamianie serwera web FastAPI...\n", console=console)
            self.app.log("\U0001f4e1 Serwer backend startuje lokalnie...\n", console=console)
            self.app.log("=" * 60 + "\n", console=console)

        env = self.app._prepare_process_env()

        if cmd_override:
            command = cmd_override
            script_info = SCRIPTS.get(key, {})
        else:
            script_info = SCRIPTS[key]
            command = self.app._prepare_command(key, script_info)

        creation_flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if platform.system() == "nt" else 0

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=script_info.get("cwd") if cmd_override else script_info["cwd"],
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
            env=env,
        )

        info = {"process": process, "console": console, "tab_frame": tab_frame, "name": name}
        if extra_info:
            info.update(extra_info)
        self.managed_processes[key] = info

        threading.Thread(target=self.read_process_output, args=(key,), daemon=True).start()

        if cmd_override:
            urls = {}
        else:
            urls = get_urls()

        if key in urls and key != "backend":
            def _open_when_ready(url, process_key):
                import re as _re
                import time as _time
                port_match = _re.search(r':(\d{4,5})/', url)
                if not port_match:
                    _time.sleep(3)
                    try:
                        webbrowser.open(url)
                    except Exception:
                        pass
                    return
                port = int(port_match.group(1))
                if process_key in ("parcel_editor", "genealogy_editor"):
                    import requests as _requests
                    health_url = f"http://127.0.0.1:{port}/api/health"
                    for _ in range(40):
                        try:
                            r = _requests.get(health_url, timeout=0.5)
                            if r.status_code == 200:
                                webbrowser.open(url)
                                return
                        except Exception:
                            pass
                        _time.sleep(0.5)
                else:
                    for _ in range(40):
                        try:
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.settimeout(0.5)
                            result = s.connect_ex(('127.0.0.1', port))
                            s.close()
                            if result == 0:
                                webbrowser.open(url)
                                return
                        except Exception:
                            pass
                        _time.sleep(0.5)
                    try:
                        webbrowser.open(url)
                    except Exception:
                        pass
            threading.Thread(target=_open_when_ready, args=(urls[key], key), daemon=True).start()

        self.update_processes_ui()

    # ------------------------------------------------------------------
    # Stop managed process (was stop_managed_process in process_runtime)
    # ------------------------------------------------------------------

    def stop_managed_process(self, key, force=False):
        """Zatrzymuje zarz\u0105dzany proces."""
        if key not in self.managed_processes:
            return

        info = self.managed_processes[key]
        process = info["process"]
        name = info["name"]

        msg = f"\n\u23f9\ufe0f Zatrzymywanie procesu: {name}...\n"
        self.app.log(msg, console=info["console"])
        self.app.log(msg)

        try:
            if force:
                if platform.system() == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW, timeout=1)
                else:
                    process.kill()
            elif platform.system() == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
                process.wait(timeout=1)
            else:
                process.terminate()
                process.wait(timeout=1)
        except Exception:
            try:
                if platform.system() == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW, timeout=1)
                else:
                    process.kill()
            except Exception:
                pass

        del self.managed_processes[key]
        try:
            self.app.notebook.forget(info["tab_frame"])
        except Exception:
            pass
        self.update_processes_ui()

        if key == "backend":
            self.app.server_btn.config(text="\U0001f680 Uruchom Serwer Backend", style="Success.TButton")
            self.app.network_server_btn.config(text="\U0001f310 Uruchom Serwer Sieciowy", style="Info.TButton")

    # ------------------------------------------------------------------
    # Read process output (was read_process_output in process_runtime)
    # ------------------------------------------------------------------

    def read_process_output(self, key):
        """Czyta wyj\u015bcie z procesu."""
        if key not in self.managed_processes:
            return
        info = self.managed_processes.get(key)
        if not info:
            return
        process = info["process"]
        console = info["console"]
        for line in iter(process.stdout.readline, ""):
            self.app.after(0, self.app.log, line, console)
        process.stdout.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            for _ in range(60):
                if process.poll() is not None:
                    break
                time.sleep(1)
        if process.poll() is not None:
            self.event_queue.put((key, "finished"))

    # ------------------------------------------------------------------
    # Server toggling (was toggle_server in backend_runtime)
    # ------------------------------------------------------------------

    def toggle_server(self, network_mode=False):
        """Prze\u0142\u0105cza stan serwera backend."""
        if "backend" in self.managed_processes:
            self.stop_managed_process("backend")
        else:
            if network_mode:
                self.start_network_server()
            else:
                self.start_managed_process("backend", "Serwer Backend (Lokalny)")
                self.app.server_btn.config(text="\u23f9\ufe0f Zatrzymaj Serwer (Lokalny)", style="Danger.TButton")

    # ------------------------------------------------------------------
    # Network server toggle (was toggle_network_server in backend_runtime)
    # ------------------------------------------------------------------

    def toggle_network_server(self):
        """Prze\u0142\u0105cza serwer sieciowy."""
        return network_runtime.toggle_network_server(self)

    # ------------------------------------------------------------------
    # Start network server (was start_network_server in backend_runtime)
    # ------------------------------------------------------------------

    def start_network_server(self):
        """Uruchamia serwer FastAPI dostępny w sieci lokalnej."""
        return network_runtime.start_network_server(self)

    # ------------------------------------------------------------------
    # Firewall rule (was setup_firewall_rule in backend_runtime)
    # ------------------------------------------------------------------

    def setup_firewall_rule(self):
        """Konfiguruje regu\u0142\u0119 firewall Windows."""
        return firewall_runtime.setup_firewall_rule(self.app, self.app.load_flask_config)

    # ------------------------------------------------------------------
    # Firewall instructions dialog (was show_firewall_instructions in backend_runtime)
    # ------------------------------------------------------------------

    def show_firewall_instructions(self):
        """Wyświetla instrukcje ręcznej konfiguracji firewall."""
        return firewall_runtime.show_firewall_instructions(self.app)

    # ------------------------------------------------------------------
    # Network info dialog (was show_network_info_dialog in backend_runtime)
    # ------------------------------------------------------------------

    def show_network_info_dialog(self, local_ip):
        """Wyświetla okno dialogowe z informacjami o dostępie sieciowym."""
        return network_runtime.show_network_info_dialog(self.app, local_ip)
