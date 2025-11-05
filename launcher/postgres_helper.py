"""
Moduł pomocniczy do zarządzania bazami PostgreSQL
Używany przez kreator bazy danych i launcher
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os


class PostgresHelper:
    """Klasa pomocnicza do operacji na PostgreSQL"""

    def __init__(self, host='localhost', port=5432, user='postgres', password=''):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    def test_connection(self):
        """
        Sprawdza czy można połączyć się z PostgreSQL.
        Zwraca (success: bool, message: str)
        """
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database='postgres'  # Domyślna baza systemowa
            )
            conn.close()
            return True, "Połączenie udane"
        except psycopg2.OperationalError as e:
            return False, f"Błąd połączenia: {str(e)}"
        except Exception as e:
            return False, f"Nieznany błąd: {str(e)}"

    def database_exists(self, db_name):
        """Sprawdza czy baza danych istnieje"""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database='postgres'
            )
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (db_name,)
            )
            exists = cursor.fetchone() is not None
            cursor.close()
            conn.close()
            return exists
        except Exception as e:
            print(f"Błąd sprawdzania bazy: {e}")
            return False

    def create_database(self, db_name):
        """
        Tworzy nową bazę danych.
        Zwraca (success: bool, message: str)
        """
        try:
            # Połącz się z bazą systemową
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Utwórz bazę
            cursor.execute(f'CREATE DATABASE "{db_name}"')

            cursor.close()
            conn.close()
            return True, f"Baza '{db_name}' utworzona"
        except psycopg2.errors.DuplicateDatabase:
            return True, f"Baza '{db_name}' już istnieje"
        except Exception as e:
            return False, f"Błąd tworzenia bazy: {str(e)}"

    def has_postgis(self, db_name):
        """Sprawdza czy baza ma włączony PostGIS"""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=db_name
            )
            cursor = conn.cursor()
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')"
            )
            has_it = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return has_it
        except Exception as e:
            print(f"Błąd sprawdzania PostGIS: {e}")
            return False

    def enable_postgis(self, db_name):
        """
        Włącza rozszerzenie PostGIS w bazie.
        Zwraca (success: bool, message: str)
        """
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=db_name
            )
            cursor = conn.cursor()
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            conn.commit()
            cursor.close()
            conn.close()
            return True, "PostGIS włączony"
        except Exception as e:
            return False, f"Błąd włączania PostGIS: {str(e)}"

    def execute_sql_file(self, db_name, sql_file_path):
        """
        Wykonuje plik SQL w danej bazie.
        Zwraca (success: bool, message: str)
        """
        try:
            if not os.path.exists(sql_file_path):
                return False, f"Plik nie istnieje: {sql_file_path}"

            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=db_name
            )
            cursor = conn.cursor()
            cursor.execute(sql_content)
            conn.commit()
            cursor.close()
            conn.close()
            return True, "SQL wykonany pomyślnie"
        except Exception as e:
            return False, f"Błąd wykonywania SQL: {str(e)}"

    def get_table_count(self, db_name):
        """Zwraca liczbę tabel w bazie (bez tabel systemowych)"""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=db_name
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """)
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return count
        except Exception:
            return 0

    def list_databases(self):
        """Zwraca listę wszystkich baz (bez systemowych)"""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database='postgres'
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT datname FROM pg_database
                WHERE datistemplate = false
                AND datname NOT IN ('postgres', 'template0', 'template1')
                ORDER BY datname
            """)
            databases = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return databases
        except Exception as e:
            print(f"Błąd listowania baz: {e}")
            return []

    def drop_database(self, db_name):
        """
        USUWA bazę danych! UWAGA: Nieodwracalne!
        Zwraca (success: bool, message: str)
        """
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Rozłącz wszystkie połączenia do bazy
            cursor.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                AND pid <> pg_backend_pid()
            """)

            # Usuń bazę
            cursor.execute(f'DROP DATABASE IF EXISTS "{db_name}"')

            cursor.close()
            conn.close()
            return True, f"Baza '{db_name}' usunięta"
        except Exception as e:
            return False, f"Błąd usuwania bazy: {str(e)}"

    def get_connection(self, db_name):
        """Zwraca połączenie do konkretnej bazy"""
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=db_name
        )


# Funkcje pomocnicze (bez klasy)

def get_default_postgres_config():
    """Zwraca domyślną konfigurację PostgreSQL"""
    return {
        'host': 'localhost',
        'port': 5432,
        'user': 'postgres',
        'password': ''
    }


def save_postgres_config(config, env_file_path):
    """Zapisuje konfigurację PostgreSQL do pliku .env"""
    try:
        # Wczytaj istniejący .env jeśli istnieje
        existing_lines = []
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r', encoding='utf-8') as f:
                existing_lines = f.readlines()

        # Usuń stare wpisy PostgreSQL
        filtered_lines = [
            line for line in existing_lines
            if not any(key in line for key in ['PG_HOST=', 'PG_PORT=', 'PG_USER=', 'PG_PASSWORD='])
        ]

        # Dodaj nowe
        filtered_lines.append(f"\n# PostgreSQL Configuration\n")
        filtered_lines.append(f"PG_HOST={config['host']}\n")
        filtered_lines.append(f"PG_PORT={config['port']}\n")
        filtered_lines.append(f"PG_USER={config['user']}\n")
        filtered_lines.append(f"PG_PASSWORD={config['password']}\n")

        # Zapisz
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.writelines(filtered_lines)

        return True
    except Exception as e:
        print(f"Błąd zapisywania konfiguracji: {e}")
        return False


def load_postgres_config(env_file_path):
    """Wczytuje konfigurację PostgreSQL z pliku .env"""
    config = get_default_postgres_config()

    if not os.path.exists(env_file_path):
        return config

    try:
        with open(env_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('PG_HOST='):
                    config['host'] = line.split('=', 1)[1]
                elif line.startswith('PG_PORT='):
                    config['port'] = int(line.split('=', 1)[1])
                elif line.startswith('PG_USER='):
                    config['user'] = line.split('=', 1)[1]
                elif line.startswith('PG_PASSWORD='):
                    config['password'] = line.split('=', 1)[1]
    except Exception as e:
        print(f"Błąd wczytywania konfiguracji: {e}")

    return config
