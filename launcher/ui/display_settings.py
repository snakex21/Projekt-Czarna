"""Dialog ustawień skali interfejsu launchera.

Moduł wydzielony z ``launcher_app.py``. Zawiera wyłącznie okno Tkinter;
zapisywanie ustawienia i restart aplikacji pozostają w ``AppLauncher``.
"""

import tkinter as tk
from tkinter import ttk

from launcher.config.settings import COLORS
from launcher.config.ui_settings import get_ui_scale_setting
from launcher.utils import set_dialog_icon


class DisplaySettingsDialog(tk.Toplevel):
    """Okno ustawień skali interfejsu i czcionki launchera."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        self.title("🔎 Skala interfejsu")
        base_scale = max(parent.ui_scale, get_ui_scale_setting()) if hasattr(parent, "ui_scale") else get_ui_scale_setting()
        self.dialog_width = max(760, int(720 * base_scale))
        self.dialog_height = max(560, int(520 * base_scale))
        self.geometry(f"{self.dialog_width}x{self.dialog_height}")
        self.minsize(720, 520)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        set_dialog_icon(self)

        current_scale = get_ui_scale_setting()
        self.scale_var = tk.DoubleVar(value=round(current_scale * 100))
        self.scale_text_var = tk.StringVar(value=f"{int(round(current_scale * 100))}%")

        self._build_ui()
        self.center_window()
        self.update_preview()

    def _build_ui(self):
        main = ttk.Frame(self, padding=18)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="Rozmiar czcionki i skala UI", style="Heading.TLabel").pack(anchor=tk.W)
        ttk.Label(
            main,
            text="To ustawienie przydaje się szczególnie na dużych monitorach albo ekranach 4K.\n"
                 "Zmiana zostanie zapisana lokalnie i może zostać zastosowana po restarcie launchera.",
            wraplength=max(self.dialog_width - 80, 420),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(8, 14))

        selector_frame = ttk.LabelFrame(main, text="Skala interfejsu", padding=12)
        selector_frame.pack(fill=tk.X)

        ttk.Label(selector_frame, text="Mniej").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 8))
        self.scale_slider = ttk.Scale(
            selector_frame,
            from_=85,
            to=175,
            orient=tk.HORIZONTAL,
            variable=self.scale_var,
            command=self.on_slider_changed,
        )
        self.scale_slider.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(selector_frame, text="Więcej").grid(row=0, column=2, sticky="w", pady=4, padx=(8, 12))
        ttk.Label(selector_frame, textvariable=self.scale_text_var, width=6, font=("Segoe UI", 11, "bold")).grid(row=0, column=3, sticky="e")

        ttk.Label(
            selector_frame,
            text="Zakres: 85–175%. Suwak zaokrągla do 5%, więc łatwo ustawić np. 135% albo 140%.",
            foreground=COLORS['secondary'],
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))

        quick_frame = ttk.Frame(selector_frame)
        quick_frame.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Label(quick_frame, text="Szybko:").pack(side=tk.LEFT, padx=(0, 6))
        for percent in (100, 125, 135, 140, 150):
            ttk.Button(
                quick_frame,
                text=f"{percent}%",
                width=6,
                command=lambda p=percent: self.set_slider_percent(p),
            ).pack(side=tk.LEFT, padx=2)
        selector_frame.columnconfigure(1, weight=1)

        buttons = ttk.Frame(main)
        buttons.pack(fill=tk.X, pady=(14, 0), side=tk.BOTTOM)

        ttk.Button(buttons, text="Anuluj", command=self.destroy, style="Secondary.TButton").pack(side=tk.LEFT)
        ttk.Button(buttons, text="Zapisz", command=self.save_only, style="Success.TButton").pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Zapisz i uruchom ponownie", command=self.save_and_restart, style="Primary.TButton").pack(side=tk.RIGHT, padx=(0, 8))

        action_hint = ttk.Label(
            main,
            text="Jeśli przyciski były wcześniej ucięte, to okno można też ręcznie powiększyć.",
            foreground=COLORS['secondary'],
        )
        action_hint.pack(fill=tk.X, pady=(10, 0), side=tk.BOTTOM)

        preview_frame = ttk.LabelFrame(main, text="Podgląd", padding=12)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        self.preview_title = tk.Label(preview_frame, text="Przykładowy nagłówek", font=("Segoe UI", 14, "bold"))
        self.preview_title.pack(anchor="w")

        self.preview_text = tk.Label(
            preview_frame,
            text="Tak będą wyglądały etykiety, przyciski i część tekstów w launcherze.",
            justify=tk.LEFT,
            wraplength=max(self.dialog_width - 120, 420),
        )
        self.preview_text.pack(anchor="w", pady=(8, 10))

        self.preview_button = ttk.Button(preview_frame, text="Przykładowy przycisk")
        self.preview_button.pack(anchor="w")

        self.preview_hint = ttk.Label(
            preview_frame,
            text="Najlepszy efekt uzyskasz po restarcie aplikacji.",
            foreground=COLORS['secondary'],
        )
        self.preview_hint.pack(anchor="w", pady=(12, 0))
        self.bind("<Return>", lambda _event: self.save_only())
        self.bind("<Escape>", lambda _event: self.destroy())

    def center_window(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(self.winfo_width(), max(sw - 80, 400))
        h = min(self.winfo_height(), max(sh - 80, 300))
        x = max((sw - w) // 2, 0)
        y = max((sh - h) // 2, 0)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def get_selected_scale(self):
        percent = int(round(float(self.scale_var.get()) / 5) * 5)
        percent = max(85, min(percent, 175))
        return percent / 100

    def on_slider_changed(self, _value=None):
        percent = int(round(float(self.scale_var.get()) / 5) * 5)
        percent = max(85, min(percent, 175))
        self.scale_var.set(percent)
        self.scale_text_var.set(f"{percent}%")
        self.update_preview()

    def set_slider_percent(self, percent):
        self.scale_var.set(percent)
        self.scale_text_var.set(f"{percent}%")
        self.update_preview()

    def update_preview(self):
        scale = self.get_selected_scale()
        base = max(10, int(round(10 * scale)))
        self.preview_title.config(font=("Segoe UI", base + 4, "bold"))
        self.preview_text.config(font=("Segoe UI", base))
        self.preview_hint.config(font=("Segoe UI", max(base - 1, 9)))

    def save_only(self):
        if self.parent_app.apply_ui_scale(self.get_selected_scale(), restart_now=False):
            self.destroy()

    def save_and_restart(self):
        self.parent_app.apply_ui_scale(self.get_selected_scale(), restart_now=True)
