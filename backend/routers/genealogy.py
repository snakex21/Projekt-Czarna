"""Router genealogii - drzewa, osoby, malzenstwa."""
import re
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db, fetch_one, fetch_all
from ..services.genealogy_service import build_persons_map, build_persons_json_format, build_family_tree_persons

try:
    from ..utils.pdf_generator import generate_family_pdf
except Exception:  # pragma: no cover - zalezy od srodowiska uruchomienia
    generate_family_pdf = None

router = APIRouter(prefix="/api/genealogia", tags=["genealogy"])


@router.get("/list")
async def get_genealogy_list(db: AsyncSession = Depends(get_db)):
    """Zwraca pelna liste osob."""
    persons = await fetch_all(db, """
        SELECT 
            og.id, og.json_id, og.imie_nazwisko AS name, og.plec AS gender, 
            og.rok_urodzenia, og.rok_smierci, og.uwagi AS notes,
            og.id_ojca, og.id_matki, w.unikalny_klucz AS protocol_key
        FROM osoby_genealogia og
        LEFT JOIN wlasciciele w ON og.id_protokolu = w.id
    """)

    marriages = await fetch_all(db, """
        SELECT malzonek1_id, malzonek2_id, rok_slubu, data_slubu 
        FROM malzenstwa
    """)

    persons_map = build_persons_map(persons, marriages)
    return {"persons": list(persons_map.values())}


@router.get("/persons-format")
async def get_genealogy_persons_format(db: AsyncSession = Depends(get_db)):
    """Zwraca wszystkie osoby w formacie genealogicznym uzywanym przez frontend."""
    persons = await fetch_all(db, """
        SELECT
            og.id, og.json_id, og.imie_nazwisko, og.plec,
            og.rok_urodzenia, og.rok_smierci,
            og.numer_domu, og.uwagi, og.id_ojca, og.id_matki,
            w.unikalny_klucz AS protocol_key
        FROM osoby_genealogia og
        LEFT JOIN wlasciciele w ON og.id_protokolu = w.id
    """)

    marriages = await fetch_all(db, "SELECT malzonek1_id, malzonek2_id, rok_slubu FROM malzenstwa")

    persons_json = build_persons_json_format(persons, marriages)
    return {"persons": persons_json}


@router.get("/pdf/{person_id}")
async def get_family_card_pdf(person_id: str, db: AsyncSession = Depends(get_db)):
    """Generuje i zwraca Karte Rodziny i Majatku jako PDF."""
    if not generate_family_pdf:
        raise HTTPException(status_code=503, detail="Generator PDF niedostepny")

    persons_rows = await fetch_all(db, """
        SELECT
            og.id, og.json_id, og.imie_nazwisko, og.plec,
            og.rok_urodzenia, og.rok_smierci,
            og.numer_domu, og.uwagi, og.id_ojca, og.id_matki,
            w.unikalny_klucz AS protocol_key
        FROM osoby_genealogia og
        LEFT JOIN wlasciciele w ON og.id_protokolu = w.id
    """)

    marriages_rows = await fetch_all(db, "SELECT malzonek1_id, malzonek2_id, rok_slubu FROM malzenstwa")
    persons = build_persons_json_format(persons_rows, marriages_rows)

    db_id_to_json_id = {str(row["id"]): row["json_id"] for row in persons_rows}
    selected_json_id = db_id_to_json_id.get(str(person_id), person_id)
    person = next((p for p in persons if str(p.get("id")) == str(selected_json_id)), None)

    if not person:
        raise HTTPException(status_code=404, detail="Osoba nie znaleziona")

    pdf_buffer = generate_family_pdf(person, all_persons=persons)
    if not pdf_buffer:
        raise HTTPException(status_code=500, detail="Nie udalo sie wygenerowac PDF")

    safe_name = re.sub(r"[^\w\-]+", "_", person.get("name") or "Nieznany", flags=re.UNICODE).strip("_")
    filename = f"Karta_Rodziny_{safe_name or 'Nieznany'}.pdf"
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
    }
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)


@router.get("/{unikalny_klucz}")
async def get_family_tree(unikalny_klucz: str, db: AsyncSession = Depends(get_db)):
    """Zwraca drzewo genealogiczne dla wlasciciela."""
    owner = await fetch_one(db,
        "SELECT id FROM wlasciciele WHERE unikalny_klucz = :key",
        {"key": unikalny_klucz}
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Wlasciciel nie znaleziony")

    root = await fetch_one(db,
        "SELECT * FROM osoby_genealogia WHERE id_protokolu = :pid LIMIT 1",
        {"pid": owner["id"]}
    )
    if not root:
        raise HTTPException(status_code=404, detail="Nie znaleziono osoby powiazanej")

    all_persons = await fetch_all(db, """
        SELECT og.*, w.unikalny_klucz AS protocol_key
        FROM osoby_genealogia og
        LEFT JOIN wlasciciele w ON og.id_protokolu = w.id
    """)

    all_marriages = await fetch_all(db, "SELECT * FROM malzenstwa")

    persons_json = build_family_tree_persons(all_persons, all_marriages)
    return {"rootId": root["json_id"], "persons": persons_json}
