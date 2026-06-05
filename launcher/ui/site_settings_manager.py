"""Okno ustawien witryny i faviconu."""

import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ..config.paths import BACKUP_FOLDER
from ..services.location_service import get_active_location_name
from ..utils import set_dialog_icon, get_db_config_from_env, scale_wrap


__all__ = ["SiteSettingsManager"]


class SiteSettingsManager(tk.Toplevel):
    """Okno dialogowe do zarządzania ustawieniami witryny."""

    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        set_dialog_icon(self)
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
        
        self.path_label = ttk.Label(info_frame, text="Obecna ikona: Brak", wraplength=scale_wrap(self, 350))
        self.path_label.pack(anchor="w")
        
        ttk.Button(info_frame, text="Wybierz Ikonę (.png, .ico, .jpg)",
                  command=self.select_favicon, style="Primary.TButton").pack(pady=(10,0), anchor="w")
        
        ttk.Label(main_frame, text="Zmiany będą widoczne po restarcie serwera.",
                 foreground="grey", wraplength=scale_wrap(self, 450)).pack(pady=(15,0))
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(button_frame, text="Zamknij", command=self.destroy).pack(side=tk.RIGHT)

    def load_current_settings(self):
        """Wczytuje aktualny favicon z folderu backup aktywnej miejscowości."""
        try:
            location_name = get_active_location_name()
            if not location_name:
                self.path_label.config(text="Obecna ikona: Brak aktywnej miejscowości")
                return

            backup_location_folder = os.path.join(BACKUP_FOLDER, location_name)

            # Sprawdź różne rozszerzenia favicon
            favicon_extensions = ['.ico', '.png', '.jpg', '.jpeg']
            for ext in favicon_extensions:
                favicon_path = os.path.join(backup_location_folder, f"favicon{ext}")
                if os.path.exists(favicon_path):
                    self.current_favicon_path = favicon_path
                    self.update_preview()
                    return

            self.path_label.config(text="Obecna ikona: Brak (używana domyślna)")
        except Exception as e:
            self.path_label.config(text=f"Błąd: {e}")

    def update_preview(self):
        """Aktualizuje podgląd ikony."""
        if not self.current_favicon_path:
            self.path_label.config(text="Obecna ikona: Brak (używana domyślna)")
            return

        if os.path.exists(self.current_favicon_path):
            try:
                # Pokaż ścieżkę relatywną do backup
                rel_path = os.path.relpath(self.current_favicon_path, BACKUP_FOLDER)
                self.path_label.config(text=f"Obecna ikona: backup/{rel_path}")
                from PIL import Image, ImageTk

                img = Image.open(self.current_favicon_path)
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
        """Otwiera dialog wyboru pliku i kopiuje go do folderu backup aktywnej miejscowości."""
        filepath = filedialog.askopenfilename(
            title="Wybierz plik ikony",
            filetypes=[("Obrazy", "*.png *.ico *.jpg *.jpeg"), ("Wszystkie pliki", "*.*")]
        )

        if not filepath:
            return

        # Pobierz nazwę aktywnej miejscowości
        try:
            location_name = get_active_location_name()
            if not location_name:
                messagebox.showerror("Błąd", "Brak aktywnej miejscowości.", parent=self)
                return
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można pobrać aktywnej miejscowości: {e}", parent=self)
            return

        # Ścieżka do folderu backup miejscowości
        backup_location_folder = os.path.join(BACKUP_FOLDER, location_name)
        os.makedirs(backup_location_folder, exist_ok=True)

        file_extension = os.path.splitext(filepath)[1]
        dest_filename = f"favicon{file_extension}"
        dest_path = os.path.join(backup_location_folder, dest_filename)

        try:
            shutil.copy(filepath, dest_path)
            self.parent_app.log(f"🖼️ Ustawiono nowy favicon w backup/{location_name}/{dest_filename}\n")
            messagebox.showinfo("Sukces",
                              f"Nowa ikona została zapisana w backup/{location_name}/\n"
                              "Zmiany będą widoczne po odświeżeniu strony.",
                              parent=self)
            self.current_favicon_path = dest_path
            self.update_preview()
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się przetworzyć pliku: {e}", parent=self)

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
