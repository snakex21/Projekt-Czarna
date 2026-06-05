"""
================================================================================
Plik: launcher.py
System Mapy Katastralnej - Centrum Zarządzania
================================================================================
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import os
import sys
import platform
import ctypes


def _safe_print(message):
    """Print text without failing on legacy Windows console encodings."""
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(str(message).encode(encoding, errors="replace").decode(encoding, errors="replace"))


# === Dodaj katalog projektu do ścieżki Pythona (dla importów modułów launcher.*) ===
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

# === Import nowego silnika bazy danych ===
try:
    from launcher.db.engine import detect_engine, get_engine
    _DB_ENGINE = detect_engine()
    _safe_print(f"🗺️ Silnik bazy: {_DB_ENGINE.label} ({_DB_ENGINE.name})")
    _safe_print(f"📋 Dostępne edytory: {_DB_ENGINE.available_editors}")
except ImportError as e:
    _safe_print(f"⚠️ Nie udało się zaimportować silnika DB: {e}")
    _DB_ENGINE = None

# =============================================================================
# KONFIGURACJA DPI DLA WINDOWS
# =============================================================================
if platform.system() == "Windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass

# =============================================================================
# KONFIGURACJA ŚCIEŻEK I STAŁYCH
# =============================================================================
from launcher.config.paths import (
    BACKEND_DIR as PATH_BACKEND_DIR,
    BASE_DIR as PATH_BASE_DIR,
    SITE_ASSETS_FOLDER as PATH_SITE_ASSETS_FOLDER,
    TOOLS_DIR as PATH_TOOLS_DIR,
)

# Legacy API launchera oczekuje stringów, ale źródłem prawdy jest paths.py.
BASE_DIR = str(PATH_BASE_DIR)
BACKEND_DIR = str(PATH_BACKEND_DIR)
TOOLS_DIR = str(PATH_TOOLS_DIR)
SITE_ASSETS_FOLDER = str(PATH_SITE_ASSETS_FOLDER)

# =============================================================================
# TRYB BAZY DANYCH — wykrywany z launcher/db/engine.py
# =============================================================================
# SQLITE_MODE zachowane dla kompatybilności z istniejącym kodem.
# Preferuj _DB_ENGINE (z engine.py) dla nowego kodu.
SQLITE_MODE = _DB_ENGINE is not None and _DB_ENGINE.name == "sqlite"
if SQLITE_MODE:
    _safe_print("💾 Tryb SQLite — PostgreSQL nie jest wymagany")

# Import stałych konfiguracyjnych
from launcher.config.settings import DEFAULT_LOCATION_NAME

# Import helpera z process_manager (zachowany dla kompatybilności)
from launcher.utils import (_read_backend_env_value, set_dialog_icon,
    set_windows_taskbar_icon_for_window,
    get_data_files,
    check_env_configuration, get_location_env_path, read_env_config,
    apply_homepage_template)
from launcher.config.ui_settings import (
    get_ui_scale_setting,
)

# Import klas dialogowych z dedykowanych modułów UI
from launcher.ui.add_edit_location_dialog import AddEditLocationDialog as _AddEditLocationDialog
from launcher.ui.loading_dialog import LoadingDialog
from launcher.ui.photos_manager_dialog import PhotosManagerDialog as _PhotosManagerDialog
from launcher.ui.site_settings_manager import SiteSettingsManager as _SiteSettingsManager
from launcher.ui.icon_chooser_window import IconChooserWindow as _IconChooserWindow
from launcher.ui.location_manager import LocationManager as _LocationManager, TemplateChangeDialog as _TemplateChangeDialog
from launcher.ui.database_wizard import DatabaseWizard as _DatabaseWizard
from launcher.ui.instructions_window import InstructionsWindow as _InstructionsWindow
from launcher.ui.database_config_dialogs import (
    choose_database_engine as _choose_database_engine,
    setup_postgres_config as _setup_postgres_config,
)
from launcher.ui.main_dashboard import build_main_dashboard
from launcher.ui.admin_settings import AdminSettings as _AdminSettings
from launcher.ui.backup_manager import BackupManager as _BackupManager
from launcher.ui.display_settings import DisplaySettingsDialog as _DisplaySettingsDialog
from launcher.ui.env_editor import EnvEditor as _EnvEditor
from launcher.ui.map_calibrator import (
    CalibrationInstructions as _CalibrationInstructions,
    MapCalibrator as _MapCalibrator,
)
from launcher.ui.progress_dialog import ProgressDialog as _ProgressDialog
from launcher.ui.program_settings import ProgramSettingsWindow
from launcher.ui import console_runtime, db_engine_switcher, env_runtime, shutdown_runtime, window_runtime
from launcher.services.system_diagnostics import (
    get_database_diagnostics as build_database_diagnostics,
    init_location_database,
)
from launcher.services import firewall_runtime
from launcher.services import guardian_runtime
from launcher.services import icon_service
from launcher.services import location_files_service
from launcher.services import location_service
from launcher.services import location_runtime
from launcher.services import location_migration_service
from launcher.services import startup_initialization_service
from launcher.services import site_generation_service
from launcher.services import test_runtime
from launcher.services.process_manager import ProcessManager


# =============================================================================
# POSTGRESQL - FUNKCJE POMOCNICZE I SCHEMA
# =============================================================================
# ZARZĄDZANIE MIEJSCOWOŚCIAMI
# =============================================================================
# Implementacje przeniesiono do launcher.services.location_service.
# Cienkie wrappery kompatybilnościowe znajdują się poniżej migracji ikon.
def migrate_custom_icon_to_backup():
    return icon_service.migrate_custom_icon_to_backup()

# =============================================================================
# ZARZĄDZANIE MIEJSCOWOŚCIAMI — cienkie wrappery dla kompatybilności
# =============================================================================
def init_locations_db():
    return location_service.init_locations_db()


def get_all_locations():
    return location_service.get_all_locations()


def get_active_location():
    return location_service.get_active_location()


def _get_active_location_from_json():
    return location_service._get_active_location_from_json()


def get_active_location_name():
    return location_service.get_active_location_name()


def set_active_location(location_id):
    return location_service.set_active_location(location_id)


def generate_location_config_js():
    return location_service.generate_location_config_js()


def set_location_template(location_id, template_name):
    return location_service.set_location_template(location_id, template_name)


def ensure_location_data_files(location_folder):
    return location_service.ensure_location_data_files(location_folder)


def add_location(name, full_name, powiat="", region="", homepage_template="standardowy", year="1882", century="XIX w.",
                homepage_description="Odkryj historię zapisaną w ziemi. Przeglądaj historyczne działki katastralne, poznaj dawnych właścicieli i zgłębiaj genealogiczne powiązania mieszkańców z 1882 roku.",
                history_paragraph1="", history_paragraph2="", history_paragraph3="",
                history_photos=None, postgres_db_name="", gmina_katastralna=DEFAULT_LOCATION_NAME,
                jewish_protocol_numbers="", custom_icon="custom_icon.png"):
    return location_service.add_location(
        name, full_name, powiat, region, homepage_template, year, century,
        homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
        history_photos, postgres_db_name, gmina_katastralna, jewish_protocol_numbers, custom_icon
    )


def update_location(location_id, name, full_name, powiat, region, year, century,
                   homepage_description="", history_paragraph1="", history_paragraph2="", history_paragraph3="",
                   history_photos=None, postgres_db_name="", homepage_template="standardowy",
                   gmina_katastralna=DEFAULT_LOCATION_NAME, jewish_protocol_numbers="", custom_icon="custom_icon.png"):
    return location_service.update_location(
        location_id, name, full_name, powiat, region, year, century,
        homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
        history_photos, postgres_db_name, homepage_template,
        gmina_katastralna, jewish_protocol_numbers, custom_icon
    )


def delete_location(location_id):
    return location_service.delete_location(location_id)


def load_default_location_config():
    return location_service.load_default_location_config()


def ensure_default_location_exists():
    return location_service.ensure_default_location_exists()


def migrate_old_backup_structure():
    return location_service.migrate_old_backup_structure()


def invalidate_locations_cache():
    return location_service.invalidate_locations_cache()

# Dla kompatybilności wstecznej
DATA_FILES = get_data_files()


def refresh_data_files():
    """Odświeża kompatybilnościowy słownik DATA_FILES po zmianie miejscowości."""
    global DATA_FILES
    DATA_FILES = get_data_files()
    return DATA_FILES


# Zrodlem prawdy dla COLORS jest launcher.config.settings.COLORS.
COLORS = {
    'primary': '#0d6efd', 'success': '#198754', 'danger': '#dc3545',
    'warning': '#ffc107', 'info': '#0dcaf0', 'secondary': '#6c757d',
    'dark': '#212529', 'light': '#f8f9fa',
}



def _auto_sync_site_icon():
    return icon_service.auto_sync_site_icon()


def check_backup_folder_files():
    return location_files_service.check_backup_folder_files()

# =============================================================================
# GŁÓWNA KLASA APLIKACJI
# =============================================================================
class AppLauncher(tk.Tk):
    """Główna klasa aplikacji centrum zarządzania."""
    
    def __init__(self):
        """Inicjalizacja głównego okna aplikacji."""
        super().__init__()
        self.title("🗺️ Centrum Zarządzania - System Mapy Katastralnej")
        self.ui_scale = get_ui_scale_setting()
        self.setup_window_geometry()

        # Ustaw ikonę okna (pióro)
        self.set_window_icon()

        self.process_mgr = ProcessManager(self)
        self._refresh_pending = False  # Debounce flag
        self._cached_locations = None  # Cache lokacji w pamięci
        self._location_refresh_force = False
        self._log_buffer = {}  # Buffer logów dla każdej konsoli (batching)
        self._log_flush_pending = False  # Flaga pending flush
        self._guardian_last_check_at = None
        self._guardian_last_issues = None
        self._guardian_last_duration = None
        self.setup_styles()

        # UKRYJ główne okno przed pierwszą konfiguracją bazy danych
        self.withdraw()

        # Migracja starych danych
        migrate_old_backup_structure()

        # Sprawdź konfigurację wybranego silnika (SQLite / PostgreSQL)
        # Przekazujemy self jako parent żeby dialog był przypisany do głównego okna
        setup_postgres_config(parent=self)

        # Migruj stare custom_icon z launcher/assets do backup/{miejscowość}/
        # (musi być po setup_postgres_config i migrate_old_backup_structure)
        migrate_custom_icon_to_backup()

        # POKAŻ główne okno po konfiguracji bazy danych
        self.deiconify()

        # Ustaw ikonę PO odkryciu okna (na ukrytym Windows gubi powiązanie)
        self.set_window_icon()

        # Zawsze tworzymy okno ładowania dla lepszej UX
        loading_dialog = LoadingDialog(self)
        loading_dialog.update_status("Inicjalizacja...", "Sprawdzanie konfiguracji")

        # Automatyczna inicjalizacja baz przy pierwszym uruchomieniu.
        def _loading_status_adapter(status, detail=""):
            loading_dialog.update_status(status, detail)

        init_result = startup_initialization_service.auto_initialize_on_startup(
            status_callback=_loading_status_adapter
        )
        loading_dialog.init_summary = init_result.summary
        if not init_result.success and init_result.error:
            _safe_print(f"⚠️ Automatyczna inicjalizacja nie powiodła się: {init_result.error}")

        # === FIX: NATYCHMIASTOWA AKTUALIZACJA IKONY PO INICJALIZACJI ===
        # Wymuszamy odświeżenie cache i ponowne ustawienie ikony,
        # aby po pierwszym utworzeniu "Czarnej" ikona załadowała się natychmiast bez restartu.
        try:
            invalidate_locations_cache()     # Wyczyść cache, by widzieć nową aktywną miejscowość
            migrate_custom_icon_to_backup()  # Przenieś ikonę, teraz gdy folder backup/Czarna już istnieje
            self.set_window_icon()           # Załaduj ikonę ponownie (teraz pobierze ją z folderu Czarnej)
        except Exception as e:
            _safe_print(f"⚠️ Błąd odświeżania ikony po inicjalizacji: {e}")

        # Kontynuuj inicjalizację z oknem ładowania
        loading_dialog.update_status("Konfiguracja plików...", "Sprawdzanie środowiska")

        check_env_configuration()
        check_backup_folder_files()

        loading_dialog.update_status("Synchronizacja ikon...", "Favicon i zasoby")

        _auto_sync_site_icon()

        # Automatycznie odśwież strony HTML z placeholderami (w tle aby nie blokować startu)
        loading_dialog.update_status("Aktualizacja stron HTML...", "Generowanie szablonów")

        def _async_refresh():
            try:
                self.refresh_html_pages()
                _safe_print("✅ Strony HTML i konfiguracja zaktualizowane w tle")
            except Exception as e:
                _safe_print(f"⚠️ Błąd podczas generowania plików: {e}")

        # Uruchom w tle - nie blokuj GUI
        threading.Thread(target=_async_refresh, daemon=True).start()

        # Zamknij okno ładowania i pokaż podsumowanie
        loading_dialog.update_status("System gotowy!", "Uruchamianie interfejsu...")
        import time
        time.sleep(0.5)
        loading_dialog.close()

        # Pokaż podsumowanie inicjalizacji
        if hasattr(loading_dialog, 'init_summary'):
            summary = loading_dialog.init_summary
            if summary['created_launcher'] or summary['created_czarna_location'] or \
               summary['created_czarna_db'] or summary['migrated_data']:

                message = "🎉 System jest gotowy do użycia!\n\n"

                if summary['created_launcher']:
                    message += "✅ Utworzono bazę mapa_launcher_db\n"
                else:
                    message += "✅ Baza mapa_launcher_db gotowa\n"

                if summary['created_czarna_location']:
                    message += "✅ Utworzono miejscowość 'Czarna'\n"
                else:
                    message += "✅ Miejscowość 'Czarna' gotowa\n"

                if summary['created_czarna_db']:
                    message += "✅ Utworzono bazę mapa_czarna_db\n"
                else:
                    message += "✅ Baza mapa_czarna_db gotowa\n"

                if summary['migrated_data']:
                    message += "✅ Dane zmigrowane z backup/Czarna\n"

                message += "\n💡 Możesz teraz:\n"
                message += "• Włączyć serwer i zobaczyć mapę\n"
                message += "• Edytować dane właścicieli\n"
                message += "• Kalibrować mapę\n"
                message += "• Zarządzać miejscowościami"

                messagebox.showinfo("System gotowy!", message)

        self.create_widgets()

        # === PONOWNE USTAWIENIE IKONY PO ZBUDOWANIU UI ===
        # create_widgets() i messagebox mogą zresetować ikonę na pasku Windows.
        self.after(100, self.set_window_icon)

        # Odroczone operacje I/O - wykonaj po pełnej inicjalizacji GUI (nie blokuj startu)
        self.after(10, self.refresh_locations)  # Załaduj lokacje asynchronicznie
        self.after(30, self.refresh_quick_links)  # Konfiguruj przyciski szybkiego dostępu
        self.after(40, self.start_env_watcher)  # Uruchom watcher pliku .env
        self.after(20, lambda: setattr(self, '_last_port', self.load_flask_config().get("port")))
        self.after(100, self.run_proactive_health_check) # Pierwsza kontrola Strażnika
        

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Fallback: jeśli główne okno zostanie zniszczone inną ścieżką niż
        # WM_DELETE_WINDOW (np. przez self.destroy()), natychmiast zakończ proces,
        # żeby okno konsoli py.exe nie zostawało otwarte.
        self._exiting = False
        self.bind("<Destroy>", self._on_root_destroy, add="+")

        # Obsługa focusu okna - naprawia problem z alt+tab i przełączania myszką
        self.bind("<FocusIn>", self.on_window_focus)
        self.bind("<Visibility>", self.on_window_focus)  # Gdy okno staje się widoczne
        self.bind("<Map>", self.on_window_focus)  # Gdy okno jest mapowane na ekran

        # Dla Windows - dodatkowa obsługa aktywacji okna
        if platform.system() == "Windows":
            self.bind("<Activate>", self.on_window_focus)

        self.process_queue()

    def setup_window_geometry(self):
        """Inteligentnie dostosowuje rozmiar okna do ekranu i DPI."""
        return window_runtime.setup_window_geometry(self)

    def setup_styles(self):
        """Konfiguruje style i czcionki dla aplikacji."""
        from launcher.ui.styles import setup_app_styles
        self.style, self.base_font_size = setup_app_styles(self, ui_scale=self.ui_scale)

    def open_display_settings(self):
        """Otwiera ustawienia skali interfejsu launchera."""
        dialog = DisplaySettingsDialog(self)
        self.wait_window(dialog)

    def open_program_settings(self):
        """Otwiera centralny panel ustawień programu."""
        ProgramSettingsWindow(self)

    def apply_ui_scale(self, new_scale, restart_now=False):
        """Zapisuje skalę UI i restartuje launcher by zastosować."""
        return window_runtime.apply_ui_scale(self, new_scale, restart_now=restart_now)

    def set_window_icon(self):
        """Ustawia ikonę okna aplikacji (custom lub domyślna)."""
        try:
            # Dla Windows, ustaw AppUserModelID aby ikona była widoczna w pasku zadań
            if platform.system() == "Windows":
                try:
                    import ctypes
                    myappid = 'projekt.czarna.launcher.1.0'
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                except Exception as e:
                    _safe_print(f"⚠️ Nie udało się ustawić AppUserModelID: {e}")

            # Pobierz aktywną miejscowość
            active_location = get_active_location()
            png_path = None
            ico_path = None

            # Najpierw szukaj w backup/{miejscowość}/
            if active_location:
                location_name = active_location[1]
                backup_icon_dir = os.path.join(BASE_DIR, "data", "locations", location_name)

                # Sprawdź czy jest custom_icon w folderze miejscowości
                custom_png = os.path.join(backup_icon_dir, 'custom_icon.png')
                custom_ico = os.path.join(backup_icon_dir, 'custom_icon.ico')

                if os.path.exists(custom_png):
                    png_path = custom_png
                if os.path.exists(custom_ico):
                    ico_path = custom_ico

            # Jeśli miejscowość nie ma własnej ikony, użyj domyślnej feather_icon
            icon_dir = os.path.join(os.path.dirname(__file__), 'assets')
            if not png_path:
                png_path = os.path.join(icon_dir, 'feather_icon.png')
                _safe_print(f"🔄  Używam domyślnej ikony: {png_path}")
            else:
                _safe_print(f"🔄  Używam custom ikony: {png_path}")
            if not ico_path:
                ico_path = os.path.join(icon_dir, 'feather_icon.ico')

            # Usuń starą referencję ikony
            if hasattr(self, '_icon_image'):
                del self._icon_image

            # Spróbuj użyć PNG z iconphoto() (wieloplatformowe)
            if os.path.exists(png_path):
                icon_image = tk.PhotoImage(file=png_path)
                # Użyj False aby ikona była tylko dla tego okna (lepiej dla dynamicznej zmiany)
                self.iconphoto(False, icon_image)
                # Zachowaj referencję aby uniknąć garbage collection
                self._icon_image = icon_image
                _safe_print(f"✅ Ikona załadowana pomyślnie")
            else:
                _safe_print(f"⚠️ Plik ikony nie istnieje: {png_path}")

            # Dla Windows, ustaw ICO i ikonę paska zadań
            if platform.system() == "Windows":
                if os.path.exists(ico_path):
                    self.iconbitmap(ico_path)
                    # Ustaw także ikonę paska zadań używając Windows API dla lepszej jakości
                    set_windows_taskbar_icon_for_window(self, ico_path)
        except Exception as e:
            _safe_print(f"⚠️ Nie udało się ustawić ikony okna: {e}")

    def change_taskbar_icon(self):
        """Otwiera okno do wyboru i zmiany ikony aplikacji."""
        IconChooserWindow(self)

    def create_console_widget(self, parent):
        """Tworzy widget konsoli z ciemnym motywem."""
        return console_runtime.create_console_widget(self, parent)

    def process_queue(self):
        """Przetwarza zdarzenia z kolejki w pętli głównej."""
        if getattr(self, "_process_queue_started", False):
            return
        self._process_queue_started = True
        self.process_mgr.process_queue()

    def create_widgets(self):
        """Tworzy kompletny interfejs użytkownika."""
        build_main_dashboard(self)

    def log(self, message, console=None):
        """Wypisuje wiadomość do konsoli (zoptymalizowane z batchingiem)."""
        return console_runtime.log(self, message, console)

    def _flush_logs(self):
        """Flush wszystkich zabuforowanych logów na raz."""
        return console_runtime.flush_logs(self)

    def update_processes_ui(self):
        """Odświeża listę uruchomionych procesów."""
        self.process_mgr.update_processes_ui()

    def load_flask_config(self):
        """Czyta aktualny host/port z backend/.env."""
        return env_runtime.load_flask_config(SQLITE_MODE, BACKEND_DIR, get_location_env_path)

    def refresh_quick_links(self):
        """Aktualizuje komendy przycisków Szybkiego Dostępu z aktualnego .env."""
        return env_runtime.refresh_quick_links(
            self,
            get_urls_func=lambda: env_runtime.get_urls(
                SQLITE_MODE, BACKEND_DIR, get_location_env_path, _read_backend_env_value
            ),
        )

    def get_env_mtime(self):
        """Zwraca czas modyfikacji właściwego .env używanego przez szybkie linki."""
        return env_runtime.get_env_mtime(SQLITE_MODE, BACKEND_DIR, get_location_env_path)

    def start_env_watcher(self):
        """Cyklicznie sprawdza zmiany w pliku .env (zoptymalizowane - mniej częste sprawdzanie)."""
        return env_runtime.start_env_watcher(self)

    def on_env_changed(self):
        """Reakcja na zmianę .env."""
        return env_runtime.on_env_changed(self)

    def setup_firewall_rule_for_port(self, port: int):
        """Konfiguruje regułę zapory Windows dla portu."""
        return firewall_runtime.setup_firewall_rule_for_port(port)

    def refresh_html_pages(self):
        """Automatycznie odświeża dane miejscowości poprzez wygenerowanie pliku JS."""
        try:
            site_generation_service.refresh_html_pages(
                get_active_location,
                generate_location_config_js,
                apply_homepage_template,
            )
        except Exception as e:
            _safe_print(f"⚠️ Nie udało się automatycznie zaktualizować danych miejscowości: {e}")

    def refresh_locations(self, force=False):
        """Odświeża listę miejscowości w menu rozwijanym (ultra zoptymalizowane)."""
        self._location_refresh_force = bool(force)
        location_runtime.refresh_locations(self, get_all_locations, set_active_location)

    def on_location_selected(self, event=None):
        """Obsługuje zmianę wybranej miejscowości (zoptymalizowana)."""
        location_runtime.on_location_selected(
            self,
            get_all_locations,
            set_active_location,
            refresh_data_files,
        )

    def open_location_manager(self):
        """Otwiera okno zarządzania miejscowościami."""
        location_runtime.open_location_manager(self)

    def open_database_wizard(self):
        """Otwiera narzędzie zarządzania bazą danych PostgreSQL."""
        location_runtime.open_database_wizard(self)

    def open_backup_manager(self):
        """Otwiera okno menedżera kopii zapasowych."""
        if any(key.endswith("_editor") for key in self.process_mgr.managed_processes):
            messagebox.showwarning("⚠️ Uwaga",
                                 "Zamknij wszystkie aktywne edytory przed zarządzaniem kopiami zapasowymi,\n"
                                 "aby uniknąć konfliktów plików.")
            return
        
        manager = BackupManager(self)
        self.wait_window(manager)

    def open_map_calibrator(self):
        """Otwiera okno kalibracji mapy."""
        if "backend" in self.process_mgr.managed_processes:
            messagebox.showwarning("Serwer aktywny",
                                 "Zatrzymaj serwer backend przed zmianą kalibracji.\n"
                                 "Zmiany zostaną zastosowane po ponownym uruchomieniu serwera.",
                                 parent=self)
        
        MapCalibrator(self)

    def open_db_engine_switcher(self):
        """Otwiera okno dialogowe zmiany silnika bazy danych (PostgreSQL ? SQLite)."""
        current_engine = _DB_ENGINE.name if _DB_ENGINE else "postgresql"
        return db_engine_switcher.open_db_engine_switcher(self, current_engine, COLORS)

    def restart_application(self):
        """Restartuje aplikację."""
        python = sys.executable
        script = os.path.abspath(__file__)
        subprocess.Popen([python, script])
        self._force_exit()

    def _force_exit(self):
        """Natychmiast kończy proces launchera i zamyka konsolę.

        Delegacja do ``shutdown_runtime.force_close_application``.
        """
        return shutdown_runtime.force_close_application(self)

    def _close_console_window(self):
        """Zamyka dedykowane okno konsoli py.exe na Windows.

        Delegacja do ``shutdown_runtime.close_console_window``.
        """
        return shutdown_runtime.close_console_window()

    def _on_root_destroy(self, event=None):
        """Awaryjnie kończy proces, gdy znika główne okno Tk.

        Delegacja do ``shutdown_runtime.handle_destroy_event``.
        """
        return shutdown_runtime.handle_destroy_event(self, event)

    def open_env_editor(self):
        """Otwiera edytor konfiguracji .env aktywnej miejscowości."""
        return env_runtime.open_env_editor(
            self,
            sqlite_mode=SQLITE_MODE,
            backend_dir=BACKEND_DIR,
            get_location_env_path=get_location_env_path,
            check_env_configuration=check_env_configuration,
            env_editor_cls=EnvEditor,
        )

    def open_admin_settings(self):
        """Otwiera okno ustawień administratora."""
        AdminSettings(self)

    def open_site_settings(self):
        """Otwiera okno ustawień witryny."""
        if "backend" in self.process_mgr.managed_processes:
            messagebox.showwarning("Serwer aktywny",
                                 "Zatrzymaj serwer backend przed zmianą ustawień witryny.\n"
                                 "Zmiany zostaną zastosowane po ponownym uruchomieniu serwera.",
                                 parent=self)
        
        SiteSettingsManager(self)

    def start_managed_process(self, key, name, cmd_override=None, extra_info=None, pre_spawn_log=None, tab_title=None):
        """Uruchamia zewnętrzny skrypt jako zarządzany proces."""
        self.process_mgr.start_managed_process(key, name, cmd_override=cmd_override, extra_info=extra_info, pre_spawn_log=pre_spawn_log, tab_title=tab_title)

    def stop_managed_process(self, key, force=False):
        """Zatrzymuje zarządzany proces."""
        self.process_mgr.stop_managed_process(key, force)

    def run_script_in_thread(self, script_info, script_name):
        """Uruchamia jednorazowy skrypt w wątku."""
        def target():
            self.log(f"⚡ Uruchamianie: {script_name}...\n")
            
            env = self._prepare_process_env()
            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "nt" else 0
            
            process = subprocess.Popen(
                [sys.executable, "-X", "utf8", "-u", script_info["path"]],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                cwd=script_info["cwd"], encoding="utf-8", errors="replace",
                creationflags=creation_flags, env=env
            )
            
            for line in iter(process.stdout.readline, ""):
                self.log(line)
            process.stdout.close()
            
            return_code = process.wait()
            status = "✅ Zakończono pomyślnie" if return_code == 0 else f"❌ Zakończono z błędem (kod: {return_code})"
            self.log(f"{status}: {script_name}\n")
        
        threading.Thread(target=target, daemon=True).start()

    def open_test_center_window(self):
        """Otwiera dedykowane okno Centrum Testów."""
        test_runtime.open_test_center_window(self, get_active_location_name)

    def copy_test_logs_to_clipboard(self):
        """Kopiuje zawartość konsoli testów do schowka."""
        test_runtime.copy_test_logs_to_clipboard(self)

    def save_test_logs_to_file(self):
        """Zapisuje zawartość konsoli testów do pliku."""
        test_runtime.save_test_logs_to_file(self)

    def run_selected_tests(self):
        """Uruchamia sekwencję wybranych testów."""
        test_runtime.run_selected_tests(self, get_active_location_name)

    def load_guardian_config(self):
        """Ładuje ustawienie Strażnika z pliku .guardian.env."""
        return guardian_runtime.load_guardian_config()

    def save_guardian_config(self):
        """Zapisuje ustawienie Strażnika do pliku .guardian.env."""
        return guardian_runtime.save_guardian_config(self)

    def run_proactive_health_check(self):
        """Uruchamia cichą weryfikację w tle dla kluczowych modułów."""
        return guardian_runtime.run_proactive_health_check(
            self,
            get_active_location_name,
            base_dir=BASE_DIR,
            colors=COLORS,
        )

    def get_guardian_status_snapshot(self):
        """Zwraca aktualny stan Strażnika do wykorzystania w panelach ustawień."""
        return guardian_runtime.get_guardian_status_snapshot(self, colors=COLORS)

    def get_database_diagnostics(self):
        """Zbiera podstawową diagnostykę aktywnego silnika bazy danych."""
        return build_database_diagnostics(self, get_active_location, read_env_config)


    def log_to_test_console(self, message):
        """Wypisuje wiadomość do konsoli testów w sposób bezpieczny dla wątków."""
        test_runtime.log_to_test_console(self, message)

    def run_pytest(self):
        """Fallback dla starych przycisków - otwiera okno z wybranymi unit testami."""
        test_runtime.run_pytest(self)

    def run_playwright_tests(self):
        """Fallback dla starych przycisków - otwiera okno z wybranymi e2e."""
        test_runtime.run_playwright_tests(self)

    def toggle_server(self, network_mode=False):
        """Przełącza stan serwera backend."""
        self.process_mgr.toggle_server(network_mode)

    def toggle_network_server(self):
        """Przełącza serwer sieciowy."""
        self.process_mgr.toggle_network_server()

    def start_network_server(self):
        """Uruchamia serwer FastAPI dostępny w sieci lokalnej."""
        self.process_mgr.start_network_server()

    def setup_firewall_rule(self):
        """Konfiguruje regułę firewall Windows."""
        return self.process_mgr.setup_firewall_rule()

    def show_firewall_instructions(self):
        """Wyświetla instrukcje ręcznej konfiguracji firewall."""
        self.process_mgr.show_firewall_instructions()

    def show_network_info_dialog(self, local_ip):
        """Wyświetla okno dialogowe z informacjami o dostępie sieciowym."""
        self.process_mgr.show_network_info_dialog(local_ip)

    def on_closing(self):
        """Obsługuje zdarzenie zamknięcia głównego okna.

        Delegacja do ``shutdown_runtime.request_graceful_close``.
        """
        return shutdown_runtime.request_graceful_close(self)

    def cleanup_temp_files(self):
        """Usuwa tymczasowe pliki utworzone przez launcher.

        Delegacja do ``shutdown_runtime.cleanup_temp_files``.
        """
        return shutdown_runtime.cleanup_temp_files(BACKEND_DIR)

    def on_window_focus(self, event=None):
        """Przywraca ikonę po powrocie fokusu do okna."""
        return window_runtime.on_window_focus(self, event)

    def _prepare_process_env(self):
        """Przygotowuje środowisko dla procesu."""
        from launcher.utils import prepare_process_env
        try:
            active_loc = get_active_location_name()
        except Exception:
            active_loc = None
        return prepare_process_env(active_loc, read_env_config)

    def _prepare_command(self, key, script_info):
        """Przygotowuje komendę do uruchomienia."""
        from launcher.utils import prepare_command
        return prepare_command(key, script_info)

# =============================================================================
# KLASY OKIEN DIALOGOWYCH
# =============================================================================

PhotosManagerDialog = _PhotosManagerDialog


AddEditLocationDialog = _AddEditLocationDialog


MapCalibrator = _MapCalibrator
CalibrationInstructions = _CalibrationInstructions
EnvEditor = _EnvEditor
DisplaySettingsDialog = _DisplaySettingsDialog
AdminSettings = _AdminSettings



def create_and_migrate_location_database(location_name, progress_callback=None):
    return location_migration_service.create_and_migrate_location_database(
        location_name,
        progress_callback=progress_callback,
    )


choose_database_engine = _choose_database_engine
setup_postgres_config = _setup_postgres_config

BackupManager = _BackupManager
DatabaseWizard = _DatabaseWizard
LocationManager = _LocationManager
ProgressDialog = _ProgressDialog
SiteSettingsManager = _SiteSettingsManager
IconChooserWindow = _IconChooserWindow
TemplateChangeDialog = _TemplateChangeDialog
InstructionsWindow = _InstructionsWindow

# =============================================================================
# PUNKT WEJŚCIA APLIKACJI
# =============================================================================
if __name__ == "__main__":
    """Główny punkt wejścia aplikacji."""
    app = AppLauncher()
    app.mainloop()
    # Fallback: jeśli mainloop zakończy się bez przejścia przez on_closing(),
    # zakończ proces natychmiast, żeby konsola nie wisiała po zamknięciu GUI.
    try:
        shutdown_runtime.shutdown_after_mainloop(app)
    except Exception:
        try:
            shutdown_runtime.close_console_window()
        except Exception:
            pass
    os._exit(0)
