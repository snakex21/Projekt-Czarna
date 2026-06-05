"""Serwis CRUD dla punktów historycznych w miejscowości.

Punkty historyczne to obiekty specjalne (dworzec, kapliczka, dróżnica itp.),
które na mapie mają dodatkowe metadane: opis, źródło archiwalne, zdjęcia.

Dane trzymane w ``data/locations/<miejscowość>/historical_points.json``
(per-miejscowość, obok ``parcels_data.json`` i ``launcher_db_config.json``).
Geometria obiektu brana jest z ``parcels_data.json`` (``kategoria =
"obiekt_specjalny"``); w ``historical_points.json`` przechowujemy tylko
metadane + nazwę obiektu, który je reprezentuje na mapie.

Moduł wydzielony zgodnie z architekturą launchera:
``launcher/services/`` = czysta logika bez Tkinter.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from launcher.config.paths import location_data_dir

logger = logging.getLogger(__name__)

FILENAME = "historical_points.json"
HISTORY_PHOTOS_SUBDIR = "history_photos"
# Osobny folder na zdjęcia przypisane do markerów (punktów historycznych).
# Galeria miejscowości pozostaje w ``history_photos/`` - tu są tylko zdjęcia
# używane przez ``historical_points.json > points[].photos[].filename``.
POINT_PHOTOS_SUBDIR = "point_photos"
SPECIAL_OBJECT_SUFFIX = "_obiekt_specjalny"
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_DESCRIPTION_LENGTH = 5000
MAX_SOURCE_NOTE_LENGTH = 1000
MAX_DISPLAY_NAME_LENGTH = 200
MAX_CAPTION_LENGTH = 500
MAX_PHOTOS_PER_POINT = 20

_FILENAME_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class HistoricalPointValidationError(ValueError):
    """Błąd walidacji danych punktu historycznego."""


@dataclass
class HistoricalPoint:
    """Pojedynczy punkt historyczny - metadane obiektu specjalnego na mapie.

    Atrybut ``object_name`` to nazwa obiektu z ``parcels_data.json``
    (klucz po odcięciu sufiksu ``_obiekt_specjalny``).
    """

    object_name: str
    display_name: str = ""
    description: str = ""
    source_note: str = ""
    photos: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializacja do dict (zgodne ze schematem JSON)."""
        return {
            "object_name": self.object_name,
            "display_name": self.display_name,
            "description": self.description,
            "source_note": self.source_note,
            "photos": [dict(p) for p in self.photos],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "HistoricalPoint":
        """Konstruktor z surowego dict (po walidacji typów)."""
        return cls(
            object_name=str(raw.get("object_name", "")),
            display_name=str(raw.get("display_name", "")),
            description=str(raw.get("description", "")),
            source_note=str(raw.get("source_note", "")),
            photos=[
                {"filename": str(p.get("filename", "")), "caption": str(p.get("caption", ""))}
                for p in (raw.get("photos") or [])
                if isinstance(p, dict)
            ],
        )

    def validate(self) -> None:
        """Waliduje dane punktu. Rzuca ``HistoricalPointValidationError``."""
        if not self.object_name or not self.object_name.strip():
            raise HistoricalPointValidationError("Pole 'object_name' jest wymagane.")
        if _FILENAME_INVALID_CHARS.search(self.object_name):
            raise HistoricalPointValidationError(
                f"Nazwa obiektu zawiera niedozwolone znaki: {self.object_name!r}"
            )
        if len(self.display_name) > MAX_DISPLAY_NAME_LENGTH:
            raise HistoricalPointValidationError(
                f"Nazwa wyświetlana jest za długa (max {MAX_DISPLAY_NAME_LENGTH})."
            )
        if len(self.description) > MAX_DESCRIPTION_LENGTH:
            raise HistoricalPointValidationError(
                f"Opis jest za długi (max {MAX_DESCRIPTION_LENGTH} znaków)."
            )
        if len(self.source_note) > MAX_SOURCE_NOTE_LENGTH:
            raise HistoricalPointValidationError(
                f"Notatka źródłowa jest za długa (max {MAX_SOURCE_NOTE_LENGTH} znaków)."
            )
        if len(self.photos) > MAX_PHOTOS_PER_POINT:
            raise HistoricalPointValidationError(
                f"Za dużo zdjęć (max {MAX_PHOTOS_PER_POINT})."
            )
        for idx, photo in enumerate(self.photos):
            filename = photo.get("filename", "")
            if not filename:
                raise HistoricalPointValidationError(
                    f"Zdjęcie #{idx + 1} nie ma nazwy pliku."
                )
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED_PHOTO_EXTENSIONS:
                raise HistoricalPointValidationError(
                    f"Zdjęcie '{filename}' ma niedozwolone rozszerzenie. "
                    f"Dozwolone: {sorted(ALLOWED_PHOTO_EXTENSIONS)}"
                )
            caption = photo.get("caption", "")
            if len(caption) > MAX_CAPTION_LENGTH:
                raise HistoricalPointValidationError(
                    f"Podpis zdjęcia '{filename}' jest za długi (max {MAX_CAPTION_LENGTH})."
                )


# ============================================================================
# Ścieżki
# ============================================================================


def get_points_file_path(location_name: str) -> Path:
    """Zwraca ścieżkę do pliku ``historical_points.json`` miejscowości."""
    return location_data_dir(location_name) / FILENAME


def get_parcels_data_path(location_name: str) -> Path:
    """Zwraca ścieżkę do ``parcels_data.json`` miejscowości."""
    return location_data_dir(location_name) / "parcels_data.json"


def get_history_photos_dir(location_name: str) -> Path:
    """Zwraca ścieżkę do katalogu ze zdjęciami historycznymi."""
    return location_data_dir(location_name) / HISTORY_PHOTOS_SUBDIR


def get_point_photos_dir(location_name: str) -> Path:
    """Zwraca ścieżkę do katalogu ze zdjęciami markerów (punktów historycznych).

    Osobny folder od galerii (``history_photos/``) - dzięki temu użytkownik
    nie musi przeglądać wszystkich zdjęć miejscowości żeby znaleźć plik
    do markera. Patrz: ``POINT_PHOTOS_SUBDIR``.
    """
    return location_data_dir(location_name) / POINT_PHOTOS_SUBDIR


# ============================================================================
# Operacje I/O
# ============================================================================


def load_historical_points(location_name: str) -> List[HistoricalPoint]:
    """Czyta ``historical_points.json`` i zwraca listę punktów.

    Brak pliku -> pusta lista (normalny stan dla nowej miejscowości).
    Błąd odczytu / nieprawidłowy JSON -> log warning, pusta lista.
    """
    path = get_points_file_path(location_name)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Nie można odczytać %s (%s) - zwracam pustą listę", path, exc
        )
        return []
    if not isinstance(data, dict):
        return []
    raw_points = data.get("points", [])
    if not isinstance(raw_points, list):
        return []
    result: List[HistoricalPoint] = []
    for raw in raw_points:
        if not isinstance(raw, dict):
            continue
        point = HistoricalPoint.from_dict(raw)
        try:
            point.validate()
        except HistoricalPointValidationError as exc:
            logger.warning("Pominięto nieprawidłowy wpis w %s: %s", path, exc)
            continue
        result.append(point)
    return result


def save_historical_points(
    location_name: str, points: List[HistoricalPoint]
) -> None:
    """Zapisuje listę punktów do ``historical_points.json`` (tworzy folder jeśli trzeba).

    Waliduje każdy punkt przed zapisem - przy pierwszym błędzie rzuca
    ``HistoricalPointValidationError`` i NIE zapisuje nic.
    """
    if not location_name or not location_name.strip():
        raise HistoricalPointValidationError("Nazwa miejscowości jest wymagana.")

    seen_objects: Dict[str, int] = {}
    for idx, point in enumerate(points):
        point.validate()
        # Identyfikujemy po object_name - jeden obiekt specjalny = jeden punkt
        if point.object_name in seen_objects:
            raise HistoricalPointValidationError(
                f"Duplikat obiektu '{point.object_name}' w punktach "
                f"(pozycje {seen_objects[point.object_name] + 1} i {idx + 1})."
            )
        seen_objects[point.object_name] = idx

    folder = location_data_dir(location_name)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / FILENAME
    payload = {
        "version": 1,
        "points": [p.to_dict() for p in points],
    }
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    logger.info("Zapisano %d punktów historycznych w %s", len(points), path)


# ============================================================================
# Listy pomocnicze (combobox / file picker w dialogu)
# ============================================================================


@dataclass(frozen=True)
class SpecialObject:
    """Obiekt specjalny z ``parcels_data.json`` - kandydat na punkt historyczny."""

    object_name: str  # np. "dworzec kolejowy"
    key: str  # np. "dworzec kolejowy_obiekt_specjalny"
    lat: float
    lng: float


def list_special_objects(location_name: str) -> List[SpecialObject]:
    """Zwraca listę obiektów z ``parcels_data.json`` o kategorii ``obiekt_specjalny``.

    Iteruje po kluczach w formacie ``<nazwa>_<kategoria>`` i filtruje po
    kategorii. Pomija wpisy z nieprawidłową geometrią.
    """
    path = get_parcels_data_path(location_name)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fp:
            parcels = json.load(fp)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Nie można odczytać %s: %s", path, exc)
        return []
    if not isinstance(parcels, dict):
        return []

    result: List[SpecialObject] = []
    for key, props in parcels.items():
        if not isinstance(props, dict):
            continue
        if props.get("kategoria") != "obiekt_specjalny":
            continue
        if not key.endswith(SPECIAL_OBJECT_SUFFIX):
            continue
        name = key[: -len(SPECIAL_OBJECT_SUFFIX)]
        geom = props.get("geometria")
        if not isinstance(geom, list) or len(geom) != 2:
            continue
        try:
            lat, lng = float(geom[0]), float(geom[1])
        except (TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        result.append(SpecialObject(object_name=name, key=key, lat=lat, lng=lng))
    # Sortujemy po nazwie dla powtarzalności UI
    result.sort(key=lambda obj: obj.object_name)
    return result


def list_history_photos(location_name: str) -> List[str]:
    """Zwraca listę plików graficznych w katalogu ``history_photos/``.

    Zwraca same nazwy plików (nie pełne ścieżki). Filtruje po dozwolonych
    rozszerzeniach - dzięki temu UI nie proponuje plików .DS_Store itp.
    """
    return _list_photos_in_dir(get_history_photos_dir(location_name))


def list_point_photos(location_name: str) -> List[str]:
    """Zwraca listę plików graficznych w katalogu ``point_photos/``.

    Osobna lista od galerii - tu są pliki przypisane do markerów na mapie
    (punktów historycznych). UI edytora pokazuje je w lewym panelu zakładki
    "Punkty historyczne" (patrz: ``add_edit_location_dialog._refresh_hp_photo_files``).
    """
    return _list_photos_in_dir(get_point_photos_dir(location_name))


def _list_photos_in_dir(photos_dir: Path) -> List[str]:
    """Wewnętrzny helper - listuje pliki graficzne w danym katalogu."""
    if not photos_dir.exists() or not photos_dir.is_dir():
        return []
    result: List[str] = []
    for entry in photos_dir.iterdir():
        if not entry.is_file():
            continue
        ext = entry.suffix.lower()
        if ext not in ALLOWED_PHOTO_EXTENSIONS:
            continue
        result.append(entry.name)
    result.sort()
    return result
