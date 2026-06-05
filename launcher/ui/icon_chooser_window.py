"""Okno wyboru ikony aplikacji."""

import json
import os
import platform
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ..config.paths import BASE_DIR
from ..services.location_service import get_active_location
from ..utils import set_dialog_icon, set_windows_taskbar_icon_for_window, scale_wrap


__all__ = ["IconChooserWindow"]


class IconChooserWindow(tk.Toplevel):
    """Okno dialogowe do wyboru i zmiany ikony aplikacji."""

    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        set_dialog_icon(self)
        self.title("🖼️ Wybierz Ikonę Aplikacji")
        self.grab_set()
        self.resizable(False, False)

        self.parent_app = parent
        self.current_icon_path = None
        self.image_preview = None

        self.create_widgets()
        self.load_current_icon()
        self.center_window()

    def create_widgets(self):
        """Tworzy interfejs wyboru ikony."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        frame_icon = ttk.LabelFrame(main_frame, text="Ikona Aplikacji", padding="15")
        frame_icon.pack(fill=tk.X)

        top_row = ttk.Frame(frame_icon)
        top_row.pack(fill=tk.X)

        # Podgląd ikony
        self.preview_canvas = tk.Canvas(top_row, width=64, height=64, bg=self.cget("background"), highlightthickness=0)
        self.preview_canvas.pack(side=tk.LEFT, padx=(0, 15))
        self.preview_label = ttk.Label(self.preview_canvas, text="Brak\nikony", foreground="grey")
        self.preview_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Informacje i przycisk
        info_frame = ttk.Frame(top_row)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.path_label = ttk.Label(info_frame, text="Obecna ikona: Domyślna", wraplength=scale_wrap(self, 350))
        self.path_label.pack(anchor="w")

        ttk.Button(info_frame, text="Wybierz Ikonę (.png, .ico, .jpg)",
                  command=self.select_icon, style="Primary.TButton").pack(pady=(10,0), anchor="w")

        ttk.Label(main_frame, text="Wybrana ikona zostanie ustawiona jako ikona okna\ni ikona na pasku zadań Windows.",
                 foreground="grey", wraplength=scale_wrap(self, 450)).pack(pady=(15,0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(button_frame, text="Zastosuj", command=self.apply_icon,
                  style="Success.TButton").pack(side=tk.RIGHT, padx=(5,0))
        ttk.Button(button_frame, text="Anuluj", command=self.destroy).pack(side=tk.RIGHT)

    def load_current_icon(self):
        """Wczytuje aktualną ikonę aplikacji."""
        try:
            # Pobierz aktywną miejscowość
            active_location = get_active_location()
            if active_location:
                location_name = active_location[1]
                backup_icon_dir = os.path.join(BASE_DIR, "data", "locations", location_name)

                # Sprawdź czy jest custom_icon w folderze miejscowości
                icon_extensions = ['.png', '.ico', '.jpg', '.jpeg']
                for ext in icon_extensions:
                    icon_path = os.path.join(backup_icon_dir, f'custom_icon{ext}')
                    if os.path.exists(icon_path):
                        self.current_icon_path = icon_path
                        self.update_preview()
                        return

            # Jeśli nie ma w backup, sprawdź stary launcher/assets (dla kompatybilności wstecznej)
            icon_dir = os.path.join(BASE_DIR, "launcher", "assets")
            custom_png = os.path.join(icon_dir, 'custom_icon.png')
            if os.path.exists(custom_png):
                self.current_icon_path = custom_png
                self.update_preview()
                return

            # W ostateczności użyj domyślnej ikony (feather)
            icon_extensions = ['.png', '.ico', '.jpg', '.jpeg']
            for ext in icon_extensions:
                icon_path = os.path.join(icon_dir, f"feather_icon{ext}")
                if os.path.exists(icon_path):
                    self.current_icon_path = icon_path
                    self.update_preview()
                    return

            self.path_label.config(text="Obecna ikona: Domyślna")
        except Exception as e:
            self.path_label.config(text=f"Błąd: {e}")

    def update_preview(self):
        """Aktualizuje podgląd ikony."""
        if not self.current_icon_path:
            self.path_label.config(text="Obecna ikona: Domyślna")
            return

        if os.path.exists(self.current_icon_path):
            try:
                # Pokaż ścieżkę
                icon_name = os.path.basename(self.current_icon_path)
                self.path_label.config(text=f"Wybrana ikona: {icon_name}")

                # Wczytaj i pokaż podgląd
                from PIL import Image, ImageTk

                img = Image.open(self.current_icon_path)
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

    def select_icon(self):
        """Otwiera dialog wyboru pliku ikony."""
        filepath = filedialog.askopenfilename(
            title="Wybierz plik ikony",
            filetypes=[("Obrazy", "*.png *.ico *.jpg *.jpeg"), ("Wszystkie pliki", "*.*")]
        )

        if not filepath:
            return

        self.current_icon_path = filepath
        self.update_preview()

    def apply_icon(self):
        """Stosuje wybraną ikonę do aplikacji."""
        if not self.current_icon_path or not os.path.exists(self.current_icon_path):
            messagebox.showerror("Błąd", "Nie wybrano prawidłowej ikony.", parent=self)
            return

        try:
            # Pobierz aktywną miejscowość
            active_location = get_active_location()
            if not active_location:
                messagebox.showerror("Błąd", "Brak aktywnej miejscowości. Najpierw utwórz i aktywuj miejscowość.", parent=self)
                return

            location_name = active_location[1]  # Nazwa miejscowości
            location_id = active_location[0]    # ID miejscowości

            # Zapisz ikonę w folderze backup/{miejscowość}/
            icon_dir = os.path.join(BASE_DIR, "data", "locations", location_name)
            os.makedirs(icon_dir, exist_ok=True)

            # Wczytaj obraz i konwertuj do RGBA jeśli potrzeba
            from PIL import Image

            img = Image.open(self.current_icon_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Zapisz jako PNG w pełnej rozdzielczości dla iconphoto()
            png_path = os.path.join(icon_dir, 'custom_icon.png')
            img.save(png_path, 'PNG')

            # Dla Windows, zapisz też jako ICO z wieloma rozmiarami
            ico_path = os.path.join(icon_dir, 'custom_icon.ico')
            if platform.system() == "Windows":
                # Stwórz ICO z wieloma rozmiarami dla lepszej jakości w pasku zadań i Alt+Tab
                # Windows używa różnych rozmiarów: 16x16, 32x32, 48x48, 64x64, 128x128, 256x256
                icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]

                # Stwórz listę obrazów w różnych rozmiarach
                icon_images = []
                for size in icon_sizes:
                    resized = img.resize(size, Image.Resampling.LANCZOS)
                    icon_images.append(resized)

                # Zapisz jako ICO z wieloma rozmiarami
                icon_images[0].save(ico_path, format='ICO', sizes=icon_sizes, append_images=icon_images[1:])

            # Zaktualizuj launcher_db_config.json
            config_file = os.path.join(icon_dir, "launcher_db_config.json")
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                config_data['default_location']['custom_icon'] = 'custom_icon.png'
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)

            # Zaktualizuj w bazie danych
            try:
                from ..db.postgres import get_launcher_postgres_connection

                conn = get_launcher_postgres_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE locations SET custom_icon = %s WHERE id = %s", ('custom_icon.png', location_id))
                conn.commit()
                cursor.close()
                conn.close()
                self.parent_app.log(f"✅ Ikona zapisana w backup/{location_name}/custom_icon.png\n")
            except Exception as db_error:
                self.parent_app.log(f"⚠️ Błąd zapisu do bazy danych: {db_error}\n")

            # Zastosuj ikonę do okna Tkinter
            icon_image = tk.PhotoImage(file=png_path)
            self.parent_app.iconphoto(True, icon_image)
            self.parent_app._custom_icon_image = icon_image  # Zachowaj referencję

            # Dla Windows, ustaw też iconbitmap
            if platform.system() == "Windows":
                try:
                    self.parent_app.iconbitmap(ico_path)
                except:
                    pass

                # Zmień ikonę na pasku zadań
                self.change_windows_taskbar_icon(ico_path)

            self.parent_app.log("✅ Ikona aplikacji została zmieniona\n")
            messagebox.showinfo("Sukces",
                              "Ikona została zmieniona!\n\n"
                              "Ikona okna i paska zadań została zaktualizowana.\n"
                              f"Zapisano w backup/{location_name}/",
                              parent=self)
            self.destroy()

        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się zastosować ikony:\n{str(e)}", parent=self)
            self.parent_app.log(f"❌ Błąd zmiany ikony: {e}\n")

    def change_windows_taskbar_icon(self, ico_path):
        """Zmienia ikonę w pasku zadań Windows używając multi-size ICO."""
        set_windows_taskbar_icon_for_window(self.parent_app, ico_path)

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
