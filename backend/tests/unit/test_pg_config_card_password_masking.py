"""Test bezpieczeństwa panelu 'Konfiguracja PostgreSQL'.

Sprawdza że pole hasła w panelu edycji konfiguracji PG ma ``show='*'``
(maskowanie) - regresja: kiedyś kod miał ``show = "" if key == "password"``
co oznaczało BRAK maskowania. Użytkownik widział hasło jawnie.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

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


# Mockujemy zależności środowiskowe zanim zaimportujemy moduł
def _build_pg_config_card_mocked():
    """Woła ``_build_pg_config_card`` z mockowanym ``self``."""
    from launcher.ui.program_settings import ProgramSettingsWindow

    # Mockowane self z brakującymi metodami (używanymi w przyciskach)
    self_mock = types.SimpleNamespace(
        _pg_config_fields=None,
        run_postgres_connection_test=lambda: None,
        _save_pg_config=lambda: None,
        _reload_pg_config=lambda: None,
        _change_pg_password_dialog=lambda: None,
    )

    root = tk.Tk()
    root.withdraw()
    parent = ttk.Frame(root)
    parent.pack()
    try:
        card = ProgramSettingsWindow._build_pg_config_card(self_mock, parent)
        root.update_idletasks()
        return card, root
    except Exception:
        root.destroy()
        raise


def test_password_entry_in_pg_config_has_mask():
    """Pole hasła w panelu konfiguracji PG MUSI mieć show='*'."""
    card, root = _build_pg_config_card_mocked()
    try:
        # Szukamy Entry w card i jego dzieciach
        entries = []
        def collect(w):
            for child in w.winfo_children():
                if isinstance(child, ttk.Entry):
                    entries.append(child)
                collect(child)
        collect(card)

        assert len(entries) == 5, (
            f"Oczekiwano 5 pól Entry (host/port/user/password/db), "
            f"znaleziono {len(entries)}"
        )

        # entries w kolejności: host, port, user, password, db_name
        # password ma index 3
        pw_entry = entries[3]
        show = pw_entry.cget("show")
        assert show == "*", (
            f"Pole hasła ma show={show!r} - hasło NIE jest maskowane! "
            f"Regresja: kiedyś kod miał 'show = \"\" if key == \"password\"' "
            f"co oznaczało BRAK maskowania."
        )
    finally:
        root.destroy()


def test_password_value_still_loads_correctly():
    """Wartość hasła powinna nadal być wczytana z .env (maskowanie dotyczy wyświetlania)."""
    card, root = _build_pg_config_card_mocked()
    try:
        # Sprawdzamy że password_var ma wartość (z .env lub pustą)
        # (nie testujemy konkretnej wartości, tylko że Entry istnieje i ma var)
        entries = []
        def collect(w):
            for child in w.winfo_children():
                if isinstance(child, ttk.Entry):
                    entries.append(child)
                collect(child)
        collect(card)
        assert len(entries) == 5
        pw_entry = entries[3]
        # textvariable istnieje i jest StringVar
        var = pw_entry.cget("textvariable")
        assert var != "", "Pole hasła nie ma textvariable"
    finally:
        root.destroy()


def test_non_password_entries_have_no_mask():
    """Pola NIE-hasła (host, port, user, db) MUSZĄ być czytelne (show='')."""
    card, root = _build_pg_config_card_mocked()
    try:
        entries = []
        def collect(w):
            for child in w.winfo_children():
                if isinstance(child, ttk.Entry):
                    entries.append(child)
                collect(child)
        collect(card)

        # entries: host, port, user, password, db_name
        for i, key in enumerate(["host", "port", "user", "password", "db_name"]):
            show = entries[i].cget("show")
            if key == "password":
                assert show == "*", f"{key} powinno być maskowane (show='*')"
            else:
                assert show == "", (
                    f"{key} powinno być czytelne (show=''), ma show={show!r}"
                )
    finally:
        root.destroy()
