# CHANGELOG

Historia istotnych zmian w projekcie **Mapa Katastralna Czarna**.

## 1.1.2 — 2026-06-04

### Zmieniono

- **Lokalizacja instalacji portable PG**: z `<project_root>/postgres/`
  (z 1.1.1) na **`<project_root>/.runtime/postgres/`**. Katalog `.runtime/`
  jest ukryty (kropka z przodu), semantyczny (przeznaczony na lokalne
  runtime artifacts) i rozszerzalny (w przyszłości może hostować inne
  pliki runtime, np. cache SQLite, logi sesji). Utrzymano politykę
  "zero AppData" — binaria i dane PG leżą WYŁĄCZNIE w katalogu projektu.

### Usunięto

- **`portable_pg_installed_legacy()`** — w 1.1.2 nie ma już czego
  migrować (wymuszamy świeżą instalację w nowej lokalizacji).
- **`_get_legacy_install_dirs()`** — wewnętrzny helper, który
  zwracał ścieżki AppData. Teraz cała logika AppData jest martwa.
- **Cała logika fallbacku do AppData w `uninstall_portable_pg()`** —
  uninstall celuje WYŁĄCZNIE w `<root>/.runtime/postgres/`. Jeśli
  katalog nie istnieje → `success=True, removed_files=0`.
- **Stan "⚠️ Legacy" w wizardzie** — w sekcji "Portable PostgreSQL"
  zostały tylko dwa stany: ✅ zainstalowany / 📦 niezainstalowany.
  Kreator nie oferuje już "czyszczenia starej instalacji AppData",
  bo nie ma czego czyścić.
- **Sekcja fallbacku w `get_pg_install_dir()`** — funkcja zawsze
  zwraca `<root>/.runtime/postgres/` (z `RuntimeError` gdy brak
  project root). Brak fallbacku na `%LOCALAPPDATA%` / `~/.local/share`
  / `~/Library/Application Support`.

### Dodano

- **`.runtime/` w `.gitignore`** — katalog jest gitignored, ale
  tworzony przez `.gitkeep` z komentarzem o przeznaczeniu.
- **Komentarz `_uninstall_log()`** — wyjaśnia, że w produkcji powinien
  być zastąpiony przez module-level `logging`.
- **2 nowe assercje w `test_get_pg_install_dir_returns_project_root_postgres`**:
  `assert result == root / ".runtime" / "postgres"` i `assert ".runtime" in str(result)`.
- **Aktualizacja 3 testów ścieżek** — `test_get_pg_install_dir_*` i
  `test_uninstall_portable_pg_uses_default_install_dir` używają teraz
  nowej ścieżki `.runtime/postgres`.

### Zmieniono (testy)

- `test_get_pg_install_dir_returns_project_root_postgres` (1.1.1) →
  weryfikuje `<root>/.runtime/postgres/` (1.1.2).
- `test_get_pg_install_dir_is_consistent_across_platforms` →
  sprawdza nową ścieżkę dla wszystkich platform.
- `test_uninstall_portable_pg_uses_default_install_dir` →
  tworzy i usuwa katalog w `<root>/.runtime/postgres/`.
- **Usunięto 2 testy legacy**:
  `test_get_legacy_install_dirs_returns_old_paths`,
  `test_portable_pg_installed_legacy_returns_false_when_no_legacy`.
- **Usunięto asercję legacy** z
  `test_pg_portable_service_has_uninstall_function` (sprawdza
  tylko `uninstall_portable_pg` i `UninstallResult`).
- **Komentarze 1.1.1 → 1.1.2** w 2 testach wizarda.

### Bezpieczeństwo

- **Brak efektów ubocznych w systemie plików poza projektem** —
  wszystkie operacje (install/uninstall) ograniczone do
  `<root>/.runtime/postgres/`. Usunięcie projektu z dysku =
  kompletne usunięcie portable PG.
- **Safety check `uninstall_portable_pg()`** nadal aktywny:
  wymaga podkatalogu `pgsql/` przed `rmtree`.

### Stabilna regresja

`pytest backend/tests/` → **1030 passed, 8 skipped, 0 failed, 0 errors**
(spadek z 1032 → 1030 testów, **−0.2%** — usunięto 2 testy legacy).
Wszystkie 8 skipów to legitymowane auto-skipy PG E2E
(brak instancji PostgreSQL w CI).

### Real-download validation (spike)

Walidacja metodą **partial download** (Range request, bez ściągania
całego archiwum) dla `get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip`:

- **Do pobrania**: 323.04 MiB
- **Po rozpakowaniu**: 919.83 MiB (0.9 GiB)
- **Pliki**: 22,649 (w tym pgAdmin 4 IDE — 172 MB sam w sobie)
- **Czas @ 2.29 MB/s**: ~2:21 min
- **EDB jest jedynym źródłem** "binaries" dla Windows (postgresql.org,
  openscg.com, community builds — niekompatybilne lub porzucone)
- Sprawdzone alternatywne wersje PG: 15.9 (289 MB), 16.3 (336 MB),
  16.5 (291 MB) — wszystkie ~300 MB, ~900 MB uncompressed

Wynik zapisany w `docs/technical/DATABASE.md` sekcja 4.6.

### Znane ograniczenia (1.1.2)

- Brak auto-cleanup jeśli użytkownik miał instalację 1.1.1
  (`<root>/postgres/`) — musi uruchomić `uninstall_portable_pg`
  ręcznie (przycisk w kreatorze), albo skasować katalog ręcznie.
  Kreator nie wykrywa już "starych" instalacji 1.1.1, bo to
  ostatnia wersja z innym katalogiem.

## 1.1.3 — 2026-06-04

### Naprawiono (real-install bugs z P2.1)

Trzy krytyczne bugi odkryte podczas real-install testu EDB ZIP 16.4
(323 MB download → 920 MB extract, 22,649 plików). Mockowane testy
**nie wykryły** tych problemów — bo w mockach `pg_ctl` zawsze zwracał
"sukces", a `proc.wait()` na krótko zwracał kod 0.

#### Bug #1: `wait_for_pg_ready` zwracał `True` mimo "starting up"

**Scenariusz:** PG w recovery binduje port natychmiast po `pg_ctl start`,
ale `psql -c "SELECT 1"` zwraca `FATAL: the database system is starting up`.
Stara implementacja sprawdzała tylko TCP socket — uznawała to za "ready".

**Fix:** dwuetapowy check w `pg_runtime.py:wait_for_pg_ready`:
1. Szybki socket check (do 1s)
2. `psql -c "SELECT 1"` z env `PGPASSWORD` (pewny check)

Fallback gdy brak `psql.exe` → wraca do socket-only.

#### Bug #2: `start_pg_server` nie wykrywał natychmiastowej śmierci `pg_ctl`

**Scenariusz:** stara wersja zwracała `ServerHandle` z referencją do
procesu `pg_ctl`, który już dawno umarł. Wizard UI mógł myśleć że
serwer działa, a tak naprawdę nie.

**Fix:** po `wait_for_pg_ready == True` sprawdź `proc.poll()`:
- `None` → OK (pg_ctl jeszcze żyje, np. bez `-w`)
- `0` → OK (pg_ctl zakończył się normalnie po sukcesie — typowe dla
  `pg_ctl start -w`)
- `!= 0` → `RuntimeError("pg_ctl zakończył się kodem N mimo gotowości")`

#### Bug #3: `stop_pg_server` wieszał się, gdy `pg_ctl stop -m fast` nie mógł dokończyć

**Scenariusz:** stara implementacja robiła tylko `handle.proc.wait(timeout)`.
Gdy baza nie była gotowa (np. start nie powiódł się), `pg_ctl stop` wisi
w nieskończoność czekając na ready, a my wisieliśmy razem z nim.

**Fix:** 4-etapowy fallback chain w `pg_runtime.py:stop_pg_server`:
1. `pg_ctl stop -m fast` (subprocess.run, timeout=30s)
2. → `pg_ctl stop -m immediate` (subprocess.run, timeout=10s)
3. → `handle.proc.terminate()` (handle.proc.wait, timeout=5s)
4. → `taskkill /F /T /PID <pid>` Windows / `kill -9` Unix (timeout=5s)

Pierwszy sukces wygrywa, ostatni krok zawsze gwarantuje cleanup.

#### Bonus bug #4: `is_pg_server_running` sprawdzał `proc.poll()` zamiast portu

**Scenariusz:** `pg_ctl start -w` po udanym starcie wychodzi z kodem 0,
więc `proc.poll() == 0` (nie `None`) — stara logika uznawała serwer
za "nieżywy" mimo że PG nasłuchiwał.

**Fix:** `is_pg_server_running` sprawdza TCP socket na `handle.port`
(0.5s timeout), nie `proc.poll()`.

#### Bonus bug #5: `launcher/ui/program_settings.py` NameError

**Scenariusz:** przy otwarciu "Ustawienia programu" → Security card
rzucało `NameError: name 'scale_wrap' is not defined`.

**Fix:** brakujący import w `program_settings.py:31`
(`from ..utils import set_dialog_icon, scale_wrap`).

### Testy dodane (1.1.3)

W `backend/tests/integration/test_pg_portable_flow_e2e.py` (+8 testów):

- `test_wait_for_pg_ready_uses_psql_query_for_real_ready`
- `test_wait_for_pg_ready_returns_false_when_psql_says_starting_up`
- `test_start_pg_server_raises_when_proc_dies_during_startup`
- `test_start_pg_server_raises_when_proc_exits_nonzero_after_ready`
- `test_start_pg_server_ok_when_proc_exits_zero_after_ready`
- `test_is_pg_server_running_uses_port_not_proc_poll`
- `test_stop_pg_server_returns_ok_when_proc_already_dead`
- `test_stop_pg_server_falls_back_to_immediate_when_fast_fails`

Łącznie: **+8 testów** (1030 → 1038 passed, 8 skipped).

### Real-install walidacja (1.1.3)

**Dwa podejścia** do real-install walidacji P2.1 — oba w repo, oba z
prawdziwymi binariami PG 16.4 EDB ZIP, zero mocków:

#### 1. `backend/tests/integration/test_pg_portable_real_install.py` (pytest, domyślnie skipped)

Waliduje **instalację**: download + extract + initdb + cleanup. Może być
wpięty do CI matrix dla smoke testu P2.1. Domyślnie skipped (za długi,
za ciężki, wymaga internetu). Włączenie przez `RUN_REAL_INSTALL=1`.

Wynik (cold start, 4.06.2026, ~35s):

| Krok | Czas | Status |
|------|------|--------|
| 1. download ZIP (323 MB) | 17.6s | OK @ 18 MB/s |
| 2. extract (920 MB, 22,649 files) | 12.3s | OK |
| 3. initdb | 5.3s | OK, klaster 16.4 |
| verify PG_VERSION=16, pg_hba.conf=5837B | < 1s | OK |
| uninstall + cleanup | < 1s | OK |

#### 2. `scripts/test_pg_portable_real_install.py` (standalone, pełen E2E)

Waliduje **pełen runtime P2.1**: install + start + psql + createdb + stop
(z 4-etapowym fallback chain). Dla deweloperów którzy chcą smoke test
przed release. Mirroruje logikę z MCP temp `pg_real_install_v2.py`,
ale z auto-cleanup i CLI args. Wymaga internetu i ~1 GB dysku.

Użycie:

```bash
# Pełen E2E (7/7 kroków, ~24s warm / ~3 min cold)
python scripts/test_pg_portable_real_install.py

# Tylko install + initdb (3/3 kroków, ~35s warm)
python scripts/test_pg_portable_real_install.py --skip-start-stop

# Inny port / workdir
python scripts/test_pg_portable_real_install.py --port 5446 --workdir D:\pg_test
```

Wynik (cold start, 4.06.2026):

| Krok | Czas | Status |
|------|------|--------|
| 1. download ZIP (323 MB) | 18.0s | OK @ 18 MB/s |
| 2. extract (920 MB, 22,649 files) | 10.1s | OK |
| 3. initdb | 4.8s | OK |
| 4. start (pg_ctl -w) | 1.1s | OK, PID=6228 |
| 5. wait_for_pg_ready (FIX) | 0.0s | True, psql `SELECT 1 = 1` |
| 6. createdb test_p2_1 + SELECT current_database() | < 1s | OK |
| 7. stop (4-etapowy fallback) | 0.0s | OK (pg_ctl juz martwy) |
| uninstall | 4.0s | OK |

**Całość: 24s (po cache)** / ~3 min (cold start z downloadem).

#### Dlaczego dwa podejścia?

Pytest test uproszczony do install + initdb only, bo start PG w
długich ścieżkach extractu (np. pytest `tmp_path`) ma race condition
z Windows Defender scanning. Standalone skrypt używa krótkiej ścieżki
`C:\pg_real_install_test` i ma 7/7 sukces. Pełen E2E (7 kroków) lepiej
odpalać jako skrypt CLI, bo pytest jest za wolny na takie duże flow.

## 1.1.1 — 2026-06-04

### Zmieniono

- **Lokalizacja instalacji portable PG**: z `%LOCALAPPDATA%/MapaCzarna/postgres`
  (Windows) / `~/.local/share/MapaCzarna/postgres` (Linux) /
  `~/Library/Application Support/MapaCzarna/postgres` (macOS)
  na **`<project_root>/postgres/`** (wspólna dla wszystkich platform).
  Pliki są teraz obok kodu źródłowego — widoczne w drzewie projektu,
  łatwe do znalezienia i skasowania, gitignored. Stara lokalizacja
  nadal wykrywana przez `portable_pg_installed_legacy()` dla
  płynnej migracji (przycisk "Odinstaluj" w kreatorze czyści oba).

### Dodano

- **`uninstall_portable_pg(install_dir=None, stop_server=True, timeout=10.0)`**
  w `pg_portable_service.py` — graceful stop serwera PG (`pg_ctl stop -m fast`)
  + `shutil.rmtree()` całego katalogu. Safety check: odmawia usunięcia
  katalogu bez podkatalogu `pgsql/`. Zwraca dataclass `UninstallResult`
  z `success`, `removed_files`, `server_was_running`, `error`.
- **`portable_pg_installed_legacy()`** w `pg_portable_service.py` — wykrywa
  stare instalacje z 1.1.0 w AppData, używane przez wizard do oferowania
  migracji.
- **Sekcja "Portable PostgreSQL" w kroku 1 kreatora** — zawsze widoczna
  LabelFrame z:
  - ✅/📦/⚠️ statusem (zainstalowany / brak / legacy w AppData),
  - pełną ścieżką instalacji,
  - przyciskiem **"🗑 Odinstaluj portable PG"** (widocznym tylko gdy
    zainstalowany). Wywołuje `uninstall_portable_pg()` z messageboxem
    potwierdzenia. Po uninstall odświeża status (komunikat "niezainstalowany").
- **12 nowych testów** (45 → 56 w `test_pg_portable_service.py`,
  25 → 28 w `test_database_wizard_contract.py`):
  - 4 testy nowej ścieżki instalacji (`<root>/postgres/`),
  - 1 test `_find_project_root()`,
  - 1 test legacy paths,
  - 7 testów `uninstall_portable_pg()` (success, safety check,
    running server, default path, `__bool__`, etc.),
  - 3 testy kontraktu wizarda (nowe metody + lokalna ścieżka).
- `.gitignore`: dodano `postgres/` i `postgres-portable/`.

### Bezpieczeństwo

- **`uninstall_portable_pg()` ma safety check**: sprawdza czy katalog
  zawiera podkatalog `pgsql/` zanim uruchomi `rmtree`. Chroni przed
  przypadkowym usunięciem niewłaściwego katalogu.
- **Nie wymaga uprawnień administratora** — pliki leżą w katalogu
  projektu, nie w lokalizacjach systemowych.
- **Graceful stop z timeoutem 10s** — w razie problemów z zatrzymaniem
  serwera (np. zablokowany proces), uninstall i tak przechodzi do
  `rmtree` (proces zostanie sierocym — Windows zwolni go po crashu,
  Linux/macOS zwolni po usunięciu plików binariów).
- **Brak efektów ubocznych w systemie**: portable PG NIE modyfikuje
  `PATH`, NIE tworzy usługi systemowej, NIE wpisuje się w
  `Add/Remove Programs`. Usunięcie = `rm -rf` katalogu.

### Stabilna regresja

`pytest backend/tests/` → **1032 passed, 8 skipped, 0 failed, 0 errors**
(wzrost z 1020 → 1032 testów, **+1.2%**). Wszystkie 8 skipów to
legitymowane auto-skipy PG E2E (brak instancji PostgreSQL w CI).

### Znane ograniczenia (1.1.1)

- Brak auto-migracji starych instalacji z AppData — user musi kliknąć
  "Odinstaluj" ręcznie, a potem zainstalować ponownie (kreator zaproponuje
  instalację w nowej lokalizacji po teście połączenia).
- Brak opcji "zachowaj dane, przenieś binaria" — uninstall jest totalny.

## 1.1.0 — 2026-06-04

## 1.1.0 — 2026-06-04

### Dodano

- **Portable PostgreSQL (Priorytet 2.1)** — launcher potrafi samodzielnie
  pobrać i zainstalować portable PostgreSQL gdy użytkownik nie ma systemowej
  instalacji. Eliminuje ręczne pobieranie instalatora EDB i konfigurację
  „z palca".
  - `launcher/services/pg_portable_service.py` (466 linii) — detekcja
    systemowego PG (`detect_system_pg`), wybór URL na podstawie
    platformy/architektury, atomic download (`download_pg_binary` z
    retry + liniowy backoff), ekstrakcja ZIP/TAR.GZ do
    `%LOCALAPPDATA%/MapaCzarna/postgres/`, weryfikacja stanu instalacji.
  - `launcher/services/pg_runtime.py` (448 linii) — `init_pg_data_dir`
    (subprocess `initdb --auth=trust`), `start_pg_server` (subprocess
    `pg_ctl start` z `postmaster.pid` tracking), `stop_pg_server`
    (graceful `pg_ctl stop -m fast` z fallback `SIGTERM`/`terminate()`),
    `wait_for_pg_ready` (TCP socket polling), `is_pg_server_running`,
    `remove_pg_data_dir`.
  - Integracja z `database_wizard.py` — auto-detekcja braku PG w
    `__init__` (opóźniona o 500 ms przez `self.after`), propozycja
    „Pobierz i zainstaluj portable PostgreSQL" po nieudanym teście
    połączenia (jedna propozycja na sesję), własny progress dialog
    (Tk Toplevel z ProgressBar) + DAEMON thread dla długich operacji.
  - Smoke test binariów po instalacji (init → start → stop), potwierdza
    że archiwum się rozpakowało poprawnie.
  - **73 nowe testy** (36 unit + 28 integration + 9 smoke), łączny czas
    wykonania < 1 s.
- Sekcja „Portable PostgreSQL (P2.1)" w `docs/technical/DATABASE.md`
  z diagramem architektury, UX flow i znanymi ograniczeniami.

### Zmieniono

- `launcher/ui/database_wizard.py` z 877 do 1181 linii (+304) — nowe
  metody `_offer_portable_pg_install`, `_install_portable_pg_with_progress`,
  `_check_portable_pg_on_startup`, importy `pg_portable_service` i
  `pg_runtime`.
- `backend/tests/unit/test_database_wizard_contract.py` z 298 do 339
  linii (+41) — nowa klasa `TestPortablePgIntegration` z 4 assercjami
  kontraktu P2.1.
- `TODO.md` — oznaczono Priorytet 2 (kreator migracji SQLite → PostgreSQL)
  jako zrobiony, dodano pełny opis Priorytetu 2.1 (portable PG) ze
  statusem zrobionym i listą 1686 linii implementacji + 73 testów.
- `PROJECT_SKILL.md` — test count 943 → 1020, dopisano `1.1.0` do
  statusu projektu.

### Stabilna regresja

`pytest backend/tests/` → **1020 passed, 8 skipped, 0 failed, 0 errors**
(wzrost z 943 → 1020 testów, **+8.2%**). Wszystkie 8 skipów to
legitymowane auto-skipy PG E2E (brak instancji PostgreSQL w CI).

## 1.0.0 — 2026-06-03

Pierwsza wersja przygotowana do publikacji / pokazania projektu.

### Dodano

- Backend FastAPI z routerami mapy, właścicieli, genealogii, admina, diagnostyki
  i punktów historycznych.
- Launcher Tkinter z zarządzaniem miejscowościami, konfiguracją, backupami,
  diagnostyką, ustawieniami admina i kreatorem PostgreSQL.
- Obsługę SQLite oraz kreator migracji SQLite → PostgreSQL/PostGIS.
- Punkt historyczny „Dworzec kolejowy w Czarnej” oraz moduł mapy
  `static/mapa/historical_points.js`.
- Panel diagnostyki jakości danych z 9 metrykami i agregatem rekordów
  niekompletnych.
- Minimum bezpieczeństwa admina: status auth, zmiana hasła, walidacja SECRET_KEY,
  ostrzeżenia trybu sieciowego, CORS z env.
- Refaktoryzację P2.5 panelu admina: `api.js`, `utils.js`, `notifications.js`,
  `diagnostics.js`, `objects.js`, `owners.js`, `owner-modal.js`, `demography.js`,
  `tree-renderer.js`, `dashboard.js`, `genealogy-mini-tree.js`, `genealogy-details.js`,
  `genealogy-modal.js`, `genealogy-list.js`, `auth.js`, `genealogy-tree.js`.
- Dokumentację techniczną w `docs/technical/`.
- Artefakty release P5.1: `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`, CI.

### Zmieniono

- `admin.js` został zmniejszony z ok. 2800 do ok. 398 linii przez wydzielenie
  modułów JS.
- Autoryzacja panelu admina została przeniesiona z `admin.js` do `auth.js`,
  z zachowaniem callbacków shellowych i kontraktu `localStorage.adminLoggedIn`.
- Legacy pełnego drzewa `genealogia_admin.js` zostało zastąpione modułem
  `js/genealogy-tree.js`, podpiętym przez przycisk „Pełne drzewo” w szczegółach osoby.
- Rozpoczęto refaktoryzację publicznych stron właścicieli: dodano
  `static/wlasciciele/js/api.js` (`OwnersAPI`) i przepięto URL-e w `protokol.js`.
- Dodano `static/wlasciciele/js/utils.js` (`OwnersUtils`) i przeniesiono helpery
  formatowania/sanityzacji z `protokol.js`.
- Dodano `static/wlasciciele/js/protocol-images.js` (`ProtocolImages`) i przeniesiono
  obsługę skanów protokołu, Panzoom oraz modala obrazu z `protokol.js`.
- Dodano `static/wlasciciele/js/protocol-genealogy-tree.js`
  (`ProtocolGenealogyTree`) i przeniesiono obsługę drzewa genealogicznego protokołu
  z `protokol.js`.
- `compare.js` zaczął korzystać z publicznych modułów `OwnersAPI`/`OwnersUtils`
  dla URL-i właścicieli, genealogii, skanów, mapy oraz formatowania ułamków.
- `compare.js` deleguje drzewo genealogiczne do `ProtocolGenealogyTree`, usuwając
  lokalny renderer drzewa z porównywarki.
- `compare.js` deleguje skany protokołów do `ProtocolImages`, usuwając lokalny modal,
  wyszukiwanie skanów, Panzoom i stan galerii z porównywarki.
- Dodano `static/wlasciciele/js/compare-renderer.js` (`CompareRenderer`) i
  przeniesiono render kolumn porównania, sekcji działek oraz wyrównywanie kart
  z `compare.js`.
- Dodano `static/wlasciciele/js/compare-interactions.js` (`CompareInteractions`) i
  przeniesiono linki mapy oraz eksport PDF z `compare.js`.
- Rozpoczęto refaktoryzację centrum analitycznego P2.8: `stats-script.js` korzysta
  z `OwnersAPI.stats()` i `OwnersUtils.formatArea()` zamiast lokalnego endpointu i
  lokalnego formattera powierzchni.
- Dodano `static/wlasciciele/js/stats-ui.js` (`StatsUI`) i przeniesiono podstawową
  synchronizację motywu oraz tryb pełnoekranowy z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-actions.js` (`StatsActions`) i przeniesiono
  akcje przycisków centrum analitycznego: eksport wykresów, TOP 10 na mapie oraz
  narzędzia porównania/Excel/druk/share.
- Dodano `static/wlasciciele/js/stats-data.js` (`StatsData`) i przeniesiono pobieranie
  pakietu statystyk przez `OwnersAPI.stats()` z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-help.js` (`StatsHelp`) i przeniesiono obsługę
  modala pomocy centrum analitycznego z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-search.js` (`StatsSearch`) i przeniesiono globalną
  wyszukiwarkę właścicieli/działek z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-counters.js` (`StatsCounters`) i przeniesiono
  animowane liczniki centrum analitycznego z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-tabs.js` (`StatsTabs`) i przeniesiono zakładki
  oraz przełączniki rankingów/infrastruktury z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-metrics.js` (`StatsMetrics`) i przeniesiono
  podstawowe metryki powierzchni, rzek/dróg, wyrysowania działek i powierzchni
  miejscowości z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-jewish.js` (`StatsJewish`) i przeniesiono sekcję
  statystyk właścicieli żydowskich z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-ranking.js` (`StatsRanking`) i przeniesiono
  ranking właścicieli oraz jego filtry z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-parcels-ranking.js` (`StatsParcelsRanking`) i
  przeniesiono ranking działek z filtrem kategorii, linkami do protokołów oraz
  fallbackiem „Pokaż na mapie” z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-infrastructure-ranking.js`
  (`StatsInfrastructureRanking`) i przeniesiono rankingi rzek/dróg z linkami do mapy
  z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-timeline.js` (`StatsTimeline`) i przeniesiono
  render osi czasu protokołów z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-demographics.js` (`StatsDemographics`) i
  przeniesiono większy blok demografii: wykres populacji, karty dekad, przełącznik
  źródeł oraz modal porównania okresów z `stats-script.js`.
- Dodano `static/wlasciciele/js/stats-genealogy.js` (`StatsGenealogy`) i przeniesiono
  większy blok genealogii: kafle, ranking nazwisk, wykresy serii oraz dodatkowe
  wykresy demograficzne XIX wieku z `stats-script.js`.
- Usunięto martwe adaptery drzewa genealogicznego z `admin.js`, które odwoływały
  się do nieistniejących pól `elements.treeModal*` i nie miały call-site'ów.
- Zdjęcia markerów punktów historycznych przeniesiono do `point_photos/`,
  oddzielnie od galerii `history_photos/`.
- `PROJECT_SKILL.md` opisuje aktualną architekturę FastAPI/Python 3.11+.

### Naprawiono

- Backend akceptuje hashe Werkzeug (`scrypt:...`) generowane przez launcher.
- Linki i statusy przypisania obiektów w panelu admina.
- CORS i walidację sekretów w trybie produkcyjnym.
- `_FakeVar` w `test_add_edit_location_dialog_photos.py` (mock `StringVar`)
  akceptuje `*args, **kwargs` w `.get()`, dzięki czemu ten sam mock pasuje
  zarówno do widgetów `Entry` (`get()`), jak i `ScrolledText`
  (`get("1.0", tk.END)`) — zamienionych w P3.1 na wielolinijkowe pole opisu.
- Fixture `server` w `backend/tests/conftest.py` wymusza `DB_ENGINE=sqlite`
  (zamiast warunku `if "DB_ENGINE" not in env`). Bez wymuszenia shell developera
  z zostawionym `DB_ENGINE=postgresql` powodował 40s timeout przy starcie
  serwera testowego (bo PG na localhost zazwyczaj nie działa).
- Helpery `_run_async` (w `test_db_helpers.py`) i `_run_compute` (w
  `test_diagnostics_service.py`) zapisują i przywracają thread-local
  `running_loop` wokół `asyncio.run` / `new_event_loop`. Bez tego teardown
  fixture `page` z `pytest-playwright` zostawiał `ProactorEventLoop` jako
  "running" w bieżącym wątku, co powodowało
  `RuntimeError: Cannot run the event loop while another loop is running`
  w 25 testach w pełnej sesji (w izolacji działały).
- Wyekstrahowano wspólny helper `tests/unit/_asyncio_helpers.py` z
  `run_async_safely()` używany przez oba pliki testów.

### Znane ograniczenia

- Brak rate-limit logowania, 2FA i audit logu — planowane po v1.0.0.
- Brak pełnego i18n oraz jednej mapy wielu miejscowości — świadomie odłożone.
- Resztkowa orkiestracja genealogii nadal pozostaje w `admin.js`, ale mini-drzewo,
  pełne drzewo, panel szczegółów, modal dodawania/edycji oraz lista/ładowanie/
  filtrowanie są już w osobnych modułach `genealogy-*.js`.
