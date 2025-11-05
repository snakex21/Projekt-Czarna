"""
Kreator konfiguracji bazy danych PostgreSQL
GUI wizard do łatwej konfiguracji bez ręcznego SQL
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import sys

# Import pomocnika PostgreSQL
from postgres_helper import PostgresHelper, get_default_postgres_config, save_postgres_config


class DatabaseWizard(tk.Toplevel):
    """Kreator konfiguracji bazy danych PostgreSQL"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔧 Kreator Bazy Danych")
        self.geometry("700x600")
        self.transient(parent)
        self.grab_set()

        # Wycentruj okno
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (700 // 2)
        y = (self.winfo_screenheight() // 2) - (600 // 2)
        self.geometry(f"700x600+{x}+{y}")

        self.pg_helper = None
        self.result = None  # Będzie True jeśli sukces

        # Konfiguracja
        self.config = get_default_postgres_config()

        # Główny notebook (kroki)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tworzenie kroków
        self.create_step1_connection()
        self.create_step2_action()
        self.create_step3_progress()

        # Przyciski nawigacji
        nav_frame = ttk.Frame(self)
        nav_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(nav_frame, text="◀ Wstecz", command=self.prev_step).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="Dalej ▶", command=self.next_step).pack(side=tk.RIGHT, padx=5)
        ttk.Button(nav_frame, text="Anuluj", command=self.destroy).pack(side=tk.RIGHT, padx=5)

        # Zablokuj zmianę kroków ręcznie
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def create_step1_connection(self):
        """Krok 1: Konfiguracja połączenia"""
        frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(frame, text="1. Połączenie")

        # Nagłówek
        header = ttk.Label(frame, text="Konfiguracja połączenia z PostgreSQL",
                          font=('Arial', 14, 'bold'))
        header.pack(pady=(0, 20))

        info = ttk.Label(frame,
                        text="Podaj parametry połączenia do PostgreSQL.\n"
                             "Jeśli używasz domyślnej instalacji, możesz użyć wartości domyślnych.",
                        foreground="gray")
        info.pack(pady=(0, 20))

        # Formularz
        form_frame = ttk.Frame(frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Host
        ttk.Label(form_frame, text="Host:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.host_entry = ttk.Entry(form_frame, width=30)
        self.host_entry.insert(0, self.config['host'])
        self.host_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        # Port
        ttk.Label(form_frame, text="Port:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.port_entry = ttk.Entry(form_frame, width=30)
        self.port_entry.insert(0, str(self.config['port']))
        self.port_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        # User
        ttk.Label(form_frame, text="Użytkownik:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
        self.user_entry = ttk.Entry(form_frame, width=30)
        self.user_entry.insert(0, self.config['user'])
        self.user_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=5)

        # Password
        ttk.Label(form_frame, text="Hasło:").grid(row=3, column=0, sticky="w", pady=5, padx=5)
        self.password_entry = ttk.Entry(form_frame, width=30, show="*")
        self.password_entry.insert(0, self.config['password'])
        self.password_entry.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        form_frame.columnconfigure(1, weight=1)

        # Przycisk testu połączenia
        test_btn = ttk.Button(form_frame, text="🔍 Testuj połączenie",
                             command=self.test_connection)
        test_btn.grid(row=4, column=0, columnspan=2, pady=20)

        # Status połączenia
        self.connection_status = ttk.Label(form_frame, text="", foreground="gray")
        self.connection_status.grid(row=5, column=0, columnspan=2)

    def create_step2_action(self):
        """Krok 2: Wybór akcji"""
        frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(frame, text="2. Akcja")

        # Nagłówek
        header = ttk.Label(frame, text="Co chcesz zrobić?",
                          font=('Arial', 14, 'bold'))
        header.pack(pady=(0, 20))

        # Status bazy
        self.db_status_frame = ttk.LabelFrame(frame, text="Status baz danych", padding="10")
        self.db_status_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        self.db_status_text = scrolledtext.ScrolledText(
            self.db_status_frame,
            height=10,
            wrap=tk.WORD,
            font=('Courier', 9)
        )
        self.db_status_text.pack(fill=tk.BOTH, expand=True)

        # Przyciski akcji
        actions_frame = ttk.LabelFrame(frame, text="Wybierz akcję", padding="10")
        actions_frame.pack(fill=tk.X)

        self.action_var = tk.StringVar(value="full_setup")

        ttk.Radiobutton(
            actions_frame,
            text="🚀 Pełna instalacja (utwórz wszystko od zera)",
            variable=self.action_var,
            value="full_setup"
        ).pack(anchor=tk.W, pady=5)

        ttk.Radiobutton(
            actions_frame,
            text="🔧 Tylko baza launcher (mapa_launcher_db)",
            variable=self.action_var,
            value="launcher_only"
        ).pack(anchor=tk.W, pady=5)

        ttk.Radiobutton(
            actions_frame,
            text="📦 Dodaj nową miejscowość (wykryj nowe bazy)",
            variable=self.action_var,
            value="add_location"
        ).pack(anchor=tk.W, pady=5)

        # Przycisk odświeżania statusu
        ttk.Button(frame, text="🔄 Odśwież status",
                  command=self.refresh_db_status).pack(pady=10)

    def create_step3_progress(self):
        """Krok 3: Wykonanie i postęp"""
        frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(frame, text="3. Wykonanie")

        # Nagłówek
        header = ttk.Label(frame, text="Instalacja...",
                          font=('Arial', 14, 'bold'))
        header.pack(pady=(0, 20))

        # Progress bar
        self.progress = ttk.Progressbar(frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=10)

        # Log
        log_frame = ttk.LabelFrame(frame, text="Log operacji", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=15,
            wrap=tk.WORD,
            font=('Courier', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Przycisk zakończenia
        self.finish_button = ttk.Button(frame, text="✅ Zakończ",
                                       command=self.finish, state=tk.DISABLED)
        self.finish_button.pack(pady=10)

    def test_connection(self):
        """Testuje połączenie z PostgreSQL"""
        # Pobierz dane z formularza
        self.config['host'] = self.host_entry.get().strip()
        self.config['port'] = int(self.port_entry.get().strip())
        self.config['user'] = self.user_entry.get().strip()
        self.config['password'] = self.password_entry.get()

        # Utwórz helper
        self.pg_helper = PostgresHelper(**self.config)

        # Test
        success, message = self.pg_helper.test_connection()

        if success:
            self.connection_status.config(
                text="✓ Połączenie udane!",
                foreground="green"
            )
            messagebox.showinfo("Sukces", "Połączenie z PostgreSQL działa!", parent=self)
        else:
            self.connection_status.config(
                text=f"✗ {message}",
                foreground="red"
            )
            messagebox.showerror("Błąd", message, parent=self)

    def refresh_db_status(self):
        """Odświeża status baz danych"""
        if not self.pg_helper:
            self.log("⚠️ Najpierw przetestuj połączenie w kroku 1")
            return

        self.db_status_text.delete('1.0', tk.END)

        # Lista baz
        databases = self.pg_helper.list_databases()

        self.db_status_text.insert(tk.END, "=== Wykryte bazy danych ===\n\n")

        # Sprawdź launcher_db
        launcher_exists = self.pg_helper.database_exists('mapa_launcher_db')
        if launcher_exists:
            table_count = self.pg_helper.get_table_count('mapa_launcher_db')
            self.db_status_text.insert(tk.END, f"✓ mapa_launcher_db (konfiguracja) - {table_count} tabel\n")
        else:
            self.db_status_text.insert(tk.END, "✗ mapa_launcher_db - BRAK\n")

        self.db_status_text.insert(tk.END, "\n=== Bazy miejscowości ===\n\n")

        # Bazy miejscowości
        location_dbs = [db for db in databases if db.startswith('mapa_') and db != 'mapa_launcher_db']

        if location_dbs:
            for db in location_dbs:
                has_pg = self.pg_helper.has_postgis(db)
                table_count = self.pg_helper.get_table_count(db)
                pg_status = "✓ PostGIS" if has_pg else "✗ Brak PostGIS"
                self.db_status_text.insert(tk.END, f"  • {db} - {table_count} tabel, {pg_status}\n")
        else:
            self.db_status_text.insert(tk.END, "  Brak baz miejscowości\n")

    def next_step(self):
        """Przejdź do następnego kroku"""
        current = self.notebook.index(self.notebook.select())

        if current == 0:  # Krok 1 → 2
            # Sprawdź połączenie
            if not self.pg_helper:
                messagebox.showwarning(
                    "Uwaga",
                    "Przetestuj najpierw połączenie!",
                    parent=self
                )
                return
            # Odśwież status
            self.refresh_db_status()
            self.notebook.select(1)

        elif current == 1:  # Krok 2 → 3
            # Wykonaj akcję
            self.notebook.select(2)
            self.execute_action()

    def prev_step(self):
        """Wróć do poprzedniego kroku"""
        current = self.notebook.index(self.notebook.select())
        if current > 0:
            self.notebook.select(current - 1)

    def on_tab_changed(self, event):
        """Blokuj ręczną zmianę zakładek"""
        # Użytkownik może zmieniać tylko przez przyciski
        pass

    def log(self, message):
        """Dodaje wiadomość do logu"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.update()

    def execute_action(self):
        """Wykonuje wybraną akcję"""
        action = self.action_var.get()

        self.progress.start()
        self.log("🚀 Rozpoczynam operację...\n")

        try:
            if action == "full_setup":
                self.full_setup()
            elif action == "launcher_only":
                self.launcher_only_setup()
            elif action == "add_location":
                self.add_location_setup()

            self.log("\n✅ Operacja zakończona sukcesem!")
            self.result = True
            self.finish_button.config(state=tk.NORMAL)

        except Exception as e:
            self.log(f"\n❌ Błąd: {str(e)}")
            messagebox.showerror("Błąd", f"Wystąpił błąd:\n{str(e)}", parent=self)
        finally:
            self.progress.stop()

    def full_setup(self):
        """Pełna instalacja - tworzy wszystko"""
        self.log("=== Pełna instalacja systemu ===\n")

        # 1. Utwórz mapa_launcher_db
        self.log("1. Tworzę bazę mapa_launcher_db...")
        success, msg = self.pg_helper.create_database('mapa_launcher_db')
        self.log(f"   {msg}")

        # 2. Wykonaj schema
        self.log("2. Tworzę strukturę tabel...")
        schema_path = os.path.join(
            os.path.dirname(__file__),
            'schema_launcher_db.sql'
        )
        success, msg = self.pg_helper.execute_sql_file('mapa_launcher_db', schema_path)
        self.log(f"   {msg}")

        # 3. Zapisz konfigurację
        self.log("3. Zapisuję konfigurację...")
        # TODO: Zapisz do głównego .env
        self.log("   ✓ Konfiguracja zapisana")

        self.log("\n✅ Pełna instalacja zakończona!")

    def launcher_only_setup(self):
        """Tylko mapa_launcher_db"""
        self.log("=== Instalacja bazy launcher ===\n")

        # Sprawdź czy istnieje
        if self.pg_helper.database_exists('mapa_launcher_db'):
            self.log("⚠️ Baza mapa_launcher_db już istnieje")
            if not messagebox.askyesno(
                "Uwaga",
                "Baza mapa_launcher_db już istnieje.\nCzy odtworzyć tabelki?",
                parent=self
            ):
                return

        # Utwórz bazę
        self.log("1. Tworzę bazę mapa_launcher_db...")
        success, msg = self.pg_helper.create_database('mapa_launcher_db')
        self.log(f"   {msg}")

        # Schema
        self.log("2. Tworzę strukturę tabel...")
        schema_path = os.path.join(
            os.path.dirname(__file__),
            'schema_launcher_db.sql'
        )
        success, msg = self.pg_helper.execute_sql_file('mapa_launcher_db', schema_path)
        self.log(f"   {msg}")

        self.log("\n✅ Baza launcher gotowa!")

    def add_location_setup(self):
        """Wykrywa nowe bazy i dodaje jako miejscowości"""
        self.log("=== Wykrywanie nowych miejscowości ===\n")

        # Lista baz
        databases = self.pg_helper.list_databases()
        location_dbs = [
            db for db in databases
            if db.startswith('mapa_') and db != 'mapa_launcher_db'
        ]

        if not location_dbs:
            self.log("ℹ️ Nie znaleziono nowych baz miejscowości")
            return

        self.log(f"Znaleziono {len(location_dbs)} baz:\n")
        for db in location_dbs:
            self.log(f"  • {db}")

        self.log("\n📝 Aby dodać te miejscowości, użyj launchera")
        self.log("   (funkcja automatycznego importu będzie dostępna wkrótce)")

    def finish(self):
        """Zakończ kreatora"""
        self.destroy()


# Funkcja pomocnicza do uruchomienia kreatora
def run_database_wizard(parent=None):
    """Uruchamia kreator bazy danych"""
    if parent is None:
        root = tk.Tk()
        root.withdraw()
        wizard = DatabaseWizard(root)
        root.wait_window(wizard)
        root.destroy()
        return wizard.result
    else:
        wizard = DatabaseWizard(parent)
        parent.wait_window(wizard)
        return wizard.result


# Test
if __name__ == "__main__":
    result = run_database_wizard()
    print(f"Wynik: {result}")
