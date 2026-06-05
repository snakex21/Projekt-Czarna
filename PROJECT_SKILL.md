# PROJECT_SKILL — Mapa Katastralna Czarna (Python 3.11+ / FastAPI)

> Konwencje kodu dla agentów AI. Zwięzły - pełna dokumentacja w `docs/`.

## Język i technologie

- **Backend:** Python 3.11+ (testowane 3.13.7), FastAPI, uvicorn, SQLAlchemy async, Werkzeug
- **Baza:** SQLite (default) / PostgreSQL + PostGIS (planowany, Priorytet 2)
- **Frontend:** HTML/CSS/JS ES6+ (bez bundlerów), MapLibre GL
- **Launcher GUI:** Python 3 Tkinter, Pillow
- **Testy:** pytest, FastAPI TestClient, Playwright (E2E)

## Architektura (stan czerwiec 2026)

```text
Projekt Mapa Czarna/
├── backend/                     # FastAPI
│   ├── main.py                  # app + lifespan (CORS, SECRET_KEY assert)
│   ├── config.py                # env, SECRET_KEY, DB_ENGINE, PRODUCTION
│   ├── db.py                    # SQLAlchemy async engine
│   ├── routers/                 # cienkie I/O (FastAPI)
│   │   ├── map.py, owners.py, genealogy.py, editor.py
│   │   ├── admin.py, admin_auth.py, diagnostics.py
│   │   ├── historical_points.py, stats.py
│   │   └── static_files.py      # catch-all /{filename:path} (ostatni)
│   ├── services/                # logika (czyste funkcje, bez Depends)
│   │   ├── diagnostics_service.py
│   │   ├── ownership_service.py, stats_service.py
│   │   ├── genealogy_service.py, geo_utils.py
│   ├── auth/                    # bezpieczeństwo admina (P6)
│   │   ├── routes.py            # login, logout, change-password
│   │   └── security.py          # is_default_*, assert_safe_secret_key, get_cors_*
│   ├── scripts/                 # jednorazowe migracje
│   └── tests/                   # unit + integration + e2e
│
├── launcher/                    # GUI (Tkinter)
│   ├── launcher_app.py          # główne okno (NOT do importowania z services/)
│   ├── services/                # logika (process, env, network, location)
│   ├── ui/                      # dialogi (wyłącznie delegacja do services)
│   ├── config/                  # paths.py, settings.py (SCRIPTS, URLS)
│   └── utils/                   # helpery (process_env, network, ...)
│
├── static/                      # frontend (serwowany przez FastAPI)
│   ├── mapa/                    # mapa publiczna (MapLibre GL)
│   ├── admin/                   # panel admina (+ diagnostics)
│   └── wlasciciele/             # protokoły
│
├── data/
│   ├── locations.db             # rejestr miejscowości (SQLite)
│   ├── czarna.db                # SQLite aktywnej miejscowości (dev)
│   └── locations/<Nazwa>/       # dane per-miejscowość
│       ├── .env, *.json, mapa.jpg
│       ├── point_photos/        # markery (P3.1)
│       └── history_photos/      # galeria
│
├── tools/                       # edytory dedykowane (owner, parcel, genealogy)
├── docs/                        # akademicka dokumentacja HTML (praca inż.)
│   └── technical/               # dokumentacja techniczna Markdown
├── requirements.txt
├── pytest.ini
├── .gitignore
├── README.md, TODO.md           # ten plik
└── PROJECT_SKILL.md             # ten plik (dla agentów AI)
```

## Zasady (obowiązkowe)

1. **FastAPI + asyncio.** Żadnego Flask. Async/await w routerach, SQLAlchemy async.
2. **Thin router / fat service.** Routery mają tylko I/O + zależności. Logika w `services/`.
3. **Kolejność routerów:** specyficzne PRZED `static_files.router` (catch-all `/{filename:path}`).
4. **Kolejność JS:** moduły (`api.js`, `utils.js`, `notifications.js`, ...) PRZED `admin.js` w `<script>`.
5. **Moduły JS:** rejestracja jako `window.<Feature> = Object.freeze({...})`. Brak bundlerów.
6. **Logika poza UI.** `launcher/ui/*` deleguje do `launcher/services/*`. Brak I/O w UI.
7. **Kierunek importów:**
   - `launcher/*` → `backend/*` ✅ (np. `backend.auth.security`)
   - `backend/*` → `launcher/*` ❌ (ZAKAZ - cykliczność)
   - `ui/*` → `routers/*` ❌ (UI w launcherze nie woła API; robi to frontend)
8. **TDD.** Testy przed kodem, regresja po każdej fazie. Mock przez `monkeypatch`, nie globalne ustawienia.
9. **Polski UI / angielski kod.** UI, komentarze UI, etykiety, komunikaty - po polsku. Identyfikatory, klucze JSON, nazwy zmiennych - po angielsku.
10. **Env-driven config.** Wszystko z `backend/.env` (z fallbackami w `config.py`). Brak hardcoded URL/portów.
11. **Nie commituj sekretów.** `.env`, `.postgres.env`, `data/locations/*/.env` w `.gitignore`.
12. **Bez lazy importów** w modułach (poza specyficznymi przypadkami w `network_runtime` dla testowalności).

## Konwencje kodowania

### Python

- Type hints (3.11+ syntax: `list[str]`, `dict[str, int]`, `X | None`).
- snake_case dla zmiennych/funkcji, PascalCase dla klas.
- Docstring po polsku (krótki, 1-2 linie).
- Wyjątki: `HTTPException(status_code=..., detail="...")` w routerach.
- Env vars: `os.getenv("FOO", "default")` - wielkimi literami.
- Ścieżki: `pathlib.Path`, nie stringi.

### JavaScript

- camelCase dla zmiennych/funkcji, PascalCase dla klas/konstruktorów.
- Funkcje modułu: `function _private()` (underscore) + publiczne w `Object.freeze({...})`.
- API fetch: `credentials: 'same-origin'` (ważne dla cookie session admina).
- Polskie etykiety/komunikaty w UI, angielskie identyfikatory.
- Brak jQuery, brak React, brak bundlerów.

### SQL

- Nazwy tabel: `snake_case`, liczba mnoga lub specyficzna (`wlasciciele`, `obiekty_geograficzne`).
- JOIN: `INNER JOIN` na FK, `LEFT JOIN` gdy chcemy NULL.
- Sample: zawsze `LIMIT 10` (diagnostyka).

## Wzorce

### FastAPI router (cienki)

```python
# backend/routers/<feature>.py
from fastapi import APIRouter, Depends
from backend.services import <feature>_service

router = APIRouter(prefix="/api", tags=["<feature>"])

@router.get("/<feature>")
async def list_<feature>(db=Depends(get_db), _=Depends(admin_required)):
    return await <feature>_service.list_all(db)
```

### Service (logika)

```python
# backend/services/<feature>_service.py
async def list_all(db) -> list[dict]:
    result = await db.execute(select(Model).order_by(Model.id))
    return [row.to_dict() for row in result.scalars()]
```

### Moduł JS frontend

```js
// static/<area>/js/<feature>.js
(function () {
    'use strict';

    function _escape(text) { /* ... */ }
    function _getApi() { return window.AdminAPI.<feature>; }
    async function load() { /* fetch + parse */ }
    function render(data) { /* DOM */ }
    async function refresh() { /* load + render */ }

    window.Admin<Feature> = Object.freeze({ load, render, refresh });
})();
```

### Test kontraktu UI (regex na źródło)

```python
# backend/tests/unit/test_<feature>_contract.py
def test_module_registers_window_namespace():
    source = (Path("static/area/js/feature.js")).read_text(encoding="utf-8")
    assert "window.AdminFeature" in source
    assert "Object.freeze" in source
```

### Walidacja (Pydantic w routerze, dataclass w service)

```python
# Router: Pydantic
class <Feature>Request(BaseModel):
    name: str
    value: int

@router.post("/<feature>")
async def create(req: <Feature>Request, db=Depends(get_db)):
    return await service.create(db, req)

# Service: dataclass
@dataclass
class <Feature>:
    name: str
    value: int
```

## Anti-wzorce (ZAKAZ)

- ❌ Logika w routerach (powyżej 30 linii per endpoint).
- ❌ Importy `launcher.*` w `backend/*`.
- ❌ Bezpośrednie I/O (file/DB/subprocess) w `launcher/ui/*`.
- ❌ Globalny mutable state poza `backend/config.py`.
- ❌ `time.sleep()` w testach (kruche).
- ❌ Catch-all `except Exception: pass` w produkcji.
- ❌ Testy bez asercji (pytest warning).
- ❌ Hardcoded URL-e/porty w kodzie.
- ❌ `cursor: pointer` na elementach nie-klikalnych.
- ❌ Moduły JS > 300 linii (wydzielaj).
- ❌ Komentarze po angielsku w UI (po polsku).

## Bezpieczeństwo admina (Priorytet 6 - obowiązkowe)

- Hasło: Werkzeug hash w `.env` (`scrypt:...`). Backend akceptuje też SHA-256 hex.
- Cookie session: `HttpOnly`, `SameSite=Lax`, `Secure` w produkcji.
- Walidacja startup: `assert_safe_secret_key()` blokuje produkcję z fallbackiem.
- Tryb sieciowy: ostrzeżenie gdy `ADMIN_AUTH_ENABLED=False`.
- CORS: env `CORS_ALLOWED_ORIGINS` (w produkcji brak → `ValueError`).
- Nigdy nie loguj haseł/sekretów.

Pełne: [docs/technical/SECURITY.md](docs/technical/SECURITY.md).

## Uruchomienie

```bash
# Instalacja
pip install -r requirements.txt

# Backend (dev)
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5000

# Launcher GUI
python launcher/launcher_app.py
```

## Testy

```bash
# Pełny pakiet CI (1038 testy + 9 skip PG E2E; nie wymaga żadnych --ignore)
python -m pytest backend/tests/

# Real-install test (wymaga internetu, ~35s, domyślnie skipped)
$env:RUN_REAL_INSTALL=1; python -m pytest backend/tests/integration/test_pg_portable_real_install.py -v -s

# Real-install pełen E2E (CLI, 7/7 kroków, ~24s warm)
python scripts/test_pg_portable_real_install.py

# Konkretny moduł
python -m pytest backend/tests/unit/test_diagnostics_service.py

# Verbose
python -m pytest backend/tests/ -v
```

Pełne konwencje TDD: [docs/technical/TESTING.md](docs/technical/TESTING.md).

## Status projektu

**1038 testy zielone w pełnej regresji + 9 skipped (PG E2E — auto-skip gdy brak instancji PostgreSQL + real-install skipped domyślnie)** (czerwiec 2026).
Ukończone priorytety: 1, 2 (kreator migracji), 2.1 (portable PG, w tym uninstall flow 1.1.1 + refaktoryzacja lokalizacji 1.1.2 na `<root>/.runtime/postgres/` + 5 bugów real-install 1.1.3), 2.5/Etap 1-13, 2.7/Etap 1-5E, 2.8/Etap 1-21, 2.9/Etap 1, 3, 3.1, 4, 4.1, 5, 5.1, 6.
Otwarte: P2.7/kolejne etapy (ew. domknięcie compare.js), P2.8/kolejne etapy (`stats-script.js`), security hardening (rate-limit/2FA/audit), tag v1.0.0.

Pełne: [TODO.md](TODO.md), [docs/technical/ROADMAP.md](docs/technical/ROADMAP.md).

## Zobacz też

- [README.md](README.md) - wejście do projektu
- [TODO.md](TODO.md) - szczegółowy plan prac
- [docs/technical/](docs/technical/) - pełna dokumentacja techniczna
