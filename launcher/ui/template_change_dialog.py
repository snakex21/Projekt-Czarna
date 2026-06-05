"""Dialog zmiany szablonu strony dla miejscowości."""

import tkinter as tk
from tkinter import ttk, messagebox

from ..db.engine import get_engine
from ..db.postgres import get_launcher_postgres_connection
from ..utils import set_dialog_icon, scale_window, scale_font, scale_wrap, apply_homepage_template
from ..services.location_service import set_location_template


__all__ = ["TemplateChangeDialog"]


class TemplateChangeDialog(tk.Toplevel):
    """Dialog do zmiany szablonu strony dla miejscowości."""

    def __init__(self, parent, location_id, location_name):
        super().__init__(parent)
        self.transient(parent)
        set_dialog_icon(self)
        self.title(f"🎨 Zmień Szablon - {location_name}")
        self.grab_set()

        self.location_id = location_id
        self.location_name = location_name

        scale_window(self, parent, 500, 350)
        self.center_window()

        self.create_widgets()

    def center_window(self):
        """Centruje okno na ekranie."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def create_widgets(self):
        """Tworzy interfejs wyboru szablonu."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Nagłówek
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(header_frame, text=f"Wybierz szablon dla: {self.location_name}",
                 font=scale_font(self, 12, "bold")).pack(anchor=tk.W)

        # Pobierz aktualny szablon z PostgreSQL
        try:
            conn = get_launcher_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT homepage_template FROM locations WHERE id = %s", (self.location_id,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            current_template = result[0] if result and result[0] else "standardowy"
        except Exception as e:
            print(f"❌ Błąd pobierania szablonu: {e}")
            current_template = "standardowy"

        # Lista szablonów
        templates_frame = ttk.LabelFrame(main_frame, text="Dostępne szablony", padding="10")
        templates_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.template_var = tk.StringVar(value=current_template)

        # Szablon 1: Standardowy
        template1_frame = ttk.Frame(templates_frame)
        template1_frame.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(template1_frame, text="📍 Standardowy",
                       variable=self.template_var, value="standardowy").pack(anchor=tk.W)

        ttk.Label(template1_frame, text="Uniwersalny szablon dostosowany do różnych miejscowości.\n"
                                        "Automatycznie podstawia nazwę, powiat i region.",
                 foreground="#666666", wraplength=scale_wrap(self, 450)).pack(anchor=tk.W, padx=(25, 0), pady=(2, 0))

        # Separator
        ttk.Separator(templates_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Szablon 2: Praca inżynierska
        template2_frame = ttk.Frame(templates_frame)
        template2_frame.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(template2_frame, text="🎓 Praca Inżynierska",
                       variable=self.template_var, value="praca_inzynierska").pack(anchor=tk.W)

        ttk.Label(template2_frame, text="Oryginalna strona dla projektu studenckiego o gminie Czarna.\n"
                                        "Zawiera informacje o Akademii Tarnowskiej.",
                 foreground="#666666", wraplength=scale_wrap(self, 450)).pack(anchor=tk.W, padx=(25, 0), pady=(2, 0))

        # Przyciski
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)

        ttk.Button(buttons_frame, text="Anuluj", command=self.destroy,
                  style="Secondary.TButton").pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(buttons_frame, text="✅ Zapisz i Zastosuj", command=self.save_template,
                  style="Success.TButton").pack(side=tk.RIGHT)

    def save_template(self):
        """Zapisuje wybrany szablon dla miejscowości."""
        template_name = self.template_var.get()

        # Zapisz szablon w bazie danych
        set_location_template(self.location_id, template_name)

        # Jeśli to aktywna miejscowość, od razu zastosuj szablon
        active_location = get_engine().get_active_location()
        if active_location and active_location[0] == self.location_id:
            success = apply_homepage_template(template_name)
            if success:
                messagebox.showinfo("✅ Sukces",
                                   f"Szablon '{template_name}' został zapisany i zastosowany!\n\n"
                                   f"Odśwież stronę w przeglądarce aby zobaczyć zmiany.",
                                   parent=self)
            else:
                messagebox.showwarning("⚠️ Zapisano",
                                      f"Szablon '{template_name}' został zapisany, ale nie udało się go zastosować.\n"
                                      f"Sprawdź logi aby uzyskać więcej informacji.",
                                      parent=self)
        else:
            messagebox.showinfo("✅ Sukces",
                               f"Szablon '{template_name}' został zapisany.\n\n"
                               f"Zostanie zastosowany gdy aktywujesz tę miejscowość.",
                               parent=self)

        self.destroy()
