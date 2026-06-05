"""Geometryczne funkcje pomocnicze — parsowanie GeoJSON, obliczanie powierzchni i dlugosci."""
import math
import json


def parse_geom(value):
    """Parsuje geometrie GeoJSON z stringa lub slownika."""
    if not value:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


def iter_coords(geom):
    """Iteruje po wszystkich wspolrzednych w geometrii GeoJSON."""
    if not geom:
        return
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    if gtype == "Point":
        yield coords
    elif gtype == "LineString":
        yield from coords
    elif gtype == "MultiLineString":
        for line in coords:
            yield from line
    elif gtype == "Polygon":
        for ring in coords:
            yield from ring
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                yield from ring


def project(lng, lat):
    """Przybliżona projekcja geograficzna na metry (dla okolic 50.06°N)."""
    lat0 = 50.06058
    return (lng * 111_320 * math.cos(math.radians(lat0)), lat * 110_540)


def polygon_area_m2(ring):
    """Pole powierzchni pierscienia wielokata w metrach kwadratowych (Shoelace)."""
    if not ring or len(ring) < 4:
        return 0.0
    pts = [project(c[0], c[1]) for c in ring]
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def geom_area_m2(geom):
    """Pole powierzchni geometrii GeoJSON w m²."""
    if not geom:
        return 0.0
    if geom.get("type") == "Polygon":
        rings = geom.get("coordinates") or []
        return polygon_area_m2(rings[0]) if rings else 0.0
    if geom.get("type") == "MultiPolygon":
        return sum(polygon_area_m2(poly[0]) for poly in (geom.get("coordinates") or []) if poly)
    return 0.0


def line_length_m(geom):
    """Dlugosc geometrii liniowej GeoJSON w metrach."""
    if not geom:
        return 0.0
    lines = []
    if geom.get("type") == "LineString":
        lines = [geom.get("coordinates") or []]
    elif geom.get("type") == "MultiLineString":
        lines = geom.get("coordinates") or []
    total = 0.0
    for line in lines:
        pts = [project(c[0], c[1]) for c in line]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            total += math.hypot(x2 - x1, y2 - y1)
    return total
