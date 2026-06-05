"""
Router panelu administracyjnego - CRUD dla wszystkich encji.
Zabezpieczony przez auth.admin_required na wszystkich mutujacych endpointach.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db, fetch_one, fetch_all, execute
from ..auth import admin_required
from ..services import admin_objects_service

router = APIRouter(prefix="/api/admin", tags=["admin"])

# === Dashboard / kontrakt z static/admin/admin.js ===
@router.get("/dashboard-stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Statystyki pulpitu admina.

    Frontend admin.js oczekuje plaskich pol total_owners / total_objects.
    Ten endpoint istnieje celowo jako kompatybilny alias dla /api/stats,
    ale bez zagniezdzonego payloadu (admin.js czyta bezposrednio data.total_*).
    """
    owners = await fetch_one(db, "SELECT COUNT(*) AS count FROM wlasciciele")
    objects = await fetch_one(db, "SELECT COUNT(*) AS count FROM obiekty_geograficzne")
    genealogy = await fetch_one(db, "SELECT COUNT(*) AS count FROM osoby_genealogia")
    demography = await fetch_one(db, "SELECT COUNT(*) AS count FROM demografia")
    return {
        "total_owners": owners["count"] if owners else 0,
        "total_objects": objects["count"] if objects else 0,
        "total_genealogy": genealogy["count"] if genealogy else 0,
        "total_demography": demography["count"] if demography else 0,
    }


# === Wlasciciele CRUD ===
@router.get("/wlasciciele")
async def list_wlasciciele(db: AsyncSession = Depends(get_db)):
    """Lista wszystkich wlascicieli (publiczne)."""
    rows = await fetch_all(db, "SELECT * FROM wlasciciele ORDER BY id")
    return rows


@router.post("/wlasciciele", status_code=201)
async def create_wlasciciel(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Tworzy nowego wlasciciela (wymaga auth)."""
    try:
        fields = []
        values = []
        params = {}
        for key in ["unikalny_klucz", "nazwa_wlasciciela", "numer_protokolu",
                     "numer_domu", "genealogia", "historia_wlasnosci", "uwagi",
                     "wspolwlasnosc", "powiazania_i_transakcje",
                     "interpretacja_i_wnioski", "data_protokolu", "miejsce_protokolu"]:
            if key in payload:
                fields.append(key)
                values.append(f":{key}")
                params[key] = payload[key]
        
        if not fields:
            raise HTTPException(status_code=400, detail="Brak danych")
        
        query = f"INSERT INTO wlasciciele ({', '.join(fields)}) VALUES ({', '.join(values)})"
        new_id = await execute(db, query, params)
        
        for typ, lista in [("rzeczywiste", payload.get("dzialki_rzeczywiste_ids", [])),
                            ("protokol", payload.get("dzialki_protokol_ids", []))]:
            for obiekt_id in lista:
                await execute(db,
                    "INSERT INTO dzialki_wlasciciele (obiekt_id, wlasciciel_id, typ_posiadania) VALUES (:oid, :wid, :typ)",
                    {"oid": obiekt_id, "wid": new_id, "typ": typ})
        
        return {"id": new_id, "status": "created"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wlasciciele/{wlasciciel_id}")
async def get_wlasciciel(wlasciciel_id: int, db: AsyncSession = Depends(get_db)):
    """Pobiera pojedynczego wlasciciela (publiczne)."""
    row = await fetch_one(db, "SELECT * FROM wlasciciele WHERE id = :id", {"id": wlasciciel_id})
    if not row:
        raise HTTPException(status_code=404, detail="Nie znaleziono")
    
    links = await fetch_all(db,
        "SELECT obiekt_id, typ_posiadania FROM dzialki_wlasciciele WHERE wlasciciel_id = :wid",
        {"wid": wlasciciel_id})
    row["dzialki_wszystkie"] = [{"id": l["obiekt_id"], "typ": l["typ_posiadania"]} for l in links]
    return row


@router.put("/wlasciciele/{wlasciciel_id}")
async def update_wlasciciel(
    wlasciciel_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Aktualizuje wlasciciela (wymaga auth)."""
    row = await fetch_one(db, "SELECT id FROM wlasciciele WHERE id = :id", {"id": wlasciciel_id})
    if not row:
        raise HTTPException(status_code=404, detail="Nie znaleziono")
    
    fields = []
    params = {"id": wlasciciel_id}
    for key in ["unikalny_klucz", "nazwa_wlasciciela", "numer_protokolu",
                 "numer_domu", "genealogia", "historia_wlasnosci", "uwagi",
                 "wspolwlasnosc", "powiazania_i_transakcje",
                 "interpretacja_i_wnioski", "data_protokolu", "miejsce_protokolu"]:
        if key in payload:
            fields.append(f"{key} = :{key}")
            params[key] = payload[key]
    
    if fields:
        await execute(db, f"UPDATE wlasciciele SET {', '.join(fields)} WHERE id = :id", params)
    
    if "dzialki_protokol_ids" in payload:
        await execute(db, "DELETE FROM dzialki_wlasciciele WHERE wlasciciel_id = :wid", {"wid": wlasciciel_id})
        for obiekt_id in payload["dzialki_protokol_ids"]:
            await execute(db,
                "INSERT INTO dzialki_wlasciciele (obiekt_id, wlasciciel_id, typ_posiadania) VALUES (:oid, :wid, :typ)",
                {"oid": obiekt_id, "wid": wlasciciel_id, "typ": "protokol"})
    
    return {"status": "success"}


@router.delete("/wlasciciele/{wlasciciel_id}")
async def delete_wlasciciel(
    wlasciciel_id: int,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Usuwa wlasciciela (wymaga auth)."""
    await execute(db, "DELETE FROM dzialki_wlasciciele WHERE wlasciciel_id = :id", {"id": wlasciciel_id})
    await execute(db, "DELETE FROM wlasciciele WHERE id = :id", {"id": wlasciciel_id})
    return {"status": "success"}


# === Obiekty CRUD ===
@router.get("/obiekty")
async def list_obiekty(db: AsyncSession = Depends(get_db)):
    """Lista wszystkich obiektow geograficznych (publiczne)."""
    return await admin_objects_service.list_objects_with_owner_links(db)


@router.get("/wszystkie-obiekty")
async def list_wszystkie_obiekty(db: AsyncSession = Depends(get_db)):
    """Alias kontraktowy dla admin.js: pelna lista obiektow do modali edycji.

    admin.js uzywa API.allObjects do wyboru dzialek wlasciciela. Endpoint zwraca
    ten sam ksztalt danych co /api/admin/obiekty, ale zostawiamy osobna sciezke,
    zeby nie lamac istniejacego frontendu.
    """
    return await admin_objects_service.list_objects_with_owner_links(db)


@router.get("/protocols")
async def list_protocols(db: AsyncSession = Depends(get_db)):
    """Lista protokolow dla autocomplete genealogii w admin.js.

    Frontend oczekuje pol: key, name, ordernumber/orderNumber. Dane bierzemy z
    wlascicieli, bo protokol administracyjny jest tam kanonicznie opisany.
    """
    rows = await fetch_all(db, """
        SELECT
            unikalny_klucz AS key,
            COALESCE(nazwa_wlasciciela, unikalny_klucz, '') AS name,
            numer_protokolu AS ordernumber,
            numer_protokolu AS "orderNumber"
        FROM wlasciciele
        WHERE unikalny_klucz IS NOT NULL AND unikalny_klucz != ''
        ORDER BY numer_protokolu, nazwa_wlasciciela
    """)
    return rows


@router.get("/export-backup")
async def export_backup(db: AsyncSession = Depends(get_db), _auth=Depends(admin_required)):
    """Pobiera lekki backup JSON z podstawowych tabel admina.

    admin.js uzywa tego endpointu przez window.location.href, wiec zwracamy plik
    do pobrania (Content-Disposition attachment), nie zwykly JSON API.
    """
    now_utc = datetime.now(timezone.utc)
    payload = {
        "created_at": now_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "tables": {
            "wlasciciele": await fetch_all(db, "SELECT * FROM wlasciciele ORDER BY id"),
            "obiekty_geograficzne": await fetch_all(db, "SELECT * FROM obiekty_geograficzne ORDER BY id"),
            "osoby_genealogia": await fetch_all(db, "SELECT * FROM osoby_genealogia ORDER BY id"),
            "demografia": await fetch_all(db, "SELECT * FROM demografia ORDER BY rok"),
        },
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    filename = f"mapa-czarna-backup-{now_utc.strftime('%Y%m%d-%H%M%S')}.json"
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/obiekty/{obiekt_id}")
async def update_obiekt(
    obiekt_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Aktualizuje obiekt geograficzny (wymaga auth)."""
    row = await fetch_one(db, "SELECT id FROM obiekty_geograficzne WHERE id = :id", {"id": obiekt_id})
    if not row:
        raise HTTPException(status_code=404, detail="Nie znaleziono")
    
    fields = []
    params = {"id": obiekt_id}
    for key in ["nazwa_lub_numer", "kategoria", "geometria"]:
        if key in payload:
            fields.append(f"{key} = :{key}")
            params[key] = payload[key]
    
    if fields:
        await execute(db, f"UPDATE obiekty_geograficzne SET {', '.join(fields)} WHERE id = :id", params)
    
    return {"status": "success"}


@router.delete("/obiekty/{obiekt_id}")
async def delete_obiekt(
    obiekt_id: int,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Usuwa obiekt geograficzny (wymaga auth)."""
    await execute(db, "DELETE FROM dzialki_wlasciciele WHERE obiekt_id = :id", {"id": obiekt_id})
    await execute(db, "DELETE FROM obiekty_geograficzne WHERE id = :id", {"id": obiekt_id})
    return {"status": "success"}


# === Genealogia CRUD ===
@router.get("/genealogia")
async def list_genealogia(db: AsyncSession = Depends(get_db)):
    """Lista wszystkich osob w genealogii (publiczne)."""
    rows = await fetch_all(db, """
        SELECT
            og.*,
            w.unikalny_klucz AS protokol_klucz
        FROM osoby_genealogia og
        LEFT JOIN wlasciciele w ON og.id_protokolu = w.id
        ORDER BY og.id
    """)
    for r in rows:
        # Kontrakt z admin.js: frontend uzywa id_osoby jako stabilnego JSON ID,
        # a db_id jako technicznego id SQLite do edycji/usuwania.
        # W bazie odpowiednikiem id_osoby jest json_id; fallback na id zabezpiecza
        # stare rekordy bez json_id i usuwa UI bug "ID: undefined".
        r["db_id"] = r["id"]
        r["id_osoby"] = r.get("json_id") or str(r["id"])
        r["imie"] = (r.get("imie_nazwisko") or "").split(" ", 1)[0] if r.get("imie_nazwisko") else ""
        r["nazwisko"] = (r.get("imie_nazwisko") or "").split(" ", 1)[1] if r.get("imie_nazwisko") and " " in r["imie_nazwisko"] else ""
        r["name"] = r.get("imie_nazwisko") or ""
    return rows


@router.post("/genealogia", status_code=201)
async def create_genealogia(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Tworzy nowa osobe w genealogii (wymaga auth)."""
    try:
        imie = payload.get("imie", "")
        nazwisko = payload.get("nazwisko", "")
        imie_nazwisko = f"{imie} {nazwisko}".strip()
        
        params = {
            "json_id": str(payload.get("id_osoby", "")),
            "imie_nazwisko": imie_nazwisko,
            "plec": payload.get("plec", ""),
            "rok_urodzenia": payload.get("rok_urodzenia"),
            "rok_smierci": payload.get("rok_smierci"),
            "uwagi": payload.get("uwagi", ""),
            "numer_domu": payload.get("numer_domu", ""),
            "id_ojca": payload.get("id_ojca"),
            "id_matki": payload.get("id_matki"),
            "id_protokolu": None,
        }
        
        new_id = await execute(db, """
            INSERT INTO osoby_genealogia (json_id, imie_nazwisko, plec, rok_urodzenia,
            rok_smierci, uwagi, numer_domu, id_ojca, id_matki, id_protokolu)
            VALUES (:json_id, :imie_nazwisko, :plec, :rok_urodzenia,
            :rok_smierci, :uwagi, :numer_domu, :id_ojca, :id_matki, :id_protokolu)
        """, params)
        
        return {"id": new_id, "id_osoby": params["json_id"], "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/genealogia/{person_id}")
async def update_genealogia(
    person_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Aktualizuje osobe w genealogii (wymaga auth)."""
    row = await fetch_one(db, "SELECT id FROM osoby_genealogia WHERE id = :id", {"id": person_id})
    if not row:
        raise HTTPException(status_code=404, detail="Nie znaleziono")
    
    imie = payload.get("imie", "")
    nazwisko = payload.get("nazwisko", "")
    imie_nazwisko = f"{imie} {nazwisko}".strip()
    
    await execute(db, """
        UPDATE osoby_genealogia SET
            imie_nazwisko = :imie_nazwisko,
            plec = :plec,
            rok_urodzenia = :rok_urodzenia,
            rok_smierci = :rok_smierci,
            uwagi = :uwagi,
            numer_domu = :numer_domu,
            id_ojca = :id_ojca,
            id_matki = :id_matki
        WHERE id = :id
    """, {
        "id": person_id,
        "imie_nazwisko": imie_nazwisko,
        "plec": payload.get("plec", ""),
        "rok_urodzenia": payload.get("rok_urodzenia"),
        "rok_smierci": payload.get("rok_smierci"),
        "uwagi": payload.get("uwagi", ""),
        "numer_domu": payload.get("numer_domu", ""),
        "id_ojca": payload.get("id_ojca"),
        "id_matki": payload.get("id_matki"),
    })
    
    return {"status": "success", "id": person_id, "id_osoby": payload.get("id_osoby")}


@router.delete("/genealogia/{person_id}")
async def delete_genealogia(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Usuwa osobe z genealogii (wymaga auth)."""
    await execute(db, "DELETE FROM osoby_genealogia WHERE id = :id", {"id": person_id})
    return {"status": "success"}


# === Demografia CRUD ===
@router.get("/demografia")
async def list_demografia(db: AsyncSession = Depends(get_db)):
    """Lista wszystkich wpisow demograficznych (publiczne)."""
    return await fetch_all(db, "SELECT * FROM demografia ORDER BY rok")


@router.post("/demografia", status_code=201)
async def create_demografia(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Tworzy nowy wpis demograficzny (wymaga auth)."""
    try:
        params = {
            "rok": payload.get("rok"),
            "populacja_ogolem": payload.get("populacja_ogolem", 0),
            "katolicy": payload.get("katolicy", 0),
            "zydzi": payload.get("zydzi", 0),
            "inni": payload.get("inni", 0),
            "opis": payload.get("opis", ""),
        }
        new_id = await execute(db, """
            INSERT INTO demografia (rok, populacja_ogolem, katolicy, zydzi, inni, opis)
            VALUES (:rok, :populacja_ogolem, :katolicy, :zydzi, :inni, :opis)
        """, params)
        return {"id": new_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/demografia/{entry_id}")
async def update_demografia(
    entry_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Aktualizuje wpis demograficzny (wymaga auth)."""
    await execute(db, """
        UPDATE demografia SET
            rok = :rok,
            populacja_ogolem = :populacja_ogolem,
            katolicy = :katolicy,
            zydzi = :zydzi,
            inni = :inni,
            opis = :opis
        WHERE id = :id
    """, {
        "id": entry_id,
        "rok": payload.get("rok"),
        "populacja_ogolem": payload.get("populacja_ogolem", 0),
        "katolicy": payload.get("katolicy", 0),
        "zydzi": payload.get("zydzi", 0),
        "inni": payload.get("inni", 0),
        "opis": payload.get("opis", ""),
    })
    return {"status": "success"}


@router.delete("/demografia/{entry_id}")
async def delete_demografia(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(admin_required),
):
    """Usuwa wpis demograficzny (wymaga auth)."""
    await execute(db, "DELETE FROM demografia WHERE id = :id", {"id": entry_id})
    return {"status": "success"}
