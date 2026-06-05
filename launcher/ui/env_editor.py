"""Hybrydowy edytor pliku .env launchera.

Moduł wydzielony z ``launcher_app.py``. Logika tekstowa, walidacja i domyślne
treści .env pozostają w ``launcher.services.env_config_service``.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from launcher.config.paths import BACKEND_DIR
from launcher.db.engine import get_engine
from launcher.services import env_config_service
from launcher.utils import set_dialog_icon


SQLITE_MODE = get_engine().name == "sqlite"


class EnvEditor(tk.Toplevel):
    """Edytor pliku konfiguracyjnego .env."""

    def __init__(self, parent, env_path):
        super().__init__(parent)
        self.title("⚙️ Edytor Konfiguracji Bazy Danych")
        set_dialog_icon(self)
        self.parent_app = parent
        self.env_path = env_path

        # Skaluj rozmiar okna wg DPI i ui_scale
        scale = max(0.85, min(float(getattr(parent, 'ui_scale', 1.0) or 1.0), 2.0))
        w = int(820 * scale)
        h = int(620 * scale)
        self.geometry(f"{w}x{h}")
        self.minsize(int(720 * scale), int(520 * scale))
        self.center_window()

        self.create_widgets()
        self.load_content()

    def create_widgets(self):
        """Tworzy hybrydowy edytor: formularz GUI + surowy plik .env."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Skala czcionek i wraplength
        scale = max(self.parent_app.winfo_fpixels("1i") / 96, getattr(self.parent_app, 'ui_scale', 1.0))
        fsize = lambda s: max(8, int(round(s * scale)))
        wrap = lambda w: int(round(w * scale))

        ttk.Label(main_frame, text="⚙️ Konfiguracja aplikacji i bazy danych",
                 font=("Segoe UI", fsize(12), "bold")).pack(pady=(0, 10))

        ttk.Label(main_frame,
                 text="Edytuj najważniejsze ustawienia w formularzu albo przejdź do zakładki zaawansowanej i edytuj surowy plik .env.",
                 wraplength=wrap(760), foreground="#666666").pack(pady=(0, 10))

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.form_tab = ttk.Frame(self.notebook, padding=10)
        self.raw_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.form_tab, text="🧩 Formularz")
        self.notebook.add(self.raw_tab, text="📝 Zaawansowane (.env)")

        self.form_vars = {}
        self.admin_enabled_var = tk.BooleanVar(value=False)
        self.create_form_tab()

        self.text_editor = scrolledtext.ScrolledText(self.raw_tab, wrap=tk.WORD,
                                                     font=("Consolas", fsize(10)), height=15)
        self.text_editor.pack(fill=tk.BOTH, expand=True)

        raw_actions = ttk.Frame(self.raw_tab)
        raw_actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(raw_actions, text="⬅️ Wczytaj .env do formularza",
                   command=self.load_form_from_raw).pack(side=tk.LEFT, padx=5)
        ttk.Button(raw_actions, text="➡️ Zastosuj formularz do .env",
                   command=self.sync_form_to_raw).pack(side=tk.LEFT, padx=5)

        # Przyciski
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="💾 Zapisz zmiany", command=self.save_env,
                  style="Success.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="🔄  Przywróć domyślne", command=self.reset_defaults,
                  style="Warning.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="❌ Zamknij", command=self.destroy,
                  style="Secondary.TButton").pack(side=tk.RIGHT, padx=5)

    def create_form_tab(self):
        """Buduje czytelny formularz dla najważniejszych kluczy .env."""
        canvas = tk.Canvas(self.form_tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.form_tab, orient="vertical", command=canvas.yview)
        form = ttk.Frame(canvas)
        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(form_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            # Windows/macOS używają event.delta, Linux często Button-4/5.
            if getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(_event=None):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_mousewheel(_event=None):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        self.form_tab.bind("<Enter>", _bind_mousewheel)
        self.form_tab.bind("<Leave>", _unbind_mousewheel)
        canvas.bind("<Enter>", _bind_mousewheel)
        form.bind("<Enter>", _bind_mousewheel)

        def section(title):
            lf = ttk.LabelFrame(form, text=title, padding=10)
            lf.pack(fill=tk.X, pady=(0, 10))
            lf.columnconfigure(1, weight=1)
            return lf

        def entry(parent, row, label, key, default="", show=None):
            ttk.Label(parent, text=label, width=24).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
            var = tk.StringVar(value=default)
            self.form_vars[key] = var
            ttk.Entry(parent, textvariable=var, show=show).grid(row=row, column=1, sticky="ew", pady=4)
            return var

        server = section("🌐 Serwer i porty")
        entry(server, 0, "Host backendu", "FLASK_HOST", "127.0.0.1")
        entry(server, 1, "Port backendu", "FLASK_PORT", "5000")
        entry(server, 2, "Port edytora genealogii", "GENEALOGY_EDITOR_PORT", "5001")
        entry(server, 3, "Port edytora działek", "PARCEL_EDITOR_PORT", "5003")

        db = section("🗄️ Baza danych")
        ttk.Label(db, text="Silnik", width=24).grid(row=0, column=0, sticky="w", pady=4, padx=(0, 8))
        engine_var = tk.StringVar(value="sqlite")
        self.form_vars["DB_ENGINE"] = engine_var
        ttk.Combobox(db, textvariable=engine_var, values=["sqlite", "postgresql"], state="readonly").grid(row=0, column=1, sticky="ew", pady=4)
        entry(db, 1, "Ścieżka SQLite", "DB_PATH", "data/czarna.db")
        entry(db, 2, "Host PostgreSQL", "DB_HOST", "localhost")
        entry(db, 3, "Port PostgreSQL", "DB_PORT", "5432")
        entry(db, 4, "Użytkownik PostgreSQL", "DB_USER", "postgres")
        entry(db, 5, "Hasło PostgreSQL", "DB_PASSWORD", "1234")
        entry(db, 6, "Nazwa bazy", "DB_NAME", "mapa_czarna_db")

        sec = section("🔐 Bezpieczeństwo")
        ttk.Checkbutton(sec, text="Włącz logowanie administratora", variable=self.admin_enabled_var).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
        entry(sec, 1, "Login admina", "ADMIN_USERNAME", "admin")
        entry(sec, 2, "Hash hasła admina", "ADMIN_PASSWORD_HASH", "")
        entry(sec, 3, "Sekretny klucz", "FLASK_SECRET_KEY", "dev-secret-change-me")

    def parse_env_content(self, content):
        return env_config_service.parse_env_content(content)

    def set_raw_content(self, content):
        self.text_editor.delete('1.0', tk.END)
        self.text_editor.insert('1.0', content)

    def get_raw_content(self):
        return self.text_editor.get('1.0', 'end-1c')

    def load_form_from_raw(self):
        """Wypełnia formularz na podstawie aktualnego tekstu .env."""
        config = self.parse_env_content(self.get_raw_content())
        defaults = env_config_service.form_defaults(SQLITE_MODE)
        for key, var in self.form_vars.items():
            var.set(config.get(key, defaults.get(key, "")))
        self.admin_enabled_var.set(config.get("ADMIN_AUTH_ENABLED", "0") == "1")

    def sync_form_to_raw(self):
        """Przenosi wartości z formularza do surowego .env, zachowując nieznane klucze i komentarze."""
        updates = {key: var.get().strip() for key, var in self.form_vars.items()}
        updates["ADMIN_AUTH_ENABLED"] = "1" if self.admin_enabled_var.get() else "0"
        content = self.update_env_content(self.get_raw_content(), updates)
        self.set_raw_content(content)
        return content

    def update_env_content(self, content, updates):
        return env_config_service.update_env_content(content, updates)

    def validate_env_content(self, content):
        """Waliduje porty z .env: liczby, zakres i brak duplikatów."""
        ok, error = env_config_service.validate_env_content(content)
        if not ok:
            messagebox.showerror("❌ Błąd walidacji", error, parent=self)
        return ok

    def load_content(self):
        """Wczytuje zawartość pliku .env."""
        try:
            content = env_config_service.read_text_file(self.env_path)
            self.set_raw_content(content)
            self.load_form_from_raw()
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Nie można wczytać pliku .env:\n{e}", parent=self)
            self.destroy()

    def save_env(self):
        """Zapisuje zmiany do pliku .env."""
        try:
            # Jeśli użytkownik jest na formularzu, najpierw przenieś wartości do .env.
            # Jeśli jest w zakładce zaawansowanej, zapisujemy dokładnie surowy tekst.
            current_tab = self.notebook.tab(self.notebook.select(), "text")
            content = self.get_raw_content() if ".env" in current_tab else self.sync_form_to_raw()

            if not self.validate_env_content(content):
                return

            env_config_service.write_text_file(self.env_path, content)

            self.parent_app.on_env_changed()

            messagebox.showinfo("✅ Sukces",
                              "Konfiguracja została zapisana.\n"
                              "Jeśli zmieniłeś port – pojawi się pytanie o restart serwera.",
                              parent=self)
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Nie można zapisać pliku:\n{e}", parent=self)

    def reset_defaults(self):
        """Przywraca domyślną konfigurację."""
        if messagebox.askyesno("⚠️ Potwierdzenie",
                               "Czy na pewno chcesz przywrócić domyślną konfigurację?",
                               parent=self):
            is_sqlite_backend_env = SQLITE_MODE and os.path.abspath(self.env_path) == os.path.abspath(os.path.join(str(BACKEND_DIR), ".env"))
            default_content = env_config_service.default_env_content(is_sqlite_backend_env)
            self.text_editor.delete('1.0', tk.END)
            self.text_editor.insert('1.0', default_content)
            self.load_form_from_raw()

    def center_window(self):
        """Wyśrodkowuje okno."""
        self.update_idletasks()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")
