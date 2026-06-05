"""Okno zarządzania miejscowościami."""

import json
import tkinter as tk
from tkinter import ttk, messagebox

from ..db.engine import get_engine
from ..db.sqlite import sqlite_get_location_by_id
from ..db.postgres import get_launcher_postgres_connection
from ..utils import set_dialog_icon, get_effective_ui_scale, check_postgres_available, apply_homepage_template
from ..services.location_service import (
    get_all_locations,
    set_active_location,
    generate_location_config_js,
    add_location,
    update_location,
    delete_location,
)
from ..services.historical_points_service import (
    HistoricalPoint,
    HistoricalPointValidationError,
    save_historical_points,
)
from .add_edit_location_dialog import AddEditLocationDialog
from .template_change_dialog import TemplateChangeDialog


__all__ = ["LocationManager", "TemplateChangeDialog"]


def _persist_historical_points(location_name: str, raw_points):
    """Zapisuje punkty historyczne do JSON. Cicho pomija przy pustej liście.

    Helper wywoływany z obu flow (add/update) - wyodrębniony bo:
    - logika identyczna w obu miejscach,
    - trzyma UI (``location_manager``) wolne od importów usługi I/O.
    """
    if not raw_points:
        return
    points = [HistoricalPoint.from_dict(raw) for raw in raw_points]
    try:
        save_historical_points(location_name, points)
    except HistoricalPointValidationError as exc:
        # Już zwalidowane w save() dialogu, więc tutaj raczej nie powinno rzucać.
        # Awaryjnie pokaż błąd ale nie blokuj reszty zapisu miejscowości.
        messagebox.showwarning(
            "⚠️ Punkty historyczne",
            f"Nie udało się zapisać punktów historycznych: {exc}",
        )


SQLITE_MODE = get_engine().name == "sqlite"


class LocationManager(tk.Toplevel):
    """Okno dialogowe do zarządzania miejscowościami."""

    def __init__(self, parent):
        super().__init__(parent)
        self.transient(parent)
        self.title("⚙️ Zarządzaj Miejscowościami")
        set_dialog_icon(self)

        # Automatyczne dostosowanie do skali UI, ale bez robienia pełnoekranowego
        # okna na 4K. Przy 135% okno ma być wygodne, nie ogromne.
        scale = get_effective_ui_scale(parent)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(max(1050, int(980 * scale)), sw - 180)
        h = min(max(680, int(620 * scale)), sh - 180)
        x = (sw - w) // 2
        y = (sh - h) // 2

        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(w, max(700, int(700 * scale))), min(h, max(500, int(500 * scale))))
        # grab_set() usunięte - pozwala na Alt+Tab między oknami

        self.create_widgets()
        self.refresh_table()

    def create_widgets(self):
        """Tworzy interfejs menedżera miejscowości."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Tabelka
        table_frame = ttk.LabelFrame(main_frame, text="📋 Lista Miejscowości", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Kolumny: ID, Nazwa, Pełna Nazwa, Powiat, Region, Szablon, Aktywna
        columns = ("id", "name", "full_name", "powiat", "region", "template", "active")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Nazwa")
        self.tree.heading("full_name", text="Pełna Nazwa")
        self.tree.heading("powiat", text="Powiat")
        self.tree.heading("region", text="Region")
        self.tree.heading("template", text="Szablon Strony")
        self.tree.heading("active", text="Aktywna")

        scale = get_effective_ui_scale(self)
        self.tree.column("id", width=int(45 * scale), anchor="center")
        self.tree.column("name", width=int(120 * scale))
        self.tree.column("full_name", width=int(170 * scale))
        self.tree.column("powiat", width=int(130 * scale))
        self.tree.column("region", width=int(130 * scale))
        self.tree.column("template", width=int(170 * scale))
        self.tree.column("active", width=int(90 * scale), anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Przyciski akcji
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)

        # Przy dużej skali dzielimy przyciski na 2 rzędy, żeby nie wychodziły poza okno.
        row_top = ttk.Frame(buttons_frame)
        row_bottom = ttk.Frame(buttons_frame)
        row_top.pack(fill=tk.X)
        row_bottom.pack(fill=tk.X, pady=(6, 0))

        ttk.Button(row_top, text="➕ Dodaj Nową Miejscowość", command=self.add_location,
                  style="Success.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(row_top, text="✏️ Edytuj", command=self.edit_location,
                  style="Primary.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(row_top, text="🗑️ Usuń", command=self.delete_location,
                  style="Danger.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(row_bottom, text="✅ Ustaw jako Aktywną", command=self.set_active,
                  style="Info.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(row_bottom, text="🔄  Odśwież", command=self.refresh_table,
                  style="Secondary.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    def refresh_table(self):
        """Odświeża tabelkę z miejscowościami."""
        # Wyczyść tabelę
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Pobierz dane
        locations = get_all_locations()

        # Mapowanie nazw szablonów na bardziej czytelne
        template_names = {
            "standardowy": "📍 Standardowy",
            "praca_inzynierska": "🎓 Praca Inżynierska"
        }

        # Wypełnij tabelę
        for loc in locations:
            # Rozpakuj wszystkie pola (ignorujemy tekst content)
            loc_id, name, full_name, powiat, region, active, template, year, century = loc[:9]
            active_str = "✓" if active else ""
            template_display = template_names.get(template, template)
            self.tree.insert("", "end", values=(loc_id, name, full_name, powiat, region, template_display, active_str))

    def add_location(self):
        """Dodaje nową miejscowość."""
        dialog = AddEditLocationDialog(self, "Dodaj Nową Miejscowość")
        self.wait_window(dialog)

        if hasattr(dialog, 'result') and dialog.result:
            (name, full_name, powiat, region, year, century,
             homepage_desc, history_p1, history_p2, history_p3,
             history_photos, postgres_db_name, homepage_template,
             gmina_katastralna, jewish_protocols, historical_points) = dialog.result
            try:
                add_location(name, full_name, powiat, region, year=year, century=century,
                           homepage_description=homepage_desc, history_paragraph1=history_p1,
                           history_paragraph2=history_p2, history_paragraph3=history_p3,
                           history_photos=history_photos, postgres_db_name=postgres_db_name,
                           homepage_template=homepage_template,
                           gmina_katastralna=gmina_katastralna,
                           jewish_protocol_numbers=jewish_protocols)
                # Zapisz punkty historyczne do pliku JSON (po utworzeniu folderu)
                _persist_historical_points(name, historical_points)
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

        # Pobierz wszystkie dane miejscowości z bazy danych
        values = self.tree.item(selected[0], "values")
        loc_id = values[0]

        # Pobierz pełne dane z bazy danych PostgreSQL
        name = full_name = powiat = region = year = century = ""
        homepage_desc = history_p1 = history_p2 = history_p3 = ""
        history_photos_json = "[]"
        postgres_db_name = ""
        homepage_template = "standardowy"
        gmina_katastralna = "Czarna"
        jewish_protocols = ""

        if SQLITE_MODE:
            try:
                loc_row = sqlite_get_location_by_id(int(loc_id))
                if not loc_row:
                    messagebox.showerror("❌ Błąd", "Nie znaleziono miejscowości", parent=self)
                    return
                name = loc_row.get("name") or ""
                full_name = loc_row.get("full_name") or name
                powiat = loc_row.get("powiat") or ""
                region = loc_row.get("region") or ""
                year = loc_row.get("year") or "1882"
                century = loc_row.get("century") or "XIX w."
                homepage_desc = loc_row.get("homepage_description") or ""
                history_p1 = loc_row.get("history_paragraph1") or ""
                history_p2 = loc_row.get("history_paragraph2") or ""
                history_p3 = loc_row.get("history_paragraph3") or ""
                postgres_db_name = loc_row.get("postgres_db_name") or loc_row.get("sqlite_db_path") or ""
                homepage_template = loc_row.get("homepage_template") or "standardowy"
                gmina_katastralna = loc_row.get("gmina_katastralna") or "Czarna"
                jewish_protocols = loc_row.get("jewish_protocol_numbers") or ""
                history_photos_json = loc_row.get("history_photos") or "[]"
            except Exception as e:
                messagebox.showerror("❌ Błąd", f"Błąd odczytu miejscowości SQLite: {e}", parent=self)
                return
        elif not check_postgres_available():
            messagebox.showerror("❌ Błąd", "PostgreSQL nie jest dostępny!", parent=self)
            return
        else:
            try:
                conn = get_launcher_postgres_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT name, full_name, powiat, region, year, century,
                           homepage_description, history_paragraph1, history_paragraph2, history_paragraph3,
                           postgres_db_name, homepage_template, gmina_katastralna,
                           jewish_protocol_numbers
                    FROM locations WHERE id = %s
                """, (loc_id,))
                result = cursor.fetchone()

                if result:
                    (name, full_name, powiat, region, year, century,
                     homepage_desc, history_p1, history_p2, history_p3, postgres_db_name, homepage_template,
                     gmina_katastralna, jewish_protocols) = result
                    postgres_db_name = postgres_db_name or ""
                    homepage_template = homepage_template or "standardowy"
                    gmina_katastralna = gmina_katastralna or "Czarna"
                    jewish_protocols = jewish_protocols or ""

                    # Pobierz zdjęcia historyczne
                    cursor.execute("""
                        SELECT filename, caption
                        FROM history_photos
                        WHERE location_id = %s
                        ORDER BY order_index
                    """, (loc_id,))
                    photos_rows = cursor.fetchall()
                    history_photos_json = json.dumps([
                        {"filename": row[0], "caption": row[1]}
                        for row in photos_rows
                    ], ensure_ascii=False)
                else:
                    messagebox.showerror("❌ Błąd", "Nie znaleziono miejscowości", parent=self)
                    cursor.close()
                    conn.close()
                    return

                cursor.close()
                conn.close()
            except Exception as e:
                print(f"❌ PostgreSQL błąd: {e}")
                messagebox.showerror("❌ Błąd", f"Błąd podczas pobierania danych: {e}", parent=self)
                return

        # Ustaw domyślne wartości jeśli None
        year = year or "1882"
        century = century or "XIX w."
        homepage_desc = homepage_desc or "Odkryj historię zapisaną w ziemi."
        history_p1 = history_p1 or ""
        history_p2 = history_p2 or ""
        history_p3 = history_p3 or ""

        # Sparsuj history_photos z JSON
        try:
            history_photos = json.loads(history_photos_json) if history_photos_json else []
        except (json.JSONDecodeError, TypeError):
            history_photos = []

        dialog = AddEditLocationDialog(self, "Edytuj Miejscowość", name, full_name, powiat, region, year, century,
                                      homepage_desc, history_p1, history_p2, history_p3,
                                      history_photos, postgres_db_name, homepage_template,
                                      gmina_katastralna, jewish_protocols)
        self.wait_window(dialog)

        if hasattr(dialog, 'result') and dialog.result:
            (new_name, new_full_name, new_powiat, new_region, new_year, new_century,
             new_homepage_desc, new_history_p1, new_history_p2, new_history_p3,
             new_history_photos, new_postgres_db_name, new_homepage_template,
             new_gmina_katastralna, new_jewish_protocols, new_historical_points) = dialog.result
            try:
                update_location(int(loc_id), new_name, new_full_name, new_powiat, new_region, new_year, new_century,
                              new_homepage_desc, new_history_p1, new_history_p2, new_history_p3,
                              new_history_photos, new_postgres_db_name, new_homepage_template,
                              new_gmina_katastralna, new_jewish_protocols)

                # Zapisz punkty historyczne do pliku JSON (obok parcels_data.json)
                _persist_historical_points(new_name, new_historical_points)

                # Jeśli edytowana miejscowość jest aktywna, wygeneruj nowy plik JS
                active_location = get_engine().get_active_location()
                if active_location and active_location[0] == int(loc_id):
                    generate_location_config_js()
                    # Zaktualizuj również stronę główną
                    template = active_location[6] if len(active_location) > 6 else "standardowy"
                    apply_homepage_template(template)

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
                                   "Zostanie usunięte:\n"
                                   "• Baza danych PostgreSQL\n"
                                   "• Cały folder z danymi\n"
                                   "• Konfiguracja miejscowości",
                                   parent=self):
            return

        try:
            delete_location(int(loc_id))
            messagebox.showinfo("✅ Sukces", f"Usunięto miejscowość: {name}", parent=self)
            self.refresh_table()
        except ValueError as e:
            messagebox.showerror("❌ Błąd", str(e), parent=self)

    def change_template(self):
        """Zmienia szablon strony dla wybranej miejscowości."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Wybierz miejscowość aby zmienić szablon", parent=self)
            return

        values = self.tree.item(selected[0], "values")
        loc_id, name = values[0], values[1]

        # Otwórz okno wyboru szablonu
        dialog = TemplateChangeDialog(self, int(loc_id), name)
        self.wait_window(dialog)

        # Odśwież tabelę
        self.refresh_table()

    def set_active(self):
        """Ustawia wybraną miejscowość jako aktywną."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("⚠️ Brak zaznaczenia", "Wybierz miejscowość do aktywacji", parent=self)
            return

        values = self.tree.item(selected[0], "values")
        loc_id, name = values[0], values[1]

        set_active_location(int(loc_id))

        # Odśwież ikonę aplikacji dla nowej miejscowości
        if hasattr(self.master, 'set_window_icon'):
            self.master.set_window_icon()

        messagebox.showinfo("✅ Sukces", f"Ustawiono jako aktywną: {name}\nZastosowano szablon strony dla tej miejscowości.", parent=self)
        self.refresh_table()
