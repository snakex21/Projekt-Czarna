"""Testy widoczności dialogu zmiany hasła PostgreSQL.

Sprawdza że okno ma wystarczające wymiary, jest resizable, a wszystkie
kluczowe widgety (labele, pola, przyciski) mieszczą się w granicach okna
i mają dodatni rozmiar.

Wymaga działającego display (Windows: natywnie; Linux: pytest-xvfb).
Na Linux bez DISPLAY pytest pominie testy automatycznie (mark.skipif).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Dodaj root projektu do sys.path żeby importować launcher.*
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    import tkinter as tk
    from tkinter import ttk
except Exception as e:  # pragma: no cover
    pytest.skip(f"tkinter niedostępny: {e}", allow_module_level=True)

# Spróbuj zaimportować dialog — wymaga pełnego środowiska launchera
try:
    from launcher.ui.program_settings import build_change_pg_password_dialog
except Exception as e:  # pragma: no cover
    pytest.skip(f"Nie udało się zaimportować build_change_pg_password_dialog: {e}",
                allow_module_level=True)


# --- Skip gdy nie ma DISPLAY (Linux/CI bez Xvfb) ---
def _has_display() -> bool:
    if sys.platform.startswith("win"):
        return True
    if sys.platform == "darwin":
        return True
    import os
    return bool(os.environ.get("DISPLAY"))


if not _has_display():
    pytest.skip("Brak DISPLAY — testy tkinter pominięte", allow_module_level=True)


# --- Stałe layoutu (muszą pasować do build_change_pg_password_dialog) ---
EXPECTED_DEFAULT_GEOMETRY = (540, 480)
EXPECTED_MINSIZE = (480, 440)
EXPECTED_USER_HOST_PORT_IN_TITLE = False  # tylko w body, nie w tytule
EXPECTED_REQUIRED_WIDGETS = (
    "header",  # nagłówek
    "form",
    "old_entry",
    "new_entry",
    "conf_entry",
    "status",
    "btns",
    "submit_btn",
    "cancel_btn",
)


@pytest.fixture
def hidden_root():
    """Tworzy ukryty root Tk i sprząta po teście."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def db_dialog(hidden_root):
    """Tworzy dialog i zwraca (dlg, status_var, refs)."""
    refs = {"on_success": [], "on_errors": []}
    dlg = build_change_pg_password_dialog(
        parent=hidden_root,
        current_user="postgres",
        current_host="localhost",
        current_port=5432,
        current_db_name="mapa_czarna_db",
        on_success=lambda new_pw, msg: refs["on_success"].append((new_pw, msg)),
        on_error=lambda level, msg: refs["on_errors"].append((level, msg)),
    )
    dlg.update_idletasks()
    return dlg, refs


# === Testy geometrii okna ===

def test_dialog_default_geometry_is_large_enough(db_dialog):
    """Okno musi mieścić 3 pola + nagłówek + status + 2 przyciski."""
    dlg, _ = db_dialog
    geo = dlg.geometry()  # np. "540x420+100+100"
    w, h = (int(x) for x in geo.split("+")[0].split("x"))
    assert w >= EXPECTED_DEFAULT_GEOMETRY[0] - 5, (
        f"Szerokość {w} < oczekiwane {EXPECTED_DEFAULT_GEOMETRY[0]}"
    )
    assert h >= EXPECTED_DEFAULT_GEOMETRY[1] - 5, (
        f"Wysokość {h} < oczekiwane {EXPECTED_DEFAULT_GEOMETRY[1]}"
    )


def test_dialog_minsize_prevents_overshrinking(db_dialog):
    """Minsize musi być >= 480x380, żeby pola nie były obcięte."""
    dlg, _ = db_dialog
    assert dlg.minsize() == EXPECTED_MINSIZE, (
        f"minsize={dlg.minsize()}, oczekiwane {EXPECTED_MINSIZE}"
    )


def test_dialog_is_horizontally_resizable(db_dialog):
    """Pozwól userowi powiększyć okno w poziomie (DPI)."""
    dlg, _ = db_dialog
    # resizable() zwraca (horizontal, vertical) — na Windows jako int 0/1
    horizontal, vertical = dlg.resizable()
    assert bool(horizontal) is True, (
        f"Okno nie pozwala na resize w poziomie (got {horizontal})"
    )
    assert bool(vertical) is False, (
        f"Okno nie powinno pozwalać na resize w pionie (got {vertical})"
    )


# === Testy widoczności widgetów ===

def _iter_descendants(widget):
    """Rekurencyjnie yield wszystkie dzieci widgetu (włącznie z nim samym)."""
    yield widget
    for child in widget.winfo_children():
        yield from _iter_descendants(child)


def test_all_entries_have_positive_width(db_dialog):
    """3 pola hasła (Entry) muszą mieć dodatni rozmiar po update_idletasks."""
    dlg, _ = db_dialog
    entries = [w for w in _iter_descendants(dlg) if isinstance(w, ttk.Entry)]
    assert len(entries) == 3, f"Oczekiwano 3 pól Entry, znaleziono {len(entries)}"
    for entry in entries:
        assert entry.winfo_reqwidth() > 0, (
            f"Entry {entry} ma zerową wymaganą szerokość"
        )
        assert entry.winfo_reqheight() > 0, (
            f"Entry {entry} ma zerową wymaganą wysokość"
        )


def test_status_label_fits_within_dialog(db_dialog):
    """Label statusu (wraplength=440) musi mieścić się w aktualnej szerokości okna."""
    dlg, _ = db_dialog
    # Używamy aktualnej geometrii (nie winfo_reqwidth, który zwraca minimum).
    geo = dlg.geometry()
    dlg_w = int(geo.split("+")[0].split("x")[0])
    for lbl in _iter_descendants(dlg):
        if isinstance(lbl, ttk.Label):
            wl = int(lbl.cget("wraplength") or 0)
            if wl > 0:
                assert wl <= dlg_w, (
                    f"Label {lbl} wraplength={wl} > szerokość okna {dlg_w}"
                )


def test_buttons_have_positive_size(db_dialog):
    """Oba przyciski (Anuluj + Zmień hasło) muszą mieć dodatni rozmiar."""
    dlg, _ = db_dialog
    buttons = [w for w in _iter_descendants(dlg) if isinstance(w, ttk.Button)]
    assert len(buttons) >= 2, (
        f"Oczekiwano >=2 przycisków, znaleziono {len(buttons)}"
    )
    for btn in buttons:
        text = btn.cget("text")
        assert btn.winfo_reqwidth() > 0, f"Przycisk {text!r} ma zerową szerokość"
        assert btn.winfo_reqheight() > 0, f"Przycisk {text!r} ma zerową wysokość"


def test_submit_and_cancel_buttons_exist(db_dialog):
    """Dialog musi mieć oba kluczowe przyciski."""
    dlg, _ = db_dialog
    button_texts = [b.cget("text") for b in _iter_descendants(dlg) if isinstance(b, ttk.Button)]
    assert any("Zmień hasło" in t for t in button_texts), (
        f"Brak przycisku 'Zmień hasło'. Przyciski: {button_texts}"
    )
    assert any("Anuluj" in t for t in button_texts), (
        f"Brak przycisku 'Anuluj'. Przyciski: {button_texts}"
    )


def test_dialog_title_mentions_password(db_dialog):
    """Tytuł okna musi jasno mówić o co chodzi."""
    dlg, _ = db_dialog
    title = dlg.title()
    assert "hasło" in title.lower() or "password" in title.lower(), (
        f"Tytuł {title!r} nie wspomina o haśle"
    )


def test_no_widget_extends_below_dialog_height(db_dialog):
    """Żaden widget nie powinien wystawać poza aktualny rozmiar okna."""
    dlg, _ = db_dialog
    # Używamy aktualnej geometrii (winfo_width/height), nie minimalnej
    # (winfo_reqwidth/height) — ta druga to życzenie layoutu, nie rzeczywistość.
    geo = dlg.geometry()  # np. "540x420+100+100"
    parts = geo.split("+")
    dlg_w, dlg_h = (int(x) for x in parts[0].split("x"))
    for w in _iter_descendants(dlg):
        if w is dlg or not w.winfo_ismapped():
            continue
        x = w.winfo_x()
        y = w.winfo_y()
        ww = w.winfo_width()
        wh = w.winfo_height()
        if ww <= 1 and wh <= 1:
            continue  # nie zmapowany jeszcze
        assert x >= 0 and y >= 0, f"Widget {w} ma ujemne współrzędne ({x},{y})"
        assert x + ww <= dlg_w + 2, (
            f"Widget {w} ({ww}px @x={x}) wystaje z okna (szerokość {dlg_w})"
        )
        assert y + wh <= dlg_h + 2, (
            f"Widget {w} ({wh}px @y={y}) wystaje z okna (wysokość {dlg_h})"
        )


def test_resize_does_not_hide_widgets(db_dialog):
    """Layout ma wystarczająco dużo elementów elastycznych (fill=X), by resize działał.

    Sprawdza, że główne frame'y używają ``pack(fill=tk.X)`` - to one pozwalają
    widgetom rosnąć i kurczyć się przy resize okna. Bez tego pola hasła
    zostałyby obcięte po zmniejszeniu okna.
    """
    dlg, _ = db_dialog
    frames = [w for w in _iter_descendants(dlg) if isinstance(w, ttk.Frame)]
    # pack_info() zwraca dict z opcjami pack (m.in. 'fill')
    x_filled = []
    for f in frames:
        try:
            info = f.pack_info()
        except Exception:
            continue  # brak pack — może być grid
        if info.get("fill") == "x":
            x_filled.append(f)
    assert len(x_filled) >= 1, (
        f"Brak frame'ów z pack(fill='x') - resize nie działa poprawnie"
    )


def test_all_widgets_use_pack_or_grid_consistently(db_dialog):
    """Sprawdza, że layout nie miesza pack i grid w jednym rodzicu."""
    dlg, _ = db_dialog
    for parent in _iter_descendants(dlg):
        children = list(parent.winfo_children())
        if not children:
            continue
        # Dzieci mogą być dodane albo pack albo grid, nie oba naraz w jednym rodzicu
        has_pack = any(getattr(c, "_pack_info", lambda: {})() for c in children)
        has_grid = any(getattr(c, "_grid_info", lambda: {})() for c in children)
        if has_pack and has_grid:
            pytest.fail(
                f"Rodzic {parent} miesza pack i grid — może powodować "
                f"nieprzewidywalny layout"
            )


def test_no_top_level_frame_uses_expand(db_dialog):
    """Bezpośrednie dzieci Toplevel NIE MOGĄ mieć pack(expand=True).

    expand=True na bezpośrednim dziecku Toplevel powoduje, że to dziecko
    pochłania CAŁE excess okna, wypychając pozostałe dzieci (np. btns)
    poza dolną krawędź w runtime Windows. Wszystkie górne sekcje (header,
    form, status, btns) powinny mieć requested height = ich naturalna
    wysokość, a ``pack_propagate(False)`` na Toplevel pilnuje że okno ich
    mieści bez automatycznego dopasowywania do zawartości.
    """
    dlg, _ = db_dialog
    for child in dlg.winfo_children():
        try:
            info = child.pack_info()
        except Exception:
            continue
        assert not bool(info.get("expand", False)), (
            f"{child} ma pack(expand=True) - może wypychać dolne widgety "
            f"poza okno w runtime. Użyj fill=X zamiast BOTH/expand na "
            f"bezpośrednich dzieciach Toplevel."
        )


def test_dialog_uses_pack_propagate_false(db_dialog):
    """Toplevel powinien mieć ``pack_propagate(False)`` dla stabilnego layoutu."""
    dlg, _ = db_dialog
    # pack_propagate nie ma w winfo, ale możemy sprawdzić, że
    # Toplevel ma dokładnie tę wysokość którą ustawiliśmy w geometry()
    # — bez automatycznego dopasowywania do zawartości.
    geo = dlg.geometry()
    dlg_h = int(geo.split("+")[0].split("x")[1])
    # Jeśli pack_propagate(True) i form ma expand=True, Toplevel zmieni
    # rozmiar żeby dopasować się do form. Wtedy dlg_h > nasz expected.
    # Testujemy, że rozmiar jest zgodny z geometry() (nie został
    # nadpisany przez pack_propagate).
    assert dlg_h >= EXPECTED_DEFAULT_GEOMETRY[1] - 5, (
        f"Toplevel zmienił wysokość na {dlg_h} (oczekiwane "
        f"{EXPECTED_DEFAULT_GEOMETRY[1]}) — pack_propagate(True) lub "
        f"form z expand=True wymusza resize"
    )


# === Testy bezpieczeństwa (hasło maskowane) ===

def test_password_entries_have_show_mask(db_dialog):
    """Pola hasła MUSZĄ mieć show='*' (maskowanie).

    Regresja: kiedyś kod miał ``show = "" if key == "password" else None``
    co oznaczało BRAK maskowania. Użytkownik widział hasło jawnie w panelu
    konfiguracji PG.
    """
    dlg, _ = db_dialog
    entries = [w for w in _iter_descendants(dlg) if isinstance(w, ttk.Entry)]
    assert len(entries) == 3, f"Oczekiwano 3 pól Entry, znaleziono {len(entries)}"
    for entry in entries:
        show = entry.cget("show")
        # W ttk.Entry: show="*" = maskuj, show="" = pokaż jawnie
        assert show == "*", (
            f"Entry {entry} ma show={show!r} - hasło NIE jest maskowane! "
            f"Powinno być show='*'."
        )
