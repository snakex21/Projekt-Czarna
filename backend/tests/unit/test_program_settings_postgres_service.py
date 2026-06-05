from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROGRAM_SETTINGS = PROJECT_ROOT / "launcher" / "ui" / "program_settings.py"
UNINSTALL_SCRIPT = PROJECT_ROOT / "scripts" / "uninstall_pg_system.py"


def test_program_settings_has_postgres_service_card_and_buttons():
    """Panel ustawień ma sekcję serwisową PostgreSQL do testowania flow."""
    source = PROGRAM_SETTINGS.read_text(encoding="utf-8")

    assert "PostgreSQL — serwis i testy" in source
    assert "Przełącz na SQLite i wyczyść konfigurację PG" in source
    assert "Odinstaluj PostgreSQL 16 z systemu" in source
    assert "reset_postgres_launcher_config" in source
    assert "uninstall_postgres_system" in source
    assert "pg_service_status_var" in source


def test_reset_postgres_launcher_config_switches_to_sqlite_and_removes_postgres_env():
    """Bezpieczny reset nie usuwa systemowego PG, tylko czyści konfigurację launchera."""
    source = PROGRAM_SETTINGS.read_text(encoding="utf-8")

    assert "def reset_postgres_launcher_config" in source
    assert 'switch_engine("sqlite")' in source
    assert "POSTGRES_CONFIG_FILE.unlink" in source
    assert 'os.environ["DB_ENGINE"] = "sqlite"' in source
    assert "Nie odinstaluje PostgreSQL" in source or "NIE odinstaluje PostgreSQL" in source


def test_uninstall_postgres_system_uses_pythonw_script_and_double_confirmation():
    """Pełna deinstalacja ma iść przez osobny GUI script z podwójnym potwierdzeniem."""
    source = PROGRAM_SETTINGS.read_text(encoding="utf-8")

    assert "def uninstall_postgres_system" in source
    assert "uninstall_pg_system.py" in source
    assert "pythonw.exe" in source
    assert source.count("messagebox.askyesno") >= 2
    assert "subprocess.Popen" in source
    assert "Deinstalator uruchomiony" not in source
    assert "parent_app.destroy" in source
    assert "grab_release" in source


def test_program_settings_disables_uninstall_when_postgres_not_installed_and_hides_pg_config_in_sqlite():
    """W trybie SQLite panel nie może sugerować, że PostgreSQL jest zainstalowany.

    Regresja UX (2026-06-05):
        User zapytał: "ma to sens pokazywać postgresa jak jestem na sqlite?"
        W trybie SQLite CAŁA sekcja PG (konfiguracja + operacje + pgAdmin)
        musi być ukryta — pokazywanie pustych formularzy PG mija się z celem
        i wprowadza w błąd.
    """
    source = PROGRAM_SETTINGS.read_text(encoding="utf-8")

    assert "def _is_postgres_system_installed" in source
    assert "PG_SYSTEM_INSTALL_DIR" in source
    assert "postgresql-x64-16" in source
    assert "btn_uninstall_pg_system.configure(state=tk.NORMAL if pg_system_installed else tk.DISABLED)" in source
    assert "Nie wykryto systemowego PostgreSQL 16" in source
    assert "self.pg_config_frame.pack_forget()" in source
    assert "self.pg_actions_frame.pack_forget()" in source
    assert "self.pgadmin_frame.pack_forget()" in source
    assert "self.pg_service_frame.pack_forget()" in source
    assert "self.pg_db_list_label" in source


def test_program_settings_hides_all_pg_frames_in_sqlite_mode():
    """W trybie SQLite CAŁA sekcja PG ma być ukryta (regresja UX).

    Sekcja serwisowa (deinstalacja) — wyjątek: pokazywana TYLKO gdy systemowe
    PG jest zainstalowane (bo wtedy ma sens opcja deinstalacji). Bez systemowego
    PG — ukryta, bo nic do deinstalacji.
    """
    source = PROGRAM_SETTINGS.read_text(encoding="utf-8")

    # Wycinamy CAŁĄ gałąź SQLite (do konkretnej linii końcowej tej gałęzi)
    sqlite_start = source.find('if data.get("mode") == "sqlite":')
    sqlite_end_marker = 'self.pg_db_list_var.set("Tryb SQLite'
    sqlite_end = source.find(sqlite_end_marker, sqlite_start)
    sqlite_branch = source[sqlite_start:sqlite_end]

    # Konfiguracja / operacje / pgAdmin ZAWSZE ukryte w trybie SQLite
    assert "self.pg_config_frame.pack_forget()" in sqlite_branch
    assert "self.pg_actions_frame.pack_forget()" in sqlite_branch
    assert "self.pgadmin_frame.pack_forget()" in sqlite_branch
    # Sekcja serwisowa warunkowo: pack_forget() gdy brak systemowego PG
    assert "_is_postgres_system_installed()" in sqlite_branch
    assert "self.pg_service_frame.pack_forget()" in sqlite_branch


def test_uninstall_pg_system_script_resets_launcher_to_sqlite_and_uses_uac():
    """Skrypt deinstalacji wymaga UAC i po operacji przełącza launcher na SQLite."""
    source = UNINSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "ShellExecuteW" in source
    assert '"runas"' in source
    assert "postgresql-x64-16" in source
    assert "uninstall-postgresql" in source
    assert "DB_ENGINE=sqlite" in source
    assert "pg_uninstall.log" in source


def test_uninstall_pg_system_window_is_centered():
    """Okno deinstalatora PostgreSQL ma być wyśrodkowane."""
    source = UNINSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "def _center_window" in source
    assert "winfo_screenwidth" in source
    assert "winfo_screenheight" in source
    assert "+{x}+{y}" in source
    assert "_center_window(root)" in source


def test_uninstall_pg_system_subprocesses_do_not_flash_console_windows():
    """Deinstalator GUI nie może migać oknami konsoli/sc.exe."""
    source = UNINSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "def _no_window_flags" in source
    assert "CREATE_NO_WINDOW" in source
    assert "creationflags=_no_window_flags()" in source


def test_uninstall_pg_system_cleans_up_pg_install_dirs():
    """Deinstalator MUSI usuwać katalog ``C:\\Program Files\\PostgreSQL\\16``
    i wszystkie ``16_old_*`` zostawione przez poprzednie deinstalacje.

    Context (2026-06-05):
        Poprzednie wersje zostawiały ``16_old_<timestamp>`` jako "backup",
        co prowadziło do śmietnika (4× ~1-2 GB po kilku cyklach reinstall).
        User klikając "Odinstaluj" daje explicit consent na usunięcie
        WSZYSTKIEGO związanego z PG. Funkcja ``_cleanup_pg_dirs`` wywoływana
        po sukcesie uninstallera czyści oba typy katalogów.
    """
    source = UNINSTALL_SCRIPT.read_text(encoding="utf-8")

    # Helper MUSI istnieć i używać shutil.rmtree
    assert "def _cleanup_pg_dirs" in source, (
        "Brak _cleanup_pg_dirs() -- katalog PG + _old_* zostaną jako śmietnik"
    )
    assert "shutil.rmtree" in source, (
        "_cleanup_pg_dirs musi używać shutil.rmtree do usuwania katalogów"
    )
    assert "16_old_*" in source, (
        "_cleanup_pg_dirs musi szukać katalogów 16_old_* (wzorzec z prepare_stale_pg_install_dir)"
    )
    assert "PG_INSTALL_DIR" in source, (
        "_cleanup_pg_dirs musi usuwać też bieżący katalog instalacji (EDB zostawia resztki)"
    )

    # Wyciągnij ciało _cleanup_pg_dirs i sprawdź że zwraca (removed, bytes_freed)
    import re

    func_match = re.search(
        r"def _cleanup_pg_dirs\([^)]*\)[^\n]*:",
        source,
    )
    assert func_match, "Nie udało się znaleźć sygnatury _cleanup_pg_dirs"
    func_start = func_match.end()
    # Koniec = następny \n\ndef na col 0
    end_match = re.search(r"\n\ndef [a-zA-Z_]", source[func_start:])
    assert end_match, "Nie udało się znaleźć końca _cleanup_pg_dirs"
    body = source[func_start : func_start + end_match.start()]
    assert "return removed, bytes_freed" in body, (
        "_cleanup_pg_dirs musi zwracać (removed, bytes_freed) żeby uninstall() "
        "mógł pokazać ile zwolniono w komunikacie."
    )

    # uninstall() MUSI wywołać _cleanup_pg_dirs po sukcesie
    uninstall_match = re.search(
        r"def uninstall\(\)[^\n]*:(.*?)(?=\n\ndef [a-zA-Z_]|\Z)",
        source,
        re.DOTALL,
    )
    assert uninstall_match, "Nie udało się wyciągnąć ciała uninstall()"
    uninstall_body = uninstall_match.group(1)
    assert "_cleanup_pg_dirs(log)" in uninstall_body, (
        "uninstall() musi wołać _cleanup_pg_dirs() po udanej deinstalacji"
    )


def test_uninstall_pg_system_cleanup_runs_even_when_uninstaller_missing():
    """Cleanup MUSI się odpalić nawet gdy uninstaller EDB nie istnieje.

    Context (2026-06-05):
        Częsty scenariusz: user ręcznie usunął uninstall-postgresql.exe albo
        katalog ``16`` jest pusty po deinstalacji. Wtedy ``_find_uninstaller()``
        zwraca None i idziemy ścieżką "brak uninstallera". Nadal jednak mogą
        istnieć ``16_old_*`` katalogi z poprzednich cykli -- trzeba je
        posprzątać.
    """
    source = UNINSTALL_SCRIPT.read_text(encoding="utf-8")

    import re

    uninstall_match = re.search(
        r"def uninstall\(\)[^\n]*:(.*?)(?=\n\ndef [a-zA-Z_]|\Z)",
        source,
        re.DOTALL,
    )
    assert uninstall_match
    body = uninstall_match.group(1)

    # W obu gałęziach (uninstaller is None / returncode != 0 / sukces)
    # MUSI być cleanup. Sprawdzamy że count >= 2 (gałąź "no uninstaller" + gałąź "success").
    cleanup_calls = body.count("_cleanup_pg_dirs(log)")
    assert cleanup_calls >= 2, (
        f"Cleanup powinien być wywołany w co najmniej 2 gałęziach uninstall() "
        f"(gdy brak uninstallera + po sukcesie). Znaleziono: {cleanup_calls}."
    )
