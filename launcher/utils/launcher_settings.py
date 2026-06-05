"""Ustawienia launchera zapisywane w bazie konfiguracji."""

import os

from .engine_access import check_postgres_available


__all__ = ["get_launcher_setting", "set_launcher_setting"]


def get_launcher_setting(key, default=None):

    """Pobiera wartosc ustawienia z tabeli launcher_settings."""

    if not check_postgres_available():

        return default

    try:

        from ..db.postgres import get_launcher_conn

        conn = get_launcher_conn({

            'host': os.getenv('DB_HOST', 'localhost'),

            'port': int(os.getenv('DB_PORT', '5432')),

            'user': os.getenv('DB_USER', 'postgres'),

            'password': os.getenv('DB_PASSWORD', ''),

        })

        cursor = conn.cursor()

        cursor.execute("SELECT setting_value FROM launcher_settings WHERE setting_key = %s", (key,))

        result = cursor.fetchone()

        cursor.close()

        conn.close()

        return result[0] if result else default

    except Exception as e:

        print(f"Blad odczytu ustawienia {key}: {e}")

        return default


def set_launcher_setting(key, value):

    """Zapisuje wartosc ustawienia do tabeli launcher_settings (UPSERT)."""

    if not check_postgres_available():

        return False

    try:

        from ..db.postgres import get_launcher_conn

        conn = get_launcher_conn({

            'host': os.getenv('DB_HOST', 'localhost'),

            'port': int(os.getenv('DB_PORT', '5432')),

            'user': os.getenv('DB_USER', 'postgres'),

            'password': os.getenv('DB_PASSWORD', ''),

        })

        cursor = conn.cursor()

        cursor.execute("""

            INSERT INTO launcher_settings (setting_key, setting_value)

            VALUES (%s, %s)

            ON CONFLICT (setting_key)

            DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = CURRENT_TIMESTAMP

        """, (key, value))

        conn.commit()

        cursor.close()

        conn.close()

        return True

    except Exception as e:

        print(f"Blad zapisu ustawienia {key}: {e}")

        return False
