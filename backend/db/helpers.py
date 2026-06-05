"""Wspolny wrapper dla asynchronicznych zapytan SQLAlchemy.
Eliminuje duplikacje _fetch_one / _fetch_all / _execute z routerow.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def fetch_one(db: AsyncSession, query: str, params: dict = None) -> dict | None:
    """Wykonuje SELECT zwracajacy max 1 wiersz."""
    result = await db.execute(text(query), params or {})
    row = result.fetchone()
    if row:
        return dict(row._mapping)
    return None


async def fetch_all(db: AsyncSession, query: str, params: dict = None) -> list[dict]:
    """Wykonuje SELECT zwracajacy liste wierszy."""
    result = await db.execute(text(query), params or {})
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def execute(db: AsyncSession, query: str, params: dict = None) -> int:
    """Wykonuje INSERT/UPDATE/DELETE, zwraca lastrowid."""
    result = await db.execute(text(query), params or {})
    await db.flush()
    return result.lastrowid or 0
