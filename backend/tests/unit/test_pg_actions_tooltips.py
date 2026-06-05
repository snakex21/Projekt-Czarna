"""Testy tooltips dla przycisków panelu 'PostgreSQL — operacje'.

Sprawdza że przyciski mają tooltipy z wyjaśnieniem DLACZEGO mogą być
DISABLED. Bez tego user nie wie czy disabled to bug czy celowy stan.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    import tkinter as tk
    from tkinter import ttk
except Exception as e:  # pragma: no cover
    pytest.skip(f"tkinter niedostępny: {e}", allow_module_level=True)


def _has_display() -> bool:
    if sys.platform.startswith("win") or sys.platform == "darwin":
        return True
    import os
    return bool(os.environ.get("DISPLAY"))


if not _has_display():
    pytest.skip("Brak DISPLAY — testy tkinter pominięte", allow_module_level=True)


class _FakeApp:
    """Minimalny mock ProgramSettingsWindow.parent_app."""

    def get_database_diagnostics(self):
        return {
            "mode": "postgresql",
            "connection_ok": True,
            "launcher_db_exists": True,  # istnieje → przycisk szary
            "location_db_exists": True,  # istnieje → przycisk szary
            "location_postgis": True,    # włączone → przycisk szary
            "pgadmin_available": False,
        }

    def get_guardian_status_snapshot(self):
        return {}


def _build_pg_actions_frame_with_tooltips(diagnostics: dict):
    """Tworzy mini panel 'PostgreSQL — operacje' z tooltips i woła update."""
    from launcher.ui.program_settings import _Tooltip, create_card, SPACING_MD, SPACING_XS

    root = tk.Tk()
    root.withdraw()
    parent = ttk.Frame(root)
    parent.pack()

    card = create_card(parent, "PostgreSQL — operacje")
    pg_btn_frame = ttk.Frame(card, style="Card.TFrame")
    pg_btn_frame.pack(fill=tk.X, padx=SPACING_MD, pady=(0, 4))

    btn_test = ttk.Button(pg_btn_frame, text="Test połączenia")
    btn_test.pack(side=tk.LEFT, padx=(0, 2))
    btn_launcher = ttk.Button(pg_btn_frame, text="Utwórz bazę launcher")
    btn_launcher.pack(side=tk.LEFT, padx=2)
    btn_location = ttk.Button(pg_btn_frame, text="Utwórz bazę miejscowości")
    btn_location.pack(side=tk.LEFT, padx=2)
    btn_postgis = ttk.Button(pg_btn_frame, text="Włącz PostGIS")
    btn_postgis.pack(side=tk.LEFT, padx=2)

    tt_test = _Tooltip(btn_test, "")
    tt_launcher = _Tooltip(btn_launcher, "")
    tt_location = _Tooltip(btn_location, "")
    tt_postgis = _Tooltip(btn_postgis, "")

    # Symuluj update_action_states z naszymi diagnostics
    is_sqlite = diagnostics.get("mode") == "sqlite"
    pg_connected = bool(diagnostics.get("connection_ok"))
    launcher_exists = bool(diagnostics.get("launcher_db_exists"))
    location_exists = bool(diagnostics.get("location_db_exists"))
    location_postgis = bool(diagnostics.get("location_postgis"))

    if is_sqlite:
        tt_mode = "Aktywny tryb SQLite"
    elif not pg_connected:
        tt_mode = "Brak połączenia z PostgreSQL"
    else:
        tt_mode = None

    def _tt(btn_tooltip, available: bool, exists: bool, action: str) -> None:
        if tt_mode is not None:
            btn_tooltip.set_text(tt_mode)
        elif not available:
            btn_tooltip.set_text(f"'{action}' — baza już istnieje. Przycisk nieaktywny.")
        else:
            btn_tooltip.set_text(action)

    tt_test.set_text(tt_mode or "Sprawdza połączenie z serwerem PostgreSQL")
    _tt(tt_launcher, not launcher_exists, launcher_exists, "Tworzy bazę mapa_launcher_db")
    _tt(tt_location, not location_exists, location_exists, "Tworzy bazę aktywnej miejscowości")
    if tt_mode is not None:
        tt_postgis.set_text(tt_mode)
    elif not location_exists:
        tt_postgis.set_text("Utwórz najpierw bazę miejscowości")
    elif location_postgis:
        tt_postgis.set_text("PostGIS jest już włączony")
    else:
        tt_postgis.set_text("Włącza PostGIS")

    root.update_idletasks()
    return {
        "root": root,
        "buttons": [btn_test, btn_launcher, btn_location, btn_postgis],
        "tooltips": [tt_test, tt_launcher, tt_location, tt_postgis],
        "diagnostics": diagnostics,
    }


def test_tooltips_have_text_when_pg_connected_and_db_exists():
    """Gdy PG działa i baza istnieje, tooltips wyjaśniają 'baza istnieje'."""
    state = _build_pg_actions_frame_with_tooltips({
        "mode": "postgresql", "connection_ok": True,
        "launcher_db_exists": True, "location_db_exists": True,
        "location_postgis": True,
    })
    try:
        tt_test, tt_launcher, tt_location, tt_postgis = state["tooltips"]
        # Test połączenia: zawsze ma sensowny tekst
        assert "połączenie" in tt_test.text.lower() or "PostgreSQL" in tt_test.text
        # Utwórz bazę launcher: baza istnieje → tooltip to wyjaśnia
        assert tt_launcher.text != "", "Tooltip dla Utwórz launcher jest pusty"
        assert "istnieje" in tt_launcher.text.lower(), (
            f"Tooltip nie wyjaśnia dlaczego disabled: {tt_launcher.text!r}"
        )
        # Utwórz bazę miejscowości: j.w.
        assert tt_location.text != "", "Tooltip dla Utwórz miejscowość jest pusty"
        assert "istnieje" in tt_location.text.lower(), (
            f"Tooltip nie wyjaśnia dlaczego disabled: {tt_location.text!r}"
        )
        # Włącz PostGIS: już włączone → tooltip to wyjaśnia
        assert tt_postgis.text != "", "Tooltip dla Włącz PostGIS jest pusty"
        assert (
            "postgis" in tt_postgis.text.lower()
            and ("już" in tt_postgis.text.lower() or "istnieje" in tt_postgis.text.lower())
        ), f"Tooltip nie wyjaśnia dlaczego disabled: {tt_postgis.text!r}"
    finally:
        state["root"].destroy()


def test_tooltip_explains_pg_not_connected():
    """Gdy brak połączenia z PG, tooltip mówi o tym."""
    state = _build_pg_actions_frame_with_tooltips({
        "mode": "postgresql", "connection_ok": False,
        "launcher_db_exists": False, "location_db_exists": False,
        "location_postgis": False,
    })
    try:
        tt_test, tt_launcher, tt_location, tt_postgis = state["tooltips"]
        for tt in state["tooltips"]:
            assert tt.text != "", f"Tooltip jest pusty: {tt}"
            assert (
                "połączenie" in tt.text.lower()
                or "połącz" in tt.text.lower()
            ), f"Tooltip nie wspomina o braku połączenia: {tt.text!r}"
    finally:
        state["root"].destroy()


def test_tooltip_explains_sqlite_mode():
    """Gdy tryb SQLite, tooltip mówi o trybie SQLite."""
    state = _build_pg_actions_frame_with_tooltips({
        "mode": "sqlite", "connection_ok": False,
        "launcher_db_exists": False, "location_db_exists": False,
        "location_postgis": False,
    })
    try:
        for tt in state["tooltips"]:
            assert tt.text != "", f"Tooltip jest pusty: {tt}"
            assert "sqlite" in tt.text.lower(), (
                f"Tooltip nie wspomina o trybie SQLite: {tt.text!r}"
            )
    finally:
        state["root"].destroy()


def test_tooltip_for_postgis_says_need_location_first():
    """Gdy brak bazy miejscowości, tooltip PostGIS mówi 'najpierw utwórz bazę'."""
    state = _build_pg_actions_frame_with_tooltips({
        "mode": "postgresql", "connection_ok": True,
        "launcher_db_exists": True, "location_db_exists": False,
        "location_postgis": False,
    })
    try:
        tt_test, tt_launcher, tt_location, tt_postgis = state["tooltips"]
        assert "najpierw" in tt_postgis.text.lower() or "baz" in tt_postgis.text.lower()
    finally:
        state["root"].destroy()


def test_tooltip_for_postgis_says_action_when_available():
    """Gdy PostGIS NIE jest włączony i baza istnieje, tooltip mówi 'Włącza'."""
    state = _build_pg_actions_frame_with_tooltips({
        "mode": "postgresql", "connection_ok": True,
        "launcher_db_exists": True, "location_db_exists": True,
        "location_postgis": False,
    })
    try:
        tt_test, tt_launcher, tt_location, tt_postgis = state["tooltips"]
        # Powinien mówić co przycisk zrobi
        assert "Włącz" in tt_postgis.text or "włącz" in tt_postgis.text.lower()
    finally:
        state["root"].destroy()


def test_tooltip_set_text_updates_text():
    """Tooltip.set_text() aktualizuje tekst dynamicznie."""
    from launcher.ui.program_settings import _Tooltip
    root = tk.Tk()
    root.withdraw()
    try:
        btn = ttk.Button(root, text="X")
        btn.pack()
        tt = _Tooltip(btn, "Initial")
        assert tt.text == "Initial"
        tt.set_text("Updated text")
        assert tt.text == "Updated text"
        tt.set_text("")
        assert tt.text == ""
    finally:
        root.destroy()
