from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


UTILS_MODULES_TO_IMPORT = [
    "launcher.utils",
    "launcher.utils.ui_scaling",
    "launcher.utils.network",
    "launcher.utils.engine_access",
    "launcher.utils.location_context",
    "launcher.utils.window_icons",
    "launcher.utils.data_files",
    "launcher.utils.template_utils",
    "launcher.utils.env_config",
    "launcher.utils.process_env",
    "launcher.utils.launcher_settings",
]

UTILS_SPLIT_FILES = [
    "launcher/utils/ui_scaling.py",
    "launcher/utils/network.py",
    "launcher/utils/engine_access.py",
    "launcher/utils/location_context.py",
    "launcher/utils/window_icons.py",
    "launcher/utils/data_files.py",
    "launcher/utils/template_utils.py",
    "launcher/utils/env_config.py",
    "launcher/utils/process_env.py",
    "launcher/utils/launcher_settings.py",
]


def _parse_project_file(relative_path: str) -> ast.Module:
    path = PROJECT_ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_level_import_roots(relative_path: str) -> set[str]:
    tree = _parse_project_file(relative_path)
    imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    return imports


@pytest.fixture
def forbid_tk_windows(monkeypatch):
    import tkinter as tk

    def fail_window_init(self, *args, **kwargs):
        raise AssertionError("Import launcher.utils must not create Tk windows")

    monkeypatch.setattr(tk.Tk, "__init__", fail_window_init)
    monkeypatch.setattr(tk.Toplevel, "__init__", fail_window_init)
    return tk


@pytest.mark.parametrize("module_name", UTILS_MODULES_TO_IMPORT)
def test_launcher_utils_split_modules_import_without_tk_windows(module_name, forbid_tk_windows, monkeypatch):
    monkeypatch.setenv("DB_ENGINE", "sqlite")
    sys.modules.pop(module_name, None)

    module = importlib.import_module(module_name)

    assert module is not None
    assert getattr(forbid_tk_windows, "_default_root", None) is None


def test_launcher_utils_facade_exports_split_functions():
    import launcher.utils as utils
    utils = importlib.reload(utils)
    from launcher.utils.data_files import get_data_files
    from launcher.utils.engine_access import _ensure_engine, check_postgres_available
    from launcher.utils.env_config import (
        _detect_sqlite_mode,
        _read_backend_env_value,
        check_env_configuration,
        get_db_config_from_env,
        get_flask_config,
        read_env_config,
    )
    from launcher.utils.launcher_settings import get_launcher_setting, set_launcher_setting
    from launcher.utils.location_context import (
        ensure_default_location_exists,
        get_active_location_name,
        get_location_env_path,
        invalidate_locations_cache,
    )
    from launcher.utils.network import get_local_ip
    from launcher.utils.process_env import prepare_command, prepare_process_env
    from launcher.utils.template_utils import apply_homepage_template, get_available_templates
    from launcher.utils.ui_scaling import get_effective_ui_scale, scale_font, scale_window, scale_wrap
    from launcher.utils.window_icons import set_dialog_icon, set_windows_taskbar_icon_for_window

    assert utils.get_effective_ui_scale is get_effective_ui_scale
    assert utils.scale_window is scale_window
    assert utils.scale_font is scale_font
    assert utils.scale_wrap is scale_wrap
    assert utils.get_local_ip is get_local_ip
    assert utils._ensure_engine is _ensure_engine
    assert utils.check_postgres_available is check_postgres_available
    assert utils.invalidate_locations_cache is invalidate_locations_cache
    assert utils.get_active_location_name is get_active_location_name
    assert utils.ensure_default_location_exists is ensure_default_location_exists
    assert utils.get_location_env_path is get_location_env_path
    assert utils.set_dialog_icon is set_dialog_icon
    assert utils.set_windows_taskbar_icon_for_window is set_windows_taskbar_icon_for_window
    assert utils.get_data_files is get_data_files
    assert utils.get_available_templates is get_available_templates
    assert utils.apply_homepage_template is apply_homepage_template
    assert utils.check_env_configuration is check_env_configuration
    assert utils.read_env_config is read_env_config
    assert utils.get_db_config_from_env is get_db_config_from_env
    assert utils.get_flask_config is get_flask_config
    assert utils._read_backend_env_value is _read_backend_env_value
    assert utils._detect_sqlite_mode is _detect_sqlite_mode
    assert utils.get_launcher_setting is get_launcher_setting
    assert utils.set_launcher_setting is set_launcher_setting
    assert utils.prepare_process_env is prepare_process_env
    assert utils.prepare_command is prepare_command


def test_launcher_utils_init_has_no_local_function_or_class_implementations():
    tree = _parse_project_file("launcher/utils/__init__.py")

    function_names = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}

    assert function_names == set()
    assert class_names == set()


@pytest.mark.parametrize("relative_path", UTILS_SPLIT_FILES)
def test_split_utils_modules_do_not_import_launcher_app_or_dialogs(relative_path):
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    top_level_imports = _top_level_import_roots(relative_path)

    assert "launcher.launcher_app" not in source
    assert "launcher.ui.dialogs" not in source
    assert ".dialogs" not in source
    assert "launcher_app" not in top_level_imports
    assert "dialogs" not in top_level_imports
    assert "from launcher.utils import" not in source
    assert "import launcher.utils" not in source
    assert "from . import" not in source
    assert "def _get_launcher" not in source
    assert "def _launcher" not in source


def test_window_icons_keeps_tkinter_import_local():
    top_level_imports = _top_level_import_roots("launcher/utils/window_icons.py")

    assert "tkinter" not in top_level_imports


def test_prepare_process_env_sets_gui_utf8_flags(monkeypatch):
    from launcher.utils.process_env import prepare_process_env

    monkeypatch.setenv("DB_ENGINE", "sqlite")
    env = prepare_process_env(active_location_name="Czarna")

    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUTF8"] == "1"
    assert env["LAUNCHED_BY_GUI"] == "1"
    assert env["ACTIVE_LOCATION"] == "Czarna"
    assert env["DB_ENGINE"] == "sqlite"


def test_get_data_files_with_explicit_location_name():
    from launcher.utils.data_files import get_data_files

    files = get_data_files("Czarna")

    assert set(files) == {"owners", "parcels", "genealogy"}
    assert files["owners"]["path"].endswith("owner_data_to_import.json")
    assert files["parcels"]["path"].endswith("parcels_data.json")
    assert files["genealogy"]["path"].endswith("genealogia.json")
