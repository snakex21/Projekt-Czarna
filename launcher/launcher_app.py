"""
================================================================================
Plik: launcher.py
System Mapy Katastralnej - Centrum Zarządzania
================================================================================
"""

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
import filecmp
import json
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from PIL import Image, ImageTk
except ImportError:
    messagebox.showerror("Brak zależności", "Biblioteka Pillow jest wymagana.\nZainstaluj: pip install Pillow")
    sys.exit(1)

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
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_FOLDER = os.path.join(BASE_DIR, "backup")
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
ASSETS_FOLDER = os.path.join(BASE_DIR, "assets")
PROTOKOLY_FOLDER = os.path.join(ASSETS_FOLDER, "protokoly")
SITE_ASSETS_FOLDER = os.path.join(ASSETS_FOLDER, "site")
LOCATIONS_DB_PATH = os.path.join(BASE_DIR, "launcher", "locations.db")
ICONS_SCAN_FOLDERS = [
    os.path.join(BASE_DIR, "icons"),
    os.path.join(ASSETS_FOLDER, "icons"),
]

# =============================================================================
# ZARZĄDZANIE MIEJSCOWOŚCIAMI - definicje funkcji przed get_data_files()
# =============================================================================
def init_locations_db():
    """Inicjalizuje bazę danych miejscowości."""
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            powiat TEXT,
            region TEXT,
            active INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_all_locations():
    """Zwraca wszystkie miejscowości z bazy danych."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, full_name, powiat, region, active FROM locations ORDER BY name")
    locations = cursor.fetchall()
    conn.close()
    return locations

def get_active_location():
    """Zwraca aktywną miejscowość jako tuple (id, name, full_name, powiat, region, active)."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, full_name, powiat, region, active FROM locations WHERE active = 1")
    location = cursor.fetchone()
    conn.close()
    return location

def get_active_location_name():
    """Zwraca nazwę aktywnej miejscowości lub None."""
    location = get_active_location()
    return location[1] if location else None

def set_active_location(location_id):
    """Ustawia miejscowość jako aktywną."""
    init_locations_db()
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    # Wyłącz wszystkie inne miejscowości
    cursor.execute("UPDATE locations SET active = 0")
    # Ustaw wybraną jako aktywną
    cursor.execute("UPDATE locations SET active = 1 WHERE id = ?", (location_id,))
    conn.commit()
    conn.close()

def add_location(name, full_name, powiat="", region=""):
    """Dodaje nową miejscowość do bazy danych i tworzy folder."""
    init_locations_db()

    # Utwórz folder dla miejscowości
    location_folder = os.path.join(BACKUP_FOLDER, name)
    os.makedirs(location_folder, exist_ok=True)

    # Utwórz domyślny plik .env
    env_path = os.path.join(location_folder, ".env")
    if not os.path.exists(env_path):
        default_env = """# Konfiguracja bazy danych PostgreSQL
DB_HOST=localhost
DB_NAME=mapa_czarna_db
DB_USER=postgres
DB_PASSWORD=1234
DB_PORT=5432

# Konfiguracja serwera Flask
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
FLASK_SECRET_KEY=change-me-once

# Ustawienia bezpieczeństwa
ADMIN_AUTH_ENABLED=0
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=
"""
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(default_env)

    # Dodaj do bazy danych
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO locations (name, full_name, powiat, region, active) VALUES (?, ?, ?, ?, 0)",
                      (name, full_name, powiat, region))
        conn.commit()
        location_id = cursor.lastrowid
        conn.close()
        return location_id
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Miejscowość '{name}' już istnieje")

def update_location(location_id, name, full_name, powiat, region):
    """Aktualizuje dane miejscowości."""
    init_locations_db()

    # Pobierz starą nazwę
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM locations WHERE id = ?", (location_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise ValueError("Miejscowość nie istnieje")

    old_name = result[0]

    # Zmień nazwę folderu jeśli nazwa się zmieniła
    if old_name != name:
        old_folder = os.path.join(BACKUP_FOLDER, old_name)
        new_folder = os.path.join(BACKUP_FOLDER, name)
        if os.path.exists(old_folder):
            os.rename(old_folder, new_folder)

    # Zaktualizuj bazę danych
    try:
        cursor.execute("UPDATE locations SET name = ?, full_name = ?, powiat = ?, region = ? WHERE id = ?",
                      (name, full_name, powiat, region, location_id))
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Miejscowość '{name}' już istnieje")

def delete_location(location_id):
    """Usuwa miejscowość z bazy danych i folder."""
    init_locations_db()

    # Pobierz nazwę miejscowości
    conn = sqlite3.connect(LOCATIONS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, active FROM locations WHERE id = ?", (location_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        raise ValueError("Miejscowość nie istnieje")

    name, active = result

    if active:
        conn.close()
        raise ValueError("Nie można usunąć aktywnej miejscowości")

    # Usuń folder
    location_folder = os.path.join(BACKUP_FOLDER, name)
    if os.path.exists(location_folder):
        shutil.rmtree(location_folder)

    # Usuń z bazy danych
    cursor.execute("DELETE FROM locations WHERE id = ?", (location_id,))
    conn.commit()
    conn.close()

def get_location_env_path(location_name=None):
    """Zwraca ścieżkę do pliku .env dla danej miejscowości."""
    if location_name is None:
        location_name = get_active_location_name()

    if location_name:
        return os.path.join(BACKUP_FOLDER, location_name, ".env")
    else:
        return os.path.join(BACKEND_DIR, ".env")

def migrate_old_backup_structure():
    """Migruje starą strukturę backup/ do nowej struktury z miejscowościami."""
    init_locations_db()

    # Sprawdź czy już są miejscowości
    locations = get_all_locations()
    if locations:
        # Już zmigrowano
        return

    print("🔄 Migracja struktury folderów backup...")

    # Sprawdź czy są stare pliki w backup/
    old_files = [
        "owner_data_to_import.json",
        "parcels_data.json",
        "demografia.json",
        "genealogia.json",
        "map_config.json"
    ]

    has_old_files = any(os.path.exists(os.path.join(BACKUP_FOLDER, f)) for f in old_files)

    if not has_old_files:
        print("ℹ️ Brak starych plików do migracji")
        return

    # Utwórz domyślną miejscowość "Czarna"
    default_location_name = "Czarna"
    default_location_folder = os.path.join(BACKUP_FOLDER, default_location_name)

    try:
        # Utwórz folder dla miejscowości
        os.makedirs(default_location_folder, exist_ok=True)

        # Przenieś stare pliki
        for filename in old_files:
            old_path = os.path.join(BACKUP_FOLDER, filename)
            if os.path.exists(old_path):
                new_path = os.path.join(default_location_folder, filename)
                shutil.move(old_path, new_path)
                print(f"✅ Przeniesiono: {filename}")

        # Przenieś plik .env jeśli istnieje
        old_env_path = os.path.join(BACKEND_DIR, ".env")
        if os.path.exists(old_env_path):
            new_env_path = os.path.join(default_location_folder, ".env")
            shutil.copy2(old_env_path, new_env_path)
            print(f"✅ Skopiowano: .env")

        # Dodaj miejscowość do bazy danych
        add_location(default_location_name, "Czarna", "", "")
        set_active_location(1)  # Ustaw jako aktywną (pierwsze ID to 1)

        print(f"✅ Migracja zakończona! Utworzono miejscowość: {default_location_name}")

    except Exception as e:
        print(f"❌ Błąd podczas migracji: {e}")
        import traceback
        traceback.print_exc()

def get_data_files(location_name=None):
    """Zwraca słownik ścieżek plików danych dla danej miejscowości."""
    if location_name is None:
        location_name = get_active_location_name()

    location_folder = os.path.join(BACKUP_FOLDER, location_name) if location_name else BACKUP_FOLDER

    return {
        "owners": {
            "path": os.path.join(location_folder, "owner_data_to_import.json"),
            "name": "Właściciele i Demografia",
            "related": [os.path.join(location_folder, "demografia.json")],
        },
        "parcels": {
            "path": os.path.join(location_folder, "parcels_data.json"),
            "name": "Działki (Geometria)",
            "related": [],
        },
        "genealogy": {
            "path": os.path.join(location_folder, "genealogia.json"),
            "name": "Genealogia",
            "related": [],
        },
    }

# Dla kompatybilności wstecznej
DATA_FILES = get_data_files()

URLS = {
    "strona_glowna": "http://127.0.0.1:5000/strona_glowna/index.html",
    "mapa": "http://127.0.0.1:5000/mapa/mapa.html",
    "admin": "http://127.0.0.1:5000/admin",
    "genealogy_editor": "http://127.0.0.1:5001/",
}

SCRIPTS = {
    "backend": {"path": os.path.join(BACKEND_DIR, "app.py"), "cwd": BACKEND_DIR},
    "migration": {"path": os.path.join(BACKEND_DIR, "migrate_data.py"), "cwd": BACKEND_DIR},
    "tests": {"path": "-m", "args": ["pytest", "tests", "-q"], "cwd": BACKEND_DIR},
    "owner_editor": {"path": os.path.join(TOOLS_DIR, "owner_editor.py"), "cwd": TOOLS_DIR},
    "parcel_editor": {"path": os.path.join(TOOLS_DIR, "parcel_editor", "parcel_editor_app.py"), "cwd": os.path.join(TOOLS_DIR, "parcel_editor")},
    "genealogy_editor": {"path": os.path.join(TOOLS_DIR, "genealogy_editor", "editor_app.py"), "cwd": os.path.join(TOOLS_DIR, "genealogy_editor")},
}

COLORS = {
    'primary': '#0d6efd', 'success': '#198754', 'danger': '#dc3545',
    'warning': '#ffc107', 'info': '#0dcaf0', 'secondary': '#6c757d',
    'dark': '#212529', 'light': '#f8f9fa',
}

# =============================================================================
# FUNKCJE POMOCNICZE
# =============================================================================
def get_local_ip():
    """Pobiera lokalny adres IP komputera."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def check_env_configuration():
    """Sprawdza i konfiguruje plik .env dla aktywnej miejscowości."""
    # Najpierw sprawdź czy jest aktywna miejscowość
    active_location = get_active_location()

    if not active_location:
        # Brak miejscowości - użyj domyślnej lokalizacji backend/.env
        env_path = os.path.join(BACKEND_DIR, ".env")
    else:
        env_path = get_location_env_path()

    env_example_path = os.path.join(BACKEND_DIR, ".env.example")

    if os.path.exists(env_path):
        return True

    if os.path.exists(env_example_path):
        try:
            # Upewnij się, że folder istnieje
            os.makedirs(os.path.dirname(env_path), exist_ok=True)
            shutil.copy(env_example_path, env_path)
            print("✅ Utworzono plik .env z przykładowej konfiguracji")
            return True
        except Exception as e:
            print(f"⚠️ Nie można utworzyć pliku .env: {e}")
            return False

    try:
        default_env = """# Konfiguracja bazy danych PostgreSQL
DB_HOST=localhost
DB_NAME=mapa_czarna_db
DB_USER=postgres
DB_PASSWORD=1234
DB_PORT=5432

# Konfiguracja serwera Flask
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
FLASK_SECRET_KEY=change-me-once

# Ustawienia bezpieczeństwa
ADMIN_AUTH_ENABLED=0
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=
"""
        # Upewnij się, że folder istnieje
        os.makedirs(os.path.dirname(env_path), exist_ok=True)
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(default_env)
        print("✅ Utworzono domyślny plik .env")
        return True
    except Exception as e:
        print(f"⚠️ Nie można utworzyć pliku .env: {e}")
        return False

def _auto_sync_site_icon():
    """Automatycznie wykrywa istniejący favicon w assets/site lub kopiuje pierwszą znalezioną ikonę 
    z folderów icons → assets/site i zapisuje ścieżkę w konfiguracji bazy danych."""
    
    # KROK 1: Sprawdź czy w folderze site już istnieje favicon
    existing_favicon = _find_existing_favicon_in_site()
    if existing_favicon:
        print(f"🔍 Wykryto istniejący favicon: {existing_favicon}")
        _save_favicon_to_database(existing_favicon)
        return
    
    # KROK 2: Jeśli brak favicon w site/, szukaj w folderach icons i kopiuj pierwszy znaleziony  
    for folder in ICONS_SCAN_FOLDERS:
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            if not fname.lower().endswith((".png", ".ico", ".jpg", ".jpeg")):
                continue
            src = os.path.join(folder, fname)
            dest = os.path.join(SITE_ASSETS_FOLDER, fname)
            
            # Kopiuj tylko jeśli plik nie istnieje lub jest różny
            if not os.path.exists(dest) or not filecmp.cmp(src, dest, shallow=False):
                os.makedirs(SITE_ASSETS_FOLDER, exist_ok=True)
                shutil.copy2(src, dest)
                print(f"📋 Skopiowano favicon z {folder}: {fname}")
            
            _save_favicon_to_database(fname)
            return  # używamy tylko pierwszego pliku

def _find_existing_favicon_in_site():
    """Szuka istniejącego pliku favicon w folderze assets/site.
    Zwraca nazwę pliku lub None jeśli nie znaleziono."""
    
    if not os.path.isdir(SITE_ASSETS_FOLDER):
        return None
    
    # Standardowe nazwy favicon (z priorytetem)
    standard_names = ["favicon.ico", "favicon.png", "favicon.jpg", "favicon.jpeg"]
    
    # Najpierw sprawdź standardowe nazwy
    for name in standard_names:
        full_path = os.path.join(SITE_ASSETS_FOLDER, name)
        if os.path.isfile(full_path):
            return name
    
    # Jeśli nie ma standardowych nazw, szukaj plików zaczynających się od "favicon"
    try:
        for fname in os.listdir(SITE_ASSETS_FOLDER):
            if (fname.lower().startswith("favicon") and 
                any(fname.lower().endswith(ext) for ext in [".png", ".ico", ".jpg", ".jpeg"])):
                return fname
    except OSError:
        pass
    
    return None

def _save_favicon_to_database(filename):
    """Zapisuje ścieżkę favicon do bazy danych."""
    try:
        db_cfg = get_db_config_from_env()
        with psycopg2.connect(**db_cfg) as conn, conn.cursor() as cur:
            rel_path = os.path.join("site", filename).replace("\\", "/")
            cur.execute(
                "INSERT INTO konfiguracja_systemu (klucz, wartosc, opis) "
                "VALUES ('site_favicon', %s, %s) "
                "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
                (json.dumps({"path": rel_path}), "Ścieżka do ikony witryny (favicon)")
            )
            conn.commit()
            print(f"✅ Zapisano favicon do bazy danych: {rel_path}")
    except psycopg2.Error as e:
        # Baza może jeszcze nie istnieć – to nie błąd krytyczny przy pierwszym uruchomieniu
        print(f"ℹ️ Nie można zapisać favicon do bazy (baza może nie istnieć): {e}")
        pass

def check_backup_folder_files():
    """Sprawdza folder aktywnej miejscowości i tworzy brakujące pliki JSON."""
    location_name = get_active_location_name()
    if not location_name:
        print("ℹ️ Brak aktywnej miejscowości, pomijam tworzenie plików danych")
        return

    location_folder = os.path.join(BACKUP_FOLDER, location_name)

    files_to_check = {
        "map_config.json": {
            "calibration": {"sw": {"lat": 50.0414, "lng": 21.2261}, "ne": {"lat": 50.0814, "lng": 21.2661}},
            "defaults": {"center": {"lat": 50.0614, "lng": 21.2461}, "zoom": 14}
        },
        "owner_data_to_import.json": {},
        "parcels_data.json": {},
        "demografia.json": [],
        "genealogia.json": {"persons": []}
    }

    os.makedirs(location_folder, exist_ok=True)

    for filename, default_content in files_to_check.items():
        path = os.path.join(location_folder, filename)
        if not os.path.exists(path):
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(default_content, f, indent=4, ensure_ascii=False)
                print(f"✅ Utworzono domyślny plik: {filename}")
            except Exception as e:
                print(f"⚠️ Nie można utworzyć pliku {filename}: {e}")

def read_env_config(key_prefix=None):
    """Odczytuje konfigurację z pliku .env aktywnej miejscowości."""
    # Sprawdź czy jest aktywna miejscowość
    active_location = get_active_location()

    if not active_location:
        # Brak miejscowości - użyj domyślnej lokalizacji backend/.env
        env_path = os.path.join(BACKEND_DIR, ".env")
    else:
        env_path = get_location_env_path()

    config = {}

    if not os.path.exists(env_path):
        return config

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key, value = key.strip(), value.strip()
                    if not key_prefix or key.startswith(key_prefix):
                        config[key] = value
    except Exception as e:
        print(f"Błąd odczytu .env: {e}")

    return config

def get_db_config_from_env():
    """Odczytuje konfigurację bazy danych z pliku .env."""
    env_config = read_env_config('DB_')
    return {
        "host": env_config.get('DB_HOST', 'localhost'),
        "dbname": env_config.get('DB_NAME', 'mapa_czarna_db'),
        "user": env_config.get('DB_USER', 'postgres'),
        "password": env_config.get('DB_PASSWORD', '1234'),
        "port": env_config.get('DB_PORT', '5432')
    }

def get_flask_config():
    """Odczytuje konfigurację Flask z pliku .env."""
    env_config = read_env_config('FLASK_')
    return {
        'host': env_config.get('FLASK_HOST', '127.0.0.1'),
        'port': env_config.get('FLASK_PORT', '5000')
    }

# =============================================================================
# GŁÓWNA KLASA APLIKACJI
# =============================================================================
class AppLauncher(tk.Tk):
    """Główna klasa aplikacji centrum zarządzania."""
    
    def __init__(self):
        """Inicjalizacja głównego okna aplikacji."""
        super().__init__()
        self.title("🗺️ Centrum Zarządzania - System Mapy Katastralnej")
        self.setup_window_geometry()
        
        self.managed_processes = {}
        self.event_queue = queue.Queue()
        self.setup_styles()

        # Migracja starych danych
        migrate_old_backup_structure()

        check_env_configuration()
        check_backup_folder_files()
        _auto_sync_site_icon()

        self.create_widgets()
        self._last_port = self.load_flask_config().get("port")
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.process_queue()

    def setup_window_geometry(self):
        """Inteligentnie dostosowuje rozmiar okna do ekranu i DPI."""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        dpi = self.winfo_fpixels("1i")
        scale_factor = dpi / 96
        
        if sw <= 1920:
            w, h = min(int(sw * 0.85), 1400), min(int(sh * 0.85), 850)
        elif sw <= 2560:
            w, h = min(int(sw * 0.75), 1600), min(int(sh * 0.80), 900)
        else:
            w, h = min(int(sw * 0.65), 1800), min(int(sh * 0.75), 1000)
        
        if scale_factor > 1.25:
            w = int(w / scale_factor * 1.2)
            h = int(h / scale_factor * 1.2)
        
        min_w = max(1000, int(900 * scale_factor))
        min_h = max(700, int(650 * scale_factor))
        w, h = max(w, min_w), max(h, min_h)
        
        x = (sw - w) // 2
        y = (sh - h) // 2
        
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min_w, min_h)
        self.scale_factor = scale_factor
        self.is_high_dpi = scale_factor > 1.25

    def setup_styles(self):
        """Konfiguruje style i czcionki dla aplikacji."""
        dpi = self.winfo_fpixels("1i")
        scale = dpi / 96
        self.tk.call("tk", "scaling", scale)
        
        base_size = 10 if scale <= 1.25 else (11 if scale <= 1.5 else 12)
        
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=base_size)
        
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        
        button_padding = int(6 * scale) if scale > 1.25 else 8
        self.style.configure("TButton", padding=button_padding, relief="flat", font=("Segoe UI", base_size))
        
        # Konfiguracja kolorów przycisków
        for name, color in [("Primary", COLORS['primary']), ("Success", COLORS['success']), 
                            ("Danger", COLORS['danger']), ("Info", COLORS['info']), 
                            ("Warning", COLORS['warning'])]:
            fg = "white" if name != "Warning" else "black"
            self.style.configure(f"{name}.TButton", foreground=fg, background=color)
            darker = color.replace('f', 'd').replace('e', 'c')
            self.style.map(f"{name}.TButton", background=[('active', darker), ('pressed', darker)])
        
        self.style.configure("Link.TLabel", foreground=COLORS['primary'], font=("Segoe UI", base_size, "underline"))
        self.style.configure("Heading.TLabel", font=("Segoe UI", base_size + 2, "bold"))
        
        row_height = int(base_size * 2.2)
        self.style.configure("Treeview", rowheight=row_height, font=("Segoe UI", base_size))
        self.style.configure("Treeview.Heading", font=("Segoe UI", base_size, "bold"))
        
        self.base_font_size = base_size

    def create_console_widget(self, parent):
        """Tworzy widget konsoli z ciemnym motywem."""
        console = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, bg="#1e1e1e", fg="#e0e0e0",
            font=("Consolas", self.base_font_size),
            insertbackground="#ffffff", selectbackground="#3a3a3a",
            selectforeground="#ffffff", height=10
        )
        console.pack(fill=tk.BOTH, expand=True)
        console.configure(state="disabled")
        return console

    def process_queue(self):
        """Przetwarza zdarzenia z kolejki w pętli głównej."""
        try:
            while True:
                key, event_type = self.event_queue.get_nowait()
                if event_type == "finished":
                    self.handle_process_finished(key)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_queue)

    def handle_process_finished(self, key):
        """Obsługuje zdarzenie zakończenia procesu."""
        if key not in self.managed_processes:
            return
            
        info = self.managed_processes[key]
        name = info["name"]
        
        msg = f"--- Proces '{name}' zakończył działanie ---\n"
        self.log(msg, console=info["console"])
        self.log(msg)
        
        self.notebook.forget(info["tab_frame"])
        del self.managed_processes[key]
        self.update_processes_ui()
        
        if key == "backend":
            self.server_btn.config(text="🚀 Uruchom Serwer Backend", style="Success.TButton")
            self.network_server_btn.config(text="🌐 Uruchom Serwer Sieciowy", style="Info.TButton")
            
            if info.get("network_mode"):
                messagebox.showwarning(
                    "Serwer sieciowy się wyłączył",
                    "Proces zakończył się niespodziewanie.\n\n"
                    "Diagnostyka: uruchom ręcznie w folderze backend:\n"
                    "python _network_server_wrapper.py"
                )

    def create_widgets(self):
        """Tworzy kompletny interfejs użytkownika."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Nagłówek
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            header_frame, text="🗺️ System Zarządzania Mapą Katastralną",
            style="Heading.TLabel", font=("Segoe UI", self.base_font_size + 4, "bold")
        ).pack(side=tk.LEFT)
        
        ttk.Label(header_frame, text="Status: Gotowy", foreground=COLORS['success']).pack(side=tk.RIGHT, padx=10)

        # Sekcja wyboru miejscowości
        location_frame = ttk.LabelFrame(main_frame, text="📍 Miejscowość", padding="10")
        location_frame.pack(fill=tk.X, pady=5)

        location_controls = ttk.Frame(location_frame)
        location_controls.pack(fill=tk.X)

        ttk.Label(location_controls, text="Aktywna miejscowość:", font=("Segoe UI", self.base_font_size)).pack(side=tk.LEFT, padx=5)

        self.location_var = tk.StringVar()
        self.location_combo = ttk.Combobox(location_controls, textvariable=self.location_var, state="readonly", width=30)
        self.location_combo.pack(side=tk.LEFT, padx=5)
        self.location_combo.bind("<<ComboboxSelected>>", self.on_location_selected)

        ttk.Button(location_controls, text="🔄 Odśwież", command=self.refresh_locations,
                  style="Info.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(location_controls, text="⚙️ Zarządzaj Miejscowościami", command=self.open_location_manager,
                  style="Primary.TButton").pack(side=tk.LEFT, padx=5)

        self.refresh_locations()

        # Sekcja operacji głównych
        operations_frame = ttk.LabelFrame(main_frame, text="⚙️ Operacje Główne", padding="10")
        operations_frame.pack(fill=tk.X, pady=5)
        
        # Pierwszy rząd przycisków
        row1 = ttk.Frame(operations_frame)
        row1.pack(fill=tk.X, pady=(0, 5))
        
        self.server_btn = ttk.Button(row1, text="🚀 Uruchom Serwer Backend", command=self.toggle_server, style="Success.TButton")
        self.server_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.network_server_btn = ttk.Button(row1, text="🌐 Uruchom Serwer Sieciowy", command=self.toggle_network_server, style="Info.TButton")
        self.network_server_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(row1, text="🔄 Migruj Dane do Bazy", 
                  command=lambda: self.run_script_in_thread(SCRIPTS["migration"], "Skrypt Migracyjny"),
                  style="Info.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Drugi rząd przycisków
        row2 = ttk.Frame(operations_frame)
        row2.pack(fill=tk.X)
        
        buttons = [
            ("💾 Menedżer Kopii", self.open_backup_manager, "Primary"),
            ("📍 Kalibracja Mapy", self.open_map_calibrator, "Primary"),
            ("⚙️ Konfiguracja DB", self.open_env_editor, "Secondary"),
            ("🔐 Ustawienia Administratora", self.open_admin_settings, "Warning"),
            ("🖼️ Ustawienia Witryny", self.open_site_settings, "Primary"),
            ("🛡️ Bezpieczeństwo", self.open_security_manager, "Primary")
        ]
        
        for text, cmd, style in buttons:
            ttk.Button(row2, text=text, command=cmd, style=f"{style}.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Sekcja narzędzi deweloperskich
        tools_frame = ttk.LabelFrame(main_frame, text="🛠️ Narzędzia Deweloperskie", padding="10")
        tools_frame.pack(fill=tk.X, pady=5)
        
        editors_container = ttk.Frame(tools_frame)
        editors_container.pack(fill=tk.X)
        
        editor_buttons = [
            ("👥 Edytor Właścicieli", "owner_editor"),
            ("🗺️ Edytor Działek", "parcel_editor"),
            ("🌳 Edytor Genealogii", "genealogy_editor"),
        ]
        
        for text, key in editor_buttons:
            ttk.Button(editors_container, text=text,
                      command=lambda k=key, n=text: self.start_managed_process(k, n),
                      style="Primary.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(editors_container, text="🧪 Uruchom Testy Jednostkowe",
                  command=self.run_pytest, style="Info.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Sekcja szybkiego dostępu
        links_frame = ttk.LabelFrame(main_frame, text="🌐 Szybki Dostęp (wymaga uruchomionego serwera)", padding="10")
        links_frame.pack(fill=tk.X, pady=5)
        
        links_container = ttk.Frame(links_frame)
        links_container.pack(fill=tk.X)
        
        self.quick_link_buttons = []
        link_defs = [
            ("🏠 Strona Główna", "/strona_glowna/index.html", "Success"),
            ("🗺️ Mapa Interaktywna", "/mapa/mapa.html", "Info"),
            ("⚙️ Panel Administracyjny", "/admin", "Warning"),
        ]
        
        for text, path, style in link_defs:
            btn = ttk.Button(links_container, text=text, style=f"{style}.TButton")
            btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            self.quick_link_buttons.append((btn, path))
        
        self._env_mtime = None
        self.refresh_quick_links()
        self.start_env_watcher()
        
        # Sekcja procesów
        self.processes_frame = ttk.LabelFrame(main_frame, text="📊 Uruchomione Procesy", padding="10")
        self.processes_frame.pack(fill=tk.X, pady=5)
        self.update_processes_ui()
        
        # Sekcja konsol
        console_container = ttk.LabelFrame(main_frame, text="💻 Konsole Wyjściowe", padding="10")
        console_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.notebook = ttk.Notebook(console_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
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
        """Wypisuje wiadomość do konsoli."""
        target_console = console or self.main_console
        target_console.configure(state="normal")
        target_console.insert(tk.END, message)
        target_console.see(tk.END)
        target_console.configure(state="disabled")

    def update_processes_ui(self):
        """Odświeża listę uruchomionych procesów."""
        for widget in self.processes_frame.winfo_children():
            widget.destroy()
        
        if not self.managed_processes:
            ttk.Label(self.processes_frame, text="📭 Brak uruchomionych procesów",
                     foreground=COLORS['secondary']).pack(pady=10)
            return
        
        for key, info in self.managed_processes.items():
            proc_frame = ttk.Frame(self.processes_frame)
            proc_frame.pack(fill=tk.X, pady=3, padx=5)
            
            ttk.Label(proc_frame, text=f"🟢 {info['name']} (PID: {info['process'].pid})",
                     font=("Segoe UI", 10)).pack(side=tk.LEFT)
            
            ttk.Button(proc_frame, text="⏹️ Zatrzymaj", style="Danger.TButton",
                      command=lambda k=key: self.stop_managed_process(k),
                      width=12).pack(side=tk.RIGHT, padx=5)

    def load_flask_config(self):
        """Czyta aktualny host/port z backend/.env."""
        cfg = get_flask_config()
        try:
            cfg['port'] = str(int(cfg.get('port', '5000')))
        except:
            cfg['port'] = '5000'
        cfg['host'] = cfg.get('host', '127.0.0.1')
        return cfg

    def refresh_quick_links(self):
        """Aktualizuje komendy przycisków Szybkiego Dostępu."""
        self.current_flask_config = self.load_flask_config()
        base_url = f"http://{self.current_flask_config['host']}:{self.current_flask_config['port']}"
        for btn, path in getattr(self, "quick_link_buttons", []):
            url = base_url + path
            btn.configure(command=lambda u=url: webbrowser.open_new_tab(u))

    def get_env_mtime(self):
        """Zwraca czas modyfikacji pliku backend/.env."""
        env_path = os.path.join(BACKEND_DIR, ".env")
        try:
            return os.path.getmtime(env_path)
        except OSError:
            return None

    def start_env_watcher(self):
        """Cyklicznie sprawdza zmiany w pliku .env."""
        def _tick():
            try:
                mtime = self.get_env_mtime()
                if self._env_mtime is None:
                    self._env_mtime = mtime
                elif mtime is not None and mtime != self._env_mtime:
                    self._env_mtime = mtime
                    self.on_env_changed()
            finally:
                self.after(2000, _tick)
        _tick()

    def on_env_changed(self):
        """Reakcja na zmianę .env."""
        old_port = getattr(self, "_last_port", None)
        was_running = "backend" in self.managed_processes
        was_network = self.managed_processes.get("backend", {}).get("network_mode", False)
        
        self.refresh_quick_links()
        new_port = self.current_flask_config.get("port")
        self._last_port = new_port
        
        self.log(f"🔎 Wykryto zmianę .env – port {old_port} ➜ {new_port}\n")
        
        if not was_running or not old_port or not new_port or old_port == new_port:
            return
        
        if messagebox.askyesno("Wykryto zmianę portu",
                               f"Zmieniono port z {old_port} na {new_port}.\n\n"
                               "Zrestartować serwer backend?"):
            self.stop_managed_process("backend")
            
            try:
                self.setup_firewall_rule_for_port(int(new_port))
            except:
                pass
            
            def _restart():
                if was_network:
                    self.start_network_server()
                else:
                    self.start_managed_process("backend", "Serwer Backend (Lokalny)")
                    self.server_btn.config(text="⏹️ Zatrzymaj Serwer (Lokalny)", style="Danger.TButton")
            
            self.after(600, _restart)

    def setup_firewall_rule_for_port(self, port: int):
        """Konfiguruje regułę zapory Windows dla portu."""
        if platform.system() != "Windows":
            return
        
        rule_name = f"Flask Server Port {port}"
        check_cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return
        
        add_cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport={port} enable=yes profile=any'
        subprocess.run(add_cmd, shell=True)

    def refresh_locations(self):
        """Odświeża listę miejscowości w menu rozwijanym."""
        locations = get_all_locations()
        location_names = [loc[1] for loc in locations]  # loc[1] to name
        self.location_combo['values'] = location_names

        # Ustaw aktywną miejscowość
        active_location = get_active_location()
        if active_location:
            self.location_var.set(active_location[1])  # active_location[1] to name
        elif location_names:
            # Jeśli brak aktywnej, ale są miejscowości, ustaw pierwszą
            self.location_var.set(location_names[0])
            # I ustaw ją jako aktywną w bazie
            set_active_location(locations[0][0])
        else:
            self.location_var.set("(brak miejscowości)")

    def on_location_selected(self, event=None):
        """Obsługuje zmianę wybranej miejscowości."""
        selected_name = self.location_var.get()
        if not selected_name or selected_name == "(brak miejscowości)":
            return

        # Znajdź ID wybranej miejscowości
        locations = get_all_locations()
        for loc in locations:
            if loc[1] == selected_name:  # loc[1] to name
                set_active_location(loc[0])  # loc[0] to id
                messagebox.showinfo("✅ Zmieniono miejscowość",
                                   f"Aktywna miejscowość: {selected_name}\n\n"
                                   "Niektóre zmiany mogą wymagać ponownego uruchomienia serwera.")
                # Odśwież DATA_FILES
                global DATA_FILES
                DATA_FILES = get_data_files()
                break

    def open_location_manager(self):
        """Otwiera okno zarządzania miejscowościami."""
        manager = LocationManager(self)
        self.wait_window(manager)
        self.refresh_locations()

    def open_backup_manager(self):
        """Otwiera okno menedżera kopii zapasowych."""
        if any(key.endswith("_editor") for key in self.managed_processes):
            messagebox.showwarning("⚠️ Uwaga",
                                 "Zamknij wszystkie aktywne edytory przed zarządzaniem kopiami zapasowymi,\n"
                                 "aby uniknąć konfliktów plików.")
            return
        
        manager = BackupManager(self)
        self.wait_window(manager)

    def open_map_calibrator(self):
        """Otwiera okno kalibracji mapy."""
        if "backend" in self.managed_processes:
            messagebox.showwarning("Serwer aktywny",
                                 "Zatrzymaj serwer backend przed zmianą kalibracji.\n"
                                 "Zmiany zostaną zastosowane po ponownym uruchomieniu serwera.",
                                 parent=self)
        
        MapCalibrator(self)

    def open_env_editor(self):
        """Otwiera edytor konfiguracji .env."""
        env_path = os.path.join(BACKEND_DIR, ".env")
        
        if not os.path.exists(env_path):
            if not check_env_configuration():
                messagebox.showerror("❌ Błąd", "Nie można utworzyć pliku .env")
                return
        
        EnvEditor(self, env_path)

    def open_admin_settings(self):
        """Otwiera okno ustawień administratora."""
        AdminSettings(self)

    def open_site_settings(self):
        """Otwiera okno ustawień witryny."""
        if "backend" in self.managed_processes:
            messagebox.showwarning("Serwer aktywny",
                                 "Zatrzymaj serwer backend przed zmianą ustawień witryny.\n"
                                 "Zmiany zostaną zastosowane po ponownym uruchomieniu serwera.",
                                 parent=self)
        
        SiteSettingsManager(self)

    def open_security_manager(self):
        """Otwiera okno menedżera bezpieczeństwa."""
        if "backend" not in self.managed_processes:
            messagebox.showwarning("Serwer nieaktywny",
                                 "Uruchom serwer backend, aby zarządzać bezpieczeństwem.",
                                 parent=self)
            return
        
        SecurityManager(self)

    def start_managed_process(self, key, name):
        """Uruchamia zewnętrzny skrypt jako zarządzany proces."""
        if key in self.managed_processes:
            messagebox.showwarning("⚠️ Proces już działa", f"Proces '{name}' jest już uruchomiony.")
            return
        
        self.log(f"🚀 Uruchamianie: {name}...\n")
        script_info = SCRIPTS[key]
        
        # Tworzenie konsoli
        tab_frame = ttk.Frame(self.notebook)
        console = self.create_console_widget(tab_frame)
        self.notebook.add(tab_frame, text=f"📋 {name}")
        self.notebook.select(tab_frame)
        
        # Przygotowanie środowiska i komendy
        env = self._prepare_process_env()
        command = self._prepare_command(key, script_info)
        
        # Uruchomienie procesu
        creation_flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if platform.system() == "nt" else 0
        
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=script_info["cwd"], encoding="utf-8",
            errors="replace", creationflags=creation_flags, env=env
        )
        
        self.managed_processes[key] = {
            "process": process, "console": console,
            "tab_frame": tab_frame, "name": name
        }
        
        threading.Thread(target=self.read_process_output, args=(key,), daemon=True).start()
        
        if key in URLS:
            threading.Timer(1.5, lambda: webbrowser.open(URLS[key])).start()
        
        self.update_processes_ui()

    def stop_managed_process(self, key):
        """Zatrzymuje zarządzany proces."""
        if key not in self.managed_processes:
            return
        
        info = self.managed_processes[key]
        process = info["process"]
        name = info["name"]
        
        msg = f"\n⏹️ Zatrzymywanie procesu: {name}...\n"
        self.log(msg, console=info["console"])
        self.log(msg)
        
        try:
            if platform.system() == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            process.wait(timeout=2)
        except (subprocess.TimeoutExpired, ProcessLookupError, PermissionError):
            msg = f"⚠️ Proces '{name}' nie odpowiedział – wymuszam zatrzymanie.\n"
            self.log(msg, console=info["console"])
            self.log(msg)
            process.kill()
            process.wait()
        
        del self.managed_processes[key]
        self.notebook.forget(info["tab_frame"])
        self.update_processes_ui()
        
        if key == "backend":
            self.server_btn.config(text="🚀 Uruchom Serwer Backend", style="Success.TButton")

    def read_process_output(self, key):
        """Czyta wyjście z procesu."""
        if key not in self.managed_processes:
            return
        
        info = self.managed_processes.get(key)
        if not info:
            return
        
        process = info["process"]
        console = info["console"]
        
        for line in iter(process.stdout.readline, ""):
            self.after(0, self.log, line, console)
        
        self.event_queue.put((key, "finished"))

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

    def run_pytest(self):
        """Uruchamia testy jednostkowe."""
        def target():
            self.log("🧪 Start testów jednostkowych (pytest)...\n")
            try:
                env = self._prepare_process_env()
                cmd = [sys.executable, "-m", "pytest", "tests", "-q"]
                creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "nt" else 0
                
                proc = subprocess.Popen(cmd, cwd=BACKEND_DIR, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                      errors="replace", creationflags=creation_flags, env=env)
                
                for line in iter(proc.stdout.readline, ""):
                    self.log(line)
                proc.stdout.close()
                
                rc = proc.wait()
                status = "✅ Testy zakończone pomyślnie." if rc == 0 else f"❌ Testy zakończone błędem (kod: {rc})."
                self.log(f"{status}\n")
            except FileNotFoundError:
                self.log("❌ Nie znaleziono pytest. Zainstaluj: pip install pytest\n")
            except Exception as e:
                self.log(f"❌ Błąd uruchamiania testów: {e}\n")
        
        threading.Thread(target=target, daemon=True).start()

    def toggle_server(self, network_mode=False):
        """Przełącza stan serwera backend."""
        if "backend" in self.managed_processes:
            self.stop_managed_process("backend")
        else:
            if network_mode:
                self.start_network_server()
            else:
                self.start_managed_process("backend", "Serwer Backend (Lokalny)")
                self.server_btn.config(text="⏹️ Zatrzymaj Serwer (Lokalny)", style="Danger.TButton")

    def toggle_network_server(self):
        """Przełącza serwer sieciowy."""
        if "backend" in self.managed_processes:
            if self.managed_processes["backend"].get("network_mode"):
                self.stop_managed_process("backend")
                self.network_server_btn.config(text="🌐 Uruchom Serwer Sieciowy", style="Info.TButton")
            else:
                messagebox.showwarning("⚠️ Uwaga",
                                     "Lokalny serwer jest już uruchomiony.\n"
                                     "Zatrzymaj go najpierw, aby uruchomić serwer sieciowy.")
        else:
            self.toggle_server(network_mode=True)

    def start_network_server(self):
        """Uruchamia serwer Flask dostępny w sieci lokalnej."""
        if platform.system() == "Windows":
            self.setup_firewall_rule()
        
        local_ip = get_local_ip()
        flask_config = get_flask_config()
        port = int(flask_config['port'])
        
        self.log(f"🌐 Uruchamianie serwera w trybie SIECIOWYM...\n")
        self.log(f"📡 Serwer będzie dostępny pod adresami:\n")
        self.log(f"   • Lokalnie: http://127.0.0.1:{port}\n")
        self.log(f"   • W sieci LAN: http://{local_ip}:{port}\n")
        self.log(f"   • Alternatywnie: http://{socket.gethostname()}:{port}\n")
        self.log(f"⚠️ UWAGA: Upewnij się, że firewall nie blokuje portu {port}!\n\n")
        
        # Tworzenie konsoli
        tab_frame = ttk.Frame(self.notebook)
        console = self.create_console_widget(tab_frame)
        self.notebook.add(tab_frame, text=f"🌐 Serwer Sieciowy")
        self.notebook.select(tab_frame)
        
        # Tworzenie skryptu wrapper
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
        
        wrapper_path = os.path.join(BACKEND_DIR, "_network_server_wrapper.py")
        with open(wrapper_path, 'w', encoding='utf-8') as f:
            f.write(wrapper_code)
        
        # Uruchomienie procesu
        env = self._prepare_process_env()
        creation_flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if platform.system() == "nt" else 0
        
        process = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-u", wrapper_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            cwd=BACKEND_DIR, encoding="utf-8", errors="replace",
            creationflags=creation_flags, env=env
        )
        
        self.managed_processes["backend"] = {
            "process": process, "console": console, "tab_frame": tab_frame,
            "name": "Serwer Backend (Sieciowy)", "network_mode": True, "local_ip": local_ip
        }
        
        threading.Thread(target=self.read_process_output, args=("backend",), daemon=True).start()
        
        self.network_server_btn.config(text="⏹️ Zatrzymaj Serwer Sieciowy", style="Danger.TButton")
        
        self.show_network_info_dialog(local_ip)
        self.update_processes_ui()

    def setup_firewall_rule(self):
        """Konfiguruje regułę firewall Windows."""
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
        
        add_cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport={port} enable=yes profile=any'
        
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            
            if not is_admin:
                response = messagebox.askyesno(
                    "🔐 Wymagane uprawnienia administratora",
                    "Aby automatycznie skonfigurować firewall, aplikacja musi być uruchomiona jako Administrator.\n\n"
                    "• TAK - Uruchomić ponownie jako Administrator?\n"
                    "• NIE - Skonfigurować firewall ręcznie później?",
                    icon="warning"
                )
                
                if response:
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                    self.destroy()
                    sys.exit(0)
                else:
                    self.log("⚠️ Firewall nie został skonfigurowany. Skonfiguruj go ręcznie.\n")
                    self.show_firewall_instructions()
                    return False
            
            result = subprocess.run(add_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log("✅ Reguła firewall została dodana pomyślnie!\n")
                messagebox.showinfo("✅ Sukces", f"Reguła firewall została skonfigurowana.\nPort {port} jest teraz otwarty.")
                return True
            else:
                self.log(f"❌ Błąd dodawania reguły: {result.stderr}\n")
                return False
        except Exception as e:
            self.log(f"❌ Błąd konfiguracji firewall: {e}\n")
            return False

    def show_firewall_instructions(self):
        """Wyświetla instrukcje ręcznej konfiguracji firewall."""
        FirewallInstructions(self)

    def show_network_info_dialog(self, local_ip):
        """Wyświetla okno dialogowe z informacjami o dostępie sieciowym."""
        NetworkInfoDialog(self, local_ip)

    def on_closing(self):
        """Obsługuje zdarzenie zamknięcia głównego okna."""
        if self.managed_processes:
            network_server = any(p.get("network_mode") for p in self.managed_processes.values())
            
            warning_msg = f"Uruchomionych jest {len(self.managed_processes)} procesów."
            if network_server:
                warning_msg += "\n\n⚠️ UWAGA: Serwer sieciowy jest aktywny!"
            warning_msg += "\n\nCzy chcesz je wszystkie zatrzymać i zamknąć aplikację?"
            
            result = messagebox.askyesno(
                "🔒 Potwierdzenie zamknięcia", warning_msg,
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

    def cleanup_temp_files(self):
        """Usuwa tymczasowe pliki utworzone przez launcher."""
        wrapper_path = os.path.join(BACKEND_DIR, "_network_server_wrapper.py")
        if os.path.exists(wrapper_path):
            try:
                os.remove(wrapper_path)
            except:
                pass

    def _prepare_process_env(self):
        """Przygotowuje środowisko dla procesu."""
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        
        env_config = read_env_config()
        env.update(env_config)
        
        return env

    def _prepare_command(self, key, script_info):
        """Przygotowuje komendę do uruchomienia."""
        if key == "tests":
            return [sys.executable, script_info["path"]] + script_info["args"]
        else:
            command = [sys.executable, "-X", "utf8", "-u", script_info["path"]]
            if key == "genealogy_editor":
                command.append("--launched-by-gui")
            return command

# =============================================================================
# KLASY OKIEN DIALOGOWYCH
# =============================================================================

class LocationManager(tk.Toplevel):
    """Okno dialogowe do zarządzania miejscowościami."""

    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("⚙️ Zarządzaj Miejscowościami")

        # Automatyczne dostosowanie do ekranu
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(int(sw * 0.6), 900), min(int(sh * 0.7), 600)
        x = (sw - w) // 2
        y = (sh - h) // 2

        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(700, 500)
        self.grab_set()

        self.create_widgets()
        self.refresh_table()

    def create_widgets(self):
        """Tworzy interfejs menedżera miejscowości."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Tabelka
        table_frame = ttk.LabelFrame(main_frame, text="📋 Lista Miejscowości", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Kolumny: ID, Nazwa, Pełna Nazwa, Powiat, Region, Aktywna
        columns = ("id", "name", "full_name", "powiat", "region", "active")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Nazwa")
        self.tree.heading("full_name", text="Pełna Nazwa")
        self.tree.heading("powiat", text="Powiat")
        self.tree.heading("region", text="Region")
        self.tree.heading("active", text="Aktywna")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("name", width=120)
        self.tree.column("full_name", width=200)
        self.tree.column("powiat", width=120)
        self.tree.column("region", width=120)
        self.tree.column("active", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Przyciski akcji
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)

        ttk.Button(buttons_frame, text="➕ Dodaj Nową Miejscowość", command=self.add_location,
                  style="Success.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(buttons_frame, text="✏️ Edytuj", command=self.edit_location,
                  style="Primary.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(buttons_frame, text="🗑️ Usuń", command=self.delete_location,
                  style="Danger.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(buttons_frame, text="✅ Ustaw jako Aktywną", command=self.set_active,
                  style="Info.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(buttons_frame, text="🔄 Odśwież", command=self.refresh_table,
                  style="Secondary.TButton").pack(side=tk.LEFT, padx=5)

    def refresh_table(self):
        """Odświeża tabelkę z miejscowościami."""
        # Wyczyść tabelę
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Pobierz dane
        locations = get_all_locations()

        # Wypełnij tabelę
        for loc in locations:
            loc_id, name, full_name, powiat, region, active = loc
            active_str = "✓" if active else ""
            self.tree.insert("", "end", values=(loc_id, name, full_name, powiat, region, active_str))

    def add_location(self):
        """Dodaje nową miejscowość."""
        dialog = AddEditLocationDialog(self, "Dodaj Nową Miejscowość")
        self.wait_window(dialog)

        if hasattr(dialog, 'result') and dialog.result:
            name, full_name, powiat, region = dialog.result
            try:
                add_location(name, full_name, powiat, region)
                messagebox.showinfo("✅ Sukces", f"Dodano miejscowość: {name}", parent=self)
                self.refresh_table()
            except ValueError as e:
                messagebox.showerror("❌ Błąd", str(e), parent=self)

    def edit_location(self):
        """Edytuje wybraną miejscowość."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Wybierz miejscowość do edycji", parent=self)
            return

        values = self.tree.item(selected[0], "values")
        loc_id, name, full_name, powiat, region = values[:5]

        dialog = AddEditLocationDialog(self, "Edytuj Miejscowość", name, full_name, powiat, region)
        self.wait_window(dialog)

        if hasattr(dialog, 'result') and dialog.result:
            new_name, new_full_name, new_powiat, new_region = dialog.result
            try:
                update_location(int(loc_id), new_name, new_full_name, new_powiat, new_region)
                messagebox.showinfo("✅ Sukces", f"Zaktualizowano miejscowość: {new_name}", parent=self)
                self.refresh_table()
            except ValueError as e:
                messagebox.showerror("❌ Błąd", str(e), parent=self)

    def delete_location(self):
        """Usuwa wybraną miejscowość."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Wybierz miejscowość do usunięcia", parent=self)
            return

        values = self.tree.item(selected[0], "values")
        loc_id, name = values[0], values[1]

        if not messagebox.askyesno("⚠️ Potwierdzenie",
                                   f"Czy na pewno chcesz usunąć miejscowość '{name}'?\n\n"
                                   "Zostanie usunięty cały folder z danymi!",
                                   parent=self):
            return

        try:
            delete_location(int(loc_id))
            messagebox.showinfo("✅ Sukces", f"Usunięto miejscowość: {name}", parent=self)
            self.refresh_table()
        except ValueError as e:
            messagebox.showerror("❌ Błąd", str(e), parent=self)

    def set_active(self):
        """Ustawia wybraną miejscowość jako aktywną."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Wybierz miejscowość do aktywacji", parent=self)
            return

        values = self.tree.item(selected[0], "values")
        loc_id, name = values[0], values[1]

        set_active_location(int(loc_id))
        messagebox.showinfo("✅ Sukces", f"Ustawiono jako aktywną: {name}", parent=self)
        self.refresh_table()


class AddEditLocationDialog(tk.Toplevel):
    """Dialog do dodawania/edytowania miejscowości."""

    def __init__(self, parent, title, name="", full_name="", powiat="", region=""):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.grab_set()

        self.result = None

        # Rozmiar
        w, h = 500, 300
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(False, False)

        # Pola formularza
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Nazwa (folder):").grid(row=0, column=0, sticky="w", pady=5)
        self.name_entry = ttk.Entry(main_frame, width=40)
        self.name_entry.insert(0, name)
        self.name_entry.grid(row=0, column=1, pady=5, padx=10)

        ttk.Label(main_frame, text="Pełna nazwa:").grid(row=1, column=0, sticky="w", pady=5)
        self.full_name_entry = ttk.Entry(main_frame, width=40)
        self.full_name_entry.insert(0, full_name)
        self.full_name_entry.grid(row=1, column=1, pady=5, padx=10)

        ttk.Label(main_frame, text="Powiat:").grid(row=2, column=0, sticky="w", pady=5)
        self.powiat_entry = ttk.Entry(main_frame, width=40)
        self.powiat_entry.insert(0, powiat)
        self.powiat_entry.grid(row=2, column=1, pady=5, padx=10)

        ttk.Label(main_frame, text="Region:").grid(row=3, column=0, sticky="w", pady=5)
        self.region_entry = ttk.Entry(main_frame, width=40)
        self.region_entry.insert(0, region)
        self.region_entry.grid(row=3, column=1, pady=5, padx=10)

        # Przyciski
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(buttons_frame, text="✅ Zapisz", command=self.save,
                  style="Success.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="❌ Anuluj", command=self.destroy,
                  style="Danger.TButton").pack(side=tk.LEFT, padx=5)

    def save(self):
        """Zapisuje dane i zamyka okno."""
        name = self.name_entry.get().strip()
        full_name = self.full_name_entry.get().strip()
        powiat = self.powiat_entry.get().strip()
        region = self.region_entry.get().strip()

        if not name:
            messagebox.showerror("❌ Błąd", "Nazwa jest wymagana!", parent=self)
            return

        if not full_name:
            messagebox.showerror("❌ Błąd", "Pełna nazwa jest wymagana!", parent=self)
            return

        self.result = (name, full_name, powiat, region)
        self.destroy()


class MapCalibrator(tk.Toplevel):
    """Okno do kalibracji współrzędnych mapy."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📍 Konfigurator Mapy")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.parent_app = parent

        # Użyj folderu aktywnej miejscowości
        active_location_name = get_active_location_name()
        if active_location_name:
            location_folder = os.path.join(BACKUP_FOLDER, active_location_name)
        else:
            location_folder = BACKUP_FOLDER

        self.config_path = os.path.join(location_folder, "map_config.json")
        self.vars = {
            'sw_lat': tk.StringVar(), 'sw_lng': tk.StringVar(),
            'ne_lat': tk.StringVar(), 'ne_lng': tk.StringVar(),
            'center_lat': tk.StringVar(), 'center_lng': tk.StringVar(),
            'zoom': tk.StringVar()
        }
        
        self.create_widgets()
        self.load_config_from_file()
        self.check_current_map_status()
        self.center_window()

    def create_widgets(self):
        """Tworzy interfejs konfiguracji mapy."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Nagłówek z przyciskiem instrukcji
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_frame, text="Konfiguracja Mapy Historycznej", style="Heading.TLabel").pack(side=tk.LEFT)
        ttk.Button(header_frame, text="📘 Instrukcja", command=self.show_instructions, style="Info.TButton").pack(side=tk.RIGHT)
        
        # Kontener na podgląd i status
        preview_container = ttk.Frame(main_frame)
        preview_container.pack(fill=tk.X, pady=5)
        preview_container.columnconfigure(1, weight=1)
        
        # Podgląd mapy
        self.map_preview_canvas = tk.Canvas(preview_container, width=200, height=120, bg="grey", highlightthickness=1)
        self.map_preview_canvas.grid(row=0, column=0, rowspan=2, padx=(0, 10), sticky="ns")
        self.map_preview_label = ttk.Label(self.map_preview_canvas, text="Podgląd mapy", foreground="white")
        self.map_preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Status mapy
        status_frame = ttk.Frame(preview_container, relief="sunken", borderwidth=1, padding=5)
        status_frame.grid(row=0, column=1, sticky="ew")
        self.map_status_label = ttk.Label(status_frame, text="Sprawdzanie statusu mapy...")
        self.map_status_label.pack()
        
        ttk.Label(preview_container, text="Podgląd jest generowany z pliku w folderze /mapa/.",
                 wraplength=400).grid(row=1, column=1, sticky="w", pady=(5,0))
        
        # Współrzędne graniczne
        frame_cal = ttk.LabelFrame(main_frame, text="1. Współrzędne graniczne (z GIS)", padding="15")
        frame_cal.pack(fill=tk.X, pady=5)
        
        self._create_coord_inputs(frame_cal)
        
        # Domyślny widok
        frame_def = ttk.LabelFrame(main_frame, text="2. Domyślny widok mapy", padding="15")
        frame_def.pack(fill=tk.X, pady=5)
        
        self._create_default_view_inputs(frame_def)
        
        # Wybór pliku mapy
        frame_map_file = ttk.LabelFrame(main_frame, text="3. Plik mapy tła", padding="15")
        frame_map_file.pack(fill=tk.X, pady=5)
        ttk.Button(frame_map_file, text="Wybierz Plik Mapy (.jpg, .png)",
                  command=self.select_map_file, style="Primary.TButton").pack(fill=tk.X, expand=True)
        ttk.Label(frame_map_file, text="Spowoduje to nadpisanie pliku 'mapa.jpg' dla aplikacji.",
                 wraplength=500).pack(pady=(5,0))
        
        # Przyciski akcji
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(button_frame, text="💾 Zapisz Konfigurację",
                  command=self.save_and_update, style="Success.TButton").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(button_frame, text="Anuluj", command=self.destroy).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    def _create_coord_inputs(self, parent):
        """Tworzy pola wprowadzania współrzędnych."""
        ttk.Label(parent, text="Narożnik Południowo-Zachodni (SW):").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(parent, text="Szerokość (Lat):").grid(row=1, column=0, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['sw_lat']).grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(parent, text="Długość (Lng):").grid(row=1, column=2, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['sw_lng']).grid(row=1, column=3, padx=5, pady=2, sticky="ew")
        
        ttk.Label(parent, text="Narożnik Północno-Wschodni (NE):").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(8, 2))
        ttk.Label(parent, text="Szerokość (Lat):").grid(row=3, column=0, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['ne_lat']).grid(row=3, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(parent, text="Długość (Lng):").grid(row=3, column=2, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['ne_lng']).grid(row=3, column=3, padx=5, pady=2, sticky="ew")
        
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)

    def _create_default_view_inputs(self, parent):
        """Tworzy pola dla domyślnego widoku mapy."""
        ttk.Label(parent, text="Centrum mapy:").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(parent, text="Szerokość (Lat):").grid(row=1, column=0, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['center_lat']).grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(parent, text="Długość (Lng):").grid(row=1, column=2, padx=5, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['center_lng']).grid(row=1, column=3, padx=5, pady=2, sticky="ew")
        
        ttk.Label(parent, text="Domyślny zoom:").grid(row=2, column=0, padx=5, pady=(8, 2), sticky=tk.W)
        ttk.Entry(parent, textvariable=self.vars['zoom'], width=10).grid(row=2, column=1, sticky=tk.W, padx=5, pady=(8, 2))
        
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)

    def show_instructions(self):
        """Wyświetla instrukcję kalibracji."""
        CalibrationInstructions(self)

    def load_config_from_file(self):
        """Wczytuje konfigurację z pliku JSON."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            cal = config.get('calibration', {})
            defs = config.get('defaults', {})
            
            self.vars['sw_lat'].set(cal.get('sw', {}).get('lat', ''))
            self.vars['sw_lng'].set(cal.get('sw', {}).get('lng', ''))
            self.vars['ne_lat'].set(cal.get('ne', {}).get('lat', ''))
            self.vars['ne_lng'].set(cal.get('ne', {}).get('lng', ''))
            self.vars['center_lat'].set(defs.get('center', {}).get('lat', ''))
            self.vars['center_lng'].set(defs.get('center', {}).get('lng', ''))
            self.vars['zoom'].set(defs.get('zoom', ''))
            
            self.parent_app.log("📍 Wczytano konfigurację mapy z pliku.\n")
        except Exception as e:
            messagebox.showerror("Błąd Pliku", f"Nie można wczytać pliku: {e}", parent=self)
            self.destroy()

    def save_and_update(self):
        """Zapisuje konfigurację do pliku i bazy danych."""
        try:
            new_config = {
                "calibration": {
                    "sw": {"lat": float(self.vars['sw_lat'].get()), "lng": float(self.vars['sw_lng'].get())},
                    "ne": {"lat": float(self.vars['ne_lat'].get()), "lng": float(self.vars['ne_lng'].get())}
                },
                "defaults": {
                    "center": {"lat": float(self.vars['center_lat'].get()), "lng": float(self.vars['center_lng'].get())},
                    "zoom": int(self.vars['zoom'].get())
                }
            }
        except ValueError:
            messagebox.showerror("Błąd Walidacji", "Wszystkie pola muszą zawierać poprawne liczby.", parent=self)
            return
        
        # Zapis do pliku
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4)
            self.parent_app.log(f"📍 Zapisano konfigurację mapy: {self.config_path}\n")
        except Exception as e:
            messagebox.showerror("Błąd Zapisu", f"Nie można zapisać pliku: {e}", parent=self)
            return
        
        # Aktualizacja bazy danych
        conn = None
        try:
            db_config = get_db_config_from_env()
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            
            cur.execute(
                "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES ('map_calibration', %s) "
                "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
                (json.dumps(new_config['calibration']),)
            )
            cur.execute(
                "INSERT INTO konfiguracja_systemu (klucz, wartosc) VALUES ('map_defaults', %s) "
                "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
                (json.dumps(new_config['defaults']),)
            )
            conn.commit()
            
            self.parent_app.log("📍 Zaktualizowano konfigurację mapy w bazie danych.\n")
            messagebox.showinfo("Sukces", "Konfiguracja mapy została zapisana.", parent=self)
            self.destroy()
        except Exception as e:
            if conn:
                conn.rollback()
            messagebox.showerror("Błąd Bazy", f"Nie można zaktualizować bazy: {e}", parent=self)
        finally:
            if conn:
                conn.close()

    def check_current_map_status(self):
        """Sprawdza status plików mapy."""
        map_path_main = os.path.join(BASE_DIR, "mapa", "mapa.jpg")
        map_path_editor = os.path.join(TOOLS_DIR, "parcel_editor", "static", "mapa.jpg")
        
        main_exists = os.path.exists(map_path_main)
        editor_exists = os.path.exists(map_path_editor)
        
        if main_exists and editor_exists:
            if filecmp.cmp(map_path_main, map_path_editor, shallow=False):
                self.map_status_label.config(text="✅ Status mapy: OK (pliki spójne)", foreground="green")
            else:
                self.map_status_label.config(text="⚠️ Status mapy: Niespójne pliki!", foreground="orange")
        elif main_exists or editor_exists:
            self.map_status_label.config(text="⚠️ Status mapy: Brakuje pliku!", foreground="orange")
        else:
            self.map_status_label.config(text="❌ Status mapy: Brak plików mapy!", foreground="red")
        
        # Aktualizacja podglądu
        map_to_preview = map_path_main if main_exists else (map_path_editor if editor_exists else None)
        
        if map_to_preview:
            try:
                img = Image.open(map_to_preview)
                w, h = img.size
                ratio = min(200/w, 120/h)
                new_w, new_h = int(w * ratio), int(h * ratio)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                self.map_image_preview = ImageTk.PhotoImage(img)
                self.map_preview_canvas.delete("all")
                self.map_preview_canvas.create_image(100, 60, image=self.map_image_preview)
                self.map_preview_label.place_forget()
            except:
                self.map_preview_canvas.delete("all")
                self.map_preview_label.config(text="Błąd\npodglądu")
                self.map_preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        else:
            self.map_preview_canvas.delete("all")
            self.map_preview_label.config(text="Brak mapy")
            self.map_preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def select_map_file(self):
        """Wybiera i kopiuje plik mapy."""
        filepath = filedialog.askopenfilename(
            title="Wybierz plik mapy tła",
            filetypes=[("Obrazy", "*.jpg *.jpeg *.png"), ("Wszystkie pliki", "*.*")]
        )
        
        if not filepath:
            return
        
        dest_paths = [
            os.path.join(BASE_DIR, "mapa", "mapa.jpg"),
            os.path.join(TOOLS_DIR, "parcel_editor", "static", "mapa.jpg")
        ]
        
        try:
            for dest_path in dest_paths:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy(filepath, dest_path)
            
            messagebox.showinfo("Sukces",
                              "Plik mapy został zaktualizowany.\n\n"
                              "WAŻNE: Upewnij się, że współrzędne odpowiadają nowej mapie!",
                              parent=self)
            
            self.parent_app.log(f"🗺️ Zaktualizowano plik mapy: {os.path.basename(filepath)}\n")
            self.check_current_map_status()
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się skopiować pliku: {e}", parent=self)

    def center_window(self):
        """Wyśrodkowuje okno względem rodzica."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f'+{x}+{y}')

class CalibrationInstructions(tk.Toplevel):
    """Okno z instrukcją kalibracji mapy."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📘 Instrukcja Kalibracji Mapy")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        
        frame = ttk.Frame(self, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20, width=80, font=("Segoe UI", 10))
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        instruction_text = """
Krok 1: Praca w Programie GIS (np. darmowy QGIS)
==============================================
Georeferencja to proces "przypinania" starej mapy do prawdziwych współrzędnych.

1. Wczytaj warstwy w GIS.
2. Znajdź punkty wspólne (GCP) - użyj co najmniej 10-15 punktów.
3. Wykonaj transformację (warping).
4. Odczytaj współrzędne graniczne z właściwości warstwy GeoTIFF:
   - Południowo-Zachodni narożnik (lewy dolny)
   - Północno-Wschodni narożnik (prawy górny)
5. Eksportuj obraz do JPG/PNG.

Krok 2: Konfiguracja w Launcherze
==================================
1. Podmień plik mapy przyciskiem "Wybierz Plik Mapy...".
2. Wprowadź współrzędne odczytane w kroku 1.
3. Zapisz konfigurację.

Po restarcie serwera mapa będzie używać nowej kalibracji.
"""
        text_widget.insert(tk.END, instruction_text.strip())
        text_widget.config(state="disabled")
        
        ttk.Button(frame, text="Zamknij", command=self.destroy).pack(pady=(10, 0))
        
        # Wyśrodkowanie
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f'+{x}+{y}')

class EnvEditor(tk.Toplevel):
    """Edytor pliku konfiguracyjnego .env."""
    
    def __init__(self, parent, env_path):
        super().__init__(parent)
        self.title("⚙️ Edytor Konfiguracji Bazy Danych")
        self.parent_app = parent
        self.env_path = env_path
        
        self.geometry("700x500")
        self.minsize(600, 420)
        self.center_window()
        
        self.create_widgets()
        self.load_content()

    def create_widgets(self):
        """Tworzy interfejs edytora."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="📝 Edycja pliku konfiguracyjnego .env",
                 font=("Segoe UI", 12, "bold")).pack(pady=(0, 10))
        
        ttk.Label(main_frame,
                 text="Ten plik zawiera konfigurację połączenia z bazą danych PostgreSQL.\n"
                      "Po wprowadzeniu zmian zapisz plik i zrestartuj serwer backend.",
                 wraplength=650, foreground="#666666").pack(pady=(0, 10))
        
        # Edytor tekstu
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.text_editor = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD,
                                                     font=("Consolas", 10), height=15)
        self.text_editor.pack(fill=tk.BOTH, expand=True)
        
        # Przyciski
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="💾 Zapisz zmiany", command=self.save_env,
                  style="Success.TButton").pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="🔄 Przywróć domyślne", command=self.reset_defaults,
                  style="Warning.TButton").pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="❌ Zamknij", command=self.destroy,
                  style="Secondary.TButton").pack(side=tk.RIGHT, padx=5)

    def load_content(self):
        """Wczytuje zawartość pliku .env."""
        try:
            with open(self.env_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.text_editor.insert('1.0', content)
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Nie można wczytać pliku .env:\n{e}", parent=self)
            self.destroy()

    def save_env(self):
        """Zapisuje zmiany do pliku .env."""
        try:
            content = self.text_editor.get('1.0', 'end-1c')
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
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
            default_content = """# Konfiguracja bazy danych PostgreSQL
DB_HOST=localhost
DB_NAME=mapa_czarna_db
DB_USER=postgres
DB_PASSWORD=1234
DB_PORT=5432

# Konfiguracja serwera Flask
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True
"""
            self.text_editor.delete('1.0', tk.END)
            self.text_editor.insert('1.0', default_content)

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

class AdminSettings(tk.Toplevel):
    """Okno ustawień administratora."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔐 Ustawienia Administratora")
        self.transient(parent)
        self.grab_set()
        self.parent_app = parent
        
        self.geometry("500x300")
        self.minsize(460, 260)
        self.center_window()
        
        self.load_current_settings()
        self.create_widgets()

    def load_current_settings(self):
        """Wczytuje obecne ustawienia z .env."""
        env_config = read_env_config()
        
        self.enabled = tk.BooleanVar(value=(env_config.get('ADMIN_AUTH_ENABLED', '0') == '1'))
        self.username = tk.StringVar(value=env_config.get('ADMIN_USERNAME', 'admin'))
        self.password = tk.StringVar(value='')
        self.env = env_config

    def create_widgets(self):
        """Tworzy interfejs ustawień."""
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)
        
        ttk.Checkbutton(frm, text="Włącz wymaganie logowania do Panelu Admina",
                       variable=self.enabled).pack(anchor=tk.W, pady=(0,8))
        
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
                 wraplength=480).pack(anchor=tk.W, pady=(6,10), fill=tk.X)
        
        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(10,0))
        
        ttk.Button(btns, text="💾 Zapisz", command=self.save, style="Success.TButton").pack(side=tk.RIGHT)
        ttk.Button(btns, text="Anuluj", command=self.destroy, style="Secondary.TButton").pack(side=tk.RIGHT, padx=(0,8))

    def save(self):
        """Zapisuje ustawienia administratora."""
        try:
            from werkzeug.security import generate_password_hash
        except:
            messagebox.showerror("Brak zależności", "Brakuje pakietu Werkzeug.", parent=self)
            return
        
        if not self.username.get().strip():
            messagebox.showwarning("Walidacja", "Login nie może być pusty.", parent=self)
            return
        
        old_auth = self.env.get('ADMIN_AUTH_ENABLED', '0')
        
        self.env['ADMIN_AUTH_ENABLED'] = '1' if self.enabled.get() else '0'
        self.env['ADMIN_USERNAME'] = self.username.get().strip()
        
        if self.password.get():
            try:
                self.env['ADMIN_PASSWORD_HASH'] = generate_password_hash(self.password.get())
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie udało się utworzyć hasha: {e}", parent=self)
                return
        
        self.env.setdefault('FLASK_SECRET_KEY', 'change-me-' + str(os.getpid()))
        
        # Zapisz .env
        env_path = os.path.join(BACKEND_DIR, ".env")
        self._save_env_file(env_path)
        
        self.parent_app.on_env_changed()
        
        # Auto-restart przy zmianie autoryzacji
        new_auth = self.env['ADMIN_AUTH_ENABLED']
        
        if old_auth != new_auth and "backend" in self.parent_app.managed_processes:
            was_network = self.parent_app.managed_processes["backend"].get("network_mode", False)
            
            messagebox.showinfo("🔄 Restart serwera",
                              f"{'Włączono' if new_auth == '1' else 'Wyłączono'} autoryzację admina.\n\n"
                              "Serwer backend zostanie automatycznie zrestartowany.",
                              parent=self)
            self.destroy()
            
            self.parent_app.log(f"\n{'='*60}\n")
            self.parent_app.log(f"🔄 Restartowanie serwera - zmiana ustawień autoryzacji...\n")
            self.parent_app.log(f"   • Autoryzacja: {'WŁĄCZONA ✅' if new_auth == '1' else 'WYŁĄCZONA ❌'}\n")
            if new_auth == '1':
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
        """Zapisuje plik .env z zachowaniem struktury."""
        order = ['DB_HOST','DB_NAME','DB_USER','DB_PASSWORD','DB_PORT',
                'FLASK_HOST','FLASK_PORT','FLASK_DEBUG','FLASK_SECRET_KEY',
                'ADMIN_AUTH_ENABLED','ADMIN_USERNAME','ADMIN_PASSWORD_HASH']
        
        lines = []
        for k in order:
            if k in self.env:
                lines.append(f"{k}={self.env[k]}")
        
        for k, v in self.env.items():
            if k not in order:
                lines.append(f"{k}={v}")
        
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("# Konfiguracja bazy danych PostgreSQL\n")
            f.write("\n".join([l for l in lines if l.split('=')[0] in 
                             {'DB_HOST','DB_NAME','DB_USER','DB_PASSWORD','DB_PORT'}]))
            f.write("\n\n# Konfiguracja serwera Flask\n")
            f.write("\n".join([l for l in lines if l.split('=')[0] in 
                             {'FLASK_HOST','FLASK_PORT','FLASK_DEBUG','FLASK_SECRET_KEY'}]))
            f.write("\n\n# Ustawienia bezpieczeństwa\n")
            f.write("\n".join([l for l in lines if l.split('=')[0] in 
                             {'ADMIN_AUTH_ENABLED','ADMIN_USERNAME','ADMIN_PASSWORD_HASH'}]))

    def center_window(self):
        """Wyśrodkowuje okno."""
        self.update_idletasks()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        x = px + (pw - 500) // 2
        y = py + (ph - 300) // 2
        self.geometry(f"+{x}+{y}")

class FirewallInstructions(tk.Toplevel):
    """Okno z instrukcjami konfiguracji firewall."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📋 Instrukcja konfiguracji Firewall")
        self.geometry("600x500")
        self.transient(parent)
        
        flask_config = get_flask_config()
        port = int(flask_config['port'])
        
        frame = ttk.Frame(self, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True)
        
        content = f"""INSTRUKCJA RĘCZNEJ KONFIGURACJI FIREWALL WINDOWS
================================================

METODA 1 - Przez interfejs graficzny:
-------------------------------------
1. Naciśnij Win + R
2. Wpisz: wf.msc
3. Kliknij "Reguły przychodzące" → "Nowa reguła..."
4. Wybierz "Port" → TCP → "{port}" → "Zezwalaj"
5. Nazwa: "Flask Server Port {port}"

METODA 2 - PowerShell (jako Administrator):
-----------------------------------------
New-NetFirewallRule -DisplayName "Flask Server Port {port}" -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow

METODA 3 - Wiersz poleceń (jako Administrator):
--------------------------------------------
netsh advfirewall firewall add rule name="Flask Server Port {port}" dir=in action=allow protocol=TCP localport={port}

TESTOWANIE:
-----------
1. Uruchom serwer sieciowy
2. Na innym urządzeniu wpisz adres IP:{port}
3. Jeśli strona się ładuje - wszystko działa!
"""
        
        text.insert("1.0", content)
        text.config(state="disabled")
        
        ttk.Button(frame, text="Zamknij", command=self.destroy,
                  style="Primary.TButton").pack(pady=10)

class NetworkInfoDialog(tk.Toplevel):
    """Okno z informacjami o dostępie sieciowym."""
    
    def __init__(self, parent, local_ip):
        super().__init__(parent)
        self.title("Informacje o Dostępie Sieciowym")
        self.transient(parent)
        self.grab_set()
        
        self.parent_app = parent
        parent._net_info_win = self
        
        flask_config = get_flask_config()
        port = flask_config['port']
        
        w, h = 600, 400
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.resizable(False, False)
        
        self.create_widgets(local_ip, port)

    def create_widgets(self, local_ip, port):
        """Tworzy interfejs z informacjami."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="✅ Serwer uruchomiony w trybie sieciowym!",
                 font=("Segoe UI", 14, "bold"),
                 foreground=COLORS['success']).pack(pady=(0, 20))
        
        # Adresy dostępu
        info_frame = ttk.LabelFrame(main_frame, text="📡 Adresy dostępu", padding="15")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        addresses = [
            ("Ten komputer:", f"http://127.0.0.1:{port}"),
            ("Inne urządzenia w sieci:", f"http://{local_ip}:{port}"),
            ("Alternatywny adres:", f"http://{socket.gethostname()}:{port}"),
        ]
        
        for label, address in addresses:
            addr_frame = ttk.Frame(info_frame)
            addr_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(addr_frame, text=label, width=25).pack(side=tk.LEFT)
            
            addr_entry = ttk.Entry(addr_frame, width=40)
            addr_entry.insert(0, address)
            addr_entry.config(state="readonly")
            addr_entry.pack(side=tk.LEFT, padx=10)
            
            def copy_addr(addr=address):
                self.clipboard_clear()
                self.clipboard_append(addr)
                messagebox.showinfo("✅ Skopiowano", f"Adres został skopiowany:\n{addr}", parent=self)
            
            ttk.Button(addr_frame, text="📋 Kopiuj", command=copy_addr, width=10).pack(side=tk.LEFT)
        
        # Komenda PowerShell
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
            messagebox.showinfo("✅ Skopiowano", "Komenda PowerShell została skopiowana.\nUruchom PowerShell jako Administrator i wklej komendę.", parent=self)
        
        ttk.Button(ps_frame, text="📋 Kopiuj", command=copy_ps, style="Primary.TButton").pack(side=tk.LEFT)
        
        # Instrukcja
        instr_row = ttk.Frame(main_frame)
        instr_row.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(instr_row, text="ℹ️").pack(side=tk.LEFT, padx=(0, 8))
        
        ttk.Button(instr_row, text="📘 Pokaż instrukcję (firewall / port 5000)",
                  command=self.open_network_instructions_centered,
                  style="Primary.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        
        ttk.Button(main_frame, text="OK, rozumiem", command=self.destroy,
                  style="Primary.TButton").pack(pady=10)
        
        # Dostosowanie rozmiaru
        self.update_idletasks()
        req_w = self.winfo_reqwidth()
        req_h = self.winfo_reqheight()
        self.geometry(f"{req_w}x{req_h}")
        self.minsize(req_w, req_h)

    def open_network_instructions_centered(self):
        """Otwiera wyskakujące okno z instrukcją dostępu sieciowego."""
        parent = getattr(self, "_net_info_win", self)
        
        win = tk.Toplevel(parent)
        win.title("Instrukcja – dostęp sieciowy / port 5000")
        win.resizable(False, False)
        win.transient(parent)
        win.grab_set()
        
        body = ttk.Frame(win, padding=14)
        body.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(body, text="Jak udostępnić aplikację w sieci lokalnej:",
                 font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 6))
        
        ttk.Label(body, justify=tk.LEFT, text=(
            "1) Upewnij się, że serwer działa (zielony status w oknie sieciowym).\n"
            "2) Komputer-serwer i urządzenie-klient muszą być w tej samej sieci Wi-Fi/LAN.\n"
            "3) Na innym urządzeniu wpisz adres IP z listy (np. http://192.168.x.x:5000).\n"
            "4) Jeśli nie działa – dodaj regułę Zapory Windows: TCP 5000, wszystkie profile.\n"
            "5) Sprawdzenie nasłuchu:\n"
            "   • PowerShell: Get-NetTCPConnection -LocalPort 5000\n"
            "   • CMD:       netstat -ano | findstr :5000\n"
        )).pack(anchor=tk.W)
        
        ttk.Button(body, text="Zamknij", command=win.destroy,
                  style="Secondary.TButton").pack(anchor=tk.E, pady=(10, 0))
        
        # Wyśrodkowanie
        parent.update_idletasks()
        win.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")
        win.focus_set()

class InstructionsWindow(tk.Toplevel):
    """Okno z instrukcjami dostępu sieciowego."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Instrukcja – dostęp sieciowy")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        body = ttk.Frame(self, padding=14)
        body.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(body, text="Jak udostępnić aplikację w sieci lokalnej:",
                 font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 6))
        
        ttk.Label(body, justify=tk.LEFT, text=(
            "1) Upewnij się, że serwer działa (zielony status).\n"
            "2) Komputer i urządzenie muszą być w tej samej sieci.\n"
            "3) Na innym urządzeniu wpisz adres IP z listy.\n"
            "4) Jeśli nie działa – dodaj regułę Zapory Windows.\n"
            "5) Sprawdzenie nasłuchu:\n"
            "   • PowerShell: Get-NetTCPConnection -LocalPort 5000\n"
            "   • CMD: netstat -ano | findstr :5000\n"
        )).pack(anchor=tk.W)
        
        ttk.Button(body, text="Zamknij", command=self.destroy,
                  style="Secondary.TButton").pack(anchor=tk.E, pady=(10, 0))
        
        # Wyśrodkowanie
        parent.update_idletasks()
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        self.focus_set()

class BackupManager(tk.Toplevel):
    """Okno dialogowe do zarządzania kopiami zapasowymi projektu."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("💾 Uniwersalny Menedżer Kopii Zapasowych")
        
        # Automatyczne dostosowanie do ekranu
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        dpi = self.winfo_fpixels("1i")
        scale_factor = dpi / 96
        
        if sw <= 1920:
            w, h = min(int(sw * 0.75), 1100), min(int(sh * 0.80), 700)
        else:
            w, h = min(int(sw * 0.60), 1200), min(int(sh * 0.75), 800)
        
        if scale_factor > 1.25:
            w = int(w / scale_factor * 1.3)
            h = int(h / scale_factor * 1.3)
        
        x = (sw - w) // 2
        y = (sh - h) // 2
        
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(800, 600)
        self.grab_set()
        
        # Konfiguracja stylów
        base_size = 10 if scale_factor <= 1.25 else (11 if scale_factor <= 1.5 else 12)
        self.base_font_size = base_size
        
        self.style = ttk.Style(self)
        row_height = int(base_size * 2.5)
        self.style.configure("Treeview", rowheight=row_height, font=("Segoe UI", base_size))
        self.style.configure("Treeview.Heading", font=("Segoe UI", base_size, "bold"))
        
        self.create_widgets()
        self.populate_backup_list()

    def create_widgets(self):
        """Tworzy interfejs menedżera kopii."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Sekcja tworzenia kopii
        create_frame = ttk.LabelFrame(main_frame, text="➕ Stwórz Nową Kopię Zapasową", padding="10")
        create_frame.pack(fill=tk.X, pady=(0, 10))

        # Wybór miejscowości
        location_select_frame = ttk.Frame(create_frame)
        location_select_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(location_select_frame, text="Miejscowość do skopiowania:").pack(side=tk.LEFT, padx=5)

        self.location_backup_var = tk.StringVar(value="Aktywna miejscowość")
        self.location_backup_combo = ttk.Combobox(location_select_frame, textvariable=self.location_backup_var,
                                                  state="readonly", width=30)
        self.location_backup_combo.pack(side=tk.LEFT, padx=5)

        # Wypełnij listę miejscowości
        locations = get_all_locations()
        location_choices = ["Aktywna miejscowość", "Wszystkie miejscowości"] + [loc[1] for loc in locations]
        self.location_backup_combo['values'] = location_choices

        # Checkboxy
        self.backup_vars = {key: tk.BooleanVar(value=True) for key in DATA_FILES}
        self.backup_vars["scans"] = tk.BooleanVar(value=True)
        self.backup_vars["config"] = tk.BooleanVar(value=True)

        content_frame = ttk.Frame(create_frame)
        content_frame.pack(fill=tk.X)

        checkbox_frame = ttk.Frame(content_frame)
        checkbox_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        col1 = ttk.Frame(checkbox_frame)
        col1.pack(side=tk.LEFT, padx=10)

        checkboxes = [
            ("📋 Właściciele i Demografia", "owners"),
            ("🗺️ Działki (geometria)", "parcels"),
            ("📍 Konfiguracja Mapy", "config")
        ]

        for text, var_key in checkboxes:
            ttk.Checkbutton(col1, text=text, variable=self.backup_vars[var_key]).pack(anchor="w", pady=2)

        col2 = ttk.Frame(checkbox_frame)
        col2.pack(side=tk.LEFT, padx=10)

        ttk.Checkbutton(col2, text="🌳 Genealogia", variable=self.backup_vars["genealogy"]).pack(anchor="w", pady=2)
        ttk.Checkbutton(col2, text="📄 Skany Protokołów", variable=self.backup_vars["scans"]).pack(anchor="w", pady=2)

        ttk.Button(content_frame, text="🎯 Stwórz Kopię ZIP", command=self.create_backup,
                  style="Success.TButton").pack(side=tk.RIGHT, padx=10)
        
        # Sekcja zarządzania kopiami
        restore_frame = ttk.LabelFrame(main_frame, text="📦 Istniejące Kopie Zapasowe", padding="10")
        restore_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Tabela kopii
        self.tree = ttk.Treeview(restore_frame, columns=("filename",), show="headings")
        self.tree.heading("filename", text="📁 Nazwa Pliku (od najnowszej)")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        
        # Pasek akcji
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.selected_label = ttk.Label(action_frame, text="📭 Nic nie zaznaczono",
                                       foreground=COLORS['secondary'],
                                       font=("Segoe UI", self.base_font_size))
        self.selected_label.pack(side=tk.LEFT, padx=5)
        
        buttons_frame = ttk.Frame(action_frame)
        buttons_frame.pack(side=tk.RIGHT)
        
        self.delete_btn = ttk.Button(buttons_frame, text="🗑️ Usuń", style="Danger.TButton",
                                     command=self.delete_backup, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.LEFT, padx=2)
        
        self.restore_btn = ttk.Button(buttons_frame, text="♻️ Przywróć", command=self.restore_backup,
                                      state=tk.DISABLED, style="Warning.TButton")
        self.restore_btn.pack(side=tk.LEFT, padx=2)
        
        self.export_btn = ttk.Button(buttons_frame, text="📤 Eksportuj", command=self.export_backup,
                                     state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=2)
        
        self.import_btn = ttk.Button(buttons_frame, text="📥 Importuj z dysku",
                                     command=self.import_backup, style="Primary.TButton")
        self.import_btn.pack(side=tk.LEFT, padx=2)

    def populate_backup_list(self):
        """Wczytuje listę plików kopii zapasowych."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            files = [f for f in os.listdir(BACKUP_FOLDER)
                    if f.startswith("backup_") and f.endswith(".zip")]
            # Dodaj również stare kopie dla kompatybilności wstecznej
            old_backups = [f for f in os.listdir(BACKUP_FOLDER)
                          if f.startswith("pelny_backup_projektu_") and f.endswith(".zip")]
            files.extend(old_backups)
            files.sort(reverse=True)

            for filename in files:
                self.tree.insert("", "end", iid=filename, values=(filename,))
        except FileNotFoundError:
            pass

        self.on_select()

    def on_select(self, event=None):
        """Aktualizuje stan przycisków w zależności od zaznaczenia."""
        selected = self.tree.selection()
        
        if selected:
            self.selected_backup_file = selected[0]
            display_name = self.selected_backup_file[:37] + "..." if len(self.selected_backup_file) > 40 else self.selected_backup_file
            self.selected_label.config(text=f"📂 {display_name}", foreground=COLORS['primary'])
            
            for btn in [self.restore_btn, self.delete_btn, self.export_btn]:
                btn.config(state=tk.NORMAL)
        else:
            self.selected_backup_file = None
            self.selected_label.config(text="📭 Nic nie zaznaczono", foreground=COLORS['secondary'])
            
            for btn in [self.restore_btn, self.delete_btn, self.export_btn]:
                btn.config(state=tk.DISABLED)

    def export_backup(self):
        """Eksportuje zaznaczoną kopię zapasową."""
        if not self.selected_backup_file:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Najpierw zaznacz plik.", parent=self)
            return
        
        source_path = os.path.join(BACKUP_FOLDER, self.selected_backup_file)
        destination_path = filedialog.asksaveasfilename(
            initialfile=self.selected_backup_file, defaultextension=".zip",
            filetypes=[("Archiwum ZIP", "*.zip")], title="Wybierz, gdzie zapisać"
        )
        
        if destination_path:
            try:
                shutil.copy2(source_path, destination_path)
                messagebox.showinfo("✅ Sukces", "Kopia zapasowa została wyeksportowana.", parent=self)
            except Exception as e:
                messagebox.showerror("❌ Błąd", f"Nie udało się zapisać:\n{e}", parent=self)

    def import_backup(self):
        """Importuje kopię zapasową z zewnętrznej lokalizacji."""
        source_path = filedialog.askopenfilename(
            filetypes=[("Archiwum ZIP", "*.zip")], title="Wybierz plik kopii zapasowej"
        )
        
        if not source_path:
            return
        
        filename = os.path.basename(source_path)
        destination_path = os.path.join(BACKUP_FOLDER, filename)
        
        if os.path.exists(destination_path):
            if not messagebox.askyesno("⚠️ Plik istnieje", f"Plik '{filename}' już istnieje.\nNadpisać?", parent=self):
                return
        
        try:
            shutil.copy2(source_path, destination_path)
            messagebox.showinfo("✅ Sukces", f"Plik '{filename}' został zaimportowany.", parent=self)
            self.populate_backup_list()
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Nie udało się skopiować:\n{e}", parent=self)

    def create_backup(self):
        """Tworzy nową kopię zapasową."""
        components = [key for key, var in self.backup_vars.items() if var.get()]

        if not components:
            messagebox.showwarning("⚠️ Nic nie wybrano", "Zaznacz co najmniej jeden element.", parent=self)
            return

        ProgressDialog(self, self._perform_backup, components)

    def _perform_backup(self, progress_callback, components):
        """Wykonuje tworzenie kopii zapasowej."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        location_choice = self.location_backup_var.get()

        # Określ jakie miejscowości kopiować
        locations_to_backup = []
        if location_choice == "Aktywna miejscowość":
            active_loc = get_active_location()
            if active_loc:
                locations_to_backup = [active_loc[1]]  # nazwa miejscowości
            backup_filename = f"backup_{timestamp}.zip"
        elif location_choice == "Wszystkie miejscowości":
            all_locs = get_all_locations()
            locations_to_backup = [loc[1] for loc in all_locs]
            backup_filename = f"backup_wszystkie_{timestamp}.zip"
        else:
            # Konkretna miejscowość
            locations_to_backup = [location_choice]
            backup_filename = f"backup_{location_choice}_{timestamp}.zip"

        if not locations_to_backup:
            raise Exception("Brak miejscowości do skopiowania")

        backup_path = os.path.join(BACKUP_FOLDER, backup_filename)

        files_to_zip = []

        # Zbieranie plików dla każdej miejscowości
        for location_name in locations_to_backup:
            location_folder = os.path.join(BACKUP_FOLDER, location_name)

            if not os.path.exists(location_folder):
                continue

            # Dodaj plik .env
            env_path = os.path.join(location_folder, ".env")
            if os.path.exists(env_path):
                arcname = os.path.join(location_name, ".env")
                files_to_zip.append((env_path, arcname))

            # Zbieranie plików danych
            data_files_for_location = get_data_files(location_name)

            if self.backup_vars["config"].get():
                map_config_path = os.path.join(location_folder, "map_config.json")
                if os.path.exists(map_config_path):
                    arcname = os.path.join(location_name, "map_config.json")
                    files_to_zip.append((map_config_path, arcname))

            for key in ["owners", "parcels", "genealogy"]:
                if self.backup_vars[key].get():
                    file_path = data_files_for_location[key]["path"]
                    if os.path.exists(file_path):
                        arcname = os.path.join(location_name, os.path.basename(file_path))
                        files_to_zip.append((file_path, arcname))
                    for related_path in data_files_for_location[key].get("related", []):
                        if os.path.exists(related_path):
                            arcname = os.path.join(location_name, os.path.basename(related_path))
                            files_to_zip.append((related_path, arcname))

        # Skany protokołów (wspólne dla wszystkich miejscowości)
        if self.backup_vars["scans"].get() and os.path.exists(PROTOKOLY_FOLDER):
            for root, _, files in os.walk(PROTOKOLY_FOLDER):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, BASE_DIR)
                    files_to_zip.append((file_path, arcname))

        # Tworzenie archiwum
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, (file_path, arcname) in enumerate(files_to_zip):
                progress_callback(i + 1, len(files_to_zip), f"Pakowanie: {os.path.basename(arcname)}")
                zf.write(file_path, arcname)

        return backup_filename

    def delete_backup(self):
        """Usuwa zaznaczony plik kopii zapasowej."""
        if not hasattr(self, "selected_backup_file") or not self.selected_backup_file:
            return
        
        if messagebox.askyesno("🗑️ Potwierdzenie", f"Czy na pewno usunąć:\n\n{self.selected_backup_file}?",
                               parent=self, icon="warning"):
            backup_path = os.path.join(BACKUP_FOLDER, self.selected_backup_file)
            try:
                os.remove(backup_path)
                messagebox.showinfo("✅ Sukces", f"Usunięto: {self.selected_backup_file}", parent=self)
                self.populate_backup_list()
            except Exception as e:
                messagebox.showerror("❌ Błąd", f"Nie udało się usunąć:\n{e}", parent=self)

    def restore_backup(self):
        """Przywraca dane z wybranej kopii zapasowej."""
        selected = self.tree.selection()
        if not selected:
            return

        filename = selected[0]

        msg = (f"⚠️ UWAGA! Ta operacja jest NIEODWRACALNA.\n\n"
               f"Czy na pewno przywrócić dane z:\n'{filename}'?\n\n"
               "Spowoduje to:\n"
               "• NADPISANIE wszystkich istniejących danych\n"
               "• ZASTĄPIENIE folderu ze skanami\n"
               "• UTRATĘ wszystkich niezapisanych zmian")

        if not messagebox.askyesno("⚠️ POTWIERDZENIE KRYTYCZNEJ OPERACJI", msg, icon="warning", parent=self):
            return

        backup_path = os.path.join(BACKUP_FOLDER, filename)

        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                archive_contents = zf.namelist()

                # Sprawdź czy to nowy format (z folderami miejscowości) czy stary
                has_location_folders = any('/' in f and not f.startswith('assets/') for f in archive_contents)

                # Przywracanie skanów
                scan_files = [f for f in archive_contents if f.startswith("assets/protokoly/")]
                if scan_files:
                    if os.path.exists(PROTOKOLY_FOLDER):
                        shutil.rmtree(PROTOKOLY_FOLDER)
                    for file_info in zf.infolist():
                        if file_info.filename.startswith("assets/protokoly/"):
                            zf.extract(file_info, path=BASE_DIR)

                if has_location_folders:
                    # Nowy format - wyodrębnij bezpośrednio do backup/
                    # Struktura w ZIP: {miejscowość}/*.json
                    for file_info in zf.infolist():
                        if not file_info.filename.startswith('assets/'):
                            # Wyodrębnij pliki miejscowości zachowując strukturę folderów
                            zf.extract(file_info, path=BACKUP_FOLDER)
                else:
                    # Stary format - pliki bezpośrednio w root ZIP
                    # Wyodrębnij do aktywnej miejscowości
                    active_location_name = get_active_location_name()
                    if active_location_name:
                        target_folder = os.path.join(BACKUP_FOLDER, active_location_name)
                    else:
                        target_folder = BACKUP_FOLDER

                    # Przywracanie plików JSON
                    if "map_config.json" in archive_contents:
                        zf.extract("map_config.json", path=target_folder)

                    for key in ["owners", "parcels", "genealogy"]:
                        json_filename = os.path.basename(DATA_FILES[key]["path"])
                        if json_filename in archive_contents:
                            zf.extract(json_filename, path=target_folder)

                        for related_path in DATA_FILES[key].get("related", []):
                            related_filename = os.path.basename(related_path)
                            if related_filename in archive_contents:
                                zf.extract(related_filename, path=target_folder)

            messagebox.showinfo("✅ Sukces",
                              "Kopia zapasowa została przywrócona.\n\n"
                              "Uruchom ponownie edytory, aby zobaczyć zmiany.",
                              parent=self)
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Wystąpił błąd:\n{e}", parent=self)

class ProgressDialog(tk.Toplevel):
    """Okno dialogowe postępu operacji."""
    
    def __init__(self, parent, task_func, task_args):
        super().__init__(parent)
        self.title("💾 Tworzenie Kopii Zapasowej")
        self.transient(parent)
        self.grab_set()
        
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 180) // 2
        self.geometry(f"400x180+{x}+{y}")
        self.resizable(False, False)
        
        ttk.Label(self, text="📦 Przygotowywanie plików...",
                 font=("Segoe UI", 11), padding=10).pack(pady=(15, 5))
        
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", length=360, mode="determinate")
        self.progress_bar.pack(pady=5, padx=20)
        
        self.status_label = ttk.Label(self, text="", padding=5, wraplength=350)
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

class SiteSettingsManager(tk.Toplevel):
    """Okno dialogowe do zarządzania ustawieniami witryny."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("🖼️ Ustawienia Witryny")
        self.grab_set()
        self.resizable(False, False)
        
        self.parent_app = parent
        self.db_config = get_db_config_from_env()
        self.current_favicon_path = None
        self.image_preview = None
        
        self.create_widgets()
        self.load_current_settings()
        self.center_window()

    def create_widgets(self):
        """Tworzy interfejs ustawień."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        frame_favicon = ttk.LabelFrame(main_frame, text="Ikona Witryny (Favicon)", padding="15")
        frame_favicon.pack(fill=tk.X)
        
        top_row = ttk.Frame(frame_favicon)
        top_row.pack(fill=tk.X)
        
        # Podgląd ikony
        self.preview_canvas = tk.Canvas(top_row, width=64, height=64, bg=self.cget("background"), highlightthickness=0)
        self.preview_canvas.pack(side=tk.LEFT, padx=(0, 15))
        self.preview_label = ttk.Label(self.preview_canvas, text="Brak\nikony", foreground="grey")
        self.preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Informacje i przycisk
        info_frame = ttk.Frame(top_row)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.path_label = ttk.Label(info_frame, text="Obecna ikona: Brak", wraplength=350)
        self.path_label.pack(anchor="w")
        
        ttk.Button(info_frame, text="Wybierz Ikonę (.png, .ico, .jpg)",
                  command=self.select_favicon, style="Primary.TButton").pack(pady=(10,0), anchor="w")
        
        ttk.Label(main_frame, text="Zmiany będą widoczne po restarcie serwera.",
                 foreground="grey", wraplength=450).pack(pady=(15,0))
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(button_frame, text="Zamknij", command=self.destroy).pack(side=tk.RIGHT)

    def load_current_settings(self):
        """Wczytuje aktualną ścieżkę do faviconu z bazy."""
        conn = None
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT wartosc FROM konfiguracja_systemu WHERE klucz = 'site_favicon';")
            result = cur.fetchone()
            
            if result and isinstance(result['wartosc'], dict) and result['wartosc'].get('path'):
                self.current_favicon_path = result['wartosc']['path']
                self.update_preview()
            else:
                self.path_label.config(text="Obecna ikona: Brak (używana domyślna)")
        except psycopg2.Error as e:
            if "does not exist" not in str(e):
                messagebox.showerror("Błąd Bazy", f"Nie można wczytać konfiguracji: {e}", parent=self)
        finally:
            if conn:
                conn.close()

    def update_preview(self):
        """Aktualizuje podgląd ikony."""
        if not self.current_favicon_path:
            self.path_label.config(text="Obecna ikona: Brak (używana domyślna)")
            return
        
        full_path = os.path.join(ASSETS_FOLDER, self.current_favicon_path)
        
        if os.path.exists(full_path):
            try:
                self.path_label.config(text=f"Obecna ikona: {self.current_favicon_path}")
                img = Image.open(full_path)
                img.thumbnail((64, 64), Image.Resampling.LANCZOS)
                self.image_preview = ImageTk.PhotoImage(img)
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(32, 32, image=self.image_preview)
                self.preview_label.place_forget()
            except Exception as e:
                self.path_label.config(text=f"Błąd podglądu: {e}")
                self.preview_canvas.delete("all")
                self.preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        else:
            self.path_label.config(text=f"❌ Błąd: Plik nie istnieje")
            self.preview_canvas.delete("all")
            self.preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def select_favicon(self):
        """Otwiera dialog wyboru pliku i przetwarza go."""
        filepath = filedialog.askopenfilename(
            title="Wybierz plik ikony",
            filetypes=[("Obrazy", "*.png *.ico *.jpg *.jpeg"), ("Wszystkie pliki", "*.*")]
        )
        
        if not filepath:
            return
        
        os.makedirs(SITE_ASSETS_FOLDER, exist_ok=True)
        
        file_extension = os.path.splitext(filepath)[1]
        dest_filename = f"favicon{file_extension}"
        dest_path = os.path.join(SITE_ASSETS_FOLDER, dest_filename)
        
        try:
            shutil.copy(filepath, dest_path)
            relative_path = os.path.join("site", dest_filename).replace("\\", "/")
            self.save_path_to_db(relative_path)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się przetworzyć pliku: {e}", parent=self)

    def save_path_to_db(self, path):
        """Zapisuje ścieżkę do faviconu w bazie."""
        conn = None
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            config_value = json.dumps({"path": path})
            
            cur.execute(
                "INSERT INTO konfiguracja_systemu (klucz, wartosc, opis) VALUES (%s, %s, %s) "
                "ON CONFLICT (klucz) DO UPDATE SET wartosc = EXCLUDED.wartosc;",
                ('site_favicon', config_value, 'Ścieżka do ikony witryny.')
            )
            conn.commit()
            
            self.parent_app.log(f"🖼️ Ustawiono nowy favicon: {path}\n")
            messagebox.showinfo("Sukces", "Nowa ikona została ustawiona.\nZrestartuj serwer, aby zobaczyć zmiany.", parent=self)
            
            self.current_favicon_path = path
            self.update_preview()
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            messagebox.showerror("Błąd Bazy", f"Nie można zapisać konfiguracji: {e}", parent=self)
        finally:
            if conn:
                conn.close()

    def center_window(self):
        """Wyśrodkowuje okno."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

class SecurityManager(tk.Toplevel):
    """Okno dialogowe do zarządzania bezpieczeństwem systemu."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("🛡️ Menedżer Bezpieczeństwa")
        
        self.geometry("900x600")
        self.minsize(700, 500)
        self.grab_set()
        
        self.parent_app = parent
        self.base_url = f"http://127.0.0.1:{self.parent_app.load_flask_config()['port']}/api/admin/security"
        
        self.create_widgets()
        self.load_data()
        self.center_window()

    def create_widgets(self):
        """Tworzy interfejs menedżera bezpieczeństwa."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Zakładka: Logi Logowania
        logs_frame = ttk.Frame(notebook, padding="10")
        notebook.add(logs_frame, text="📜 Logi Logowania")
        self.create_logs_tab(logs_frame)
        
        # Zakładka: Zablokowane IP
        blocked_frame = ttk.Frame(notebook, padding="10")
        notebook.add(blocked_frame, text="🚫 Zablokowane Adresy IP")
        self.create_blocked_ips_tab(blocked_frame)
        
        ttk.Button(main_frame, text="Zamknij", command=self.destroy, 
                  style="Secondary.TButton").pack(side=tk.RIGHT)

    def create_logs_tab(self, parent):
        """Tworzy zakładkę z logami logowania."""
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(action_frame, text="Ostatnie 100 prób logowania do panelu admina",
                 style="Heading.TLabel").pack(side=tk.LEFT, anchor=tk.W)
        
        ttk.Button(action_frame, text="🗑️ Wyczyść Wszystkie Logi",
                  command=self.clear_login_logs, style="Warning.TButton").pack(side=tk.RIGHT)
        
        # Tabela logów
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
        """Tworzy zakładkę z zablokowanymi adresami IP."""
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(action_frame, text="🚨 Odblokuj Localhost (127.0.0.1)",
                  command=self.unblock_localhost, style="Warning.TButton").pack(side=tk.LEFT)
        
        right_buttons = ttk.Frame(action_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="🔓 Odblokuj Zaznaczone",
                  command=self.unblock_selected_ip, style="Success.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(right_buttons, text="➕ Zablokuj IP",
                  command=self.manually_block_ip, style="Danger.TButton").pack(side=tk.LEFT)
        
        # Tabela zablokowanych IP
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
        """Ładuje dane logów i zablokowanych IP."""
        self.load_logs()
        self.load_blocked_ips()

    def api_request(self, endpoint, method="GET", data=None):
        """Wykonuje żądanie do API bezpieczeństwa."""
        import requests
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
        """Ładuje logi logowania z serwera."""
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)
        
        logs = self.api_request("/logs")
        if logs:
            for log in logs:
                status_text = "✅ Powodzenie" if log['successful'] else "❌ Błąd"
                tag = "success" if log['successful'] else "failure"
                self.logs_tree.insert("", "end", 
                                     values=(log['ip_address'], log['username_attempt'], 
                                           log['timestamp'], status_text),
                                     tags=(tag,))

    def clear_login_logs(self):
        """Czyści wszystkie logi logowania."""
        if messagebox.askyesno(
            "🗑️ Potwierdzenie",
            "Czy na pewno chcesz trwale usunąć WSZYSTKIE logi prób logowania?\n\n"
            "Tej operacji nie można cofnąć.",
            parent=self,
            icon="warning"
        ):
            response = self.api_request("/clear-logs", method="POST")
            if response and response.get("status") == "success":
                messagebox.showinfo("✅ Sukces", "Wszystkie logi logowania zostały usunięte.", parent=self)
                self.parent_app.log("🛡️ Wyczyszczono wszystkie logi logowania.\n")
                self.load_logs()
            else:
                messagebox.showerror("❌ Błąd", "Nie udało się wyczyścić logów.", parent=self)

    def load_blocked_ips(self):
        """Ładuje listę zablokowanych adresów IP."""
        for item in self.blocked_tree.get_children():
            self.blocked_tree.delete(item)
        
        ips = self.api_request("/blocked-ips")
        if ips:
            for ip in ips:
                self.blocked_tree.insert("", "end",
                                        values=(ip['ip_address'], ip['reason'], ip['timestamp']))

    def unblock_selected_ip(self):
        """Odblokowuje zaznaczone adresy IP."""
        selected_items = self.blocked_tree.selection()
        
        if not selected_items:
            messagebox.showwarning("Brak zaznaczenia", "Zaznacz adres IP do odblokowania.", parent=self)
            return
        
        for item_id in selected_items:
            ip_to_unblock = self.blocked_tree.item(item_id)['values'][0]
            
            if messagebox.askyesno("Potwierdzenie", 
                                  f"Czy na pewno chcesz odblokować adres IP: {ip_to_unblock}?", 
                                  parent=self):
                response = self.api_request("/unblock-ip", method="POST", 
                                          data={"ip_address": ip_to_unblock})
                
                if response and response.get("status") == "success":
                    self.parent_app.log(f"🛡️ Odblokowano adres IP: {ip_to_unblock}\n")
                else:
                    messagebox.showerror("Błąd", f"Nie udało się odblokować {ip_to_unblock}.", parent=self)
        
        self.load_blocked_ips()

    def unblock_localhost(self):
        """Odblokowuje adres localhost (127.0.0.1)."""
        ip_to_unblock = "127.0.0.1"
        
        if messagebox.askyesno(
            "Potwierdzenie",
            f"Czy na pewno chcesz odblokować adres {ip_to_unblock}?\n\n"
            "Użyj tej opcji, jeśli przypadkowo zablokowałeś dostęp z lokalnego komputera.",
            parent=self
        ):
            response = self.api_request("/unblock-ip", method="POST", 
                                      data={"ip_address": ip_to_unblock})
            
            if response and response.get("status") == "success":
                messagebox.showinfo("Sukces", 
                                  f"Wysłano żądanie odblokowania dla adresu {ip_to_unblock}.", 
                                  parent=self)
                self.parent_app.log(f"🛡️ Wysłano awaryjne odblokowanie dla: {ip_to_unblock}\n")
                self.load_blocked_ips()
            else:
                messagebox.showerror("Błąd", 
                                   f"Nie udało się odblokować {ip_to_unblock}. Sprawdź czy serwer działa.", 
                                   parent=self)

    def manually_block_ip(self):
        """Ręcznie blokuje podany adres IP."""
        from tkinter import simpledialog
        
        ip = simpledialog.askstring("Blokada IP", "Wprowadź adres IP do zablokowania:", parent=self)
        if not ip:
            return
        
        reason = simpledialog.askstring("Powód blokady", "Podaj powód blokady (opcjonalnie):", parent=self)
        
        response = self.api_request("/block-ip", method="POST",
                                  data={"ip_address": ip, "reason": reason or "Ręczna blokada."})
        
        if response and response.get("status") == "success":
            self.parent_app.log(f"🛡️ Ręcznie zablokowano adres IP: {ip}\n")
            self.load_blocked_ips()
        else:
            messagebox.showerror("Błąd", f"Nie udało się zablokować {ip}.", parent=self)

    def center_window(self):
        """Wyśrodkowuje okno."""
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

# =============================================================================
# PUNKT WEJŚCIA APLIKACJI
# =============================================================================
if __name__ == "__main__":
    """Główny punkt wejścia aplikacji."""
    app = AppLauncher()
    app.mainloop()