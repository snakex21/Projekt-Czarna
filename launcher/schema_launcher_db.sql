-- =============================================================================
-- Schema dla mapa_launcher_db
-- Baza konfiguracyjna dla launchera (zamiast SQLite)
-- =============================================================================

-- Tabela miejscowości
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
    postgres_db_name VARCHAR(100),  -- Nazwa bazy PostgreSQL dla tej miejscowości
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela zdjęć historycznych
CREATE TABLE IF NOT EXISTS history_photos (
    id SERIAL PRIMARY KEY,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    caption TEXT,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index dla szybszego wyszukiwania
CREATE INDEX IF NOT EXISTS idx_location_active ON locations(active);
CREATE INDEX IF NOT EXISTS idx_location_name ON locations(name);
CREATE INDEX IF NOT EXISTS idx_photos_location ON history_photos(location_id);
CREATE INDEX IF NOT EXISTS idx_photos_order ON history_photos(location_id, order_index);

-- Trigger do aktualizacji updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_locations_updated_at BEFORE UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Upewnij się że zawsze tylko jedna miejscowość jest aktywna
CREATE OR REPLACE FUNCTION ensure_single_active_location()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.active = TRUE THEN
        UPDATE locations SET active = FALSE WHERE id != NEW.id;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER single_active_location BEFORE INSERT OR UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION ensure_single_active_location();

-- Komentarze
COMMENT ON TABLE locations IS 'Konfiguracja wszystkich miejscowości zarządzanych przez launcher';
COMMENT ON TABLE history_photos IS 'Zdjęcia historyczne dla każdej miejscowości (max 20 na miejscowość)';
COMMENT ON COLUMN locations.postgres_db_name IS 'Nazwa bazy PostgreSQL zawierającej dane mapy (np. mapa_czarna_db)';
COMMENT ON COLUMN history_photos.order_index IS 'Kolejność wyświetlania zdjęć (od 0)';
