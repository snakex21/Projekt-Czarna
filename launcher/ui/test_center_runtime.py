"""GUI Test Center - okno, logi, akcje orkiestrujące testy.

Czysta logika (parsowanie, formattery, mapa ścieżek, budowanie komend)
znajduje się w ``launcher.services.test_service``. Ten moduł odpowiada
za:

  * budowę okna Centrum Testów,
  * pisanie do konsoli z zachowaniem bezpieczeństwa wątków,
  * uruchamianie subprocessów pytest w daemon thread,
  * akcje pomocnicze (kopiuj logi, zapisz do pliku, fallbacki dla
    starych przyciskow).
"""

from __future__ import annotations

import os
import platform
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from launcher.config.paths import BACKEND_DIR, BASE_DIR
from launcher.services import test_service
from launcher.utils import scale_font, scale_window, set_dialog_icon


# ─── Tagi kolorów dla konsoli testów ─────────────────────────────────────────
# Kolory dostosowane do ciemnego motywu konsoli (#1e1e1e tło)
CONSOLE_TAGS = {
    "passed":  "#4ec9b0",  # zielony (teal)
    "failed":  "#f44747",  # czerwony
    "skipped": "#cca700",  # zolty
    "error":   "#ff6b6b",  # jasny czerwony
    "header":  "#569cd6",  # niebieski (naglowki sekcji)
    "summary": "#c586c0",  # fioletowy (podsumowanie)
    "time":    "#808080",  # szary (czas)
    "emoji":   "#e0e0e0",  # jasny (emoji)
}


def setup_console_tags(console):
    """Konfiguruje tagi kolorów w widgetcie konsoli."""
    for tag, color in CONSOLE_TAGS.items():
        console.tag_configure(tag, foreground=color)
    # Specjalne tagi ze stylem
    console.tag_configure("bold_header", foreground="#569cd6", font=("Consolas", 11, "bold"))
    console.tag_configure("bold_summary", foreground="#c586c0", font=("Consolas", 11, "bold"))
    console.tag_configure("test_passed_line", foreground="#4ec9b0")
    console.tag_configure("test_failed_line", foreground="#f44747")
    console.tag_configure("test_skipped_line", foreground="#cca700")


def _initialize_test_vars(app):
    """Inicjalizuje ``app.test_vars`` z domyślnymi wartościami (idempotentnie)."""
    if not hasattr(app, "test_vars"):
        app.test_vars = {}

    # Idempotentnie dopisz nowe klucze po aktualizacjach launchera.
    # Bez tego istniejąca instancja app.test_vars ze starej wersji nie dostanie
    # np. nowego "integration" i checkbox nie pojawi się / nie będzie uruchamiany.
    for key, value in test_service.DEFAULT_TEST_VARS.items():
        if key not in app.test_vars:
            app.test_vars[key] = tk.BooleanVar(value=value)


def open_test_center_window(app, get_active_location_name):
    """Otwiera dedykowane okno Centrum Testów."""
    test_window = tk.Toplevel(app)
    test_window.title("🛡️ Centrum Testów i Weryfikacji")
    scale_window(test_window, app, 900, 750)
    set_dialog_icon(test_window)
    test_window.transient(app)

    main_frame = ttk.Frame(test_window, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="🛡️ Centrum Zarządzania Jakością Danych", font=scale_font(test_window, 16, "bold")).pack(pady=(0, 20))

    options_frame = ttk.LabelFrame(main_frame, text="⚙️ Wybierz zakres weryfikacji", padding="15")
    options_frame.pack(fill=tk.X, pady=(0, 15))

    guardian_cfg_frame = ttk.Frame(main_frame)
    guardian_cfg_frame.pack(fill=tk.X, pady=(0, 10))
    ttk.Checkbutton(
        guardian_cfg_frame,
        text="🛡️ Uruchamiaj Strażnika w tle (automatyczna kontrola danych)",
        variable=app.guardian_enabled,
        command=app.save_guardian_config,
    ).pack(side=tk.LEFT)

    _initialize_test_vars(app)

    cb_grid = ttk.Frame(options_frame)
    cb_grid.pack(fill=tk.X)
    tests_info = [
        ("unit", "🧪 Jednostkowe"), ("integration", "🔗 Integracja/Admin"), ("e2e", "🤖 Robot (E2E)"), ("logic", "🌳 Rodowód"),
        ("sql", "🔍 Spójność SQL"), ("duplicates", "👥 Anty-Duplikat"), ("spatial", "📐 Geodezja"),
        ("resources", "🖼️ Zasoby"), ("gaps", "📅 Chronologia"), ("backups", "🏰 Twierdza"),
        ("encoding", "🔤 Krzaki"), ("wcag", "♿ Dostępność"), ("perf", "⚡ Wydajność"),
        ("security", "🔒 Bezpieczeństwo"),
    ]
    for i, (key, label) in enumerate(tests_info):
        row = i // 5
        col = i % 5
        ttk.Checkbutton(cb_grid, text=label, variable=app.test_vars[key]).grid(row=row, column=col, padx=10, pady=5, sticky="w")

    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, pady=(0, 10))
    ttk.Button(btn_frame, text="▶️ URUCHOM WYBRANE TESTY", command=lambda: run_selected_tests(app, get_active_location_name), style="Success.TButton").pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

    ttk.Label(main_frame, text="📋 Konsola wyjściowa:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 2))
    app.test_console = app.create_console_widget(main_frame)

    bottom_frame = ttk.Frame(main_frame)
    bottom_frame.pack(fill=tk.X, pady=(15, 0))
    ttk.Button(bottom_frame, text="📋 Kopiuj do schowka", command=lambda: copy_test_logs_to_clipboard(app)).pack(side=tk.LEFT, padx=5)
    ttk.Button(bottom_frame, text="💾 Zapisz jako plik .log", command=lambda: save_test_logs_to_file(app)).pack(side=tk.LEFT, padx=5)
    ttk.Button(bottom_frame, text="🚪 Zamknij", command=test_window.destroy).pack(side=tk.RIGHT, padx=5)


def copy_test_logs_to_clipboard(app):
    try:
        content = app.test_console.get(1.0, tk.END)
        app.clipboard_clear()
        app.clipboard_append(content)
        messagebox.showinfo("✅ Sukces", "📋 Skopiowano logi do schowka!")
    except Exception as e:
        messagebox.showerror("❌ Błąd", f"Nie udało się skopiować: {e}")


def save_test_logs_to_file(app):
    try:
        filename = filedialog.asksaveasfilename(
            title="💾 Zapisz logi testów",
            defaultextension=".log",
            filetypes=[("Pliki logów", "*.log"), ("Pliki tekstowe", "*.txt"), ("Wszystkie pliki", "*.*")],
            initialfile=f"test_report_{int(time.time())}.log",
        )
        if filename:
            content = app.test_console.get(1.0, tk.END)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("✅ Sukces", f"💾 Zapisano raport w:\n{filename}")
    except Exception as e:
        messagebox.showerror("❌ Błąd", f"Nie udało się zapisać pliku: {e}")


def run_selected_tests(app, get_active_location_name):
    """Uruchamia sekwencję wybranych testów w daemon thread."""
    selected = [k for k, v in app.test_vars.items() if v.get()]
    if not selected:
        messagebox.showwarning("⚠️ Brak wyboru", "Zaznacz przynajmniej jeden zestaw testów do uruchomienia.")
        return

    def target():
        # ── Inicjalizacja konsoli ────────────────────────────────────────
        app.after(0, lambda: app.test_console.configure(state="normal"))
        app.after(0, lambda: app.test_console.delete(1.0, tk.END))
        app.after(0, lambda: setup_console_tags(app.test_console))
        app.after(0, lambda: app.test_console.configure(state="disabled"))

        # ── Naglowek ─────────────────────────────────────────────────────
        log_to_test_console(app, "🚀 ROZPOCZYNAM PROCEDURĘ WERYFIKACJI SYSTEMU...\n", tag="bold_header")
        log_to_test_console(app, f"📅 Czas: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n", tag="time")

        env = app._prepare_process_env()
        try:
            active_loc_name = get_active_location_name()
            if active_loc_name:
                env["TEST_LOCATION"] = active_loc_name
                log_to_test_console(app, f"📍 Aktywna lokacja testowa: {active_loc_name}\n\n")
        except Exception:
            pass

        # ── Zliczanie wynikow globalnych ─────────────────────────────────
        global_stats = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "tests_run": 0}

        for test_key in selected:
            log_to_test_console(app, f"\n⏳ TRWA: {test_key.upper()}...\n", tag="bold_header")
            log_to_test_console(app, "─" * 50 + "\n", tag="time")

            cmd = test_service.build_test_command(test_key, BASE_DIR)
            if not cmd:
                # Brak komendy → katalog nie istnieje lub nieznany klucz
                if test_key not in test_service.TEST_PATH_MAP and test_key != "sql":
                    log_to_test_console(app, f"⚠️ Nieznany zestaw testów: {test_key}, pomijam.\n", tag="skipped")
                else:
                    test_rel_path = test_service.TEST_PATH_MAP.get(test_key, str(test_key))
                    log_to_test_console(app, f"⚠️ Katalog {test_rel_path} nie istnieje, pomijam.\n", tag="skipped")
                continue

            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "nt" else 0
            section_stats = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creation_flags,
                    env=env,
                )
                for line in iter(proc.stdout.readline, ""):
                    emoji, tag, formatted = test_service.parse_pytest_line(line)
                    if formatted is not None:
                        test_service.accumulate_section_stats(section_stats, emoji)
                        log_to_test_console(app, formatted, tag=tag)
                proc.stdout.close()
                rc = proc.wait()

                # ── Status sekcji ────────────────────────────────────────
                if rc == 0:
                    status = "✅ SUKCES"
                    status_tag = "test_passed_line"
                elif section_stats["failed"] > 0 or section_stats["errors"] > 0:
                    status = "❌ BŁĄD"
                    status_tag = "test_failed_line"
                else:
                    status = "⚠️ OSTRZEŻENIA"
                    status_tag = "skipped"

                section_summary = test_service.format_section_summary(section_stats)
                log_to_test_console(app, f"\n🏁 {test_key.upper()}: {status}{section_summary}\n", tag=status_tag)
                log_to_test_console(app, "─" * 50 + "\n", tag="time")

                for k in section_stats:
                    global_stats[k] += section_stats[k]
                if sum(section_stats.values()) > 0:
                    global_stats["tests_run"] += sum(section_stats.values())

            except Exception as e:
                log_to_test_console(app, f"\n💥 Wyjątek podczas testu {test_key}: {e}\n", tag="test_failed_line")
                log_to_test_console(app, "─" * 50 + "\n", tag="time")

        # ── Podsumowanie globalne ─────────────────────────────────────────
        log_to_test_console(app, "\n", tag=None)
        log_to_test_console(app, "═" * 50 + "\n", tag="bold_header")
        log_to_test_console(app, "🏁 PROCEDURA WERYFIKACJI ZAKOŃCZONA\n", tag="bold_header")

        if global_stats["tests_run"] > 0:
            log_to_test_console(app, "\n", tag=None)
            total = global_stats["tests_run"]
            log_to_test_console(app, "  📊  PODSUMOWANIE GLOBALNE:\n", tag="bold_summary")
            log_to_test_console(app, "  ────────────────────────────────\n", tag="time")
            log_to_test_console(app, f"  🧪 Testów uruchomionych: {total}\n", tag="bold_summary")
            if global_stats["passed"] > 0:
                pct = (global_stats["passed"] / total) * 100
                log_to_test_console(app,  f"  ✅ Przeszło:             {global_stats['passed']}  ({pct:.0f}%)\n", tag="test_passed_line")
            if global_stats["failed"] > 0:
                pct = (global_stats["failed"] / total) * 100
                log_to_test_console(app, f"  ❌ Nie przeszło:          {global_stats['failed']}  ({pct:.0f}%)\n", tag="test_failed_line")
            if global_stats["skipped"] > 0:
                pct = (global_stats["skipped"] / total) * 100
                log_to_test_console(app, f"  ⏭️  Pominięte:            {global_stats['skipped']}  ({pct:.0f}%)\n", tag="test_skipped_line")
            if global_stats["errors"] > 0:
                pct = (global_stats["errors"] / total) * 100
                log_to_test_console(app, f"  🔴 Błędy krytyczne:      {global_stats['errors']}  ({pct:.0f}%)\n", tag="test_failed_line")

            log_to_test_console(app, "\n", tag=None)
            if global_stats["failed"] == 0 and global_stats["errors"] == 0:
                log_to_test_console(app, "  🎉 WSZYSTKO W PORZĄDKU! System przeszedł weryfikację.\n", tag="test_passed_line")
            elif global_stats["failed"] <= 2 and global_stats["errors"] == 0:
                log_to_test_console(app, "  🟡 DROBNE PROBLEMY — warto sprawdzić raport.\n", tag="skipped")
            else:
                log_to_test_console(app, "  🔴 UWAGA — wykryto poważne problemy wymagające naprawy!\n", tag="test_failed_line")

        log_to_test_console(app, "═" * 50 + "\n", tag="bold_header")
        app.after(0, app.run_proactive_health_check)

    threading.Thread(target=target, daemon=True).start()


def log_to_test_console(app, message, tag=None):
    """Wypisuje wiadomość do konsoli testów z opcjonalnym tagiem koloru."""
    def append():
        if hasattr(app, 'test_console') and app.test_console.winfo_exists():
            app.test_console.configure(state="normal")
            if tag:
                app.test_console.insert(tk.END, message, (tag,))
            else:
                app.test_console.insert(tk.END, message)
            app.test_console.see(tk.END)
            app.test_console.configure(state="disabled")
    app.after(0, append)


def run_pytest(app):
    """Fallback dla starych przyciskow - otwiera okno z wybranymi unit testami."""
    app.open_test_center_window()
    app.test_vars["unit"].set(True)


def run_playwright_tests(app):
    """Fallback dla starych przyciskow - otwiera okno z wybranymi e2e."""
    app.open_test_center_window()
    app.test_vars["e2e"].set(True)


__all__ = [
    "BACKEND_DIR",
    "BASE_DIR",
    "CONSOLE_TAGS",
    "copy_test_logs_to_clipboard",
    "log_to_test_console",
    "open_test_center_window",
    "run_playwright_tests",
    "run_pytest",
    "run_selected_tests",
    "save_test_logs_to_file",
    "setup_console_tags",
]
