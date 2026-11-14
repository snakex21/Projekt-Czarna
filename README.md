# 🗺️ Interaktywna Mapa Katastralna Gminy Czarna

> Kompleksowy system do wizualizacji i analizy historycznych danych katastralnych z XIX wieku

## 📖 O Projekcie

System łączący historię z nowoczesną technologią - umożliwia eksplorację map katastralnych, danych właścicielskich i genealogicznych gminy Czarna z 1882 roku. Projekt bazuje na autentycznych materiałach archiwalnych z Archiwum Państwowego w Tarnowie oraz księgach metrykalnych z Archiwum Diecezjalnego.

**Autor:** Maksymilian Augustyn
**Opiekun:** dr inż. Adam Pieprzycki
**Uczelnia:** Akademia Tarnowska

## ✨ Możliwości

- 🗺️ **Interaktywna mapa katastralna** (MapLibre GL) - wizualizacja działek, obiektów specjalnych i infrastruktury
- 📍 **Punkty historyczne** - markery na mapie z galerią zdjęć (np. Dworzec w Czarnej)
- 👥 **System genealogiczny** - przeglądanie drzew mieszkańców, relacji rodzinnych
- 📊 **Analizy demograficzne** - statystyki własności, struktury społecznej
- 📜 **Protokoły katastralne** - dostęp do oryginalnych dokumentów własnościowych
- 🛠️ **Centrum Zarządzania (launcher)** - GUI do konfiguracji, zarządzania miejscowościami, uruchamiania serwera
- 🔐 **Panel admina** - diagnostyka danych, edycja, bezpieczeństwo (chroniony hasłem)

## 🚀 Szybki Start

### Wymagania

- **Python 3.11+** (CI: 3.13)
- Przeglądarka (Chrome/Firefox/Edge)
- **SQLite** - tryb domyślny (zero konfiguracji)
- **PostgreSQL 12+ z PostGIS** - opcjonalny tryb produkcyjny

### Instalacja i uruchomienie (świeży klon, bez GUI)

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/snakex21/Projekt-Czarna.git
cd Projekt-Czarna

# 2. Środowisko i zależności
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# 3. Konfiguracja (opcjonalna - domyślnie SQLite w data/czarna.db)
cp backend/.env.example backend/.env

# 4. Hasło administratora (bez tego edycja danych jest zablokowana)
python -m backend.scripts.set_admin_password

# 5. Dane demo - świeży klon ma pustą bazę, więc mapa byłaby pusta
python -m backend.scripts.seed_demo

# 6. Serwer
python -m uvicorn backend.main:app --host 127.0.0.1 --port 5000
```

Następnie otwórz <http://127.0.0.1:5000/> (mapa: `/mapa/`, panel admina: `/admin/`).

Zamiast kroku 5 można ustawić `SEED_DEMO_DATA=1` - serwer zasili **pustą** bazę
SQLite przy starcie. `seed_demo --force` nadpisuje istniejące dane. Seed importuje
commitowane pliki `data/locations/<ACTIVE_LOCATION>/` (obiekty mapy, genealogia,
demografia, konfiguracja mapy); dane właścicieli (`owner_data_to_import.json`)
nie są w repozytorium i są importowane tylko, jeśli plik istnieje lokalnie.

### Launcher (GUI)

```bash
python launcher/launcher_app.py
```

Launcher poprowadzi Cię przez konfigurację graficzną:

- ✅ Konfiguracja połączenia z bazą (SQLite/PostgreSQL)
- ✅ Wybór aktywnej miejscowości
- ✅ Uruchomienie serwera backendu (lokalnie lub w sieci LAN)
- ✅ Otwarcie aplikacji w przeglądarce
- ✅ Diagnostyka systemu i panel bezpieczeństwa admina

### Konfiguracja (zmienne środowiskowe)

Wszystkie ustawienia czytane są ze zmiennych środowiskowych albo z `backend/.env`
(w `.gitignore`; wzór z opisami: [`backend/.env.example`](backend/.env.example)).
**W kodzie nie ma domyślnych haseł ani kluczy.**

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `DB_ENGINE` | `sqlite` | `sqlite` albo `postgresql` |
| `DB_PATH` | `data/czarna.db` | plik bazy SQLite |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_NAME` | `localhost` / `5432` / `postgres` / `mapa_czarna_db` | PostgreSQL |
| `DB_PASSWORD` | *(brak)* | hasło PostgreSQL - wymagane w trybie `postgresql` |
| `ACTIVE_LOCATION` | `Czarna` | folder w `data/locations/` |
| `ADMIN_USERNAME` | `admin` | login administratora |
| `ADMIN_PASSWORD_HASH` | *(brak)* | hash Werkzeug; ustaw przez `python -m backend.scripts.set_admin_password` |
| `ADMIN_SESSION_TTL_SECONDS` | `28800` | czas życia sesji admina |
| `FLASK_SECRET_KEY` / `SECRET_KEY` | *(generowany)* | klucz podpisujący sesje; pusty = losowy, zapisany poza repo |
| `SECRET_KEY_FILE` | `%LOCALAPPDATA%\MapaCzarna\secret_key` / `~/.config/mapa-czarna/secret_key` | gdzie trzymać wygenerowany klucz (nie w repozytorium) |
| `PRODUCTION` / `ENVIRONMENT=production` | `0` | tryb produkcyjny (twarde walidacje, ciasteczko `Secure`) |
| `CORS_ALLOWED_ORIGINS` | *(puste)* | originy CORS po przecinku; puste = tylko ten sam origin |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS` | `5` / `300` | limit nieudanych logowań na IP |
| `MAX_REQUEST_BODY_BYTES` | `16777216` | maks. rozmiar ciała żądania (413 powyżej) |
| `COOKIE_SECURE` | `1` w produkcji | flaga `Secure` ciasteczka sesji |
| `SEED_DEMO_DATA` | `0` | `1` = zasil pustą bazę SQLite danymi demo przy starcie |
| `ADMIN_AUTH_ENABLED` + `ADMIN_AUTH_INSECURE_DISABLE` | `1` + `0` | wyłączenie autoryzacji wymaga **obu** flag (`0` i `1`); ignorowane w produkcji |

### Bezpieczeństwo

- **Autoryzacja admina jest zawsze włączona.** Każdy endpoint zmieniający dane
  (POST/PUT/PATCH/DELETE) oraz eksport/diagnostyka wymaga zalogowania. Test
  `backend/tests/integration/test_mutating_routes_require_auth.py` sam wylicza
  wszystkie takie trasy i sprawdza 401/403 bez logowania.
- **Brak hasła domyślnego.** Dopóki nie ustawisz `ADMIN_PASSWORD_HASH`, akcje admina
  zwracają 403 z instrukcją, a serwer wypisuje ją przy starcie. Hashe znanych
  haseł (np. dawnego hasła domyślnego) nie są akceptowane.
- **Sesje**: podpisany HMAC-SHA256 token z czasem wygaśnięcia i losowym ID,
  ciasteczko `HttpOnly`, `SameSite=Strict` (`Secure` w produkcji). Wylogowanie
  unieważnia token na serwerze, zmiana hasła - wszystkie sesje.
- **Logowanie**: limit nieudanych prób per IP (429 + `Retry-After`).
- **Wejście**: modele Pydantic (typy, długości, zakresy) dla wszystkich
  endpointów zapisu; limit rozmiaru żądania (413); błędy 500 nie ujawniają treści wyjątków.
- **HTTP**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, CSP `frame-ancestors/object-src/base-uri`; żądania
  zmieniające dane z obcym `Origin` → 403; CORS domyślnie wyłączony.
- **Pliki**: serwowanie plików blokuje wyjście poza katalog (path traversal);
  nieznane `/api/*` → 404 JSON. Serwer nie przyjmuje uploadu plików
  (multipart) - zdjęcia dodaje się przez launcher.
- **Tryb LAN** (launcher, `0.0.0.0`): używaj tylko z ustawionym hasłem admina;
  w sieci niezaufanej postaw serwer za reverse proxy z HTTPS i `PRODUCTION=1`.
- Szczegóły: [docs/technical/SECURITY.md](docs/technical/SECURITY.md).

## 🏗️ Architektura

Projekt oparty jest na architekturze full-stack z wyraźnym podziałem warstw:

```text
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (przeglądarka)                                    │
│  static/mapa/     - mapa publiczna (MapLibre GL)            │
│  static/admin/    - panel administracyjny                  │
│  static/wlasciciele/ - protokoły właścicieli               │
└─────────────────────────────────────────────────────────────┘
                            ↑ JSON REST API
┌─────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI + uvicorn)                                │
│  backend/main.py            - app + lifespan               │
│  backend/routers/           - endpointy (thin I/O)         │
│  backend/services/          - logika biznesowa             │
│  backend/auth/              - bezpieczeństwo admina        │
└─────────────────────────────────────────────────────────────┘
                            ↑ SQLAlchemy async
┌─────────────────────────────────────────────────────────────┐
│  BAZA DANYCH                                                 │
│  SQLite (data/czarna.db) - tryb dev/test                   │
│  PostgreSQL + PostGIS     - tryb produkcyjny (planowany)   │
└─────────────────────────────────────────────────────────────┘
                            ↑ subprocess + env
┌─────────────────────────────────────────────────────────────┐
│  LAUNCHER (Tkinter GUI)                                     │
│  launcher/launcher_app.py  - główne okno                   │
│  launcher/services/        - logika (process_manager, env) │
│  launcher/ui/              - dialogi i widżety             │
│  launcher/config/          - ścieżki i ustawienia         │
└─────────────────────────────────────────────────────────────┘
```

### Stack technologiczny

- **Backend:** Python 3.13, FastAPI, SQLAlchemy (asyncio), uvicorn, Werkzeug
- **Baza danych:** SQLite (default) / PostgreSQL + PostGIS (opcja)
- **Frontend:** HTML5, CSS3, JavaScript ES6+ (moduły `window.*`), MapLibre GL
- **Desktop GUI:** Python Tkinter, Pillow
- **Testy:** pytest, FastAPI TestClient, Playwright (E2E)

## 📁 Struktura Projektu

```text
Projekt-Czarna/
├── backend/                 # FastAPI backend
│   ├── main.py              # app + lifespan
│   ├── config.py            # env, SECRET_KEY, DB_ENGINE
│   ├── db.py                # SQLAlchemy async engine
│   ├── routers/             # endpointy (map, owners, genealogy, admin, ...)
│   ├── services/            # logika (diagnostics, ...)
│   ├── auth/                # bezpieczeństwo admina
│   └── tests/               # unit + integration + e2e
├── launcher/                # GUI launcher (Tkinter)
│   ├── launcher_app.py      # główne okno
│   ├── services/            # process, env, network, firewall
│   ├── ui/                  # dialogi
│   └── config/              # ścieżki, SCRIPTS
├── static/                  # frontend (serwowany przez FastAPI)
│   ├── mapa/                # mapa publiczna
│   ├── admin/               # panel admina + diagnostyka
│   └── wlasciciele/         # protokoły
├── data/                    # dane per-miejscowość
│   ├── locations/Czarna/    # przykładowa miejscowość
│   │   ├── parcels_data.json
│   │   ├── owner_data.json
│   │   ├── historical_points.json
│   │   ├── point_photos/    # zdjęcia markerów
│   │   └── history_photos/  # galeria miejscowości
│   └── czarna.db            # SQLite (dev)
├── docs/                    # dokumentacja
│   ├── index.html           # akademicka dokumentacja HTML (praca inż.)
│   ├── deployment.html      # szczegóły wdrożenia
│   ├── assets/              # screeny do HTML
│   └── technical/           # dokumentacja techniczna (Markdown)
├── tools/                   # dedykowane edytory (owner, parcel, genealogy)
├── .github/workflows/ci.yml # CI pytest + ręczne E2E
├── requirements.txt
├── .gitignore
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
├── pytest.ini
├── README.md                # ten plik
└── PROJECT_SKILL.md         # konwencje kodu dla AI agentów
```

## 📊 Status Projektu

**Stan na czerwiec 2026:**

- ✅ **1283 testy** (unit, integracja, E2E Playwright) przechodzą w pełnym zestawie CI, bez wyłączeń (10 skip: PostgreSQL / instalacja PG)
- ✅ Priorytety 1, 2, 2.5 Etap 1-13, 2.7 Etap 1-5E, 2.8 Etap 1-16, 3, 3.1, 4, 4.1, 5, 5.1, 6 - ukończone

Ukończone priorytety:

- **P1** - status obiektów (`Wolny` → `Nieprzypisany` + linki do protokołów)
- **P2** - kreator PostgreSQL / migracja SQLite → PostgreSQL
- **P2.5/Etap 1-13** - wydzielenie `api.js`, `utils.js`, `notifications.js`,
  `objects.js`, `owners.js`, `owner-modal.js`, `demography.js`, `tree-renderer.js`,
  `dashboard.js`, `genealogy-mini-tree.js`, `genealogy-details.js`, `genealogy-modal.js`,
  `genealogy-list.js`, `auth.js`, `genealogy-tree.js` z monolitu/legacy admina oraz cleanup martwych adapterów drzewa
- **P2.7/Etap 1-5E** - start refaktoryzacji `static/wlasciciele/`: publiczne moduły
  `OwnersAPI`, `OwnersUtils`, `ProtocolImages`, `ProtocolGenealogyTree`, `CompareRenderer`,
  `CompareInteractions`;
  przepięcie URL-i, helperów, skanów i drzewa genealogicznego w `protokol.js` oraz
  migracja URL-i/helperów, drzewa, skanów, renderu kolumn oraz mapy/PDF w `compare.js`
- **P2.8/Etap 1-16** - rozpoczęcie refaktoryzacji centrum analitycznego: `stats-script.js`
  używa `OwnersAPI.stats()` i `OwnersUtils.formatArea()`, a podstawowy motyw/fullscreen
  deleguje do `StatsUI`; akcje przycisków mapy/eksportu deleguje do `StatsActions`,
  pobieranie pakietu statystyk do `StatsData`, modal pomocy do `StatsHelp`,
  globalną wyszukiwarkę do `StatsSearch`, animowane liczniki do `StatsCounters`,
  zakładki i przełączniki rankingów do `StatsTabs`, podstawowe metryki do `StatsMetrics`,
  sekcję właścicieli żydowskich do `StatsJewish`, ranking właścicieli do `StatsRanking`,
  ranking działek do `StatsParcelsRanking`, rankingi infrastruktury do
  `StatsInfrastructureRanking`, oś czasu protokołów do `StatsTimeline`, duży blok
  demografii do `StatsDemographics`, a statystyki genealogiczne do `StatsGenealogy`
- **P3** - punkt historyczny "Dworzec w Czarnej" + galeria
- **P3.1** - porządek ze zdjęciami markerów (osobny folder `point_photos/`)
- **P4** - panel diagnostyki (9 metryk jakości danych + agregat)
- **P4.1** - kosmetyka panelu diagnostyki (placeholder dla pustych kart)
- **P5/P5.1** - dokumentacja techniczna, release artifacts, CI, cleanup dead code
- **P6** - bezpieczeństwo admina (4 fazy: diagnostyka, fix verify_password, zmiana hasła, CORS hardening)

## 📚 Dokumentacja

Szczegółowa dokumentacja techniczna:

- **[docs/technical/ARCHITECTURE.md](docs/technical/ARCHITECTURE.md)** - architektura systemu, warstwy, decyzje
- **[docs/technical/TESTING.md](docs/technical/TESTING.md)** - jak uruchomić testy, konwencje TDD, mocki
- **[docs/technical/DATABASE.md](docs/technical/DATABASE.md)** - tryby SQLite/PostgreSQL, schemat, migracja
- **[docs/technical/LAUNCHER.md](docs/technical/LAUNCHER.md)** - GUI launchera, zarządzanie procesami, sieć
- **[docs/technical/SECURITY.md](docs/technical/SECURITY.md)** - bezpieczeństwo admina, tryb LAN, produkcja
- **[docs/technical/LOCATIONS.md](docs/technical/LOCATIONS.md)** - model danych per-miejscowość
- **[docs/technical/ROADMAP.md](docs/technical/ROADMAP.md)** - planowane kierunki rozwoju
- **[PROJECT_SKILL.md](PROJECT_SKILL.md)** - konwencje kodu dla agentów AI
- **[CHANGELOG.md](CHANGELOG.md)** - historia zmian i wersji
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - zasady współpracy i konwencje PR
- **[LICENSE](LICENSE)** - licencja MIT

Dokumentacja akademicka (praca inżynierska) nie jest częścią repozytorium
(katalog `dokumentacja/` jest w `.gitignore`).

## 🛠️ Dla Deweloperów

### Uruchomienie testów

```bash
# Instalacja zależności całego zestawu i przeglądarki
python -m pip install -r requirements-test.txt
python -m playwright install chromium

# Pełny zestaw (to samo co CI). Testy tworzą własną bazę i losowe hasło admina
# w katalogu tymczasowym - nie dotykają data/czarna.db ani backend/.env.
python -m pytest backend/tests/

# Bez testów przeglądarkowych (szybciej, bez Chromium)
python -m pytest backend/tests/ --ignore=backend/tests/e2e

# Lint i audyt zależności (jak w CI)
ruff check .
pip-audit -r requirements.txt -r requirements-test.txt

# Konkretny moduł
python -m pytest backend/tests/unit/test_diagnostics_service.py

# Z verbose
python -m pytest backend/tests/ -v

# Konkretna klasa/metoda
python -m pytest backend/tests/unit/test_auth_security.py::TestAssertSafeSecretKey
```

### Tryb developerski

```bash
# Terminal 1: backend (hot reload)
cd Projekt-Czarna
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 5000

# Terminal 2: launcher (opcjonalnie)
python launcher/launcher_app.py

# Przeglądarka
# http://127.0.0.1:5000/              - strona główna
# http://127.0.0.1:5000/mapa/         - mapa katastralna
# http://127.0.0.1:5000/admin/        - panel admina (hasło: python -m backend.scripts.set_admin_password)
# http://127.0.0.1:5000/wlasciciele/  - protokoły
```

### Zależności

`requirements.txt` podaje minimalne wersje bez znanych podatności (pip-audit).
Zestaw przetestowany (listopad 2026, Python 3.13): fastapi 0.162.7, starlette 1.10.0,
pydantic 2.14.3, uvicorn 0.54.0, SQLAlchemy 2.1.8, Werkzeug 3.1.9, Pillow 13.0.0,
requests 2.34.2. CI uruchamia `pip-audit` przy każdym pushu.

### Konwencje kodu

- **Python:** TDD (testy najpierw), pytest, type hints, snake_case
- **JavaScript:** moduły `window.*` z `Object.freeze`, brak bundlerów, namespace per moduł
- **Architektura:** `services/` (logika) + `routers/` (I/O) + `ui/` (orkiestracja)
- **Frontend:** moduły JS PRZED `admin.js`, routery FastAPI PRZED `static_files.router`
- **Polski UI / angielski kod:** UI po polsku, identyfikatory/kody po angielsku

Pełne konwencje: [PROJECT_SKILL.md](PROJECT_SKILL.md)

### Dodawanie nowej funkcjonalności

1. **Nowy endpoint API:** `backend/routers/<feature>.py` + test w `backend/tests/integration/`
2. **Nowa logika:** `backend/services/<feature>.py` + test w `backend/tests/unit/`
3. **Nowy moduł frontendu:** `static/<area>/js/<feature>.js` jako `window.<Feature> = Object.freeze({...})`
4. **Nowa zakładka w launcherze:** `launcher/ui/<feature>.py` (klasa dialogu) + test w `backend/tests/unit/`

Zawsze: TDD → implementacja → regresja → commit.

## 🤝 Współpraca

1. Fork → branch (`feature/...`) → commit → PR
2. Konwencje: [CONTRIBUTING.md](CONTRIBUTING.md) + [PROJECT_SKILL.md](PROJECT_SKILL.md) + [docs/technical/](docs/technical/)
3. Testy muszą przechodzić przed PR

## 📄 Licencja

Projekt udostępniany na licencji [MIT](LICENSE). Kontrybucje: [CONTRIBUTING.md](CONTRIBUTING.md).

## 🙏 Podziękowania

- Archiwum Państwowe w Tarnowie - za udostępnienie protokołów katastralnych
- Archiwum Diecezjalne w Tarnowie - za dostęp do ksiąg metrykalnych
- dr inż. Adam Pieprzycki - za opiekę naukową nad pracą

---

**Projekt powstał z pasji do historii lokalnej i chęci zachowania dziedzictwa kulturowego dla przyszłych pokoleń.**
