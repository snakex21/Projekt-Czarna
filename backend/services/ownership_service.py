"""Serwis wlascicieli — formatowanie dzialek, linki protokolow, konfiguracja."""
import json
import re
from pathlib import Path
from ..config import ACTIVE_LOCATION, BACKUP_DIR
from ..utils import is_real_ownership
from .geo_utils import parse_geom, geom_area_m2, line_length_m


def protocol_links_to_html(value):
    """Zamienia [[Tekst|Klucz]] na linki do protokołów, zachowując zwykły tekst."""
    if not value:
        return ""
    import html
    escaped = html.escape(str(value).replace("\\n", "\n"))
    escaped = escaped.replace("\n", "<br>")
    return re.sub(
        r"\[\[(.*?)\|(.*?)\]\]",
        lambda m: f'<a href="protokol.html?ownerId={html.escape(m.group(2))}">{html.escape(m.group(1))}</a>',
        escaped,
    )


def get_location_protocol_config():
    """Czyta nazwę gminy/miejsca protokołu z konfiguracji aktywnej miejscowości."""
    config_path = BACKUP_DIR / ACTIVE_LOCATION / "launcher_db_config.json"
    if not config_path.exists():
        return {"gmina_katastralna": ACTIVE_LOCATION, "miejscowosc_protokolu": ""}
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        loc = raw.get("default_location", raw)
        return {
            "gmina_katastralna": loc.get("gmina_katastralna") or loc.get("name") or ACTIVE_LOCATION,
            "miejscowosc_protokolu": loc.get("miejscowosc_protokolu") or loc.get("region") or "",
        }
    except Exception:
        return {"gmina_katastralna": ACTIVE_LOCATION, "miejscowosc_protokolu": ""}


def format_plot(row):
    geom = parse_geom(row.get("geometria"))
    kategoria = row.get("kategoria") or "nieznana"
    is_line = kategoria in ("droga", "rzeka") or (geom and geom.get("type") in ("LineString", "MultiLineString"))
    return {
        "id": row.get("id"),
        "nazwa_lub_numer": row.get("nazwa_lub_numer"),
        "kategoria": kategoria,
        "powierzchnia_m2": 0 if is_line else round(geom_area_m2(geom), 2),
        "dlugosc_m": round(line_length_m(geom), 2) if is_line else 0,
        "typ_posiadania": row.get("typ_posiadania"),
    }
