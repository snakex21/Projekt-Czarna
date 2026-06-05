"""launcher/ui/network_dialogs.py — Okna dialogowe sieciowe (firewall, network info)."""

import socket
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from ..config.settings import COLORS
from ..utils import set_dialog_icon, scale_window, get_flask_config


class FirewallInstructions(tk.Toplevel):
    """Okno z instrukcjami konfiguracji firewall."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("📋 Instrukcja konfiguracji Firewall")
        set_dialog_icon(self)
        scale_window(self, parent, 600, 500)
        self.transient(parent)

        flask_config = get_flask_config()
        port = int(flask_config['port'])

        frame = ttk.Frame(self, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True)

        content = f"""INSTRUKCJA RĘCZNEJ KONFIGURACJI FIREWALL WINDOWS
================================================

METODA 1 - Przez interfejs graficzny:
-------------------------------------
1. Naciśnij Win + R
2. Wpisz: wf.msc
3. Kliknij "Reguły przychodzące" → "Nowa reguła..."
4. Wybierz "Port" → TCP → "{port}" → "Zezwalaj"
5. Nazwa: "Flask Server Port {port}"

METODA 2 - PowerShell (jako Administrator):
-----------------------------------------
New-NetFirewallRule -DisplayName "Flask Server Port {port}" -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow

METODA 3 - Wiersz poleceń (jako Administrator):
--------------------------------------------
netsh advfirewall firewall add rule name="Flask Server Port {port}" dir=in action=allow protocol=TCP localport={port}

TESTOWANIE:
-----------
1. Uruchom serwer sieciowy
2. Na innym urządzeniu wpisz adres IP:{port}
3. Jeśli strona się ładuje - wszystko działa!
"""

        text.insert("1.0", content)
        text.config(state="disabled")

        ttk.Button(frame, text="Zamknij", command=self.destroy,
                   style="Primary.TButton").pack(pady=10)


class NetworkInfoDialog(tk.Toplevel):
    """Okno z informacjami o dostępie sieciowym."""

    def __init__(self, parent, local_ip):
        super().__init__(parent)
        self.title("Informacje o Dostępie Sieciowym")
        set_dialog_icon(self)
        self.transient(parent)
        self.grab_set()

        self.parent_app = parent
        parent._net_info_win = self

        flask_config = get_flask_config()
        port = flask_config['port']

        w, h = 600, 400
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.resizable(False, False)

        self.create_widgets(local_ip, port)

    def create_widgets(self, local_ip, port):
        """Tworzy interfejs z informacjami."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="✅ Serwer uruchomiony w trybie sieciowym!",
                 font=("Segoe UI", 14, "bold"),
                 foreground=COLORS['success']).pack(pady=(0, 20))

        # Adresy dostępu
        info_frame = ttk.LabelFrame(main_frame, text="📡 Adresy dostępu", padding="15")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        addresses = [
            ("Ten komputer:", f"http://127.0.0.1:{port}"),
            ("Inne urządzenia w sieci:", f"http://{local_ip}:{port}"),
            ("Alternatywny adres:", f"http://{socket.gethostname()}:{port}"),
        ]

        for label, address in addresses:
            addr_frame = ttk.Frame(info_frame)
            addr_frame.pack(fill=tk.X, pady=5)

            ttk.Label(addr_frame, text=label, width=25).pack(side=tk.LEFT)

            addr_entry = ttk.Entry(addr_frame, width=40)
            addr_entry.insert(0, address)
            addr_entry.config(state="readonly")
            addr_entry.pack(side=tk.LEFT, padx=10)

            def copy_addr(addr=address):
                self.clipboard_clear()
                self.clipboard_append(addr)
                messagebox.showinfo("✅ Skopiowano", f"Adres został skopiowany:\n{addr}", parent=self)

            ttk.Button(addr_frame, text="📋 Kopiuj", command=copy_addr, width=10).pack(side=tk.LEFT)

        # Komenda PowerShell
        ps_frame = ttk.LabelFrame(main_frame, text="⚡ Konfiguracja Firewall (PowerShell)", padding="15")
        ps_frame.pack(fill=tk.X, pady=10)

        ps_command = f'New-NetFirewallRule -DisplayName "CzarnaMapa" -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow -Profile Any'

        ps_entry = ttk.Entry(ps_frame, width=80)
        ps_entry.insert(0, ps_command)
        ps_entry.config(state="readonly")
        ps_entry.pack(side=tk.LEFT, padx=(0,10), fill=tk.X, expand=True)

        def copy_ps():
            self.clipboard_clear()
            self.clipboard_append(ps_command)
            messagebox.showinfo("✅ Skopiowano", "Komenda PowerShell została skopiowana.\nUruchom PowerShell jako Administrator i wklej komendę.", parent=self)

        ttk.Button(ps_frame, text="📋 Kopiuj", command=copy_ps, style="Primary.TButton").pack(side=tk.LEFT)

        # Instrukcja
        instr_row = ttk.Frame(main_frame)
        instr_row.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(instr_row, text="ℹ️").pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(instr_row, text="📘 Pokaż instrukcję (firewall / port 5000)",
                   command=self.open_network_instructions_centered,
                   style="Primary.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)

        ttk.Button(main_frame, text="OK, rozumiem", command=self.destroy,
                   style="Primary.TButton").pack(pady=10)

        # Dostosowanie rozmiaru
        self.update_idletasks()
        req_w = self.winfo_reqwidth()
        req_h = self.winfo_reqheight()
        self.geometry(f"{req_w}x{req_h}")
        self.minsize(req_w, req_h)

    def open_network_instructions_centered(self):
        """Otwiera wyskakujące okno z instrukcją dostępu sieciowego."""
        parent = getattr(self, "_net_info_win", self)

        win = tk.Toplevel(parent)
        win.title("Instrukcja – dostęp sieciowy / port 5000")
        set_dialog_icon(win)
        win.resizable(False, False)
        win.transient(parent)
        win.grab_set()

        body = ttk.Frame(win, padding=14)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text="Jak udostępnić aplikację w sieci lokalnej:",
                 font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 6))

        ttk.Label(body, justify=tk.LEFT, text=(
            "1) Upewnij się, że serwer działa (zielony status w oknie sieciowym).\n"
            "2) Komputer-serwer i urządzenie-klient muszą być w tej samej sieci Wi-Fi/LAN.\n"
            "3) Na innym urządzeniu wpisz adres IP z listy (np. http://192.168.x.x:5000).\n"
            "4) Jeśli nie działa – dodaj regułę Zapory Windows: TCP 5000, wszystkie profile.\n"
            "5) Sprawdzenie nasłuchu:\n"
            "   • PowerShell: Get-NetTCPConnection -LocalPort 5000\n"
            "   • CMD:       netstat -ano | findstr :5000\n"
        )).pack(anchor=tk.W)

        ttk.Button(body, text="Zamknij", command=win.destroy,
                   style="Secondary.TButton").pack(anchor=tk.E, pady=(10, 0))

        # Wyśrodkowanie
        parent.update_idletasks()
        win.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")
        win.focus_set()
