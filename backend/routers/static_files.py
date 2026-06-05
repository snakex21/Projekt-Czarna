"""Router plikow statycznych i legacy redirectow."""
import json as _json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response
from ..config import BASE_DIR, ACTIVE_LOCATION, BACKUP_DIR

router = APIRouter(tags=["static"])


@router.get("/location_map")
async def location_map():
    """Serwuje historyczny skan mapy aktywnej miejscowosci."""
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        map_path = BACKUP_DIR / ACTIVE_LOCATION / f"mapa{ext}"
        if map_path.exists() and map_path.is_file():
            return FileResponse(map_path)
    raise HTTPException(status_code=404, detail="Location map image not found")


def _favicon_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".ico":
        return "image/x-icon"
    return "image/x-icon"


@router.get("/location_favicon")
async def location_favicon():
    """Serwuje favicon aktywnej miejscowosci."""
    for name in ("favicon.ico", "favicon.png", "favicon.jpg", "favicon.jpeg", "favicon.webp"):
        icon_path = BACKUP_DIR / ACTIVE_LOCATION / name
        if icon_path.exists() and icon_path.is_file():
            return FileResponse(icon_path, media_type=_favicon_media_type(icon_path), headers={"Cache-Control": "no-store"})
    raise HTTPException(status_code=404, detail="Location favicon not found")


@router.get("/favicon.ico")
async def favicon_ico():
    """Fallback dla przegladarek, ktore automatycznie prosza o /favicon.ico."""
    return await location_favicon()


@router.get("/mapa/mapa.jpg")
async def legacy_map_image():
    """Kompatybilnosc z frontendem MapLibre z projektu czarna-mapa."""
    return await location_map()


@router.get("/history_photos/{filename:path}")
async def history_photo(filename: str):
    """Serwuje zdjecia historyczne z folderu backup/aktywnej_miejscowosci/history_photos."""
    photo_path = BACKUP_DIR / ACTIVE_LOCATION / "history_photos" / filename
    if photo_path.exists() and photo_path.is_file():
        return FileResponse(photo_path)
    raise HTTPException(status_code=404, detail="Photo not found")


@router.get("/point_photos/{filename:path}")
async def point_photo(filename: str):
    """Serwuje zdjęcia markerów (punktów historycznych) z folderu point_photos/.

    Osobny folder od galerii (``/history_photos/``) - tu są pliki przypisane
    do markerów na mapie (dworzec, kapliczka, …). UI: ``static/mapa/historical_points.js``.
    """
    photo_path = BACKUP_DIR / ACTIVE_LOCATION / "point_photos" / filename
    if photo_path.exists() and photo_path.is_file():
        return FileResponse(photo_path)
    raise HTTPException(status_code=404, detail="Point photo not found")


@router.get("/protokoly/{owner_key}/{filename}")
async def protocol_scan(owner_key: str, filename: str):
    """Serwuje skany protokołu wlasciciela z folderu backup/aktywnej_miejscowosci/protokoly/{owner_key}/."""
    # Ochrona przed wyjsciem poza katalog protokoly (path traversal).
    if any(sep in owner_key for sep in ("..", "/", "\\")):
        raise HTTPException(status_code=400, detail="Invalid owner key")
    if any(sep in filename for sep in ("..", "/", "\\")):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    scan_path = BACKUP_DIR / ACTIVE_LOCATION / "protokoly" / owner_key / filename
    if scan_path.exists() and scan_path.is_file():
        return FileResponse(scan_path, media_type=_scan_media_type(scan_path))
    raise HTTPException(status_code=404, detail="Protocol scan not found")


def _scan_media_type(path: Path) -> str:
    """Zwraca MIME type dla skanu protokołu na podstawie rozszerzenia."""
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


@router.get("/dokumentacja/{filename:path}")
async def serve_dokumentacja(filename: str):
    """Serwuje pliki dokumentacji papierowej (PDF, DOCX)."""
    doc_path = BASE_DIR / "dokumentacja" / filename
    if doc_path.exists() and doc_path.is_file():
        return FileResponse(doc_path)
    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/location_js/location-config.js")
async def location_config_js():
    """Konfiguracja miejscowosci - laduje dane z launcher_db_config.json aktywnej miejscowosci."""
    config = {
        "name": ACTIVE_LOCATION,
        "fullName": ACTIVE_LOCATION,
        "year": "1882",
        "century": "XIX w.",
        "powiat": "",
        "region": "",
        "homepageDescription": "",
        "historyParagraph1": "",
        "historyParagraph2": "",
        "historyParagraph3": "",
        "historyPhotos": [],
    }

    json_path = BACKUP_DIR / ACTIVE_LOCATION / "launcher_db_config.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw = _json.load(f)
            loc = raw.get("default_location", raw)
            config["name"] = loc.get("name", config["name"])
            config["fullName"] = loc.get("full_name", config["fullName"])
            config["powiat"] = loc.get("powiat", "")
            config["region"] = loc.get("region", "")
            config["year"] = loc.get("year", "1882")
            config["century"] = loc.get("century", "XIX w.")
            config["homepageDescription"] = loc.get("homepage_description", "")
            config["historyParagraph1"] = loc.get("history_paragraph1", "")
            config["historyParagraph2"] = loc.get("history_paragraph2", "")
            config["historyParagraph3"] = loc.get("history_paragraph3", "")
            config["historyPhotos"] = loc.get("history_photos", [])
        except Exception as e:
            print(f"WARN: Blad wczytywania {json_path}: {e}")

    js = (
        "window.LOCATION_CONFIG = window.LOCATION_CONFIG || {\n"
        f"  name: {_json.dumps(config['name'], ensure_ascii=False)},\n"
        f"  fullName: {_json.dumps(config['fullName'], ensure_ascii=False)},\n"
        f"  powiat: {_json.dumps(config['powiat'], ensure_ascii=False)},\n"
        f"  region: {_json.dumps(config['region'], ensure_ascii=False)},\n"
        f"  year: {_json.dumps(config['year'], ensure_ascii=False)},\n"
        f"  century: {_json.dumps(config['century'], ensure_ascii=False)},\n"
        f"  homepageDescription: {_json.dumps(config['homepageDescription'], ensure_ascii=False)},\n"
        f"  historyParagraph1: {_json.dumps(config['historyParagraph1'], ensure_ascii=False)},\n"
        f"  historyParagraph2: {_json.dumps(config['historyParagraph2'], ensure_ascii=False)},\n"
        f"  historyParagraph3: {_json.dumps(config['historyParagraph3'], ensure_ascii=False)},\n"
        f"  historyPhotos: {_json.dumps(config['historyPhotos'], ensure_ascii=False)}\n"
        "};\n"
    )
    return Response(js, media_type="application/javascript", headers={"Cache-Control": "no-store"})


@router.get("/location_js/location-data.js")
async def location_data_js():
    """Serwuje skrypt location-data.js ktory zamienia {{placeholder}} na dane z LOCATION_CONFIG."""
    script_path = Path(__file__).parent.parent.parent / "static" / "js" / "location-data.js"
    if script_path.exists():
        content = script_path.read_text(encoding="utf-8")
        return Response(content, media_type="application/javascript", headers={"Cache-Control": "no-store"})
    return Response("// location-data.js not found", media_type="application/javascript")


@router.get("/")
async def root():
    """Przekierowanie na strone glowna (sciezka absolutna aby dzialaly CSS/JS)."""
    return RedirectResponse(url="/strona_glowna/index.html")


@router.get("/admin")
async def admin_redirect():
    """Przekierowanie /admin na /admin/admin.html."""
    return RedirectResponse(url="/admin/admin.html")


@router.get("/admin/admin.html")
async def admin_html():
    """Serwuje panel administracyjny."""
    admin_path = BASE_DIR / "static" / "admin" / "admin.html"
    if admin_path.exists():
        return FileResponse(admin_path, headers={"Cache-Control": "no-store"})
    raise HTTPException(status_code=404, detail="Admin panel not found")


FRONTEND_DIR = BASE_DIR / "static"


@router.get("/{filename:path}")
async def serve_static(filename: str):
    """Serwuje pliki statyczne z katalogu projektu."""
    blocked_patterns = [".env", ".git", "__pycache__", "*.py", "*.sql", "*.db"]
    for pattern in blocked_patterns:
        if pattern.startswith("*"):
            if filename.endswith(pattern[1:]):
                raise HTTPException(status_code=404, detail="Not found")
        elif pattern in filename:
            raise HTTPException(status_code=404, detail="Not found")

    file_path = FRONTEND_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path, headers={"Cache-Control": "no-store"})
    index_path = BASE_DIR / "static" / "strona_glowna" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "File not found"}
