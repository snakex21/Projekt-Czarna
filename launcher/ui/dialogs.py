"""Kompatybilnościowe re-exporty okien dialogowych launchera.

Implementacje klas UI są wydzielone do dedykowanych modułów w ``launcher.ui``.
Ten moduł pozostaje cienką warstwą zgodności dla starszych importów.
"""

from .add_edit_location_dialog import AddEditLocationDialog
from .admin_settings import AdminSettings
from .backup_manager import BackupManager
from .database_wizard import (
    DatabaseWizard,
    postgres_create_database,
    postgres_database_exists,
    postgres_enable_postgis,
    postgres_execute_schema,
    postgres_list_databases,
    test_postgres_connection,
)
from .display_settings import DisplaySettingsDialog
from .env_editor import EnvEditor
from .icon_chooser_window import IconChooserWindow
from .instructions_window import InstructionsWindow
from .loading_dialog import LoadingDialog
from .location_manager import LocationManager, TemplateChangeDialog
from .map_calibrator import CalibrationInstructions, MapCalibrator
from .photos_manager_dialog import PhotosManagerDialog
from .progress_dialog import ProgressDialog
from .site_settings_manager import SiteSettingsManager

from ..services.location_migration_service import create_and_migrate_location_database


__all__ = [
    "AddEditLocationDialog",
    "AdminSettings",
    "BackupManager",
    "CalibrationInstructions",
    "DatabaseWizard",
    "DisplaySettingsDialog",
    "EnvEditor",
    "IconChooserWindow",
    "InstructionsWindow",
    "LoadingDialog",
    "LocationManager",
    "MapCalibrator",
    "PhotosManagerDialog",
    "ProgressDialog",
    "SiteSettingsManager",
    "TemplateChangeDialog",
    "create_and_migrate_location_database",
    "postgres_create_database",
    "postgres_database_exists",
    "postgres_enable_postgis",
    "postgres_execute_schema",
    "postgres_list_databases",
    "test_postgres_connection",
]
