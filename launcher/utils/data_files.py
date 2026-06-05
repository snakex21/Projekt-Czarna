"""Ścieżki plików danych aktywnej miejscowości."""

import os

from ..config.paths import BACKUP_FOLDER
from .location_context import get_active_location_name


__all__ = ["get_data_files"]


def get_data_files(location_name=None):

    """Zwraca słownik ścieżek plików danych dla danej miejscowości."""

    if location_name is None:

        try:

            location_name = get_active_location_name()

        except Exception:

            # Import-time safe fallback: przy uszkodzonej/niepełnej konfiguracji
            # PostgreSQL launcher musi się uruchomić, żeby pokazać dialog naprawy
            # konfiguracji zamiast crashować podczas importu modułów UI.
            location_name = None

    location_folder = os.path.join(BACKUP_FOLDER, location_name) if location_name else BACKUP_FOLDER

    return {

        "owners": {

            "path": os.path.join(location_folder, "owner_data_to_import.json"),

            "name": "Właściciele i Demografia",

            "related": [os.path.join(location_folder, "demografia.json")],

        },

        "parcels": {

            "path": os.path.join(location_folder, "parcels_data.json"),

            "name": "Działki (Geometria)",

            "related": [],

        },

        "genealogy": {

            "path": os.path.join(location_folder, "genealogia.json"),

            "name": "Genealogia",

            "related": [],

        },

    }
