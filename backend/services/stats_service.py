"""Serwis statystyk — oblicza rankingi, demografie, genealogie, dane zydowskie."""
import json
import re
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..db import fetch_one, fetch_all
from ..config import DB_ENGINE, ACTIVE_LOCATION, BACKUP_DIR
from ..utils import extract_year, is_real_ownership
from .geo_utils import parse_geom, geom_area_m2, line_length_m


def valid_year(value, current_year=None):
    """Sprawdza czy wartosc jest poprawnym rokiem."""
    if current_year is None:
        current_year = datetime.now().year
    if isinstance(value, int) and 0 < value <= current_year:
        return value
    if isinstance(value, str) and value.isdigit():
        year = int(value)
        if 0 < year <= current_year:
            return year
    return None


def decade_series(people, field):
    """Liczy osoby w dekadach na podstawie pola (rok_urodzenia / rok_smierci)."""
    c = Counter()
    for p in people:
        year = valid_year(p.get(field))
        if year:
            c[f"{year // 10 * 10}s"] += 1
    labels = sorted(c.keys())
    return {"labels": labels, "data": [c[l] for l in labels]}


def series_from_years(years):
    """Liczy wystapienia w dekadach z listy lat."""
    c = Counter((y // 10) * 10 for y in years)
    if not c:
        return {"labels": [], "data": []}
    labels = [f"{d}s" for d in range(min(c), max(c) + 10, 10)]
    return {"labels": labels, "data": [c.get(int(label[:4]), 0) for label in labels]}


# ---- Obliczanie metryk obiektow ----

def compute_object_metrics(objects):
    """Dla kazdego obiektu geograficznego oblicza powierzchnie i dlugosc."""
    object_metrics = {}
    location_outline_area = 0.0
    polygon_areas = []

    for obj in objects:
        geom = parse_geom(obj.get("geometria"))
        area = geom_area_m2(geom)
        length = line_length_m(geom)
        object_metrics[obj["id"]] = {"area_m2": area, "length_m": length, "geom": geom}

        if obj.get("kategoria") == "obrys_miejscowosci":
            location_outline_area += area
        elif area > 0 and obj.get("kategoria") not in ("droga", "rzeka", "obiekt_specjalny"):
            polygon_areas.append(area)

    return object_metrics, location_outline_area, polygon_areas


def compute_area_stats(polygon_areas):
    """Statystyki powierzchni dzialek."""
    return {
        "total_area_ha": round(sum(polygon_areas) / 10000, 2),
        "avg_area_ares": round((sum(polygon_areas) / len(polygon_areas) / 100) if polygon_areas else 0, 2),
        "min_area_m2": round(min(polygon_areas), 2) if polygon_areas else 0,
        "max_area_m2": round(max(polygon_areas), 2) if polygon_areas else 0,
    }


def compute_line_stats(objects, object_metrics, category):
    """Statystyki dla obiektow liniowych (rzeki, drogi)."""
    vals = [object_metrics[o["id"]]["length_m"] for o in objects if o.get("kategoria") == category]
    return {
        "total_count": len(vals),
        "max_length_m": max(vals) if vals else 0,
        "avg_length_m": (sum(vals) / len(vals)) if vals else 0,
        "min_length_m": min(vals) if vals else 0,
    }


def compute_line_ranking(objects, object_metrics, category, label_key):
    """TOP 50 ranking dla obiektow liniowych."""
    rows = []
    for obj in objects:
        if obj.get("kategoria") == category:
            rows.append({
                label_key: obj.get("nazwa_lub_numer") or "Bez nazwy",
                "length_m": round(object_metrics.get(obj["id"], {}).get("length_m", 0.0), 2),
            })
    rows.sort(key=lambda x: x["length_m"], reverse=True)
    return rows[:50]


# ---- Rankingi wlascicieli i dzialek ----

def compute_owner_rankings(links, object_metrics):
    """Buduje rankingi wlascicieli (rzeczywiste i protokolarne)."""
    owner_acc = defaultdict(lambda: {
        "owner_id": None, "unikalny_klucz": "", "nazwa_wlasciciela": "", "numer_protokolu": None,
        "ids": set(), "area": 0.0, "categories": defaultdict(lambda: {"ids": set(), "area": 0.0})
    })
    owner_acc_protocol = defaultdict(lambda: {
        "owner_id": None, "unikalny_klucz": "", "nazwa_wlasciciela": "", "numer_protokolu": None,
        "ids": set(), "area": 0.0, "categories": defaultdict(lambda: {"ids": set(), "area": 0.0})
    })

    for row in links:
        if not row.get("object_id"):
            continue
        is_real = is_real_ownership(row.get("typ_posiadania"))
        acc = owner_acc if is_real else owner_acc_protocol
        rec = acc[row["owner_id"]]
        rec.update({
            "owner_id": row["owner_id"],
            "unikalny_klucz": row.get("unikalny_klucz") or "",
            "nazwa_wlasciciela": row.get("nazwa_wlasciciela") or "",
            "numer_protokolu": row.get("numer_protokolu"),
        })
        metric = object_metrics.get(row["object_id"], {})
        area = metric.get("area_m2", 0.0)
        cat = row.get("kategoria") or "default"
        rec["ids"].add(row["object_id"])
        rec["area"] += area
        rec["categories"][cat]["ids"].add(row["object_id"])
        rec["categories"][cat]["area"] += area

    def _build_ranking(acc):
        result = {"all_plots": []}
        for cat in ["budowlana", "rolna", "las", "pastwisko", "droga", "rzeka", "budynek", "kapliczka", "obiekt_specjalny"]:
            result[cat] = []
        for rec in acc.values():
            base = {
                "unikalny_klucz": rec["unikalny_klucz"],
                "nazwa_wlasciciela": rec["nazwa_wlasciciela"],
                "numer_protokolu": rec["numer_protokolu"],
                "plot_count": len(rec["ids"]),
                "total_area_m2": round(rec["area"], 2),
            }
            result["all_plots"].append(base)
            for cat, data in rec["categories"].items():
                result.setdefault(cat, []).append({**base, "plot_count": len(data["ids"]), "total_area_m2": round(data["area"], 2)})
        for key in result:
            result[key].sort(key=lambda x: (x.get("plot_count") or 0, x.get("total_area_m2") or 0), reverse=True)
        return result

    return _build_ranking(owner_acc), _build_ranking(owner_acc_protocol)


def compute_parcels_ranking(objects, links, object_metrics):
    """Ranking dzialek wg powierzchni."""
    parcels_by_owner = defaultdict(list)
    for row in links:
        if row.get("object_id"):
            parcels_by_owner[row["object_id"]].append(row)

    parcels_ranking = defaultdict(list)
    for obj in objects:
        if obj.get("kategoria") == "obrys_miejscowosci":
            continue
        metric = object_metrics.get(obj["id"], {})
        owners = parcels_by_owner.get(obj["id"], [])
        owner_names = ", ".join(sorted({o.get("nazwa_wlasciciela") or "" for o in owners if o.get("nazwa_wlasciciela")})) or "Brak wlasciciela"
        first_owner = owners[0] if owners else {}
        item = {
            "parcel_number": obj.get("nazwa_lub_numer"),
            "kategoria": obj.get("kategoria"),
            "area_m2": round(metric.get("area_m2", 0.0), 2),
            "nazwa_wlasciciela": owner_names,
            "unikalny_klucz": first_owner.get("unikalny_klucz"),
        }
        parcels_ranking["all"].append(item)
        parcels_ranking[obj.get("kategoria") or "default"].append(item)
    for key in parcels_ranking:
        parcels_ranking[key].sort(key=lambda x: x.get("area_m2") or 0, reverse=True)
    return dict(parcels_ranking)


# ---- Genealogia i demografia ----

def load_backup_genealogy_people(backup_dir: Path, active_location: str):
    """Czyta genealogia.json z backupu (fallback gdy SQLite nie ma lat)."""
    path = backup_dir / active_location / "genealogia.json"
    if not path.exists():
        return [], []
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return [], []

    normalized = []
    marriage_years = []
    seen_marriages = set()
    for person in raw.get("persons", []):
        person_id = person.get("id")
        normalized.append({
            "id": person_id,
            "json_id": str(person_id) if person_id is not None else None,
            "imie_nazwisko": person.get("name") or "",
            "plec": person.get("gender") or "",
            "rok_urodzenia": extract_year(person.get("birthDate")),
            "rok_smierci": extract_year(person.get("deathDate")),
            "numer_domu": person.get("houseNumber") or "",
            "id_ojca": person.get("fatherId"),
            "id_matki": person.get("motherId"),
        })

        for marriage in person.get("marriages") or []:
            spouse_id = marriage.get("spouseId")
            key = tuple(sorted([str(person_id), str(spouse_id)]))
            year = extract_year(marriage.get("date"))
            if key not in seen_marriages and year:
                seen_marriages.add(key)
                marriage_years.append(year)

    return normalized, marriage_years


async def fetch_marriage_years(db):
    """Pobiera lata slubow z bazy malzenstw."""
    years = []
    try:
        rows = await fetch_all(db, "SELECT rok_slubu, data_slubu FROM malzenstwa")
        for row in rows:
            year = valid_year(row.get("rok_slubu"))
            if not year:
                match = re.search(r"(17|18|19|20)\d{2}", str(row.get("data_slubu") or ""))
                year = valid_year(match.group(0)) if match else None
            if year:
                years.append(year)
    except Exception:
        pass
    return years


async def fetch_protocols_per_day(db):
    """Pobiera protokoly pogrupowane wg dnia."""
    protocols_per_day_rows = await fetch_all(db, """
        SELECT data_protokolu AS protocol_date, COUNT(*) AS protocol_count
        FROM wlasciciele
        WHERE data_protokolu IS NOT NULL AND data_protokolu != ''
        GROUP BY data_protokolu
        ORDER BY data_protokolu
    """)
    protocol_owner_rows = await fetch_all(db, """
        SELECT data_protokolu AS protocol_date, unikalny_klucz, nazwa_wlasciciela
        FROM wlasciciele
        WHERE data_protokolu IS NOT NULL AND data_protokolu != ''
        ORDER BY data_protokolu, nazwa_wlasciciela
    """)
    owners_by_day = defaultdict(list)
    for row in protocol_owner_rows:
        owners_by_day[row.get("protocol_date")].append({
            "unikalny_klucz": row.get("unikalny_klucz"),
            "nazwa_wlasciciela": row.get("nazwa_wlasciciela"),
        })
    result = []
    for row in protocols_per_day_rows:
        date_value = row.get("protocol_date")
        if date_value:
            result.append({
                "protocol_date": str(date_value),
                "protocol_count": row.get("protocol_count") or 0,
                "owners": owners_by_day.get(date_value, []),
            })
    return result


async def fetch_objects_with_geom(db):
    """Pobiera obiekty z geometria."""
    geom_expr = "geometria" if DB_ENGINE == "sqlite" else "ST_AsGeoJSON(geometria) AS geometria"
    return await fetch_all(db, f"""
        SELECT id, nazwa_lub_numer, kategoria, {geom_expr}
        FROM obiekty_geograficzne
        WHERE kategoria IS NOT NULL
    """)


async def fetch_owner_links(db):
    """Pobiera powiazania wlasciciele-obiekty z geometriami."""
    link_geom_expr = "o.geometria AS geometria" if DB_ENGINE == "sqlite" else "ST_AsGeoJSON(o.geometria) AS geometria"
    return await fetch_all(db, f"""
        SELECT
            w.id AS owner_id,
            w.unikalny_klucz,
            w.nazwa_wlasciciela,
            w.numer_protokolu,
            o.id AS object_id,
            o.nazwa_lub_numer,
            o.kategoria,
            {link_geom_expr},
            dw.typ_posiadania
        FROM wlasciciele w
        LEFT JOIN dzialki_wlasciciele dw ON dw.wlasciciel_id = w.id
        LEFT JOIN obiekty_geograficzne o ON o.id = dw.obiekt_id
    """)


def compute_genealogy_stats(people, marriage_years, backup_marriage_years):
    """Pelne statystyki genealogiczne."""
    current_year = datetime.now().year

    male_count = sum(1 for p in people if str(p.get("plec") or "").lower().startswith("m"))
    female_count = sum(1 for p in people if str(p.get("plec") or "").lower().startswith(("k", "f")))
    surnames = Counter((p.get("imie_nazwisko") or "").split()[-1] for p in people
                       if p.get("imie_nazwisko") and len((p.get("imie_nazwisko") or "").split()) > 1)

    birth_years = [y for y in (valid_year(p.get("rok_urodzenia"), current_year) for p in people) if y]
    death_years = [y for y in (valid_year(p.get("rok_smierci"), current_year) for p in people) if y]

    all_marriage_years = list(marriage_years)
    if backup_marriage_years:
        all_marriage_years.extend(y for y in backup_marriage_years if valid_year(y, current_year))

    # Smiertelnosc niemowlat
    infant_people = [p for p in people
                     if valid_year(p.get("rok_urodzenia"), current_year) and valid_year(p.get("rok_smierci"), current_year)
                     and valid_year(p.get("rok_smierci"), current_year) - valid_year(p.get("rok_urodzenia"), current_year) <= 1]
    ages_at_death = [valid_year(p.get("rok_smierci"), current_year) - valid_year(p.get("rok_urodzenia"), current_year)
                     for p in people
                     if valid_year(p.get("rok_urodzenia"), current_year) and valid_year(p.get("rok_smierci"), current_year)
                     and valid_year(p.get("rok_smierci"), current_year) >= valid_year(p.get("rok_urodzenia"), current_year)]
    infant_mortality = {
        "total_births": len(birth_years),
        "infant_deaths": len(infant_people),
        "mortality_rate": round((len(infant_people) / len(birth_years) * 100) if birth_years else 0, 2),
        "by_decade": series_from_years([valid_year(p.get("rok_urodzenia"), current_year) for p in infant_people
                                        if valid_year(p.get("rok_urodzenia"), current_year)]),
    }

    # Dlugosc zycia wg dekady urodzenia
    lifespan_by_birth_decade = defaultdict(list)
    for p in people:
        birth = valid_year(p.get("rok_urodzenia"), current_year)
        death = valid_year(p.get("rok_smierci"), current_year)
        if birth and death and death > birth:
            lifespan_by_birth_decade[birth // 10 * 10].append(death - birth)
    lifespan_labels = [f"{d}s" for d in sorted(lifespan_by_birth_decade)]
    lifespan_data = [round(sum(lifespan_by_birth_decade[int(label[:4])]) / len(lifespan_by_birth_decade[int(label[:4])]), 1)
                     for label in lifespan_labels]
    lifespan_by_generation = {
        "labels": lifespan_labels,
        "data": lifespan_data,
        "avg_lifespan": round(sum(ages_at_death) / len(ages_at_death), 1) if ages_at_death else 0,
        "total_records": len(ages_at_death),
    }

    # Dystrybucja wieku smierci
    age_ranges = {"0-1": 0, "1-5": 0, "5-10": 0, "10-20": 0, "20-30": 0, "30-40": 0,
                  "40-50": 0, "50-60": 0, "60-70": 0, "70-80": 0, "80+": 0}
    for age in ages_at_death:
        if age <= 1: age_ranges["0-1"] += 1
        elif age <= 5: age_ranges["1-5"] += 1
        elif age <= 10: age_ranges["5-10"] += 1
        elif age <= 20: age_ranges["10-20"] += 1
        elif age <= 30: age_ranges["20-30"] += 1
        elif age <= 40: age_ranges["30-40"] += 1
        elif age <= 50: age_ranges["40-50"] += 1
        elif age <= 60: age_ranges["50-60"] += 1
        elif age <= 70: age_ranges["60-70"] += 1
        elif age <= 80: age_ranges["70-80"] += 1
        else: age_ranges["80+"] += 1
    death_age_distribution = {"labels": list(age_ranges.keys()), "data": list(age_ranges.values()), "total_deaths": len(ages_at_death)}

    # Struktura rodziny
    parent_children = Counter()
    for p in people:
        for parent_key in ("id_ojca", "id_matki"):
            if p.get(parent_key):
                parent_children[p.get(parent_key)] += 1
    child_counts = list(parent_children.values())
    family_distribution = {
        "1 dziecko": sum(1 for c in child_counts if c == 1),
        "2 dzieci": sum(1 for c in child_counts if c == 2),
        "3-5 dzieci": sum(1 for c in child_counts if 3 <= c <= 5),
        "6-10 dzieci": sum(1 for c in child_counts if 6 <= c <= 10),
        ">10 dzieci": sum(1 for c in child_counts if c > 10),
    }
    households = Counter(p.get("numer_domu") for p in people if p.get("numer_domu"))
    family_structure = {
        "avg_children_per_parent": round(sum(child_counts) / len(child_counts), 2) if child_counts else 0,
        "family_size_distribution": {"labels": list(family_distribution.keys()), "data": list(family_distribution.values())},
        "total_families": len(child_counts),
        "avg_household_size": round(sum(households.values()) / len(households), 1) if households else 0,
        "total_households": len(households),
    }

    return {
        "male_count": male_count,
        "female_count": female_count,
        "top_surnames": [{"name": k, "count": v} for k, v in surnames.most_common(10)],
        "births_by_decade": decade_series(people, "rok_urodzenia"),
        "deaths_by_decade": decade_series(people, "rok_smierci"),
        "marriages_by_decade": series_from_years(all_marriage_years),
        "infant_mortality": infant_mortality,
        "lifespan_by_generation": lifespan_by_generation,
        "death_age_distribution": death_age_distribution,
        "family_structure": family_structure,
    }


def compute_demography_metrical(people, official_events_map, current_year, demografia_official):
    """Rekonstruuje populacje rok po roku na podstawie dat urodzenia/smierci."""
    birth_years = [y for y in (valid_year(p.get("rok_urodzenia"), current_year) for p in people) if y]
    death_years = [y for y in (valid_year(p.get("rok_smierci"), current_year) for p in people) if y]

    result = []
    if birth_years:
        min_year = min(birth_years)
        max_year = min(max(max(birth_years), max(death_years) if death_years else 0) + 1, current_year)
        for year in range(min_year, max_year + 1):
            population = 0
            for person in people:
                birth = valid_year(person.get("rok_urodzenia"), current_year)
                death = valid_year(person.get("rok_smierci"), current_year)
                if birth and birth <= year and ((death and death >= year) or (not death and year - birth <= 95)):
                    population += 1
            if population > 0:
                result.append({
                    "rok": year,
                    "populacja_ogolem": population,
                    "katolicy": 0,
                    "zydzi": 0,
                    "inni": 0,
                    "opis": official_events_map.get(year, ""),
                })

    if not result:
        result = demografia_official
    return result


def read_jewish_protocols(backup_dir: Path, active_location: str):
    """Odczytuje numery protokolow zydowskich z konfiguracji."""
    cfg_path = backup_dir / active_location / "launcher_db_config.json"
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        data = raw.get("default_location", raw)
        return [p.strip() for p in str(data.get("jewish_protocol_numbers") or "").split(",") if p.strip()]
    except Exception:
        return []


def compute_jewish_stats(jewish_protocols, ranking_real_all):
    """Statystyki wlascicieli zydowskich."""
    jewish_owners = []
    if jewish_protocols:
        by_protocol = {str(rec.get("numer_protokolu")): rec for rec in ranking_real_all}
        for protocol in jewish_protocols:
            owner = by_protocol.get(protocol)
            if owner:
                jewish_owners.append({**owner, "parcels_count": owner.get("plot_count", 0)})
    jewish_total_area = sum(o.get("total_area_m2") or 0 for o in jewish_owners)
    return {
        "owners_count": len(jewish_owners),
        "parcels_count": sum(o.get("plot_count") or 0 for o in jewish_owners),
        "total_area_m2": round(jewish_total_area, 2),
        "total_area_ha": round(jewish_total_area / 10000, 2),
        "owners": jewish_owners,
    }


# ---- Glowna funkcja ----

async def compute_all_stats(db: AsyncSession) -> dict:
    """Glowna funkcja obliczajaca wszystkie statystyki dla endpointu /api/stats."""
    current_year = datetime.now().year

    total_owners = await fetch_one(db, "SELECT COUNT(*) as cnt FROM wlasciciele")
    total_plots = await fetch_one(db,
        "SELECT COUNT(*) as cnt FROM obiekty_geograficzne WHERE kategoria != 'obrys_miejscowosci'"
    )
    total_people = await fetch_one(db, "SELECT COUNT(*) as cnt FROM osoby_genealogia")

    categories = await fetch_all(db, """
        SELECT kategoria, COUNT(*) as count
        FROM obiekty_geograficzne
        WHERE kategoria IS NOT NULL AND kategoria != 'obrys_miejscowosci'
        GROUP BY kategoria
    """)
    category_counts = {c["kategoria"]: c["count"] for c in categories}

    owners_count = total_owners["cnt"] if total_owners else 0
    plots_count = total_plots["cnt"] if total_plots else 0
    people_count = total_people["cnt"] if total_people else 0

    objects = await fetch_objects_with_geom(db)
    links = await fetch_owner_links(db)

    object_metrics, location_outline_area, polygon_areas = compute_object_metrics(objects)

    area_stats = compute_area_stats(polygon_areas)

    ranking_real, ranking_protocol = compute_owner_rankings(links, object_metrics)
    parcels_ranking = compute_parcels_ranking(objects, links, object_metrics)

    protocols_per_day = await fetch_protocols_per_day(db)

    # Demografia urzedowa
    demografia_official = await fetch_all(db,
        "SELECT rok, populacja_ogolem, katolicy, zydzi, inni, opis FROM demografia ORDER BY rok")
    for row in demografia_official:
        if not row.get("populacja_ogolem"):
            row["populacja_ogolem"] = (row.get("katolicy") or 0) + (row.get("zydzi") or 0) + (row.get("inni") or 0)
    official_events_map = {row.get("rok"): row.get("opis") for row in demografia_official if row.get("opis")}

    # Genealogia
    people = await fetch_all(db,
        "SELECT id, json_id, imie_nazwisko, plec, rok_urodzenia, rok_smierci, numer_domu, id_ojca, id_matki FROM osoby_genealogia")

    db_has_years = any(p.get("rok_urodzenia") or p.get("rok_smierci") for p in people)
    backup_marriage_years = []
    if not db_has_years:
        backup_people, backup_marriage_years = load_backup_genealogy_people(BACKUP_DIR, ACTIVE_LOCATION)
        if backup_people:
            people = backup_people

    marriage_years = await fetch_marriage_years(db)
    if backup_marriage_years:
        marriage_years.extend(y for y in backup_marriage_years if valid_year(y, current_year))

    genealogy_stats = compute_genealogy_stats(people, marriage_years, backup_marriage_years)
    genealogy_stats["total_people"] = people_count

    demografia_metrical = compute_demography_metrical(people, official_events_map, current_year, demografia_official)

    # Statystyki zydowskie
    jewish_protocols = set(read_jewish_protocols(BACKUP_DIR, ACTIVE_LOCATION))
    jewish_stats = compute_jewish_stats(jewish_protocols, ranking_real.get("all_plots", []))

    # Procent narysowanych dzialek
    drawn_count = sum(1 for o in objects if o.get("geometria"))

    return {
        "general_stats": {"total_owners": owners_count, "total_plots": plots_count, "total_people": people_count},
        "total_owners": owners_count,
        "total_plots": plots_count,
        "total_people": people_count,
        "category_counts": category_counts,
        "area_stats": area_stats,
        "rivers_stats": compute_line_stats(objects, object_metrics, "rzeka"),
        "roads_stats": compute_line_stats(objects, object_metrics, "droga"),
        "drawn_percentage": {
            "drawn_count": drawn_count,
            "protocol_count": plots_count,
            "percentage": round((drawn_count / plots_count * 100) if plots_count else 0, 1),
            "missing_count": max(plots_count - drawn_count, 0),
        },
        "location_area": {
            "area_hectares": round(location_outline_area / 10000, 2) if location_outline_area else None,
            "area_km2": round(location_outline_area / 1_000_000, 2) if location_outline_area else None,
        },
        "jewish_stats": jewish_stats,
        "rankings_real": ranking_real,
        "rankings_protocol": ranking_protocol,
        "parcels_ranking": parcels_ranking,
        "rivers_ranking": compute_line_ranking(objects, object_metrics, "rzeka", "river_name"),
        "roads_ranking": compute_line_ranking(objects, object_metrics, "droga", "road_number"),
        "demografia": demografia_metrical,
        "demografia_official": demografia_official,
        "protocols_per_day": protocols_per_day,
        "genealogy_stats": genealogy_stats,
    }
