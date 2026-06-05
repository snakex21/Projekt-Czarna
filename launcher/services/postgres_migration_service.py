"""Czysty serwis migracji danych lokalnych do PostgreSQL.

Moduł nie zawiera zależności od Tkintera ani warstwy UI. Służy jako
orkiestrator dla kreatora PostgreSQL: sprawdza połączenie, przygotowuje bazę
miejscowości, uruchamia istniejącą migrację JSON -> PostgreSQL, weryfikuje
liczniki i dopiero po pełnym sukcesie przełącza konfigurację backendu na
``DB_ENGINE=postgresql``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Any

from launcher.config.paths import BACKEND_DIR, BASE_DIR, location_data_dir, location_env_path
from launcher.db import postgres as postgres_db
from launcher.db.schemas import LOCATION_DB_SCHEMA
from launcher.services.env_config_service import update_env_content


LogCallback = Callable[[str], None]


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    user: str
    password: str = ""


@dataclass(frozen=True)
class MigrationOptions:
    location_name: str
    db_name: str | None = None
    create_database: bool = True
    recreate_schema: bool = True
    enable_postgis: bool = True
    switch_engine_on_success: bool = True
    migration_timeout_seconds: int = 300


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass(frozen=True)
class DataCounts:
    owners: int = 0
    objects: int = 0
    genealogy_persons: int = 0
    parcel_owner_links: int = 0
    demography_rows: int = 0
    marriages: int = 0


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    source_counts: DataCounts
    target_counts: DataCounts
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StepResult:
    name: str
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MigrationRunResult:
    ok: bool
    db_name: str
    steps: list[StepResult]
    verification: VerificationResult | None = None
    log_path: Path | None = None


def normalize_postgres_config(config: PostgresConfig | dict[str, Any]) -> PostgresConfig:
    """Normalizuje konfigurację PostgreSQL z dicta albo dataclass."""
    if isinstance(config, PostgresConfig):
        return config
    try:
        port = int(config.get("port", 5432))
    except (TypeError, ValueError):
        port = 0
    return PostgresConfig(
        host=str(config.get("host", "") or "").strip(),
        port=port,
        user=str(config.get("user", "") or "").strip(),
        password=str(config.get("password", "") or ""),
    )


def postgres_config_to_dict(config: PostgresConfig | dict[str, Any]) -> dict[str, Any]:
    """Zwraca format konfiguracji oczekiwany przez ``launcher.db.postgres``."""
    cfg = normalize_postgres_config(config)
    return {"host": cfg.host, "port": cfg.port, "user": cfg.user, "password": cfg.password}


def validate_postgres_config(config: PostgresConfig | dict[str, Any]) -> ValidationResult:
    """Waliduje podstawowe pola połączenia PostgreSQL."""
    cfg = normalize_postgres_config(config)
    issues: list[ValidationIssue] = []
    if not cfg.host:
        issues.append(ValidationIssue("host", "Host PostgreSQL jest wymagany."))
    if not 1 <= cfg.port <= 65535:
        issues.append(ValidationIssue("port", "Port PostgreSQL musi być liczbą z zakresu 1-65535."))
    if not cfg.user:
        issues.append(ValidationIssue("user", "Użytkownik PostgreSQL jest wymagany."))
    return ValidationResult(ok=not issues, issues=issues)


def build_location_db_name(location_name: str, explicit_db_name: str | None = None) -> str:
    """Buduje bezpieczną nazwę bazy miejscowości, domyślnie ``mapa_<nazwa>_db``."""
    raw_name = explicit_db_name or f"mapa_{location_name}_db"
    polish_replacements = str.maketrans({
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z",
        "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N", "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
    })
    normalized = unicodedata.normalize("NFKD", raw_name.translate(polish_replacements))
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    safe = re.sub(r"[^a-z0-9_]+", "_", ascii_name)
    safe = re.sub(r"_+", "_", safe).strip("_")
    if not safe:
        raise ValueError("Nie można zbudować bezpiecznej nazwy bazy PostgreSQL.")
    if not re.match(r"^[a-z_]", safe):
        safe = f"db_{safe}"
    return safe


def create_migration_log_path(location_name: str) -> Path:
    """Tworzy ścieżkę logu migracji w katalogu aktywnej miejscowości."""
    logs_dir = location_data_dir(location_name) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return logs_dir / f"postgres_migration_{stamp}.log"


def append_migration_log(log_path: Path, message: str) -> None:
    """Dopisuje linię do pliku logu migracji."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(message.rstrip() + "\n")


def _log(message: str, log_path: Path | None = None, callback: LogCallback | None = None) -> None:
    if log_path is not None:
        append_migration_log(log_path, message)
    if callback is not None:
        callback(message)


def test_postgres_connection(
    config: PostgresConfig | dict[str, Any],
    timeout_seconds: int = 3,
) -> StepResult:
    """Sprawdza połączenie do serwera PostgreSQL bez wybierania bazy miejscowości."""
    cfg = normalize_postgres_config(config)
    validation = validate_postgres_config(cfg)
    if not validation.ok:
        return StepResult(
            "test_connection",
            False,
            "; ".join(issue.message for issue in validation.issues),
        )
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            database="postgres",
            connect_timeout=timeout_seconds,
        )
        conn.close()
        return StepResult("test_connection", True, "Połączenie z PostgreSQL udane.")
    except Exception as exc:
        return StepResult("test_connection", False, f"Błąd połączenia z PostgreSQL: {exc}")


def check_database_exists(config: PostgresConfig | dict[str, Any], db_name: str) -> bool:
    """Sprawdza czy baza istnieje."""
    return postgres_db.database_exists(postgres_config_to_dict(config), db_name)


def ensure_location_database(
    config: PostgresConfig | dict[str, Any],
    db_name: str,
    create_if_missing: bool = True,
) -> StepResult:
    """Zapewnia istnienie bazy miejscowości."""
    cfg = postgres_config_to_dict(config)
    if postgres_db.database_exists(cfg, db_name):
        return StepResult("ensure_database", True, f"Baza {db_name} już istnieje.", {"created": False})
    if not create_if_missing:
        return StepResult("ensure_database", False, f"Baza {db_name} nie istnieje.", {"created": False})
    ok, msg = postgres_db.create_database(cfg, db_name)
    return StepResult("ensure_database", ok, msg, {"created": ok})


def ensure_postgis_enabled(config: PostgresConfig | dict[str, Any], db_name: str) -> StepResult:
    """Włącza PostGIS w bazie miejscowości."""
    cfg = postgres_config_to_dict(config)
    ok, msg = postgres_db.enable_postgis(cfg, db_name)
    if ok and hasattr(postgres_db, "has_postgis_extension"):
        try:
            ok = bool(postgres_db.has_postgis_extension(cfg, db_name))
            if not ok:
                msg = "PostGIS nie został potwierdzony po włączeniu."
        except Exception:
            pass
    return StepResult("ensure_postgis", ok, msg)


def execute_location_schema(
    config: PostgresConfig | dict[str, Any],
    db_name: str,
    schema_sql: str = LOCATION_DB_SCHEMA,
) -> StepResult:
    """Wykonuje schemat bazy miejscowości.

    Uwaga: aktualny ``LOCATION_DB_SCHEMA`` zawiera DROP TABLE i jest operacją
    odtwarzającą schemat.
    """
    ok, msg = postgres_db.execute_schema(postgres_config_to_dict(config), db_name, schema_sql)
    return StepResult("execute_schema", ok, msg)


def _norm_plot_number(value: Any) -> str:
    if isinstance(value, dict):
        numerator = str(value.get("numerator") or value.get("numarator") or "").strip()
        denominator = str(value.get("denominator") or "").strip()
        return f"{numerator}/{denominator}" if numerator and denominator else numerator
    return str(value or "").strip()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def count_source_data(location_name: str) -> DataCounts:
    """Liczy dane źródłowe z katalogu ``data/locations/<miejscowość>``."""
    folder = location_data_dir(location_name)
    owners_raw = _read_json(folder / "owner_data_to_import.json", {})
    parcels_raw = _read_json(folder / "parcels_data.json", {})
    genealogy_raw = _read_json(folder / "genealogia.json", {})
    demography_raw = _read_json(folder / "demografia.json", [])

    object_keys: set[tuple[str, str]] = set()
    if isinstance(parcels_raw, dict):
        for raw_key, data in parcels_raw.items():
            data = data if isinstance(data, dict) else {}
            if "_" in str(raw_key):
                raw_number, category_from_key = str(raw_key).split("_", 1)
                category = category_from_key or data.get("kategoria", "rolna")
            else:
                raw_number = raw_key
                category = data.get("kategoria", "rolna")
            object_keys.add((_norm_plot_number(raw_number), str(category or "rolna")))

    genealogy_persons = 0
    marriages = 0
    if isinstance(genealogy_raw, dict):
        persons = genealogy_raw.get("persons", [])
        genealogy_persons = len(persons) if isinstance(persons, list) else 0
        seen_pairs: set[tuple[str, str]] = set()
        for person in persons if isinstance(persons, list) else []:
            pid = str(person.get("id", ""))
            for spouse_id in person.get("spouseIds", []) or []:
                pair = tuple(sorted((pid, str(spouse_id))))
                if pair[0] and pair[1]:
                    seen_pairs.add(pair)
            for marriage in person.get("marriages", []) or []:
                spouse_id = marriage.get("spouseId")
                pair = tuple(sorted((pid, str(spouse_id))))
                if pair[0] and pair[1] and pair[1] != "None":
                    seen_pairs.add(pair)
        marriages = len(seen_pairs)

    links = 0
    if isinstance(owners_raw, dict):
        for owner in owners_raw.values():
            if not isinstance(owner, dict):
                continue
            for field_name in ("realbuildingPlots", "realagriculturalPlots", "buildingPlots", "agriculturalPlots"):
                values = owner.get(field_name, []) or []
                links += len(values) if isinstance(values, list) else 0
            if owner.get("houseNumber"):
                links += 1

    return DataCounts(
        owners=len(owners_raw) if isinstance(owners_raw, dict) else 0,
        objects=len(object_keys),
        genealogy_persons=genealogy_persons,
        parcel_owner_links=links,
        demography_rows=len(demography_raw) if isinstance(demography_raw, list) else 0,
        marriages=marriages,
    )


def count_target_data(config: PostgresConfig | dict[str, Any], db_name: str) -> DataCounts:
    """Liczy rekordy w docelowej bazie PostgreSQL."""
    cfg = normalize_postgres_config(config)
    import psycopg2

    table_map = {
        "owners": "wlasciciele",
        "objects": "obiekty_geograficzne",
        "genealogy_persons": "osoby_genealogia",
        "parcel_owner_links": "dzialki_wlasciciele",
        "demography_rows": "demografia",
        "marriages": "malzenstwa",
    }
    values: dict[str, int] = {}
    conn = psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        dbname=db_name,
    )
    try:
        cursor = conn.cursor()
        try:
            for field_name, table_name in table_map.items():
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                values[field_name] = int(cursor.fetchone()[0])
        finally:
            cursor.close()
    finally:
        conn.close()
    return DataCounts(**values)


def verify_migration(source_counts: DataCounts, target_counts: DataCounts) -> VerificationResult:
    """Porównuje liczniki źródłowe i docelowe po migracji."""
    errors: list[str] = []
    warnings: list[str] = []

    if target_counts.owners != source_counts.owners:
        errors.append(f"Liczba właścicieli: źródło={source_counts.owners}, PostgreSQL={target_counts.owners}.")
    if target_counts.objects < source_counts.objects:
        errors.append(f"Liczba obiektów: źródło={source_counts.objects}, PostgreSQL={target_counts.objects}.")
    elif target_counts.objects > source_counts.objects:
        warnings.append("PostgreSQL ma więcej obiektów niż źródło — importer mógł dodać brakujące działki z protokołów.")
    if source_counts.genealogy_persons and target_counts.genealogy_persons != source_counts.genealogy_persons:
        errors.append(
            f"Liczba osób genealogicznych: źródło={source_counts.genealogy_persons}, "
            f"PostgreSQL={target_counts.genealogy_persons}."
        )
    if source_counts.demography_rows and target_counts.demography_rows != source_counts.demography_rows:
        errors.append(f"Liczba wpisów demografii: źródło={source_counts.demography_rows}, PostgreSQL={target_counts.demography_rows}.")
    if source_counts.parcel_owner_links and target_counts.parcel_owner_links == 0:
        errors.append("Źródło zawiera powiązania działka–właściciel, ale PostgreSQL ma 0 powiązań.")

    return VerificationResult(
        ok=not errors,
        source_counts=source_counts,
        target_counts=target_counts,
        errors=errors,
        warnings=warnings,
    )


def run_json_to_postgres_migration(
    config: PostgresConfig | dict[str, Any],
    location_name: str,
    db_name: str,
    timeout_seconds: int = 300,
    log_callback: LogCallback | None = None,
) -> StepResult:
    """Uruchamia istniejący skrypt migracji JSON -> PostgreSQL jako subprocess."""
    cfg = normalize_postgres_config(config)
    script_path = BACKEND_DIR / "scripts" / "migrate_data.py"
    if not script_path.exists():
        return StepResult("run_migration", False, f"Brak skryptu migracji: {script_path}")

    env = os.environ.copy()
    env.update({
        "DB_ENGINE": "postgresql",
        "DB_HOST": cfg.host,
        "DB_PORT": str(cfg.port),
        "DB_NAME": db_name,
        "DB_USER": cfg.user,
        "DB_PASSWORD": cfg.password,
    })

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), location_name],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return StepResult("run_migration", False, f"Migracja przekroczyła limit czasu: {timeout_seconds}s")

    if log_callback and result.stdout:
        for line in result.stdout.splitlines():
            log_callback(line)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"Migracja zakończona kodem {result.returncode}."
        return StepResult("run_migration", False, message, {"returncode": result.returncode})
    return StepResult("run_migration", True, "Migracja JSON -> PostgreSQL zakończona pomyślnie.", {"returncode": 0})


def build_postgres_env_updates(config: PostgresConfig | dict[str, Any], db_name: str) -> dict[str, str]:
    """Buduje zestaw wpisów .env dla pracy backendu na PostgreSQL."""
    cfg = normalize_postgres_config(config)
    return {
        "DB_ENGINE": "postgresql",
        "DB_HOST": cfg.host,
        "DB_PORT": str(cfg.port),
        "DB_USER": cfg.user,
        "DB_PASSWORD": cfg.password,
        "DB_NAME": db_name,
    }


def _update_env_file(path: Path, updates: dict[str, str]) -> None:
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(update_env_content(content, updates), encoding="utf-8")


def update_backend_env_for_postgres(config: PostgresConfig | dict[str, Any], db_name: str) -> StepResult:
    """Aktualizuje ``backend/.env`` na PostgreSQL."""
    try:
        _update_env_file(BACKEND_DIR / ".env", build_postgres_env_updates(config, db_name))
        os.environ["DB_ENGINE"] = "postgresql"
        return StepResult("switch_engine", True, "backend/.env przełączony na PostgreSQL.")
    except Exception as exc:
        return StepResult("switch_engine", False, f"Nie udało się przełączyć backend/.env: {exc}")


def update_location_env_for_postgres(location_name: str, config: PostgresConfig | dict[str, Any], db_name: str) -> StepResult:
    """Aktualizuje ``data/locations/<name>/.env`` danymi PostgreSQL."""
    try:
        _update_env_file(location_env_path(location_name), build_postgres_env_updates(config, db_name))
        return StepResult("update_location_env", True, f".env miejscowości {location_name} zaktualizowany.")
    except Exception as exc:
        return StepResult("update_location_env", False, f"Nie udało się zaktualizować .env miejscowości: {exc}")


def run_postgres_migration_wizard(
    config: PostgresConfig | dict[str, Any],
    options: MigrationOptions,
    log_callback: LogCallback | None = None,
) -> MigrationRunResult:
    """Wykonuje pełny bezpieczny flow migracji dla kreatora PostgreSQL."""
    db_name = build_location_db_name(options.location_name, options.db_name)
    log_path = create_migration_log_path(options.location_name)
    steps: list[StepResult] = []

    def record(step: StepResult) -> StepResult:
        steps.append(step)
        _log(f"[{step.name}] {'OK' if step.ok else 'BŁĄD'}: {step.message}", log_path, log_callback)
        return step

    _log(f"Start migracji PostgreSQL dla: {options.location_name} -> {db_name}", log_path, log_callback)

    validation = validate_postgres_config(config)
    if not validation.ok:
        step = record(StepResult("validate_config", False, "; ".join(issue.message for issue in validation.issues)))
        return MigrationRunResult(False, db_name, steps=[step], log_path=log_path)
    record(StepResult("validate_config", True, "Konfiguracja PostgreSQL poprawna."))

    for step in [
        test_postgres_connection(config),
        ensure_location_database(config, db_name, create_if_missing=options.create_database),
    ]:
        record(step)
        if not step.ok:
            return MigrationRunResult(False, db_name, steps=steps, log_path=log_path)

    if options.enable_postgis:
        step = record(ensure_postgis_enabled(config, db_name))
        if not step.ok:
            return MigrationRunResult(False, db_name, steps=steps, log_path=log_path)

    if options.recreate_schema:
        step = record(execute_location_schema(config, db_name))
        if not step.ok:
            return MigrationRunResult(False, db_name, steps=steps, log_path=log_path)

    source_counts = count_source_data(options.location_name)
    record(StepResult("count_source", True, "Policzono dane źródłowe.", source_counts.__dict__))

    step = record(run_json_to_postgres_migration(config, options.location_name, db_name, options.migration_timeout_seconds, log_callback))
    if not step.ok:
        return MigrationRunResult(False, db_name, steps=steps, log_path=log_path)

    try:
        target_counts = count_target_data(config, db_name)
        record(StepResult("count_target", True, "Policzono dane w PostgreSQL.", target_counts.__dict__))
    except Exception as exc:
        step = record(StepResult("count_target", False, f"Nie udało się policzyć danych w PostgreSQL: {exc}"))
        return MigrationRunResult(False, db_name, steps=steps, log_path=log_path)

    verification = verify_migration(source_counts, target_counts)
    record(StepResult(
        "verify_migration",
        verification.ok,
        "Weryfikacja migracji zakończona pomyślnie." if verification.ok else "; ".join(verification.errors),
        {"warnings": verification.warnings},
    ))
    if not verification.ok:
        return MigrationRunResult(False, db_name, steps=steps, verification=verification, log_path=log_path)

    location_env_step = record(update_location_env_for_postgres(options.location_name, config, db_name))
    if not location_env_step.ok:
        return MigrationRunResult(False, db_name, steps=steps, verification=verification, log_path=log_path)

    if options.switch_engine_on_success:
        switch_step = record(update_backend_env_for_postgres(config, db_name))
        if not switch_step.ok:
            return MigrationRunResult(False, db_name, steps=steps, verification=verification, log_path=log_path)

    _log("Migracja PostgreSQL zakończona sukcesem.", log_path, log_callback)
    return MigrationRunResult(True, db_name, steps=steps, verification=verification, log_path=log_path)
