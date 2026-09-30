"""Regresje izolacji syntetycznych danych testowych."""
import sqlite3
import pytest
from backend.tests.sample_data import create_sample_database, create_sample_location


def test_sample_database_has_real_relational_data(tmp_path):
    path = create_sample_database(tmp_path / "sample.db")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM obiekty_geograficzne").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM osoby_genealogia WHERE imie_nazwisko LIKE '%Kubicki%'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM dzialki_wlasciciele d JOIN wlasciciele w ON w.id=d.wlasciciel_id JOIN obiekty_geograficzne o ON o.id=d.obiekt_id").fetchone()[0] == 1
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_sample_database_never_overwrites_existing_file(tmp_path):
    path = tmp_path / "existing.db"
    path.write_bytes(b"untouched")
    with pytest.raises(ValueError):
        create_sample_database(path)
    assert path.read_bytes() == b"untouched"


def test_sample_location_contains_generated_browser_assets(tmp_path):
    from PIL import Image
    location = create_sample_location(tmp_path)
    assert (location / ".env").read_text() == "ACTIVE_LOCATION=Czarna\n"
    for name in ("mapa.jpg", "favicon.png"):
        with Image.open(location / name) as image:
            image.verify()


def test_server_preflight_rejects_an_existing_listener():
    import socket
    from backend.tests.sample_data import assert_port_available
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(OSError):
            assert_port_available("127.0.0.1", port)
    assert_port_available("127.0.0.1", port)
