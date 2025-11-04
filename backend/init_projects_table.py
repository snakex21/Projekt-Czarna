"""
================================================================================
Skrypt: init_projects_table.py
Opis: Inicjalizacja tabeli projects i migracja istniejących danych Czarnej
      jako pierwszy projekt w systemie multi-projekt
================================================================================
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import shutil
from pathlib import Path

# ================================================================================
# KONFIGURACJA
# ================================================================================

load_dotenv()

def get_env_variable(var_name, default_value=None):
    """Pobiera zmienną środowiskową z opcjonalną wartością domyślną."""
    value = os.getenv(var_name, default_value)
    if value is None:
        print(f"⚠️ Uwaga: Zmienna środowiskowa {var_name} nie jest ustawiona!")
    return value

DB_CONFIG = {
    "host": get_env_variable("DB_HOST", "localhost"),
    "dbname": get_env_variable("DB_NAME", "mapa_czarna_db"),
    "user": get_env_variable("DB_USER", "postgres"),
    "password": get_env_variable("DB_PASSWORD", "1234"),
    "port": get_env_variable("DB_PORT", "5432")
}

BASE_DIR = Path(__file__).parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
BACKUP_DIR = BASE_DIR / "backup"

print("\n" + "=" * 80)
print("      INICJALIZACJA SYSTEMU MULTI-PROJEKT")
print("=" * 80)

# ================================================================================
# FUNKCJE POMOCNICZE
# ================================================================================

def get_db_connection():
    """Tworzy i zwraca połączenie z bazą danych."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding('UTF8')
    return conn

def create_projects_table():
    """Tworzy tabelę projects jeśli nie istnieje."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n📊 Tworzenie tabeli 'projects'...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            short_code VARCHAR(50) UNIQUE NOT NULL,
            nazwa VARCHAR(200) NOT NULL,
            pelna_nazwa VARCHAR(500),
            opis TEXT,
            kontekst_czasowy VARCHAR(200),
            rok_zrodlowy INTEGER,
            okres_danych VARCHAR(100),
            region VARCHAR(200),
            wojewodztwo VARCHAR(100),
            jezyk_zrodel VARCHAR(100),
            uwagi TEXT,
            status VARCHAR(50) DEFAULT 'aktywny',
            html_title_mapa TEXT,
            html_title_wlasciciele TEXT,
            html_title_genealogia TEXT,
            html_title_stats TEXT,
            html_opis_strony_glownej TEXT,
            data_utworzenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ostatnia_modyfikacja TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT check_status CHECK (status IN ('aktywny', 'archiwum'))
        );
    """)
    
    # Dodaj indeksy
    cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_short_code ON projects(short_code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);")
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("✅ Tabela 'projects' utworzona pomyślnie")

def create_project_folders(project_code):
    """Tworzy strukturę folderów dla projektu."""
    project_path = PROJECTS_DIR / project_code
    
    folders = [
        project_path / "data",
        project_path / "geojson",
        project_path / "backups"
    ]
    
    print(f"\n📁 Tworzenie folderów dla projektu '{project_code}'...")
    
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        print(f"   ✓ {folder.relative_to(BASE_DIR)}")
    
    return project_path

def migrate_czarna_data():
    """Migruje istniejące dane Czarnej do nowej struktury projektów."""
    print("\n🔄 Migracja danych projektu Czarna...")
    
    # Utwórz folder projektu i backup
    czarna_project_path = create_project_folders("czarna")
    czarna_backup_path = BASE_DIR / "backup" / "czarna"
    
    # Utwórz strukturę backup/czarna/
    for subdir in ['data', 'geojson', 'backups']:
        (czarna_backup_path / subdir).mkdir(parents=True, exist_ok=True)
    
    print(f"   ✓ Utworzono backup/czarna/")
    
    # Skopiuj pliki z backup/ do backup/czarna/data/ i projects/czarna/data/
    files_to_copy = [
        ("owner_data_to_import.json", "database.json"),
        ("demografia.json", "demografia.json"),
        ("genealogia.json", "genealogia.json"),
        ("parcels_data.json", "parcels.json")
    ]
    
    print("\n📋 Kopiowanie plików danych...")
    for src_name, dest_name in files_to_copy:
        src = BACKUP_DIR / src_name
        dest_project = czarna_project_path / "data" / dest_name
        dest_backup = czarna_backup_path / "data" / dest_name
        
        if src.exists():
            # Kopiuj do projects/czarna/data/
            shutil.copy2(src, dest_project)
            # Kopiuj też do backup/czarna/data/
            shutil.copy2(src, dest_backup)
            print(f"   ✓ {src_name} → {dest_name} (projects + backup)")
        else:
            print(f"   ⚠️ Plik {src_name} nie istnieje, tworzę pusty plik")
            # Utwórz pusty plik JSON
            if dest_name.endswith('.json'):
                empty_data = {} if dest_name != "demografia.json" else []
                with open(dest_project, 'w', encoding='utf-8') as f:
                    json.dump(empty_data, f, indent=2)
                with open(dest_backup, 'w', encoding='utf-8') as f:
                    json.dump(empty_data, f, indent=2)
    
    print("✅ Migracja plików zakończona")

def insert_czarna_project():
    """Wstawia rekord projektu Czarna do bazy danych."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n💾 Dodawanie projektu Czarna do bazy danych...")
    
    # Sprawdź czy projekt już istnieje
    cur.execute("SELECT id FROM projects WHERE short_code = 'czarna'")
    existing = cur.fetchone()
    
    if existing:
        print("   ℹ️ Projekt Czarna już istnieje w bazie danych")
        conn.close()
        return existing[0]
    
    project_data = {
        'short_code': 'czarna',
        'nazwa': 'Czarna',
        'pelna_nazwa': 'Gmina Czarna - System Mapy Katastralnej',
        'opis': 'Interaktywna mapa katastralina gminy Czarna z XIX wieku wraz z bazą danych właścicieli, genealogią i analizą demograficzną.',
        'kontekst_czasowy': 'XIX wiek',
        'rok_zrodlowy': 1880,
        'okres_danych': '1850-1900',
        'region': 'Powiat Mielecki',
        'wojewodztwo': 'Podkarpackie',
        'jezyk_zrodel': 'Polski',
        'uwagi': 'Dane pochodzą z archiwum państwowego w Mielcu. Pierwsza instancja systemu.',
        'status': 'aktywny'
    }
    
    cur.execute("""
        INSERT INTO projects (
            short_code, nazwa, pelna_nazwa, opis, kontekst_czasowy,
            rok_zrodlowy, okres_danych, region, wojewodztwo,
            jezyk_zrodel, uwagi, status
        ) VALUES (
            %(short_code)s, %(nazwa)s, %(pelna_nazwa)s, %(opis)s, %(kontekst_czasowy)s,
            %(rok_zrodlowy)s, %(okres_danych)s, %(region)s, %(wojewodztwo)s,
            %(jezyk_zrodel)s, %(uwagi)s, %(status)s
        ) RETURNING id;
    """, project_data)
    
    project_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"✅ Projekt Czarna dodany pomyślnie (ID: {project_id})")
    return project_id

def save_active_project_config(project_code):
    """Zapisuje aktywny projekt do pliku konfiguracyjnego."""
    config_file = BASE_DIR / "backend" / ".active_project"
    
    print(f"\n⚙️ Ustawianie aktywnego projektu: {project_code}")
    
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(project_code)
    
    print(f"✅ Projekt '{project_code}' ustawiony jako aktywny")

# ================================================================================
# GŁÓWNA FUNKCJA MIGRACJI
# ================================================================================

def main():
    """Główna funkcja wykonująca migrację."""
    try:
        print(f"\n📊 Konfiguracja połączenia:")
        print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"   Baza: {DB_CONFIG['dbname']}")
        print(f"   Użytkownik: {DB_CONFIG['user']}")
        
        # Krok 1: Utwórz tabelę projects
        create_projects_table()
        
        # Krok 2: Migruj dane Czarnej
        migrate_czarna_data()
        
        # Krok 3: Dodaj projekt Czarna do bazy
        project_id = insert_czarna_project()
        
        # Krok 4: Ustaw jako aktywny projekt
        save_active_project_config('czarna')
        
        print("\n" + "=" * 80)
        print("✅ MIGRACJA ZAKOŃCZONA POMYŚLNIE!")
        print("=" * 80)
        print("\n📌 Następne kroki:")
        print("   1. Uruchom serwer backend: python app.py")
        print("   2. Sprawdź endpoint: GET /api/projects")
        print("   3. Sprawdź info o aktywnym projekcie: GET /api/project-info")
        print("\n")
        
    except psycopg2.Error as e:
        print(f"\n❌ BŁĄD BAZY DANYCH: {e}")
        print("   Sprawdź czy PostgreSQL jest uruchomiony i dane dostępowe są poprawne")
        return 1
    except Exception as e:
        print(f"\n❌ BŁĄD: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
