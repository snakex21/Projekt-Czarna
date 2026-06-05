"""Adaptery zgodności dla helperów PostgreSQL używanych przez starsze UI."""

from __future__ import annotations

from ..db.postgres import (
    test_connection as _test_postgres_connection,
    database_exists as _postgres_database_exists,
    create_database as _postgres_create_database,
    enable_postgis as _postgres_enable_postgis,
    execute_schema as _postgres_execute_schema,
    list_databases as _postgres_list_databases,
)


__all__ = [
    "test_postgres_connection",
    "postgres_database_exists",
    "postgres_create_database",
    "postgres_enable_postgis",
    "postgres_execute_schema",
    "postgres_list_databases",
]


def _normalize_pg_config_args(args, kwargs, *, needs_db_name=False, needs_schema=False):
    """Normalizuje stare i nowe style wywołań helperów PostgreSQL."""
    args = list(args)
    kwargs = dict(kwargs)

    if args and isinstance(args[0], dict):
        config = args.pop(0)
    elif len(args) >= 4:
        host, port, user, password = args[:4]
        args = args[4:]
        config = {"host": host, "port": port, "user": user, "password": password}
    else:
        try:
            config = {
                "host": kwargs.pop("host"),
                "port": kwargs.pop("port"),
                "user": kwargs.pop("user"),
                "password": kwargs.pop("password"),
            }
        except KeyError as exc:
            raise TypeError(f"Brak wymaganego argumentu konfiguracji PostgreSQL: {exc.args[0]}") from exc

    db_name = None
    schema_sql = None
    if needs_db_name:
        if "db_name" in kwargs:
            db_name = kwargs.pop("db_name")
        elif args:
            db_name = args.pop(0)
        else:
            raise TypeError("Brak wymaganego argumentu db_name")
    if needs_schema:
        if "schema_sql" in kwargs:
            schema_sql = kwargs.pop("schema_sql")
        elif args:
            schema_sql = args.pop(0)
        else:
            raise TypeError("Brak wymaganego argumentu schema_sql")
    if kwargs:
        raise TypeError(f"Nieobsługiwane argumenty PostgreSQL: {', '.join(kwargs.keys())}")
    if args:
        raise TypeError(f"Nieobsługiwane argumenty pozycyjne PostgreSQL: {args!r}")
    if needs_schema:
        return config, db_name, schema_sql
    if needs_db_name:
        return config, db_name
    return config


def test_postgres_connection(*args, **kwargs):
    config = _normalize_pg_config_args(args, kwargs)
    return _test_postgres_connection(config)


def postgres_database_exists(*args, **kwargs):
    config, db_name = _normalize_pg_config_args(args, kwargs, needs_db_name=True)
    return _postgres_database_exists(config, db_name)


def postgres_create_database(*args, **kwargs):
    config, db_name = _normalize_pg_config_args(args, kwargs, needs_db_name=True)
    return _postgres_create_database(config, db_name)


def postgres_enable_postgis(*args, **kwargs):
    config, db_name = _normalize_pg_config_args(args, kwargs, needs_db_name=True)
    return _postgres_enable_postgis(config, db_name)


def postgres_execute_schema(*args, **kwargs):
    config, db_name, schema_sql = _normalize_pg_config_args(args, kwargs, needs_db_name=True, needs_schema=True)
    return _postgres_execute_schema(config, db_name, schema_sql)


def postgres_list_databases(*args, **kwargs):
    config = _normalize_pg_config_args(args, kwargs)
    return _postgres_list_databases(config)
