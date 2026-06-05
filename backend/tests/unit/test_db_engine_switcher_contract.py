from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SWITCHER = PROJECT_ROOT / "launcher" / "ui" / "db_engine_switcher.py"


def test_db_engine_switcher_hides_raw_connection_refused_errors():
    """Dialog zmiany silnika nie pokazuje surowego psycopg2 traceback/errora."""
    source = SWITCHER.read_text(encoding="utf-8")

    assert "def _friendly_postgres_status" in source
    assert "PostgreSQL nie działa albo nie jest zainstalowany" in source
    assert "detail_label.insert(\"1.0\", msg)" not in source
    assert "detail_label.insert(\"1.0\", _friendly_postgres_status" in source


def test_db_engine_switcher_blocks_switch_to_unavailable_postgres():
    """Nie wolno zapisać DB_ENGINE=postgresql, gdy serwer PG nie odpowiada."""
    source = SWITCHER.read_text(encoding="utf-8")

    assert 'pg_available = {"ok": False}' in source
    assert 'selected == "postgresql" and not pg_available["ok"]' in source
    assert "Nie można przełączyć na PostgreSQL" in source
    assert "switch_engine(selected)" in source


def test_db_engine_switcher_offers_postgres_installer_when_unavailable():
    """Gdy PG jest niedostępny, dialog oferuje instalację PostgreSQL + PostGIS."""
    source = SWITCHER.read_text(encoding="utf-8")

    assert "from launcher.ui.database_config_dialogs import _run_edb_installer" in source
    assert "Zainstaluj PostgreSQL + PostGIS" in source
    assert "install_pg_button" in source
    assert "_run_edb_installer(dialog)" in source
    assert "Czy chcesz teraz uruchomić graficzny instalator" in source
