"""Uniwersalne okno postępu dla operacji launchera."""

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from launcher.utils import scale_font, scale_window, scale_wrap, set_dialog_icon


class ProgressDialog(tk.Toplevel):
    """Okno dialogowe postępu operacji."""

    def __init__(self, parent, task_func, task_args):
        super().__init__(parent)
        self.title("💾 Tworzenie Kopii Zapasowej")
        set_dialog_icon(self)
        self.transient(parent)
        self.grab_set()

        scale_window(self, parent, 400, 180, resizable=False)
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        ttk.Label(self, text="📦 Przygotowywanie plików...",
                 font=scale_font(self, 11), padding=10).pack(pady=(15, 5))

        self.progress_bar = ttk.Progressbar(self, orient="horizontal", length=360, mode="determinate")
        self.progress_bar.pack(pady=5, padx=20)

        self.status_label = ttk.Label(self, text="", padding=5, wraplength=scale_wrap(self, 350))
        self.status_label.pack(pady=(5, 10))

        self.success = None
        self.result = None
        self.error_message = None

        threading.Thread(target=self._run_task, args=(task_func, task_args), daemon=True).start()

    def _run_task(self, task_func, task_args):
        """Wykonuje zadanie w osobnym wątku."""
        try:
            def progress_callback(current, total, message):
                self.progress_bar["maximum"] = total
                self.progress_bar["value"] = current
                self.status_label.config(text=message)
                self.update_idletasks()

            self.result = task_func(progress_callback, task_args)
            self.success = True
        except Exception as e:
            self.success = False
            self.error_message = str(e)
        finally:
            self.after(100, self._finish)

    def _finish(self):
        """Kończy operację i wyświetla wynik."""
        self.destroy()

        if self.success:
            messagebox.showinfo("✅ Sukces", f"Utworzono kopię zapasową:\n{self.result}", parent=self.master)
            self.master.populate_backup_list()
        else:
            messagebox.showerror("❌ Błąd", f"Nie udało się utworzyć kopii:\n{self.error_message}", parent=self.master)
