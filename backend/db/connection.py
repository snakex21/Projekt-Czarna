"""
Warstwa dostępu do bazy danych - PostgreSQL (asyncpg) + SQLite (aiosqlite).
Używa SQLAlchemy 2.0 asyncio dla obu silników.
"""

import os
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from ..config import ASYNC_DATABASE_URL, DB_ENGINE, DB_PATH, DATA_DIR

# === Silnik SQLAlchemy ===
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_size=5 if DB_ENGINE != "sqlite" else 1,
    max_overflow=10,
    connect_args={
        "check_same_thread": False
    } if DB_ENGINE == "sqlite" else {}
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Zwraca sesję bazy danych (do użycia jako FastAPI dependency)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context():
    """Context manager dla sesji bazy danych."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Inicjalizuje bazę danych przy starcie aplikacji."""
    if DB_ENGINE == "sqlite":
        # Dla SQLite - użyj aiosqlite bezpośrednio (SQLAlchemy engine.begin() ma problemy
        # z wieloma instrukcjami w jednym execute)
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute("PRAGMA busy_timeout=5000")

            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
            if os.path.exists(schema_path):
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                # Usun komentarze, podziel na instrukcje
                lines = [l for l in schema_sql.split('\n') if not l.strip().startswith('--')]
                clean_sql = '\n'.join(lines)
                for statement in clean_sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        try:
                            await db.execute(statement)
                        except Exception as e:
                            print(f"⚠️ Błąd SQL: {e}")
            await db.commit()

            if DB_ENGINE == "sqlite":
                try:
                    cols = await db.execute("PRAGMA table_info(demografia)")
                    col_names = [row[1] for row in await cols.fetchall()]
                    if "populacja_ogolem" not in col_names:
                        await db.execute("ALTER TABLE demografia ADD COLUMN populacja_ogolem INTEGER DEFAULT 0")
                        await db.commit()
                except Exception as e:
                    print(f"⚠️ Migracja demografia.populacja_ogolem: {e}")
    else:
        # PostgreSQL - sprawdź połączenie
        async with engine.begin() as conn:
            pass

    print("✅ Baza danych zainicjalizowana")


def get_db_connection():
    """Zwraca synchroniczne polaczenie: psycopg2 dla PostgreSQL, sqlite3 dla SQLite."""
    from ..config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_ENGINE, DB_PATH
    if DB_ENGINE == "sqlite":
        import sqlite3
        if not os.path.exists(DB_PATH):
            return None
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )
        return conn
    except Exception:
        return None


async def close_db():
    """Zamyka połączenie z bazą."""
    await engine.dispose()
    print("[CLOSE] Baza danych zamknieta")


async def execute_raw_query(query: str, params: dict = None) -> list:
    """Wykonuje surowe zapytanie SQL i zwraca wyniki jako listę dictów."""
    async with async_session_factory() as session:
        result = await session.execute(text(query), params or {})
        rows = result.fetchall()
        if rows:
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in rows]
        return []


async def execute_raw_single(query: str, params: dict = None) -> dict | None:
    """Wykonuje zapytanie i zwraca pojedynczy wynik."""
    async with async_session_factory() as session:
        result = await session.execute(text(query), params or {})
        row = result.fetchone()
        if row:
            columns = list(result.keys())
            return dict(zip(columns, row))
        return None
