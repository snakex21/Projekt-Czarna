"""
Testy guard / anty-regresji architektonicznej.

Pilnuja, zeby refaktor backend/ (database.py -> db/, db_helpers.py -> db/helpers.py,
auth.py -> auth/, shared_utils.py -> utils/) sie nie cofnal. W szczegolnosci:

- Stare moduly top-level NIE istnieja (zostaly usuniete, nie shim'owane)
- Nowe pakiety maja __init__.py z re-exportem
- Sciezki importu zgadzaja sie z konwencja

Te testy sa celowo proste (bez async, bez DB) - maja byc szybkie i deterministyczne.
"""
import importlib
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ================================================================================
# Stare moduly top-level sa USUNIETE
# ================================================================================
# Po refaktorze te pliki NIE istnieja:
# - backend/database.py
# - backend/db_helpers.py
# - backend/auth.py
# - backend/shared_utils.py
# Jesli ktos (czlowiek lub AI) doda je "dla wstecznej kompatybilnosci",
# te testy to zlapia.


REMOVED_MODULES = [
    "backend.database",
    "backend.db_helpers",
    "backend.shared_utils",
]


@pytest.mark.parametrize("module_name", REMOVED_MODULES)
def test_old_top_level_module_is_removed(module_name):
    """Stare moduly top-level nie istnieja po refaktorze.

    Zapobiega dodawaniu shim'ow 'dla wstecznej kompatybilnosci', ktore
    rozmydlaja architekture. Jesli potrzebny jest wsteczny import, dodaj
    go jawnie do odpowiedniego pakietu (np. backend.db.__init__).

    Uwaga: backend.auth NIE jest na tej liscie - zostal przekształcony
    z pliku auth.py w pakiet auth/__init__.py. Pilnuje tego osobny test
    test_backend_root_has_no_auth_py.
    """
    # Wymus ponowny import (gdyby ktorys test wczesniej cos zaimportowal)
    sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_backend_auth_is_package_not_module():
    """backend.auth to PAKIET (katalog z __init__.py), nie plik auth.py.

    Po refaktorze backend/auth.py zostal zastapiony przez backend/auth/__init__.py.
    Ten test pilnuje, zeby ktos nie 'cofnął' refaktoru zamieniajac pakiet z powrotem
    w pojedynczy plik (co zlamaloby znowu architekture).
    """
    import backend.auth
    # Pakiet ma __path__ (sciezke do katalogu); modul (plik) nie ma.
    assert hasattr(backend.auth, "__path__"), (
        "backend.auth powinien byc pakietem (katalog z __init__.py), "
        "a nie modulem (plik auth.py). Sprawdz czy nie cofnales refaktoru."
    )


def test_backend_root_has_no_database_py():
    """backend/database.py nie istnieje na dysku."""
    assert not (PROJECT_ROOT / "backend" / "database.py").exists(), (
        "backend/database.py powinien zostac usuniety po refaktorze. "
        "Jezeli potrzebujesz wstecznej kompatybilnosci, dodaj re-export "
        "w backend/db/__init__.py zamiast tworzyc nowy plik top-level."
    )


def test_backend_root_has_no_db_helpers_py():
    """backend/db_helpers.py nie istnieje na dysku."""
    assert not (PROJECT_ROOT / "backend" / "db_helpers.py").exists()


def test_backend_root_has_no_auth_py():
    """backend/auth.py nie istnieje na dysku."""
    assert not (PROJECT_ROOT / "backend" / "auth.py").exists()


def test_backend_root_has_no_shared_utils_py():
    """backend/shared_utils.py nie istnieje na dysku."""
    assert not (PROJECT_ROOT / "backend" / "shared_utils.py").exists()


# ================================================================================
# Nowe pakiety maja __init__.py
# ================================================================================


@pytest.mark.parametrize("package", ["db", "auth", "utils"])
def test_new_package_has_init_py(package):
    """backend/<package>/__init__.py musi istniec (pakiet, nie katalog)."""
    init_path = PROJECT_ROOT / "backend" / package / "__init__.py"
    assert init_path.exists(), f"backend/{package}/__init__.py brakuje"


# ================================================================================
# Konwencja: top-level to main.py + config.py
# ================================================================================


def test_backend_root_only_has_main_and_config():
    """backend/*.py (top-level, nie w podfolderach) to main.py i config.py.

    Zapobiega dodawaniu nowych modulow top-level 'bo tak jest krotszy import'.
    """
    root_files = {
        p.name
        for p in (PROJECT_ROOT / "backend").iterdir()
        if p.is_file() and p.suffix == ".py" and p.name != "__init__.py"
    }
    expected = {"main.py", "config.py"}
    assert root_files == expected, (
        f"backend/ ma niechciane pliki top-level: {root_files - expected}. "
        f"Brakuje: {expected - root_files}. "
        f"Nowy modul powinien isc do podfolderu (np. backend/core/, backend/api/)."
    )


# ================================================================================
# Re-export w __init__.py pokrywa kluczowe symbole
# ================================================================================


def test_backend_db_init_exports_helpers():
    """backend.db.__init__ eksportuje fetch_one/fetch_all/execute z helpers.py."""
    from backend.db import execute, fetch_all, fetch_one
    assert callable(fetch_one)
    assert callable(fetch_all)
    assert callable(execute)


def test_backend_db_init_exports_connection():
    """backend.db.__init__ eksportuje get_db, init_db, close_db z connection.py."""
    from backend.db import close_db, get_db, init_db
    assert callable(get_db)
    assert callable(init_db)
    assert callable(close_db)


def test_backend_auth_init_exports_routes():
    """backend.auth.__init__ eksportuje admin_required, verify_password, itd."""
    from backend.auth import (
        admin_required,
        get_token,
        is_admin_authenticated,
        verify_password,
    )
    assert callable(admin_required)
    assert callable(verify_password)
    assert callable(get_token)
    assert callable(is_admin_authenticated)


def test_backend_utils_init_exports_shared():
    """backend.utils.__init__ eksportuje 4 publiczne funkcje."""
    from backend.utils import (
        extract_year,
        fix_windows_console_encoding,
        is_real_ownership,
        parse_polish_date,
    )
    assert callable(extract_year)
    assert callable(parse_polish_date)
    assert callable(is_real_ownership)
    assert callable(fix_windows_console_encoding)


# ================================================================================
# Sciezki importu w testach/routerach zaktualizowane
# ================================================================================


def test_no_router_uses_old_database_import():
    """aden router nie importuje z '..database' (stara sciezka)."""
    import ast
    routers_dir = PROJECT_ROOT / "backend" / "routers"
    offenders = []
    for py_file in routers_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module in ("..database", "..db_helpers", "..shared_utils", "..auth"):
                    offenders.append(f"{py_file.name}: {node.module}")
    assert not offenders, (
        f"Routery uzywaja starych importow: {offenders}. "
        f"Po refaktorze backend/ powinny importowac z backend.db, backend.auth, backend.utils."
    )


def test_no_service_uses_old_shared_utils_import():
    """aden service nie importuje z '..shared_utils' (stara sciezka)."""
    import ast
    services_dir = PROJECT_ROOT / "backend" / "services"
    offenders = []
    for py_file in services_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module in ("..shared_utils", "..database", "..db_helpers"):
                    offenders.append(f"{py_file.name}: {node.module}")
    assert not offenders, (
        f"Serwisy uzywaja starych importow: {offenders}. "
        f"Powinny importowac z backend.utils, backend.db."
    )


def test_main_uses_new_db_import():
    """backend/main.py importuje z .db (nie .database)."""
    main_source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "from .db import" in main_source, (
        "backend/main.py powinien importowac z '.db' (nowa struktura)."
    )
    assert "from .database import" not in main_source, (
        "backend/main.py uzywa STAREJ sciezki '.database'. "
        "Zmien na 'from .db import'."
    )
