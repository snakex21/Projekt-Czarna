"""
Plik: test_data_integrity.py
Opis: Automatyczne testy spójności danych JSON (Integrity Checks).
      Sprawdza poprawność logiczną plików genealogia.json dla wszystkich miejscowości.
"""

import os
import json
import pytest

# Ścieżka bazowa projektu (wychodzimy z backend/tests/unit/ do root)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BACKUP_DIR = os.path.join(BASE_DIR, "data", "locations")

def get_all_genealogy_files():
    """Znajduje wszystkie pliki genealogia.json w folderze backup."""
    locs = []
    if not os.path.exists(BACKUP_DIR):
        return locs
    
    for item in os.listdir(BACKUP_DIR):
        loc_path = os.path.join(BACKUP_DIR, item)
        if os.path.isdir(loc_path):
            gen_file = os.path.join(loc_path, "genealogia.json")
            if os.path.exists(gen_file):
                locs.append((item, gen_file))
    return locs

def verify_genealogy(location, file_path):
    """
    Analizuje plik genealogia.json i zwraca listę znalezionych błędów logicznych.
    """
    errors = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return [f"Plik JSON jest uszkodzony: {e}"]

    persons = data.get("persons", [])
    if not persons:
        return []

    person_map = {str(p.get("id")): p for p in persons if p.get("id") is not None}
    person_ids = set(person_map.keys())

    for p in persons:
        pid = str(p.get("id", "brak_ID"))
        name = p.get("name", "Nieznany")
        
        for parent_key in ["fatherId", "motherId"]:
            parent_id = p.get(parent_key)
            if parent_id and str(parent_id) not in person_ids:
                label = "Ojciec" if parent_key == "fatherId" else "Matka"
                errors.append(f"Osoba {name} (ID {pid}): {label} (ID {parent_id}) nie istnieje w bazie.")

        spouses = p.get("spouses", [])
        if not isinstance(spouses, list):
            spouses = [spouses] if spouses else []
            
        for s_id in spouses:
            if s_id and str(s_id) not in person_ids:
                errors.append(f"Osoba {name} (ID {pid}): Małżonek (ID {s_id}) nie istnieje w bazie.")
            elif str(s_id) == pid:
                errors.append(f"Osoba {name} (ID {pid}): Jest przypisany jako własny małżonek.")

        def parse_year(y):
            if not y: return None
            try:
                clean = "".join([c for c in str(y) if c.isdigit()])
                return int(clean) if clean else None
            except: return None

        b_year = parse_year(p.get("birthYear"))
        d_year = parse_year(p.get("deathYear"))

        if b_year and d_year and d_year < b_year:
            errors.append(f"Osoba {name} (ID {pid}): Rok śmierci ({p.get('deathYear')}) jest wcześniejszy niż rok urodzenia ({p.get('birthYear')}).")

        if str(p.get("fatherId")) == pid or str(p.get("motherId")) == pid:
            errors.append(f"Osoba {name} (ID {pid}): Jest przypisana jako własny rodzic.")

    return errors

@pytest.mark.parametrize("location, file_path", get_all_genealogy_files())
def test_genealogia_integrity(location, file_path):
    """Test dla pytest."""
    errors = verify_genealogy(location, file_path)
    if errors:
        error_msg = f"\nBłędy spójności danych dla miejscowości [{location}]:\n" + "\n".join([f"  - {e}" for e in errors])
        pytest.fail(error_msg)

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 WERYFIKACJA SPÓJNOŚCI DANYCH GENEALOGICZNYCH")
    print("=" * 50)
    files = get_all_genealogy_files()
    if not files:
        print("❌ Nie znaleziono żadnych plików genealogia.json w backup/")
    
    total_locs = len(files)
    total_errors = 0
    
    for loc, path in files:
        print(f"\n📂 Miejscowość: {loc}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                d = json.load(f)
                print(f"📊 Liczba osób: {len(d.get('persons', []))}")
            
            errors = verify_genealogy(loc, path)
            
            if errors:
                for msg in errors:
                    print(f"❌ {msg}")
                    total_errors += 1
            else:
                print(f"✅ Brak błędów logicznych.")
        except Exception as e:
            print(f"💥 Błąd krytyczny: {e}")
            total_errors += 1
    
    print("\n" + "=" * 50)
    if total_errors == 0:
        print(f"🎉 Sukces! Wszystkie miejscowości ({total_locs}) są poprawne.")
    else:
        print(f"⚠️ Uwaga! Znaleziono łącznie {total_errors} błędów w {total_locs} miejscowościach.")
    print("=" * 50)

