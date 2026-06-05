"""launcher/utils.py — kompatybilnościowe re-exporty helperów launchera."""

from .ui_scaling import get_effective_ui_scale, scale_window, scale_font, scale_wrap
from .network import get_local_ip
from .engine_access import _ensure_engine, check_postgres_available
from .location_context import (
    invalidate_locations_cache,
    get_active_location_name,
    ensure_default_location_exists,
    get_location_env_path,
)
from .window_icons import set_dialog_icon, set_windows_taskbar_icon_for_window
from .data_files import get_data_files
from .template_utils import get_available_templates, apply_homepage_template
from .env_config import (
    check_env_configuration,
    read_env_config,
    get_db_config_from_env,
    get_flask_config,
    _read_backend_env_value,
    _detect_sqlite_mode,
)
from .launcher_settings import get_launcher_setting, set_launcher_setting
from .process_env import prepare_process_env, prepare_command


SQLITE_MODE = False


__all__ = [
    "get_effective_ui_scale",
    "scale_window",
    "scale_font",
    "scale_wrap",
    "get_local_ip",
    "_ensure_engine",
    "check_postgres_available",
    "invalidate_locations_cache",
    "get_active_location_name",
    "ensure_default_location_exists",
    "get_location_env_path",
    "set_dialog_icon",
    "set_windows_taskbar_icon_for_window",
    "get_data_files",
    "get_available_templates",
    "apply_homepage_template",
    "check_env_configuration",
    "read_env_config",
    "get_db_config_from_env",
    "get_flask_config",
    "_read_backend_env_value",
    "_detect_sqlite_mode",
    "get_launcher_setting",
    "set_launcher_setting",
    "prepare_process_env",
    "prepare_command",
    "SQLITE_MODE",
]
