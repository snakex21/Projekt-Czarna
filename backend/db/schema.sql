-- Schema dla SQLite (mapa_czarna_db)
-- Uruchamiane przez backend/database.py:init_db() gdy DB_ENGINE=sqlite

CREATE TABLE IF NOT EXISTS konfiguracja_systemu (
    klucz TEXT PRIMARY KEY,
    wartosc TEXT
);

CREATE TABLE IF NOT EXISTS obiekty_geograficzne (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa_lub_numer TEXT,
    kategoria TEXT DEFAULT 'default',
    geometria TEXT  -- GeoJSON jako TEXT
);

CREATE TABLE IF NOT EXISTS wlasciciele (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unikalny_klucz TEXT,
    nazwa_wlasciciela TEXT,
    numer_protokolu TEXT,
    numer_domu TEXT,
    genealogia TEXT,
    historia_wlasnosci TEXT,
    uwagi TEXT,
    wspolwlasnosc TEXT,
    powiazania_i_transakcje TEXT,
    interpretacja_i_wnioski TEXT,
    data_protokolu TEXT,
    miejsce_protokolu TEXT
);

CREATE TABLE IF NOT EXISTS dzialki_wlasciciele (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obiekt_id INTEGER REFERENCES obiekty_geograficzne(id),
    wlasciciel_id INTEGER REFERENCES wlasciciele(id),
    typ_posiadania TEXT
);

CREATE TABLE IF NOT EXISTS osoby_genealogia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    json_id TEXT,
    imie_nazwisko TEXT,
    plec TEXT,
    rok_urodzenia INTEGER,
    rok_smierci INTEGER,
    uwagi TEXT,
    numer_domu TEXT,
    id_protokolu INTEGER REFERENCES wlasciciele(id),
    id_ojca INTEGER,
    id_matki INTEGER
);

CREATE TABLE IF NOT EXISTS malzenstwa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    malzonek1_id INTEGER,
    malzonek2_id INTEGER,
    rok_slubu INTEGER,
    data_slubu TEXT
);

CREATE TABLE IF NOT EXISTS demografia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rok INTEGER,
    populacja_ogolem INTEGER DEFAULT 0,
    katolicy INTEGER DEFAULT 0,
    zydzi INTEGER DEFAULT 0,
    inni INTEGER DEFAULT 0,
    opis TEXT
);

-- === Indeksy dla poprawy wydajności zapytań ===

-- Wyszukiwanie właścicieli po unikalnym kluczu i numerze protokołu
CREATE INDEX IF NOT EXISTS idx_wlasciciele_klucz ON wlasciciele(unikalny_klucz);
CREATE INDEX IF NOT EXISTS idx_wlasciciele_numer ON wlasciciele(numer_protokolu);

-- Powiązania działek z właścicielami (częste JOIN i WHERE)
CREATE INDEX IF NOT EXISTS idx_dzialki_obiekt ON dzialki_wlasciciele(obiekt_id);
CREATE INDEX IF NOT EXISTS idx_dzialki_wlasciciel ON dzialki_wlasciciele(wlasciciel_id);
CREATE INDEX IF NOT EXISTS idx_dzialki_typ ON dzialki_wlasciciele(typ_posiadania);

-- Genealogia — wyszukiwanie po protokole, rodzicach, json_id
CREATE INDEX IF NOT EXISTS idx_osoby_protokol ON osoby_genealogia(id_protokolu);
CREATE INDEX IF NOT EXISTS idx_osoby_ojciec ON osoby_genealogia(id_ojca);
CREATE INDEX IF NOT EXISTS idx_osoby_matka ON osoby_genealogia(id_matki);
CREATE INDEX IF NOT EXISTS idx_osoby_json ON osoby_genealogia(json_id);

-- Małżeństwa — wyszukiwanie po małżonkach
CREATE INDEX IF NOT EXISTS idx_malzenstwa_m1 ON malzenstwa(malzonek1_id);
CREATE INDEX IF NOT EXISTS idx_malzenstwa_m2 ON malzenstwa(malzonek2_id);
