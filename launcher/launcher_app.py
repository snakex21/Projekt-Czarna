import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import subprocess
import threading
import os
import socket
import sys
import webbrowser
import signal
import platform
import queue
import zipfile
from datetime import datetime
import shutil
import tkinter.font as tkfont
import ctypes

# --- KONFIGURACJA DPI DLA WINDOWS ---

# Ustawienie świadomości DPI dla systemów Windows, aby interfejs był ostry
# na monitorach o wysokiej rozdzielczości (4K, wysokie DPI).
if platform.system() == "Windows":
    try:  # Windows ≥ 8.1
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):  # Windows 7 lub brak modułu
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass

# --- KONFIGURACJA ŚCIEŻEK PROJEKTU ---

# Definicje kluczowych ścieżek w strukturze projektu.
# BASE_DIR to katalog główny projektu (jeden poziom wyżej od tools/).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ścieżka do folderu z kopiami zapasowymi.
BACKUP_FOLDER = os.path.join(BASE_DIR, "backup")

# Ścieżka do katalogu backend z serwerem Flask.
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

# Ścieżka do katalogu z narzędziami deweloperskimi.
TOOLS_DIR = os.path.join(BASE_DIR, "tools")

# Ścieżka do katalogu z zasobami projektu.
ASSETS_FOLDER = os.path.join(BASE_DIR, "assets")

# Ścieżka do folderu ze skanami protokołów.
PROTOKOLY_FOLDER = os.path.join(ASSETS_FOLDER, "protokoly")

# --- KONFIGURACJA PLIKÓW DANYCH ---

# Konfiguracja plików danych, które podlegają operacjom importu/eksportu i tworzenia kopii zapasowych.
# Każdy wpis definiuje ścieżkę do pliku, jego czytelną nazwę oraz ewentualne pliki powiązane.
DATA_FILES = {
    "owners": {
        "path": os.path.join(BACKUP_FOLDER, "owner_data_to_import.json"),
        "name": "Właściciele i Demografia",
        "related": [os.path.join(BACKUP_FOLDER, "demografia.json")],
    },
    "parcels": {
        "path": os.path.join(BACKUP_FOLDER, "parcels_data.json"),
        "name": "Działki (Geometria)",
        "related": [],
    },
    "genealogy": {
        "path": os.path.join(BACKUP_FOLDER, "genealogia.json"),
        "name": "Genealogia",
        "related": [],
    },
}

# --- KONFIGURACJA ADRESÓW URL ---

# Słownik przechowujący adresy URL do kluczowych widoków aplikacji webowej.
URLS = {
    "strona_glowna": "http://127.0.0.1:5000/strona_glowna/index.html",
    "mapa": "http://127.0.0.1:5000/mapa/mapa.html",
    "admin": "http://127.0.0.1:5000/admin",
    "genealogy_editor": "http://127.0.0.1:5001/",
}

# --- KONFIGURACJA SKRYPTÓW ---

# Słownik konfiguracyjny dla skryptów zewnętrznych uruchamianych przez launcher.
# 'path' to ścieżka do pliku, a 'cwd' to katalog roboczy, w którym skrypt powinien być uruchomiony.
SCRIPTS = {
    "backend": {
        "path": os.path.join(BACKEND_DIR, "app.py"), 
        "cwd": BACKEND_DIR
    },
    "migration": {
        "path": os.path.join(BACKEND_DIR, "migrate_data.py"),
        "cwd": BACKEND_DIR,
    },
    "tests": {
        "path": "-m",
        "args": ["pytest", "tests", "-q"],   
        "cwd": BACKEND_DIR,
    },
    "owner_editor": {
        "path": os.path.join(TOOLS_DIR, "owner_editor.py"),
        "cwd": TOOLS_DIR,
    },
    "parcel_editor": {
        "path": os.path.join(TOOLS_DIR, "parcel_editor", "parcel_editor_app.py"),
        "cwd": os.path.join(TOOLS_DIR, "parcel_editor"),
    },
    "genealogy_editor": {
        "path": os.path.join(TOOLS_DIR, "genealogy_editor", "editor_app.py"),
        "cwd": os.path.join(TOOLS_DIR, "genealogy_editor"),
    },
}


# --- STAŁE STYLIZACJI INTERFEJSU ---

# Definicje kolorów dla przycisków i elementów interfejsu
COLORS = {
    'primary': '#0d6efd',    # Niebieski
    'success': '#198754',    # Zielony 
    'danger': '#dc3545',     # Czerwony
    'warning': '#ffc107',    # Żółty
    'info': '#0dcaf0',       # Jasnoniebieski
    'secondary': '#6c757d',  # Szary
    'dark': '#212529',       # Ciemnoszary
    'light': '#f8f9fa',      # Jasnoszary
}

# --- FUNKCJE POMOCNICZE SIECIOWE ---

def get_local_ip():
    """
    Pobiera lokalny adres IP komputera w sieci.
    Zwraca localhost jeśli nie może określić IP.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"

# --- FUNKCJE ZARZĄDZANIA KONFIGURACJĄ ---

def check_env_configuration():
    """
    Sprawdza i konfiguruje plik .env dla backendu.
    Tworzy plik .env jeśli nie istnieje, kopiując z .env.example.
    """
    env_path = os.path.join(BACKEND_DIR, ".env")
    env_example_path = os.path.join(BACKEND_DIR, ".env.example")
    
    # Jeśli .env nie istnieje, spróbuj utworzyć z przykładu
    if not os.path.exists(env_path):
        if os.path.exists(env_example_path):
            try:
                shutil.copy(env_example_path, env_path)
                print("✅ Utworzono plik .env z przykładowej konfiguracji")
                return True
            except Exception as e:
                print(f"⚠️ Nie można utworzyć pliku .env: {e}")
                return False
        else:
            # Utwórz podstawowy plik .env
            try:
                default_env_content = """# --- KONFIGURACJA BAZY DANYCH POSTGRESQL ---
DB_HOST=localhost
DB_NAME=mapa_czarna_db
DB_USER=postgres
DB_PASSWORD=1234
DB_PORT=5432

# --- KONFIGURACJA SERWERA FLASK ---
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
FLASK_SECRET_KEY=change-me-once

# --- ADMIN / BEZPIECZEŃSTWO ---
ADMIN_AUTH_ENABLED=0
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=
"""
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.write(default_env_content)
                print("✅ Utworzono domyślny plik .env")
                return True
            except Exception as e:
                print(f"⚠️ Nie można utworzyć pliku .env: {e}")
                return False
    return True

def get_flask_config():
    """
    Odczytuje konfigurację Flask z pliku .env.
    Zwraca słownik z host i port.
    """
    env_path = os.path.join(BACKEND_DIR, ".env")
    config = {
        'host': '127.0.0.1',
        'port': '5000'
    }
    
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key == 'FLASK_HOST':
                            config['host'] = value
                        elif key == 'FLASK_PORT':
                            config['port'] = value
        except:
            pass
    
    return config
        
# --- GŁÓWNA KLASA APLIKACJI ---

class AppLauncher(tk.Tk):
    """
    Główna klasa aplikacji launchera.
    Zarządza uruchamianiem i monitorowaniem wszystkich komponentów projektu
    oraz zapewnia interfejs graficzny do kontroli procesów.
    """

    def __init__(self):
        """Inicjalizacja głównego okna aplikacji i wszystkich komponentów."""
        super().__init__()
        
        # --- KONFIGURACJA OKNA GŁÓWNEGO ---
        
        self.title("🗺️ Centrum Zarządzania - System Mapy Katastralnej")
        
        # Automatyczne dostosowanie do rozmiaru ekranu i DPI
        self.setup_window_geometry()

        # --- INICJALIZACJA ZMIENNYCH STANU ---
        
        # Słownik do przechowywania informacji o uruchomionych procesach.
        self.managed_processes = {}
        
        # Kolejka do bezpiecznej komunikacji między wątkami a głównym wątkiem GUI.
        self.event_queue = queue.Queue()

        # --- KONFIGURACJA STYLÓW I CZCIONEK ---
        
        self.setup_styles()
        
        # --- SPRAWDZENIE KONFIGURACJI ---
        
        # Upewnienie się, że plik .env istnieje przed uruchomieniem
        check_env_configuration()

        # --- UTWORZENIE INTERFEJSU ---
        
        self.create_widgets()

        # Snapshot ostatniego znanego portu z pliku .env.
        # Używany do wykrywania zmian konfiguracji (np. zmiana FLASK_PORT),
        # aby móc zaproponować automatyczny restart serwera backend.
        self._last_port = self.load_flask_config().get("port")
        # --- KONFIGURACJA ZDARZEŃ ---
        
        # Obsługa zamykania okna
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Uruchomienie cyklicznego sprawdzania kolejki zdarzeń.
        self.process_queue()

    def setup_window_geometry(self):
        """
        Inteligentnie dostosowuje rozmiar okna do ekranu i DPI.
        Obsługuje różne rozdzielczości od HD do 4K.
        """
        # Pobranie rzeczywistych wymiarów ekranu
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Pobranie DPI i obliczenie skali
        dpi = self.winfo_fpixels("1i")
        scale_factor = dpi / 96  # 96 DPI to standard (100% w Windows)
        
        # Określenie typu ekranu na podstawie rozdzielczości
        if screen_width <= 1920:  # HD/Full HD
            window_width = min(int(screen_width * 0.85), 1400)
            window_height = min(int(screen_height * 0.85), 850)
        elif screen_width <= 2560:  # 2K/QHD
            window_width = min(int(screen_width * 0.75), 1600)
            window_height = min(int(screen_height * 0.80), 900)
        else:  # 4K i większe
            window_width = min(int(screen_width * 0.65), 1800)
            window_height = min(int(screen_height * 0.75), 1000)
        
        # Dostosowanie do skalowania systemu
        if scale_factor > 1.25:  # Wysokie DPI (125% i więcej)
            window_width = int(window_width / scale_factor * 1.2)
            window_height = int(window_height / scale_factor * 1.2)
        
        # Minimalne rozmiary
        min_width = max(1000, int(900 * scale_factor))
        min_height = max(700, int(650 * scale_factor))
        
        # Upewnienie się, że okno nie jest za małe
        window_width = max(window_width, min_width)
        window_height = max(window_height, min_height)
        
        # Wycentrowanie okna
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Ustawienie geometrii
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(min_width, min_height)
        
        # Zapisanie informacji o skalowaniu dla późniejszego użycia
        self.scale_factor = scale_factor
        self.is_high_dpi = scale_factor > 1.25

    def center_window(self):
        """Centruje okno aplikacji na ekranie."""
        self.update_idletasks()
        
        # Pobranie wymiarów ekranu
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Pobranie wymiarów okna - zwiększone
        window_width = 1400
        window_height = 900
        
        # Obliczenie pozycji
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def setup_styles(self):
        """
        Konfiguruje style i czcionki dla całej aplikacji.
        Automatycznie dostosowuje do DPI monitora.
        """
        
        # --- SKALOWANIE DPI ---
        
        # Pobranie skali DPI
        dpi = self.winfo_fpixels("1i")
        scale = dpi / 96
        
        # Ustawienie skalowania Tkinter
        self.tk.call("tk", "scaling", scale)
        
        # --- KONFIGURACJA CZCIONEK ---
        
        # Inteligentne obliczenie rozmiaru czcionki
        if scale <= 1.0:  # Standardowe DPI
            base_size = 10
        elif scale <= 1.25:  # 125% skalowanie
            base_size = 10
        elif scale <= 1.5:  # 150% skalowanie
            base_size = 11
        else:  # Wyższe skalowanie
            base_size = 12
        
        # Aktualizacja domyślnej czcionki
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=base_size)
        
        # --- KONFIGURACJA STYLÓW TTK ---
        
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        
        # Dostosowany padding dla przycisków
        button_padding = int(6 * scale) if scale > 1.25 else 8
        
        # Style dla przycisków
        self.style.configure(
            "TButton", 
            padding=button_padding,
            relief="flat", 
            font=("Segoe UI", base_size)
        )
        
        # Kolory przycisków (bez zmian)
        self.style.configure("Primary.TButton", foreground="white", background=COLORS['primary'])
        self.style.map("Primary.TButton", background=[('active', '#0b5ed7'), ('pressed', '#0a58ca')])
        
        self.style.configure("Success.TButton", foreground="white", background=COLORS['success'])
        self.style.map("Success.TButton", background=[('active', '#157347'), ('pressed', '#146c43')])
        
        self.style.configure("Danger.TButton", foreground="white", background=COLORS['danger'])
        self.style.map("Danger.TButton", background=[('active', '#bb2d3b'), ('pressed', '#b02a37')])
        
        self.style.configure("Info.TButton", foreground="white", background=COLORS['info'])
        self.style.map("Info.TButton", background=[('active', '#06b6d4'), ('pressed', '#0891b2')])
        
        self.style.configure("Warning.TButton", foreground="black", background=COLORS['warning'])
        self.style.map("Warning.TButton", background=[('active', '#ffca2c'), ('pressed', '#ffc720')])
        
        # Styl dla linków
        self.style.configure("Link.TLabel", foreground=COLORS['primary'], font=("Segoe UI", base_size, "underline"))
        
        # Styl dla nagłówków
        self.style.configure("Heading.TLabel", font=("Segoe UI", base_size + 2, "bold"))
        
        # Konfiguracja wysokości wierszy Treeview
        row_height = int(base_size * 2.2)
        self.style.configure("Treeview", rowheight=row_height, font=("Segoe UI", base_size))
        self.style.configure("Treeview.Heading", font=("Segoe UI", base_size, "bold"))
        
        # Zapisanie rozmiaru bazowego
        self.base_font_size = base_size

    def create_console_widget(self, parent):
        """
        Tworzy widget konsoli z ciemnym motywem i odpowiednim rozmiarem czcionki.
        
        Args:
            parent: Widget rodzica dla konsoli
            
        Returns:
            scrolledtext.ScrolledText: Widget konsoli
        """
        # Użycie zapisanego rozmiaru czcionki
        console_font_size = self.base_font_size
        
        console = scrolledtext.ScrolledText(
            parent, 
            wrap=tk.WORD, 
            bg="#1e1e1e",
            fg="#e0e0e0",
            font=("Consolas", console_font_size),
            insertbackground="#ffffff",
            selectbackground="#3a3a3a",
            selectforeground="#ffffff",
            height=10  # Stała minimalna wysokość
        )
        console.pack(fill=tk.BOTH, expand=True)
        console.configure(state="disabled")
        return console

    def process_queue(self):
        """
        Przetwarza zdarzenia z kolejki w pętli głównej Tkinter.
        Zapewnia bezpieczną komunikację między wątkami a GUI.
        """
        try:
            # Pętla odczytuje wszystkie oczekujące zdarzenia.
            while True:
                key, event_type = self.event_queue.get_nowait()
                if event_type == "finished":
                    self.handle_process_finished(key)
        except queue.Empty:
            # Kolejka jest pusta, nic więcej do zrobienia w tym cyklu.
            pass
        finally:
            # Ponowne wywołanie funkcji po 100ms, tworząc pętlę.
            self.after(100, self.process_queue)

    def handle_process_finished(self, key):
        """
        Obsługuje zdarzenie zakończenia procesu potomnego.
        Aktualizuje interfejs i czyści zasoby związane z procesem.
        
        Args:
            key: Identyfikator zakończonego procesu
        """
        if key in self.managed_processes:
            info = self.managed_processes[key]
            name = info["name"]
            
            # Logowanie informacji o zakończeniu
            msg_finished = f"--- Proces '{name}' zakończył działanie ---\n"
            self.log(msg_finished, console=info["console"])
            self.log(msg_finished)

            # Usunięcie zakładki z konsolą i wpisu z listy procesów.
            self.notebook.forget(info["tab_frame"])
            del self.managed_processes[key]
            self.update_processes_ui()

            # Specjalna obsługa dla serwera backend
            if key == "backend":
                # Przywróć etykiety przycisków
                self.server_btn.config(
                    text="🚀 Uruchom Serwer Backend", 
                    style="Success.TButton"
                )
                self.network_server_btn.config(
                    text="🌐 Uruchom Serwer Sieciowy",
                    style="Info.TButton"
                )
                # Jeśli to był tryb sieciowy – pokaż podpowiedź
                if info.get("network_mode"):
                    messagebox.showwarning(
                        "Serwer sieciowy się wyłączył",
                        "Proces zakończył się niespodziewanie.\n\n"
                        "Najczęstsza przyczyna: błąd w pliku _network_server_wrapper.py.\n"
                        "Po aktualizacji launchera spróbuj ponownie.\n\n"
                        "Diagnostyka: uruchom ręcznie w folderze backend:\n"
                        "python _network_server_wrapper.py"
                    )

    def create_widgets(self):
        """
        Tworzy kompletny interfejs użytkownika aplikacji.
        Używa elastycznego układu dostosowanego do różnych rozmiarów ekranu.
        """
        
        # --- GŁÓWNY KONTENER ---
        
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Używamy pack zamiast grid dla lepszej elastyczności
        
        # --- NAGŁÓWEK APLIKACJI ---
        
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(
            header_frame,
            text="🗺️ System Zarządzania Mapą Katastralną",
            style="Heading.TLabel",
            font=("Segoe UI", self.base_font_size + 4, "bold")
        )
        title_label.pack(side=tk.LEFT)
        
        status_label = ttk.Label(
            header_frame,
            text="Status: Gotowy",
            foreground=COLORS['success']
        )
        status_label.pack(side=tk.RIGHT, padx=10)

        # --- SEKCJA GŁÓWNYCH OPERACJI ---
        
        operations_frame = ttk.LabelFrame(
            main_frame, 
            text="⚙️ Operacje Główne", 
            padding="10"
        )
        operations_frame.pack(fill=tk.X, pady=5)
        
        # PIERWSZY RZĄD przycisków operacyjnych
        ops_buttons_row1 = ttk.Frame(operations_frame)
        ops_buttons_row1.pack(fill=tk.X, pady=(0, 5))
        
        # Przyciski pierwszego rzędu - bardziej przestronne
        self.server_btn = ttk.Button(
            ops_buttons_row1,
            text="🚀 Uruchom Serwer Backend",
            command=self.toggle_server,
            style="Success.TButton"
        )
        self.server_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.network_server_btn = ttk.Button(
            ops_buttons_row1,
            text="🌐 Uruchom Serwer Sieciowy",
            command=self.toggle_network_server,
            style="Info.TButton"
        )
        self.network_server_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(
            ops_buttons_row1,
            text="🔄 Migruj Dane do Bazy",
            command=lambda: self.run_script_in_thread(
                SCRIPTS["migration"], "Skrypt Migracyjny"
            ),
            style="Info.TButton"
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # DRUGI RZĄD przycisków operacyjnych
        ops_buttons_row2 = ttk.Frame(operations_frame)
        ops_buttons_row2.pack(fill=tk.X)
        
        # Przyciski drugiego rzędu - teraz mają więcej miejsca
        ttk.Button(
            ops_buttons_row2,
            text="💾 Menedżer Kopii",
            command=self.open_backup_manager,
            style="Primary.TButton"
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(
            ops_buttons_row2,
            text="⚙️ Konfiguracja DB",
            command=self.open_env_editor,
            style="Secondary.TButton"
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(
            ops_buttons_row2,
            text="🔐 Ustawienia Administratora",
            command=self.open_admin_settings,
            style="Warning.TButton"
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(
            ops_buttons_row2,
            text="🛡️ Bezpieczeństwo",
            command=self.open_security_manager,
            style="Primary.TButton"
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # --- SEKCJA NARZĘDZI DEWELOPERSKICH ---
        
        tools_frame = ttk.LabelFrame(
            main_frame, 
            text="🛠️ Narzędzia Deweloperskie", 
            padding="10"
        )
        tools_frame.pack(fill=tk.X, pady=5)

        # Kontener na przyciski edytorów
        editors_container = ttk.Frame(tools_frame)
        editors_container.pack(fill=tk.X)
        
        # Przyciski edytorów
        editor_buttons = [
            ("👥 Edytor Właścicieli", "owner_editor"),
            ("🗺️ Edytor Działek", "parcel_editor"),
            ("🌳 Edytor Genealogii", "genealogy_editor"),
        ]
        
        for text, key in editor_buttons:
            btn = ttk.Button(
                editors_container,
                text=text,
                command=lambda k=key, n=text: self.start_managed_process(k, n),
                style="Primary.TButton"
            )
            btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Przycisk do uruchamiania testów jednostkowych
        ttk.Button(
            editors_container,
            text="🧪 Uruchom Testy Jednostkowe",
            command=self.run_pytest,   
            style="Info.TButton"
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # --- SEKCJA SZYBKIEGO DOSTĘPU ---
        links_frame = ttk.LabelFrame(
            main_frame,
            text="🌐 Szybki Dostęp (wymaga uruchomionego serwera)",
            padding="10"
        )
        links_frame.pack(fill=tk.X, pady=5)
        
        # Kontener na linki
        links_container = ttk.Frame(links_frame)
        links_container.pack(fill=tk.X)
        
        # Zapamiętujemy przyciski, aby móc je „przeprogramować" po zmianie .env
        self.quick_link_buttons = []

        # Utworzenie przycisków (na razie puste komendy – uzupełnimy w refresh_quick_links)
        link_defs = [
            ("🏠 Strona Główna", "/strona_glowna/index.html", "Success"),
            ("🗺️ Mapa Interaktywna", "/mapa/mapa.html", "Info"),
            ("⚙️ Panel Administracyjny", "/admin", "Warning"),
        ]
        for text, path, style in link_defs:
            btn = ttk.Button(
                links_container,
                text=text,
                style=f"{style}.TButton"
            )
            btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            self.quick_link_buttons.append((btn, path))

        # Pierwsze odświeżenie linków i start obserwatora .env
        self._env_mtime = None
        self.refresh_quick_links()
        self.start_env_watcher()

        # --- SEKCJA PROCESÓW ---
        
        self.processes_frame = ttk.LabelFrame(
            main_frame, 
            text="📊 Uruchomione Procesy", 
            padding="10"
        )
        self.processes_frame.pack(fill=tk.X, pady=5)
        self.update_processes_ui()

        # --- SEKCJA KONSOL ---
        
        console_container = ttk.LabelFrame(
            main_frame, 
            text="💻 Konsole Wyjściowe", 
            padding="10"
        )
        console_container.pack(fill=tk.BOTH, expand=True, pady=5)

        # Notebook z zakładkami dla konsol
        self.notebook = ttk.Notebook(console_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Główna konsola launchera
        self.main_console_frame = ttk.Frame(self.notebook)
        self.main_console = self.create_console_widget(self.main_console_frame)
        self.notebook.add(self.main_console_frame, text="🏠 Launcher")
        
        # Wiadomość powitalna
        self.log("=" * 60 + "\n")
        self.log("🗺️ System Zarządzania Mapą Katastralną - Uruchomiony\n")
        self.log("=" * 60 + "\n")
        self.log("ℹ️ Witaj w centrum zarządzania projektem!\n")
        self.log("ℹ️ Użyj przycisków powyżej, aby uruchomić komponenty.\n\n")

    def log(self, message, console=None):
        """
        Wypisuje wiadomość do określonej konsoli.
        
        Args:
            message: Tekst do wyświetlenia
            console: Widget konsoli (domyślnie główna konsola)
        """
        target_console = console or self.main_console
        target_console.configure(state="normal")
        target_console.insert(tk.END, message)
        target_console.see(tk.END)
        target_console.configure(state="disabled")

    def update_processes_ui(self):
        """
        Odświeża listę uruchomionych procesów w interfejsie.
        Wyświetla procesy z informacjami o PID i przyciskami akcji.
        """
        # Czyszczenie obecnej listy
        for widget in self.processes_frame.winfo_children():
            widget.destroy()

        if not self.managed_processes:
            # Komunikat gdy brak procesów
            empty_label = ttk.Label(
                self.processes_frame, 
                text="📭 Brak uruchomionych procesów",
                foreground=COLORS['secondary']
            )
            empty_label.pack(pady=10)
            return

        # Tworzenie listy procesów
        for key, info in self.managed_processes.items():
            proc_frame = ttk.Frame(self.processes_frame)
            proc_frame.pack(fill=tk.X, pady=3, padx=5)
            
            # Ikona statusu i informacje o procesie
            status_text = f"🟢 {info['name']} (PID: {info['process'].pid})"
            ttk.Label(
                proc_frame, 
                text=status_text,
                font=("Segoe UI", 10)
            ).pack(side=tk.LEFT)
            
            # Przycisk zatrzymania procesu
            ttk.Button(
                proc_frame,
                text="⏹️ Zatrzymaj",
                style="Danger.TButton",
                command=lambda k=key: self.stop_managed_process(k),
                width=12
            ).pack(side=tk.RIGHT, padx=5)

    def load_flask_config(self):
        """Czyta aktualny host/port z backend/.env."""
        cfg = get_flask_config()
        # sanity – port jako int/string
        try:
            cfg['port'] = str(int(cfg.get('port', '5000')))
        except:
            cfg['port'] = '5000'
        cfg['host'] = cfg.get('host', '127.0.0.1')
        return cfg

    def refresh_quick_links(self):
        """Aktualizuje komendy przycisków Szybkiego Dostępu na podstawie .env."""
        self.current_flask_config = self.load_flask_config()
        base_url = f"http://{self.current_flask_config['host']}:{self.current_flask_config['port']}"
        for btn, path in getattr(self, "quick_link_buttons", []):
            url = base_url + path
            btn.configure(command=lambda u=url: webbrowser.open_new_tab(u))

    def get_env_mtime(self):
        """Zwraca mtime pliku backend/.env (albo None)."""
        env_path = os.path.join(BACKEND_DIR, ".env")
        try:
            return os.path.getmtime(env_path)
        except OSError:
            return None

    def start_env_watcher(self):
        """Cyklicznie sprawdza, czy .env się zmienił, i reaguje."""
        def _tick():
            try:
                mtime = self.get_env_mtime()
                if self._env_mtime is None:
                    self._env_mtime = mtime
                elif mtime is not None and mtime != self._env_mtime:
                    self._env_mtime = mtime
                    self.on_env_changed()
            finally:
                # sprawdzaj co 2000 ms
                self.after(2000, _tick)
        _tick()

    def on_env_changed(self):
        """Reakcja na zmianę .env: odśwież linki i (opcjonalnie) restart backendu."""
        # snapshot „starego” portu i trybu zanim odświeżymy linki
        old_port = getattr(self, "_last_port", None)
        was_running = "backend" in self.managed_processes
        was_network = self.managed_processes.get("backend", {}).get("network_mode", False)

        # odczytaj nową konfigurację + podmień komendy przycisków
        self.refresh_quick_links()
        new_port = self.current_flask_config.get("port")
        self._last_port = new_port  # zaktualizuj snapshot

        self.log(f"🔎 Wykryto zmianę .env – port {old_port} ➜ {new_port}\n")

        # jeśli backend nie działa, tylko zaktualizowaliśmy linki
        if not was_running or not old_port or not new_port or old_port == new_port:
            return

        # zapytać o restart
        if messagebox.askyesno(
            "Wykryto zmianę portu",
            f"Zmieniono port z {old_port} na {new_port}.\n\n"
            "Zrestartować serwer backend, aby zastosować nowy port?"
        ):
            # 1) zatrzymaj
            self.stop_managed_process("backend")

            # 2) przygotuj firewall dla nowego portu (Windows) – tylko sieciowy ma znaczenie
            try:
                self.setup_firewall_rule_for_port(int(new_port))
            except Exception:
                pass

            # 3) wystartuj ponownie w tym samym trybie, z lekkim opóźnieniem
            def _restart():
                if was_network:
                    self.start_network_server()   # wróć do trybu LAN
                else:
                    self.start_managed_process("backend", "Serwer Backend (Lokalny)")
                    self.server_btn.config(text="⏹️ Zatrzymaj Serwer (Lokalny)", style="Danger.TButton")

            # daj OS 400–600 ms na domknięcie procesu i zwolnienie portu
            self.after(600, _restart)

    def setup_firewall_rule_for_port(self, port: int):
        """Wariant reguły zapory podany konkretnym portem (używane przy hot‑change)."""
        if platform.system() != "Windows":
            return
        rule_name = f"Flask Server Port {port}"
        check_cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return  # już jest
        add_cmd = (
            'netsh advfirewall firewall add rule '
            f'name="{rule_name}" dir=in action=allow protocol=TCP localport={port} enable=yes profile=any'
        )
        subprocess.run(add_cmd, shell=True)

    def open_backup_manager(self):
        """
        Otwiera okno menedżera kopii zapasowych.
        Sprawdza czy nie ma konfliktów z otwartymi edytorami.
        """
        # Sprawdzenie otwartych edytorów
        if any(key.endswith("_editor") for key in self.managed_processes):
            messagebox.showwarning(
                "⚠️ Uwaga",
                "Zamknij wszystkie aktywne edytory przed zarządzaniem kopiami zapasowymi,\n"
                "aby uniknąć konfliktów plików.",
                icon="warning"
            )
            return
        
        # Utworzenie i wyświetlenie okna menedżera
        manager = BackupManager(self)
        self.wait_window(manager)

    def open_env_editor(self):
        """
        Otwiera edytor konfiguracji .env w osobnym oknie.
        Pozwala na łatwą edycję parametrów połączenia z bazą danych.
        """
        env_path = os.path.join(BACKEND_DIR, ".env")
        
        # Sprawdź czy plik istnieje
        if not os.path.exists(env_path):
            if not check_env_configuration():
                messagebox.showerror(
                    "❌ Błąd",
                    "Nie można utworzyć pliku konfiguracyjnego .env"
                )
                return
        
        # Okno edytora
        editor_window = tk.Toplevel(self)
        # ustal minimalny rozmiar po załadowaniu
        editor_window.update_idletasks()
        w, h = 700, 500
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_w = self.winfo_width()
        parent_h = self.winfo_height()
        x = parent_x + (parent_w - w) // 2
        y = parent_y + (parent_h - h) // 2
        editor_window.geometry(f"{w}x{h}+{x}+{y}")
        editor_window.minsize(600, 420)
        editor_window.title("⚙️ Edytor Konfiguracji Bazy Danych")
        editor_window.geometry("700x500")
        
        # Główna ramka
        main_frame = ttk.Frame(editor_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Nagłówek
        ttk.Label(
            main_frame,
            text="📝 Edycja pliku konfiguracyjnego .env",
            font=("Segoe UI", 12, "bold")
        ).pack(pady=(0, 10))
        
        # Informacja
        info_text = (
            "Ten plik zawiera konfigurację połączenia z bazą danych PostgreSQL.\n"
            "Po wprowadzeniu zmian zapisz plik i zrestartuj serwer backend."
        )
        ttk.Label(
            main_frame,
            text=info_text,
            wraplength=650,
            foreground="#666666"
        ).pack(pady=(0, 10))
        
        # Edytor tekstu
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_editor = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            height=15
        )
        text_editor.pack(fill=tk.BOTH, expand=True)
        
        # Wczytaj zawartość pliku
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                content = f.read()
                text_editor.insert('1.0', content)
        except Exception as e:
            messagebox.showerror(
                "❌ Błąd",
                f"Nie można wczytać pliku .env:\n{e}",
                parent=editor_window
            )
            editor_window.destroy()
            return
        
        # Przyciski
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def save_env():
            """Zapisuje zmiany do pliku .env"""
            try:
                content = text_editor.get('1.0', 'end-1c')
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                # natychmiastowe odświeżenie linków (watcher i tak to wykryje, ale będzie szybciej)
                self.on_env_changed()

                messagebox.showinfo(
                    "✅ Sukces",
                    "Konfiguracja została zapisana.\n"
                    "Jeśli zmieniłeś port – pojawi się pytanie o restart serwera.",
                    parent=editor_window
                )
            except Exception as e:
                messagebox.showerror(
                    "❌ Błąd",
                    f"Nie można zapisać pliku:\n{e}",
                    parent=editor_window
                )
        
        def reset_defaults():
            """Przywraca domyślną konfigurację"""
            if messagebox.askyesno(
                "⚠️ Potwierdzenie",
                "Czy na pewno chcesz przywrócić domyślną konfigurację?",
                parent=editor_window
            ):
                default_content = """# --- KONFIGURACJA BAZY DANYCH POSTGRESQL ---
DB_HOST=localhost
DB_NAME=mapa_czarna_db
DB_USER=postgres
DB_PASSWORD=1234
DB_PORT=5432

# --- KONFIGURACJA SERWERA FLASK ---
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
"""
                text_editor.delete('1.0', tk.END)
                text_editor.insert('1.0', default_content)
        
        ttk.Button(
            button_frame,
            text="💾 Zapisz zmiany",
            command=save_env,
            style="Success.TButton"
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="🔄 Przywróć domyślne",
            command=reset_defaults,
            style="Warning.TButton"
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="❌ Zamknij",
            command=editor_window.destroy,
            style="Secondary.TButton"
        ).pack(side=tk.RIGHT, padx=5)

    def open_admin_settings(self):
        """Okno do włączania/wyłączania logowania admina i ustawiania hasła."""
        import re
        from tkinter import StringVar, BooleanVar
        try:
            from werkzeug.security import generate_password_hash
        except Exception:
            messagebox.showerror("Brak zależności", "Brakuje pakietu Werkzeug (instalowany z Flask).")
            return

        env_path = os.path.join(BACKEND_DIR, ".env")
        if not os.path.exists(env_path):
            if not check_env_configuration():
                messagebox.showerror("❌ Błąd", "Nie można utworzyć pliku .env")
                return

        # Wczytaj istniejące wartości
        env = {}
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k,v = line.split('=',1)
                    env[k.strip()] = v.strip()

        enabled = BooleanVar(value=(env.get('ADMIN_AUTH_ENABLED','0') == '1'))
        username = StringVar(value=env.get('ADMIN_USERNAME','admin'))
        # hasła nie pokazujemy – tylko pole do wpisania nowego (opcjonalnie)
        password = StringVar(value='')

        win = tk.Toplevel(self)
        win.title("🔐 Ustawienia Administratora")
        win.transient(self)
        win.grab_set()
        
        # --- WYCENTROWANIE OKNA ---
        # Najpierw ustawiamy minimalny rozmiar
        win.minsize(460, 260)
        
        # Czekamy na aktualizację rozmiaru okna
        win.update_idletasks()
        
        # Ustawiamy rozmiar okna
        window_width = 500
        window_height = 300
        
        # Pobieramy pozycję i rozmiar okna rodzica (głównego okna aplikacji)
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_width = self.winfo_width()
        parent_height = self.winfo_height()
        
        # Obliczamy pozycję dla wycentrowania względem okna rodzica
        x = parent_x + (parent_width - window_width) // 2
        y = parent_y + (parent_height - window_height) // 2
        
        # Ustawiamy geometrię (rozmiar + pozycja)
        win.geometry(f"{window_width}x{window_height}+{x}+{y}")

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Checkbutton(frm, text="Włącz wymaganie logowania do Panelu Admina",
                        variable=enabled).pack(anchor=tk.W, pady=(0,8))

        row1 = ttk.Frame(frm); row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="Login administratora:", width=22).pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=username).pack(side=tk.LEFT, fill=tk.X, expand=True)

        row2 = ttk.Frame(frm); row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="Nowe hasło (opcjonalnie):", width=22).pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=password, show="•").pack(side=tk.LEFT, fill=tk.X, expand=True)

        hint = ttk.Label(frm, foreground="#6c757d",
            text="Zostanie zapisane w .env jako hash (bezpiecznie). Pozostaw puste, by nie zmieniać.",
            wraplength=480)  # Dodana właściwość zawijania tekstu
        hint.pack(anchor=tk.W, pady=(6,10), fill=tk.X)

        btns = ttk.Frame(frm); btns.pack(fill=tk.X, pady=(10,0))
        def save():
            # Zapisz stare wartości do porównania
            old_auth_enabled = env.get('ADMIN_AUTH_ENABLED', '0')
            
            # walidacja loginu
            if not username.get().strip():
                messagebox.showwarning("Walidacja", "Login nie może być pusty.", parent=win)
                return
            # aktualizacja słownika env
            env['ADMIN_AUTH_ENABLED'] = '1' if enabled.get() else '0'
            env['ADMIN_USERNAME'] = username.get().strip()
            # jeśli podano nowe hasło – generuj hash
            if password.get():
                try:
                    env['ADMIN_PASSWORD_HASH'] = generate_password_hash(password.get())
                except Exception as e:
                    messagebox.showerror("Błąd", f"Nie udało się utworzyć hasha: {e}", parent=win)
                    return
            # zadbaj o SECRET_KEY jeśli brak
            env.setdefault('FLASK_SECRET_KEY', 'change-me-' + str(os.getpid()))

            # zapisz .env – zachowując proste uporządkowanie
            order = [
                'DB_HOST','DB_NAME','DB_USER','DB_PASSWORD','DB_PORT',
                'FLASK_HOST','FLASK_PORT','FLASK_DEBUG',
                'FLASK_SECRET_KEY',
                'ADMIN_AUTH_ENABLED','ADMIN_USERNAME','ADMIN_PASSWORD_HASH'
            ]
            lines = []
            for k in order:
                if k in env: lines.append(f"{k}={env[k]}")
            # dopisz resztę ewentualnych kluczy
            for k,v in env.items():
                if k not in order: lines.append(f"{k}={v}")

            try:
                with open(env_path,'w',encoding='utf-8') as f:
                    f.write("# --- KONFIGURACJA BAZY DANYCH POSTGRESQL ---\n")
                    f.write("\n".join([l for l in lines if l.split('=')[0] in {'DB_HOST','DB_NAME','DB_USER','DB_PASSWORD','DB_PORT'}]))
                    f.write("\n\n# --- KONFIGURACJA SERWERA FLASK ---\n")
                    f.write("\n".join([l for l in lines if l.split('=')[0] in {'FLASK_HOST','FLASK_PORT','FLASK_DEBUG','FLASK_SECRET_KEY'}]))
                    f.write("\n\n# --- ADMIN / BEZPIECZEŃSTWO ---\n")
                    f.write("\n".join([l for l in lines if l.split('=')[0] in {'ADMIN_AUTH_ENABLED','ADMIN_USERNAME','ADMIN_PASSWORD_HASH'}]))
                    # wszelka reszta:
                    others = [l for l in lines if l.split('=')[0] not in {
                        'DB_HOST','DB_NAME','DB_USER','DB_PASSWORD','DB_PORT',
                        'FLASK_HOST','FLASK_PORT','FLASK_DEBUG','FLASK_SECRET_KEY',
                        'ADMIN_AUTH_ENABLED','ADMIN_USERNAME','ADMIN_PASSWORD_HASH'
                    }]
                    if others:
                        f.write("\n\n# --- POZOSTAŁE ---\n")
                        f.write("\n".join(others))
            except Exception as e:
                messagebox.showerror("❌ Błąd zapisu", str(e), parent=win)
                return

            # poinformuj launcher o zmianach
            self.on_env_changed()
            
            # Automatyczny restart serwera przy zmianie autoryzacji 
            new_auth_enabled = env['ADMIN_AUTH_ENABLED']
            
            # Sprawdź czy zmieniono ustawienia autoryzacji i czy serwer działa
            if old_auth_enabled != new_auth_enabled and "backend" in self.managed_processes:
                # Zapamiętaj tryb serwera
                was_network = self.managed_processes["backend"].get("network_mode", False)
                
                # Komunikat o restarcie
                restart_msg = (
                    f"{'Włączono' if new_auth_enabled == '1' else 'Wyłączono'} autoryzację admina.\n\n"
                    "Serwer backend zostanie automatycznie zrestartowany,\n"
                    "aby zastosować nowe ustawienia bezpieczeństwa."
                )
                
                messagebox.showinfo("🔄 Restart serwera", restart_msg, parent=win)
                
                # Zamknij okno ustawień
                win.destroy()
                
                # Logowanie do konsoli
                self.log(f"\n{'='*60}\n")
                self.log(f"🔄 Restartowanie serwera - zmiana ustawień autoryzacji admina...\n")
                self.log(f"   • Autoryzacja: {'WŁĄCZONA ✅' if new_auth_enabled == '1' else 'WYŁĄCZONA ❌'}\n")
                if new_auth_enabled == '1':
                    self.log(f"   • Login: {env['ADMIN_USERNAME']}\n")
                    self.log(f"   • Hasło: {'Ustawione ✅' if env.get('ADMIN_PASSWORD_HASH') else 'Brak ⚠️'}\n")
                self.log(f"{'='*60}\n\n")
                
                # Zatrzymaj serwer
                self.stop_managed_process("backend")
                
                # Funkcja do ponownego uruchomienia
                def restart_server():
                    if was_network:
                        self.start_network_server()
                    else:
                        self.start_managed_process("backend", "Serwer Backend (Lokalny)")
                        self.server_btn.config(
                            text="⏹️ Zatrzymaj Serwer (Lokalny)", 
                            style="Danger.TButton"
                        )
                    
                    # Dodatkowe powiadomienie po restarcie
                    if new_auth_enabled == '1':
                        self.log("\n✅ Serwer uruchomiony z WŁĄCZONĄ autoryzacją.\n")
                        self.log(f"   Aby wejść do panelu admina użyj:\n")
                        self.log(f"   • Login: {env['ADMIN_USERNAME']}\n")
                        self.log(f"   • Hasło: (to które ustawiłeś)\n\n")
                    else:
                        self.log("\n✅ Serwer uruchomiony z WYŁĄCZONĄ autoryzacją.\n")
                        self.log("   Panel admina jest teraz dostępny bez logowania.\n\n")
                
                # Poczekaj 800ms i wystartuj ponownie
                self.after(800, restart_server)
            else:
                # Nie było zmiany autoryzacji lub serwer nie działa
                messagebox.showinfo("✅ Zapisano", "Ustawienia administratora zapisane.", parent=win)
                win.destroy()

        ttk.Button(btns, text="💾 Zapisz", command=save, style="Success.TButton").pack(side=tk.RIGHT)
        ttk.Button(btns, text="Anuluj", command=win.destroy, style="Secondary.TButton").pack(side=tk.RIGHT, padx=(0,8))


    def start_managed_process(self, key, name):
        """
        Uruchamia zewnętrzny skrypt jako zarządzany proces potomny.
        Tworzy dedykowaną konsolę i monitoruje wyjście procesu.
        
        Args:
            key: Identyfikator procesu (klucz w słowniku SCRIPTS)
            name: Czytelna nazwa procesu
        """
        # Sprawdzenie czy proces już działa
        if key in self.managed_processes:
            messagebox.showwarning(
                "⚠️ Proces już działa", 
                f"Proces '{name}' jest już uruchomiony."
            )
            return

        self.log(f"🚀 Uruchamianie: {name}...\n")
        script_info = SCRIPTS[key]

        # --- TWORZENIE KONSOLI DLA PROCESU ---
        
        # Tworzenie nowej zakładki z konsolą
        tab_frame = ttk.Frame(self.notebook)
        console = self.create_console_widget(tab_frame)
        
        # Ikona dla zakładki
        tab_text = f"📋 {name}"
        self.notebook.add(tab_frame, text=tab_text)
        self.notebook.select(tab_frame)

        # --- KONFIGURACJA ŚRODOWISKA ---
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        # Wczytanie zmiennych z pliku .env do środowiska procesu
        # Zapewnia to, że wszystkie uruchamiane skrypty mają dostęp do konfiguracji
        env_path = os.path.join(BACKEND_DIR, ".env")
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        env_key, env_value = line.split('=', 1)  
                        env[env_key.strip()] = env_value.strip()

        # --- PRZYGOTOWANIE KOMENDY ---
        
        # Budowanie listy argumentów dla Popen
        if key == "tests":
            # Odpal pytest jako moduł Pythona
            command = [sys.executable, script_info["path"]] + script_info["args"]
        else:
            command = [sys.executable, "-X", "utf8", "-u", script_info["path"]]

        # Dodanie specjalnej flagi dla edytora genealogii
        if key == "genealogy_editor":
            command.append("--launched-by-gui")
        
        # --- URUCHOMIENIE PROCESU ---
        
        # Flagi creationflags do ukrycia okna konsoli na Windows
        creation_flags = (
            (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
            if platform.system() == "nt"
            else 0
        )
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=script_info["cwd"],
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
            env=env,
        )

        # --- ZAPISANIE INFORMACJI O PROCESIE ---
        
        self.managed_processes[key] = {
            "process": process,
            "console": console,
            "tab_frame": tab_frame,
            "name": name,
        }

        # --- URUCHOMIENIE MONITOROWANIA ---
        
        # Uruchomienie wątku do odczytywania wyjścia z procesu
        threading.Thread(
            target=self.read_process_output, 
            args=(key,), 
            daemon=True
        ).start()

        # Automatyczne otwarcie URL jeśli zdefiniowany
        if key in URLS:
            threading.Timer(1.5, lambda: webbrowser.open(URLS[key])).start()

        # Aktualizacja interfejsu
        self.update_processes_ui()

    def stop_managed_process(self, key):
        """
        Zatrzymuje zarządzany proces w bezpieczny sposób.
        Najpierw próbuje zakończyć gracefully, potem wymusza zabicie.
        
        Args:
            key: Identyfikator procesu do zatrzymania
        """
        if key not in self.managed_processes:
            return

        info = self.managed_processes[key]
        process = info["process"]
        name = info["name"]

        # Logowanie akcji
        msg_stop = f"\n⏹️ Zatrzymywanie procesu: {name}...\n"
        self.log(msg_stop, console=info["console"])
        self.log(msg_stop)

        try:
            # --- PRÓBA NORMALNEGO ZATRZYMANIA ---
            
            # Użycie odpowiedniej metody w zależności od systemu
            if platform.system() == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            
            # Oczekiwanie na zakończenie (timeout 2 sekundy)
            process.wait(timeout=2)
            
        except (subprocess.TimeoutExpired, ProcessLookupError, PermissionError):
            # --- WYMUSZENIE ZATRZYMANIA ---
            
            msg_kill = f"⚠️ Proces '{name}' nie odpowiedział – wymuszam zatrzymanie.\n"
            self.log(msg_kill, console=info["console"])
            self.log(msg_kill)
            process.kill()
            process.wait()

        # --- CZYSZCZENIE ZASOBÓW ---
        
        # Usunięcie z listy procesów
        del self.managed_processes[key]
        
        # Usunięcie zakładki konsoli
        self.notebook.forget(info["tab_frame"])
        
        # Aktualizacja interfejsu
        self.update_processes_ui()

        # Specjalna obsługa dla serwera backend
        if key == "backend":
            self.server_btn.config(
                text="🚀 Uruchom Serwer Backend", 
                style="Success.TButton"
            )

    def read_process_output(self, key):
        """
        Czyta wyjście z procesu linia po linii w osobnym wątku.
        Przekazuje dane do konsoli GUI przez główny wątek.
        
        Args:
            key: Identyfikator procesu
        """
        if key not in self.managed_processes:
            return

        info = self.managed_processes.get(key)
        if not info:
            return

        process = info["process"]
        console = info["console"]

        # Pętla odczytuje dane aż do zamknięcia strumienia wyjściowego
        for line in iter(process.stdout.readline, ""):
            # Przekazanie linii do GUI przez główny wątek
            self.after(0, self.log, line, console)
            
        # Po zakończeniu pętli, proces jest zakończony
        self.event_queue.put((key, "finished"))

    def run_script_in_thread(self, script_info, script_name):
        """
        Uruchamia jednorazowy skrypt w wątku.
        Używane dla skryptów które wykonują zadanie i kończą działanie.
        
        Args:
            script_info: Słownik z informacjami o skrypcie
            script_name: Czytelna nazwa skryptu
        """
        def target():
            """Funkcja wykonywana w osobnym wątku."""
            
            self.log(f"⚡ Uruchamianie: {script_name}...\n")
            
            # Konfiguracja środowiska
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"

            # Wczytanie zmiennych z pliku .env do środowiska procesu
            env_path = os.path.join(BACKEND_DIR, ".env")
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            env_key, env_value = line.split('=', 1)  
                            env[env_key.strip()] = env_value.strip()

            # Flagi dla Windows
            creation_flags = (
                subprocess.CREATE_NO_WINDOW if platform.system() == "nt" else 0
            )
            
            # Uruchomienie procesu
            process = subprocess.Popen(
                [sys.executable, "-X", "utf8", "-u", script_info["path"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=script_info["cwd"],
                encoding="utf-8",
                errors="replace",
                creationflags=creation_flags,
                env=env,
            )
            
            # Odczyt wyjścia linia po linii
            for line in iter(process.stdout.readline, ""):
                self.log(line)
            process.stdout.close()
            
            # Raportowanie zakończenia
            return_code = process.wait()
            if return_code == 0:
                self.log(f"✅ Zakończono pomyślnie: {script_name}\n")
            else:
                self.log(f"❌ Zakończono z błędem: {script_name} (kod: {return_code})\n")

        # Uruchomienie w osobnym wątku
        threading.Thread(target=target, daemon=True).start()

    def run_pytest(self):
        """
        Uruchamia pytest w wątku i przekierowuje wyjście bezpośrednio
        do głównej konsoli launchera (jak w migracji).
        """
        def target():
            self.log("🧪 Start testów jednostkowych (pytest)...\n")
            try:
                # Środowisko jak w migracji – wczytaj .env backendu
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"

                env_path = os.path.join(BACKEND_DIR, ".env")
                if os.path.exists(env_path):
                    with open(env_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                k, v = line.split('=', 1)
                                env[k.strip()] = v.strip()

                # Komenda pytest (cicho: -q). Katalog pracy: backend
                cmd = [sys.executable, "-m", "pytest", "tests", "-q"]

                # Windows: bez dodatkowego okna konsoli
                creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "nt" else 0

                proc = subprocess.Popen(
                    cmd,
                    cwd=BACKEND_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creation_flags,
                    env=env
                )

                # Strumieniuj linie do głównej konsoli
                for line in iter(proc.stdout.readline, ""):
                    self.log(line)
                proc.stdout.close()

                rc = proc.wait()
                if rc == 0:
                    self.log("✅ Testy zakończone pomyślnie.\n")
                else:
                    self.log(f"❌ Testy zakończone błędem (kod: {rc}).\n")

            except FileNotFoundError:
                self.log("❌ Nie znaleziono pytest. Zainstaluj: pip install pytest\n")
            except Exception as e:
                self.log(f"❌ Błąd uruchamiania testów: {e}\n")

        threading.Thread(target=target, daemon=True).start()


    def toggle_server(self, network_mode=False):  
        """
        Przełącza stan serwera backend (uruchamia lub zatrzymuje).
        
        Args:
            network_mode: Jeśli True, serwer będzie dostępny w sieci lokalnej
        """
        if "backend" in self.managed_processes:
            self.stop_managed_process("backend")
        else:
            if network_mode:
                self.start_network_server()
            else:
                self.start_managed_process("backend", "Serwer Backend (Lokalny)")
                self.server_btn.config(
                    text="⏹️ Zatrzymaj Serwer (Lokalny)", 
                    style="Danger.TButton"
                )

    def start_network_server(self):
        """
        Uruchamia serwer Flask dostępny w sieci lokalnej.
        Modyfikuje sposób uruchomienia aby nasłuchiwał na wszystkich interfejsach.
        """
        # Sprawdź/skonfiguruj firewall
        if platform.system() == "Windows":
            self.setup_firewall_rule()
        
        # Pobierz lokalny IP
        local_ip = get_local_ip()
        
        # Pobierz konfigurację
        flask_config = get_flask_config()
        port = int(flask_config['port'])
        # Informacja dla użytkownika
        self.log(f"🌐 Uruchamianie serwera w trybie SIECIOWYM...\n")
        self.log(f"📡 Serwer będzie dostępny pod adresami:\n")
        self.log(f"   • Lokalnie: http://127.0.0.1:{port}\n")
        self.log(f"   • W sieci LAN: http://{local_ip}:{port}\n")
        self.log(f"   • Alternatywnie: http://{socket.gethostname()}:{port}\n")
        self.log(f"⚠️ UWAGA: Upewnij się, że firewall nie blokuje portu {port}!\n\n")
        
        script_info = SCRIPTS["backend"]
        
        # Tworzenie nowej zakładki z konsolą
        tab_frame = ttk.Frame(self.notebook)
        console = self.create_console_widget(tab_frame)
        tab_text = f"🌐 Serwer Sieciowy"
        self.notebook.add(tab_frame, text=tab_text)
        self.notebook.select(tab_frame)
        
        # Konfiguracja środowiska
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        # Wczytanie zmiennych z pliku .env
        env_path = os.path.join(BACKEND_DIR, ".env")
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        env_key, env_value = line.split('=', 1)  
                        env[env_key.strip()] = env_value.strip()
        
        # Tworzymy skrypt wrapper który uruchomi Flask z odpowiednimi parametrami
        wrapper_code = f'''import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from app import app

if __name__ == '__main__':
    print('🚀 Uruchamianie serwera Flask w trybie sieciowym...')
    print('📡 Serwer nasłuchuje na wszystkich interfejsach (0.0.0.0)')
    print('=' * 60)
    app.run(host="0.0.0.0", port={port}, debug=True, use_reloader=False)
'''
        
        # Zapisz tymczasowy plik wrapper
        wrapper_path = os.path.join(BACKEND_DIR, "_network_server_wrapper.py")
        with open(wrapper_path, 'w', encoding='utf-8') as f:
            f.write(wrapper_code)
        
        # Uruchomienie procesu
        creation_flags = (
            (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
            if platform.system() == "nt"
            else 0
        )
        
        process = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-u", wrapper_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=BACKEND_DIR,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
            env=env,
        )
        
        # Zapisanie informacji o procesie
        self.managed_processes["backend"] = {
            "process": process,
            "console": console,
            "tab_frame": tab_frame,
            "name": "Serwer Backend (Sieciowy)",
            "network_mode": True,
            "local_ip": local_ip
        }
        
        # Uruchomienie wątku do odczytywania wyjścia
        threading.Thread(
            target=self.read_process_output, 
            args=("backend",), 
            daemon=True
        ).start()
        
        # Aktualizacja przycisku
        self.network_server_btn.config(
            text="⏹️ Zatrzymaj Serwer Sieciowy",
            style="Danger.TButton"
        )
        
        # Pokaż dialog z informacjami o dostępie
        self.show_network_info_dialog(local_ip)
        
        self.update_processes_ui()

    def setup_firewall_rule(self):
        if platform.system() != "Windows":
            return True

        flask_config = get_flask_config()
        port = int(flask_config['port'])
        rule_name = f"Flask Server Port {port}"

        check_cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            self.log("✅ Reguła firewall już istnieje.\n")
            return True

        self.log("🔧 Konfigurowanie reguły firewall...\n")

        add_cmd = (
            'netsh advfirewall firewall add rule '
            f'name="{rule_name}" '
            'dir=in action=allow protocol=TCP '
            f'localport={port} enable=yes profile=any'
        )
        
        try:
            # Sprawdź czy mamy uprawnienia administratora
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            
            if not is_admin:
                # Poproś o uruchomienie jako administrator
                response = messagebox.askyesno(
                    "🔐 Wymagane uprawnienia administratora",
                    "Aby automatycznie skonfigurować firewall, aplikacja musi być uruchomiona jako Administrator.\n\n"
                    "Czy chcesz:\n"
                    "• TAK - Uruchomić ponownie aplikację jako Administrator?\n"
                    "• NIE - Skonfigurować firewall ręcznie później?\n\n"
                    "Bez konfiguracji firewall serwer sieciowy nie będzie dostępny z innych urządzeń.",
                    icon="warning"
                )
                
                if response:
                    # Uruchom ponownie jako administrator
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", sys.executable, " ".join(sys.argv), None, 1
                    )
                    self.destroy()
                    sys.exit(0)
                else:
                    self.log("⚠️ Firewall nie został skonfigurowany. Skonfiguruj go ręcznie.\n")
                    self.show_firewall_instructions()
                    return False
            
            # Mamy uprawnienia - dodaj regułę
            result = subprocess.run(add_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log("✅ Reguła firewall została dodana pomyślnie!\n")
                messagebox.showinfo(
                    "✅ Sukces",
                    "Reguła firewall została skonfigurowana.\n"
                    "Port 5000 jest teraz otwarty dla połączeń przychodzących."
                )
                return True
            else:
                self.log(f"❌ Błąd dodawania reguły: {result.stderr}\n")
                return False
                
        except Exception as e:
            self.log(f"❌ Błąd konfiguracji firewall: {e}\n")
            return False

    def show_firewall_instructions(self):
        """
        Wyświetla instrukcje ręcznej konfiguracji firewall.
        """
        flask_config = get_flask_config()
        port = int(flask_config['port'])
        instructions = tk.Toplevel(self)
        instructions.title("📋 Instrukcja konfiguracji Firewall")
        instructions.geometry("600x500")
        instructions.transient(self)
        
        frame = ttk.Frame(instructions, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True)
        
        content = """INSTRUKCJA RĘCZNEJ KONFIGURACJI FIREWALL WINDOWS
    ================================================

    METODA 1 - Przez interfejs graficzny:
    -------------------------------------
    1. Naciśnij Win + R
    2. Wpisz: wf.msc
    3. Naciśnij Enter
    4. Kliknij "Reguły przychodzące" (po lewej)
    5. Kliknij "Nowa reguła..." (po prawej)
    6. Wybierz "Port" → Dalej
    7. Wybierz "TCP" i wpisz "5000" → Dalej
    8. Wybierz "Zezwalaj na połączenie" → Dalej
    9. Zaznacz wszystkie profile → Dalej
    10. Nazwa: "Flask Server Port 5000" → Zakończ

    METODA 2 - Przez PowerShell (jako Administrator):
    -------------------------------------------------
    1. Kliknij prawym na Start → Windows PowerShell (Administrator)
    2. Wklej i wykonaj komendę:

    New-NetFirewallRule -DisplayName "Flask Server Port 5000" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Any

    METODA 3 - Przez Wiersz poleceń (jako Administrator):
    ----------------------------------------------------
    1. Kliknij prawym na Start → Wiersz poleceń (Administrator)
    2. Wklej i wykonaj komendę:

    netsh advfirewall firewall add rule name="Flask Server Port 5000" dir=in action=allow protocol=TCP localport=5000

    TESTOWANIE:
    -----------
    Po dodaniu reguły, możesz sprawdzić czy port jest otwarty:
    1. Uruchom serwer sieciowy
    2. Na innym urządzeniu w sieci wpisz adres IP:5000
    3. Jeśli strona się ładuje - wszystko działa!

    UWAGA: Upewnij się, że oba urządzenia są w tej samej sieci WiFi/LAN!
    """
        
        text.insert("1.0", content)
        text.config(state="disabled")
        
        ttk.Button(
            frame,
            text="Zamknij",
            command=instructions.destroy,
            style="Primary.TButton"
        ).pack(pady=10)

    def toggle_network_server(self):
        """Przełącza serwer sieciowy - uruchamia lub zatrzymuje."""
        if "backend" in self.managed_processes:
            if self.managed_processes["backend"].get("network_mode"):
                self.stop_managed_process("backend")
                self.network_server_btn.config(
                    text="🌐 Uruchom Serwer Sieciowy",
                    style="Info.TButton"
                )
            else:
                messagebox.showwarning(
                    "⚠️ Uwaga",
                    "Lokalny serwer jest już uruchomiony.\n"
                    "Zatrzymaj go najpierw, aby uruchomić serwer sieciowy."
                )
        else:
            self.toggle_server(network_mode=True)

    def show_network_info_dialog(self, local_ip):
        """
        Wyświetla okno dialogowe z informacjami o dostępie sieciowym.
        
        Args:
            local_ip: Lokalny adres IP serwera
        """
        # Pobierz konfigurację
        flask_config = get_flask_config()
        port = flask_config['port']
        
        info_window = tk.Toplevel(self)
        info_window.title("Informacje o Dostępie Sieciowym")
        self._net_info_win = info_window 
        info_window.transient(self)
        info_window.grab_set()
        
        # Wycentrowanie okna
        w, h = 600, 400
        sw, sh = info_window.winfo_screenwidth(), info_window.winfo_screenheight()
        info_window.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        info_window.resizable(False, False)
        
        # Główna ramka
        main_frame = ttk.Frame(info_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Nagłówek
        ttk.Label(
            main_frame,
            text="✅ Serwer uruchomiony w trybie sieciowym!",
            font=("Segoe UI", 14, "bold"),
            foreground=COLORS['success']
        ).pack(pady=(0, 20))
        
        # Informacje o dostępie
        info_frame = ttk.LabelFrame(main_frame, text="📡 Adresy dostępu", padding="15")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Lista adresów
        addresses = [
            ("Ten komputer:", f"http://127.0.0.1:{port}"),
            ("Inne urządzenia w sieci:", f"http://{local_ip}:{port}"),
            ("Alternatywny adres:", f"http://{socket.gethostname()}:{port}"),
        ]

        # Sekcja: szybka komenda PowerShell
        ps_frame = ttk.LabelFrame(main_frame, text="⚡ Konfiguracja Firewall (PowerShell)", padding="15")
        ps_frame.pack(fill=tk.X, pady=10)

        ps_command = f'New-NetFirewallRule -DisplayName "CzarnaMapa" -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow -Profile Any'

        ps_entry = ttk.Entry(ps_frame, width=80)
        ps_entry.insert(0, ps_command)
        ps_entry.config(state="readonly")
        ps_entry.pack(side=tk.LEFT, padx=(0,10), fill=tk.X, expand=True)

        def copy_ps():
            self.clipboard_clear()
            self.clipboard_append(ps_command)
            messagebox.showinfo("✅ Skopiowano", "Komenda PowerShell została skopiowana.\nUruchom PowerShell jako Administrator i wklej komendę.", parent=info_window)

        ttk.Button(ps_frame, text="📋 Kopiuj", command=copy_ps, style="Primary.TButton").pack(side=tk.LEFT)

        for label, address in addresses:
            addr_frame = ttk.Frame(info_frame)
            addr_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(addr_frame, text=label, width=25).pack(side=tk.LEFT)
            
            # Pole z adresem (do kopiowania)
            addr_entry = ttk.Entry(addr_frame, width=40)
            addr_entry.insert(0, address)
            addr_entry.config(state="readonly")
            addr_entry.pack(side=tk.LEFT, padx=10)
            
            # Przycisk kopiowania
            def copy_addr(addr=address):
                self.clipboard_clear()
                self.clipboard_append(addr)
                messagebox.showinfo("✅ Skopiowano", f"Adres został skopiowany:\n{addr}", parent=info_window)
            
            ttk.Button(
                addr_frame,
                text="📋 Kopiuj",
                command=copy_addr,
                width=10
            ).pack(side=tk.LEFT)
        
        # Instrukcje
        instr_row = ttk.Frame(main_frame)
        instr_row.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(instr_row, text="ℹ️").pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            instr_row,
            text="📘 Pokaż instrukcję (firewall / port 5000)",
            command=self.open_network_instructions_centered,
            style="Primary.TButton"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)

        # Przycisk zamknięcia
        ttk.Button(
            main_frame,
            text="OK, rozumiem",
            command=info_window.destroy,
            style="Primary.TButton"
        ).pack(pady=10)

        #dopasowanie rozmiaru okna do zawartości i ustawienie minimalnego rozmiaru
        info_window.update_idletasks()
        req_w = info_window.winfo_reqwidth()
        req_h = info_window.winfo_reqheight()
        info_window.geometry(f"{req_w}x{req_h}")   # ustaw dokładnie wymagany rozmiar
        info_window.minsize(req_w, req_h)

    def open_network_instructions_centered(self):
        """Otwiera wyskakujące okno z instrukcją i centruje je względem okna sieciowego."""
        parent = getattr(self, "_net_info_win", self)

        win = tk.Toplevel(parent)
        win.title("Instrukcja – dostęp sieciowy / port 5000")
        win.resizable(False, False)
        win.transient(parent)   # trzymaj nad oknem sieciowym
        win.grab_set()          # tryb pseudo-modalny

        # Treść okna
        body = ttk.Frame(win, padding=14)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            body, text="Jak udostępnić aplikację w sieci lokalnej:",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor=tk.W, pady=(0, 6))

        ttk.Label(
            body, justify=tk.LEFT,
            text=(
                "1) Upewnij się, że serwer działa (zielony status w oknie sieciowym).\n"
                "2) Komputer-serwer i urządzenie-klient muszą być w tej samej sieci Wi-Fi/LAN.\n"
                "3) Na innym urządzeniu wpisz adres IP z listy (np. http://192.168.x.x:5000).\n"
                "4) Jeśli nie działa – dodaj regułę Zapory Windows: TCP 5000, wszystkie profile.\n"
                "5) Sprawdzenie nasłuchu:\n"
                "   • PowerShell: Get-NetTCPConnection -LocalPort 5000\n"
                "   • CMD:       netstat -ano | findstr :5000\n"
            ),
        ).pack(anchor=tk.W)

        ttk.Button(body, text="Zamknij", command=win.destroy, style="Secondary.TButton")\
        .pack(anchor=tk.E, pady=(10, 0))

        # Wyśrodkowanie względem rodzica
        parent.update_idletasks()
        win.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width()  - win.winfo_width())  // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")
        win.focus_set()

    def on_closing(self):  
        """
        Obsługuje zdarzenie zamknięcia głównego okna aplikacji.
        Pyta o potwierdzenie jeśli są uruchomione procesy.
        """
        if self.managed_processes:
            network_server = any(
                p.get("network_mode") for p in self.managed_processes.values()
            )
            
            warning_msg = f"Uruchomionych jest {len(self.managed_processes)} procesów."
            if network_server:
                warning_msg += "\n\n⚠️ UWAGA: Serwer sieciowy jest aktywny!"
            warning_msg += "\n\nCzy chcesz je wszystkie zatrzymać i zamknąć aplikację?"
            
            result = messagebox.askyesno(
                "🔒 Potwierdzenie zamknięcia",
                warning_msg,
                icon="warning" if network_server else "question"
            )
            
            if result:
                self.log("\n" + "=" * 60 + "\n")
                self.log("🔒 Zamykanie aplikacji - zatrzymywanie procesów...\n")
                
                for key in list(self.managed_processes.keys()):
                    self.stop_managed_process(key)
                
                self.cleanup_temp_files()  
                self.destroy()
        else:
            self.cleanup_temp_files()  
            self.destroy()

    # --- METODY POMOCNICZE ---
    
    def cleanup_temp_files(self): 
        """Usuwa tymczasowe pliki utworzone przez launcher."""
        wrapper_path = os.path.join(BACKEND_DIR, "_network_server_wrapper.py")
        if os.path.exists(wrapper_path):
            try:
                os.remove(wrapper_path)
            except:
                pass
    def open_security_manager(self):
        """Otwiera okno menedżera bezpieczeństwa."""
        if "backend" not in self.managed_processes:
            messagebox.showwarning(
                "Serwer nieaktywny",
                "Uruchom serwer backend, aby zarządzać bezpieczeństwem.",
                parent=self
            )
            return
        
        manager = SecurityManager(self)
        self.wait_window(manager)

#--- KLASA MENEDŻERA BEZPIECZEŃSTWA ---
class SecurityManager(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("🛡️ Menedżer Bezpieczeństwa")
        
        window_width = 900
        window_height = 600

        # Pobranie wymiarów ekranu
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Obliczenie pozycji x i y
        x_pos = (screen_width - window_width) // 2
        y_pos = (screen_height - window_height) // 2

        # Ustawienie geometrii (rozmiar + pozycja)
        self.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
        
        self.minsize(700, 500)
        self.grab_set()
        self.parent_app = parent
        self.base_url = f"http://127.0.0.1:{self.parent_app.load_flask_config()['port']}/api/admin/security"

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # --- Zakładka: Logi Logowania ---
        logs_frame = ttk.Frame(notebook, padding="10")
        notebook.add(logs_frame, text="📜 Logi Logowania")
        self.create_logs_tab(logs_frame)

        # --- Zakładka: Zablokowane IP ---
        blocked_frame = ttk.Frame(notebook, padding="10")
        notebook.add(blocked_frame, text="🚫 Zablokowane Adresy IP")
        self.create_blocked_ips_tab(blocked_frame)

        # Przycisk zamknięcia
        ttk.Button(main_frame, text="Zamknij", command=self.destroy, style="Secondary.TButton").pack(side=tk.RIGHT)

    def create_logs_tab(self, parent):
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(action_frame, text="Ostatnie 100 prób logowania do panelu admina", style="Heading.TLabel").pack(side=tk.LEFT, anchor=tk.W)
        
        ttk.Button(action_frame, text="🗑️ Wyczyść Wszystkie Logi", command=self.clear_login_logs, style="Warning.TButton").pack(side=tk.RIGHT)
        
        cols = ("ip", "user", "time", "status")
        self.logs_tree = ttk.Treeview(parent, columns=cols, show="headings")
        self.logs_tree.heading("ip", text="Adres IP")
        self.logs_tree.heading("user", text="Użyty login")
        self.logs_tree.heading("time", text="Czas")
        self.logs_tree.heading("status", text="Status")
        self.logs_tree.column("ip", width=120)
        self.logs_tree.column("user", width=150)
        self.logs_tree.column("time", width=160)
        self.logs_tree.column("status", width=100, anchor=tk.CENTER)
        
        self.logs_tree.tag_configure("success", foreground="green")
        self.logs_tree.tag_configure("failure", foreground="red")

        self.logs_tree.pack(fill=tk.BOTH, expand=True)

    def create_blocked_ips_tab(self, parent):
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Przycisk awaryjny po lewej
        emergency_btn = ttk.Button(action_frame, text="🚨 Odblokuj Localhost (127.0.0.1)", command=self.unblock_localhost, style="Warning.TButton")
        emergency_btn.pack(side=tk.LEFT)
        
        # Kontener na przyciski po prawej stronie
        right_buttons_frame = ttk.Frame(action_frame)
        right_buttons_frame.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons_frame, text="🔓 Odblokuj Zaznaczone", command=self.unblock_selected_ip, style="Success.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(right_buttons_frame, text="➕ Zablokuj IP", command=self.manually_block_ip, style="Danger.TButton").pack(side=tk.LEFT)

        # BRAKUJĄCA CZĘŚĆ - TWORZENIE TABELI
        cols = ("ip", "reason", "time")
        self.blocked_tree = ttk.Treeview(parent, columns=cols, show="headings")
        self.blocked_tree.heading("ip", text="Adres IP")
        self.blocked_tree.heading("reason", text="Powód blokady")
        self.blocked_tree.heading("time", text="Czas blokady")
        self.blocked_tree.column("ip", width=120)
        self.blocked_tree.column("reason", width=400)
        self.blocked_tree.column("time", width=160)
        self.blocked_tree.pack(fill=tk.BOTH, expand=True)

    def load_data(self):
        self.load_logs()
        self.load_blocked_ips()

    def api_request(self, endpoint, method="GET", data=None):
        import requests
        import json
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {"Content-Type": "application/json"}
            if method.upper() == "GET":
                response = requests.get(url, timeout=5)
            else:
                response = requests.post(url, data=json.dumps(data), headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Błąd API", f"Nie można połączyć się z serwerem:\n{e}", parent=self)
            return None

    def load_logs(self):
        for i in self.logs_tree.get_children(): self.logs_tree.delete(i)
        logs = self.api_request("/logs")
        if logs:
            for log in logs:
                status_text = "✅ Powodzenie" if log['successful'] else "❌ Błąd"
                tag = "success" if log['successful'] else "failure"
                self.logs_tree.insert("", "end", values=(log['ip_address'], log['username_attempt'], log['timestamp'], status_text), tags=(tag,))

    def clear_login_logs(self):
        """Wyświetla potwierdzenie i czyści logi logowania po stronie serwera."""
        if messagebox.askyesno(
            "🗑️ Potwierdzenie",
            "Czy na pewno chcesz trwale usunąć WSZYSTKIE logi prób logowania?\n\nTej operacji nie można cofnąć.",
            parent=self,
            icon="warning"
        ):
            response = self.api_request("/clear-logs", method="POST")
            if response and response.get("status") == "success":
                messagebox.showinfo("✅ Sukces", "Wszystkie logi logowania zostały usunięte.", parent=self)
                self.parent_app.log("🛡️ Wyczyszczono wszystkie logi logowania.\n")
                self.load_logs()  # Odśwież widok
            else:
                messagebox.showerror("❌ Błąd", "Nie udało się wyczyścić logów. Sprawdź konsolę serwera.", parent=self)

    def load_blocked_ips(self):
        for i in self.blocked_tree.get_children(): self.blocked_tree.delete(i)
        ips = self.api_request("/blocked-ips")
        if ips:
            for ip in ips:
                self.blocked_tree.insert("", "end", values=(ip['ip_address'], ip['reason'], ip['timestamp']))

    def unblock_selected_ip(self):
        selected_items = self.blocked_tree.selection()
        if not selected_items:
            messagebox.showwarning("Brak zaznaczenia", "Zaznacz adres IP do odblokowania.", parent=self)
            return
        
        for item_id in selected_items:
            ip_to_unblock = self.blocked_tree.item(item_id)['values'][0]
            if messagebox.askyesno("Potwierdzenie", f"Czy na pewno chcesz odblokować adres IP: {ip_to_unblock}?", parent=self):
                response = self.api_request("/unblock-ip", method="POST", data={"ip_address": ip_to_unblock})
                if response and response.get("status") == "success":
                    self.parent_app.log(f"🛡️ Odblokowano adres IP: {ip_to_unblock}\n")
                else:
                    messagebox.showerror("Błąd", f"Nie udało się odblokować {ip_to_unblock}.", parent=self)
        
        self.load_blocked_ips()

    def unblock_localhost(self):
        """Wysyła żądanie odblokowania adresu 127.0.0.1."""
        ip_to_unblock = "127.0.0.1"
        if messagebox.askyesno("Potwierdzenie", f"Czy na pewno chcesz odblokować adres {ip_to_unblock}?\n\nUżyj tej opcji, jeśli przypadkowo zablokowałeś dostęp do serwera z lokalnego komputera.", parent=self):
            response = self.api_request("/unblock-ip", method="POST", data={"ip_address": ip_to_unblock})
            if response and response.get("status") == "success":
                messagebox.showinfo("Sukces", f"Wysłano żądanie odblokowania dla adresu {ip_to_unblock}.", parent=self)
                self.parent_app.log(f"🛡️ Wysłano awaryjne odblokowanie dla: {ip_to_unblock}\n")
                self.load_blocked_ips() # Odśwież listę, aby zobaczyć efekt
            else:
                messagebox.showerror("Błąd", f"Nie udało się odblokować {ip_to_unblock}. Sprawdź, czy serwer działa.", parent=self)

    def manually_block_ip(self):
        from tkinter import simpledialog
        ip = simpledialog.askstring("Blokada IP", "Wprowadź adres IP do zablokowania:", parent=self)
        if ip:
            reason = simpledialog.askstring("Powód blokady", "Podaj powód blokady (opcjonalnie):", parent=self)
            response = self.api_request("/block-ip", method="POST", data={"ip_address": ip, "reason": reason or "Ręczna blokada."})
            if response and response.get("status") == "success":
                self.parent_app.log(f"🛡️ Ręcznie zablokowano adres IP: {ip}\n")
                self.load_blocked_ips()
            else:
                messagebox.showerror("Błąd", f"Nie udało się zablokować {ip}.", parent=self)


# --- KLASA MENEDŻERA KOPII ZAPASOWYCH ---

class BackupManager(tk.Toplevel):
    """
    Okno dialogowe do zarządzania kopiami zapasowymi projektu.
    Umożliwia tworzenie, przywracanie, import i eksport archiwów ZIP.
    """
    
    def __init__(self, parent):
        """
        Inicjalizacja okna menedżera kopii zapasowych.
        
        Args:
            parent: Okno rodzica (główna aplikacja)
        """
        super().__init__(parent)
        self.transient(parent)
        self.title("💾 Uniwersalny Menedżer Kopii Zapasowych")

        # --- AUTOMATYCZNE DOSTOSOWANIE DO EKRANU I DPI ---
        
        # Pobranie wymiarów ekranu i DPI
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        dpi = self.winfo_fpixels("1i")
        scale_factor = dpi / 96
        
        # Inteligentne określenie rozmiaru okna
        if sw <= 1920:  # HD/Full HD
            w, h = min(int(sw * 0.75), 1100), min(int(sh * 0.80), 700)
        else:  # Wyższe rozdzielczości
            w, h = min(int(sw * 0.60), 1200), min(int(sh * 0.75), 800)
        
        # Dostosowanie do wysokiego DPI
        if scale_factor > 1.25:
            w = int(w / scale_factor * 1.3)
            h = int(h / scale_factor * 1.3)
        
        # Wycentrowanie okna
        x = (sw - w) // 2
        y = (sh - h) // 2
        
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(800, 600)
        
        self.grab_set()
        
        # --- KONFIGURACJA STYLÓW ---
        
        # Obliczenie rozmiaru czcionki
        if scale_factor <= 1.0:
            base_size = 10
        elif scale_factor <= 1.25:
            base_size = 10
        elif scale_factor <= 1.5:
            base_size = 11
        else:
            base_size = 12
        
        self.base_font_size = base_size
        
        # Konfiguracja stylu dla Treeview
        self.style = ttk.Style(self)
        row_height = int(base_size * 2.5)
        self.style.configure(
            "Treeview",
            rowheight=row_height,
            font=("Segoe UI", base_size)
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Segoe UI", base_size, "bold")
        )

        # --- UTWORZENIE INTERFEJSU ---
        
        self.create_widgets()
        self.populate_backup_list()

    def create_widgets(self):
        """
        Tworzy interfejs graficzny menedżera kopii zapasowych.
        Używa elastycznego układu pack dla lepszego dostosowania.
        """
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- SEKCJA TWORZENIA KOPII ---
        
        create_frame = ttk.LabelFrame(
            main_frame, 
            text="➕ Stwórz Nową Kopię Zapasową", 
            padding="10"
        )
        create_frame.pack(fill=tk.X, pady=(0, 10))

        # Checkboxy do wyboru elementów
        self.backup_vars = {key: tk.BooleanVar(value=True) for key in DATA_FILES}
        self.backup_vars["scans"] = tk.BooleanVar(value=True)

        # Kontener na checkboxy i przycisk
        content_frame = ttk.Frame(create_frame)
        content_frame.pack(fill=tk.X)
        
        # Lewa strona - checkboxy w dwóch kolumnach
        checkbox_frame = ttk.Frame(content_frame)
        checkbox_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Pierwsza kolumna checkboxów
        col1 = ttk.Frame(checkbox_frame)
        col1.pack(side=tk.LEFT, padx=10)
        
        ttk.Checkbutton(
            col1, 
            text="📋 Właściciele i Demografia", 
            variable=self.backup_vars["owners"]
        ).pack(anchor="w", pady=2)
        
        ttk.Checkbutton(
            col1, 
            text="🗺️ Działki (geometria)", 
            variable=self.backup_vars["parcels"]
        ).pack(anchor="w", pady=2)
        
        # Druga kolumna checkboxów
        col2 = ttk.Frame(checkbox_frame)
        col2.pack(side=tk.LEFT, padx=10)
        
        ttk.Checkbutton(
            col2, 
            text="🌳 Genealogia", 
            variable=self.backup_vars["genealogy"]
        ).pack(anchor="w", pady=2)
        
        ttk.Checkbutton(
            col2, 
            text="📄 Skany Protokołów", 
            variable=self.backup_vars["scans"]
        ).pack(anchor="w", pady=2)
        
        # Prawa strona - przycisk tworzenia
        ttk.Button(
            content_frame, 
            text="🎯 Stwórz Kopię ZIP", 
            command=self.create_backup, 
            style="Success.TButton"
        ).pack(side=tk.RIGHT, padx=10)

        # --- SEKCJA ZARZĄDZANIA KOPIAMI ---
        
        restore_frame = ttk.LabelFrame(
            main_frame, 
            text="📦 Istniejące Kopie Zapasowe", 
            padding="10"
        )
        restore_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Tabela z listą kopii
        self.tree = ttk.Treeview(
            restore_frame, 
            columns=("filename",), 
            show="headings"
        )
        self.tree.heading("filename", text="📁 Nazwa Pliku (od najnowszej)")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # --- PASEK AKCJI ---
        
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Lewa strona - etykieta statusu
        self.selected_label = ttk.Label(
            action_frame, 
            text="📭 Nic nie zaznaczono",
            foreground=COLORS['secondary'],
            font=("Segoe UI", self.base_font_size)
        )
        self.selected_label.pack(side=tk.LEFT, padx=5)

        # Prawa strona - przyciski akcji
        buttons_frame = ttk.Frame(action_frame)
        buttons_frame.pack(side=tk.RIGHT)
        
        self.delete_btn = ttk.Button(
            buttons_frame, 
            text="🗑️ Usuń", 
            style="Danger.TButton", 
            command=self.delete_backup, 
            state=tk.DISABLED
        )
        self.delete_btn.pack(side=tk.LEFT, padx=2)
        
        self.restore_btn = ttk.Button(
            buttons_frame, 
            text="♻️ Przywróć", 
            command=self.restore_backup, 
            state=tk.DISABLED,
            style="Warning.TButton"
        )
        self.restore_btn.pack(side=tk.LEFT, padx=2)

        self.export_btn = ttk.Button(
            buttons_frame, 
            text="📤 Eksportuj", 
            command=self.export_backup, 
            state=tk.DISABLED
        )
        self.export_btn.pack(side=tk.LEFT, padx=2)

        self.import_btn = ttk.Button(
            buttons_frame, 
            text="📥 Importuj z dysku", 
            command=self.import_backup,
            style="Primary.TButton"
        )
        self.import_btn.pack(side=tk.LEFT, padx=2)

    def populate_backup_list(self):
        """
        Wczytuje listę plików kopii zapasowych z folderu backup.
        Sortuje pliki od najnowszych i wyświetla w tabeli.
        """
        # Czyszczenie obecnej listy
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            # Wyszukiwanie plików backup
            files = [
                f for f in os.listdir(BACKUP_FOLDER) 
                if f.startswith("pelny_backup_projektu_") and f.endswith(".zip")
            ]
            
            # Sortowanie od najnowszych
            files.sort(reverse=True)
            
            # Dodawanie do tabeli
            for filename in files:
                self.tree.insert("", "end", iid=filename, values=(filename,))
                
        except FileNotFoundError:
            # Folder backup nie istnieje
            pass
            
        self.on_select()

    def on_select(self, event=None):
        """
        Aktualizuje stan przycisków w zależności od zaznaczenia.
        
        Args:
            event: Zdarzenie zmiany zaznaczenia (opcjonalne)
        """
        selected = self.tree.selection()
        
        if selected:
            self.selected_backup_file = selected[0]
            # Skrócenie nazwy jeśli za długa
            display_name = self.selected_backup_file
            if len(display_name) > 40:
                display_name = display_name[:37] + "..."
            self.selected_label.config(
                text=f"📂 {display_name}",
                foreground=COLORS['primary']
            )
            self.restore_btn.config(state=tk.NORMAL)
            self.delete_btn.config(state=tk.NORMAL)
            self.export_btn.config(state=tk.NORMAL)
        else:
            self.selected_backup_file = None
            self.selected_label.config(
                text="📭 Nic nie zaznaczono",
                foreground=COLORS['secondary']
            )
            self.restore_btn.config(state=tk.DISABLED)
            self.delete_btn.config(state=tk.DISABLED)
            self.export_btn.config(state=tk.DISABLED)

    def export_backup(self):
        """
        Eksportuje zaznaczoną kopię zapasową do wybranej lokalizacji.
        Otwiera dialog wyboru miejsca zapisu.
        """
        if not self.selected_backup_file:
            messagebox.showwarning(
                "⚠️ Brak zaznaczenia", 
                "Najpierw zaznacz plik, który chcesz wyeksportować.", 
                parent=self
            )
            return

        source_path = os.path.join(BACKUP_FOLDER, self.selected_backup_file)
        
        # Otwarcie dialogu "Zapisz jako"
        destination_path = filedialog.asksaveasfilename(
            initialfile=self.selected_backup_file,
            defaultextension=".zip",
            filetypes=[("Archiwum ZIP", "*.zip")],
            title="Wybierz, gdzie zapisać kopię zapasową",
        )

        if destination_path:
            try:
                shutil.copy2(source_path, destination_path)
                messagebox.showinfo(
                    "✅ Sukces", 
                    f"Kopia zapasowa została pomyślnie wyeksportowana.", 
                    parent=self
                )
            except Exception as e:
                messagebox.showerror(
                    "❌ Błąd eksportu", 
                    f"Nie udało się zapisać pliku:\n{e}", 
                    parent=self
                )

    def import_backup(self):
        """
        Importuje kopię zapasową z zewnętrznej lokalizacji.
        Kopiuje wybrany plik do folderu backup projektu.
        """
        source_path = filedialog.askopenfilename(
            filetypes=[("Archiwum ZIP", "*.zip")],
            title="Wybierz plik kopii zapasowej do zaimportowania",
        )

        if source_path:
            filename = os.path.basename(source_path)
            destination_path = os.path.join(BACKUP_FOLDER, filename)

            # Sprawdzenie czy plik już istnieje
            if os.path.exists(destination_path):
                if not messagebox.askyesno(
                    "⚠️ Plik istnieje", 
                    f"Plik '{filename}' już istnieje.\nCzy chcesz go nadpisać?", 
                    parent=self
                ):
                    return

            try:
                shutil.copy2(source_path, destination_path)
                messagebox.showinfo(
                    "✅ Sukces", 
                    f"Plik '{filename}' został pomyślnie zaimportowany.", 
                    parent=self
                )
                self.populate_backup_list()
            except Exception as e:
                messagebox.showerror(
                    "❌ Błąd importu", 
                    f"Nie udało się skopiować pliku:\n{e}", 
                    parent=self
                )

    def create_backup(self):
        """
        Tworzy nową kopię zapasową z wybranymi elementami.
        Wyświetla pasek postępu podczas archiwizacji.
        """
        # Sprawdzenie czy coś wybrano
        components_to_backup = [key for key, var in self.backup_vars.items() if var.get()]
        if not components_to_backup:
            messagebox.showwarning(
                "⚠️ Nic nie wybrano", 
                "Zaznacz co najmniej jeden element do zarchiwizowania.", 
                parent=self
            )
            return
        
        # --- OKNO POSTĘPU ---
        
        progress_window = tk.Toplevel(self)
        progress_window.title("💾 Tworzenie Kopii Zapasowej")
        progress_window.transient(self)
        progress_window.grab_set()
        
        # Pozycjonowanie okna
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 150) // 2
        progress_window.geometry(f"400x180+{x}+{y}")
        progress_window.resizable(False, False)

        # Elementy interfejsu
        ttk.Label(
            progress_window, 
            text="📦 Przygotowywanie plików...", 
            font=("Segoe UI", 11), 
            padding=10
        ).pack(pady=(15, 5))
        
        progress_bar = ttk.Progressbar(
            progress_window, 
            orient="horizontal", 
            length=360, 
            mode="determinate"
        )
        progress_bar.pack(pady=5, padx=20)
        
        status_label = ttk.Label(
            progress_window, 
            text="", 
            padding=5, 
            wraplength=350
        )
        status_label.pack(pady=(5, 10))

        # --- FUNKCJA ARCHIWIZACJI ---
        
        def backup_thread_func():
            """Funkcja wykonywana w osobnym wątku - tworzy archiwum."""
            try:
                # Generowanie nazwy pliku
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"pelny_backup_projektu_{timestamp}.zip"
                backup_path = os.path.join(BACKUP_FOLDER, backup_filename)

                # Zbieranie plików do archiwizacji
                files_to_zip = []
                
                # Pliki JSON
                for key in ["owners", "parcels", "genealogy"]:
                    if self.backup_vars[key].get():
                        if os.path.exists(DATA_FILES[key]["path"]):
                            files_to_zip.append(
                                (DATA_FILES[key]["path"], os.path.basename(DATA_FILES[key]["path"]))
                            )
                        for related_path in DATA_FILES[key].get("related", []):
                            if os.path.exists(related_path):
                                files_to_zip.append(
                                    (related_path, os.path.basename(related_path))
                                )
                
                # Skany protokołów
                if self.backup_vars["scans"].get() and os.path.exists(PROTOKOLY_FOLDER):
                    for root, _, files in os.walk(PROTOKOLY_FOLDER):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, BASE_DIR)
                            files_to_zip.append((file_path, arcname))

                # Konfiguracja paska postępu
                progress_bar["maximum"] = len(files_to_zip)

                # Tworzenie archiwum ZIP
                with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i, (file_path, arcname) in enumerate(files_to_zip):
                        # Aktualizacja statusu
                        status_label.config(text=f"📁 Pakowanie: {os.path.basename(arcname)}")
                        zf.write(file_path, arcname)
                        progress_bar["value"] = i + 1
                        self.update_idletasks()

                # Oznaczenie sukcesu
                progress_window.success = True
                progress_window.backup_name = backup_filename
                
            except Exception as e:
                progress_window.success = False
                progress_window.error_message = str(e)
            finally:
                # Zamknięcie okna postępu
                self.after(100, progress_window.destroy)

        # Uruchomienie archiwizacji w wątku
        progress_window.success = None
        threading.Thread(target=backup_thread_func, daemon=True).start()
        self.wait_window(progress_window)

        # --- OBSŁUGA WYNIKU ---
        
        if hasattr(progress_window, "success") and progress_window.success:
            messagebox.showinfo(
                "✅ Sukces", 
                f"Utworzono kopię zapasową:\n{progress_window.backup_name}", 
                parent=self
            )
            self.populate_backup_list()
        elif hasattr(progress_window, "error_message") and progress_window.error_message:
            messagebox.showerror(
                "❌ Błąd", 
                f"Nie udało się utworzyć kopii zapasowej:\n{progress_window.error_message}", 
                parent=self
            )

    def delete_backup(self):
        """
        Usuwa zaznaczony plik kopii zapasowej.
        Wymaga potwierdzenia użytkownika.
        """
        if not hasattr(self, "selected_backup_file") or not self.selected_backup_file:
            return

        filename = self.selected_backup_file
        
        # Potwierdzenie usunięcia
        if messagebox.askyesno(
            "🗑️ Potwierdzenie usunięcia", 
            f"Czy na pewno chcesz trwale usunąć plik:\n\n{filename}?", 
            parent=self,
            icon="warning"
        ):
            backup_path = os.path.join(BACKUP_FOLDER, filename)
            try:
                os.remove(backup_path)
                messagebox.showinfo(
                    "✅ Sukces", 
                    f"Usunięto plik: {filename}", 
                    parent=self
                )
                self.populate_backup_list()
            except Exception as e:
                messagebox.showerror(
                    "❌ Błąd", 
                    f"Nie udało się usunąć pliku:\n{e}", 
                    parent=self
                )

    def restore_backup(self):
        """
        Przywraca dane z wybranej kopii zapasowej.
        UWAGA: Operacja nieodwracalna - nadpisuje obecne dane!
        """
        selected = self.tree.selection()
        if not selected:
            return
            
        filename = selected[0]

        # Ostrzeżenie dla użytkownika
        msg = (
            "⚠️ UWAGA! Ta operacja jest NIEODWRACALNA.\n\n"
            f"Czy na pewno chcesz przywrócić dane z pliku:\n'{filename}'?\n\n"
            "Spowoduje to:\n"
            "• NADPISANIE wszystkich istniejących danych (JSON)\n"
            "• ZASTĄPIENIE folderu ze skanami\n"
            "• UTRATĘ wszystkich niezapisanych zmian"
        )

        if messagebox.askyesno(
            "⚠️ POTWIERDZENIE KRYTYCZNEJ OPERACJI", 
            msg, 
            icon="warning", 
            parent=self
        ):
            backup_path = os.path.join(BACKUP_FOLDER, filename)
            
            try:
                with zipfile.ZipFile(backup_path, "r") as zf:
                    archive_contents = zf.namelist()

                    # --- PRZYWRACANIE SKANÓW ---
                    
                    scan_files_in_zip = [
                        f for f in archive_contents 
                        if f.startswith("assets/protokoly/")
                    ]
                    
                    if scan_files_in_zip:
                        # Usunięcie obecnego folderu
                        if os.path.exists(PROTOKOLY_FOLDER):
                            shutil.rmtree(PROTOKOLY_FOLDER)
                        
                        # Rozpakowanie skanów
                        for file_info in zf.infolist():
                            if file_info.filename.startswith("assets/protokoly/"):
                                zf.extract(file_info, path=BASE_DIR)
                    
                    # --- PRZYWRACANIE PLIKÓW JSON ---
                    
                    for key in ["owners", "parcels", "genealogy"]:
                        json_filename = os.path.basename(DATA_FILES[key]["path"])
                        if json_filename in archive_contents:
                            zf.extract(json_filename, path=BACKUP_FOLDER)
                        
                        # Przywracanie plików powiązanych
                        for related_path in DATA_FILES[key].get("related", []):
                            related_filename = os.path.basename(related_path)
                            if related_filename in archive_contents:
                                zf.extract(related_filename, path=BACKUP_FOLDER)

                messagebox.showinfo(
                    "✅ Sukces", 
                    "Kopia zapasowa została przywrócona pomyślnie.\n\n"
                    "Uruchom ponownie edytory, aby zobaczyć przywrócone dane.", 
                    parent=self
                )
                
            except Exception as e:
                messagebox.showerror(
                    "❌ Błąd przywracania", 
                    f"Wystąpił krytyczny błąd:\n{e}", 
                    parent=self
                )

# --- PUNKT WEJŚCIA APLIKACJI ---

if __name__ == "__main__":
    """
    Główny punkt wejścia aplikacji.
    Tworzy instancję launchera i uruchamia pętlę zdarzeń.
    """
    
    # Utworzenie i uruchomienie aplikacji
    app = AppLauncher()
    app.mainloop()