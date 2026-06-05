"""Kontekst aktywnej miejscowości launchera."""

import os

from ..config.paths import BACKUP_FOLDER
from .engine_access import _ensure_engine


__all__ = [
    "invalidate_locations_cache",
    "get_active_location_name",
    "ensure_default_location_exists",
    "get_location_env_path",
]


_locations_cache = None
_locations_cache_time = 0


def invalidate_locations_cache():

    global _locations_cache, _locations_cache_time

    _locations_cache = None

    _locations_cache_time = 0


def get_active_location_name():

    """Zwraca nazwę aktywnej miejscowości z silnika DB (bez zależności od launcher_app)."""

    eng = _ensure_engine()

    active = eng.get_active_location()

    return active[1] if active else None


def ensure_default_location_exists():

    """Tworzy domyślną miejscowość jeśli nie istnieje (deleguje do silnika)."""

    eng = _ensure_engine()

    try:

        eng.ensure_default_location_exists()

    except AttributeError:

        pass  # niektóre silniki mogą nie mieć tej metody


def get_location_env_path(location_name=None):

    """Zwraca ścieżkę do pliku .env dla danej miejscowości."""

    if location_name is None:

        # Upewnij się, że istnieje domyślna miejscowość

        ensure_default_location_exists()

        location_name = get_active_location_name()

    if not location_name:

        raise ValueError("Brak aktywnej miejscowości")

    return os.path.join(BACKUP_FOLDER, location_name, ".env")
