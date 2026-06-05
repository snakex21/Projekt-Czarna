"""Dialogi pierwszej konfiguracji silnika bazy danych launchera."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from launcher.config.ui_settings import get_ui_scale_setting, _read_db_engine_from_env
from launcher.config.paths import BACKEND_DIR
from launcher.db.engine import switch_engine
from launcher.services import database_setup_service
from launcher.utils import set_dialog_icon
from launcher.utils.engine_access import check_postgres_available


__all__ = ["choose_database_engine", "setup_postgres_config", "configure_postgres_connection"]


def _reset_db_engine_to_empty():
    """Zresetuj ``DB_ENGINE`` w ``backend/.env`` do pustego stringa.

    Context (2026-06-05):
        Po deinstalacji PostgreSQL, ``.env`` mógł mieć ``DB_ENGINE=postgresql``
        -- ale PG nie było w systemie. ``choose_database_engine`` czytał
        ``.env`` i zwracał cicho "postgresql", NIE pokazując dialogu.
        Launcher próbował łączyć się z nieistniejącym PG i crashował.

    Ten helper:
    1. Czyta ``backend/.env``
    2. Zamienia linię ``DB_ENGINE=postgresql`` na ``DB_ENGINE=`` (pustą)
    3. Zapisuje z powrotem

    Po resecie ``choose_database_engine`` pokaże first-run dialog
    (bo ``DB_ENGINE=`` nie jest w liście ``("sqlite", "postgresql")``).
    User musi świadomie wybrać: SQLite (natychmiast) lub PG (wymaga instalacji).
    """
    from launcher.config.paths import BACKEND_DIR as _BACKEND_DIR
    env_path = _BACKEND_DIR / ".env"
    if not env_path.exists():
        return

    lines = []
    found = False
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("DB_ENGINE="):
                lines.append("DB_ENGINE=\n")
                found = True
            else:
                lines.append(line)

    if found:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        _safe_print("⚠️ Zresetowano DB_ENGINE= w .env (PostgreSQL nie zainstalowane)")


def _safe_print(message):
    """Print text without failing on legacy Windows console encodings."""
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(str(message).encode(encoding, errors="replace").decode(encoding, errors="replace"))


def _center_window_on_screen(dialog, w, h, parent=None):
    """Wyśrodkuj okno na ekranie (lub względem parenta jeśli podany).

    Context (2026-06-05):
        User zgłosił że okno ``setup_postgres_config`` nie wyświetla się
        na środku ekranu. Pomimo że kod miał ręczne obliczanie
        ``(winfo_screenwidth // 2) - (w // 2)``, na Windows 11 z
        multi-monitor okno czasem lądowało poza widocznym obszarem.

        Ta funkcja:
        1. Preferuje wyśrodkowanie WZGLĘDEM PARENTA (jeśli parent ma
           widoczną pozycję) — okno pojawia się dokładnie nad oknem
           macierzystym (typowe zachowanie modalnych dialogów).
        2. Fallback: wyśrodkowanie na GŁÓWNYM ekranie (gdy parent=None
           lub parent nie ma jeszcze wymiarów, np. przy starcie launchera).

    Użycie:
        >>> dialog = tk.Toplevel(parent)
        >>> _center_window_on_screen(dialog, 800, 600, parent=parent)
    """
    dialog.update_idletasks()

    # Preferuj wyśrodkowanie względem parenta (jeśli ma widoczną pozycję)
    if parent is not None and parent.winfo_viewable():
        try:
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            # Sprawdź czy parent ma sensowną pozycję (nie 0,0 z zerowym rozmiarem)
            if parent_w > 0 and parent_h > 0:
                x = parent_x + (parent_w // 2) - (w // 2)
                y = parent_y + (parent_h // 2) - (h // 2)
                dialog.geometry(f"{w}x{h}+{x}+{y}")
                return
        except (tk.TclError, AttributeError):
            pass  # Parent zniszczony lub nie ma metody — fallback

    # Fallback: wyśrodkuj na głównym ekranie
    screen_w = dialog.winfo_screenwidth()
    screen_h = dialog.winfo_screenheight()
    x = (screen_w // 2) - (w // 2)
    y = (screen_h // 2) - (h // 2)
    dialog.geometry(f"{w}x{h}+{x}+{y}")


def _run_edb_installer(dialog):
    """Woła graficzną instalację EDB PostgreSQL + PostGIS system-wide.

    Reużywane przez:
    - ``choose_database_engine`` (button "Zainstaluj EDB..." w first-run)
    - ``_show_postgres_install_required`` (button "Zainstaluj EDB..." w dialogu
      "Wymagana instalacja" gdy PG nie jest zainstalowane a user próbuje
      skonfigurować połączenie)

    Context (2026-06-05):
        Wcześniej ta logika była zagnieżdżona w ``choose_database_engine``.
        Po przeniesieniu do ``_show_postgres_install_required`` wymagałaby
        duplikacji -- dlatego wyciągnęliśmy ją do helpera (DRY).

    Args:
        dialog: Okno parent dla messagebox (zapobiega zniknięciu za oknem głównym).
    """
    if not messagebox.askyesno(
        "⚠️ Wymagane uprawnienia administratora",
        "Instalacja EDB PostgreSQL + PostGIS wymaga uprawnień administratora.\n\n"
        "Skrypt zostanie uruchomiony z UAC elevation. Jeśli teraz nie masz "
        "uprawnień, system zapyta o hasło administratora.\n\n"
        "Kontynuować?",
        parent=dialog,
    ):
        return

    import subprocess
    import sys as _sys

    scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
    install_script = scripts_dir / "install_pg_gui.py"

    if not install_script.is_file():
        messagebox.showerror(
            "❌ Brak graficznego instalatora",
            f"Nie znaleziono {install_script}.\n\n"
            f"Sprawdź czy plik install_pg_gui.py istnieje w katalogu scripts/.",
            parent=dialog,
        )
        return

    # Uruchom przez pythonw.exe, żeby nie pokazywać surowego okna konsoli.
    python_executable = Path(_sys.executable)
    pythonw = python_executable.with_name("pythonw.exe")
    runner = pythonw if pythonw.exists() else python_executable

    _safe_print(f"[EDB installer GUI] Uruchamiam {install_script}")
    try:
        subprocess.Popen([str(runner), str(install_script)])
    except Exception as e:
        messagebox.showerror(
            "❌ Nie udało się uruchomić instalatora",
            f"Błąd: {e}",
            parent=dialog,
        )
        return

    # Nie pokazuj dodatkowego popupu po starcie — zasłania
    # właściwe okno instalatora. Po starcie instalatora zamykamy launcher,
    # żeby po instalacji PostgreSQL użytkownik uruchomił program już ze świeżym
    # stanem DB_ENGINE/.env.
    try:
        root = dialog
        while getattr(root, "master", None) is not None:
            root = root.master
        dialog.after(100, root.destroy)
    except Exception:
        try:
            dialog.destroy()
        except Exception:
            pass


def _show_postgres_install_required(parent=None):
    """Dialog 'Wymagana instalacja PostgreSQL' gdy PG nie jest zainstalowane.

    Wywoływany przez ``setup_postgres_config`` PRZED pokazaniem formularza
    konfiguracji połączenia (host/port/user/password). Bez tego formularz
    jest bez sensu -- nie da się połączyć z bazą której nie ma.

    Context (2026-06-05):
        User zgłosił że okno "Konfiguracja PostgreSQL - WYMAGANE" pojawia się
        po wybraniu PostgreSQL w first-run dialogu, ALE nie ma jak go
        wypełnić bo PG nie jest zainstalowane. Pytanie o host/port/user
        jest wtedy bezcelowe (test połączenia i tak się nie uda).

    Co daje ten dialog:
    1. Wyjaśnia DLACZEGO nie pokazujemy formularza (PG nie ma)
    2. Daje button "Zainstaluj EDB PostgreSQL + PostGIS" (jedyna ścieżka)
    3. Daje button "Przełącz na SQLite" (fail-safe bez powrotu do wyboru)
    """
    _safe_print("⚠️ PostgreSQL nie zainstalowane - pokazuję dialog instalacji")

    # Utwórz parent_window (analogicznie do choose_database_engine)
    temp_root = None
    if parent is None:
        temp_root = tk.Tk()
        temp_root.withdraw()
        parent_window = temp_root
    else:
        parent_window = parent

    dialog = tk.Toplevel(parent_window)
    dialog.title("⚠️ Wymagana instalacja PostgreSQL")
    scale = get_ui_scale_setting()
    w = int(640 * scale)
    h = int(420 * scale)
    dialog.geometry(f"{w}x{h}")
    dialog.minsize(w, h)
    dialog.resizable(True, True)
    dialog.transient(parent_window)
    dialog.grab_set()
    dialog.focus_force()
    dialog.attributes('-topmost', True)
    set_dialog_icon(dialog)
    _center_window_on_screen(dialog, w, h, parent=parent_window)

    main_frame = tk.Frame(dialog, bg='#f8f9fa', padx=30, pady=24)
    main_frame.pack(fill='both', expand=True)

    # Ikona ostrzeżenia
    tk.Label(
        main_frame,
        text="⚠️",
        font=('Segoe UI Emoji', 48),
        bg='#f8f9fa',
        fg='#dc3545',
    ).pack(pady=(0, 8))

    # Tytuł
    tk.Label(
        main_frame,
        text="PostgreSQL nie jest zainstalowany",
        font=('Segoe UI', 15, 'bold'),
        bg='#f8f9fa',
        fg='#212529',
    ).pack()

    # Opis problemu
    tk.Label(
        main_frame,
        text=(
            "Konfiguracja połączenia z PostgreSQL nie ma sensu, "
            "gdy serwer nie jest zainstalowany w systemie.\n\n"
            "Aby móc skonfigurować połączenie, musisz najpierw zainstalować "
            "PostgreSQL + PostGIS."
        ),
        font=('Segoe UI', 10),
        bg='#f8f9fa',
        fg='#495057',
        justify='center',
        wraplength=560,
    ).pack(pady=(10, 16), fill='x')

    # Sekcja z buttonem instalacji
    install_frame = tk.Frame(
        main_frame, bg='#FFF3CD', relief='solid', borderwidth=2, padx=20, pady=14
    )
    install_frame.pack(fill='x', pady=(0, 14))

    tk.Label(
        install_frame,
        text="📦 Instalacja EDB PostgreSQL + PostGIS",
        font=('Segoe UI', 11, 'bold'),
        bg='#FFF3CD',
        fg='#856404',
    ).pack(anchor='w')

    tk.Label(
        install_frame,
        text=(
            "Wymaga uprawnień administratora (UAC). "
            "Czas: ~5-10 min. Rozmiar: ~460 MB."
        ),
        font=('Segoe UI', 9),
        bg='#FFF3CD',
        fg='#856404',
        justify='left',
    ).pack(anchor='w', pady=(4, 8))

    tk.Button(
        install_frame,
        text="🔧  Zainstaluj EDB PostgreSQL + PostGIS",
        font=('Segoe UI', 10, 'bold'),
        bg='#0d6efd',
        fg='white',
        activeforeground='white',
        activebackground='#0b5ed7',
        relief='flat',
        cursor='hand2',
        padx=14,
        pady=8,
        command=lambda: _run_edb_installer(dialog),
    ).pack(anchor='w')

    # Dolne buttony
    buttons_frame = tk.Frame(main_frame, bg='#f8f9fa')
    buttons_frame.pack(fill='x', pady=(8, 0))

    tk.Button(
        buttons_frame,
        text="Przełącz na SQLite",
        font=('Segoe UI', 10),
        bg='#6c757d',
        fg='white',
        activeforeground='white',
        activebackground='#5c636a',
        relief='flat',
        cursor='hand2',
        padx=14,
        pady=8,
        command=lambda: (switch_engine("sqlite"), dialog.destroy()),
    ).pack(side='right')

    def on_closing():
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", on_closing)
    dialog.wait_window()

    if temp_root is not None:
        temp_root.destroy()


def choose_database_engine(parent=None):
    """Pokazuje okno pierwszej konfiguracji z wyborem SQLite lub PostgreSQL.

    Context (2026-06-05):
        Wcześniej ta funkcja zwracała cicho ``"postgresql"`` gdy ``.env`` mówił
        ``DB_ENGINE=postgresql`` -- nawet jeśli PG nie było zainstalowane.
        Powodowało to że launcher próbował łączyć się z nieistniejącym PG
        i crashował z błędem ``Connection refused``.

        Fix: nawet gdy ``.env`` mówi ``"postgresql"``, weryfikujemy
        ``check_postgres_available()``. Jeśli PG nie ma w systemie:
        1. Resetujemy ``DB_ENGINE`` w ``.env`` do pustego stringa
        2. Pokazujemy dialog first-run (user wybiera SQLite LUB instaluje PG)
    """
    current_engine = _read_db_engine_from_env()

    # Guard: .env mówi "postgresql" ale PG nie ma w systemie
    # -> zresetuj .env i pokaż dialog (user musi wybrać świadomie)
    if current_engine == "postgresql" and not check_postgres_available():
        _safe_print(
            "⚠️ .env mówi 'postgresql' ale PostgreSQL nie jest zainstalowane "
            "w systemie. Resetuję .env do pustego i pokazuję dialog."
        )
        _reset_db_engine_to_empty()
        current_engine = ""  # wymuś pokazanie dialogu

    if current_engine in ("sqlite", "postgresql"):
        return current_engine

    _safe_print("🗄️ Brak DB_ENGINE w konfiguracji — uruchamiam wybór silnika bazy danych")

    temp_root = None
    if parent is None:
        temp_root = tk.Tk()
        temp_root.withdraw()
        parent_window = temp_root
    else:
        parent_window = parent

    result = {"engine": None}

    dialog = tk.Toplevel(parent_window)
    dialog.title("🗄️ Pierwsza konfiguracja bazy danych")
    scale = get_ui_scale_setting()
    # Rozmiar okna dobrany tak, by zmieściły się BEZ scrollowania:
    # - tytuł + opis (~110px)
    # - karty SQLite/PostgreSQL side-by-side (~340px)
    # - sekcja EDB installer (ikona + opis + button) (~160px)
    # - dolne buttony Kontynuuj/Anuluj (~60px)
    # - footer z wskazówką (~30px)
    # - marginesy (40px)
    w = int(820 * scale)
    h = int(900 * scale)
    dialog.geometry(f"{w}x{h}")
    dialog.minsize(w, h)
    dialog.resizable(True, True)
    dialog.transient(parent_window)
    dialog.grab_set()
    dialog.focus_force()
    set_dialog_icon(dialog)

    _center_window_on_screen(dialog, w, h, parent=parent_window)

    selected_engine = tk.StringVar(value="sqlite")

    main_frame = tk.Frame(dialog, bg="#f8f9fa", padx=28, pady=24)
    main_frame.pack(fill="both", expand=True)

    tk.Label(
        main_frame,
        text="Wybierz silnik bazy danych",
        font=("Segoe UI", 18, "bold"),
        bg="#f8f9fa",
        fg="#212529"
    ).pack(anchor="w")

    tk.Label(
        main_frame,
        text="Możesz wybrać szybki start na SQLite albo pełną konfigurację z PostgreSQL.\n"
             "Ten wybór można później zmienić w Centrum Zarządzania.",
        font=("Segoe UI", 10),
        bg="#f8f9fa",
        fg="#495057",
        justify="left"
    ).pack(anchor="w", pady=(8, 20))

    cards = tk.Frame(main_frame, bg="#f8f9fa")
    cards.pack(fill="x", expand=True)

    selected_info = tk.StringVar(value="Wybrano: SQLite — szybki start bez serwera")

    def select_engine(engine_name, *, close_after=True):
        try:
            switch_engine(engine_name)
            result["engine"] = engine_name
            if close_after:
                dialog.destroy()
        except Exception as e:
            messagebox.showerror(
                "Błąd konfiguracji",
                f"Nie udało się zapisać wyboru silnika bazy danych:\n\n{e}",
                parent=dialog,
            )

    def build_card(parent_widget, *, engine_name, icon, title, description, bullets, button_text, button_bg):
        card = tk.Frame(parent_widget, bg="white", bd=1, relief="solid", padx=20, pady=18)
        card.pack(side="left", fill="both", expand=True, padx=8)

        def on_pick():
            selected_engine.set(engine_name)
            selection_text = "SQLite — szybki start bez serwera" if engine_name == "sqlite" else "PostgreSQL — pełna konfiguracja serwerowa"
            selected_info.set(f"Wybrano: {selection_text}")

        def on_apply():
            on_pick()
            select_engine(engine_name)

        tk.Label(card, text=icon, font=("Segoe UI Emoji", 26), bg="white").pack(anchor="w")
        tk.Label(card, text=title, font=("Segoe UI", 15, "bold"), bg="white", fg="#212529").pack(anchor="w", pady=(8, 10))
        tk.Label(card, text=description, font=("Segoe UI", 10), bg="white", fg="#495057",
                 justify="left", wraplength=280).pack(anchor="w")

        ttk.Radiobutton(
            card,
            text="Ustaw jako wybór",
            variable=selected_engine,
            value=engine_name,
            command=on_pick,
        ).pack(anchor="w", pady=(12, 4))

        bullets_frame = tk.Frame(card, bg="white")
        bullets_frame.pack(fill="x", pady=(14, 16))
        for bullet in bullets:
            tk.Label(
                bullets_frame,
                text=f"• {bullet}",
                font=("Segoe UI", 9),
                bg="white",
                fg="#343a40",
                justify="left",
                anchor="w"
            ).pack(anchor="w", pady=2)

        tk.Button(
            card,
            text=button_text,
            font=("Segoe UI", 10, "bold"),
            bg=button_bg,
            fg="white",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=10,
            command=on_apply,
        ).pack(anchor="w", pady=(6, 0))

    build_card(
        cards,
        engine_name="sqlite",
        icon="💾",
        title="SQLite",
        description="Lokalna baza plikowa. Najszybszy start bez dodatkowej instalacji serwera.",
        bullets=[
            "działa od razu po wyborze",
            "dobra opcja na start i pracę lokalną",
            "nie wymaga konfiguracji PostgreSQL",
        ],
        button_text="Użyj SQLite",
        button_bg="#198754",
    )

    build_card(
        cards,
        engine_name="postgresql",
        icon="🐘",
        title="PostgreSQL",
        description="Pełna konfiguracja serwerowa. Po wyborze otworzy się formularz połączenia.",
        bullets=[
            "dla bardziej zaawansowanych wdrożeń",
            "lepsze zarządzanie danymi i rozbudowa",
            "po wyborze podasz host, port, użytkownika i hasło",
            "wymaga PostGIS dla map GIS (geometria działek)",
        ],
        button_text="Skonfiguruj PostgreSQL",
        button_bg="#0d6efd",
    )

    bottom_frame = tk.Frame(main_frame, bg="#f8f9fa")
    bottom_frame.pack(fill="x", pady=(16, 0))
    tk.Label(
        bottom_frame,
        textvariable=selected_info,
        font=("Segoe UI", 10, "bold"),
        bg="#f8f9fa",
        fg="#0d6efd",
        justify="left"
    ).pack(anchor="w", pady=(0, 10))

    # === Przycisk "Zainstaluj EDB PostgreSQL + PostGIS system-wide" ===
    # Jedyna wspierana ścieżka dla użytkowników bez PG w systemie. Wcześniej
    # była tu opcja portable PG, ale portable ma bug z DLL (pg_ctl nie
    # startuje na wielu Windows). EDB installer system-wide działa na
    # wszystkich Windows ale wymaga uprawnień administratora.
    edb_frame = tk.Frame(bottom_frame, bg="#fff3cd", bd=1, relief="solid", padx=14, pady=12)
    edb_frame.pack(fill="x", pady=(0, 12))
    tk.Label(
        edb_frame,
        text="📦 Brak PostgreSQL w systemie?",
        font=("Segoe UI", 11, "bold"),
        bg="#fff3cd",
        fg="#856404",
        justify="left",
    ).pack(anchor="w")
    tk.Label(
        edb_frame,
        text=(
            "Zainstaluj EDB PostgreSQL + PostGIS system-wide (~460 MB, wymaga "
            "uprawnień administratora). Działa na wszystkich Windows."
        ),
        font=("Segoe UI", 9),
        bg="#fff3cd",
        fg="#856404",
        justify="left",
        wraplength=640,
    ).pack(anchor="w", pady=(4, 8))

    def on_install_edb_pg_postgis():
        """Woła instalację EDB PostgreSQL + PostGIS system-wide (subprocess).

        Wyciągnięte do helpera ``_run_edb_installer`` -- DRY, reużywane
        też przez ``_show_postgres_install_required``.
        """
        _run_edb_installer(dialog)

    tk.Button(
        edb_frame,
        text="🔧  Zainstaluj EDB PostgreSQL + PostGIS (~460 MB)",
        font=("Segoe UI", 10, "bold"),
        bg="#0d6efd",
        fg="white",
        activeforeground="white",
        relief="flat",
        cursor="hand2",
        padx=14,
        pady=8,
        command=on_install_edb_pg_postgis,
    ).pack(anchor="w")

    buttons_frame = tk.Frame(bottom_frame, bg="#f8f9fa")
    buttons_frame.pack(fill="x")

    def on_closing():
        if messagebox.askyesno(
            "Zamknąć konfigurację?",
            "Nie wybrano jeszcze silnika bazy danych.\n\n"
            "Zamknięcie przerwie uruchamianie programu. Czy chcesz zakończyć?",
            parent=dialog,
        ):
            dialog.destroy()

    def apply_selected_engine():
        select_engine(selected_engine.get())

    tk.Button(
        buttons_frame,
        text="Kontynuuj z wybranym silnikiem",
        font=("Segoe UI", 10, "bold"),
        bg="#212529",
        fg="white",
        activeforeground="white",
        relief="flat",
        cursor="hand2",
        padx=16,
        pady=10,
        command=apply_selected_engine,
    ).pack(side="left")

    ttk.Button(buttons_frame, text="Anuluj", command=on_closing).pack(side="right")

    footer = tk.Frame(main_frame, bg="#f8f9fa")
    footer.pack(fill="x", pady=(14, 0))
    tk.Label(
        footer,
        text="Wskazówka: pgAdmin to narzędzie do obsługi PostgreSQL — tutaj wybierasz sam silnik bazy danych.",
        font=("Segoe UI", 9),
        bg="#f8f9fa",
        fg="#6c757d",
        justify="left"
    ).pack(anchor="w")

    dialog.protocol("WM_DELETE_WINDOW", on_closing)
    dialog.wait_window()

    if temp_root is not None:
        temp_root.destroy()

    if result["engine"] is None:
        sys.exit(1)

    return result["engine"]


def setup_postgres_config(parent=None):
    """
    Sprawdza konfigurację wybranego silnika bazy danych.
    Dla SQLite pomija konfigurację PostgreSQL.
    Dla PostgreSQL pilnuje istnienia pliku .postgres.env.

    Refactor (2026-06-05):
        Wcześniej ta funkcja miała 300+ linii inline'owego formularza.
        Teraz deleguje do ``configure_postgres_connection`` — zunifikowany
        dialog z 2 ścieżkami (Połącz z istniejącym PG / Zainstaluj EDB).

        Po zamknięciu dialogu instalacji (bez instalacji):
        1. Button w dialogu zapisuje ``DB_ENGINE=sqlite`` przez ``switch_engine``
        2. ``setup_postgres_config`` przechodzi dalej na SQLite bez kolejnego
           ``choose_database_engine``
        3. To zapobiega pętli PG → Wróć → PG → Wróć → SQLite
    """
    db_engine = choose_database_engine(parent=parent)

    if db_engine.lower() == "sqlite":
        _safe_print("✅ SQLite wybrany - pomijanie konfiguracji PostgreSQL")
        database_setup_service.ensure_sqlite_postgres_placeholder()
        return True

    # Sprawdź czy plik już istnieje
    if database_setup_service.postgres_config_exists():
        return True

    _safe_print("⚠️ Wybrano PostgreSQL, ale brak pliku konfiguracji (.postgres.env)")

    # Nowy dialog z 2 ścieżkami: "Połącz z istniejącym" albo "Zainstaluj EDB"
    return configure_postgres_connection(parent=parent)


# =============================================================================
# UNIFIKOWANY DIALOG KONFIGURACJI POSTGRESQL (2026-06-05)
# =============================================================================
# Dwie ścieżki w jednym oknie:
# 1) "Połącz z istniejącą instancją PG" — formularz host/port/user/hasło/baza,
#    test połączenia, "🎯 Domyślne" dla lokalnej instalacji, hint o zewnętrznej
#    instancji. Po sukcesie: zapis .postgres.env + create DB + PostGIS + schemat.
# 2) "Zainstaluj EDB PostgreSQL + PostGIS" — woła _run_edb_installer (ten sam
#    helper co w pierwszym flow). Po instalacji launcher zamyka się i user
#    uruchamia ponownie ze świeżym stanem.

# Stałe pomocnicze (zgodne z install_pg_unattended.py i dotychczasowym formularzem)
_PG_DEFAULTS = {
    "host": "localhost",
    "port": "5432",
    "user": "postgres",
    "password": "1234",
    "db_name": "mapa_czarna_db",
}


def configure_postgres_connection(parent=None) -> bool:
    """Zunifikowany dialog konfiguracji PostgreSQL z 2 ścieżkami.

    Ścieżka A: "Połącz z istniejącą instancją"
        Formularz host/port/user/hasło/baza. Przycisk "🎯 Domyślne" wypełnia
        wartościami dla lokalnej instalacji EDB (localhost/5432/postgres/1234
        /mapa_czarna_db). "🔌 Test połączenia" sprawdza czy serwer żyje.
        "💾 Zapisz i skonfiguruj" zapisuje .postgres.env i wywołuje
        ``ensure_postgres_database_with_postgis`` — tworzy bazę jeśli nie ma,
        włącza PostGIS, aplikuje schemat.

    Ścieżka B: "Zainstaluj EDB PostgreSQL + PostGIS"
        Wywołuje ``_run_edb_installer`` (helper z istniejącego flow). Po
        instalacji launcher się zamyka (zachowanie zgodne z pierwotnym flow).

    Returns:
        True jeśli konfiguracja zakończyła się sukcesem (połączenie OK albo
        uruchomiono instalator). False jeśli user anulował.
    """
    if parent is None:
        temp_root = tk.Tk()
        temp_root.withdraw()
        parent_window = temp_root
    else:
        parent_window = parent
        temp_root = None

    dialog = tk.Toplevel(parent_window)
    dialog.title("Konfiguracja PostgreSQL")
    scale = getattr(parent, "ui_scale", get_ui_scale_setting()) if parent else get_ui_scale_setting()
    w = int(720 * scale)
    h = int(660 * scale)
    dialog.geometry(f"{w}x{h}")
    dialog.minsize(w, h)
    dialog.resizable(True, True)
    dialog.transient(parent_window)
    set_dialog_icon(dialog)
    _center_window_on_screen(dialog, w, h, parent=parent_window)
    dialog.grab_set()
    dialog.focus_force()
    dialog.attributes("-topmost", True)

    # === Zmienne wynikowe ===
    # success = True oznacza: albo user wybrał "Zainstaluj" (instalator uruchomiony),
    # albo "Połącz" i konfiguracja zakończyła się sukcesem.
    result = {"success": False}

    main = tk.Frame(dialog, bg="#f8f9fa", padx=32, pady=24)
    main.pack(fill="both", expand=True)

    # === Nagłówek ===
    tk.Label(
        main,
        text="Wybierz źródło PostgreSQL",
        font=("Segoe UI", 16, "bold"),
        bg="#f8f9fa",
        fg="#212529",
    ).pack(anchor="w")

    tk.Label(
        main,
        text=(
            "Masz już PostgreSQL na swoim komputerze / serwerze? Wpisz dane. "
            "Nie masz? Zainstalujemy EDB PostgreSQL 16 + PostGIS."
        ),
        font=("Segoe UI", 10),
        bg="#f8f9fa",
        fg="#495057",
        justify="left",
        wraplength=640,
    ).pack(anchor="w", pady=(6, 18))

    # === Tryb (2 radio buttony) ===
    mode_var = tk.StringVar(value="connect")

    radio_frame = tk.Frame(main, bg="#f8f9fa")
    radio_frame.pack(fill="x", pady=(0, 16))

    def _select_mode(mode: str) -> None:
        mode_var.set(mode)
        if mode == "connect":
            connect_frame.pack(fill="x", pady=(0, 12), after=radio_frame)
            install_frame.pack_forget()
        else:
            install_frame.pack(fill="x", pady=(0, 12), after=radio_frame)
            connect_frame.pack_forget()

    tk.Radiobutton(
        radio_frame,
        text="🔌  Połącz z istniejącą instancją PostgreSQL",
        variable=mode_var,
        value="connect",
        font=("Segoe UI", 11),
        bg="#f8f9fa",
        activebackground="#f8f9fa",
        selectcolor="#f8f9fa",
        anchor="w",
        command=lambda: _select_mode("connect"),
    ).pack(anchor="w", pady=4)

    tk.Radiobutton(
        radio_frame,
        text="📦  Zainstaluj EDB PostgreSQL + PostGIS lokalnie",
        variable=mode_var,
        value="install",
        font=("Segoe UI", 11),
        bg="#f8f9fa",
        activebackground="#f8f9fa",
        selectcolor="#f8f9fa",
        anchor="w",
        command=lambda: _select_mode("install"),
    ).pack(anchor="w", pady=4)

    # === Ścieżka A: Połącz z istniejącym ===
    connect_frame = tk.Frame(main, bg="#f8f9fa")

    # Szybki start — "🎯 Domyślne" (tu MA sens: user wchodzi z pustym formularzem)
    preset_row = ttk.Frame(connect_frame)
    preset_row.pack(fill="x", pady=(0, 8))
    ttk.Label(
        preset_row, text="Szybki start:", font=("Segoe UI", 9, "bold")
    ).pack(side="left", padx=(0, 12))
    ttk.Button(
        preset_row,
        text="🎯 Wypełnij domyślnymi",
        command=lambda: _fill_pg_defaults(fields),
    ).pack(side="left")

    # Hint o zewnętrznej instancji
    ttk.Label(
        connect_frame,
        text=(
            "💡 Wskazówka: możesz też wskazać zewnętrzną instancję PostgreSQL "
            "(swój serwer) — zmień Host i Port na jej adres."
        ),
        font=("Segoe UI", 9),
        foreground="#6c757d",
        wraplength=640,
        justify="left",
    ).pack(anchor="w", pady=(0, 12))

    # Formularz: host, port, user, hasło, baza
    form = tk.Frame(connect_frame, bg="#f8f9fa")
    form.pack(fill="x")
    form.columnconfigure(1, weight=1)

    fields: dict = {}
    for i, (key, label) in enumerate([
        ("host", "Host:"),
        ("port", "Port:"),
        ("user", "Użytkownik:"),
        ("password", "Hasło:"),
        ("db_name", "Baza danych:"),
    ]):
        tk.Label(
            form, text=label, font=("Segoe UI", 10, "bold"),
            bg="#f8f9fa", anchor="w",
        ).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 10))
        show = "*" if key == "password" else ""
        var = tk.StringVar(value=_PG_DEFAULTS[key] if key != "password" else "")
        entry = tk.Entry(form, textvariable=var, font=("Segoe UI", 11),
                         show=show, relief="solid", borderwidth=2)
        entry.grid(row=i, column=1, sticky="ew", pady=4, ipady=4)
        fields[key] = var

    # "Pokaż hasło" checkbox
    show_pw_var = tk.BooleanVar(value=False)
    def _toggle_pw() -> None:
        pw_entry = form.grid_slaves(row=3, column=1)
        if not pw_entry:
            return
        pw_entry[0].destroy()
        new_entry = tk.Entry(
            form, textvariable=fields["password"], font=("Segoe UI", 11),
            show="" if show_pw_var.get() else "*",
            relief="solid", borderwidth=2,
        )
        new_entry.grid(row=3, column=1, sticky="ew", pady=4, ipady=4)
    tk.Checkbutton(
        form, text="Pokaż hasło", variable=show_pw_var,
        command=_toggle_pw, bg="#f8f9fa", activebackground="#f8f9fa",
    ).grid(row=4, column=1, sticky="e", pady=(0, 4))

    # Status (ikona + komunikat testu połączenia)
    status_var = tk.StringVar(value="")
    status_label = tk.Label(
        connect_frame, textvariable=status_var, font=("Segoe UI", 10),
        bg="#f8f9fa", wraplength=640, justify="left",
    )
    status_label.pack(anchor="w", pady=(8, 4))

    # Info o automatycznym tworzeniu bazy
    tk.Label(
        connect_frame,
        text=(
            "ℹ️ Jeśli baza nie istnieje, zostanie automatycznie utworzona "
            "z PostGIS i schematem launchera."
        ),
        font=("Segoe UI", 9),
        fg="#6c757d", bg="#f8f9fa",
        wraplength=640, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    # === Ścieżka B: Zainstaluj EDB ===
    install_frame = tk.Frame(main, bg="#FFF3CD", bd=1, relief="solid", padx=16, pady=14)
    tk.Label(
        install_frame,
        text="📦 Instalacja EDB PostgreSQL 16 + PostGIS",
        font=("Segoe UI", 11, "bold"),
        bg="#FFF3CD", fg="#856404", justify="left",
    ).pack(anchor="w")
    tk.Label(
        install_frame,
        text=(
            "Wymaga uprawnień administratora (UAC). "
            "Czas: 5-10 min. Rozmiar: ~460 MB. "
            "Po instalacji baza 'mapa_czarna_db' zostanie utworzona automatycznie."
        ),
        font=("Segoe UI", 9),
        bg="#FFF3CD", fg="#856404", justify="left", wraplength=600,
    ).pack(anchor="w", pady=(4, 10))
    tk.Button(
        install_frame,
        text="🔧  Zainstaluj EDB PostgreSQL + PostGIS",
        font=("Segoe UI", 10, "bold"),
        bg="#0d6efd", fg="white", activeforeground="white",
        activebackground="#0b5ed7", relief="flat", cursor="hand2",
        padx=14, pady=8,
        command=lambda: _on_install_click(),
    ).pack(anchor="w")

    def _on_install_click() -> None:
        result["success"] = True
        _run_edb_installer(dialog)

    # === Przycisk "Zapisz i skonfiguruj" (tylko dla ścieżki A) ===
    save_button = tk.Button(
        connect_frame,
        text="💾  Zapisz i skonfiguruj",
        font=("Segoe UI", 11, "bold"),
        bg="#198754", fg="white", activeforeground="white",
        activebackground="#146c43", relief="flat", cursor="hand2",
        padx=20, pady=10,
        command=lambda: _on_save_click(),
    )
    save_button.pack(anchor="w", pady=(8, 0))

    # === Dolne buttony (Anuluj) ===
    bottom = tk.Frame(main, bg="#f8f9fa")
    bottom.pack(fill="x", pady=(12, 0), side="bottom")
    tk.Button(
        bottom, text="Anuluj", font=("Segoe UI", 10),
        bg="#6c757d", fg="white", activeforeground="white",
        relief="flat", cursor="hand2", padx=14, pady=8,
        command=dialog.destroy,
    ).pack(side="right")

    # Pokaż domyślną ścieżkę (connect) przy starcie
    _select_mode("connect")

    def _on_save_click() -> None:
        """Walidacja → test → zapis .postgres.env → create DB → PostGIS → schemat."""
        host = fields["host"].get().strip()
        port_str = fields["port"].get().strip()
        user = fields["user"].get().strip()
        password = fields["password"].get()  # NIE strip() — hasło może mieć spacje
        db_name = fields["db_name"].get().strip()

        # Walidacja
        if not all([host, port_str, user, password, db_name]):
            status_var.set("⚠️ Uzupełnij wszystkie pola (w tym hasło).")
            status_label.config(fg="#dc3545")
            return
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            status_var.set(f"⚠️ Port musi być liczbą 1-65535, podano: {port_str!r}")
            status_label.config(fg="#dc3545")
            return

        # Disable buttonu podczas pracy
        save_button.config(state="disabled", text="⏳  Konfiguruję…")
        dialog.update_idletasks()

        # Helper tworzy bazę jeśli nie ma + PostGIS + schemat
        ok, msg = database_setup_service.ensure_postgres_database_with_postgis(
            host, port, user, password, db_name,
        )
        if ok:
            # Zapisz .postgres.env (DB_HOST/DB_USER/...) do launchera
            database_setup_service.save_launcher_postgres_config(host, port, user, password)
            status_var.set(f"✅ {msg}")
            status_label.config(fg="#198754")
            result["success"] = True
            dialog.after(800, dialog.destroy)
        else:
            status_var.set(f"❌ {msg}")
            status_label.config(fg="#dc3545")
            save_button.config(state="normal", text="💾  Zapisz i skonfiguruj")

    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.wait_window()

    if temp_root is not None:
        temp_root.destroy()

    return result["success"]


def _fill_pg_defaults(fields: dict) -> None:
    """Wypełnia pola formularza wartościami dla lokalnej instalacji EDB."""
    fields["host"].set(_PG_DEFAULTS["host"])
    fields["port"].set(_PG_DEFAULTS["port"])
    fields["user"].set(_PG_DEFAULTS["user"])
    fields["password"].set(_PG_DEFAULTS["password"])
    fields["db_name"].set(_PG_DEFAULTS["db_name"])
