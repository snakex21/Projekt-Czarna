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

# --- KONFIGURACJA DPI DLA WINDOWS ---

# Ustawienie świadomości DPI dla systemów Windows, aby interfejs był ostry
# na monitorach o wysokiej rozdzielczości (4K, wysokie DPI).
if platform.system() == "Windows":
    try:  # Windows ≥ 8.1
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE_V2
    except AttributeError:  # Windows 7
        ctypes.windll.user32.SetProcessDPIAware()

# --- KONFIGURACJA ŚCIEŻEK I PLIKÓW ---

# Określenie katalogu, w którym znajduje się ten skrypt.
# Używane jako punkt odniesienia dla wszystkich względnych ścieżek.
script_dir = os.path.dirname(os.path.abspath(__file__))

# Ścieżka do folderu z kopiami zapasowymi danych.
BACKUP_FOLDER = os.path.join(script_dir, "..", "backup")

# Ścieżka do głównego pliku JSON z danymi właścicieli.
JSON_FILE_PATH = os.path.join(BACKUP_FOLDER, "owner_data_to_import.json")

# Ścieżka do pliku JSON z danymi demograficznymi.
DEMOGRAFIA_JSON_PATH = os.path.join(BACKUP_FOLDER, "demografia.json")

# Ścieżka do pliku JavaScript zawierającego oryginalne dane (do importu jednorazowego).
JS_FILE_PATH = os.path.join(script_dir, "..", "wlasciciele", "owner.js")

# Ścieżka do katalogu backend z skryptami migracji.
BACKEND_DIR = os.path.join(script_dir, "..", "backend")

# Ścieżka do skryptu Python odpowiedzialnego za migrację danych do bazy.
MIGRATE_SCRIPT = os.path.join(BACKEND_DIR, "migrate_data.py")

# --- STAŁE STYLIZACJI INTERFEJSU ---

# Definicje kolorów dla przycisków
BUTTON_COLORS = {
    'primary': '#0d6efd',    # Niebieski
    'success': '#198754',    # Zielony 
    'danger': '#dc3545',     # Czerwony
    'warning': '#ffc107',    # Żółty
    'info': '#0dcaf0',       # Jasnoniebieski
    'secondary': '#6c757d',  # Szary
}

# --- GŁÓWNA KLASA APLIKACJI ---

class OwnerEditorApp(tk.Tk):
    """
    Główna aplikacja edytora danych właścicieli.
    Zapewnia interfejs graficzny do zarządzania danymi protokołów,
    skanami dokumentów oraz danymi demograficznymi.
    """
    
    def __init__(self):
        """Inicjalizacja głównego okna aplikacji i wszystkich komponentów."""
        super().__init__()

        # --- KONFIGURACJA SKALOWANIA DPI I CZCIONEK ---
        
        # Obliczenie skali DPI dla bieżącego monitora.
        # 96 DPI to standardowa wartość (100% skali w Windows).
        dpi = self.winfo_fpixels("1i")
        scale = dpi / 96
        
        # Ustawienie skalowania Tkinter zgodnie z DPI monitora.
        self.tk.call("tk", "scaling", scale)

        # Obliczenie bazowego rozmiaru czcionki proporcjonalnie do skali DPI.
        base_size = int(11 * scale)  # 11pt przy 100% skali

        # Konfiguracja domyślnej czcionki systemowej dla całej aplikacji.
        def_font = tkfont.nametofont("TkDefaultFont")
        def_font.configure(family="Segoe UI", size=base_size)
        
        # Aktualizacja wszystkich predefiniowanych czcionek Tkinter.
        for name in (
            "TkTextFont",
            "TkFixedFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
        ):
            try:
                tkfont.nametofont(name).configure(size=base_size)
            except tk.TclError:
                pass

        # --- KONFIGURACJA STYLÓW TTK ---
        
        # Inicjalizacja menedżera stylów dla widgetów TTK.
        self.style = ttk.Style(self)
        self.style.theme_use("clam")  # Używamy motywu 'clam' dla lepszej kontroli nad wyglądem

        # Konfiguracja wysokości wierszy w Treeview proporcjonalnie do DPI.
        row_h = int(base_size * 3.0)  # Wyższy wiersz zapobiega ucięciu liter "g/y"
        self.style.configure(
            "Treeview", 
            rowheight=row_h, 
            padding=(0, 2)  # Dodatkowy padding góra/dół
        )
        self.style.configure(
            "Treeview.Heading", 
            font=("Segoe UI", base_size + 1, "bold")
        )
        
        # Definicje stylów dla przycisków akcji z kolorami.
        self.style.configure("Primary.TButton", foreground="white", background=BUTTON_COLORS['primary'])
        self.style.configure("Success.TButton", foreground="white", background=BUTTON_COLORS['success'])
        self.style.configure("Danger.TButton", foreground="white", background=BUTTON_COLORS['danger'])
        self.style.configure("Warning.TButton", foreground="black", background=BUTTON_COLORS['warning'])
        self.style.configure("Info.TButton", foreground="white", background=BUTTON_COLORS['info'])
        
        # Konfiguracja efektów hover dla przycisków
        self.style.map("Primary.TButton",
            background=[('active', '#0b5ed7'), ('pressed', '#0a58ca')])
        self.style.map("Success.TButton",
            background=[('active', '#157347'), ('pressed', '#146c43')])
        self.style.map("Danger.TButton",
            background=[('active', '#bb2d3b'), ('pressed', '#b02a37')])

        # --- GEOMETRIA I POZYCJONOWANIE OKNA ---
        
        # Pobranie wymiarów ekranu.
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        
        # Ustawienie okna na 90% szerokości i wysokości ekranu.
        w, h = int(sw * 0.90), int(sh * 0.90)
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
        self.minsize(800, 600)  # Minimalne wymiary okna

        # Automatyczna maksymalizacja okna na systemie Windows.
        if platform.system() == "Windows":
            self.state("zoomed")

        # --- OPÓŹNIONA MAKSYMALIZACJA I FOKUS ---
        
        # Funkcja wywoływana po uruchomieniu pętli zdarzeń.
        def _maximize_and_focus():
            """Maksymalizuje okno i ustawia fokus na polu wyszukiwania."""
            self.state("zoomed")  # Pełny ekran
            self.focus_force()  # Aktywacja okna
            self.search_entry.focus_force()  # Kursor w polu wyszukiwania

        # Zaplanowanie wykonania po 0ms (gdy pętla zdarzeń się uruchomi).
        self.after(0, _maximize_and_focus)

        self.title("📋 Edytor Danych Właścicieli - System Zarządzania Protokołami")

        # --- INICJALIZACJA INTERFEJSU I DANYCH ---
        
        # Utworzenie wszystkich widgetów interfejsu.
        self.create_widgets()
        
        # Globalne skróty klawiszowe.
        self.bind_all(
            "<Control-f>", lambda e: self.after_idle(self.search_entry.focus_force)
        )
        
        # Automatyczne dopasowanie szerokości kolumn przy zmianie rozmiaru okna.
        self.bind("<Configure>", self._auto_resize_columns)
        
        # Upewnienie się, że folder backup istnieje.
        self.ensure_backup_folder_exists()
        
        # Wczytanie danych z pliku JSON.
        self.load_from_json()
        
        # Sprawdzenie integralności folderów ze skanami (po 100ms).
        self.after(100, self.check_for_unlinked_folders)

        # Nasłuchiwanie zmian w polu wyszukiwania.
        self.search_var.trace_add("write", self._filter_owners)
        
        # Aktualizacja układu i ustawienie początkowego fokusu.
        self.update_idletasks()
        self.search_entry.focus_set()

    # --- METODY SPRAWDZANIA INTEGRALNOŚCI DANYCH ---

    def check_for_unlinked_folders(self):
        """
        Sprawdza folder z protokołami i szuka folderów osieroconych
        (które nie mają odpowiednika w danych JSON).
        Oferuje użytkownikowi możliwość ich usunięcia.
        """
        print("Sprawdzanie integralności folderów ze skanami...")
        
        # Ścieżka do głównego folderu ze skanami protokołów.
        protokoly_path = os.path.join(script_dir, "..", "assets", "protokoly")
        if not os.path.exists(protokoly_path):
            return

        try:
            # Pobranie listy wszystkich folderów w katalogu protokołów.
            all_folders = {
                f
                for f in os.listdir(protokoly_path)
                if os.path.isdir(os.path.join(protokoly_path, f))
            }

            # Pobranie zbioru wszystkich kluczy z załadowanych danych.
            all_keys = set(self.data.keys())

            # Identyfikacja folderów bez odpowiednika w danych.
            unlinked_folders = all_folders - all_keys

            if unlinked_folders:
                # Przygotowanie komunikatu dla użytkownika.
                message = (
                    f"Znaleziono {len(unlinked_folders)} folder(ów) w 'assets/protokoly', "
                    "które nie są powiązane z żadnym właścicielem w pliku JSON:\n\n"
                    f"- {', '.join(unlinked_folders)}\n\n"
                    "Czy chcesz je usunąć? Może to być przydatne do posprzątania po starych lub "
                    "błędnych wpisach."
                )

                # Dialog z pytaniem o usunięcie.
                if messagebox.askyesno("Wykryto niepowiązane foldery", message):
                    deleted_count = 0
                    errors = []
                    
                    # Próba usunięcia każdego osieroconego folderu.
                    for folder_name in unlinked_folders:
                        try:
                            shutil.rmtree(os.path.join(protokoly_path, folder_name))
                            print(f"Usunięto osierocony folder: {folder_name}")
                            deleted_count += 1
                        except Exception as e:
                            errors.append(f"- {folder_name}: {e}")

                    # Podsumowanie operacji czyszczenia.
                    summary = (
                        f"Usunięto {deleted_count} z {len(unlinked_folders)} folderów."
                    )
                    if errors:
                        summary += (
                            "\n\nWystąpiły błędy podczas usuwania:\n"
                            + "\n".join(errors)
                        )
                        messagebox.showerror("Błędy podczas czyszczenia", summary)
                    else:
                        messagebox.showinfo("Czyszczenie zakończone", summary)
            else:
                print("Wszystkie foldery są poprawnie powiązane.")
                
        except Exception as e:
            messagebox.showwarning(
                "Błąd", f"Wystąpił błąd podczas sprawdzania folderów: {e}"
            )

    # --- METODY TWORZENIA INTERFEJSU ---

    def create_widgets(self):
        """
        Tworzy i rozmieszcza wszystkie widgety interfejsu użytkownika.
        Struktura:
        - Pasek narzędzi (toolbar) z przyciskami akcji
        - Pole wyszukiwania
        - Tabela (Treeview) z listą właścicieli
        """
        
        # Główna ramka z paddingiem.
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Konfiguracja rozciągania głównego okna.
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Konfiguracja rozciągania zawartości głównej ramki.
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # --- PASEK NARZĘDZI Z UPIĘKSZONYMI PRZYCISKAMI ---
        
        toolbar = ttk.Frame(main_frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Utworzenie poszczególnych ramek dla grup przycisków
        data_frame = ttk.LabelFrame(toolbar, text="📁 Dane", padding="5")
        data_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        # Przycisk wczytywania danych z JSON z ikoną.
        load_btn = ttk.Button(
            data_frame, 
            text="📂 Wczytaj dane", 
            command=self.load_from_json,
            style="Primary.TButton"
        )
        load_btn.pack(side=tk.LEFT, padx=2)

        # Przycisk zarządzania kopiami zapasowymi z ikoną.
        backup_btn = ttk.Button(
            data_frame, 
            text="💾 Kopie zapasowe", 
            command=self.open_backup_manager
        )
        backup_btn.pack(side=tk.LEFT, padx=2)
        
        # Przycisk zapisu zmian z ikoną i stylem.
        save_btn = ttk.Button(
            data_frame,
            text="✅ ZAPISZ ZMIANY",
            command=self.save_to_json,
            style="Success.TButton",
        )
        save_btn.pack(side=tk.LEFT, padx=2)
        
        # Grupa przycisków migracji
        migration_frame = ttk.LabelFrame(toolbar, text="🔄 Migracja", padding="5")
        migration_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        # Przycisk migracji danych z ikoną.
        migrate_btn = ttk.Button(
            migration_frame, 
            text="⚡ MIGRUJ DANE", 
            command=self.run_migration,
            style="Info.TButton"
        )
        migrate_btn.pack(side=tk.LEFT, padx=2)
        
        # Przycisk zapisz + migruj z ikoną.
        save_migrate_btn = ttk.Button(
            migration_frame,
            text="💫 ZAPISZ + MIGRUJ",
            command=self.save_and_migrate,
            style="Success.TButton",
        )
        save_migrate_btn.pack(side=tk.LEFT, padx=2)
        
        # Grupa dodatkowych narzędzi
        tools_frame = ttk.LabelFrame(toolbar, text="🛠️ Narzędzia", padding="5")
        tools_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        # Przycisk edytora demografii z ikoną.
        demo_btn = ttk.Button(
            tools_frame, 
            text="📊 Demografia", 
            command=self.open_demografia_editor
        )
        demo_btn.pack(side=tk.LEFT, padx=2)
        
        # --- SEKCJA WYSZUKIWANIA I ZARZĄDZANIA ---
        
        # Ramka wyszukiwania po prawej
        search_frame = ttk.LabelFrame(toolbar, text="🔍 Wyszukiwanie", padding="5")
        search_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Pole wyszukiwania z placeholderem.
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=2)
        self.search_entry.bind(
            "<Return>", lambda e: self._filter_owners()
        )  # Filtruj po Enter

        # Grupa przycisków zarządzania właścicielami
        manage_frame = ttk.LabelFrame(toolbar, text="👥 Zarządzaj", padding="5")
        manage_frame.pack(side=tk.RIGHT, padx=(10, 10))
        
        # Przycisk dodawania właściciela z ikoną.
        add_btn = ttk.Button(
            manage_frame, 
            text="➕ Dodaj właściciela", 
            command=self.add_new_owner,
            style="Success.TButton"
        )
        add_btn.pack(side=tk.LEFT, padx=2)
        
        # Przycisk usuwania z ikoną ostrzeżenia.
        delete_btn = ttk.Button(
            manage_frame,
            text="🗑️ Usuń zaznaczonych",
            command=self.delete_selected_owner,
            style="Danger.TButton",
        )
        delete_btn.pack(side=tk.LEFT, padx=2)

        # --- TABELA Z LISTĄ WŁAŚCICIELI ---
        
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Konfiguracja kolumn tabeli.
        self.tree = ttk.Treeview(
            tree_frame, columns=("lp", "name", "plots_count"), show="headings"
        )
        self.tree.heading("lp", text="Lp.")
        self.tree.heading("name", text="Imię i Nazwisko")
        self.tree.heading("plots_count", text="Liczba działek")
        
        # Szerokości kolumn.
        self.tree.column("lp", width=60, anchor="center", stretch=tk.NO)
        self.tree.column("name", width=300, stretch=tk.YES)
        self.tree.column("plots_count", width=150, anchor="center", stretch=tk.NO)
        
        # Paski przewijania.
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Rozmieszczenie tabeli i pasków.
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        # Bindowanie zdarzeń.
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Delete>", self.on_delete_key)

    # --- METODY POMOCNICZE ---

    def ensure_backup_folder_exists(self):
        """Upewnia się, że folder backup istnieje. Tworzy go, jeśli nie istnieje."""
        if not os.path.exists(BACKUP_FOLDER):
            os.makedirs(BACKUP_FOLDER)

    # --- METODY OTWIERANIA OKIEN DIALOGOWYCH ---

    def open_demografia_editor(self):
        """Otwiera okno edytora danych demograficznych."""
        demografia_editor = DemografiaEditorWindow(self)
        self.wait_window(
            demografia_editor
        )  # Czekaj, aż okno demografii zostanie zamknięte
        self.search_entry.focus_set()  # Przywróć fokus do pola wyszukiwania

    def open_backup_manager(self):
        """Otwiera okno menedżera kopii zapasowych."""
        backup_manager = BackupManagerWindow(self)
        self.wait_window(backup_manager)
        self.search_entry.focus_set()

    # --- METODY ZARZĄDZANIA DANYMI WŁAŚCICIELI ---

    def delete_selected_owner(self):
        """
        Usuwa zaznaczonego właściciela (lub wielu) z danych.
        Opcjonalnie usuwa również powiązany folder ze skanami.
        """
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning(
                "Brak zaznaczenia",
                "Najpierw zaznacz właściciela (lub kilku) na liście.",
            )
            return

        # Iteracja przez zaznaczone elementy.
        for item_key in list(selected_items):
            owner_name = self.data[item_key].get("ownerName", "tego właściciela")

            # Potwierdzenie usunięcia.
            if messagebox.askyesno(
                "Potwierdzenie usunięcia",
                f"Czy na pewno chcesz usunąć wpis dla: {owner_name}?",
            ):
                # Sprawdzenie istnienia folderu ze skanami.
                folder_to_delete = os.path.join(
                    script_dir, "..", "assets", "protokoly", item_key
                )
                should_delete_folder = False
                
                if os.path.exists(folder_to_delete):
                    if messagebox.askyesno(
                        "Usuwanie Folderu",
                        f"Znaleziono folder '{item_key}' ze skanami. Czy chcesz go również usunąć?",
                    ):
                        should_delete_folder = True

                try:
                    # Usunięcie danych z pamięci.
                    del self.data[item_key]

                    # Opcjonalne usunięcie folderu.
                    if should_delete_folder:
                        shutil.rmtree(folder_to_delete)
                        print(f"Usunięto folder: {folder_to_delete}")

                except Exception as e:
                    messagebox.showerror("Błąd", f"Wystąpił błąd podczas usuwania: {e}")

        self.refresh_treeview()

    def refresh_treeview(self):
        """
        Odświeża zawartość tabeli z listą właścicieli.
        Dodatkowo wykonuje mechanizm "samonaprawy" - tworzy brakujące foldery dla skanów.
        """
        # Czyszczenie obecnej zawartości tabeli.
        for item in self.tree.get_children():
            self.tree.delete(item)

        # --- MECHANIZM SAMONAPRAWY FOLDERÓW ---
        
        protokoly_path = os.path.join(script_dir, "..", "assets", "protokoly")
        if not os.path.exists(protokoly_path):
            os.makedirs(protokoly_path)

        # Utworzenie brakujących folderów dla każdego klucza w danych.
        for key in self.data.keys():
            owner_folder = os.path.join(protokoly_path, key)
            if not os.path.exists(owner_folder):
                try:
                    os.makedirs(owner_folder)
                    print(f"Naprawiono: Utworzono brakujący folder '{key}'")
                except Exception as e:
                    print(f"Błąd przy tworzeniu folderu dla '{key}': {e}")

        # --- SORTOWANIE I WYPEŁNIANIE TABELI ---
        
        try:
            # Sortowanie kluczy według numeru porządkowego (Lp.).
            sorted_keys = sorted(
                self.data.keys(),
                key=lambda k: int(self.data[k].get("orderNumber", "99999")),
            )
        except (ValueError, TypeError):
            # Fallback: sortowanie alfabetyczne.
            sorted_keys = sorted(self.data.keys())

        # Dodawanie wpisów do tabeli.
        for key in sorted_keys:
            owner = self.data[key]
            # Obliczenie łącznej liczby działek.
            plot_count = len(owner.get("buildingPlots", [])) + len(
                owner.get("agriculturalPlots", [])
            )
            self.tree.insert(
                "",
                tk.END,
                iid=key,
                values=(
                    owner.get("orderNumber", "N/A"),
                    owner.get("ownerName", "Brak nazwy"),
                    plot_count,
                ),
            )

    def _filter_owners(self, *args):
        """
        Filtruje listę właścicieli na podstawie tekstu w polu wyszukiwania.
        Przeszukuje zarówno nazwę właściciela, jak i unikalny klucz.
        """
        search_term = self.search_var.get().lower()
        
        # Czyszczenie tabeli.
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Sortowanie kluczy.
        sorted_keys = sorted(
            self.data.keys(),
            key=lambda k: int(self.data[k].get("orderNumber", "99999")),
        )
        
        # Filtrowanie i dodawanie pasujących wpisów.
        for key in sorted_keys:
            owner = self.data[key]
            owner_name = owner.get("ownerName", "Brak nazwy").lower()
            unique_key = key.lower()

            # Sprawdzenie, czy fraza wyszukiwania występuje w nazwie lub kluczu.
            if search_term in owner_name or search_term in unique_key:
                plot_count = len(owner.get("buildingPlots", [])) + len(
                    owner.get("agriculturalPlots", [])
                )
                self.tree.insert(
                    "",
                    tk.END,
                    iid=key,
                    values=(
                        owner.get("orderNumber", "N/A"),
                        owner.get("ownerName", "Brak nazwy"),
                        plot_count,
                    ),
                )

    def _auto_resize_columns(self, event):
        """
        Automatycznie dostosowuje szerokość kolumn tabeli
        przy zmianie rozmiaru okna.
        """
        # Całkowita szerokość dostępna (minus pasek przewijania).
        total = event.width - 20
        lp_w = 60  # Stała szerokość kolumny Lp.
        count_w = 150  # Stała szerokość kolumny liczby działek
        # Reszta przestrzeni dla kolumny z nazwą.
        name_w = max(total - lp_w - count_w, 150)
        self.tree.column("name", width=name_w)

    # --- METODY IMPORTU I EKSPORTU DANYCH ---

    def load_from_json(self):
        """
        Wczytuje dane właścicieli z pliku JSON.
        Jest to standardowa metoda odczytu danych roboczych.
        """
        if not os.path.exists(JSON_FILE_PATH):
            messagebox.showinfo(
                "Informacja", "Nie znaleziono pliku JSON. Zaimportuj dane z 'owner.js'."
            )
            return
            
        try:
            with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            messagebox.showinfo("✅ Sukces", f"Wczytano {len(self.data)} właścicieli.")
            self.refresh_treeview()
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Nie udało się wczytać pliku JSON: {e}")

    def save_to_json(self):
        """Zapisuje bieżące dane do pliku JSON."""
        try:
            with open(JSON_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("✅ Sukces", f"Zmiany zapisano w:\n{JSON_FILE_PATH}")
        except Exception as e:
            messagebox.showerror("❌ Błąd zapisu", f"Nie udało się zapisać pliku: {e}")

    # --- METODY MIGRACJI DANYCH DO BAZY ---

    def run_migration(self) -> bool:
        """
        Uruchamia skrypt migrate_data.py, który migruje dane do bazy PostgreSQL.
        Metoda konfiguruje środowisko z prawidłowym kodowaniem UTF-8 dla Windows,
        uruchamia skrypt migracji w osobnym procesie i przetwarza jego wyjście.
        
        Returns:
            bool: True jeśli migracja zakończyła się sukcesem, False w przeciwnym razie.
            
        Proces migracji:
        1. Konfiguracja środowiska z wymuszeniem UTF-8
        2. Uruchomienie skryptu migrate_data.py
        3. Przechwycenie i analiza wyjścia
        4. Wyświetlenie szczegółów w oknie dialogowym
        """
        try:
            # --- KONFIGURACJA ŚRODOWISKA ---
            
            # Przygotowanie środowiska z wymuszeniem kodowania UTF-8.
            # Jest to krytyczne dla poprawnej obsługi polskich znaków na Windows.
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # --- URUCHOMIENIE SKRYPTU MIGRACJI ---
            
            # Uruchomienie skryptu Python w osobnym procesie z odpowiednim kodowaniem.
            result = subprocess.run(
                [sys.executable, MIGRATE_SCRIPT],  # Użycie interpretera Python z sys.executable
                cwd=BACKEND_DIR,                   # Katalog roboczy to backend/
                capture_output=True,                # Przechwytywanie stdout i stderr
                text=True,                          # Traktowanie wyjścia jako tekst (nie bajty)
                encoding='utf-8',                   # Wymuszenie kodowania UTF-8
                errors='replace',                   # Zastąpienie nieprawidłowych znaków
                env=env                             # Przekazanie skonfigurowanego środowiska
            )
            
            # --- ANALIZA WYNIKU MIGRACJI ---
            
            # Sprawdzenie kodu wyjścia procesu (0 = sukces).
            if result.returncode == 0:
                # Migracja zakończona sukcesem.
                success_msg = "Migracja danych zakończyła się pomyślnie."
                
                if result.stdout:
                    # Jeśli są dane wyjściowe, pokaż szczegółowe okno.
                    self.show_migration_details(success_msg, result.stdout, is_error=False)
                else:
                    # Brak szczegółów - prosty komunikat.
                    messagebox.showinfo("✅ Migracja zakończona", success_msg)
                return True
            else:
                # Migracja zakończona błędem.
                error_msg = f"Skrypt migracji zwrócił kod błędu: {result.returncode}"
                
                if result.stderr:
                    # Analiza typu błędu i dostosowanie komunikatu.
                    if 'UnicodeEncodeError' in result.stderr:
                        # Specjalna obsługa błędów kodowania.
                        clean_error = "Wystąpił problem z kodowaniem znaków. Sprawdź logi migracji."
                        self.show_migration_details(error_msg, clean_error, is_error=True)
                    else:
                        # Wyświetlenie pełnego komunikatu błędu.
                        self.show_migration_details(error_msg, result.stderr, is_error=True)
                else:
                    # Brak szczegółów błędu.
                    messagebox.showerror("❌ Błąd migracji", error_msg)
                return False
                
        except FileNotFoundError:
            # Nie znaleziono skryptu migracji.
            messagebox.showerror(
                "❌ Nie znaleziono skryptu", 
                f"Sprawdź ścieżkę:\n{MIGRATE_SCRIPT}"
            )
            return False
        except Exception as e:
            # Nieoczekiwany błąd podczas uruchamiania migracji.
            messagebox.showerror("❌ Błąd migracji", str(e))
            return False

    def show_migration_details(self, title, details, is_error=False):
        """
        Wyświetla szczegóły migracji w osobnym oknie z możliwością przewijania.
        Okno zawiera sformatowany tekst z emoji zamiast znaczników tekstowych
        oraz przyciski do kopiowania i zapisu logów.
        
        Args:
            title: Tytuł komunikatu wyświetlany u góry okna
            details: Szczegółowe informacje do wyświetlenia (output skryptu)
            is_error: Czy to komunikat błędu (True) czy sukcesu (False)
            
        Funkcjonalności okna:
        - Formatowanie tekstu z kolorowaniem i emoji
        - Przycisk kopiowania do schowka
        - Przycisk zapisu do pliku
        - Przewijanie długich logów
        """
        # --- UTWORZENIE OKNA DIALOGOWEGO ---
        
        # Utworzenie nowego okna potomnego.
        detail_window = tk.Toplevel(self)
        detail_window.title("📋 Szczegóły migracji")
        detail_window.transient(self)
        detail_window.grab_set()
        
        # --- POZYCJONOWANIE I ROZMIAR OKNA ---
        
        # Ustawienie rozmiaru okna na podstawie rozmiaru ekranu.
        sw, sh = detail_window.winfo_screenwidth(), detail_window.winfo_screenheight()
        w, h = 700, 500
        detail_window.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        detail_window.minsize(600, 400)
        
        # --- GŁÓWNA RAMKA INTERFEJSU ---
        
        main_frame = ttk.Frame(detail_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Etykieta z tytułem komunikatu.
        title_label = ttk.Label(
            main_frame, 
            text=title, 
            font=("Segoe UI", 11, "bold")
        )
        title_label.pack(anchor="w", pady=(0, 10))
        
        # --- POLE TEKSTOWE Z LOGAMI ---
        
        # Ramka dla pola tekstowego.
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # Pole tekstowe z przewijaniem dla szczegółów.
        text_widget = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            width=80,
            height=20,
            font=("Consolas", 10)  # Czcionka o stałej szerokości dla logów
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # --- FORMATOWANIE TEKSTU ---
        
        # Zamiana znaczników tekstowych na emoji dla lepszej czytelności.
        formatted_details = details
        formatted_details = formatted_details.replace('[OK]', '✔️')
        formatted_details = formatted_details.replace('[SUKCES]', '✅')
        formatted_details = formatted_details.replace('[BŁĄD KRYTYCZNY]', '❌')
        formatted_details = formatted_details.replace('[BŁĄD]', '❌')
        formatted_details = formatted_details.replace('[INFO]', 'ℹ️')
        formatted_details = formatted_details.replace('[OSTRZEŻENIE]', '⚠️')
        
        # Dodatkowe formatowanie separatorów.
        formatted_details = formatted_details.replace('========================================', '═' * 45)
        formatted_details = formatted_details.replace('=============================================', '═' * 45)
        
        # Wstawienie sformatowanego tekstu.
        text_widget.insert("1.0", formatted_details)
        
        # --- KONFIGURACJA KOLOROWANIA TEKSTU ---
        
        # Definicja tagów do kolorowania różnych typów komunikatów.
        text_widget.tag_configure("header", font=("Consolas", 10, "bold"), foreground="#1e88e5")
        text_widget.tag_configure("success", foreground="#2e7d32")
        text_widget.tag_configure("error", foreground="#c62828")
        text_widget.tag_configure("warning", foreground="#f57c00")
        text_widget.tag_configure("step", font=("Consolas", 10, "bold"), foreground="#5e35b1")
        text_widget.tag_configure("separator", foreground="#757575")
        
        # --- AUTOMATYCZNE KOLOROWANIE LINII ---
        
        # Parsowanie i kolorowanie każdej linii na podstawie zawartości.
        lines = formatted_details.split('\n')
        current_pos = "1.0"
        
        for i, line in enumerate(lines):
            line_start = f"{i+1}.0"
            line_end = f"{i+1}.end"
            
            # Zastosowanie odpowiedniego tagu na podstawie treści linii.
            if '═══' in line or '───' in line:
                text_widget.tag_add("separator", line_start, line_end)
            elif 'SKRYPT MIGRACJI DANYCH' in line:
                text_widget.tag_add("header", line_start, line_end)
            elif line.startswith('--- Krok'):
                text_widget.tag_add("step", line_start, line_end)
            elif '✔️' in line:
                text_widget.tag_add("success", line_start, line_end)
            elif '✅' in line or 'SUKCES' in line:
                text_widget.tag_add("success", line_start, line_end)
            elif '❌' in line or 'BŁĄD' in line:
                text_widget.tag_add("error", line_start, line_end)
            elif '⚠️' in line or 'OSTRZEŻENIE' in line:
                text_widget.tag_add("warning", line_start, line_end)
            elif '    ->' in line:  # Podkroki
                text_widget.tag_add("step", line_start, line_end)
        
        # Ustawienie pola jako tylko do odczytu.
        text_widget.config(state=tk.DISABLED)
        
        # --- RAMKA Z PRZYCISKAMI AKCJI ---
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Przycisk zamknięcia (kolor zależy od typu komunikatu).
        close_btn = ttk.Button(
            btn_frame,
            text="Zamknij",
            command=detail_window.destroy,
            style="Success.TButton" if not is_error else "Danger.TButton"
        )
        close_btn.pack(side=tk.RIGHT)
        
        # --- PRZYCISK KOPIOWANIA DO SCHOWKA ---
        
        def copy_to_clipboard():
            """Kopiuje zawartość logów do schowka systemowego."""
            self.clipboard_clear()
            self.clipboard_append(formatted_details)
            messagebox.showinfo("✅ Skopiowano", "Treść została skopiowana do schowka.", parent=detail_window)
        
        copy_btn = ttk.Button(
            btn_frame,
            text="📋 Kopiuj do schowka",
            command=copy_to_clipboard
        )
        copy_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        # --- PRZYCISK ZAPISU DO PLIKU ---
        
        def save_to_file():
            """Zapisuje logi do pliku tekstowego."""
            from datetime import datetime
            
            # Generowanie domyślnej nazwy pliku z datą i czasem.
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                parent=detail_window,
                defaultextension=".txt",
                initialfile=f"migracja_log_{timestamp}.txt",
                filetypes=[("Pliki tekstowe", "*.txt"), ("Wszystkie pliki", "*.*")]
            )
            if filename:
                try:
                    # Zapis do pliku z kodowaniem UTF-8.
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(formatted_details)
                    messagebox.showinfo("✅ Zapisano", f"Log został zapisany do:\n{filename}", parent=detail_window)
                except Exception as e:
                    messagebox.showerror("❌ Błąd", f"Nie udało się zapisać pliku:\n{e}", parent=detail_window)
        
        save_btn = ttk.Button(
            btn_frame,
            text="💾 Zapisz do pliku",
            command=save_to_file
        )
        save_btn.pack(side=tk.RIGHT, padx=(0, 5))

    def save_and_migrate(self):
        """
        Zapisuje dane do JSON, a następnie od razu uruchamia migrację.
        Metoda łączy dwie operacje w jedną akcję dla wygody użytkownika.
        """
        try:
            # --- ZAPIS DANYCH DO JSON ---
            
            # Najpierw zapisz dane do pliku.
            with open(JSON_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            print(f"Dane zapisane do: {JSON_FILE_PATH}")
            
            # --- URUCHOMIENIE MIGRACJI ---
            
            # Następnie uruchom migrację danych do bazy.
            success = self.run_migration()
            
            # Odświeżenie widoku jeśli migracja się powiodła.
            if success:
                self.refresh_treeview()
                
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Wystąpił błąd podczas zapisu i migracji:\n{e}")

    # --- METODY OBSŁUGI ZDARZEŃ ---

    def _open_edit_window(self, owner_dict, key=None):
        """
        Otwiera okno edycji dla wybranego właściciela.
        
        Args:
            owner_dict: Słownik z danymi właściciela
            key: Unikalny klucz właściciela (None dla nowego wpisu)
        """
        # Pobierz aktualnie posortowane i przefiltrowane klucze z widoku.
        sorted_keys_on_screen = self.tree.get_children()

        # Otwórz okno edycji.
        dlg = EditWindow(self, owner_dict, key, self.on_save, sorted_keys_on_screen)

        # Czekaj na zamknięcie okna.
        self.wait_window(dlg)
        self.search_entry.focus_force()

    def on_double_click(self, event):
        """Obsługuje podwójne kliknięcie na elemencie listy - otwiera okno edycji."""
        item_key = self.tree.focus()
        if item_key:
            self._open_edit_window(self.data[item_key], item_key)

    def on_delete_key(self, event):
        """Obsługuje naciśnięcie klawisza Delete - usuwa zaznaczonego właściciela."""
        self.delete_selected_owner()

    def add_new_owner(self):
        """Otwiera okno edycji dla nowego właściciela."""
        self._open_edit_window({}, None)

    def on_save(self, new_data, original_key):
        """
        Callback wywoływany po zapisie danych w oknie edycji.
        Waliduje dane i aktualizuje struktury danych.
        
        Args:
            new_data: Nowe dane właściciela
            original_key: Oryginalny klucz (może się zmienić)
            
        Returns:
            bool: True jeśli zapis się powiódł, False w przypadku błędu
        """
        # Pobranie i czyszczenie klucza.
        raw_key = new_data.get("unikalny_klucz", "").strip()

        # Sanityzacja klucza - usunięcie niedozwolonych znaków.
        safe_key = re.sub(r'[\\/*?:"<>|\s]+', "_", raw_key)
        safe_key = re.sub(r"__+", "_", safe_key)
        safe_key = safe_key.strip("_")

        if raw_key != safe_key:
            print(
                f"INFO: Klucz '{raw_key}' został automatycznie poprawiony na '{safe_key}'."
            )
            new_data["unikalny_klucz"] = safe_key

        new_key = safe_key

        # --- WALIDACJA DANYCH ---
        
        if not new_key:
            messagebox.showerror(
                "❌ Błąd Walidacji", "Pole 'Unikalny klucz' nie może być puste!"
            )
            return False

        # Sprawdzenie unikalności klucza.
        if new_key in self.data and new_key != original_key:
            messagebox.showerror(
                "❌ Błąd Walidacji",
                f"Unikalny klucz '{new_key}' jest już używany przez innego właściciela!",
            )
            return False

        # --- ZARZĄDZANIE FOLDERAMI SKANÓW ---
        
        protokoly_path = os.path.join(script_dir, "..", "assets", "protokoly")

        try:
            if original_key and original_key != new_key:
                # Zmiana nazwy folderu przy zmianie klucza.
                old_folder = os.path.join(protokoly_path, original_key)
                if os.path.exists(old_folder):
                    new_folder = os.path.join(protokoly_path, new_key)
                    os.rename(old_folder, new_folder)
            elif not original_key:
                # Utworzenie nowego folderu dla nowego właściciela.
                new_folder = os.path.join(protokoly_path, new_key)
                if not os.path.exists(new_folder):
                    os.makedirs(new_folder)
        except OSError as e:
            messagebox.showerror(
                "❌ Błąd Systemu Plików",
                f"Nie udało się zarządzać folderem protokołu:\n{e}",
            )
            return False

        # --- AKTUALIZACJA DANYCH ---
        
        # Usunięcie klucza ze słownika danych (jest używany jako klucz słownika).
        del new_data["unikalny_klucz"]
        
        # Zapisanie danych pod nowym kluczem.
        self.data[new_key] = new_data

        # Usunięcie starego klucza, jeśli się zmienił.
        if original_key and original_key != new_key:
            del self.data[original_key]

        # Odświeżenie widoku.
        self.refresh_treeview()
        self.search_entry.focus_set()
        return True

# --- KLASA OKNA EDYCJI WŁAŚCICIELA ---

class EditWindow(tk.Toplevel):
    """
    Okno dialogowe do edycji szczegółowych danych właściciela.
    Zawiera formularz z wszystkimi polami oraz zarządzanie skanami dokumentów.
    """
    
    def __init__(
        self, parent, owner_data, original_key, save_callback, sorted_keys=None
    ):
        """
        Inicjalizacja okna edycji.
        
        Args:
            parent: Okno rodzica (główna aplikacja)
            owner_data: Słownik z danymi właściciela
            original_key: Oryginalny klucz właściciela
            save_callback: Funkcja callback do zapisu danych
            sorted_keys: Lista posortowanych kluczy do nawigacji
        """
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title(f"Edycja Danych - {owner_data.get('ownerName', 'Nowy Wpis')}")

        # --- GEOMETRIA I POZYCJONOWANIE OKNA ---
        
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * 0.90), int(sh * 0.90)
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
        if platform.system() == "Windows":
            self.state("zoomed")
        self.minsize(800, 600)

        # Przechowywanie danych i stanu.
        self.owner_data = owner_data
        self.original_key = original_key
        self.save_callback = save_callback
        self.fields = {}  # Słownik przechowujący referencje do pól formularza
        self.scans_widgets = {}  # Słownik widgetów zarządzania skanami

        # Lista kluczy do nawigacji między wpisami.
        self.sorted_keys = sorted_keys or []

        # --- UTWORZENIE PRZEWIJALNEGO KONTENERA ---
        
        outer = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True)
        
        # Canvas umożliwia przewijanie zawartości.
        canvas = tk.Canvas(
            outer, highlightthickness=0, background=self.cget("background")
        )
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Główna ramka z formularzem.
        main = ttk.Frame(canvas, padding=15)
        win_id = canvas.create_window((0, 0), window=main, anchor="nw")
        
        # Konfiguracja automatycznego dopasowania rozmiaru.
        main.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind(
            "<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width)
        )

        self._bind_mousewheel_to_canvas(canvas, main)

        # --- BUDOWA FORMULARZA ---
        
        self._build_form(main)

        # Zapisanie początkowego stanu formularza (do wykrywania zmian).
        self.initial_form_data = self._get_current_form_data()

        # --- PRZYCISKI NAWIGACJI I ZAPISU ---
        
        EXTRA_BOTTOM_MARGIN = 60  # Margines dolny
        bottom_frame = ttk.Frame(main)
        bottom_frame.pack(fill=tk.X, pady=(20, EXTRA_BOTTOM_MARGIN))
        bottom_frame.columnconfigure((0, 1, 2), weight=1)

        # Przycisk "Poprzedni".
        self.prev_btn = ttk.Button(
            bottom_frame, text="<< Poprzedni", command=lambda: self._navigate(-1)
        )
        self.prev_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        # Przycisk "Zapisz".
        save_btn = ttk.Button(
            bottom_frame, text="Zapisz", command=self.save, style="Success.TButton"
        )
        save_btn.grid(row=0, column=1, sticky="ew", ipady=6)

        # Przycisk "Następny".
        self.next_btn = ttk.Button(
            bottom_frame, text="Następny >>", command=lambda: self._navigate(1)
        )
        self.next_btn.grid(row=0, column=2, sticky="ew", padx=(5, 0))

        # Aktualizacja stanu przycisków nawigacji.
        self._update_nav_buttons_state()
        
        # Bindowanie klawisza Escape do zamknięcia okna.
        self.bind("<Escape>", lambda e: self.destroy())

    # --- METODY POMOCNICZE POZYCJONOWANIA ---

    def _center_or_maximize(self, percent=0.9):
        """
        Centruje okno na ekranie lub maksymalizuje na Windows.
        
        Args:
            percent: Procent szerokości/wysokości ekranu do wykorzystania
        """
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * percent), int(sh * percent)
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
        self.minsize(800, 600)
        if platform.system() == "Windows":
            self.state("zoomed")

    def _bind_mousewheel_to_canvas(self, canvas, main_frame):
        """
        Binduje scroll myszką do canvas niezależnie od tego, gdzie jest kursor.
        Działa globalnie w całym oknie edycji.
        """
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

    # --- METODY NAWIGACJI MIĘDZY WPISAMI ---

    def _navigate(self, direction):
        """
        Przechodzi do poprzedniego lub następnego właściciela.
        Pyta o zapis niezapisanych zmian.
        
        Args:
            direction: -1 dla poprzedniego, 1 dla następnego
        """
        # Sprawdzenie, czy są niezapisane zmiany.
        current_data = self._get_current_form_data()
        if current_data != self.initial_form_data:
            answer = messagebox.askyesnocancel(
                "Nawigacja",
                "Wykryto niezapisane zmiany. Czy chcesz je zapisać przed przejściem dalej?",
                parent=self,
            )
            if answer is None:  # Anuluj
                return
            if answer is True:  # Tak - zapisz
                if not self.save(close_after=False):
                    return  # Przerwij, jeśli zapis się nie powiódł

        # Znalezienie nowego indeksu.
        try:
            current_index = self.sorted_keys.index(self.original_key)
        except ValueError:
            messagebox.showwarning(
                "Błąd nawigacji",
                "Nie można odnaleźć bieżącego wpisu na liście.",
                parent=self,
            )
            return

        new_index = current_index + direction
        next_key = self.sorted_keys[new_index]
        next_data = self.master.data[next_key]

        # Załadowanie nowych danych.
        self._load_data(next_data, next_key)

        # Zaktualizowanie migawki stanu.
        self.initial_form_data = self._get_current_form_data()

    def _load_data(self, owner_data, key):
        """
        Ładuje dane właściciela do formularza.
        
        Args:
            owner_data: Słownik z danymi właściciela
            key: Unikalny klucz właściciela
        """
        self.owner_data = owner_data
        self.original_key = key

        # Wypełnienie wszystkich pól formularza.
        for f_key, widget in self.fields.items():
            value = owner_data.get(f_key, "")
            if f_key == "unikalny_klucz":
                value = key

            # Różne typy pól wymagają różnego sposobu wypełniania.
            if isinstance(widget, tuple):  # Pole daty (3 osobne pola)
                day, month, year = "", "", ""
                if value:
                    match = re.match(
                        r"(\d+)\s+([a-zA-Zęóąśłżźćń]+)\s+(\d{4})", str(value).strip()
                    )
                    if match:
                        day, month, year = match.groups()
                widget[0].delete(0, tk.END)
                widget[0].insert(0, day)
                widget[1].delete(0, tk.END)
                widget[1].insert(0, month)
                widget[2].delete(0, tk.END)
                widget[2].insert(0, year)
            elif isinstance(widget, scrolledtext.ScrolledText):  # Pola tekstowe
                widget.delete("1.0", tk.END)
                # Specjalna obsługa dla list działek.
                if "Plots" in f_key and isinstance(value, list):
                    value = self.format_plots_for_display(value)
                widget.insert("1.0", str(value))
            else:  # Zwykłe pola Entry
                widget.delete(0, tk.END)
                widget.insert(0, str(value))

        # Aktualizacja tytułu okna.
        self.title(f"Edycja Danych - {owner_data.get('ownerName', key)}")
        
        # Odświeżenie sekcji skanów i przycisków.
        self._check_key_and_enable_scans()
        self._update_nav_buttons_state()

    def _update_nav_buttons_state(self):
        """Włącza/wyłącza przyciski nawigacji w zależności od pozycji na liście."""
        try:
            current_index = self.sorted_keys.index(self.original_key)
            self.prev_btn.config(state=tk.NORMAL if current_index > 0 else tk.DISABLED)
            self.next_btn.config(
                state=(
                    tk.NORMAL
                    if current_index < len(self.sorted_keys) - 1
                    else tk.DISABLED
                )
            )
        except (ValueError, AttributeError):
            # Nowy wpis - wyłącz oba przyciski.
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)

    # --- METODY BUDOWANIA FORMULARZA ---

    def _build_form(self, parent):
        """
        Tworzy wszystkie pola formularza w podanym kontenerze.
        
        Args:
            parent: Kontener dla pól formularza
        """
        
        # --- SEKCJA IDENTYFIKATORA ---
        
        key_frame = ttk.LabelFrame(parent, text="Identyfikator", padding=10)
        key_frame.pack(fill=tk.X, pady=5)
        self.create_field(
            key_frame, "unikalny_klucz", "Unikalny klucz:", self.original_key or ""
        )

        # --- SEKCJA DANYCH WŁAŚCICIELA ---
        
        details_frame = ttk.LabelFrame(parent, text="Dane Właściciela", padding=10)
        details_frame.pack(fill=tk.X, pady=5)
        
        self.create_field(
            details_frame, "orderNumber", "Lp:", self.owner_data.get("orderNumber", "")
        )
        self.create_field(
            details_frame,
            "ownerName",
            "Imię i Nazwisko:",
            self.owner_data.get("ownerName", ""),
        )
        self.create_date_field(
            details_frame,
            "protocolDate",
            "Data protokołu:",
            self.owner_data.get("protocolDate", ""),
        )
        self.create_field(
            details_frame,
            "houseNumber",
            "Numer domu:",
            self.owner_data.get("houseNumber", ""),
        )
        self.create_field(
            details_frame,
            "protocolLocation",
            "Miejsce protokołu:",
            self.owner_data.get("protocolLocation", ""),
        )

        # --- SEKCJA DZIAŁEK ---
        
        plots_frame = ttk.LabelFrame(
            parent, text="Działki (numery oddzielone przecinkami)", padding=10
        )
        plots_frame.pack(fill=tk.X, pady=5)
        
        self.create_textarea(
            plots_frame,
            "buildingPlots",
            "Działki budowlane (z protokołu):",
            self.format_plots_for_display(self.owner_data.get("buildingPlots", [])),
            height=2,
        )
        self.create_textarea(
            plots_frame,
            "agriculturalPlots",
            "Działki rolne (z protokołu):",
            self.format_plots_for_display(self.owner_data.get("agriculturalPlots", [])),
            height=2,
        )
        self.create_textarea(
            plots_frame,
            "realbuildingPlots",
            "Działki budowlane (rzeczywiste):",
            self.format_plots_for_display(self.owner_data.get("realbuildingPlots", [])),
            height=2,
        )
        self.create_textarea(
            plots_frame,
            "realagriculturalPlots",
            "Działki rolne (rzeczywiste):",
            self.format_plots_for_display(
                self.owner_data.get("realagriculturalPlots", [])
            ),
            height=2,
        )

        # --- SEKCJA DODATKOWYCH INFORMACJI ---
        
        notes_frame = ttk.LabelFrame(parent, text="Dodatkowe Informacje", padding=10)
        notes_frame.pack(fill=tk.X, pady=5)
        
        self.create_textarea(
            notes_frame,
            "genealogy",
            "Genealogia:",
            self.owner_data.get("genealogy", ""),
            height=4,
        )
        self.create_textarea(
            notes_frame,
            "ownershipHistory",
            "Historia posiadania działek:",
            self.owner_data.get("ownershipHistory", ""),
            height=4,
        )
        self.create_textarea(
            notes_frame,
            "remarks",
            "Ciąg dalszy/Uwagi:",
            self.owner_data.get("remarks", ""),
            height=4,
        )
        self.create_textarea(
            notes_frame,
            "wspolwlasnosc",
            "Współwłasność/Służebność:",
            self.owner_data.get("wspolwlasnosc", ""),
            height=4,
        )

        # --- POLE POWIĄZAŃ Z TOOLTIPEM ---
        
        relacje_frame = ttk.Frame(notes_frame)
        relacje_frame.pack(fill=tk.X, pady=4)
        relacje_frame.columnconfigure(0, weight=1)
        relacje_frame.rowconfigure(1, weight=1)

        # Etykieta z ikoną pomocy.
        label_icon_frame = ttk.Frame(relacje_frame)
        label_icon_frame.grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(label_icon_frame, text="Powiązania i transakcje").pack(
            side=tk.LEFT, anchor="w"
        )
        
        # Ikona pomocy "?".
        help_icon = ttk.Label(
            label_icon_frame, text="?", cursor="hand2", font=("Segoe UI", 10, "bold")
        )
        help_icon.pack(side=tk.LEFT, anchor="w", padx=5)
        help_icon.bind("<Button-1>", self.toggle_relacje_tooltip)

        self.tooltip_window = None
        
        # Pole tekstowe dla powiązań.
        relacje_content = self.owner_data.get(
            "powiazania_i_transakcje", self.owner_data.get("relacje_rodzinne", "")
        )
        txt_frame, self.fields["powiazania_i_transakcje"] = (
            self.create_textarea_in_frame(relacje_frame, relacje_content, height=4)
        )
        txt_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")

        # --- SEKCJA ANALIZY ---
        
        analysis_frame = ttk.LabelFrame(parent, text="Analiza", padding=10)
        analysis_frame.pack(fill=tk.X, pady=5)
        self.create_textarea(
            analysis_frame,
            "interpretacja_i_wnioski",
            "Interpretacja i wnioski:",
            self.owner_data.get("interpretacja_i_wnioski", ""),
            height=6,
        )

        # --- SEKCJA ZARZĄDZANIA SKANAMI ---
        
        scans_frame = ttk.LabelFrame(
            parent, text="Zarządzanie Skanami Protokółu", padding=10
        )
        scans_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Utworzenie interfejsu skanów.
        self.create_scans_section(scans_frame)

        # Dynamiczne włączanie/wyłączanie sekcji skanów.
        self._check_key_and_enable_scans()
        self.fields["unikalny_klucz"].bind(
            "<KeyRelease>", self._check_key_and_enable_scans
        )

    # --- METODY SPRAWDZANIA I AKTYWACJI SEKCJI SKANÓW ---

    def _check_key_and_enable_scans(self, event=None):
        """
        Sprawdza, czy unikalny klucz jest wpisany i na tej podstawie
        aktywuje lub deaktywuje sekcję zarządzania skanami.
        
        Args:
            event: Zdarzenie klawiatury (opcjonalne)
        """
        # Pobranie wartości klucza z pola formularza.
        key = self.fields["unikalny_klucz"].get().strip()
        is_enabled = bool(key)

        # Określenie nowego stanu widgetów.
        new_state = tk.NORMAL if is_enabled else tk.DISABLED

        # Aktualizacja stanu wszystkich widgetów zarządzania skanami.
        for widget in self.scans_widgets.values():
            if isinstance(widget, (ttk.Button, tk.Listbox)):
                widget.config(state=new_state)

        if is_enabled:
            # Jeśli sekcja jest aktywna, odśwież listę plików.
            self.populate_scans_list()
        else:
            # Jeśli sekcja jest nieaktywna, wyczyść listę.
            self.scans_widgets["listbox"].delete(0, tk.END)

    # --- METODY TWORZENIA PÓL FORMULARZA ---

    def create_textarea_in_frame(self, parent, initial_content, height):
        """
        Tworzy pole tekstowe ScrolledText w osobnej ramce.
        Używane dla pól wymagających specjalnego układu.
        
        Args:
            parent: Widget rodzica
            initial_content: Początkowa zawartość pola
            height: Wysokość pola w liniach
            
        Returns:
            tuple: (ramka, widget ScrolledText)
        """
        # Utworzenie ramki kontenerowej.
        txt_frame = ttk.Frame(parent)

        # Zwiększenie rozmiaru czcionki dla lepszej czytelności.
        bigger = tkfont.nametofont("TkTextFont").cget("size") + 2
        
        # Utworzenie pola tekstowego z przewijaniem.
        txt = scrolledtext.ScrolledText(
            txt_frame,
            height=height,
            wrap=tk.WORD,  # Zawijanie po słowach
            relief=tk.SOLID,
            borderwidth=1,
            font=("Segoe UI", bigger),
        )
        
        # Wstawienie początkowej zawartości z konwersją \n.
        txt.insert("1.0", initial_content.replace("\\n", "\n"))
        txt.pack(fill=tk.BOTH, expand=True)

        return txt_frame, txt

    def create_scans_section(self, parent):
        """
        Tworzy kompletny interfejs do zarządzania skanami dokumentów.
        Zawiera listę plików, przyciski do dodawania/usuwania
        oraz przyciski do zmiany kolejności.
        
        Args:
            parent: Widget rodzica dla sekcji skanów
        """
        # Konfiguracja układu grid dla rodzica.
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        # Główna ramka dla listy skanów.
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # --- PRZYCISKI ZMIANY KOLEJNOŚCI ---
        
        reorder_frame = ttk.Frame(list_frame)
        reorder_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # Przycisk przesunięcia w górę.
        up_btn = ttk.Button(reorder_frame, text="▲", command=self.move_scan_up, width=3)
        up_btn.pack(pady=2)
        
        # Przycisk przesunięcia w dół.
        down_btn = ttk.Button(
            reorder_frame, text="▼", command=self.move_scan_down, width=3
        )
        down_btn.pack(pady=2)
        
        # Zapisanie referencji do przycisków.
        self.scans_widgets["up_btn"] = up_btn
        self.scans_widgets["down_btn"] = down_btn

        # --- LISTA SKANÓW ---
        
        listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bindowanie podwójnego kliknięcia do otwierania pliku.
        listbox.bind("<Double-1>", self.open_selected_scan)
        self.scans_widgets["listbox"] = listbox

        # Pasek przewijania dla listy.
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)

        # --- PRZYCISKI AKCJI ---
        
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=5)

        # Przycisk dodawania skanów.
        add_btn = ttk.Button(btn_frame, text="Dodaj skany...", command=self.add_scans)
        add_btn.pack(side=tk.LEFT)
        self.scans_widgets["add_btn"] = add_btn

        # Przycisk usuwania zaznaczonego skanu.
        remove_btn = ttk.Button(
            btn_frame,
            text="Usuń zaznaczony",
            command=self.remove_selected_scan,
            style="Danger.TButton",
        )
        remove_btn.pack(side=tk.LEFT, padx=5)
        self.scans_widgets["remove_btn"] = remove_btn

    # --- METODY ZARZĄDZANIA KOLEJNOŚCIĄ SKANÓW ---

    def move_scan_up(self):
        """
        Przesuwa zaznaczony skan o jedną pozycję w górę na liście.
        Zmiana kolejności jest zachowywana przy zapisie.
        """
        listbox = self.scans_widgets["listbox"]
        selected_indices = listbox.curselection()
        
        if not selected_indices:
            return

        idx = selected_indices[0]
        
        # Sprawdzenie, czy można przesunąć w górę.
        if idx > 0:
            # Pobranie tekstu zaznaczonego elementu.
            text = listbox.get(idx)
            
            # Usunięcie z bieżącej pozycji.
            listbox.delete(idx)
            
            # Wstawienie o jedną pozycję wyżej.
            listbox.insert(idx - 1, text)
            
            # Przywrócenie zaznaczenia.
            listbox.selection_set(idx - 1)
            listbox.activate(idx - 1)

    def move_scan_down(self):
        """
        Przesuwa zaznaczony skan o jedną pozycję w dół na liście.
        Zmiana kolejności jest zachowywana przy zapisie.
        """
        listbox = self.scans_widgets["listbox"]
        selected_indices = listbox.curselection()
        
        if not selected_indices:
            return

        idx = selected_indices[0]
        
        # Sprawdzenie, czy można przesunąć w dół.
        if idx < listbox.size() - 1:
            # Pobranie tekstu zaznaczonego elementu.
            text = listbox.get(idx)
            
            # Usunięcie z bieżącej pozycji.
            listbox.delete(idx)
            
            # Wstawienie o jedną pozycję niżej.
            listbox.insert(idx + 1, text)
            
            # Przywrócenie zaznaczenia.
            listbox.selection_set(idx + 1)
            listbox.activate(idx + 1)

    # --- METODY POBIERANIA STANU FORMULARZA ---

    def _get_current_form_data(self):
        """
        Zbiera aktualne dane ze wszystkich pól formularza.
        Używane do wykrywania niezapisanych zmian.
        
        Returns:
            dict: Słownik z aktualnymi danymi formularza
        """
        current_data = {}
        
        # Iteracja przez wszystkie pola formularza.
        for key, widget in self.fields.items():
            if isinstance(widget, tuple):  # Pole daty (3 komponenty)
                day, month, year = widget[0].get(), widget[1].get(), widget[2].get()
                current_data[key] = (
                    f"{day} {month} {year} rok" if day and month and year else ""
                )
            elif isinstance(widget, scrolledtext.ScrolledText):  # Pole tekstowe
                current_data[key] = widget.get("1.0", tk.END).strip()
            else:  # Zwykłe pole Entry
                current_data[key] = widget.get().strip()

        # Przetworzenie pól działek na listy.
        for key in [
            "buildingPlots",
            "agriculturalPlots",
            "realbuildingPlots",
            "realagriculturalPlots",
        ]:
            current_data[key] = self.parse_plots_from_string(current_data.get(key, ""))

        return current_data

    # --- METODY OTWIERANIA PLIKÓW SKANÓW ---

    def open_selected_scan(self, event):
        """
        Otwiera zaznaczony plik skanu w domyślnej aplikacji systemowej.
        
        Args:
            event: Zdarzenie podwójnego kliknięcia
        """
        listbox = self.scans_widgets["listbox"]
        selected_indices = listbox.curselection()
        
        if not selected_indices:
            return

        # Pobranie nazwy pliku do otwarcia.
        filename_to_open = listbox.get(selected_indices[0])

        # Pobranie ścieżki do folderu ze skanami.
        folder_path = self.get_scans_folder_path()
        if not folder_path:
            return

        file_path = os.path.join(folder_path, filename_to_open)

        if os.path.exists(file_path):
            try:
                # Otwarcie pliku w domyślnej aplikacji (Windows).
                os.startfile(file_path)
            except Exception as e:
                messagebox.showerror(
                    "Błąd otwierania pliku",
                    f"Nie można otworzyć pliku: {file_path}\nBłąd: {e}",
                )
        else:
            messagebox.showwarning(
                "Plik nie istnieje", f"Plik '{filename_to_open}' nie został znaleziony."
            )

    # --- METODY ZARZĄDZANIA TOOLTIPAMI ---

    def close_tooltip_if_exists(self, event=None):
        """
        Bezpiecznie zamyka okno podpowiedzi, jeśli istnieje.
        
        Args:
            event: Zdarzenie (opcjonalne)
        """
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def toggle_relacje_tooltip(self, event):
        """
        Pokazuje lub ukrywa okno podpowiedzi dla pola powiązań rodzinnych.
        Podpowiedź wyjaśnia składnię tworzenia linków do innych protokołów.
        
        Args:
            event: Zdarzenie kliknięcia na ikonę pomocy
        """
        # Jeśli tooltip jest już otwarty, zamknij go.
        if self.tooltip_window:
            self.close_tooltip_if_exists()
            return

        # Pobranie widgetu, który wywołał zdarzenie (ikona "?").
        trigger_widget = event.widget

        # Utworzenie nowego okna tooltip.
        self.tooltip_window = tk.Toplevel(self)
        self.tooltip_window.wm_overrideredirect(True)  # Usuwa ramkę okna

        # Ramka z zawartością tooltip.
        frame = ttk.Frame(
            self.tooltip_window, padding=10, relief="solid", borderwidth=1
        )
        frame.pack()

        # Nagłówek instrukcji.
        ttk.Label(
            frame,
            text="Jak tworzyć linki do innych protokołów:",
            font=("Calibri", 10, "bold"),
        ).pack(anchor="w")
        
        # Opis składni.
        ttk.Label(
            frame,
            text="Użyj składni: [[Tekst widoczny|KluczUnikalny]]",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 5))
        
        ttk.Separator(frame).pack(fill="x", pady=5)
        ttk.Label(frame, text="Przykład:").pack(anchor="w")

        # Przykład kodu.
        code_label = ttk.Label(
            frame,
            text="Żona: [[Anna Micek|Anna_Micek]]",
            background="#e9ecef",
            padding=5,
            relief="solid",
            borderwidth=1,
        )
        code_label.pack(anchor="w", fill="x", pady=2)

        # Pozycjonowanie tooltip względem ikony pomocy.
        x = trigger_widget.winfo_rootx()
        y = trigger_widget.winfo_rooty()
        
        # Ustaw pozycję 155px powyżej ikony.
        self.tooltip_window.geometry(f"+{x}+{y - 155}")

        # Zamknięcie tooltip po kliknięciu poza nim.
        self.tooltip_window.bind("<FocusOut>", self.close_tooltip_if_exists)
        self.tooltip_window.focus_set()

    # --- METODY TWORZENIA PODSTAWOWYCH PÓL FORMULARZA ---

    def create_field(self, parent, key, label_text, initial_value):
        """
        Tworzy standardowe pole tekstowe Entry z etykietą.
        
        Args:
            parent: Widget rodzica
            key: Klucz pola (do zapisania w self.fields)
            label_text: Tekst etykiety
            initial_value: Początkowa wartość pola
        """
        # Ramka dla pola.
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=4)
        
        # Etykieta po lewej stronie.
        ttk.Label(frame, text=label_text).pack(side=tk.LEFT, anchor="w", padx=(0, 10))
        
        # Pole tekstowe.
        entry = ttk.Entry(frame)
        entry.insert(0, str(initial_value))
        entry.pack(fill=tk.X, expand=True)
        
        # Zapisanie referencji do pola.
        self.fields[key] = entry

    def create_date_field(self, parent, key, label_text, initial_value):
        """
        Tworzy specjalne pole do wprowadzania daty.
        Składa się z trzech osobnych pól: dzień, miesiąc (słownie), rok.
        
        Args:
            parent: Widget rodzica
            key: Klucz pola (do zapisania w self.fields)
            label_text: Tekst etykiety
            initial_value: Początkowa wartość daty jako string
        """
        # Główna ramka dla całego pola daty.
        main_date_frame = ttk.Frame(parent)
        main_date_frame.pack(fill=tk.X, pady=4)

        # Etykieta główna.
        ttk.Label(main_date_frame, text=label_text).pack(
            side=tk.LEFT, anchor="n", padx=(0, 10)
        )

        # Ramka na poszczególne komponenty daty.
        fields_frame = ttk.Frame(main_date_frame)
        fields_frame.pack(fill=tk.X, expand=True)

        # Parsowanie istniejącej daty.
        day, month, year = "", "", ""
        if initial_value:
            # Obsługa formatu "DD miesiąc YYYY rok".
            match = re.match(
                r"(\d+)\s+([a-zA-Zęóąśłżźćń]+)\s+(\d{4})(?:\s+rok)?",
                initial_value.strip(),
            )
            if match:
                day, month, year = match.groups()

        # --- POLE DZIEŃ ---
        
        day_frame = ttk.Frame(fields_frame)
        day_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Label(day_frame, text="Dzień").pack(anchor="w")
        day_entry = ttk.Entry(day_frame)
        day_entry.insert(0, day)
        day_entry.pack(fill=tk.X)

        # --- POLE MIESIĄC ---
        
        month_frame = ttk.Frame(fields_frame)
        month_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Label(month_frame, text="Miesiąc (słownie)").pack(anchor="w")
        month_entry = ttk.Entry(month_frame)
        month_entry.insert(0, month)
        month_entry.pack(fill=tk.X)

        # --- POLE ROK ---
        
        year_frame = ttk.Frame(fields_frame)
        year_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Label(year_frame, text="Rok").pack(anchor="w")
        year_entry = ttk.Entry(year_frame)
        year_entry.insert(0, year)
        year_entry.pack(fill=tk.X)

        # Zapisanie referencji do wszystkich trzech pól jako krotki.
        self.fields[key] = (day_entry, month_entry, year_entry)

    def create_textarea(self, parent, key, label, initial="", *, height=3):
        """
        Tworzy duże pole tekstowe ScrolledText z przyciskiem "Powiększ".
        
        Args:
            parent: Widget rodzica
            key: Klucz pola (do zapisania w self.fields)
            label: Tekst etykiety
            initial: Początkowa zawartość
            height: Wysokość pola w liniach
        """
        # Ramka główna dla etykiety i przycisku.
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=4)

        header = ttk.Frame(row)
        header.pack(fill=tk.X)

        # Etykieta pola.
        ttk.Label(header, text=label).pack(side=tk.LEFT, anchor="w")

        # Przycisk otwierający duże okno edycji.
        expand_btn = ttk.Button(
            header, text="Powiększ", command=lambda: self._open_text_popup(txt, label)
        )
        expand_btn.pack(side=tk.RIGHT)

        # Zwiększona czcionka dla lepszej czytelności.
        bigger = tkfont.nametofont("TkTextFont").cget("size") + 2

        # Właściwe pole tekstowe.
        txt = scrolledtext.ScrolledText(
            row,
            height=height,
            wrap=tk.WORD,
            relief=tk.SOLID,
            borderwidth=1,
            font=("Segoe UI", bigger),
        )
        
        # Wstawienie początkowej zawartości.
        txt.insert("1.0", initial.replace("\\n", "\n"))
        txt.pack(fill=tk.X, expand=True, pady=(2, 0))

        # Zapisanie referencji.
        self.fields[key] = txt

    def _open_text_popup(self, original_widget, title="Edytuj tekst"):
        """
        Otwiera duże okno popup do wygodnej edycji długiego tekstu.
        Po zapisie, treść wraca do oryginalnego pola.
        
        Args:
            original_widget: Widget źródłowy (ScrolledText)
            title: Tytuł okna popup
        """
        # Utworzenie nowego okna popup.
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.transient(self)
        popup.grab_set()

        # Ustawienie rozmiaru na 80% ekranu.
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        w, h = int(sw * 0.8), int(sh * 0.8)
        popup.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Duże pole tekstowe z większą czcionką.
        big_font = ("Segoe UI", tkfont.nametofont("TkTextFont").cget("size") + 4)

        txt = scrolledtext.ScrolledText(
            popup, wrap=tk.WORD, font=big_font, relief=tk.SOLID, borderwidth=1
        )
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Skopiowanie zawartości z oryginalnego pola.
        txt.insert("1.0", original_widget.get("1.0", tk.END))

        # Pasek przycisków.
        btn_bar = ttk.Frame(popup)
        btn_bar.pack(fill=tk.X, pady=5, padx=10)

        def _save_and_close():
            """Zapisuje zmiany i zamyka popup."""
            original_widget.delete("1.0", tk.END)
            original_widget.insert("1.0", txt.get("1.0", tk.END).rstrip())
            popup.destroy()

        # Przycisk zapisania.
        ttk.Button(
            btn_bar, text="Zapisz", style="Accent.TButton", command=_save_and_close
        ).pack(side=tk.RIGHT, padx=5)
        
        # Przycisk anulowania.
        ttk.Button(btn_bar, text="Anuluj", command=popup.destroy).pack(side=tk.RIGHT)

    # --- METODY ZARZĄDZANIA PLIKAMI SKANÓW ---

    def get_scans_folder_path(self):
        """
        Zwraca ścieżkę do folderu ze skanami dla bieżącego właściciela.
        NIE tworzy folderu - tylko oblicza ścieżkę.
        
        Returns:
            str: Ścieżka do folderu lub None jeśli brak klucza
        """
        current_key = self.fields["unikalny_klucz"].get().strip()
        if not current_key:
            return None

        return os.path.join(script_dir, "..", "assets", "protokoly", current_key)

    def populate_scans_list(self):
        """
        Wypełnia listę istniejącymi plikami skanów.
        Sortuje pliki numerycznie (1.jpg, 2.jpg, ..., 10.jpg).
        """
        listbox = self.scans_widgets["listbox"]
        listbox.delete(0, tk.END)

        folder_path = self.get_scans_folder_path()
        if folder_path and os.path.exists(folder_path):
            try:
                # Sortowanie numeryczne plików.
                files = sorted(
                    os.listdir(folder_path),
                    key=lambda x: (
                        int(os.path.splitext(x)[0])
                        if x.replace(".jpg", "").isdigit()
                        else 999
                    ),
                )
                
                # Dodanie plików JPG do listy.
                for filename in files:
                    if filename.lower().endswith(".jpg"):
                        listbox.insert(tk.END, filename)
            except Exception as e:
                print(f"Błąd odczytu folderu ze skanami: {e}")

    def add_scans(self):
        """
        Otwiera dialog wyboru plików i kopiuje wybrane skany
        do folderu protokołu. Automatycznie numeruje pliki.
        """
        folder_path = self.get_scans_folder_path()
        if not folder_path:
            messagebox.showwarning(
                "Brak klucza", "Wpisz i zatwierdź unikalny klucz, aby dodać skany."
            )
            return

        # Upewnienie się, że folder docelowy istnieje.
        try:
            os.makedirs(folder_path, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Błąd", f"Nie można utworzyć folderu dla skanów:\n{e}")
            return

        # Dialog wyboru plików.
        files_to_add = filedialog.askopenfilenames(
            title="Wybierz pliki JPG do dodania", 
            filetypes=[("Obrazy JPG", "*.jpg")]
        )
        
        if not files_to_add:
            return

        # Kopiowanie wybranych plików z automatyczną numeracją.
        for source_path in files_to_add:
            # Znalezienie najwyższego istniejącego numeru.
            existing_numbers = [
                int(os.path.splitext(f)[0])
                for f in os.listdir(folder_path)
                if f.replace(".jpg", "").isdigit()
            ]
            next_num = max(existing_numbers) + 1 if existing_numbers else 1

            # Określenie nazwy docelowej.
            dest_filename = f"{next_num}.jpg"
            dest_path = os.path.join(folder_path, dest_filename)

            try:
                shutil.copy(source_path, dest_path)
            except Exception as e:
                messagebox.showerror(
                    "Błąd kopiowania",
                    f"Nie udało się skopiować pliku: {source_path}\nBłąd: {e}",
                )
                break

        # Odświeżenie listy plików.
        self.populate_scans_list()

    def remove_selected_scan(self):
        """
        Usuwa zaznaczony plik skanu z folderu.
        Wymaga potwierdzenia użytkownika.
        """
        listbox = self.scans_widgets["listbox"]
        selected_indices = listbox.curselection()
        
        if not selected_indices:
            messagebox.showwarning("Brak zaznaczenia", "Zaznacz skan do usunięcia.")
            return

        filename_to_delete = listbox.get(selected_indices[0])

        # Potwierdzenie usunięcia.
        if messagebox.askyesno(
            "Potwierdzenie", f"Czy na pewno chcesz usunąć plik '{filename_to_delete}'?"
        ):
            folder_path = self.get_scans_folder_path()
            file_path = os.path.join(folder_path, filename_to_delete)
            
            try:
                os.remove(file_path)
                self.populate_scans_list()
            except Exception as e:
                messagebox.showerror(
                    "Błąd usuwania", f"Nie udało się usunąć pliku: {e}"
                )

    # --- METODY FORMATOWANIA I PARSOWANIA DANYCH ---

    def format_plots_for_display(self, plots):
        """
        Formatuje listę działek do wyświetlenia w polu tekstowym.
        Konwertuje obiekty dict na format "numerator/denominator".
        
        Args:
            plots: Lista działek (stringi lub słowniki)
            
        Returns:
            str: Sformatowany string z numerami działek
        """
        if not plots:
            return ""
            
        formatted_list = []
        for p in plots:
            if isinstance(p, dict):
                # Obsługa starszego formatu z literówką "numarator".
                num = p.get("numerator") or p.get("numarator", "?")
                den = p.get("denominator", "?")
                formatted_list.append(f"{num}/{den}")
            else:
                formatted_list.append(str(p))
                
        return ", ".join(formatted_list)

    def parse_plots_from_string(self, text):
        """
        Parsuje string z numerami działek na listę.
        Rozpoznaje format "numerator/denominator" i zwykłe numery.
        
        Args:
            text: String z numerami działek oddzielonymi przecinkami
            
        Returns:
            list: Lista działek jako stringi lub słowniki
        """
        if not text.strip():
            return []
            
        parsed_plots = []
        parts = text.split(",")
        
        for p in parts:
            p_clean = p.strip()
            if not p_clean:
                continue
                
            if "/" in p_clean:
                # Działka z ułamkiem.
                num, den = p_clean.split("/", 1)
                parsed_plots.append(
                    {"numerator": num.strip(), "denominator": den.strip()}
                )
            else:
                # Zwykły numer działki.
                parsed_plots.append(p_clean)
                
        return parsed_plots

    def save(self, close_after=True):
        """
        Zbiera dane z formularza, reorganizuje pliki skanów i zapisuje wszystko.
        
        Args:
            close_after: Czy zamknąć okno po zapisie (domyślnie True)
            
        Returns:
            bool: True jeśli zapis się powiódł, False w przypadku błędu
        """
        # --- ZBIERANIE DANYCH Z FORMULARZA ---
        
        saved_data = {}
        for key, widget in self.fields.items():
            if isinstance(widget, tuple):  # Pole daty
                day, month, year = widget[0].get(), widget[1].get(), widget[2].get()
                saved_data[key] = (
                    f"{day} {month} {year} rok" if day and month and year else ""
                )
            elif isinstance(widget, scrolledtext.ScrolledText):  # Pole tekstowe
                saved_data[key] = widget.get("1.0", tk.END).strip()
            else:  # Zwykłe pole Entry
                saved_data[key] = widget.get().strip()

        # Parsowanie pól z działkami.
        saved_data["buildingPlots"] = self.parse_plots_from_string(
            saved_data.get("buildingPlots", "")
        )
        saved_data["agriculturalPlots"] = self.parse_plots_from_string(
            saved_data.get("agriculturalPlots", "")
        )
        saved_data["realbuildingPlots"] = self.parse_plots_from_string(
            saved_data.get("realbuildingPlots", "")
        )
        saved_data["realagriculturalPlots"] = self.parse_plots_from_string(
            saved_data.get("realagriculturalPlots", "")
        )

        # --- REORGANIZACJA PLIKÓW SKANÓW ---
        
        try:
            folder_path = self.get_scans_folder_path()
            if folder_path and os.path.exists(folder_path):
                listbox = self.scans_widgets["listbox"]
                final_order = list(listbox.get(0, tk.END))

                # Utworzenie tymczasowego folderu.
                temp_folder = os.path.join(folder_path, "_temp_reorder")
                if not os.path.exists(temp_folder):
                    os.makedirs(temp_folder)

                # Przeniesienie plików do folderu tymczasowego.
                current_files_in_folder = os.listdir(folder_path)
                for filename in final_order:
                    if filename in current_files_in_folder:
                        shutil.move(
                            os.path.join(folder_path, filename),
                            os.path.join(temp_folder, filename),
                        )

                # Przenumerowanie plików zgodnie z nową kolejnością.
                for i, old_filename in enumerate(final_order):
                    if os.path.exists(os.path.join(temp_folder, old_filename)):
                        new_filename = f"{i + 1}.jpg"
                        shutil.move(
                            os.path.join(temp_folder, old_filename),
                            os.path.join(folder_path, new_filename),
                        )

                # Usunięcie folderu tymczasowego.
                os.rmdir(temp_folder)
                
        except Exception as e:
            messagebox.showerror(
                "Błąd Reorganizacji Skanów",
                f"Nie udało się zmienić kolejności plików skanów:\n{e}",
                parent=self,
            )
            return False

        # --- WYWOŁANIE CALLBACK ZAPISU ---
        
        save_successful = self.save_callback(saved_data, self.original_key)

        if not save_successful:
            return False  # Jeśli zapis się nie powiódł, zostań w oknie

        # --- AKTUALIZACJA STANU PO ZAPISIE ---
        
        # Aktualizacja klucza, jeśli się zmienił.
        self.original_key = saved_data.get("unikalny_klucz", self.original_key)
        
        # Pobranie zaktualizowanych danych.
        if self.original_key in self.master.data:
            self.owner_data = self.master.data[self.original_key]

        if close_after:
            # Zamknięcie okna.
            self.destroy()
        else:
            # Pozostanie w oknie z odświeżeniem.
            self.master.refresh_treeview()
            self.sorted_keys = self.master.tree.get_children()
            self._update_nav_buttons_state()
            self.title(
                f"Edycja Danych - {self.owner_data.get('ownerName', self.original_key)}"
            )
            messagebox.showinfo("Zapisano", "Zmiany zostały zapisane.", parent=self)
            
            # Zaktualizowanie migawki stanu.
            self.initial_form_data = self._get_current_form_data()

        return True

# --- KLASA OKNA EDYTORA DEMOGRAFII ---
class DemografiaEditorWindow(tk.Toplevel):
    """
    Okno do edycji danych demograficznych miejscowości.
    Pozwala na dodawanie, edycję i usuwanie wpisów demograficznych.
    """
    
    def __init__(self, parent):
        """
        Inicjalizacja okna edytora demografii.
        
        Args:
            parent: Okno rodzica (główna aplikacja)
        """
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Edytor Danych Demograficznych")
        
        # Poprawione pozycjonowanie okna
        self._setup_window_geometry()

        self.data = []
        self.load_data()
        self.create_widgets()

    def _setup_window_geometry(self):
        """
        Konfiguruje geometrię okna z uwzględnieniem paska zadań Windows.
        """
        # Pobierz wymiary ekranu
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        
        # Dla Windows, uwzględnij pasek zadań (zazwyczaj 40-50px)
        if platform.system() == "Windows":
            # Rezerwuj przestrzeń na pasek zadań
            taskbar_height = 50
            available_height = sh - taskbar_height
            
            # Ustaw okno na 85% dostępnej przestrzeni
            w = int(sw * 0.85)
            h = int(available_height * 0.85)
            
            # Wycentruj okno
            x = (sw - w) // 2
            y = (available_height - h) // 2
            
            self.geometry(f"{w}x{h}+{x}+{y}")
            
            # Maksymalizuj jeśli okno jest większe niż 1400x800
            if w > 1400 and h > 800:
                self.after(100, lambda: self.state('zoomed'))
        else:
            # Dla innych systemów
            w = min(int(sw * 0.8), 1200)
            h = min(int(sh * 0.8), 700)
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")
        
        self.minsize(600, 400)

    def load_data(self):
        """Wczytuje dane demograficzne z pliku JSON."""
        try:
            if os.path.exists(DEMOGRAFIA_JSON_PATH):
                with open(DEMOGRAFIA_JSON_PATH, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
        except Exception as e:
            messagebox.showerror(
                "Błąd odczytu", f"Nie udało się wczytać pliku demografia.json:\n{e}"
            )

    def save_data(self):
        """Zapisuje dane demograficzne do pliku JSON."""
        try:
            with open(DEMOGRAFIA_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Sukces", "Dane demograficzne zostały zapisane.")
            self.destroy()
        except Exception as e:
            messagebox.showerror(
                "Błąd zapisu", f"Nie udało się zapisać pliku demografia.json:\n{e}"
            )

    def create_widgets(self):
        """
        Tworzy kompletny interfejs użytkownika dla edytora demografii.
        
        Struktura interfejsu:
        - Zewnętrzna ramka z marginesem (zapobiega zakrywaniu przez pasek zadań)
        - Tabela z danymi demograficznymi (Treeview)
        - Panel przycisków akcji (dodawanie, usuwanie, zapis)
        
        Margines dolny zapewnia widoczność wszystkich elementów na różnych
        konfiguracjach systemu Windows z paskiem zadań o różnej wysokości.
        """
        
        # --- ZEWNĘTRZNY KONTENER Z MARGINESEM BEZPIECZEŃSTWA ---
        
        # Utworzenie zewnętrznej ramki z marginesem dolnym.
        # Margines 50px zapobiega zakrywaniu przycisków przez pasek zadań Windows.
        outer_frame = ttk.Frame(self)
        outer_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 50))
        
        # --- GŁÓWNY KONTENER INTERFEJSU ---
        
        # Główny kontener wewnątrz ramki z marginesem.
        main_container = ttk.Frame(outer_frame)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Konfiguracja siatki grid dla elastycznego układu.
        # Wiersz 0 (tabela) otrzymuje całą dostępną przestrzeń (weight=1).
        # Wiersz 1 (przyciski) zachowuje stały rozmiar (weight=0).
        main_container.grid_rowconfigure(0, weight=1)  # Tabela - rozciągalna
        main_container.grid_rowconfigure(1, weight=0)  # Przyciski - stała wysokość
        main_container.grid_columnconfigure(0, weight=1)
        
        # --- SEKCJA TABELI Z DANYMI DEMOGRAFICZNYMI ---
        
        # Ramka z etykietą dla tabeli danych.
        tree_frame = ttk.LabelFrame(
            main_container, 
            text="Dane demograficzne", 
            padding="10"
        )
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        
        # Konfiguracja rozciągania zawartości ramki.
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Kontener wewnętrzny dla tabeli i pasków przewijania.
        table_container = ttk.Frame(tree_frame)
        table_container.grid(row=0, column=0, sticky="nsew")
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)
        
        # --- KONFIGURACJA TABELI TREEVIEW ---
        
        # Definicja kolumn tabeli demograficznej.
        columns = ("rok", "populacja", "katolicy", "zydzi", "inni", "opis")
        
        # Utworzenie widgetu Treeview do wyświetlania danych tabelarycznych.
        self.tree = ttk.Treeview(
            table_container, 
            columns=columns, 
            show="headings",  # Pokazuj tylko nagłówki kolumn (bez kolumny tree)
            selectmode="browse"  # Pozwól na wybór tylko jednego wiersza
        )
        
        # --- KONFIGURACJA WYSOKOŚCI WIERSZY ---
        
        # Pobranie domyślnej czcionki i obliczenie odpowiedniej wysokości wiersza.
        base_font = tkfont.nametofont("TkDefaultFont")
        row_height = base_font.cget("size") * 2  # Podwójna wysokość dla lepszej czytelności
        
        # Zastosowanie stylu z dostosowaną wysokością wierszy.
        self.style = ttk.Style(self)
        self.style.configure("Treeview", rowheight=row_height)
        
        # --- KONFIGURACJA NAGŁÓWKÓW KOLUMN ---
        
        # Ustawienie tekstów nagłówków dla każdej kolumny.
        self.tree.heading("rok", text="Rok")
        self.tree.heading("populacja", text="Populacja")
        self.tree.heading("katolicy", text="Katolicy")
        self.tree.heading("zydzi", text="Żydzi")
        self.tree.heading("inni", text="Inni")
        self.tree.heading("opis", text="Opis")
        
        # --- KONFIGURACJA SZEROKOŚCI KOLUMN ---
        
        # Ustawienie szerokości kolumn z wartościami minimalnymi.
        # Kolumna "opis" ma stretch=True, więc rozciąga się na dostępną przestrzeń.
        self.tree.column("rok", width=80, minwidth=60)
        self.tree.column("populacja", width=100, minwidth=80)
        self.tree.column("katolicy", width=100, minwidth=80)
        self.tree.column("zydzi", width=100, minwidth=80)
        self.tree.column("inni", width=100, minwidth=80)
        self.tree.column("opis", width=250, minwidth=150, stretch=True)  # Elastyczna szerokość
        
        # Umieszczenie tabeli w kontenerze.
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        # --- PASKI PRZEWIJANIA ---
        
        # Pionowy pasek przewijania.
        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        
        # Poziomy pasek przewijania.
        hsb = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        
        # Połączenie pasków przewijania z tabelą.
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Wypełnienie tabeli istniejącymi danymi.
        self.populate_tree()
        
        # --- PANEL PRZYCISKÓW AKCJI ---
        
        # Ramka na przyciski (zawsze widoczna u dołu okna).
        button_frame = ttk.Frame(main_container)
        # Zwiększony padding dolny (20px) dla dodatkowej pewności widoczności.
        button_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 20))
        
        # --- PRZYCISKI PO LEWEJ STRONIE ---
        
        # Kontener dla przycisków akcji (lewa strona).
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)
        
        # Przycisk dodawania nowego wiersza.
        ttk.Button(
            left_buttons, 
            text="➕ Dodaj wiersz", 
            command=self.add_row
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        # Przycisk usuwania zaznaczonego wiersza.
        ttk.Button(
            left_buttons, 
            text="🗑️ Usuń zaznaczony", 
            command=self.delete_row,
            style="Danger.TButton"  # Czerwony styl dla akcji destrukcyjnej
        ).pack(side=tk.LEFT, padx=5)
        
        # --- PRZYCISKI PO PRAWEJ STRONIE ---
        
        # Kontener dla przycisku zapisu (prawa strona).
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        # Przycisk zapisywania i zamykania okna.
        ttk.Button(
            right_buttons, 
            text="💾 Zapisz i zamknij", 
            command=self.save_and_close,
            style="Accent.TButton"  # Zielony styl dla głównej akcji
        ).pack(side=tk.RIGHT)
        
        # --- BINDOWANIE ZDARZEŃ ---
        
        # Obsługa podwójnego kliknięcia na komórkę tabeli (edycja inline).
        self.tree.bind("<Double-1>", self.on_double_click)
        
        # Konfiguracja obsługi scrolla myszki dla tabeli.
        self._bind_mousewheel()

    def _bind_mousewheel(self):
        """Binduje scroll myszki do tabeli."""
        def _on_mousewheel(event):
            self.tree.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        self.tree.bind("<MouseWheel>", _on_mousewheel)
        # Dla Linuxa
        self.tree.bind("<Button-4>", lambda e: self.tree.yview_scroll(-1, "units"))
        self.tree.bind("<Button-5>", lambda e: self.tree.yview_scroll(1, "units"))

    def populate_tree(self):
        """Wypełnia tabelę danymi demograficznymi."""
        # Czyszczenie tabeli
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Dodawanie wierszy
        for row in self.data:
            self.tree.insert(
                "",
                "end",
                values=(
                    row.get("rok", ""),
                    row.get("populacja_ogolem", ""),
                    row.get("katolicy", ""),
                    row.get("zydzi", ""),
                    row.get("inni", ""),
                    row.get("opis", ""),
                ),
            )

    def on_double_click(self, event):
        """
        Obsługuje edycję komórki po dwukliku.
        Dla kolumny 'Opis' otwiera duże okno, dla pozostałych - małe pole Entry.
        
        Args:
            event: Zdarzenie podwójnego kliknięcia
        """
        item_id = self.tree.focus()
        if not item_id:
            return

        # Identyfikacja klikniętej kolumny
        column = self.tree.identify_column(event.x)
        column_index = int(column.replace("#", "")) - 1  # Indeks 0-based
        current_values = list(self.tree.item(item_id)["values"])

        # Kolumna 'Opis' (indeks 5) - duże okno edycji
        if column_index == 5:
            self._open_text_popup(item_id, column_index, current_values[column_index])
            return

        # Pozostałe kolumny - inline edycja
        x, y, width, height = self.tree.bbox(item_id, column)

        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, current_values[column_index])
        entry.focus_set()
        entry.select_range(0, tk.END)

        def _save_and_close(_=None):
            """Zapisuje wartość i zamyka pole edycji."""
            current_values[column_index] = entry.get()
            self.tree.item(item_id, values=current_values)
            entry.destroy()

        entry.bind("<FocusOut>", _save_and_close)
        entry.bind("<Return>", _save_and_close)
        entry.bind("<Escape>", lambda e: entry.destroy())

    def _open_text_popup(self, item_id, col_idx, initial_text):
        """
        Otwiera duże okno do edycji długiego tekstu (kolumna Opis).
        
        Args:
            item_id: ID wiersza w tabeli
            col_idx: Indeks kolumny
            initial_text: Początkowy tekst
        """
        popup = tk.Toplevel(self)
        popup.title("Edytuj opis")
        popup.transient(self)
        popup.grab_set()

        # Rozmiar 60% ekranu
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        w, h = int(sw * 0.6), int(sh * 0.6)
        popup.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Pole tekstowe
        big_font = ("Segoe UI", tkfont.nametofont("TkTextFont").cget("size") + 2)
        txt = scrolledtext.ScrolledText(
            popup, wrap=tk.WORD, font=big_font, relief=tk.SOLID, borderwidth=1
        )
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt.insert("1.0", initial_text)
        txt.focus_set()

        # Przyciski
        btn_bar = ttk.Frame(popup)
        btn_bar.pack(fill=tk.X, pady=(0, 10), padx=10)

        def _save():
            """Zapisuje zmiany do tabeli."""
            new_text = txt.get("1.0", tk.END).rstrip()
            values = list(self.tree.item(item_id)["values"])
            values[col_idx] = new_text
            self.tree.item(item_id, values=values)
            popup.destroy()

        ttk.Button(btn_bar, text="Zapisz", style="Accent.TButton", command=_save).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(btn_bar, text="Anuluj", command=popup.destroy).pack(side=tk.RIGHT)

    def add_row(self):
        """Dodaje pusty wiersz do tabeli."""
        self.tree.insert("", "end", values=("", "", "", "", "", ""))
        # Przewiń do nowego wiersza
        children = self.tree.get_children()
        if children:
            self.tree.see(children[-1])
            self.tree.selection_set(children[-1])

    def delete_row(self):
        """Usuwa zaznaczony wiersz z tabeli."""
        selected_item = self.tree.selection()
        if selected_item:
            if messagebox.askyesno("Potwierdzenie", "Czy na pewno chcesz usunąć zaznaczony wiersz?", parent=self):
                self.tree.delete(selected_item)

    def save_and_close(self):
        """
        Zapisuje dane z tabeli do pliku JSON i zamyka okno.
        Waliduje poprawność danych numerycznych.
        """
        new_data = []
        
        # Zbieranie danych z tabeli
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id)["values"]

            # Pomijanie całkowicie pustych wierszy
            if not any(str(v).strip() for v in values):
                continue

            try:
                # Funkcja pomocnicza do bezpiecznej konwersji
                def to_int_or_none(value):
                    """Konwertuje wartość na int lub None."""
                    if isinstance(value, str) and value.strip() == "":
                        return None
                    if value is None:
                        return None
                    return int(value)

                # Tworzenie wpisu demograficznego
                new_data.append(
                    {
                        "rok": to_int_or_none(values[0]),
                        "populacja_ogolem": to_int_or_none(values[1]),
                        "katolicy": to_int_or_none(values[2]),
                        "zydzi": to_int_or_none(values[3]),
                        "inni": to_int_or_none(values[4]),
                        "opis": str(values[5]) if values[5] else "",
                    }
                )
            except (ValueError, IndexError):
                messagebox.showerror(
                    "Błąd Danych",
                    "Upewnij się, że w kolumnach numerycznych znajdują się tylko liczby.",
                    parent=self
                )
                return

        self.data = new_data
        self.save_data()

# --- KLASA MENEDŻERA KOPII ZAPASOWYCH ---

class BackupManagerWindow(tk.Toplevel):
    """
    Okno do zarządzania kopiami zapasowymi.
    Umożliwia tworzenie, przywracanie i usuwanie kopii ZIP
    zawierających dane JSON oraz wszystkie skany.
    """
    
    def __init__(self, parent):
        """
        Inicjalizacja okna menedżera kopii zapasowych.
        
        Args:
            parent: Okno rodzica (główna aplikacja)
        """
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Menedżer Kopii Zapasowych (Dane + Skany)")

        self.parent = parent
        self.selected_backup_file = None

        self._center_or_maximize()
        self.create_widgets()
        self.populate_backup_list()

    def _center_or_maximize(self):
        """Maksymalizuje okno na Windows lub centruje na innych systemach."""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        if platform.system() == "Windows":
            self.state("zoomed")
            self.geometry(f"{int(sw*0.9)}x{int(sh*0.9)}+{int(sw*0.05)}+{int(sh*0.05)}")
        else:
            w, h = 800, 600
            self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
        self.minsize(600, 400)

    def create_widgets(self):
        """Tworzy interfejs użytkownika menedżera kopii."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # --- PASEK GÓRNY ---
        
        top_bar = ttk.Frame(main_frame)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Button(
            top_bar,
            text="Stwórz nową kompletną kopię (ZIP)",
            command=self.create_backup,
            style="Accent.TButton",
        ).pack(side=tk.LEFT)
        
        ttk.Label(top_bar, text="Kopie .zip zawierają dane i wszystkie skany").pack(
            side=tk.RIGHT, padx=10
        )

        # --- LISTA KOPII ZAPASOWYCH ---
        
        list_frame = ttk.LabelFrame(
            main_frame, text="Dostępne kopie zapasowe (od najnowszej)", padding="10"
        )
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(list_frame, columns=("filename",), show="headings")
        self.tree.heading("filename", text="Nazwa Pliku Kopii Zapasowej (.zip)")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # --- PASEK AKCJI ---
        
        EXTRA_BOTTOM_MARGIN = 60
        action_bar = ttk.Frame(main_frame, padding=(0, 10, 0, EXTRA_BOTTOM_MARGIN))
        action_bar.grid(row=2, column=0, sticky="ew")

        self.selected_label = ttk.Label(
            action_bar, text="Nic nie zaznaczono", anchor="w"
        )
        self.selected_label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.restore_btn = ttk.Button(
            action_bar, text="Przywróć", command=self.restore_backup, state=tk.DISABLED
        )
        self.restore_btn.pack(side=tk.RIGHT, padx=5)
        
        self.delete_btn = ttk.Button(
            action_bar,
            text="Usuń",
            style="Danger.TButton",
            command=self.delete_backup,
            state=tk.DISABLED,
        )
        self.delete_btn.pack(side=tk.RIGHT)

    def populate_backup_list(self):
        """
        Wyszukuje i wyświetla wszystkie dostępne kopie zapasowe.
        Sortuje pliki od najnowszych.
        """
        # Czyszczenie listy.
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            # Wyszukiwanie plików backup_*.zip.
            files = [
                f
                for f in os.listdir(BACKUP_FOLDER)
                if f.startswith("backup_") and f.endswith(".zip")
            ]
            files.sort(reverse=True)  # Od najnowszych

            # Dodawanie do listy.
            for filename in files:
                self.tree.insert("", "end", iid=filename, values=(filename,))
                
        except FileNotFoundError:
            ttk.Label(self.tree, text="Folder backup nie istnieje.").pack()
            
        self.on_select()  # Odświeżenie stanu przycisków

    def on_select(self, event=None):
        """
        Aktualizuje panel akcji po zaznaczeniu elementu na liście.
        
        Args:
            event: Zdarzenie zmiany zaznaczenia (opcjonalne)
        """
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
        """
        Tworzy kompletną kopię zapasową w formacie ZIP.
        Uruchamia proces w osobnym wątku z paskiem postępu.
        """
        if not os.path.exists(JSON_FILE_PATH):
            messagebox.showwarning(
                "Brak pliku",
                "Nie można utworzyć kopii, ponieważ plik roboczy nie istnieje.",
                parent=self,
            )
            return

        # --- OKNO Z PASKIEM POSTĘPU ---
        
        progress_window = tk.Toplevel(self)
        progress_window.title("Tworzenie kopii zapasowej")
        progress_window.transient(self)
        progress_window.grab_set()

        # Pozycjonowanie okna postępu.
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 150) // 2
        progress_window.geometry(f"400x180+{x}+{y}")
        progress_window.resizable(False, False)

        # Elementy interfejsu.
        ttk.Label(
            progress_window,
            text="Przygotowywanie plików...",
            font=("Segoe UI", 11),
            padding=10,
        ).pack(pady=(15, 5))
        
        progress_bar = ttk.Progressbar(
            progress_window, orient="horizontal", length=360, mode="determinate"
        )
        progress_bar.pack(pady=5, padx=20)
        
        status_label = ttk.Label(
            progress_window, text="", padding=5, wraplength=350
        )
        status_label.pack(pady=(5, 10))

        # --- FUNKCJA WĄTKU TWORZENIA KOPII ---
        
        def backup_thread_func():
            """Funkcja wykonywana w osobnym wątku - tworzy archiwum ZIP."""
            try:
                from datetime import datetime

                # Przygotowanie ścieżek.
                protokoly_path = os.path.join(script_dir, "..", "assets", "protokoly")
                files_to_backup = [JSON_FILE_PATH]
                
                if os.path.exists(DEMOGRAFIA_JSON_PATH):
                    files_to_backup.append(DEMOGRAFIA_JSON_PATH)

                # Zbieranie wszystkich plików skanów.
                scan_files = []
                if os.path.exists(protokoly_path):
                    for root, _, files in os.walk(protokoly_path):
                        for file in files:
                            scan_files.append(os.path.join(root, file))

                # Konfiguracja paska postępu.
                total_steps = len(files_to_backup) + len(scan_files)
                progress_bar["maximum"] = total_steps

                # Generowanie nazwy pliku z datą i czasem.
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(BACKUP_FOLDER, f"backup_{timestamp}.zip")

                # Tworzenie archiwum ZIP.
                with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    # Archiwizacja plików JSON.
                    for i, file_path in enumerate(files_to_backup):
                        arcname = os.path.basename(file_path)
                        status_label.config(text=f"Archiwizuję: {arcname}")
                        zf.write(file_path, arcname=arcname)
                        progress_bar["value"] = i + 1
                        self.update_idletasks()

                    # Archiwizacja skanów.
                    for i, file_path in enumerate(scan_files):
                        arcname = os.path.join(
                            "assets",
                            "protokoly",
                            os.path.relpath(file_path, protokoly_path),
                        )
                        # Aktualizacja co 10 plików dla wydajności.
                        if (i % 10 == 0) or (i == len(scan_files) - 1):
                            status_label.config(
                                text=f"Archiwizuję skany: {i+1}/{len(scan_files)}"
                            )
                        zf.write(file_path, arcname)
                        progress_bar["value"] = len(files_to_backup) + i + 1
                        self.update_idletasks()

                # Oznaczenie sukcesu.
                progress_window.success = True
                progress_window.backup_name = os.path.basename(backup_path)

            except Exception as e:
                progress_window.success = False
                progress_window.error_message = str(e)
            finally:
                # Zamknięcie okna postępu.
                self.after(100, progress_window.destroy)

        # Ustawienie flag domyślnych.
        progress_window.success = None
        progress_window.error_message = ""
        progress_window.backup_name = ""

        # Uruchomienie wątku.
        backup_thread = threading.Thread(target=backup_thread_func, daemon=True)
        backup_thread.start()

        # Oczekiwanie na zakończenie.
        self.wait_window(progress_window)

        # --- OBSŁUGA WYNIKÓW ---
        
        if hasattr(progress_window, "success") and progress_window.success:
            messagebox.showinfo(
                "Sukces",
                f"Utworzono kompletną kopię zapasową:\n{progress_window.backup_name}",
                parent=self,
            )
            self.populate_backup_list()
        elif (
            hasattr(progress_window, "error_message") and progress_window.error_message
        ):
            messagebox.showerror(
                "Błąd",
                f"Nie udało się utworzyć kopii:\n{progress_window.error_message}",
                parent=self,
            )

        self.on_select()

    def restore_backup(self):
        """
        Przywraca kompletną kopię zapasową z pliku ZIP.
        UWAGA: Operacja nieodwracalna - nadpisuje obecne dane!
        """
        if not self.selected_backup_file:
            return

        filename = self.selected_backup_file
        
        # Ostrzeżenie dla użytkownika.
        msg = (
            "UWAGA! Ta operacja jest NIEODWRACALNA.\n\n"
            f"Czy na pewno chcesz przywrócić kopię '{filename}'?\n\n"
            "Spowoduje to:\n"
            "1. NADPISANIE plików JSON z danymi.\n"
            "2. CAŁKOWITE USUNIĘCIE obecnego folderu ze skanami i zastąpienie go wersją z kopii."
        )

        if messagebox.askyesno(
            "POTWIERDZENIE KRYTYCZNEJ OPERACJI", msg, icon="warning", parent=self
        ):
            backup_zip_path = os.path.join(BACKUP_FOLDER, filename)
            temp_restore_path = os.path.join(BACKUP_FOLDER, "_temp_restore")

            self.selected_label.config(text="Przywracanie kopii, proszę czekać...")
            self.update_idletasks()

            success = False
            try:
                # Przygotowanie folderu tymczasowego.
                if os.path.exists(temp_restore_path):
                    shutil.rmtree(temp_restore_path)
                os.makedirs(temp_restore_path)
                
                # Rozpakowanie archiwum.
                with zipfile.ZipFile(backup_zip_path, "r") as zf:
                    zf.extractall(temp_restore_path)

                # Sprawdzenie kompletności archiwum.
                temp_json_owner = os.path.join(
                    temp_restore_path, "owner_data_to_import.json"
                )
                temp_protokoly = os.path.join(temp_restore_path, "assets", "protokoly")
                
                if not os.path.exists(temp_json_owner) or not os.path.exists(
                    temp_protokoly
                ):
                    raise FileNotFoundError(
                        "Archiwum ZIP jest niekompletne."
                    )

                # Usunięcie obecnych danych.
                protokoly_path = os.path.join(script_dir, "..", "assets", "protokoly")
                if os.path.exists(protokoly_path):
                    shutil.rmtree(protokoly_path)

                # Przywrócenie danych z kopii.
                shutil.move(temp_protokoly, os.path.join(script_dir, "..", "assets"))
                shutil.move(temp_json_owner, JSON_FILE_PATH)

                # Przywrócenie danych demograficznych (jeśli istnieją).
                temp_json_demo = os.path.join(temp_restore_path, "demografia.json")
                if os.path.exists(temp_json_demo):
                    shutil.move(temp_json_demo, DEMOGRAFIA_JSON_PATH)
                    print("Przywrócono dane demograficzne.")

                messagebox.showinfo(
                    "Sukces",
                    "Kopia zapasowa została przywrócona.\nDane w edytorze zostaną przeładowane.",
                    parent=self,
                )
                
                # Przeładowanie danych w głównym oknie.
                self.parent.load_from_json()

                success = True
                self.destroy()
                
            except Exception as e:
                messagebox.showerror(
                    "Błąd przywracania", f"Wystąpił krytyczny błąd: {e}", parent=self
                )
            finally:
                # Czyszczenie folderu tymczasowego.
                if os.path.exists(temp_restore_path):
                    shutil.rmtree(temp_restore_path)
                if not success:
                    self.populate_backup_list()

    def delete_backup(self):
        """
        Trwale usuwa wybrany plik kopii zapasowej.
        Wymaga potwierdzenia użytkownika.
        """
        if not self.selected_backup_file:
            return

        filename = self.selected_backup_file
        
        if messagebox.askyesno(
            "Potwierdzenie usunięcia",
            f"Czy na pewno chcesz trwale usunąć plik kopii zapasowej:\n\n{filename}?",
            parent=self,
        ):
            backup_path = os.path.join(BACKUP_FOLDER, filename)
            try:
                os.remove(backup_path)
                self.populate_backup_list()
            except Exception as e:
                messagebox.showerror(
                    "Błąd", f"Nie udało się usunąć pliku: {e}", parent=self
                )

# --- PUNKT WEJŚCIA PROGRAMU ---

if __name__ == "__main__":
    """
    Główny punkt wejścia aplikacji.
    Tworzy instancję głównego okna i uruchamia pętlę zdarzeń.
    """
    app = OwnerEditorApp()
    app.mainloop()
