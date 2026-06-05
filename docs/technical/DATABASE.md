# Baza danych

> Tryby (SQLite / PostgreSQL), schemat, konfiguracja, migracja.

## 1. Tryby bazy danych

Projekt obsĹ‚uguje dwa tryby pracy bazy danych:

| Cecha | SQLite (domyĹ›lny) | PostgreSQL + PostGIS (planowany) |
|-------|-------------------|-----------------------------------|
| Konfiguracja | Zero (automatycznie) | Kreator w launcherze (Priorytet 2) |
| Wymagania | Nic (wbudowane w Python) | PostgreSQL 12+ + rozszerzenie PostGIS |
| WydajnoĹ›Ä‡ | WystarczajÄ…ca do 10k rekordĂłw | Lepsza dla duĹĽych zbiorĂłw |
| Geometria | WspĂłĹ‚rzÄ™dne w kolumnach TEXT | Natywne typy PostGIS (Point, Polygon) |
| Przypadki uĹĽycia | Dev, testy, single-user | Produkcja, multi-user |
| ĹšcieĹĽka | `data/czarna.db` | `postgresql://user:pass@host:port/dbname` |

### 1.1 Jak wybraÄ‡ tryb

W pliku `backend/.env`:

```bash
# Tryb SQLite (domyĹ›lny)
DB_ENGINE=sqlite
DB_PATH=C:\Users\...\Projekt Mapa Czarna\data\czarna.db
ACTIVE_LOCATION=Czarna

# Tryb PostgreSQL (po migracji)
DB_ENGINE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mapa_czarna
DB_USER=mapa_user
DB_PASSWORD=...
```

Launcher (przyszĹ‚y Priorytet 2) pomoĹĽe:

- SprawdziÄ‡ poĹ‚Ä…czenie z PostgreSQL.
- UtworzyÄ‡ bazÄ™ jeĹ›li nie istnieje.
- PrzenieĹ›Ä‡ dane z SQLite.
- PrzeĹ‚Ä…czyÄ‡ `.env` na nowy tryb.
- W razie bĹ‚Ä™du - zostawiÄ‡ system na SQLite.

### 1.2 Jak wybierany jest tryb w runtime

W `backend/config.py`:

```python
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").lower()
PRODUCTION = (
    os.getenv("PRODUCTION", "0") == "1"
    or os.getenv("ENVIRONMENT", "").lower() == "production"
)
```

Backend startuje zawsze - loguje tryb DB przy starcie:

```text
đź—„ď¸Ź Silnik bazy: sqlite
đź“ Baza danych: sqlite:///C:/Projekt Mapa Czarna/data/czarna.db
đź“Ť Aktywna miejscowoĹ›Ä‡: Czarna
```

## 2. Schemat bazy (SQLite + PostgreSQL)

### 2.1 Tabele

| Tabela | Opis | Kluczowe kolumny |
|--------|------|------------------|
| `konfiguracja_systemu` | Ustawienia per-miejscowoĹ›Ä‡ (klucz/wartoĹ›Ä‡) | `klucz`, `wartosc`, `kategoria` |
| `obiekty_geograficzne` | DziaĹ‚ki + obiekty specjalne | `id`, `numer`, `kategoria`, `geom_x`, `geom_y`, `wlasciciel_id` |
| `wlasciciele` | Osoby i rodziny | `id`, `nazwisko`, `imie`, `numer_domu`, `zawod` |
| `dzialki_wlasciciele` | Tabela Ĺ‚Ä…czÄ…ca M:N | `dzialka_id`, `wlasciciel_id`, `typ_wlasnosci`, `udzial` |
| `osoby_genealogia` | Drzewo genealogiczne | `id`, `imie`, `nazwisko`, `data_urodzenia`, `data_smierci`, `ojciec_id`, `matka_id` |
| `malzenstwa` | MaĹ‚ĹĽeĹ„stwa | `id`, `malzonek_id`, `malzonka_id`, `data_slubu` |
| `demografia` | Statystyki per rok | `rok`, `liczba_ludnosci`, `liczba_domow`, ... |

### 2.2 Tabele launcherowe (SQLite, `data/locations.db`)

| Tabela | Opis |
|--------|------|
| `locations` | Lista miejscowoĹ›ci (nazwa, Ĺ›cieĹĽka, aktywna) |
| `launcher_settings` | Ustawienia launchera (motyw, port, itd.) |

### 2.3 Pliki per-miejscowoĹ›Ä‡ (`data/locations/<Nazwa>/`)

| Plik | Format | Opis |
|------|--------|------|
| `parcels_data.json` | JSON | Geometria dziaĹ‚ek (GeoJSON) |
| `owner_data.json` | JSON | WĹ‚aĹ›ciciele (cache do szybkiego startu) |
| `demografia.json` | JSON | Statystyki demograficzne |
| `genealogia.json` | JSON | Drzewo genealogiczne |
| `historical_points.json` | JSON | Markery punktĂłw historycznych (P3) |
| `point_photos/` | katalog | ZdjÄ™cia przypisane do markerĂłw (P3.1) |
| `history_photos/` | katalog | Galeria miejscowoĹ›ci |
| `protokoly/` | katalog | Pliki protokoĹ‚Ăłw |
| `map_config.json` | JSON | Kalibracja mapy (naroĹĽniki) |
| `.env` | env | Konfiguracja per-miejscowoĹ›Ä‡ (w `.gitignore`) |

## 3. Hierarchia danych

```text
data/
â”śâ”€â”€ locations.db                       # SQLite launcher (lista miejscowoĹ›ci)
â”śâ”€â”€ czarna.db                          # SQLite aktywnej miejscowoĹ›ci (legacy)
â”śâ”€â”€ locations/
â”‚   â”śâ”€â”€ Czarna/                        # jedna miejscowoĹ›Ä‡ = jeden katalog
â”‚   â”‚   â”śâ”€â”€ .env                       # konfiguracja (DB, port, hasĹ‚o)
â”‚   â”‚   â”śâ”€â”€ parcels_data.json          # geometria
â”‚   â”‚   â”śâ”€â”€ owner_data.json            # wĹ‚aĹ›ciciele
â”‚   â”‚   â”śâ”€â”€ demografia.json
â”‚   â”‚   â”śâ”€â”€ genealogia.json
â”‚   â”‚   â”śâ”€â”€ historical_points.json     # markery
â”‚   â”‚   â”śâ”€â”€ map_config.json            # kalibracja
â”‚   â”‚   â”śâ”€â”€ point_photos/              # zdjÄ™cia markerĂłw
â”‚   â”‚   â”śâ”€â”€ history_photos/            # galeria
â”‚   â”‚   â””â”€â”€ protokoly/                 # pliki
â”‚   â””â”€â”€ InnaMiejscowosc/               # kolejna miejscowoĹ›Ä‡ (niezaleĹĽna)
â”‚       â””â”€â”€ ...
```

**Kluczowa decyzja (ADR-001):** jedna miejscowoĹ›Ä‡ = jedna instancja. Aktywna
miejscowoĹ›Ä‡ wybrana w launcherze. PrzeĹ‚Ä…czanie miejscowoĹ›ci = nowy proces
backendu z nowym `ACTIVE_LOCATION` env var.

## 5. Migracja SQLite → PostgreSQL (Priorytet 2 — ZROBIONE)

### 5.1 Zakres (✅ wszystko zrobione)

- [x] SprawdziÄ‡ poĹ‚Ä…czenie z PostgreSQL (host, port, user, hasĹ‚o).
- [x] SprawdziÄ‡ uprawnienia i istnienie bazy.
- [x] UtworzyÄ‡ bazÄ™ automatycznie jeĹ›li nie istnieje.
- [x] UtworzyÄ‡ schemat tabel (z typami PostGIS dla geometrii).
- [x] PrzenieĹ›Ä‡ dane z SQLite / backupĂłw.
- [x] ZweryfikowaÄ‡: liczba wĹ‚aĹ›cicieli, obiektĂłw, osĂłb, powiÄ…zaĹ„.
- [x] Dopiero po sukcesie przeĹ‚Ä…czyÄ‡ `.env` na `DB_ENGINE=postgresql`.
- [x] W razie bĹ‚Ä™du - zostawiÄ‡ system na SQLite.
- [x] ZapisywaÄ‡ log migracji.

### 5.2 UI launchera (zrobione)

```text
Kreator PostgreSQL
[SprawdĹş poĹ‚Ä…czenie]   â†' ping + walidacja user/hasĹ‚o
[UtwĂłrz bazÄ™]          â†' CREATE DATABASE jeĹ›li brak
[Migruj z SQLite]      â†' kopiowanie tabel + danych
[PrzeĹ‚Ä…cz aplikacjÄ™]   â†' zmiana .env + restart
[Testuj]               â†' smoke test po migracji
```

Lub jeden przycisk: `[Skonfiguruj automatycznie]`.

### 5.3 WaĹźne zaĹ‚oĹźenie (NIEAKTUALNE)

Pierwotne zaĹ‚oĹźenie „na poczÄ…tek nie robimy peĹ‚nego instalatora PostgreSQL"
zostaĹ‚o **zastÄ…pione przez Priorytet 2.1 (portable PG)** — zob. sekcja 4.

## 4. Portable PostgreSQL (Priorytet 2.1 — ZROBIONE)

> Sekcja 4 jest zarezerwowana dla portable PG. Sekcja 5 (Backup) i dalsze są numerowane jak w oryginale (5→6, 6→7, 7→8, 8→9, 9→10 po renumeracji poniżej).

### 4.1 Zakres (wszystko zrobione)

- [x] Wykrywanie systemowego PG w PATH i standardowych lokalizacjach.
- [x] Pobieranie portable PG z `get.enterprisedb.com` (ZIP dla Windows/macOS, TAR.GZ dla Linux).
- [x] Ekstrakcja archiwum do `<project_root>/.runtime/postgres/` (wspólna lokalizacja dla Windows, Linux, macOS; od wersji 1.1.2).
- [x] `initdb` klastra danych z `--auth=trust` i `--username=postgres`.
- [x] Start serwera PG jako subprocess, graceful stop.
- [x] Detekcja gotowości (TCP socket polling).
- [x] Integracja z wizardem PostgreSQL — banner + propozycja instalacji po nieudanym teście połączenia.
- [x] Smoke test binariów po instalacji.
- [x] Testy jednostkowe i integracyjne (mockowane HTTP + subprocess).

### 4.2 UX flow (od v1.1.0)

1. User otwiera kreator bazy danych (`DatabaseWizard`).
2. Wizard wywołuje `pg_portable_service.detect_system_pg()` w `__init__` (opóźnione o 500 ms).
3. Brak systemowego PG **i** brak portable PG → banner "Brak PostgreSQL".
4. `auto_test_connection` zwraca błąd → `_offer_portable_pg_install` pyta użytkownika (jedna propozycja na sesję).
5. Po zgodzie → `_install_portable_pg_with_progress`: download → extract → initdb → smoke start/stop.
6. User klika "Testuj połączenie" ponownie → sukces.

### 4.3 Architektura

- `launcher/services/pg_portable_service.py` (466 linii) — detekcja, download, extract. Publiczne API: `detect_system_pg`, `get_pg_download_url`, `download_pg_binary`, `extract_pg_archive`, `is_pg_initialized`, `get_portable_pg_paths`, `portable_pg_installed`, `verify_pg_archive_checksum`. Atomic download (write to `.tmp`, `Path.replace`), retry z liniowym backoff, progress callback.
- `launcher/services/pg_runtime.py` (448 linii) — initdb, start, stop, health check. Publiczne API: `init_pg_data_dir`, `start_pg_server`, `stop_pg_server`, `is_pg_server_running`, `wait_for_pg_ready`, `get_postmaster_pid`, `remove_pg_data_dir`. Dataclassy: `PgServerConfig`, `PgServerHandle`, `StepResult`. Idempotentne `stop_pg_server` (graceful `pg_ctl stop -m fast` z fallback `SIGTERM`).
- `launcher/ui/database_wizard.py` — 3 nowe metody: `_offer_portable_pg_install`, `_install_portable_pg_with_progress`, `_check_portable_pg_on_startup`. Auto-startup check w `self.after(500, ...)`. Własny progress dialog (Tk Toplevel z ProgressBar) + DAEMON thread dla długich operacji.

### 4.4 Pliki i lokalizacje (od wersji 1.1.2)

- **Katalog instalacji**: `<project_root>/.runtime/postgres/` (ten sam dla Windows, Linux, macOS).
  Identyfikowany przez `_find_project_root()` (szuka `launcher/launcher_app.py`,
  `requirements.txt` lub `backend/main.py`).
- Binaria portable PG: `<install_root>/pgsql/bin/`.
- Data dir: `<install_root>/data/`.
- Log serwera: `<data_dir>/pg_server.log` (gdy start przez wizard).
- Plik PID postmastera: `<data_dir>/postmaster.pid`.
- **Gitignored**: `.runtime/` w `.gitignore` (katalog istnieje dzięki `.gitkeep`).
- **Katalog `.runtime/`** służy WYŁĄCZNIE na lokalne runtime artifacts:
  binaria i dane portable PG. Nie należy tam umieszczać plików
  użytkownika ani wyników analiz — do tego służy `data/`.
- **Brak fallbacku do lokalizacji systemowych** — `get_pg_install_dir()`
  zawsze zwraca `<root>/.runtime/postgres/` lub rzuca `RuntimeError`
  gdy `_find_project_root()` nie znajdzie markerów. Wcześniejsze wersje
  (1.1.0 AppData, 1.1.1 `<root>/postgres/`) są **nieobsługiwane** —
  jeśli user miał taką instalację, musi ją ręcznie usunąć.

### 4.5 Odinstalowanie (dodane w 1.1.1, ugruntowane w 1.1.2)

Funkcja `uninstall_portable_pg(install_dir=None, stop_server=True, timeout=10.0)`:

1. Sprawdza czy katalog istnieje (sukces z `removed_files=0` jeśli nie).
2. **Safety check**: odmawia usunięcia katalogu bez podkatalogu `pgsql/`.
3. Jeśli `stop_server=True` (domyślnie):
   - Wywołuje `pg_ctl -D <data_dir> status` — wykrywa czy serwer działa.
   - Jeśli tak: `pg_ctl stop -m fast` z timeoutem 10s (graceful shutdown).
4. Liczy pliki (best-effort, przed `rmtree`).
5. `shutil.rmtree(install_dir, ignore_errors=True)`.
6. Weryfikuje że katalog zniknął (jeśli nie — raportuje błąd).
7. Zwraca `UninstallResult(success, install_dir, removed_files, server_was_running, error)`.

**Od 1.1.2** `uninstall_portable_pg()` celuje WYŁĄCZNIE w
`<root>/.runtime/postgres/`. Nie szuka starych instalacji w AppData
ani `<root>/postgres/`. Jeśli user chce usunąć pozostałości po 1.1.1
(`<root>/postgres/`), musi to zrobić ręcznie.

W kreatorze bazy danych (krok 1) jest sekcja **"Portable PostgreSQL"** z
przyciskiem **"🗑 Odinstaluj portable PG"**:

- Widoczny tylko gdy portable PG jest zainstalowany.
- Messagebox z potwierdzeniem i informacją co zostanie usunięte.
- Po uninstall odświeża status (komunikat "niezainstalowany").
- **Brak obsługi lokalizacji legacy** (1.1.1 → 1.1.2) — kreator
  nie oferuje już "czyszczenia starej instalacji", bo to ostatnia
  wersja z innym katalogiem.

### 4.6 Real-download validation (spike 2026-06-04)

Walidacja real-download dla `https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip`
metodą **partial download** (Range request, bez pobierania całego pliku):

| Metryka | Wartość |
|---|---|
| **Pobieranie (compressed)** | **323.04 MiB** (338,727,828 B) |
| **Rozpakowane (uncompressed)** | **919.83 MiB** (964,508,759 B) ≈ 0.9 GiB |
| **Pliki w archiwum** | 22,649 |
| **Compression ratio** | 65.4% |
| **Czas pobierania @ 2.29 MB/s** | ~2:21 min |

**Top 3 największych plików w archiwum:**

| Rozmiar | Plik |
|---|---|
| 172.07 MB | `pgsql/pgAdmin 4/runtime/pgAdmin4.exe` |
| 31.10 MB | `pgsql/symbols/postgres.pdb` (debug symbols) |
| 27.08 MB | `pgsql/bin/icudt67.dll` |

**Wniosek:** Archiwum EDB zawiera **pełny stack** = PostgreSQL server
+ pgAdmin 4 IDE + Python 3.12 + Electron + biblioteki. Sam serwer PG
to ~50 MB, ale pgAdmin 4 ciągnie archiwum do 0.9 GB.

**Sprawdzone alternatywy (2026-06-04):**
- `get.postgresql.org` — nie udostępnia binariów ZIP/EXE
- `ftp.postgresql.org/pub/binary/v16.4/win/` — nie istnieje
- `openscg.com` — projekt porzucony
- Oficjalne community builds — niekompatybilne ścieżki/initdb

**EDB jest jedynym aktualnym źródłem "binaries" dla Windows.**
Akceptujemy 323 MB downloadu / 920 MB na dysku. W przyszłości (P3)
można rozważyć własny build ze źródeł albo opcję "skip pgAdmin" w
kreatorze (jako advanced toggle).

W kreatorze warto pokazać userowi te liczby przed kliknięciem
"Pobierz i zainstaluj" — np. "To pobierze 323 MB i zajmie ~920 MB
na dysku po instalacji (zawiera pgAdmin 4 IDE)".

### 4.7 Testowanie

- 36 testów jednostkowych `pg_portable_service` (mockowane HTTP, FS, subprocess) w `backend/tests/unit/test_pg_portable_service.py`.
- 36 testów integracyjnych flow (detect → download → extract → init → start → stop + fallback chain + port check) w `backend/tests/integration/test_pg_portable_flow_e2e.py` (8 nowych w 1.1.3).
- 9 smoke testów API w `backend/tests/integration/test_pg_portable_smoke.py`.
- 1 real-install pytest test (install + initdb only, domyślnie skipped) w `backend/tests/integration/test_pg_portable_real_install.py` — waliduje P2.1 z prawdziwymi binariami EDB ZIP bez mocków.
- Łącznie 82 testy, łączny czas < 1 s (real-install skipped domyślnie).

**Real-install validation (1.1.3)** — dwa podejścia do walidacji z prawdziwymi binariami PG 16.4 EDB ZIP, zero mocków:

1. **`backend/tests/integration/test_pg_portable_real_install.py`** (pytest, domyślnie skipped)
   Waliduje **instalację** (download + extract + initdb + cleanup). Włączenie: `RUN_REAL_INSTALL=1`.
   Wynik: 3/3 kroki OK w ~35s (cold). Odkrył 3 krytyczne bugi w `pg_runtime.py`:
   - `wait_for_pg_ready` zwracał True na "starting up" (sam socket to za mało)
   - `start_pg_server` nie wykrywał natychmiastowej śmierci `pg_ctl`
   - `stop_pg_server` wieszał się na `pg_ctl stop -m fast` gdy baza nie ready

2. **`scripts/test_pg_portable_real_install.py`** (standalone CLI, pełen E2E)
   Waliduje **pełen runtime P2.1** (install + start + psql + createdb + stop). Wynik: 7/7 kroków OK w ~24s (warm) / ~3 min (cold). Odkrył te same 3 bugi co pytest test, plus dodał realną walidację runtime.

   Użycie:
   ```bash
   python scripts/test_pg_portable_real_install.py                    # pełen E2E 7/7
   python scripts/test_pg_portable_real_install.py --skip-start-stop  # install + initdb 3/3
   python scripts/test_pg_portable_real_install.py --port 5446         # inny port
   ```

Fix: 4-etapowy fallback chain + dwuetapowy ready check + defensive `proc.poll()`.

### 4.8 Bezpieczeństwo i znane ograniczenia

- **Brak fallback URL-i** w runtime (tylko primary URL; retry obsługuje transient failures).
- **Brak weryfikacji SHA256** archiwum w runtime wizarda (funkcja `verify_pg_archive_checksum` istnieje, ale nie jest wołana).
- **Brak wsparcia dla Apple Silicon** (arm64) — tylko x86_64.
- **Real-install E2E test skipped domyślnie** — pytest test wymaga `RUN_REAL_INSTALL=1`. Standalone skrypt `scripts/test_pg_portable_real_install.py` to alternatywa dla manual/on-demand smoke testów.
- **Brak limitu rozmiaru** archiwum (cap do rozważenia, np. 500 MB).
- **Brak wsparcia dla firmowych proxy** z auth.
- **Race condition start PG w długich ścieżkach** — Windows Defender scanning może zabić proces. Rozwiązanie: używać krótkich ścieżek (< 100 znaków, np. `C:\pg_real_install_test`).

### 4.9 Rozszerzenia do rozważenia

- Weryfikacja SHA256 archiwum po pobraniu (z pliku `.sha256` z EDB).
- Fallback URL-i (lista mirrorów) przy 404 lub timeout.
- Wsparcie dla Apple Silicon (`Darwin` + `arm64`).
- Live E2E w CI z kontenerem `postgres` (`docker run postgres`).
- Wielojęzyczne komunikaty błędów (obecnie tylko polski).

## 6. Backup i przywracanie

### 5.1 RÄ™czny backup (SQLite)

```bash
# Kopia pliku (gdy serwer nie dziaĹ‚a)
copy data\czarna.db data\czarna.backup.2026-06-02.db

# Lub przez sqlite3
sqlite3 data\czarna.db ".backup data\czarna.backup.db"
```

### 5.2 Przywracanie

```bash
# Zatrzymaj backend
copy data\czarna.backup.db data\czarna.db
python launcher/launcher_app.py
```

### 5.3 Automatyczny backup (planowany)

Launcher moĹĽe oferowaÄ‡ harmonogram backupĂłw z kompresjÄ… + retencjÄ….
Poza zakresem obecnego rozwoju.

## 7. Konwencje dostÄ™pu do DB

### 6.1 Z backendu (async)

```python
from backend.db import get_db

async def get_owner(id: int):
    async with get_db() as db:
        result = await db.execute(
            select(Wlasciciel).where(Wlasciciel.id == id)
        )
        return result.scalar_one_or_none()
```

### 6.2 Z launchera (sync)

Launcher uĹĽywa `sqlite3` bezpoĹ›rednio (lokalna baza launcherowa):

```python
import sqlite3
con = sqlite3.connect(str(BACKUP_DIR / "locations.db"))
for row in con.execute("SELECT name FROM locations WHERE active = 1"):
    print(row[0])
```

### 6.3 Z testĂłw (fixture)

Testy uĹĽywajÄ… kopii `czarna.db` w katalogu tymczasowym
(setup w `backend/tests/conftest.py`). KaĹĽdy test ma Ĺ›wieĹĽÄ… bazÄ™.

## 8. Indeksy (planowane)

```sql
-- WydajnoĹ›Ä‡
CREATE INDEX idx_parcels_owners ON dzialki_wlasciciele(wlasciciel_id);
CREATE INDEX idx_parcels_parcel  ON dzialki_wlasciciele(dzialka_id);
CREATE INDEX idx_owners_surname  ON wlasciciele(nazwisko);
CREATE INDEX idx_genealogy_parents ON osoby_genealogia(ojciec_id, matka_id);
```

## 9. Znane ograniczenia

- **Brak transakcji miÄ™dzy SQLite a JSON per-miejscowoĹ›Ä‡.** Dane rozdzielone
  miÄ™dzy bazÄ™ a pliki JSON. Aktualizacja w dwĂłch miejscach.
- **Brak migracji schematu (Alembic).** Schemat ewoluuje rÄ™cznie w testach +
  skryptach migracyjnych w `backend/scripts/`.
- **PostgreSQL tylko w planach (Priorytet 2).** Na razie SQLite dla wszystkiego.

## 10. Zobacz teĹĽ

- [ARCHITECTURE.md](ARCHITECTURE.md) - architektura systemu
- [LOCATIONS.md](LOCATIONS.md) - model miejscowoĹ›ci
- [TESTING.md](TESTING.md) - testy
- [TODO.md](../TODO.md) - status Priorytetu 2
