"""
Edytor Mapy Katastralnej - FastAPI (wiernie przepisany z Flask).
Dziala na JSON-ie: czyta/zapisuje parcels_data.json w folderze aktywnej miejscowosci.
"""
import os
import sys
import json
import shutil
import threading
import webbrowser
import socket
import time
from datetime import datetime
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

app = FastAPI(title="Edytor Mapy Katastralnej")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Statyczne pliki i templatki (dokladnie jak w starym Flask)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# Serwowanie plikow statycznych przez sciezki
@app.get("/static/{filename:path}")
async def serve_static(filename: str):
    # mapa.jpg - z folderu lokacji (BACKUP_DIR)
    if filename == "mapa.jpg":
        mapa = BACKUP_DIR / "mapa.jpg" if BACKUP_DIR else None
        if mapa and mapa.exists():
            return FileResponse(mapa)
    # pozostale pliki - z local static/
    file_path = BASE_DIR / "static" / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(404)

map_config = {}
parcels_data = {}
BACKUP_DIR = None
DATA_FILE_PATH = None


def get_ports_config(location_folder=None):
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
                            try: config[mapping[key]] = int(value)
                            except ValueError: pass
        except Exception: pass
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


def get_active_location():
    # Najpierw sprawdź zmienne środowiskowe (najszybsza ścieżka)
    loc = os.getenv("ACTIVE_LOCATION")
    if loc:
        return PROJECT_DIR / "data" / "locations" / loc
    
    # Sprawdź czy launcher ustawił DB_ENGINE - jeśli sqlite, pomiń PostgreSQL
    db_engine = os.getenv("DB_ENGINE", "").lower()
    
    if db_engine != "sqlite":
        # PostgreSQL z timeoutem 2s (bez niego psycopg2 może wisieć ~30s)
        try:
            import psycopg2
            conn = psycopg2.connect(host=os.getenv("DB_HOST", "localhost"), dbname="mapa_launcher_db",
                                    user=os.getenv("DB_USER", "postgres"), password=os.getenv("DB_PASSWORD", "1234"),
                                    port=os.getenv("DB_PORT", "5432"), connect_timeout=2)
            cur = conn.cursor(); cur.execute("SELECT name FROM locations WHERE active = TRUE LIMIT 1"); row = cur.fetchone(); conn.close()
            if row: return PROJECT_DIR / "data" / "locations" / row[0]
        except Exception: pass
    
    # SQLite fallback
    db_path = PROJECT_DIR / "data" / "locations.db"
    if db_path.exists():
        try:
            import sqlite3; conn = sqlite3.connect(str(db_path)); cur = conn.cursor()
            cur.execute("SELECT name FROM locations WHERE active = 1"); row = cur.fetchone(); conn.close()
            if row: return PROJECT_DIR / "data" / "locations" / row[0]
        except Exception: pass
    return PROJECT_DIR / "data" / "locations" / os.getenv("TEST_LOCATION", "Czarna")


def load_map_config():
    global map_config
    config_path = BACKUP_DIR / "map_config.json"
    defaults = {"calibration": {"sw": {"lat": 50.0414, "lng": 21.2261}, "ne": {"lat": 50.0814, "lng": 21.2661}},
                "defaults": {"center": {"lat": 50.0614, "lng": 21.2461}, "zoom": 14}}
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f: map_config = json.load(f)
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f: json.dump(defaults, f, indent=4, ensure_ascii=False)
            map_config = defaults
    except Exception: map_config = defaults


def load_data():
    global parcels_data
    try:
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f: parcels_data = json.load(f)
        print(f"  🗺️  Załadowano {len(parcels_data)} działek")
    except (FileNotFoundError, json.JSONDecodeError):
        parcels_data = {}
        print("  📭 Brak danych - nowa baza działek")


def save_data():
    try:
        os.makedirs(os.path.dirname(DATA_FILE_PATH), exist_ok=True)
        with open(DATA_FILE_PATH, "w", encoding="utf-8") as f: json.dump(parcels_data, f, indent=4, ensure_ascii=False)
    except Exception as e: print(f"[PARCEL] Blad zapisu: {e}")


# === API (identyczne jak stary Flask) ===
@app.get("/api/health")
async def health_check():
    """Endpoint kontroli gotowości - używany przez launcher."""
    return {"status": "ok", "parcels": len(parcels_data)}

@app.get("/api/parcels")
async def get_parcels():
    return parcels_data


@app.post("/api/parcels")
async def add_parcel(request: Request):
    data = await request.json()
    parcel_id = data.get("id", "")
    parcel_info = data.get("parcel", {})
    category = parcel_info.get("kategoria", "")
    full_key = f"{parcel_id}_{category}" if category else parcel_id
    if full_key in parcels_data:
        raise HTTPException(409, f"Dzialka '{parcel_id}' typu '{category}' juz istnieje")
    parcels_data[full_key] = parcel_info
    save_data()
    return {"status": "success", "full_key": full_key, "message": f"Dodano obiekt '{parcel_id}'"}


@app.post("/api/parcel")
async def add_parcel_legacy(request: Request):
    """Alias dla frontendu edytora. Wcześniej JS wysyłał POST /api/parcel,
    a backend miał tylko POST /api/parcels, co dawało 405 Method Not Allowed."""
    return await add_parcel(request)


@app.put("/api/parcel/{parcel_id:path}")
async def update_parcel(parcel_id: str, request: Request):
    if parcel_id not in parcels_data:
        raise HTTPException(404, "Dzialka nie istnieje")
    data = await request.json()
    geo = data.get("geometria")
    if not geo: raise HTTPException(400, "Brak geometrii")
    parcels_data[parcel_id]["geometria"] = geo
    save_data()
    return {"status": "success", "message": "Zapisano zmiany geometrii"}


@app.patch("/api/parcel/{parcel_id:path}/category")
async def change_category(parcel_id: str, request: Request):
    if parcel_id not in parcels_data:
        raise HTTPException(404, "Dzialka nie istnieje")
    data = await request.json()
    new_cat = data.get("kategoria", "")
    if not new_cat: raise HTTPException(400, "Brak kategorii")
    content = parcels_data[parcel_id]
    old_cat = content.get("kategoria", "")
    if old_cat == new_cat:
        return {"status": "success", "message": "Typ bez zmian"}
    last_us = parcel_id.rfind(f"_{old_cat}")
    base = parcel_id[:last_us] if last_us > 0 else parcel_id
    new_key = f"{base}_{new_cat}"
    if new_key in parcels_data:
        raise HTTPException(409, f"Dzialka juz istnieje")
    content["kategoria"] = new_cat
    items = list(parcels_data.items())
    idx = next((i for i, (k, _) in enumerate(items) if k == parcel_id), -1)
    del parcels_data[parcel_id]
    new_items = [(k, v) for k, v in items if k != parcel_id]
    new_items.insert(idx, (new_key, content))
    parcels_data.clear(); parcels_data.update(new_items)
    save_data()
    return {"status": "success", "full_key": new_key, "message": "Zmieniono typ obiektu"}


@app.patch("/api/parcel/rename/{old_id:path}")
async def rename_parcel(old_id: str, request: Request):
    if old_id not in parcels_data:
        raise HTTPException(404, "Dzialka nie istnieje")
    data = await request.json()
    new_id = data.get("new_id", "")
    if not new_id: raise HTTPException(400, "Brak nowego ID")
    content = parcels_data[old_id]
    cat = content.get("kategoria", "")
    new_key = f"{new_id}_{cat}" if cat else new_id
    if new_key in parcels_data and new_key != old_id:
        raise HTTPException(409, f"ID zajete")
    items = list(parcels_data.items())
    idx = next((i for i, (k, _) in enumerate(items) if k == old_id), -1)
    del parcels_data[old_id]
    new_items = [(k, v) for k, v in items if k != old_id]
    new_items.insert(idx, (new_key, content))
    parcels_data.clear(); parcels_data.update(new_items)
    save_data()
    return {"status": "success", "full_key": new_key, "message": "Zmieniono nazwę obiektu"}


@app.delete("/api/parcels/delete_all")
async def delete_all():
    parcels_data.clear(); save_data()
    return {"status": "success", "message": "Usunięto wszystkie obiekty"}


@app.delete("/api/parcel/{parcel_id:path}")
async def delete_parcel(parcel_id: str):
    if parcel_id not in parcels_data:
        raise HTTPException(404, "Dzialka nie istnieje")
    del parcels_data[parcel_id]; save_data()
    return {"status": "success", "message": "Usunięto obiekt"}


# === BACKUP ===
@app.get("/api/backups")
async def list_backups():
    if not BACKUP_DIR or not BACKUP_DIR.exists(): return []
    return sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".json") and "backup" in f], reverse=True)


@app.post("/backup")
async def create_backup():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = BACKUP_DIR / f"parcels_data_backup_{ts}.json"
    save_data(); shutil.copy2(DATA_FILE_PATH, p)
    return {"status": "success", "message": "Utworzono kopię zapasową"}


@app.post("/restore")
async def restore_backup(request: Request):
    data = await request.json()
    fn = data.get("filename", "")
    if not fn: raise HTTPException(400, "Brak nazwy")
    src = BACKUP_DIR / fn
    if not src.is_file() or not str(src.resolve()).startswith(str(BACKUP_DIR.resolve())):
        raise HTTPException(404, "Plik nie istnieje")
    shutil.copy2(src, DATA_FILE_PATH); load_data()
    return {"status": "success", "message": "Przywrócono kopię zapasową"}


@app.post("/delete_backup")
async def delete_backup(request: Request):
    data = await request.json()
    fn = data.get("filename", "")
    if not fn or not fn.endswith(".json") or "backup" not in fn:
        raise HTTPException(400, "Nieprawidlowa nazwa")
    p = BACKUP_DIR / fn
    if not p.is_file() or not str(p.resolve()).startswith(str(BACKUP_DIR.resolve())):
        raise HTTPException(404)
    os.remove(p)
    return {"status": "success", "message": "Usunięto kopię zapasową"}


# === INTERFEJS (dokladnie jak stary Flask) ===
@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("template.html", {"request": request, "map_config_data": map_config})


@app.get("/template.html")
async def template(request: Request):
    return templates.TemplateResponse("template.html", {"request": request, "map_config_data": map_config})


def _delayed_shutdown():
    """Zamyka proces po krótkim opóźnieniu, żeby przeglądarka zdążyła odebrać odpowiedź."""
    time.sleep(0.5)
    os._exit(0)


@app.post("/shutdown")
async def shutdown():
    threading.Thread(target=_delayed_shutdown, daemon=True).start()
    return {"status": "success"}


@app.post("/api/shutdown")
async def api_shutdown():
    return await shutdown()


# === START ===
if __name__ == "__main__":
    location = get_active_location()
    BACKUP_DIR = location
    DATA_FILE_PATH = BACKUP_DIR / "parcels_data.json"
    os.makedirs(BACKUP_DIR, exist_ok=True)
    load_data()
    load_map_config()

    ports = get_ports_config(location)
    configured = ports.get("PARCEL_EDITOR_PORT", 5003)

    port = configured if is_port_available(configured) else (find_available_port(configured + 1) or configured)

    url = f"http://127.0.0.1:{port}/template.html"

    print("=" * 50)
    print("  🗺️  Edytor Mapy Katastralnej")
    print(f"  🌍 Adres:     {url}")
    print(f"  📦 Działki:   {len(parcels_data)} obiektów")
    print(f"  📁 Dane:      {DATA_FILE_PATH}")
    print("=" * 50)

    # Serwer w tle, przegladarka dopiero gdy gotowy
    import requests as _requests

    def _open_browser_when_ready():
        import time
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
