"""Schema SQL dla PostgreSQL — wspólne dla launcher_app.py i db/postgres.py."""
# Uwaga: to są schematy PostgreSQL (nie SQLite). SQLite ma osobny schemat w backend/db/schema.sql.

# Schemat bazy launcher (mapa_launcher_db) — rejestr miejscowości
LAUNCHER_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(200),
    powiat VARCHAR(100),
    region VARCHAR(100),
    active BOOLEAN DEFAULT FALSE,
    homepage_template VARCHAR(50) DEFAULT 'standardowy',
    year VARCHAR(10) DEFAULT '1882',
    century VARCHAR(20) DEFAULT 'XIX w.',
    homepage_description TEXT,
    history_paragraph1 TEXT,
    history_paragraph2 TEXT,
    history_paragraph3 TEXT,
    postgres_db_name VARCHAR(100),
    gmina_katastralna VARCHAR(100),
    miejscowosc_protokolu VARCHAR(100),
    area_hectares NUMERIC(10, 2),
    area_km2 NUMERIC(10, 4),
    boundary_coordinates JSONB,
    jewish_protocol_numbers TEXT,
    custom_icon VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS history_photos (
    id SERIAL PRIMARY KEY,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    caption TEXT,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS launcher_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_location_active ON locations(active);
CREATE INDEX IF NOT EXISTS idx_location_name ON locations(name);
CREATE INDEX IF NOT EXISTS idx_photos_location ON history_photos(location_id);
CREATE INDEX IF NOT EXISTS idx_photos_order ON history_photos(location_id, order_index);
CREATE INDEX IF NOT EXISTS idx_launcher_settings_key ON launcher_settings(setting_key);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_locations_updated_at ON locations;
CREATE TRIGGER update_locations_updated_at BEFORE UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_launcher_settings_updated_at ON launcher_settings;
CREATE TRIGGER update_launcher_settings_updated_at BEFORE UPDATE ON launcher_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE FUNCTION ensure_single_active_location()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.active = TRUE THEN
        UPDATE locations SET active = FALSE WHERE id != NEW.id;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS single_active_location ON locations;
CREATE TRIGGER single_active_location BEFORE INSERT OR UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION ensure_single_active_location();
"""

# Schemat usuwania tabel launcher
LAUNCHER_DROP_TABLES = """
DROP TRIGGER IF EXISTS update_locations_updated_at ON locations;
DROP TRIGGER IF EXISTS single_active_location ON locations;
DROP TABLE IF EXISTS history_photos CASCADE;
DROP TABLE IF EXISTS locations CASCADE;
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS ensure_single_active_location() CASCADE;
"""

# Schemat bazy danych dla miejscowości (mapa_*_db)
LOCATION_DB_SCHEMA = """
DROP TABLE IF EXISTS malzenstwa, osoby_genealogia, powiazania_protokolow, dzialki_wlasciciele,
                     wlasciciele, obiekty_geograficzne, demografia, login_attempts,
                     blocked_ips, konfiguracja_systemu CASCADE;

CREATE TABLE konfiguracja_systemu (
    klucz VARCHAR(50) PRIMARY KEY,
    wartosc JSONB NOT NULL,
    opis TEXT
);

CREATE TABLE obiekty_geograficzne (
    id SERIAL PRIMARY KEY,
    nazwa_lub_numer VARCHAR(50) NOT NULL,
    kategoria VARCHAR(50) NOT NULL,
    geometria GEOMETRY(GEOMETRY, 4326),
    UNIQUE (nazwa_lub_numer, kategoria)
);

CREATE TABLE wlasciciele (
    id SERIAL PRIMARY KEY,
    unikalny_klucz VARCHAR(100) NOT NULL UNIQUE,
    nazwa_wlasciciela VARCHAR(255) NOT NULL,
    numer_protokolu INTEGER,
    numer_domu VARCHAR(50),
    data_protokolu DATE,
    miejsce_protokolu VARCHAR(100),
    genealogia TEXT,
    historia_wlasnosci TEXT,
    uwagi TEXT,
    wspolwlasnosc TEXT,
    powiazania_i_transakcje TEXT,
    interpretacja_i_wnioski TEXT
);

CREATE TABLE osoby_genealogia (
    id SERIAL PRIMARY KEY,
    json_id INTEGER UNIQUE NOT NULL,
    imie_nazwisko VARCHAR(255) NOT NULL,
    plec VARCHAR(1),
    numer_domu VARCHAR(50),
    rok_urodzenia INTEGER,
    rok_smierci INTEGER,
    id_ojca INTEGER REFERENCES osoby_genealogia(id) ON DELETE SET NULL,
    id_matki INTEGER REFERENCES osoby_genealogia(id) ON DELETE SET NULL,
    id_protokolu INTEGER REFERENCES wlasciciele(id) ON DELETE SET NULL,
    uwagi TEXT
);

CREATE TABLE malzenstwa (
    malzonek1_id INTEGER NOT NULL REFERENCES osoby_genealogia(id) ON DELETE CASCADE,
    malzonek2_id INTEGER NOT NULL REFERENCES osoby_genealogia(id) ON DELETE CASCADE,
    rok_slubu INTEGER, miesiac_slubu INTEGER, dzien_slubu INTEGER,
    data_slubu TEXT,
    PRIMARY KEY (malzonek1_id, malzonek2_id),
    CONSTRAINT rozne_osoby CHECK (malzonek1_id <> malzonek2_id)
);

CREATE TABLE dzialki_wlasciciele (
    id SERIAL PRIMARY KEY,
    wlasciciel_id INTEGER NOT NULL REFERENCES wlasciciele(id) ON DELETE CASCADE,
    obiekt_id INTEGER NOT NULL REFERENCES obiekty_geograficzne(id) ON DELETE CASCADE,
    typ_posiadania VARCHAR(50),
    opis_udzialu TEXT,
    UNIQUE (wlasciciel_id, obiekt_id, typ_posiadania)
);

CREATE TABLE demografia (
    id SERIAL PRIMARY KEY,
    rok INTEGER NOT NULL UNIQUE,
    populacja_ogolem INTEGER DEFAULT 0,
    katolicy INTEGER, zydzi INTEGER, inni INTEGER,
    opis TEXT
);

CREATE TABLE powiazania_protokolow (
    id SERIAL PRIMARY KEY,
    wlasciciel_id_1 INTEGER NOT NULL REFERENCES wlasciciele(id) ON DELETE CASCADE,
    wlasciciel_id_2 INTEGER NOT NULL REFERENCES wlasciciele(id) ON DELETE CASCADE,
    typ_relacji VARCHAR(50),
    opis_relacji TEXT
);

CREATE TABLE login_attempts (
    id SERIAL PRIMARY KEY,
    ip_address VARCHAR(45) NOT NULL,
    username_attempt VARCHAR(255),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    successful BOOLEAN NOT NULL
);

CREATE TABLE blocked_ips (
    id SERIAL PRIMARY KEY,
    ip_address VARCHAR(45) NOT NULL UNIQUE,
    reason TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_obiekty_geometria ON obiekty_geograficzne USING GIST (geometria);
CREATE INDEX idx_wlasciciele_nazwa ON wlasciciele (nazwa_wlasciciela);
CREATE INDEX idx_osoby_genealogia_protokol ON osoby_genealogia (id_protokolu);
CREATE INDEX idx_login_attempts_ip ON login_attempts (ip_address);

INSERT INTO konfiguracja_systemu (klucz, wartosc, opis) VALUES
('map_calibration', '{"sw": {"lat": 50.0414, "lng": 21.2261}, "ne": {"lat": 50.0814, "lng": 21.2661}}', 'Współrzędne kalibracji mapy'),
('map_defaults', '{"center": {"lat": 50.0614, "lng": 21.2461}, "zoom": 14}', 'Domyślny widok startowy mapy')
ON CONFLICT (klucz) DO NOTHING;
"""

# Schemat usuwania tabel miejscowości
LOCATION_DROP_TABLES = """
DROP TABLE IF EXISTS malzenstwa, osoby_genealogia, powiazania_protokolow, dzialki_wlasciciele,
                     wlasciciele, obiekty_geograficzne, demografia, login_attempts,
                     blocked_ips, konfiguracja_systemu CASCADE;
"""
