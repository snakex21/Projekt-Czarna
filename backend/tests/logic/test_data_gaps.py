import json
import os
import pytest

def get_genealogia_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    test_location = os.environ.get('TEST_LOCATION', 'Czarna')
    return os.path.join(base_dir, "data", "locations", test_location, "genealogia.json")

def load_data():
    path = get_genealogia_path()
    if not os.path.exists(path):
        pytest.skip(f"Brak pliku danych: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_chronological_gaps():
    """Analizuje luki w danych rok po roku."""
    data = load_data()
    years = {}
    
    # Zbieramy wszystkie daty (urodzenia, zgony, śluby - jeśli są)
    for p in data.get("persons", []):
        for date_key in ["birthDate", "deathDate"]:
            y = p.get(date_key, {}).get("year") if p.get(date_key) else None
            if y and isinstance(y, int) and 1700 < y < 2025:
                years[y] = years.get(y, 0) + 1
                
    if not years:
        pytest.skip("Brak danych z datami do analizy.")
        
    min_year = min(years.keys())
    max_year = max(years.keys())
    
    gaps = []
    current_gap_start = None
    
    for y in range(min_year, max_year + 1):
        count = years.get(y, 0)
        if count == 0:
            if current_gap_start is None:
                current_gap_start = y
        else:
            if current_gap_start is not None:
                if y - current_gap_start > 1:
                    gaps.append(f"{current_gap_start}-{y-1}")
                else:
                    gaps.append(str(current_gap_start))
                current_gap_start = None
                
    if gaps:
        print(f"\n📅 Wykryto luki w danych (lata bez żadnego wpisu):")
        print(f"  Zakres danych: {min_year} - {max_year}")
        print(f"  Brakujące lata: {', '.join(gaps)}")
    else:
        print(f"\n📅 Brak luk w danych w zakresie {min_year}-{max_year}. Świetna ciągłość!")
        
    # Sprawdź „podejrzanie niską” aktywność (np. mniej niż 2 wpisy na rok w środku zakresu)
    low_activity = []
    for y in range(min_year + 5, max_year - 5): # Pomijamy końce
        if 0 < years.get(y, 0) < 2:
            low_activity.append(str(y))
            
    if low_activity:
        print(f"\n[PODEJRZENIE LUK] Lata z bardzo niską aktywnością (prawdopodobnie niepełne dane):")
        print(f"  Lata: {', '.join(low_activity[:20])}")

    assert True
