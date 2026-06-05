"""Testy serwisu historical_points_service.

Testują czystą logikę (bez Tkinter) - walidacja, I/O, parsowanie
parcels_data.json. Każdy test działa na własnym katalogu tymczasowym
``data/locations/<losowa>/`` - nie dotyka prawdziwych danych.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from launcher.services import historical_points_service as svc
from launcher.services.historical_points_service import (
    ALLOWED_PHOTO_EXTENSIONS,
    FILENAME,
    HistoricalPoint,
    HistoricalPointValidationError,
    SpecialObject,
    list_history_photos,
    list_point_photos,
    list_special_objects,
    load_historical_points,
    save_historical_points,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def location_name(request) -> str:
    """Unikalna nazwa miejscowości dla każdego testu (izolacja I/O)."""
    return f"test_loc_{request.node.name}"


@pytest.fixture
def location_data_dir_path(tmp_path, monkeypatch, location_name):
    """Mockujemy location_data_dir żeby pisać do tmp_path/<location_name>."""
    target = tmp_path / location_name

    def fake_dir(name: str) -> Path:
        if name != location_name:
            raise AssertionError(
                f"Test używa lokalizacji {location_name!r}, "
                f"ale serwis zażądał {name!r}"
            )
        return target

    monkeypatch.setattr(svc, "location_data_dir", fake_dir)
    return target


def _write_parcels(folder: Path, parcels: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "parcels_data.json").write_text(
        json.dumps(parcels, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_history_photos(folder: Path, filenames: list) -> None:
    photos_dir = folder / "history_photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    for name in filenames:
        (photos_dir / name).write_bytes(b"\x89PNG\r\n\x1a\n")  # pusty PNG


# ============================================================================
# HistoricalPoint - walidacja
# ============================================================================


class TestHistoricalPointValidation:
    def test_minimal_valid_point(self):
        point = HistoricalPoint(object_name="dworzec kolejowy")
        point.validate()  # nie rzuca

    def test_missing_object_name_raises(self):
        point = HistoricalPoint(object_name="")
        with pytest.raises(HistoricalPointValidationError, match="object_name"):
            point.validate()

    def test_whitespace_only_object_name_raises(self):
        point = HistoricalPoint(object_name="   ")
        with pytest.raises(HistoricalPointValidationError, match="object_name"):
            point.validate()

    def test_invalid_chars_in_object_name_raises(self):
        for bad in ["a/b", "a\\b", "a:b", 'a"b', "a|b", "a?b", "a*b", "a\x00b"]:
            point = HistoricalPoint(object_name=bad)
            with pytest.raises(HistoricalPointValidationError, match="niedozwolone"):
                point.validate()

    def test_display_name_too_long_raises(self):
        point = HistoricalPoint(object_name="x", display_name="x" * 201)
        with pytest.raises(HistoricalPointValidationError, match="Nazwa wyświetlana"):
            point.validate()

    def test_description_too_long_raises(self):
        point = HistoricalPoint(object_name="x", description="x" * 5001)
        with pytest.raises(HistoricalPointValidationError, match="Opis jest za długi"):
            point.validate()

    def test_source_note_too_long_raises(self):
        point = HistoricalPoint(object_name="x", source_note="x" * 1001)
        with pytest.raises(HistoricalPointValidationError, match="Notatka źródłowa"):
            point.validate()

    def test_photo_without_filename_raises(self):
        point = HistoricalPoint(
            object_name="x", photos=[{"filename": "", "caption": "x"}]
        )
        with pytest.raises(HistoricalPointValidationError, match="nazwy pliku"):
            point.validate()

    def test_photo_with_bad_extension_raises(self):
        point = HistoricalPoint(
            object_name="x", photos=[{"filename": "evil.exe", "caption": "x"}]
        )
        with pytest.raises(HistoricalPointValidationError, match="rozszerzenie"):
            point.validate()

    def test_too_many_photos_raises(self):
        photos = [{"filename": f"f{i}.png", "caption": "x"} for i in range(21)]
        point = HistoricalPoint(object_name="x", photos=photos)
        with pytest.raises(HistoricalPointValidationError, match="max"):
            point.validate()

    def test_caption_too_long_raises(self):
        point = HistoricalPoint(
            object_name="x",
            photos=[{"filename": "ok.png", "caption": "x" * 501}],
        )
        with pytest.raises(HistoricalPointValidationError, match="Podpis zdjęcia"):
            point.validate()

    def test_to_dict_roundtrip(self):
        original = HistoricalPoint(
            object_name="dworzec kolejowy",
            display_name="Dworzec",
            description="Opis",
            source_note="Źródło",
            photos=[{"filename": "a.png", "caption": "A"}],
        )
        reconstructed = HistoricalPoint.from_dict(original.to_dict())
        assert reconstructed.object_name == original.object_name
        assert reconstructed.display_name == original.display_name
        assert reconstructed.description == original.description
        assert reconstructed.source_note == original.source_note
        assert reconstructed.photos == original.photos


# ============================================================================
# I/O - load / save
# ============================================================================


class TestLoadHistoricalPoints:
    def test_no_file_returns_empty_list(self, location_data_dir_path, location_name):
        # Brak pliku - normalny stan nowej miejscowości
        result = load_historical_points(location_name)
        assert result == []

    def test_corrupted_json_returns_empty(self, location_data_dir_path, location_name):
        location_data_dir_path.mkdir(parents=True, exist_ok=True)
        (location_data_dir_path / FILENAME).write_text("{to nie jest json", encoding="utf-8")
        result = load_historical_points(location_name)
        assert result == []

    def test_invalid_root_structure_returns_empty(
        self, location_data_dir_path, location_name
    ):
        location_data_dir_path.mkdir(parents=True, exist_ok=True)
        (location_data_dir_path / FILENAME).write_text('"string zamiast dict"', encoding="utf-8")
        result = load_historical_points(location_name)
        assert result == []

    def test_skips_invalid_entries(self, location_data_dir_path, location_name):
        location_data_dir_path.mkdir(parents=True, exist_ok=True)
        (location_data_dir_path / FILENAME).write_text(
            json.dumps(
                {
                    "points": [
                        {"object_name": "ok", "description": "dobra"},
                        {"description": "brak object_name"},  # invalid -> skip
                        "string zamiast dict",  # invalid -> skip
                        {"object_name": "drugie_ok"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = load_historical_points(location_name)
        assert len(result) == 2
        assert [p.object_name for p in result] == ["ok", "drugie_ok"]


class TestSaveHistoricalPoints:
    def test_save_creates_file_and_directory(
        self, tmp_path, location_data_dir_path, location_name
    ):
        points = [HistoricalPoint(object_name="dworzec kolejowy", display_name="Dworzec")]
        save_historical_points(location_name, points)
        path = location_data_dir_path / FILENAME
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert len(data["points"]) == 1
        assert data["points"][0]["object_name"] == "dworzec kolejowy"
        assert data["points"][0]["display_name"] == "Dworzec"

    def test_save_preserves_unicode(self, location_data_dir_path, location_name):
        points = [
            HistoricalPoint(
                object_name="dróżnica",
                description="Opis z ąćęłńóśźż ĄĆĘŁŃÓŚŹŻ",
            )
        ]
        save_historical_points(location_name, points)
        path = location_data_dir_path / FILENAME
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "ąćęłńóśźż" in data["points"][0]["description"]

    def test_save_rejects_duplicate_object_name(
        self, location_data_dir_path, location_name
    ):
        points = [
            HistoricalPoint(object_name="dworzec"),
            HistoricalPoint(object_name="dworzec"),
        ]
        with pytest.raises(HistoricalPointValidationError, match="Duplikat"):
            save_historical_points(location_name, points)

    def test_save_rejects_empty_location_name(self, location_data_dir_path):
        with pytest.raises(HistoricalPointValidationError, match="Nazwa miejscowości"):
            save_historical_points("", [HistoricalPoint(object_name="x")])

    def test_save_rejects_invalid_point(
        self, location_data_dir_path, location_name
    ):
        points = [HistoricalPoint(object_name="ok"), HistoricalPoint(object_name="")]
        with pytest.raises(HistoricalPointValidationError):
            save_historical_points(location_name, points)

    def test_save_does_not_overwrite_on_validation_error(
        self, location_data_dir_path, location_name
    ):
        # Najpierw zapisujemy prawidłowe dane
        location_data_dir_path.mkdir(parents=True, exist_ok=True)
        path = location_data_dir_path / FILENAME
        original_data = {"version": 1, "points": [{"object_name": "istniejacy"}]}
        path.write_text(json.dumps(original_data), encoding="utf-8")

        # Próba nadpisania z błędnych danych NIE zmienia pliku
        bad_points = [HistoricalPoint(object_name="ok"), HistoricalPoint(object_name="")]
        with pytest.raises(HistoricalPointValidationError):
            save_historical_points(location_name, bad_points)
        assert json.loads(path.read_text(encoding="utf-8")) == original_data


# ============================================================================
# list_special_objects
# ============================================================================


class TestListSpecialObjects:
    def test_no_parcels_file_returns_empty(self, location_data_dir_path, location_name):
        result = list_special_objects(location_name)
        assert result == []

    def test_filters_only_obiekt_specjalny(self, location_data_dir_path, location_name):
        _write_parcels(
            location_data_dir_path,
            {
                "dworzec kolejowy_obiekt_specjalny": {
                    "kategoria": "obiekt_specjalny",
                    "geometria": [50.0, 21.0],
                },
                "krzyż_kapliczka": {
                    "kategoria": "kapliczka",
                    "geometria": [50.1, 21.1],
                },
                "budynek_budynki": {
                    "kategoria": "budynek",
                    "geometria": [50.2, 21.2],
                },
            },
        )
        result = list_special_objects(location_name)
        assert len(result) == 1
        assert result[0].object_name == "dworzec kolejowy"
        assert result[0].lat == 50.0
        assert result[0].lng == 21.0

    def test_returns_sorted_by_name(self, location_data_dir_path, location_name):
        _write_parcels(
            location_data_dir_path,
            {
                "zamek_obiekt_specjalny": {"kategoria": "obiekt_specjalny", "geometria": [50.0, 21.0]},
                "dworzec kolejowy_obiekt_specjalny": {"kategoria": "obiekt_specjalny", "geometria": [50.1, 21.1]},
                "kapliczka_obiekt_specjalny": {"kategoria": "obiekt_specjalny", "geometria": [50.2, 21.2]},
            },
        )
        result = list_special_objects(location_name)
        names = [obj.object_name for obj in result]
        assert names == sorted(names)

    def test_skips_invalid_geometry(self, location_data_dir_path, location_name):
        _write_parcels(
            location_data_dir_path,
            {
                "ok_obiekt_specjalny": {
                    "kategoria": "obiekt_specjalny",
                    "geometria": [50.0, 21.0],
                },
                "zly_format_obiekt_specjalny": {
                    "kategoria": "obiekt_specjalny",
                    "geometria": [50.0],  # tylko jeden element
                },
                "zly_string_obiekt_specjalny": {
                    "kategoria": "obiekt_specjalny",
                    "geometria": "nie lista",
                },
                "poza_zakresem_obiekt_specjalny": {
                    "kategoria": "obiekt_specjalny",
                    "geometria": [200.0, 21.0],  # lat poza zakresem
                },
            },
        )
        result = list_special_objects(location_name)
        assert [obj.object_name for obj in result] == ["ok"]

    def test_skips_key_without_suffix(self, location_data_dir_path, location_name):
        _write_parcels(
            location_data_dir_path,
            {
                "specjalny bez sufiksu": {
                    "kategoria": "obiekt_specjalny",
                    "geometria": [50.0, 21.0],
                },
                "wlasciwy_obiekt_specjalny": {
                    "kategoria": "obiekt_specjalny",
                    "geometria": [50.1, 21.1],
                },
            },
        )
        result = list_special_objects(location_name)
        assert [obj.object_name for obj in result] == ["wlasciwy"]


# ============================================================================
# list_history_photos
# ============================================================================


class TestListHistoryPhotos:
    def test_no_dir_returns_empty(self, location_data_dir_path, location_name):
        result = list_history_photos(location_name)
        assert result == []

    def test_returns_only_allowed_extensions(
        self, location_data_dir_path, location_name
    ):
        _write_history_photos(
            location_data_dir_path,
            [
                "a.png",
                "b.JPG",   # case-insensitive
                "c.webp",
                "d.txt",   # nie dozwolone
                "e.exe",   # nie dozwolone
                ".DS_Store",  # nie dozwolone
            ],
        )
        result = list_history_photos(location_name)
        assert result == ["a.png", "b.JPG", "c.webp"]

    def test_returns_sorted(self, location_data_dir_path, location_name):
        _write_history_photos(location_data_dir_path, ["z.png", "a.png", "m.png"])
        result = list_history_photos(location_name)
        assert result == ["a.png", "m.png", "z.png"]


# ============================================================================
# Ścieżki
# ============================================================================


class TestPaths:
    def test_get_points_file_path_uses_location_data_dir(self, monkeypatch):
        captured = {}

        def fake_dir(name):
            captured["name"] = name
            return Path("/tmp/xxx")

        monkeypatch.setattr(svc, "location_data_dir", fake_dir)
        path = svc.get_points_file_path("Czarna")
        assert captured["name"] == "Czarna"
        assert path.name == FILENAME
        assert "xxx" in str(path)

    def test_get_history_photos_dir_uses_subdir(self, monkeypatch):
        monkeypatch.setattr(svc, "location_data_dir", lambda n: Path(f"/data/{n}"))
        path = svc.get_history_photos_dir("Foo")
        assert path == Path("/data/Foo/history_photos")

    def test_get_point_photos_dir_uses_separate_subdir(self, monkeypatch):
        """Folder zdjęć markerów jest OSOBNY od galerii (``point_photos``)."""
        monkeypatch.setattr(svc, "location_data_dir", lambda n: Path(f"/data/{n}"))
        path = svc.get_point_photos_dir("Foo")
        assert path == Path("/data/Foo/point_photos")
        # Anty-regresja: nie jest tym samym co galeria
        assert path != svc.get_history_photos_dir("Foo")


# ============================================================================
# list_point_photos (zdjęcia markerów - OSOBNY folder)
# ============================================================================


class TestListPointPhotos:
    def test_no_dir_returns_empty(self, location_data_dir_path, location_name):
        result = list_point_photos(location_name)
        assert result == []

    def test_returns_only_files_in_point_photos_subdir(
        self, location_data_dir_path, location_name
    ):
        """Pliki w ``history_photos/`` (galeria) nie są zwracane jako marker photos."""
        # Galeria: pliki które NIE powinny się pokazać
        _write_history_photos(
            location_data_dir_path,
            ["gallery1.png", "gallery2.jpg"],
        )
        # Marker photos: pliki które powinny się pokazać
        point_dir = location_data_dir_path / "point_photos"
        point_dir.mkdir()
        (point_dir / "dworzec.png").write_bytes(b"x")
        (point_dir / "kapliczka.jpg").write_bytes(b"y")
        result = list_point_photos(location_name)
        assert result == ["dworzec.png", "kapliczka.jpg"]
        # Galeria nie wycieka
        assert "gallery1.png" not in result
        assert "gallery2.jpg" not in result

    def test_filters_disallowed_extensions(
        self, location_data_dir_path, location_name
    ):
        point_dir = location_data_dir_path / "point_photos"
        point_dir.mkdir(parents=True, exist_ok=True)
        (point_dir / "good.png").write_bytes(b"x")
        (point_dir / "good.JPG").write_bytes(b"x")
        (point_dir / "bad.txt").write_bytes(b"x")
        (point_dir / "bad.exe").write_bytes(b"x")
        result = list_point_photos(location_name)
        assert result == ["good.JPG", "good.png"]  # sortowane

    def test_returns_sorted(self, location_data_dir_path, location_name):
        point_dir = location_data_dir_path / "point_photos"
        point_dir.mkdir(parents=True, exist_ok=True)
        for fn in ["z.png", "a.png", "m.png"]:
            (point_dir / fn).write_bytes(b"x")
        result = list_point_photos(location_name)
        assert result == ["a.png", "m.png", "z.png"]
