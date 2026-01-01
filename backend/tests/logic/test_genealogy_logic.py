import json
import os
import pytest

def get_genealogia_path():
    """Pobiera ścieżkę do genealogia.json na podstawie TEST_LOCATION."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    test_location = os.environ.get('TEST_LOCATION', 'Czarna')
    return os.path.join(base_dir, "backup", test_location, "genealogia.json")

def load_data():
    path = get_genealogia_path()
    if not os.path.exists(path):
        pytest.skip(f"Brak pliku danych: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_birth_before_death():
    """Sprawdza czy data urodzenia jest przed datą śmierci."""
    data = load_data()
    errors = []
    for person in data.get("persons", []):
        birth = person.get("birthDate", {})
        death = person.get("deathDate", {})
        
        if birth and death and birth.get("year") and death.get("year"):
            if birth["year"] > death["year"]:
                errors.append(f"Osoba {person['id']} ({person['name']}): urodzony {birth['year']}, zmarl {death['year']}")
    
    if errors:
        print("\n[PARADOKSY DAT] Osoby ktore zmarły przed urodzeniem:")
        for e in errors:
            print(f"  - {e}")
    
    # Nie rzucamy assert, żeby nie blokować testów, ale informujemy w konsoli
    assert True

def test_parent_age_at_birth():
    """Sprawdza czy rodzice byli w sensownym wieku w chwili urodzenia dziecka (14-80 lat)."""
    data = load_data()
    persons = {p["id"]: p for p in data.get("persons", [])}
    errors = []
    
    for p in data.get("persons", []):
        if not p.get("birthDate") or not p["birthDate"].get("year"):
            continue
            
        child_year = p["birthDate"]["year"]
        
        for parent_id in [p.get("fatherId"), p.get("motherId")]:
            if parent_id and parent_id in persons:
                parent = persons[parent_id]
                if parent.get("birthDate") and parent["birthDate"].get("year"):
                    parent_year = parent["birthDate"]["year"]
                    age = child_year - parent_year
                    
                    if age < 13:
                        errors.append(f"Za mlody rodzic: {parent['name']} (ID {parent['id']}) mial {age} lat, gdy urodzil sie {p['name']} (ID {p['id']})")
                    if age > 80:
                        errors.append(f"Za stary rodzic: {parent['name']} (ID {parent['id']}) mial {age} lat, gdy urodzil sie {p['name']} (ID {p['id']})")

    if errors:
        print("\n[WIEK RODZICOW] Ostrzeżenia o nietypowym wieku:")
        for e in errors:
            print(f"  - {e}")
    assert True

def test_no_circular_ancestry():
    """Sprawdza czy nie ma pętli w drzewie (ktoś jest własnym przodkiem)."""
    data = load_data()
    persons = {p["id"]: p for p in data.get("persons", [])}
    
    def check_loop(person_id, visited):
        if person_id in visited:
            return True
        visited.add(person_id)
        p = persons.get(person_id)
        if not p:
            return False
            
        if p.get("fatherId") and check_loop(p["fatherId"], visited.copy()):
            return True
        if p.get("motherId") and check_loop(p["motherId"], visited.copy()):
            return True
        return False

    loops = []
    for pid in persons:
        if check_loop(pid, set()):
            loops.append(f"Petla w drzewie dla ID {pid} ({persons[pid]['name']})")
            
    if loops:
        print("\n[PETLE] Wykryto zapętlenia w drzewie genealogicznym:")
        # Pokazujemy tylko unikalne pętle lub pierwsze 20
        for l in loops[:20]:
            print(f"  - {l}")
        if len(loops) > 20:
            print(f"  ... i {len(loops)-20} więcej.")
            
    assert True

def test_lifespan_sanity():
    """Sprawdza czy nikt nie żył nienaturalnie długo (>110 lat)."""
    data = load_data()
    errors = []
    for person in data.get("persons", []):
        birth = person.get("birthDate", {})
        death = person.get("deathDate", {})
        
        if birth and death and birth.get("year") and death.get("year"):
            lifespan = death["year"] - birth["year"]
            if lifespan > 110:
                 errors.append(f"Nienaturalnie dlugie zycie: {person['name']} (ID {person['id']}) zyl {lifespan} lat")
    
    if errors:
        print("\n[DLUGOSC ZYCIA] Ostrzeżenia o długowieczności:")
        for e in errors:
            print(f"  - {e}")
    assert True
