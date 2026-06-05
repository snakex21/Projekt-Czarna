from __future__ import annotations

import importlib
import ast
import inspect
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _parse_project_file(relative_path: str) -> ast.Module:
    path = PROJECT_ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_level_import_roots(relative_path: str) -> set[str]:
    """Return imported root package names from direct module-level imports only."""
    tree = _parse_project_file(relative_path)
    imports: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])

    return imports


MODULES_TO_IMPORT = [
    "launcher.ui.loading_dialog",
    "launcher.ui.photos_manager_dialog",
    "launcher.ui.add_edit_location_dialog",
    "launcher.ui.template_change_dialog",
    "launcher.ui.location_manager",
    "launcher.ui.database_wizard",
    "launcher.ui.database_config_dialogs",
    "launcher.ui.db_engine_switcher",
    "launcher.ui.env_runtime",
    "launcher.ui.window_runtime",
    "launcher.ui.console_runtime",
    "launcher.ui.test_center_runtime",
    "launcher.ui.shutdown_runtime",
    "launcher.services.firewall_runtime",
    "launcher.services.guardian_runtime",
    "launcher.services.network_runtime",
    "launcher.services.test_service",
    "launcher.ui.site_settings_manager",
    "launcher.ui.icon_chooser_window",
    "launcher.ui.instructions_window",
    "launcher.ui.network_dialogs",
    "launcher.ui.backup_manager",
    "launcher.ui.map_calibrator",
    "launcher.ui.env_editor",
    "launcher.ui.admin_settings",
    "launcher.ui.display_settings",
    "launcher.ui.progress_dialog",
    "launcher.launcher_app",
    "launcher.ui.program_settings",
]


@pytest.fixture
def forbid_tk_windows(monkeypatch):
    """Guard smoke imports against creating real Tkinter windows/dialogs."""
    import platform
    import tkinter as tk
    from tkinter import messagebox

    def fail_window_init(self, *args, **kwargs):
        raise AssertionError("Smoke import must not create Tkinter windows")

    def fail_dialog(*args, **kwargs):
        raise AssertionError("Smoke import must not open Tkinter dialogs")

    monkeypatch.setattr(tk.Tk, "__init__", fail_window_init)
    monkeypatch.setattr(tk.Toplevel, "__init__", fail_window_init)
    monkeypatch.setattr(messagebox, "showerror", fail_dialog)
    monkeypatch.setattr(messagebox, "showwarning", fail_dialog)
    monkeypatch.setattr(messagebox, "showinfo", fail_dialog)
    monkeypatch.setattr(messagebox, "askyesno", fail_dialog)

    # Avoid import-time Windows DPI calls in launcher_app during tests.
    monkeypatch.setattr(platform, "system", lambda: "Linux")

    return tk


@pytest.mark.parametrize("module_name", MODULES_TO_IMPORT)
def test_launcher_ui_modules_import_without_creating_windows(
    module_name,
    forbid_tk_windows,
    monkeypatch,
):
    monkeypatch.setenv("DB_ENGINE", "sqlite")

    try:
        from launcher.db import engine as db_engine

        db_engine._engine = None
    except Exception:
        pass

    sys.modules.pop(module_name, None)

    try:
        module = importlib.import_module(module_name)
    except SystemExit as exc:
        pytest.fail(f"{module_name} raised SystemExit during import: {exc}")

    assert module is not None
    assert getattr(forbid_tk_windows, "_default_root", None) is None


def test_launcher_app_public_ui_aliases():
    import launcher.launcher_app as app
    from launcher.ui.add_edit_location_dialog import AddEditLocationDialog
    from launcher.ui.admin_settings import AdminSettings
    from launcher.ui.backup_manager import BackupManager
    from launcher.ui.database_wizard import DatabaseWizard
    from launcher.ui.display_settings import DisplaySettingsDialog
    from launcher.ui.env_editor import EnvEditor
    from launcher.ui.icon_chooser_window import IconChooserWindow
    from launcher.ui.instructions_window import InstructionsWindow
    from launcher.ui.loading_dialog import LoadingDialog
    from launcher.ui.location_manager import LocationManager, TemplateChangeDialog
    from launcher.ui.map_calibrator import CalibrationInstructions, MapCalibrator
    from launcher.ui.photos_manager_dialog import PhotosManagerDialog
    from launcher.ui.progress_dialog import ProgressDialog
    from launcher.ui.site_settings_manager import SiteSettingsManager

    from launcher.ui.database_config_dialogs import choose_database_engine, setup_postgres_config

    assert app.AddEditLocationDialog is AddEditLocationDialog
    assert app.AdminSettings is AdminSettings
    assert app.BackupManager is BackupManager
    assert app.DatabaseWizard is DatabaseWizard
    assert app.DisplaySettingsDialog is DisplaySettingsDialog
    assert app.EnvEditor is EnvEditor
    assert app.IconChooserWindow is IconChooserWindow
    assert app.InstructionsWindow is InstructionsWindow
    assert app.LoadingDialog is LoadingDialog
    assert app.MapCalibrator is MapCalibrator
    assert app.CalibrationInstructions is CalibrationInstructions
    assert app.LocationManager is LocationManager
    assert app.TemplateChangeDialog is TemplateChangeDialog
    assert app.PhotosManagerDialog is PhotosManagerDialog
    assert app.ProgressDialog is ProgressDialog
    assert app.SiteSettingsManager is SiteSettingsManager
    assert app.choose_database_engine is choose_database_engine
    assert app.setup_postgres_config is setup_postgres_config


def test_dialogs_reexport_split_ui_classes():
    import launcher.ui.dialogs as dialogs
    from launcher.ui.add_edit_location_dialog import AddEditLocationDialog
    from launcher.ui.admin_settings import AdminSettings
    from launcher.ui.backup_manager import BackupManager
    from launcher.ui.database_wizard import DatabaseWizard
    from launcher.ui.env_editor import EnvEditor
    from launcher.ui.icon_chooser_window import IconChooserWindow
    from launcher.ui.instructions_window import InstructionsWindow
    from launcher.ui.loading_dialog import LoadingDialog
    from launcher.ui.location_manager import LocationManager, TemplateChangeDialog
    from launcher.ui.map_calibrator import CalibrationInstructions, MapCalibrator
    from launcher.ui.photos_manager_dialog import PhotosManagerDialog
    from launcher.ui.progress_dialog import ProgressDialog
    from launcher.ui.site_settings_manager import SiteSettingsManager

    assert dialogs.AddEditLocationDialog is AddEditLocationDialog
    assert dialogs.AdminSettings is AdminSettings
    assert dialogs.BackupManager is BackupManager
    assert dialogs.DatabaseWizard is DatabaseWizard
    assert dialogs.EnvEditor is EnvEditor
    assert dialogs.IconChooserWindow is IconChooserWindow
    assert dialogs.InstructionsWindow is InstructionsWindow
    assert dialogs.LoadingDialog is LoadingDialog
    assert dialogs.LocationManager is LocationManager
    assert dialogs.MapCalibrator is MapCalibrator
    assert dialogs.CalibrationInstructions is CalibrationInstructions
    assert dialogs.PhotosManagerDialog is PhotosManagerDialog
    assert dialogs.ProgressDialog is ProgressDialog
    assert dialogs.SiteSettingsManager is SiteSettingsManager
    assert dialogs.TemplateChangeDialog is TemplateChangeDialog


def test_dialogs_no_longer_defines_ui_classes_locally():
    tree = _parse_project_file("launcher/ui/dialogs.py")

    class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert class_names == set()

    source = (PROJECT_ROOT / "launcher/ui/dialogs.py").read_text(encoding="utf-8")
    legacy_prefix = "_" + "Split"
    assert legacy_prefix + "LoadingDialog" not in source
    assert legacy_prefix + "PhotosManagerDialog" not in source
    assert legacy_prefix + "AddEditLocationDialog" not in source

    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert function_names == set()


def test_security_manager_dead_code_removed_from_launcher():
    """P5.1: relikt Flask `security_manager.py` nie może zostać w launcherze.

    Stary moduł wołał nieistniejące endpointy `/api/admin/security/*`, więc
    zamiast utrzymywać fałszywy przycisk bezpieczeństwa usuwamy moduł i
    publiczne aliasy. Aktualna diagnostyka bezpieczeństwa jest w
    `ProgramSettingsWindow` → zakładka "Diagnostyka".
    """
    security_manager_path = PROJECT_ROOT / "launcher" / "ui" / "security_manager.py"
    launcher_source = (PROJECT_ROOT / "launcher" / "launcher_app.py").read_text(encoding="utf-8")
    dialogs_source = (PROJECT_ROOT / "launcher" / "ui" / "dialogs.py").read_text(encoding="utf-8")
    program_settings_source = (
        PROJECT_ROOT / "launcher" / "ui" / "program_settings.py"
    ).read_text(encoding="utf-8")

    assert not security_manager_path.exists(), "security_manager.py powinien zostać usunięty (dead code Flask)"
    assert "security_manager" not in launcher_source
    assert "SecurityManager" not in launcher_source
    assert "open_security_manager" not in launcher_source
    assert "security_manager" not in dialogs_source
    assert "SecurityManager" not in dialogs_source
    assert "open_security_manager" not in program_settings_source


@pytest.mark.parametrize(
    "relative_path",
    [
        "launcher/ui/loading_dialog.py",
        "launcher/ui/photos_manager_dialog.py",
        "launcher/ui/add_edit_location_dialog.py",
    ],
)
def test_next_split_ui_modules_do_not_import_dialogs(relative_path):
    top_level_imports = _top_level_import_roots(relative_path)
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    assert "launcher.ui.dialogs" not in source
    assert ".dialogs" not in source
    assert "dialogs" not in top_level_imports


def test_location_runtime_no_longer_imports_dialogs():
    source = (PROJECT_ROOT / "launcher/services/location_runtime.py").read_text(encoding="utf-8")

    assert "from ..ui.dialogs import LocationManager" not in source
    assert "from ..ui.dialogs import DatabaseWizard" not in source
    assert "from ..ui.location_manager import LocationManager" in source
    assert "from ..ui.database_wizard import DatabaseWizard" in source


def test_launcher_app_no_longer_defines_next_split_ui_locally():
    tree = _parse_project_file("launcher/launcher_app.py")

    class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "InstructionsWindow" not in class_names
    assert "choose_database_engine" not in function_names
    assert "setup_postgres_config" not in function_names


@pytest.mark.parametrize(
    "relative_path",
    [
        "launcher/ui/instructions_window.py",
        "launcher/ui/database_config_dialogs.py",
    ],
)
def test_next_split_dialog_modules_do_not_import_launcher_app_or_dialogs(relative_path):
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    top_level_imports = _top_level_import_roots(relative_path)

    assert "launcher.launcher_app" not in source
    assert "import_module(\"launcher.launcher_app\")" not in source
    assert "import_module('launcher.launcher_app')" not in source
    assert "def _get_launcher" not in source
    assert "def _launcher" not in source
    assert "launcher_app" not in top_level_imports

    assert "launcher.ui.dialogs" not in source
    assert ".dialogs" not in source
    assert "dialogs" not in top_level_imports


def test_database_config_dialogs_uses_database_setup_service_without_persistence_duplication():
    relative_path = "launcher/ui/database_config_dialogs.py"
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    top_level_imports = _top_level_import_roots(relative_path)

    assert "database_setup_service.ensure_sqlite_postgres_placeholder" in source
    assert "database_setup_service.postgres_config_exists" in source
    assert "database_setup_service.save_launcher_postgres_config" in source
    # Refactor (2026-06-05): test połączenia jest teraz wewnątrz
    # ``ensure_postgres_database_with_postgis`` (helper w database_setup_service),
    # a dialog woła ten helper zamiast bezpośrednio testować połączenie.
    assert "database_setup_service.ensure_postgres_database_with_postgis" in source
    assert "psycopg2" not in top_level_imports
    assert "POSTGRES_CONFIG_FILE" not in source
    assert "LAUNCHER_DB_PASSWORD=" not in source
    assert "connect_timeout=3" not in source


def test_database_config_dialogs_import_does_not_probe_database(monkeypatch, forbid_tk_windows):
    from launcher.services import database_setup_service

    def fail_db_probe(*args, **kwargs):
        raise AssertionError("Import must not test or write database config")

    monkeypatch.setattr(database_setup_service, "postgres_config_exists", fail_db_probe)
    monkeypatch.setattr(database_setup_service, "test_postgres_connection_values", fail_db_probe)
    monkeypatch.setattr(database_setup_service, "save_launcher_postgres_config", fail_db_probe)
    monkeypatch.setattr(database_setup_service, "ensure_sqlite_postgres_placeholder", fail_db_probe)

    sys.modules.pop("launcher.ui.database_config_dialogs", None)
    module = importlib.import_module("launcher.ui.database_config_dialogs")

    assert module is not None


# ---------------------------------------------------------------------------
# "Pierwsza konfiguracja" -- widoczność PostGIS info + przycisk "Pobierz portable"
# ---------------------------------------------------------------------------


def test_choose_database_engine_postgres_card_mentions_postgis():
    """Karta PostgreSQL w choose_database_engine musi wspomnieć o PostGIS.

    Użytkownik musi wiedzieć, że do map GIS (działki, geometria) potrzebny
    jest PostGIS. Bez tej informacji wybór PG bez PostGIS prowadzi do
    błędu ``CREATE EXTENSION postgis`` w kreatorze bez wyjaśnienia.
    """
    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")
    # Szukamy bullets z "postgis" (case-insensitive) w obrębie budowy karty PG.
    assert "PostGIS" in source, "Karta PG musi wspomnieć o PostGIS"
    assert "wymaga PostGIS" in source.lower() or "wymaga postgis" in source.lower(), (
        "Bullets karty PG muszą explicite mówić, że PostGIS jest wymagany"
    )


# ---------------------------------------------------------------------------
# Regression test dla fixu detect_engine() -- bezpieczny fallback SQLite
# ---------------------------------------------------------------------------


def test_choose_database_engine_defines_on_closing_before_button_command():
    """``on_closing`` musi być zdefiniowane ZANIM button "Anuluj" go użyje.

    Context (2026-06-05):
        Podczas refaktoryzacji (dodanie EDB button) ``def on_closing()``
        zostało przeniesione pod button "Anuluj". W Pythonie to powoduje
        ``UnboundLocalError: cannot access local variable 'on_closing'``
        przy starcie launchera -- dialog first-run w ogóle się nie pokazuje.

    Naprawione: ``on_closing`` jest teraz PRZED buttonem.

    Ten test parsuje AST i sprawdza kolejność definicji vs użycia.
    """
    import ast
    from pathlib import Path

    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Znajdź funkcję choose_database_engine
    choose_func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "choose_database_engine":
            choose_func = node
            break
    assert choose_func is not None, "Brak funkcji choose_database_engine"

    # Znajdź linię def on_closing() wewnątrz choose_database_engine
    on_closing_def_line = None
    for sub in ast.walk(choose_func):
        if isinstance(sub, ast.FunctionDef) and sub.name == "on_closing":
            on_closing_def_line = sub.lineno
            break
    assert on_closing_def_line is not None, (
        "Brak lokalnej funkcji on_closing wewnątrz choose_database_engine"
    )

    # Znajdź linię button "Anuluj" z command=on_closing
    anuluj_line = None
    for sub in ast.walk(choose_func):
        if isinstance(sub, ast.Assign):
            continue
        src_line = ast.unparse(sub) if hasattr(ast, "unparse") else ""
        if "Anuluj" in src_line and "on_closing" in src_line:
            for n in ast.walk(sub):
                if isinstance(n, ast.Name) and n.id == "on_closing":
                    anuluj_line = n.lineno
                    break
            if anuluj_line:
                break
    assert anuluj_line is not None, (
        "Brak button 'Anuluj' z command=on_closing w choose_database_engine"
    )

    # on_closing MUSI być zdefiniowane PRZED buttonem (linia mniejsza)
    assert on_closing_def_line < anuluj_line, (
        f"on_closing jest zdefiniowane na linii {on_closing_def_line} "
        f"ale button 'Anuluj' go używa na linii {anuluj_line}. "
        f"Python rzuci UnboundLocalError przy starcie launchera."
    )


# ---------------------------------------------------------------------------
# Regression test: okno first-run musi mieścić wszystkie widgety
# ---------------------------------------------------------------------------


def test_choose_database_engine_window_is_tall_enough_for_all_widgets():
    """Okno first-run dialogu musi być wystarczająco wysokie, by zmieścić
    WSZYSTKIE widgety BEZ scrollowania:

    - tytuł + opis tekstu (~110px)
    - dwie karty SQLite/PostgreSQL side-by-side (~340px)
    - sekcja EDB installer z ikonką, opisem i buttonem "Zainstaluj" (~160px)
    - dolne buttony "Kontynuuj z wybranym silnikiem" / "Anuluj" (~60px)
    - footer z wskazówką "Wskazówka: pgAdmin..." (~30px)
    - marginesy/paddingi (~40px)

    Context (2026-06-05):
        Domyślny rozmiar okna był 760x430 -- za mały. User widział TYLKO
        karty SQLite/PostgreSQL, ale NIE widział: statusu wyboru, sekcji
        EDB installer, dolnych buttonów ani footera. To czyniło dialog
        nieużytecznym (nie mógł kliknąć "Kontynuuj" żeby przejść dalej).

    Naprawione: ``h = int(900 * scale)`` (zamiast 430).
    Ten test sprawdza że h jest >= 750 w wartości bazowej (scale=1.0).
    """
    import re
    from pathlib import Path

    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")

    # Szukamy w, h w obrębie choose_database_engine (identyfikujemy po tytule
    # "Pierwsza konfiguracja bazy danych" -- tylko choose_database_engine go ma).
    # Inne dialogi (setup_postgres_config, _show_postgres_install_required)
    # mają WŁASNE w, h -- test NIE może ich łapać (mniejsze okna pomocnicze).
    title_marker = 'dialog.title("🗄️ Pierwsza konfiguracja bazy danych")'
    title_pos = source.find(title_marker)
    assert title_pos > 0, (
        "Nie znaleziono tytułu 'Pierwsza konfiguracja bazy danych' "
        "w choose_database_engine -- test nie może zlokalizować okna first-run."
    )

    # Szukamy h = int(X * scale) w obrębie 2000 znaków PO tytule
    # (okno first-run ma tylko jedną parę w, h).
    search_window = source[title_pos : title_pos + 2000]
    h_match = re.search(r"^\s*h\s*=\s*int\((\d+)\s*\*\s*scale\)", search_window, re.MULTILINE)
    assert h_match, (
        "Brak 'h = int(X * scale)' w oknie choose_database_engine "
        "(po tytule 'Pierwsza konfiguracja bazy danych')."
    )
    h = int(h_match.group(1))

    # Minimalna wysokość potrzebna do pokazania wszystkich widgetów
    # (szczegóły w docstringu testu)
    MIN_HEIGHT = 750
    assert h >= MIN_HEIGHT, (
        f"Okno first-run ma wysokość {h}px -- za mało, by zmieścić "
        f"karty + EDB installer + buttony + footer. "
        f"Wymagane minimum: {MIN_HEIGHT}px. "
        f"Zwiększ 'h = int(X * scale)' w choose_database_engine."
    )

    # Sprawdź też szerokość -- musi zmieścić 2 karty side-by-side
    w_match = re.search(r"^\s*w\s*=\s*int\((\d+)\s*\*\s*scale\)", search_window, re.MULTILINE)
    assert w_match, "Brak linii 'w = int(X * scale)' w choose_database_engine"
    w = int(w_match.group(1))
    MIN_WIDTH = 760
    assert w >= MIN_WIDTH, (
        f"Okno first-run ma szerokość {w}px -- za mało, by zmieścić "
        f"2 karty side-by-side. Minimum: {MIN_WIDTH}px."
    )

    # Sprawdź że minsize też używa tych wartości (nie hardcoded mniejsze)
    assert "dialog.minsize(w, h)" in source, (
        "dialog.minsize() musi używać tych samych wartości w, h "
        "co dialog.geometry() (inaczej okno można zmniejszyć poniżej "
        "wymaganego minimum i widgety znikną)."
    )


# ---------------------------------------------------------------------------
# Regression test: oba dialogi muszą być wyśrodkowane na ekranie
# ---------------------------------------------------------------------------


def test_setup_postgres_config_is_centered_on_screen():
    """Dialog ``setup_postgres_config`` musi być wyśrodkowany na ekranie.

    Context (2026-06-05):
        User zgłosił, że okno konfiguracji PostgreSQL pojawia się w losowym
        miejscu ekranu (a nie na środku). Po refaktoryzacji wyśrodkowanie
        było skopiowane ręcznie (3 linie) i pominęło ``dialog.transient`` --
        co na Windows 11 z multi-monitor powodowało że okno lądowało poza
        widocznym obszarem (np. na ujemnym X).

    Naprawione:
    1. Wspólny helper ``_center_window_on_screen`` (DRY, single source of truth)
    2. Helper preferuje wyśrodkowanie WZGLĘDEM PARENTA (główny monitor
       parenta, a nie ``winfo_screenwidth()`` który zwraca primary screen)
    3. Fallback: wyśrodkowanie na ekranie (gdy parent=None)
    4. ``dialog.transient(parent_window)`` dodane do setup_postgres_config
       (było tylko w choose_database_engine) -- zapewnia poprawne parentowanie
       okna w taskbarze Windowsa i ułatwia menadżerom okien.
    """
    import re
    from pathlib import Path

    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")

    # 1. Helper musi istnieć
    assert "def _center_window_on_screen(" in source, (
        "Brak helpera _center_window_on_screen() -- oba dialogi powinny "
        "używać wspólnej funkcji do wyśrodkowania okna (DRY)."
    )

    # 2. Helper musi wywoływać dialog.geometry z pozycją (X+Y)
    helper_match = re.search(
        r"def _center_window_on_screen\([^)]*\)[^\n]*:.*?(?=\ndef |\Z)",
        source,
        re.DOTALL,
    )
    assert helper_match, "Nie udało się wyciągnąć ciała helpera _center_window_on_screen"
    helper_body = helper_match.group(0)
    assert "dialog.geometry(" in helper_body, (
        "Helper _center_window_on_screen musi wywoływać dialog.geometry() "
        "z wartościami X+Y żeby faktycznie wyśrodkować okno."
    )
    assert "winfo_screenwidth" in helper_body, (
        "Helper musi używać winfo_screenwidth() do obliczenia środka ekranu"
    )

    # 3. setup_postgres_config musi mieć transient(parent_window)
    #    (WYMAGANE żeby okno było właściwie parentowane w taskbarze Windows)
    assert re.search(
        r"def setup_postgres_config\([^)]*\)[^\n]*:.*?dialog\.transient\(parent_window\)",
        source,
        re.DOTALL,
    ), (
        "Brak dialog.transient(parent_window) w setup_postgres_config! "
        "Bez tego okno nie jest właściwie parentowane -- na Windows 11 z "
        "multi-monitor może lądować poza widocznym obszarem ekranu."
    )

    # 4. setup_postgres_config musi wywoływać helper do wyśrodkowania
    assert re.search(
        r"def setup_postgres_config\([^)]*\)[^\n]*:.*?_center_window_on_screen\(",
        source,
        re.DOTALL,
    ), (
        "setup_postgres_config nie wywołuje _center_window_on_screen()! "
        "Powinien używać wspólnego helpera zamiast ręcznego kodu."
    )

    # 5. choose_database_engine też musi wywoływać helper (DRY)
    assert re.search(
        r"def choose_database_engine\([^)]*\)[^\n]*:.*?_center_window_on_screen\(",
        source,
        re.DOTALL,
    ), (
        "choose_database_engine nie wywołuje _center_window_on_screen()! "
        "Powinien używać wspólnego helpera zamiast ręcznego kodu."
    )

    # 6. Oba dialogi przekazują parent=parent_window do helpera
    #    (dzięki temu okno wyśrodkowuje się względem parenta, nie ekranu)
    assert source.count("_center_window_on_screen(dialog, w, h, parent=parent_window)") >= 2, (
        "Oba dialogi (choose_database_engine i setup_postgres_config) "
        "muszą wywoływać _center_window_on_screen z parent=parent_window."
    )


# ---------------------------------------------------------------------------
# Regression test: setup_postgres_config musi sprawdzić czy PG jest zainstalowane
# ---------------------------------------------------------------------------


def test_setup_postgres_config_checks_postgres_availability_before_form():
    """``setup_postgres_config`` MUSI sprawdzić ``check_postgres_available()``
    ZANIM pokaże formularz konfiguracji połączenia (host/port/user/password).

    Context (2026-06-05):
        User zgłosił, że okno "Konfiguracja PostgreSQL - WYMAGANE" pojawia
        się po wybraniu PG w first-run dialogu, ALE nie ma jak go wypełnić
        bo PG nie jest zainstalowane. Formularz pyta o host/port/user/password
        -- ale test połączenia (``test_postgres_connection_values``) i tak
        się nie uda bo serwera nie ma w systemie.

        To było logicznie bez sensu ("bezmózgu"): pytanie o konfigurację
        połączenia z bazą, której nie ma.

    Naprawione:
        ``setup_postgres_config`` wywołuje ``check_postgres_available()``
        PRZED otwarciem formularza. Jeśli PG nie ma, pokazuje dialog
        "Wymagana instalacja PostgreSQL" z buttonem "Zainstaluj EDB..."
        zamiast formularza. Formularz jest bezcelowy bez serwera.
    """
    import re
    from pathlib import Path

    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")

    # 1. Import check_postgres_available musi istnieć
    assert (
        "from launcher.utils.engine_access import check_postgres_available" in source
    ), "Brak importu check_postgres_available -- guard nie może działać bez niego"

    # 2. Refactor (2026-06-05): setup_postgres_config deleguje do
    #    configure_postgres_connection, który ma obie ścieżki (Połącz / Zainstaluj).
    #    Formularz nie pokazuje się gdy PG nie ma, bo ścieżka "Połącz" zawiera
    #    button "Zainstaluj EDB..." (call do _run_edb_installer) — user wybiera
    #    świadomie, bez formularza host/port.
    # Uwaga: sygnatura używa [^)]*\) zamiast .*?\\):, żeby regex nie zjadał
    # ciała funkcji do pierwszego `):` w środku (np. w for-loopie
    # `(key, label) in enumerate([...]):`).
    setup_func_match = re.search(
        r"def setup_postgres_config\([^)]*\)[^\n]*:(.*?)(?=\n\ndef |\Z)",
        source,
        re.DOTALL,
    )
    assert setup_func_match, "Nie udało się wyciągnąć ciała setup_postgres_config"
    setup_body = setup_func_match.group(1)

    assert "configure_postgres_connection" in setup_body, (
        "setup_postgres_config musi delegować do configure_postgres_connection "
        "(zunifikowany dialog z 2 ścieżkami)."
    )

    # 3. configure_postgres_connection MUSI istnieć i zawierać obie ścieżki
    config_func_match = re.search(
        r"def configure_postgres_connection\([^)]*\)[^\n]*:(.*?)(?=\n\ndef |\Z)",
        source,
        re.DOTALL,
    )
    assert config_func_match, (
        "Brak funkcji configure_postgres_connection! Formularz konfiguracji "
        "połączenia nie ma jak się pokazać."
    )
    config_body = config_func_match.group(1)

    # Ścieżka "Połącz z istniejącym" — musi mieć formularz i "🎯 Domyślne"
    assert "Połącz z istniejącą instancją PostgreSQL" in config_body, (
        "configure_postgres_connection musi mieć ścieżkę 'Połącz z istniejącą'."
    )
    assert "Wypełnij domyślnymi" in config_body, (
        "Ścieżka 'Połącz' musi mieć przycisk 'Wypełnij domyślnymi' dla "
        "lokalnej instalacji EDB (tu MA sens: user wchodzi z pustym formularzem)."
    )

    # Ścieżka "Zainstaluj EDB" — musi istnieć i wołać _run_edb_installer
    assert "Zainstaluj EDB PostgreSQL + PostGIS lokalnie" in config_body, (
        "configure_postgres_connection musi mieć ścieżkę 'Zainstaluj EDB'."
    )
    assert "_run_edb_installer" in config_body, (
        "Ścieżka 'Zainstaluj' musi wołać _run_edb_installer (instalator EDB + PostGIS)."
    )

    # Helper "create DB + PostGIS + schemat" musi być wołany po "Zapisz i skonfiguruj"
    assert "ensure_postgres_database_with_postgis" in config_body, (
        "Po zapisie konfiguracji musi być wywołany helper tworzący bazę "
        "+ PostGIS + schemat (jeśli nie istnieją)."
    )


def test_show_postgres_install_required_dialog_function_exists():
    """Funkcja ``_show_postgres_install_required`` musi istnieć.

    Context (2026-06-05):
        Gdy ``setup_postgres_config`` wykryje brak PG w systemie, musi
        pokazać specjalny dialog zamiast formularza. Ten dialog:
        1. Wyjaśnia DLACZEGO nie ma formularza (PG nie ma)
        2. Daje button "Zainstaluj EDB PostgreSQL + PostGIS" (jedyna ścieżka)
        3. Daje button "Przełącz na SQLite" (fail-safe bez pętli wyboru)
    """
    import re
    from pathlib import Path

    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")

    # Funkcja musi istnieć
    func_match = re.search(
        r"def _show_postgres_install_required\(.*?\):",
        source,
    )
    assert func_match, (
        "Brak funkcji _show_postgres_install_required()! "
        "Gdy PG nie jest zainstalowane, setup_postgres_config musi "
        "pokazać dialog instalacji zamiast formularza host/port/user/password."
    )

    # Wyciągnij ciało funkcji
    func_body_match = re.search(
        r"def _show_postgres_install_required\([^)]*\)[^\n]*:(.*?)(?=\n\ndef |\Z)",
        source,
        re.DOTALL,
    )
    assert func_body_match, "Nie udało się wyciągnąć ciała _show_postgres_install_required"
    body = func_body_match.group(1)

    # Dialog MUSI mieć przycisk instalacji EDB
    assert "_run_edb_installer" in body, (
        "_show_postgres_install_required nie wywołuje _run_edb_installer! "
        "Bez tego dialog jest bez sensu -- user nie ma jak zainstalować PG."
    )

    # Dialog MUSI mieć przycisk przełączenia na SQLite bez powrotu do wyboru
    assert "Przełącz na SQLite" in body, (
        "_show_postgres_install_required nie ma button 'Przełącz na SQLite'! "
        "User musi mieć opcję fail-safe bez ponownego choose_database_engine."
    )
    assert 'switch_engine("sqlite")' in body, (
        "Button 'Przełącz na SQLite' musi zapisywać DB_ENGINE=sqlite przez switch_engine."
    )

    # Dialog MUSI wyjaśniać dlaczego nie pokazujemy formularza
    assert "nie ma sensu" in body or "nie jest zainstalowany" in body, (
        "_show_postgres_install_required nie wyjaśnia userowi "
        "dlaczego nie pokazujemy formularza konfiguracji."
    )

    # Dialog MUSI być wyśrodkowany
    assert "_center_window_on_screen" in body, (
        "_show_postgres_install_required nie jest wyśrodkowany!"
    )


def test_run_edb_installer_is_used_by_both_dialogs():
    """Helper ``_run_edb_installer`` musi być reużywany (DRY).

    Context (2026-06-05):
        Logika EDB installer (subprocess.Popen + UAC + zamknięcie launchera)
        była zagnieżdżona w ``choose_database_engine``. Po dodaniu
        ``_show_postgres_install_required`` wymagałaby duplikacji.

    Naprawione: wyciągnięta do ``_run_edb_installer(dialog)``.
    Ten test sprawdza że helper istnieje i jest używany w obu miejscach.
    """
    import re
    from pathlib import Path

    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")

    # 1. Helper musi istnieć
    assert re.search(
        r"def _run_edb_installer\([^)]*\)[^\n]*:", source
    ), "Brak helpera _run_edb_installer() -- DRY violation, logika jest duplikowana"

    # 2. choose_database_engine wywołuje helper (NIE ma już zagnieżdżonej wersji)
    choose_match = re.search(
        r"def choose_database_engine\([^)]*\)[^\n]*:(.*?)(?=\n\ndef |\Z)",
        source,
        re.DOTALL,
    )
    assert choose_match, "Nie udało się wyciągnąć ciała choose_database_engine"
    choose_body = choose_match.group(1)

    assert "_run_edb_installer(dialog)" in choose_body, (
        "choose_database_engine nie wywołuje _run_edb_installer(dialog)! "
        "Powinien używać helpera zamiast duplikować logikę EDB installer."
    )

    # 3. _show_postgres_install_required wywołuje helper
    show_match = re.search(
        r"def _show_postgres_install_required\([^)]*\)[^\n]*:(.*?)(?=\n\ndef |\Z)",
        source,
        re.DOTALL,
    )
    assert show_match, "Nie udało się wyciągnąć ciała _show_postgres_install_required"
    show_body = show_match.group(1)

    assert "_run_edb_installer(dialog)" in show_body, (
        "_show_postgres_install_required nie wywołuje _run_edb_installer(dialog)!"
    )

    # 4. Helper musi używać subprocess.Popen (rdzeń logiki)
    helper_match = re.search(
        r"def _run_edb_installer\([^)]*\)[^\n]*:(.*?)(?=\n\ndef |\Z)",
        source,
        re.DOTALL,
    )
    assert helper_match, "Nie udało się wyciągnąć ciała _run_edb_installer"
    helper_body = helper_match.group(1)

    assert "subprocess.Popen" in helper_body, (
        "_run_edb_installer nie używa subprocess.Popen -- brakuje logiki uruchamiania instalatora"
    )
    assert "install_pg_gui.py" in helper_body, (
        "_run_edb_installer nie odwołuje się do graficznego instalatora install_pg_gui.py"
    )
    assert "pythonw.exe" in helper_body, (
        "_run_edb_installer powinien uruchamiać GUI przez pythonw.exe, bez okna konsoli"
    )
    assert "CREATE_NEW_CONSOLE" not in helper_body, (
        "Graficzny instalator nie może wymuszać otwierania nowej konsoli"
    )
    assert "Instalator uruchomiony" not in helper_body, (
        "Nie pokazujemy osobnego popupu po starcie instalatora — zasłania GUI instalacji"
    )
    assert "root.destroy" in helper_body, (
        "Po uruchomieniu instalatora launcher powinien się zamknąć, żeby nie trzymać starego stanu"
    )


# ---------------------------------------------------------------------------
# Regression test: choose_database_engine musi resetować .env gdy PG nie ma
# ---------------------------------------------------------------------------


def test_choose_database_engine_resets_env_when_postgres_missing():
    """``choose_database_engine`` MUSI zresetować ``.env`` gdy mówi ``postgresql``
    ale PG nie jest zainstalowane w systemie.

    Context (2026-06-05):
        Po deinstalacji PG, ``.env`` miał ``DB_ENGINE=postgresql`` (z poprzedniej
        konfiguracji). Stary kod ``choose_database_engine`` czytał ``.env``
        i zwracał cicho ``"postgresql"`` BEZ pokazywania dialogu -- bo
        ``.env`` już mówiło "postgresql". Launcher próbował łączyć się z
        nieistniejącym PG i crashował z ``Connection refused``.

        Fix: ``choose_database_engine`` wywołuje ``check_postgres_available()``.
        Jeśli ``.env`` mówi ``postgresql`` ale PG nie ma:
        1. Wywołuje ``_reset_db_engine_to_empty()`` (czyści ``.env``)
        2. Pokazuje dialog (user musi świadomie wybrać: SQLite LUB zainstalować PG)
    """
    import re
    from pathlib import Path

    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")

    # 1. Helper _reset_db_engine_to_empty musi istnieć
    assert re.search(
        r"def _reset_db_engine_to_empty\(.*?\):", source
    ), "Brak helpera _reset_db_engine_to_empty() -- flow nie może się zregenerować"

    # 2. choose_database_engine musi wywołać check_postgres_available()
    choose_match = re.search(
        r"def choose_database_engine\([^)]*\)[^\n]*:(.*?)(?=\n\ndef |\Z)",
        source,
        re.DOTALL,
    )
    assert choose_match, "Nie udało się wyciągnąć ciała choose_database_engine"
    choose_body = choose_match.group(1)

    assert "check_postgres_available()" in choose_body, (
        "choose_database_engine nie sprawdza check_postgres_available()! "
        "Bez tego launcher zwraca cicho 'postgresql' z .env nawet gdy "
        "PG nie ma w systemie, i crashuje przy próbie połączenia."
    )

    # 3. Guard musi być PRZED return current_engine (inaczej nigdy się nie wywoła)
    available_pos = choose_body.find("check_postgres_available()")
    return_pos = choose_body.find("if current_engine in (")
    assert available_pos > 0, "Nie znaleziono check_postgres_available() w choose_database_engine"
    assert return_pos > 0, "Nie znaleziono 'if current_engine in' w choose_database_engine"
    assert available_pos < return_pos, (
        f"check_postgres_available() jest na pozycji {available_pos} ale "
        f"return current_engine na {return_pos}. "
        f"Guard musi być PRZED return -- inaczej user z .env='postgresql' "
        f"ale bez PG w systemie zobaczy cichy return (crash)."
    )

    # 4. Guard musi wywołać _reset_db_engine_to_empty (nie tylko messagebox)
    assert "_reset_db_engine_to_empty" in choose_body, (
        "choose_database_engine nie wywołuje _reset_db_engine_to_empty()! "
        "Bez resetu .env, przy kolejnym uruchomieniu launchera znowu "
        "będzie próbował łączyć się z nieistniejącym PG."
    )


def test_setup_postgres_config_uses_sqlite_after_install_dialog_without_rechoosing():
    """``setup_postgres_config`` po SQLite przechodzi bez pętli wyboru silnika.

    Context (2026-06-05):
        Refactor: ``setup_postgres_config`` deleguje do ``configure_postgres_connection``.
        Ten nowy dialog ma 2 ścieżki, więc nie ma już pętli PG → Wróć → PG → Wróć → SQLite.
        Test weryfikuje:
        1. SQLite path: setup_postgres_config NIE woła choose_database_engine ponownie
        2. Po SQLite jest ensure_sqlite_postgres_placeholder + return True
    """
    import re

    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")

    setup_match = re.search(
        r"def setup_postgres_config\([^)]*\)[^\n]*:(.*?)(?=\n\ndef |\Z)",
        source,
        re.DOTALL,
    )
    assert setup_match, "Nie udało się wyciągnąć ciała setup_postgres_config"
    setup_body = setup_match.group(1)

    # 1. SQLite path: zapewnia placeholder i zwraca True (bez ponownego wyboru silnika)
    assert "db_engine.lower() == \"sqlite\"" in setup_body
    assert "ensure_sqlite_postgres_placeholder()" in setup_body, (
        "Ścieżka SQLite w setup_postgres_config musi wywołać ensure_sqlite_postgres_placeholder"
    )
    # NIE może być ponownego choose_database_engine w tej ścieżce
    sqlite_branch = setup_body[setup_body.find('db_engine.lower() == "sqlite"'):]
    # Koniec brancha to "return True" w tej samej ścieżce
    end_pos = sqlite_branch.find("return True")
    sqlite_branch = sqlite_branch[:end_pos] if end_pos > 0 else sqlite_branch
    assert "choose_database_engine(" not in sqlite_branch, (
        "Ścieżka SQLite nie może ponownie wołać choose_database_engine (pętla)."
    )

    # 2. PG path: deleguje do configure_postgres_connection (nowy zunifikowany dialog)
    assert "configure_postgres_connection(parent=parent)" in setup_body, (
        "Ścieżka PG musi delegować do configure_postgres_connection."
    )


def test_show_postgres_install_required_has_switch_to_sqlite_button():
    """Dialog instalacji ma button ``Przełącz na SQLite``."""
    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")

    assert "Przełącz na SQLite" in source
    assert 'command=lambda: (switch_engine("sqlite"), dialog.destroy())' in source


def test_show_postgres_install_required_switch_to_sqlite_writes_db_engine_sqlite(monkeypatch, tmp_path):
    """Klik ``Przełącz na SQLite`` zapisuje ``DB_ENGINE=sqlite`` w ``backend/.env``."""
    from launcher.db import engine as db_engine
    from launcher.ui import database_config_dialogs as dialogs

    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    env_path = fake_backend / ".env"
    env_path.write_text("FLASK_HOST=127.0.0.1\nDB_ENGINE=postgresql\n", encoding="utf-8")

    monkeypatch.setattr(db_engine, "BACKEND_DIR", fake_backend)
    monkeypatch.setattr(db_engine, "_engine", None)
    monkeypatch.delenv("DB_ENGINE", raising=False)
    monkeypatch.setattr(dialogs, "get_ui_scale_setting", lambda: 1)
    monkeypatch.setattr(dialogs, "set_dialog_icon", lambda dialog: None)
    monkeypatch.setattr(dialogs, "_center_window_on_screen", lambda dialog, w, h, parent=None: None)

    created_buttons = []

    class FakeWidget:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def pack(self, *args, **kwargs):
            return None

        def grid(self, *args, **kwargs):
            return None

        def destroy(self):
            return None

    class FakeRoot(FakeWidget):
        def withdraw(self):
            return None

        def winfo_viewable(self):
            return False

    class FakeDialog(FakeWidget):
        def title(self, value):
            return None

        def geometry(self, value):
            return None

        def minsize(self, *args):
            return None

        def resizable(self, *args):
            return None

        def transient(self, parent):
            return None

        def grab_set(self):
            return None

        def focus_force(self):
            return None

        def attributes(self, *args):
            return None

        def protocol(self, *args):
            return None

        def wait_window(self):
            return None

    class FakeButton(FakeWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created_buttons.append(self)

    monkeypatch.setattr(dialogs.tk, "Tk", FakeRoot)
    monkeypatch.setattr(dialogs.tk, "Toplevel", FakeDialog)
    monkeypatch.setattr(dialogs.tk, "Frame", FakeWidget)
    monkeypatch.setattr(dialogs.tk, "Label", FakeWidget)
    monkeypatch.setattr(dialogs.tk, "Button", FakeButton)

    dialogs._show_postgres_install_required(parent=None)

    switch_buttons = [
        button for button in created_buttons
        if button.kwargs.get("text") == "Przełącz na SQLite"
    ]
    assert switch_buttons, "Brak buttona 'Przełącz na SQLite' w dialogu instalacji"

    switch_buttons[0].kwargs["command"]()

    result = env_path.read_text(encoding="utf-8")
    assert "DB_ENGINE=sqlite" in result
    assert "DB_ENGINE=postgresql" not in result


def test_reset_db_engine_to_empty_helper_writes_correctly(monkeypatch, tmp_path):
    """``_reset_db_engine_to_empty`` czyści ``DB_ENGINE`` w ``.env`` do pustego.

    Test dynamiczny (z mockiem ``BACKEND_DIR``) -- sprawdza że helper:
    1. Czyta istniejący ``.env``
    2. Zamienia linię ``DB_ENGINE=postgresql`` na ``DB_ENGINE=``
    3. NIE modyfikuje innych linii
    4. Zapisuje z powrotem
    """
    import sys
    from pathlib import Path

    # Utwórz tymczasowy .env
    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    env_path = fake_backend / ".env"
    env_path.write_text(
        "# Konfiguracja\n"
        "FLASK_HOST=127.0.0.1\n"
        "DB_ENGINE=postgresql\n"
        "DB_PATH=data/czarna.db\n",
        encoding="utf-8",
    )

    # Mock BACKEND_DIR
    monkeypatch.setattr(
        "launcher.config.paths.BACKEND_DIR", fake_backend, raising=False
    )
    # Patch import wewnątrz funkcji (lazy import przez _reset_db_engine_to_empty)
    # Usuwamy cache modułu żeby re-import wziął nasz mock
    sys.modules.pop("launcher.ui.database_config_dialogs", None)

    from launcher.ui.database_config_dialogs import _reset_db_engine_to_empty

    _reset_db_engine_to_empty()

    # Sprawdź zawartość po resecie
    result = env_path.read_text(encoding="utf-8")

    assert "DB_ENGINE=" in result, "Linia DB_ENGINE musi istnieć po resecie"
    assert "DB_ENGINE=postgresql" not in result, (
        "DB_ENGINE=postgresql musi być ZAMIENIONE na DB_ENGINE= (puste)"
    )
    # Sprawdź że pusta linia ma końcówkę
    assert "DB_ENGINE=\n" in result, "DB_ENGINE musi być pustym stringiem (z newline)"

    # Inne linie nie mogą być zmienione
    assert "FLASK_HOST=127.0.0.1" in result, "FLASK_HOST nie może być zmieniony"
    assert "DB_PATH=data/czarna.db" in result, "DB_PATH nie może być zmieniony"



def test_detect_engine_falls_back_to_sqlite_when_db_engine_empty(monkeypatch, tmp_path):
    """``detect_engine()`` zwraca SQLiteEngine (NIE PostgreSQLEngine) gdy
    ``DB_ENGINE`` jest pusty string w backend/.env.

    Context (2026-06-05):
        Po deinstalacji PG, w .env zostało ``DB_ENGINE=`` (pusty). Stary
        kod w ``launcher/db/engine.py:detect_engine()`` traktował pusty
        string jako "brak wartości" i wpadał w domyślny fallback
        ``os.getenv("DB_ENGINE", "postgresql")`` -- co zwracało 'postgresql'
        i powodowało że launcher próbował łączyć się z PG zanim user
        wybrał silnik w first-run dialogu.

    Naprawione: pusty/brak ``DB_ENGINE`` -> ``SQLiteEngine()`` (safe default).
    ``setup_postgres_config`` i tak wywoła ``choose_database_engine`` --
    dialog first-run pokaże się i user może wybrać PG świadomie.

    Ten test pilnuje żeby fallback na 'postgresql' nigdy nie wrócił.
    """
    # 1. Wyczyść cache engine (singleton)
    from launcher.db import engine as db_engine
    monkeypatch.setattr(db_engine, "_engine", None)

    # 2. Wyczyść os.environ (bez DB_ENGINE, bez DB_HOST itd.)
    for key in ("DB_ENGINE", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"):
        monkeypatch.delenv(key, raising=False)

    # 3. Napisz .env z pustym DB_ENGINE= (symulacja first-run po uninstall)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Konfiguracja serwera (FastAPI)\n"
        "FLASK_HOST=127.0.0.1\n"
        "FLASK_PORT=5000\n"
        "\n"
        "# Silnik bazy danych: pusty = first-run mode\n"
        "DB_ENGINE=\n"
        "DB_PATH=data/czarna.db\n",
        encoding="utf-8",
    )

    # 4. Zmonkuj ścieżkę do .env (BACKEND_DIR jest używany przez engine.py)
    from launcher.config import paths as launcher_paths
    monkeypatch.setattr(launcher_paths, "BACKEND_DIR", tmp_path)
    # engine.py importuje BACKEND_DIR przez `from ..config.paths import BACKEND_DIR`
    monkeypatch.setattr(db_engine, "BACKEND_DIR", tmp_path)

    # 5. Wywołaj detect_engine() -- powinien zwrócić SQLiteEngine, NIE PostgreSQLEngine
    detected = db_engine.detect_engine()

    assert detected.name == "sqlite", (
        f"detect_engine() zwrócił {detected.name!r} -- oczekiwano 'sqlite'. "
        "To jest REGRESJA fixu first-run: pusty DB_ENGINE nie może wpadać "
        "w domyślny 'postgresql' bo launcher szukałby PG bez pytania usera."
    )
    assert detected.label == "SQLite", (
        f"Engine label powinien być 'SQLite', jest {detected.label!r}"
    )


def test_choose_database_engine_has_edb_installer_button():
    """Dialog ma button 'Zainstaluj EDB PostgreSQL + PostGIS system-wide'.

    Jedyna wspierana ścieżka dla użytkowników bez PG w systemie. Wcześniej
    była też opcja portable PG, ale portable ma bug z DLL 0xC0000142 na
    wielu Windows. EDB installer system-wide działa na wszystkich Windows
    (wymaga uprawnień administratora).
    """
    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")
    assert "Zainstaluj EDB PostgreSQL" in source or "EDB Installer" in source, (
        "Brak buttonu EDB Installer w dialogu"
    )
    assert "on_install_edb_pg_postgis" in source, (
        "Brak handlera on_install_edb_pg_postgis"
    )
    # Musi wołać graficzny instalator, nie surowy skrypt konsolowy.
    assert "install_pg_gui.py" in source, (
        "Brak odwołania do graficznego instalatora install_pg_gui.py"
    )
    assert "pythonw.exe" in source, (
        "Instalator powinien startować przez pythonw.exe, żeby nie pokazywać konsoli"
    )
    assert "CREATE_NEW_CONSOLE" not in source, (
        "Instalator GUI nie może otwierać nowej konsoli"
    )


def test_database_config_dialogs_has_no_portable_pg_references():
    """Dialog nie zawiera już przestarzałych odwołań do portable PG.

    Po decyzji usunięcia portable flow (bug DLL 0xC0000142 na Windows):
        * Brak buttonu 'Pobierz i zainstaluj portable PG'
        * Brak funkcji install_portable_pg_with_postgis
        * Brak importu pg_portable_service
        * Brak ostrzeżeń o DLL 0xC0000142 (bo nie ma już portable flow)

    Gdyby ktoś w przyszłości dodał portable z powrotem, ten test
    zmusza do świadomej refaktoryzacji (świadomego usunięcia testu).
    """
    source = (PROJECT_ROOT / "launcher/ui/database_config_dialogs.py").read_text(encoding="utf-8")
    assert "install_portable_pg_with_postgis" not in source, (
        "Została przestarzała funkcja install_portable_pg_with_postgis -- "
        "usunięta bo portable PG ma bug DLL na Windows"
    )
    assert "pg_portable_service" not in source, (
        "Został import pg_portable_service -- powinien być usunięty wraz z portable"
    )
    assert "Pobierz i zainstaluj portable" not in source, (
        "Został button portable PG -- usunięty bo nie działa na Windows"
    )
    assert "0xC0000142" not in source, (
        "Zostało ostrzeżenie o DLL 0xC0000142 -- niepotrzebne po usunięciu portable"
    )


def test_backup_manager_uses_services_without_local_location_wrappers():
    tree = _parse_project_file("launcher/ui/backup_manager.py")
    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    source = (PROJECT_ROOT / "launcher/ui/backup_manager.py").read_text(encoding="utf-8")

    assert "get_all_locations" not in function_names
    assert "get_active_location" not in function_names
    assert "get_active_location_name" not in function_names
    assert "create_and_migrate_location_database" not in function_names
    assert "location_service.get_all_locations" in source
    assert "location_service.get_active_location" in source
    assert "location_service.get_active_location_name" in source
    assert "location_migration_service.create_and_migrate_location_database" in source


def test_database_wizard_uses_postgres_adapter_service():
    import launcher.ui.database_wizard as wizard
    from launcher.services import postgres_adapter_service as service

    source = (PROJECT_ROOT / "launcher/ui/database_wizard.py").read_text(encoding="utf-8")

    assert "postgres_adapter_service" in source
    assert "def _normalize_pg_config_args" not in source
    assert "def postgres_database_exists" not in source
    assert "def postgres_create_database" not in source
    assert "def postgres_enable_postgis" not in source
    assert "def postgres_execute_schema" not in source
    assert "def postgres_list_databases" not in source
    assert wizard.test_postgres_connection is service.test_postgres_connection
    assert wizard.postgres_database_exists is service.postgres_database_exists
    assert wizard.postgres_create_database is service.postgres_create_database
    assert wizard.postgres_enable_postgis is service.postgres_enable_postgis
    assert wizard.postgres_execute_schema is service.postgres_execute_schema
    assert wizard.postgres_list_databases is service.postgres_list_databases


def test_database_wizard_delegates_migration_to_service():
    """Wizard korzysta z czystego serwisu migracji — nie wywołuje subprocess bezpośrednio."""
    import launcher.ui.database_wizard as wizard
    from launcher.services import postgres_migration_service as migration_service

    source = (PROJECT_ROOT / "launcher/ui/database_wizard.py").read_text(encoding="utf-8")

    # Nowa domyślna akcja to 'migrate_to_postgresql' — realizowana przez serwis
    assert "migrate_to_postgresql" in source
    assert "run_postgres_migration_wizard" in source
    assert "MigrationOptions" in source
    assert "PostgresConfig" in source

    # Wizard NIE implementuje lokalnie logiki migracji / subprocess / env-update
    assert "subprocess.run" not in source
    assert "update_backend_env_for_postgres" not in source
    assert "update_location_env_for_postgres" not in source
    assert "build_location_db_name" not in source
    assert "count_source_data" not in source
    assert "verify_migration" not in source

    # Publiczne API serwisu jest importowane z modułu (nie z launcher_app)
    assert wizard.run_postgres_migration_wizard is migration_service.run_postgres_migration_wizard
    assert wizard.MigrationOptions is migration_service.MigrationOptions
    assert wizard.PostgresConfig is migration_service.PostgresConfig


def test_database_wizard_hides_destructive_actions_by_default():
    """Wariant A: destrukcyjne opcje są domyślnie zablokowane checkboxem ryzyka."""
    source = (PROJECT_ROOT / "launcher/ui/database_wizard.py").read_text(encoding="utf-8")

    # Checkbox potwierdzenia ryzyka + domyślna wartość False
    assert "risk_ack_var" in source
    assert "Rozumiem ryzyko utraty danych" in source
    assert "_on_risk_ack_toggle" in source
    # Sekcja zaawansowana z destrukcyjnymi radiobuttonami istnieje
    assert "Operacje destrukcyjne (zaawansowane" in source


@pytest.mark.parametrize("forbidden_import", ["psycopg2", "PIL"])
def test_dialogs_has_no_heavy_top_level_imports(forbidden_import):
    top_level_imports = _top_level_import_roots("launcher/ui/dialogs.py")

    assert forbidden_import not in top_level_imports


@pytest.mark.parametrize(
    "module_name",
    ["launcher.ui.backup_manager", "launcher.ui.map_calibrator"],
)
def test_split_ui_modules_no_longer_lazy_load_launcher_app(module_name):
    module = importlib.import_module(module_name)
    source = inspect.getsource(module)

    assert 'import_module("launcher.launcher_app")' not in source
    assert "import_module('launcher.launcher_app')" not in source
    assert "def _launcher(" not in source
    assert "def _get_launcher(" not in source


def test_launcher_utils_no_longer_has_get_launcher_lazy_import():
    tree = _parse_project_file("launcher/utils/__init__.py")

    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_get_launcher" not in function_names


def test_auto_migrate_helpers_import_from_service_without_dialogs():
    sys.modules.pop("launcher.ui.dialogs", None)

    migration_module = importlib.import_module("launcher.services.location_migration_service")

    assert callable(getattr(migration_module, "auto_migrate_data_function"))
    assert callable(getattr(migration_module, "auto_calibrate_map_from_backup"))

    assert "launcher.ui.dialogs" not in sys.modules


def test_startup_initialization_imports_from_service_without_dialogs():
    sys.modules.pop("launcher.ui.dialogs", None)

    startup_module = importlib.import_module("launcher.services.startup_initialization_service")

    assert callable(getattr(startup_module, "auto_initialize_on_startup"))
    assert "launcher.ui.dialogs" not in sys.modules


def test_dialogs_no_longer_defines_auto_initialize_on_startup_locally():
    tree = _parse_project_file("launcher/ui/dialogs.py")

    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "auto_initialize_on_startup" not in function_names


def test_backup_manager_does_not_import_auto_migrate_helpers_from_dialogs():
    source = (PROJECT_ROOT / "launcher/ui/backup_manager.py").read_text(encoding="utf-8")

    assert "from launcher.ui.dialogs import auto_calibrate_map_from_backup, auto_migrate_data_function" not in source
    assert "from launcher.ui.dialogs import auto_migrate_data_function" not in source
    assert "launcher.ui.dialogs" not in source


def test_program_settings_database_wizard_uses_parent_app_api():
    from launcher.ui.program_settings import ProgramSettingsWindow

    source = inspect.getsource(ProgramSettingsWindow)
    assert "self.parent_app.open_database_wizard" in source
    assert "_get_launcher()" not in source
    assert "DatabaseWizard(self)" not in source


def test_launcher_app_delegates_guardian_runtime():
    source = (PROJECT_ROOT / "launcher/launcher_app.py").read_text(encoding="utf-8")

    assert "from launcher.services import guardian_runtime" in source
    assert "guardian_runtime.load_guardian_config" in source
    assert "guardian_runtime.save_guardian_config" in source
    assert "guardian_runtime.run_proactive_health_check" in source
    assert "guardian_runtime.get_guardian_status_snapshot" in source
    assert "for mod in guardian_service.CRITICAL_MODULES" not in source
    assert "guardian_service.health_check_command" not in source


def test_guardian_runtime_keeps_service_boundary_and_generation_guard():
    source = (PROJECT_ROOT / "launcher/services/guardian_runtime.py").read_text(encoding="utf-8")

    assert "launcher.launcher_app" not in source
    assert "launcher.ui.dialogs" not in source
    assert "guardian_service.load_guardian_config" in source
    assert "guardian_service.save_guardian_config" in source
    assert "guardian_service.CRITICAL_MODULES" in source
    assert "guardian_service.health_check_command" in source
    assert "_guardian_check_generation" in source
    assert "def _is_current_check" in source
    assert ".guardian.env" not in source


def test_launcher_app_delegates_firewall_for_port_runtime():
    source = (PROJECT_ROOT / "launcher/launcher_app.py").read_text(encoding="utf-8")

    assert "from launcher.services import firewall_runtime" in source
    assert "def setup_firewall_rule_for_port(self, port: int):" in source
    assert "firewall_runtime.setup_firewall_rule_for_port(port)" in source
    assert "netsh advfirewall firewall show rule" not in source
    assert "netsh advfirewall firewall add rule" not in source


def test_process_manager_delegates_network_firewall_runtime_without_local_netsh():
    source = (PROJECT_ROOT / "launcher/services/process_manager.py").read_text(encoding="utf-8")

    assert "firewall_runtime.setup_firewall_rule" in source
    assert "network_runtime.toggle_network_server" in source
    assert "network_runtime.start_network_server" in source
    assert "netsh advfirewall firewall show rule" not in source
    assert "netsh advfirewall firewall add rule" not in source
    assert "IsUserAnAdmin" not in source
    assert "ShellExecuteW" not in source
    assert '"backend.main:app"' not in source
    assert '"--host", "0.0.0.0"' not in source


def test_network_firewall_runtime_do_not_import_launcher_app_or_dialogs():
    for relative_path in [
        "launcher/services/firewall_runtime.py",
        "launcher/services/network_runtime.py",
    ]:
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        top_level_imports = _top_level_import_roots(relative_path)

        assert "launcher.launcher_app" not in source
        assert "launcher.ui.dialogs" not in source
        assert ".dialogs" not in source
        assert "launcher_app" not in top_level_imports
        assert "dialogs" not in top_level_imports
        assert "import_module(\"launcher.launcher_app\")" not in source
        assert "import_module('launcher.launcher_app')" not in source
        assert "def _get_launcher" not in source
        assert "def _launcher" not in source


def test_firewall_runtime_preserves_windows_firewall_contract():
    source = (PROJECT_ROOT / "launcher/services/firewall_runtime.py").read_text(encoding="utf-8")

    assert 'platform.system() != "Windows"' in source
    assert 'rule_name = f"Flask Server Port {port}"' in source
    assert 'netsh advfirewall firewall show rule name="{rule_name}"' in source
    assert 'netsh advfirewall firewall add rule name="{rule_name}"' in source
    assert "subprocess.run(check_cmd, shell=True, capture_output=True, text=True)" in source
    assert "ctypes.windll.shell32.IsUserAnAdmin()" in source
    assert "messagebox.askyesno" in source
    assert "ShellExecuteW" in source
    assert "sys.exit(0)" in source
    assert "def setup_firewall_rule_for_port" in source


def test_network_runtime_preserves_network_server_command_and_metadata():
    source = (PROJECT_ROOT / "launcher/services/network_runtime.py").read_text(encoding="utf-8")

    assert "get_local_ip()" in source
    assert "get_flask_config()" in source
    assert '"backend.main:app"' in source
    assert '"--host", "0.0.0.0"' in source
    assert '"--port", str(port)' in source
    assert '"network_mode": True' in source
    assert '"local_ip": local_ip' in source
    assert "start_managed_process" in source
    assert "show_network_info_dialog" in source


def test_launcher_app_delegates_env_quick_links_runtime():
    source = (PROJECT_ROOT / "launcher/launcher_app.py").read_text(encoding="utf-8")

    assert "from launcher.ui import console_runtime, db_engine_switcher, env_runtime, shutdown_runtime, window_runtime" in source
    assert "env_runtime.load_flask_config" in source
    assert "env_runtime.refresh_quick_links" in source
    assert "env_runtime.get_env_mtime" in source
    assert "env_runtime.start_env_watcher" in source
    assert "env_runtime.on_env_changed" in source
    assert "env_runtime.open_env_editor" in source
    # Martwa delegacja get_urls w launcher_app zostala usunieta - URLS
    # pochodzi wylacznie z launcher.config.settings (jedyne zrodlo prawdy).
    assert "def get_urls(" not in source
    assert "launcher_url_service.get_launcher_urls" not in source
    assert "launcher_url_service.load_flask_config" not in source
    assert "env_watcher_service.get_env_mtime" not in source
    assert "env_watcher_service.should_handle_env_change" not in source
    assert "env_watcher_service.env_port_changed" not in source
    assert "webbrowser.open_new_tab" not in source


def test_env_runtime_keeps_ui_boundary_and_uses_services():
    relative_path = "launcher/ui/env_runtime.py"
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    tree = _parse_project_file(relative_path)
    top_level_imports = _top_level_import_roots(relative_path)

    class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert class_names == set()
    assert "launcher.launcher_app" not in source
    assert "launcher.ui.dialogs" not in source
    assert ".dialogs" not in source
    assert "launcher_app" not in top_level_imports
    assert "dialogs" not in top_level_imports
    assert "import_module(\"launcher.launcher_app\")" not in source
    assert "import_module('launcher.launcher_app')" not in source
    assert "def _get_launcher" not in source
    assert "def _launcher" not in source
    assert "launcher_url_service.get_launcher_urls" in source
    assert "launcher_url_service.load_flask_config" in source
    assert "env_watcher_service.get_env_mtime" in source
    assert "env_watcher_service.should_handle_env_change" in source
    assert "env_watcher_service.env_port_changed" in source


@pytest.mark.parametrize(
    "relative_path",
    [
        "launcher/services/launcher_url_service.py",
        "launcher/services/env_watcher_service.py",
    ],
)
def test_env_url_services_stay_gui_free(relative_path):
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    top_level_imports = _top_level_import_roots(relative_path)

    assert "tkinter" not in top_level_imports
    assert "webbrowser" not in top_level_imports
    assert "messagebox" not in source
    assert "launcher.launcher_app" not in source
    assert "launcher.ui.dialogs" not in source
    assert ".dialogs" not in source
    assert "def _get_launcher" not in source
    assert "def _launcher" not in source


def test_env_runtime_refresh_quick_links_configures_buttons(monkeypatch):
    from launcher.ui import env_runtime

    opened = []

    class FakeButton:
        def __init__(self):
            self.configured = {}

        def configure(self, **kwargs):
            self.configured.update(kwargs)

    class FakeApp:
        def load_flask_config(self):
            return {"host": "127.0.0.1", "port": "5000", "db_engine": "sqlite"}

    app = FakeApp()
    btn = FakeButton()
    app.quick_link_buttons = [(btn, "mapa")]

    monkeypatch.setattr(env_runtime.webbrowser, "open_new_tab", lambda url: opened.append(url))

    env_runtime.refresh_quick_links(
        app,
        get_urls_func=lambda: {"mapa": "http://127.0.0.1:5000/mapa/mapa.html?v=1"},
    )

    assert app.current_flask_config == {"host": "127.0.0.1", "port": "5000", "db_engine": "sqlite"}
    assert callable(btn.configured["command"])

    btn.configured["command"]()
    assert opened == ["http://127.0.0.1:5000/mapa/mapa.html?v=1"]


# ─── Test Center split ──────────────────────────────────────────────────────


def test_launcher_app_delegates_test_center_runtime():
    source = (PROJECT_ROOT / "launcher/launcher_app.py").read_text(encoding="utf-8")

    assert "from launcher.services import test_runtime" in source
    assert "test_runtime.open_test_center_window" in source
    assert "test_runtime.copy_test_logs_to_clipboard" in source
    assert "test_runtime.save_test_logs_to_file" in source
    assert "test_runtime.run_selected_tests" in source
    assert "test_runtime.log_to_test_console" in source
    assert "test_runtime.run_pytest" in source
    assert "test_runtime.run_playwright_tests" in source
    # Brak lokalnej implementacji CIELOWEJ - lokalnie ma tylko jednolinijkowe wrappery
    assert "parse_pytest_line" not in source
    assert "log_to_test_console(app, message, tag=" not in source
    assert "def _setup_console_tags" not in source
    # Brak ciężkich importow
    assert "from tkinter import filedialog" not in source
    assert "CONSOLE_TAGS = {" not in source


def test_test_center_runtime_keeps_ui_boundary_and_uses_service():
    relative_path = "launcher/ui/test_center_runtime.py"
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    tree = _parse_project_file(relative_path)
    top_level_imports = _top_level_import_roots(relative_path)

    class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert class_names == set()
    assert "launcher.launcher_app" not in source
    assert "launcher.ui.dialogs" not in source
    assert ".dialogs" not in source
    assert "launcher_app" not in top_level_imports
    assert "dialogs" not in top_level_imports
    assert "def _get_launcher" not in source
    assert "def _launcher" not in source
    assert "test_service.DEFAULT_TEST_VARS" in source
    assert "test_service.build_test_command" in source
    assert "test_service.parse_pytest_line" in source
    assert "test_service.accumulate_section_stats" in source
    assert "test_service.format_section_summary" in source


def test_test_service_stays_gui_free():
    relative_path = "launcher/services/test_service.py"
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    top_level_imports = _top_level_import_roots(relative_path)

    assert "tkinter" not in top_level_imports
    assert "messagebox" not in top_level_imports
    assert "webbrowser" not in top_level_imports
    assert "filedialog" not in top_level_imports
    assert "launcher.launcher_app" not in source
    assert "launcher.ui.dialogs" not in source
    assert ".dialogs" not in source
    assert "launcher_app" not in top_level_imports
    assert "dialogs" not in top_level_imports


def test_test_runtime_is_thin_compatibility_wrapper():
    source = (PROJECT_ROOT / "launcher/services/test_runtime.py").read_text(encoding="utf-8")
    tree = _parse_project_file("launcher/services/test_runtime.py")

    class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert class_names == set()

    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert function_names == set()

    assert "from launcher.ui.test_center_runtime import" in source
    assert "from launcher.services.test_service import" in source


def test_test_service_parse_pytest_line_pure_logic():
    from launcher.services.test_service import (
        TEST_PATH_MAP,
        extract_percentage,
    )

    from launcher.services import test_service

    emoji, tag, formatted = test_service.parse_pytest_line(
        "tests/unit/test_foo.py::test_bar PASSED   [ 50%]"
    )
    assert emoji == "✅"
    assert tag == "test_passed_line"
    assert "test_foo.py::test_bar" in formatted

    # verbose-match z .py:: wymaga, zeby linia miala '.py::'
    emoji, tag, formatted = test_service.parse_pytest_line(
        "tests/x.py::test_x SKIPPED [ 10%]"
    )
    assert emoji == "⏭️"
    assert "test_x" in formatted

    emoji, tag, formatted = test_service.parse_pytest_line("5 passed in 0.12s")
    assert emoji == "📊"
    assert "5 passed" in formatted

    # Summary FAILED ma byc widoczny, ale bez podwojnego zliczania failure.
    emoji, tag, formatted = test_service.parse_pytest_line("FAILED tests/x.py::test_x")
    assert emoji is None
    assert tag == "test_failed_line"
    assert "test_x" in formatted

    emoji, tag, formatted = test_service.parse_pytest_line("test session starts")
    assert formatted is None

    assert extract_percentage("foo [ 42%]") == "[42%]"
    assert "passed" in test_service.format_summary_line("5 passed in 0.12s")

    assert set(TEST_PATH_MAP.keys()) >= {
        "unit", "integration", "e2e", "logic", "duplicates", "spatial", "resources",
        "gaps", "backups", "encoding", "wcag", "perf", "security",
    }

    assert test_service.DEFAULT_TEST_VARS["integration"] is True

    # Budowanie komendy dla znanego klucza
    cmd = test_service.build_test_command("unit", str(test_service.BASE_DIR))
    assert cmd[0].endswith("python") or cmd[0].endswith("python.exe")
    assert "pytest" in cmd
    integration_cmd = test_service.build_test_command("integration", str(test_service.BASE_DIR))
    assert "backend/tests/integration" in integration_cmd
    # Nieznany klucz → pusta lista
    assert test_service.build_test_command("nieznany_klucz", str(test_service.BASE_DIR)) == []
    # SQL → skrypt
    sql_cmd = test_service.build_test_command("sql", str(test_service.BASE_DIR))
    assert "test_data_integrity.py" in sql_cmd[-1]

    # Akumulacja statystyk
    stats = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    test_service.accumulate_section_stats(stats, "✅")
    test_service.accumulate_section_stats(stats, "❌")
    test_service.accumulate_section_stats(stats, "⏭️")
    test_service.accumulate_section_stats(stats, "🔴")
    test_service.accumulate_section_stats(stats, None)
    assert stats == {"passed": 1, "failed": 1, "skipped": 1, "errors": 1}

    # Format sekcji
    s = test_service.format_section_summary({"passed": 3, "failed": 1})
    assert "3 passed" in s and "1 failed" in s
    assert test_service.format_section_summary({}) == ""


# ─── Shutdown runtime split ──────────────────────────────────────────────────


def test_launcher_app_delegates_shutdown_runtime():
    source = (PROJECT_ROOT / "launcher/launcher_app.py").read_text(encoding="utf-8")

    assert "from launcher.ui import console_runtime, db_engine_switcher, env_runtime, shutdown_runtime, window_runtime" in source
    assert "shutdown_runtime.request_graceful_close" in source
    assert "shutdown_runtime.force_close_application" in source
    assert "shutdown_runtime.handle_destroy_event" in source
    assert "shutdown_runtime.close_console_window" in source
    assert "shutdown_runtime.cleanup_temp_files" in source
    assert "shutdown_runtime.shutdown_after_mainloop" in source
    # Lokalne metody to tylko jednolinijkowe wrappery (nie pelne implementacje)
    # Brak w nich niskopoziomowych wywolan
    assert "ctypes.windll.kernel32.GetConsoleWindow" not in source
    assert "ctypes.windll.user32.PostMessageW" not in source
    assert "WM_CLOSE = 0x0010" not in source
    # Brak askyesno dla shutdown (sprawdzanie) — to jest w shutdown_runtime
    assert 'askyesno(\n                "\ud83d\udd12' not in source
    # Brak ciala loga zamykajacego
    assert "Zamykanie aplikacji - zatrzymywanie proces" not in source


def test_shutdown_runtime_keeps_ui_boundary_and_uses_services():
    relative_path = "launcher/ui/shutdown_runtime.py"
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    tree = _parse_project_file(relative_path)
    top_level_imports = _top_level_import_roots(relative_path)

    class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert class_names == set()
    assert "launcher.launcher_app" not in source
    assert "launcher.ui.dialogs" not in source
    assert ".dialogs" not in source
    assert "launcher_app" not in top_level_imports
    assert "dialogs" not in top_level_imports
    assert "import_module(\"launcher.launcher_app\")" not in source
    assert "import_module('launcher.launcher_app')" not in source
    assert "def _get_launcher" not in source
    assert "def _launcher" not in source
    assert "from launcher.services.process_manager" not in source


def test_shutdown_runtime_pure_functions(tmp_path):
    from launcher.ui import shutdown_runtime

    wrapper = tmp_path / "_network_server_wrapper.py"
    wrapper.write_text("# wrapper")

    shutdown_runtime.cleanup_temp_files(str(tmp_path))
    assert not wrapper.exists()

    shutdown_runtime.cleanup_temp_files(str(tmp_path))

    assert shutdown_runtime.is_exiting(_FakeApp(exiting=False)) is False
    shutdown_runtime.mark_exiting(_FakeApp(exiting=False))


def _FakeApp(exiting=False):
    class _Stub:
        pass
    app = _Stub()
    app._exiting = exiting
    return app


def test_shutdown_runtime_is_idempotent_for_exiting():
    from launcher.ui import shutdown_runtime

    class _App:
        _exiting = True
        called = False

        def stop_managed_process(self, key, force=False):
            self.called = True

        def quit(self): pass
        def destroy(self): pass
    app = _App()
    # handle_destroy_event ma wczesny return jesli is_exiting
    shutdown_runtime.handle_destroy_event(app, event=None)
    assert app.called is False
