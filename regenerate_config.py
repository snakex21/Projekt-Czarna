#!/usr/bin/env python3
"""
Skrypt do regeneracji location-config.js z PostgreSQL
"""

import json
import os
import psycopg2

# Konfiguracja
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_postgres_connection():
    """Połączenie z PostgreSQL"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname="mapa_launcher_db",
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "1234"),
        port=os.getenv("DB_PORT", "5432"),
        client_encoding="UTF8"
    )

def escape_js_string(s):
    """Escapuj string dla JavaScript"""
    if not s:
        return ""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')

def generate_location_config_js():
    """Generuje location-config.js z danych PostgreSQL"""

    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()

        # Pobierz aktywną miejscowość wraz z history_photos
        cursor.execute("""
            SELECT
                l.id, l.name, l.full_name, l.powiat, l.region, l.active,
                l.homepage_template, l.year, l.century,
                l.homepage_description, l.history_paragraph1, l.history_paragraph2, l.history_paragraph3,
                l.postgres_db_name,
                l.gmina_katastralna, l.miejscowosc_protokolu,
                COALESCE(
                    (SELECT json_agg(json_build_object('filename', filename, 'caption', caption) ORDER BY order_index)
                     FROM history_photos WHERE location_id = l.id),
                    '[]'::json
                )::text as history_photos
            FROM locations l
            WHERE l.active = true
        """)

        location = cursor.fetchone()
        cursor.close()
        conn.close()

        if not location:
            print("❌ Brak aktywnej miejscowości w PostgreSQL!")
            return False

        # Parsuj dane
        location_name = location[1] or "Miejscowość"
        location_full_name = location[2] or location_name
        location_powiat = location[3] or "Powiat"
        location_region = location[4] or "Region"
        location_year = location[7] or "1882"
        location_century = location[8] or "XIX"
        homepage_description = location[9] or "Odkryj historię zapisaną w ziemi."
        history_p1 = location[10] or ""
        history_p2 = location[11] or ""
        history_p3 = location[12] or ""

        # Pobierz history_photos jako JSON (indeks 16)
        history_photos_json = location[16]
        try:
            history_photos = json.loads(history_photos_json) if history_photos_json else []
        except (json.JSONDecodeError, TypeError):
            history_photos = []

        print(f"📊 Dane z PostgreSQL:")
        print(f"   Miejscowość: {location_full_name}")
        print(f"   Liczba zdjęć: {len(history_photos)}")
        if history_photos:
            print(f"   Zdjęcia:")
            for photo in history_photos:
                print(f"     - {photo.get('filename')}: {photo.get('caption')}")

        # Przygotuj JSON dla history_photos
        photos_json = json.dumps(history_photos, ensure_ascii=False, indent=4)

        # Wygeneruj zawartość pliku JS
        js_content = f"""// Konfiguracja aktualnej miejscowości
// Ten plik jest automatycznie generowany przez launcher
window.LOCATION_CONFIG = {{
    name: "{escape_js_string(location_name)}",
    fullName: "{escape_js_string(location_full_name)}",
    powiat: "{escape_js_string(location_powiat)}",
    region: "{escape_js_string(location_region)}",
    year: "{escape_js_string(location_year)}",
    century: "{escape_js_string(location_century)}",
    homepageDescription: "{escape_js_string(homepage_description)}",
    historyParagraph1: "{escape_js_string(history_p1)}",
    historyParagraph2: "{escape_js_string(history_p2)}",
    historyParagraph3: "{escape_js_string(history_p3)}",
    historyPhotos: {photos_json}
}};
"""

        # Zapisz plik
        static_js_folder = os.path.join(BASE_DIR, "static", "js")
        js_path = os.path.join(static_js_folder, "location-config.js")

        os.makedirs(static_js_folder, exist_ok=True)

        with open(js_path, 'w', encoding='utf-8') as f:
            f.write(js_content)

        print(f"✅ Wygenerowano location-config.js dla miejscowości: {location_full_name}")
        print(f"✅ Plik zapisany: {js_path}")
        return True

    except Exception as e:
        print(f"❌ Błąd: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🔄 Regeneruję location-config.js...")
    if generate_location_config_js():
        print("\n✅ Gotowe!")
    else:
        print("\n❌ Niepowodzenie!")
        exit(1)
