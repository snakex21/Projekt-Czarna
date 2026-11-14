"""Dialog ustawień administratora launchera.

Moduł wydzielony z ``launcher_app.py``. Zawiera wyłącznie warstwę Tkinter;
operacje hashowania i formatowania .env są delegowane do
``launcher.services.admin_config_service``.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

from launcher.config.paths import BACKEND_DIR
from launcher.db.engine import get_engine
from launcher.services import admin_config_service
from launcher.utils import get_location_env_path, read_env_config, scale_window, scale_wrap, set_dialog_icon


SQLITE_MODE = get_engine().name == "sqlite"


class AdminSettings(tk.Toplevel):
    """Okno ustawień administratora."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔐 Ustawienia Administratora")
        set_dialog_icon(self)
        self.transient(parent)
        self.grab_set()
        self.parent_app = parent

        scale_window(self, parent, 520, 360)
        self.center_window()

        self.load_current_settings()
        self.create_widgets()

    def load_current_settings(self):
        """Wczytuje obecne ustawienia z .env."""
        env_config = read_env_config()

        self.username = tk.StringVar(value=env_config.get('ADMIN_USERNAME', 'admin'))
        self.password = tk.StringVar(value='')
        self.env = env_config

    def create_widgets(self):
        """Tworzy interfejs ustawień."""
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        # Logowanie jest zawsze włączone (v2.0.0). Bez przełącznika: pokazujemy
        # stan i jedyny sposób wyłączenia (ręcznie w .env, tylko do testów).
        insecure = admin_config_service.auth_insecurely_disabled(self.env)
        ttk.Label(frm, text=admin_config_service.auth_status_text(self.env),
                  foreground="#b02a37" if insecure else "#198754",
                  font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        ttk.Label(frm, foreground="#6c757d",
                  text=admin_config_service.INSECURE_DISABLE_HINT,
                  wraplength=scale_wrap(self, 480)).pack(anchor=tk.W, pady=(2, 8), fill=tk.X)

        row1 = ttk.Frame(frm)
        row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="Login administratora:", width=22).pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.username).pack(side=tk.LEFT, fill=tk.X, expand=True)

        row2 = ttk.Frame(frm)
        row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="Nowe hasło (opcjonalnie):", width=22).pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.password, show="•").pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(frm, foreground="#6c757d",
                 text="Zostanie zapisane w .env jako hash. Pozostaw puste, by nie zmieniać.",
                 wraplength=scale_wrap(self, 480)).pack(anchor=tk.W, pady=(6, 10), fill=tk.X)

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btns, text="💾 Zapisz", command=self.save, style="Success.TButton").pack(side=tk.RIGHT)
        ttk.Button(btns, text="Anuluj", command=self.destroy, style="Secondary.TButton").pack(side=tk.RIGHT, padx=(0, 8))

    def save(self):
        """Zapisuje ustawienia administratora."""
        if not self.username.get().strip():
            messagebox.showwarning("Walidacja", "Login nie może być pusty.", parent=self)
            return

        try:
            changed = admin_config_service.apply_admin_settings(
                self.env,
                self.username.get().strip(),
                self.password.get(),
            )
        except ImportError:
            messagebox.showerror("Brak zależności", "Brakuje pakietu Werkzeug.", parent=self)
            return
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się utworzyć hasha: {e}", parent=self)
            return

        # W SQLite backend czyta backend/.env; w PostgreSQL pozostaje .env miejscowości.
        if SQLITE_MODE:
            env_path = os.path.join(str(BACKEND_DIR), ".env")
        else:
            try:
                env_path = get_location_env_path()
            except ValueError:
                messagebox.showerror("❌ Błąd", "Brak aktywnej miejscowości", parent=self)
                return

        self._save_env_file(env_path)

        self.parent_app.on_env_changed()

        # Auto-restart, żeby backend wczytał nowy login/hash hasła.
        if changed and "backend" in self.parent_app.process_mgr.managed_processes:
            was_network = self.parent_app.process_mgr.managed_processes["backend"].get("network_mode", False)

            messagebox.showinfo("🔄  Restart serwera",
                              "Zmieniono dane logowania administratora.\n\n"
                              "Serwer backend zostanie automatycznie zrestartowany.",
                              parent=self)
            self.destroy()

            self.parent_app.log(f"\n{'='*60}\n")
            self.parent_app.log("🔄  Restartowanie serwera - zmiana danych logowania admina...\n")
            self.parent_app.log(f"   • Login: {self.env['ADMIN_USERNAME']}\n")
            self.parent_app.log(f"{'='*60}\n\n")

            self.parent_app.stop_managed_process("backend")

            def restart():
                if was_network:
                    self.parent_app.start_network_server()
                else:
                    self.parent_app.start_managed_process("backend", "Serwer Backend (Lokalny)")
                    self.parent_app.server_btn.config(text="⏹️ Zatrzymaj Serwer (Lokalny)", style="Danger.TButton")

            self.parent_app.after(800, restart)
        else:
            messagebox.showinfo("✅ Zapisano", "Ustawienia administratora zapisane.", parent=self)
            self.destroy()

    def _save_env_file(self, env_path):
        """Zapisuje plik .env z ładnym, jednolitym formatem."""
        backend_env_path = os.path.join(str(BACKEND_DIR), ".env")
        is_sqlite_backend_env = SQLITE_MODE and os.path.abspath(env_path) == os.path.abspath(backend_env_path)
        admin_config_service.save_env_file(
            env_path,
            self.env,
            sqlite_backend_env=is_sqlite_backend_env,
            sqlite_mode=SQLITE_MODE,
        )

    def center_window(self):
        """Wyśrodkowuje okno."""
        self.update_idletasks()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        x = px + (pw - 520) // 2
        y = py + (ph - 360) // 2
        self.geometry(f"+{x}+{y}")
