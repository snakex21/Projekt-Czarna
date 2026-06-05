"""Router punktów historycznych.

Zwraca FeatureCollection obiektów specjalnych (np. dworzec, dróżnica)
wzbogaconych o metadane z pliku ``historical_points.json`` w aktywnej
miejscowości. Geometria pobierana jest z kanonicznego źródła -
``parcels_data.json`` (plik ten pozostaje źródłem prawdy nawet po migracji
do PostgreSQL: skrypt migracji kopiuje geometrię do tabeli
``obiekty_geograficzne``, ale plik JSON nie jest usuwany).

Schemat ``historical_points.json``::

    {
        "points": [
            {
                "object_name": "dworzec kolejowy",
                "display_name": "Dworzec kolejowy w Czarnej",
                "description": "Budynek stacji z 1905 r. ...",
                "source_note": "Archiwum Państwowe w Rzeszowie, sygn. 123",
                "photos": [
                    {"filename": "dworzec_czarna.png", "caption": "Widok z 1935 r."}
                ]
            }
        ]
    }
"""
from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from ..config import ACTIVE_LOCATION, BACKUP_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["map"])

HISTORICAL_POINTS_FILENAME = "historical_points.json"
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_DESCRIPTION_LENGTH = 5000
MAX_SOURCE_NOTE_LENGTH = 1000
MAX_DISPLAY_NAME_LENGTH = 200
MAX_CAPTION_LENGTH = 500
MAX_PHOTOS_PER_POINT = 20


def _location_data_dir() -> Path:
    """Folder danych aktywnej miejscowości."""
    return Path(BACKUP_DIR) / ACTIVE_LOCATION


def _parcels_data_path() -> Path:
    return _location_data_dir() / "parcels_data.json"


def _historical_points_path() -> Path:
    return _location_data_dir() / HISTORICAL_POINTS_FILENAME


def _history_photos_dir() -> Path:
    return _location_data_dir() / "history_photos"


def _load_parcels() -> Dict[str, Dict[str, Any]]:
    """Czyta ``parcels_data.json`` i zwraca słownik obiektów (klucz -> właściwości)."""
    path = _parcels_data_path()
    if not path.exists():
        logger.warning("Brak pliku parcels_data.json: %s", path)
        return {}
    try:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Błąd odczytu parcels_data.json: %s", exc)
        return {}
    if not isinstance(data, dict):
        logger.error("parcels_data.json ma nieprawidłowy typ: %s", type(data).__name__)
        return {}
    return data


def _load_historical_points() -> List[Dict[str, Any]]:
    """Czyta ``historical_points.json`` i zwraca listę wpisów.

    Brak pliku -> pusta lista (nie 404, warstwa mapy renderuje pustą kolekcję).
    """
    path = _historical_points_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Błąd odczytu historical_points.json: %s", exc)
        return []
    if not isinstance(data, dict):
        return []
    points = data.get("points", [])
    if not isinstance(points, list):
        return []
    return [p for p in points if isinstance(p, dict)]


def _parse_geometry(value: Any) -> Optional[List[float]]:
    """Konwertuje ``[lat, lng]`` z ``parcels_data.json`` na ``[lng, lat]`` GeoJSON.

    Zwraca ``None`` jeśli geometria nie jest listą dwóch liczb w prawidłowym
    zakresie (współrzędne Polski ~ lng 14-25, lat 49-55).
    """
    if not isinstance(value, list) or len(value) != 2:
        return None
    try:
        lat, lng = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        return None
    return [lng, lat]


def _parse_photo(raw: Any) -> Optional[Dict[str, str]]:
    """Waliduje i normalizuje wpis zdjęcia ``{filename, caption}``."""
    if not isinstance(raw, dict):
        return None
    filename = raw.get("filename")
    if not isinstance(filename, str) or not filename:
        return None
    # Odcinanie ewentualnych ścieżek - zwracamy sam basename
    safe_name = Path(filename).name
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        return None
    caption = raw.get("caption", "")
    if not isinstance(caption, str):
        caption = ""
    return {"filename": safe_name, "caption": caption[:MAX_CAPTION_LENGTH]}


def _build_feature(point: Dict[str, Any], parcels: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Łączy metadane punktu z geometrią z ``parcels_data.json``.

    Zwraca ``None`` gdy nie znaleziono pasującego obiektu specjalnego lub gdy
    geometria jest nieprawidłowa - wtedy wpis jest pomijany w wyniku.
    """
    object_name = point.get("object_name")
    if not isinstance(object_name, str) or not object_name:
        return None

    # Szukamy obiektu w parcels_data.json po nazwie
    # Nazwa obiektu specjalnego to część klucza przed "_obiekt_specjalny"
    # (klucz ma format "<numer_lub_nazwa>_obiekt_specjalny")
    matching_key: Optional[str] = None
    matching_props: Optional[Dict[str, Any]] = None
    suffix = "_obiekt_specjalny"
    for key, props in parcels.items():
        if not isinstance(props, dict):
            continue
        if props.get("kategoria") != "obiekt_specjalny":
            continue
        if not key.endswith(suffix):
            continue
        candidate_name = key[: -len(suffix)]
        if candidate_name == object_name:
            matching_key = key
            matching_props = props
            break

    if matching_props is None:
        warnings.warn(
            f"Punkt historyczny '{object_name}' nie ma pasującego obiektu "
            f"specjalnego w parcels_data.json - pomijam",
            stacklevel=2,
        )
        return None

    geometry = _parse_geometry(matching_props.get("geometria"))
    if geometry is None:
        warnings.warn(
            f"Obiekt '{matching_key}' ma nieprawidłową geometrię - pomijam",
            stacklevel=2,
        )
        return None

    display_name = point.get("display_name", object_name)
    if not isinstance(display_name, str) or not display_name:
        display_name = object_name
    display_name = display_name[:MAX_DISPLAY_NAME_LENGTH]

    description = point.get("description", "")
    if not isinstance(description, str):
        description = ""
    description = description[:MAX_DESCRIPTION_LENGTH]

    source_note = point.get("source_note", "")
    if not isinstance(source_note, str):
        source_note = ""
    source_note = source_note[:MAX_SOURCE_NOTE_LENGTH]

    raw_photos = point.get("photos", [])
    photos: List[Dict[str, str]] = []
    if isinstance(raw_photos, list):
        for raw in raw_photos[:MAX_PHOTOS_PER_POINT]:
            parsed = _parse_photo(raw)
            if parsed is not None:
                photos.append(parsed)

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": geometry},
        "properties": {
            "object_name": object_name,
            "display_name": display_name,
            "description": description,
            "source_note": source_note,
            "photos": photos,
        },
    }


@router.get("/historical-points")
async def get_historical_points():
    """Zwraca FeatureCollection punktów historycznych aktywnej miejscowości.

    Warstwa mapy korzysta z tej kolekcji do wyświetlenia markerów z metadanymi
    (opis, źródło, zdjęcia) w popupie. Brak pliku ``historical_points.json``
    NIE jest błędem - zwracamy pustą kolekcję.
    """
    parcels = _load_parcels()
    points_meta = _load_historical_points()

    features: List[Dict[str, Any]] = []
    for point in points_meta:
        feature = _build_feature(point, parcels)
        if feature is not None:
            features.append(feature)

    return {"type": "FeatureCollection", "features": features}
