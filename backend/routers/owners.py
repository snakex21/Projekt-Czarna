"""Router wlascicieli - lista, szczegoly, graf powiazan."""
import json
import re
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db, fetch_one, fetch_all
from ..config import DB_ENGINE
from ..utils import is_real_ownership
from ..services.ownership_service import protocol_links_to_html, get_location_protocol_config, format_plot

router = APIRouter(prefix="/api", tags=["owners"])


@router.get("/wlasciciele")
async def get_all_owners(db: AsyncSession = Depends(get_db)):
    """Pobiera liste wszystkich wlascicieli z podzialem dzialek."""
    query = """
        SELECT
            w.id, w.unikalny_klucz, w.nazwa_wlasciciela, w.numer_protokolu,
            COALESCE(
                json_agg(json_build_object('id', o.id, 'nazwa_lub_numer', o.nazwa_lub_numer))
                    FILTER (WHERE dw.typ_posiadania = 'wlasnosc rzeczywista'),
                '[]'::json
            ) AS dzialki_rzeczywiste,
            COALESCE(
                json_agg(json_build_object('id', o.id, 'nazwa_lub_numer', o.nazwa_lub_numer))
                    FILTER (WHERE dw.typ_posiadania != 'wlasnosc rzeczywista' OR dw.typ_posiadania IS NULL),
                '[]'::json
            ) AS dzialki_protokol
        FROM wlasciciele w
        LEFT JOIN dzialki_wlasciciele dw ON w.id = dw.wlasciciel_id
        LEFT JOIN obiekty_geograficzne o ON dw.obiekt_id = o.id
        GROUP BY w.id
        ORDER BY w.numer_protokolu
    """

    if DB_ENGINE == "sqlite":
        query = """
            SELECT
                w.id, w.unikalny_klucz, w.nazwa_wlasciciela, w.numer_protokolu,
                COALESCE(
                    (SELECT json_group_array(json_object('id', o.id, 'nazwa_lub_numer', o.nazwa_lub_numer))
                     FROM dzialki_wlasciciele dw
                     JOIN obiekty_geograficzne o ON dw.obiekt_id = o.id
                      WHERE dw.wlasciciel_id = w.id AND dw.typ_posiadania = 'wlasnosc rzeczywista'),
                    '[]'
                ) AS dzialki_rzeczywiste,
                COALESCE(
                    (SELECT json_group_array(json_object('id', o.id, 'nazwa_lub_numer', o.nazwa_lub_numer))
                     FROM dzialki_wlasciciele dw
                     JOIN obiekty_geograficzne o ON dw.obiekt_id = o.id
                     WHERE dw.wlasciciel_id = w.id
                       AND (dw.typ_posiadania != 'wlasnosc rzeczywista' OR dw.typ_posiadania IS NULL)),
                    '[]'
                ) AS dzialki_protokol
            FROM wlasciciele w
            ORDER BY w.numer_protokolu
        """

    owners = await fetch_all(db, query)

    range_query = "SELECT MIN(numer_protokolu) as min_lp, MAX(numer_protokolu) as max_lp FROM wlasciciele WHERE numer_protokolu IS NOT NULL"
    zakres = await fetch_one(db, range_query)

    for owner in owners:
        for key in ["dzialki_rzeczywiste", "dzialki_protokol"]:
            val = owner.get(key)
            if isinstance(val, str):
                try:
                    owner[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    owner[key] = []

    return {
        "owners": owners,
        "metadata": {
            "total_count": len(owners),
            "zakres_lp": {
                "min": zakres.get("min_lp") or 1 if zakres else 1,
                "max": zakres.get("max_lp") or 1 if zakres else 1
            }
        }
    }


@router.get("/wlasciciel/{unikalny_klucz}")
async def get_owner_by_key(unikalny_klucz: str, db: AsyncSession = Depends(get_db)):
    """Pobiera szczegolowe dane pojedynczego wlasciciela."""
    query = """
        SELECT unikalny_klucz, id, nazwa_wlasciciela, numer_protokolu, numer_domu,
               genealogia, historia_wlasnosci, uwagi, wspolwlasnosc,
               powiazania_i_transakcje, interpretacja_i_wnioski,
               data_protokolu, miejsce_protokolu
        FROM wlasciciele WHERE unikalny_klucz = :key
    """
    owner = await fetch_one(db, query, {"key": unikalny_klucz})

    if not owner:
        raise HTTPException(status_code=404, detail="Wlasciciel nie znaleziony")

    tree_query = "SELECT EXISTS (SELECT 1 FROM osoby_genealogia WHERE id_protokolu = :id) AS ma_drzewo"
    if DB_ENGINE == "sqlite":
        tree_query = "SELECT COUNT(*) > 0 AS ma_drzewo FROM osoby_genealogia WHERE id_protokolu = :id"
    tree_result = await fetch_one(db, tree_query, {"id": owner["id"]})
    owner["ma_drzewo_genealogiczne"] = bool(tree_result.get("ma_drzewo", False)) if tree_result else False

    plot_rows = await fetch_all(db, """
        SELECT o.id, o.nazwa_lub_numer, o.kategoria, o.geometria, dw.typ_posiadania
        FROM dzialki_wlasciciele dw
        JOIN obiekty_geograficzne o ON o.id = dw.obiekt_id
        WHERE dw.wlasciciel_id = :id
        ORDER BY o.nazwa_lub_numer
    """, {"id": owner["id"]})

    owner["dzialki_protokol"] = []
    owner["dzialki_rzeczywiste"] = []
    for row in plot_rows:
        plot = format_plot(row)
        if is_real_ownership(row.get("typ_posiadania")):
            owner["dzialki_rzeczywiste"].append(plot)
        else:
            owner["dzialki_protokol"].append(plot)

    owner["dzialki_wszystkie"] = owner["dzialki_rzeczywiste"] + owner["dzialki_protokol"]
    owner["dom_numer"] = owner.get("numer_domu")

    # Szukaj obiektu domu/budynku powiązanego z właścicielem
    dom_query = """
        SELECT o.id
        FROM obiekty_geograficzne o
        JOIN dzialki_wlasciciele dw ON dw.obiekt_id = o.id
        WHERE dw.wlasciciel_id = :owner_id
          AND o.kategoria IN ('dom', 'budynek')
        LIMIT 1
    """
    if owner.get("numer_domu"):
        # Najpierw szukaj domu powiązanego z właścicielem
        dom_result = await fetch_one(db, dom_query, {"owner_id": owner["id"]})
        if dom_result:
            owner["dom_obiekt_id"] = dom_result["id"]
        else:
            # Fallback: szukaj po numerze domu w nazwie obiektu
            fallback_query = """
                SELECT id FROM obiekty_geograficzne
                WHERE kategoria IN ('dom', 'budynek')
                  AND nazwa_lub_numer = :numer_domu
                LIMIT 1
            """
            fallback_result = await fetch_one(db, fallback_query, {"numer_domu": owner["numer_domu"]})
            owner["dom_obiekt_id"] = fallback_result["id"] if fallback_result else None
    else:
        owner["dom_obiekt_id"] = None

    # Dane oczekiwane przez widok protokołu.
    protocol_cfg = get_location_protocol_config()
    owner["gmina_katastralna"] = protocol_cfg.get("gmina_katastralna")
    if not owner.get("miejsce_protokolu"):
        owner["miejsce_protokolu"] = protocol_cfg.get("miejscowosc_protokolu")
    owner["pelna_historia"] = owner.get("historia_wlasnosci") or owner.get("uwagi") or ""
    owner["powiazania_i_transakcje_html"] = protocol_links_to_html(owner.get("powiazania_i_transakcje"))

    return owner


@router.get("/graph-data")
async def get_graph_data(db: AsyncSession = Depends(get_db)):
    """Zwraca dane do wizualizacji grafu powiazan miedzy protokolami."""
    owners = await fetch_all(db,
        "SELECT id, unikalny_klucz, nazwa_wlasciciela, numer_protokolu, powiazania_i_transakcje FROM wlasciciele"
    )

    nodes = []
    for owner in owners:
        nodes.append({
            "id": owner.get("unikalny_klucz") or "",
            "label": f"{owner.get('nazwa_wlasciciela') or ''}\n(Lp. {owner.get('numer_protokolu') or 'N/A'})",
            "title": f"Protokol Lp. {owner.get('numer_protokolu') or 'N/A'}",
        })

    edges = []
    link_pattern = re.compile(r'\[\[.*?\|(.*?)\]\]')
    for owner in owners:
        text = owner.get("powiazania_i_transakcje") or ""
        if text:
            targets = set(link_pattern.findall(text))
            for target in targets:
                source_key = owner.get("unikalny_klucz") or ""
                if source_key != target:
                    edges.append({"from": source_key, "to": target, "arrows": "to"})

    return {"nodes": nodes, "edges": edges}
