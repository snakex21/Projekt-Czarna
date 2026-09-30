"""Małe, fikcyjne dane testowe; nigdy nie kopiują bazy użytkownika."""
import json
import sqlite3
from pathlib import Path


def create_sample_database(path):
    path = Path(path)
    if path.exists():
        raise ValueError("Baza testowa musi być nowym plikiem")
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = Path(__file__).resolve().parents[1] / "db/schema.sql"
    with sqlite3.connect(path) as db:
        db.executescript(schema.read_text(encoding="utf-8"))
        db.executemany(
            "INSERT INTO obiekty_geograficzne (id, nazwa_lub_numer, kategoria, geometria) VALUES (?, ?, ?, ?)",
            [(1, "TEST-1", "rolna", json.dumps({"type": "Point", "coordinates": [20, 50]})),
             (2, "TEST-2", "budowlana", json.dumps({"type": "Point", "coordinates": [20.01, 50.01]}))],
        )
        db.execute("INSERT INTO wlasciciele (id, unikalny_klucz, nazwa_wlasciciela, numer_protokolu, numer_domu) VALUES (1, 'SYNTHETIC_OWNER', 'Jan Testowy', '1', '1')")
        db.execute("INSERT INTO dzialki_wlasciciele (obiekt_id, wlasciciel_id, typ_posiadania) VALUES (2, 1, 'protokol')")
        db.executemany(
            "INSERT INTO osoby_genealogia (id, json_id, imie_nazwisko, plec, rok_urodzenia, rok_smierci, numer_domu, id_protokolu) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(1, "fixture-1", "Jan Kubicki", "M", 1880, 1940, "1", 1),
             (2, "fixture-2", "Anna Testowa", "F", 1885, 1950, "1", 1)],
        )
        db.execute("INSERT INTO malzenstwa (malzonek1_id, malzonek2_id, rok_slubu) VALUES (1, 2, 1905)")
    return path


def create_sample_location(root, name="Czarna"):
    from PIL import Image
    location = Path(root) / name
    location.mkdir(parents=True)
    (location / ".env").write_text("ACTIVE_LOCATION=" + name + "\n", encoding="utf-8")
    (location / "genealogia.json").write_text(json.dumps({"persons": [{"id": "fixture-1", "name": "Jan Kubicki"}]}), encoding="utf-8")
    Image.new("RGB", (32, 32), "#d7cba8").save(location / "mapa.jpg")
    Image.new("RGB", (16, 16), "#38534a").save(location / "favicon.png")
    return location


def assert_port_available(host, port):
    """Odrzuca zajęty port zanim testy uruchomią proces lub wyślą HTTP."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((host, port))
