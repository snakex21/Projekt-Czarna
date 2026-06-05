"""Router statystyk — deleguje obliczenia do services/stats_service.py."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db, fetch_all
from ..services.stats_service import compute_all_stats

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Zwraca kompleksowe statystyki."""
    return await compute_all_stats(db)


@router.get("/stats/rankings")
async def get_rankings(db: AsyncSession = Depends(get_db)):
    """Zwraca rankingi wlascicieli wg liczby dzialek."""
    ranking = await fetch_all(db, """
        SELECT w.nazwa_wlasciciela, w.unikalny_klucz, w.numer_protokolu,
               COUNT(dw.obiekt_id) as plot_count
        FROM wlasciciele w
        JOIN dzialki_wlasciciele dw ON w.id = dw.wlasciciel_id
        GROUP BY w.id, w.nazwa_wlasciciela, w.unikalny_klucz, w.numer_protokolu
        HAVING COUNT(dw.obiekt_id) > 0
        ORDER BY plot_count DESC
        LIMIT 20
    """)
    return {"ranking": ranking}
