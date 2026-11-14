"""Wspólny, ukryty root Tk dla testów GUI launchera.

Tworzenie wielu interpreterów Tcl/Tk (``tk.Tk()``) w jednym procesie pytest
na Windows sporadycznie kończy się błędem ``Can't find a usable tk.tcl ...
couldn't read file .../ttk/<plik>.tcl`` - każdy ``tk.Tk()`` ładuje od nowa
~25 skryptów ttk z dysku i pojedynczy nieudany odczyt wywraca test. Testy
padały więc tylko w pełnej sesji (więcej utworzonych interpreterów), a w
izolacji przechodziły.

Rozwiązanie: jeden root Tk na moduł testów (tworzony leniwie, z ponowieniem
przy przejściowym ``TclError``; niszczony po module przez fixture w
``backend/tests/conftest.py``), a każdy test dostaje własne okno ``Toplevel``,
które sam niszczy.
"""
from __future__ import annotations

import time
import tkinter as tk

_root: tk.Tk | None = None


def _alive(root: tk.Tk | None) -> bool:
    if root is None:
        return False
    try:
        return bool(root.winfo_exists())
    except tk.TclError:
        return False


def shared_tk_root(retries: int = 3) -> tk.Tk:
    """Zwraca (tworząc w razie potrzeby) ukryty, współdzielony root Tk."""
    global _root
    if _alive(_root):
        return _root
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            _root = tk.Tk()
            _root.withdraw()
            return _root
        except tk.TclError as exc:  # przejściowy błąd ładowania skryptów Tk
            last_error = exc
            time.sleep(0.2 * (attempt + 1))
    raise last_error  # type: ignore[misc]


def new_toplevel() -> tk.Toplevel:
    """Nowe, ukryte okno testowe; test wywołuje na nim ``destroy()``."""
    window = tk.Toplevel(shared_tk_root())
    window.withdraw()
    return window


def destroy_shared_root() -> None:
    global _root
    if _alive(_root):
        try:
            _root.destroy()
        except tk.TclError:
            pass
    _root = None
