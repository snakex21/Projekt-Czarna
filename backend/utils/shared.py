"""Wspólne funkcje pomocnicze używane przez wiele modułów backendu."""
from datetime import datetime
import unicodedata
import sys


def extract_year(value):
    """Wyciaga rok z dicta, inta lub stringa. Zwraca int lub None."""
    if isinstance(value, dict):
        value = value.get("year")
    if isinstance(value, int) and 0 < value <= datetime.now().year:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        year = int(value.strip())
        if 0 < year <= datetime.now().year:
            return year
    return None


def parse_polish_date(date_str):
    """Konwertuje polską datę tekstową na format YYYY-MM-DD.
    Obsluguje format: '15 maja 1930 rok'."""
    if not date_str:
        return None
    months = {
        "stycznia": "01", "styczeń": "01",
        "lutego": "02", "luty": "02",
        "marca": "03", "marzec": "03",
        "kwietnia": "04", "kwiecień": "04",
        "maja": "05", "maj": "05",
        "czerwca": "06", "czerwiec": "06",
        "lipca": "07", "lipiec": "07",
        "sierpnia": "08", "sierpień": "08",
        "września": "09", "wrzesnia": "09", "wrzesień": "09",
        "października": "10", "pazdziernika": "10", "październik": "10",
        "listopada": "11", "listopad": "11",
        "grudnia": "12", "grudzień": "12",
    }
    try:
        parts = date_str.lower().replace("rok", "").strip().split()
        if len(parts) < 3:
            return None
        day = parts[0].zfill(2)
        month = months.get(parts[1])
        year = parts[2]
        if not month or not year.isdigit():
            return None
        return f"{year}-{month}-{day}"
    except Exception:
        return None


def is_real_ownership(value):
    """Porównuje typ_posiadania odpornie na brak polskich znaków."""
    if not value:
        return False
    text = str(value).strip().lower()
    # Translacja polskich znaków na ASCII (ł/ą/ę/ż/ź/ń/ó/ś/ć)
    # unicodedata NFKD nie dekomponuje tych znaków na ASCII, więc potrzebna
    # ręczna mapa. Dzięki temu 'własność rzeczywista' i 'WLASNOSC RZECZYWISTA'
    # dają ten sam wynik.
    pl_to_ascii = {
        "\u0105": "a",  # ą
        "\u0107": "c",  # ć
        "\u0119": "e",  # ę
        "\u0142": "l",  # ł
        "\u0144": "n",  # ń
        "\u00f3": "o",  # ó
        "\u015b": "s",  # ś
        "\u017a": "z",  # ź
        "\u017c": "z",  # ż
    }
    for pl, asc in pl_to_ascii.items():
        text = text.replace(pl, asc)
    return text == "wlasnosc rzeczywista"


def fix_windows_console_encoding():
    """Naprawia kodowanie konsoli Windows dla emoji i polskich znaków."""
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
