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

- **Python 3.11+** (testowane na 3.13.7)
- Przeglądarka (Chrome/Firefox/Edge)
- **SQLite** - tryb domyślny (zero konfiguracji)
- **PostgreSQL 12+ z PostGIS** - opcjonalny tryb produkcyjny (planowane: kreator migracji, Priorytet 2)

### Instalacja

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/snakex21/Projekt-Czarna.git
cd Projekt-Czarna

# 2. Zainstaluj zależności
pip install -r requirements.txt

# 3. Uruchom Centrum Zarządzania (launcher GUI)
python launcher/launcher_app.py
```

Launcher poprowadzi Cię przez konfigurację graficzną. Wszystko w jednym miejscu:

- ✅ Konfiguracja połączenia z bazą (SQLite/PostgreSQL)
- ✅ Wybór aktywnej miejscowości
- ✅ Uruchomienie serwera backendu (lokalnie lub w sieci LAN)
- ✅ Otwarcie aplikacji w przeglądarce
- ✅ Diagnostyka systemu i panel bezpieczeństwa admina

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
├── TODO.md                  # plan rozwoju
└── PROJECT_SKILL.md         # konwencje kodu dla AI agentów
```

## 📊 Status Projektu

**Stan na czerwiec 2026:**

- ✅ **833 testów** przechodzi w stabilnym zestawie regresji (+8 skip PostgreSQL E2E)
- ✅ Priorytety 1, 2, 2.5 Etap 1-13, 2.7 Etap 1-5E, 2.8 Etap 1-16, 3, 3.1, 4, 4.1, 5, 5.1, 6 - ukończone
- ⚠️ Znane flaky/środowiskowe testy są opisane w `CHANGELOG.md`/CI i naprawiane osobno

Ukończone priorytety (szczegóły w [TODO.md](TODO.md)):

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
- **[TODO.md](TODO.md)** - szczegółowy plan prac
- **[PROJECT_SKILL.md](PROJECT_SKILL.md)** - konwencje kodu dla agentów AI
- **[CHANGELOG.md](CHANGELOG.md)** - historia zmian i wersji
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - zasady współpracy i konwencje PR
- **[LICENSE](LICENSE)** - licencja MIT

Dokumentacja akademicka (praca inżynierska):

- `dokumentacja/dokumentacja.pdf` - wersja finalna
- `dokumentacja/dokumentacja.md` - wersja tekstowa

## 🛠️ Dla Deweloperów

### Uruchomienie testów

```bash
# Stabilny pakiet CI (pomija znane flaky/środowiskowe testy)
python -m pytest backend/tests/ \
  --ignore=backend/tests/integration/test_add_edit_location_dialog_photos.py \
  --ignore=backend/tests/unit/test_add_edit_location_dialog_photos.py \
  --ignore=backend/tests/unit/test_db_helpers.py \
  --ignore=backend/tests/unit/test_diagnostics_service.py

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
# http://127.0.0.1:5000/admin/        - panel admina (domyślnie: admin / admin123)
# http://127.0.0.1:5000/wlasciciele/  - protokoły
```

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
