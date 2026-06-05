"""Pomocnicze funkcje skalowania UI launchera."""

from __future__ import annotations


__all__ = ["get_effective_ui_scale", "scale_window", "scale_font", "scale_wrap"]


def get_effective_ui_scale(widget, default=1.0):
    """Znajduje ui_scale w rodzicu, parent_app albo w łańcuchu masterów."""
    current = widget
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if hasattr(current, 'ui_scale'):
            try:
                return max(0.85, min(float(getattr(current, 'ui_scale') or default), 2.0))
            except (TypeError, ValueError):
                return default
        parent_app = getattr(current, 'parent_app', None)
        if parent_app is not None and hasattr(parent_app, 'ui_scale'):
            try:
                return max(0.85, min(float(getattr(parent_app, 'ui_scale') or default), 2.0))
            except (TypeError, ValueError):
                return default
        current = getattr(current, 'master', None)
    return default


def scale_window(window, parent, base_w, base_h, resizable=True):
    """
    Skaluje rozmiar i minsize okna Toplevel na podstawie DPI systemu
    oraz ui_scale rodzica. Zwraca krotkę (scale_factor, width, height).

    Użycie:
        scale, w, h = scale_window(self, parent, 800, 600)
    """
    scale = get_effective_ui_scale(parent)
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    w = min(int(base_w * scale), max(sw - 80, base_w))
    h = min(int(base_h * scale), max(sh - 80, base_h))
    window.geometry(f"{w}x{h}")
    window.minsize(w, h)
    if resizable:
        window.resizable(True, True)
    return scale, w, h


def scale_font(window_or_parent, base_size, weight="normal"):
    """Zwraca tuple czcionki skalowanej wg DPI/ui_scale."""
    parent = window_or_parent
    scale = get_effective_ui_scale(parent)
    size = max(8, int(round(base_size * scale)))
    if weight and weight != "normal":
        return ("Segoe UI", size, weight)
    return ("Segoe UI", size)


def scale_wrap(window_or_parent, base_wrap):
    """Zwraca skalowany wraplength."""
    parent = window_or_parent
    scale = get_effective_ui_scale(parent)
    return max(200, int(round(base_wrap * scale)))
