"""
==========================================================================
Aplikacja: Edytor Danych Właścicieli
Opis: System zarządzania protokołami właścicielskimi z interfejsem GUI.
      Umożliwia edycję danych, zarządzanie skanami i tworzenie kopii.
==========================================================================
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
import json
import os
import re
import shutil
import zipfile
import threading
import tkinter.font as tkfont
import subprocess
import sys
import ctypes
import platform
import sqlite3
import psycopg2

# ==========================================================================
# KONFIGURACJA DPI
# ==========================================================================

if platform.system() == "Windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE_V2
    except AttributeError:
        ctypes.windll.user32.SetProcessDPIAware()

# ==========================================================================
# KONFIGURACJA ŚCIEŻEK
# ==========================================================================

script_dir = os.path.dirname(os.path.abspath(__file__))

# Funkcja do określenia aktywnej miejscowości
def get_active_location_backup_folder():
    """Zwraca folder backup aktywnej miejscowości."""
    base_dir = os.path.dirname(script_dir)

    # Najpierw spróbuj PostgreSQL (baza launcher)
    try:
        launcher_db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "dbname": "mapa_launcher_db",
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "1234"),
            "port": os.getenv("DB_PORT", "5432"),
            "client_encoding": "UTF8"
        }

        conn = psycopg2.connect(**launcher_db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM locations WHERE active = TRUE LIMIT 1")
        result = cursor.fetchone()
        conn.close()

        if result:
            location_name = result[0]
            backup_folder = os.path.join(base_dir, "backup", location_name)
            print(f"✅ Edytor właścicieli - aktywna miejscowość: {location_name}")
            return backup_folder
    except Exception as e:
        print(f"⚠️ PostgreSQL niedostępny, próbuję SQLite: {e}")

    # Fallback do SQLite jeśli PostgreSQL nie działa
    launcher_dir = os.path.join(base_dir, "launcher")
    locations_db_path = os.path.join(launcher_dir, "locations.db")

    if os.path.exists(locations_db_path):
        try:
            conn = sqlite3.connect(locations_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM locations WHERE active = 1")
            result = cursor.fetchone()
            conn.close()

            if result:
                location_name = result[0]
                backup_folder = os.path.join(base_dir, "backup", location_name)
                print(f"✅ Edytor właścicieli (SQLite) - aktywna miejscowość: {location_name}")
                return backup_folder
        except Exception as e:
            print(f"⚠️ Błąd podczas odczytu SQLite: {e}")

    # Fallback do domyślnej lokalizacji
    print(f"⚠️ Używam domyślnej lokalizacji backup")
    return os.path.join(base_dir, "backup")

def ensure_location_data_files(location_folder):
    """Tworzy wymagane pliki JSON dla miejscowości jeśli nie istnieją."""
    data_files = {
        'demografia.json': [],
        'genealogia.json': {"persons": []},
        'map_config.json': {
            "calibration": {"sw": {"lat": 0, "lng": 0}, "ne": {"lat": 0, "lng": 0}},
            "defaults": {"center": {"lat": 0, "lng": 0}, "zoom": 15}
        },
        'owner_data_to_import.json': {},
        'parcels_data.json': {}}

    created_files = []
    for filename, structure in data_files.items():
        file_path = os.path.join(location_folder, filename)
        if not os.path.exists(file_path):
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(structure, f, ensure_ascii=False, indent=4)
                created_files.append(filename)
            except Exception as e:
                print(f"⚠️ Błąd tworzenia {filename}: {e}")

    if created_files:
        print(f"✅ Utworzono brakujące pliki: {', '.join(created_files)}")

BACKUP_FOLDER = get_active_location_backup_folder()
ensure_location_data_files(BACKUP_FOLDER)  # Upewnij się że pliki istnieją

JSON_FILE_PATH = os.path.join(BACKUP_FOLDER, "owner_data_to_import.json")
DEMOGRAFIA_JSON_PATH = os.path.join(BACKUP_FOLDER, "demografia.json")
JS_FILE_PATH = os.path.join(script_dir, "..", "wlasciciele", "owner.js")
BACKEND_DIR = os.path.join(script_dir, "..", "backend")
MIGRATE_SCRIPT = os.path.join(BACKEND_DIR, "migrate_data.py")

# ==========================================================================
# STAŁE INTERFEJSU
# ==========================================================================

BUTTON_COLORS = {
    'primary': '#0d6efd',
    'success': '#198754',
    'danger': '#dc3545',
    'warning': '#ffc107',
    'info': '#0dcaf0',
    'secondary': '#6c757d',
}

# ==========================================================================
# KLASA GŁÓWNA APLIKACJI
# ==========================================================================

class OwnerEditorApp(tk.Tk):
    """
    Główna aplikacja edytora danych właścicieli.
    Zarządza interfejsem użytkownika i operacjami na danych.
    """
    
    def __init__(self):
        """Inicjalizacja aplikacji i komponentów interfejsu."""
        super().__init__()

        # Ustaw ikonę okna (pióro z launchera)
        self.set_window_icon()

        # Konfiguracja skalowania DPI
        dpi = self.winfo_fpixels("1i")
        scale = dpi / 96
        self.tk.call("tk", "scaling", scale)

        # Konfiguracja czcionek
        base_size = int(11 * scale)
        def_font = tkfont.nametofont("TkDefaultFont")
        def_font.configure(family="Segoe UI", size=base_size)
        
        for name in ("TkTextFont", "TkFixedFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
            try:
                tkfont.nametofont(name).configure(size=base_size)
            except tk.TclError:
                pass

        # Konfiguracja stylów TTK
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        row_h = int(base_size * 3.0)
        self.style.configure("Treeview", rowheight=row_h, padding=(0, 2))
        self.style.configure("Treeview.Heading", font=("Segoe UI", base_size + 1, "bold"))
        
        # Definicje stylów przycisków
        self.style.configure("Primary.TButton", foreground="white", background=BUTTON_COLORS['primary'])
        self.style.configure("Success.TButton", foreground="white", background=BUTTON_COLORS['success'])
        self.style.configure("Danger.TButton", foreground="white", background=BUTTON_COLORS['danger'])
        self.style.configure("Warning.TButton", foreground="black", background=BUTTON_COLORS['warning'])
        self.style.configure("Info.TButton", foreground="white", background=BUTTON_COLORS['info'])
        
        # Efekty hover
        self.style.map("Primary.TButton", background=[('active', '#0b5ed7'), ('pressed', '#0a58ca')])
        self.style.map("Success.TButton", background=[('active', '#157347'), ('pressed', '#146c43')])
        self.style.map("Danger.TButton", background=[('active', '#bb2d3b'), ('pressed', '#b02a37')])

        # Geometria okna
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * 0.90), int(sh * 0.90)
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
        self.minsize(800, 600)

        if platform.system() == "Windows":
            self.state("zoomed")

        def _maximize_and_focus():
            """Maksymalizuje okno i ustawia fokus."""
            self.state("zoomed")
            self.focus_force()
            self.search_entry.focus_force()

        self.after(0, _maximize_and_focus)
        self.title("📋 Edytor Danych Właścicieli - System Zarządzania Protokołami")

        # Inicjalizacja interfejsu
        self.create_widgets()
        self.bind_all("<Control-f>", lambda e: self.after_idle(self.search_entry.focus_force))
        self.bind("<Configure>", self._auto_resize_columns)
        
        # Wczytanie danych
        self.ensure_backup_folder_exists()
        self.load_from_json()
        self.after(100, self.check_for_unlinked_folders)

        # Konfiguracja wyszukiwania
        self.search_var.trace_add("write", self._filter_owners)
        self.update_idletasks()
        self.search_entry.focus_set()

    def set_window_icon(self):
        """Ustawia ikonę okna aplikacji (pióro z launchera lub custom ikona)."""
        try:
            # Ścieżka do ikony w katalogu launcher/assets
            launcher_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'launcher')
            icon_dir = os.path.join(launcher_dir, 'assets')

            # Dla Windows, ustaw AppUserModelID aby ikona była widoczna w pasku zadań
            if platform.system() == "Windows":
                try:
                    myappid = 'projekt.czarna.owner_editor.1.0'
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                except Exception as e:
                    print(f"⚠️ Nie udało się ustawić AppUserModelID: {e}")

            # Sprawdź czy jest zapisana custom ikona
            custom_png = os.path.join(icon_dir, 'custom_icon.png')
            custom_ico = os.path.join(icon_dir, 'custom_icon.ico')

            # Preferuj custom ikonę jeśli istnieje
            png_path = custom_png if os.path.exists(custom_png) else os.path.join(icon_dir, 'feather_icon.png')
            ico_path = custom_ico if os.path.exists(custom_ico) else os.path.join(icon_dir, 'feather_icon.ico')

            # Spróbuj użyć PNG z iconphoto() (wieloplatformowe)
            if os.path.exists(png_path):
                icon_image = tk.PhotoImage(file=png_path)
                self.iconphoto(True, icon_image)
                # Zachowaj referencję aby uniknąć garbage collection
                self._icon_image = icon_image

            # Dla Windows, spróbuj też ICO
            if platform.system() == "Windows":
                if os.path.exists(ico_path):
                    self.iconbitmap(ico_path)
        except Exception as e:
            print(f"⚠️ Nie udało się ustawić ikony okna: {e}")

    # ==========================================================================
    # METODY SPRAWDZANIA INTEGRALNOŚCI
    # ==========================================================================

    def check_for_unlinked_folders(self):
        """Sprawdza i usuwa osierocone foldery ze skanami."""
        print("Sprawdzanie integralności folderów ze skanami...")

        backup_folder = get_active_location_backup_folder()
        protokoly_path = os.path.join(backup_folder, "protokoly")
        if not os.path.exists(protokoly_path):
            return

        try:
            all_folders = {
                f for f in os.listdir(protokoly_path)
                if os.path.isdir(os.path.join(protokoly_path, f))
            }
            all_keys = set(self.data.keys())
            unlinked_folders = all_folders - all_keys

            if unlinked_folders:
                message = (
                    f"Znaleziono {len(unlinked_folders)} folder(ów) w folderze protokołów, "
                    "które nie są powiązane z żadnym właścicielem w pliku JSON:\n\n"
                    f"- {', '.join(unlinked_folders)}\n\n"
                    "Czy chcesz je usunąć?"
                )

                if messagebox.askyesno("Wykryto niepowiązane foldery", message):
                    deleted_count = 0
                    errors = []
                    
                    for folder_name in unlinked_folders:
                        try:
                            shutil.rmtree(os.path.join(protokoly_path, folder_name))
                            print(f"Usunięto osierocony folder: {folder_name}")
                            deleted_count += 1
                        except Exception as e:
                            errors.append(f"- {folder_name}: {e}")

                    summary = f"Usunięto {deleted_count} z {len(unlinked_folders)} folderów."
                    if errors:
                        summary += "\n\nWystąpiły błędy podczas usuwania:\n" + "\n".join(errors)
                        messagebox.showerror("Błędy podczas czyszczenia", summary)
                    else:
                        messagebox.showinfo("Czyszczenie zakończone", summary)
            else:
                print("Wszystkie foldery są poprawnie powiązane.")
                
        except Exception as e:
            messagebox.showwarning("Błąd", f"Wystąpił błąd podczas sprawdzania folderów: {e}")

    # ==========================================================================
    # TWORZENIE INTERFEJSU
    # ==========================================================================

    def create_widgets(self):
        """Tworzy główny interfejs użytkownika."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Pasek narzędzi
        toolbar = ttk.Frame(main_frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Grupa przycisków danych
        data_frame = ttk.LabelFrame(toolbar, text="📁 Dane", padding="5")
        data_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        load_btn = ttk.Button(data_frame, text="📂 Wczytaj dane", command=self.load_from_json, style="Primary.TButton")
        load_btn.pack(side=tk.LEFT, padx=2)

        backup_btn = ttk.Button(data_frame, text="💾 Kopie zapasowe", command=self.open_backup_manager)
        backup_btn.pack(side=tk.LEFT, padx=2)
        
        save_btn = ttk.Button(data_frame, text="✅ ZAPISZ ZMIANY", command=self.save_to_json, style="Success.TButton")
        save_btn.pack(side=tk.LEFT, padx=2)
        
        # Grupa migracji
        migration_frame = ttk.LabelFrame(toolbar, text="🔄 Migracja", padding="5")
        migration_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        migrate_btn = ttk.Button(migration_frame, text="⚡ MIGRUJ DANE", command=self.run_migration, style="Info.TButton")
        migrate_btn.pack(side=tk.LEFT, padx=2)
        
        save_migrate_btn = ttk.Button(migration_frame, text="💫 ZAPISZ + MIGRUJ", command=self.save_and_migrate, style="Success.TButton")
        save_migrate_btn.pack(side=tk.LEFT, padx=2)
        
        # Grupa narzędzi
        tools_frame = ttk.LabelFrame(toolbar, text="🛠️ Narzędzia", padding="5")
        tools_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        demo_btn = ttk.Button(tools_frame, text="📊 Demografia", command=self.open_demografia_editor)
        demo_btn.pack(side=tk.LEFT, padx=2)
        
        # Sekcja wyszukiwania
        search_frame = ttk.LabelFrame(toolbar, text="🔍 Wyszukiwanie", padding="5")
        search_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=2)
        self.search_entry.bind("<Return>", lambda e: self._filter_owners())

        # Grupa zarządzania
        manage_frame = ttk.LabelFrame(toolbar, text="👥 Zarządzaj", padding="5")
        manage_frame.pack(side=tk.RIGHT, padx=(10, 10))
        
        add_btn = ttk.Button(manage_frame, text="➕ Dodaj właściciela", command=self.add_new_owner, style="Success.TButton")
        add_btn.pack(side=tk.LEFT, padx=2)
        
        delete_btn = ttk.Button(manage_frame, text="🗑️ Usuń zaznaczonych", command=self.delete_selected_owner, style="Danger.TButton")
        delete_btn.pack(side=tk.LEFT, padx=2)

        # Tabela właścicieli
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        self.tree = ttk.Treeview(tree_frame, columns=("lp", "name", "plots_count"), show="headings")
        self.tree.heading("lp", text="Lp.")
        self.tree.heading("name", text="Imię i Nazwisko")
        self.tree.heading("plots_count", text="Liczba działek")
        
        self.tree.column("lp", width=60, anchor="center", stretch=tk.NO)
        self.tree.column("name", width=300, stretch=tk.YES)
        self.tree.column("plots_count", width=150, anchor="center", stretch=tk.NO)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Delete>", self.on_delete_key)

    # ==========================================================================
    # METODY POMOCNICZE
    # ==========================================================================

    def ensure_backup_folder_exists(self):
        """Tworzy folder backup jeśli nie istnieje."""
        if not os.path.exists(BACKUP_FOLDER):
            os.makedirs(BACKUP_FOLDER)

    def open_demografia_editor(self):
        """Otwiera edytor danych demograficznych."""
        demografia_editor = DemografiaEditorWindow(self)
        self.wait_window(demografia_editor)
        self.search_entry.focus_set()

    def open_backup_manager(self):
        """Otwiera menedżera kopii zapasowych."""
        backup_manager = BackupManagerWindow(self)
        self.wait_window(backup_manager)
        self.search_entry.focus_set()

    # ==========================================================================
    # ZARZĄDZANIE WŁAŚCICIELAMI
    # ==========================================================================

    def delete_selected_owner(self):
        """Usuwa zaznaczonych właścicieli wraz z opcją usunięcia folderów."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Brak zaznaczenia", "Najpierw zaznacz właściciela na liście.")
            return

        for item_key in list(selected_items):
            owner_name = self.data[item_key].get("ownerName", "tego właściciela")

            if messagebox.askyesno("Potwierdzenie usunięcia", f"Czy na pewno chcesz usunąć wpis dla: {owner_name}?"):
                # Pobierz folder backup aktywnej miejscowości
                backup_folder = get_active_location_backup_folder()
                folder_to_delete = os.path.join(backup_folder, "protokoly", item_key)
                should_delete_folder = False
                
                if os.path.exists(folder_to_delete):
                    if messagebox.askyesno("Usuwanie Folderu", f"Znaleziono folder '{item_key}' ze skanami. Czy chcesz go również usunąć?"):
                        should_delete_folder = True

                try:
                    del self.data[item_key]
                    if should_delete_folder:
                        shutil.rmtree(folder_to_delete)
                        print(f"Usunięto folder: {folder_to_delete}")
                except Exception as e:
                    messagebox.showerror("Błąd", f"Wystąpił błąd podczas usuwania: {e}")

        self.refresh_treeview()

    def refresh_treeview(self):
        """Odświeża tabelę właścicieli i naprawia brakujące foldery."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Mechanizm samonaprawy folderów
        backup_folder = get_active_location_backup_folder()
        protokoly_path = os.path.join(backup_folder, "protokoly")
        if not os.path.exists(protokoly_path):
            os.makedirs(protokoly_path)

        for key in self.data.keys():
            owner_folder = os.path.join(protokoly_path, key)
            if not os.path.exists(owner_folder):
                try:
                    os.makedirs(owner_folder)
                    print(f"Naprawiono: Utworzono brakujący folder '{key}'")
                except Exception as e:
                    print(f"Błąd przy tworzeniu folderu dla '{key}': {e}")

        # Sortowanie i wyświetlanie
        try:
            sorted_keys = sorted(self.data.keys(), key=lambda k: int(self.data[k].get("orderNumber", "99999")))
        except (ValueError, TypeError):
            sorted_keys = sorted(self.data.keys())

        for key in sorted_keys:
            owner = self.data[key]
            plot_count = len(owner.get("buildingPlots", [])) + len(owner.get("agriculturalPlots", []))
            self.tree.insert("", tk.END, iid=key, values=(
                owner.get("orderNumber", "N/A"),
                owner.get("ownerName", "Brak nazwy"),
                plot_count,
            ))

    def _filter_owners(self, *args):
        """Filtruje listę właścicieli według frazy wyszukiwania."""
        search_term = self.search_var.get().lower()
        
        for item in self.tree.get_children():
            self.tree.delete(item)

        sorted_keys = sorted(self.data.keys(), key=lambda k: int(self.data[k].get("orderNumber", "99999")))
        
        for key in sorted_keys:
            owner = self.data[key]
            owner_name = owner.get("ownerName", "Brak nazwy").lower()
            unique_key = key.lower()

            if search_term in owner_name or search_term in unique_key:
                plot_count = len(owner.get("buildingPlots", [])) + len(owner.get("agriculturalPlots", []))
                self.tree.insert("", tk.END, iid=key, values=(
                    owner.get("orderNumber", "N/A"),
                    owner.get("ownerName", "Brak nazwy"),
                    plot_count,
                ))

    def _auto_resize_columns(self, event):
        """Automatycznie dostosowuje szerokość kolumn."""
        total = event.width - 20
        lp_w = 60
        count_w = 150
        name_w = max(total - lp_w - count_w, 150)
        self.tree.column("name", width=name_w)

    # ==========================================================================
    # IMPORT I EKSPORT DANYCH
    # ==========================================================================

    def load_from_json(self):
        """Wczytuje dane właścicieli z pliku JSON."""
        if not os.path.exists(JSON_FILE_PATH):
            messagebox.showinfo("Informacja", "Nie znaleziono pliku JSON. Zaimportuj dane z 'owner.js'.")
            return
            
        try:
            with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            messagebox.showinfo("✅ Sukces", f"Wczytano {len(self.data)} właścicieli.")
            self.refresh_treeview()
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Nie udało się wczytać pliku JSON: {e}")

    def save_to_json(self):
        """Zapisuje dane do pliku JSON."""
        try:
            with open(JSON_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("✅ Sukces", f"Zmiany zapisano w:\n{JSON_FILE_PATH}")
        except Exception as e:
            messagebox.showerror("❌ Błąd zapisu", f"Nie udało się zapisać pliku: {e}")

    # ==========================================================================
    # MIGRACJA DANYCH
    # ==========================================================================

    def run_migration(self) -> bool:
        """
        Uruchamia skrypt migracji danych do bazy PostgreSQL.
        Zwraca True przy sukcesie, False przy błędzie.
        """
        try:
            # Konfiguracja środowiska UTF-8
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # Uruchomienie skryptu
            result = subprocess.run(
                [sys.executable, MIGRATE_SCRIPT],
                cwd=BACKEND_DIR,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            # Analiza wyniku
            if result.returncode == 0:
                success_msg = "Migracja danych zakończyła się pomyślnie."
                if result.stdout:
                    self.show_migration_details(success_msg, result.stdout, is_error=False)
                else:
                    messagebox.showinfo("✅ Migracja zakończona", success_msg)
                return True
            else:
                error_msg = f"Skrypt migracji zwrócił kod błędu: {result.returncode}"
                if result.stderr:
                    if 'UnicodeEncodeError' in result.stderr:
                        clean_error = "Wystąpił problem z kodowaniem znaków. Sprawdź logi migracji."
                        self.show_migration_details(error_msg, clean_error, is_error=True)
                    else:
                        self.show_migration_details(error_msg, result.stderr, is_error=True)
                else:
                    messagebox.showerror("❌ Błąd migracji", error_msg)
                return False
                
        except FileNotFoundError:
            messagebox.showerror("❌ Nie znaleziono skryptu", f"Sprawdź ścieżkę:\n{MIGRATE_SCRIPT}")
            return False
        except Exception as e:
            messagebox.showerror("❌ Błąd migracji", str(e))
            return False

    def show_migration_details(self, title, details, is_error=False):
        """Wyświetla szczegóły migracji w osobnym oknie."""
        detail_window = tk.Toplevel(self)
        detail_window.title("📋 Szczegóły migracji")
        detail_window.transient(self)
        detail_window.grab_set()
        
        # Pozycjonowanie okna
        sw, sh = detail_window.winfo_screenwidth(), detail_window.winfo_screenheight()
        w, h = 700, 500
        detail_window.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        detail_window.minsize(600, 400)
        
        main_frame = ttk.Frame(detail_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text=title, font=("Segoe UI", 11, "bold"))
        title_label.pack(anchor="w", pady=(0, 10))
        
        # Pole tekstowe z logami
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, width=80, height=20, font=("Consolas", 10))
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Formatowanie tekstu
        formatted_details = details
        formatted_details = formatted_details.replace('[OK]', '✔️')
        formatted_details = formatted_details.replace('[SUKCES]', '✅')
        formatted_details = formatted_details.replace('[BŁĄD KRYTYCZNY]', '❌')
        formatted_details = formatted_details.replace('[BŁĄD]', '❌')
        formatted_details = formatted_details.replace('[INFO]', 'ℹ️')
        formatted_details = formatted_details.replace('[OSTRZEŻENIE]', '⚠️')
        formatted_details = formatted_details.replace('========================================', '═' * 45)
        
        text_widget.insert("1.0", formatted_details)
        
        # Konfiguracja kolorowania
        text_widget.tag_configure("header", font=("Consolas", 10, "bold"), foreground="#1e88e5")
        text_widget.tag_configure("success", foreground="#2e7d32")
        text_widget.tag_configure("error", foreground="#c62828")
        text_widget.tag_configure("warning", foreground="#f57c00")
        text_widget.tag_configure("step", font=("Consolas", 10, "bold"), foreground="#5e35b1")
        text_widget.tag_configure("separator", foreground="#757575")
        
        # Kolorowanie linii
        lines = formatted_details.split('\n')
        for i, line in enumerate(lines):
            line_start = f"{i+1}.0"
            line_end = f"{i+1}.end"
            
            if '═══' in line or '───' in line:
                text_widget.tag_add("separator", line_start, line_end)
            elif 'SKRYPT MIGRACJI DANYCH' in line:
                text_widget.tag_add("header", line_start, line_end)
            elif line.startswith('--- Krok'):
                text_widget.tag_add("step", line_start, line_end)
            elif '✔️' in line or '✅' in line or 'SUKCES' in line:
                text_widget.tag_add("success", line_start, line_end)
            elif '❌' in line or 'BŁĄD' in line:
                text_widget.tag_add("error", line_start, line_end)
            elif '⚠️' in line or 'OSTRZEŻENIE' in line:
                text_widget.tag_add("warning", line_start, line_end)
            elif '    ->' in line:
                text_widget.tag_add("step", line_start, line_end)
        
        text_widget.config(state=tk.DISABLED)
        
        # Przyciski akcji
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        close_btn = ttk.Button(btn_frame, text="Zamknij", command=detail_window.destroy,
                              style="Success.TButton" if not is_error else "Danger.TButton")
        close_btn.pack(side=tk.RIGHT)
        
        def copy_to_clipboard():
            """Kopiuje logi do schowka."""
            self.clipboard_clear()
            self.clipboard_append(formatted_details)
            messagebox.showinfo("✅ Skopiowano", "Treść została skopiowana do schowka.", parent=detail_window)
        
        copy_btn = ttk.Button(btn_frame, text="📋 Kopiuj do schowka", command=copy_to_clipboard)
        copy_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        def save_to_file():
            """Zapisuje logi do pliku."""
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                parent=detail_window,
                defaultextension=".txt",
                initialfile=f"migracja_log_{timestamp}.txt",
                filetypes=[("Pliki tekstowe", "*.txt"), ("Wszystkie pliki", "*.*")]
            )
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(formatted_details)
                    messagebox.showinfo("✅ Zapisano", f"Log został zapisany do:\n{filename}", parent=detail_window)
                except Exception as e:
                    messagebox.showerror("❌ Błąd", f"Nie udało się zapisać pliku:\n{e}", parent=detail_window)
        
        save_btn = ttk.Button(btn_frame, text="💾 Zapisz do pliku", command=save_to_file)
        save_btn.pack(side=tk.RIGHT, padx=(0, 5))

    def save_and_migrate(self):
        """Zapisuje dane i uruchamia migrację."""
        try:
            with open(JSON_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            print(f"Dane zapisane do: {JSON_FILE_PATH}")
            
            success = self.run_migration()
            if success:
                self.refresh_treeview()
                
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Wystąpił błąd podczas zapisu i migracji:\n{e}")

    # ==========================================================================
    # OBSŁUGA ZDARZEŃ
    # ==========================================================================

    def _open_edit_window(self, owner_dict, key=None):
        """Otwiera okno edycji właściciela."""
        sorted_keys_on_screen = self.tree.get_children()
        dlg = EditWindow(self, owner_dict, key, self.on_save, sorted_keys_on_screen)
        self.wait_window(dlg)
        self.search_entry.focus_force()

    def on_double_click(self, event):
        """Obsługuje podwójne kliknięcie na właścicielu."""
        item_key = self.tree.focus()
        if item_key:
            self._open_edit_window(self.data[item_key], item_key)

    def on_delete_key(self, event):
        """Obsługuje klawisz Delete."""
        self.delete_selected_owner()

    def add_new_owner(self):
        """Dodaje nowego właściciela."""
        self._open_edit_window({}, None)

    def on_save(self, new_data, original_key):
        """
        Zapisuje dane właściciela.
        Zwraca True przy sukcesie, False przy błędzie.
        """
        # Walidacja i sanityzacja klucza
        raw_key = new_data.get("unikalny_klucz", "").strip()
        safe_key = re.sub(r'[\\/*?:"<>|\s]+', "_", raw_key)
        safe_key = re.sub(r"__+", "_", safe_key)
        safe_key = safe_key.strip("_")

        if raw_key != safe_key:
            print(f"INFO: Klucz '{raw_key}' został automatycznie poprawiony na '{safe_key}'.")
            new_data["unikalny_klucz"] = safe_key

        new_key = safe_key

        # Walidacja danych
        if not new_key:
            messagebox.showerror("❌ Błąd Walidacji", "Pole 'Unikalny klucz' nie może być puste!")
            return False

        if new_key in self.data and new_key != original_key:
            messagebox.showerror("❌ Błąd Walidacji", f"Unikalny klucz '{new_key}' jest już używany!")
            return False

        # Zarządzanie folderami
        backup_folder = get_active_location_backup_folder()
        protokoly_path = os.path.join(backup_folder, "protokoly")

        try:
            if original_key and original_key != new_key:
                old_folder = os.path.join(protokoly_path, original_key)
                if os.path.exists(old_folder):
                    new_folder = os.path.join(protokoly_path, new_key)
                    os.rename(old_folder, new_folder)
            elif not original_key:
                new_folder = os.path.join(protokoly_path, new_key)
                if not os.path.exists(new_folder):
                    os.makedirs(new_folder)
        except OSError as e:
            messagebox.showerror("❌ Błąd Systemu Plików", f"Nie udało się zarządzać folderem protokołu:\n{e}")
            return False

        # Aktualizacja danych
        del new_data["unikalny_klucz"]
        self.data[new_key] = new_data

        if original_key and original_key != new_key:
            del self.data[original_key]

        self.refresh_treeview()
        self.search_entry.focus_set()
        return True

# ==========================================================================
# FUNKCJE POMOCNICZE DLA IKON OKIEN
# ==========================================================================

def set_dialog_icon(window):
    """
    Ustawia ikonę dla okna dialogowego (Toplevel).
    Używa custom ikony jeśli istnieje, w przeciwnym razie domyślnej.

    Args:
        window: Okno tk.Toplevel do którego ma być dodana ikona
    """
    try:
        # Ścieżka do ikony w katalogu launcher/assets
        launcher_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'launcher')
        icon_dir = os.path.join(launcher_dir, 'assets')

        # Sprawdź czy jest zapisana custom ikona
        custom_png = os.path.join(icon_dir, 'custom_icon.png')
        custom_ico = os.path.join(icon_dir, 'custom_icon.ico')

        # Preferuj custom ikonę jeśli istnieje
        png_path = custom_png if os.path.exists(custom_png) else os.path.join(icon_dir, 'feather_icon.png')
        ico_path = custom_ico if os.path.exists(custom_ico) else os.path.join(icon_dir, 'feather_icon.ico')

        if os.path.exists(png_path):
            icon_image = tk.PhotoImage(file=png_path)
            window.iconphoto(True, icon_image)
            # Zachowaj referencję aby uniknąć garbage collection
            window._icon_image = icon_image

        # Dla Windows, spróbuj też ICO
        if platform.system() == "Windows":
            if os.path.exists(ico_path):
                window.iconbitmap(ico_path)
    except Exception as e:
        print(f"⚠️ Nie udało się ustawić ikony okna: {e}")

# ==========================================================================
# KLASA OKNA EDYCJI
# ==========================================================================

class EditWindow(tk.Toplevel):
    """Okno edycji danych właściciela z zarządzaniem skanami."""
    
    def __init__(self, parent, owner_data, original_key, save_callback, sorted_keys=None):
        """Inicjalizacja okna edycji."""
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title(f"Edycja Danych - {owner_data.get('ownerName', 'Nowy Wpis')}")

        # Ustaw ikonę okna
        set_dialog_icon(self)

        # Geometria okna
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * 0.90), int(sh * 0.90)
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
        if platform.system() == "Windows":
            self.state("zoomed")
        self.minsize(800, 600)

        # Dane i stan
        self.owner_data = owner_data
        self.original_key = original_key
        self.save_callback = save_callback
        self.fields = {}
        self.scans_widgets = {}
        self.sorted_keys = sorted_keys or []

        # Utworzenie przewijalnego kontenera
        outer = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(outer, highlightthickness=0, background=self.cget("background"))
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        main = ttk.Frame(canvas, padding=15)
        win_id = canvas.create_window((0, 0), window=main, anchor="nw")
        
        main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))

        self._bind_mousewheel_to_canvas(canvas, main)

        # Budowa formularza
        self._build_form(main)
        self.initial_form_data = self._get_current_form_data()

        # Przyciski nawigacji
        EXTRA_BOTTOM_MARGIN = 60
        bottom_frame = ttk.Frame(main)
        bottom_frame.pack(fill=tk.X, pady=(20, EXTRA_BOTTOM_MARGIN))
        bottom_frame.columnconfigure((0, 1, 2), weight=1)

        self.prev_btn = ttk.Button(bottom_frame, text="<< Poprzedni", command=lambda: self._navigate(-1))
        self.prev_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        save_btn = ttk.Button(bottom_frame, text="Zapisz", command=self.save, style="Success.TButton")
        save_btn.grid(row=0, column=1, sticky="ew", ipady=6)

        self.next_btn = ttk.Button(bottom_frame, text="Następny >>", command=lambda: self._navigate(1))
        self.next_btn.grid(row=0, column=2, sticky="ew", padx=(5, 0))

        self._update_nav_buttons_state()
        self.bind("<Escape>", lambda e: self.destroy())

    # ==========================================================================
    # METODY POMOCNICZE
    # ==========================================================================

    def _center_or_maximize(self, percent=0.9):
        """Centruje lub maksymalizuje okno."""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * percent), int(sh * percent)
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
        self.minsize(800, 600)
        if platform.system() == "Windows":
            self.state("zoomed")

    def _bind_mousewheel_to_canvas(self, canvas, main_frame):
        """Binduje scroll myszki do canvas."""
        def _on_mousewheel(event):
            if canvas.winfo_exists():
                if platform.system() == 'Windows':
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                else:
                    canvas.yview_scroll(int(-1*event.delta), "units")
        
        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        
        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
        
        self.bind("<Enter>", _bind_to_mousewheel)
        self.bind("<Leave>", _unbind_from_mousewheel)
        main_frame.bind("<Enter>", _bind_to_mousewheel)

    # ==========================================================================
    # NAWIGACJA MIĘDZY WPISAMI
    # ==========================================================================

    def _navigate(self, direction):
        """Przechodzi do poprzedniego lub następnego właściciela."""
        current_data = self._get_current_form_data()
        if current_data != self.initial_form_data:
            answer = messagebox.askyesnocancel(
                "Nawigacja",
                "Wykryto niezapisane zmiany. Czy chcesz je zapisać przed przejściem dalej?",
                parent=self,
            )
            if answer is None:
                return
            if answer is True:
                if not self.save(close_after=False):
                    return

        try:
            current_index = self.sorted_keys.index(self.original_key)
        except ValueError:
            messagebox.showwarning("Błąd nawigacji", "Nie można odnaleźć bieżącego wpisu na liście.", parent=self)
            return

        new_index = current_index + direction
        next_key = self.sorted_keys[new_index]
        next_data = self.master.data[next_key]

        self._load_data(next_data, next_key)
        self.initial_form_data = self._get_current_form_data()

    def _load_data(self, owner_data, key):
        """Ładuje dane właściciela do formularza."""
        self.owner_data = owner_data
        self.original_key = key

        for f_key, widget in self.fields.items():
            value = owner_data.get(f_key, "")
            if f_key == "unikalny_klucz":
                value = key

            if isinstance(widget, tuple):  # Pole daty
                day, month, year = "", "", ""
                if value:
                    match = re.match(r"(\d+)\s+([a-zA-Zęóąśłżźćń]+)\s+(\d{4})", str(value).strip())
                    if match:
                        day, month, year = match.groups()
                widget[0].delete(0, tk.END)
                widget[0].insert(0, day)
                widget[1].delete(0, tk.END)
                widget[1].insert(0, month)
                widget[2].delete(0, tk.END)
                widget[2].insert(0, year)
            elif isinstance(widget, scrolledtext.ScrolledText):
                widget.delete("1.0", tk.END)
                if "Plots" in f_key and isinstance(value, list):
                    value = self.format_plots_for_display(value)
                widget.insert("1.0", str(value))
            else:
                widget.delete(0, tk.END)
                widget.insert(0, str(value))

        self.title(f"Edycja Danych - {owner_data.get('ownerName', key)}")
        self._check_key_and_enable_scans()
        self._update_nav_buttons_state()

    def _update_nav_buttons_state(self):
        """Aktualizuje stan przycisków nawigacji."""
        try:
            current_index = self.sorted_keys.index(self.original_key)
            self.prev_btn.config(state=tk.NORMAL if current_index > 0 else tk.DISABLED)
            self.next_btn.config(state=tk.NORMAL if current_index < len(self.sorted_keys) - 1 else tk.DISABLED)
        except (ValueError, AttributeError):
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)

    # ==========================================================================
    # BUDOWANIE FORMULARZA
    # ==========================================================================

    def _build_form(self, parent):
        """Tworzy pola formularza edycji."""
        
        # Sekcja identyfikatora
        key_frame = ttk.LabelFrame(parent, text="Identyfikator", padding=10)
        key_frame.pack(fill=tk.X, pady=5)
        self.create_field(key_frame, "unikalny_klucz", "Unikalny klucz:", self.original_key or "")

        # Sekcja danych właściciela
        details_frame = ttk.LabelFrame(parent, text="Dane Właściciela", padding=10)
        details_frame.pack(fill=tk.X, pady=5)
        
        self.create_field(details_frame, "orderNumber", "Lp:", self.owner_data.get("orderNumber", ""))
        self.create_field(details_frame, "ownerName", "Imię i Nazwisko:", self.owner_data.get("ownerName", ""))
        self.create_date_field(details_frame, "protocolDate", "Data protokołu:", self.owner_data.get("protocolDate", ""))
        self.create_field(details_frame, "houseNumber", "Numer domu:", self.owner_data.get("houseNumber", ""))
        self.create_field(details_frame, "protocolLocation", "Miejsce protokołu:", self.owner_data.get("protocolLocation", ""))

        # Sekcja działek
        plots_frame = ttk.LabelFrame(parent, text="Działki (numery oddzielone przecinkami)", padding=10)
        plots_frame.pack(fill=tk.X, pady=5)
        
        self.create_textarea(plots_frame, "buildingPlots", "Działki budowlane (z protokołu):",
                            self.format_plots_for_display(self.owner_data.get("buildingPlots", [])), height=2)
        self.create_textarea(plots_frame, "agriculturalPlots", "Działki rolne (z protokołu):",
                            self.format_plots_for_display(self.owner_data.get("agriculturalPlots", [])), height=2)
        self.create_textarea(plots_frame, "realbuildingPlots", "Działki budowlane (rzeczywiste):",
                            self.format_plots_for_display(self.owner_data.get("realbuildingPlots", [])), height=2)
        self.create_textarea(plots_frame, "realagriculturalPlots", "Działki rolne (rzeczywiste):",
                            self.format_plots_for_display(self.owner_data.get("realagriculturalPlots", [])), height=2)

        # Sekcja dodatkowych informacji
        notes_frame = ttk.LabelFrame(parent, text="Dodatkowe Informacje", padding=10)
        notes_frame.pack(fill=tk.X, pady=5)
        
        self.create_textarea(notes_frame, "genealogy", "Genealogia:", self.owner_data.get("genealogy", ""), height=4)
        self.create_textarea(notes_frame, "ownershipHistory", "Historia posiadania działek:",
                            self.owner_data.get("ownershipHistory", ""), height=4)
        self.create_textarea(notes_frame, "remarks", "Ciąg dalszy/Uwagi:", self.owner_data.get("remarks", ""), height=4)
        self.create_textarea(notes_frame, "wspolwlasnosc", "Współwłasność/Służebność:",
                            self.owner_data.get("wspolwlasnosc", ""), height=4)

        # Pole powiązań z tooltipem
        relacje_frame = ttk.Frame(notes_frame)
        relacje_frame.pack(fill=tk.X, pady=4)
        relacje_frame.columnconfigure(0, weight=1)
        relacje_frame.rowconfigure(1, weight=1)

        label_icon_frame = ttk.Frame(relacje_frame)
        label_icon_frame.grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(label_icon_frame, text="Powiązania i transakcje").pack(side=tk.LEFT, anchor="w")
        
        help_icon = ttk.Label(label_icon_frame, text="?", cursor="hand2", font=("Segoe UI", 10, "bold"))
        help_icon.pack(side=tk.LEFT, anchor="w", padx=5)
        help_icon.bind("<Button-1>", self.toggle_relacje_tooltip)

        self.tooltip_window = None
        
        relacje_content = self.owner_data.get("powiazania_i_transakcje", self.owner_data.get("relacje_rodzinne", ""))
        txt_frame, self.fields["powiazania_i_transakcje"] = self.create_textarea_in_frame(relacje_frame, relacje_content, height=4)
        txt_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")

        # Sekcja analizy
        analysis_frame = ttk.LabelFrame(parent, text="Analiza", padding=10)
        analysis_frame.pack(fill=tk.X, pady=5)
        self.create_textarea(analysis_frame, "interpretacja_i_wnioski", "Interpretacja i wnioski:",
                            self.owner_data.get("interpretacja_i_wnioski", ""), height=6)

        # Sekcja zarządzania skanami
        scans_frame = ttk.LabelFrame(parent, text="Zarządzanie Skanami Protokółu", padding=10)
        scans_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.create_scans_section(scans_frame)
        self._check_key_and_enable_scans()
        self.fields["unikalny_klucz"].bind("<KeyRelease>", self._check_key_and_enable_scans)

    def _check_key_and_enable_scans(self, event=None):
        """Aktywuje/dezaktywuje sekcję skanów w zależności od klucza."""
        key = self.fields["unikalny_klucz"].get().strip()
        is_enabled = bool(key)
        new_state = tk.NORMAL if is_enabled else tk.DISABLED

        for widget in self.scans_widgets.values():
            if isinstance(widget, (ttk.Button, tk.Listbox)):
                widget.config(state=new_state)

        if is_enabled:
            self.populate_scans_list()
        else:
            self.scans_widgets["listbox"].delete(0, tk.END)

    # ==========================================================================
    # TWORZENIE PÓL FORMULARZA
    # ==========================================================================

    def create_field(self, parent, key, label_text, initial_value):
        """Tworzy standardowe pole tekstowe."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=4)
        ttk.Label(frame, text=label_text).pack(side=tk.LEFT, anchor="w", padx=(0, 10))
        entry = ttk.Entry(frame)
        entry.insert(0, str(initial_value))
        entry.pack(fill=tk.X, expand=True)
        self.fields[key] = entry

    def create_date_field(self, parent, key, label_text, initial_value):
        """Tworzy pole daty (dzień, miesiąc, rok)."""
        main_date_frame = ttk.Frame(parent)
        main_date_frame.pack(fill=tk.X, pady=4)
        ttk.Label(main_date_frame, text=label_text).pack(side=tk.LEFT, anchor="n", padx=(0, 10))

        fields_frame = ttk.Frame(main_date_frame)
        fields_frame.pack(fill=tk.X, expand=True)

        day, month, year = "", "", ""
        if initial_value:
            match = re.match(r"(\d+)\s+([a-zA-Zęóąśłżźćń]+)\s+(\d{4})(?:\s+rok)?", initial_value.strip())
            if match:
                day, month, year = match.groups()

        # Pole dzień
        day_frame = ttk.Frame(fields_frame)
        day_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Label(day_frame, text="Dzień").pack(anchor="w")
        day_entry = ttk.Entry(day_frame)
        day_entry.insert(0, day)
        day_entry.pack(fill=tk.X)

        # Pole miesiąc
        month_frame = ttk.Frame(fields_frame)
        month_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Label(month_frame, text="Miesiąc (słownie)").pack(anchor="w")
        month_entry = ttk.Entry(month_frame)
        month_entry.insert(0, month)
        month_entry.pack(fill=tk.X)

        # Pole rok
        year_frame = ttk.Frame(fields_frame)
        year_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Label(year_frame, text="Rok").pack(anchor="w")
        year_entry = ttk.Entry(year_frame)
        year_entry.insert(0, year)
        year_entry.pack(fill=tk.X)

        self.fields[key] = (day_entry, month_entry, year_entry)

    def create_textarea(self, parent, key, label, initial="", *, height=3):
        """Tworzy pole tekstowe z możliwością powiększenia."""
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=4)

        header = ttk.Frame(row)
        header.pack(fill=tk.X)
        ttk.Label(header, text=label).pack(side=tk.LEFT, anchor="w")

        expand_btn = ttk.Button(header, text="Powiększ", command=lambda: self._open_text_popup(txt, label))
        expand_btn.pack(side=tk.RIGHT)

        bigger = tkfont.nametofont("TkTextFont").cget("size") + 2
        txt = scrolledtext.ScrolledText(row, height=height, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1,
                                       font=("Segoe UI", bigger))
        txt.insert("1.0", initial.replace("\\n", "\n"))
        txt.pack(fill=tk.X, expand=True, pady=(2, 0))

        self.fields[key] = txt

    def create_textarea_in_frame(self, parent, initial_content, height):
        """Tworzy pole tekstowe w osobnej ramce."""
        txt_frame = ttk.Frame(parent)
        bigger = tkfont.nametofont("TkTextFont").cget("size") + 2
        txt = scrolledtext.ScrolledText(txt_frame, height=height, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1,
                                       font=("Segoe UI", bigger))
        txt.insert("1.0", initial_content.replace("\\n", "\n"))
        txt.pack(fill=tk.BOTH, expand=True)
        return txt_frame, txt

    def _open_text_popup(self, original_widget, title="Edytuj tekst"):
        """Otwiera duże okno do edycji tekstu."""
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.transient(self)
        popup.grab_set()

        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        w, h = int(sw * 0.8), int(sh * 0.8)
        popup.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        big_font = ("Segoe UI", tkfont.nametofont("TkTextFont").cget("size") + 4)
        txt = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=big_font, relief=tk.SOLID, borderwidth=1)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt.insert("1.0", original_widget.get("1.0", tk.END))

        btn_bar = ttk.Frame(popup)
        btn_bar.pack(fill=tk.X, pady=5, padx=10)

        def _save_and_close():
            original_widget.delete("1.0", tk.END)
            original_widget.insert("1.0", txt.get("1.0", tk.END).rstrip())
            popup.destroy()

        ttk.Button(btn_bar, text="Zapisz", style="Accent.TButton", command=_save_and_close).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_bar, text="Anuluj", command=popup.destroy).pack(side=tk.RIGHT)

    # ==========================================================================
    # ZARZĄDZANIE SKANAMI
    # ==========================================================================

    def create_scans_section(self, parent):
        """Tworzy interfejs zarządzania skanami."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Przyciski zmiany kolejności
        reorder_frame = ttk.Frame(list_frame)
        reorder_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        up_btn = ttk.Button(reorder_frame, text="▲", command=self.move_scan_up, width=3)
        up_btn.pack(pady=2)
        down_btn = ttk.Button(reorder_frame, text="▼", command=self.move_scan_down, width=3)
        down_btn.pack(pady=2)
        
        self.scans_widgets["up_btn"] = up_btn
        self.scans_widgets["down_btn"] = down_btn

        # Lista skanów
        listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        listbox.bind("<Double-1>", self.open_selected_scan)
        self.scans_widgets["listbox"] = listbox

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)

        # Przyciski akcji
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=5)

        add_btn = ttk.Button(btn_frame, text="Dodaj skany...", command=self.add_scans)
        add_btn.pack(side=tk.LEFT)
        self.scans_widgets["add_btn"] = add_btn

        remove_btn = ttk.Button(btn_frame, text="Usuń zaznaczony", command=self.remove_selected_scan, style="Danger.TButton")
        remove_btn.pack(side=tk.LEFT, padx=5)
        self.scans_widgets["remove_btn"] = remove_btn

    def move_scan_up(self):
        """Przesuwa skan w górę na liście."""
        listbox = self.scans_widgets["listbox"]
        selected_indices = listbox.curselection()
        
        if not selected_indices:
            return

        idx = selected_indices[0]
        if idx > 0:
            text = listbox.get(idx)
            listbox.delete(idx)
            listbox.insert(idx - 1, text)
            listbox.selection_set(idx - 1)
            listbox.activate(idx - 1)

    def move_scan_down(self):
        """Przesuwa skan w dół na liście."""
        listbox = self.scans_widgets["listbox"]
        selected_indices = listbox.curselection()
        
        if not selected_indices:
            return

        idx = selected_indices[0]
        if idx < listbox.size() - 1:
            text = listbox.get(idx)
            listbox.delete(idx)
            listbox.insert(idx + 1, text)
            listbox.selection_set(idx + 1)
            listbox.activate(idx + 1)

    def get_scans_folder_path(self):
        """Zwraca ścieżkę do folderu ze skanami."""
        current_key = self.fields["unikalny_klucz"].get().strip()
        if not current_key:
            return None
        backup_folder = get_active_location_backup_folder()
        return os.path.join(backup_folder, "protokoly", current_key)

    def populate_scans_list(self):
        """Wypełnia listę skanów."""
        listbox = self.scans_widgets["listbox"]
        listbox.delete(0, tk.END)

        folder_path = self.get_scans_folder_path()
        if folder_path and os.path.exists(folder_path):
            try:
                files = sorted(
                    os.listdir(folder_path),
                    key=lambda x: (int(os.path.splitext(x)[0]) if x.replace(".jpg", "").isdigit() else 999)
                )
                for filename in files:
                    if filename.lower().endswith(".jpg"):
                        listbox.insert(tk.END, filename)
            except Exception as e:
                print(f"Błąd odczytu folderu ze skanami: {e}")

    def add_scans(self):
        """Dodaje nowe skany do folderu."""
        folder_path = self.get_scans_folder_path()
        if not folder_path:
            messagebox.showwarning("Brak klucza", "Wpisz i zatwierdź unikalny klucz, aby dodać skany.")
            return

        try:
            os.makedirs(folder_path, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Błąd", f"Nie można utworzyć folderu dla skanów:\n{e}")
            return

        files_to_add = filedialog.askopenfilenames(title="Wybierz pliki JPG", filetypes=[("Obrazy JPG", "*.jpg")])
        
        if not files_to_add:
            return

        for source_path in files_to_add:
            existing_numbers = [
                int(os.path.splitext(f)[0])
                for f in os.listdir(folder_path)
                if f.replace(".jpg", "").isdigit()
            ]
            next_num = max(existing_numbers) + 1 if existing_numbers else 1

            dest_filename = f"{next_num}.jpg"
            dest_path = os.path.join(folder_path, dest_filename)

            try:
                shutil.copy(source_path, dest_path)
            except Exception as e:
                messagebox.showerror("Błąd kopiowania", f"Nie udało się skopiować pliku: {source_path}\nBłąd: {e}")
                break

        self.populate_scans_list()

    def remove_selected_scan(self):
        """Usuwa zaznaczony skan."""
        listbox = self.scans_widgets["listbox"]
        selected_indices = listbox.curselection()
        
        if not selected_indices:
            messagebox.showwarning("Brak zaznaczenia", "Zaznacz skan do usunięcia.")
            return

        filename_to_delete = listbox.get(selected_indices[0])

        if messagebox.askyesno("Potwierdzenie", f"Czy na pewno chcesz usunąć plik '{filename_to_delete}'?"):
            folder_path = self.get_scans_folder_path()
            file_path = os.path.join(folder_path, filename_to_delete)
            
            try:
                os.remove(file_path)
                self.populate_scans_list()
            except Exception as e:
                messagebox.showerror("Błąd usuwania", f"Nie udało się usunąć pliku: {e}")

    def open_selected_scan(self, event):
        """Otwiera zaznaczony skan w domyślnej aplikacji."""
        listbox = self.scans_widgets["listbox"]
        selected_indices = listbox.curselection()
        
        if not selected_indices:
            return

        filename_to_open = listbox.get(selected_indices[0])
        folder_path = self.get_scans_folder_path()
        if not folder_path:
            return

        file_path = os.path.join(folder_path, filename_to_open)

        if os.path.exists(file_path):
            try:
                os.startfile(file_path)
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie można otworzyć pliku: {file_path}\nBłąd: {e}")
        else:
            messagebox.showwarning("Plik nie istnieje", f"Plik '{filename_to_open}' nie został znaleziony.")

    # ==========================================================================
    # TOOLTIPS I POMOCNICZE
    # ==========================================================================

    def close_tooltip_if_exists(self, event=None):
        """Zamyka tooltip jeśli istnieje."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def toggle_relacje_tooltip(self, event):
        """Pokazuje/ukrywa tooltip dla pola powiązań."""
        if self.tooltip_window:
            self.close_tooltip_if_exists()
            return

        trigger_widget = event.widget

        self.tooltip_window = tk.Toplevel(self)
        self.tooltip_window.wm_overrideredirect(True)

        frame = ttk.Frame(self.tooltip_window, padding=10, relief="solid", borderwidth=1)
        frame.pack()

        ttk.Label(frame, text="Jak tworzyć linki do innych protokołów:", font=("Calibri", 10, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Użyj składni: [[Tekst widoczny|KluczUnikalny]]", foreground="gray").pack(anchor="w", pady=(0, 5))
        
        ttk.Separator(frame).pack(fill="x", pady=5)
        ttk.Label(frame, text="Przykład:").pack(anchor="w")

        code_label = ttk.Label(frame, text="Żona: [[Anna Micek|Anna_Micek]]", background="#e9ecef", padding=5,
                             relief="solid", borderwidth=1)
        code_label.pack(anchor="w", fill="x", pady=2)

        x = trigger_widget.winfo_rootx()
        y = trigger_widget.winfo_rooty()
        self.tooltip_window.geometry(f"+{x}+{y - 155}")

        self.tooltip_window.bind("<FocusOut>", self.close_tooltip_if_exists)
        self.tooltip_window.focus_set()

    # ==========================================================================
    # FORMATOWANIE I PARSOWANIE
    # ==========================================================================

    def format_plots_for_display(self, plots):
        """Formatuje listę działek do wyświetlenia."""
        if not plots:
            return ""
            
        formatted_list = []
        for p in plots:
            if isinstance(p, dict):
                num = p.get("numerator") or p.get("numarator", "?")
                den = p.get("denominator", "?")
                formatted_list.append(f"{num}/{den}")
            else:
                formatted_list.append(str(p))
                
        return ", ".join(formatted_list)

    def parse_plots_from_string(self, text):
        """Parsuje string z numerami działek."""
        if not text.strip():
            return []
            
        parsed_plots = []
        parts = text.split(",")
        
        for p in parts:
            p_clean = p.strip()
            if not p_clean:
                continue
                
            if "/" in p_clean:
                num, den = p_clean.split("/", 1)
                parsed_plots.append({"numerator": num.strip(), "denominator": den.strip()})
            else:
                parsed_plots.append(p_clean)
                
        return parsed_plots

    def _get_current_form_data(self):
        """Zbiera aktualne dane z formularza."""
        current_data = {}
        
        for key, widget in self.fields.items():
            if isinstance(widget, tuple):  # Pole daty
                day, month, year = widget[0].get(), widget[1].get(), widget[2].get()
                current_data[key] = f"{day} {month} {year} rok" if day and month and year else ""
            elif isinstance(widget, scrolledtext.ScrolledText):
                current_data[key] = widget.get("1.0", tk.END).strip()
            else:
                current_data[key] = widget.get().strip()

        for key in ["buildingPlots", "agriculturalPlots", "realbuildingPlots", "realagriculturalPlots"]:
            current_data[key] = self.parse_plots_from_string(current_data.get(key, ""))

        return current_data

    def save(self, close_after=True):
        """
        Zapisuje dane z formularza.
        Zwraca True przy sukcesie.
        """
        # Zbieranie danych
        saved_data = {}
        for key, widget in self.fields.items():
            if isinstance(widget, tuple):  # Pole daty
                day, month, year = widget[0].get(), widget[1].get(), widget[2].get()
                saved_data[key] = f"{day} {month} {year} rok" if day and month and year else ""
            elif isinstance(widget, scrolledtext.ScrolledText):
                saved_data[key] = widget.get("1.0", tk.END).strip()
            else:
                saved_data[key] = widget.get().strip()

        # Parsowanie działek
        saved_data["buildingPlots"] = self.parse_plots_from_string(saved_data.get("buildingPlots", ""))
        saved_data["agriculturalPlots"] = self.parse_plots_from_string(saved_data.get("agriculturalPlots", ""))
        saved_data["realbuildingPlots"] = self.parse_plots_from_string(saved_data.get("realbuildingPlots", ""))
        saved_data["realagriculturalPlots"] = self.parse_plots_from_string(saved_data.get("realagriculturalPlots", ""))

        # Reorganizacja skanów
        try:
            folder_path = self.get_scans_folder_path()
            if folder_path and os.path.exists(folder_path):
                listbox = self.scans_widgets["listbox"]
                final_order = list(listbox.get(0, tk.END))

                temp_folder = os.path.join(folder_path, "_temp_reorder")
                if not os.path.exists(temp_folder):
                    os.makedirs(temp_folder)

                current_files_in_folder = os.listdir(folder_path)
                for filename in final_order:
                    if filename in current_files_in_folder:
                        shutil.move(os.path.join(folder_path, filename), os.path.join(temp_folder, filename))

                for i, old_filename in enumerate(final_order):
                    if os.path.exists(os.path.join(temp_folder, old_filename)):
                        new_filename = f"{i + 1}.jpg"
                        shutil.move(os.path.join(temp_folder, old_filename), os.path.join(folder_path, new_filename))

                os.rmdir(temp_folder)
                
        except Exception as e:
            messagebox.showerror("Błąd Reorganizacji Skanów", f"Nie udało się zmienić kolejności plików:\n{e}", parent=self)
            return False

        # Wywołanie callback zapisu
        save_successful = self.save_callback(saved_data, self.original_key)

        if not save_successful:
            return False

        # Aktualizacja stanu
        self.original_key = saved_data.get("unikalny_klucz", self.original_key)
        
        if self.original_key in self.master.data:
            self.owner_data = self.master.data[self.original_key]

        if close_after:
            self.destroy()
        else:
            self.master.refresh_treeview()
            self.sorted_keys = self.master.tree.get_children()
            self._update_nav_buttons_state()
            self.title(f"Edycja Danych - {self.owner_data.get('ownerName', self.original_key)}")
            messagebox.showinfo("Zapisano", "Zmiany zostały zapisane.", parent=self)
            self.initial_form_data = self._get_current_form_data()

        return True

# ==========================================================================
# KLASA EDYTORA DEMOGRAFII
# ==========================================================================

class DemografiaEditorWindow(tk.Toplevel):
    """Okno edycji danych demograficznych."""
    
    def __init__(self, parent):
        """Inicjalizacja edytora demografii."""
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Edytor Danych Demograficznych")

        # Ustaw ikonę okna
        set_dialog_icon(self)

        self._setup_window_geometry()
        self.data = []
        self.load_data()
        self.create_widgets()

    def _setup_window_geometry(self):
        """Konfiguruje geometrię okna."""
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        
        if platform.system() == "Windows":
            taskbar_height = 50
            available_height = sh - taskbar_height
            w = int(sw * 0.85)
            h = int(available_height * 0.85)
            x = (sw - w) // 2
            y = (available_height - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")
            
            if w > 1400 and h > 800:
                self.after(100, lambda: self.state('zoomed'))
        else:
            w = min(int(sw * 0.8), 1200)
            h = min(int(sh * 0.8), 700)
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")
        
        self.minsize(600, 400)

    def load_data(self):
        """Wczytuje dane demograficzne."""
        try:
            if os.path.exists(DEMOGRAFIA_JSON_PATH):
                with open(DEMOGRAFIA_JSON_PATH, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
        except Exception as e:
            messagebox.showerror("Błąd odczytu", f"Nie udało się wczytać pliku demografia.json:\n{e}")

    def save_data(self):
        """Zapisuje dane demograficzne."""
        try:
            with open(DEMOGRAFIA_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Sukces", "Dane demograficzne zostały zapisane.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Błąd zapisu", f"Nie udało się zapisać pliku demografia.json:\n{e}")

    def create_widgets(self):
        """Tworzy interfejs edytora demografii."""
        # Zewnętrzna ramka z marginesem
        outer_frame = ttk.Frame(self)
        outer_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 50))
        
        main_container = ttk.Frame(outer_frame)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=0)
        main_container.grid_columnconfigure(0, weight=1)
        
        # Tabela danych
        tree_frame = ttk.LabelFrame(main_container, text="Dane demograficzne", padding="10")
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        table_container = ttk.Frame(tree_frame)
        table_container.grid(row=0, column=0, sticky="nsew")
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)
        
        # Konfiguracja Treeview
        columns = ("rok", "populacja", "katolicy", "zydzi", "inni", "opis")
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="browse")
        
        base_font = tkfont.nametofont("TkDefaultFont")
        row_height = base_font.cget("size") * 2
        
        self.style = ttk.Style(self)
        self.style.configure("Treeview", rowheight=row_height)
        
        # Nagłówki kolumn
        self.tree.heading("rok", text="Rok")
        self.tree.heading("populacja", text="Populacja")
        self.tree.heading("katolicy", text="Katolicy")
        self.tree.heading("zydzi", text="Żydzi")
        self.tree.heading("inni", text="Inni")
        self.tree.heading("opis", text="Opis")
        
        # Szerokości kolumn
        self.tree.column("rok", width=80, minwidth=60)
        self.tree.column("populacja", width=100, minwidth=80)
        self.tree.column("katolicy", width=100, minwidth=80)
        self.tree.column("zydzi", width=100, minwidth=80)
        self.tree.column("inni", width=100, minwidth=80)
        self.tree.column("opis", width=250, minwidth=150, stretch=True)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        # Paski przewijania
        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.populate_tree()
        
        # Panel przycisków
        button_frame = ttk.Frame(main_container)
        button_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 20))
        
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)
        
        ttk.Button(left_buttons, text="➕ Dodaj wiersz", command=self.add_row).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_buttons, text="🗑️ Usuń zaznaczony", command=self.delete_row, style="Danger.TButton").pack(side=tk.LEFT, padx=5)
        
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="💾 Zapisz i zamknij", command=self.save_and_close, style="Accent.TButton").pack(side=tk.RIGHT)
        
        # Bindowanie zdarzeń
        self.tree.bind("<Double-1>", self.on_double_click)
        self._bind_mousewheel()

    def _bind_mousewheel(self):
        """Binduje scroll myszki."""
        def _on_mousewheel(event):
            self.tree.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        self.tree.bind("<MouseWheel>", _on_mousewheel)
        self.tree.bind("<Button-4>", lambda e: self.tree.yview_scroll(-1, "units"))
        self.tree.bind("<Button-5>", lambda e: self.tree.yview_scroll(1, "units"))

    def populate_tree(self):
        """Wypełnia tabelę danymi."""
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for row in self.data:
            self.tree.insert("", "end", values=(
                row.get("rok", ""),
                row.get("populacja_ogolem", ""),
                row.get("katolicy", ""),
                row.get("zydzi", ""),
                row.get("inni", ""),
                row.get("opis", ""),
            ))

    def on_double_click(self, event):
        """Obsługuje edycję komórki."""
        item_id = self.tree.focus()
        if not item_id:
            return

        column = self.tree.identify_column(event.x)
        column_index = int(column.replace("#", "")) - 1
        current_values = list(self.tree.item(item_id)["values"])

        if column_index == 5:  # Kolumna Opis
            self._open_text_popup(item_id, column_index, current_values[column_index])
            return

        x, y, width, height = self.tree.bbox(item_id, column)

        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, current_values[column_index])
        entry.focus_set()
        entry.select_range(0, tk.END)

        def _save_and_close(_=None):
            current_values[column_index] = entry.get()
            self.tree.item(item_id, values=current_values)
            entry.destroy()

        entry.bind("<FocusOut>", _save_and_close)
        entry.bind("<Return>", _save_and_close)
        entry.bind("<Escape>", lambda e: entry.destroy())

    def _open_text_popup(self, item_id, col_idx, initial_text):
        """Otwiera okno edycji długiego tekstu."""
        popup = tk.Toplevel(self)
        popup.title("Edytuj opis")
        popup.transient(self)
        popup.grab_set()

        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        w, h = int(sw * 0.6), int(sh * 0.6)
        popup.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        big_font = ("Segoe UI", tkfont.nametofont("TkTextFont").cget("size") + 2)
        txt = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=big_font, relief=tk.SOLID, borderwidth=1)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt.insert("1.0", initial_text)
        txt.focus_set()

        btn_bar = ttk.Frame(popup)
        btn_bar.pack(fill=tk.X, pady=(0, 10), padx=10)

        def _save():
            new_text = txt.get("1.0", tk.END).rstrip()
            values = list(self.tree.item(item_id)["values"])
            values[col_idx] = new_text
            self.tree.item(item_id, values=values)
            popup.destroy()

        ttk.Button(btn_bar, text="Zapisz", style="Accent.TButton", command=_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_bar, text="Anuluj", command=popup.destroy).pack(side=tk.RIGHT)

    def add_row(self):
        """Dodaje pusty wiersz."""
        self.tree.insert("", "end", values=("", "", "", "", "", ""))
        children = self.tree.get_children()
        if children:
            self.tree.see(children[-1])
            self.tree.selection_set(children[-1])

    def delete_row(self):
        """Usuwa zaznaczony wiersz."""
        selected_item = self.tree.selection()
        if selected_item:
            if messagebox.askyesno("Potwierdzenie", "Czy na pewno chcesz usunąć zaznaczony wiersz?", parent=self):
                self.tree.delete(selected_item)

    def save_and_close(self):
        """Zapisuje dane i zamyka okno."""
        new_data = []
        
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id)["values"]

            if not any(str(v).strip() for v in values):
                continue

            try:
                def to_int_or_none(value):
                    if isinstance(value, str) and value.strip() == "":
                        return None
                    if value is None:
                        return None
                    return int(value)

                new_data.append({
                    "rok": to_int_or_none(values[0]),
                    "populacja_ogolem": to_int_or_none(values[1]),
                    "katolicy": to_int_or_none(values[2]),
                    "zydzi": to_int_or_none(values[3]),
                    "inni": to_int_or_none(values[4]),
                    "opis": str(values[5]) if values[5] else "",
                })
            except (ValueError, IndexError):
                messagebox.showerror("Błąd Danych", "Upewnij się, że w kolumnach numerycznych znajdują się tylko liczby.", parent=self)
                return

        self.data = new_data
        self.save_data()

# ==========================================================================
# KLASA MENEDŻERA KOPII ZAPASOWYCH
# ==========================================================================

class BackupManagerWindow(tk.Toplevel):
    """Okno zarządzania kopiami zapasowymi."""
    
    def __init__(self, parent):
        """Inicjalizacja menedżera kopii."""
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Menedżer Kopii Zapasowych (Dane + Skany)")

        # Ustaw ikonę okna
        set_dialog_icon(self)

        self.parent = parent
        self.selected_backup_file = None

        self._center_or_maximize()
        self.create_widgets()
        self.populate_backup_list()

    def _center_or_maximize(self):
        """Maksymalizuje lub centruje okno."""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        if platform.system() == "Windows":
            self.state("zoomed")
            self.geometry(f"{int(sw*0.9)}x{int(sh*0.9)}+{int(sw*0.05)}+{int(sh*0.05)}")
        else:
            w, h = 800, 600
            self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
        self.minsize(600, 400)

    def create_widgets(self):
        """Tworzy interfejs menedżera kopii."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Pasek górny
        top_bar = ttk.Frame(main_frame)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Button(top_bar, text="Stwórz nową kompletną kopię (ZIP)", command=self.create_backup,
                  style="Accent.TButton").pack(side=tk.LEFT)
        ttk.Label(top_bar, text="Kopie .zip zawierają dane i wszystkie skany").pack(side=tk.RIGHT, padx=10)

        # Lista kopii
        list_frame = ttk.LabelFrame(main_frame, text="Dostępne kopie zapasowe (od najnowszej)", padding="10")
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(list_frame, columns=("filename",), show="headings")
        self.tree.heading("filename", text="Nazwa Pliku Kopii Zapasowej (.zip)")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # Pasek akcji
        EXTRA_BOTTOM_MARGIN = 60
        action_bar = ttk.Frame(main_frame, padding=(0, 10, 0, EXTRA_BOTTOM_MARGIN))
        action_bar.grid(row=2, column=0, sticky="ew")

        self.selected_label = ttk.Label(action_bar, text="Nic nie zaznaczono", anchor="w")
        self.selected_label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.restore_btn = ttk.Button(action_bar, text="Przywróć", command=self.restore_backup, state=tk.DISABLED)
        self.restore_btn.pack(side=tk.RIGHT, padx=5)
        
        self.delete_btn = ttk.Button(action_bar, text="Usuń", style="Danger.TButton", command=self.delete_backup, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.RIGHT)

    def populate_backup_list(self):
        """Wyszukuje i wyświetla kopie zapasowe."""
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            files = [f for f in os.listdir(BACKUP_FOLDER) if f.startswith("backup_") and f.endswith(".zip")]
            files.sort(reverse=True)

            for filename in files:
                self.tree.insert("", "end", iid=filename, values=(filename,))
                
        except FileNotFoundError:
            ttk.Label(self.tree, text="Folder backup nie istnieje.").pack()
            
        self.on_select()

    def on_select(self, event=None):
        """Aktualizuje panel akcji."""
        selected_items = self.tree.selection()
        
        if selected_items:
            self.selected_backup_file = selected_items[0]
            self.selected_label.config(text=f"Zaznaczono: {self.selected_backup_file}")
            self.restore_btn.config(state=tk.NORMAL)
            self.delete_btn.config(state=tk.NORMAL)
        else:
            self.selected_backup_file = None
            self.selected_label.config(text="Nic nie zaznaczono")
            self.restore_btn.config(state=tk.DISABLED)
            self.delete_btn.config(state=tk.DISABLED)

    def create_backup(self):
        """Tworzy kompletną kopię zapasową ZIP."""
        if not os.path.exists(JSON_FILE_PATH):
            messagebox.showwarning("Brak pliku", "Nie można utworzyć kopii, ponieważ plik roboczy nie istnieje.", parent=self)
            return

        # Okno postępu
        progress_window = tk.Toplevel(self)
        progress_window.title("Tworzenie kopii zapasowej")
        progress_window.transient(self)
        progress_window.grab_set()

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 150) // 2
        progress_window.geometry(f"400x180+{x}+{y}")
        progress_window.resizable(False, False)

        ttk.Label(progress_window, text="Przygotowywanie plików...", font=("Segoe UI", 11), padding=10).pack(pady=(15, 5))
        
        progress_bar = ttk.Progressbar(progress_window, orient="horizontal", length=360, mode="determinate")
        progress_bar.pack(pady=5, padx=20)
        
        status_label = ttk.Label(progress_window, text="", padding=5, wraplength=350)
        status_label.pack(pady=(5, 10))

        def backup_thread_func():
            """Tworzy archiwum w osobnym wątku."""
            try:
                from datetime import datetime

                backup_folder = get_active_location_backup_folder()
                protokoly_path = os.path.join(backup_folder, "protokoly")
                files_to_backup = [JSON_FILE_PATH]
                
                if os.path.exists(DEMOGRAFIA_JSON_PATH):
                    files_to_backup.append(DEMOGRAFIA_JSON_PATH)

                scan_files = []
                if os.path.exists(protokoly_path):
                    for root, _, files in os.walk(protokoly_path):
                        for file in files:
                            scan_files.append(os.path.join(root, file))

                total_steps = len(files_to_backup) + len(scan_files)
                progress_bar["maximum"] = total_steps

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(BACKUP_FOLDER, f"backup_{timestamp}.zip")

                with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i, file_path in enumerate(files_to_backup):
                        arcname = os.path.basename(file_path)
                        status_label.config(text=f"Archiwizuję: {arcname}")
                        zf.write(file_path, arcname=arcname)
                        progress_bar["value"] = i + 1
                        self.update_idletasks()

                    for i, file_path in enumerate(scan_files):
                        arcname = os.path.join("protokoly", os.path.relpath(file_path, protokoly_path))
                        if (i % 10 == 0) or (i == len(scan_files) - 1):
                            status_label.config(text=f"Archiwizuję skany: {i+1}/{len(scan_files)}")
                        zf.write(file_path, arcname)
                        progress_bar["value"] = len(files_to_backup) + i + 1
                        self.update_idletasks()

                progress_window.success = True
                progress_window.backup_name = os.path.basename(backup_path)

            except Exception as e:
                progress_window.success = False
                progress_window.error_message = str(e)
            finally:
                self.after(100, progress_window.destroy)

        progress_window.success = None
        progress_window.error_message = ""
        progress_window.backup_name = ""

        backup_thread = threading.Thread(target=backup_thread_func, daemon=True)
        backup_thread.start()

        self.wait_window(progress_window)

        if hasattr(progress_window, "success") and progress_window.success:
            messagebox.showinfo("Sukces", f"Utworzono kompletną kopię zapasową:\n{progress_window.backup_name}", parent=self)
            self.populate_backup_list()
        elif hasattr(progress_window, "error_message") and progress_window.error_message:
            messagebox.showerror("Błąd", f"Nie udało się utworzyć kopii:\n{progress_window.error_message}", parent=self)

        self.on_select()

    def restore_backup(self):
        """Przywraca kopię zapasową."""
        if not self.selected_backup_file:
            return

        filename = self.selected_backup_file
        
        msg = (
            "UWAGA! Ta operacja jest NIEODWRACALNA.\n\n"
            f"Czy na pewno chcesz przywrócić kopię '{filename}'?\n\n"
            "Spowoduje to:\n"
            "1. NADPISANIE plików JSON z danymi.\n"
            "2. CAŁKOWITE USUNIĘCIE obecnego folderu ze skanami."
        )

        if messagebox.askyesno("POTWIERDZENIE KRYTYCZNEJ OPERACJI", msg, icon="warning", parent=self):
            backup_zip_path = os.path.join(BACKUP_FOLDER, filename)
            temp_restore_path = os.path.join(BACKUP_FOLDER, "_temp_restore")

            self.selected_label.config(text="Przywracanie kopii, proszę czekać...")
            self.update_idletasks()

            success = False
            try:
                if os.path.exists(temp_restore_path):
                    shutil.rmtree(temp_restore_path)
                os.makedirs(temp_restore_path)
                
                with zipfile.ZipFile(backup_zip_path, "r") as zf:
                    zf.extractall(temp_restore_path)

                temp_json_owner = os.path.join(temp_restore_path, "owner_data_to_import.json")
                # Obsłuż stare i nowe archiwa
                temp_protokoly_old = os.path.join(temp_restore_path, "assets", "protokoly")
                temp_protokoly_new = os.path.join(temp_restore_path, "protokoly")

                if os.path.exists(temp_protokoly_new):
                    temp_protokoly = temp_protokoly_new
                elif os.path.exists(temp_protokoly_old):
                    temp_protokoly = temp_protokoly_old
                else:
                    raise FileNotFoundError("Archiwum ZIP nie zawiera folderu protokoly.")

                if not os.path.exists(temp_json_owner):
                    raise FileNotFoundError("Archiwum ZIP jest niekompletne - brak owner_data_to_import.json.")

                backup_folder = get_active_location_backup_folder()
                protokoly_path = os.path.join(backup_folder, "protokoly")
                if os.path.exists(protokoly_path):
                    shutil.rmtree(protokoly_path)

                shutil.move(temp_protokoly, protokoly_path)
                shutil.move(temp_json_owner, JSON_FILE_PATH)

                temp_json_demo = os.path.join(temp_restore_path, "demografia.json")
                if os.path.exists(temp_json_demo):
                    shutil.move(temp_json_demo, DEMOGRAFIA_JSON_PATH)
                    print("Przywrócono dane demograficzne.")

                messagebox.showinfo("Sukces", "Kopia zapasowa została przywrócona.\nDane w edytorze zostaną przeładowane.", parent=self)
                self.parent.load_from_json()
                success = True
                self.destroy()
                
            except Exception as e:
                messagebox.showerror("Błąd przywracania", f"Wystąpił krytyczny błąd: {e}", parent=self)
            finally:
                if os.path.exists(temp_restore_path):
                    shutil.rmtree(temp_restore_path)
                if not success:
                    self.populate_backup_list()

    def delete_backup(self):
        """Usuwa wybraną kopię zapasową."""
        if not self.selected_backup_file:
            return

        filename = self.selected_backup_file
        
        if messagebox.askyesno("Potwierdzenie usunięcia", f"Czy na pewno chcesz trwale usunąć plik kopii zapasowej:\n\n{filename}?", parent=self):
            backup_path = os.path.join(BACKUP_FOLDER, filename)
            try:
                os.remove(backup_path)
                self.populate_backup_list()
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie udało się usunąć pliku: {e}", parent=self)

# ==========================================================================
# PUNKT WEJŚCIA APLIKACJI
# ==========================================================================

if __name__ == "__main__":
    """Uruchomienie aplikacji."""
    app = OwnerEditorApp()
    app.mainloop()