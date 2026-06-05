"""Loading dialog used during launcher initialization."""

import tkinter as tk
from tkinter import ttk

from ..utils import set_dialog_icon, scale_window, scale_font, scale_wrap


__all__ = ["LoadingDialog"]


class LoadingDialog(tk.Toplevel):
    """Okno z animacją ładowania podczas inicjalizacji."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Inicjalizacja systemu")
        set_dialog_icon(self)
        scale_window(self, parent, 450, 250)
        self.resizable(False, False)

        # Ukryj przyciski okna
        self.overrideredirect(False)
        if parent:
            self.transient(parent)

        # ZAWSZE NA WIERZCHU
        self.attributes('-topmost', True)

        # Główny frame
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Tytuł
        ttk.Label(main_frame, text="⚙️ Przygotowywanie systemu...",
                 font=scale_font(self, 14, "bold")).pack(pady=(0, 20))

        # Progress bar (animowany)
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=350)
        self.progress.pack(pady=10)
        self.progress.start(10)

        # Status text
        self.status_label = ttk.Label(main_frame, text="Sprawdzanie konfiguracji...",
                                      font=scale_font(self, 10), wraplength=scale_wrap(self, 400))
        self.status_label.pack(pady=20)

        # Szczegóły (mniejszym fontem)
        self.detail_label = ttk.Label(main_frame, text="",
                                      font=scale_font(self, 9), foreground='gray')
        self.detail_label.pack(pady=5)

        # Wymuś bycie na wierzchu i modal
        self.lift()
        self.focus_force()
        self.grab_set()  # Blokuj dostęp do innych okien
        self.center_window()

    def center_window(self):
        """Wyśrodkowuje okno względem rodzica albo ekranu."""
        self.update_idletasks()

        width = self.winfo_width()
        height = self.winfo_height()

        parent = self.master if isinstance(self.master, tk.Misc) else None
        if parent and parent.winfo_exists() and parent.state() != 'withdrawn':
            try:
                parent.update_idletasks()
                px = parent.winfo_rootx()
                py = parent.winfo_rooty()
                pw = parent.winfo_width()
                ph = parent.winfo_height()
                x = px + max((pw - width) // 2, 0)
                y = py + max((ph - height) // 2, 0)
            except Exception:
                x = (self.winfo_screenwidth() // 2) - (width // 2)
                y = (self.winfo_screenheight() // 2) - (height // 2)
        else:
            x = (self.winfo_screenwidth() // 2) - (width // 2)
            y = (self.winfo_screenheight() // 2) - (height // 2)

        x = max(x, 0)
        y = max(y, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def update_status(self, status, detail=""):
        """Aktualizuje tekst statusu."""
        self.status_label.config(text=status)
        self.detail_label.config(text=detail)
        self.lift()  # Zawsze wychodź na wierzch
        self.center_window()
        self.update()  # Odśwież GUI

    def close(self):
        """Zamyka okno."""
        self.progress.stop()
        try:
            self.grab_release()  # Zwolnij modal
        except:
            pass
        self.destroy()
