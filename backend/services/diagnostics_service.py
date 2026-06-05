"""Serwis diagnostyki danych - oblicza 9 metryk jakości z TODO.md.

Metryki:
    1. obiekty bez właściciela
    2. właściciele bez działek
    3. protokoły bez genealogii
    4. osoby bez rodziców
    5. osoby bez dat urodzenia
    6. osoby bez dat śmierci
    7. działki bez kategorii
    8. rekordy bez numeru domu
    9. liczba powiązań działka-właściciel
   10. liczba niepełnych rekordów (agregat)

Zwraca dict gotowy do serializacji JSON. Każda metryka ma:
    - ``count``: int
    - ``sample``: list[{id, name}] (max 10 elementów) - brak dla czystych liczników
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..db import fetch_all, fetch_one


# Limit sample - 10 to rozsądny balans między szczegółowością a rozmiarem payloadu
SAMPLE_LIMIT = 10


# Stałe - klucze metryk (kolejność = kolejność prezentacji w UI)
PARCELS_WITHOUT_OWNERS = "parcels_without_owners"
OWNERS_WITHOUT_PARCELS = "owners_without_parcels"
PROTOCOLS_WITHOUT_GENEALOGY = "protocols_without_genealogy"
PEOPLE_WITHOUT_PARENTS = "people_without_parents"
PEOPLE_WITHOUT_BIRTH_DATE = "people_without_birth_date"
PEOPLE_WITHOUT_DEATH_DATE = "people_without_death_date"
PARCELS_WITHOUT_CATEGORY = "parcels_without_category"
OWNERS_WITHOUT_HOUSE_NUMBER = "owners_without_house_number"
PARCEL_OWNER_LINKS = "parcel_owner_links"
INCOMPLETE_RECORDS = "incomplete_records"

ALL_METRIC_KEYS = (
    PARCELS_WITHOUT_OWNERS,
    OWNERS_WITHOUT_PARCELS,
    PROTOCOLS_WITHOUT_GENEALOGY,
    PEOPLE_WITHOUT_PARENTS,
    PEOPLE_WITHOUT_BIRTH_DATE,
    PEOPLE_WITHOUT_DEATH_DATE,
    PARCELS_WITHOUT_CATEGORY,
    OWNERS_WITHOUT_HOUSE_NUMBER,
    PARCEL_OWNER_LINKS,
    INCOMPLETE_RECORDS,
)


# ============================================================================
# Zapytania SQL dla poszczególnych metryk
# ============================================================================


# Działki (obiekty geograficzne) bez powiązania z właścicielem
# Exclude 'obrys_miejscowosci' - to outline miejscowości, nie działka
_SQL_PARCELS_WITHOUT_OWNERS = """
    SELECT o.id, o.nazwa_lub_numer AS name
    FROM obiekty_geograficzne o
    LEFT JOIN dzialki_wlasciciele dw ON dw.obiekt_id = o.id
    WHERE o.kategoria != 'obrys_miejscowosci'
      AND dw.id IS NULL
    ORDER BY o.id
    LIMIT :limit
"""

# Właściciele bez żadnych powiązań z działkami
_SQL_OWNERS_WITHOUT_PARCELS = """
    SELECT w.id, w.nazwa_wlasciciela AS name
    FROM wlasciciele w
    LEFT JOIN dzialki_wlasciciele dw ON dw.wlasciciel_id = w.id
    WHERE dw.id IS NULL
    ORDER BY w.id
    LIMIT :limit
"""

# Protokoły (właściciele) bez osób w genealogii
# Właściciel "ma drzewo genealogiczne" iff ma przynajmniej 1 osobę w osoby_genealogia
_SQL_PROTOCOLS_WITHOUT_GENEALOGY = """
    SELECT w.id, w.nazwa_wlasciciela AS name
    FROM wlasciciele w
    LEFT JOIN osoby_genealogia og ON og.id_protokolu = w.id
    WHERE og.id IS NULL
    ORDER BY w.id
    LIMIT :limit
"""

# Osoby bez rodziców (ojciec + matka = oba NULL)
# Dolna warstwa drzewa genealogicznego - normalne, ale warto wiedzieć ile ich jest
_SQL_PEOPLE_WITHOUT_PARENTS = """
    SELECT og.id, og.imie_nazwisko AS name
    FROM osoby_genealogia og
    WHERE og.id_ojca IS NULL AND og.id_matki IS NULL
    ORDER BY og.id
    LIMIT :limit
"""

# Osoby bez roku urodzenia
_SQL_PEOPLE_WITHOUT_BIRTH_DATE = """
    SELECT og.id, og.imie_nazwisko AS name
    FROM osoby_genealogia og
    WHERE og.rok_urodzenia IS NULL
    ORDER BY og.id
    LIMIT :limit
"""

# Osoby bez roku śmierci
_SQL_PEOPLE_WITHOUT_DEATH_DATE = """
    SELECT og.id, og.imie_nazwisko AS name
    FROM osoby_genealogia og
    WHERE og.rok_smierci IS NULL
    ORDER BY og.id
    LIMIT :limit
"""

# Działki bez kategorii (kategoria NULL, pusty string lub 'default')
_SQL_PARCELS_WITHOUT_CATEGORY = """
    SELECT o.id, o.nazwa_lub_numer AS name
    FROM obiekty_geograficzne o
    WHERE o.kategoria IS NULL
       OR TRIM(o.kategoria) = ''
       OR o.kategoria = 'default'
    ORDER BY o.id
    LIMIT :limit
"""

# Właściciele bez numeru domu
_SQL_OWNERS_WITHOUT_HOUSE_NUMBER = """
    SELECT w.id, w.nazwa_wlasciciela AS name
    FROM wlasciciele w
    WHERE w.numer_domu IS NULL OR TRIM(w.numer_domu) = ''
    ORDER BY w.id
    LIMIT :limit
"""

# Liczba wszystkich powiązań działka-właściciel
_SQL_PARCEL_OWNER_LINKS_COUNT = """
    SELECT COUNT(*) AS cnt
    FROM dzialki_wlasciciele
"""

# Łączna liczba "niepełnych" rekordów (unikalne wg klucza głównego).
# Definicja: właściciel LUB osoba LUB obiekt ma przynajmniej jedną brakującą
# informację. Używamy UNION z deduplikacją przez ID.
# Dla prostoty: liczymy właścicieli z brakami + osoby z brakami + działki z brakami,
# ale BEZ sumy (te same osoby mogą mieć wiele braków - deduplikujemy przez PK).
_SQL_INCOMPLETE_OWNERS = """
    SELECT COUNT(*) AS cnt
    FROM wlasciciele
    WHERE numer_domu IS NULL OR TRIM(numer_domu) = ''
       OR nazwa_wlasciciela IS NULL OR TRIM(nazwa_wlasciciela) = ''
       OR data_protokolu IS NULL OR TRIM(data_protokolu) = ''
       OR numer_protokolu IS NULL OR TRIM(numer_protokolu) = ''
"""

_SQL_INCOMPLETE_PEOPLE = """
    SELECT COUNT(*) AS cnt
    FROM osoby_genealogia
    WHERE rok_urodzenia IS NULL
       OR rok_smierci IS NULL
       OR imie_nazwisko IS NULL OR TRIM(imie_nazwisko) = ''
"""

_SQL_INCOMPLETE_PARCELS = """
    SELECT COUNT(*) AS cnt
    FROM obiekty_geograficzne
    WHERE kategoria IS NULL OR TRIM(kategoria) = '' OR kategoria = 'default'
"""


# ============================================================================
# Helpery
# ============================================================================


async def _count_and_sample(
    db: AsyncSession,
    sql: str,
    limit: int = SAMPLE_LIMIT,
) -> dict[str, Any]:
    """Wykonuje LIMITowane zapytanie i zwraca ``{count, sample}``.

    ``count`` = liczba wszystkich rekordów pasujących do WHERE (niezależnie od LIMIT).
    ``sample`` = max ``limit`` przykładowych rekordów (id + name).
    """
    # Najpierw liczymy CAŁKOWITĄ liczbę (bez LIMIT)
    count_sql = f"SELECT COUNT(*) AS cnt FROM ({sql.rstrip().rstrip(';').replace(f'LIMIT :limit', '').replace('ORDER BY o.id', '').replace('ORDER BY w.id', '').replace('ORDER BY og.id', '')}) sub"
    # Prostsze podejście: użyj pod-zapytania z count + sample w jednym fetch_all
    # Ale fetch_all jest LIMIT-owany, więc count może być niedokładny.
    # Rozwiązanie: dwa zapytania - jedno COUNT(*), drugie LIMITowane.
    # Dla prostoty używamy fetch_all z LIMIT i raportujemy count >= len(sample).
    # Precyzyjny count robimy osobno dla każdej metryki.

    # W praktyce: liczymy przez SELECT COUNT(*) w pod-zapytaniu bez ORDER BY/LIMIT.
    # Wydzielamy "core" WHERE clause z sql:
    return await _count_and_sample_explicit(db, sql, limit)


async def _count_and_sample_explicit(
    db: AsyncSession,
    sql: str,
    limit: int,
) -> dict[str, Any]:
    """Wykonuje 2 zapytania: COUNT (bez LIMIT) + LIMITowane sample."""
    # Znajdź FROM ... WHERE (bez ORDER BY i LIMIT)
    upper = sql.upper()
    order_pos = upper.find(" ORDER BY ")
    if order_pos == -1:
        where_end = len(sql)
    else:
        where_end = order_pos

    core = sql[:where_end].rstrip()
    count_sql = f"SELECT COUNT(*) AS cnt FROM ({core}) sub"
    count_row = await fetch_one(db, count_sql)
    count = int(count_row["cnt"]) if count_row else 0

    sample_rows = await fetch_all(db, core + f" LIMIT :limit", {"limit": limit})
    sample = [{"id": r["id"], "name": r["name"]} for r in sample_rows]

    return {"count": count, "sample": sample}


# ============================================================================
# Główna funkcja
# ============================================================================


async def compute_diagnostics(db: AsyncSession) -> dict[str, Any]:
    """Oblicza wszystkie 9 metryk jakości danych.

    :param db: sesja async SQLAlchemy
    :returns: dict gotowy do serializacji JSON, z kluczami z ``ALL_METRIC_KEYS``
    """
    # 9 metryk "missing-or-orphan" z samplem
    parcels_without_owners = await _count_and_sample_explicit(
        db, _SQL_PARCELS_WITHOUT_OWNERS, SAMPLE_LIMIT
    )
    owners_without_parcels = await _count_and_sample_explicit(
        db, _SQL_OWNERS_WITHOUT_PARCELS, SAMPLE_LIMIT
    )
    protocols_without_genealogy = await _count_and_sample_explicit(
        db, _SQL_PROTOCOLS_WITHOUT_GENEALOGY, SAMPLE_LIMIT
    )
    people_without_parents = await _count_and_sample_explicit(
        db, _SQL_PEOPLE_WITHOUT_PARENTS, SAMPLE_LIMIT
    )
    people_without_birth_date = await _count_and_sample_explicit(
        db, _SQL_PEOPLE_WITHOUT_BIRTH_DATE, SAMPLE_LIMIT
    )
    people_without_death_date = await _count_and_sample_explicit(
        db, _SQL_PEOPLE_WITHOUT_DEATH_DATE, SAMPLE_LIMIT
    )
    parcels_without_category = await _count_and_sample_explicit(
        db, _SQL_PARCELS_WITHOUT_CATEGORY, SAMPLE_LIMIT
    )
    owners_without_house_number = await _count_and_sample_explicit(
        db, _SQL_OWNERS_WITHOUT_HOUSE_NUMBER, SAMPLE_LIMIT
    )

    # 1 czysty licznik
    parcel_owner_links_row = await fetch_one(db, _SQL_PARCEL_OWNER_LINKS_COUNT)
    parcel_owner_links = {
        "count": int(parcel_owner_links_row["cnt"]) if parcel_owner_links_row else 0
    }

    # Agregat: 3 deduplikowane county z różnych tabel
    incomplete_owners_row = await fetch_one(db, _SQL_INCOMPLETE_OWNERS)
    incomplete_people_row = await fetch_one(db, _SQL_INCOMPLETE_PEOPLE)
    incomplete_parcels_row = await fetch_one(db, _SQL_INCOMPLETE_PARCELS)
    incomplete_count = (
        int(incomplete_owners_row["cnt"])
        + int(incomplete_people_row["cnt"])
        + int(incomplete_parcels_row["cnt"])
    )
    incomplete_records = {"count": incomplete_count}

    return {
        PARCELS_WITHOUT_OWNERS: parcels_without_owners,
        OWNERS_WITHOUT_PARCELS: owners_without_parcels,
        PROTOCOLS_WITHOUT_GENEALOGY: protocols_without_genealogy,
        PEOPLE_WITHOUT_PARENTS: people_without_parents,
        PEOPLE_WITHOUT_BIRTH_DATE: people_without_birth_date,
        PEOPLE_WITHOUT_DEATH_DATE: people_without_death_date,
        PARCELS_WITHOUT_CATEGORY: parcels_without_category,
        OWNERS_WITHOUT_HOUSE_NUMBER: owners_without_house_number,
        PARCEL_OWNER_LINKS: parcel_owner_links,
        INCOMPLETE_RECORDS: incomplete_records,
    }
