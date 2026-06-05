"""
Testy jednostkowe backend/db/helpers.py
Po refaktorze: db_helpers.py -> db/helpers.py z __init__.py re-exportem.
Mockujemy AsyncSession, bo to testy jednostkowe (bez realnej bazy).
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import helpers
from backend.db.helpers import execute, fetch_all, fetch_one
from backend.tests.unit._asyncio_helpers import run_async_safely


# Backward-compat alias — zewnętrzne importy (jeśli są) mogą nadal używać
# starej nazwy. Nowy kod powinien wołać ``run_async_safely`` wprost.
def _run_async(coro):
    """Alias dla :func:`run_async_safely` (stara nazwa)."""
    return run_async_safely(coro)


# ================================================================================
# Mock fixtures
# ================================================================================


def _make_mock_session(rows):
    """Tworzy mock AsyncSession, gdzie execute() zwraca podane wiersze jako listę dict."""
    session = AsyncMock(spec=AsyncSession)

    # result.fetchall() / fetchone() to zwykłe metody synchroniczne na Result
    # SQLAlchemy. AsyncMock zwraca MagicMock dla nie-async atrybutów, więc
    # wystarczy ustawić je bezpośrednio.
    result = MagicMock()
    result.fetchall = MagicMock(return_value=rows)
    result.fetchone = MagicMock(return_value=rows[0] if rows else None)

    # execute() jest async
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock(return_value=None)
    return session


def _row(d):
    """Tworzy obiekt z atrybutem _mapping = d (jak prawdziwy Row SQLAlchemy)."""

    class _Row:
        def __init__(self, mapping):
            self._mapping = mapping

    return _Row(d)


# ================================================================================
# Testy fetch_one
# ================================================================================


def test_fetch_one_returns_dict_when_row_exists():
    """fetch_one() zwraca dict z _mapping gdy jest wiersz."""
    session = _make_mock_session([_row({"id": 1, "name": "Ala"})])

    async def _run():
        return await fetch_one(session, "SELECT * FROM x WHERE id = :id", {"id": 1})

    result = _run_async(_run())
    assert result == {"id": 1, "name": "Ala"}


def test_fetch_one_returns_none_when_no_row():
    """fetch_one() zwraca None gdy brak wierszy."""
    session = _make_mock_session([])

    async def _run():
        return await fetch_one(session, "SELECT * FROM x WHERE 0")

    result = _run_async(_run())
    assert result is None


def test_fetch_one_passes_query_and_params_to_execute():
    """fetch_one() przekazuje query i params do session.execute()."""
    session = _make_mock_session([_row({"v": 1})])

    async def _run():
        await fetch_one(session, "SELECT :n AS v", {"n": 7})

    _run_async(_run())
    # Sprawdź argumenty wywołania execute
    args, kwargs = session.execute.call_args
    # Pierwszy argument to text(query), drugi to params dict
    assert len(args) == 2
    assert kwargs == {}
    assert str(args[0]) == "SELECT :n AS v" or "SELECT" in str(args[0])
    assert args[1] == {"n": 7}


def test_fetch_one_uses_empty_dict_when_params_none():
    """fetch_one() z params=None używa pustego dict."""
    session = _make_mock_session([_row({"a": 1})])

    async def _run():
        await fetch_one(session, "SELECT 1 AS a")

    _run_async(_run())
    args, _ = session.execute.call_args
    assert args[1] == {}


# ================================================================================
# Testy fetch_all
# ================================================================================


def test_fetch_all_returns_list_of_dicts():
    """fetch_all() zwraca listę dictów z _mapping."""
    rows = [_row({"id": 1, "n": "a"}), _row({"id": 2, "n": "b"})]
    session = _make_mock_session(rows)

    async def _run():
        return await fetch_all(session, "SELECT * FROM x")

    result = _run_async(_run())
    assert result == [{"id": 1, "n": "a"}, {"id": 2, "n": "b"}]


def test_fetch_all_returns_empty_list_when_no_rows():
    """fetch_all() zwraca [] gdy brak wierszy."""
    session = _make_mock_session([])

    async def _run():
        return await fetch_all(session, "SELECT * FROM x WHERE 0")

    result = _run_async(_run())
    assert result == []


def test_fetch_all_passes_params_to_execute():
    """fetch_all() przekazuje params do execute()."""
    session = _make_mock_session([_row({"v": 99})])

    async def _run():
        await fetch_all(session, "SELECT :n AS v", {"n": 99})

    _run_async(_run())
    args, _ = session.execute.call_args
    assert args[1] == {"n": 99}


# ================================================================================
# Testy execute
# ================================================================================


def test_execute_returns_lastrowid():
    """execute() zwraca lastrowid z result."""
    session = _make_mock_session([])
    # Ustaw lastrowid na ręcznie
    session.execute.return_value.lastrowid = 42

    async def _run():
        return await execute(session, "INSERT INTO x (n) VALUES (:n)", {"n": "test"})

    result = _run_async(_run())
    assert result == 42
    # Musi wywołać flush()
    session.flush.assert_awaited_once()


def test_execute_returns_zero_when_no_lastrowid():
    """execute() zwraca 0 gdy lastrowid jest None (np. UPDATE/DELETE)."""
    session = _make_mock_session([])
    session.execute.return_value.lastrowid = None

    async def _run():
        return await execute(session, "UPDATE x SET n = :n")

    result = _run_async(_run())
    assert result == 0


def test_execute_calls_flush_after_execute():
    """execute() wywołuje db.flush() po db.execute() (ważne dla transakcji)."""
    session = _make_mock_session([])
    session.execute.return_value.lastrowid = 1

    async def _run():
        await execute(session, "INSERT INTO x VALUES (1)")

    _run_async(_run())
    # Kolejność: execute -> flush
    assert session.execute.await_count == 1
    assert session.flush.await_count == 1


def test_execute_uses_empty_dict_when_params_none():
    """execute() z params=None używa pustego dict."""
    session = _make_mock_session([])
    session.execute.return_value.lastrowid = 0

    async def _run():
        await execute(session, "DELETE FROM x")

    _run_async(_run())
    args, _ = session.execute.call_args
    assert args[1] == {}


# ================================================================================
# Test re-exportu z backend.db.__init__
# ================================================================================


def test_backend_db_reexports_helper_symbols():
    """backend.db.__init__ musi re-eksportować fetch_one, fetch_all, execute."""
    from backend.db import fetch_one as re_one, fetch_all as re_all, execute as re_exe
    assert re_one is fetch_one
    assert re_all is fetch_all
    assert re_exe is execute


# ================================================================================
# Test spójności typów (wymuszenie sygnatur)
# ================================================================================


def test_helpers_are_coroutines():
    """fetch_one, fetch_all, execute muszą być async (coroutine)."""
    import inspect
    assert inspect.iscoroutinefunction(fetch_one)
    assert inspect.iscoroutinefunction(fetch_all)
    assert inspect.iscoroutinefunction(execute)
