# Architektura systemu

> Cel: jedno miejsce opisujące warstwy, decyzje projektowe i granice odpowiedzialności.

## 1. Przegląd wysokopoziomowy

System składa się z czterech logicznych warstw, komunikujących się przez jasne interfejsy:

```text
┌──────────────────────────────────────────────────────────────┐
│ 1. FRONTEND (przeglądarka)                                  │
│    static/mapa/  static/admin/  static/wlasciciele/         │
└──────────────────────────────────────────────────────────────┘
                       ▲ JSON REST (HTTP)
                       │ cookie session dla admina
┌──────────────────────────────────────────────────────────────┐
│ 2. BACKEND (FastAPI + uvicorn)                              │
│    backend/main.py      ← app + lifespan (security)         │
│    backend/routers/     ← cienkie I/O (FastAPI)             │
│    backend/services/    ← logika biznesowa                  │
│    backend/auth/        ← bezpieczeństwo admina             │
└──────────────────────────────────────────────────────────────┘
                       ▲ SQLAlchemy async
                       │ asyncpg (PostgreSQL) / aiosqlite
┌──────────────────────────────────────────────────────────────┐
│ 3. BAZA DANYCH                                               │
│    SQLite (data/czarna.db)            ← dev/test            │
│    PostgreSQL + PostGIS (planowany)   ← produkcja           │
└──────────────────────────────────────────────────────────────┘
                       ▲ subprocess.Popen + env vars
                       │
┌──────────────────────────────────────────────────────────────┐
│ 4. LAUNCHER (Tkinter GUI)                                   │
│    launcher/launcher_app.py  ← główne okno                  │
│    launcher/services/        ← logika (process, env...)     │
│    launcher/ui/              ← dialogi (delegacja)          │
│    launcher/config/          ← ścieżki, SCRIPTS, ust.       │
└──────────────────────────────────────────────────────────────┘
```

## 2. Warstwy w szczegółach

### 2.1 Frontend (`static/`)

Trzy niezależne aplikacje webowe:

- **`mapa/`** - mapa publiczna (MapLibre GL). Warstwy: działki, obiekty specjalne,
  infrastruktura, **punkty historyczne** (markery z galerią).
- **`admin/`** - panel administracyjny. Wymaga logowania (cookie session).
  Sekcje: dashboard, właściciele, obiekty, demografia, genealogia, **diagnostyka**.
- **`wlasciciele/`** - protokoły właścicieli (widok publiczny).

**Konwencje JavaScript:**

- Moduły rejestrują się w `window` jako `Object.freeze({...})`:
  ```js
  window.AdminAPI = Object.freeze({ diagnostics: '/api/admin/diagnostics', ... });
  window.AdminDiagnostics = Object.freeze({ load, render, refresh, ... });
  window.MapV2 = Object.freeze({ addGeojsonSource, addGeojsonLayer, ... });
  ```
- Brak bundlerów (czysty ES6+). Moduły ładowane w kolejności zależności w HTML.
- **Kolejność ładowania** (w `<script>`): `api.js` → `utils.js` →
  `notifications.js` → moduły specyficzne → `admin.js`.
- Polskie komentarze i etykiety UI, angielskie identyfikatory.

### 2.2 Backend (`backend/`)

#### `main.py` - punkt wejścia

```python
app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_cors_allowed_origins(), ...)
```

- **`lifespan`**: na starcie `assert_safe_secret_key()` (Priorytet 6.6) + `init_db()`.
- **Kolejność rejestracji routerów**: najpierw specyficzne (`map`, `owners`,
  `genealogy`, `admin_auth`, `diagnostics`, `historical_points`, ...), na końcu
  **`static_files.router`** (catch-all `/{filename:path}`).
- **CORS**: env `CORS_ALLOWED_ORIGINS` (Priorytet 6.8). W produkcji brak env →
  `ValueError`. W dev fallback `["*"]`.

#### `routers/` - cienkie I/O

Każdy router ma:

- Schematy Pydantic dla request/response.
- Zależności (`Depends`) dla auth (`admin_required`).
- Wywołania do `services/`. **Brak logiki biznesowej w routerach.**

Przykład: `backend/routers/diagnostics.py`:

```python
@router.get("/api/admin/diagnostics")
async def get_diagnostics(db = Depends(get_db), _=Depends(admin_required)):
    return compute_diagnostics(db)
```

#### `services/` - logika biznesowa

- Czyste funkcje (bez `Depends`).
- Dostęp do DB przez parametry (engine/sesja przekazana z routera).
- Bez importów `launcher.*` (launcher to osobna warstwa).

#### `auth/` - bezpieczeństwo admina

- `routes.py` - endpointy `login`, `logout`, `check-auth`, `change-password`.
- `security.py` - utility diagnostyczne i walidacja:
  - `is_default_admin_password()`, `is_default_secret_key()`, `is_production_mode()`.
  - `get_admin_security_status()` - pełny raport.
  - `assert_safe_secret_key()` - walidacja startup (Priorytet 6.6).
  - `get_network_security_warnings()` - ostrzeżenia dla trybu LAN (Priorytet 6.7).
  - `get_cors_allowed_origins()` - CORS hardening (Priorytet 6.8).

### 2.3 Baza danych

- **Tryb SQLite (default):** `data/czarna.db`. Zero konfiguracji.
- **Tryb PostgreSQL (planowany):** PostGIS dla geometrii działek.

Szczegóły: [DATABASE.md](DATABASE.md).

### 2.4 Launcher (`launcher/`)

Tkinter GUI z podziałem:

- **`launcher_app.py`** - główne okno. Wywołuje dialogi i startuje/zatrzymuje procesy.
- **`services/`** - logika:
  - `process_manager.py` - zarządzanie procesami backendu (subprocess).
  - `env_runtime.py` - odczyt i zapis `.env`.
  - `network_runtime.py` - tryb sieciowy (LAN), firewall, info dialog.
  - `firewall_runtime.py` - reguły Windows Firewall dla portu backendu.
  - `admin_config_service.py` - hasło admina (Werkzeug hash + zapis do .env).
  - `location_migration_service.py` - tworzenie i migracja miejscowości.
  - `shutdown_runtime.py` - housekeeping przy zamykaniu launchera.
- **`ui/`** - dialogi (zakładki, listy, formularze). **Wyłącznie delegacja do services**.
  Brak bezpośredniego I/O (file/DB/subprocess) w UI.
- **`config/`** - ścieżki (`paths.py`), ustawienia UI (`ui_settings.py`),
  stałe runtime (`settings.py` - SCRIPTS, URLS).

Szczegóły: [LAUNCHER.md](LAUNCHER.md).

## 3. Konwencje międzywarstwowe

### 3.1 Kierunki importów (zależności)

```text
launcher/  →  backend/   ✅  (launcher używa config i security z backendu)
backend/   →  launcher/  ❌  (ZAKAZ - cykliczność)
routers/   →  services/  ✅
services/  →  models/    ✅
ui/        →  services/  ✅
ui/        →  routers/   ❌  (UI w launcherze nie woła API - robi to frontend)
```

W praktyce: launcher używa `backend.config`, `backend.auth.security`,
`backend.services.location_migration_service` (do tworzenia miejscowości
w sposób wspólny z CLI). Backend **nigdy** nie importuje z `launcher.*`.

### 3.2 Format danych: JSON

- Wszystkie API → JSON.
- Daty: ISO 8601 (`YYYY-MM-DD` lub `YYYY-MM-DDTHH:MM:SS`).
- ID: integer (autoincrement z bazy).
- Geometria: GeoJSON (`Point`, `Polygon`) - zgodne z PostGIS.

### 3.3 Obsługa błędów

- Backend: `HTTPException` z kodem (4xx/5xx) + JSON `{"detail": "..."}`.
- Frontend: try/catch + `AdminNotifications.showToast()`.
- Launcher: `messagebox.showerror()` + log do konsoli procesu.

## 4. Decyzje architektoniczne (ADRs)

### ADR-001: Jedna miejscowość = jedna instancja

**Status:** ✅ Przyjęte

**Kontekst:** Czy obsługiwać wiele miejscowości w jednej instancji programu?

**Decyzja:** Nie. Każda miejscowość = osobna instancja (osobny katalog `data/locations/<nazwa>/`).
Opcjonalnie: różne miejscowości na różnych portach (przyszłość).

**Uzasadnienie:** Projekt mocno osadzony w polskim kontekście katastralnym
(protokoły, własność rzeczywista). Różne miejscowości mogą mieć różne typy
dokumentów. Wiele miejscowości naraz komplikuje ID, kalibracje map, statystyki,
backupy i admina.

### ADR-002: Brak bundlerów JavaScript

**Status:** ✅ Przyjęte

**Decyzja:** Czysty ES6+ w `<script>` tagach, moduły `window.*` z `Object.freeze`.

**Uzasadnienie:** Zero złożoności buildu. Moduły czytelne bezpośrednio w przeglądarce.
Cache przeglądarki na poziomie pliku działa out-of-box. HMR niepotrzebny - mamy
launcher z auto-restartem backendu.

### ADR-003: TDD z testami przed kodem

**Status:** ✅ Przyjęte

**Decyzja:** Każda nowa funkcjonalność = testy (red) → implementacja (green)
→ regresja.

**Uzasadnienie:** Pewność refactoru, dokumentacja zachowania, wykrywanie regresji
przy 468+ testach.

### ADR-004: Logika poza UI

**Status:** ✅ Przyjęte

**Decyzja:** `launcher/ui/*` deleguje do `launcher/services/*` i `backend/services/*`.
Brak I/O (file/DB/subprocess) bezpośrednio w klasach UI.

**Uzasadnienie:** Testowalność logiki bez podnoszenia Tk. Możliwość użycia
tej samej logiki z CLI (np. `location_migration_service.create_and_migrate_location_database`).

### ADR-005: Moduły JS zamiast monolitu admin.js

**Status:** 🔄 W toku (Etap 1 ukończony)

**Decyzja:** Nowe funkcje = osobny plik `js/<feature>.js` rejestrujący
`window.<Feature> = Object.freeze({...})`. Stary `admin.js` nadal istnieje,
ale nowe moduły się do niego podpinają cienkimi aliasami.

**Plan:**
- Etap 1 ✅ `api.js`, `utils.js`, `notifications.js`.
- Etap 2 🔄 `objects.js` (loadObjects, renderObjects, editObject, ...).
- Etap 3 🔄 `historical-points.js`, dalsze moduły.

**Uzasadnienie:** `admin.js` przekroczył 1000 linii, robi za dużo naraz
(auth, dashboard, właściciele, obiekty, demografia, genealogia, modale, toasty,
backup). Dalsze dopisywanie do monolitu = katastrofa.

## 5. Przepływ danych (przykład: "Eksportuj protokół właściciela")

```text
[Przeglądarka]
    GET /api/owners/42/protocol
       │
       ▼
[backend/routers/owners.py]
    async def get_owner_protocol(id: int, db):
        owner = await owners_service.get_by_id(db, id)
        protocol = await owners_service.get_protocol(db, id)
        return ProtocolResponse(...)
       │
       ▼
[backend/services/owners.py]
    query: SELECT * FROM wlasciciele WHERE id = :id
    query: SELECT * FROM protokol WHERE wlasciciel_id = :id
       │
       ▼
[SQLite/PostgreSQL]
    return rows
       │
       ▼
[Przeglądarka]
    render protocol.html z danymi
```

## 6. Wzorce i antywzorce

### ✅ Wzorce

- **Thin router / fat service** - router robi tylko I/O, logika w service.
- **DTO przez Pydantic** - schematy request/response w `routers/<feature>.py`.
- **TDD z regresją** - testy przed kodem, `pytest` po każdej fazie.
- **Module registry** - `window.<Feature> = Object.freeze({...})`.
- **Env-based config** - wszystko w `.env` (z fallbackami w `config.py`).
- **Graceful degradation** - backend z SQLite działa, z PostgreSQL też działa.

### ❌ Antywzorce (do unikania)

- ❌ Logika w routerach (powyżej 30 linii per endpoint = za dużo).
- ❌ Importy `launcher.*` w `backend/*` (cykliczność).
- ❌ Bezpośrednie I/O w klasach UI (file/DB/subprocess w `launcher/ui/*`).
- ❌ Globalny mutable state poza `config` (np. mutable w `routers/*`).
- ❌ Skrypty w `backend/` uruchamiane ręcznie - wszystko przez `tools/`,
  launcher lub CLI.
- ❌ Hardcoded URL-e/porty - wszystko z `URLS` / `config.SECRET_KEY` / env.

## 7. Bezpieczeństwo (wysoki poziom)

- Panel admina: cookie session (HttpOnly, SameSite=Lax).
- Hasło admina: Werkzeug hash w `.env` (Priorytet 6.3 fix - czyta poprawnie
  Werkzeug + SHA-256 fallback).
- SECRETS: `backend/.env` (w `.gitignore`).
- Tryb sieciowy: ostrzeżenie gdy `ADMIN_AUTH_ENABLED=False` (Priorytet 6.7).
- CORS: env-driven (Priorytet 6.8).

Szczegóły: [SECURITY.md](SECURITY.md).

## 8. Wydajność

- **Backend:** async I/O (SQLAlchemy asyncio), nieblokujące routery.
- **Frontend:** MapLibre GL z cache'owaniem źródeł GeoJSON w pamięci.
- **Baza:** indeksy na `parcels_data.owners_id`, `genealogy.parent_id`.
- **Launcher:** subprocess z `CREATE_NO_WINDOW` (Windows), konsola w Ttk Notebook.

## 9. Zobacz też

- [TESTING.md](TESTING.md) - jak testować
- [DATABASE.md](DATABASE.md) - tryby DB
- [LAUNCHER.md](LAUNCHER.md) - GUI launchera
- [SECURITY.md](SECURITY.md) - bezpieczeństwo admina
- [LOCATIONS.md](LOCATIONS.md) - model miejscowości
- [ROADMAP.md](ROADMAP.md) - planowane kierunki
- [TODO.md](../TODO.md) - szczegółowy plan prac
- [PROJECT_SKILL.md](../PROJECT_SKILL.md) - konwencje kodu
