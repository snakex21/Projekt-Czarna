"""
launcher/ui/styles.py — Konfiguracja stylów Tkinter/ttk.
Zablokowane piksele, nowoczesny wygląd kart i KPI.
"""

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

from ..config.settings import COLORS


# === Stałe odstępów (px) — siatka 4px ===
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 20
SPACING_XXL = 24

# === Kolory powierzchni ===
CARD_BG = '#ffffff'
SURFACE_BG = '#f0f2f5'
HEADER_BG = '#1a1d23'
HEADER_FG = '#ffffff'
HEADER_SUB_FG = '#94a3b8'
BORDER_COLOR = '#e2e5ea'
TEXT_PRIMARY = '#1a1d23'
TEXT_SECONDARY = '#64748b'
TEXT_MUTED = '#94a3b8'
KPI_BG = '#f8fafc'
KPI_BORDER = '#e2e5ea'
SEPARATOR_COLOR = '#e2e5ea'


def setup_app_styles(app: tk.Tk, base_font_size: int = None, ui_scale: float = 1.0):
    """
    Konfiguruje style i czcionki dla aplikacji Tkinter.

    Args:
        app: Główne okno Tk (lub Toplevel)
        base_font_size: Rozmiar czcionki (None = auto-detect na podstawie DPI)
        ui_scale: Skala interfejsu (0.85 - 2.0)
    """
    dpi = app.winfo_fpixels("1i")
    dpi_scale = dpi / 96

    ui_scale = max(0.85, min(float(ui_scale or 1.0), 2.0))
    # Efektywna skala jest absolutnym ustawieniem launchera.
    # Dzięki temu przy Windows 150% i UI 100% launcher wygląda jak 100%,
    # a nie jak 150%.
    effective_scale = ui_scale
    base_font_size = max(9, int(round(10 * effective_scale)))

    app.tk.call("tk", "scaling", effective_scale)

    # --- Czcionki ---
    default_font = tkfont.nametofont("TkDefaultFont")
    default_font.configure(family="Segoe UI", size=base_font_size)
    text_font = tkfont.nametofont("TkTextFont")
    text_font.configure(family="Segoe UI", size=base_font_size)
    menu_font = tkfont.nametofont("TkMenuFont")
    menu_font.configure(family="Segoe UI", size=base_font_size)
    heading_font = tkfont.nametofont("TkHeadingFont")
    heading_font.configure(family="Segoe UI", size=base_font_size + 1, weight="bold")
    caption_font = tkfont.nametofont("TkCaptionFont")
    caption_font.configure(family="Segoe UI", size=max(base_font_size - 1, 8))
    fixed_font = tkfont.nametofont("TkFixedFont")
    fixed_font.configure(family="Consolas", size=base_font_size)

    app.option_add("*Font", default_font)

    style = ttk.Style(app)
    style.theme_use("clam")

    # --- Skala DPI ---
    dpi = app.winfo_fpixels("1i")
    dpi_scale = dpi / 96
    button_padding = int(6 * dpi_scale) if dpi_scale > 1.25 else 8

    # ──────────────────────────────────────────────
    # PODSTAWOWE WIDGETY
    # ──────────────────────────────────────────────
    style.configure("TButton",
                     padding=button_padding,
                     relief="flat",
                     font=("Segoe UI", base_font_size))
    style.configure("TLabel",
                     font=("Segoe UI", base_font_size),
                     background=SURFACE_BG)
    style.configure("TFrame",
                     background=SURFACE_BG)
    style.configure("TLabelframe",
                     font=("Segoe UI", base_font_size, "bold"),
                     background=CARD_BG,
                     relief="solid",
                     borderwidth=1,
                     bordercolor=BORDER_COLOR)
    style.configure("TLabelframe.Label",
                     font=("Segoe UI", base_font_size, "bold"),
                     background=CARD_BG,
                     foreground=TEXT_PRIMARY)
    style.configure("TCheckbutton",
                     font=("Segoe UI", base_font_size),
                     background=CARD_BG)
    style.configure("Small.TCheckbutton",
                     font=("Segoe UI", max(base_font_size - 1, 8)),
                     background=CARD_BG)
    style.configure("TRadiobutton",
                     font=("Segoe UI", base_font_size),
                     background=CARD_BG)
    style.configure("TEntry",
                     font=("Segoe UI", base_font_size))
    style.configure("TCombobox",
                     font=("Segoe UI", base_font_size))
    style.configure("TMenubutton",
                     font=("Segoe UI", base_font_size))

    # ──────────────────────────────────────────────
    # NOTEBOOK (ZAKŁADKI)
    # ──────────────────────────────────────────────
    style.configure("TNotebook",
                     background=SURFACE_BG,
                     borderwidth=0,
                     tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab",
                     font=("Segoe UI", base_font_size),
                     padding=(SPACING_LG, SPACING_SM + 2),
                     background=SURFACE_BG,
                     foreground=TEXT_SECONDARY)
    style.map("TNotebook.Tab",
              background=[("selected", CARD_BG)],
              foreground=[("selected", TEXT_PRIMARY)])

    # ──────────────────────────────────────────────
    # PRZYCISKI KOLOROWE
    # ──────────────────────────────────────────────
    for name, color in [
        ("Primary", COLORS['primary']),
        ("Success", COLORS['success']),
        ("Danger", COLORS['danger']),
        ("Info", COLORS['info']),
        ("Warning", COLORS['warning']),
    ]:
        fg = "white" if name != "Warning" else "black"
        style.configure(f"{name}.TButton",
                         foreground=fg,
                         background=color,
                         font=("Segoe UI", base_font_size),
                         padding=(button_padding + 4, button_padding))
        darker = color.replace('f', 'd').replace('e', 'c')
        style.map(f"{name}.TButton",
                  background=[('active', darker), ('pressed', darker)])

    # Przycisk secondary (szary)
    style.configure("Secondary.TButton",
                     foreground=TEXT_SECONDARY,
                     background="#e9ecef",
                     font=("Segoe UI", base_font_size),
                     padding=(button_padding + 4, button_padding))
    style.map("Secondary.TButton",
              background=[('active', '#dee2e6'), ('pressed', '#dee2e6')])

    # ──────────────────────────────────────────────
    # STYLE POMOCNICZE
    # ──────────────────────────────────────────────
    style.configure("Link.TLabel",
                     foreground=COLORS['primary'],
                     font=("Segoe UI", base_font_size, "underline"))
    style.configure("Heading.TLabel",
                     font=("Segoe UI", base_font_size + 2, "bold"),
                     foreground=TEXT_PRIMARY)

    # ──────────────────────────────────────────────
    # KARTY (Card) — białe tło, cienka ramka
    # ──────────────────────────────────────────────
    style.configure("Card.TFrame",
                     background=CARD_BG)
    style.configure("CardInner.TFrame",
                     background=CARD_BG)

    style.configure("Card.TLabelframe",
                     background=CARD_BG,
                     relief="solid",
                     borderwidth=1,
                     bordercolor=BORDER_COLOR)
    style.configure("Card.TLabelframe.Label",
                     background=CARD_BG,
                     foreground=TEXT_PRIMARY,
                     font=("Segoe UI", base_font_size, "bold"))

    # ──────────────────────────────────────────────
    # KPI — boxy ze statystykami
    # ──────────────────────────────────────────────
    style.configure("KPI.TFrame",
                     background=KPI_BG,
                     relief="solid",
                     borderwidth=1,
                     bordercolor=KPI_BORDER)
    style.configure("KPITitle.TLabel",
                     background=KPI_BG,
                     foreground=TEXT_MUTED,
                     font=("Segoe UI", max(base_font_size - 2, 8)))
    style.configure("KPIValue.TLabel",
                     background=KPI_BG,
                     foreground=TEXT_PRIMARY,
                     font=("Segoe UI", base_font_size + 3, "bold"))
    style.configure("KPIStatus.TLabel",
                     background=KPI_BG,
                     foreground=TEXT_SECONDARY,
                     font=("Segoe UI", max(base_font_size - 1, 8)))

    # ──────────────────────────────────────────────
    # SEPARATOR
    # ──────────────────────────────────────────────
    style.configure("Separator.TFrame",
                     background=BORDER_COLOR,
                     height=1)

    # ──────────────────────────────────────────────
    # TREEVIEW
    # ──────────────────────────────────────────────
    row_height = int(base_font_size * 2.2)
    style.configure("Treeview",
                     rowheight=row_height,
                     font=("Segoe UI", base_font_size),
                     background=CARD_BG,
                     fieldbackground=CARD_BG)
    style.configure("Treeview.Heading",
                     font=("Segoe UI", base_font_size, "bold"))

    return style, base_font_size


def create_card(parent, text, padding=SPACING_MD):
    """Tworzy kartę (LabelFrame) z białym tłem i cienką ramką."""
    card = ttk.LabelFrame(parent, text=text, padding=padding, style="Card.TLabelframe")
    return card


def create_kpi(parent, title, value_var, status_var=None, width=140):
    """Tworzy box KPI z tytułem, wartością i opcjonalnym statusem."""
    kpi = tk.Frame(parent, bg=KPI_BG, highlightbackground=KPI_BORDER,
                    highlightthickness=1, width=width)
    kpi.pack_propagate(False)

    tk.Label(kpi, text=title, bg=KPI_BG, fg=TEXT_MUTED,
             font=("Segoe UI", 9), anchor="w").pack(
        fill=tk.X, padx=SPACING_SM, pady=(SPACING_SM, 0), anchor=tk.W)

    tk.Label(kpi, textvariable=value_var, bg=KPI_BG, fg=TEXT_PRIMARY,
             font=("Segoe UI", 15, "bold"), anchor="w").pack(
        fill=tk.X, padx=SPACING_SM, pady=(2, 0), anchor=tk.W)

    if status_var:
        tk.Label(kpi, textvariable=status_var, bg=KPI_BG, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9), anchor="w").pack(
            fill=tk.X, padx=SPACING_SM, pady=(0, SPACING_SM), anchor=tk.W)
    else:
        tk.Frame(kpi, bg=KPI_BG, height=SPACING_SM).pack()

    return kpi


def create_separator(parent):
    """Tworzy poziomą linię separującą."""
    sep = tk.Frame(parent, bg=BORDER_COLOR, height=1)
    return sep


def create_badge(parent, text, color, fg="white"):
    """Tworzy badge (mały kolorowy label)."""
    badge = tk.Label(parent, text=text, bg=color, fg=fg,
                      font=("Segoe UI", 9, "bold"),
                      padx=SPACING_SM, pady=SPACING_XS)
    return badge
