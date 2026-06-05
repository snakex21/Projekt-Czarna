"""
launcher/db/engine.py — Abstrakcja silnika bazy danych.
Rozpoznaje aktywny silnik (PostgreSQL / SQLite), udostępnia wspólny interfejs
i informuje o możliwościach danego silnika.
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from ..config.paths import BASE_DIR, BACKEND_DIR, LOCATIONS_DB_PATH, LOCATIONS_DATA_DIR


class DatabaseEngine(ABC):
    """Abstrakcyjna klasa silnika bazy danych."""

    # Metadane silnika
    name: str = "unknown"  # "postgresql", "sqlite"
    label: str = "Nieznany"  # "PostgreSQL", "SQLite"
    description: str = ""

    # Możliwości silnika
    supports_postgis: bool = False  # geometria przestrzenna
    supports_jsonb: bool = False    # zapytania JSONB
    supports_fulltext: bool = False # wyszukiwanie pełnotekstowe
    requires_server: bool = False   # wymaga działającego serwera DB

    # Które edytory są dostępne dla tego silnika
    @property
    def available_editors(self) -> list[str]:
        """Lista kluczy edytorów dostępnych dla tego silnika.
        Wszystkie edytory działają na plikach JSON — są dostępne niezależnie od silnika."""
        return ["owner_editor", "parcel_editor", "genealogy_editor"]

    @abstractmethod
    def get_all_locations(self) -> list:
        """Zwraca listę wszystkich miejscowości."""
        ...

    @abstractmethod
    def get_active_location(self) -> Optional[tuple]:
        """Zwraca aktywną miejscowość lub None."""
        ...

    @abstractmethod
    def set_active_location(self, location_id) -> None:
        """Ustawia podaną miejscowość jako aktywną."""
        ...

    @abstractmethod
    def add_location(self, name: str, full_name: str, **kwargs) -> int:
        """Dodaje nową miejscowość. Zwraca jej ID."""
        ...

    @abstractmethod
    def update_location(self, location_id, **kwargs) -> None:
        """Aktualizuje dane miejscowości."""
        ...

    @abstractmethod
    def delete_location(self, location_id) -> None:
        """Usuwa miejscowość."""
        ...

    @abstractmethod
    def init_database(self) -> None:
        """Inicjalizuje struktury bazy danych (tabele, indeksy)."""
        ...

    def check_connection(self) -> tuple[bool, str]:
        """Sprawdza czy połączenie z bazą jest możliwe."""
        return True, "OK"

    def get_location_db_name(self, location_name: str) -> str:
        """Zwraca nazwę bazy danych dla miejscowości."""
        return f"mapa_{location_name.lower()}_db"


class SQLiteEngine(DatabaseEngine):
    """Silnik SQLite — lokalna baza plikowa."""

    name = "sqlite"
    label = "SQLite"
    description = "Lokalna baza plikowa — nie wymaga serwera. Bez PostGIS."
    supports_postgis = False
    supports_jsonb = False
    supports_fulltext = False
    requires_server = False

    def __init__(self):
        self._db_path = LOCATIONS_DB_PATH

    def check_connection(self) -> tuple[bool, str]:
        if self._db_path.exists():
            return True, f"Baza istnieje: {self._db_path}"
        return True, "Baza zostanie utworzona automatycznie"

    def get_all_locations(self) -> list:
        from .sqlite import sqlite_get_all_locations
        return sqlite_get_all_locations()

    def get_active_location(self) -> Optional[tuple]:
        from .sqlite import sqlite_get_active_location
        return sqlite_get_active_location()

    def set_active_location(self, location_id) -> None:
        from .sqlite import sqlite_set_active_location
        sqlite_set_active_location(location_id)

    def add_location(self, name: str, full_name: str, **kwargs) -> int:
        from .sqlite import sqlite_add_location
        return sqlite_add_location(name, full_name, **kwargs)

    def update_location(self, location_id, **kwargs) -> None:
        from .sqlite import sqlite_update_location
        sqlite_update_location(location_id, **kwargs)

    def delete_location(self, location_id) -> None:
        from .sqlite import sqlite_delete_location
        sqlite_delete_location(location_id)

    def init_database(self) -> None:
        from .sqlite import sqlite_init_locations_db
        sqlite_init_locations_db()


class PostgreSQLEngine(DatabaseEngine):
    """Silnik PostgreSQL — pełna funkcjonalność z PostGIS."""

    name = "postgresql"
    label = "PostgreSQL"
    description = "Serwer bazy danych z PostGIS — pełna funkcjonalność przestrzenna."
    supports_postgis = True
    supports_jsonb = True
    supports_fulltext = True
    requires_server = True

    def __init__(self):
        self._config = None

    @property
    def config(self) -> dict:
        if self._config is None:
            self._config = self._read_config()
        return self._config

    def _read_config(self) -> dict:
        """Odczytuje konfigurację PostgreSQL z env, .env i .postgres.env."""
        config = {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': ''
        }
        from ..config.paths import BACKEND_DIR, POSTGRES_CONFIG_FILE

        # 1. backend/.env (DB_*) -- po instalatorze GUI to główne źródło
        # konfiguracji backendu i dobry fallback, gdy .postgres.env jest
        # brakujące lub stare.
        env_path = BACKEND_DIR / ".env"
        if env_path.exists():
            try:
                from dotenv import dotenv_values
                env = dotenv_values(str(env_path))
                config['host'] = env.get('DB_HOST') or config['host']
                config['port'] = int(env.get('DB_PORT') or config['port'])
                config['user'] = env.get('DB_USER') or config['user']
                config['password'] = env.get('DB_PASSWORD') or config['password']
            except Exception:
                pass

        # 2. backend/.postgres.env (LAUNCHER_DB_*) -- override dla launchera,
        # ale tylko niepuste wartości, żeby puste hasło nie skasowało fallbacku.
        if POSTGRES_CONFIG_FILE.exists():
            try:
                from dotenv import dotenv_values
                env = dotenv_values(str(POSTGRES_CONFIG_FILE))
                config['host'] = env.get('LAUNCHER_DB_HOST') or config['host']
                config['port'] = int(env.get('LAUNCHER_DB_PORT') or config['port'])
                config['user'] = env.get('LAUNCHER_DB_USER') or config['user']
                config['password'] = env.get('LAUNCHER_DB_PASSWORD') or config['password']
            except Exception:
                pass

        # 3. Zmienne środowiskowe procesu mają najwyższy priorytet.
        config['host'] = os.getenv('DB_HOST') or config['host']
        config['port'] = int(os.getenv('DB_PORT') or config['port'])
        config['user'] = os.getenv('DB_USER') or config['user']
        config['password'] = os.getenv('DB_PASSWORD') or config['password']
        return config

    def check_connection(self) -> tuple[bool, str]:
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database='postgres',
                connect_timeout=5
            )
            conn.close()
            return True, "Połączenie udane"
        except Exception as e:
            return False, f"Błąd połączenia: {e}"

    def get_all_locations(self) -> list:
        from .postgres import postgres_get_all_locations
        return postgres_get_all_locations(self.config)

    def get_active_location(self) -> Optional[tuple]:
        from .postgres import postgres_get_active_location
        return postgres_get_active_location(self.config)

    def set_active_location(self, location_id) -> None:
        from .postgres import postgres_set_active_location
        postgres_set_active_location(self.config, location_id)

    def add_location(self, name: str, full_name: str, **kwargs) -> int:
        from .postgres import postgres_add_location
        return postgres_add_location(self.config, name, full_name, **kwargs)

    def update_location(self, location_id, **kwargs) -> None:
        from .postgres import postgres_update_location
        postgres_update_location(self.config, location_id, **kwargs)

    def delete_location(self, location_id) -> None:
        from .postgres import postgres_delete_location
        postgres_delete_location(self.config, location_id)

    def init_database(self) -> None:
        from .postgres import init_postgres_locations_db
        init_postgres_locations_db(self.config)


# === Funkcja wykrywająca aktywny silnik ===
_engine: Optional[DatabaseEngine] = None


def detect_engine() -> DatabaseEngine:
    """
    Wykrywa aktywny silnik bazy danych na podstawie backend/.env.
    Zwraca instancję DatabaseEngine (singleton).
    """
    global _engine
    if _engine is not None:
        return _engine

    # 1. Sprawdź backend/.env
    env_path = BACKEND_DIR / ".env"
    db_engine = os.getenv("DB_ENGINE", "")

    if not db_engine and env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DB_ENGINE="):
                        db_engine = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass

    # 2. BEZPIECZNY FALLBACK (FIX 2026-06-05):
    #    Gdy DB_ENGINE jest pusty (first-run, brak linii w .env, lub DB_ENGINE=)
    #    NIE wybieramy domyślnie 'postgresql' -- to powodowało że launcher
    #    próbował łączyć się z PG zanim user wybrał silnik w first-run dialog.
    #
    #    Domyślnie używamy SQLite (bez zewnętrznych zależności, zawsze działa).
    #    ``setup_postgres_config`` (w launcher_app.py) i tak wywoła
    #    ``choose_database_engine`` który pokaże dialog jeśli brak wyboru --
    #    user może wtedy przełączyć na PG.
    #
    # 3. Wybierz silnik
    if db_engine and db_engine.lower() == "sqlite":
        _engine = SQLiteEngine()
    elif db_engine and db_engine.lower() == "postgresql":
        _engine = PostgreSQLEngine()
    else:
        # Pusty string, brak wartości, lub nieznany silnik -> SQLite (safe default).
        _engine = SQLiteEngine()

    return _engine


def get_engine() -> DatabaseEngine:
    """Zwraca aktywny silnik bazy danych."""
    return detect_engine()


def switch_engine(engine_name: str) -> DatabaseEngine:
    """
    Przełącza silnik bazy danych.
    engine_name: "sqlite" lub "postgresql"
    """
    global _engine

    # Zapisz do backend/.env
    env_path = BACKEND_DIR / ".env"
    lines = []
    found = False
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("DB_ENGINE="):
                    lines.append(f"DB_ENGINE={engine_name}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"\nDB_ENGINE={engine_name}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Ustaw zmienną środowiskową
    os.environ["DB_ENGINE"] = engine_name

    # Zresetuj cache silnika
    _engine = None

    # Zwróć nowy silnik
    return detect_engine()
