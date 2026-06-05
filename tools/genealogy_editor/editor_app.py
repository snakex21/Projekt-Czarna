"""
Edytor Genealogii - FastAPI (przepisany z Flask).
Dziala na JSON-ie: czyta/zapisuje genealogia.json w folderze aktywnej miejscowosci.
"""
import os
import sys
import json
import shutil
import threading
import webbrowser
import socket
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import uvicorn

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent

app = FastAPI(title="Edytor Genealogii")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Globalne ścieżki danych
BACKUP_DIR = None
GENEALOGIA_JSON_PATH = None
OWNER_JSON_PATH = None

# Stan komunikacji między edytorami
EDITOR_STATUS = {
    "is_running": False,
    "address": None,
    "port": None,
    "last_heartbeat": None
}


# ==========================================================================
# KONFIGURACJA
# ==========================================================================

def get_active_location():
    """Zwraca folder danych aktywnej miejscowości."""
    # Najpierw ACTIVE_LOCATION z launcher (najszybsze)
    loc = os.getenv("ACTIVE_LOCATION")
    if loc:
        folder = PROJECT_DIR / "data" / "locations" / loc
        print(f"✅ Edytor genealogii (ACTIVE_LOCATION) - miejscowość: {loc}")
        return folder

    # Sprawdź DB_ENGINE
    db_engine = os.getenv("DB_ENGINE", "").lower()

    if db_engine != "sqlite":
        # PostgreSQL z timeoutem
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                dbname="mapa_launcher_db",
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "1234"),
                port=os.getenv("DB_PORT", "5432"),
                connect_timeout=2
            )
            cur = conn.cursor()
            cur.execute("SELECT name FROM locations WHERE active = TRUE LIMIT 1")
            row = cur.fetchone()
            conn.close()
            if row:
                folder = PROJECT_DIR / "data" / "locations" / row[0]
                print(f"✅ Edytor genealogii (PostgreSQL) - miejscowość: {row[0]}")
                return folder
        except Exception as e:
            print(f"⚠️ PostgreSQL niedostępny: {e}")

    # SQLite fallback
    db_path = PROJECT_DIR / "data" / "locations.db"
    if db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT name FROM locations WHERE active = 1")
            row = cur.fetchone()
            conn.close()
            if row:
                folder = PROJECT_DIR / "data" / "locations" / row[0]
                print(f"✅ Edytor genealogii (SQLite) - miejscowość: {row[0]}")
                return folder
        except Exception as e:
            print(f"⚠️ Błąd SQLite: {e}")

    print("⚠️ Używam domyślnej lokalizacji")
    return PROJECT_DIR / "data" / "locations" / os.getenv("TEST_LOCATION", "Czarna")


def get_ports_config(location_folder=None):
    """Odczytuje konfigurację portów z .env."""
    config = {"MAIN_SERVER_PORT": 5000, "GENEALOGY_EDITOR_PORT": 5001, "PARCEL_EDITOR_PORT": 5003}
    mapping = {"FLASK_PORT": "MAIN_SERVER_PORT", "GENEALOGY_EDITOR_PORT": "GENEALOGY_EDITOR_PORT", "PARCEL_EDITOR_PORT": "PARCEL_EDITOR_PORT"}
    backend_env_path = os.path.join(PROJECT_DIR, "backend", ".env")
    # SQLite: porty są w backend/.env. PostgreSQL/legacy: w .env miejscowości.
    env_path = backend_env_path if os.getenv("DB_ENGINE", "").lower() == "sqlite" else (os.path.join(location_folder, ".env") if location_folder else backend_env_path)
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key, value = key.strip(), value.strip().strip('"').strip("'")
                        if key in mapping and mapping[key] in config:
                            try:
                                config[mapping[key]] = int(value)
                            except ValueError:
                                pass
        except Exception:
            pass
    return config


def is_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) != 0


def find_available_port(start, max_attempts=10):
    for offset in range(max_attempts):
        p = start + offset
        if is_port_available(p):
            return p
    return None


def is_port_open(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0


# ==========================================================================
# OPERACJE NA DANYCH (JSON)
# ==========================================================================

def _get_storage_data():
    if not GENEALOGIA_JSON_PATH or not os.path.exists(GENEALOGIA_JSON_PATH):
        return {"persons": []}
    with open(GENEALOGIA_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_storage_data(data):
    os.makedirs(os.path.dirname(GENEALOGIA_JSON_PATH), exist_ok=True)
    with open(GENEALOGIA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def _convert_to_storage_format(frontend_data, existing_person=None):
    """Konwertuje dane z frontu (PL) na format storage (EN)."""
    try:
        pid = int(frontend_data.get("id_osoby"))
    except (TypeError, ValueError):
        pid = int(time.time())

    imie = frontend_data.get("imie", "").strip()
    nazwisko = frontend_data.get("nazwisko", "").strip()
    full_name = f"{imie} {nazwisko}".strip()

    b_year = frontend_data.get("rok_urodzenia")
    d_year = frontend_data.get("rok_smierci")

    fid = frontend_data.get("id_ojca")
    mid = frontend_data.get("id_matki")

    marriages_data = frontend_data.get("marriages", [])
    spouse_ids = []
    if marriages_data:
        for m in marriages_data:
            sid = m.get("spouse_json_id")
            if sid:
                try:
                    spouse_ids.append(int(sid))
                except (TypeError, ValueError):
                    pass

    if not spouse_ids and frontend_data.get("id_malzonka"):
        try:
            spouse_ids.append(int(frontend_data.get("id_malzonka")))
        except (TypeError, ValueError):
            pass

    gender = frontend_data.get("plec", existing_person.get("gender", "M") if existing_person else "M")
    protocol = frontend_data.get("protokol_klucz")
    notes = frontend_data.get("uwagi", "")

    return {
        "id": pid,
        "name": full_name,
        "gender": gender,
        "birthDate": {"year": int(b_year)} if b_year else None,
        "deathDate": {"year": int(d_year)} if d_year else None,
        "fatherId": int(fid) if fid else None,
        "motherId": int(mid) if mid else None,
        "spouseIds": spouse_ids,
        "protokolKey": protocol if protocol else None,
        "notes": notes,
        "houseNumber": frontend_data.get("numer_domu")
    }


def _transform_person(person):
    """Konwertuje osobę z formatu storage na format frontendu."""
    name_parts = person["name"].split(" ", 1)
    imie = name_parts[0] if name_parts else ""
    nazwisko = name_parts[1] if len(name_parts) > 1 else ""

    spouse_ids = person.get("spouseIds", [])
    if not isinstance(spouse_ids, list):
        spouse_ids = [spouse_ids] if spouse_ids else []

    marriages = []
    if spouse_ids:
        for sid in spouse_ids:
            marriages.append({"spouseId": str(sid), "date": ""})

    return {
        "id_osoby": str(person["id"]),
        "db_id": str(person["id"]),
        "imie": imie,
        "nazwisko": nazwisko,
        "rok_urodzenia": person.get("birthDate", {}).get("year") if person.get("birthDate") else None,
        "rok_smierci": person.get("deathDate", {}).get("year") if person.get("deathDate") else None,
        "id_ojca": str(person["fatherId"]) if person.get("fatherId") else None,
        "id_matki": str(person["motherId"]) if person.get("motherId") else None,
        "id_malzonka": str(spouse_ids[0]) if spouse_ids else None,
        "marriages": marriages,
        "protokol_klucz": person.get("protokolKey"),
        "plec": person.get("gender", "M"),
        "numer_domu": person.get("houseNumber"),
        "uwagi": person.get("notes", ""),
    }


def _surname_matches(surname, target):
    """Porównuje nazwiska z normalizacją polskich znaków."""
    trans = str.maketrans("ąćęłńóśżźĄĆĘŁŃÓŚŻŹ", "acelnoszzACELNOSZZ")
    norm = lambda s: "".join(ch for ch in s.translate(trans).lower() if ch.isalnum())
    return norm(target) in norm(surname)


# ==========================================================================
# API PROTOKOŁÓW
# ==========================================================================

@app.get("/api/protocols")
async def get_protocols():
    if not OWNER_JSON_PATH or not os.path.exists(OWNER_JSON_PATH):
        return []
    try:
        with open(OWNER_JSON_PATH, "r", encoding="utf-8") as f:
            owner_data = json.load(f)
        return [
            {
                "key": key,
                "name": data.get("ownerName", "Brak nazwy"),
                "orderNumber": data.get("orderNumber", "N/A"),
            }
            for key, data in owner_data.items()
        ]
    except Exception as e:
        raise HTTPException(500, str(e))


# ==========================================================================
# API GENEALOGII (CRUD)
# ==========================================================================

@app.get("/api/genealogia")
async def get_genealogia():
    if not GENEALOGIA_JSON_PATH or not os.path.exists(GENEALOGIA_JSON_PATH):
        return []
    try:
        with open(GENEALOGIA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        persons = data.get("persons", []) if isinstance(data, dict) else data
        return [_transform_person(p) for p in persons]
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/genealogia")
async def create_person(request: Request):
    try:
        new_p = await request.json()
        if not new_p.get("id_osoby"):
            raise HTTPException(400, "Brak ID osoby")

        data = _get_storage_data()
        persons = data.get("persons", [])

        if any(str(p["id"]) == str(new_p["id_osoby"]) for p in persons):
            raise HTTPException(400, "Osoba o takim ID już istnieje")

        storage_person = _convert_to_storage_format(new_p)
        persons.append(storage_person)
        data["persons"] = persons
        _save_storage_data(data)
        return new_p
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.put("/api/genealogia/{person_id}")
async def update_person(person_id: str, request: Request):
    try:
        update_data = await request.json()
        data = _get_storage_data()
        persons = data.get("persons", [])

        idx = next((i for i, p in enumerate(persons) if str(p["id"]) == str(person_id)), -1)
        if idx == -1:
            raise HTTPException(404, "Osoba nie znaleziona")

        existing = persons[idx]
        updated = _convert_to_storage_format(update_data, existing)
        persons[idx] = updated
        data["persons"] = persons
        _save_storage_data(data)
        return update_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/genealogia/{person_id}")
async def delete_person(person_id: str):
    try:
        data = _get_storage_data()
        persons = data.get("persons", [])
        initial_len = len(persons)
        persons = [p for p in persons if str(p["id"]) != str(person_id)]
        if len(persons) == initial_len:
            raise HTTPException(404, "Osoba nie znaleziona")
        data["persons"] = persons
        _save_storage_data(data)
        return {"message": "Usunięto pomyślnie"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ==========================================================================
# API DRZEWA GENEALOGICZNEGO
# ==========================================================================

@app.get("/api/genealogia/drzewo/{family_name}")
async def get_family_tree(family_name: str):
    if not GENEALOGIA_JSON_PATH or not os.path.exists(GENEALOGIA_JSON_PATH):
        return {"people": [], "start_node_id": None}

    try:
        with open(GENEALOGIA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        all_people = [_transform_person(p) for p in data.get("persons", [])]

        # Przypadek 1: ID osoby
        specific = next((p for p in all_people if p["id_osoby"] == family_name), None)
        if specific:
            return {
                "people": [{
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
                }],
                "start_node_id": specific["id_osoby"],
            }

        # Przypadek 2: Nazwisko rodu
        family_people = []
        related_ids = set()

        for p in all_people:
            if _surname_matches(p.get("nazwisko", ""), family_name):
                family_people.append(p)
                related_ids.add(p["id_osoby"])

        if len(family_people) > 1:
            family_people = [
                p for p in family_people
                if (p.get("id_ojca") or p.get("id_matka") or p.get("id_malzonka")
                    or any(o.get("id_ojca") == p["id_osoby"]
                           or o.get("id_matki") == p["id_osoby"]
                           or o.get("id_malzonka") == p["id_osoby"]
                           for o in family_people))
            ]

        def add_related(pid):
            if not pid or pid in related_ids:
                return
            pers = next((x for x in all_people if x["id_osoby"] == pid), None)
            if not pers:
                return
            family_people.append(pers)
            related_ids.add(pid)
            add_related(pers.get("id_ojca"))
            add_related(pers.get("id_matki"))
            add_related(pers.get("id_malzonka"))

        for p in family_people.copy():
            add_related(p.get("id_ojca"))
            add_related(p.get("id_matki"))
            add_related(p.get("id_malzonka"))

        # Dodaj rodzeństwo
        newly_added = True
        while newly_added:
            newly_added = False
            parent_ids = set()
            for p in family_people:
                if p.get("id_ojca"):
                    parent_ids.add(p["id_ojca"])
                if p.get("id_matki"):
                    parent_ids.add(p["id_matki"])
            for person in all_people:
                if person["id_osoby"] in related_ids:
                    continue
                if (person.get("id_ojca") in parent_ids or person.get("id_matki") in parent_ids):
                    family_people.append(person)
                    related_ids.add(person["id_osoby"])
                    newly_added = True

        # BFS dla dzieci
        newly_added = True
        while newly_added:
            newly_added = False
            for child in all_people:
                if child["id_osoby"] in related_ids:
                    continue
                if child.get("id_ojca") in related_ids or child.get("id_matki") in related_ids:
                    family_people.append(child)
                    related_ids.add(child["id_osoby"])
                    newly_added = True

        tree_people = [{
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
            "plec": p.get("plec", "M"),
        } for p in family_people]

        root_id = next(
            (p["id"] for p in tree_people
             if _surname_matches(p["nazwisko"], family_name)
             and not p["ojciec_id"] and not p["matka_id"]),
            None
        )

        if not root_id and tree_people:
            root_id = min(
                (p for p in tree_people if p["rok_urodzenia"]),
                key=lambda x: x["rok_urodzenia"],
                default=tree_people[0]
            )["id"]

        return {"people": tree_people, "start_node_id": root_id}

    except Exception as e:
        raise HTTPException(500, str(e))


# ==========================================================================
# API KOPII ZAPASOWYCH
# ==========================================================================

@app.get("/api/genealogy/backups")
async def list_backups():
    if not BACKUP_DIR or not BACKUP_DIR.exists():
        return []
    files = [f for f in os.listdir(BACKUP_DIR) if f.startswith("genealogia_") and f.endswith(".json.bak")]
    files.sort(reverse=True)
    return files


@app.post("/api/genealogy/backups/create")
async def create_backup():
    if not GENEALOGIA_JSON_PATH or not os.path.exists(GENEALOGIA_JSON_PATH):
        raise HTTPException(404, "Plik roboczy nie istnieje.")
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"genealogia_{timestamp}.json.bak")
        shutil.copy(GENEALOGIA_JSON_PATH, backup_path)
        return {"message": "Kopia zapasowa utworzona pomyślnie.", "filename": os.path.basename(backup_path)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/genealogy/backups/restore")
async def restore_backup(request: Request):
    data = await request.json()
    filename = data.get("filename", "")
    if not filename or not filename.startswith("genealogia_") or ".." in filename:
        raise HTTPException(400, "Nieprawidłowa nazwa pliku.")
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        raise HTTPException(404, "Plik kopii zapasowej nie istnieje.")
    try:
        shutil.copy(backup_path, GENEALOGIA_JSON_PATH)
        return {"message": "Kopia zapasowa przywrócona. Odśwież stronę, aby zobaczyć zmiany."}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/genealogy/backups/{filename}")
async def delete_backup(filename: str):
    if not filename or not filename.startswith("genealogia_") or ".." in filename:
        raise HTTPException(400, "Nieprawidłowa nazwa pliku.")
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        raise HTTPException(404, "Plik kopii zapasowej nie istnieje.")
    try:
        os.remove(backup_path)
        return {"message": "Kopia zapasowa usunięta."}
    except Exception as e:
        raise HTTPException(500, str(e))


# ==========================================================================
# API KOMUNIKACJI MIĘDZY EDYTORAMI
# ==========================================================================

@app.get("/api/editor/status")
async def get_editor_status():
    if EDITOR_STATUS["last_heartbeat"]:
        time_diff = datetime.now() - EDITOR_STATUS["last_heartbeat"]
        if time_diff > timedelta(seconds=30):
            EDITOR_STATUS["is_running"] = False
            EDITOR_STATUS["address"] = None
            EDITOR_STATUS["port"] = None
    return {
        "is_running": EDITOR_STATUS["is_running"],
        "address": EDITOR_STATUS["address"],
        "port": EDITOR_STATUS["port"]
    }


@app.post("/api/editor/register")
async def register_editor(request: Request):
    data = await request.json()
    EDITOR_STATUS["is_running"] = True
    EDITOR_STATUS["address"] = data.get("address", "127.0.0.1")
    EDITOR_STATUS["port"] = data.get("port", 5000)
    EDITOR_STATUS["last_heartbeat"] = datetime.now()
    return {"status": "registered"}


@app.post("/api/editor/heartbeat")
async def editor_heartbeat():
    EDITOR_STATUS["last_heartbeat"] = datetime.now()
    return {"status": "alive"}


@app.get("/api/editor/check-main")
async def check_main_editor():
    ports_config = get_ports_config(BACKUP_DIR)
    main_port = ports_config.get("MAIN_SERVER_PORT", 5000)
    if is_port_open("127.0.0.1", main_port):
        return {"available": True, "url": f"http://127.0.0.1:{main_port}", "port": main_port}
    else:
        return {"available": False, "url": None, "port": main_port}


@app.post("/api/editor/launch-main")
async def launch_main_editor():
    try:
        launcher_path = os.path.join(PROJECT_DIR, "launcher", "launcher_app.py")
        if os.path.exists(launcher_path):
            import subprocess
            subprocess.Popen(
                [sys.executable, launcher_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(2)
            if is_port_open("127.0.0.1", 5000):
                return {"success": True, "url": "http://127.0.0.1:5000"}
        return {"success": False, "error": "Nie można uruchomić głównego edytora"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==========================================================================
# HEALTH CHECK
# ==========================================================================

@app.get("/api/health")
async def health_check():
    """Endpoint kontroli gotowości - używany przez launcher."""
    person_count = 0
    if GENEALOGIA_JSON_PATH and os.path.exists(GENEALOGIA_JSON_PATH):
        try:
            with open(GENEALOGIA_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            person_count = len(data.get("persons", []))
        except Exception:
            pass
    return {"status": "ok", "persons": person_count}


# ==========================================================================
# FRONTEND (HTML)
# ==========================================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("editor.html", {"request": request})


@app.get("/editor.html", response_class=HTMLResponse)
async def editor_page(request: Request):
    return templates.TemplateResponse("editor.html", {"request": request})


# ==========================================================================
# STATYCZNE PLIKI
# ==========================================================================

@app.get("/static/{filename:path}")
async def serve_static(filename: str):
    file_path = BASE_DIR / "static" / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(404)


# ==========================================================================
# SHUTDOWN
# ==========================================================================

@app.post("/shutdown")
async def shutdown():
    threading.Thread(target=lambda: (time.sleep(0.5), os._exit(0))).start()
    return {"status": "success"}


# ==========================================================================
# START
# ==========================================================================

if __name__ == "__main__":
    location = get_active_location()
    BACKUP_DIR = location
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Upewnij się, że pliki JSON istnieją
    gen_path = BACKUP_DIR / "genealogia.json"
    if not gen_path.exists():
        with open(gen_path, "w", encoding="utf-8") as f:
            json.dump({"persons": []}, f, indent=4, ensure_ascii=False)

    owner_path = BACKUP_DIR / "owner_data_to_import.json"
    if not owner_path.exists():
        with open(owner_path, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)

    GENEALOGIA_JSON_PATH = str(gen_path)
    OWNER_JSON_PATH = str(owner_path)

    ports = get_ports_config(location)
    configured = ports.get("GENEALOGY_EDITOR_PORT", 5001)

    port = configured if is_port_available(configured) else (find_available_port(configured + 1) or configured)

    url = f"http://127.0.0.1:{port}"

    print("=" * 50)
    print("  🌳 Edytor Genealogii")
    print(f"  🌍 Adres:     {url}")
    print(f"  📁 Dane:      {GENEALOGIA_JSON_PATH}")
    print("=" * 50)

    # Serwer w tle, przeglądarka dopiero gdy gotowy
    import requests as _requests

    def _open_browser_when_ready():
        for _ in range(30):
            try:
                _requests.get(f"http://127.0.0.1:{port}/api/health", timeout=0.5)
                webbrowser.open(url)
                return
            except Exception:
                time.sleep(0.5)

    if "--launched-by-gui" not in sys.argv:
        threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
