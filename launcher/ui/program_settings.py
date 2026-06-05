"""Centralny panel ustawień programu dla launchera — zablokowane piksele."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, ttk

from ..config.paths import BACKEND_DIR, BASE_DIR, POSTGRES_CONFIG_FILE
from ..config.settings import COLORS, DEFAULT_LOCATION_NAME, SCRIPTS
from ..db.postgres import (
    change_pg_password as postgres_change_pg_password,
    create_database as postgres_create_database,
    database_exists as postgres_database_exists,
    enable_postgis as postgres_enable_postgis,
    execute_schema as postgres_execute_schema,
    get_postgres_config,
    has_postgis_extension as postgres_has_postgis_extension,
    save_pg_config_to_env_files,
)
from ..db.engine import switch_engine
from ..db.schemas import LAUNCHER_DB_SCHEMA
from ..services import test_service
from ..services.system_diagnostics import detect_pgadmin_path, init_location_database
from ..utils import set_dialog_icon, scale_wrap
from ..utils.env_config import _read_backend_env_value

# === Import nowych stylów ===
from .styles import (
    CARD_BG, SURFACE_BG, HEADER_BG, HEADER_FG, HEADER_SUB_FG,
    BORDER_COLOR, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, KPI_BG,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL, SPACING_XXL,
    create_card, create_kpi, create_separator, create_badge,
)


# =============================================================================
# Stałe wymiarów okna — SKALOWANE z UI scale
# =============================================================================
BASE_WIN_W = 1020
BASE_WIN_H = 900
KPI_WIDTH = 155
TAB_PAD = 10
PG_SYSTEM_INSTALL_DIR = r"C:\Program Files\PostgreSQL\16"
PG_SYSTEM_SERVICE_NAME = "postgresql-x64-16"


def _is_postgres_system_installed() -> bool:
    """Czy systemowy PostgreSQL 16 wygląda na zainstalowany."""
    if os.path.exists(os.path.join(PG_SYSTEM_INSTALL_DIR, "uninstall-postgresql.exe")):
        return True
    if os.path.exists(os.path.join(PG_SYSTEM_INSTALL_DIR, "bin", "psql.exe")):
        return True
    try:
        result = subprocess.run(
            ["sc", "query", PG_SYSTEM_SERVICE_NAME],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
        )
        return result.returncode == 0 and PG_SYSTEM_SERVICE_NAME in (result.stdout or "")
    except Exception:
        return False


class ProgramSettingsWindow(tk.Toplevel):
    """Centralny panel ustawień i diagnostyki launchera — pixel-locked."""

    QUICK_SCALES = [0.90, 1.00, 1.10, 1.25, 1.50]

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        self.title("Ustawienia programu")
        set_dialog_icon(self)
        self.transient(parent)
        self.grab_set()

        # === ROZMIAR OKNA — skalowany wg ui_scale rodzica ===
        scale = getattr(parent, 'ui_scale', 1.0)
        win_w = max(int(BASE_WIN_W * scale), 800)
        win_h = max(int(BASE_WIN_H * scale), 600)
        self.geometry(f"{win_w}x{win_h}")
        self.minsize(800, 600)
        self.resizable(True, True)

        # === Zmienne ===
        self.guardian_enabled_var = tk.BooleanVar(value=bool(parent.guardian_enabled.get()))
        self.db_status_var = tk.StringVar(value="Wczytywanie...")
        self.db_details_var = tk.StringVar(value="")
        self.ui_scale_var = tk.StringVar(value=f"{int(round(parent.ui_scale * 100))}%")
        self.ui_scale_slider_var = tk.DoubleVar(value=int(round(parent.ui_scale * 100)))
        self.guardian_summary_var = tk.StringVar(value="")
        self.overall_status_var = tk.StringVar(value="Analiza systemu...")
        self.overall_hint_var = tk.StringVar(value="")
        self.overall_badge_var = tk.StringVar(value="ANALIZA")
        self.kpi_engine_var = tk.StringVar(value="—")
        self.kpi_backend_var = tk.StringVar(value="—")
        self.kpi_guard_var = tk.StringVar(value="—")
        self.kpi_location_var = tk.StringVar(value="—")
        self.actions_hint_var = tk.StringVar(value="")
        self._recent_actions = []

        self._build_ui()
        self.center_window()
        self.after(50, self._auto_resize)
        self.refresh_all()

    # =========================================================================
    # GEOMETRIA
    # =========================================================================
    def center_window(self):
        self.update_idletasks()
        px = self.parent_app.winfo_rootx()
        py = self.parent_app.winfo_rooty()
        pw = self.parent_app.winfo_width()
        ph = self.parent_app.winfo_height()
        w = self.winfo_width()
        h = self.winfo_height()
        x = max(px + (pw - w) // 2, 0)
        y = max(py + (ph - h) // 2, 0)
        self.geometry(f"+{x}+{y}")

    def _auto_resize(self):
        """Przy zablokowanym rozmiarze — tylko centruj."""
        self.update_idletasks()
        self.center_window()

    def _open_external(self, open_action):
        """Otwiera okno z poziomu ustawień: zwalnia grab i centruje nad panelem."""
        before = set()

        def _collect(parent):
            for child in parent.winfo_children():
                if isinstance(child, tk.Toplevel):
                    before.add(child)

        _collect(self.parent_app)
        _collect(self)

        self.grab_release()
        open_action()

        def _after():
            for parent in (self.parent_app, self):
                for child in parent.winfo_children():
                    if isinstance(child, tk.Toplevel) and child is not self and child not in before:
                        self._center_over(child)
                        return

        self.after(120, _after)

    def _center_over(self, window):
        """Centruje okno nad tym panelem."""
        try:
            window.update_idletasks()
            w = window.winfo_width() or window.winfo_reqwidth() or 400
            h = window.winfo_height() or window.winfo_reqheight() or 300
            x = self.winfo_rootx() + (self.winfo_width() - w) // 2
            y = self.winfo_rooty() + 20
            window.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

    # =========================================================================
    # BUDOWA UI — HEADER + KPI + NOTEBOOK + FOOTER
    # =========================================================================
    def _build_ui(self):
        # Tło okna
        self.configure(bg=SURFACE_BG)

        # === KOLEJNOŚĆ: footer i separator NAJPIERW (rezerwują miejsce na dole) ===

        # Separator na samym dole
        create_separator(self).pack(fill=tk.X, side=tk.BOTTOM)

        # Footer z przyciskami (nad separatorem)
        footer = tk.Frame(self, bg=SURFACE_BG)
        footer.pack(fill=tk.X, side=tk.BOTTOM, ipady=6)

        footer_inner = tk.Frame(footer, bg=SURFACE_BG)
        footer_inner.pack(fill=tk.BOTH, expand=True, padx=SPACING_XL, pady=8)

        ttk.Button(footer_inner, text="Odśwież wszystko",
                   command=self.refresh_all, style="Info.TButton").pack(side=tk.LEFT)
        ttk.Button(footer_inner, text="Zamknij",
                   command=self.destroy, style="Secondary.TButton").pack(side=tk.RIGHT)

        # === RESZTA: tytuł + KPI + notebook (wypełniają środek) ===

        # Tytuł
        title_frame = tk.Frame(self, bg=SURFACE_BG)
        title_frame.pack(fill=tk.X, padx=SPACING_XL, pady=(SPACING_SM, 0))
        tk.Label(title_frame, text="⚙ Ustawienia programu",
                 bg=SURFACE_BG, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        tk.Label(title_frame, text="  Konfiguracja, diagnostyka i kontrola Strażnika.",
                 bg=SURFACE_BG, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(8, 0))

        # KPI (kompaktowy)
        kpi_container = tk.Frame(self, bg=SURFACE_BG)
        kpi_container.pack(fill=tk.X, padx=SPACING_XL, pady=(4, 4))

        for i, (title, var) in enumerate([
            ("SILNIK DB", self.kpi_engine_var),
            ("BACKEND", self.kpi_backend_var),
            ("STRAŻNIK", self.kpi_guard_var),
            ("MIEJSCOWOŚĆ", self.kpi_location_var),
        ]):
            box = create_kpi(kpi_container, title, var, width=KPI_WIDTH)
            box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, SPACING_SM) if i < 3 else (0, 0))

        # Notebook
        notebook_frame = tk.Frame(self, bg=SURFACE_BG)
        notebook_frame.pack(fill=tk.BOTH, expand=True, padx=SPACING_XL, pady=(0, 4))

        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.general_tab = ttk.Frame(self.notebook, padding=TAB_PAD)
        self.database_tab = ttk.Frame(self.notebook, padding=TAB_PAD)
        self.interface_tab = ttk.Frame(self.notebook, padding=TAB_PAD)
        self.guardian_tab = ttk.Frame(self.notebook, padding=TAB_PAD)
        self.diagnostics_tab = ttk.Frame(self.notebook, padding=TAB_PAD)
        self.advanced_tab = ttk.Frame(self.notebook, padding=TAB_PAD)

        self.notebook.add(self.general_tab, text="  Ogólne  ")
        self.notebook.add(self.database_tab, text="  Baza danych  ")
        self.notebook.add(self.interface_tab, text="  Interfejs  ")
        self.notebook.add(self.guardian_tab, text="  Guard  ")
        self.notebook.add(self.diagnostics_tab, text="  Diagnostyka  ")
        self.notebook.add(self.advanced_tab, text="  Zaawansowane  ")

        self._build_general_tab()
        self._build_database_tab()
        self._build_interface_tab()
        self._build_guardian_tab()
        self._build_diagnostics_tab()
        self._build_advanced_tab()

        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.after(50, self._auto_resize))

    # =========================================================================
    # ZAKŁADKA: OGÓLNE
    # =========================================================================
    def _build_general_tab(self):
        # === 2×2 grid kart — każda zajmuje równą część miejsca ===
        grid = ttk.Frame(self.general_tab)
        grid.pack(fill=tk.BOTH, expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        # --- (0,0) Status operatora ---
        status_card = create_card(grid, "Status operatora")
        status_card.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))

        self.overall_status_label = tk.Label(
            status_card, textvariable=self.overall_status_var,
            bg=CARD_BG, fg=TEXT_PRIMARY,
            font=("Segoe UI", 13, "bold"), anchor="w")
        self.overall_status_label.pack(fill=tk.X, padx=SPACING_SM, pady=(SPACING_SM, 2))

        self.overall_hint_label = tk.Label(
            status_card, textvariable=self.overall_hint_var,
            bg=CARD_BG, fg=TEXT_SECONDARY,
            font=("Segoe UI", 9), anchor="w", wraplength=380, justify=tk.LEFT)
        self.overall_hint_label.pack(fill=tk.X, padx=SPACING_SM, pady=(0, 6))

        kpi_frame = ttk.Frame(status_card, style="Card.TFrame")
        kpi_frame.pack(fill=tk.X, padx=SPACING_SM, pady=(0, SPACING_SM))
        for idx in range(4):
            kpi_frame.columnconfigure(idx, weight=1)
        self._build_kpi_box(kpi_frame, 0, "Silnik DB", self.kpi_engine_var)
        self._build_kpi_box(kpi_frame, 1, "Backend", self.kpi_backend_var)
        self._build_kpi_box(kpi_frame, 2, "Strażnik", self.kpi_guard_var)
        self._build_kpi_box(kpi_frame, 3, "Miejscowość", self.kpi_location_var)

        # --- (0,1) Co naprawić ---
        todo_card = create_card(grid, "Co naprawić")
        todo_card.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))
        self.repair_summary = tk.Text(todo_card, height=6, wrap=tk.WORD,
                                       font=("Segoe UI", 10), bg=CARD_BG,
                                       relief="flat", highlightthickness=0,
                                       bd=0, padx=SPACING_SM, pady=SPACING_SM)
        self.repair_summary.pack(fill=tk.BOTH, expand=True, padx=SPACING_XS, pady=SPACING_XS)
        self.repair_summary.configure(state="disabled")

        # --- (1,0) Stan programu ---
        summary_card = create_card(grid, "Stan programu")
        summary_card.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(4, 0))
        self.general_summary = tk.Text(summary_card, height=6, wrap=tk.WORD,
                                        font=("Segoe UI", 10), bg=CARD_BG,
                                        relief="flat", highlightthickness=0,
                                        bd=0, padx=SPACING_SM, pady=SPACING_SM)
        self.general_summary.pack(fill=tk.BOTH, expand=True, padx=SPACING_XS, pady=SPACING_XS)
        self.general_summary.configure(state="disabled")

        # --- (1,1) Ostatnie akcje ---
        recent_card = create_card(grid, "Ostatnie akcje")
        recent_card.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))
        self.recent_actions_text = tk.Text(recent_card, height=6, wrap=tk.WORD,
                                            font=("Segoe UI", 10), bg=CARD_BG,
                                            relief="flat", highlightthickness=0,
                                            bd=0, padx=SPACING_SM, pady=SPACING_SM)
        self.recent_actions_text.pack(fill=tk.BOTH, expand=True, padx=SPACING_XS, pady=SPACING_XS)
        self.recent_actions_text.configure(state="disabled")

        # --- Napraw system (pod gridem) ---
        repairs_card = create_card(self.general_tab, "Napraw system")
        repairs_card.pack(fill=tk.X, pady=(4, 0))

        repair_row1 = ttk.Frame(repairs_card, style="Card.TFrame")
        repair_row1.pack(fill=tk.X, padx=SPACING_SM, pady=(0, 4))
        self.btn_repair_safe = ttk.Button(repair_row1, text="Napraw bezpieczne elementy",
                                           command=self.repair_safe_items, style="Success.TButton")
        self.btn_repair_safe.pack(side=tk.LEFT, padx=(0, SPACING_SM))
        self.btn_repair_and_recheck = ttk.Button(repair_row1, text="Napraw i sprawdź ponownie",
                                                  command=self.repair_and_recheck, style="Primary.TButton")
        self.btn_repair_and_recheck.pack(side=tk.LEFT, padx=(0, SPACING_SM))
        self.btn_test_postgres = ttk.Button(repair_row1, text="Test PostgreSQL",
                                            command=self.run_postgres_connection_test, style="Info.TButton")
        self.btn_test_postgres.pack(side=tk.LEFT, padx=(0, SPACING_XS))
        self.btn_run_guardian = ttk.Button(repair_row1, text="Sprawdź Strażnika",
                                           command=self.run_guardian_check_now, style="Info.TButton")
        self.btn_run_guardian.pack(side=tk.LEFT, padx=SPACING_XS)

        repair_row2 = ttk.Frame(repairs_card, style="Card.TFrame")
        repair_row2.pack(fill=tk.X, padx=SPACING_SM, pady=(0, 4))
        self.btn_create_launcher_db = ttk.Button(repair_row2, text="Utwórz bazę launcher",
                                                  command=self.create_launcher_database, style="Primary.TButton")
        self.btn_create_launcher_db.pack(side=tk.LEFT, padx=(0, SPACING_XS))
        self.btn_create_location_db = ttk.Button(repair_row2, text="Utwórz bazę miejscowości",
                                                  command=self.create_active_location_database, style="Success.TButton")
        self.btn_create_location_db.pack(side=tk.LEFT, padx=(0, SPACING_XS))
        self.btn_enable_postgis = ttk.Button(repair_row2, text="Włącz PostGIS",
                                              command=self.enable_postgis_for_active_database, style="Warning.TButton")
        self.btn_enable_postgis.pack(side=tk.LEFT, padx=SPACING_XS)

        self.actions_hint_label = tk.Label(
            repairs_card, textvariable=self.actions_hint_var,
            bg=CARD_BG, fg=TEXT_SECONDARY,
            font=("Segoe UI", 9), wraplength=820, justify=tk.LEFT, anchor="w")
        self.actions_hint_label.pack(fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_MD))

    # =========================================================================
    # ZAKŁADKA: BAZA DANYCH
    # =========================================================================
    def _build_database_tab(self):
        top_card = create_card(self.database_tab, "Status aktywnej bazy")
        top_card.pack(fill=tk.X, pady=(0, SPACING_SM))

        ttk.Label(top_card, textvariable=self.db_status_var,
                  font=("Segoe UI", 11, "bold"), style="Card.TLabel").pack(anchor=tk.W)
        ttk.Label(top_card, textvariable=self.db_details_var,
                  foreground=TEXT_SECONDARY, wraplength=820, justify=tk.LEFT).pack(
            anchor=tk.W, pady=(SPACING_XS, 0))

        actions = ttk.Frame(top_card, style="Card.TFrame")
        actions.pack(fill=tk.X, pady=(SPACING_SM, 0))
        self.btn_refresh_db_status = ttk.Button(actions, text="Odśwież status",
                                                command=self.refresh_database_status, style="Info.TButton")
        self.btn_refresh_db_status.pack(side=tk.LEFT, padx=(0, SPACING_XS))
        self.btn_open_db_config = ttk.Button(actions, text="Konfiguracja DB",
                                              command=lambda: self._open_external(self.parent_app.open_env_editor),
                                              style="Secondary.TButton")
        self.btn_open_db_config.pack(side=tk.LEFT, padx=SPACING_XS)
        self.btn_switch_db_engine = ttk.Button(actions, text="Zmień silnik DB",
                                               command=lambda: self._open_external(self.parent_app.open_db_engine_switcher),
                                               style="Warning.TButton")
        self.btn_switch_db_engine.pack(side=tk.LEFT, padx=SPACING_XS)

        # Konfiguracja połączenia (host / port / user / hasło / baza) —
        # pozwala edytować parametry PG bez otwierania kreatora ani edytora .env.
        self.pg_config_frame = self._build_pg_config_card(self.database_tab)
        self.pg_config_frame.pack(fill=tk.X, pady=(0, SPACING_SM))

        # PostgreSQL — narzędzia: napraw bazę + pgAdmin (scalona sekcja, kompaktowo)
        self.pg_actions_frame = create_card(self.database_tab, "PostgreSQL — narzędzia")
        self.pg_actions_frame.pack(fill=tk.X, pady=(0, SPACING_SM))
        pg_btn_frame = ttk.Frame(self.pg_actions_frame, style="Card.TFrame")
        pg_btn_frame.pack(fill=tk.X, padx=SPACING_MD, pady=(SPACING_SM, SPACING_XS))
        # 1 button zamiast 3 — helper ensure_postgres_database_with_postgis robi
        # całą robotę (test, create DB, PostGIS, schemat) idempotentnie.
        self.btn_pg_repair = ttk.Button(
            pg_btn_frame,
            text="🔧 Napraw aktywną bazę (PostGIS + schemat)",
            command=self.repair_active_database,
            style="Success.TButton",
        )
        self.btn_pg_repair.pack(side=tk.LEFT, padx=(0, SPACING_XS))
        # pgAdmin w tej samej sekcji — 1 linia: status + 2 buttony
        self.pgadmin_status_var = tk.StringVar(value="Sprawdzanie pgAdmin...")
        ttk.Label(
            pg_btn_frame, textvariable=self.pgadmin_status_var,
            foreground=TEXT_SECONDARY, justify=tk.LEFT,
        ).pack(side=tk.LEFT, padx=(SPACING_MD, SPACING_XS))
        self.btn_detect_pgadmin = ttk.Button(pg_btn_frame, text="Wykryj pgAdmin",
                                              command=self.refresh_database_status, style="Info.TButton")
        self.btn_detect_pgadmin.pack(side=tk.LEFT, padx=(0, SPACING_XS))
        self.btn_open_pgadmin = ttk.Button(pg_btn_frame, text="Otwórz pgAdmin",
                                            command=self.open_pgadmin, style="Primary.TButton")
        self.btn_open_pgadmin.pack(side=tk.LEFT, padx=SPACING_XS)
        # Backward-compat atrybuty (referencje używane w innych miejscach)
        self.btn_pg_test_connection = None  # usunięty duplikat; helper w formularzu wyżej
        self.btn_pg_create_launcher = None
        self.btn_pg_create_location = None
        self.btn_pg_enable_postgis = None
        self.pgadmin_frame = self.pg_actions_frame  # alias dla testów / innych referencji

        self.pg_service_frame = create_card(self.database_tab, "PostgreSQL — serwis i testy")
        self.pg_service_frame.pack(fill=tk.X, pady=(0, SPACING_SM))
        self.pg_service_status_var = tk.StringVar(value="Sprawdzanie instalacji PostgreSQL...")
        ttk.Label(
            self.pg_service_frame,
            textvariable=self.pg_service_status_var,
            font=("Segoe UI", 9, "bold"),
            wraplength=820,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=SPACING_MD, pady=(SPACING_SM, 0))
        pg_service_buttons = ttk.Frame(self.pg_service_frame, style="Card.TFrame")
        pg_service_buttons.pack(fill=tk.X, padx=SPACING_MD, pady=(SPACING_XS, SPACING_SM))
        self.btn_reset_pg_launcher = ttk.Button(
            pg_service_buttons,
            text="Przełącz na SQLite i wyczyść konfigurację PG",
            command=self.reset_postgres_launcher_config,
            style="Warning.TButton",
        )
        self.btn_reset_pg_launcher.pack(side=tk.LEFT, padx=(0, SPACING_XS))
        self.btn_uninstall_pg_system = ttk.Button(
            pg_service_buttons,
            text="Odinstaluj PostgreSQL 16 z systemu...",
            command=self.uninstall_postgres_system,
            style="Danger.TButton",
        )
        self.btn_uninstall_pg_system.pack(side=tk.LEFT, padx=SPACING_XS)

        self.pg_db_list_var = tk.StringVar(value="")
        self.pg_db_list_label = ttk.Label(
            self.database_tab,
            textvariable=self.pg_db_list_var,
            foreground=TEXT_SECONDARY,
            wraplength=820,
            justify=tk.LEFT,
        )
        self.pg_db_list_label.pack(anchor=tk.W, pady=(0, SPACING_XS))

        # Konsola zmniejszona z 12 → 6 linii (główna treść to diagnostyka a nie logi)
        self.db_console = scrolledtext.ScrolledText(
            self.database_tab, height=6, wrap=tk.WORD, font=("Consolas", 10),
            bg=CARD_BG, relief="flat", highlightthickness=0)
        self.db_console.pack(fill=tk.BOTH, expand=True)
        self.db_console.insert(tk.END, "Tutaj pojawi się diagnostyka i wyniki operacji bazodanowych.\n")
        self.db_console.configure(state="disabled")

    # =========================================================================
    # ZAKŁADKA: INTERFEJS
    # =========================================================================
    def _build_interface_tab(self):
        current_card = create_card(self.interface_tab, "Skala interfejsu")
        current_card.pack(fill=tk.X, pady=(0, SPACING_SM))

        ttk.Label(current_card, text="Aktualna skala:",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=SPACING_MD, pady=(SPACING_MD, 0))
        ttk.Label(current_card, textvariable=self.ui_scale_var,
                  font=("Segoe UI", 18, "bold"), foreground=COLORS['info']).pack(
            anchor=tk.W, padx=SPACING_MD, pady=(SPACING_XS, SPACING_SM))

        ttk.Label(current_card,
                  text="Zmiana działa także w trybie SQLite. Ustawienie zapisuje się lokalnie z fallbackiem do ustawień launchera.",
                  wraplength=820, justify=tk.LEFT).pack(anchor=tk.W, padx=SPACING_MD, pady=(0, SPACING_SM))

        slider_frame = ttk.Frame(current_card, style="Card.TFrame")
        slider_frame.pack(fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_SM))
        ttk.Label(slider_frame, text="Mniej").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.ui_scale_slider = ttk.Scale(
            slider_frame,
            from_=85,
            to=175,
            orient=tk.HORIZONTAL,
            variable=self.ui_scale_slider_var,
            command=self.on_interface_slider_changed,
        )
        self.ui_scale_slider.grid(row=0, column=1, sticky="ew")
        ttk.Label(slider_frame, text="Więcej").grid(row=0, column=2, sticky="w", padx=(8, 0))
        slider_frame.columnconfigure(1, weight=1)

        buttons = ttk.Frame(current_card, style="Card.TFrame")
        buttons.pack(fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_MD))
        ttk.Button(buttons, text="Zastosuj skalę",
                   command=self.apply_slider_scale,
                   style="Success.TButton").pack(side=tk.LEFT, padx=(0, SPACING_SM))
        ttk.Button(buttons, text="Pełne okno skali UI",
                   command=lambda: self._open_external(self.parent_app.open_display_settings),
                   style="Primary.TButton").pack(side=tk.LEFT, padx=(0, SPACING_SM))
        for percent in (100, 125, 135, 140, 150):
            ttk.Button(buttons, text=f"{percent}%",
                       command=lambda p=percent: self.set_interface_slider_percent(p),
                       style="Info.TButton", width=6).pack(side=tk.LEFT, padx=2)

        hint_card = create_card(self.interface_tab, "Uwaga UX")
        hint_card.pack(fill=tk.BOTH, expand=True)
        ttk.Label(hint_card,
                  text=("Nowy panel ma zastąpić rozproszone okna i stopniowo przejmować konfiguracjęję programu.\n"
                        "Stare okno 'Skala UI' nadal działa, ale teraz jest też dostępne z poziomu centrum ustawień."),
                  justify=tk.LEFT, wraplength=820).pack(anchor=tk.W, padx=SPACING_MD, pady=SPACING_MD)

    # =========================================================================
    # ZAKŁADKA: GUARD
    # =========================================================================
    def _build_guardian_tab(self):
        # --- Opis co to jest Strażnik ---
        info = tk.Label(self.guardian_tab,
                        text="Strażnik to system monitoringu danych działający w tle. Automatycznie sprawdza "
                             "spójność baz danych, kompletność zasobów i integralność danych. "
                             "Możesz uruchomić kontrolę ręcznie lub pozostawić Strażnika w trybie ciągłym.",
                        bg=SURFACE_BG, fg=TEXT_SECONDARY,
                        font=("Segoe UI", 9), wraplength=900, justify=tk.LEFT, anchor="w")
        info.pack(fill=tk.X, pady=(0, 6))

        # --- Górny rząd: status + checkboxy + przycisk obok siebie ---
        top_row = ttk.Frame(self.guardian_tab)
        top_row.pack(fill=tk.X, pady=(0, 6))
        top_row.columnconfigure(0, weight=1)
        top_row.columnconfigure(1, weight=3)

        # Status Strażnika (lewa kolumna)
        state_card = create_card(top_row, "Status Strażnika")
        state_card.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        # --- Wskaźnik statusu (duży) ---
        self.guardian_status_label = tk.Label(
            state_card, textvariable=self.guardian_summary_var,
            bg=CARD_BG, fg=TEXT_PRIMARY,
            font=("Segoe UI", 13, "bold"), anchor="w")
        self.guardian_status_label.pack(fill=tk.X, padx=SPACING_MD, pady=(SPACING_MD, 0))

        self.guardian_meta_var = tk.StringVar(value="")
        tk.Label(state_card, textvariable=self.guardian_meta_var,
                 bg=CARD_BG, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9), anchor="w", wraplength=350).pack(
            fill=tk.X, padx=SPACING_MD, pady=(2, SPACING_SM))

        # --- Separator ---
        tk.Frame(state_card, bg=BORDER_COLOR, height=1).pack(
            fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_SM))

        # --- Szczegóły (siatka 2×2) ---
        details = tk.Frame(state_card, bg=CARD_BG)
        details.pack(fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_SM))
        details.columnconfigure(0, weight=1)
        details.columnconfigure(1, weight=1)

        self.guardian_last_check_var = tk.StringVar(value="Ostatnie sprawdzenie: —")
        self.guardian_issues_var = tk.StringVar(value="Problemy: —")
        self.guardian_duration_var = tk.StringVar(value="Czas trwania: —")
        self.guardian_mode_var = tk.StringVar(value="Tryb: ręczny")

        for r, (var, icon) in enumerate([
            (self.guardian_last_check_var, "📅"),
            (self.guardian_issues_var, "🔍"),
            (self.guardian_duration_var, "⏱️"),
            (self.guardian_mode_var, "⚙️"),
        ]):
            col = r % 2
            row = r // 2
            tk.Label(details, textvariable=var, bg=CARD_BG, fg=TEXT_SECONDARY,
                     font=("Segoe UI", 9), anchor="w").grid(
                row=row, column=col, sticky="w", padx=(0, SPACING_SM), pady=2)

        # --- Separator ---
        tk.Frame(state_card, bg=BORDER_COLOR, height=1).pack(
            fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_SM))

        # --- Kontrolki ---
        controls = ttk.Frame(state_card, style="Card.TFrame")
        controls.pack(fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_MD))
        ttk.Checkbutton(controls, text="Automatycznie w tle",
                        variable=self.guardian_enabled_var, command=self.toggle_guardian).pack(side=tk.LEFT)
        self.btn_guardian_run_now = ttk.Button(controls, text="Uruchom teraz",
                                               command=self.run_guardian_check_now, style="Success.TButton")
        self.btn_guardian_run_now.pack(side=tk.RIGHT, padx=(4, 0))

        # Checkboxy testów (prawa kolumna)
        options_card = create_card(top_row, "Wybierz testy")
        options_card.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        if not hasattr(self.parent_app, 'test_vars'):
            self.parent_app.test_vars = {}
        # Idempotentnie dopisz nowe klucze (np. integration) nawet gdy app.test_vars
        # powstalo w starszym widoku launchera.
        for key, value in test_service.DEFAULT_TEST_VARS.items():
            if key not in self.parent_app.test_vars:
                self.parent_app.test_vars[key] = tk.BooleanVar(value=value)

        cb_grid = ttk.Frame(options_card, style="Card.TFrame")
        cb_grid.pack(fill=tk.X, padx=SPACING_SM, pady=(SPACING_SM, SPACING_SM))
        tests_info = [
            ("unit", "🧪 Jednostkowe"), ("integration", "🔗 Integracja/Admin"), ("e2e", "🤖 Robot (E2E)"), ("logic", "🌳 Rodowód"),
            ("sql", "🔍 Spójność SQL"), ("duplicates", "👥 Anti-Duplikat"), ("spatial", "📐 Geodezja"),
            ("resources", "🖼️ Zasoby"), ("gaps", "📅 Chronologia"), ("backups", "🏰 Twierdza"),
            ("encoding", "🔤 Krzaki"), ("wcag", "♿ Dostępność"), ("perf", "⚡ Wydajność"),
            ("security", "🔒 Bezpieczeństwo"),
        ]
        for i, (key, label) in enumerate(tests_info):
            row = i // 2
            col = i % 2
            ttk.Checkbutton(cb_grid, text=label,
                            variable=self.parent_app.test_vars[key],
                            style="Small.TCheckbutton").grid(
                row=row, column=col, padx=SPACING_SM, pady=2, sticky="w")

        # --- Przycisk URUCHOM (pełna szerokość) ---
        btn_frame = ttk.Frame(self.guardian_tab)
        btn_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(
            btn_frame, text="▶  URUCHOM WYBRANE TESTY",
            command=lambda: self._run_selected_tests(),
            style="Success.TButton",
        ).pack(side=tk.LEFT, padx=0, fill=tk.X, expand=True)

        # --- Dolne przyciski (na dole) ---
        bottom_frame = ttk.Frame(self.guardian_tab)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))
        ttk.Button(bottom_frame, text="Kopiuj do schowka",
                   command=self._copy_test_logs).pack(side=tk.LEFT, padx=SPACING_XS)
        ttk.Button(bottom_frame, text="Zapisz jako .log",
                   command=self._save_test_logs).pack(side=tk.LEFT, padx=SPACING_XS)

        # --- Konsola testów (wypełnia resztę miejsca) ---
        ttk.Label(self.guardian_tab, text="Konsola testów:",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(2, 2))
        console_box = ttk.Frame(self.guardian_tab)
        console_box.pack(fill=tk.BOTH, expand=True)
        self.test_console = self.parent_app.create_console_widget(console_box)
        self.test_console.configure(height=12)

    # =========================================================================
    # ZAKŁADKA: DIAGNOSTYKA
    # =========================================================================
    def _build_diagnostics_tab(self):
        # Karta 1: szybka diagnostyka systemowa (silnik DB, ścieżki, health)
        sys_box = create_card(self.diagnostics_tab, "Szybka diagnostyka systemu")
        sys_box.pack(fill=tk.X, expand=False, pady=(0, SPACING_SM))
        self.diagnostics_text = scrolledtext.ScrolledText(
            sys_box, height=8, wrap=tk.WORD, font=("Consolas", 10),
            bg=CARD_BG, relief="flat", highlightthickness=0)
        self.diagnostics_text.pack(fill=tk.BOTH, expand=True, padx=SPACING_SM, pady=SPACING_SM)
        self.diagnostics_text.configure(state="disabled")

        # Karta 2: jakość danych (9 metryk z backendu)
        self._build_data_quality_card(self.diagnostics_tab)

        # Karta 3: bezpieczeństwo admina (Priorytet 6.5)
        self._build_security_card(self.diagnostics_tab)

    def _build_data_quality_card(self, parent):
        """Karta pokazująca 9 metryk jakości danych z /api/admin/diagnostics.

        Backend liczy metryki po stronie serwera (single source of truth).
        Launcher tylko je wyświetla + odświeża na żądanie.
        """
        box = create_card(parent, "Jakość danych")
        box.pack(fill=tk.BOTH, expand=True)

        # Opis + przycisk odświeżania
        header = ttk.Frame(box, style="Card.TFrame")
        header.pack(fill=tk.X, padx=SPACING_MD, pady=(SPACING_MD, SPACING_SM))
        tk.Label(
            header,
            text="Działki bez właściciela, osoby bez dat, powiązania, itd. "
                 "Backend: GET /api/admin/diagnostics",
            bg=CARD_BG, fg=TEXT_SECONDARY, wraplength=820, justify=tk.LEFT,
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, anchor=tk.W)
        self.refresh_quality_btn = ttk.Button(
            header, text="🔄 Odśwież z backendu",
            command=self._refresh_data_quality,
        )
        self.refresh_quality_btn.pack(side=tk.RIGHT)

        # Pole tekstowe z wynikami
        self.data_quality_text = scrolledtext.ScrolledText(
            box, height=14, wrap=tk.WORD, font=("Consolas", 9),
            bg=CARD_BG, relief="flat", highlightthickness=0,
        )
        self.data_quality_text.pack(fill=tk.BOTH, expand=True, padx=SPACING_SM, pady=SPACING_SM)
        self.data_quality_text.configure(state="disabled")
        # Placeholder - użytkownik musi kliknąć Odśwież
        self._set_data_quality_text(
            "Kliknij 'Odśwież z backendu' aby pobrać 9 metryk jakości danych."
        )

    def _set_data_quality_text(self, text: str):
        self.data_quality_text.configure(state="normal")
        self.data_quality_text.delete("1.0", tk.END)
        self.data_quality_text.insert("1.0", text)
        self.data_quality_text.configure(state="disabled")

    def _refresh_data_quality(self):
        """Pobiera metryki jakości z /api/admin/diagnostics w wątku tła."""
        self.refresh_quality_btn.configure(state="disabled", text="⏳ Pobieranie…")
        # HTTP w tle (nie blokuj UI launchera)
        thread = threading.Thread(target=self._fetch_data_quality_sync, daemon=True)
        thread.start()

    def _fetch_data_quality_sync(self):
        """Wykonuje HTTP GET i aktualizuje ``data_quality_text`` w głównym wątku."""
        backend_url = self._get_backend_url()
        url = f"{backend_url}/api/admin/diagnostics"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            text = self._format_diagnostics_payload(payload)
        except urllib.error.HTTPError as exc:
            text = (
                f"❌ Błąd HTTP {exc.code} {exc.reason}\n"
                f"URL: {url}\n"
                f"Sprawdź czy admin auth jest wyłączony (ADMIN_AUTH_ENABLED=0) "
                f"lub zaloguj się w przeglądarce."
            )
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            text = (
                f"❌ Backend niedostępny: {exc}\n"
                f"URL: {url}\n"
                f"Uruchom backend przyciskiem 'Uruchom serwer' w launcherze."
            )
        except Exception as exc:  # noqa: BLE001
            text = f"❌ Nieoczekiwany błąd: {exc}"
        # Aktualizuj UI w głównym wątku
        try:
            self.diagnostics_tab.after(0, lambda: self._set_data_quality_text(text))
            self.diagnostics_tab.after(
                0,
                lambda: self.refresh_quality_btn.configure(
                    state="normal", text="🔄 Odśwież z backendu"
                ),
            )
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _format_diagnostics_payload(data: dict) -> str:
        """Formatuje dict z diagnostyki w czytelny raport tekstowy.

        Kolejność metryk = kolejność kart w panelu webowym.
        """
        order = [
            ("parcels_without_owners", "Działki bez właściciela"),
            ("owners_without_parcels", "Właściciele bez działek"),
            ("protocols_without_genealogy", "Protokoły bez genealogii"),
            ("people_without_parents", "Osoby bez rodziców"),
            ("people_without_birth_date", "Osoby bez daty urodzenia"),
            ("people_without_death_date", "Osoby bez daty śmierci"),
            ("parcels_without_category", "Działki bez kategorii"),
            ("owners_without_house_number", "Właściciele bez numeru domu"),
            ("parcel_owner_links", "Powiązania działka-właściciel"),
            ("incomplete_records", "Niepełne rekordy (agregat)"),
        ]
        lines = [
            "=== JAKOŚĆ DANYCH ===",
            f"Źródło: GET /api/admin/diagnostics",
            f"Czas pobrania: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        for key, label in order:
            value = data.get(key, {})
            count = value.get("count", 0) if isinstance(value, dict) else 0
            marker = "✅" if count == 0 else ("⚠️ " if count < 50 else "❌")
            lines.append(f"{marker} {label}: {count}")
        return "\n".join(lines)

    def _build_security_card(self, parent):
        """Karta 'Bezpieczeństwo admina' w zakładce Diagnostyka (Priorytet 6.5).

        Pokazuje: auth_enabled, hasło domyślne, SECRET_KEY, tryb produkcyjny,
        lista ostrzeżeń. Fetch z ``GET /api/admin/auth-status``.
        """
        security_box = create_card(parent, "Bezpieczeństwo admina")
        security_box.pack(fill=tk.BOTH, expand=True, pady=(0, SPACING_SM))

        info_label = ttk.Label(
            security_box,
            text=("Status autoryzacji admina, hasła i klucza SECRET_KEY. "
                  "Fetch: GET /api/admin/auth-status."),
            foreground="gray", wraplength=scale_wrap(self, 600),
        )
        info_label.pack(anchor=tk.W, padx=SPACING_MD, pady=(SPACING_MD, SPACING_SM))

        btn_row = ttk.Frame(security_box)
        btn_row.pack(fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_SM))
        self.security_refresh_btn = ttk.Button(
            btn_row, text="🔄 Odśwież status",
            command=self._refresh_security,
        )
        self.security_refresh_btn.pack(side=tk.LEFT, padx=2)

        self.security_text = scrolledtext.ScrolledText(
            security_box, height=10, wrap=tk.WORD, font=("Consolas", 10),
            bg=CARD_BG, relief="flat", highlightthickness=0,
        )
        self.security_text.pack(fill=tk.BOTH, expand=True, padx=SPACING_SM, pady=SPACING_SM)
        self.security_text.configure(state="disabled")

    def _set_security_text(self, text: str):
        """Helper - wpisuje tekst do self.security_text."""
        self.security_text.configure(state="normal")
        self.security_text.delete("1.0", tk.END)
        self.security_text.insert("1.0", text)
        self.security_text.configure(state="disabled")

    def _refresh_security(self):
        """Fetch ``/api/admin/auth-status`` w wątku tła, wynik wpisuje do widgetu."""
        import threading
        threading.Thread(target=self._fetch_security_sync, daemon=True).start()

    def _fetch_security_sync(self):
        """Synchroniczny GET /api/admin/auth-status, wyświetla wynik w UI."""
        import json
        from datetime import datetime
        import urllib.request
        from urllib.error import URLError, HTTPError
        try:
            url = f"{self._get_backend_url()}/api/admin/auth-status"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            formatted = self._format_security_status(data)
        except (URLError, ConnectionError) as exc:
            formatted = (
                "=== BEZPIECZEŃSTWO ADMINA ===\n"
                f"⚠️ Backend niedostępny: {exc}\n"
                "Uruchom backend aby zobaczyć aktualny stan bezpieczeństwa."
            )
        except HTTPError as exc:
            formatted = (
                "=== BEZPIECZEŃSTWO ADMINA ===\n"
                f"⚠️ Błąd HTTP {exc.code}: {exc.reason}\n"
            )
        except Exception as exc:
            formatted = (
                "=== BEZPIECZEŃSTWO ADMINA ===\n"
                f"⚠️ Nieoczekiwany błąd: {exc}\n"
            )
        # Update UI w głównym wątku
        self.diagnostics_tab.after(0, lambda: self._set_security_text(formatted))

    def _format_security_status(self, data: dict) -> str:
        """Formatuje payload ``/api/admin/auth-status`` w czytelny raport (Priorytet 6.5)."""
        from datetime import datetime
        auth_enabled = data.get("auth_enabled", False)
        using_default_pw = data.get("using_default_password", True)
        using_default_key = data.get("using_default_secret_key", True)
        is_prod = data.get("is_production", False)
        warnings = data.get("warnings", []) or []

        # Etykiety + emoji
        auth_mark = "✅" if auth_enabled else "❌"
        pw_mark = "✅" if (auth_enabled and not using_default_pw) else ("⚠️ " if auth_enabled else "—")
        key_mark = "✅" if not using_default_key else "❌"
        prod_mark = "🚨 TAK" if is_prod else "🧪 dev"

        lines = [
            "=== BEZPIECZEŃSTWO ADMINA ===",
            f"Źródło: GET /api/admin/auth-status",
            f"Czas pobrania: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        f"{auth_mark} Autoryzacja: {'WŁĄCZONA' if auth_enabled else 'WYŁĄCZONA'}",
        f"{pw_mark} Hasło: {'własne' if (auth_enabled and not using_default_pw) else 'domyślne (admin123)' if auth_enabled else '—'}",
        f"{key_mark} SECRET_KEY: {'własny' if not using_default_key else 'domyślny (dev-secret-change-me)'}",
        f"Produkcja: {prod_mark}",
        ]
        if warnings:
            lines.append("")
            lines.append(f"⚠️  OSTRZEŻENIA ({len(warnings)}):")
            for w in warnings:
                lines.append(f"  • {w}")
        else:
            lines.append("")
            lines.append("✅ Brak ostrzeżeń - konfiguracja bezpieczna.")
        return "\n".join(lines)

    def _get_backend_url(self) -> str:
        """Zwraca URL backendu (domyślnie http://127.0.0.1:5000)."""
        from ..config.settings import URLS
        # URLS["backend"] zwraca "http://host:port/" — obcinamy trailing slash
        url = URLS.get("backend", "http://127.0.0.1:5000/")
        return url.rstrip("/")

    # =========================================================================
    # ZAKŁADKA: ZAAWANSOWANE
    # =========================================================================
    def _build_advanced_tab(self):
        admin_card = create_card(self.advanced_tab, "Administracja")
        admin_card.pack(fill=tk.X, pady=(0, SPACING_SM))

        tk.Label(admin_card,
                 text="Rzadziej używane akcje przeniesione z głównego ekranu. Używaj ich świadomie.",
                 bg=CARD_BG, fg=TEXT_SECONDARY, wraplength=820, justify=tk.LEFT,
                 font=("Segoe UI", 10)).pack(anchor=tk.W, padx=SPACING_MD, pady=(SPACING_MD, SPACING_SM))

        row1 = ttk.Frame(admin_card, style="Card.TFrame")
        row1.pack(fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_SM))
        for text, cmd, style in [
            ("Kreator baz danych", lambda: self._open_external(self.parent_app.open_database_wizard), "Primary"),
            ("Ustawienia Administratora", lambda: self._open_external(self.parent_app.open_admin_settings), "Warning"),
        ]:
            ttk.Button(row1, text=text, command=cmd, style=f"{style}.TButton").pack(
                side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        row2 = ttk.Frame(admin_card, style="Card.TFrame")
        row2.pack(fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_MD))
        for text, cmd, style in [
            ("Ustawienia Witryny", lambda: self._open_external(self.parent_app.open_site_settings), "Primary"),
            ("Wybierz Ikony", lambda: self._open_external(self.parent_app.change_taskbar_icon), "Info"),
        ]:
            ttk.Button(row2, text=text, command=cmd, style=f"{style}.TButton").pack(
                side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        note_card = create_card(self.advanced_tab, "Porządek launchera")
        note_card.pack(fill=tk.BOTH, expand=True)
        tk.Label(note_card,
                 text=("Główny ekran jest teraz pulpitem codziennej pracy. "
                       "Konfiguracja, administracja, migracje i testy są zebrane tutaj, "
                       "żeby nie mieszać ich z uruchamianiem mapy."),
                 bg=CARD_BG, fg=TEXT_SECONDARY,
                 wraplength=820, justify=tk.LEFT,
                 font=("Segoe UI", 10)).pack(anchor=tk.W, padx=SPACING_MD, pady=SPACING_MD)

    # =========================================================================
    # KPI BOX (w karcie Status operatora)
    # =========================================================================
    def _build_kpi_box(self, parent, column, title, value_var):
        box = tk.Frame(parent, bg=KPI_BG, highlightbackground=BORDER_COLOR,
                        highlightthickness=1, padx=8, pady=4)
        box.grid(row=0, column=column, sticky="ew", padx=3)
        tk.Label(box, text=title, bg=KPI_BG, fg=TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(anchor=tk.W)
        tk.Label(box, textvariable=value_var, bg=KPI_BG, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(1, 0))

    # =========================================================================
    # TESTY
    # =========================================================================
    def _run_selected_tests(self):
        """Uruchamia wybrane testy delegując do test_runtime (wspólna implementacja)."""
        app = self.parent_app
        selected = [k for k, v in app.test_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("Brak wyboru", "Zaznacz przynajmniej jeden zestaw testów.", parent=self)
            return

        # Ustaw konsolę testów na tę z program_settings,
        # żeby test_runtime używał jej zamiast własnej
        app.test_console = self.test_console

        # Deleguj do wspólnej implementacji w test_runtime
        # (która ma emoji, kolory i pełne formatowanie)
        from ..services import test_runtime
        from ..utils import get_active_location_name
        test_runtime.run_selected_tests(app, get_active_location_name)

    def _copy_test_logs(self):
        try:
            content = self.test_console.get(1.0, tk.END)
            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo("Skopiowano", "Logi w schowku.", parent=self)
        except Exception as e:
            messagebox.showerror("Błąd", str(e), parent=self)

    def _save_test_logs(self):
        try:
            filename = filedialog.asksaveasfilename(
                title="Zapisz logi testów", defaultextension=".log",
                filetypes=[("Logi", "*.log"), ("Tekst", "*.txt")],
                initialfile=f"test_report_{int(time.time())}.log", parent=self,
            )
            if filename:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(self.test_console.get(1.0, tk.END))
                messagebox.showinfo("Zapisano", f"Raport: {filename}", parent=self)
        except Exception as e:
            messagebox.showerror("Błąd", str(e), parent=self)

    # =========================================================================
    # POMOCNICZE
    # =========================================================================
    def _append_db_log(self, message):
        self.db_console.configure(state="normal")
        self.db_console.insert(tk.END, message.rstrip() + "\n")
        self.db_console.see(tk.END)
        self.db_console.configure(state="disabled")

    def _set_diagnostics_text(self, text):
        self.diagnostics_text.configure(state="normal")
        self.diagnostics_text.delete("1.0", tk.END)
        self.diagnostics_text.insert("1.0", text)
        self.diagnostics_text.configure(state="disabled")

    def _set_text_widget(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _record_action(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self._recent_actions.insert(0, entry)
        self._recent_actions = self._recent_actions[:12]
        self._set_text_widget(self.recent_actions_text, "\n".join(self._recent_actions))

    def _set_badge_state(self, text, color):
        self.overall_badge_var.set(text)

    # =========================================================================
    # OBLICZENIA I REFRESH
    # =========================================================================
    def _compute_repair_items(self, db, guard):
        items = []
        if db.get("mode") == "postgresql":
            if not db.get("connection_ok"):
                items.append("PostgreSQL nie odpowiada — sprawdź host, port, użytkownika i hasło.")
            if db.get("connection_ok") and not db.get("launcher_db_exists"):
                items.append("Brakuje bazy mapa_launcher_db — utwórz ją jednym kliknięęciem.")
            if db.get("connection_ok") and db.get("launcher_db_exists") and not db.get("launcher_postgis"):
                items.append("W bazie launcher nie ma PostGIS — warto go włączyć dla pełnej zgodności.")
            if db.get("connection_ok") and not db.get("location_db_exists"):
                items.append(f"Brakuje bazy aktywnej miejscowości: {db.get('location_db_name')}.")
            if db.get("connection_ok") and db.get("location_db_exists") and not db.get("location_postgis"):
                items.append(f"Aktywna baza {db.get('location_db_name')} nie ma PostGIS.")
            if not db.get("pgadmin_available"):
                items.append("pgAdmin nie został wykryty lokalnie — to opcjonalne, ale przydatne narzędzie diagnostyczne.")
        else:
            if not db.get("sqlite_exists"):
                items.append("Plik SQLite jeszcze nie istnieje — zostanie utworzony automatycznie przy pierwszym użyciu.")
        if not guard.get("enabled"):
            items.append("Strażnik jest wyłączony — włącz go, jeśli chcesz automatyczną kontrolę danych w tle.")
        elif isinstance(guard.get("last_issues"), int) and guard.get("last_issues", 0) > 0:
            items.append(f"Strażnik wykrył uwagi: {guard.get('last_issues')} modułów wymaga sprawdzenia.")
        elif guard.get("last_check_at") is None and guard.get("enabled"):
            items.append("Strażnik nie ukończył jeszcze żadnego sprawdzenia w tej sesji — uruchom kontrolę ręcznie.")
        health = db.get("backend_health")
        if db.get("backend_running") and health and not health.get("ok"):
            items.append("Backend działa, ale /api/health nie odpowiada poprawnie — sprawdź logi backendu.")
        return items

    def refresh_all(self):
        self.refresh_general_summary()
        self.refresh_database_status()
        self.refresh_guardian_status()
        self.refresh_diagnostics_tab()
        self.update_action_states()
        self.ui_scale_var.set(f"{int(round(self.parent_app.ui_scale * 100))}%")
        self.ui_scale_slider_var.set(int(round(self.parent_app.ui_scale * 100)))
        if not self._recent_actions:
            self._set_text_widget(self.recent_actions_text, "Brak ręcznych akcji w tej sesji panelu.")

    def update_action_states(self):
        db = self.parent_app.get_database_diagnostics()
        guard = self.parent_app.get_guardian_status_snapshot()
        is_sqlite = db.get("mode") == "sqlite"
        pg_connected = bool(db.get("connection_ok"))
        launcher_exists = bool(db.get("launcher_db_exists"))
        location_exists = bool(db.get("location_db_exists"))
        location_postgis = bool(db.get("location_postgis"))
        pgadmin_available = bool(db.get("pgadmin_available"))
        pg_system_installed = _is_postgres_system_installed()
        postgres_state = tk.NORMAL if not is_sqlite else tk.DISABLED
        postgres_connected_state = tk.NORMAL if (not is_sqlite and pg_connected) else tk.DISABLED
        self.btn_test_postgres.configure(state=postgres_state)
        self.btn_create_launcher_db.configure(state=postgres_connected_state if not launcher_exists else tk.DISABLED)
        self.btn_create_location_db.configure(state=postgres_connected_state if not location_exists else tk.DISABLED)
        self.btn_enable_postgis.configure(state=postgres_connected_state if (location_exists and not location_postgis) else tk.DISABLED)
        # Backward-compat: 4 buttony zastąpione jednym "Napraw aktywną bazę" — wyłączone (None).
        # Stare ustawienia stanu: nieaktywne, bo cała logika siedzi w formularzu połączenia.
        # (Sekcja "PostgreSQL — narzędzia" sama z siebie nie ma już tych 4 buttonów.)
        self.btn_open_pgadmin.configure(state=tk.NORMAL if pgadmin_available and not is_sqlite else tk.DISABLED)
        self.btn_detect_pgadmin.configure(state=postgres_state)
        self.btn_reset_pg_launcher.configure(state=tk.NORMAL)
        self.btn_uninstall_pg_system.configure(state=tk.NORMAL if pg_system_installed else tk.DISABLED)
        if pg_system_installed:
            self.pg_service_status_var.set("Wykryto PostgreSQL 16 w systemie — pełna deinstalacja jest dostępna.")
        else:
            self.pg_service_status_var.set(
                "Nie wykryto systemowego PostgreSQL 16 — deinstalacja jest nieaktywna. "
                "Do testowania flow użyj bezpiecznego resetu SQLite."
            )
        self.btn_repair_safe.configure(state=tk.NORMAL)
        self.btn_repair_and_recheck.configure(state=tk.NORMAL)
        self.btn_run_guardian.configure(state=tk.NORMAL)
        self.btn_guardian_run_now.configure(state=tk.NORMAL)
        hints = []
        if is_sqlite:
            hints.append("Tryb SQLite: akcje PostgreSQL są wyłączone.")
        elif not pg_connected:
            hints.append("PostgreSQL nie odpowiada: najpierw popraw połączenie.")
        else:
            if launcher_exists:
                hints.append("Baza launcher już istnieje.")
            if location_exists:
                hints.append(f"Baza aktywnej miejscowości ({db.get('location_db_name')}) już istnieje.")
            if location_exists and location_postgis:
                hints.append("PostGIS aktywnej bazy jest już włączony.")
            if not pgadmin_available:
                hints.append("pgAdmin nie został wykryty lokalnie.")
        if not guard.get("enabled"):
            hints.append("Strażnik jest wyłączony, ale test ręczny nadal jest dostępny.")
        self.actions_hint_var.set(" ".join(hints) if hints else "Akcje są gotowe do użycia zgodnie z aktualnym stanem systemu.")

    def refresh_general_summary(self):
        db = self.parent_app.get_database_diagnostics()
        guard = self.parent_app.get_guardian_status_snapshot()
        backend_status = "tak" if db.get("backend_running") else "nie"
        engine = f"{db.get('engine_label')} ({db.get('engine_name')})"
        lines = [
            f"Aktywna miejscowość: {db.get('active_location')}",
            f"Silnik bazy danych: {engine}",
            f"Backend uruchomiony: {backend_status}",
            f"Strażnik: {'włączony' if guard.get('enabled') else 'wyłączony'}",
            f"Status Strażnika: {guard.get('text')}",
        ]
        self.kpi_engine_var.set(db.get('engine_label') or '—')
        self.kpi_backend_var.set("Online" if db.get("backend_running") else "Offline")
        self.kpi_guard_var.set("Aktywny" if guard.get("enabled") else "Wylaczony")
        self.kpi_location_var.set(db.get('active_location') or DEFAULT_LOCATION_NAME)
        repair_items = self._compute_repair_items(db, guard)
        if repair_items:
            self.overall_status_var.set(f"Wymaga uwagi ({len(repair_items)})")
            self.overall_hint_var.set("System działa, ale są elementy konfiguracjęyjne lub diagnostyczne, które warto poprawić.")
            self._set_badge_state("WYMAGA UWAGI", COLORS['warning'])
        else:
            self.overall_status_var.set("System gotowy")
            self.overall_hint_var.set("Najważniejsze komponenty wyglądają poprawnie. Panel może służyć teraz głównie do monitoringu i szybkich akcji.")
            self._set_badge_state("SYSTEM OK", COLORS['success'])
        self._set_text_widget(self.general_summary, "\n".join(lines))
        self._set_text_widget(self.repair_summary, "\n".join(repair_items) if repair_items else "Brak krytycznych zalecen. System wygląda spójnie.")

    def refresh_database_status(self):
        data = self.parent_app.get_database_diagnostics()
        if data.get("mode") == "sqlite":
            exists = "istnieje" if data.get("sqlite_exists") else "nie istnieje jeszcze"
            size = data.get("sqlite_size", 0)
            self.db_status_var.set(f"SQLite — plik {exists}")
            self.db_details_var.set(f"Tryb uproszczony bez serwera. Ścieżka: {data.get('sqlite_path')} | Rozmiar: {size} B")
            self.pg_config_frame.pack_forget()
            self.pg_actions_frame.pack_forget()
            self.pgadmin_frame.pack_forget()
            if _is_postgres_system_installed():
                if not self.pg_service_frame.winfo_manager():
                    self.pg_service_frame.pack(fill=tk.X, pady=(0, SPACING_SM), before=self.pg_db_list_label)
            else:
                self.pg_service_frame.pack_forget()
            self.pg_db_list_var.set("Tryb SQLite — lista baz PostgreSQL i pgAdmin są nieaktywne.")
        else:
            if not self.pg_config_frame.winfo_manager():
                self.pg_config_frame.pack(fill=tk.X, pady=(0, SPACING_SM), before=self.pg_actions_frame)
            if not self.pg_service_frame.winfo_manager():
                self.pg_service_frame.pack(fill=tk.X, pady=(0, SPACING_SM), before=self.pg_db_list_label)
            conn_ok = data.get("connection_ok")
            launcher_ok = data.get("launcher_db_exists")
            loc_ok = data.get("location_db_exists")
            status_icon = "OK" if conn_ok and launcher_ok and loc_ok else ("UWAGA" if conn_ok else "BLAD")
            self.db_status_var.set(f"{status_icon} PostgreSQL — {'połączenie OK' if conn_ok else 'problem z połączeniem'}")
            self.db_details_var.set(
                f"Launcher DB: {'jest' if launcher_ok else 'brak'} | "
                f"PostGIS launcher: {'tak' if data.get('launcher_postgis') else 'nie'} | "
                f"Baza miejscowości ({data.get('location_db_name')}): {'jest' if loc_ok else 'brak'} | "
                f"PostGIS aktywnej bazy: {'tak' if data.get('location_postgis') else 'nie'} | "
                f"{data.get('connection_msg', '')}"
            )
            if not self.pg_actions_frame.winfo_manager():
                self.pg_actions_frame.pack(fill=tk.X, pady=(0, SPACING_SM))
            if not self.pgadmin_frame.winfo_manager():
                self.pgadmin_frame.pack(fill=tk.X, pady=(0, SPACING_SM))
            databases = data.get("databases") or []
            self.pg_db_list_var.set("Dostępne bazy na serwerze: " + ", ".join(databases) if databases else "Nie udało się pobrać listy baz albo serwer nie zwrócił danych.")
            self.pgadmin_status_var.set(f"Wykryto pgAdmin: {data.get('pgadmin_path')}" if data.get("pgadmin_available") else "Nie wykryto pgAdmin lokalnie. Można dodać go później lub uruchomić ręcznie.")

    def refresh_guardian_status(self):
        snapshot = self.parent_app.get_guardian_status_snapshot()
        self.guardian_enabled_var.set(bool(snapshot.get("enabled")))
        self.guardian_summary_var.set(snapshot.get("text", "Brak danych"))
        self.guardian_status_label.configure(foreground=snapshot.get("color") or COLORS['info'])
        last_check = snapshot.get("last_check_at")
        last_issues = snapshot.get("last_issues")
        last_duration = snapshot.get("last_duration")
        if last_check:
            last_check_text = last_check.strftime("%Y-%m-%d %H:%M:%S")
            self.guardian_last_check_var.set(f"Ostatnie sprawdzenie: {last_check_text}")
            self.guardian_issues_var.set(f"Problemy: {last_issues if last_issues is not None else '—'}")
            self.guardian_duration_var.set(f"Czas trwania: {last_duration if last_duration is not None else '—'} s")
            self.guardian_meta_var.set("")
        else:
            self.guardian_last_check_var.set("Ostatnie sprawdzenie: brak")
            self.guardian_issues_var.set("Problemy: —")
            self.guardian_duration_var.set("Czas trwania: —")
            self.guardian_meta_var.set("Brak zakończonego sprawdzenia w tej sesji.")
        self.guardian_mode_var.set("Tryb: automatyczny" if snapshot.get("enabled") else "Tryb: ręczny")
        if not snapshot.get("enabled"):
            self.guardian_summary_var.set("Strażnik wyłączony — monitoring tła nie pracuje")

    def refresh_diagnostics_tab(self):
        data = self.parent_app.get_database_diagnostics()
        guard = self.parent_app.get_guardian_status_snapshot()
        lines = [
            "=== DIAGNOSTYKA PROGRAMU ===",
            f"Silnik DB: {data.get('engine_label')} ({data.get('engine_name')})",
            f"Aktywna miejscowość: {data.get('active_location')}",
            f"Backend działa: {data.get('backend_running')}",
            f"Strażnik włączony: {guard.get('enabled')}",
            f"Status Strażnika: {guard.get('text')}",
            "",
        ]
        if data.get("mode") == "sqlite":
            lines.extend(["--- SQLite ---", f"Plik DB: {data.get('sqlite_path')}", f"Plik istnieje: {data.get('sqlite_exists')}", f"Rozmiar: {data.get('sqlite_size')} B"])
        else:
            cfg = data.get("postgres_config", {})
            lines.extend([
                "--- PostgreSQL ---",
                f"Host: {cfg.get('host')}",
                f"Port: {cfg.get('port')}",
                f"Użytkownik: {cfg.get('user')}",
                f"Launcher DB: {data.get('launcher_db_name')} -> {data.get('launcher_db_exists')}",
                f"PostGIS launcher: {data.get('launcher_postgis')}",
                f"Location DB: {data.get('location_db_name')} -> {data.get('location_db_exists')}",
                f"PostGIS aktywnej bazy: {data.get('location_postgis')}",
                f"Wszystkie bazy: {', '.join(data.get('databases') or [])}",
                f"pgAdmin: {data.get('pgadmin_path') or 'nie wykryto'}",
                f"Połączenie: {data.get('connection_msg')}",
            ])
        health = data.get("backend_health")
        if health:
            lines.extend(["", "--- Backend health ---", f"OK: {health.get('ok')}", f"Kod HTTP: {health.get('status_code')}", f"URL: {health.get('url', 'n/d')}", f"Payload: {health.get('payload')}", f"Błąd: {health.get('error', '')}"])
        self._set_diagnostics_text("\n".join(lines))

    # =========================================================================
    # AKCJE
    # =========================================================================
    def _normalized_slider_percent(self):
        percent = int(round(float(self.ui_scale_slider_var.get()) / 5) * 5)
        return max(85, min(percent, 175))

    def on_interface_slider_changed(self, _value=None):
        percent = self._normalized_slider_percent()
        self.ui_scale_slider_var.set(percent)
        self.ui_scale_var.set(f"{percent}%")

    def set_interface_slider_percent(self, percent):
        self.ui_scale_slider_var.set(percent)
        self.ui_scale_var.set(f"{percent}%")

    def apply_slider_scale(self):
        self.apply_quick_scale(self._normalized_slider_percent() / 100)

    def apply_quick_scale(self, scale):
        if self.parent_app.apply_ui_scale(scale, restart_now=False):
            self.ui_scale_var.set(f"{int(round(scale * 100))}%")

    def toggle_guardian(self):
        self.parent_app.guardian_enabled.set(self.guardian_enabled_var.get())
        self.parent_app.save_guardian_config()
        self.refresh_guardian_status()
        self.refresh_general_summary()
        self.refresh_diagnostics_tab()

    def run_guardian_check_now(self):
        self.parent_app.guardian_enabled.set(True)
        self.guardian_enabled_var.set(True)
        self.parent_app.save_guardian_config()
        self._record_action("Uruchomiono ręczną kontrolę Strażnika")
        self.parent_app.run_proactive_health_check()
        self.after(300, self.refresh_guardian_status)

    def reset_postgres_launcher_config(self):
        """Przełącza launcher na SQLite i usuwa lokalną konfigurację PG."""
        if not messagebox.askyesno(
            "Przełączyć na SQLite?",
            "To NIE odinstaluje PostgreSQL z systemu.\n\n"
            "Launcher zostanie przełączony na SQLite, a plik backend/.postgres.env "
            "zostanie usunięty. To bezpieczny reset do testowania flow instalacji.\n\n"
            "Kontynuować?",
            parent=self,
        ):
            return

        try:
            switch_engine("sqlite")
            if POSTGRES_CONFIG_FILE.exists():
                POSTGRES_CONFIG_FILE.unlink()
            os.environ["DB_ENGINE"] = "sqlite"
            for key in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"):
                os.environ.pop(key, None)
            self._record_action("Przełączono launcher na SQLite i wyczyszczono konfigurację PG")
            self._append_db_log("[SERWIS] DB_ENGINE=sqlite; usunięto backend/.postgres.env")
            self.refresh_all()
            messagebox.showinfo(
                "Gotowe",
                "Launcher przełączony na SQLite. Uruchom ponownie aplikację, aby w pełni odświeżyć stan.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("Błąd resetu", f"Nie udało się przełączyć na SQLite:\n{exc}", parent=self)

    def uninstall_postgres_system(self):
        """Uruchamia graficzną deinstalację PostgreSQL 16 z UAC."""
        if not messagebox.askyesno(
            "Odinstalować PostgreSQL 16?",
            "Ta operacja spróbuje odinstalować PostgreSQL 16 z systemu Windows.\n\n"
            "Uwaga: jeśli inne projekty używają PostgreSQL 16, też zostaną dotknięte. "
            "Po deinstalacji launcher zostanie przełączony na SQLite.\n\n"
            "Czy na pewno kontynuować?",
            icon="warning",
            parent=self,
        ):
            return
        if not messagebox.askyesno(
            "Potwierdzenie krytyczne",
            "Ostatnie potwierdzenie: uruchomić deinstalator PostgreSQL z uprawnieniami administratora?",
            icon="warning",
            parent=self,
        ):
            return

        script = BASE_DIR / "scripts" / "uninstall_pg_system.py"
        if not script.exists():
            messagebox.showerror("Brak skryptu", f"Nie znaleziono:\n{script}", parent=self)
            return

        python_executable = os.path.abspath(sys.executable)
        pythonw = os.path.join(os.path.dirname(python_executable), "pythonw.exe")
        runner = pythonw if os.path.exists(pythonw) else python_executable
        try:
            subprocess.Popen([runner, str(script)])
            self._record_action("Uruchomiono deinstalator PostgreSQL 16")
            self._append_db_log("[SERWIS] Uruchomiono scripts/uninstall_pg_system.py")
            # Nie pokazuj dodatkowego messageboxa „deinstalator uruchomiony”:
            # zasłania on właściwe okno procesu i może wyglądać jak zawieszony.
            # Deinstalator sam pokaże komunikat końcowy, a launcher zamykamy od
            # razu, żeby po zmianie DB_ENGINE nie trzymać starego stanu w pamięci.
            try:
                self.grab_release()
            except Exception:
                pass
            self.parent_app.after(100, self.parent_app.destroy)
        except Exception as exc:
            messagebox.showerror("Błąd uruchomienia", f"Nie udało się uruchomić deinstalatora:\n{exc}", parent=self)

    def run_postgres_connection_test(self):
        data = self.parent_app.get_database_diagnostics()
        if data.get("mode") != "postgresql":
            messagebox.showinfo("SQLite aktywne", "Diagnostyka PostgreSQL jest dostępna tylko po przełączeniu na PostgreSQL.", parent=self)
            return
        self._record_action("Wykonano test połączenia PostgreSQL")
        self._append_db_log(f"[TEST] PostgreSQL: {data.get('connection_msg')}")
        self.refresh_all()

    def repair_safe_items(self):
        db = self.parent_app.get_database_diagnostics()
        guard = self.parent_app.get_guardian_status_snapshot()
        actions_done = []
        warnings = []
        if db.get("mode") == "sqlite":
            if guard.get("enabled") and guard.get("last_check_at") is None:
                self._append_db_log("[AUTO] Uruchamiam pierwszą kontrolę Strażnika dla trybu SQLite")
                self.run_guardian_check_now()
                actions_done.append("uruchomiono kontrolę Strażnika")
            if not actions_done:
                messagebox.showinfo("Brak bezpiecznych napraw", "W trybie SQLite nie było nic do automatycznej naprawy.\n\nPlik bazy SQLite tworzy sie sam przy pierwszym uzyciu.", parent=self)
            else:
                self._record_action("Wykonano bezpieczne naprawy w trybie SQLite")
                messagebox.showinfo("Naprawy zakończone", "Wykonano: " + ", ".join(actions_done), parent=self)
            self.refresh_all()
            return
        if not db.get("connection_ok"):
            messagebox.showwarning("Brak połączenia z PostgreSQL", "Automatyczna bezpieczna naprawa nie może ruszyć bez działającego połączenia z PostgreSQL.\n\nNajpierw popraw konfiguracjęję połączenia.", parent=self)
            return
        config = get_postgres_config()
        if not db.get("launcher_db_exists"):
            ok, msg = postgres_create_database(config, "mapa_launcher_db")
            self._append_db_log(f"[AUTO][launcher_db] {msg}")
            if ok:
                schema_ok, schema_msg = postgres_execute_schema(config, "mapa_launcher_db", LAUNCHER_DB_SCHEMA)
                self._append_db_log(f"[AUTO][launcher_schema] {schema_msg}")
                actions_done.append("utworzono bazę launcher")
                if not schema_ok:
                    warnings.append(schema_msg)
            else:
                warnings.append(msg)
        if postgres_database_exists(config, "mapa_launcher_db") and not postgres_has_postgis_extension(config, "mapa_launcher_db"):
            ok, msg = postgres_enable_postgis(config, "mapa_launcher_db")
            self._append_db_log(f"[AUTO][launcher_postgis] {msg}")
            if ok:
                actions_done.append("włączono PostGIS w bazie launcher")
            else:
                warnings.append(msg)
        location_db_name = self.parent_app.get_database_diagnostics().get("location_db_name")
        if location_db_name and not self.parent_app.get_database_diagnostics().get("location_db_exists"):
            ok, msg = init_location_database(location_db_name)
            self._append_db_log(f"[AUTO][location_db] {msg}")
            if ok:
                actions_done.append(f"utworzono baze {location_db_name}")
            else:
                warnings.append(msg)
        if location_db_name and postgres_database_exists(config, location_db_name) and not postgres_has_postgis_extension(config, location_db_name):
            ok, msg = postgres_enable_postgis(config, location_db_name)
            self._append_db_log(f"[AUTO][location_postgis] {msg}")
            if ok:
                actions_done.append(f"włączono PostGIS w bazie {location_db_name}")
            else:
                warnings.append(msg)
        if guard.get("enabled") and guard.get("last_check_at") is None:
            self._append_db_log("[AUTO][guardian] Uruchamiam pierwszą kontrolę Strażnika")
            self.run_guardian_check_now()
            actions_done.append("uruchomiono kontrolę Strażnika")
        self.refresh_all()
        if actions_done:
            self._record_action("Wykonano bezpieczne naprawy systemu")
            msg = "Wykonano bezpieczne naprawy:\n• " + "\n• ".join(actions_done)
            if warnings:
                msg += "\n\nUwagi:\n• " + "\n• ".join(warnings)
            messagebox.showinfo("Bezpieczne naprawy zakończone", msg, parent=self)
        elif warnings:
            messagebox.showwarning("Naprawa częściowa", "Nie wykonano zmian automatycznych.\n\nUwagi:\n• " + "\n• ".join(warnings), parent=self)
        else:
            messagebox.showinfo("System wygląda dobrze", "Nie było nic bezpiecznego do automatycznej naprawy.", parent=self)

    def repair_and_recheck(self):
        self._record_action("Uruchomiono sekwencję: napraw i sprawdź ponownie")
        self.repair_safe_items()
        try:
            db = self.parent_app.get_database_diagnostics()
            if db.get("mode") == "postgresql" and db.get("connection_ok"):
                self._append_db_log("[RECHECK] Ponowny test diagnostyczny PostgreSQL po naprawach")
            self.parent_app.run_proactive_health_check()
        except Exception as e:
            self._append_db_log(f"[RECHECK][WARN] Nie udało się uruchomić pełnego sprawdzenia: {e}")
        self.after(400, self.refresh_all)

    def create_launcher_database(self):
        data = self.parent_app.get_database_diagnostics()
        if data.get("mode") != "postgresql":
            messagebox.showinfo("SQLite aktywne", "Baza launcher PostgreSQL nie dotyczy trybu SQLite.", parent=self)
            return
        self._record_action("Rozpoczęto tworzenie bazy launcher")
        self._append_db_log("[START] Tworzenie / inicjalizacja bazy mapa_launcher_db")
        config = get_postgres_config()
        ok, msg = postgres_create_database(config, "mapa_launcher_db")
        self._append_db_log(f"[DB] {msg}")
        if ok:
            _, postgis_msg = postgres_enable_postgis(config, "mapa_launcher_db")
            self._append_db_log(f"[POSTGIS] {postgis_msg}")
            schema_ok, schema_msg = postgres_execute_schema(config, "mapa_launcher_db", LAUNCHER_DB_SCHEMA)
            self._append_db_log(f"[SCHEMA] {schema_msg}")
            if schema_ok:
                messagebox.showinfo("Sukces", "Baza mapa_launcher_db jest gotowa.", parent=self)
            else:
                messagebox.showerror("Błąd", schema_msg, parent=self)
        else:
            messagebox.showerror("Błąd", msg, parent=self)
        self.refresh_all()

    def enable_postgis_for_active_database(self):
        data = self.parent_app.get_database_diagnostics()
        if data.get("mode") != "postgresql":
            messagebox.showinfo("SQLite aktywne", "PostGIS nie dotyczy trybu SQLite.", parent=self)
            return
        db_name = data.get("location_db_name")
        if not db_name:
            messagebox.showerror("Brak nazwy bazy", "Nie udało się ustalić aktywnej bazy miejscowości.", parent=self)
            return
        self._record_action(f"Próba włączenia PostGIS dla bazy {db_name}")
        ok, msg = postgres_enable_postgis(get_postgres_config(), db_name)
        self._append_db_log(f"[POSTGIS:{db_name}] {msg}")
        if ok:
            messagebox.showinfo("PostGIS", f"Operacja zakończona dla bazy '{db_name}'.\n\n{msg}", parent=self)
        else:
            messagebox.showwarning("PostGIS", msg, parent=self)
        self.refresh_all()

    def open_pgadmin(self):
        path = detect_pgadmin_path()
        if not path:
            messagebox.showwarning("pgAdmin nie znaleziony", "Nie udało się wykryć lokalnej instalacji pgAdmin.\n\nMożesz zainstalować go później albo uruchomić ręcznie.", parent=self)
            return
        try:
            self._record_action("Uruchomiono pgAdmin")
            subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._append_db_log(f"[PGADMIN] Uruchomiono: {path}")
        except Exception as e:
            messagebox.showerror("Błąd uruchamiania pgAdmin", str(e), parent=self)

    def create_active_location_database(self):
        data = self.parent_app.get_database_diagnostics()
        if data.get("mode") != "postgresql":
            messagebox.showinfo("SQLite aktywne", "Tworzenie bazy PostgreSQL nie dotyczy trybu SQLite.", parent=self)
            return
        db_name = data.get("location_db_name")
        if not db_name:
            messagebox.showerror("Brak nazwy bazy", "Nie udało się ustalić nazwy bazy aktywnej miejscowości.", parent=self)
            return
        if postgres_database_exists(get_postgres_config(), db_name):
            if not messagebox.askyesno("Baza już istnieje", f"Baza '{db_name}' już istnieje. Czy ponownie wykonać inicjalizację schematu?", parent=self):
                return
        self._record_action(f"Rozpoczęto tworzenie / inicjalizację bazy {db_name}")
        self._append_db_log(f"[START] Tworzenie / inicjalizacja bazy: {db_name}")
        ok, msg = init_location_database(db_name)
        self._append_db_log(f"[WYNIK] {msg}")
        if ok:
            messagebox.showinfo("Sukces", f"Baza '{db_name}' jest gotowa.\n\n{msg}", parent=self)
        else:
            messagebox.showerror("Błąd", msg, parent=self)
        self.refresh_all()

    def repair_active_database(self):
        """Napraw aktywną bazę miejscowości: test + create (jeśli brak) + PostGIS + schemat.

        Zastępuje 3 stare buttony (``Utwórz bazę launcher``, ``Utwórz bazę miejscowości``,
        ``Włącz PostGIS``) — helper ``ensure_postgres_database_with_postgis`` robi
        całą robotę idempotentnie (bezpiecznie klikać wiele razy).
        """
        from launcher.services.database_setup_service import (
            ensure_postgres_database_with_postgis,
            save_launcher_postgres_config,
        )
        from launcher.services.postgres_adapter_service import LAUNCHER_DB_SCHEMA

        data = self.parent_app.get_database_diagnostics()
        if data.get("mode") != "postgresql":
            messagebox.showinfo("SQLite aktywne", "Naprawa bazy PG nie dotyczy trybu SQLite.", parent=self)
            return
        db_name = data.get("location_db_name")
        if not db_name:
            messagebox.showerror("Brak nazwy bazy", "Nie udało się ustalić aktywnej bazy miejscowości.", parent=self)
            return
        config = get_postgres_config()
        self._record_action(f"Naprawa bazy {db_name} (PostGIS + schemat)")
        self._append_db_log(f"[REPAIR:{db_name}] start — test + create + PostGIS + schemat")
        try:
            ok, msg = ensure_postgres_database_with_postgis(
                config.get("host", "localhost"),
                int(config.get("port", 5432)),
                config.get("user", "postgres"),
                config.get("password", ""),
                db_name,
                schema_sql=LAUNCHER_DB_SCHEMA,
            )
        except Exception as exc:
            ok, msg = False, f"Wyjątek: {exc}"
        self._append_db_log(f"[REPAIR:{db_name}] {'OK' if ok else 'FAIL'} — {msg}")
        if ok:
            messagebox.showinfo("Baza naprawiona", f"'{db_name}' jest gotowa.\n\n{msg}", parent=self)
        else:
            messagebox.showerror("Błąd naprawy", msg, parent=self)
        self.refresh_all()

    # === Konfiguracja połączenia PostgreSQL (host/port/user/hasło/baza) ===
    def _build_pg_config_card(self, parent) -> ttk.Frame:
        """Karta z polami edycji parametrów połączenia PG.

        Pozwala zmienić host/port/user/hasło/bazę bez otwierania kreatora
        ani edytora .env — zapis trafia jednocześnie do ``backend/.env``
        (DB_*) i ``backend/.postgres.env`` (LAUNCHER_DB_*), oraz odświeża
        ``os.environ`` żeby ``check_postgres_available()`` widział nowe hasło.
        """
        from tkinter import StringVar

        card = create_card(parent, "Konfiguracja PostgreSQL")
        body = ttk.Frame(card, style="Card.TFrame")
        body.pack(fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_SM))

        # Odczytaj aktualne wartości — z .env (DB_*) i .postgres.env (LAUNCHER_DB_*)
        launcher_cfg = get_postgres_config()
        current = {
            "host": _read_backend_env_value("DB_HOST") or launcher_cfg.get("host", "localhost"),
            "port": _read_backend_env_value("DB_PORT") or str(launcher_cfg.get("port", 5432)),
            "user": _read_backend_env_value("DB_USER") or launcher_cfg.get("user", "postgres"),
            "password": _read_backend_env_value("DB_PASSWORD") or launcher_cfg.get("password", ""),
            "db_name": _read_backend_env_value("DB_NAME") or "mapa_czarna_db",
        }

        # Pola edycji w grid 2-kolumnowym
        fields = {}
        labels = [
            ("host", "Host:"),
            ("port", "Port:"),
            ("user", "Użytkownik:"),
            ("password", "Hasło:"),
            ("db_name", "Baza danych:"),
        ]
        for i, (key, label_text) in enumerate(labels):
            ttk.Label(body, text=label_text).grid(
                row=i, column=0, sticky="w", pady=4, padx=(0, SPACING_SM)
            )
            var = StringVar(value=current[key])
            # W ttk.Entry: show="*" maskuj, show="" pokaż jawnie.
            # Domyślnie hasło MUSI być maskowane, inaczej ktoś zerka na ekran
            # i widzi hasło w czytelnej postaci.
            show = "*" if key == "password" else ""
            entry = ttk.Entry(body, textvariable=var, width=38, show=show)
            entry.grid(row=i, column=1, sticky="ew", pady=4, padx=(0, SPACING_SM))
            fields[key] = var

        body.columnconfigure(1, weight=1)
        self._pg_config_fields = fields

        # Checkbox "pokaż hasło"
        show_pw_var = tk.BooleanVar(value=False)
        def _toggle_pw():
            # Rekreuj Entry z show=""
            pw_entry = body.grid_slaves(row=3, column=1)
            if not pw_entry:
                return
            current_val = fields["password"].get()
            pw_entry[0].destroy()
            new_entry = ttk.Entry(
                body, textvariable=fields["password"], width=38,
                show="" if show_pw_var.get() else "*",
            )
            new_entry.grid(row=3, column=1, sticky="ew", pady=4, padx=(0, SPACING_SM))

        ttk.Checkbutton(
            body, text="Pokaż hasło", variable=show_pw_var, command=_toggle_pw
        ).grid(row=4, column=1, sticky="e", padx=(0, SPACING_SM), pady=(0, 4))

        # Przyciski
        btns = ttk.Frame(card, style="Card.TFrame")
        btns.pack(fill=tk.X, padx=SPACING_MD, pady=(0, SPACING_MD))
        ttk.Button(btns, text="💾 Zapisz konfigurację", style="Primary.TButton",
                   command=self._save_pg_config).pack(side=tk.LEFT, padx=(0, SPACING_XS))
        ttk.Button(btns, text="🔌 Test połączenia", style="Info.TButton",
                   command=self.run_postgres_connection_test).pack(side=tk.LEFT, padx=SPACING_XS)
        ttk.Button(btns, text="🔄 Przywróć z .env", style="Secondary.TButton",
                   command=self._reload_pg_config).pack(side=tk.LEFT, padx=SPACING_XS)
        ttk.Button(btns, text="🔑 Zmień hasło PG", style="Warning.TButton",
                   command=self._change_pg_password_dialog).pack(side=tk.LEFT, padx=SPACING_XS)

        return card

    def _reload_pg_config(self):
        """Ponownie wczytuje wartości z .env / .postgres.env do pól edycji."""
        if not hasattr(self, "_pg_config_fields"):
            return
        launcher_cfg = get_postgres_config()
        self._pg_config_fields["host"].set(
            _read_backend_env_value("DB_HOST") or launcher_cfg.get("host", "localhost")
        )
        self._pg_config_fields["port"].set(
            _read_backend_env_value("DB_PORT") or str(launcher_cfg.get("port", 5432))
        )
        self._pg_config_fields["user"].set(
            _read_backend_env_value("DB_USER") or launcher_cfg.get("user", "postgres")
        )
        self._pg_config_fields["password"].set(
            _read_backend_env_value("DB_PASSWORD") or launcher_cfg.get("password", "")
        )
        self._pg_config_fields["db_name"].set(
            _read_backend_env_value("DB_NAME") or "mapa_czarna_db"
        )
        self._append_db_log("[CFG] Pola konfiguracji PG przeładowane z plików env")

    def _save_pg_config(self):
        """Zapisuje wartości z pól do backend/.env i backend/.postgres.env."""
        if not hasattr(self, "_pg_config_fields"):
            return
        host = self._pg_config_fields["host"].get().strip() or "localhost"
        port_str = self._pg_config_fields["port"].get().strip() or "5432"
        user = self._pg_config_fields["user"].get().strip() or "postgres"
        password = self._pg_config_fields["password"].get()  # NIE strip() - hasło może mieć spacje wiodące
        db_name = self._pg_config_fields["db_name"].get().strip() or "mapa_czarna_db"

        # Walidacja portu
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Niepoprawny port",
                f"Port musi być liczbą 1-65535, podano: {port_str!r}",
                parent=self,
            )
            return

        ok, msg = save_pg_config_to_env_files(host, port, user, password, db_name)
        if ok:
            self._record_action(
                f"Zapisano konfigurację PG: {user}@{host}:{port}/{db_name}"
            )
            self._append_db_log(
                f"[CFG] {msg} ({user}@{host}:{port}/{db_name})"
            )
            messagebox.showinfo(
                "Zapisano",
                f"Konfiguracja PG zapisana do .env i .postgres.env.\n\n"
                f"Host: {host}\nPort: {port}\nUżytkownik: {user}\n"
                f"Baza: {db_name}\n\n"
                "Tip: Restart backendu (Ctrl+R w przeglądarce) zastosuje nowe ustawienia.",
                parent=self,
            )
        else:
            self._append_db_log(f"[CFG][ERROR] {msg}")
            messagebox.showerror("Błąd zapisu", msg, parent=self)
        self.refresh_all()

    def _change_pg_password_dialog(self):
        """Otwiera dialog zmiany hasła PG. Wydzielone do
        :func:`build_change_pg_password_dialog` (testowalne bez klasy).
        """
        launcher_cfg = get_postgres_config()
        cur_user = launcher_cfg.get("user", "postgres")
        cur_host = launcher_cfg.get("host", "localhost")
        cur_port = launcher_cfg.get("port", 5432)
        cur_db_name = (
            self._pg_config_fields["db_name"].get().strip()
            if hasattr(self, "_pg_config_fields")
            else "mapa_czarna_db"
        ) or "mapa_czarna_db"

        def _on_success(new_password: str, log_message: str) -> None:
            self._record_action(log_message)
            self._append_db_log(f"[PG-PW] {log_message}")
            if hasattr(self, "_pg_config_fields"):
                self._pg_config_fields["password"].set(new_password)
            self.refresh_all()

        def _on_error(level: str, message: str) -> None:
            self._append_db_log(f"[PG-PW][{level}] {message}")

        build_change_pg_password_dialog(
            parent=self,
            current_user=cur_user,
            current_host=cur_host,
            current_port=cur_port,
            current_db_name=cur_db_name,
            on_success=_on_success,
            on_error=_on_error,
        )


def build_change_pg_password_dialog(
    parent,
    *,
    current_user: str,
    current_host: str,
    current_port: int,
    current_db_name: str,
    on_success=None,
    on_error=None,
) -> tk.Toplevel:
    """Tworzy dialog zmiany hasła użytkownika PostgreSQL (testowalne bez klasy).

    Args:
        parent: Widget rodzica (okno ustawień lub testowe root).
        current_user / current_host / current_port: aktualne parametry PG.
        current_db_name: nazwa bazy miejscowości (do aktualizacji .env).
        on_success: opcjonalny ``callable(new_password: str, log_message: str)``
            wywoływany po pomyślnej zmianie hasła i zapisie plików env.
        on_error: opcjonalny ``callable(level: str, message: str)``
            do logowania błędów (level = "ERROR" / "WARN").

    Returns:
        Utworzone :class:`tk.Toplevel` — caller może je trzymać jeśli potrzebuje
        (np. testy widoczności), ale dialog jest samozamykający po sukcesie.

    Layout (wysokość ~420 px):
        - nagłówek (2 linie tekstu)
        - 3 pola: Aktualne hasło / Nowe hasło / Powtórz nowe
        - status (1 linia, wraplength=440)
        - 2 przyciski: Anuluj | 🔑 Zmień hasło

    Resizable w poziomie (DPI), zablokowany w pionie.
    """
    from tkinter import StringVar

    def _log_error(level: str, message: str) -> None:
        if on_error:
            try:
                on_error(level, message)
            except Exception:
                pass

    def _notify_success(new_password: str, log_message: str) -> None:
        if on_success:
            try:
                on_success(new_password, log_message)
            except Exception:
                pass

    dlg = tk.Toplevel(parent)
    dlg.title("🔑 Zmień hasło PostgreSQL")
    dlg.transient(parent)
    dlg.grab_set()
    dlg.resizable(True, False)
    dlg.configure(bg=SURFACE_BG)
    set_dialog_icon(dlg)

    # WAŻNE: pack_propagate(False) zapobiega dopasowywaniu okna do zawartości.
    # Bez tego, gdy wewnętrzny layout (np. form z expand=True) "chce" być
    # większy niż geometry(), WM na Windows obcina dolne widgety (btns).
    dlg.pack_propagate(False)

    # Centrowanie nad parent — fallback do (0, 0) jeśli parent nie ma wymiarów
    dlg.update_idletasks()
    w, h = 540, 480  # Zwiększona wysokość: uwzględnia Windows titlebar (~30px) i WM border
    try:
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw // 2) - (w // 2)
        y = py + (ph // 2) - (h // 2)
    except Exception:
        x, y = 100, 100
    dlg.geometry(f"{w}x{h}+{x}+{y}")
    dlg.minsize(480, 440)

    # === Nagłówek ===
    header = ttk.Frame(dlg, padding=(20, 16, 20, 8))
    header.pack(fill=tk.X)
    ttk.Label(
        header, text="🔑 Zmień hasło użytkownika PostgreSQL",
        font=("Segoe UI", 12, "bold"),
    ).pack(anchor=tk.W)
    ttk.Label(
        header,
        text=(
            f"Użytkownik: {current_user}    "
            f"Host: {current_host}:{current_port}\n\n"
            "Wpisz aktualne hasło i nowe hasło dwukrotnie. "
            "Po zmianie pliki .env i .postgres.env zostaną "
            "zaktualizowane automatycznie."
        ),
        foreground=TEXT_SECONDARY, justify=tk.LEFT, wraplength=440,
    ).pack(anchor=tk.W, pady=(8, 0))

    # === Formularz ===
    # fill=X (nie BOTH/expand) — form ma sztywny układ 3 wierszy, nie powinien
    # pochłaniać nadmiar, bo wypycha btns poza okno (Windows titlebar overhead)
    form = ttk.Frame(dlg, padding=(20, 8, 20, 8))
    form.pack(fill=tk.X)
    form.columnconfigure(1, weight=1)

    old_pw_var = StringVar()
    new_pw_var = StringVar()
    confirm_pw_var = StringVar()

    def _add_field(row: int, label: str, var: StringVar) -> ttk.Entry:
        ttk.Label(form, text=label).grid(
            row=row, column=0, sticky="w", pady=6, padx=(0, 10),
        )
        entry = ttk.Entry(form, textvariable=var, show="*", width=32)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        return entry

    old_entry = _add_field(0, "Aktualne hasło:", old_pw_var)
    new_entry = _add_field(1, "Nowe hasło:", new_pw_var)
    conf_entry = _add_field(2, "Powtórz nowe:", confirm_pw_var)

    # === Status ===
    status_var = tk.StringVar(value="")
    ttk.Label(
        dlg, textvariable=status_var, foreground=TEXT_SECONDARY,
        padding=(20, 4, 20, 4), wraplength=440, justify=tk.LEFT,
    ).pack(fill=tk.X)

    # === Przyciski ===
    btns = ttk.Frame(dlg, padding=(20, 8, 20, 16))
    btns.pack(fill=tk.X)

    def _do_change() -> None:
        old_pw = old_pw_var.get()
        new_pw = new_pw_var.get()
        conf_pw = confirm_pw_var.get()

        # Walidacja GUI
        if not old_pw:
            status_var.set("⚠️ Wpisz aktualne hasło")
            old_entry.focus_set()
            return
        if not new_pw:
            status_var.set("⚠️ Wpisz nowe hasło")
            new_entry.focus_set()
            return
        if new_pw != conf_pw:
            status_var.set("⚠️ Nowe hasła nie są identyczne")
            conf_entry.focus_set()
            return
        if len(new_pw) < 4:
            status_var.set("⚠️ Nowe hasło musi mieć min. 4 znaki")
            new_entry.focus_set()
            return

        # Potwierdzenie
        if not messagebox.askyesno(
            "Potwierdź zmianę hasła",
            f"Czy na pewno zmienić hasło użytkownika '{current_user}' "
            f"na serwerze {current_host}:{current_port}?\n\n"
            f"Nowe hasło: {'*' * len(new_pw)} ({len(new_pw)} znaków)\n\n"
            "Tej operacji nie da się cofnąć inaczej niż przez ręczne "
            "ALTER USER w psql.",
            parent=dlg,
        ):
            status_var.set("Anulowano")
            return

        # ALTER USER
        status_var.set("⏳ Łączenie z serwerem…")
        dlg.update_idletasks()
        ok, msg = postgres_change_pg_password(
            host=current_host, port=current_port, user=current_user,
            old_password=old_pw, new_password=new_pw,
        )
        if not ok:
            if "old_password_invalid" in msg:
                friendly = "❌ Aktualne hasło jest nieprawidłowe"
            elif "permission_denied" in msg:
                friendly = "❌ Brak uprawnień do zmiany hasła (wymagany superuser)"
            elif "connection_failed" in msg:
                friendly = f"❌ Nie można połączyć się z serwerem: {msg.split(':', 1)[-1].strip()}"
            else:
                friendly = f"❌ {msg}"
            status_var.set(friendly)
            _log_error("ERROR", msg)
            return

        # Sukces ALTER USER — aktualizuj pliki env
        status_var.set("⏳ Aktualizacja plików konfiguracyjnych…")
        dlg.update_idletasks()
        ok2, msg2 = save_pg_config_to_env_files(
            host=current_host, port=current_port, user=current_user,
            password=new_pw, db_name=current_db_name,
        )
        if not ok2:
            status_var.set(
                f"⚠️ Hasło zmienione na serwerze, ale .env nie zaktualizowany: {msg2}\n"
                "Zmień hasło ręcznie w polach powyżej i kliknij 'Zapisz konfigurację'."
            )
            _log_error("WARN", f"ALTER OK ale save_pg_config: {msg2}")
            return

        # Sukces
        log_message = (
            f"Zmieniono hasło PG dla {current_user}@{current_host}:{current_port} | "
            f"{msg} | {msg2}"
        )
        status_var.set("✅ Hasło zmienione i zapisane w .env / .postgres.env")
        _notify_success(new_pw, log_message)
        messagebox.showinfo(
            "Sukces",
            f"Hasło użytkownika '{current_user}' zostało zmienione.\n\n"
            f"Pliki .env i .postgres.env zaktualizowane.\n\n"
            "Tip: zrestartuj backend (Ctrl+R w przeglądarce) "
            "aby FastAPI używał nowego hasła.",
            parent=dlg,
        )
        dlg.after(800, dlg.destroy)

    ttk.Button(btns, text="Anuluj", style="Secondary.TButton",
               command=dlg.destroy).pack(side=tk.RIGHT, padx=(8, 0))
    ttk.Button(btns, text="🔑 Zmień hasło", style="Warning.TButton",
               command=_do_change).pack(side=tk.RIGHT)
    conf_entry.bind("<Return>", lambda e: _do_change())
    old_entry.focus_set()

    return dlg


# === Tooltip helper ===

class _Tooltip:
    """Lekki tooltip na hover (tk.Toplevel + bind <Enter>/<Leave>).

    Użycie::

        tt = _Tooltip(button, "Tworzy bazę danych")
        tt.set_text("Inna treść")  # dynamiczna zmiana

    Tooltip pojawia się pod kursorem, znika po opuszczeniu widgetu.
    """

    def __init__(self, widget, text: str = "") -> None:
        self.widget = widget
        self.text = text
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def set_text(self, text: str) -> None:
        """Zmień tekst (np. po aktualizacji stanu przycisku)."""
        self.text = text

    def _show(self, event=None) -> None:
        if self.tip or not self.text:
            return
        # Pozycja: pod widgetem, lekko w prawo
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # bez ramki okna
        tw.wm_geometry(f"+{x}+{y}")
        ttk.Label(
            tw, text=self.text, background="#ffffe0", foreground="#222",
            relief="solid", borderwidth=1, padding=(6, 3),
            wraplength=320, justify=tk.LEFT,
        ).pack()

    def _hide(self, event=None) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None
