"""Logika obiektów geograficznych dla panelu admina."""

from sqlalchemy.ext.asyncio import AsyncSession

from ..db import fetch_all


async def list_objects_with_owner_links(db: AsyncSession) -> list[dict]:
    """Zwraca obiekty z informacją o przypisanych właścicielach/protokołach."""
    rows = await fetch_all(db, """
        SELECT
            o.*,
            dw.typ_posiadania,
            w.id AS owner_db_id,
            w.unikalny_klucz AS owner_key,
            w.nazwa_wlasciciela AS owner_name,
            w.numer_protokolu AS protocol_number
        FROM obiekty_geograficzne o
        LEFT JOIN dzialki_wlasciciele dw ON dw.obiekt_id = o.id
        LEFT JOIN wlasciciele w ON w.id = dw.wlasciciel_id
        ORDER BY o.id, w.numer_protokolu, w.nazwa_wlasciciela
    """)

    objects_by_id: dict[int, dict] = {}
    seen_links: dict[int, set[tuple]] = {}

    for row in rows:
        object_id = row["id"]
        if object_id not in objects_by_id:
            obj = {
                key: value
                for key, value in row.items()
                if key not in {
                    "typ_posiadania", "owner_db_id", "owner_key",
                    "owner_name", "protocol_number",
                }
            }
            obj["assigned_owners"] = []
            obj["assigned_count"] = 0
            obj["is_linked"] = False
            obj["status"] = "Nieprzypisany"
            objects_by_id[object_id] = obj
            seen_links[object_id] = set()

        if row.get("owner_db_id") is None:
            continue

        link_key = (
            row.get("owner_db_id"),
            row.get("owner_key"),
            row.get("typ_posiadania"),
        )
        if link_key in seen_links[object_id]:
            continue
        seen_links[object_id].add(link_key)

        objects_by_id[object_id]["assigned_owners"].append({
            "id": row.get("owner_db_id"),
            "owner_id": row.get("owner_key"),
            "unikalny_klucz": row.get("owner_key"),
            "name": row.get("owner_name") or row.get("owner_key") or "",
            "nazwa_wlasciciela": row.get("owner_name") or "",
            "protocol_number": row.get("protocol_number"),
            "numer_protokolu": row.get("protocol_number"),
            "typ_posiadania": row.get("typ_posiadania"),
            "protocol_url": (
                f"../wlasciciele/protokol.html?ownerId={row.get('owner_key')}"
                if row.get("owner_key") else None
            ),
        })

    for obj in objects_by_id.values():
        obj["assigned_count"] = len(obj["assigned_owners"])
        obj["is_linked"] = obj["assigned_count"] > 0
        obj["status"] = "Przypisany" if obj["is_linked"] else "Nieprzypisany"

    return list(objects_by_id.values())
