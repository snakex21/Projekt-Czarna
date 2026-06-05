"""Budowa głównego dashboardu launchera."""

import tkinter as tk
from tkinter import ttk

from ..config.settings import COLORS, SCRIPTS


def build_main_dashboard(app):
    """Buduje główne sekcje interfejsu launchera."""
    ui_scale = float(getattr(app, "ui_scale", 1.0) or 1.0)
    compact = ui_scale >= 1.5
    pad = 6 if compact else 10
    section_pady = 3 if compact else 5

    main_frame = ttk.Frame(app, padding=str(pad))
    main_frame.pack(fill=tk.BOTH, expand=True)

    header_frame = ttk.Frame(main_frame)
    header_frame.pack(fill=tk.X, pady=(0, 6 if compact else 10))

    ttk.Label(
        header_frame,
        text="🗺️ System Zarządzania Mapą Katastralną",
        style="Heading.TLabel",
        font=("Segoe UI", app.base_font_size + (2 if compact else 4), "bold"),
    ).pack(side=tk.LEFT)
    ttk.Label(header_frame, text="Status: Gotowy", foreground=COLORS['success']).pack(side=tk.RIGHT, padx=10)

    location_frame = ttk.LabelFrame(main_frame, text="📍 Miejscowość", padding=str(pad))
    location_frame.pack(fill=tk.X, pady=section_pady)
    location_controls = ttk.Frame(location_frame)
    location_controls.pack(fill=tk.X)
    location_controls.columnconfigure(1, weight=1)
    ttk.Label(location_controls, text="Aktywna miejscowość:", font=("Segoe UI", app.base_font_size)).grid(row=0, column=0, sticky="w", padx=5, pady=(0, 6))

    app.location_var = tk.StringVar()
    app.location_combo = ttk.Combobox(location_controls, textvariable=app.location_var, state="readonly", width=30)
    app.location_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=(0, 6))
    app.location_combo.bind("<<ComboboxSelected>>", app.on_location_selected)

    location_buttons = ttk.Frame(location_controls)
    location_buttons.grid(row=1, column=0, columnspan=2, sticky="ew")
    for idx in range(3):
        location_buttons.columnconfigure(idx, weight=1)
    ttk.Button(location_buttons, text="🔄  Odśwież", command=app.refresh_locations, style="Info.TButton").grid(row=0, column=0, sticky="ew", padx=5)
    ttk.Button(location_buttons, text="⚙️ Zarządzaj Miejscowościami", command=app.open_location_manager, style="Primary.TButton").grid(row=0, column=1, sticky="ew", padx=5)
    ttk.Button(location_buttons, text="⚙️ Ustawienia programu", command=app.open_program_settings, style="Info.TButton").grid(row=0, column=2, sticky="ew", padx=5)

    quick_start_frame = ttk.LabelFrame(main_frame, text="🚀 Szybki start", padding=str(pad))
    quick_start_frame.pack(fill=tk.X, pady=section_pady)
    if not compact:
        ttk.Label(
            quick_start_frame,
            text="Codzienne akcje: uruchom serwer, udostępnij w sieci albo zrób kopię. Konfiguracja jest w Ustawieniach programu.",
            foreground=COLORS['secondary'],
        ).pack(anchor=tk.W, pady=(0, 8))

    row1 = ttk.Frame(quick_start_frame)
    row1.pack(fill=tk.X, pady=(0, 3 if compact else 5))
    app.server_btn = ttk.Button(row1, text="🚀 Uruchom Serwer Backend", command=app.toggle_server, style="Success.TButton")
    app.server_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    app.network_server_btn = ttk.Button(row1, text="🌐 Uruchom Serwer Sieciowy", command=app.toggle_network_server, style="Info.TButton")
    app.network_server_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    ttk.Button(row1, text="💾 Menedżer Kopii", command=app.open_backup_manager, style="Primary.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    row2 = ttk.Frame(quick_start_frame)
    row2.pack(fill=tk.X)
    ttk.Button(
        row2,
        text="🔄 Migruj Dane do Bazy",
        command=lambda: app.run_script_in_thread(SCRIPTS["migration"], "Skrypt Migracyjny"),
        style="Info.TButton",
    ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    tools_frame = ttk.LabelFrame(main_frame, text="🛠️ Narzędzia edycyjne", padding=str(pad))
    tools_frame.pack(fill=tk.X, pady=section_pady)
    editors_container = ttk.Frame(tools_frame)
    editors_container.pack(fill=tk.X)

    app.guardian_enabled = tk.BooleanVar(value=app.load_guardian_config())
    app.guardian_status_text = tk.StringVar(value="⏳ Inicjalizacja...")

    ttk.Button(editors_container, text="📍 Kalibracja Mapy", command=app.open_map_calibrator, style="Primary.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    for text, key in [("👥 Edytor Właścicieli", "owner_editor"), ("🗺️ Edytor Działek", "parcel_editor"), ("🌳 Edytor Genealogii", "genealogy_editor")]:
        ttk.Button(editors_container, text=text, command=lambda k=key, n=text: app.start_managed_process(k, n), style="Primary.TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    app.guardian_status_label = ttk.Label(tools_frame, textvariable=app.guardian_status_text, font=("Segoe UI", 9, "bold"), foreground=COLORS['info'])
    app.guardian_status_label.pack(anchor=tk.W, padx=5, pady=(6, 0))

    links_frame = ttk.LabelFrame(main_frame, text="🌐 Szybki Dostęp (wymaga uruchomionego serwera)", padding=str(pad))
    links_frame.pack(fill=tk.X, pady=section_pady)
    links_container = ttk.Frame(links_frame)
    links_container.pack(fill=tk.X)
    app.quick_link_buttons = []
    for text, url_key, style in [("🏠 Strona Główna", "strona_glowna", "Success"), ("🗺️ Mapa Interaktywna", "mapa", "Info"), ("⚙️ Panel Administracyjny", "admin", "Warning")]:
        btn = ttk.Button(links_container, text=text, style=f"{style}.TButton")
        btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        app.quick_link_buttons.append((btn, url_key))
    app._env_mtime = None

    app.processes_frame = ttk.LabelFrame(main_frame, text="📊 Uruchomione Procesy", padding=str(pad))
    app.processes_frame.pack(fill=tk.X, pady=section_pady)
    app.update_processes_ui()

    console_container = ttk.LabelFrame(main_frame, text="💻 Konsole Wyjściowe", padding=str(pad))
    console_container.pack(fill=tk.BOTH, expand=True, pady=section_pady)
    if compact:
        console_container.configure(height=260)
        console_container.pack_propagate(False)
    app.notebook = ttk.Notebook(console_container)
    app.notebook.pack(fill=tk.BOTH, expand=True)
    app.main_console_frame = ttk.Frame(app.notebook)
    app.main_console = app.create_console_widget(app.main_console_frame)
    app.notebook.add(app.main_console_frame, text="🏠 Launcher")

    app.log("=" * 60 + "\n")
    app.log("🗺️ System Zarządzania Mapą Katastralną - Uruchomiony\n")
    app.log("=" * 60 + "\n")
    app.log("ℹ️ Witaj w centrum zarządzania projektem!\n")
    app.log("ℹ️ Użyj przycisków powyżej, aby uruchomić komponenty.\n\n")
