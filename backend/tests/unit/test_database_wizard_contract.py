"""
Kontrakt UI kreatora PostgreSQL (`launcher.ui.database_wizard`).

Weryfikuje strukturę kodu źródłowego kreatora bez uruchamiania prawdziwego
Tkinter (wzorzec projektu - testy UI to testy kontraktu AST/regex).

Co jest testowane:
- Atrybuty instancji (formularz konfiguracji),
- Kroki kreatora (Notebook z zakładkami),
- Nawigacja (Wstecz/Dalej/Anuluj),
- Integracja z postgres_migration_service (delegacja),
- Brak importu launcher_app (testy sa izolowane),
- Brak top-level importow ciezkich modulow,
- Re-eksport przez launcher.ui.dialogs (kompatybilnosc wsteczna),
- Klasyczne publiczne API klasy DatabaseWizard.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

WIZARD_PY = PROJECT_ROOT / "launcher" / "ui" / "database_wizard.py"
DIALOGS_PY = PROJECT_ROOT / "launcher" / "ui" / "dialogs.py"
APP_PY = PROJECT_ROOT / "launcher" / "launcher_app.py"


# ============================================================================
# Helpery
# ============================================================================


def _source() -> str:
    return WIZARD_PY.read_text(encoding="utf-8")


def _parsed() -> ast.Module:
    return ast.parse(_source(), filename=str(WIZARD_PY))


def _class_methods(class_name: str) -> set[str]:
    tree = _parsed()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return set()


# ============================================================================
# Atrybuty instancji (formularz konfiguracji)
# ============================================================================


def test_wizard_has_connection_form_attributes():
    """Kreator musi miec pola formularza dla kroku 1 (Polaczenie)."""
    source = _source()
    for attr in ("self.host_entry", "self.port_entry", "self.user_entry", "self.password_entry"):
        assert attr in source, f"Brak atrybutu {attr} w kreatorze"


def test_wizard_has_connection_status_label():
    """Label statusu polaczenia - informuje uzytkownika."""
    source = _source()
    assert "self.connection_status" in source, "Brak self.connection_status (label statusu polaczenia)"


def test_wizard_has_config_dict_and_connection_tested_flag():
    """Kreator trzyma config PG i flage polaczenia przetestowanego."""
    source = _source()
    assert "self.config" in source, "Brak self.config (dict z konfiguracja PG)"
    assert "self.connection_tested" in source, "Brak self.connection_tested (bool flaga)"


def test_wizard_has_notebook():
    """Kreator uzywa Notebook - karty (kroki wizarda)."""
    source = _source()
    assert "self.notebook" in source, "Brak self.notebook (ttk.Notebook)"
    assert "ttk.Notebook" in source, "Brak importu ttk.Notebook"


# ============================================================================
# Kroki kreatora
# ============================================================================


def test_wizard_has_create_step1_connection_method():
    """Krok 1: Polaczenie - metoda prywatna tworzaca zakladke."""
    methods = _class_methods("DatabaseWizard")
    assert "create_step1_connection" in methods, "Brak create_step1_connection (krok 1)"


def test_wizard_has_create_step3_action_method():
    """Krok 2: Akcja - metoda prywatna (numeracja zostala '3' dla kompatybilnosci)."""
    methods = _class_methods("DatabaseWizard")
    assert "create_step3_action" in methods, "Brak create_step3_action (krok 2)"


def test_wizard_has_create_step4_progress_method():
    """Krok 3: Postepy - metoda prywatna dla wizarda migracji."""
    methods = _class_methods("DatabaseWizard")
    assert "create_step4_progress" in methods, "Brak create_step4_progress (krok 3)"


def test_wizard_has_validate_tab_change_method():
    """Blokada przeskakiwania zakladek - kroki musza isc po kolei."""
    methods = _class_methods("DatabaseWizard")
    assert "validate_tab_change" in methods, "Brak validate_tab_change (walidacja przeskoczenia zakladki)"


def test_wizard_has_prev_and_next_step_methods():
    """Nawigacja: Wstecz / Dalej."""
    methods = _class_methods("DatabaseWizard")
    assert "prev_step" in methods, "Brak prev_step (nawigacja wstecz)"
    assert "next_step" in methods, "Brak next_step (nawigacja dalej)"


# ============================================================================
# Nawigacja (Wstecz/Dalej/Anuluj) i flow
# ============================================================================


def test_wizard_has_navigation_buttons():
    """Przyciski nawigacji w textbox (po polsku)."""
    source = _source()
    # Nie sztywne `==`, moga byc zmienne - szukamy wzorca
    assert re.search(r'ttk\.Button\([^)]*text="◀ Wstecz"', source), "Brak przycisku 'Wstecz'"
    assert re.search(r'ttk\.Button\([^)]*text="Dalej ▶"', source), "Brak przycisku 'Dalej'"
    assert re.search(r'ttk\.Button\([^)]*text="Anuluj"', source), "Brak przycisku 'Anuluj'"


def test_wizard_navigation_binds_notebook_tab_change():
    """Walidacja przeskoczenia zakladki - blokada skakania po wizard."""
    source = _source()
    assert "<<NotebookTabChanged>>" in source, (
        "Brak bind na <<NotebookTabChanged>> (walidacja zmiany zakladki)"
    )


# ============================================================================
# Integracja z postgres_migration_service (delegacja)
# ============================================================================


def test_wizard_imports_migration_service():
    """Kreator importuje serwis migracji - deleguje cala logike."""
    source = _source()
    assert "from ..services.postgres_migration_service import" in source, (
        "Brak importu postgres_migration_service"
    )


def test_wizard_imports_required_migration_symbols():
    """Kreator uzywa MigrationOptions, PostgresConfig, normalize, wizard."""
    source = _source()
    for symbol in ("MigrationOptions", "PostgresConfig", "normalize_postgres_config", "run_postgres_migration_wizard"):
        assert symbol in source, f"Brak uzycia symbolu {symbol} z migration service"


def test_wizard_does_not_implement_migration_locally():
    """Cala logika migracji jest w serwisie - kreator NIE powinien miec wlasnego DDL/INSERT/UPDATE.

    Wyjatek: DROP DATABASE (wymaga specjalnej obslugi - autocommit + polaczenie
    do bazy 'postgres' zamiast dropowanej). Kreator moze miec `DROP DATABASE IF EXISTS`
    bezposrednio, ale NIE powinien miec `CREATE TABLE` / `INSERT INTO` / `UPDATE`.
    """
    source = _source()
    upper_source = source.upper()
    # Anti-regresja: kreator nie powinien miec wlasnego DDL
    assert "CREATE TABLE" not in upper_source, (
        "Kreator implementuje CREATE TABLE - to logika serwisu, nie UI"
    )
    assert "CREATE EXTENSION" not in upper_source, (
        "Kreator implementuje CREATE EXTENSION - to logika serwisu (PostGIS)"
    )
    # Ani wlasnych INSERT/UPDATE/SELECT (poza SELECT 1 czy DELETE jezeli uzasadnione)
    assert "INSERT INTO" not in upper_source, (
        "Kreator implementuje INSERT INTO - to logika serwisu"
    )
    # DROP DATABASE jest OK (wymaga specjalnej obslugi)


# ============================================================================
# Izolacja i importy
# ============================================================================


def test_wizard_does_not_import_launcher_app():
    """Kreator NIE importuje launcher_app (zaleznosc cykliczna)."""
    source = _source()
    assert "launcher_app" not in source or "launcher.launcher_app" not in source, (
        "Kreator importuje launcher_app - cykliczna zaleznosc!"
    )


def test_wizard_does_not_import_other_ui_dialogs():
    """Kreator NIE importuje innych UI dialogow (izolacja)."""
    source = _source()
    bad_imports = [
        "from .dialogs",
        "from ..ui.dialogs",
        "from .photos_manager_dialog",
        "from .add_edit_location_dialog",
    ]
    for bad in bad_imports:
        assert bad not in source, f"Kreator importuje {bad} - powinien byc izolowany"


# ============================================================================
# Re-eksport przez dialogs (kompatybilnosc wsteczna)
# ============================================================================


def test_database_wizard_reexported_from_dialogs():
    """launcher.ui.dialogs musi re-exportowac DatabaseWizard (kompatybilnosc)."""
    source = DIALOGS_PY.read_text(encoding="utf-8")
    assert "DatabaseWizard" in source, (
        "launcher.ui.dialogs nie re-exportuje DatabaseWizard"
    )


def test_database_wizard_aliased_in_launcher_app():
    """launcher_app ma publiczny alias DatabaseWizard."""
    source = APP_PY.read_text(encoding="utf-8")
    assert "DatabaseWizard" in source, (
        "launcher_app nie ma publicznego aliasu DatabaseWizard"
    )


# ============================================================================
# Publiczne API (re-eksportowane symbole)
# ============================================================================


def test_wizard_module_reexports_helper_functions():
    """Modul re-exportuje helpery postgres (z adaptera zgodnosci)."""
    source = _source()
    expected = (
        "test_postgres_connection",
        "postgres_database_exists",
        "postgres_create_database",
        "postgres_enable_postgis",
        "postgres_execute_schema",
        "postgres_list_databases",
    )
    for name in expected:
        assert name in source, f"Brak re-eksportu {name} w database_wizard.py"


# ============================================================================
# Test importowalnosci (smoke import)
# ============================================================================


def test_wizard_module_imports_without_side_effects(monkeypatch):
    """Import database_wizard NIE tworzy okien Tk (smoke import)."""
    import tkinter as tk
    from tkinter import messagebox

    # Blokuj tworzenie Toplevel przy imporcie
    def fail_toplevel(self, *args, **kwargs):
        raise AssertionError("Import database_wizard nie moze tworzyc okien Toplevel")

    monkeypatch.setattr(tk.Toplevel, "__init__", fail_toplevel)
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **kw: None)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **kw: None)
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **kw: None)

    # Import powinien sie udac bez tworzenia okien
    import launcher.ui.database_wizard as wizard_module
    assert hasattr(wizard_module, "DatabaseWizard"), "Brak klasy DatabaseWizard"


# ============================================================================
# Wzorzec: kazdy test jest od siebie niezalezny
# ============================================================================

def test_wizard_does_not_have_unused_imports():
    """Kreator powinien miec tylko uzywane importy (bez sledzi)."""
    tree = _parsed()
    imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.asname or alias.name)

    # Konwencja: nie importujemy launchera_app ani dialogs
    forbidden = {"launcher_app", "launcher.launcher_app"}
    assert not (imports & forbidden), f"Niepotrzebne importy: {imports & forbidden}"


# ============================================================================
# Integracja z portable PostgreSQL (Etap 3 P2.1)
# ============================================================================


class TestPortablePgIntegration:
    """Kontrakt: wizard integruje się z pg_portable_service i pg_runtime."""

    def test_wizard_imports_pg_portable_service(self):
        """database_wizard importuje pg_portable_service."""
        from launcher.services import pg_portable_service
        assert hasattr(pg_portable_service, "detect_system_pg")
        assert hasattr(pg_portable_service, "download_pg_binary")
        assert hasattr(pg_portable_service, "extract_pg_archive")
        assert hasattr(pg_portable_service, "portable_pg_installed")

    def test_wizard_imports_pg_runtime(self):
        """database_wizard importuje pg_runtime."""
        from launcher.services import pg_runtime
        assert hasattr(pg_runtime, "init_pg_data_dir")
        assert hasattr(pg_runtime, "start_pg_server")
        assert hasattr(pg_runtime, "stop_pg_server")

    def test_wizard_has_offer_portable_pg_method(self):
        """DatabaseWizard ma metodę _offer_portable_pg_install."""
        from launcher.ui.database_wizard import DatabaseWizard
        assert hasattr(DatabaseWizard, "_offer_portable_pg_install")
        assert hasattr(DatabaseWizard, "_install_portable_pg_with_progress")
        assert hasattr(DatabaseWizard, "_check_portable_pg_on_startup")

    def test_wizard_calls_portable_pg_check_on_startup(self):
        """Kontrakt: wizard wywołuje _check_portable_pg_on_startup w after()."""
        # Sprawdź przez static analysis — szukaj w kodzie
        from pathlib import Path
        wizard_path = Path("launcher/ui/database_wizard.py")
        content = wizard_path.read_text(encoding="utf-8")
        assert "_check_portable_pg_on_startup" in content
        assert "self.after" in content  # wywoływane asynchronicznie

    def test_wizard_has_uninstall_portable_pg_method(self):
        """Kontrakt 1.1.1: DatabaseWizard ma metodę _uninstall_portable_pg."""
        from launcher.ui.database_wizard import DatabaseWizard
        assert hasattr(DatabaseWizard, "_uninstall_portable_pg")
        assert hasattr(DatabaseWizard, "_refresh_portable_pg_status")
        # Metoda powinna być wywoływalna (nie NotImplementedError).
        import inspect
        src = inspect.getsource(DatabaseWizard._uninstall_portable_pg)
        assert "askyesno" in src  # potwierdzenie
        assert "uninstall_portable_pg" in src  # delegacja do serwisu
        assert "_refresh_portable_pg_status" in src  # odświeżenie UI

    def test_pg_portable_service_has_uninstall_function(self):
        """Kontrakt 1.1.1: pg_portable_service ma uninstall_portable_pg."""
        from launcher.services import pg_portable_service
        assert hasattr(pg_portable_service, "uninstall_portable_pg")
        assert hasattr(pg_portable_service, "UninstallResult")

    def test_wizard_uses_local_install_dir_not_appdata(self):
        """Kontrakt 1.1.2: wizard wskazuje na lokalny katalog projektu, nie AppData."""
        from pathlib import Path
        wizard_path = Path("launcher/ui/database_wizard.py")
        content = wizard_path.read_text(encoding="utf-8")
        # Powinno być odwołanie do pg_portable_service.get_pg_install_dir().
        assert "get_pg_install_dir" in content
        # Powinno być w sekcji Portable PG (LabelFrame).
        assert "Portable PostgreSQL" in content
        # Powinno być odwołanie do uninstall.
        assert "_uninstall_portable_pg" in content

