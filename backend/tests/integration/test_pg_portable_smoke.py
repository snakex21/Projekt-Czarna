"""Smoke testy: serwisy portable PG importują się i mają oczekiwane API.

Lekka sanity-checka używana w ``backend/tests/integration/``:
sprawdza że moduły ``pg_portable_service`` i ``pg_runtime`` istnieją
i eksponują API, na którym polegają wizardy / wyższe warstwy launchera.
Nie wywołuje prawdziwego HTTP / subprocess / I/O poza tworzeniem
dataclass.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Import modułów
# ---------------------------------------------------------------------------


def test_pg_portable_service_module_imports():
    """``launcher.services.pg_portable_service`` importuje się bez błędów."""
    from launcher.services import pg_portable_service
    assert pg_portable_service is not None


def test_pg_runtime_module_imports():
    """``launcher.services.pg_runtime`` importuje się bez błędów."""
    from launcher.services import pg_runtime
    assert pg_runtime is not None


# ---------------------------------------------------------------------------
# Publiczne API: pg_portable_service (Etap 1)
# ---------------------------------------------------------------------------


def test_pg_portable_service_has_all_required_functions():
    """``pg_portable_service`` eksponuje pełne API Etapu 1."""
    from launcher.services import pg_portable_service
    required = [
        "detect_system_pg",
        "get_pg_download_url",
        "get_pg_install_dir",
        "download_pg_binary",
        "extract_pg_archive",
        "is_pg_initialized",
        "get_portable_pg_paths",
        "portable_pg_installed",
        "verify_pg_archive_checksum",
    ]
    for name in required:
        assert hasattr(pg_portable_service, name), (
            f"Brak funkcji {name!r} w launcher.services.pg_portable_service"
        )
        assert callable(getattr(pg_portable_service, name)), (
            f"{name!r} w pg_portable_service nie jest callable"
        )


# ---------------------------------------------------------------------------
# Publiczne API: pg_runtime (Etap 2)
# ---------------------------------------------------------------------------


def test_pg_runtime_has_all_required_functions():
    """``pg_runtime`` eksponuje pełne API Etapu 2 (init/start/stop)."""
    from launcher.services import pg_runtime
    required = [
        "init_pg_data_dir",
        "start_pg_server",
        "stop_pg_server",
        "is_pg_server_running",
        "wait_for_pg_ready",
        "get_postmaster_pid",
        "remove_pg_data_dir",
        # dataclassy
        "PgServerConfig",
        "PgServerHandle",
        "ServerHandle",
        "StepResult",
    ]
    for name in required:
        assert hasattr(pg_runtime, name), (
            f"Brak {name!r} w launcher.services.pg_runtime"
        )


def test_pg_server_handle_alias_matches_server_handle():
    """``PgServerHandle`` jest aliasem ``ServerHandle`` (kompatybilność)."""
    from launcher.services.pg_runtime import PgServerHandle, ServerHandle
    assert PgServerHandle is ServerHandle


# ---------------------------------------------------------------------------
# Dataclassy
# ---------------------------------------------------------------------------


def test_portable_pg_paths_dataclass_holds_expected_fields():
    """``PortablePgPaths`` przechowuje ścieżki i wersję PG."""
    from launcher.services.pg_portable_service import PortablePgPaths

    paths = PortablePgPaths(
        root_dir=Path("/tmp/pg"),
        bin_dir=Path("/tmp/pg/pgsql/bin"),
        data_dir=Path("/tmp/pg/data"),
        pg_ctl_path=Path("/tmp/pg/pgsql/bin/pg_ctl"),
        initdb_path=Path("/tmp/pg/pgsql/bin/initdb"),
        pg_version="16.4",
    )
    assert paths.pg_version == "16.4"
    assert paths.data_dir == Path("/tmp/pg/data")
    assert paths.pg_ctl_path.name == "pg_ctl"
    assert paths.initdb_path.name == "initdb"


def test_pg_server_config_dataclass_holds_paths_and_port():
    """``PgServerConfig`` przechowuje ``paths`` i ``port`` (i domyślne)."""
    from launcher.services.pg_portable_service import PortablePgPaths
    from launcher.services.pg_runtime import PgServerConfig

    paths = PortablePgPaths(
        root_dir=Path("/tmp/pg"),
        bin_dir=Path("/tmp/pg/pgsql/bin"),
        data_dir=Path("/tmp/pg/data"),
        pg_ctl_path=Path("/tmp/pg/pgsql/bin/pg_ctl"),
        initdb_path=Path("/tmp/pg/pgsql/bin/initdb"),
        pg_version="16.4",
    )
    config = PgServerConfig(paths=paths, port=5433)
    assert config.paths is paths
    assert config.port == 5433
    # Domyślne wartości
    assert config.username == "postgres"
    assert config.listen_addresses == "127.0.0.1"
    assert config.password is None
    assert config.extra_initdb_args == ()


def test_step_result_dataclass_constructs_with_ok_flag():
    """``StepResult`` przechowuje flagę ``ok`` + komunikat + szczegóły."""
    from launcher.services.pg_runtime import StepResult

    result = StepResult(
        name="initdb",
        ok=True,
        message="ok",
        details={"data_dir": "/x"},
    )
    assert result.name == "initdb"
    assert result.ok is True
    assert result.message == "ok"
    assert result.details == {"data_dir": "/x"}


def test_server_handle_dataclass_default_optional_fields():
    """``ServerHandle`` ma sensowne wartości domyślne (proc=None)."""
    from launcher.services.pg_runtime import ServerHandle

    handle = ServerHandle(pid=123, data_dir=Path("/x"), port=5432)
    assert handle.pid == 123
    assert handle.data_dir == Path("/x")
    assert handle.port == 5432
    assert handle.host == "127.0.0.1"
    assert handle.bin_dir is None
    assert handle.proc is None
    assert handle.config is None
