"""
================================================================================
Plik: app.py
System Mapy Katastralnej - Serwer Backend Flask
================================================================================
Główny moduł aplikacji backendowej obsługujący API REST dla systemu mapy katastralnej.
Zapewnia endpointy do zarządzania danymi właścicieli, działek, genealogii oraz demografii.
================================================================================
"""

import re
import io
import zipfile
from flask import send_file
import json
from flask_cors import CORS
import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, session
import os
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from collections import Counter

# =============================================================================
# KONFIGURACJA ŚRODOWISKA
# =============================================================================

# Wczytanie zmiennych środowiskowych z pliku .env
load_dotenv()

def get_env_variable(var_name, default_value=None):
    """Pobiera zmienną środowiskową z opcjonalną wartością domyślną."""
    value = os.getenv(var_name, default_value)
    if value is None:
        print(f"⚠️ Uwaga: Zmienna środowiskowa {var_name} nie jest ustawiona!")
    return value

# =============================================================================
# INICJALIZACJA APLIKACJI FLASK
# =============================================================================

app = Flask(__name__)
CORS(app)  # Włączenie CORS dla komunikacji frontend-backend

# Konfiguracja aplikacji
app.config['JSON_AS_ASCII'] = False  # Poprawne renderowanie polskich znaków
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-me')

# Konfiguracja autoryzacji admina
ADMIN_AUTH_ENABLED = os.environ.get('ADMIN_AUTH_ENABLED', '0') == '1'
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH', '')

# Konfiguracja połączenia z bazą danych PostgreSQL
DB_CONFIG = {
    "host": get_env_variable("DB_HOST", "localhost"),
    "dbname": get_env_variable("DB_NAME", "mapa_czarna_db"),
    "user": get_env_variable("DB_USER", "postgres"),
    "password": get_env_variable("DB_PASSWORD", "1234"),
    "port": get_env_variable("DB_PORT", "5432")
}

# =============================================================================
# POMOCNICZE FUNKCJE BAZODANOWE
# =============================================================================

def get_db_connection():
    """Tworzy i zwraca połączenie z bazą danych PostgreSQL."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding('UTF8')  # Obsługa polskich znaków
    return conn

# Globalne przechowywanie konfiguracji
map_config = {}
favicon_path = None

def load_system_config():
    """Wczytuje całą konfigurację systemową (mapa, favicon) z bazy danych."""
    global map_config, favicon_path
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT klucz, wartosc FROM konfiguracja_systemu;")
            rows = cur.fetchall()
            config_data = {row['klucz']: row['wartosc'] for row in rows}

            # Konfiguracja mapy
            map_config = {
                'calibration': config_data.get('map_calibration', {}),
                'defaults': config_data.get('map_defaults', {})
            }
            print("🗺️  Konfiguracja mapy załadowana pomyślnie.")
            
            # Konfiguracja faviconu
            favicon_config = config_data.get('site_favicon', {})
            if isinstance(favicon_config, dict) and favicon_config.get('path'):
                favicon_path = favicon_config['path']
                print(f"🖼️  Favicon załadowany: {favicon_path}")
            else:
                favicon_path = None
                print("🖼️  Brak niestandardowego faviconu w konfiguracji.")

    except Exception as e:
        print(f"❌ KRYTYCZNY BŁĄD: Nie można załadować konfiguracji z bazy danych: {e}")
        # Ustawienie twardych wartości awaryjnych dla mapy
        map_config = {
            'calibration': {"sw": {"lat": 50.0414, "lng": 21.2261}, "ne": {"lat": 50.0814, "lng": 21.2661}},
            'defaults': {"center": {"lat": 50.0614, "lng": 21.2461}, "zoom": 14}
        }
        print("⚠️  Użyto awaryjnej, domyślnej konfiguracji mapy.")
    finally:
        if conn:
            conn.close()

# Załaduj konfigurację przy starcie serwera
load_system_config()

# =============================================================================
# MIDDLEWARE - MECHANIZM BEZPIECZEŃSTWA
# =============================================================================

@app.before_request
def check_ip_blacklist():
    """Sprawdza czy adres IP jest zablokowany przed przetworzeniem żądania."""
    user_ip = request.remote_addr

    # Zawsze zezwalaj na localhost
    if user_ip == '127.0.0.1':
        return

    # Pomiń dla zasobów statycznych i logowania
    if request.endpoint in ['static', 'admin_static_files', 'admin_login', 'admin_auth_status']:
        return

    # Sprawdź czarną listę jeśli autoryzacja włączona
    if ADMIN_AUTH_ENABLED:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM blocked_ips WHERE ip_address = %s", (user_ip,))
                if cur.fetchone():
                    return jsonify({"status": "error", "message": "Dostęp z tego adresu IP został zablokowany."}), 403
        finally:
            conn.close()

# =============================================================================
# POMOCNICZE FUNKCJE BAZODANOWE
# =============================================================================

def get_db_connection():
    """Tworzy i zwraca połączenie z bazą danych PostgreSQL."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding('UTF8')  # Obsługa polskich znaków
    return conn

# =============================================================================
# PUBLICZNE ENDPOINTY API
# =============================================================================

@app.route('/')
def index():
    """Przekierowanie na stronę główną."""
    return redirect(url_for('serve_main_page', filename='index.html'))

@app.route('/api/wlasciciele')
def get_all_wlasciciele():
    """Pobiera listę wszystkich właścicieli z podziałem działek na protokołowe i rzeczywiste."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Agregacja działek dla każdego właściciela
    cur.execute("""
        SELECT
            w.id, w.unikalny_klucz, w.nazwa_wlasciciela, w.numer_protokolu,
            json_agg(json_build_object('id', o.id, 'nazwa_lub_numer', o.nazwa_lub_numer))
                FILTER (WHERE dw.typ_posiadania = 'własność rzeczywista') as dzialki_rzeczywiste,
            json_agg(json_build_object('id', o.id, 'nazwa_lub_numer', o.nazwa_lub_numer))
                FILTER (WHERE dw.typ_posiadania != 'własność rzeczywista' OR dw.typ_posiadania IS NULL) as dzialki_protokol
        FROM wlasciciele w
        LEFT JOIN dzialki_wlasciciele dw ON w.id = dw.wlasciciel_id
        LEFT JOIN obiekty_geograficzne o ON dw.obiekt_id = o.id
        GROUP BY w.id ORDER BY w.numer_protokolu;
    """)
    wlasciciele = cur.fetchall()

    # Pobranie metadanych
    cur.execute("SELECT MIN(numer_protokolu) as min_lp, MAX(numer_protokolu) as max_lp FROM wlasciciele WHERE numer_protokolu IS NOT NULL;")
    zakres = cur.fetchone()
    total_owners_count = len(wlasciciele)

    cur.close()
    conn.close()

    return jsonify({
        'owners': wlasciciele,
        'metadata': {
            'total_count': total_owners_count,
            'zakres_lp': {'min': zakres['min_lp'] or 1, 'max': zakres['max_lp'] or 1}
        }
    })

@app.route('/api/dzialki')
def get_all_dzialki():
    """Zwraca wszystkie obiekty geograficzne w formacie GeoJSON dla mapy."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Budowanie struktury GeoJSON bezpośrednio w bazie
    sql_query = """
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', json_agg(features.feature)
        )
        FROM (
            SELECT json_build_object(
                'type', 'Feature',
                'id', o.id,
                'geometry', ST_AsGeoJSON(o.geometria)::json,
                'properties', json_build_object(
                    'numer_obiektu', o.nazwa_lub_numer,
                    'kategoria', o.kategoria,
                    'wlasciciele', (
                        SELECT json_agg(owner_data) FROM (
                            SELECT DISTINCT ON (w.id) json_build_object(
                                'id', w.id, 'unikalny_klucz', w.unikalny_klucz, 'nazwa', w.nazwa_wlasciciela
                            ) as owner_data
                            FROM wlasciciele w JOIN dzialki_wlasciciele dw ON w.id = dw.wlasciciel_id
                            WHERE dw.obiekt_id = o.id
                        ) as sub
                    )
                )
            ) AS feature
            FROM obiekty_geograficzne AS o WHERE o.geometria IS NOT NULL
        ) AS features;
    """
    cur.execute(sql_query)
    dzialki_geojson = cur.fetchone()[0]
    cur.close()
    conn.close()
    
    # Zabezpieczenie przed pustą bazą
    if dzialki_geojson is None or dzialki_geojson.get('features') is None:
        dzialki_geojson = {"type": "FeatureCollection", "features": []}

    return jsonify(dzialki_geojson)

@app.route('/api/wlasciciel/<string:unikalny_klucz>')
def get_wlasciciel_by_key(unikalny_klucz):
    """Pobiera szczegółowe dane pojedynczego właściciela."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Pobranie danych właściciela
    cur.execute("""
        SELECT unikalny_klucz, id, nazwa_wlasciciela, numer_protokolu, numer_domu,
               genealogia, historia_wlasnosci, uwagi, wspolwlasnosc,
               powiazania_i_transakcje, interpretacja_i_wnioski,
               data_protokolu, miejsce_protokolu
        FROM wlasciciele WHERE unikalny_klucz = %s
    """, (unikalny_klucz,))
    wlasciciel = cur.fetchone()

    if not wlasciciel:
        return jsonify({"error": "Właściciel nie znaleziony"}), 404

    # Sprawdzenie drzewa genealogicznego
    cur.execute("SELECT EXISTS (SELECT 1 FROM osoby_genealogia WHERE id_protokolu = %s) AS ma_drzewo;", (wlasciciel['id'],))
    wlasciciel['ma_drzewo_genealogiczne'] = cur.fetchone()['ma_drzewo']

    # Pobranie działek z sortowaniem numerycznym
    cur.execute("""
        SELECT 
            json_agg(json_build_object('id', o.id, 'nazwa_lub_numer', o.nazwa_lub_numer, 'kategoria', o.kategoria) 
                ORDER BY (regexp_split_to_array(o.nazwa_lub_numer, E'[^0-9]+'))[1]::integer, 
                COALESCE((regexp_split_to_array(o.nazwa_lub_numer, E'[^0-9]+'))[2]::integer, 0)) 
                FILTER (WHERE dw.typ_posiadania != 'własność rzeczywista' OR dw.typ_posiadania IS NULL) as dzialki_protokol,
            json_agg(json_build_object('id', o.id, 'nazwa_lub_numer', o.nazwa_lub_numer, 'kategoria', o.kategoria) 
                ORDER BY (regexp_split_to_array(o.nazwa_lub_numer, E'[^0-9]+'))[1]::integer, 
                COALESCE((regexp_split_to_array(o.nazwa_lub_numer, E'[^0-9]+'))[2]::integer, 0)) 
                FILTER (WHERE dw.typ_posiadania = 'własność rzeczywista') as dzialki_rzeczywiste
        FROM dzialki_wlasciciele dw JOIN obiekty_geograficzne o ON o.id = dw.obiekt_id
        WHERE dw.wlasciciel_id = %s;
    """, (wlasciciel['id'],))
    fetched_plots = cur.fetchone()

    # Pobranie wszystkich działek
    cur.execute("""
        SELECT o.id, o.nazwa_lub_numer, o.kategoria, dw.typ_posiadania
        FROM obiekty_geograficzne o JOIN dzialki_wlasciciele dw ON o.id = dw.obiekt_id
        WHERE dw.wlasciciel_id = %s
    """, (wlasciciel['id'],))
    wlasciciel['dzialki_wszystkie'] = cur.fetchall()

    cur.close()
    conn.close()

    # Uzupełnienie danych
    wlasciciel['dzialki_protokol'] = fetched_plots['dzialki_protokol'] or []
    wlasciciel['dzialki_rzeczywiste'] = fetched_plots['dzialki_rzeczywiste'] or []
    wlasciciel['dom_obiekt_id'] = None
    wlasciciel['dom_numer'] = wlasciciel.get('numer_domu')
    
    # Szukanie domu wśród działek
    if wlasciciel.get('numer_domu'):
        for dzialka in wlasciciel['dzialki_wszystkie']:
            if dzialka['kategoria'] in ['dom', 'budynek'] and dzialka['nazwa_lub_numer'] == wlasciciel['numer_domu']:
                wlasciciel['dom_obiekt_id'] = dzialka['id']
                break

    def nl2br(text): return text.replace('\\n', '<br>') if text else ''
    def create_link(match): return f'<a href="protokol.html?ownerId={match.group(2)}">{match.group(1)}</a>'

    powiazania_raw = wlasciciel.get('powiazania_i_transakcje', '') or ''
    wlasciciel['powiazania_i_transakcje_html'] = re.sub(r'\[\[([^|\]]+)\|([^\]]+)\]\]', create_link, nl2br(powiazania_raw))
    
    historia = nl2br(wlasciciel.get('historia_wlasnosci', ''))
    uwagi = nl2br(wlasciciel.get('uwagi', ''))
    wlasciciel['pelna_historia'] = f"{historia}<hr><b>Ciąg dalszy / Uwagi:</b><br>{uwagi}" if uwagi and uwagi.strip() else historia

    wlasciciel['genealogia'] = nl2br(wlasciciel.get('genealogia', ''))
    wlasciciel['wspolwlasnosc'] = nl2br(wlasciciel.get('wspolwlasnosc', ''))
    wlasciciel['interpretacja_i_wnioski'] = nl2br(wlasciciel.get('interpretacja_i_wnioski', ''))

    return jsonify(wlasciciel)

@app.route('/api/genealogia/<string:unikalny_klucz>')
def get_drzewo_genealogiczne(unikalny_klucz):
    """Pobiera dane do zbudowania drzewa genealogicznego dla właściciela."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Znajdź właściciela
    cur.execute("SELECT id FROM wlasciciele WHERE unikalny_klucz = %s;", (unikalny_klucz,))
    wlasciciel = cur.fetchone()
    if not wlasciciel:
        cur.close()
        conn.close()
        return jsonify({"error": "Właściciel nie znaleziony"}), 404
    id_protokolu = wlasciciel['id']

    # Znajdź osobę startową
    cur.execute("SELECT * FROM osoby_genealogia WHERE id_protokolu = %s LIMIT 1;", (id_protokolu,))
    root_person = cur.fetchone()
    if not root_person:
        cur.close()
        conn.close()
        return jsonify({"error": "Nie znaleziono osoby powiązanej z tym protokołem"}), 404

    # Algorytm BFS do znalezienia wszystkich połączonych osób
    queue = [root_person['id']]
    visited_ids = {root_person['id']}
    while queue:
        current_id = queue.pop(0)
        cur.execute("""
            SELECT id_ojca as id FROM osoby_genealogia WHERE id = %s AND id_ojca IS NOT NULL UNION
            SELECT id_matki as id FROM osoby_genealogia WHERE id = %s AND id_matki IS NOT NULL UNION
            SELECT malzonek2_id as id FROM malzenstwa WHERE malzonek1_id = %s UNION
            SELECT malzonek1_id as id FROM malzenstwa WHERE malzonek2_id = %s UNION
            SELECT id FROM osoby_genealogia WHERE id_ojca = %s OR id_matki = %s;
        """, (current_id, current_id, current_id, current_id, current_id, current_id))
        
        for person in cur.fetchall():
            if person['id'] not in visited_ids:
                visited_ids.add(person['id'])
                queue.append(person['id'])

    if not visited_ids:
        cur.close()
        conn.close()
        return jsonify({"error": "Nie znaleziono powiązanych osób"}), 404

    # Pobierz dane wszystkich osób
    placeholders = ','.join(['%s'] * len(visited_ids))
    cur.execute(f"SELECT * FROM osoby_genealogia WHERE id IN ({placeholders});", list(visited_ids))
    all_persons_in_tree = cur.fetchall()
    cur.execute(f"SELECT malzonek1_id, malzonek2_id FROM malzenstwa WHERE malzonek1_id IN ({placeholders}) AND malzonek2_id IN ({placeholders});", list(visited_ids) * 2)
    all_marriages_in_tree = cur.fetchall()

    cur.close()
    conn.close()

    # Formatowanie danych dla frontendu
    db_id_to_json_id = {p['id']: p['json_id'] for p in all_persons_in_tree}
    spouse_map = {}
    for marriage in all_marriages_in_tree:
        id1, id2 = marriage['malzonek1_id'], marriage['malzonek2_id']
        json_id1, json_id2 = db_id_to_json_id.get(id1), db_id_to_json_id.get(id2)
        if json_id1 and json_id2:
            spouse_map.setdefault(id1, []).append(json_id2)
            spouse_map.setdefault(id2, []).append(json_id1)

    persons_json = []
    for p in all_persons_in_tree:
        persons_json.append({
            "id": p['json_id'], 
            "name": p['imie_nazwisko'], 
            "gender": p['plec'], 
            "houseNumber": p.get('numer_domu'),
            "birthDate": {"year": p.get('rok_urodzenia')} if p.get('rok_urodzenia') else None,
            "deathDate": {"year": p.get('rok_smierci')} if p.get('rok_smierci') else None,
            "protocolKey": None, 
            "fatherId": db_id_to_json_id.get(p.get('id_ojca')), 
            "motherId": db_id_to_json_id.get(p.get('id_matki')),
            "spouseIds": spouse_map.get(p['id'], []), 
            "notes": p.get('uwagi')
        })

    return jsonify({"rootId": root_person['json_id'], "persons": persons_json})

@app.route('/api/stats')
def get_stats():
    """Zwraca kompleksowe statystyki systemu."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Statystyki ogólne
    cur.execute("SELECT COUNT(*) as total_owners FROM wlasciciele;")
    total_owners = cur.fetchone()['total_owners']
    cur.execute("SELECT COUNT(*) as total_plots FROM obiekty_geograficzne;")
    total_plots = cur.fetchone()['total_plots']

    # Protokoły dzienne
    cur.execute("""
        SELECT data_protokolu::date as protocol_date, COUNT(*) as protocol_count,
               json_agg(json_build_object('unikalny_klucz', unikalny_klucz, 'nazwa_wlasciciela', nazwa_wlasciciela) 
               ORDER BY nazwa_wlasciciela) as owners
        FROM wlasciciele WHERE data_protokolu IS NOT NULL
        GROUP BY protocol_date ORDER BY protocol_date ASC;
    """)
    protocols_per_day = cur.fetchall()

    # Funkcja do generowania rankingów
    def get_rankings_for_type(ownership_type):
        condition = "dw.typ_posiadania = 'własność rzeczywista'" if ownership_type == 'rzeczywista' else "(dw.typ_posiadania != 'własność rzeczywista' OR dw.typ_posiadania IS NULL)"
        def get_top_by_category(category_name=None):
            category_condition = f"AND o.kategoria = '{category_name}'" if category_name else ""
            query = f"""
                SELECT w.nazwa_wlasciciela, w.unikalny_klucz, w.numer_protokolu, COUNT(dw.obiekt_id) as plot_count
                FROM wlasciciele w
                JOIN dzialki_wlasciciele dw ON w.id = dw.wlasciciel_id
                JOIN obiekty_geograficzne o ON dw.obiekt_id = o.id
                WHERE {condition} {category_condition}
                GROUP BY w.id, w.nazwa_wlasciciela, w.unikalny_klucz, w.numer_protokolu
                HAVING COUNT(dw.obiekt_id) > 0 ORDER BY plot_count DESC;
            """
            cur.execute(query)
            return cur.fetchall()

        return {
            'all_plots': get_top_by_category(),
            'rolna': get_top_by_category('rolna'),
            'budowlana': get_top_by_category('budowlana'),
            'las': get_top_by_category('las'),
            'pastwisko': get_top_by_category('pastwisko'),
            'droga': get_top_by_category('droga'),
            'rzeka': get_top_by_category('rzeka'),
            'budynek': get_top_by_category('budynek'),
            'kapliczka': get_top_by_category('kapliczka'),
            'obiekt_specjalny': get_top_by_category('obiekt_specjalny')
        }

    rankings_real = get_rankings_for_type('rzeczywista')
    rankings_protocol = get_rankings_for_type('protokol')

    # Demografia
    cur.execute("SELECT * FROM demografia ORDER BY rok ASC;")
    demografia_data = cur.fetchall()

    # Kategorie obiektów
    cur.execute("""
        SELECT kategoria, COUNT(*) as count 
        FROM obiekty_geograficzne 
        WHERE kategoria IS NOT NULL 
        GROUP BY kategoria;
    """)
    category_counts_list = cur.fetchall()
    category_counts = {item['kategoria']: item['count'] for item in category_counts_list}

    # Statystyki genealogiczne
    cur.execute("SELECT rok_urodzenia, plec, imie_nazwisko FROM osoby_genealogia;")
    genealogia_raw = cur.fetchall()

    total_people = len(genealogia_raw)
    gender_counts = Counter(p['plec'] for p in genealogia_raw)
    
    # Top nazwisk
    surnames = [p['imie_nazwisko'].split()[-1] for p in genealogia_raw if ' ' in p['imie_nazwisko']]
    top_surnames = Counter(surnames).most_common(10)
    
    # Urodzenia wg dekad
    births_by_decade = Counter()
    for person in genealogia_raw:
        if person['rok_urodzenia']:
            decade = (person['rok_urodzenia'] // 10) * 10
            births_by_decade[decade] += 1
    
    sorted_decades = sorted(births_by_decade.items())
    births_by_decade_chart = {
        'labels': [f"{d[0]}s" for d in sorted_decades],
        'data': [d[1] for d in sorted_decades]
    }

    genealogy_stats = {
        'total_people': total_people,
        'male_count': gender_counts.get('M', 0),
        'female_count': gender_counts.get('F', 0),
        'top_surnames': [{'name': name, 'count': count} for name, count in top_surnames],
        'births_by_decade': births_by_decade_chart
    }
    
    cur.close()
    conn.close()

    return jsonify({
        'general_stats': {'total_owners': total_owners, 'total_plots': total_plots},
        'protocols_per_day': protocols_per_day,
        'rankings_real': rankings_real,
        'rankings_protocol': rankings_protocol,
        'demografia': demografia_data,
        'category_counts': category_counts,
        'genealogy_stats': genealogy_stats
    })

@app.route('/api/plots-for-owners', methods=['POST'])
def get_plots_for_owners():
    """Pobiera działki dla podanych właścicieli (używane na mapie statystyk)."""
    owner_ids = request.get_json().get('owner_ids', [])
    if not owner_ids: 
        return jsonify({})
    owner_ids_int = [int(id) for id in owner_ids]

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = """
        SELECT
            w.id as owner_id, w.nazwa_wlasciciela,
            json_agg(json_build_object(
                'type', 'Feature', 'id', o.id, 'geometry', ST_AsGeoJSON(o.geometria)::json,
                'properties', json_build_object('numer_obiektu', o.nazwa_lub_numer, 'kategoria', o.kategoria)
            )) as features
        FROM wlasciciele w
        JOIN dzialki_wlasciciele dw ON w.id = dw.wlasciciel_id
        JOIN obiekty_geograficzne o ON o.id = dw.obiekt_id
        WHERE w.id = ANY(%s) AND o.geometria IS NOT NULL GROUP BY w.id;
    """
    cur.execute(query, (owner_ids_int,))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(data)

@app.route('/api/graph-data')
def get_graph_data():
    """
    Zwraca dane do wizualizacji grafu powiązań między protokołami.
    Węzły (nodes) to właściciele, a krawędzie (edges) są tworzone na podstawie
    linków [[...|...]] w polu 'powiazania_i_transakcje'.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Krok 1: Pobierz wszystkich właścicieli jako węzły.
    cur.execute("SELECT id, unikalny_klucz, nazwa_wlasciciela, numer_protokolu FROM wlasciciele")
    wlasciciele = cur.fetchall()
    nodes = [{'id': w['unikalny_klucz'], 'label': f"{w['nazwa_wlasciciela']}\n(Lp. {w['numer_protokolu'] or 'N/A'})", 'title': f"Protokół Lp. {w['numer_protokolu'] or 'N/A'}"} for w in wlasciciele]
        
    # Krok 2: Przetwórz pole 'powiazania_i_transakcje' w poszukiwaniu linków, aby stworzyć krawędzie.
    edges = []
    link_pattern = re.compile(r'\[\[.*?\|(.*?)\]\]')
    cur.execute("SELECT unikalny_klucz, powiazania_i_transakcje FROM wlasciciele")
    wszystkie_powiazania = cur.fetchall()

    for zrodlo in wszystkie_powiazania:
        if zrodlo['powiazania_i_transakcje']:
            cele = set(link_pattern.findall(zrodlo['powiazania_i_transakcje']))
            for cel in cele:
                if zrodlo['unikalny_klucz'] != cel:
                    edges.append({'from': zrodlo['unikalny_klucz'], 'to': cel, 'arrows': 'to'})

    cur.close()
    conn.close()
    return jsonify({'nodes': nodes, 'edges': edges})

@app.route('/api/genealogia/full-graph')
def get_full_genealogy_graph():
    """Zwraca pełny graf genealogiczny wszystkich osób."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Pobierz osoby jako węzły
    cur.execute("SELECT p.id, p.imie_nazwisko, p.plec, w.unikalny_klucz as protocol_key FROM osoby_genealogia p LEFT JOIN wlasciciele w ON p.id_protokolu = w.id;")
    wszystkie_osoby = cur.fetchall()
    nodes = []
    for osoba in wszystkie_osoby:
        tooltip_text = f"ID: {osoba['id']}" + (f"\nProtokół: {osoba['protocol_key']}" if osoba['protocol_key'] else "")
        nodes.append({
            'id': osoba['id'], 
            'label': osoba['imie_nazwisko'],
            'shape': 'box' if osoba['plec'] == 'M' else 'ellipse',
            'color': '#3498db' if osoba['plec'] == 'M' else '#e91e63',
            'title': tooltip_text, 
            'protocolKey': osoba['protocol_key']
        })
        
    # Relacje jako krawędzie
    edges = []
    cur.execute("SELECT id, id_ojca, id_matki FROM osoby_genealogia WHERE id_ojca IS NOT NULL OR id_matki IS NOT NULL;")
    for relacja in cur.fetchall():
        if relacja['id_ojca']: 
            edges.append({'from': relacja['id_ojca'], 'to': relacja['id']})
        if relacja['id_matki']: 
            edges.append({'from': relacja['id_matki'], 'to': relacja['id']})
            
    cur.execute("SELECT malzonek1_id, malzonek2_id FROM malzenstwa;")
    for malzenstwo in cur.fetchall():
        edges.append({'from': malzenstwo['malzonek1_id'], 'to': malzenstwo['malzonek2_id'], 
                     'dashes': True, 'color': '#9b59b6', 'arrows': ''})

    cur.close()
    conn.close()
    return jsonify({'nodes': nodes, 'edges': edges})

# =============================================================================
# SERWOWANIE PLIKÓW STATYCZNYCH (FRONTEND)
# =============================================================================

# Ścieżki do katalogów frontendu
BASE_PATH = os.path.dirname(__file__)
STRONA_GLOWNA_PATH = os.path.join(BASE_PATH, '..', 'strona_glowna')
MAPA_PATH = os.path.join(BASE_PATH, '..', 'mapa')
WLASCICIELE_PATH = os.path.join(BASE_PATH, '..', 'wlasciciele')
GRAF_PATH = os.path.join(BASE_PATH, '..', 'graf')
GENEALOGIA_PATH = os.path.join(BASE_PATH, '..', 'genealogia')
DOCS_PATH = os.path.join(BASE_PATH, '..', 'docs')
ZGLOSZENIE_I_KARTA_PROJEKTU_PATH = os.path.join(BASE_PATH, '..', 'Zgloszenie_i_Karta_Projektu')
ASSETS_PATH = os.path.join(BASE_PATH, '..', 'assets')
ASSETS_INDEX_PATH = os.path.join(STRONA_GLOWNA_PATH, 'assets_index')
ADMIN_FOLDER_PATH = os.path.join(BASE_PATH, '..', 'admin')

# Endpointy serwujące pliki
@app.route('/genealogia/<path:filename>')
def serve_genealogy_files(filename): 
    return send_from_directory(GENEALOGIA_PATH, filename)

@app.route('/graf/<path:filename>')
def serve_graph_files(filename): 
    return send_from_directory(GRAF_PATH, filename)

@app.route('/Zgloszenie_i_Karta_Projektu/<path:filename>')
def serve_project_card_files(filename): 
    return send_from_directory(ZGLOSZENIE_I_KARTA_PROJEKTU_PATH, filename)

@app.route('/strona_glowna/<path:filename>')
def serve_main_page(filename): 
    return send_from_directory(STRONA_GLOWNA_PATH, filename)

@app.route('/mapa/mapa.html')
def serve_map_page():
    """Serwuje główną stronę mapy, wstrzykując do niej konfigurację."""
    from flask import render_template_string
    
    template_path = os.path.join(MAPA_PATH, 'mapa.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()

    # Wstrzyknięcie konfiguracji jako globalny obiekt JS
    # Przekazujemy bezpośrednio obiekt Pythona, a szablon Jinja2 zamieni go na JSON
    return render_template_string(
        template_content, 
        map_config_data=map_config
    )

@app.route('/mapa/<path:filename>')
def serve_map_files(filename): 
    # Ta funkcja obsługuje teraz tylko pliki statyczne (JS, CSS)
    if filename == 'mapa.html':
        return redirect(url_for('serve_map_page'))
    return send_from_directory(MAPA_PATH, filename)

@app.route('/wlasciciele/<path:filename>')
def serve_owner_files(filename): 
    return send_from_directory(WLASCICIELE_PATH, filename)

@app.route('/strona_glowna/assets_index/<path:filename>')
def serve_main_page_assets(filename): 
    return send_from_directory(ASSETS_INDEX_PATH, filename)

@app.route('/docs/<path:filename>')
def serve_docs_files(filename): 
    return send_from_directory(DOCS_PATH, filename)

@app.route('/docs/assets/<path:filename>')
def serve_docs_assets(filename): 
    return send_from_directory(os.path.join(DOCS_PATH, 'assets'), filename)

@app.route('/assets/<path:subfolder>/<path:filename>')
def serve_assets(subfolder, filename):
    """Serwuje pliki z podfolderów assets (np. skany protokołów)."""
    return send_from_directory(os.path.join(ASSETS_PATH, subfolder), filename)

@app.route('/assets/<path:filename>')
def serve_root_asset(filename):
    return send_from_directory(ASSETS_PATH, filename)

@app.route('/favicon.ico')
def favicon():
    """Dynamicznie serwuje favicon zdefiniowany w bazie danych."""
    if favicon_path:
        directory, filename = os.path.split(favicon_path)
        # Buduje pełną ścieżkę do katalogu wewnątrz ASSETS_PATH
        full_directory_path = os.path.join(ASSETS_PATH, directory)
        return send_from_directory(full_directory_path, filename)
    
    # Jeśli brak konfiguracji, zwróć błąd 404, przeglądarka użyje domyślnej ikony
    return '', 404

# =============================================================================
# PANEL ADMINISTRACYJNY - AUTORYZACJA
# =============================================================================

@app.route('/admin')
def admin_index():
    """Przekierowanie na panel administracyjny."""
    return redirect(url_for('admin_static_files', filename='admin.html'))

@app.route('/admin/<path:filename>')
def admin_static_files(filename):
    """Serwuje pliki panelu admina."""
    file_path = os.path.join(ADMIN_FOLDER_PATH, filename)
    if not os.path.exists(file_path):
        return redirect(url_for('admin_index'))
    return send_from_directory(ADMIN_FOLDER_PATH, filename)

@app.route('/api/admin/check-auth')
def check_admin_auth():
    """Sprawdza status autoryzacji admina."""
    if not ADMIN_AUTH_ENABLED:
        return jsonify({"authenticated": True, "auth_required": False})
    
    is_logged_in = session.get('admin_logged_in', False)
    return jsonify({"authenticated": is_logged_in, "auth_required": True})

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Obsługuje logowanie do panelu admina z mechanizmem blokowania IP."""
    user_ip = request.remote_addr
    
    # Autoryzacja wyłączona - automatyczne logowanie
    if not ADMIN_AUTH_ENABLED:
        session["admin_logged_in"] = True
        return jsonify({"status": "ok", "message": "Auth disabled – auto-login"})

    data = request.get_json() or {}
    username = data.get("username", "")
    password = data.get("password", "")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Sprawdź blokadę IP
            cur.execute("SELECT 1 FROM blocked_ips WHERE ip_address = %s", (user_ip,))
            if cur.fetchone():
                cur.execute(
                    "INSERT INTO login_attempts (ip_address, username_attempt, successful) VALUES (%s, %s, %s)",
                    (user_ip, username, False)
                )
                conn.commit()
                return jsonify({"status": "error", "message": "Dostęp z tego adresu IP jest zablokowany."}), 403

            # Weryfikacja danych logowania
            login_successful = (username == ADMIN_USERNAME and ADMIN_PASSWORD_HASH and 
                              check_password_hash(ADMIN_PASSWORD_HASH, password))

            # Zapisz próbę logowania
            cur.execute(
                "INSERT INTO login_attempts (ip_address, username_attempt, successful) VALUES (%s, %s, %s)",
                (user_ip, username, login_successful)
            )

            if login_successful:
                # Sukces - wyczyść nieudane próby
                cur.execute(
                    "DELETE FROM login_attempts WHERE ip_address = %s AND successful = FALSE",
                    (user_ip,)
                )
                session["admin_logged_in"] = True
                conn.commit()
                return jsonify({"status": "ok"})
            else:
                # Błąd - sprawdź limit prób
                fifteen_minutes_ago = datetime.utcnow() - timedelta(minutes=15)
                cur.execute(
                    "SELECT COUNT(*) FROM login_attempts WHERE ip_address = %s AND successful = FALSE AND timestamp > %s",
                    (user_ip, fifteen_minutes_ago)
                )
                failed_attempts = cur.fetchone()[0]

                # Zablokuj po 5 nieudanych próbach
                if failed_attempts >= 5:
                    cur.execute(
                        "INSERT INTO blocked_ips (ip_address, reason) VALUES (%s, %s) ON CONFLICT (ip_address) DO NOTHING",
                        (user_ip, f"Automatyczna blokada po {failed_attempts} nieudanych próbach logowania.")
                    )
                    conn.commit()
                    return jsonify({"status": "error", "message": "Zbyt wiele nieudanych prób. Twój adres IP został zablokowany."}), 403
                
                conn.commit()
                return jsonify({"status": "error", "message": "Nieprawidłowy login lub hasło."}), 401
    finally:
        conn.close()

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    """Wylogowanie z panelu admina."""
    session.pop("admin_logged_in", None)  
    return jsonify({"status": "ok"})

@app.route('/api/admin/auth-status')
def admin_auth_status():
    """Zwraca status autoryzacji."""
    return jsonify({
        "enabled": ADMIN_AUTH_ENABLED,
        "logged_in": bool(session.get("admin_logged_in"))
    })

# =============================================================================
# PANEL ADMINISTRACYJNY - CRUD
# =============================================================================

@app.route('/api/admin/dashboard-stats')
def admin_get_dashboard_stats():
    """Statystyki dla pulpitu admina."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM wlasciciele;")
    total_owners = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM obiekty_geograficzne;")
    total_objects = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({'total_owners': total_owners, 'total_objects': total_objects})

# --- Właściciele ---

@app.route('/api/admin/wlasciciele', methods=['GET'])
def admin_get_all_wlasciciele():
    """Lista wszystkich właścicieli dla admina."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM wlasciciele ORDER BY numer_protokolu, id;')
    wlasciciele = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(wlasciciele)

@app.route('/api/admin/wlasciciele/<int:id>', methods=['GET'])
def admin_get_single_wlasciciel(id):
    """Szczegóły właściciela do edycji."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM wlasciciele WHERE id = %s", (id,))
    wlasciciel_data = cur.fetchone()
    if not wlasciciel_data:
        return jsonify({"status": "error", "message": "Właściciel nie znaleziony"}), 404
    cur.execute("SELECT o.id, o.nazwa_lub_numer, o.kategoria, dw.typ_posiadania FROM obiekty_geograficzne o JOIN dzialki_wlasciciele dw ON o.id = dw.obiekt_id WHERE dw.wlasciciel_id = %s", (id,))
    wlasciciel_data['dzialki_wszystkie'] = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(wlasciciel_data)

@app.route('/api/admin/wlasciciele', methods=['POST'])
def admin_create_wlasciciel():
    """Tworzenie nowego właściciela."""
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            numer_protokolu_int = int(data['numer_protokolu']) if data.get('numer_protokolu') else None
            cur.execute("""
                INSERT INTO wlasciciele (unikalny_klucz, nazwa_wlasciciela, numer_protokolu, numer_domu, 
                    genealogia, historia_wlasnosci, uwagi, wspolwlasnosc, powiazania_i_transakcje, 
                    interpretacja_i_wnioski, data_protokolu, miejsce_protokolu)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """, (data['unikalny_klucz'], data['nazwa_wlasciciela'], numer_protokolu_int, 
                  data.get('numer_domu'), data.get('genealogia'), data.get('historia_wlasnosci'), 
                  data.get('uwagi'), data.get('wspolwlasnosc'), data.get('powiazania_i_transakcje'), 
                  data.get('interpretacja_i_wnioski'), data.get('data_protokolu') or None, 
                  data.get('miejsce_protokolu')))
            new_id = cur.fetchone()[0]
            conn.commit()
            return jsonify({'status': 'success', 'id': new_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/wlasciciele/<int:id>', methods=['PUT'])
def admin_update_wlasciciel(id):
    """Aktualizacja właściciela i jego powiązań z działkami."""
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Aktualizacja danych właściciela
            numer_protokolu = int(data.get('numer_protokolu')) if str(data.get('numer_protokolu')).isdigit() else None
            
            cur.execute("""
                UPDATE wlasciciele SET 
                    unikalny_klucz = %s, nazwa_wlasciciela = %s, numer_protokolu = %s, 
                    numer_domu = %s, genealogia = %s, historia_wlasnosci = %s, 
                    uwagi = %s, wspolwlasnosc = %s, powiazania_i_transakcje = %s, 
                    interpretacja_i_wnioski = %s, data_protokolu = %s, miejsce_protokolu = %s
                WHERE id = %s;
            """, (data.get('unikalny_klucz'), data.get('nazwa_wlasciciela'), numer_protokolu,
                  data.get('numer_domu'), data.get('genealogia'), data.get('historia_wlasnosci'),
                  data.get('uwagi'), data.get('wspolwlasnosc'), data.get('powiazania_i_transakcje'),
                  data.get('interpretacja_i_wnioski'), data.get('data_protokolu') or None, 
                  data.get('miejsce_protokolu'), id))

            # Aktualizacja powiązań z działkami
            cur.execute("DELETE FROM dzialki_wlasciciele WHERE wlasciciel_id = %s;", (id,))

            real_ids = set(map(int, data.get('dzialki_rzeczywiste_ids', [])))
            prot_ids = set(map(int, data.get('dzialki_protokol_ids', [])))
            prot_only_ids = prot_ids - real_ids  # Uniknięcie duplikatów

            rows_to_insert = []
            if real_ids:
                rows_to_insert.extend([(id, parcel_id, 'własność rzeczywista') for parcel_id in sorted(real_ids)])
            if prot_only_ids:
                rows_to_insert.extend([(id, parcel_id, 'własność z protokołu') for parcel_id in sorted(prot_only_ids)])

            if rows_to_insert:
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO dzialki_wlasciciele (wlasciciel_id, obiekt_id, typ_posiadania) VALUES %s",
                    rows_to_insert
                )
            
            conn.commit()
            return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': f'Błąd po stronie serwera: {e}'}), 500
    finally:
        conn.close()

@app.route('/api/admin/wlasciciele/<int:id>', methods=['DELETE'])
def admin_delete_wlasciciel(id):
    """Usuwanie właściciela."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM wlasciciele WHERE id = %s;", (id,))
            conn.commit()
            return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

# --- Obiekty geograficzne ---

@app.route('/api/admin/wszystkie-obiekty', methods=['GET'])
def admin_get_all_obiekty():
    """Lista obiektów do formularzy."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, nazwa_lub_numer, kategoria FROM obiekty_geograficzne 
        ORDER BY NULLIF((regexp_split_to_array(nazwa_lub_numer, E'[^0-9]+'))[1], '')::integer NULLS FIRST,
                nazwa_lub_numer;
    """)
    obiekty = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(obiekty)

@app.route('/api/admin/obiekty', methods=['GET'])
def admin_get_all_obiekty_full():
    """Pełna lista obiektów dla tabeli admina."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT o.id, o.nazwa_lub_numer, o.kategoria,
            CASE WHEN dw.obiekt_id IS NULL THEN false ELSE true END as is_linked
        FROM obiekty_geograficzne o
        LEFT JOIN dzialki_wlasciciele dw ON o.id = dw.obiekt_id
        GROUP BY o.id, dw.obiekt_id
        ORDER BY NULLIF((regexp_split_to_array(o.nazwa_lub_numer, E'[^0-9]+'))[1], '')::integer NULLS FIRST,
                o.nazwa_lub_numer;
    """)
    obiekty = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(obiekty)

@app.route('/api/admin/obiekty/<int:id>', methods=['PUT'])
def admin_update_obiekt(id):
    """Aktualizacja obiektu."""
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE obiekty_geograficzne SET nazwa_lub_numer = %s, kategoria = %s WHERE id = %s;", 
                       (data.get('nazwa_lub_numer'), data.get('kategoria'), id))
            conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/obiekty/<int:id>', methods=['DELETE'])
def admin_delete_obiekt(id):
    """Usuwanie obiektu."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM obiekty_geograficzne WHERE id = %s;", (id,))
            conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

# --- Demografia ---

@app.route('/api/admin/demografia', methods=['GET'])
def get_demografia_data():
    """Lista danych demograficznych."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM demografia ORDER BY rok ASC;")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(data)

@app.route('/api/admin/demografia', methods=['POST'])
def add_demografia_entry():
    """Dodawanie wpisu demograficznego."""
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO demografia (rok, populacja_ogolem, katolicy, zydzi, inni, opis) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;", 
                       (data['rok'], data.get('populacja_ogolem'), data.get('katolicy'), 
                        data.get('zydzi'), data.get('inni'), data.get('opis')))
            new_id = cur.fetchone()[0]
            conn.commit()
            return jsonify({'status': 'success', 'id': new_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/demografia/<int:id>', methods=['PUT'])
def update_demografia_entry(id):
    """Aktualizacja wpisu demograficznego."""
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE demografia SET rok = %s, populacja_ogolem = %s, katolicy = %s, zydzi = %s, inni = %s, opis = %s WHERE id = %s;", 
                       (data['rok'], data.get('populacja_ogolem'), data.get('katolicy'), 
                        data.get('zydzi'), data.get('inni'), data.get('opis'), id))
            conn.commit()
            return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/demografia/<int:id>', methods=['DELETE'])
def delete_demografia_entry(id):
    """Usuwanie wpisu demograficznego."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM demografia WHERE id = %s;", (id,))
            conn.commit()
            return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

# --- Genealogia ---

@app.route('/api/admin/genealogia', methods=['GET'])
def admin_get_genealogia():
    """Lista osób w genealogii."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT p.id AS db_id, p.json_id AS id_osoby, p.imie_nazwisko, p.rok_urodzenia, 
               p.rok_smierci, p.id_ojca, p.id_matki, p.plec, p.numer_domu, p.uwagi, 
               w.unikalny_klucz AS protokol_klucz,
               CASE WHEN m1.malzonek2_id IS NOT NULL THEN m1.malzonek2_id 
                    ELSE m2.malzonek1_id END AS id_malzonka
        FROM osoby_genealogia p
        LEFT JOIN wlasciciele w ON p.id_protokolu = w.id 
        LEFT JOIN malzenstwa m1 ON p.id = m1.malzonek1_id
        LEFT JOIN malzenstwa m2 ON p.id = m2.malzonek2_id 
        ORDER BY p.rok_urodzenia, p.imie_nazwisko;
    """)
    people = cur.fetchall()
    cur.close()
    conn.close()
    
    # Rozdzielenie imienia i nazwiska
    for person in people:
        name_parts = (person['imie_nazwisko'] or '').split(' ', 1)
        person['imie'] = name_parts[0]
        person['nazwisko'] = name_parts[1] if len(name_parts) > 1 else ''
    return jsonify(people)

@app.route('/api/admin/genealogia', methods=['POST'])
def admin_create_osoba():
    """Tworzenie nowej osoby w genealogii."""
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO osoby_genealogia (json_id, imie_nazwisko, plec, numer_domu, 
                    rok_urodzenia, rok_smierci, id_ojca, id_matki, id_protokolu, uwagi)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 
                    (SELECT id FROM wlasciciele WHERE unikalny_klucz = %s), %s) RETURNING id;
            """, (int(data['id_osoby']), f"{data['imie']} {data['nazwisko']}".strip(), 
                  data.get('plec'), data.get('numer_domu'), data.get('rok_urodzenia'), 
                  data.get('rok_smierci'), data.get('id_ojca'), data.get('id_matki'), 
                  data.get('protokol_klucz'), data.get('uwagi')))
            new_id = cur.fetchone()[0]
            
            # Małżeństwo
            if data.get('id_malzonka'):
                para = tuple(sorted((new_id, int(data['id_malzonka']))))
                cur.execute("INSERT INTO malzenstwa (malzonek1_id, malzonek2_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;", para)
            conn.commit()
            return jsonify({'status': 'success', 'id': new_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/genealogia/<int:id>', methods=['PUT'])
def admin_update_osoba(id):
    """Aktualizacja osoby w genealogii."""
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE osoby_genealogia SET json_id = %s, imie_nazwisko = %s, plec = %s, 
                    numer_domu = %s, rok_urodzenia = %s, rok_smierci = %s, id_ojca = %s, 
                    id_matki = %s, id_protokolu = (SELECT id FROM wlasciciele WHERE unikalny_klucz = %s), 
                    uwagi = %s WHERE id = %s;
            """, (int(data['id_osoby']), f"{data['imie']} {data['nazwisko']}".strip(), 
                  data.get('plec'), data.get('numer_domu'), data.get('rok_urodzenia'), 
                  data.get('rok_smierci'), data.get('id_ojca'), data.get('id_matki'), 
                  data.get('protokol_klucz'), data.get('uwagi'), id))
            
            # Aktualizacja małżeństw
            cur.execute("DELETE FROM malzenstwa WHERE malzonek1_id = %s OR malzonek2_id = %s;", (id, id))
            if data.get('id_malzonka'):
                para = tuple(sorted((id, int(data['id_malzonka']))))
                cur.execute("INSERT INTO malzenstwa (malzonek1_id, malzonek2_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;", para)
            conn.commit()
            return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/genealogia/<int:id>', methods=['DELETE'])
def admin_delete_osoba(id):
    """Usuwanie osoby z genealogii."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Usuwanie powiązań
            cur.execute("DELETE FROM malzenstwa WHERE malzonek1_id = %s OR malzonek2_id = %s;", (id, id))
            cur.execute("UPDATE osoby_genealogia SET id_ojca = NULL WHERE id_ojca = %s;", (id,))
            cur.execute("UPDATE osoby_genealogia SET id_matki = NULL WHERE id_matki = %s;", (id,))
            cur.execute("DELETE FROM osoby_genealogia WHERE id = %s;", (id,))
            conn.commit()
            return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/protocols', methods=['GET'])
def admin_get_protocols():
    """Lista protokołów dla formularzy."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT unikalny_klucz as key, nazwa_wlasciciela as name, numer_protokolu as orderNumber FROM wlasciciele ORDER BY numer_protokolu;")
    protocols = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(protocols)

# =============================================================================
# EKSPORT I BEZPIECZEŃSTWO
# =============================================================================

@app.route('/api/admin/export-backup')
def export_backup():
    """Tworzy kompletną kopię zapasową w formacie ZIP."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # Eksport działek
        cur.execute("SELECT id, nazwa_lub_numer, kategoria, ST_AsGeoJSON(geometria) as geojson FROM obiekty_geograficzne;")
        obiekty = cur.fetchall()
        parcels_data = {}
        for obj in obiekty:
            geom_data = None
            if obj['geojson']:
                geom = json.loads(obj['geojson'])
                if geom['type'] == 'Point': 
                    geom_data = [geom['coordinates'][1], geom['coordinates'][0]]
                elif geom['type'] == 'LineString': 
                    geom_data = [[p[1], p[0]] for p in geom['coordinates']]
                elif geom['type'] == 'Polygon': 
                    geom_data = [[p[1], p[0]] for p in geom['coordinates'][0]]
            parcels_data[obj['nazwa_lub_numer']] = {'geometria': geom_data, 'kategoria': obj['kategoria']}

        # Eksport właścicieli
        cur.execute("SELECT * FROM wlasciciele;")
        wlasciciele_wszyscy = cur.fetchall()
        cur.execute("SELECT dw.wlasciciel_id, o.nazwa_lub_numer, o.kategoria, dw.typ_posiadania FROM dzialki_wlasciciele dw JOIN obiekty_geograficzne o ON dw.obiekt_id = o.id")
        powiazania = cur.fetchall()
        
        owner_data_to_import = {}
        for w in wlasciciele_wszyscy:
            key = w['unikalny_klucz']
            owner_data_to_import[key] = {
                "ownerName": w['nazwa_wlasciciela'], 
                "protocolDate": w['data_protokolu'].strftime('%d %B %Y') if w.get('data_protokolu') else "",
                "protocolLocation": w['miejsce_protokolu'], 
                "orderNumber": str(w['numer_protokolu'] or ''), 
                "houseNumber": w['numer_domu'],
                "buildingPlots": [], "agriculturalPlots": [], 
                "realbuildingPlots": [], "realagriculturalPlots": [],
                "genealogy": w.get('genealogia'), 
                "ownershipHistory": w.get('historia_wlasnosci'), 
                "remarks": w.get('uwagi'),
                "wspolwlasnosc": w.get('wspolwlasnosc'),
                "powiazania_i_transakcje": w.get('powiazania_i_transakcje'), 
                "interpretacja_i_wnioski": w.get('interpretacja_i_wnioski')
            }
            for p in powiazania:
                if p['wlasciciel_id'] == w['id']:
                    plot_id = p['nazwa_lub_numer']
                    if p['typ_posiadania'] == 'własność rzeczywista':
                        (owner_data_to_import[key]['realbuildingPlots'] if p['kategoria'] == 'budowlana' 
                         else owner_data_to_import[key]['realagriculturalPlots']).append(plot_id)
                    else:
                        (owner_data_to_import[key]['buildingPlots'] if p['kategoria'] == 'budowlana' 
                         else owner_data_to_import[key]['agriculturalPlots']).append(plot_id)

        # Demografia
        cur.execute("SELECT rok, populacja_ogolem, katolicy, zydzi, inni, opis FROM demografia ORDER BY rok ASC;")
        demografia_data = cur.fetchall()

        # Genealogia
        cur.execute("SELECT * FROM osoby_genealogia;")
        osoby_db = cur.fetchall()
        cur.execute("SELECT * FROM malzenstwa;")
        malzenstwa_db = cur.fetchall()
        
        db_id_to_json_id = {o['id']: o['json_id'] for o in osoby_db}
        spouse_map = {}
        for m in malzenstwa_db:
            id1, id2 = m['malzonek1_id'], m['malzonek2_id']
            spouse_map.setdefault(id1, []).append(db_id_to_json_id.get(id2))
            spouse_map.setdefault(id2, []).append(db_id_to_json_id.get(id1))
        
        persons_json = []
        for p in osoby_db:
            persons_json.append({
                "id": p['json_id'], "name": p['imie_nazwisko'], 
                "gender": p['plec'], "houseNumber": p.get('numer_domu'),
                "birthDate": {"year": p.get('rok_urodzenia')} if p.get('rok_urodzenia') else None,
                "deathDate": {"year": p.get('rok_smierci')} if p.get('rok_smierci') else None,
                "protocolKey": None, 
                "fatherId": db_id_to_json_id.get(p.get('id_ojca')), 
                "motherId": db_id_to_json_id.get(p.get('id_matki')),
                "spouseIds": [spouse for spouse in spouse_map.get(p['id'], []) if spouse is not None], 
                "notes": p.get('uwagi')
            })
        genealogia_data = {"persons": persons_json}

        # Eksport konfiguracji mapy
        cur.execute("SELECT klucz, wartosc FROM konfiguracja_systemu WHERE klucz IN ('map_calibration', 'map_defaults');")
        rows = cur.fetchall()
        config_data = {row['klucz']: row['wartosc'] for row in rows}
        map_config_export = {
            'calibration': config_data.get('map_calibration', {}),
            'defaults': config_data.get('map_defaults', {})
        }

        # Tworzenie archiwum ZIP
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('map_config.json', json.dumps(map_config_export, indent=4, ensure_ascii=False))
            zf.writestr('owner_data_to_import.json', json.dumps(owner_data_to_import, indent=4, ensure_ascii=False))
            zf.writestr('parcels_data.json', json.dumps(parcels_data, indent=4, ensure_ascii=False))
            zf.writestr('demografia.json', json.dumps(demografia_data, indent=4, ensure_ascii=False))
            zf.writestr('genealogia.json', json.dumps(genealogia_data, indent=4, ensure_ascii=False))
        memory_file.seek(0)
        
        return send_file(
            memory_file,
            download_name='pelny_backup_danych.zip',
            as_attachment=True,
            mimetype='application/zip'
        )
    finally:
        cur.close()
        conn.close()

# --- Bezpieczeństwo ---

@app.route('/api/admin/security/status', methods=['GET'])
def get_security_status():
    """Status bezpieczeństwa."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM blocked_ips;")
            blocked_count = cur.fetchone()[0]
            return jsonify({"blocked_ips_count": blocked_count})
    finally:
        conn.close()

@app.route('/api/admin/security/logs', methods=['GET'])
def get_login_logs():
    """Lista prób logowania."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT ip_address, username_attempt, timestamp, successful FROM login_attempts ORDER BY timestamp DESC LIMIT 100;")
            logs = cur.fetchall()
            for log in logs:
                log['timestamp'] = log['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            return jsonify(logs)
    finally:
        conn.close()

@app.route('/api/admin/security/blocked-ips', methods=['GET'])
def get_blocked_ips():
    """Lista zablokowanych IP."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT ip_address, reason, timestamp FROM blocked_ips ORDER BY timestamp DESC;")
            ips = cur.fetchall()
            for ip in ips:
                ip['timestamp'] = ip['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            return jsonify(ips)
    finally:
        conn.close()

@app.route('/api/admin/security/block-ip', methods=['POST'])
def block_ip():
    """Blokowanie adresu IP."""
    data = request.get_json()
    ip_to_block = data.get('ip_address')
    reason = data.get('reason', 'Ręczna blokada przez administratora.')
    if not ip_to_block:
        return jsonify({"status": "error", "message": "Nie podano adresu IP."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO blocked_ips (ip_address, reason) VALUES (%s, %s) ON CONFLICT (ip_address) DO UPDATE SET reason = EXCLUDED.reason, timestamp = NOW();", 
                       (ip_to_block, reason))
            conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/security/unblock-ip', methods=['POST'])
def unblock_ip():
    """Odblokowanie adresu IP."""
    data = request.get_json()
    ip_to_unblock = data.get('ip_address')
    if not ip_to_unblock:
        return jsonify({"status": "error", "message": "Nie podano adresu IP."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM blocked_ips WHERE ip_address = %s;", (ip_to_unblock,))
            conn.commit()
        return jsonify({"status": "success"})
    finally:
        conn.close()

@app.route('/api/admin/security/clear-logs', methods=['POST'])
def clear_login_logs():
    """Czyszczenie logów logowania."""
    if ADMIN_AUTH_ENABLED and not session.get('admin_logged_in'):
        return jsonify({"status": "error", "message": "Brak autoryzacji"}), 401

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM login_attempts;")
            conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# =============================================================================
# URUCHOMIENIE SERWERA
# =============================================================================

if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    
    print(f"\n🚀 Uruchamianie serwera Flask...")
    print(f"   Adres: http://{host}:{port}")
    print(f"   Debug: {debug}")
    print("=" * 60 + "\n")
    
    app.run(host=host, port=port, debug=debug, use_reloader=False)