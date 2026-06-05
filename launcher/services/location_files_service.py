"""Pliki danych aktywnej miejscowości.

Wydzielone z ``launcher_app.py`` tworzenie brakujących plików JSON w
``data/locations/<miejscowość>``.
"""

from __future__ import annotations

import json
import os

from launcher.config.paths import location_data_dir
from launcher.services import location_service


DEFAULT_LOCATION_DATA_FILES = {
    "map_config.json": {
        "calibration": {
            "sw": {"lat": 50.0414, "lng": 21.2261},
            "ne": {"lat": 50.0814, "lng": 21.2661},
        },
        "defaults": {"center": {"lat": 50.0614, "lng": 21.2461}, "zoom": 14},
    },
    "owner_data_to_import.json": {},
    "parcels_data.json": {},
    "demografia.json": [],
    "genealogia.json": {"persons": []},
}


def check_backup_folder_files():
    """Sprawdza folder aktywnej miejscowości i tworzy brakujące pliki JSON."""
    location_name = location_service.get_active_location_name()
    if not location_name:
        print("ℹ️ Brak aktywnej miejscowości, pomijam tworzenie plików danych")
        return

    location_folder = str(location_data_dir(location_name))
    os.makedirs(location_folder, exist_ok=True)

    for filename, default_content in DEFAULT_LOCATION_DATA_FILES.items():
        path = os.path.join(location_folder, filename)
        if not os.path.exists(path):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default_content, f, indent=4, ensure_ascii=False)
                print(f"✅ Utworzono domyślny plik: {filename}")
            except Exception as e:
                print(f"⚠️ Nie można utworzyć pliku {filename}: {e}")
