"""
launcher/db/postgres.py — Funkcje bazy danych PostgreSQL.
Obsługa rejestru miejscowości i schematów baz danych.
"""

import logging
from typing import Optional, Tuple, Any

import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from .schemas import LAUNCHER_DB_SCHEMA, LOCATION_DB_SCHEMA


logger = logging.getLogger(__name__)


def _get_pg_conn(config: dict, database: str = "postgres"):
    """Tworzy połączenie do PostgreSQL."""
    return psycopg2.connect(
        host=config['host'], port=config['port'],
        user=config['user'], password=config['password'],
        database=database
    )


def test_connection(config: dict) -> Tuple[bool, str]:
    """Testuje połączenie z PostgreSQL."""
    try:
        conn = _get_pg_conn(config)
        conn.close()
        return True, "Połączenie udane"
    except Exception as e:
        return False, f"Błąd połączenia: {e}"


def database_exists(config: dict, db_name: str) -> bool:
    """Sprawdza czy baza danych istnieje."""
    try:
        conn = _get_pg_conn(config)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return exists
    except Exception:
        return False


def list_databases(config: dict) -> list[str]:
    """Zwraca listę baz danych PostgreSQL dostępnych na serwerze."""
    try:
        conn = _get_pg_conn(config)
        cursor = conn.cursor()
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row[0] for row in rows]
    except Exception:
        return []


def create_database(config: dict, db_name: str) -> Tuple[bool, str]:
    """Tworzy nową bazę PostgreSQL."""
    try:
        conn = _get_pg_conn(config)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        cursor.execute(f'CREATE DATABASE "{db_name}"')
        cursor.close()
        conn.close()
        return True, f"Baza '{db_name}' utworzona"
    except psycopg2.errors.DuplicateDatabase:
        return True, f"Baza '{db_name}' już istnieje"
    except Exception as e:
        return False, f"Błąd: {e}"


def enable_postgis(config: dict, db_name: str) -> Tuple[bool, str]:
    """Włącza PostGIS w bazie."""
    try:
        conn = _get_pg_conn(config, db_name)
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='postgis')")
        if cursor.fetchone()[0]:
            cursor.close(); conn.close()
            return True, "PostGIS już włączony"
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        cursor.close(); conn.close()
        return True, "PostGIS włączony"
    except Exception as e:
        return False, f"Błąd PostGIS: {e}"


def has_postgis_extension(config: dict, db_name: str) -> bool:
    """Sprawdza czy w danej bazie jest włączone rozszerzenie PostGIS."""
    try:
        conn = _get_pg_conn(config, db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='postgis')")
        enabled = bool(cursor.fetchone()[0])
        cursor.close()
        conn.close()
        return enabled
    except Exception:
        return False


def execute_schema(config: dict, db_name: str, schema_sql: str) -> Tuple[bool, str]:
    """Wykonuje SQL schema w bazie."""
    try:
        conn = _get_pg_conn(config, db_name)
        cursor = conn.cursor()
        cursor.execute(schema_sql)
        conn.commit()
        cursor.close(); conn.close()
        return True, "Schema wykonana"
    except Exception as e:
        return False, f"Błąd: {e}"


def get_launcher_conn(config: dict):
    """Zwraca połączenie do mapa_launcher_db."""
    return _get_pg_conn(config, 'mapa_launcher_db')


def get_launcher_postgres_connection():
    """Bezparametrowy wrapper — pobiera config z get_postgres_config()."""
    return get_launcher_conn(get_postgres_config())


def init_postgres_locations_db(config: dict) -> bool:
    """Inicjalizuje bazę PostgreSQL mapa_launcher_db (idempotentna).

    Komunikat sukcesu idzie do ``logger.debug``, bo ta funkcja jest wołana
    przy każdym odczycie listy miejscowości (``postgres_get_all_locations``,
    ``postgres_get_active_location`` itd.) — przy domyślnym poziomie logów
    w GUI nie chcemy widzieć 15+ identycznych komunikatów.
    """
    db_exists = database_exists(config, 'mapa_launcher_db')
    created_now = False
    if not db_exists:
        ok, msg = create_database(config, 'mapa_launcher_db')
        if not ok:
            logger.error("init_postgres_locations_db: %s", msg)
            return False
        created_now = True

    enable_postgis(config, 'mapa_launcher_db')
    ok, msg = execute_schema(config, 'mapa_launcher_db', LAUNCHER_DB_SCHEMA)
    if not ok:
        logger.error("init_postgres_locations_db: %s", msg)
        return False

    # Migracja kolumn
    try:
        conn = get_launcher_conn(config)
        cursor = conn.cursor()
        for col_name, col_type in [
            ('gmina_katastralna', 'VARCHAR(100)'),
            ('miejscowosc_protokolu', 'VARCHAR(100)'),
            ('area_hectares', 'NUMERIC(10,2)'),
            ('area_km2', 'NUMERIC(10,4)'),
            ('boundary_coordinates', 'JSONB'),
            ('jewish_protocol_numbers', 'TEXT'),
            ('custom_icon', 'VARCHAR(255)'),
        ]:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='locations' AND column_name=%s
            """, (col_name,))
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE locations ADD COLUMN {col_name} {col_type}")
        conn.commit()
        cursor.close(); conn.close()
    except Exception as e:
        logger.warning("Migracja kolumn: %s", e)

    if created_now:
        logger.info("✅ mapa_launcher_db utworzona i zainicjalizowana")
    else:
        logger.debug("mapa_launcher_db OK (idempotent)")
    return True


def postgres_get_all_locations(config: dict) -> list:
    init_postgres_locations_db(config)
    conn = get_launcher_conn(config)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.id, l.name, l.full_name, l.powiat, l.region, l.active,
               l.homepage_template, l.year, l.century,
               l.homepage_description, l.history_paragraph1, l.history_paragraph2,
               l.history_paragraph3, l.postgres_db_name,
               l.gmina_katastralna, l.miejscowosc_protokolu,
               COALESCE(
                   (SELECT json_agg(json_build_object('filename', filename, 'caption', caption)
                    ORDER BY order_index) FROM history_photos WHERE location_id = l.id),
                   '[]'::json
               )::text as history_photos,
               l.jewish_protocol_numbers, l.custom_icon
        FROM locations l
        ORDER BY l.name
    """)
    locations = cursor.fetchall()
    cursor.close(); conn.close()
    return locations


def postgres_get_active_location(config: dict) -> Optional[tuple]:
    init_postgres_locations_db(config)
    conn = get_launcher_conn(config)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.id, l.name, l.full_name, l.powiat, l.region, l.active,
               l.homepage_template, l.year, l.century,
               l.homepage_description, l.history_paragraph1, l.history_paragraph2,
               l.history_paragraph3, l.postgres_db_name,
               l.gmina_katastralna, l.miejscowosc_protokolu,
               COALESCE(
                   (SELECT json_agg(json_build_object('filename', filename, 'caption', caption)
                    ORDER BY order_index) FROM history_photos WHERE location_id = l.id),
                   '[]'::json
               )::text as history_photos,
               l.jewish_protocol_numbers, l.custom_icon
        FROM locations l WHERE l.active = true
    """)
    location = cursor.fetchone()
    cursor.close(); conn.close()
    return location


def postgres_set_active_location(config: dict, location_id) -> None:
    conn = get_launcher_conn(config)
    cursor = conn.cursor()
    cursor.execute("UPDATE locations SET active = FALSE WHERE active = TRUE")
    cursor.execute("UPDATE locations SET active = TRUE WHERE id = %s", (location_id,))
    conn.commit()
    cursor.close(); conn.close()


def postgres_add_location(config: dict, name, full_name, **kwargs) -> int:
    """Dodaje miejscowość do bazy launcher PostgreSQL (czysta operacja SQL).
    
    Returns:
        int: ID nowej miejscowości
    Raises:
        ValueError: Jeśli miejscowość już istnieje
    """
    conn = get_launcher_conn(config)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO locations (name, full_name, powiat, region, active,
                                  homepage_template, year, century,
                                  homepage_description, history_paragraph1,
                                  history_paragraph2, history_paragraph3, postgres_db_name,
                                  gmina_katastralna, jewish_protocol_numbers, custom_icon)
            VALUES (%s, %s, %s, %s, false, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            name, full_name,
            kwargs.get('powiat', ''), kwargs.get('region', ''),
            kwargs.get('homepage_template', 'standardowy'),
            kwargs.get('year', '1882'), kwargs.get('century', 'XIX w.'),
            kwargs.get('homepage_description', ''),
            kwargs.get('history_paragraph1', ''), kwargs.get('history_paragraph2', ''),
            kwargs.get('history_paragraph3', ''), kwargs.get('postgres_db_name', ''),
            kwargs.get('gmina_katastralna', ''), kwargs.get('jewish_protocol_numbers', ''),
            kwargs.get('custom_icon', 'custom_icon.png')
        ))
        location_id = cursor.fetchone()[0]

        history_photos = kwargs.get('history_photos', [])
        if history_photos:
            for idx, photo in enumerate(history_photos):
                if isinstance(photo, dict):
                    cursor.execute("""
                        INSERT INTO history_photos (location_id, filename, caption, order_index)
                        VALUES (%s, %s, %s, %s)
                    """, (location_id, photo.get('filename', ''), photo.get('caption', ''), idx))

        conn.commit()
        return location_id
    except psycopg2.IntegrityError:
        conn.rollback()
        raise ValueError(f"Miejscowość '{name}' już istnieje")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def postgres_update_location(config: dict, location_id, **kwargs) -> None:
    """Aktualizuje dane miejscowości w PostgreSQL (czysta operacja SQL).
    
    Raises:
        ValueError: Jeśli miejscowość nie istnieje
    """
    conn = get_launcher_conn(config)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM locations WHERE id = %s", (location_id,))
        if not cursor.fetchone():
            raise ValueError("Miejscowość nie istnieje")

        cursor.execute("""
            UPDATE locations SET
                name = %s, full_name = %s, powiat = %s, region = %s,
                year = %s, century = %s,
                homepage_description = %s, history_paragraph1 = %s,
                history_paragraph2 = %s, history_paragraph3 = %s,
                postgres_db_name = %s, homepage_template = %s,
                gmina_katastralna = %s,
                jewish_protocol_numbers = %s,
                custom_icon = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            kwargs.get('name', ''),
            kwargs.get('full_name', ''),
            kwargs.get('powiat', ''),
            kwargs.get('region', ''),
            kwargs.get('year', '1882'),
            kwargs.get('century', 'XIX w.'),
            kwargs.get('homepage_description', ''),
            kwargs.get('history_paragraph1', ''),
            kwargs.get('history_paragraph2', ''),
            kwargs.get('history_paragraph3', ''),
            kwargs.get('postgres_db_name', ''),
            kwargs.get('homepage_template', 'standardowy'),
            kwargs.get('gmina_katastralna', ''),
            kwargs.get('jewish_protocol_numbers', ''),
            kwargs.get('custom_icon', 'custom_icon.png'),
            location_id
        ))

        cursor.execute("DELETE FROM history_photos WHERE location_id = %s", (location_id,))
        history_photos = kwargs.get('history_photos', [])
        if history_photos:
            for idx, photo in enumerate(history_photos):
                if isinstance(photo, dict):
                    cursor.execute("""
                        INSERT INTO history_photos (location_id, filename, caption, order_index)
                        VALUES (%s, %s, %s, %s)
                    """, (location_id, photo.get('filename', ''), photo.get('caption', ''), idx))

        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        raise ValueError(f"Miejscowość '{kwargs.get('name', '')}' już istnieje")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def postgres_delete_location(config: dict, location_id) -> None:
    """Usuwa miejscowość z bazy launcher PostgreSQL (czysta operacja SQL).
    
    Raises:
        ValueError: Jeśli miejscowość nie istnieje lub jest aktywna
    """
    conn = get_launcher_conn(config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT name, active, postgres_db_name FROM locations WHERE id = %s",
            (location_id,)
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError("Miejscowość nie istnieje")

        name, active, postgres_db_name = result
        if active:
            raise ValueError("Nie można usunąć aktywnej miejscowości")

        cursor.execute("DELETE FROM history_photos WHERE location_id = %s", (location_id,))
        cursor.execute("DELETE FROM locations WHERE id = %s", (location_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


# === Konfiguracja PostgreSQL (z .postgres.env) ===
import os as _os
from ..config.paths import POSTGRES_CONFIG_FILE as _PCF

def get_postgres_config() -> dict:
    config = {'host': 'localhost', 'port': 5432, 'user': 'postgres', 'password': ''}
    if _PCF.exists():
        try:
            from dotenv import dotenv_values
            env = dotenv_values(str(_PCF))
            config['host'] = env.get('LAUNCHER_DB_HOST', config['host'])
            config['port'] = int(env.get('LAUNCHER_DB_PORT', config['port']))
            config['user'] = env.get('LAUNCHER_DB_USER', config['user'])
            config['password'] = env.get('LAUNCHER_DB_PASSWORD', config['password'])
        except: pass
    return config

def change_pg_password(host: str, port: int, user: str,
                       old_password: str, new_password: str) -> tuple[bool, str]:
    """Zmienia hasło użytkownika PostgreSQL.

    1. Weryfikuje stare hasło (łączy się z PG do maintenance DB ``postgres``).
    2. Wykonuje ``ALTER USER ... WITH PASSWORD '...'``.
    3. Zwraca (ok, msg). Błędy rozróżniane w ``msg`` prefiksem:
       ``old_password_invalid``, ``permission_denied``,
       ``connection_failed``, ``alter_failed``.

    UWAGA: po zmianie hasła caller musi zaktualizować ``.env`` i
    ``.postgres.env`` (użyj :func:`save_pg_config_to_env_files`) — w innym
    wypadku backend FastAPI wciąż będzie się łączył starym hasłem.
    """
    import psycopg2 as _pg
    if not new_password or not new_password.strip():
        return False, "Nowe hasło nie może być puste"
    if new_password == old_password:
        return False, "Nowe hasło musi być różne od starego"

    # 1. Weryfikacja starego hasła.
    # UWAGA: serwer ma ``lc_messages='Polish_Poland.1250'`` — psycopg2 rzuca
    # ``UnicodeDecodeError`` zanim zdąży zbudować obiekt wyjątku z pgcode.
    # Łapiemy to osobno i heurystycznie rozpoznajemy "invalid password"
    # po bajtach ``0xb3`` (= 'ł' w CP1250) i frazie "hasłem nie powiod".
    try:
        test_conn = _pg.connect(
            host=host, port=int(port), user=user, password=old_password,
            dbname="postgres", connect_timeout=5,
        )
        test_conn.close()
    except _pg.OperationalError as e:
        sqlstate = getattr(e, "pgcode", None) or ""
        if sqlstate in ("28P01", "28000"):
            return False, "old_password_invalid: stare hasło jest nieprawidłowe"
        return False, f"connection_failed: {e}"
    except UnicodeDecodeError as e:
        # bytes zawierają polski komunikat CP1250 z serwera
        raw = e.args[1] if len(e.args) > 1 else b""
        if isinstance(raw, (bytes, bytearray)) and (
            b"has\xb3em nie powiod" in raw or b"authentication failed" in raw
        ):
            return False, "old_password_invalid: stare hasło jest nieprawidłowe"
        return False, f"connection_failed (encoding): {e}"
    except Exception as e:
        return False, f"connection_failed: {e}"

    # 2. ALTER USER (wymaga uprawnień superuser lub CREATEROLE)
    try:
        admin_conn = _pg.connect(
            host=host, port=int(port), user=user, password=old_password,
            dbname="postgres", connect_timeout=5,
        )
        admin_conn.autocommit = True
        cur = admin_conn.cursor()
        # Literalne wstawienie hasła — escapujemy tylko pojedyncze cudzysłowy.
        safe_pw = new_password.replace("'", "''")
        cur.execute(f"ALTER USER {user} WITH PASSWORD '{safe_pw}'")
        cur.close()
        admin_conn.close()
    except _pg.OperationalError as e:
        sqlstate = getattr(e, "pgcode", None) or ""
        if "permission" in sqlstate.lower() or sqlstate in ("42501",):
            return False, "permission_denied: brak uprawnień do zmiany hasła"
        return False, f"alter_failed: {e}"
    except UnicodeDecodeError as e:
        return False, f"alter_failed (encoding): {e}"
    except Exception as e:
        return False, f"alter_failed: {e}"

    logger.info("Hasło PG zmienione dla użytkownika %s@%s:%s", user, host, port)
    return True, "Hasło zmienione pomyślnie"


def save_postgres_config(host, port, user, password):
    try:
        with open(str(_PCF), 'w', encoding='utf-8') as f:
            f.write(f"LAUNCHER_DB_HOST={host}\nLAUNCHER_DB_PORT={port}\n")
            f.write(f"LAUNCHER_DB_USER={user}\nLAUNCHER_DB_PASSWORD={password}\n")
        return True
    except Exception as e:
        logger.error("Zapis konfiguracji PG nie powiódł się: %s", e)
        return False


def save_pg_config_to_env_files(host: str, port: int, user: str,
                                password: str, db_name: str) -> tuple[bool, str]:
    """Zapisuje konfigurację PG do ``backend/.env`` (klucze ``DB_*``) i
    ``backend/.postgres.env`` (klucze ``LAUNCHER_DB_*``).

    Oba pliki muszą być zsynchronizowane — backend FastAPI czyta z ``.env``
    (DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME), a launcher DB helpers
    czytają z ``.postgres.env`` (LAUNCHER_DB_*). Bez tej synchronizacji
    ``check_postgres_available()`` widzi puste hasło i rzuca ``RuntimeError``.

    Returns:
        (ok, msg) — ``ok=True`` jeśli oba pliki zaktualizowane, inaczej
        ``ok=False`` z komunikatem błędu.
    """
    from ..config.paths import BACKEND_DIR
    from ..services.env_config_service import update_env_content

    try:
        # 1. backend/.env (DB_*)
        backend_env = BACKEND_DIR / ".env"
        if backend_env.exists():
            content = backend_env.read_text(encoding="utf-8")
            updates = {
                "DB_HOST": str(host).strip(),
                "DB_PORT": str(port).strip(),
                "DB_USER": str(user).strip(),
                "DB_PASSWORD": str(password),
                "DB_NAME": str(db_name).strip(),
            }
            content = update_env_content(content, updates)
            backend_env.write_text(content, encoding="utf-8")
        else:
            return False, f"Brak pliku {backend_env}"

        # 2. backend/.postgres.env (LAUNCHER_DB_*)
        ok = save_postgres_config(host, port, user, password)
        if not ok:
            return False, "Zapis .postgres.env nie powiódł się"

        # 3. Odśwież os.environ (bo check_postgres_available() czyta z env)
        import os
        os.environ["DB_HOST"] = str(host).strip()
        os.environ["DB_PORT"] = str(port).strip()
        os.environ["DB_USER"] = str(user).strip()
        os.environ["DB_PASSWORD"] = str(password)
        os.environ["DB_NAME"] = str(db_name).strip()

        logger.info(
            "Konfiguracja PG zapisana: %s@%s:%s/%s",
            user, host, port, db_name,
        )
        return True, "Zapisano do .env i .postgres.env"
    except Exception as e:
        logger.error("save_pg_config_to_env_files: %s", e)
        return False, str(e)
