"""Dialog do zarządzania zdjęciami historycznymi."""
import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from ..utils import set_dialog_icon, scale_window

__all__ = ["PhotosManagerDialog"]


class PhotosManagerDialog(tk.Toplevel):
    """Dialog do zarządzania listą zdjęć historycznych (max 20)."""

    def __init__(self, parent, photos_list, base_dir, location_name="Czarna"):
        super().__init__(parent)
        self.title("📸 Zarządzaj zdjęciami historycznymi")
        set_dialog_icon(self)
        scale_window(self, parent, 820, 560)
        self.transient(parent)
        self.grab_set()

        self.photos_list = photos_list.copy() if photos_list else []
        self.base_dir = base_dir
        self.location_name = location_name
        # Ścieżka do folderu history_photos w miejscowości
        self.assets_dir = os.path.join(base_dir, "data", "locations", location_name, "history_photos")
        self.result = None

        # Główny frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Info o limicie
        info_label = ttk.Label(main_frame, text="Możesz dodać maksymalnie 20 zdjęć. Zarządzaj kolejnością i podpisami.",
                               foreground="gray")
        info_label.pack(anchor=tk.W, pady=(0, 10))

        # Frame z listą i scrollbarem
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.photos_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=15)
        self.photos_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.photos_listbox.yview)
        self.photos_listbox.bind("<Double-1>", self.open_selected_photo)

        # Przyciski do zarządzania
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))
        for col in range(6):
            buttons_frame.columnconfigure(col, weight=1)

        ttk.Button(buttons_frame, text="➕ Dodaj zdjęcie", command=self.add_photo).grid(row=0, column=0, sticky="ew", padx=4, pady=2)
        ttk.Button(buttons_frame, text="👁️ Otwórz", command=self.open_selected_photo).grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        ttk.Button(buttons_frame, text="✏️ Edytuj", command=self.edit_photo).grid(row=0, column=2, sticky="ew", padx=4, pady=2)
        ttk.Button(buttons_frame, text="🗑️ Usuń", command=self.delete_photo).grid(row=0, column=3, sticky="ew", padx=4, pady=2)
        ttk.Button(buttons_frame, text="⬆️ W górę", command=self.move_up).grid(row=0, column=4, sticky="ew", padx=4, pady=2)
        ttk.Button(buttons_frame, text="⬇️ W dół", command=self.move_down).grid(row=0, column=5, sticky="ew", padx=4, pady=2)

        # Przyciski OK/Cancel
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(bottom_frame, text="✅ OK", command=self.on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom_frame, text="❌ Anuluj", command=self.destroy).pack(side=tk.RIGHT)

        # Załaduj listę
        self.refresh_list()

    def refresh_list(self):
        """Odśwież listę zdjęć."""
        self.photos_listbox.delete(0, tk.END)
        for i, photo in enumerate(self.photos_list, 1):
            self.photos_listbox.insert(tk.END, f"{i}. {photo['filename']} - {photo['caption'][:50]}")

    def add_photo(self):
        """Dodaj nowe zdjęcie."""
        if len(self.photos_list) >= 20:
            messagebox.showwarning("Limit zdjęć", "Możesz dodać maksymalnie 20 zdjęć.", parent=self)
            return

        # Wybierz plik
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Wybierz zdjęcie",
            filetypes=[
                ("Pliki graficzne", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("Wszystkie pliki", "*.*")
            ]
        )

        if not file_path:
            return

        # Pobierz nazwę bez rozszerzenia
        original_filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(original_filename)[0]
        extension = os.path.splitext(original_filename)[1]

        # Zapytaj o nazwę pliku
        new_filename = simpledialog.askstring(
            "Nazwa pliku",
            f"Podaj nazwę dla tego zdjęcia (bez rozszerzenia):",
            initialvalue=name_without_ext,
            parent=self
        )

        if not new_filename:
            return

        # Dodaj rozszerzenie
        new_filename = new_filename + extension

        # Zapytaj o podpis
        caption = simpledialog.askstring(
            "Podpis zdjęcia",
            "Podaj podpis do zdjęcia:",
            parent=self
        )

        if not caption:
            caption = "Zdjęcie historyczne"

        # Sprawdź czy plik o tej nazwie już istnieje
        dest_path = os.path.join(self.assets_dir, new_filename)
        if os.path.exists(dest_path):
            if not messagebox.askyesno("Plik istnieje",
                                       f"Plik {new_filename} już istnieje. Czy nadpisać?",
                                       parent=self):
                return

        # Skopiuj plik
        try:
            os.makedirs(self.assets_dir, exist_ok=True)
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się skopiować pliku:\n{e}", parent=self)
            return

        # Dodaj do listy
        self.photos_list.append({
            "filename": new_filename,
            "caption": caption
        })

        self.refresh_list()
        self.photos_listbox.selection_clear(0, tk.END)
        self.photos_listbox.selection_set(tk.END)
        self.photos_listbox.see(tk.END)

    def edit_photo(self):
        """Edytuj wybrany."""
        selection = self.photos_listbox.curselection()
        if not selection:
            messagebox.showinfo("Brak wyboru", "Wybierz zdjęcie do edycji.", parent=self)
            return

        idx = selection[0]
        photo = self.photos_list[idx]

        # Edytuj podpis
        new_caption = simpledialog.askstring(
            "Edytuj podpis",
            "Podaj nowy podpis:",
            initialvalue=photo['caption'],
            parent=self
        )

        if new_caption is not None:
            photo['caption'] = new_caption
            self.refresh_list()
            self.photos_listbox.selection_set(idx)

    def open_selected_photo(self, _event=None):
        """Otwórz zaznaczone zdjęcie w domyślnym programie Windows."""
        selection = self.photos_listbox.curselection()
        if not selection:
            messagebox.showinfo("Brak wyboru", "Wybierz zdjęcie do otwarcia.", parent=self)
            return

        photo = self.photos_list[selection[0]]
        file_path = os.path.join(self.assets_dir, photo["filename"])
        if not os.path.exists(file_path):
            messagebox.showerror("Brak pliku", f"Nie znaleziono pliku:\n{file_path}", parent=self)
            return
        try:
            os.startfile(file_path)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się otworzyć zdjęcia:\n{e}", parent=self)

    def delete_photo(self):
        """Usuń wybrane zdjęcie."""
        selection = self.photos_listbox.curselection()
        if not selection:
            messagebox.showinfo("Brak wyboru", "Wybierz zdjęcie do usunięcia.", parent=self)
            return

        idx = selection[0]
        photo = self.photos_list[idx]

        if messagebox.askyesno("Potwierdź usunięcie",
                               f"Czy na pewno usunąć zdjęcie:\n{photo['filename']}?\n\nPlik zostanie trwale usunięty z folderu.",
                               parent=self):
            # Usuń fizyczny plik z dysku
            file_path = os.path.join(self.assets_dir, photo['filename'])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"✓ Usunięto plik: {file_path}")
                else:
                    print(f"⚠️ Plik nie istnieje: {file_path}")
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie udało się usunąć pliku:\n{e}", parent=self)
                return

            # Usuń z listy
            del self.photos_list[idx]
            self.refresh_list()

    def move_up(self):
        """Przesuń zdjęcie w górę."""
        selection = self.photos_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx == 0:
            return  # Już na górze

        # Zamień miejscami
        self.photos_list[idx], self.photos_list[idx-1] = self.photos_list[idx-1], self.photos_list[idx]
        self.refresh_list()
        self.photos_listbox.selection_set(idx-1)
        self.photos_listbox.see(idx-1)

    def move_down(self):
        """Przesuń zdjęcie w dół."""
        selection = self.photos_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx >= len(self.photos_list) - 1:
            return  # Już na dole

        # Zamień miejscami
        self.photos_list[idx], self.photos_list[idx+1] = self.photos_list[idx+1], self.photos_list[idx]
        self.refresh_list()
        self.photos_listbox.selection_set(idx+1)
        self.photos_listbox.see(idx+1)

    def on_ok(self):
        """Zatwierdź zmiany."""
        self.result = self.photos_list
        self.destroy()
