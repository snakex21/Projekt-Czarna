"""Router mapy - GeoJSON, dzialki, obiekty geograficzne."""
import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..db import get_db, fetch_one, fetch_all
from ..config import DB_ENGINE

router = APIRouter(prefix="/api", tags=["map"])


@router.get("/dzialki")
async def get_parcels(db: AsyncSession = Depends(get_db)):
    """Zwraca wszystkie obiekty geograficzne w formacie GeoJSON (PG: ST_AsGeoJSON, SQLite: TEXT)."""
    if DB_ENGINE == "postgresql":
        query = """
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(f.feature) FILTER (WHERE f.feature IS NOT NULL), '[]'::json)
            ) AS geojson
            FROM (
                SELECT json_build_object(
                    'type', 'Feature',
                    'id', o.id,
                    'geometry', ST_AsGeoJSON(o.geometria)::json,
                    'properties', json_build_object(
                        'numer_obiektu', o.nazwa_lub_numer,
                        'kategoria', o.kategoria,
                        'wlasciciele', (
                            SELECT COALESCE(json_agg(ow) FILTER (WHERE ow IS NOT NULL), '[]'::json)
                            FROM (
                                SELECT DISTINCT ON (w.id) json_build_object(
                                    'id', w.id, 'unikalny_klucz', w.unikalny_klucz,
                                    'nazwa', w.nazwa_wlasciciela, 'typ_posiadania', dw.typ_posiadania
                                ) AS ow
                                FROM wlasciciele w
                                JOIN dzialki_wlasciciele dw ON w.id = dw.wlasciciel_id
                                WHERE dw.obiekt_id = o.id
                            ) sub
                        )
                    )
                ) AS feature
                FROM obiekty_geograficzne o
                WHERE o.geometria IS NOT NULL
            ) f;
        """
    else:
        query = """
            SELECT json_object(
                'type', 'FeatureCollection',
                'features', COALESCE(
                    (SELECT json_group_array(
                        json_object(
                            'type', 'Feature',
                            'id', o.id,
                            'geometry', json(o.geometria),
                            'properties', json_object(
                                'numer_obiektu', o.nazwa_lub_numer,
                                'kategoria', o.kategoria,
                                'wlasciciele', (
                                    SELECT COALESCE(json_group_array(DISTINCT
                                        json_object(
                                            'id', w.id, 'unikalny_klucz', w.unikalny_klucz,
                                            'nazwa', w.nazwa_wlasciciela, 'typ_posiadania', dw.typ_posiadania
                                        )
                                    ), '[]')
                                    FROM wlasciciele w
                                    JOIN dzialki_wlasciciele dw ON w.id = dw.wlasciciel_id
                                    WHERE dw.obiekt_id = o.id
                                )
                            )
                        )
                    ) FROM obiekty_geograficzne o WHERE o.geometria IS NOT NULL),
                    '[]'
                )
            ) AS geojson;
        """

    result = await fetch_one(db, query)
    if result and result.get("geojson"):
        geojson = result["geojson"]
        if isinstance(geojson, str):
            try:
                return json.loads(geojson)
            except json.JSONDecodeError:
                return {"type": "FeatureCollection", "features": []}
        return geojson
    return {"type": "FeatureCollection", "features": []}


@router.get("/map-config")
async def get_map_config(db: AsyncSession = Depends(get_db)):
    """Zwraca konfiguracje mapy (kalibracja, widok domyslny)."""

    def parse_config_value(value, fallback):
        if value is None:
            return fallback
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return fallback
        return fallback

    default_calibration = {
        "sw": {"lat": 50.0445232994271194, "lng": 21.2118218969993393},
        "ne": {"lat": 50.0766374787729518, "lng": 21.2672168223566409}
    }
    default_map_defaults = {
        "center": {"lat": 50.0605803891, "lng": 21.2395193597},
        "zoom": 14
    }

    try:
        rows = await fetch_all(db, "SELECT klucz, wartosc FROM konfiguracja_systemu")
        config_data = {row["klucz"]: row["wartosc"] for row in rows}
    except Exception:
        config_data = {}

    return {
        "calibration": parse_config_value(config_data.get("map_calibration"), default_calibration),
        "defaults": parse_config_value(config_data.get("map_defaults"), default_map_defaults),
        "historical_map_url": "/location_map"
    }
