"""Router diagnostyki danych - panel jakosci z TODO.md.

Endpoint ``GET /api/admin/diagnostics`` zwraca 9 metryk jakosci (parcels
without owners, owners without parcels, itd.). Chroniony przez admin auth.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..auth import admin_required
from ..services.diagnostics_service import compute_diagnostics


router = APIRouter(prefix="/api/admin", tags=["admin-diagnostics"])


@router.get("/diagnostics")
async def get_diagnostics(
    db: AsyncSession = Depends(get_db),
    _admin: bool = Depends(admin_required),
):
    """Zwraca 9 metryk jakosci danych + sample (max 10) dla kazdej.

    Metryki:
        - parcels_without_owners
        - owners_without_parcels
        - protocols_without_genealogy
        - people_without_parents
        - people_without_birth_date
        - people_without_death_date
        - parcels_without_category
        - owners_without_house_number
        - parcel_owner_links (czysty licznik)
        - incomplete_records (agregat)
    """
    return await compute_diagnostics(db)
