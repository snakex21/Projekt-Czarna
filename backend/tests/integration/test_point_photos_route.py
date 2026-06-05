"""Testy integracji routera static_files - serwowanie zdjęć markerów z point_photos/.

Kontrakt: marker zdjęcia (z ``historical_points.json > points[].photos[].filename``)
są serwowane pod URL ``/point_photos/{filename}`` z folderu
``data/locations/<active>/point_photos/``.
"""
from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STATIC_FILES_PY = PROJECT_ROOT / "backend" / "routers" / "static_files.py"


def test_static_files_has_point_photos_route():
    """Router ma endpoint GET ``/point_photos/{filename:path}``."""
    source = STATIC_FILES_PY.read_text(encoding="utf-8")
    match = re.search(
        r"@router\.get\(\s*[\"']/point_photos/\{filename:path\}[\"']\s*\)",
        source,
    )
    assert match, (
        "Brak route @router.get('/point_photos/{filename:path}') - "
        "zdjęcia markerów nie mogą być serwowane przeglądarce"
    )


def test_point_photos_route_serves_from_subdir():
    """Handler czyta pliki z katalogu ``point_photos/`` aktywnej miejscowości."""
    source = STATIC_FILES_PY.read_text(encoding="utf-8")
    # Wyciągnij ciało funkcji point_photo (lub analogicznej nazwy)
    match = re.search(
        r"async\s+def\s+point_photo\s*\([^)]*\)(?:\s*->\s*[^:]+)?\s*:(.*?)(?=\n@router|\nasync\s+def|\ndef\s+|\Z)",
        source,
        re.S,
    )
    assert match, "Brak handlera point_photo dla route /point_photos/"
    body = match.group(1)
    assert "point_photos" in body, (
        "Handler point_photo musi czytać z katalogu point_photos/"
    )
    # Powinien używać BACKUP_DIR / ACTIVE_LOCATION (jak inne handlery w tym pliku)
    assert "BACKUP_DIR" in body and "ACTIVE_LOCATION" in body, (
        "Handler point_photo musi bazować na BACKUP_DIR/ACTIVE_LOCATION "
        "(jak reszta routerów static_files)"
    )
    # Zwraca FileResponse
    assert "FileResponse" in body, "Handler point_photo powinien zwracać FileResponse"
