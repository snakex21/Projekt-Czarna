"""
================================================================================
Skrypt: migrate_data.py
Opis: Migracja danych katastralnych z plików JSON do bazy PostgreSQL
      Obsługuje import właścicieli, obiektów geograficznych, demografii i genealogii
================================================================================
"""

import json
import os
import psycopg2
from psycopg2.extras import execute_values
import re
from dotenv import load_dotenv

# ================================================================================
# KONFIGURACJA ŚRODOWISKA
# ================================================================================

# Załadowanie zmiennych środowiskowych
load_dotenv()

def get_env_variable(var_name, default_value=None):
    """
    Pobiera wartość zmiennej środowiskowej z opcjonalną wartością domyślną.
    
    Args:
        var_name: Nazwa zmiennej środowiskowej
        default_value: Wartość domyślna jeśli zmienna nie istnieje
    
    Returns:
        Wartość zmiennej lub wartość domyślna
    """
    value = os.getenv(var_name, default_value)
    if value is None:
        print(f"⚠️  Uwaga: Zmienna środowiskowa {var_name} nie jest ustawiona!")
    return value

print("\n" + "=" * 50)
print("      SKRYPT MIGRACJI DANYCH KATASTRALNYCH")
print("=" * 50)

# ================================================================================
# ŚCIEŻKI I PARAMETRY POŁĄCZENIA
# ================================================================================

# Lokalizacje plików źródłowych
BACKUP_DIR = "../backup/"
OWNER_DATA_FILE = os.path.join(BACKUP_DIR, "owner_data_to_import.json")
PARCEL_DATA_FILE = os.path.join(BACKUP_DIR, "parcels_data.json")
DEMOGRAFIA_DATA_FILE = os.path.join(BACKUP_DIR, "demografia.json")
GENEALOGIA_DATA_FILE = os.path.join(BACKUP_DIR, "genealogia.json")

# Konfiguracja bazy danych PostgreSQL
DB_CONFIG = {
    "host": get_env_variable("DB_HOST", "localhost"),
    "dbname": get_env_variable("DB_NAME", "mapa_czarna_db"),
    "user": get_env_variable("DB_USER", "postgres"),
    "password": get_env_variable("DB_PASSWORD", "1234"),
    "port": get_env_variable("DB_PORT", "5432")
}

print("\n📊 Konfiguracja połączenia:")
print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
print(f"   Baza: {DB_CONFIG['dbname']}")
print(f"   Użytkownik: {DB_CONFIG['user']}")
print("=" * 50)

# ================================================================================
# FUNKCJE POMOCNICZE
# ================================================================================

def parse_polish_date(date_str):
    """
    Konwertuje polską datę tekstową na format SQL YYYY-MM-DD.
    Obsługuje format: '15 maja 1930 rok'
    """
    if not date_str:
        return None

    months = {
        "stycznia": "01", "luty": "02", "lutego": "02", "marca": "03",
        "kwietnia": "04", "maja": "05", "czerwca": "06", "lipca": "07",
        "sierpnia": "08", "września": "09", "października": "10",
        "listopada": "11", "grudnia": "12",
    }

    try:
        parts = date_str.lower().replace("rok", "").strip().split()
        if len(parts) < 3:
            return None

        day = parts[0].zfill(2)
        month_name = parts[1]
        year = parts[2]
        month = months.get(month_name)

        if not month:
            return None

        return f"{year}-{month}-{day}"
    except Exception:
        return None

def get_wkt_from_geometry(geom_data, kategoria):
    """
    Konwertuje dane geometryczne na format WKT (Well-Known Text).
    Obsługuje punkty, linie i poligony w zależności od kategorii obiektu.
    """
    if not geom_data:
        return None
    
    # Obiekty punktowe
    if kategoria in ["dom", "kapliczka", "budynek", "dworzec", "obiekt_specjalny"]:
        lat, lng = geom_data
        return f"POINT({lng} {lat})"
    
    # Obiekty liniowe    
    if kategoria in ["droga", "rzeka"]:
        if len(geom_data) < 2: 
            return None
        coords_str = ", ".join([f"{lng} {lat}" for lat, lng in geom_data])
        return f"LINESTRING({coords_str})"
    
    # Poligony    
    if len(geom_data) > 2 and isinstance(geom_data[0], list):
        if geom_data[0] != geom_data[-1]:
            geom_data.append(geom_data[0])
        coords_str = ", ".join([f"{lng} {lat}" for lat, lng in geom_data])
        return f"POLYGON(({coords_str}))"
        
    return None

def norm(num):
    """Normalizuje numer działki do formatu string (np. '800/23')."""
    if isinstance(num, dict):
        a = str(num.get("numerator") or num.get("numarator") or "").strip()
        b = str(num.get("denominator") or "").strip()
        return f"{a}/{b}" if a and b else a
    return str(num).strip()

# ================================================================================
# GŁÓWNA LOGIKA MIGRACJI
# ================================================================================

conn = None
try:
    # --- ETAP 1: WCZYTYWANIE DANYCH ---
    print("\n--- Etap 1: Wczytywanie danych źródłowych ---")
    
    with open(OWNER_DATA_FILE, "r", encoding="utf-8") as f:
        owner_data = json.load(f)
    print(f"✔️ Załadowano {len(owner_data)} właścicieli")

    with open(PARCEL_DATA_FILE, "r", encoding="utf-8") as f:
        parcel_data = json.load(f)
    print(f"✔️ Załadowano {len(parcel_data)} obiektów geograficznych")

    # Opcjonalne pliki
    demografia_data = []
    if os.path.exists(DEMOGRAFIA_DATA_FILE):
        with open(DEMOGRAFIA_DATA_FILE, "r", encoding="utf-8") as f:
            demografia_data = json.load(f)
        print(f"✔️ Załadowano {len(demografia_data)} wpisów demograficznych")
    else:
        print(f"⚠️  Plik demografii nie znaleziony - pomijam")

    genealogia_data = []
    if os.path.exists(GENEALOGIA_DATA_FILE):
        with open(GENEALOGIA_DATA_FILE, "r", encoding="utf-8") as f:
            genealogia_data = json.load(f).get("persons", [])
        print(f"✔️ Załadowano {len(genealogia_data)} osób genealogicznych")
    else:
        print(f"⚠️  Plik genealogii nie znaleziony - pomijam")

    # --- ETAP 2: INICJALIZACJA BAZY ---
    print("\n--- Etap 2: Przygotowanie bazy danych ---")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding("UTF8")
    cur = conn.cursor()
    print("✔️ Połączono z bazą danych")
    
    # Czyszczenie tabel
    cur.execute("""
        TRUNCATE TABLE malzenstwa, osoby_genealogia, demografia, 
                      dzialki_wlasciciele, powiazania_protokolow, 
                      obiekty_geograficzne, wlasciciele 
        RESTART IDENTITY CASCADE
    """)
    print("✔️ Tabele wyczyszczone")
    
    # --- ETAP 3: IMPORT WŁAŚCICIELI ---
    print("\n--- Etap 3: Import właścicieli ---")
    owner_id_map = {}
    
    for key, v in owner_data.items():
        try:
            protocol_date = parse_polish_date(v.get("protocolDate"))
            protocol_location = v.get("protocolLocation", "")
            order_number_str = str(v.get("orderNumber", "")).strip()
            order_number = int(order_number_str) if order_number_str.isdigit() else None

            cur.execute(
                """
                INSERT INTO wlasciciele (
                    unikalny_klucz, nazwa_wlasciciela, numer_protokolu, numer_domu, 
                    genealogia, historia_wlasnosci, uwagi, wspolwlasnosc, 
                    powiazania_i_transakcje, interpretacja_i_wnioski, 
                    data_protokolu, miejsce_protokolu
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
                RETURNING id
                """,
                (
                    key, v.get("ownerName", ""), order_number, v.get("houseNumber", ""),
                    v.get("genealogy", ""), v.get("ownershipHistory", ""), 
                    v.get("remarks", ""), v.get("wspolwlasnosc", ""), 
                    v.get("powiazania_i_transakcje", v.get("relacje_rodzinne", "")),
                    v.get("interpretacja_i_wnioski", ""), protocol_date, protocol_location,
                ),
            )
            owner_id = cur.fetchone()[0]
            owner_id_map[key] = owner_id
        except Exception as e:
            print(f"❌ Błąd przy właścicielu '{key}': {e}")
            conn.rollback()

    print(f"✔️ Wstawiono {len(owner_id_map)} właścicieli")

    # --- ETAP 4: IMPORT OBIEKTÓW GEOGRAFICZNYCH ---
    print("\n--- Etap 4: Import obiektów geograficznych ---")

    objects_to_insert = []
    for raw_num, data in parcel_data.items():
        num_norm = norm(raw_num)
        kategoria = data.get("kategoria") or "rolna"
        wkt = get_wkt_from_geometry(data.get("geometria"), kategoria)
        objects_to_insert.append((num_norm, kategoria, wkt))
    
    # Masowe wstawianie
    query = """
        INSERT INTO obiekty_geograficzne (nazwa_lub_numer, kategoria, geometria) 
        VALUES %s
        ON CONFLICT (nazwa_lub_numer, kategoria) DO NOTHING
        RETURNING id, nazwa_lub_numer, kategoria
    """
    execute_values(cur, query, objects_to_insert)
    
    object_id_map = {(num, kat): obj_id for obj_id, num, kat in cur.fetchall()}
    print(f"✔️ Wstawiono {len(object_id_map)} obiektów")

    # --- ETAP 5: POWIĄZANIA WŁAŚCICIEL-DZIAŁKA ---
    print("\n--- Etap 5: Tworzenie powiązań ---")
    link_rows, seen = [], set()

    def add_link(owner_id, object_id, typ):
        """Dodaje unikalne powiązanie do listy."""
        key = (owner_id, object_id, typ)
        if key not in seen:
            link_rows.append((owner_id, object_id, typ, ""))
            seen.add(key)

    def ensure_object(num_norm: str, hint_building: bool):
        """Zapewnia istnienie obiektu w bazie, tworzy jeśli brak."""
        if not num_norm: 
            return None
            
        wanted_cat = "budowlana" if hint_building else "rolna"
        wanted_key = (num_norm, wanted_cat)
        
        # Sprawdź czy istnieje
        if wanted_key in object_id_map:
            return object_id_map[wanted_key]
            
        # Dla działek rolnych - szukaj alternatyw
        if not hint_building:
            for (num, cat), obj_id in object_id_map.items():
                if num == num_norm and cat != "budowlana":
                    return obj_id
                    
        # Utwórz nowy obiekt
        cur.execute(
            """INSERT INTO obiekty_geograficzne 
               (nazwa_lub_numer, kategoria, geometria) 
               VALUES (%s, %s, NULL) RETURNING id""",
            (num_norm, wanted_cat),
        )
        new_id = cur.fetchone()[0]
        object_id_map[wanted_key] = new_id
        return new_id

    # Przetwarzanie własności
    for owner_key, details in owner_data.items():
        owner_id = owner_id_map.get(owner_key)
        if not owner_id:
            continue
        
        # Własność rzeczywista
        for key in ("realbuildingPlots", "realagriculturalPlots"):
            for p in details.get(key, []):
                obj_id = ensure_object(norm(p), key.startswith("realbuilding"))
                if obj_id: 
                    add_link(owner_id, obj_id, "własność rzeczywista")
                
        # Własność z protokołu
        for key in ("buildingPlots", "agriculturalPlots"):
            for p in details.get(key, []):
                obj_id = ensure_object(norm(p), key.startswith("building"))
                if obj_id: 
                    add_link(owner_id, obj_id, "własność z protokołu")
    
    # Wstaw powiązania
    if link_rows:
        execute_values(
            cur,
            """INSERT INTO dzialki_wlasciciele 
               (wlasciciel_id, obiekt_id, typ_posiadania, opis_udzialu) 
               VALUES %s
               ON CONFLICT (wlasciciel_id, obiekt_id, typ_posiadania) DO NOTHING""",
            link_rows
        )
        print(f"✔️ Utworzono {cur.rowcount} powiązań właściciel-działka")

    # --- ETAP 5.5: POWIĄZANIA DOMÓW ---
    print("\n--- Etap 5.5: Powiązania właściciel-dom ---")
    house_links = []
    
    # Mapa domów i budynków
    house_objects_map = {
        num: obj_id for (num, cat), obj_id in object_id_map.items() 
        if cat in ['dom', 'budynek']
    }

    for owner_key, details in owner_data.items():
        owner_id = owner_id_map.get(owner_key)
        house_number = details.get("houseNumber")

        if owner_id and house_number:
            house_object_id = house_objects_map.get(house_number)
            if house_object_id:
                key = (owner_id, house_object_id, "własność rzeczywista")
                if key not in seen:
                    house_links.append((owner_id, house_object_id, "własność rzeczywista", ""))
                    seen.add(key)

    if house_links:
        execute_values(
            cur,
            """INSERT INTO dzialki_wlasciciele 
               (wlasciciel_id, obiekt_id, typ_posiadania, opis_udzialu) 
               VALUES %s
               ON CONFLICT (wlasciciel_id, obiekt_id, typ_posiadania) DO NOTHING""",
            house_links
        )
        print(f"✔️ Utworzono {cur.rowcount} powiązań właściciel-dom")

    # --- ETAP 6: IMPORT DEMOGRAFII ---
    if demografia_data:
        print("\n--- Etap 6: Import danych demograficznych ---")
        demografia_to_insert = [
            (e.get("rok"), e.get("populacja_ogolem"), e.get("katolicy"), 
             e.get("zydzi"), e.get("inni"), e.get("opis"))
            for e in demografia_data
        ]
        execute_values(
            cur, 
            """INSERT INTO demografia 
               (rok, populacja_ogolem, katolicy, zydzi, inni, opis) 
               VALUES %s""", 
            demografia_to_insert
        )
        print(f"✔️ Wstawiono {len(demografia_to_insert)} wpisów")
        
    # --- ETAP 7: IMPORT GENEALOGII ---
    if genealogia_data:
        print("\n--- Etap 7: Import danych genealogicznych ---")
        json_id_to_db_id = {}

        # Wstaw osoby
        print("  → Wstawianie osób...")
        for osoba in genealogia_data:
            id_protokolu = owner_id_map.get(osoba.get("protocolKey"))
            birth_date_obj = osoba.get("birthDate")
            rok_urodzenia = birth_date_obj.get("year") if birth_date_obj else None
            death_date_obj = osoba.get("deathDate")
            rok_smierci = death_date_obj.get("year") if death_date_obj else None

            cur.execute(
                """INSERT INTO osoby_genealogia 
                   (json_id, imie_nazwisko, plec, numer_domu, 
                    rok_urodzenia, rok_smierci, id_protokolu, uwagi) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
                   RETURNING id""",
                (osoba["id"], osoba["name"], osoba.get("gender"), 
                 osoba.get("houseNumber"), rok_urodzenia, rok_smierci, 
                 id_protokolu, osoba.get("notes"))
            )
            db_id = cur.fetchone()[0]
            json_id_to_db_id[osoba["id"]] = db_id
        print(f"  ✔️ Wstawiono {len(json_id_to_db_id)} osób")

        # Aktualizuj relacje rodzicielskie
        print("  → Tworzenie relacji rodzicielskich...")
        for osoba in genealogia_data:
            db_id = json_id_to_db_id.get(osoba["id"])
            id_ojca = json_id_to_db_id.get(osoba.get("fatherId"))
            id_matki = json_id_to_db_id.get(osoba.get("motherId"))
            if db_id and (id_ojca or id_matki):
                cur.execute(
                    """UPDATE osoby_genealogia 
                       SET id_ojca = %s, id_matki = %s 
                       WHERE id = %s""", 
                    (id_ojca, id_matki, db_id)
                )

        # Wstaw małżeństwa
        print("  → Tworzenie relacji małżeńskich...")
        malzenstwa_to_insert = []
        seen_malzenstwa = set()
        
        for osoba in genealogia_data:
            id1 = json_id_to_db_id.get(osoba["id"])
            for spouse_json_id in osoba.get("spouseIds", []):
                id2 = json_id_to_db_id.get(spouse_json_id)
                if id1 and id2:
                    para = tuple(sorted((id1, id2)))
                    if para not in seen_malzenstwa:
                        malzenstwa_to_insert.append(para)
                        seen_malzenstwa.add(para)

        if malzenstwa_to_insert:
            execute_values(
                cur, 
                "INSERT INTO malzenstwa (malzonek1_id, malzonek2_id) VALUES %s", 
                malzenstwa_to_insert
            )
            print(f"  ✔️ Wstawiono {len(malzenstwa_to_insert)} małżeństw")
    
    # Zatwierdź transakcję
    conn.commit()
    print("\n" + "=" * 50)
    print("✅  MIGRACJA ZAKOŃCZONA POMYŚLNIE")
    print("=" * 50)

except FileNotFoundError as e:
    print(f"\n❌ BŁĄD: Nie znaleziono pliku!")
    print(f"   Brakujący plik: {e.filename}")
    print(f"   Upewnij się, że pliki JSON są w folderze 'backup'")
except Exception as e:
    print(f"\n❌ BŁĄD: {e}")
    if conn:
        conn.rollback()
        print("   → Zmiany wycofane")
finally:
    # Zamknij połączenie
    if conn:
        cur.close()
        conn.close()
        print("\nPołączenie z bazą zamknięte")