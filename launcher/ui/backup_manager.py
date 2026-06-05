"""Menedżer kopii zapasowych launchera.

Moduł wydzielony z ``launcher_app.py``. Ciężkie operacje plikowe są
delegowane do ``launcher.services.backup_service``; ten moduł zawiera warstwę UI
i orkiestrację pytań użytkownika.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

from launcher.config.settings import COLORS
from launcher.services import backup_service, location_migration_service, location_service
from launcher.ui.progress_dialog import ProgressDialog
from launcher.utils import get_data_files, scale_font, scale_window, set_dialog_icon


DATA_FILES = get_data_files()


class BackupManager(tk.Toplevel):
    """Okno dialogowe do zarządzania kopiami zapasowymi projektu."""

    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        set_dialog_icon(self)
        self.title("💾 Uniwersalny Menedżer Kopii Zapasowych")

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

        base_size = 10 if scale_factor <= 1.25 else (11 if scale_factor <= 1.5 else 12)
        self.base_font_size = base_size
        self.style = ttk.Style(self)
        self.style.configure("Treeview", rowheight=int(base_size * 2.5), font=("Segoe UI", base_size))
        self.style.configure("Treeview.Heading", font=("Segoe UI", base_size, "bold"))

        self.create_widgets()
        self.populate_backup_list()

    def create_widgets(self):
        """Tworzy interfejs menedżera kopii."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        create_frame = ttk.LabelFrame(main_frame, text="➕ Stwórz Nową Kopię Zapasową", padding="10")
        create_frame.pack(fill=tk.X, pady=(0, 10))

        location_select_frame = ttk.Frame(create_frame)
        location_select_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(location_select_frame, text="Miejscowość do skopiowania:").pack(side=tk.LEFT, padx=5)

        self.location_backup_var = tk.StringVar(value="Aktywna miejscowość")
        self.location_backup_combo = ttk.Combobox(location_select_frame, textvariable=self.location_backup_var,
                                                  state="readonly", width=30)
        self.location_backup_combo.pack(side=tk.LEFT, padx=5)
        self.location_backup_combo['values'] = ["Aktywna miejscowość", "Wszystkie miejscowości"] + [loc[1] for loc in location_service.get_all_locations()]

        self.backup_vars = {key: tk.BooleanVar(value=True) for key in DATA_FILES}
        self.backup_vars.update({
            "config": tk.BooleanVar(value=True),
            "map_image": tk.BooleanVar(value=True),
            "history_photos": tk.BooleanVar(value=True),
            "scans": tk.BooleanVar(value=True),
            "custom_icons": tk.BooleanVar(value=True),
            "favicon": tk.BooleanVar(value=True),
            "launcher_db": tk.BooleanVar(value=True),
        })

        content_frame = ttk.Frame(create_frame)
        content_frame.pack(fill=tk.X)
        checkbox_frame = ttk.Frame(content_frame)
        checkbox_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        groups = [
            [("📋 Właściciele i Demografia", "owners"), ("🗺️ Działki (geometria)", "parcels"),
             ("📍 Konfiguracja Mapy", "config"), ("🗾 Plik mapy (mapa.*)", "map_image")],
            [("🌳 Genealogia", "genealogy"), ("🖼️ Zdjęcia historyczne", "history_photos"),
             ("📄 Skany Protokołów", "scans")],
            [("🖥️ Ikony Launchera", "custom_icons"), ("🌐 Favicon witryny", "favicon"),
             ("🗄️ Baza Launcher (konfiguracja stron)", "launcher_db")],
        ]
        for group in groups:
            col = ttk.Frame(checkbox_frame)
            col.pack(side=tk.LEFT, padx=10)
            for text, var_key in group:
                ttk.Checkbutton(col, text=text, variable=self.backup_vars[var_key]).pack(anchor="w", pady=2)

        ttk.Button(content_frame, text="🎯 Stwórz Kopię ZIP", command=self.create_backup,
                  style="Success.TButton").pack(side=tk.RIGHT, padx=10)

        restore_frame = ttk.LabelFrame(main_frame, text="📦 Istniejące Kopie Zapasowe", padding="10")
        restore_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.tree = ttk.Treeview(restore_frame, columns=("filename",), show="headings")
        self.tree.heading("filename", text="📁 Nazwa Pliku (od najnowszej)")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        self.selected_label = ttk.Label(action_frame, text="📭 Nic nie zaznaczono",
                                       foreground=COLORS['secondary'], font=("Segoe UI", self.base_font_size))
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
        ttk.Button(buttons_frame, text="📥 Importuj z dysku", command=self.import_backup,
                   style="Primary.TButton").pack(side=tk.LEFT, padx=2)

    def populate_backup_list(self):
        """Wczytuje listę plików kopii zapasowych."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for filename in backup_service.list_backup_files():
            self.tree.insert("", "end", iid=filename, values=(filename,))
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
        if not self.selected_backup_file:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Najpierw zaznacz plik.", parent=self)
            return
        destination_path = filedialog.asksaveasfilename(
            initialfile=self.selected_backup_file, defaultextension=".zip",
            filetypes=[("Archiwum ZIP", "*.zip")], title="Wybierz, gdzie zapisać"
        )
        if destination_path:
            try:
                backup_service.export_backup_file(self.selected_backup_file, destination_path)
                messagebox.showinfo("✅ Sukces", "Kopia zapasowa została wyeksportowana.", parent=self)
            except Exception as e:
                messagebox.showerror("❌ Błąd", f"Nie udało się zapisać:\n{e}", parent=self)

    def import_backup(self):
        source_path = filedialog.askopenfilename(filetypes=[("Archiwum ZIP", "*.zip")], title="Wybierz plik kopii zapasowej")
        if not source_path:
            return
        filename = os.path.basename(source_path)
        destination_path = backup_service.backup_path(filename)
        if destination_path.exists() and not messagebox.askyesno("⚠️ Plik istnieje", f"Plik '{filename}' już istnieje.\nNadpisać?", parent=self):
            return
        try:
            backup_service.import_backup_file(source_path)
            messagebox.showinfo("✅ Sukces", f"Plik '{filename}' został zaimportowany.", parent=self)
            self.populate_backup_list()
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Nie udało się skopiować:\n{e}", parent=self)

    def create_backup(self):
        components = [key for key, var in self.backup_vars.items() if var.get()]
        if not components:
            messagebox.showwarning("⚠️ Nic nie wybrano", "Zaznacz co najmniej jeden element.", parent=self)
            return
        ProgressDialog(self, self._perform_backup, components)

    def _perform_backup(self, progress_callback, components):
        location_choice = self.location_backup_var.get()
        backup_flags = {key: var.get() for key, var in self.backup_vars.items()}
        backup_filename, _, files_to_zip, temp_json_paths = backup_service.build_backup_package(
            location_choice,
            backup_flags,
            location_service.get_active_location,
            location_service.get_all_locations,
        )
        backup_path_value = backup_service.backup_path(backup_filename)
        try:
            backup_service.write_backup_archive(str(backup_path_value), files_to_zip, progress_callback)
        finally:
            backup_service.cleanup_temp_backup_files(temp_json_paths)
        return backup_filename

    def delete_backup(self):
        if not getattr(self, "selected_backup_file", None):
            return
        if messagebox.askyesno("🗑️ Potwierdzenie", f"Czy na pewno usunąć:\n\n{self.selected_backup_file}?",
                               parent=self, icon="warning"):
            try:
                backup_service.delete_backup_file(self.selected_backup_file)
                messagebox.showinfo("✅ Sukces", f"Usunięto: {self.selected_backup_file}", parent=self)
                self.populate_backup_list()
            except Exception as e:
                messagebox.showerror("❌ Błąd", f"Nie udało się usunąć:\n{e}", parent=self)

    def restore_backup(self):
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
        try:
            restored_locations = backup_service.restore_backup_archive(
                filename,
                location_service.get_active_location_name,
                DATA_FILES,
            )
            migration_success, migration_errors = [], []
            if restored_locations:
                locations_list = "\n".join([f"  • {loc}" for loc in restored_locations])
                migrate_msg = (
                    f"✅ Kopia zapasowa została przywrócona.\n\n"
                    f"Znaleziono dane dla miejscowości:\n{locations_list}\n\n"
                    f"Czy chcesz automatycznie utworzyć bazy danych i zmigrować dane do PostgreSQL?"
                )
                if messagebox.askyesno("🔄  Migracja Danych", migrate_msg, icon="question", parent=self):
                    self._run_restore_migration(restored_locations, migration_success, migration_errors)

            final_msg = "Kopia zapasowa została przywrócona.\n\n"
            if migration_success:
                final_msg += f"✅ Zmigrowano dane dla: {', '.join(migration_success)}\n"
            if migration_errors:
                final_msg += f"\n⚠️ Błędy migracji dla: {', '.join([loc for loc, _ in migration_errors])}\n"
            final_msg += "\nUruchom ponownie edytory, aby zobaczyć zmiany."
            messagebox.showinfo("✅ Sukces", final_msg, parent=self)
        except Exception as e:
            messagebox.showerror("❌ Błąd", f"Wystąpił błąd:\n{e}", parent=self)

    def _run_restore_migration(self, restored_locations, migration_success, migration_errors):
        progress_window = tk.Toplevel(self)
        progress_window.title("🔄  Migracja Danych")
        set_dialog_icon(progress_window)
        progress_window.transient(self)
        progress_window.grab_set()
        scale_window(progress_window, self, 600, 400)
        progress_window.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - progress_window.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - progress_window.winfo_height()) // 2
        progress_window.geometry(f"+{x}+{y}")
        ttk.Label(progress_window, text="Migracja danych do PostgreSQL",
                 font=scale_font(progress_window, 12, "bold")).pack(pady=10)
        progress_text = scrolledtext.ScrolledText(progress_window, height=15, width=70)
        progress_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        def log_progress(message):
            progress_text.insert(tk.END, message + "\n")
            progress_text.see(tk.END)
            progress_text.update()

        for location_name in restored_locations:
            log_progress(f"\n{'='*50}")
            log_progress(f"📍 Miejscowość: {location_name}")
            log_progress(f"{'='*50}")
            success, msg = location_migration_service.create_and_migrate_location_database(
                location_name,
                progress_callback=log_progress,
            )
            if success:
                migration_success.append(location_name)
                log_progress(f"✅ {msg}")
            else:
                migration_errors.append((location_name, msg))
                log_progress(f"❌ {msg}")

        log_progress(f"\n{'='*50}")
        log_progress("📊 Podsumowanie migracji:")
        log_progress(f"  ✅ Sukces: {len(migration_success)}/{len(restored_locations)}")
        if migration_errors:
            log_progress(f"  ❌ Błędy: {len(migration_errors)}")
        log_progress(f"{'='*50}")
        button_frame = ttk.Frame(progress_window)
        button_frame.pack(pady=15)
        ttk.Button(button_frame, text="✅ Zamknij", command=progress_window.destroy,
                   style="Primary.TButton").pack()
        progress_window.wait_window()
