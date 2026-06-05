"""Testy integracyjne endpointu /api/historical-points.

Weryfikują:
- zwraca FeatureCollection nawet gdy brak pliku historical_points.json,
- pomija wpisy bez pasującego obiektu specjalnego w parcels_data.json,
- ucina za długie pola i normalizuje nazwy plików zdjęć,
- nie wpada w 404 gdy brak pliku metadanych.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.routers import historical_points as router_module


@pytest.fixture
def fake_location_dir(tmp_path, monkeypatch):
    """Podmienia katalog danych aktywnej miejscowości na katalog tymczasowy.

    Tworzy minimalne ``parcels_data.json`` z dwoma obiektami specjalnymi
    i pusty ``history_photos/`` - wystarczające do testów endpointu.
    """
    parcels = {
        "dworzec kolejowy_obiekt_specjalny": {
            "kategoria": "obiekt_specjalny",
            # parcels_data.json: [lat, lng] -> GeoJSON: [lng, lat]
            "geometria": [50.060552057627206, 21.248808587842237],
        },
        "dróżnica_obiekt_specjalny": {
            "kategoria": "obiekt_specjalny",
            "geometria": [50.061499648585745, 21.24641022624839],
        },
        # Inna kategoria - powinna być ignorowana
        "krzyż_kapliczka": {
            "kategoria": "kapliczka",
            "geometria": [50.07, 21.258],
        },
    }
    (tmp_path / "parcels_data.json").write_text(
        json.dumps(parcels, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (tmp_path / "history_photos").mkdir()

    monkeypatch.setattr(router_module, "_location_data_dir", lambda: tmp_path)
    return tmp_path


def test_returns_empty_feature_collection_when_no_file(fake_location_dir, client):
    """Gdy brak pliku historical_points.json, zwraca pustą kolekcję (nie 404)."""
    resp = client.get("/api/historical-points")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"] == []


def test_returns_feature_with_geometry_from_parcels(fake_location_dir, client):
    """Punkt z poprawnym object_name dostaje geometrię z parcels_data.json."""
    (fake_location_dir / "historical_points.json").write_text(
        json.dumps({
            "points": [
                {
                    "object_name": "dworzec kolejowy",
                    "display_name": "Dworzec kolejowy w Czarnej",
                    "description": "Budynek z 1905 r.",
                    "source_note": "Archiwum w Rzeszowie, sygn. 123",
                    "photos": [{"filename": "dworzec_czarna.png", "caption": "Widok 1935"}],
                }
            ]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    resp = client.get("/api/historical-points")
    assert resp.status_code == 200
    features = resp.json()["features"]
    assert len(features) == 1
    feat = features[0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    assert feat["geometry"]["coordinates"] == [21.248808587842237, 50.060552057627206]  # [lng, lat]
    props = feat["properties"]
    assert props["object_name"] == "dworzec kolejowy"
    assert props["display_name"] == "Dworzec kolejowy w Czarnej"
    assert props["description"] == "Budynek z 1905 r."
    assert props["source_note"] == "Archiwum w Rzeszowie, sygn. 123"
    assert props["photos"] == [{"filename": "dworzec_czarna.png", "caption": "Widok 1935"}]


def test_skips_point_without_matching_object(fake_location_dir, client):
    """Wpis bez obiektu specjalnego w parcels_data.json jest pomijany."""
    (fake_location_dir / "historical_points.json").write_text(
        json.dumps({
            "points": [
                {"object_name": "dworzec kolejowy", "description": "OK"},
                {"object_name": "nieistniejący obiekt", "description": "Pominięty"},
            ]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    resp = client.get("/api/historical-points")
    assert resp.status_code == 200
    features = resp.json()["features"]
    assert len(features) == 1
    assert features[0]["properties"]["object_name"] == "dworzec kolejowy"


def test_ignores_non_special_objects(fake_location_dir, client):
    """Punkt wskazujący na obiekt z innej kategorii (np. kapliczka) jest pomijany."""
    (fake_location_dir / "historical_points.json").write_text(
        json.dumps({
            "points": [
                {"object_name": "krzyż", "description": "Nie specjalny"},
            ]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    resp = client.get("/api/historical-points")
    assert resp.status_code == 200
    assert resp.json()["features"] == []


def test_truncates_long_fields(fake_location_dir, client):
    """Za długie opisy/nazwy są obcinane zgodnie z MAX_*_LENGTH."""
    long_desc = "a" * 6000
    long_source = "b" * 1500
    long_caption = "c" * 800
    (fake_location_dir / "historical_points.json").write_text(
        json.dumps({
            "points": [{
                "object_name": "dworzec kolejowy",
                "display_name": "x" * 500,
                "description": long_desc,
                "source_note": long_source,
                "photos": [{"filename": "ok.png", "caption": long_caption}],
            }]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    resp = client.get("/api/historical-points")
    assert resp.status_code == 200
    props = resp.json()["features"][0]["properties"]
    assert len(props["description"]) == 5000  # MAX_DESCRIPTION_LENGTH
    assert len(props["source_note"]) == 1000   # MAX_SOURCE_NOTE_LENGTH
    assert len(props["display_name"]) == 200   # MAX_DISPLAY_NAME_LENGTH
    assert len(props["photos"][0]["caption"]) == 500  # MAX_CAPTION_LENGTH


def test_rejects_disallowed_photo_extensions(fake_location_dir, client):
    """Zdjęcia z niedozwolonym rozszerzeniem są odrzucane."""
    (fake_location_dir / "historical_points.json").write_text(
        json.dumps({
            "points": [{
                "object_name": "dworzec kolejowy",
                "photos": [
                    {"filename": "ok.png", "caption": "OK"},
                    {"filename": "evil.exe", "caption": "Odrzucone"},
                    {"filename": "noext", "caption": "Odrzucone"},
                ],
            }]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    resp = client.get("/api/historical-points")
    photos = resp.json()["features"][0]["properties"]["photos"]
    assert photos == [{"filename": "ok.png", "caption": "OK"}]


def test_sanitizes_photo_path_traversal(fake_location_dir, client):
    """Ścieżki w filename są obcinane do samej nazwy pliku (anty path traversal)."""
    (fake_location_dir / "historical_points.json").write_text(
        json.dumps({
            "points": [{
                "object_name": "dworzec kolejowy",
                "photos": [{"filename": "../../../etc/passwd.png", "caption": "x"}],
            }]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    resp = client.get("/api/historical-points")
    photo = resp.json()["features"][0]["properties"]["photos"][0]
    assert photo["filename"] == "passwd.png"


def test_handles_corrupted_json_gracefully(fake_location_dir, client):
    """Wadliwy JSON w historical_points.json nie powoduje 500 - zwraca pustą listę."""
    (fake_location_dir / "historical_points.json").write_text(
        "{to nie jest json",
        encoding="utf-8",
    )
    resp = client.get("/api/historical-points")
    assert resp.status_code == 200
    assert resp.json()["features"] == []


def test_missing_parcels_data_returns_empty(fake_location_dir, client, monkeypatch):
    """Gdy brak parcels_data.json, zwraca pustą kolekcję (nie 500)."""
    # Ukrywamy parcels_data.json - symulujemy brak pliku
    (fake_location_dir / "parcels_data.json").unlink()
    (fake_location_dir / "historical_points.json").write_text(
        json.dumps({"points": [{"object_name": "x", "description": "y"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    resp = client.get("/api/historical-points")
    assert resp.status_code == 200
    assert resp.json()["features"] == []
