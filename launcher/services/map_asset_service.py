"""Operacje plikowe dla mapy tła miejscowości."""

from __future__ import annotations

import os
import shutil

from launcher.config.paths import location_data_dir


def get_map_path(location_name: str):
    """Zwraca ścieżkę do pliku mapa.jpg dla danej miejscowości."""
    return location_data_dir(location_name) / "mapa.jpg"


def map_exists(location_name: str) -> bool:
    """Sprawdza czy dla miejscowości istnieje mapa tła."""
    return get_map_path(location_name).exists()


def save_map_file(source_path: str, location_name: str) -> str:
    """Kopiuje wskazany plik jako mapa.jpg dla miejscowości."""
    map_path = get_map_path(location_name)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source_path, map_path)
    return str(map_path)
