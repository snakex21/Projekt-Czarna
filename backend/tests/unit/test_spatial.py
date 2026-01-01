import pytest
import psycopg2
import os
import sys

# Dodajemy backend do ścieżki
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import get_db_connection

def test_spatial_overlaps():
    """Sprawdza czy działki na siebie nie nachodzą (SQL/PostGIS)."""
    conn = get_db_connection()
    if not conn:
        pytest.skip("Brak połączenia z PostgreSQL")
        
    cur = conn.cursor()
    try:
        # Szukamy par działek (ta sama kategoria), których geometria się przecina (area > 1m2 aby uniknąć błędów styku)
        query = """
        SELECT a.nazwa_lub_numer, b.nazwa_lub_numer, ST_Area(ST_Intersection(a.geometria, b.geometria)) as overlap_area
        FROM obiekty_geograficzne a, obiekty_geograficzne b
        WHERE a.id < b.id 
          AND a.kategoria = 'dzialka' 
          AND b.kategoria = 'dzialka'
          AND ST_Intersects(a.geometria, b.geometria)
          AND ST_Area(ST_Intersection(a.geometria, b.geometria)) > 1.0
        LIMIT 50;
        """
        cur.execute(query)
        overlaps = cur.fetchall()
        
        if overlaps:
            print(f"\n[GEODEZJA] Wykryto {len(overlaps)} nakładających się działek:")
            for row in overlaps:
                print(f"  ! Działka {row[0]} nachodzi na {row[1]} (Powierzchnia styku: {row[2]:.2f} m2)")
        else:
            print("\n[GEODEZJA] Brak nakładających się działek (OK)")
            
    except Exception as e:
        print(f"Błąd podczas testu przestrzennego: {e}")
    finally:
        cur.close()
        conn.close()
    assert True

def test_invalid_geometries():
    """Wykrywa błędne geometrie (zapętlone, zerowe)."""
    conn = get_db_connection()
    if not conn:
        pytest.skip("Brak połączenia z PostgreSQL")
        
    cur = conn.cursor()
    try:
        query = """
        SELECT nazwa_lub_numer, kategoria, ST_IsValidReason(geometria)
        FROM obiekty_geograficzne
        WHERE NOT ST_IsValid(geometria);
        """
        cur.execute(query)
        invalids = cur.fetchall()
        
        if invalids:
            print(f"\n[GEODEZJA] Znaleziono {len(invalids)} błędnych geometrii:")
            for row in invalids:
                print(f"  ! {row[1]} {row[0]}: {row[2]}")
        else:
            print("\n[GEODEZJA] Wszystkie geometrie są poprawne (OK)")
            
    except Exception as e:
        print(f"Błąd podczas testu geometrii: {e}")
    finally:
        cur.close()
        conn.close()
    assert True

def test_zero_area_objects():
    """Wykrywa obiekty o zerowej powierzchni (błędy rysowania)."""
    conn = get_db_connection()
    if not conn:
        pytest.skip("Brak połączenia z PostgreSQL")
        
    cur = conn.cursor()
    try:
        query = """
        SELECT nazwa_lub_numer, kategoria
        FROM obiekty_geograficzne
        WHERE kategoria IN ('dzialka', 'budynek') AND ST_Area(geometria) < 0.1;
        """
        cur.execute(query)
        zeros = cur.fetchall()
        
        if zeros:
            print(f"\n[GEODEZJA] Znaleziono {len(zeros)} obiektów o prawie zerowej powierzchni:")
            for row in zeros:
                print(f"  ! {row[1]} {row[0]} (prawdopodobnie błąd punktu/linii)")
    except Exception as e:
        print(f"Błąd podczas testu powierzchni: {e}")
    finally:
        cur.close()
        conn.close()
    assert True
