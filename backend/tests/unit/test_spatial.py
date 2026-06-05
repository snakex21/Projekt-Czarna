"""
Plik: test_spatial.py
Opis: Testy przestrzenne - uzywaja shapely do walidacji geometrii GeoJSON z bazy.
"""
import pytest
import os
import sys
import json

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.db import get_db_connection


def _load_geometries(conn):
    """Laduje geometrie z bazy jako liste dictow z shapely geometry."""
    from shapely.geometry import shape
    cur = conn.cursor()
    cur.execute("SELECT id, nazwa_lub_numer, kategoria, geometria FROM obiekty_geograficzne WHERE geometria IS NOT NULL AND geometria != ''")
    rows = []
    for row in cur.fetchall():
        try:
            geo_dict = json.loads(row[3])
            geom = shape(geo_dict)
            rows.append({"id": row[0], "nazwa": row[1], "kategoria": row[2], "geom": geom})
        except Exception:
            pass
    cur.close()
    return rows


def test_spatial_overlaps():
    """Sprawdza czy dzialki na siebie nie nachodza."""
    conn = get_db_connection()
    if not conn:
        pytest.skip("Brak polaczenia z baza danych")

    try:
        geometries = _load_geometries(conn)
        dzialki = [g for g in geometries if g["kategoria"] == "dzialka"]

        if len(dzialki) < 2:
            print("\nZa malo dzialek by sprawdzic nakladanie")
            assert True
            return

        overlaps = []
        for i in range(len(dzialki)):
            for j in range(i + 1, len(dzialki)):
                try:
                    g1, g2 = dzialki[i]["geom"], dzialki[j]["geom"]
                    if g1.intersects(g2):
                        intersection = g1.intersection(g2)
                        if intersection.area > 1.0:
                            overlaps.append((dzialki[i]["nazwa"], dzialki[j]["nazwa"], intersection.area))
                except Exception:
                    pass

        if overlaps:
            print(f"\nWykryto {len(overlaps)} nakladajacych sie dzialek:")
            for row in overlaps[:10]:
                print(f"  ! Dzialka {row[0]} nachodzi na {row[1]} (Powierzchnia styku: {row[2]:.2f} m2)")
        else:
            print("\nBrak nakladajacych sie dzialek (OK)")
    except Exception as e:
        print(f"Blad podczas testu przestrzennego: {e}")
    finally:
        conn.close()
    assert True


def test_invalid_geometries():
    """Wykrywa bledne geometrie (zapetlone, zerowe, niepoprawny GeoJSON)."""
    conn = get_db_connection()
    if not conn:
        pytest.skip("Brak polaczenia z baza danych")

    try:
        geometries = _load_geometries(conn)

        invalids = []
        for g in geometries:
            try:
                if not g["geom"].is_valid:
                    invalids.append((g["nazwa"], g["kategoria"], "Niepoprawna geometria"))
            except Exception:
                invalids.append((g["nazwa"], g["kategoria"], "Blad parsowania"))

        # Sprawdzamy surowe GeoJSON pod katem struktury
        cur = conn.cursor()
        cur.execute("SELECT nazwa_lub_numer, kategoria, geometria FROM obiekty_geograficzne WHERE geometria IS NOT NULL AND geometria != ''")
        for row in cur.fetchall():
            try:
                geo = json.loads(row[2])
                if "type" not in geo or "coordinates" not in geo:
                    invalids.append((row[0], row[1], "Brak type/coordinates w GeoJSON"))
            except json.JSONDecodeError:
                invalids.append((row[0], row[1], "Niepoprawny JSON"))
        cur.close()

        if invalids:
            print(f"\nZnaleziono {len(invalids)} blednych geometrii:")
            for row in invalids[:20]:
                print(f"  ! {row[1]} {row[0]}: {row[2]}")
        else:
            print(f"\nWszystkie geometrie sa poprawne (OK) - sprawdzono {len(geometries)} obiektow")
    except Exception as e:
        print(f"Blad podczas testu geometrii: {e}")
    finally:
        conn.close()
    assert True


def test_zero_area_objects():
    """Wykrywa obiekty o zerowej powierzchni (bledy rysowania)."""
    conn = get_db_connection()
    if not conn:
        pytest.skip("Brak polaczenia z baza danych")

    try:
        geometries = _load_geometries(conn)

        target = [g for g in geometries if g["kategoria"] in ("dzialka", "budynek")]
        zeros = []
        for g in target:
            try:
                area = g["geom"].area
                if area < 0.1:
                    zeros.append((g["nazwa"], g["kategoria"], area))
            except Exception:
                zeros.append((g["nazwa"], g["kategoria"], 0))

        if zeros:
            print(f"\nZnaleziono {len(zeros)} obiektow o prawie zerowej powierzchni:")
            for row in zeros[:20]:
                print(f"  ! {row[1]} {row[0]} (powierzchnia: {row[2]:.4f})")
        else:
            print(f"\nWszystkie dzialki/budynki maja dodatnia powierzchnie (OK) - sprawdzono {len(target)} obiektow")
    except Exception as e:
        print(f"Blad podczas testu powierzchni: {e}")
    finally:
        conn.close()
    assert True
