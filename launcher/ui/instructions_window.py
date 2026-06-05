"""Okno instrukcji dostępu sieciowego."""

import tkinter as tk
from tkinter import ttk

from launcher.utils import set_dialog_icon, scale_font


__all__ = ["InstructionsWindow"]


class InstructionsWindow(tk.Toplevel):
    """Okno z instrukcjami dostępu sieciowego."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Instrukcja – dostęp sieciowy")
        set_dialog_icon(self)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        body = ttk.Frame(self, padding=14)
        body.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(body, text="Jak udostępnić aplikację w sieci lokalnej:",
                 font=scale_font(self, 11, "bold")).pack(anchor=tk.W, pady=(0, 6))
        
        ttk.Label(body, justify=tk.LEFT, text=(
            "1) Upewnij się, że serwer działa (zielony status).\n"
            "2) Komputer i urządzenie muszą być w tej samej sieci.\n"
            "3) Na innym urządzeniu wpisz adres IP z listy.\n"
            "4) Jeśli nie działa – dodaj regułę Zapory Windows.\n"
            "5) Sprawdzenie nasłuchu:\n"
            "   • PowerShell: Get-NetTCPConnection -LocalPort 5000\n"
            "   • CMD: netstat -ano | findstr :5000\n"
        )).pack(anchor=tk.W)
        
        ttk.Button(body, text="Zamknij", command=self.destroy,
                  style="Secondary.TButton").pack(anchor=tk.E, pady=(10, 0))
        
        # Wyśrodkowanie
        parent.update_idletasks()
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        self.focus_set()
