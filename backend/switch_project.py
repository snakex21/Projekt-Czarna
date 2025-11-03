#!/usr/bin/env python3
"""
================================================================================
Skrypt: switch_project.py
Opis: Narzędzie CLI do przełączania aktywnego projektu
================================================================================
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "dbname": os.getenv("DB_NAME", "mapa_czarna_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "1234"),
    "port": os.getenv("DB_PORT", "5432")
}

ACTIVE_PROJECT_FILE = os.path.join(os.path.dirname(__file__), '.active_project')

def list_projects():
    """Wyświetla listę dostępnych projektów."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT short_code, nazwa, kontekst_czasowy, status
                FROM projects
                ORDER BY status DESC, nazwa ASC
            """)
            projects = cur.fetchall()
        
        conn.close()
        
        # Odczytaj aktywny projekt
        active = get_active_project()
        
        print("\n" + "=" * 70)
        print("  DOSTĘPNE PROJEKTY")
        print("=" * 70)
        print(f"{'Kod':<15} {'Nazwa':<25} {'Kontekst':<15} {'Status':<10}")
        print("-" * 70)
        
        for proj in projects:
            marker = "⭐" if proj['short_code'] == active else "  "
            print(f"{marker} {proj['short_code']:<13} {proj['nazwa']:<25} {proj['kontekst_czasowy'] or '':<15} {proj['status']:<10}")
        
        print("=" * 70)
        print(f"\n✅ Aktywny projekt: {active}\n")
        
        return projects
    
    except Exception as e:
        print(f"❌ Błąd: {e}")
        sys.exit(1)

def get_active_project():
    """Zwraca kod aktywnego projektu."""
    if os.path.exists(ACTIVE_PROJECT_FILE):
        with open(ACTIVE_PROJECT_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return 'czarna'

def switch_project(project_code):
    """Przełącza na wybrany projekt."""
    # Sprawdź czy projekt istnieje
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM projects WHERE short_code = %s", (project_code,))
            project = cur.fetchone()
        
        conn.close()
        
        if not project:
            print(f"❌ Projekt '{project_code}' nie istnieje w bazie danych")
            print("\nDostępne projekty:")
            list_projects()
            sys.exit(1)
        
        # Zapisz aktywny projekt
        with open(ACTIVE_PROJECT_FILE, 'w', encoding='utf-8') as f:
            f.write(project_code)
        
        print("\n" + "=" * 70)
        print("  PROJEKT PRZEŁĄCZONY")
        print("=" * 70)
        print(f"Nowy aktywny projekt: {project['nazwa']} ({project_code})")
        print(f"Kontekst: {project['kontekst_czasowy']}")
        print(f"Region: {project['region']}")
        print("=" * 70)
        print("\n⚠️  WAŻNE: Zrestartuj serwer backend, aby zmiany zostały zastosowane!\n")
        
        return True
    
    except Exception as e:
        print(f"❌ Błąd: {e}")
        sys.exit(1)

def show_usage():
    """Wyświetla instrukcję użycia."""
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║  NARZĘDZIE PRZEŁĄCZANIA PROJEKTÓW                                        ║
╚══════════════════════════════════════════════════════════════════════════╝

UŻYCIE:
    python switch_project.py [opcja] [kod_projektu]

OPCJE:
    list                    - Wyświetl listę wszystkich projektów
    switch <kod>           - Przełącz na projekt o podanym kodzie
    current                - Wyświetl aktywny projekt
    help                   - Wyświetl tę pomoc

PRZYKŁADY:
    python switch_project.py list
    python switch_project.py switch borowa
    python switch_project.py current

UWAGA:
    Po przełączeniu projektu należy zrestartować serwer backend!
    """)

def main():
    """Główna funkcja programu."""
    if len(sys.argv) < 2:
        show_usage()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == 'list':
        list_projects()
    
    elif command == 'switch':
        if len(sys.argv) < 3:
            print("❌ Błąd: Nie podano kodu projektu")
            print("Użycie: python switch_project.py switch <kod_projektu>")
            sys.exit(1)
        
        project_code = sys.argv[2]
        switch_project(project_code)
    
    elif command == 'current':
        active = get_active_project()
        print(f"\n✅ Aktywny projekt: {active}\n")
    
    elif command in ['help', '--help', '-h']:
        show_usage()
    
    else:
        print(f"❌ Nieznana komenda: {command}")
        show_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
