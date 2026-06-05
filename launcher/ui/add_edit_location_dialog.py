"""Dialog dodawania i edycji miejscowości."""

import os
import tkinter as tk
import shutil
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog

from ..config.paths import BASE_DIR
from ..db.engine import get_engine
from ..db.postgres import get_postgres_config, list_databases
from ..services.historical_points_service import (
    HistoricalPoint,
    HistoricalPointValidationError,
    list_history_photos,
    list_point_photos,
    list_special_objects,
    get_point_photos_dir,
    load_historical_points,
)
from ..utils import set_dialog_icon, scale_window, scale_wrap, check_postgres_available


__all__ = ["AddEditLocationDialog"]


def is_sqlite_mode():
    return get_engine().name == "sqlite"


class AddEditLocationDialog(tk.Toplevel):
    """Dialog do dodawania/edytowania miejscowości z zakładkami."""

    HOMEPAGE_TEMPLATE_LABELS = {
        "standardowy": "standardowy",
        "praca_inzynierska": "praca inżynierska",
    }
    HOMEPAGE_TEMPLATE_VALUES = {label: key for key, label in HOMEPAGE_TEMPLATE_LABELS.items()}
    NEW_DB_LABEL = "(nowa baza - wpisz nazwę)"
    LEGACY_NEW_DB_LABEL = "(nowa baza - wpisz nazwe)"

    def __init__(self, parent, title, name="", full_name="", powiat="", region="", year="1882", century="XIX w.",
                 homepage_description="", history_paragraph1="", history_paragraph2="", history_paragraph3="",
                 history_photos=None, postgres_db_name="", homepage_template="standardowy",
                 gmina_katastralna="Czarna", jewish_protocol_numbers="", historical_points=None):
        super().__init__(parent)
        set_dialog_icon(self)
        self.transient(parent)
        self.title(title)
        self.grab_set()

        self.result = None
        self.history_photos = history_photos if history_photos else []
        # Punkty historyczne - lista dictów (zgodna ze schematem JSON).
        # Ładowane leniwie w _build_historical_points_tab() gdy znamy location_name.
        self.historical_points_data = historical_points if historical_points else []

        # Rozmiar większy dla zakładek. Zakładka "Punkty historyczne" ma
        # dwupanelowy edytor zdjęć (Priorytet 3.1), więc 700px powodowało
        # ściskanie kolumn i ucinanie nagłówków/przycisków.
        # Przy skali Windows 175% lepiej powiększyć okno niż zmniejszać czcionki.
        # scale_window ogranicza rozmiar do ekranu, więc dialog nie powinien
        # wyjść poza pulpit, a UI zostaje czytelne i spójne z resztą aplikacji.
        ui_scale, win_w, win_h = scale_window(self, parent, 900, 680)
        # Przy 150-175% skali Windows tkinterowe kontrolki robią się bardzo
        # szerokie. Nie blokuj wtedy ręcznego zmniejszania okna ogromnym
        # minsize i otwórz dialog zmaksymalizowany, żeby cała treść była
        # dostępna bez ucinania.
        self.minsize(min(win_w, 900), min(win_h, 620))
        self.resizable(True, True)
        self._center_window()

        # Główny kontener
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Notebook (zakładki)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # === ZAKLADKA 1: Podstawowe dane ===
        basic_frame = ttk.Frame(notebook, padding="20")
        notebook.add(basic_frame, text="Podstawowe")

        ttk.Label(basic_frame, text="Nazwa (folder):").grid(row=0, column=0, sticky="w", pady=5)
        self.name_entry = ttk.Entry(basic_frame, width=50)
        self.name_entry.insert(0, name)
        self.name_entry.grid(row=0, column=1, pady=5, padx=10, sticky="ew")

        ttk.Label(basic_frame, text="Pełna nazwa:").grid(row=1, column=0, sticky="w", pady=5)
        self.full_name_entry = ttk.Entry(basic_frame, width=50)
        self.full_name_entry.insert(0, full_name)
        self.full_name_entry.grid(row=1, column=1, pady=5, padx=10, sticky="ew")

        ttk.Label(basic_frame, text="Powiat:").grid(row=2, column=0, sticky="w", pady=5)
        self.powiat_entry = ttk.Entry(basic_frame, width=50)
        self.powiat_entry.insert(0, powiat)
        self.powiat_entry.grid(row=2, column=1, pady=5, padx=10, sticky="ew")

        ttk.Label(basic_frame, text="Region:").grid(row=3, column=0, sticky="w", pady=5)
        self.region_entry = ttk.Entry(basic_frame, width=50)
        self.region_entry.insert(0, region)
        self.region_entry.grid(row=3, column=1, pady=5, padx=10, sticky="ew")

        # NOWE POLE: Baza danych PostgreSQL
        ttk.Label(basic_frame, text="Baza danych:").grid(row=4, column=0, sticky="w", pady=5)

        # Pobierz listę dostępnych baz PostgreSQL
        available_dbs = self.get_available_databases()

        # Jeśli postgres_db_name jest podane ale nie ma go w liście, dodaj do listy
        # (może być sytuacja gdy baza istnieje ale nie została wykryta)
        if postgres_db_name and postgres_db_name not in available_dbs:
            # Wstaw przed opcja "(nowa baza...)"
            available_dbs.insert(-1, postgres_db_name)

        self.db_combo = ttk.Combobox(basic_frame, width=47, state="readonly")
        self.db_combo['values'] = available_dbs

        # Ustaw domyślną wartość
        if postgres_db_name:
            # Jeśli jest postgres_db_name, użyj go
            self.db_combo.set(postgres_db_name)
        elif available_dbs:
            # Jeśli brak wartości, zaproponuj bazę na podstawie nazwy miejscowości
            if name:
                suggested_db = f"mapa_{name.lower()}_db"
                if suggested_db in available_dbs:
                    self.db_combo.set(suggested_db)
                else:
                    self.db_combo.set(available_dbs[0])
            else:
                self.db_combo.set(available_dbs[0])

        self.db_combo.grid(row=4, column=1, pady=5, padx=10, sticky="ew")

        # Dodaj przycisk odświeżania listy baz
        refresh_btn = ttk.Button(basic_frame, text="🔄 ", width=3,
                                command=self.refresh_databases)
        refresh_btn.grid(row=4, column=2, pady=5, padx=(0, 10))

        ttk.Label(basic_frame, text="Rok mapy:").grid(row=5, column=0, sticky="w", pady=5)
        self.year_entry = ttk.Entry(basic_frame, width=50)
        self.year_entry.insert(0, year)
        self.year_entry.grid(row=5, column=1, pady=5, padx=10, sticky="ew")

        ttk.Label(basic_frame, text="Wiek (np. XIX w.):").grid(row=6, column=0, sticky="w", pady=5)
        self.century_entry = ttk.Entry(basic_frame, width=50)
        self.century_entry.insert(0, century)
        self.century_entry.grid(row=6, column=1, pady=5, padx=10, sticky="ew")

        basic_frame.columnconfigure(1, weight=1)

        # === ZAKŁADKA 2: Protokół ===
        protokol_frame = ttk.Frame(notebook, padding="20")
        notebook.add(protokol_frame, text="Protokół")

        ttk.Label(protokol_frame, text="Gmina katastralna:").grid(row=0, column=0, sticky="w", pady=5)
        self.gmina_katastralna_entry = ttk.Entry(protokol_frame, width=50)
        self.gmina_katastralna_entry.insert(0, gmina_katastralna)
        self.gmina_katastralna_entry.grid(row=0, column=1, pady=5, padx=10, sticky="ew")

        ttk.Label(protokol_frame, text="Numery protokołów żydowskich:").grid(row=1, column=0, sticky="w", pady=5)
        self.jewish_protocols_entry = ttk.Entry(protokol_frame, width=50)
        self.jewish_protocols_entry.insert(0, jewish_protocol_numbers)
        self.jewish_protocols_entry.grid(row=1, column=1, pady=5, padx=10, sticky="ew")

        # Info
        info_label = ttk.Label(protokol_frame,
                               text="Gmina katastralna: używana w tytule protokołu.\n"
                                    "Numery protokołów żydowskich: oddzielone przecinkami, np: 12,45,67\n\n"
                                    "💡 Powierzchnia miejscowości jest automatycznie obliczana\n"
                                    "    z wyrysowanego obrysu w edytorze działek.",
                               foreground="gray", wraplength=scale_wrap(self, 500))
        info_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=15)

        protokol_frame.columnconfigure(1, weight=1)

        # === ZAKŁADKA 3: Strona główna ===
        homepage_frame = ttk.Frame(notebook, padding="20")
        notebook.add(homepage_frame, text="Strona")

        # Wybór szablonu
        template_selection_frame = ttk.Frame(homepage_frame)
        template_selection_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(template_selection_frame, text="Szablon strony głównej:").pack(side=tk.LEFT, padx=(0, 10))

        self.homepage_template_var = tk.StringVar(
            value=self.HOMEPAGE_TEMPLATE_LABELS.get(homepage_template, homepage_template)
        )
        self.template_combo = ttk.Combobox(template_selection_frame,
                                          textvariable=self.homepage_template_var,
                                          values=list(self.HOMEPAGE_TEMPLATE_LABELS.values()),
                                          state="readonly", width=30)
        self.template_combo.pack(side=tk.LEFT)
        self.template_combo.bind("<<ComboboxSelected>>", self.on_template_change)

        # Frame dla opisu (pokazywany/ukrywany w zależności od szablonu)
        self.homepage_desc_frame = ttk.Frame(homepage_frame)
        self.homepage_desc_frame.pack(fill=tk.BOTH, expand=True)

        self.homepage_desc_label = ttk.Label(self.homepage_desc_frame, text="Opis strony głównej:")
        self.homepage_desc_label.pack(anchor="w", pady=(0, 5))

        self.homepage_desc_text = scrolledtext.ScrolledText(
            self.homepage_desc_frame, width=60, height=8, wrap=tk.WORD
        )
        self.homepage_desc_text.insert("1.0", homepage_description)
        self.homepage_desc_text.pack(fill=tk.BOTH, expand=True)

        # Info o szablonie inżynierskim
        self.template_info_label = ttk.Label(homepage_frame,
                                            text="Szablon 'praca inżynierska' ma stały wygląd i nie jest modyfikowalny.",
                                            foreground="gray", wraplength=scale_wrap(self, 500))

        # Pokaż/ukryj opis w zależności od szablonu
        self.update_template_visibility()

        # === ZAKLADKA 4: Historia ===
        history_frame = ttk.Frame(notebook, padding="20")
        notebook.add(history_frame, text="Historia")

        ttk.Label(history_frame, text="Akapit 1 (pochodzenie miejscowości):").pack(anchor="w", pady=(0, 5))
        self.history_p1_text = scrolledtext.ScrolledText(history_frame, width=60, height=5, wrap=tk.WORD)
        self.history_p1_text.insert("1.0", history_paragraph1)
        self.history_p1_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ttk.Label(history_frame, text="Akapit 2 (rozwój, kolej):").pack(anchor="w", pady=(0, 5))
        self.history_p2_text = scrolledtext.ScrolledText(history_frame, width=60, height=5, wrap=tk.WORD)
        self.history_p2_text.insert("1.0", history_paragraph2)
        self.history_p2_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ttk.Label(history_frame, text="Akapit 3 (statystyki 1882):").pack(anchor="w", pady=(0, 5))
        self.history_p3_text = scrolledtext.ScrolledText(history_frame, width=60, height=4, wrap=tk.WORD)
        self.history_p3_text.insert("1.0", history_paragraph3)
        self.history_p3_text.pack(fill=tk.BOTH, expand=True)

        # === ZAKŁADKA 5: Zdjęcia historyczne ===
        self._build_history_photos_tab(notebook)

        # === ZAKŁADKA 6: Punkty historyczne ===
        self._build_historical_points_tab(notebook)

        # Przyciski
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(buttons_frame, text="✅ Zapisz", command=self.save,
                  style="Success.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="❌ Anuluj", command=self.destroy,
                  style="Danger.TButton").pack(side=tk.LEFT, padx=5)

    def _center_window(self):
        """Centruje okno na ekranie."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    def _maximize_for_large_scale(self):
        """Maksymalizuje dialog na dużej skali DPI, jeśli system na to pozwala."""
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass

    def get_available_databases(self):
        """
        Pobiera listę dostępnych baz danych PostgreSQL (mapa_*_db).
        """
        if is_sqlite_mode():
            return ["czarna.db", "(SQLite lokalnie)"]

        databases = []

        # Sprawdź czy PostgreSQL jest dostępny
        if check_postgres_available():
            try:
                config = get_postgres_config()
                pg_dbs = list_databases(config)

                # Filtruj tylko bazy zaczynające się od "mapa_"
                map_dbs = [db for db in pg_dbs if db.startswith('mapa_') and db != 'mapa_launcher_db']
                databases.extend(sorted(map_dbs))
            except Exception as e:
                print(f"❌ Błąd pobierania listy baz: {e}")

        # Dodaj opcję tworzenia nowej bazy
        databases.append(self.NEW_DB_LABEL)
        return databases

    def refresh_databases(self):
        """Odświeża listę dostępnych baz danych."""
        current_value = self.db_combo.get()
        available_dbs = self.get_available_databases()
        self.db_combo['values'] = available_dbs

        # Przywróć wartość jeśli istnieje
        if current_value in available_dbs:
            self.db_combo.set(current_value)
        elif available_dbs:
            self.db_combo.set(available_dbs[0])

    def on_template_change(self, event=None):
        """Wywoływana gdy zmieni się wybór szablonu."""
        self.update_template_visibility()

    def update_template_visibility(self):
        """Pokazuje/ukrywa pole opisu w zależności od wybranego szablonu."""
        template = self.HOMEPAGE_TEMPLATE_VALUES.get(
            self.homepage_template_var.get(),
            self.homepage_template_var.get(),
        )

        if template == "standardowy":
            # Pokaż pole opisu
            self.homepage_desc_frame.pack(fill=tk.BOTH, expand=True)
            self.template_info_label.pack_forget()
        else:
            # Ukryj pole opisu, pokaż info
            self.homepage_desc_frame.pack_forget()
            self.template_info_label.pack(anchor="w", pady=(0, 10))

    def _build_history_photos_tab(self, notebook):
        """Zakładka do zarządzania zdjęciami historycznymi bez osobnego okna."""
        photos_frame = ttk.Frame(notebook, padding="10")
        notebook.add(photos_frame, text="Zdjęcia")
        photos_frame.columnconfigure(0, weight=1)
        photos_frame.rowconfigure(1, weight=1)

        ttk.Label(
            photos_frame,
            text="Zdjęcia historyczne wyświetlane na stronie Historia. Dwuklik otwiera zdjęcie.",
            foreground="gray",
            wraplength=scale_wrap(self, 700),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 6))

        list_frame = ttk.Frame(photos_frame)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        yscroll = ttk.Scrollbar(list_frame)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.history_photos_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=yscroll.set,
            xscrollcommand=xscroll.set,
            height=12,
            exportselection=False,
        )
        self.history_photos_listbox.grid(row=0, column=0, sticky="nsew")
        yscroll.config(command=self.history_photos_listbox.yview)
        xscroll.config(command=self.history_photos_listbox.xview)
        self.history_photos_listbox.bind("<Double-1>", self.open_history_photo)

        self.photos_count_label = ttk.Label(photos_frame, foreground="gray")
        self.photos_count_label.grid(row=2, column=0, sticky="w", pady=(6, 0))

        buttons = ttk.Frame(photos_frame)
        buttons.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        for col in range(6):
            buttons.columnconfigure(col, weight=1)
        ttk.Button(buttons, text="➕ Dodaj", command=self.add_history_photo).grid(row=0, column=0, sticky="ew", padx=3)
        ttk.Button(buttons, text="👁️ Otwórz", command=self.open_history_photo).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(buttons, text="✏️ Podpis", command=self.edit_history_photo_caption).grid(row=0, column=2, sticky="ew", padx=3)
        ttk.Button(buttons, text="🗑️ Usuń", command=self.delete_history_photo).grid(row=0, column=3, sticky="ew", padx=3)
        ttk.Button(buttons, text="⬆️ Góra", command=lambda: self.move_history_photo(-1)).grid(row=0, column=4, sticky="ew", padx=3)
        ttk.Button(buttons, text="⬇️ Dół", command=lambda: self.move_history_photo(+1)).grid(row=0, column=5, sticky="ew", padx=3)

        self.refresh_history_photos_list()

    def _history_photos_dir(self):
        """Folder ``history_photos`` dla aktualnej miejscowości."""
        location_name = self.name_entry.get().strip() or "Czarna"
        return BASE_DIR / "data" / "locations" / location_name / "history_photos"

    def refresh_history_photos_list(self):
        """Odświeża listę zdjęć historycznych w zakładce Zdjęcia."""
        self.history_photos_listbox.delete(0, tk.END)
        for i, photo in enumerate(self.history_photos, 1):
            filename = photo.get("filename", "")
            caption = photo.get("caption", "")
            self.history_photos_listbox.insert(tk.END, f"{i}. {filename} — {caption}")
        self.photos_count_label.config(text=f"Obecnie: {len(self.history_photos)}/20 zdjęć")

    def _selected_history_photo_index(self):
        selection = self.history_photos_listbox.curselection()
        if not selection:
            messagebox.showinfo("Brak wyboru", "Wybierz zdjęcie z listy.", parent=self)
            return None
        return selection[0]

    def add_history_photo(self):
        """Dodaje zdjęcie historyczne do folderu miejscowości i listy."""
        if len(self.history_photos) >= 20:
            messagebox.showwarning("Limit zdjęć", "Możesz dodać maksymalnie 20 zdjęć.", parent=self)
            return
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Wybierz zdjęcie historyczne",
            filetypes=[("Pliki graficzne", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("Wszystkie pliki", "*.*")],
        )
        if not file_path:
            return

        original_filename = os.path.basename(file_path)
        name_without_ext, extension = os.path.splitext(original_filename)
        new_name = simpledialog.askstring(
            "Nazwa pliku",
            "Podaj nazwę dla tego zdjęcia (bez rozszerzenia):",
            initialvalue=name_without_ext,
            parent=self,
        )
        if not new_name:
            return
        new_filename = f"{new_name}{extension}"
        caption = self._ask_photo_caption("Podpis zdjęcia", "Podaj podpis do zdjęcia:")
        if not caption:
            caption = "Zdjęcie historyczne"

        photos_dir = self._history_photos_dir()
        photos_dir.mkdir(parents=True, exist_ok=True)
        dest_path = photos_dir / new_filename
        if dest_path.exists() and not messagebox.askyesno(
            "Plik istnieje",
            f"Plik {new_filename} już istnieje. Czy nadpisać?",
            parent=self,
        ):
            return
        try:
            shutil.copy2(file_path, dest_path)
        except Exception as exc:
            messagebox.showerror("Błąd", f"Nie udało się skopiować pliku:\n{exc}", parent=self)
            return

        self.history_photos.append({"filename": new_filename, "caption": caption})
        self.refresh_history_photos_list()
        self.history_photos_listbox.selection_set(tk.END)
        self.history_photos_listbox.see(tk.END)

    def open_history_photo(self, _event=None):
        """Otwiera zaznaczone zdjęcie w domyślnym programie Windows."""
        idx = self._selected_history_photo_index()
        if idx is None:
            return
        photo = self.history_photos[idx]
        file_path = self._history_photos_dir() / photo.get("filename", "")
        if not file_path.exists():
            messagebox.showerror("Brak pliku", f"Nie znaleziono pliku:\n{file_path}", parent=self)
            return
        try:
            os.startfile(file_path)
        except Exception as exc:
            messagebox.showerror("Błąd", f"Nie udało się otworzyć zdjęcia:\n{exc}", parent=self)

    def edit_history_photo_caption(self):
        """Edytuje podpis zaznaczonego zdjęcia."""
        idx = self._selected_history_photo_index()
        if idx is None:
            return
        photo = self.history_photos[idx]
        new_caption = self._ask_photo_caption(
            "Edytuj podpis",
            "Podaj nowy podpis:",
            initialvalue=photo.get("caption", ""),
        )
        if new_caption is not None:
            photo["caption"] = new_caption
            self.refresh_history_photos_list()
            self.history_photos_listbox.selection_set(idx)

    def _ask_photo_caption(self, title, prompt, initialvalue=""):
        """Duże okno edycji podpisu zdjęcia zamiast małego simpledialog."""
        dialog = tk.Toplevel(self)
        dialog.title(title)
        set_dialog_icon(dialog)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(True, True)
        dialog.geometry("720x260")
        dialog.minsize(520, 220)
        self._center_child_dialog(dialog, 720, 260)

        result = {"value": None}
        frame = ttk.Frame(dialog, padding="12")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=prompt).pack(anchor="w", pady=(0, 6))
        text = scrolledtext.ScrolledText(frame, height=5, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert("1.0", initialvalue or "")
        text.focus_set()

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(10, 0))

        def ok():
            result["value"] = text.get("1.0", tk.END).strip()
            dialog.destroy()

        def cancel():
            result["value"] = None
            dialog.destroy()

        ttk.Button(buttons, text="OK", command=ok).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(buttons, text="Anuluj", command=cancel).pack(side=tk.RIGHT)
        dialog.bind("<Control-Return>", lambda _event: ok())
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.wait_window(dialog)
        return result["value"]

    def _center_child_dialog(self, dialog, width, height):
        """Centruje małe okno pomocnicze względem dialogu edycji miejscowości."""
        self.update_idletasks()
        dialog.update_idletasks()
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_w = max(self.winfo_width(), 1)
        parent_h = max(self.winfo_height(), 1)
        x = parent_x + (parent_w - width) // 2
        y = parent_y + (parent_h - height) // 2
        x = max(0, x)
        y = max(0, y)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

    def delete_history_photo(self):
        """Usuwa zaznaczone zdjęcie z listy i dysku."""
        idx = self._selected_history_photo_index()
        if idx is None:
            return
        photo = self.history_photos[idx]
        filename = photo.get("filename", "")
        if not messagebox.askyesno(
            "Potwierdź usunięcie",
            f"Czy na pewno usunąć zdjęcie:\n{filename}?\n\nPlik zostanie trwale usunięty z folderu.",
            parent=self,
        ):
            return
        file_path = self._history_photos_dir() / filename
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as exc:
            messagebox.showerror("Błąd", f"Nie udało się usunąć pliku:\n{exc}", parent=self)
            return
        del self.history_photos[idx]
        self.refresh_history_photos_list()

    def move_history_photo(self, delta):
        """Przesuwa zaznaczone zdjęcie w kolejności galerii."""
        idx = self._selected_history_photo_index()
        if idx is None:
            return
        new_idx = idx + delta
        if not (0 <= new_idx < len(self.history_photos)):
            return
        self.history_photos[idx], self.history_photos[new_idx] = self.history_photos[new_idx], self.history_photos[idx]
        self.refresh_history_photos_list()
        self.history_photos_listbox.selection_set(new_idx)
        self.history_photos_listbox.see(new_idx)

    def _build_historical_points_tab(self, notebook):
        """Nowe, kompaktowe GUI zakładki 'Punkty'.

        Układ jest celowo prosty: lewa kolumna to lista punktów i akcje,
        prawa kolumna to formularz + edytor zdjęć. Nie ma długich opisów ani
        wielkich paneli, więc okno lepiej mieści się przy skali Windows 175%.
        """
        hp_frame = ttk.Frame(notebook, padding="4")
        notebook.add(hp_frame, text="Punkty")
        hp_frame.columnconfigure(0, weight=1)
        hp_frame.rowconfigure(0, weight=1)

        # Treeview przy skali Windows 175% potrafi ucinać dolne części liter
        # (np. „j”, „g”, „y”), bo domyślna wysokość wiersza jest za mała.
        hp_style = ttk.Style(self)
        hp_style.configure("HistoricalPoints.Treeview", rowheight=38)
        hp_style.configure("HistoricalPoints.Treeview.Heading", padding=(4, 6))

        # --- TRYB 1: sama lista punktów ---
        list_frame = ttk.LabelFrame(hp_frame, text="Punkty", padding="3")
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.hp_list_frame = list_frame

        list_scroll = ttk.Scrollbar(list_frame)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.hp_tree = ttk.Treeview(
            list_frame,
            columns=("point",),
            show="headings",
            selectmode="browse",
            yscrollcommand=list_scroll.set,
            style="HistoricalPoints.Treeview",
            height=14,
        )
        self.hp_tree.heading("point", text="Punkt")
        self.hp_tree.column("point", width=520, minwidth=240, anchor="w")
        self.hp_tree.grid(row=0, column=0, sticky="nsew")
        list_scroll.config(command=self.hp_tree.yview)
        self.hp_tree.bind("<<TreeviewSelect>>", self._on_hp_select)
        self.hp_tree.bind("<Double-1>", lambda _event: self._on_hp_edit_selected())

        hp_buttons = ttk.Frame(list_frame)
        hp_buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        ttk.Button(hp_buttons, text="➕ Nowy punkt", command=self._on_hp_new).pack(side=tk.LEFT, padx=2)
        ttk.Button(hp_buttons, text="✏️ Edytuj", command=self._on_hp_edit_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(hp_buttons, text="🗑️ Usuń", command=self._on_hp_delete).pack(side=tk.LEFT, padx=2)

        # --- TRYB 2: formularz edycji punktu ---
        form_frame = ttk.LabelFrame(hp_frame, text="Edycja punktu", padding="3")
        form_frame.grid(row=0, column=0, sticky="nsew")
        self.hp_edit_frame = form_frame
        form_frame.columnconfigure(1, weight=1)
        form_frame.rowconfigure(5, weight=1)

        edit_buttons = ttk.Frame(form_frame)
        edit_buttons.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        ttk.Button(edit_buttons, text="← Wróć do listy", command=self._show_hp_list_mode).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_buttons, text="💾 Zapisz punkt", command=self._on_hp_save).pack(side=tk.LEFT, padx=2)

        ttk.Label(form_frame, text="Obiekt*").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=1)
        self.hp_object_combo = ttk.Combobox(form_frame, state="readonly", width=24)
        self.hp_object_combo.grid(row=1, column=1, sticky="ew", pady=1)

        ttk.Label(form_frame, text="Nazwa").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=1)
        self.hp_display_entry = ttk.Entry(form_frame, width=24)
        self.hp_display_entry.grid(row=2, column=1, sticky="ew", pady=1)

        ttk.Label(form_frame, text="Opis").grid(row=3, column=0, sticky="nw", padx=(0, 4), pady=1)
        self.hp_desc_text = scrolledtext.ScrolledText(form_frame, width=24, height=4, wrap=tk.WORD)
        self.hp_desc_text.grid(row=3, column=1, sticky="ew", pady=1)

        ttk.Label(form_frame, text="Źródło").grid(row=4, column=0, sticky="nw", padx=(0, 4), pady=1)
        self.hp_source_entry = scrolledtext.ScrolledText(form_frame, width=24, height=3, wrap=tk.WORD)
        self.hp_source_entry.grid(row=4, column=1, sticky="ew", pady=1)

        self._build_hp_photos_widgets(form_frame)

        # Stan: lista zdjęć bieżącego punktu (ładowana przy zaznaczeniu / _on_hp_new).
        # Każdy element: ``{"filename": str, "caption": str}``.
        self.hp_point_photos: list[dict] = []
        # Synchronizacja caption -> hp_point_photos (wyłączamy, gdy programowo ustawiamy Entry).
        self._hp_caption_sync_active = True

        # ID edytowanego punktu (None = nowy)
        self.hp_current_id = None

        # Wypełnij listę kandydatów (z parcels_data.json) i listę zdjęć
        self._refresh_hp_candidates()
        self._refresh_hp_photo_files()
        # Wypełnij listę punktów z danych przekazanych do dialogu
        # (lokalizacja musi już istnieć - dla "Dodaj nową" lista jest pusta).
        location_name = self.name_entry.get().strip() or None
        if location_name and not self.historical_points_data:
            try:
                loaded = load_historical_points(location_name)
                self.historical_points_data = [p.to_dict() for p in loaded]
            except Exception:
                self.historical_points_data = []
        self._refresh_hp_list()
        self._show_hp_list_mode()

    def _build_hp_photos_widgets(self, parent):
        """Kompaktowy edytor plików punktu historycznego."""
        outer = ttk.LabelFrame(parent, text="Zdjęcia", padding="3")
        outer.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(3, 0))
        outer.columnconfigure(0, weight=1, uniform="hp_photos")
        outer.columnconfigure(2, weight=1, uniform="hp_photos")
        outer.rowconfigure(0, weight=1)

        # --- LEWA: pliki na dysku ---
        left_lf = ttk.LabelFrame(outer, text="Dostępne", padding="3")
        left_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left_lf.columnconfigure(0, weight=1)
        left_lf.rowconfigure(0, weight=1)

        left_scroll = ttk.Scrollbar(left_lf)
        left_scroll.grid(row=0, column=1, sticky="ns")
        self.hp_files_listbox = tk.Listbox(
            left_lf, selectmode=tk.EXTENDED, height=3,
            yscrollcommand=left_scroll.set,
            exportselection=False,
        )
        self.hp_files_listbox.grid(row=0, column=0, sticky="nsew")
        left_scroll.config(command=self.hp_files_listbox.yview)

        self.hp_files_status_var = tk.StringVar(value="Dostępne: 0")
        ttk.Label(
            left_lf,
            textvariable=self.hp_files_status_var,
            foreground="gray",
            wraplength=scale_wrap(self, 140),
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))

        left_file_buttons = ttk.Frame(left_lf)
        left_file_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        ttk.Button(
            left_file_buttons,
            text="➕",
            width=3,
            command=self._hp_import_point_photos,
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            left_file_buttons,
            text="🗑️",
            width=3,
            command=self._hp_delete_selected_photo_file,
        ).pack(side=tk.LEFT)

        # --- ŚRODEK: przyciski przenoszenia ---
        mid_frame = ttk.Frame(outer)
        mid_frame.grid(row=0, column=1, sticky="ns", padx=2)
        ttk.Button(mid_frame, text="→", width=3,
                   command=self._hp_add_to_point).pack(pady=2)
        ttk.Button(mid_frame, text="←", width=3,
                   command=self._hp_remove_from_point).pack(pady=2)

        # --- PRAWA: drzewo zdjęć punktu + podpis + reorder ---
        right_lf = ttk.LabelFrame(outer, text="Przypisane", padding="3")
        right_lf.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        right_lf.columnconfigure(0, weight=1)
        right_lf.rowconfigure(0, weight=1)

        right_scroll = ttk.Scrollbar(right_lf)
        right_scroll.grid(row=0, column=1, sticky="ns")
        right_xscroll = ttk.Scrollbar(right_lf, orient=tk.HORIZONTAL)
        right_xscroll.grid(row=1, column=0, sticky="ew")
        self.hp_point_photos_tree = ttk.Treeview(
            right_lf, columns=("idx", "filename", "caption"),
            show="headings", selectmode="browse",
            yscrollcommand=right_scroll.set,
            xscrollcommand=right_xscroll.set,
            style="HistoricalPoints.Treeview",
            height=3,
        )
        self.hp_point_photos_tree.heading("idx", text="#")
        self.hp_point_photos_tree.heading("filename", text="Plik")
        self.hp_point_photos_tree.heading("caption", text="Podpis")
        self.hp_point_photos_tree.column("idx", width=30, minwidth=30, stretch=False, anchor="center")
        self.hp_point_photos_tree.column("filename", width=220, minwidth=140, stretch=True, anchor="w")
        self.hp_point_photos_tree.column("caption", width=420, minwidth=220, stretch=True, anchor="w")
        self.hp_point_photos_tree.grid(row=0, column=0, sticky="nsew")
        right_scroll.config(command=self.hp_point_photos_tree.yview)
        right_xscroll.config(command=self.hp_point_photos_tree.xview)
        self.hp_point_photos_tree.bind("<<TreeviewSelect>>", self._on_hp_photo_select)

        # Podpis (Caption) dla zaznaczonego zdjęcia
        cap_frame = ttk.Frame(right_lf)
        cap_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 1))
        cap_frame.columnconfigure(1, weight=1)
        ttk.Label(cap_frame, text="Podpis:").grid(row=0, column=0, sticky="w")
        self.hp_caption_var = tk.StringVar()
        self.hp_caption_entry = ttk.Entry(cap_frame, textvariable=self.hp_caption_var)
        self.hp_caption_entry.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        # Synchronizacja Entry -> hp_point_photos
        self.hp_caption_var.trace_add("write", self._hp_sync_caption_to_data)

        # Przyciski reorder + usuń
        btns = ttk.Frame(right_lf)
        btns.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        ttk.Button(btns, text="▲", width=3,
                   command=lambda: self._hp_move_photo(-1)).pack(side=tk.LEFT, padx=1)
        ttk.Button(btns, text="▼", width=3,
                   command=lambda: self._hp_move_photo(+1)).pack(side=tk.LEFT, padx=1)
        ttk.Button(btns, text="🗑️ Lista",
                    command=self._hp_remove_from_point).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="🗑️ Plik",
                   command=self._hp_delete_selected_photo_file).pack(side=tk.LEFT, padx=4)


    def _show_hp_list_mode(self):
        """Pokazuje tylko tabelę punktów (tryb przeglądania)."""
        if hasattr(self, "hp_edit_frame"):
            self.hp_edit_frame.grid_remove()
        if hasattr(self, "hp_list_frame"):
            self.hp_list_frame.grid()

    def _show_hp_edit_mode(self):
        """Pokazuje formularz edycji punktu na pełną szerokość zakładki."""
        if hasattr(self, "hp_list_frame"):
            self.hp_list_frame.grid_remove()
        if hasattr(self, "hp_edit_frame"):
            self.hp_edit_frame.grid()

    def _on_hp_edit_selected(self):
        """Przechodzi do edycji zaznaczonego punktu."""
        sel = self.hp_tree.selection()
        if not sel:
            messagebox.showwarning(
                "⚠️ Brak zaznaczenia",
                "Wybierz punkt z tabeli albo kliknij 'Nowy punkt'.",
                parent=self,
            )
            return
        self._on_hp_select()
        self._show_hp_edit_mode()


    def _refresh_hp_candidates(self):
        """Ładuje kandydatów do comboboxa z parcels_data.json aktywnej miejscowości."""
        location_name = self.name_entry.get().strip()
        self._hp_candidate_map = {}
        if not location_name:
            self.hp_object_combo["values"] = []
            return
        try:
            objects = list_special_objects(location_name)
        except Exception:
            objects = []
        # Wartość comboboxa: "nazwa | 50.06, 21.25" (ludzka etykieta)
        values = [f"{obj.object_name}  ({obj.lat:.4f}, {obj.lng:.4f})" for obj in objects]
        self.hp_object_combo["values"] = values
        # Zapamiętaj mapowanie etykieta -> object_name dla późniejszego odczytu
        self._hp_candidate_map = {f"{obj.object_name}  ({obj.lat:.4f}, {obj.lng:.4f})": obj.object_name for obj in objects}

    def _hp_import_point_photos(self):
        """Kopiuje wybrane pliki graficzne do folderu ``point_photos``."""
        location_name = self.name_entry.get().strip()
        if not location_name:
            messagebox.showwarning(
                "⚠️ Brak miejscowości",
                "Najpierw wpisz nazwę miejscowości w zakładce Podstawowe.",
                parent=self,
            )
            return
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Dodaj zdjęcia punktów historycznych",
            filetypes=(
                ("Pliki graficzne", "*.jpg *.jpeg *.png *.webp *.gif"),
                ("Wszystkie pliki", "*.*"),
            ),
        )
        if not paths:
            return
        target_dir = get_point_photos_dir(location_name)
        target_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        skipped = 0
        for source in paths:
            src = getattr(source, "__fspath__", lambda: source)()
            filename = src.split("/")[-1].split("\\")[-1]
            target = target_dir / filename
            if target.exists():
                if not messagebox.askyesno(
                    "Plik już istnieje",
                    f"Plik '{filename}' już istnieje w point_photos. Nadpisać?",
                    parent=self,
                ):
                    skipped += 1
                    continue
            try:
                shutil.copy2(src, target)
                copied += 1
            except Exception as exc:
                messagebox.showerror("❌ Błąd", f"Nie udało się dodać pliku '{filename}':\n{exc}", parent=self)
        self._refresh_hp_photo_files()
        if copied or skipped:
            messagebox.showinfo(
                "Gotowe",
                f"Dodano plików: {copied}\nPominięto: {skipped}",
                parent=self,
            )

    def _hp_selected_photo_filenames(self):
        """Zwraca nazwy plików zaznaczone po lewej albo po prawej stronie."""
        left_sel = self.hp_files_listbox.curselection()
        if left_sel:
            return [self.hp_files_listbox.get(i) for i in left_sel]
        right_sel = self.hp_point_photos_tree.selection()
        filenames = []
        for item in right_sel:
            try:
                idx = int(item)
            except ValueError:
                continue
            if 0 <= idx < len(self.hp_point_photos):
                filenames.append(self.hp_point_photos[idx].get("filename", ""))
        return [f for f in filenames if f]

    def _hp_delete_selected_photo_file(self):
        """Usuwa zaznaczony plik z folderu ``point_photos`` i list punktów."""
        location_name = self.name_entry.get().strip()
        if not location_name:
            return
        filenames = self._hp_selected_photo_filenames()
        if not filenames:
            messagebox.showwarning(
                "⚠️ Brak zaznaczenia",
                "Zaznacz plik w 'Dostępne pliki' albo zdjęcie w 'Zdjęcia punktu'.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "🗑️ Usuń plik",
            "Usunąć zaznaczone pliki z folderu point_photos?\n"
            "Zostaną też odpięte od punktów historycznych.",
            parent=self,
        ):
            return
        target_dir = get_point_photos_dir(location_name)
        removed = 0
        for filename in filenames:
            try:
                path = target_dir / filename
                if path.exists() and path.is_file():
                    path.unlink()
                    removed += 1
            except Exception as exc:
                messagebox.showerror("❌ Błąd", f"Nie udało się usunąć '{filename}':\n{exc}", parent=self)
        names = set(filenames)
        self.hp_point_photos = [p for p in self.hp_point_photos if p.get("filename") not in names]
        for point in self.historical_points_data:
            photos = point.get("photos") or []
            point["photos"] = [p for p in photos if not isinstance(p, dict) or p.get("filename") not in names]
        self._refresh_hp_point_photos()
        self._refresh_hp_photo_files()
        if removed:
            messagebox.showinfo("Gotowe", f"Usunięto plików: {removed}", parent=self)

    def _refresh_hp_photo_files(self):
        """Ładuje pliki graficzne z point_photos/ do listboxa (markery).

        Zdjęcia markerów (przypisywane do punktów historycznych) są w OSOBNYM
        folderze ``point_photos/`` - nie w galerii ``history_photos/``. Dzięki
        temu w lewym listboxie widać tylko pliki kandydatów do przypisania
        (bez śmieci z galerii miejscowości).

        Dodatkowo filtruje pliki już przypisane do bieżącego punktu
        (``self.hp_point_photos``) - są one widoczne w prawym panelu
        "Zdjęcia teg..." więc nie trzeba ich pokazywać ponownie w lewym.
        (Priorytet 3.1 + refaktor folderów.)
        """
        location_name = self.name_entry.get().strip()
        if not location_name:
            files = []
        else:
            try:
                files = list_point_photos(location_name)
            except Exception:
                files = []
        # Zbiór plików już użytych w bieżącym punkcie
        used = {p.get("filename") for p in self.hp_point_photos if isinstance(p, dict)}
        # Pokaż tylko nieprzypisane pliki
        available = [f for f in files if f not in used]
        self.hp_files_listbox.delete(0, tk.END)
        for f in available:
            self.hp_files_listbox.insert(tk.END, f)
        if hasattr(self, "hp_files_status_var"):
            if not files:
                self.hp_files_status_var.set(
                    "Brak plików — użyj ➕ Pliki."
                )
            elif not available:
                self.hp_files_status_var.set(
                    f"Dostępne: 0/{len(files)}"
                )
            else:
                self.hp_files_status_var.set(f"Dostępne: {len(available)}/{len(files)}")

    def _refresh_hp_list(self):
        """Przeładowuje Treeview z listą punktów w pamięci."""
        self.hp_tree.delete(*self.hp_tree.get_children())
        for idx, point in enumerate(self.historical_points_data):
            label = point.get("display_name") or point.get("object_name", "")
            self.hp_tree.insert(
                "", "end", iid=str(idx),
                values=(label,),
            )

    def _on_hp_select(self, _event=None):
        """Po zaznaczeniu punktu na liście - ładuje dane do formularza."""
        sel = self.hp_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self.historical_points_data)):
            return
        point = self.historical_points_data[idx]
        self.hp_current_id = idx
        # Combobox - ustaw po kluczu mapy (etykieta "name | lat, lng")
        target = point.get("object_name", "")
        matched = next((label for label, name in self._hp_candidate_map.items() if name == target), None)
        if matched:
            self.hp_object_combo.set(matched)
        else:
            self.hp_object_combo.set(target)  # fallback (gdy obiekt usunięty z parcels)
        self.hp_display_entry.delete(0, tk.END)
        self.hp_display_entry.insert(0, point.get("display_name", ""))
        self.hp_desc_text.delete("1.0", tk.END)
        self.hp_desc_text.insert("1.0", point.get("description", ""))
        self.hp_source_entry.delete("1.0", tk.END)
        self.hp_source_entry.insert("1.0", point.get("source_note", ""))
        # Lista zdjęć punktu (kolejność + podpisy)
        self.hp_point_photos = [dict(p) for p in point.get("photos", []) if isinstance(p, dict)]
        self._refresh_hp_point_photos()
        # Przeładuj lewy listbox plików — ma pokazywać tylko te nieprzypisane
        # do NOWO wybranego punktu (Priorytet 3.1).
        self._refresh_hp_photo_files()

    def _on_hp_new(self):
        """Czyści formularz - tryb 'nowy punkt'."""
        self.hp_current_id = None
        self.hp_tree.selection_remove(self.hp_tree.selection())
        self.hp_object_combo.set("")
        self.hp_display_entry.delete(0, tk.END)
        self.hp_desc_text.delete("1.0", tk.END)
        self.hp_source_entry.delete("1.0", tk.END)
        self.hp_point_photos = []
        self._refresh_hp_point_photos()
        # Dla nowego punktu hp_point_photos jest puste → pokaż WSZYSTKIE pliki
        # w lewym listboxie (Priorytet 3.1).
        self._refresh_hp_photo_files()
        self._show_hp_edit_mode()

    def _on_hp_save(self):
        """Zapisuje aktualny stan formularza do listy (nowy lub aktualizacja).

        :returns: ``True`` gdy zapisano, ``False`` gdy walidacja się nie powiodła
                  (wyświetlono messagebox, dialog pozostaje otwarty).
        """
        label = self.hp_object_combo.get().strip()
        object_name = self._hp_candidate_map.get(label, label).strip()
        display_name = self.hp_display_entry.get().strip()
        description = self.hp_desc_text.get("1.0", tk.END).strip()
        source_note = self.hp_source_entry.get("1.0", tk.END).strip()
        # Zdjęcia z bieżącej listy punktu (z zachowanymi podpisami i kolejnością).
        photos = [dict(p) for p in self.hp_point_photos]

        point = HistoricalPoint(
            object_name=object_name,
            display_name=display_name,
            description=description,
            source_note=source_note,
            photos=photos,
        )
        try:
            point.validate()
        except HistoricalPointValidationError as exc:
            messagebox.showerror("❌ Błąd walidacji", str(exc), parent=self)
            return False

        payload = point.to_dict()
        if self.hp_current_id is None:
            # Nowy punkt
            self.historical_points_data.append(payload)
            new_id = len(self.historical_points_data) - 1
        else:
            # Aktualizacja istniejącego
            self.historical_points_data[self.hp_current_id] = payload
            new_id = self.hp_current_id
        self._refresh_hp_list()
        self.hp_tree.selection_set(str(new_id))
        self.hp_tree.see(str(new_id))
        self._show_hp_list_mode()
        return True

    def _on_hp_delete(self):
        """Usuwa zaznaczony punkt z listy."""
        sel = self.hp_tree.selection()
        if not sel:
            messagebox.showwarning(
                "⚠️ Brak zaznaczenia",
                "Wybierz punkt do usunięcia z listy po lewej stronie.",
                parent=self,
            )
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self.historical_points_data)):
            return
        if not messagebox.askyesno(
            "🗑️ Potwierdzenie",
            f"Czy na pewno usunąć punkt "
            f"'{self.historical_points_data[idx].get('object_name', '?')}'?",
            parent=self,
        ):
            return
        del self.historical_points_data[idx]
        self._on_hp_new()  # czyści formularz
        self._refresh_hp_list()
        self._show_hp_list_mode()

    # --- Zdjęcia punktu (prawa strona formularza) ---

    def _refresh_hp_point_photos(self):
        """Przeładowuje drzewo zdjęć bieżącego punktu z ``self.hp_point_photos``."""
        self.hp_point_photos_tree.delete(*self.hp_point_photos_tree.get_children())
        for idx, photo in enumerate(self.hp_point_photos):
            self.hp_point_photos_tree.insert(
                "", "end", iid=str(idx),
                values=(idx + 1, photo.get("filename", ""), photo.get("caption", "")),
            )
        # Wyczyść pole podpisu (synchronizacja wyłączona, bo to ustawienie programowe).
        self._hp_caption_sync_active = False
        self.hp_caption_var.set("")
        self._hp_caption_sync_active = True

    def _on_hp_photo_select(self, _event=None):
        """Po zaznaczeniu zdjęcia w drzewie - ładuje podpis do Entry."""
        sel = self.hp_point_photos_tree.selection()
        if not sel:
            self._hp_caption_sync_active = False
            self.hp_caption_var.set("")
            self._hp_caption_sync_active = True
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self.hp_point_photos)):
            return
        # Caption -> Entry (bez triggerowania trace, bo to ustawienie programowe)
        self._hp_caption_sync_active = False
        self.hp_caption_var.set(self.hp_point_photos[idx].get("caption", ""))
        self._hp_caption_sync_active = True

    def _hp_sync_caption_to_data(self, *_args):
        """Synchronizuje pole 'Podpis' z listą ``self.hp_point_photos``."""
        if not getattr(self, "_hp_caption_sync_active", True):
            return
        sel = self.hp_point_photos_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.hp_point_photos):
            self.hp_point_photos[idx]["caption"] = self.hp_caption_var.get()
            # Odśwież kolumnę 'caption' w drzewie bez resetowania zaznaczenia.
            self.hp_point_photos_tree.set(str(idx), "caption", self.hp_point_photos[idx]["caption"])

    def _hp_add_to_point(self):
        """Dodaje zaznaczone pliki z listboxa do listy zdjęć bieżącego punktu.

        Duplikaty (ten sam ``filename``) są pomijane. Kolejność dodania
        odpowiada kolejności zaznaczenia w listboxie (kolejność ``curselection()``).
        """
        sel = self.hp_files_listbox.curselection()
        if not sel:
            messagebox.showwarning(
                "⚠️ Brak zaznaczenia",
                "Zaznacz pliki w lewym panelu (Ctrl+klik dla wielu).",
                parent=self,
            )
            return
        existing = {p.get("filename") for p in self.hp_point_photos}
        added = 0
        for i in sel:
            filename = self.hp_files_listbox.get(i)
            if filename in existing:
                continue
            self.hp_point_photos.append({"filename": filename, "caption": ""})
            existing.add(filename)
            added += 1
        if added == 0:
            messagebox.showinfo(
                "ℹ️ Brak zmian",
                "Wszystkie zaznaczone pliki są już na liście punktu.",
                parent=self,
            )
            return
        self._refresh_hp_point_photos()
        self._refresh_hp_photo_files()
        # Zaznacz ostatnio dodane zdjęcie
        last_idx = len(self.hp_point_photos) - 1
        self.hp_point_photos_tree.selection_set(str(last_idx))
        self.hp_point_photos_tree.see(str(last_idx))

    def _hp_remove_from_point(self):
        """Usuwa zaznaczone zdjęcie z listy bieżącego punktu (nie z dysku)."""
        sel = self.hp_point_photos_tree.selection()
        if not sel:
            messagebox.showwarning(
                "⚠️ Brak zaznaczenia",
                "Zaznacz zdjęcie w prawym panelu.",
                parent=self,
            )
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self.hp_point_photos)):
            return
        removed = self.hp_point_photos.pop(idx)
        self._refresh_hp_point_photos()
        # Usunięty plik powinien z powrotem pojawić się w lewym listboxie
        # plików (Priorytet 3.1).
        self._refresh_hp_photo_files()
        # Ustaw zaznaczenie na sąsiednie zdjęcie (lub ostatnie)
        if self.hp_point_photos:
            new_idx = min(idx, len(self.hp_point_photos) - 1)
            self.hp_point_photos_tree.selection_set(str(new_idx))
            self.hp_point_photos_tree.see(str(new_idx))
        # Zachowaj nazwę usuniętego do ewentualnego info
        self._hp_last_removed = removed.get("filename", "")

    def _hp_move_photo(self, delta):
        """Przesuwa zaznaczone zdjęcie o ``delta`` pozycji (-1 w górę, +1 w dół)."""
        sel = self.hp_point_photos_tree.selection()
        if not sel:
            messagebox.showwarning(
                "⚠️ Brak zaznaczenia",
                "Zaznacz zdjęcie w prawym panelu, żeby zmienić kolejność.",
                parent=self,
            )
            return
        idx = int(sel[0])
        new_idx = idx + delta
        if not (0 <= new_idx < len(self.hp_point_photos)):
            return  # już na skraju
        self.hp_point_photos[idx], self.hp_point_photos[new_idx] = (
            self.hp_point_photos[new_idx], self.hp_point_photos[idx],
        )
        self._refresh_hp_point_photos()
        self.hp_point_photos_tree.selection_set(str(new_idx))
        self.hp_point_photos_tree.see(str(new_idx))

    def save(self):
        """Zapisuje dane i zamyka okno."""
        name = self.name_entry.get().strip()
        full_name = self.full_name_entry.get().strip()
        powiat = self.powiat_entry.get().strip()
        region = self.region_entry.get().strip()
        year = self.year_entry.get().strip()
        century = self.century_entry.get().strip()
        postgres_db_name = self.db_combo.get().strip()

        # Pobierz teksty z ScrolledText
        homepage_desc = self.homepage_desc_text.get("1.0", tk.END).strip()
        history_p1 = self.history_p1_text.get("1.0", tk.END).strip()
        history_p2 = self.history_p2_text.get("1.0", tk.END).strip()
        history_p3 = self.history_p3_text.get("1.0", tk.END).strip()

        if not name:
            messagebox.showerror("❌ Błąd", "Nazwa jest wymagana!", parent=self)
            return

        if not full_name:
            messagebox.showerror("❌ Błąd", "Pełna nazwa jest wymagana!", parent=self)
            return

        if not year:
            year = "1882"  # Domyślna wartość

        if not century:
            century = "XIX w."  # Domyślna wartość

        # Obsłuż specjalne wartości bazy danych.
        # W trybie SQLite to pole jest opcjonalne i nie może blokować zapisu miejscowości.
        if is_sqlite_mode():
            if not postgres_db_name or postgres_db_name in (self.NEW_DB_LABEL, self.LEGACY_NEW_DB_LABEL, "(SQLite lokalnie)"):
                postgres_db_name = f"{name.lower()}.db"
        elif postgres_db_name in (self.NEW_DB_LABEL, self.LEGACY_NEW_DB_LABEL):
            # Zaproponuj domyślną nazwę
            suggested_name = f"mapa_{name.lower()}_db"
            new_db_name = simpledialog.askstring(
                "Nazwa bazy danych",
                f"Podaj nazwę nowej bazy danych PostgreSQL:",
                initialvalue=suggested_name,
                parent=self
            )
            if not new_db_name:
                messagebox.showerror("❌ Błąd", "Musisz podać nazwę bazy danych!", parent=self)
                return
            else:
                postgres_db_name = new_db_name.strip()

        # Walidacja - baza PostgreSQL jest wymagana tylko w trybie PostgreSQL
        if not is_sqlite_mode() and not postgres_db_name:
            messagebox.showerror("❌ Błąd", "Musisz wybrać lub utworzyć bazę danych PostgreSQL!", parent=self)
            return

        # Pobierz wybrany szablon
        homepage_template = self.HOMEPAGE_TEMPLATE_VALUES.get(
            self.homepage_template_var.get(),
            self.homepage_template_var.get(),
        )

        # Pobierz wartości protokołu
        gmina_katastralna = self.gmina_katastralna_entry.get().strip()
        jewish_protocols = self.jewish_protocols_entry.get().strip()

        # Ustaw domyślne wartości jeśli puste
        if not gmina_katastralna:
            gmina_katastralna = "Czarna"

        # Powierzchnia (ha i km2) nie jest zapisywana - obliczana automatycznie z obrysu
        # Auto-commit bieżącego stanu formularza punktu (edytowanego LUB świeżo
        # wypełnionego w trybie "Nowy") - inaczej zdjęcia/podpisy trafiają do
        # ``historical_points_data`` dopiero po kliknięciu "Zapisz" na punkcie,
        # a user nie zawsze o tym pamięta. Wywołanie jest idempotentne i bezpieczne
        # - pomijane gdy formularz jest całkowicie pusty (user nie wpisał nic
        # w trybie "Nowy", więc commit nie miałby sensu).
        form_has_data = (
            self.hp_current_id is not None
            or bool(self.hp_point_photos)
            or bool(self.hp_object_combo.get().strip())
            or bool(self.hp_display_entry.get().strip())
            or bool(self.hp_desc_text.get("1.0", tk.END).strip())
            or bool(self.hp_source_entry.get("1.0", tk.END).strip())
        )
        if form_has_data and not self._on_hp_save():
            return  # walidacja bieżącego punktu nie przeszła - dialog zostaje otwarty
        # Walidacja punktów historycznych - żeby user widział błędy przed zapisem
        for idx, raw in enumerate(self.historical_points_data):
            try:
                HistoricalPoint.from_dict(raw).validate()
            except HistoricalPointValidationError as exc:
                messagebox.showerror(
                    "❌ Błąd walidacji punktu historycznego",
                    f"Punkt #{idx + 1} ({raw.get('object_name', '?')}): {exc}",
                    parent=self,
                )
                return
        self.result = (name, full_name, powiat, region, year, century,
                       homepage_desc, history_p1, history_p2, history_p3,
                       self.history_photos, postgres_db_name, homepage_template,
                       gmina_katastralna, jewish_protocols, self.historical_points_data)
        self.destroy()
