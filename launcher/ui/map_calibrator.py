"""Okno kalibracji mapy historycznej.

Moduł wydzielony z ``launcher_app.py``. Operacje na ``map_config.json`` oraz
zapis kalibracji do bazy są delegowane do serwisów ``map_calibration_service``
i ``map_asset_service``.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

from PIL import Image, ImageTk

from launcher.config.paths import BACKUP_FOLDER
from launcher.config.settings import DEFAULT_LOCATION_NAME
from launcher.services import location_service, map_asset_service, map_calibration_service
from launcher.utils import scale_font, scale_wrap, set_dialog_icon


class MapCalibrator(tk.Toplevel):
    """Okno do kalibracji współrzędnych mapy."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("📍 Konfigurator Mapy")
        set_dialog_icon(self)
        self.transient(parent)
        # grab_set() usunięte - pozwala na Alt+Tab między oknami
        self.resizable(False, False)

        self.parent_app = parent

        # Użyj folderu aktywnej miejscowości
        active_location_name = location_service.get_active_location_name()
        if active_location_name:
            location_folder = os.path.join(str(BACKUP_FOLDER), active_location_name)
        else:
            location_folder = str(BACKUP_FOLDER)

        self.config_path = map_calibration_service.get_map_config_path(active_location_name or DEFAULT_LOCATION_NAME)
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
                 wraplength=scale_wrap(self, 400)).grid(row=1, column=1, sticky="w", pady=(5,0))

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
                 wraplength=scale_wrap(self, 500)).pack(pady=(5,0))

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
            active_location_name = location_service.get_active_location_name()
            config = map_calibration_service.load_map_config(active_location_name) if active_location_name else {}

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
            active_location_name = location_service.get_active_location_name()
            if active_location_name:
                map_calibration_service.save_map_config(active_location_name, new_config)
            self.parent_app.log(f"📍 Zapisano konfigurację mapy: {self.config_path}\n")
        except Exception as e:
            messagebox.showerror("Błąd Zapisu", f"Nie można zapisać pliku: {e}", parent=self)
            return

        # Aktualizacja bazy danych
        try:
            map_calibration_service.save_map_calibration_to_db(new_config)

            self.parent_app.log("📍 Zaktualizowano konfigurację mapy w bazie danych.\n")
            messagebox.showinfo("Sukces", "Konfiguracja mapy została zapisana.", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Błąd Bazy", f"Nie można zaktualizować bazy: {e}", parent=self)

    def check_current_map_status(self):
        """Sprawdza status pliku mapy w backup aktywnej miejscowości."""
        location_name = location_service.get_active_location_name()

        if not location_name:
            self.map_status_label.config(text="❌ Brak aktywnej miejscowości!", foreground="red")
            self.map_preview_canvas.delete("all")
            self.map_preview_label.config(text="Brak\nmiejscowości")
            self.map_preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            return

        backup_map_path = map_asset_service.get_map_path(location_name)
        map_exists = backup_map_path.exists()

        if map_exists:
            self.map_status_label.config(text=f"✅ Status mapy: OK ({location_name})", foreground="green")
        else:
            self.map_status_label.config(text=f"❌ Brak mapy dla {location_name}", foreground="red")

        # Aktualizacja podglądu
        if map_exists:
            try:
                img = Image.open(backup_map_path)
                w, h = img.size
                ratio = min(200/w, 120/h)
                new_w, new_h = int(w * ratio), int(h * ratio)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                self.map_image_preview = ImageTk.PhotoImage(img)
                self.map_preview_canvas.delete("all")
                self.map_preview_canvas.create_image(100, 60, image=self.map_image_preview)
                self.map_preview_label.place_forget()
            except Exception:
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

        # Zapisz mapę tylko do backup aktywnej miejscowości
        location_name = location_service.get_active_location_name()
        if not location_name:
            messagebox.showerror("Błąd",
                              "Brak aktywnej miejscowości!\n\n"
                              "Proszę wybrać miejscowość przed dodaniem mapy.",
                              parent=self)
            return

        try:
            map_asset_service.save_map_file(filepath, location_name)

            messagebox.showinfo("Sukces",
                              f"Plik mapy został zapisany dla miejscowości: {location_name}\n\n"
                              "WAŻNE: Upewnij się, że współrzędne odpowiadają nowej mapie!",
                              parent=self)

            self.parent_app.log(f"🗺️ Zapisano mapę do backup/{location_name}/mapa.jpg: {os.path.basename(filepath)}\n")
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
        set_dialog_icon(self)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        frame = ttk.Frame(self, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=20, width=80, font=scale_font(self, 10))
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
