import json
import os
import psycopg2
from psycopg2.extras import execute_values
import re
from dotenv import load_dotenv

# --- WCZYTYWANIE KONFIGURACJI ŚRODOWISKOWEJ ---

# Załadowanie zmiennych środowiskowych z pliku .env
# Pozwala to na centralne zarządzanie konfiguracją bazy danych
# wspólnie z plikiem app.py, co zapewnia spójność połączeń.
load_dotenv()

# Funkcja pomocnicza do pobierania zmiennych środowiskowych
def get_env_variable(var_name, default_value=None):
    """
    Pobiera wartość zmiennej środowiskowej z opcjonalną wartością domyślną.
    Wyświetla ostrzeżenie jeśli zmienna nie jest ustawiona.
    
    Args:
        var_name: Nazwa zmiennej środowiskowej
        default_value: Wartość domyślna jeśli zmienna nie istnieje
        
    Returns:
        Wartość zmiennej środowiskowej lub wartość domyślna
    """
    value = os.getenv(var_name, default_value)
    if value is None:
        print(f"⚠️  Uwaga: Zmienna środowiskowa {var_name} nie jest ustawiona!")
    return value

print("\n=============================================")
print("===      SKRYPT MIGRACJI DANYCH         ===")
print("=============================================")

# --- KONFIGURACJA ---

# Określenie ścieżek do plików źródłowych JSON.
BACKUP_DIR = "../backup/"
OWNER_DATA_FILE = os.path.join(BACKUP_DIR, "owner_data_to_import.json")
PARCEL_DATA_FILE = os.path.join(BACKUP_DIR, "parcels_data.json")
DEMOGRAFIA_DATA_FILE = os.path.join(BACKUP_DIR, "demografia.json")
GENEALOGIA_DATA_FILE = os.path.join(BACKUP_DIR, "genealogia.json")

# Dane do połączenia z bazą danych PostgreSQL.
# Konfiguracja jest wczytywana ze zmiennych środowiskowych zdefiniowanych w pliku .env.
# Zapewnia to spójność z konfiguracją serwera Flask w app.py.
DB_CONFIG = {
    "host": get_env_variable("DB_HOST", "localhost"),
    "dbname": get_env_variable("DB_NAME", "mapa_czarna_db"),
    "user": get_env_variable("DB_USER", "postgres"),
    "password": get_env_variable("DB_PASSWORD", "1234"),
    "port": get_env_variable("DB_PORT", "5432")
}

# Wyświetlenie informacji o konfiguracji połączenia (bez hasła)
print("\n📊 Konfiguracja połączenia z bazą danych:")
print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
print(f"   Baza: {DB_CONFIG['dbname']}")
print(f"   Użytkownik: {DB_CONFIG['user']}")
print("=============================================")


def parse_polish_date(date_str):
    """
    Konwertuje datę w formacie tekstowym z polskimi nazwami miesięcy
    (np. '15 maja 1930 rok') na standardowy format SQL 'YYYY-MM-DD'.
    Funkcja jest odporna na różne przypadki gramatyczne miesięcy.
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
        # W przypadku błędu parsowania, zwraca None, aby uniknąć awarii skryptu.
        return None


def get_wkt_from_geometry(geom_data, kategoria):
    if not geom_data:
        return None
    
    if kategoria in ["dom", "kapliczka", "budynek", "dworzec", "obiekt_specjalny"]:
        lat, lng = geom_data
        return f"POINT({lng} {lat})"
        
    if kategoria in ["droga", "rzeka"]:
        if len(geom_data) < 2: return None
        coords_str = ", ".join([f"{lng} {lat}" for lat, lng in geom_data])
        return f"LINESTRING({coords_str})"
        
    if len(geom_data) > 2 and isinstance(geom_data[0], list):
        if geom_data[0] != geom_data[-1]:
            geom_data.append(geom_data[0])
        coords_str = ", ".join([f"{lng} {lat}" for lat, lng in geom_data])
        return f"POLYGON(({coords_str}))"
        
    return None


conn = None
try:
    # --- KROK 1: WCZYTYWANIE DANYCH Z PLIKÓW JSON ---
    print("\n--- Krok 1: Wczytywanie plików źródłowych JSON ---")
    with open(OWNER_DATA_FILE, "r", encoding="utf-8") as f:
        owner_data = json.load(f)
    print(f"✔️ Załadowano {len(owner_data)} właścicieli.")

    with open(PARCEL_DATA_FILE, "r", encoding="utf-8") as f:
        parcel_data = json.load(f)
    print(f"✔️ Załadowano {len(parcel_data)} obiektów geograficznych.")

    demografia_data = []
    if os.path.exists(DEMOGRAFIA_DATA_FILE):
        with open(DEMOGRAFIA_DATA_FILE, "r", encoding="utf-8") as f:
            demografia_data = json.load(f)
        print(f"✔️ Załadowano {len(demografia_data)} wpisów demograficznych.")
    else:
        print(f"⚠️  Plik {DEMOGRAFIA_DATA_FILE} nie został znaleziony - pomijam.")

    genealogia_data = []
    if os.path.exists(GENEALOGIA_DATA_FILE):
        with open(GENEALOGIA_DATA_FILE, "r", encoding="utf-8") as f:
            genealogia_data = json.load(f).get("persons", [])
        print(f"✔️ Załadowano {len(genealogia_data)} osób do drzewa genealogicznego.")
    else:
        print(f"⚠️  Plik {GENEALOGIA_DATA_FILE} nie został znaleziony - pomijam.")

    # --- KROK 2: POŁĄCZENIE Z BAZĄ I CZYSZCZENIE TABEL ---
    print("\n--- Krok 2: Łączenie z bazą i przygotowanie tabel ---")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding("UTF8")
    cur = conn.cursor()
    print("✔️ Połączono z bazą danych.")
    
    # Czyszczenie tabel przed importem, aby uniknąć duplikatów.
    # RESTART IDENTITY CASCADE resetuje liczniki auto-inkrementacji i zależności.
    cur.execute("TRUNCATE TABLE malzenstwa, osoby_genealogia, demografia, dzialki_wlasciciele, powiazania_protokolow, obiekty_geograficzne, wlasciciele RESTART IDENTITY CASCADE;")
    print("✔️ Tabele zostały wyczyszczone.")
    
    # --- KROK 3: IMPORT WŁAŚCICIELI ---
    print("\n--- Krok 3: Wstawianie właścicieli do bazy danych ---")
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
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (
                    key, v.get("ownerName", ""), order_number, v.get("houseNumber", ""),
                    v.get("genealogy", ""), v.get("ownershipHistory", ""), v.get("remarks", ""),
                    v.get("wspolwlasnosc", ""), v.get("powiazania_i_transakcje", v.get("relacje_rodzinne", "")),
                    v.get("interpretacja_i_wnioski", ""), protocol_date, protocol_location,
                ),
            )
            # Zapisanie mapowania: klucz z JSON -> nowe ID z bazy danych.
            owner_id = cur.fetchone()[0]
            owner_id_map[key] = owner_id
        except Exception as e:
            print(f"❌ BŁĄD przy wstawianiu właściciela o kluczu '{key}': {e}")
            conn.rollback()

    print(f"✔️ Wstawiono {len(owner_id_map)} właścicieli.")

    # --- KROK 4: IMPORT OBIEKTÓW GEOGRAFICZNYCH (Z GEOMETRIĄ) ---
    print("\n--- Krok 4: Wstawianie obiektów geograficznych (z geometrią) ---")

    def norm(num) -> str:
        """Normalizuje numer działki do jednolitego formatu string, np. '800/23'."""
        if isinstance(num, dict):
            a = str(num.get("numerator") or num.get("numarator") or "").strip()
            b = str(num.get("denominator") or "").strip()
            return f"{a}/{b}" if a and b else a
        return str(num).strip()

    objects_to_insert = []
    for raw_num, data in parcel_data.items():
        num_norm = norm(raw_num)
        kategoria = data.get("kategoria") or "rolna"
        wkt = get_wkt_from_geometry(data.get("geometria"), kategoria)
        objects_to_insert.append((num_norm, kategoria, wkt))
    
    # Użycie execute_values do masowego i wydajnego wstawiania danych.
    query = """
        INSERT INTO obiekty_geograficzne (nazwa_lub_numer, kategoria, geometria) VALUES %s
        ON CONFLICT (nazwa_lub_numer, kategoria) DO NOTHING
        RETURNING id, nazwa_lub_numer, kategoria
    """
    execute_values(cur, query, objects_to_insert)
    
    # Stworzenie mapy (numer, kategoria) -> ID obiektu, dla dalszego użytku.
    object_id_map = {(num, kat): obj_id for obj_id, num, kat in cur.fetchall()}
    print(f"✔️ Wstawiono/zaktualizowano {len(object_id_map)} obiektów z geometrią.")

    # --- KROK 5: TWORZENIE POWIĄZAŃ WŁAŚCICIEL-DZIAŁKA ---
    print("\n--- Krok 5: Przetwarzanie własności i tworzenie powiązań ---")
    link_rows, seen = [], set()

    def add_link(owner_id, object_id, typ):
        """Dodaje powiązanie do listy, unikając duplikatów."""
        key = (owner_id, object_id, typ)
        if key not in seen:
            link_rows.append((owner_id, object_id, typ, ""))
            seen.add(key)

    def ensure_object(num_norm: str, hint_building: bool) -> int | None:
        """
        Zapewnia istnienie obiektu w bazie. Jeśli nie istnieje, tworzy
        "wirtualny" rekord bez geometrii i zwraca jego ID.
        """
        if not num_norm: return None
        wanted_cat = "budowlana" if hint_building else "rolna"
        wanted_key = (num_norm, wanted_cat)
        
        # Przypadek 1: Obiekt z dokładną kategorią już istnieje.
        if wanted_key in object_id_map:
            return object_id_map[wanted_key]
            
        # Przypadek 2: Szukamy działki rolnej, a istnieje inna (nie-budowlana) o tym numerze.
        if not hint_building:
            for (num, cat), obj_id in object_id_map.items():
                if num == num_norm and cat != "budowlana":
                    return obj_id
                    
        # Przypadek 3: Obiekt nie istnieje, tworzymy nowy "wirtualny" rekord.
        cur.execute(
            "INSERT INTO obiekty_geograficzne (nazwa_lub_numer, kategoria, geometria) VALUES (%s, %s, NULL) RETURNING id",
            (num_norm, wanted_cat),
        )
        new_id = cur.fetchone()[0]
        object_id_map[wanted_key] = new_id
        return new_id

    # Przetwarzanie list działek dla każdego właściciela.
    for owner_key, details in owner_data.items():
        owner_id = owner_id_map.get(owner_key)
        if not owner_id:
            print(f"⚠️  Ostrzeżenie: brak ID dla właściciela '{owner_key}' – pomijam jego działki.")
            continue
        
        # Własność rzeczywista.
        for key in ("realbuildingPlots", "realagriculturalPlots"):
            for p in details.get(key, []):
                obj_id = ensure_object(norm(p), key.startswith("realbuilding"))
                if obj_id: add_link(owner_id, obj_id, "własność rzeczywista")
                
        # Własność wg protokołu.
        for key in ("buildingPlots", "agriculturalPlots"):
            for p in details.get(key, []):
                obj_id = ensure_object(norm(p), key.startswith("building"))
                if obj_id: add_link(owner_id, obj_id, "własność z protokołu")
    
    # Masowe wstawianie zebranych powiązań do bazy.
    if link_rows:
        execute_values(
            cur,
            """
            INSERT INTO dzialki_wlasciciele (wlasciciel_id, obiekt_id, typ_posiadania, opis_udzialu) VALUES %s
            ON CONFLICT (wlasciciel_id, obiekt_id, typ_posiadania) DO NOTHING
            """,
            link_rows
        )
        print(f"✔️ Utworzono {cur.rowcount} nowych powiązań właściciel-działka.")

# --- KROK 5.5: DEDYKOWANE PRZYPISYWANIE DOMÓW DO WŁAŚCICIELI ---
    print("\n--- Krok 5.5: Tworzenie powiązań właściciel-dom ---")
    house_links = []
    
    # Tworzymy mapę obiektów, które są domami lub budynkami dla szybszego wyszukiwania
    house_objects_map = {
        num: obj_id for (num, cat), obj_id in object_id_map.items() if cat in ['dom', 'budynek']
    }

    for owner_key, details in owner_data.items():
        owner_id = owner_id_map.get(owner_key)
        house_number = details.get("houseNumber")

        if owner_id and house_number:
            # Szukamy obiektu domu w naszej przygotowanej mapie
            house_object_id = house_objects_map.get(house_number)
            if house_object_id:
                # Dodajemy powiązanie, oznaczając je jako 'własność rzeczywista'
                # Unikamy duplikatów, jeśli powiązanie już istnieje
                key = (owner_id, house_object_id, "własność rzeczywista")
                if key not in seen:
                    house_links.append((owner_id, house_object_id, "własność rzeczywista", ""))
                    seen.add(key)

    # Masowe wstawianie powiązań domów, jeśli jakieś znaleziono
    if house_links:
        execute_values(
            cur,
            """
            INSERT INTO dzialki_wlasciciele (wlasciciel_id, obiekt_id, typ_posiadania, opis_udzialu) VALUES %s
            ON CONFLICT (wlasciciel_id, obiekt_id, typ_posiadania) DO NOTHING
            """,
            house_links
        )
        print(f"✔️ Utworzono {cur.rowcount} nowych powiązań właściciel-dom.")
    else:
        print("✔️ Nie znaleziono dedykowanych powiązań dla domów.")

    # --- KROK 6: IMPORT DANYCH DEMOGRAFICZNYCH ---
    if demografia_data:
        print("\n--- Krok 6: Wstawianie danych demograficznych ---")
        demografia_to_insert = [
            (e.get("rok"), e.get("populacja_ogolem"), e.get("katolicy"), e.get("zydzi"), e.get("inni"), e.get("opis"))
            for e in demografia_data
        ]
        execute_values(cur, "INSERT INTO demografia (rok, populacja_ogolem, katolicy, zydzi, inni, opis) VALUES %s;", demografia_to_insert)
        print(f"✔️ Wstawiono {len(demografia_to_insert)} wpisów demograficznych.")
        
    # --- KROK 7: IMPORT DANYCH GENEALOGICZNYCH ---
    if genealogia_data:
        print("\n--- Krok 7: Wstawianie danych genealogicznych ---")
        json_id_to_db_id = {}

        # Etap 1: Wstawienie wszystkich osób, aby uzyskać ich ID w bazie.
        print("    -> Etap 7a: Wstawianie osób...")
        for osoba in genealogia_data:
            id_protokolu = owner_id_map.get(osoba.get("protocolKey"))
            birth_date_obj = osoba.get("birthDate")
            rok_urodzenia = birth_date_obj.get("year") if birth_date_obj else None
            death_date_obj = osoba.get("deathDate")
            rok_smierci = death_date_obj.get("year") if death_date_obj else None

            cur.execute(
                "INSERT INTO osoby_genealogia (json_id, imie_nazwisko, plec, numer_domu, rok_urodzenia, rok_smierci, id_protokolu, uwagi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;",
                (osoba["id"], osoba["name"], osoba.get("gender"), osoba.get("houseNumber"), rok_urodzenia, rok_smierci, id_protokolu, osoba.get("notes"))
            )
            db_id = cur.fetchone()[0]
            json_id_to_db_id[osoba["id"]] = db_id
        print(f"    ✔️ Wstawiono {len(json_id_to_db_id)} osób.")

        # Etap 2: Aktualizacja relacji rodzic-dziecko.
        print("    -> Etap 7b: Tworzenie relacji rodzicielskich...")
        for osoba in genealogia_data:
            db_id = json_id_to_db_id.get(osoba["id"])
            id_ojca = json_id_to_db_id.get(osoba.get("fatherId"))
            id_matki = json_id_to_db_id.get(osoba.get("motherId"))
            if db_id and (id_ojca or id_matki):
                cur.execute("UPDATE osoby_genealogia SET id_ojca = %s, id_matki = %s WHERE id = %s;", (id_ojca, id_matki, db_id))

        # Etap 3: Wstawienie relacji małżeńskich.
        print("    -> Etap 7c: Tworzenie relacji małżeńskich...")
        malzenstwa_to_insert = []
        seen_malzenstwa = set()
        for osoba in genealogia_data:
            id1 = json_id_to_db_id.get(osoba["id"])
            for spouse_json_id in osoba.get("spouseIds", []):
                id2 = json_id_to_db_id.get(spouse_json_id)
                if id1 and id2:
                    # Sortowanie ID w parze, aby uniknąć duplikatów (A,B) i (B,A).
                    para = tuple(sorted((id1, id2)))
                    if para not in seen_malzenstwa:
                        malzenstwa_to_insert.append(para)
                        seen_malzenstwa.add(para)

        if malzenstwa_to_insert:
            execute_values(cur, "INSERT INTO malzenstwa (malzonek1_id, malzonek2_id) VALUES %s", malzenstwa_to_insert)
            print(f"    ✔️ Wstawiono {len(malzenstwa_to_insert)} unikalnych relacji małżeńskich.")
    
    # Zatwierdzenie wszystkich zmian w bazie danych.
    conn.commit()
    print("\n\n✅ --- SUKCES! Migracja danych zakończona pomyślnie. --- ✅")

except FileNotFoundError as e:
    print(f"\n❌ BŁĄD KRYTYCZNY: Nie znaleziono pliku! Upewnij się, że pliki JSON istnieją w folderze 'backup'.")
    print(f"Brakujący plik: {e.filename}")
except Exception as e:
    print(f"\n❌ BŁĄD KRYTYCZNY: Wystąpił nieoczekiwany błąd: {e}")
    # Wycofanie transakcji w przypadku błędu, aby nie zostawić bazy w niespójnym stanie.
    if conn:
        conn.rollback()
        print("   -> Zmiany w bazie danych zostały wycofane.")
finally:
    # Zawsze zamykaj połączenie z bazą, niezależnie od wyniku.
    if conn:
        cur.close()
        conn.close()
        print("\nPołączenie z bazą danych zostało zamknięte.")