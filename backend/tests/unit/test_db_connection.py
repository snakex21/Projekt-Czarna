"""
Testy jednostkowe backend/db/connection.py
Po refaktorze: database.py -> db/connection.py z __init__.py re-exportem.

Skupiamy sie na get_db_connection (synchroniczne, sqlite) - jedyny kawalek
tego modulu, ktory mozna przetestowac bez odpalania event loop pytest-asyncio
(ten globalny engine koliduje z TestClient z innych testow - feature, nie bug).

Kontrakt modulu (typy, re-exporty, import) jest pilnowany przez:
- backend/tests/unit/test_backend_refactor_guards.py (architektoniczne)
- import w pierwszej linii kazdego testu (gwarantuje existence)
"""
import sqlite3

from backend import config as backend_config
from backend.db.connection import get_db_connection


def test_get_db_connection_returns_sqlite_conn_for_sqlite_engine(tmp_path, monkeypatch):
    """Dla DB_ENGINE=sqlite i istniejacego pliku zwraca sqlite3.Connection.

    Realna asercja: row_factory = sqlite3.Row, query przechodzi, tabela widoczna.
    """
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE x (id INTEGER)")
    conn.commit()
    conn.close()

    monkeypatch.setattr(backend_config, "DB_ENGINE", "sqlite")
    monkeypatch.setattr(backend_config, "DB_PATH", str(db_file))

    result = get_db_connection()
    try:
        assert result is not None
        assert isinstance(result, sqlite3.Connection)
        # row_factory = sqlite3.Row (kluczowe dla wiekszosci endpointow)
        assert result.row_factory is sqlite3.Row
        cur = result.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = [r[0] for r in cur.fetchall()]
        assert "x" in names
    finally:
        if result is not None:
            result.close()


def test_get_db_connection_returns_none_when_sqlite_file_missing(tmp_path, monkeypatch):
    """Dla sqlite bez pliku -> None (bez wyjatku, bez crasha).

    Wazny kontrakt: kod konsumujacy moze pisac 'conn = get_db_connection(); if conn:'
    zamiast try/except. To stabilizuje ~10 endpointow backendu.
    """
    missing = tmp_path / "ghost.db"
    monkeypatch.setattr(backend_config, "DB_ENGINE", "sqlite")
    monkeypatch.setattr(backend_config, "DB_PATH", str(missing))

    assert get_db_connection() is None


def test_get_db_connection_returns_none_for_postgres_when_unreachable(monkeypatch):
    """Dla postgresql z bledem polaczenia -> None (bez crasha).

    Zamykamy port 1 (zamkniety systemowo) - polaczenie nie moze sie udac
    w realnym czasie. Sprawdzamy czy get_db_connection NIE propaguje wyjatku.
    """
    monkeypatch.setattr(backend_config, "DB_ENGINE", "postgresql")
    monkeypatch.setattr(backend_config, "DB_HOST", "127.0.0.1")
    monkeypatch.setattr(backend_config, "DB_PORT", "1")  # zamkniety port
    monkeypatch.setattr(backend_config, "DB_USER", "nope")
    monkeypatch.setattr(backend_config, "DB_PASSWORD", "nope")
    monkeypatch.setattr(backend_config, "DB_NAME", "nope")

    assert get_db_connection() is None


def test_get_db_connection_handles_polish_chars_in_path(tmp_path, monkeypatch):
    """get_db_connection obsluguje sciezki z polskimi znakami (lokalizacje genealogiczne).

    Realny use case: baza dla 'Biala Podlaska' / 'Lomza' / 'Zoliborz'.
    Polskie znaki w sciezce to potencjalny wektor bugow (encoding mismatch na Windows).
    """
    # tmp_path jest bezpieczny od polskich znakow - budujemy wlasna sciezke
    polish_dir = tmp_path / "Bia\u0142a Podlaska"  # 'Biała Podlaska'
    polish_dir.mkdir()
    db_file = polish_dir / "genealogy.db"

    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE locations (id INTEGER, name TEXT)")
    conn.execute("INSERT INTO locations VALUES (1, 'Bia\u0142a Podlaska')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(backend_config, "DB_ENGINE", "sqlite")
    monkeypatch.setattr(backend_config, "DB_PATH", str(db_file))

    result = get_db_connection()
    try:
        assert result is not None, (
            f"get_db_connection zwrocil None dla sciezki z polskimi znakami: {db_file}"
        )
        cur = result.execute("SELECT name FROM locations WHERE id=1")
        row = cur.fetchone()
        assert row is not None
        # Row factory Row - nazwa musi przejsc encoding-czysto
        assert row[0] == "Bia\u0142a Podlaska"
    finally:
        if result is not None:
            result.close()


def test_get_db_connection_handles_spaces_in_path(tmp_path, monkeypatch):
    """get_db_connection obsluguje sciezki ze spacjami (np. 'Moja Lokalizacja').

    Realny use case: uzytkownik tworzy lokalizacje 'Moja Wies' / 'Stary Majatek'.
    Spacje w sciezce moga powodowac problemy z shell-quoting lub URL encoding.
    """
    spaced_dir = tmp_path / "Moj Majatek"  # ze spacja
    spaced_dir.mkdir()
    db_file = spaced_dir / "data.db"

    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    conn.close()

    monkeypatch.setattr(backend_config, "DB_ENGINE", "sqlite")
    monkeypatch.setattr(backend_config, "DB_PATH", str(db_file))

    result = get_db_connection()
    try:
        assert result is not None, (
            f"get_db_connection zwrocil None dla sciezki ze spacjami: {db_file}"
        )
        cur = result.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = [r[0] for r in cur.fetchall()]
        assert "t" in names
    finally:
        if result is not None:
            result.close()
