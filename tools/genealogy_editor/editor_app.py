"""
Plik: editor_app.py
Opis: Aplikacja Flask do edycji danych genealogicznych.
      Zapewnia API REST, zarządzanie kopiami zapasowymi oraz integrację z głównym edytorem.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
import json
import os
import re
import shutil
import tkinter.font as tkfont
import subprocess
import sys, ctypes, platform
import webbrowser
import threading
from flask import Flask, render_template, jsonify, request, send_from_directory
import os
import threading
import time
from flask import request, Flask
from collections import Counter
import requests
import socket
from datetime import datetime, timedelta
import sqlite3
import psycopg2

# ==========================================================================
# KONFIGURACJA ŚCIEŻEK
# ==========================================================================

# Struktura folderów wymaga przejścia przez trzy poziomy katalogów nadrzędnych
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Funkcja do określenia aktywnej miejscowości
def get_active_location_backup_folder():
    """Zwraca folder backup aktywnej miejscowości."""
    # Najpierw spróbuj PostgreSQL (baza launcher)
    try:
        launcher_db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "dbname": "mapa_launcher_db",
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "1234"),
            "port": os.getenv("DB_PORT", "5432"),
            "client_encoding": "UTF8"
        }

        conn = psycopg2.connect(**launcher_db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM locations WHERE active = TRUE LIMIT 1")
        result = cursor.fetchone()
        conn.close()

        if result:
            location_name = result[0]
            backup_folder = os.path.join(BASE_DIR, "backup", location_name)
            print(f"✅ Edytor genealogii - aktywna miejscowość: {location_name}")
            return backup_folder
    except Exception as e:
        print(f"⚠️ PostgreSQL niedostępny, próbuję SQLite: {e}")

    # Fallback do SQLite jeśli PostgreSQL nie działa
    launcher_dir = os.path.join(BASE_DIR, "launcher")
    locations_db_path = os.path.join(launcher_dir, "locations.db")

    if os.path.exists(locations_db_path):
        try:
            conn = sqlite3.connect(locations_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM locations WHERE active = 1")
            result = cursor.fetchone()
            conn.close()

            if result:
                location_name = result[0]
                backup_folder = os.path.join(BASE_DIR, "backup", location_name)
                print(f"✅ Edytor genealogii (SQLite) - aktywna miejscowość: {location_name}")
                return backup_folder
        except Exception as e:
            print(f"⚠️ Błąd podczas odczytu SQLite: {e}")

    # Fallback do domyślnej lokalizacji
    print(f"⚠️ Używam domyślnej lokalizacji backup")
    return os.path.join(BASE_DIR, "backup")

def ensure_location_data_files(location_folder):
    """Tworzy wymagane pliki JSON dla miejscowości jeśli nie istnieją."""
    data_files = {
        'demografia.json': [],
        'genealogia.json': {"persons": []},
        'map_config.json': {
            "calibration": {"sw": {"lat": 0, "lng": 0}, "ne": {"lat": 0, "lng": 0}},
            "defaults": {"center": {"lat": 0, "lng": 0}, "zoom": 15}
        },
        'owner_data_to_import.json': {},
        'parcels_data.json': {}
    }

    created_files = []
    for filename, structure in data_files.items():
        file_path = os.path.join(location_folder, filename)
        if not os.path.exists(file_path):
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(structure, f, ensure_ascii=False, indent=4)
                created_files.append(filename)
            except Exception as e:
                print(f"⚠️ Błąd tworzenia {filename}: {e}")

    if created_files:
        print(f"✅ Utworzono brakujące pliki: {', '.join(created_files)}")

# Ścieżki do plików danych
BACKUP_FOLDER = get_active_location_backup_folder()
ensure_location_data_files(BACKUP_FOLDER)  # Upewnij się że pliki istnieją

GENEALOGIA_JSON_PATH = os.path.join(BACKUP_FOLDER, "genealogia.json")
OWNER_JSON_PATH = os.path.join(BACKUP_FOLDER, "owner_data_to_import.json")

# ==========================================================================
# INICJALIZACJA APLIKACJI FLASK
# ==========================================================================

app = Flask(__name__, template_folder="templates", static_folder="static")

# Stan głównego edytora - wykorzystywany do koordynacji między edytorami
EDITOR_STATUS = {
    "is_running": False,
    "address": None,
    "port": None,
    "last_heartbeat": None
}

# ==========================================================================
# FUNKCJE POMOCNICZE
# ==========================================================================

def is_port_open(host, port):
    """
    Sprawdza dostępność portu TCP.
    
    Args:
        host: Adres IP lub nazwa hosta
        port: Numer portu TCP
        
    Returns:
        bool: True jeśli port otwarty, False w przeciwnym wypadku
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

# ==========================================================================
# API PROTOKOŁÓW
# ==========================================================================

@app.route("/api/protocols", methods=["GET"])
def get_protocols_data():
    """Zwraca uproszczoną listę protokołów dla frontendu."""
    if not os.path.exists(OWNER_JSON_PATH):
        return jsonify([])
    
    try:
        with open(OWNER_JSON_PATH, "r", encoding="utf-8") as f:
            owner_data = json.load(f)

        protocol_list = [
            {
                "key": key,
                "name": data.get("ownerName", "Brak nazwy"),
                "orderNumber": data.get("orderNumber", "N/A"),
            }
            for key, data in owner_data.items()
        ]
        return jsonify(protocol_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================================================
# API DANYCH GENEALOGICZNYCH
# ==========================================================================

@app.route("/api/genealogia", methods=["GET"])
def get_genealogia_data():
    """Pobiera dane genealogiczne i przekształca je dla edytora."""
    if not os.path.exists(GENEALOGIA_JSON_PATH):
        return jsonify([])
    
    try:
        with open(GENEALOGIA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Przekształcenie formatu danych
        if "persons" in data:
            transformed_persons = []
            
            for person in data["persons"]:
                # Rozdzielenie imienia i nazwiska
                name_parts = person["name"].split(" ", 1)
                imie = name_parts[0] if name_parts else ""
                nazwisko = name_parts[1] if len(name_parts) > 1 else ""

                # Budowanie obiektu osoby
                transformed_person = {
                    "id_osoby": str(person["id"]),
                    "imie": imie,
                    "nazwisko": nazwisko,
                    "rok_urodzenia": (
                        person["birthDate"]["year"] if person.get("birthDate") else None
                    ),
                    "rok_smierci": (
                        person["deathDate"]["year"] if person.get("deathDate") else None
                    ),
                    "id_ojca": (
                        str(person["fatherId"]) if person.get("fatherId") else None
                    ),
                    "id_matki": (
                        str(person["motherId"]) if person.get("motherId") else None
                    ),
                    "id_malzonka": (
                        str(person["spouseIds"][0])
                        if person.get("spouseIds") and len(person["spouseIds"]) > 0
                        else None
                    ),
                    "protokol_klucz": person.get("protocolKey"),
                    "plec": person.get("gender", "M"),
                    "numer_domu": person.get("houseNumber"),
                    "uwagi": person.get("notes", ""),
                }
                transformed_persons.append(transformed_person)
            
            return jsonify(transformed_persons)
        else:
            return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/genealogia", methods=["POST"])
def save_genealogia_data():
    """
    Zapisuje dane genealogiczne z walidacją i auto-symetryzacją małżeństw.
    
    Walidacja obejmuje:
    - Unikalność ID osób
    - Poprawność referencji rodzinnych
    - Automatyczną symetryzację relacji małżeńskich
    """
    people = request.get_json()
    if not isinstance(people, list):
        return jsonify({"error": "Oczekiwano listy osób w formacie JSON"}), 400

    # Walidacja unikalności ID
    ids = [p.get("id_osoby") for p in people]
    dup = [i for i, cnt in Counter(ids).items() if cnt > 1]
    if dup:
        return jsonify({"error": f"Duplikaty ID: {dup}"}), 400

    by_id = {p["id_osoby"]: p for p in people}

    # Walidacja referencji i symetryzacja małżeństw
    problems = []
    
    for p in people:
        pid = p["id_osoby"]

        # Sprawdzenie rodziców
        for rel in ("id_ojca", "id_matki"):
            rid = p.get(rel)
            if rid and rid not in by_id:
                problems.append(f"{pid}: {rel}={rid} nie istnieje")

        # Symetryzacja małżeństw
        spouse_id = p.get("id_malzonka")
        if spouse_id:
            if spouse_id not in by_id:
                problems.append(f"{pid}: id_malzonka={spouse_id} nie istnieje")
            else:
                spouse = by_id[spouse_id]
                if spouse.get("id_malzonka") != pid:
                    spouse["id_malzonka"] = pid

    if problems:
        return jsonify({"error": "Błędne referencje", "details": problems}), 400

    # Przekształcenie do formatu zapisu
    try:
        existing_data = {}
        if os.path.exists(GENEALOGIA_JSON_PATH):
            with open(GENEALOGIA_JSON_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)

        transformed_persons = []
        
        for p in people:
            # Zachowanie dodatkowych pól z istniejących danych
            existing_person = next(
                (
                    person
                    for person in existing_data.get("persons", [])
                    if str(person["id"]) == p["id_osoby"]
                ),
                {},
            )

            transformed_person = {
                "id": int(p["id_osoby"]),
                "name": f"{p['imie']} {p['nazwisko']}".strip(),
                "gender": p.get("plec", existing_person.get("gender", "M")),
                "houseNumber": p.get("numer_domu", existing_person.get("houseNumber")),
                "birthDate": (
                    {"year": p["rok_urodzenia"]} if p["rok_urodzenia"] else None
                ),
                "deathDate": {"year": p["rok_smierci"]} if p["rok_smierci"] else None,
                "protocolKey": p.get("protokol_klucz"),
                "fatherId": int(p["id_ojca"]) if p.get("id_ojca") else None,
                "motherId": int(p["id_matki"]) if p.get("id_matki") else None,
                "spouseIds": [int(p["id_malzonka"])] if p.get("id_malzonka") else [],
                "notes": p.get("uwagi", ""),
            }
            transformed_persons.append(transformed_person)

        # Zapis do pliku
        data_to_save = {"persons": transformed_persons}
        with open(GENEALOGIA_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)

        return jsonify({"message": "Dane zapisane pomyślnie ✔"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================================================
# API DRZEWA GENEALOGICZNEGO
# ==========================================================================

@app.route("/api/genealogia/drzewo/<family_name>", methods=["GET"])
def get_family_tree_data(family_name):
    """
    Generuje dane drzewa genealogicznego.
    
    Obsługuje dwa przypadki:
    1. family_name jako ID osoby - zwraca pojedyncze mikro-drzewko
    2. family_name jako nazwisko - zwraca całe drzewo rodu (algorytm BFS)
    """
    if not os.path.exists(GENEALOGIA_JSON_PATH):
        return jsonify({"people": [], "start_node_id": None})

    try:
        with open(GENEALOGIA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Przekształcenie danych
        if "persons" in data:
            all_people = []
            
            for person in data["persons"]:
                name_parts = person["name"].split(" ", 1)
                imie = name_parts[0] if name_parts else ""
                nazwisko = name_parts[1] if len(name_parts) > 1 else ""

                spouse_ids = person.get("spouseIds", [])
                if not isinstance(spouse_ids, list):
                    spouse_ids = [spouse_ids] if spouse_ids else []

                transformed_person = {
                    "id_osoby": str(person["id"]),
                    "imie": imie,
                    "nazwisko": nazwisko,
                    "rok_urodzenia": (
                        person["birthDate"]["year"] if person.get("birthDate") else None
                    ),
                    "rok_smierci": (
                        person["deathDate"]["year"] if person.get("deathDate") else None
                    ),
                    "id_ojca": (
                        str(person["fatherId"]) if person.get("fatherId") else None
                    ),
                    "id_matki": (
                        str(person["motherId"]) if person.get("motherId") else None
                    ),
                    "id_malzonka": (
                        str(spouse_ids[0])
                        if spouse_ids and len(spouse_ids) > 0
                        else None
                    ),
                    "protokol_klucz": person.get("protocolKey"),
                    "plec": person.get("gender", "M"),
                    "numer_domu": person.get("houseNumber"),
                    "uwagi": person.get("notes", ""),
                }
                all_people.append(transformed_person)
        else:
            all_people = data

        def surname_matches(surname: str, target: str) -> bool:
            """Porównuje nazwiska z normalizacją polskich znaków."""
            trans = str.maketrans("ąćęłńóśżźĄĆĘŁŃÓŚŻŹ", "acelnoszzACELNOSZZ")
            norm = lambda s: "".join(
                ch for ch in s.translate(trans).lower() if ch.isalnum()
            )
            return norm(target) in norm(surname)

        # Przypadek 1: ID osoby
        specific = next((p for p in all_people if p["id_osoby"] == family_name), None)
        if specific:
            return jsonify(
                {
                    "people": [
                        {
                            "id": specific["id_osoby"],
                            "imie": specific.get("imie", ""),
                            "nazwisko": specific.get("nazwisko", ""),
                            "rok_urodzenia": specific.get("rok_urodzenia"),
                            "rok_smierci": specific.get("rok_smierci"),
                            "ojciec_id": specific.get("id_ojca"),
                            "matka_id": specific.get("id_matki"),
                            "malzonek_id": specific.get("id_malzonka"),
                            "unikalny_klucz": specific.get("protokol_klucz"),
                            "malzenstwa": [],
                        }
                    ],
                    "start_node_id": specific["id_osoby"],
                }
            )

        # Przypadek 2: Nazwisko rodu
        family_people = []
        related_ids = set()

        # Znajdź osoby z tym nazwiskiem
        for p in all_people:
            if surname_matches(p.get("nazwisko", ""), family_name):
                family_people.append(p)
                related_ids.add(p["id_osoby"])

        # Usuń osoby izolowane
        if len(family_people) > 1:
            family_people = [
                p
                for p in family_people
                if (
                    p.get("id_ojca")
                    or p.get("id_matka")
                    or p.get("id_malzonka")
                    or any(
                        (
                            o.get("id_ojca") == p["id_osoby"]
                            or o.get("id_matki") == p["id_osoby"]
                            or o.get("id_malzonka") == p["id_osoby"]
                        )
                        for o in family_people
                    )
                )
            ]

        # Rekurencyjne dodawanie powiązanych osób
        def add_related(pid: str):
            """Dodaje rodziców i małżonków rekurencyjnie."""
            if not pid or pid in related_ids:
                return
            pers = next((x for x in all_people if x["id_osoby"] == pid), None)
            if not pers:
                return
            family_people.append(pers)
            related_ids.add(pid)
            add_related(pers.get("id_ojca"))
            add_related(pers.get("id_matka"))
            add_related(pers.get("id_malzonka"))

        for p in family_people.copy():
            add_related(p.get("id_ojca"))
            add_related(p.get("id_matka"))
            add_related(p.get("id_malzonka"))

        # Algorytm BFS dla dzieci
        newly_added = True
        while newly_added:
            newly_added = False
            for child in all_people:
                if child["id_osoby"] in related_ids:
                    continue
                if not surname_matches(child.get("nazwisko", ""), family_name):
                    continue
                if (
                    child.get("id_ojca") in related_ids
                    or child.get("id_matki") in related_ids
                ):
                    family_people.append(child)
                    related_ids.add(child["id_osoby"])
                    newly_added = True

        # Konwersja do formatu D3.js
        tree_people = [
            {
                "id": p["id_osoby"],
                "imie": p.get("imie", ""),
                "nazwisko": p.get("nazwisko", ""),
                "rok_urodzenia": p.get("rok_urodzenia"),
                "rok_smierci": p.get("rok_smierci"),
                "ojciec_id": p.get("id_ojca"),
                "matka_id": p.get("id_matki"),
                "malzonek_id": p.get("id_malzonka"),
                "unikalny_klucz": p.get("protokol_klucz"),
                "malzenstwa": [],
            }
            for p in family_people
        ]

        # Wybór osoby root
        root_id = next(
            (
                p["id"]
                for p in tree_people
                if surname_matches(p["nazwisko"], family_name)
                and not p["ojciec_id"]
                and not p["matka_id"]
            ),
            None,
        )
        
        # Fallback: najstarsza osoba
        if not root_id and tree_people:
            root_id = min(
                (p for p in tree_people if p["rok_urodzenia"]),
                key=lambda x: x["rok_urodzenia"],
                default=tree_people[0],
            )["id"]

        return jsonify({"people": tree_people, "start_node_id": root_id})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================================================
# API KOPII ZAPASOWYCH
# ==========================================================================

@app.route("/api/genealogy/backups", methods=["GET"])
def list_genealogy_backups():
    """Zwraca listę kopii zapasowych genealogii."""
    try:
        files = [
            f
            for f in os.listdir(BACKUP_FOLDER)
            if f.startswith("genealogia_") and f.endswith(".json.bak")
        ]
        files.sort(reverse=True)  # Najnowsze pierwsze
        return jsonify(files)
    except FileNotFoundError:
        return jsonify([])

@app.route("/api/genealogy/backups/create", methods=["POST"])
def create_genealogy_backup():
    """Tworzy nową kopię zapasową z timestampem."""
    if not os.path.exists(GENEALOGIA_JSON_PATH):
        return jsonify({"error": "Plik roboczy nie istnieje."}), 404
    
    try:
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_FOLDER, f"genealogia_{timestamp}.json.bak")
        
        shutil.copy(GENEALOGIA_JSON_PATH, backup_path)
        
        return jsonify(
            {
                "message": "Kopia zapasowa utworzona pomyślnie.",
                "filename": os.path.basename(backup_path),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/genealogy/backups/restore", methods=["POST"])
def restore_genealogy_backup():
    """Przywraca wybraną kopię zapasową."""
    data = request.get_json()
    filename = data.get("filename")
    
    # Walidacja bezpieczeństwa
    if not filename or not filename.startswith("genealogia_") or ".." in filename:
        return jsonify({"error": "Nieprawidłowa nazwa pliku."}), 400

    backup_path = os.path.join(BACKUP_FOLDER, filename)
    if not os.path.exists(backup_path):
        return jsonify({"error": "Plik kopii zapasowej nie istnieje."}), 404

    try:
        shutil.copy(backup_path, GENEALOGIA_JSON_PATH)
        return jsonify(
            {
                "message": "Kopia zapasowa przywrócona. Odśwież stronę, aby zobaczyć zmiany."
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/genealogy/backups/<string:filename>", methods=["DELETE"])
def delete_genealogy_backup(filename):
    """Usuwa wybraną kopię zapasową."""
    # Walidacja bezpieczeństwa
    if not filename or not filename.startswith("genealogia_") or ".." in filename:
        return jsonify({"error": "Nieprawidłowa nazwa pliku."}), 400

    backup_path = os.path.join(BACKUP_FOLDER, filename)
    if not os.path.exists(backup_path):
        return jsonify({"error": "Plik kopii zapasowej nie istnieje."}), 404

    try:
        os.remove(backup_path)
        return jsonify({"message": "Kopia zapasowa usunięta."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================================================
# API KOMUNIKACJI MIĘDZY EDYTORAMI
# ==========================================================================

@app.route("/api/editor/status", methods=["GET"])
def get_editor_status():
    """Zwraca status głównego edytora z timeoutem 30 sekund."""
    if EDITOR_STATUS["last_heartbeat"]:
        time_diff = datetime.now() - EDITOR_STATUS["last_heartbeat"]
        if time_diff > timedelta(seconds=30):
            EDITOR_STATUS["is_running"] = False
            EDITOR_STATUS["address"] = None
            EDITOR_STATUS["port"] = None
    
    return jsonify({
        "is_running": EDITOR_STATUS["is_running"],
        "address": EDITOR_STATUS["address"],
        "port": EDITOR_STATUS["port"]
    })

@app.route("/api/editor/register", methods=["POST"])
def register_editor():
    """Rejestruje główny edytor w systemie."""
    data = request.get_json()
    
    EDITOR_STATUS["is_running"] = True
    EDITOR_STATUS["address"] = data.get("address", "127.0.0.1")
    EDITOR_STATUS["port"] = data.get("port", 5000)
    EDITOR_STATUS["last_heartbeat"] = datetime.now()
    
    return jsonify({"status": "registered"})

@app.route("/api/editor/heartbeat", methods=["POST"])
def editor_heartbeat():
    """Odbiera sygnał życia od głównego edytora."""
    EDITOR_STATUS["last_heartbeat"] = datetime.now()
    return jsonify({"status": "alive"})

@app.route("/api/editor/check-main", methods=["GET"])
def check_main_editor():
    """Sprawdza dostępność głównego edytora na porcie 5000."""
    main_port = 5000
    main_host = "127.0.0.1"
    
    if is_port_open(main_host, main_port):
        return jsonify({
            "available": True,
            "url": f"http://{main_host}:{main_port}"
        })
    else:
        return jsonify({
            "available": False,
            "url": None
        })

@app.route("/api/editor/launch-main", methods=["POST"])
def launch_main_editor():
    """Uruchamia główny edytor aplikacji."""
    try:
        main_editor_path = os.path.join(BASE_DIR, "launcher.py")
        
        if os.path.exists(main_editor_path):
            subprocess.Popen(
                [sys.executable, main_editor_path], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            
            time.sleep(2)  # Oczekiwanie na start
            
            if is_port_open("127.0.0.1", 5000):
                return jsonify({
                    "success": True, 
                    "url": "http://127.0.0.1:5000"
                })
        
        return jsonify({
            "success": False, 
            "error": "Nie można uruchomić głównego edytora"
        })
        
    except Exception as e:
        return jsonify({
            "success": False, 
            "error": str(e)
        })

# ==========================================================================
# ROUTING GŁÓWNY
# ==========================================================================

@app.route("/")
def editor_home():
    """Serwuje główną stronę edytora."""
    return render_template("editor.html")

@app.route("/shutdown", methods=["POST"])
def shutdown():
    """
    Zamyka serwer Flask z opóźnieniem.
    
    Wykorzystuje wątek w tle do opóźnionego zamknięcia,
    co pozwala na dokończenie zapisów.
    """
    shutdown_func = request.environ.get("werkzeug.server.shutdown")
    delay_secs = 3

    def stopper(func=shutdown_func):
        """Wykonuje opóźnione zamknięcie serwera."""
        time.sleep(delay_secs)
        if func:
            func()
        else:
            os._exit(0)

    threading.Thread(target=stopper, daemon=True).start()
    return f"Serwer się zamknie za ok. {delay_secs} sekundy…", 200

# ==========================================================================
# GŁÓWNA FUNKCJA URUCHOMIENIOWA
# ==========================================================================

def main():
    """
    Uruchamia serwer Flask i otwiera przeglądarkę.
    
    Port: 5001 (edytor genealogii)
    Automatyczne otwarcie przeglądarki po starcie.
    """
    port = 5001
    url = f"http://127.0.0.1:{port}"

    # Automatyczne otwarcie przeglądarki
    if "--launched-by-gui" not in sys.argv:
        threading.Timer(1.25, lambda: webbrowser.open(url)).start()

    print(f"Uruchamianie edytora genealogii pod adresem: {url}")
    print("Aby zakończyć, użyj przycisku 'Zapisz i Zamknij' w przeglądarce lub zamknij to okno konsoli.")

    # Uruchomienie serwera
    app.run(port=port, debug=False, use_reloader=False)

# ==========================================================================
# PUNKT WEJŚCIA
# ==========================================================================

if __name__ == "__main__":
    import sys
    main()