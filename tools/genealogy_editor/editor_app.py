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

# --- KONFIGURACJA ŚCIEŻEK ---

# Wychodzimy TRZY poziomy w górę (z tools/genealogy_editor/) do głównego folderu projektu.
# Struktura folderów wymaga przejścia przez trzy poziomy katalogów nadrzędnych.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ścieżka do folderu z kopiami zapasowymi
BACKUP_FOLDER = os.path.join(BASE_DIR, "backup")

# Ścieżka do głównego pliku JSON z danymi genealogicznymi
GENEALOGIA_JSON_PATH = os.path.join(BACKUP_FOLDER, "genealogia.json")

# Ścieżka do pliku JSON z danymi protokołów właścicieli
OWNER_JSON_PATH = os.path.join(BACKUP_FOLDER, "owner_data_to_import.json")

# --- KONFIGURACJA APLIKACJI FLASK ---

# Inicjalizacja głównego obiektu aplikacji Flask.
# Ustawiamy ścieżki do szablonów i plików statycznych wewnątrz naszego folderu edytora.
app = Flask(__name__, template_folder="templates", static_folder="static")

# --- STAN GŁÓWNEGO EDYTORA ---

# Struktura przechowująca informacje o stanie głównego edytora aplikacji.
# Wykorzystywana do koordynacji między edytorem genealogii a główną aplikacją.
EDITOR_STATUS = {
    "is_running": False,      # Flaga określająca czy główny edytor jest aktywny
    "address": None,          # Adres IP głównego edytora
    "port": None,            # Port na którym nasłuchuje główny edytor
    "last_heartbeat": None   # Czas ostatniego sygnału życia
}

# --- FUNKCJE POMOCNICZE KOMUNIKACJI SIECIOWEJ ---

def is_port_open(host, port):
    """
    Sprawdza dostępność określonego portu TCP na danym hoście.
    
    Wykorzystuje socket do próby połączenia z timeoutem 1 sekundy.
    Używane do weryfikacji czy główny edytor jest uruchomiony.
    
    Args:
        host: Adres IP lub nazwa hosta do sprawdzenia
        port: Numer portu TCP do sprawdzenia
        
    Returns:
        bool: True jeśli port jest otwarty, False w przeciwnym wypadku
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

# === SEKCJA: API DO SERWOWANIA DANYCH O PROTOKOŁACH ===

@app.route("/api/protocols", methods=["GET"])
def get_protocols_data():
    """Wysyła uproszczoną listę protokołów do frontendu.
    
    Funkcja przekształca dane z pliku owner_data_to_import.json
    w format łatwy do wykorzystania przez komponenty frontendowe.
    """
    # Sprawdzenie czy plik z danymi istnieje
    if not os.path.exists(OWNER_JSON_PATH):
        return jsonify([])
    
    try:
        # Odczyt danych z pliku JSON
        with open(OWNER_JSON_PATH, "r", encoding="utf-8") as f:
            owner_data = json.load(f)

        # Przekształcamy słownik w listę obiektów potrzebną dla frontendu.
        # Każdy protokół otrzymuje klucz, nazwę i numer porządkowy.
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
        # Zwracamy błąd HTTP 500 w przypadku problemów z odczytem danych
        return jsonify({"error": str(e)}), 500

# === SEKCJA: API DO ZARZĄDZANIA DANYMI GENEALOGICZNYMI ===

@app.route("/api/genealogia", methods=["GET"])
def get_genealogia_data():
    """Wysyła dane z pliku genealogia.json do frontendu.
    
    Funkcja przekształca dane z formatu zapisu do formatu
    oczekiwanego przez edytor genealogiczny w przeglądarce.
    """
    # Sprawdzenie istnienia pliku z danymi
    if not os.path.exists(GENEALOGIA_JSON_PATH):
        return jsonify([])  # Zwróć pustą listę, jeśli plik nie istnieje
    
    try:
        # Odczyt danych z pliku
        with open(GENEALOGIA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Przekształć dane, aby pasowały do formatu oczekiwanego przez frontend
        if "persons" in data:
            transformed_persons = []
            
            # Przetwarzamy każdą osobę z pliku
            for person in data["persons"]:
                # Podziel imię i nazwisko z pola "name"
                name_parts = person["name"].split(" ", 1)
                imie = name_parts[0] if name_parts else ""
                nazwisko = name_parts[1] if len(name_parts) > 1 else ""

                # Tworzenie obiektu osoby w formacie edytora
                transformed_person = {
                    "id_osoby": str(person["id"]),  # Upewnij się, że ID jest stringiem
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
            # Jeśli dane są już w odpowiednim formacie, zwracamy je bez zmian
            return jsonify(data)
    except Exception as e:
        # Obsługa błędów podczas odczytu lub przetwarzania danych
        return jsonify({"error": str(e)}), 500

@app.route("/api/genealogia", methods=["POST"])
def save_genealogia_data():
    """Zapisuje genealogia.json z walidacją i auto-symetryzacją małżeństw.
    
    Funkcja wykonuje kompleksową walidację danych przed zapisem:
    - Sprawdza unikalność ID osób
    - Weryfikuje poprawność referencji (rodzice, małżonkowie)
    - Automatycznie symetryzuje relacje małżeńskie
    """
    # Pobieranie danych z żądania HTTP
    people = request.get_json()
    if not isinstance(people, list):
        return jsonify({"error": "Oczekiwano listy osób w formacie JSON"}), 400

    # --- 1. WALIDACJA: Sprawdzanie unikalności ID ---
    ids = [p.get("id_osoby") for p in people]
    # Znajdowanie duplikatów ID przy użyciu Counter
    dup = [i for i, cnt in Counter(ids).items() if cnt > 1]
    if dup:
        return jsonify({"error": f"Duplikaty ID: {dup}"}), 400

    # Tworzenie słownika dla szybkiego dostępu do osób po ID
    by_id = {p["id_osoby"]: p for p in people}

    # --- 2. WALIDACJA: Sprawdzanie referencji i symetryzacja małżeństw ---
    problems = []
    
    for p in people:
        pid = p["id_osoby"]

        # Sprawdzanie czy rodzice istnieją w bazie
        for rel in ("id_ojca", "id_matki"):
            rid = p.get(rel)
            if rid and rid not in by_id:
                problems.append(f"{pid}: {rel}={rid} nie istnieje")

        # Sprawdzanie i symetryzacja relacji małżeńskich
        spouse_id = p.get("id_malzonka")
        if spouse_id:
            if spouse_id not in by_id:
                problems.append(f"{pid}: id_malzonka={spouse_id} nie istnieje")
            else:
                # Automatyczne dodawanie brakującego linku zwrotnego małżeństwa
                spouse = by_id[spouse_id]
                if spouse.get("id_malzonka") != pid:
                    spouse["id_malzonka"] = pid

    # Jeśli znaleziono problemy z referencjami, zwracamy błąd
    if problems:
        return jsonify({"error": "Błędne referencje", "details": problems}), 400

    # --- 3. PRZEKSZTAŁCENIE: Konwersja danych do formatu zapisu ---
    try:
        # Wczytaj istniejące dane, aby zachować inne pola
        existing_data = {}
        if os.path.exists(GENEALOGIA_JSON_PATH):
            with open(GENEALOGIA_JSON_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)

        # Przygotuj przekształcone osoby
        transformed_persons = []
        
        for p in people:
            # Znajdź istniejącą osobę o tym samym ID, aby zachować dodatkowe pola
            existing_person = next(
                (
                    person
                    for person in existing_data.get("persons", [])
                    if str(person["id"]) == p["id_osoby"]
                ),
                {},
            )

            # Tworzenie obiektu osoby w formacie zapisu
            transformed_person = {
                "id": int(p["id_osoby"]),  # Konwertuj ID z powrotem na liczbę
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

        # Przygotuj dane do zapisu
        data_to_save = {"persons": transformed_persons}

        # --- 4. ZAPIS: Zapisanie danych do pliku ---
        with open(GENEALOGIA_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)

        return jsonify({"message": "Dane zapisane pomyślnie ✔"})
    except Exception as e:
        # Obsługa błędów podczas zapisu
        return jsonify({"error": str(e)}), 500

# === SEKCJA: API DO GENEROWANIA DRZEWA GENEALOGICZNEGO ===

@app.route("/api/genealogia/drzewo/<family_name>", methods=["GET"])
def get_family_tree_data(family_name):
    """Zwraca dane drzewa genealogicznego – cały ród ORAZ pojedynczą osobę.
    
    Funkcja obsługuje dwa przypadki:
    1. Jeśli family_name to id_osoby - zwraca mikro-drzewko pojedynczej osoby
    2. Jeśli family_name to nazwisko - zwraca całe drzewo rodu
    
    Wykorzystuje algorytm BFS do znajdowania wszystkich powiązanych osób.
    """
    # Sprawdzenie istnienia pliku z danymi
    if not os.path.exists(GENEALOGIA_JSON_PATH):
        return jsonify({"people": [], "start_node_id": None})

    try:
        # Odczyt i przetwarzanie danych z pliku
        with open(GENEALOGIA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Przekształć dane do formatu oczekiwanego przez frontend
        if "persons" in data:
            all_people = []
            
            for person in data["persons"]:
                # Podziel imię i nazwisko z pola "name"
                name_parts = person["name"].split(" ", 1)
                imie = name_parts[0] if name_parts else ""
                nazwisko = name_parts[1] if len(name_parts) > 1 else ""

                # Upewnij się, że spouseIds jest listą
                spouse_ids = person.get("spouseIds", [])
                if not isinstance(spouse_ids, list):
                    spouse_ids = [spouse_ids] if spouse_ids else []

                # Tworzenie obiektu osoby
                transformed_person = {
                    "id_osoby": str(person["id"]),  # Upewnij się, że ID jest stringiem
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

        # --- FUNKCJA POMOCNICZA: Luźne dopasowanie nazwiska ---
        def surname_matches(surname: str, target: str) -> bool:
            """Porównuje nazwiska z pominięciem znaków diakrytycznych i odmian.
            
            Normalizuje teksty usuwając polskie znaki i porównuje je.
            """
            # Tabela transliteracji polskich znaków
            trans = str.maketrans("ąćęłńóśżźĄĆĘŁŃÓŚŻŹ", "acelnoszzACELNOSZZ")
            # Funkcja normalizująca tekst
            norm = lambda s: "".join(
                ch for ch in s.translate(trans).lower() if ch.isalnum()
            )
            return norm(target) in norm(surname)

        # --- PRZYPADEK 1: family_name to ID osoby - mikro-drzewko ---
        specific = next((p for p in all_people if p["id_osoby"] == family_name), None)
        if specific:
            # Zwracamy pojedynczą osobę jako drzewo
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

        # --- PRZYPADEK 2: Ród o nazwisku family_name ---
        family_people = []  # Lista osób należących do rodu
        related_ids = set()  # Zbiór ID powiązanych osób

        # a) Znajdź osoby NOSZĄCE to nazwisko
        for p in all_people:
            if surname_matches(p.get("nazwisko", ""), family_name):
                family_people.append(p)
                related_ids.add(p["id_osoby"])

        # b) Usuń osoby izolowane (jeśli ród ma więcej niż 1 członka)
        if len(family_people) > 1:
            family_people = [
                p
                for p in family_people
                if (
                    # Osoba ma rodziców, małżonka lub dzieci
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

        # c) Rekurencyjnie dodaj RODZICÓW i MAŁŻONKÓW
        def add_related(pid: str):
            """Rekurencyjnie dodaje osoby powiązane (rodziców i małżonków)."""
            if not pid or pid in related_ids:
                return
            pers = next((x for x in all_people if x["id_osoby"] == pid), None)
            if not pers:
                return
            # Dodaj osobę do rodu
            family_people.append(pers)
            related_ids.add(pid)
            # Rekurencyjnie dodaj jej relacje
            add_related(pers.get("id_ojca"))
            add_related(pers.get("id_matka"))
            add_related(pers.get("id_malzonka"))

        # Przetwórz wszystkie osoby z rodu
        for p in family_people.copy():
            add_related(p.get("id_ojca"))
            add_related(p.get("id_matka"))
            add_related(p.get("id_malzonka"))

        # d) Dodaj DZIECI pasujące do nazwiska rodu (algorytm BFS)
        newly_added = True
        while newly_added:  # Pętla BFS, żeby złapać wnuki itd.
            newly_added = False
            for child in all_people:
                if child["id_osoby"] in related_ids:
                    continue
                if not surname_matches(child.get("nazwisko", ""), family_name):
                    continue
                # Jeśli dziecko ma rodzica w rodzie, dodaj je
                if (
                    child.get("id_ojca") in related_ids
                    or child.get("id_matki") in related_ids
                ):
                    family_people.append(child)
                    related_ids.add(child["id_osoby"])
                    newly_added = True

        # --- 3. KONWERSJA: Przekształcenie do formatu D3.js ---
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

        # Znajdź osobę root (najstarszy przedstawiciel rodu bez rodziców)
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
        
        # Fallback: jeśli nie znaleziono roota, wybierz osobę z najwcześniejszą datą urodzenia
        if not root_id and tree_people:
            root_id = min(
                (p for p in tree_people if p["rok_urodzenia"]),
                key=lambda x: x["rok_urodzenia"],
                default=tree_people[0],
            )["id"]

        return jsonify({"people": tree_people, "start_node_id": root_id})

    except Exception as e:
        # Obsługa błędów podczas przetwarzania danych
        return jsonify({"error": str(e)}), 500

# === SEKCJA: API DO ZARZĄDZANIA KOPIAMI ZAPASOWYMI ===

@app.route("/api/genealogy/backups", methods=["GET"])
def list_genealogy_backups():
    """Zwraca listę dostępnych plików kopii zapasowych dla genealogii.
    
    Skanuje folder backup w poszukiwaniu plików .json.bak
    i zwraca je posortowane według daty (najnowsze pierwsze).
    """
    try:
        # Filtrowanie plików - tylko kopie zapasowe genealogii
        files = [
            f
            for f in os.listdir(BACKUP_FOLDER)
            if f.startswith("genealogia_") and f.endswith(".json.bak")
        ]
        # Sortowanie malejące po nazwie (która zawiera datę)
        files.sort(reverse=True)
        return jsonify(files)
    except FileNotFoundError:
        # Jeśli folder nie istnieje, zwracamy pustą listę
        return jsonify([])

@app.route("/api/genealogy/backups/create", methods=["POST"])
def create_genealogy_backup():
    """Tworzy nową kopię zapasową pliku genealogia.json.
    
    Kopia jest zapisywana z unikalną nazwą zawierającą timestamp,
    co zapewnia unikalność i chronologiczne sortowanie.
    """
    # Sprawdzenie czy plik źródłowy istnieje
    if not os.path.exists(GENEALOGIA_JSON_PATH):
        return jsonify({"error": "Plik roboczy nie istnieje."}), 404
    
    try:
        from datetime import datetime
        
        # Generowanie unikalnej nazwy z timestampem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_FOLDER, f"genealogia_{timestamp}.json.bak")
        
        # Kopiowanie pliku
        shutil.copy(GENEALOGIA_JSON_PATH, backup_path)
        
        return jsonify(
            {
                "message": "Kopia zapasowa utworzona pomyślnie.",
                "filename": os.path.basename(backup_path),
            }
        )
    except Exception as e:
        # Obsługa błędów podczas tworzenia kopii
        return jsonify({"error": str(e)}), 500

@app.route("/api/genealogy/backups/restore", methods=["POST"])
def restore_genealogy_backup():
    """Przywraca wybraną kopię zapasową.
    
    Zastępuje aktualny plik genealogia.json wybraną kopią zapasową.
    Zawiera walidację nazwy pliku dla bezpieczeństwa.
    """
    # Pobieranie danych z żądania
    data = request.get_json()
    filename = data.get("filename")
    
    # Walidacja nazwy pliku (zabezpieczenie przed path traversal)
    if not filename or not filename.startswith("genealogia_") or ".." in filename:
        return jsonify({"error": "Nieprawidłowa nazwa pliku."}), 400

    # Budowanie pełnej ścieżki do pliku kopii
    backup_path = os.path.join(BACKUP_FOLDER, filename)
    if not os.path.exists(backup_path):
        return jsonify({"error": "Plik kopii zapasowej nie istnieje."}), 404

    try:
        # Przywracanie kopii (kopiowanie pliku backup na miejsce aktualnego)
        shutil.copy(backup_path, GENEALOGIA_JSON_PATH)
        return jsonify(
            {
                "message": "Kopia zapasowa przywrócona. Odśwież stronę, aby zobaczyć zmiany."
            }
        )
    except Exception as e:
        # Obsługa błędów podczas przywracania
        return jsonify({"error": str(e)}), 500

@app.route("/api/genealogy/backups/<string:filename>", methods=["DELETE"])
def delete_genealogy_backup(filename):
    """Usuwa wybraną kopię zapasową.
    
    Zawiera walidację nazwy pliku dla bezpieczeństwa
    przed próbami usunięcia plików spoza katalogu backup.
    """
    # Walidacja nazwy pliku (zabezpieczenie przed path traversal)
    if not filename or not filename.startswith("genealogia_") or ".." in filename:
        return jsonify({"error": "Nieprawidłowa nazwa pliku."}), 400

    # Budowanie pełnej ścieżki do pliku
    backup_path = os.path.join(BACKUP_FOLDER, filename)
    if not os.path.exists(backup_path):
        return jsonify({"error": "Plik kopii zapasowej nie istnieje."}), 404

    try:
        # Usuwanie pliku
        os.remove(backup_path)
        return jsonify({"message": "Kopia zapasowa usunięta."})
    except Exception as e:
        # Obsługa błędów podczas usuwania
        return jsonify({"error": str(e)}), 500

# === SEKCJA: API KOMUNIKACJI MIĘDZY EDYTORAMI ===

@app.route("/api/editor/status", methods=["GET"])
def get_editor_status():
    """
    Endpoint zwracający aktualny status głównego edytora.
    
    Sprawdza aktualność heartbeatu - jeśli ostatni sygnał był
    dawniej niż 30 sekund temu, uznaje edytor za nieaktywny.
    
    Returns:
        JSON z informacjami o stanie głównego edytora
    """
    # Weryfikacja aktualności heartbeatu
    if EDITOR_STATUS["last_heartbeat"]:
        time_diff = datetime.now() - EDITOR_STATUS["last_heartbeat"]
        # Timeout 30 sekund - po tym czasie uznajemy edytor za nieaktywny
        if time_diff > timedelta(seconds=30):
            EDITOR_STATUS["is_running"] = False
            EDITOR_STATUS["address"] = None
            EDITOR_STATUS["port"] = None
    
    # Zwracamy aktualny stan
    return jsonify({
        "is_running": EDITOR_STATUS["is_running"],
        "address": EDITOR_STATUS["address"],
        "port": EDITOR_STATUS["port"]
    })

@app.route("/api/editor/register", methods=["POST"])
def register_editor():
    """
    Rejestruje główny edytor jako aktywny w systemie.
    
    Endpoint wywoływany przez główny edytor podczas startu,
    aby poinformować edytor genealogii o swojej dostępności.
    
    Returns:
        JSON z potwierdzeniem rejestracji
    """
    data = request.get_json()
    
    # Aktualizacja stanu głównego edytora
    EDITOR_STATUS["is_running"] = True
    EDITOR_STATUS["address"] = data.get("address", "127.0.0.1")
    EDITOR_STATUS["port"] = data.get("port", 5000)
    EDITOR_STATUS["last_heartbeat"] = datetime.now()
    
    return jsonify({"status": "registered"})

@app.route("/api/editor/heartbeat", methods=["POST"])
def editor_heartbeat():
    """
    Odbiera sygnał życia od głównego edytora.
    
    Endpoint wywoływany cyklicznie przez główny edytor
    aby potwierdzić że nadal działa.
    
    Returns:
        JSON z potwierdzeniem otrzymania sygnału
    """
    EDITOR_STATUS["last_heartbeat"] = datetime.now()
    return jsonify({"status": "alive"})

@app.route("/api/editor/check-main", methods=["GET"])
def check_main_editor():
    """
    Sprawdza dostępność głównego edytora na standardowym porcie.
    
    Wykorzystuje funkcję is_port_open do weryfikacji czy
    główny edytor nasłuchuje na porcie 5000.
    
    Returns:
        JSON z informacją o dostępności i URL głównego edytora
    """
    # Standardowa konfiguracja głównego edytora
    main_port = 5000
    main_host = "127.0.0.1"
    
    # Sprawdzenie dostępności portu
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
    """
    Próbuje uruchomić główny edytor aplikacji.
    
    Funkcja lokalizuje i uruchamia launcher.py który zarządza
    całą aplikacją. Po uruchomieniu czeka 2 sekundy i weryfikuje
    czy proces wystartował poprawnie.
    
    Returns:
        JSON z informacją o sukcesie lub błędzie uruchomienia
    """
    try:
        # Konstrukcja ścieżki do głównego launchera
        # Przechodzimy trzy poziomy w górę od tools/genealogy_editor/
        main_editor_path = os.path.join(BASE_DIR, "launcher.py")
        
        # Weryfikacja istnienia pliku
        if os.path.exists(main_editor_path):
            # Uruchomienie launchera w tle bez wyświetlania konsoli
            subprocess.Popen(
                [sys.executable, main_editor_path], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            
            # Oczekiwanie na uruchomienie serwera
            time.sleep(2)
            
            # Weryfikacja czy serwer wystartował
            if is_port_open("127.0.0.1", 5000):
                return jsonify({
                    "success": True, 
                    "url": "http://127.0.0.1:5000"
                })
        
        # Serwer nie wystartował lub plik nie istnieje
        return jsonify({
            "success": False, 
            "error": "Nie można uruchomić głównego edytora"
        })
        
    except Exception as e:
        # Obsługa błędów podczas uruchamiania
        return jsonify({
            "success": False, 
            "error": str(e)
        })

# --- SERWOWANIE GŁÓWNEJ STRONY EDYTORA ---

@app.route("/")
def editor_home():
    """Serwuje główny plik HTML edytora genealogicznego.
    
    Renderuje szablon editor.html który zawiera
    interfejs użytkownika aplikacji.
    """
    return render_template("editor.html")

# --- FUNKCJA DO ZAMYKANIA SERWERA ---

@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Zamyka serwer Flask z kilkusekundowym opóźnieniem.
    
    Wykorzystuje wątek w tle do opóźnionego zamknięcia,
    co pozwala na dokończenie zapisów i zwrócenie odpowiedzi HTTP.
    Zawiera fallback na os._exit() jeśli standardowa metoda nie działa.
    """
    # Pobieramy funkcję shutdown z kontekstu Werkzeug (serwer deweloperski Flask)
    shutdown_func = request.environ.get("werkzeug.server.shutdown")
    
    # Czas oczekiwania przed zamknięciem (w sekundach)
    delay_secs = 3  

    def stopper(func=shutdown_func):
        """Funkcja pomocnicza wykonująca opóźnione zamknięcie."""
        # Czekamy, żeby dokończyć ewentualne zapisy
        time.sleep(delay_secs)
        
        # Wykonujemy shutdown
        if func:
            # Standardowa metoda zamknięcia (działa tylko w trybie debug)
            func()
        else:
            # Fallback - wymuszenie zamknięcia procesu
            os._exit(0)

    # Uruchamiamy zamykanie w osobnym wątku (daemon=True zapewnia że wątek nie blokuje zamknięcia)
    threading.Thread(target=stopper, daemon=True).start()
    
    # Zwracamy odpowiedź HTTP przed faktycznym zamknięciem
    return f"Serwer się zamknie za ok. {delay_secs} sekundy…", 200

# --- GŁÓWNA FUNKCJA URUCHOMIENIOWA ---

def main():
    """Główna funkcja uruchamiająca serwer i przeglądarkę.
    
    Konfiguruje port, automatycznie otwiera przeglądarkę
    (chyba że uruchomiono z GUI) i startuje serwer Flask.
    """
    # Konfiguracja portu dla serwera
    port = 5001
    url = f"http://127.0.0.1:{port}"

    # Sprawdzenie czy aplikacja została uruchomiona z GUI
    # Jeśli nie, automatycznie otwieramy przeglądarkę
    if "--launched-by-gui" not in sys.argv:
        # Timer zapewnia że przeglądarka otworzy się po uruchomieniu serwera
        threading.Timer(1.25, lambda: webbrowser.open(url)).start()

    # Wyświetlenie informacji w konsoli
    print(f"Uruchamianie edytora genealogii pod adresem: {url}")
    print(
        "Aby zakończyć, użyj przycisku 'Zapisz i Zamknij' w przeglądarce lub zamknij to okno konsoli."
    )

    # Uruchomienie serwera Flask
    # debug=False - wyłączony tryb debugowania dla produkcji
    # use_reloader=False - ważne! zapobiega podwójnemu uruchomieniu
    app.run(port=port, debug=False, use_reloader=False)  

# --- PUNKT WEJŚCIA APLIKACJI ---

if __name__ == "__main__":
    import sys
    # Uruchomienie głównej funkcji gdy skrypt jest wykonywany bezpośrednio
    main()