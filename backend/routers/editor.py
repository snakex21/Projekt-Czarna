"""Router do zapisu/edycji danych (edytor mapy, CRUD)."""
import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..db import get_db
from ..config import DB_ENGINE
from ..auth import admin_required
from ..core.schemas import FeatureCollectionIn

router = APIRouter(prefix="/api/dzialki", tags=["editor"])


@router.post("/save")
async def save_parcels(
    body: FeatureCollectionIn,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Zapisuje wszystkie dzialki (GeoJSON FeatureCollection). Wymaga autoryzacji."""
    saved = 0
    for feature in body.features:
        props = feature.properties
        geometry = feature.geometry or {}
        feature_id = feature.id

        numer = str(props.get("numer_obiektu", "") or "")[:255]
        kategoria = str(props.get("kategoria", "default") or "default")[:64]

        geom_json = json.dumps(geometry)

        if DB_ENGINE == "postgresql":
            query = """
                INSERT INTO obiekty_geograficzne (id, nazwa_lub_numer, kategoria, geometria)
                VALUES (:id, :numer, :kategoria, ST_GeomFromGeoJSON(:geom))
                ON CONFLICT (id) DO UPDATE SET
                    nazwa_lub_numer = :numer2,
                    kategoria = :kategoria2,
                    geometria = ST_GeomFromGeoJSON(:geom2)
            """
        else:
            query = """
                INSERT OR REPLACE INTO obiekty_geograficzne (id, nazwa_lub_numer, kategoria, geometria)
                VALUES (:id, :numer, :kategoria, :geom)
            """

        await db.execute(text(query), {
            "id": feature_id,
            "numer": numer,
            "numer2": numer,
            "kategoria": kategoria,
            "kategoria2": kategoria,
            "geom": geom_json,
            "geom2": geom_json,
        })
        saved += 1

    await db.commit()
    return {"status": "ok", "saved": saved}
