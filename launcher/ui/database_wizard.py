"""Kreator zarządzania bazami PostgreSQL launchera."""

import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from ..config.paths import BASE_DIR
from ..db.postgres import (
    get_postgres_config,
    save_postgres_config,
)
from ..db.schemas import LAUNCHER_DB_SCHEMA, LAUNCHER_DROP_TABLES, LOCATION_DB_SCHEMA, LOCATION_DROP_TABLES
from ..services import pg_portable_service, pg_runtime
from ..services.location_service import get_all_locations
from ..services.postgres_adapter_service import (
    test_postgres_connection,
    postgres_database_exists,
    postgres_create_database,
    postgres_enable_postgis,
    postgres_execute_schema,
    postgres_list_databases,
)
from ..services.postgres_migration_service import (
    MigrationOptions,
    PostgresConfig,
    normalize_postgres_config,
    run_postgres_migration_wizard,
)
from ..utils import set_dialog_icon


__all__ = [
    "DatabaseWizard",
    "test_postgres_connection",
    "postgres_database_exists",
    "postgres_create_database",
    "postgres_enable_postgis",
    "postgres_execute_schema",
    "postgres_list_databases",
]


LOCATIONS_DB_INITIALIZED = False


class DatabaseWizard(tk.Toplevel):
    """Narzędzie do zarządzania bazą danych PostgreSQL"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔧 Zarządzanie Bazą Danych")
        set_dialog_icon(self)

        # Ustawienie większego rozmiaru okna z możliwością zmiany rozmiaru
        # Skaluj rozmiar okna wg DPI
        scale = max(0.85, min(float(getattr(parent, 'ui_scale', 1.0) or 1.0), 2.0))
        width = int(800 * scale)
        height = int(800 * scale)
        self.geometry(f"{width}x{height}")
        self.minsize(width, height)
        self.transient(parent)
        # grab_set() usunięte - pozwala na Alt+Tab między oknami

        # Wycentruj
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.result = None
        self.config = get_postgres_config()
        self.connection_tested = False

        # Notebook (kroki)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Kroki
        self.create_step1_connection()
        self.create_step3_action()
        self.create_step4_progress()

        # Zablokuj bezpośrednie przełączanie zakładek - wymuś użycie przycisków nawigacji
        self.last_valid_tab = 0
        self.notebook.bind("<<NotebookTabChanged>>", self.validate_tab_change)

        # Nawigacja
        nav_frame = ttk.Frame(self)
        nav_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(nav_frame, text="◀ Wstecz", command=self.prev_step).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="Dalej ▶", command=self.next_step).pack(side=tk.RIGHT, padx=5)
        ttk.Button(nav_frame, text="Anuluj", command=self.destroy).pack(side=tk.RIGHT, padx=5)

        # Flaga zapobiegająca powtórnemu oferowaniu instalacji portable PG
        # w ramach jednej sesji kreatora (auto_test_connection jest wywoływane
        # na każdym KeyRelease / FocusOut - nie chcemy spamować dialogami).
        self._portable_pg_offered = False
        self._portable_pg_install_in_progress = False

        # Sprawdź asynchronicznie (po 500 ms) czy system ma PostgreSQL.
        # Pozwalamy UI się w pełni zinicjalizować zanim odpytamy system.
        self.after(500, self._check_portable_pg_on_startup)

    def create_step1_connection(self):
        """Krok 1: Połączenie"""
        frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(frame, text="1. Połączenie")

        ttk.Label(frame, text="Konfiguracja PostgreSQL", font=('Arial', 16, 'bold')).pack(pady=(0, 10))

        # Ostrzeżenie o braku PostgreSQL - ukryte domyślnie, pokazywane
        # przez _check_portable_pg_on_startup() gdy brak systemowego PG.
        self._pg_missing_label = ttk.Label(
            frame,
            text=(
                "⚠️ Brak PostgreSQL — pobierz portable lub zainstaluj systemowe.\n"
                "Wpisz dowolne parametry połączenia i kliknij 'Testuj' — "
                "po nieudanym teście kreator zaproponuje pobranie portable PG."
            ),
            foreground="#856404",
            background="#fff3cd",
            padding=10,
            justify=tk.LEFT,
        )
        # Początkowo ukryty - ``pack_forget()`` przywraca po ``pack()``.
        # Trzymamy referencję w self, żeby móc go pokazać / ukryć.

        # Sekcja zarządzania portable PG (dodana w 1.1.1).
        # Zawsze widoczna w kroku 1 — pokazuje status (zainstalowany / brak)
        # oraz przycisk do odinstalowania. User może w każdej chwili
        # skasować portable PG, pliki będą w katalogu projektu
        # (`<root>/postgres/`).
        self._portable_pg_status_frame = ttk.LabelFrame(
            frame,
            text="Portable PostgreSQL",
            padding=(10, 5),
        )
        self._portable_pg_status_frame.pack(fill=tk.X, pady=(10, 5))

        # Label ze statusem i ścieżką instalacji.
        self._portable_pg_path_label = ttk.Label(
            self._portable_pg_status_frame,
            text="Sprawdzanie…",
            justify=tk.LEFT,
            wraplength=480,
        )
        self._portable_pg_path_label.pack(side=tk.TOP, anchor=tk.W, fill=tk.X)

        # Przycisk odinstalowania (pokazywany tylko gdy portable PG istnieje).
        self._uninstall_portable_pg_button = ttk.Button(
            self._portable_pg_status_frame,
            text="🗑 Odinstaluj portable PG",
            command=self._uninstall_portable_pg,
        )
        # Nie pakujemy tutaj — pokaże go _refresh_portable_pg_status()
        # jeśli portable PG jest zainstalowany.

        # Informacja o wymaganiach
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill=tk.X, pady=(0, 20))

        info_text = ttk.Label(info_frame,
                             text="⚠️ Program wymaga PostgreSQL do działania\n\n"
                                  "Podaj parametry połączenia do serwera PostgreSQL.\n"
                                  "Po udanym połączeniu będziesz mógł wybrać źródło danych:\n"
                                  "• Import z pliku ZIP (backup)\n"
                                  "• Rozpocznij z szablonem Czarna",
                             foreground="gray", justify=tk.LEFT)
        info_text.pack(pady=(0, 10))

        form = ttk.Frame(frame)
        form.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form, text="Host:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.host_entry = ttk.Entry(form, width=30)
        self.host_entry.insert(0, self.config['host'])
        self.host_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(form, text="Port:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.port_entry = ttk.Entry(form, width=30)
        self.port_entry.insert(0, str(self.config['port']))
        self.port_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(form, text="Użytkownik:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
        self.user_entry = ttk.Entry(form, width=30)
        self.user_entry.insert(0, self.config['user'])
        self.user_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(form, text="Hasło:").grid(row=3, column=0, sticky="w", pady=5, padx=5)
        self.password_entry = ttk.Entry(form, width=30, show="*")
        self.password_entry.insert(0, self.config['password'])
        self.password_entry.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        # Automatyczne testowanie po wpisaniu hasła
        self.password_entry.bind('<KeyRelease>', self.auto_test_connection)
        self.password_entry.bind('<FocusOut>', self.auto_test_connection)

        form.columnconfigure(1, weight=1)

        # Status połączenia z większą czcionką
        self.connection_status = ttk.Label(form, text="⚠️ Wpisz hasło do PostgreSQL",
                                          foreground="#856404", font=('Arial', 12, 'bold'))
        self.connection_status.grid(row=4, column=0, columnspan=2, pady=20)

        # Test początkowy jeśli hasło już istnieje
        if self.config['password']:
            self.after(100, self.test_connection)

    def create_step3_action(self):
        """Krok 2: Akcja"""
        frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(frame, text="2. Akcja")

        ttk.Label(frame, text="Co chcesz zrobić?", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Status
        self.db_status_frame = ttk.LabelFrame(frame, text="Status", padding="10")
        self.db_status_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        self.db_status_text = scrolledtext.ScrolledText(self.db_status_frame, height=8, wrap=tk.WORD, font=('Courier', 9))
        self.db_status_text.pack(fill=tk.BOTH, expand=True)

        # Akcje
        actions_frame = ttk.LabelFrame(frame, text="Wybierz", padding="10")
        actions_frame.pack(fill=tk.X)

        # Domyślna (bezpieczna) akcja: pełna migracja JSON -> PostgreSQL dla wybranej miejscowości
        self.action_var = tk.StringVar(value="migrate_to_postgresql")

        safe_frame = ttk.Frame(actions_frame)
        safe_frame.pack(fill=tk.X, pady=(5, 2))
        ttk.Radiobutton(
            safe_frame,
            text="🚀 Przygotuj i zmigruj dane do PostgreSQL (zalecane)",
            variable=self.action_var,
            value="migrate_to_postgresql",
        ).pack(anchor=tk.W, pady=2, padx=10)

        ttk.Label(
            safe_frame,
            text=(
                "    Tworzy bazę miejscowości, włącza PostGIS, tworzy schemat, "
                "importuje dane z JSON, weryfikuje liczniki\n"
                "    i dopiero po pełnym sukcesie przełącza backend na PostgreSQL."
            ),
            foreground="gray",
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 4))

        ttk.Separator(actions_frame, orient='horizontal').pack(fill='x', pady=10)

        # === Sekcja "zaawansowane / destrukcyjne" (ukryta domyślnie) ===
        self.risk_ack_var = tk.BooleanVar(value=False)
        self._destructive_widgets: list[ttk.Radiobutton] = []

        advanced_frame = ttk.LabelFrame(
            actions_frame,
            text="⚠️ Operacje destrukcyjne (zaawansowane — domyślnie ukryte)",
            padding="10",
        )
        advanced_frame.pack(fill=tk.X, pady=(5, 2))

        risk_check = ttk.Checkbutton(
            advanced_frame,
            text="Rozumiem ryzyko utraty danych (odblokowuje destrukcyjne akcje)",
            variable=self.risk_ack_var,
            command=self._on_risk_ack_toggle,
        )
        risk_check.pack(anchor=tk.W, pady=(0, 6))

        # Opcje dla bazy launcher (mapa_launcher_db)
        ttk.Label(advanced_frame, text="Baza launcher:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(5, 2))
        self._destructive_widgets.append(ttk.Radiobutton(
            advanced_frame,
            text="❌ Usuń tabele launcher (DROP TABLES)",
            variable=self.action_var,
            value="drop_launcher_tables",
        ))
        self._destructive_widgets[-1].pack(anchor=tk.W, pady=2, padx=10)

        self._destructive_widgets.append(ttk.Radiobutton(
            advanced_frame,
            text="♻️ Odtwórz tabele launcher (DROP + CREATE)",
            variable=self.action_var,
            value="recreate_launcher_tables",
        ))
        self._destructive_widgets[-1].pack(anchor=tk.W, pady=2, padx=10)

        ttk.Separator(advanced_frame, orient='horizontal').pack(fill='x', pady=8)

        # Opcje dla bazy miejscowości
        ttk.Label(advanced_frame, text="Baza miejscowości:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(5, 2))
        self._destructive_widgets.append(ttk.Radiobutton(
            advanced_frame,
            text="❌ Usuń tabele miejscowości (DROP TABLES)",
            variable=self.action_var,
            value="drop_location_tables",
        ))
        self._destructive_widgets[-1].pack(anchor=tk.W, pady=2, padx=10)

        self._destructive_widgets.append(ttk.Radiobutton(
            advanced_frame,
            text="♻️ Odtwórz tabele miejscowości (DROP + CREATE)",
            variable=self.action_var,
            value="recreate_location_tables",
        ))
        self._destructive_widgets[-1].pack(anchor=tk.W, pady=2, padx=10)

        # Dropdown z wyborem miejscowości (potrzebny dla destrukcyjnych i dla migracji)
        location_frame = ttk.Frame(advanced_frame)
        location_frame.pack(anchor=tk.W, pady=5, padx=20)

        ttk.Label(location_frame, text="Wybierz miejscowość:").pack(side=tk.LEFT, padx=(0, 10))

        self.location_var = tk.StringVar()
        self.location_combo = ttk.Combobox(location_frame, textvariable=self.location_var, state="readonly", width=30)
        self.location_combo.pack(side=tk.LEFT)

        # Wypełnij listę miejscowości
        self.refresh_locations_list()

        # Domyślnie destrukcyjne akcje zablokowane (wariant A)
        self._on_risk_ack_toggle()

        ttk.Button(frame, text="🔄  Odśwież status", command=self.refresh_status).pack(pady=10)

    def create_step4_progress(self):
        """Krok 3: Wykonanie"""
        frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(frame, text="3. Wykonanie")

        ttk.Label(frame, text="Instalacja...", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        self.progress = ttk.Progressbar(frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=10)

        log_frame = ttk.LabelFrame(frame, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD, font=('Courier', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.finish_button = ttk.Button(frame, text="✅ Zakończ", command=self.finish, state=tk.DISABLED)
        self.finish_button.pack(pady=10)

    def auto_test_connection(self, event=None):
        """Automatyczne testowanie połączenia po wpisaniu hasła"""
        password = self.password_entry.get()

        # Testuj tylko jeśli hasło ma przynajmniej 1 znak
        if len(password) > 0:
            # Anuluj poprzedni timer jeśli istnieje
            if hasattr(self, '_test_timer'):
                self.after_cancel(self._test_timer)

            # Ustaw nowy timer - test po 1 sekundzie od ostatniego znaku
            self._test_timer = self.after(1000, self.test_connection)

    def test_connection(self):
        """Test połączenia z PostgreSQL"""
        self.connection_status.config(text="🔄  Testowanie połączenia...", foreground="blue")
        self.update_idletasks()

        self.config['host'] = self.host_entry.get().strip()
        self.config['port'] = int(self.port_entry.get().strip())
        self.config['user'] = self.user_entry.get().strip()
        self.config['password'] = self.password_entry.get()

        success, msg = test_postgres_connection(**self.config)

        if success:
            # Zielona fajka - połączenie OK
            self.connection_status.config(text="✓ Połączenie Udane!", foreground="green")

            # Zapisz hasło do .postgres.env
            save_postgres_config(self.config['host'], self.config['port'],
                               self.config['user'], self.config['password'])

            # Włącz możliwość przejścia dalej
            self.connection_tested = True
        else:
            # Czerwony krzyżyk - błąd
            self.connection_status.config(text=f"✗ Błąd: {msg}", foreground="red")
            self.connection_tested = False

            # Gdy brak PG w systemie i nie udało się połączyć - zaproponuj
            # pobranie portable PostgreSQL (tylko raz na sesję, żeby nie
            # spamować dialogami przy każdym KeyRelease / FocusOut).
            if not self._portable_pg_offered and not self._portable_pg_install_in_progress:
                self._offer_portable_pg_install()

    def auto_migrate_data(self, backup_folder):
        """DEPRECATED: stary helper do automatycznej migracji. Logika przeniesiona
        do ``launcher.services.postgres_migration_service.run_postgres_migration_wizard``
        i wywoływana z poziomu kreatora akcją ``migrate_to_postgresql``.

        Zachowany jako thin wrapper, żeby nie łamać ewentualnych wywołań
        z zewnętrznych skryptów — loguje tylko ostrzeżenie.
        """
        try:
            print(
                "⚠️ DatabaseWizard.auto_migrate_data jest deprecated. "
                "Użyj akcji 'Przygotuj i zmigruj dane do PostgreSQL' w kreatorze."
            )
        except Exception:
            pass

    def refresh_status(self):
        """Odśwież status baz"""
        self.db_status_text.delete('1.0', tk.END)

        databases = postgres_list_databases(**self.config)

        self.db_status_text.insert(tk.END, "=== Bazy danych ===\n\n")

        launcher_exists = postgres_database_exists(**self.config, db_name='mapa_launcher_db')
        if launcher_exists:
            self.db_status_text.insert(tk.END, "✓ mapa_launcher_db (konfiguracja)\n")
        else:
            self.db_status_text.insert(tk.END, "✗ mapa_launcher_db - BRAK\n")

        self.db_status_text.insert(tk.END, "\n=== Miejscowości ===\n\n")

        location_dbs = [db for db in databases if db.startswith('mapa_') and db != 'mapa_launcher_db']
        if location_dbs:
            for db in location_dbs:
                self.db_status_text.insert(tk.END, f"  • {db}\n")
        else:
            self.db_status_text.insert(tk.END, "  Brak\n")

    def refresh_locations_list(self):
        """Odśwież listę miejscowości w dropdownie"""
        try:
            locations = get_all_locations()
            if locations:
                # Format: (id, name, full_name, powiat, region, active, homepage_template, year, century,
                #          homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
                #          postgres_db_name, history_photos)
                location_items = []
                for loc in locations:
                    loc_id, name = loc[0], loc[1]
                    postgres_db_name = loc[13] if len(loc) > 13 and loc[13] else ""  # postgres_db_name jest na indeksie 13

                    # Pokaż nazwę miejscowości i nazwę bazy
                    if postgres_db_name:
                        display = f"{name} → {postgres_db_name}"
                        location_items.append((display, postgres_db_name))
                    else:
                        display = f"{name} (brak bazy)"
                        location_items.append((display, ""))

                # Ustaw wartości w combobox
                self.location_combo['values'] = [item[0] for item in location_items]
                self.location_data = location_items  # Przechowuj pełne dane

                if location_items:
                    self.location_combo.current(0)
            else:
                self.location_combo['values'] = ["Brak miejscowości"]
                self.location_data = []
        except Exception as e:
            print(f"⚠️ Błąd odświeżania listy miejscowości: {e}")
            import traceback
            traceback.print_exc()
            self.location_combo['values'] = ["Błąd wczytywania"]
            self.location_data = []

    def validate_tab_change(self, event=None):
        """Waliduje zmianę zakładki - blokuje bezpośrednie klikanie na zaawansowane kroki"""
        current = self.notebook.index(self.notebook.select())

        # Zezwól tylko na powrót do poprzednich kroków lub pozostanie na obecnym
        if current <= self.last_valid_tab:
            self.last_valid_tab = current
            return

        # Próba przeskoczenia do przodu - zablokuj i powiadom
        self.notebook.select(self.last_valid_tab)
        messagebox.showinfo(
            "Informacja",
            "Użyj przycisków nawigacji 'Dalej ▶' i '◀ Wstecz' aby przechodzić między krokami.\n\n"
            "Bezpośrednie klikanie w zakładki jest zablokowane dla bezpieczeństwa.",
            parent=self
        )

    def next_step(self):
        """Następny krok"""
        current = self.notebook.index(self.notebook.select())

        if current == 0:
            # Krok 1 -> 2: Sprawdź czy połączenie zostało przetestowane
            if not self.connection_tested:
                messagebox.showwarning("Uwaga", "Przetestuj połączenie z PostgreSQL!", parent=self)
                return
            # Przejdź do kroku 2 (Akcja) i odśwież status
            self.refresh_status()
            self.last_valid_tab = 1
            self.notebook.select(1)

        elif current == 1:
            # Krok 2 -> 3: Walidacja przed wykonaniem akcji
            action = self.action_var.get()

            # Sprawdź czy akcja została wybrana
            if not action:
                messagebox.showwarning("Uwaga", "Wybierz akcję do wykonania!", parent=self)
                return

            # Akcje destrukcyjne wymagają potwierdzenia ryzyka (wariant A)
            destructive_actions = {
                "drop_launcher_tables",
                "recreate_launcher_tables",
                "drop_location_tables",
                "recreate_location_tables",
                "drop_location_database",
            }
            if action in destructive_actions and not self.risk_ack_var.get():
                messagebox.showwarning(
                    "Akcja destrukcyjna zablokowana",
                    "Ta operacja usuwa dane i jest domyślnie ukryta.\n\n"
                    "Zaznacz checkbox 'Rozumiem ryzyko utraty danych' "
                    "w sekcji 'Operacje destrukcyjne (zaawansowane)', aby ją odblokować.",
                    parent=self,
                )
                return

            # Migracja: wymaga wybranej miejscowości
            if action == "migrate_to_postgresql":
                try:
                    self._get_selected_location_name()
                except Exception as exc:
                    messagebox.showwarning(
                        "Uwaga",
                        f"Wybierz miejscowość z listy: {exc}",
                        parent=self,
                    )
                    return

            # Jeśli akcja dotyczy miejscowości, sprawdź czy wybrano miejscowość z bazą
            if action in ["drop_location_tables", "recreate_location_tables"]:
                selected_location = self.location_var.get()

                # Sprawdź czy w ogóle wybrano miejscowość
                if not selected_location or selected_location == "Brak miejscowości" or selected_location == "Błąd wczytywania":
                    messagebox.showwarning("Uwaga", "Wybierz miejscowość z listy!", parent=self)
                    return

                # Sprawdź czy miejscowość ma przypisaną bazę danych
                if "(brak bazy)" in selected_location:
                    messagebox.showwarning("Uwaga",
                                         "Wybrana miejscowość nie ma przypisanej bazy danych!\n\n"
                                         "Najpierw utwórz bazę dla tej miejscowości.",
                                         parent=self)
                    return

            # Przygotuj komunikat potwierdzający
            action_messages = {
                "migrate_to_postgresql": (
                    "🚀 Przeprowadzić pełną migrację danych do PostgreSQL?\n\n"
                    f"Miejscowość: {self.location_var.get()}\n\n"
                    "Zostaną wykonane kroki:\n"
                    "  1. Połączenie z serwerem PostgreSQL\n"
                    "  2. Utworzenie bazy miejscowości (jeśli brak)\n"
                    "  3. Włączenie PostGIS\n"
                    "  4. Utworzenie schematu tabel\n"
                    "  5. Import danych z JSON\n"
                    "  6. Weryfikacja liczników\n"
                    "  7. Przełączenie backendu na PostgreSQL\n\n"
                    "W razie błędu któregokolwiek kroku system pozostanie na SQLite."
                ),
                "drop_launcher_tables": "❌ Usunąć tabele launcher (DROP TABLES)?\n\nUWAGA: Stracisz wszystkie dane konfiguracyjne!",
                "recreate_launcher_tables": "♻️ Odtworzyć tabele launcher (DROP + CREATE)?\n\nUWAGA: Obecne dane zostaną usunięte!",
                "drop_location_tables": f"❌ Usunąć tabele miejscowości?\n\nMiejscowość: {self.location_var.get()}\n\nUWAGA: Stracisz wszystkie dane tej miejscowości!",
                "recreate_location_tables": f"♻️ Odtworzyć tabele miejscowości?\n\nMiejscowość: {self.location_var.get()}\n\nUWAGA: Obecne dane zostaną usunięte!"
            }

            confirm_msg = action_messages.get(action, "Wykonać wybraną akcję?")

            # Potwierdź akcję
            confirm = messagebox.askyesno(
                "Potwierdzenie",
                confirm_msg + "\n\nCzy kontynuować?",
                parent=self,
                icon='warning'
            )

            if not confirm:
                return

            # Przejdź do kroku wykonania i uruchom akcję
            self.last_valid_tab = 2
            self.notebook.select(2)
            self.execute_action()

    def prev_step(self):
        """Poprzedni krok"""
        current = self.notebook.index(self.notebook.select())
        if current > 0:
            self.notebook.select(current - 1)

    def log(self, msg):
        """Log"""
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.update()

    def _on_risk_ack_toggle(self):
        """Odblokowuje / blokuje destrukcyjne radiobuttony (wariant A)."""
        state = tk.NORMAL if self.risk_ack_var.get() else tk.DISABLED
        for widget in getattr(self, "_destructive_widgets", []):
            try:
                widget.configure(state=state)
            except Exception:
                pass
        # Gdy destrukcyjne akcje są zablokowane, upewnij się, że wybrana jest bezpieczna akcja
        if not self.risk_ack_var.get():
            current = self.action_var.get()
            if current in {
                "drop_launcher_tables",
                "recreate_launcher_tables",
                "drop_location_tables",
                "recreate_location_tables",
                "drop_location_database",
            }:
                self.action_var.set("migrate_to_postgresql")

    # =========================================================================
    # Sekcja: integracja z portable PostgreSQL (Etap 3 P2.1)
    # =========================================================================

    def _check_portable_pg_on_startup(self):
        """Sprawdza przy starcie kreatora czy system ma PostgreSQL.

        Logika:
            * Jeśli portable PG jest już zainstalowany — nic nie rób.
            * Jeśli systemowy ``pg_ctl`` jest w PATH / standardowej
              lokalizacji — też nic nie rób (zakładamy, że user
              świadomie używa własnego serwera).
            * W przeciwnym razie pokaż ostrzeżenie w kroku 1
              ("⚠️ Brak PostgreSQL — pobierz portable lub zainstaluj
              systemowe"), żeby user wiedział, że test połączenia
              może zakończyć się propozycją instalacji.

        Od wersji 1.1.1 dodatkowo:
            * Odświeża sekcję "Portable PostgreSQL" (pokazuje ścieżkę
              instalacji i przycisk "Odinstaluj" gdy zainstalowany).
        """
        try:
            self._refresh_portable_pg_status()
        except Exception:
            # _refresh_portable_pg_status może rzucić w środowisku testowym.
            pass

        try:
            if pg_portable_service.portable_pg_installed():
                return
            if pg_portable_service.detect_system_pg() is not None:
                return
        except Exception:
            # Detekcja może rzucić wyjątek (np. w środowisku testowym
            # bez tk / z niestandowym PATH). Nie blokujemy UI.
            return

        # Pokaż ostrzeżenie w kroku 1 (jeśli label istnieje).
        label = getattr(self, "_pg_missing_label", None)
        if label is not None:
            try:
                label.pack(fill=tk.X, pady=(0, 10), before=self._pg_missing_label.master.winfo_children()[2])
            except Exception:
                # Fallback - pokaż na górze frame'a.
                try:
                    label.pack(fill=tk.X, pady=(0, 10))
                except Exception:
                    pass

    def _refresh_portable_pg_status(self) -> None:
        """Odświeża sekcję "Portable PostgreSQL" w kroku 1.

        Pokazuje:
            * ✅ Zainstalowany: pełna ścieżka + przycisk "Odinstaluj".
            * 📦 Niezainstalowany: ścieżka docelowa (gdzie BY BYŁ zainstalowany)
              i komunikat, że nic nie jest zainstalowane.

        Bezpiecznie obsługuje środowisko testowe (gdy ``_portable_pg_path_label``
        nie istnieje).
        """
        label = getattr(self, "_portable_pg_path_label", None)
        button = getattr(self, "_uninstall_portable_pg_button", None)
        if label is None or button is None:
            return

        try:
            install_dir = pg_portable_service.get_pg_install_dir()
            installed = pg_portable_service.portable_pg_installed(install_dir)
        except Exception as exc:
            label.config(text=f"❌ Błąd sprawdzania portable PG: {exc}")
            try:
                button.pack_forget()
            except Exception:
                pass
            return

        if installed:
            # ✅ Zainstalowany
            label.config(
                text=(
                    f"✅ Portable PostgreSQL jest zainstalowany.\n"
                    f"📂 Ścieżka: {install_dir}\n"
                    f"Kliknij 'Odinstaluj' aby trwale usunąć pliki."
                ),
                foreground="#155724",
            )
            try:
                button.pack(side=tk.BOTTOM, anchor=tk.E, pady=(5, 0))
                button.config(state=tk.NORMAL)
            except Exception:
                pass
        else:
            # 📦 Niezainstalowany
            label.config(
                text=(
                    f"📦 Portable PostgreSQL nie jest zainstalowany.\n"
                    f"📂 Zostanie zainstalowany w: {install_dir}\n"
                    f"Kliknij 'Testuj połączenie' — po nieudanym teście kreator "
                    f"zaproponuje pobranie i instalację."
                ),
                foreground="#0c5460",
            )
            try:
                button.pack_forget()
            except Exception:
                pass

    def _uninstall_portable_pg(self) -> None:
        """Obsługuje kliknięcie przycisku "Odinstaluj portable PG".

        Procedura:
            1. Pokazuje messagebox z potwierdzeniem (trwałe usunięcie).
            2. Wywołuje :func:`pg_portable_service.uninstall_portable_pg`
               z timeoutem 10s na graceful stop serwera.
            3. Pokazuje wynik (sukces / błąd / liczba usuniętych plików).
            4. Odświeża status (sekcja Portable PG).
        """
        if getattr(self, "_portable_pg_uninstall_in_progress", False):
            return
        self._portable_pg_uninstall_in_progress = True

        try:
            install_dir = pg_portable_service.get_pg_install_dir()
            try:
                answer = messagebox.askyesno(
                    "Odinstalowanie portable PostgreSQL",
                    f"Czy na pewno chcesz trwale usunąć portable PostgreSQL?\n\n"
                    f"Lokalizacja:\n{install_dir}\n\n"
                    f"⚠️ Tej operacji nie można cofnąć. Wszystkie dane (initdb, "
                    f"logi, PID) zostaną usunięte.\n\n"
                    f"Możesz zainstalować ponownie w dowolnym momencie.",
                    parent=self,
                )
            except Exception:
                return
            finally:
                self._portable_pg_uninstall_in_progress = False

            if not answer:
                return

            # Odinstaluj.
            result = pg_portable_service.uninstall_portable_pg(
                install_dir=install_dir,
                stop_server=True,
                timeout=10.0,
            )

            # Pokaż wynik.
            try:
                if result.success:
                    extra = ""
                    if result.server_was_running:
                        extra = " (serwer został zatrzymany)"
                    messagebox.showinfo(
                        "Sukces",
                        f"✅ Portable PostgreSQL został odinstalowany.\n"
                        f"Usunięto {result.removed_files} plików{extra}.",
                        parent=self,
                    )
                else:
                    messagebox.showerror(
                        "Błąd",
                        f"❌ Nie udało się odinstalować portable PG:\n\n"
                        f"{result.error or 'nieznany błąd'}",
                        parent=self,
                    )
            except Exception:
                pass

            # Odśwież status (nowa etykieta "niezainstalowany").
            self._refresh_portable_pg_status()
        except Exception as exc:
            try:
                messagebox.showerror(
                    "Błąd krytyczny",
                    f"Nieoczekiwany błąd podczas odinstalowania:\n{exc}",
                    parent=self,
                )
            except Exception:
                pass
        finally:
            self._portable_pg_uninstall_in_progress = False

    def _offer_portable_pg_install(self):
        """Pyta użytkownika czy pobrać i zainstalować portable PostgreSQL.

        Wywoływane z :meth:`test_connection` gdy:
            * ``test_postgres_connection`` zwrócił ``(False, msg)``,
            * ``detect_system_pg()`` zwraca ``None`` (brak PG w systemie).

        Po kliknięciu "Tak" uruchamia :meth:`_install_portable_pg_with_progress`
        w osobnym wątku, żeby nie blokować UI.
        """
        # Oznacz, że już zaproponowaliśmy - auto_test_connection jest
        # odpalany na każdym FocusOut, więc bez flagi dialog by spamował.
        self._portable_pg_offered = True

        try:
            answer = messagebox.askyesno(
                "Brak PostgreSQL",
                "Nie wykryto PostgreSQL w systemie.\n\n"
                "Czy chcesz pobrać i zainstalować portable PostgreSQL "
                "(ok. 200 MB, pobierane z oficjalnego źródła EDB)?\n\n"
                "Bez tego kreator nie będzie mógł połączyć się z bazą.",
                parent=self,
            )
        except Exception:
            return

        if not answer:
            return

        self._install_portable_pg_with_progress()

    def _install_portable_pg_with_progress(self):
        """Otwiera okno postępu i uruchamia instalację portable PG w wątku.

        Sekwencja kroków (w wątku ``_portable_pg_install_thread``):
            1. ``pg_portable_service.get_pg_install_dir()`` → ``install_dir``
            2. ``pg_portable_service.get_pg_download_url()`` → ``url``
            3. ``pg_portable_service.download_pg_binary(url, install_dir, cb)``
            4. ``pg_portable_service.extract_pg_archive(archive_path, install_dir, cb)``
            5. ``pg_runtime.init_pg_data_dir(config)`` → ``StepResult``
            6. ``pg_runtime.start_pg_server(config)`` → ``ServerHandle``
            7. ``pg_runtime.stop_pg_server(handle)`` (natychmiast —
               instalator nie ma utrzymywać serwera; pełen start
               będzie w Etapach 4-5 po migracji).
            8. Zamknięcie okna postępu i powrót do UI.
        """
        if self._portable_pg_install_in_progress:
            return
        self._portable_pg_install_in_progress = True

        # Utwórz okno postępu.
        progress_win = tk.Toplevel(self)
        progress_win.title("📥 Instalacja portable PostgreSQL")
        progress_win.transient(self)
        progress_win.resizable(False, False)
        try:
            set_dialog_icon(progress_win)
        except Exception:
            pass

        # Wycentruj nad kreatorem.
        progress_win.update_idletasks()
        try:
            x = self.winfo_rootx() + (self.winfo_width() - 480) // 2
            y = self.winfo_rooty() + (self.winfo_height() - 200) // 2
            progress_win.geometry(f"480x200+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            progress_win.geometry("480x200")

        ttk.Label(
            progress_win,
            text="📥 Pobieranie i instalacja PostgreSQL...",
            font=('Arial', 11, 'bold'),
            padding=10,
        ).pack(pady=(15, 5))

        progress_bar = ttk.Progressbar(
            progress_win, orient="horizontal", length=440, mode="determinate"
        )
        progress_bar.pack(pady=5, padx=20)

        status_label = ttk.Label(progress_win, text="Przygotowywanie...", padding=5,
                                 wraplength=440, justify=tk.LEFT)
        status_label.pack(pady=(5, 10), padx=20, fill=tk.X)

        # Wyłącz parent, żeby user nie klikał w trakcie instalacji.
        try:
            progress_win.grab_set()
        except Exception:
            pass

        def _progress_cb(downloaded: int, total: int) -> None:
            """Callback postępu pobierania - aktualizuje pasek + status."""
            try:
                if total > 0:
                    progress_bar["maximum"] = total
                    progress_bar["value"] = downloaded
                else:
                    # Brak Content-Length - pokaż przynajmniej nieokreślony postęp.
                    progress_bar.config(mode="indeterminate")
                    progress_bar.start(50)
                size_mb = downloaded / (1024 * 1024) if downloaded else 0
                if total > 0:
                    total_mb = total / (1024 * 1024)
                    status_label.config(text=f"Pobrano {size_mb:.1f} / {total_mb:.1f} MB")
                else:
                    status_label.config(text=f"Pobrano {size_mb:.1f} MB...")
            except Exception:
                pass

        def _extract_cb(message: str) -> None:
            """Callback postępu rozpakowywania - aktualizuje status."""
            try:
                status_label.config(text=message)
                progress_bar.config(mode="indeterminate")
                progress_bar.start(50)
            except Exception:
                pass

        def _set_status(message: str) -> None:
            """Ustawia tekst statusu (thread-safe dzięki after)."""
            try:
                progress_win.after(0, lambda: status_label.config(text=message))
            except Exception:
                pass

        def _finish_in_ui(success: bool, error_msg: str) -> None:
            """Zamyka okno postępu i wraca do głównego wątku UI."""
            self._portable_pg_install_in_progress = False
            try:
                progress_win.grab_release()
            except Exception:
                pass
            try:
                progress_win.destroy()
            except Exception:
                pass
            self._on_portable_pg_install_complete(success, error_msg)

        def _worker() -> None:
            """Wątek roboczy: pobranie → ekstrakcja → init → start → stop."""
            try:
                _set_status("Wybieram katalog instalacji...")
                install_dir = pg_portable_service.get_pg_install_dir()

                _set_status("Pobieram URL...")
                url = pg_portable_service.get_pg_download_url()

                _set_status(f"Pobieram archiwum PostgreSQL z {url}...")
                archive_path = pg_portable_service.download_pg_binary(
                    url, install_dir, progress_callback=_progress_cb
                )

                _set_status("Rozpakowuję archiwum...")
                bin_dir = pg_portable_service.extract_pg_archive(
                    archive_path, install_dir, progress_callback=_extract_cb
                )

                # Zbuduj konfigurację dla pg_runtime. Host = 127.0.0.1 (lokalny).
                pg_cfg = PostgresConfig(
                    host="127.0.0.1",
                    port=5432,
                    user="postgres",
                    password="postgres",
                )

                _set_status("Inicjalizuję klaster danych (initdb)...")
                step_result = pg_runtime.init_pg_data_dir(pg_cfg)
                if not getattr(step_result, "ok", True):
                    raise RuntimeError(getattr(step_result, "message", "init_pg_data_dir zwrócił błąd"))

                _set_status("Uruchamiam serwer PostgreSQL (smoke test)...")
                handle = pg_runtime.start_pg_server(pg_cfg)

                _set_status("Zatrzymuję serwer (smoke test)...")
                pg_runtime.stop_pg_server(handle)

                # Sukces - wróć do UI.
                try:
                    progress_win.after(0, lambda: _finish_in_ui(True, ""))
                except Exception:
                    _finish_in_ui(True, "")

            except Exception as exc:
                try:
                    progress_win.after(0, lambda: _finish_in_ui(False, str(exc)))
                except Exception:
                    _finish_in_ui(False, str(exc))

        # Uruchom wątek.
        threading.Thread(target=_worker, daemon=True).start()

    def _on_portable_pg_install_complete(self, success: bool, error_msg: str):
        """Callback po zakończeniu instalacji portable PG.

        Args:
            success: ``True`` jeśli instalacja zakończyła się bez błędów.
            error_msg: komunikat błędu (``""`` przy sukcesie).
        """
        if success:
            messagebox.showinfo(
                "✅ Portable PostgreSQL zainstalowany",
                "Portable PostgreSQL został pobrany i zainicjalizowany.\n\n"
                "Serwer został uruchomiony i zatrzymany (smoke test).\n"
                "Możesz teraz ponownie przetestować połączenie.",
                parent=self,
            )
            # Po instalacji spróbuj ponownie przetestować połączenie -
            # kreator powinien sam wrócić do flow test_connection.
            try:
                self.test_connection()
            except Exception:
                pass
        else:
            messagebox.showerror(
                "❌ Instalacja nie powiodła się",
                f"Nie udało się zainstalować portable PostgreSQL:\n\n{error_msg}\n\n"
                "Zainstaluj PostgreSQL ręcznie albo sprawdź połączenie sieciowe.",
                parent=self,
            )
            # Zaktualizuj status połączenia w kroku 1.
            try:
                self.connection_status.config(
                    text=f"✗ Brak PG: {error_msg}",
                    foreground="red",
                )
            except Exception:
                pass


    def _get_selected_location_name(self) -> str:
        """Zwraca nazwę (name) wybranej miejscowości z comboboxa.

        Wykorzystywane przez kreator migracji do zbudowania ``MigrationOptions``."""
        selected_index = self.location_combo.current()
        if selected_index < 0 or not hasattr(self, 'location_data') or not self.location_data:
            raise Exception("Wybierz miejscowość z listy.")

        display_name, db_name = self.location_data[selected_index]
        # ``display_name`` ma format ``"<name> -> <db_name>"`` albo ``"<name> (brak bazy)"``.
        # Wyciągamy czystą nazwę miejscowości z lewej części.
        if " -> " in display_name:
            return display_name.split(" -> ", 1)[0].strip()
        if " (brak bazy)" in display_name:
            return display_name.split(" (brak bazy)", 1)[0].strip()
        return display_name.strip()

    def migrate_to_postgresql(self):
        """Bezpieczna migracja: orkiestruje wszystko przez postgres_migration_service.

        Logika (walidacja, tworzenie bazy, PostGIS, schemat, import, weryfikacja,
        przełączenie ``backend/.env``) jest w ``launcher.services.postgres_migration_service``.
        """
        location_name = self._get_selected_location_name()
        self.log(f"=== Migracja do PostgreSQL: {location_name} ===\n")
        self.log("Log jest zapisywany do data/locations/<miejscowość>/logs/postgres_migration_*.log\n")

        pg_config = PostgresConfig(
            host=self.config['host'],
            port=int(self.config['port']),
            user=self.config['user'],
            password=self.config['password'],
        )
        options = MigrationOptions(
            location_name=location_name,
            create_database=True,
            recreate_schema=True,
            enable_postgis=True,
            switch_engine_on_success=True,
        )

        try:
            result = run_postgres_migration_wizard(
                pg_config,
                options,
                log_callback=self.log,
            )
        except Exception as exc:
            self.log(f"\n❌ Nieoczekiwany błąd migracji: {exc}")
            raise

        # Wypisz kroki w logu
        for step in result.steps:
            self.log(f"   • {step.name}: {step.message}")

        if not result.ok:
            # Nie przełączono backendu — system pozostanie na SQLite
            self.log(
                "\n⚠️ Migracja nie powiodła się. Backend pozostaje na SQLite. "
                "Sprawdź log: {log}".format(log=result.log_path or "-")
            )
            raise Exception("Migracja zakończona błędem. Backend pozostaje na SQLite.")

        # Sukces
        self.log("\n✅ Migracja zakończona pomyślnie.")
        self.log(f"   Baza: {result.db_name}")
        self.log(f"   Log: {result.log_path or '-'}")
        if result.verification and result.verification.warnings:
            for warning in result.verification.warnings:
                self.log(f"   ⚠️ {warning}")

    def execute_action(self):
        """Wykonaj akcję"""
        action = self.action_var.get()
        self.progress.start()
        self.log("🚀 Rozpoczynam...\n")

        try:
            if action == "migrate_to_postgresql":
                self.migrate_to_postgresql()
            elif action == "create_launcher_db":
                self.create_launcher_database()
            elif action == "drop_launcher_tables":
                self.drop_launcher_tables()
            elif action == "recreate_launcher_tables":
                self.recreate_launcher_tables()
            elif action == "create_location_db":
                self.create_location_database()
            elif action == "drop_location_tables":
                self.drop_location_tables()
            elif action == "recreate_location_tables":
                self.recreate_location_tables()
            elif action == "drop_location_database":
                self.drop_location_database()

            self.log("\n✅ Gotowe!")
            self.result = True
            self.finish_button.config(state=tk.NORMAL)
        except Exception as e:
            self.log(f"\n❌ Błąd: {e}")
            messagebox.showerror("Błąd", str(e), parent=self)
        finally:
            self.progress.stop()

    # === FUNKCJE DLA BAZY LAUNCHER ===

    def create_launcher_database(self):
        """Utwórz bazę launcher (CREATE DATABASE + tables)"""
        self.log("=== Tworzenie bazy launcher ===\n")

        self.log("1. Tworzę bazę mapa_launcher_db...")
        success, msg = postgres_create_database(**self.config, db_name='mapa_launcher_db')
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("2. Włączam rozszerzenie PostGIS...")
        success, msg = postgres_enable_postgis(**self.config, db_name='mapa_launcher_db')
        self.log(f"   {msg}")
        if not success:
            self.log(f"   ⚠️ Ostrzeżenie: {msg}")

        self.log("3. Tworzę tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name='mapa_launcher_db', schema_sql=LAUNCHER_DB_SCHEMA)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        global LOCATIONS_DB_INITIALIZED
        LOCATIONS_DB_INITIALIZED = False

    def drop_launcher_tables(self):
        """Usuń tabele launcher (DROP TABLES)"""
        self.log("=== Usuwanie tabel launcher ===\n")

        if not postgres_database_exists(**self.config, db_name='mapa_launcher_db'):
            raise Exception("Baza mapa_launcher_db nie istnieje!")

        self.log("Usuwam tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name='mapa_launcher_db', schema_sql=LAUNCHER_DROP_TABLES)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("\n⚠️ Wszystkie dane usunięte!")

        global LOCATIONS_DB_INITIALIZED
        LOCATIONS_DB_INITIALIZED = False

    def recreate_launcher_tables(self):
        """Odtwórz tabele launcher (DROP + CREATE)"""
        self.log("=== Odtwarzanie tabel launcher ===\n")

        if not postgres_database_exists(**self.config, db_name='mapa_launcher_db'):
            raise Exception("Baza mapa_launcher_db nie istnieje!")

        self.log("1. Usuwam stare tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name='mapa_launcher_db', schema_sql=LAUNCHER_DROP_TABLES)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("2. Włączam rozszerzenie PostGIS...")
        success, msg = postgres_enable_postgis(**self.config, db_name='mapa_launcher_db')
        self.log(f"   {msg}")
        if not success:
            self.log(f"   ⚠️ Ostrzeżenie: {msg}")

        self.log("3. Tworzę nowe tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name='mapa_launcher_db', schema_sql=LAUNCHER_DB_SCHEMA)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("\n⚠️ Wszystkie dane usunięte i tabele odtworzone!")

        global LOCATIONS_DB_INITIALIZED
        LOCATIONS_DB_INITIALIZED = False

    # === FUNKCJE DLA BAZY MIEJSCOWOŚCI ===

    def _get_selected_location_db(self):
        """Pobiera nazwę bazy wybranej miejscowości"""
        selected_index = self.location_combo.current()
        if selected_index < 0 or not hasattr(self, 'location_data') or not self.location_data:
            raise Exception("Wybierz miejscowość z listy!")

        display_name, db_name = self.location_data[selected_index]
        if not db_name:
            raise Exception("Wybrana miejscowość nie ma przypisanej bazy danych!")

        return db_name

    def create_location_database(self):
        """Utwórz bazę miejscowości (CREATE DATABASE + tables)"""
        self.log("=== Tworzenie bazy miejscowości ===\n")

        db_name = self._get_selected_location_db()
        self.log(f"Baza: {db_name}\n")

        self.log("1. Tworzę bazę...")
        success, msg = postgres_create_database(**self.config, db_name=db_name)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("2. Włączam rozszerzenie PostGIS...")
        success, msg = postgres_enable_postgis(**self.config, db_name=db_name)
        self.log(f"   {msg}")
        if not success:
            self.log(f"   ⚠️ Ostrzeżenie: {msg}")

        self.log("3. Tworzę tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name=db_name, schema_sql=LOCATION_DB_SCHEMA)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

    def drop_location_tables(self):
        """Usuń tabele miejscowości (DROP TABLES)"""
        self.log("=== Usuwanie tabel miejscowości ===\n")

        db_name = self._get_selected_location_db()
        self.log(f"Baza: {db_name}\n")

        if not postgres_database_exists(**self.config, db_name=db_name):
            raise Exception(f"Baza {db_name} nie istnieje!")

        self.log("Usuwam tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name=db_name, schema_sql=LOCATION_DROP_TABLES)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("\n⚠️ Wszystkie dane usunięte!")

    def recreate_location_tables(self):
        """Odtwórz tabele miejscowości (DROP + CREATE)"""
        self.log("=== Odtwarzanie tabel miejscowości ===\n")

        db_name = self._get_selected_location_db()
        self.log(f"Baza: {db_name}\n")

        if not postgres_database_exists(**self.config, db_name=db_name):
            raise Exception(f"Baza {db_name} nie istnieje!")

        self.log("1. Usuwam stare tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name=db_name, schema_sql=LOCATION_DROP_TABLES)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("2. Włączam rozszerzenie PostGIS...")
        success, msg = postgres_enable_postgis(**self.config, db_name=db_name)
        self.log(f"   {msg}")
        if not success:
            self.log(f"   ⚠️ Ostrzeżenie: {msg}")

        self.log("3. Tworzę nowe tabele...")
        success, msg = postgres_execute_schema(**self.config, db_name=db_name, schema_sql=LOCATION_DB_SCHEMA)
        self.log(f"   {msg}")
        if not success:
            raise Exception(msg)

        self.log("\n⚠️ Wszystkie dane usunięte i tabele odtworzone!")

    def drop_location_database(self):
        """Usuń całą bazę miejscowości (DROP DATABASE)"""
        self.log("=== Usuwanie całej bazy miejscowości ===\n")

        db_name = self._get_selected_location_db()
        self.log(f"Baza: {db_name}\n")

        if not postgres_database_exists(**self.config, db_name=db_name):
            raise Exception(f"Baza {db_name} nie istnieje!")

        # Potwierdzenie
        confirm = messagebox.askyesno(
            "⚠️ UWAGA",
            f"Czy na pewno chcesz CAŁKOWICIE USUNĄĆ bazę {db_name}?\n\n"
            "Wszystkie dane zostaną bezpowrotnie utracone!",
            icon='warning',
            parent=self
        )

        if not confirm:
            raise Exception("Anulowano przez użytkownika")

        self.log("Usuwam bazę danych...")

        # DROP DATABASE
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database='postgres'
            )
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(f"DROP DATABASE IF EXISTS {db_name}")
            cursor.close()
            conn.close()

            self.log(f"   ✓ Baza {db_name} została usunięta")
        except Exception as e:
            raise Exception(f"Błąd usuwania bazy: {e}")

        self.log("\n⚠️ Baza całkowicie usunięta!")

    def finish(self):
        """Zakończ"""
        self.destroy()
