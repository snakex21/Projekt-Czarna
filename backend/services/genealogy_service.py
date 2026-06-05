"""Serwis genealogii — transformacja danych dla endpointow."""
from collections import defaultdict


def build_persons_map(persons_rows, marriages_rows):
    """Buduje slownik osob z relacjami rodzicielskimi i malzenskimi."""
    persons_map = {}
    for p in persons_rows:
        pid = p["id"]
        persons_map[pid] = {
            "id": pid,
            "originalId": p["json_id"],
            "name": p["name"],
            "gender": p["gender"],
            "birthDate": {"year": p["rok_urodzenia"]} if p["rok_urodzenia"] else None,
            "deathDate": {"year": p["rok_smierci"]} if p["rok_smierci"] else None,
            "notes": p["notes"],
            "protocolId": p["protocol_key"],
            "parentIds": [],
            "spouseIds": [],
            "marriages": [],
        }
        if p["id_ojca"]:
            persons_map[pid]["parentIds"].append(p["id_ojca"])
        if p["id_matki"]:
            persons_map[pid]["parentIds"].append(p["id_matki"])

    for m in marriages_rows:
        id1, id2 = m["malzonek1_id"], m["malzonek2_id"]
        date_str = m["data_slubu"] or (str(m["rok_slubu"]) if m["rok_slubu"] else None)
        if id1 in persons_map and id2 in persons_map:
            if id2 not in persons_map[id1]["spouseIds"]:
                persons_map[id1]["spouseIds"].append(id2)
                persons_map[id1]["marriages"].append({"spouseId": id2, "date": date_str})
            if id1 not in persons_map[id2]["spouseIds"]:
                persons_map[id2]["spouseIds"].append(id1)
                persons_map[id2]["marriages"].append({"spouseId": id1, "date": date_str})

    return persons_map


def build_persons_json_format(persons_rows, marriages_rows):
    """Buduje liste osob w formacie JSON z relacjami (json_id zamiast db_id)."""
    db_id_to_json = {p["id"]: p["json_id"] for p in persons_rows}

    spouse_map = {}
    marriages_map = {}
    for m in marriages_rows:
        id1, id2 = m["malzonek1_id"], m["malzonek2_id"]
        json1, json2 = db_id_to_json.get(id1), db_id_to_json.get(id2)
        if json1 and json2:
            spouse_map.setdefault(id1, []).append(json2)
            spouse_map.setdefault(id2, []).append(json1)
            marriages_map.setdefault(id1, []).append({"spouseId": json2, "year": m.get("rok_slubu")})
            marriages_map.setdefault(id2, []).append({"spouseId": json1, "year": m.get("rok_slubu")})

    persons_json = []
    for p in persons_rows:
        person_data = {
            "id": p["json_id"],
            "dbId": p["id"],
            "name": p["imie_nazwisko"],
            "gender": p["plec"],
            "houseNumber": p.get("numer_domu"),
            "protocolKey": p.get("protocol_key"),
            "parents": [],
            "children": [],
            "spouses": spouse_map.get(p["id"], []),
            "marriages": marriages_map.get(p["id"], []),
            "notes": p.get("uwagi"),
            "birthDate": {"year": p["rok_urodzenia"]} if p.get("rok_urodzenia") else None,
            "deathDate": {"year": p["rok_smierci"]} if p.get("rok_smierci") else None,
        }

        if p.get("id_ojca"):
            father_json = db_id_to_json.get(p["id_ojca"])
            if father_json:
                person_data["fatherId"] = father_json
                person_data["parents"].append(father_json)
        else:
            person_data["fatherId"] = None

        if p.get("id_matki"):
            mother_json = db_id_to_json.get(p["id_matki"])
            if mother_json:
                person_data["motherId"] = mother_json
                person_data["parents"].append(mother_json)
        else:
            person_data["motherId"] = None

        persons_json.append(person_data)

    _attach_children(persons_rows, persons_json, db_id_to_json)

    return persons_json


def _attach_children(persons_rows, persons_json, db_id_to_json):
    """Dolacza liste dzieci do kazdej osoby."""
    person_db_id_map = {p["json_id"]: p["id"] for p in persons_rows}
    children_map = {}
    for p in persons_rows:
        for parent_key in ("id_ojca", "id_matki"):
            parent_id = p.get(parent_key)
            if parent_id:
                children_map.setdefault(parent_id, []).append(p["json_id"])

    for person in persons_json:
        person_db_id = person_db_id_map.get(person["id"])
        if person_db_id:
            person["children"] = children_map.get(person_db_id, [])


def build_family_tree_persons(all_persons_rows, all_marriages_rows):
    """Buduje liste osob dla endpointu drzewa genealogicznego."""
    db_id_to_json = {p["id"]: p["json_id"] for p in all_persons_rows}
    spouse_map = {}
    for m in all_marriages_rows:
        id1, id2 = m["malzonek1_id"], m["malzonek2_id"]
        j1, j2 = db_id_to_json.get(id1), db_id_to_json.get(id2)
        if j1 and j2:
            spouse_map.setdefault(id1, []).append(j2)
            spouse_map.setdefault(id2, []).append(j1)

    persons_json = []
    for p in all_persons_rows:
        persons_json.append({
            "id": p["json_id"],
            "name": p["imie_nazwisko"],
            "gender": p["plec"],
            "houseNumber": p.get("numer_domu"),
            "birthDate": {"year": p["rok_urodzenia"]} if p.get("rok_urodzenia") else None,
            "deathDate": {"year": p["rok_smierci"]} if p.get("rok_smierci") else None,
            "protocolKey": p.get("protocol_key"),
            "fatherId": db_id_to_json.get(p.get("id_ojca")),
            "motherId": db_id_to_json.get(p.get("id_matki")),
            "spouseIds": spouse_map.get(p["id"], []),
            "notes": p.get("uwagi"),
        })

    return persons_json
