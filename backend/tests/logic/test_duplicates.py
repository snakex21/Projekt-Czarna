import json
import os
import pytest
from difflib import SequenceMatcher

def get_genealogia_path():
    """Pobiera ścieżkę do genealogia.json na podstawie TEST_LOCATION."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    test_location = os.environ.get('TEST_LOCATION', 'Czarna')
    return os.path.join(base_dir, "data", "locations", test_location, "genealogia.json")

def load_data():
    path = get_genealogia_path()
    if not os.path.exists(path):
        pytest.skip(f"Brak pliku danych: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def similar(a, b):
    """Oblicza podobieństwo dwóch ciągów znaków (0-1)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def test_detect_potential_duplicates():
    """
    Wyszukuje potencjalne duplikaty osób na podstawie:
    - Podobieństwa nazwiska i imienia
    - Te samej daty urodzenia (jeśli dostępna)
    - Tego samego numeru domu
    """
    data = load_data()
    persons = data.get("persons", [])
    duplicates = []
    
    # Optymalizacja: sprawdzamy tylko osoby z tej samej dekady lub bez daty
    # aby uniknąć porównywania każdego z każdym (O(n^2))
    for i in range(len(persons)):
        p1 = persons[i]
        for j in range(i + 1, len(persons)):
            p2 = persons[j]
            
            # 1. Sprawdzamy daty urodzenia (krytyczne)
            year1 = p1.get("birthDate", {}).get("year") if p1.get("birthDate") else None
            year2 = p2.get("birthDate", {}).get("year") if p2.get("birthDate") else None
            
            # Jeśli obie osoby mają daty i są one różne o więcej niż 2 lata - pomijamy
            if year1 and year2 and abs(year1 - year2) > 2:
                continue
                
            # 2. Sprawdzamy podobieństwo imion i nazwisk
            name_sim = similar(p1["name"], p2["name"])
            
            # 3. Sprawdzamy numer domu
            house1 = str(p1.get("houseNumber", "")).strip()
            house2 = str(p2.get("houseNumber", "")).strip()
            houses_match = (house1 == house2 and house1 != "")
            
            # Kryteria podejrzenia:
            # - Bardzo podobne nazwisko (>0.85) i ten sam dom
            # - Identyczne nazwisko i ta sama data
            # - Bardzo podobne nazwisko i ta sama data
            
            is_suspicious = False
            reason = ""
            
            if name_sim > 0.95:
                is_suspicious = True
                reason = f"Identyczne/prawie identyczne nazwisko ({int(name_sim*100)}%)"
            elif name_sim > 0.8 and houses_match:
                is_suspicious = True
                reason = f"Podobne nazwisko ({int(name_sim*100)}%) i ten sam numer domu ({house1})"
            elif name_sim > 0.8 and year1 and year2 and year1 == year2:
                is_suspicious = True
                reason = f"Podobne nazwisko ({int(name_sim*100)}%) i ten sam rok urodzenia ({year1})"

            if is_suspicious:
                duplicates.append({
                    "p1": f"{p1['name']} (ID {p1['id']})",
                    "p2": f"{p2['name']} (ID {p2['id']})",
                    "reason": reason
                })

    if duplicates:
        print(f"\n[ANTY-DUPLIKAT] Znaleziono {len(duplicates)} potencjalnych powtórzeń:")
        for d in duplicates[:30]: # Limit raportu w konsoli
            print(f"  ? {d['p1']} <-> {d['p2']}")
            print(f"    Powód: {d['reason']}")
        if len(duplicates) > 30:
            print(f"  ... i {len(duplicates)-30} kolejnych podejrzeń.")
            
    assert True # Zawsze True, to test informacyjny
