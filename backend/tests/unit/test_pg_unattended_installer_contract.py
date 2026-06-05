from __future__ import annotations

import ast
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _function_source(function_name: str) -> str:
    path = SCRIPTS_DIR / "install_pg_unattended.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"Brak funkcji {function_name}")


def test_apply_postgis_and_schema_uses_installer_password_not_stale_env():
    """Schemat PG ma używać hasła instalatora, nie starego `.postgres.env`."""
    body = _function_source("apply_postgis_and_schema")

    assert "get_postgres_config" not in body, (
        "Instalator nie może czytać .postgres.env przed utworzeniem schematu, "
        "bo plik może nie istnieć albo zawierać stare hasło."
    )
    assert "PG_PASSWORD" in body
    assert '"password": PG_PASSWORD' in body


def test_update_env_files_replaces_empty_engine_and_writes_pg_credentials(tmp_path):
    """Aktualizacja `.env` musi działać także dla `DB_ENGINE=` po first-run."""
    import install_pg_unattended as installer

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    env_path = backend_dir / ".env"
    env_path.write_text(
        "FLASK_HOST=127.0.0.1\n"
        "DB_ENGINE=\n"
        "DB_PORT=5444\n"
        "DB_PATH=data/czarna.db\n",
        encoding="utf-8",
    )

    installer.update_env_files(tmp_path)

    result = env_path.read_text(encoding="utf-8")
    assert "DB_ENGINE=postgresql" in result
    assert "DB_HOST=localhost" in result
    assert f"DB_PORT={installer.PG_PORT}" in result
    assert "DB_USER=postgres" in result
    assert f"DB_PASSWORD={installer.PG_PASSWORD}" in result
    assert f"DB_NAME={installer.PG_DB_NAME}" in result
    assert "DB_PORT=5444" not in result

    pg_env = backend_dir / ".postgres.env"
    assert pg_env.exists()
    pg_result = pg_env.read_text(encoding="utf-8")
    assert f"LAUNCHER_DB_PASSWORD={installer.PG_PASSWORD}" in pg_result


def test_installer_logs_do_not_print_plain_default_password():
    """Logi instalatora nie powinny pokazywać surowego hasła `1234`."""
    source = (SCRIPTS_DIR / "install_pg_unattended.py").read_text(encoding="utf-8")

    assert "hasło: {PG_PASSWORD}" not in source
    assert "'*' * len(PG_PASSWORD)" in source


def test_subprocess_output_uses_safe_decoding_for_polish_windows_messages():
    """Subprocessy instalatora muszą używać `errors=replace`.

    Bez tego psql/PowerShell na polskim Windows potrafi przerwać GUI przez
    ``UnicodeDecodeError: 'charmap' codec can't decode byte ...``.
    """
    source = (SCRIPTS_DIR / "install_pg_unattended.py").read_text(encoding="utf-8")

    assert "def _run_text" in source
    assert 'encoding="utf-8"' in source
    assert 'errors="replace"' in source
    assert "subprocess.run(" not in source.replace("return subprocess.run(", ""), (
        "Bezpośrednie subprocess.run(text=True) może crashować na polskich komunikatach. "
        "Użyj _run_text(...)."
    )


def test_installer_subprocesses_do_not_flash_console_windows():
    """Instalator GUI nie może migać PowerShellem/konsolą przy subprocessach."""
    source = (SCRIPTS_DIR / "install_pg_unattended.py").read_text(encoding="utf-8")

    assert "def _no_window_flags" in source
    assert "CREATE_NO_WINDOW" in source
    assert 'kwargs.setdefault("creationflags", _no_window_flags())' in source


def test_installer_does_not_treat_leftover_pg_directory_as_healthy_install():
    """Po deinstalacji EDB może zostać katalog PG bez usługi Windows."""
    unattended = (SCRIPTS_DIR / "install_pg_unattended.py").read_text(encoding="utf-8")
    gui = (SCRIPTS_DIR / "install_pg_gui.py").read_text(encoding="utf-8")

    assert "def is_pg_service_registered" in unattended
    assert "def is_pg_install_healthy" in unattended
    assert "def prepare_stale_pg_install_dir" in unattended
    assert "shutil.move" in unattended
    assert "osierocony katalog PG" in unattended
    assert "Path(core.PG_INSTALL_DIR).exists()" not in gui
    assert "core.is_pg_install_healthy()" in gui
    assert "core.prepare_stale_pg_install_dir()" in gui


def test_wait_for_pg_service_fails_fast_when_service_missing():
    """Nie czekamy 300s, jeśli usługa po deinstalacji nie istnieje."""
    body = _function_source("wait_for_pg_service")

    assert "is_pg_service_registered()" in body
    assert "nie istnieje" in body
    assert "return False" in body


def test_create_database_handles_missing_stderr_and_polish_existing_db_message():
    """`create_database` nie może robić `.lower()` na None."""
    body = _function_source("create_database")

    assert 'stderr = r.stderr or ""' in body
    assert 'stdout = r.stdout or ""' in body
    assert "combined" in body
    assert "już istnieje" in body or "juz istnieje" in body


def test_pg_gui_window_is_large_enough_and_keeps_buttons_visible():
    """Okno GUI instalatora ma mieć widoczne dolne przyciski.

    Regresja: okno 760x560 było za małe na Windows i przyciski znikały pod
    panelem logów. Przyciski muszą być tworzone przed sekcją szczegółów, żeby
    były zawsze nad rozciągliwym panelem logu.
    """
    source = (SCRIPTS_DIR / "install_pg_gui.py").read_text(encoding="utf-8")

    assert "WINDOW_WIDTH = 900" in source
    assert "WINDOW_HEIGHT = 760" in source
    assert "WINDOW_MIN_HEIGHT = 700" in source
    assert "Otwórz log" in source
    assert "Zamknij po zakończeniu" in source

    buttons_pos = source.find("buttons = tk.Frame")
    details_pos = source.find("details_frame = tk.LabelFrame")
    assert buttons_pos > 0 and details_pos > 0
    assert buttons_pos < details_pos, (
        "Przyciski muszą być przed panelem szczegółów, żeby nie znikały przy "
        "mniejszym oknie."
    )


def test_pg_gui_success_message_closes_installer_window():
    """Po sukcesie OK w komunikacie końcowym zamyka okno instalatora."""
    source = (SCRIPTS_DIR / "install_pg_gui.py").read_text(encoding="utf-8")

    assert "PostgreSQL + PostGIS są gotowe. Uruchom launcher ponownie." in source
    assert "self.root.destroy()" in source


def test_pg_gui_window_is_centered_on_screen():
    """Okno instalatora ma być wycentrowane (regresja UX: pojawiało się w 0,0).

    Regresja: ``install_pg_gui.py`` ustawiał tylko ``geometry(f"{W}x{H}")``
    bez pozycji, więc okno lądowało w lewym górnym rogu ekranu — szczególnie
    irytujące na multi-monitor. Naprawa: ``_center_window()`` w ``__init__``
    zaraz po ustawieniu geometrii.
    """
    source = (SCRIPTS_DIR / "install_pg_gui.py").read_text(encoding="utf-8")

    assert "def _center_window" in source, (
        "Brak metody _center_window w install_pg_gui.py — okno wyląduje w 0,0."
    )
    # _center_window musi używać screenwidth/screenheight do centrowania
    assert "winfo_screenwidth" in source
    assert "winfo_screenheight" in source
    # Musi ustawiać pozycję (np. "+{x}+{y}") a nie tylko rozmiar
    assert 'f"+{x}+{y}"' in source
    # Musi być wywołane w __init__ po ustawieniu geometrii
    init_start = source.find("def __init__(self):")
    init_end = source.find("def _center_window", init_start)
    init_body = source[init_start:init_end]
    assert "self._center_window()" in init_body, (
        "_center_window() musi być wywołane w __init__, inaczej okno wyskoczy w 0,0."
    )


def test_cleanup_installer_cache_removes_pg_and_postgis_after_install():
    """Po udanej instalacji PG + PostGIS cache/ zwalnia 457 MB automatycznie.

    Context (2026-06-05):
        Instalatory (postgresql-16.4-1-windows-x64.exe + postgis-bundle-...)
        są pobierane do cache/ na czas instalacji. Po zakończeniu są zbędne
        (reinstall pobierze je ponownie via download_or_skip). User nie
        powinien ręcznie sprzątać 457 MB po każdej instalacji.
    """
    import importlib.util
    from pathlib import Path

    # Dynamicznie załaduj install_pg_unattended.py
    spec = importlib.util.spec_from_file_location(
        "install_pg_unattended_test",
        SCRIPTS_DIR / "install_pg_unattended.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Helper musi istnieć i eksportować listę instalatorów
    assert hasattr(module, "cleanup_installer_cache"), (
        "Brak cleanup_installer_cache() — instalatory zostaną w cache/ po każdej instalacji."
    )
    assert hasattr(module, "INSTALLER_FILES"), (
        "Brak stałej INSTALLER_FILES — co dokładnie usuwać?"
    )
    assert "postgresql-16.4-1-windows-x64.exe" in module.INSTALLER_FILES
    assert "postgis-bundle-pg16x64-setup-3.6.2-1.exe" in module.INSTALLER_FILES

    # Test: utwórz 2 pliki w tmp, wywołaj cleanup, sprawdź że usunięte
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for name in module.INSTALLER_FILES:
            (tmp_path / name).write_bytes(b"X" * 1024)  # 1 KB każdy
        removed, bytes_freed = module.cleanup_installer_cache(tmp_path)
        assert removed == 2, f"cleanup_installer_cache powinien usunąć 2 pliki, usunął {removed}"
        assert bytes_freed == 2048
        for name in module.INSTALLER_FILES:
            assert not (tmp_path / name).exists(), f"{name} powinien być usunięty"

    # Test: brak plików → 0 usuniętych, 0 bajtów (nie crashuje)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        removed, bytes_freed = module.cleanup_installer_cache(tmp_path)
        assert removed == 0
        assert bytes_freed == 0


def test_main_flow_calls_cleanup_installer_cache_after_verify():
    """``main()`` musi wołać cleanup_installer_cache po verify_installation()."""
    source = (SCRIPTS_DIR / "install_pg_unattended.py").read_text(encoding="utf-8")
    gui_source = (SCRIPTS_DIR / "install_pg_gui.py").read_text(encoding="utf-8")

    assert "cleanup_installer_cache(cache_dir)" in source, (
        "main() w install_pg_unattended.py nie woła cleanup_installer_cache() "
        "po verify_installation() — 457 MB zostanie w cache/ po każdej instalacji."
    )
    assert "cleanup_installer_cache(cache_dir)" in gui_source, (
        "install_pg_gui.py nie woła cleanup_installer_cache() po sukcesie — "
        "GUI wersja pominie cleanup."
    )
