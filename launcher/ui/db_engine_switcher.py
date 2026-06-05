"""Dialog zmiany silnika bazy danych launchera."""

import tkinter as tk
from tkinter import ttk, messagebox

from launcher.db.engine import switch_engine
from launcher.utils import set_dialog_icon
from launcher.ui.database_config_dialogs import _run_edb_installer


__all__ = ["open_db_engine_switcher"]


def _friendly_postgres_status(message: str) -> str:
        """Zamienia techniczny błąd psycopg2 na krótki komunikat UI."""
        text = str(message or "").lower()
        if "connection refused" in text or "10061" in text:
                return "PostgreSQL nie działa albo nie jest zainstalowany. Wybierz SQLite albo uruchom/zainstaluj serwer."
        if "no password supplied" in text or "fe_sendauth" in text:
                return "Brakuje hasła PostgreSQL w konfiguracji. Uzupełnij konfigurację albo wybierz SQLite."
        if "password authentication failed" in text or "28p01" in text:
                return "Hasło PostgreSQL jest nieprawidłowe. Popraw konfigurację albo wybierz SQLite."
        return "PostgreSQL jest teraz niedostępny. Wybierz SQLite albo sprawdź konfigurację serwera."


def open_db_engine_switcher(app, current_engine, colors):
        """Otwiera okno dialogowe zmiany silnika bazy danych (PostgreSQL ↔ SQLite)."""
        dialog = tk.Toplevel(app)
        dialog.title("Zmień Silnik Bazy Danych")
        scale = getattr(app, 'ui_scale', 1.0)
        w = max(int(540 * scale), 500)
        h = max(int(500 * scale), 440)
        dialog.geometry(f"{w}x{h}")
        dialog.minsize(460, 360)
        dialog.resizable(True, True)
        dialog.update_idletasks()
        sw = dialog.winfo_screenwidth()
        sh = dialog.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.transient(app)
        dialog.grab_set()
        set_dialog_icon(dialog)

        main_frame = ttk.Frame(dialog, padding="24")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Wybierz silnik bazy danych:",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        engine_var = tk.StringVar(value=current_engine)

        options = [
            ("postgresql", "PostgreSQL + PostGIS", 
             "Pełna funkcjonalność — geometria przestrzenna, wszystkie edytory.\n"
             "Wymaga działającego serwera PostgreSQL z rozszerzeniem PostGIS."),
            ("sqlite", "SQLite (lokalna baza plikowa)",
             "Lokalna baza danych bez serwera. Brak obsługi PostGIS.\n"
             "Edytor działek niedostępny. Działa od razu, bez konfiguracji.")
        ]

        for value, title, desc in options:
            rb_frame = ttk.Frame(main_frame)
            rb_frame.pack(fill=tk.X, pady=8)

            tk.Radiobutton(rb_frame, text=title, variable=engine_var, 
                           value=value, font=("Segoe UI", 12),
                           bg="white", activebackground="white",
                           selectcolor="white").pack(anchor=tk.W)
            ttk.Label(rb_frame, text=desc, font=("Segoe UI", 10),
                     foreground=colors['secondary'], wraplength=440).pack(anchor=tk.W, padx=(28, 0), pady=(4, 0))

        # Status połączenia
        status_var = tk.StringVar(value="")
        pg_available = {"ok": False}
        status_label = ttk.Label(main_frame, textvariable=status_var, 
                                 font=("Segoe UI", 11))

        detail_label = tk.Text(main_frame, height=4, wrap=tk.WORD, font=("Consolas", 9),
                               bg="#fef3c7", fg="#92400e", relief="flat", highlightthickness=0,
                               state="disabled")

        install_pg_button = ttk.Button(
                main_frame,
                text="Zainstaluj PostgreSQL + PostGIS",
                command=lambda: _run_edb_installer(dialog),
                style="Primary.TButton",
        )

        def check_selected():
            detail_label.pack_forget()
            install_pg_button.pack_forget()
            detail_label.configure(state="normal")
            detail_label.delete("1.0", tk.END)
            detail_label.configure(state="disabled")
            selected = engine_var.get()
            if selected == "sqlite":
                pg_available["ok"] = True
                status_var.set("✅ SQLite — gotowy do użycia (bez serwera)")
                status_label.config(foreground=colors['success'])
            else:
                # Sprawdź połączenie z PostgreSQL
                try:
                    from launcher.db.engine import PostgreSQLEngine
                    pg = PostgreSQLEngine()
                    ok, msg = pg.check_connection()
                    if ok:
                        pg_available["ok"] = True
                        status_var.set(f"✅ {msg}")
                        status_label.config(foreground=colors['success'])
                    else:
                        pg_available["ok"] = False
                        status_var.set("⚠️ PostgreSQL — niedostępny")
                        status_label.config(foreground="#d97706")
                        detail_label.configure(state="normal")
                        detail_label.delete("1.0", tk.END)
                        detail_label.insert("1.0", _friendly_postgres_status(msg))
                        detail_label.configure(state="disabled")
                        detail_label.pack(fill=tk.X, pady=(4, 0))
                        install_pg_button.pack(anchor=tk.W, pady=(8, 0))
                except Exception as e:
                    pg_available["ok"] = False
                    status_var.set("⚠️ PostgreSQL — niedostępny")
                    status_label.config(foreground="#d97706")
                    detail_label.configure(state="normal")
                    detail_label.delete("1.0", tk.END)
                    detail_label.insert("1.0", _friendly_postgres_status(str(e)))
                    detail_label.configure(state="disabled")
                    detail_label.pack(fill=tk.X, pady=(4, 0))
                    install_pg_button.pack(anchor=tk.W, pady=(8, 0))

        engine_var.trace("w", lambda *_: check_selected())
        status_label.pack(anchor=tk.W, pady=(10, 0))
        check_selected()

        def apply_change():
            selected = engine_var.get()
            if selected == current_engine:
                messagebox.showinfo("Bez zmian", "Silnik bazy danych nie został zmieniony.")
                dialog.destroy()
                return

            if selected == "postgresql" and not pg_available["ok"]:
                if messagebox.askyesno(
                    "PostgreSQL niedostępny",
                    "Nie można przełączyć na PostgreSQL, bo serwer nie odpowiada.\n\n"
                    "Czy chcesz teraz uruchomić graficzny instalator PostgreSQL + PostGIS?",
                    parent=dialog,
                ):
                    _run_edb_installer(dialog)
                return

            if not messagebox.askyesno("Potwierdź zmianę",
                f"Zmieniasz silnik z '{current_engine}' na '{selected}'.\n\n"
                "⚠️ Ta zmiana wymaga:\n"
                "1. Zatrzymania serwera backend (jeśli działa)\n"
                "2. Restartu aplikacji\n\n"
                "Czy chcesz kontynuować?"):
                return

            try:
                switch_engine(selected)
                messagebox.showinfo("Sukces", 
                    f"✅ Silnik zmieniony na '{selected}'.\n\n"
                    "Zrestartuj aplikację, aby zastosować zmiany.")
                dialog.destroy()
                # Zaproponuj restart
                if messagebox.askyesno("Restart", "Czy chcesz teraz zrestartować Centrum Zarządzania?"):
                    app.restart_application()
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie udało się zmienić silnika: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(btn_frame, text="✅ Zastosuj i zamknij", 
                  command=apply_change, style="Success.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Anuluj", 
                  command=dialog.destroy, style="Secondary.TButton").pack(side=tk.RIGHT, padx=5)
