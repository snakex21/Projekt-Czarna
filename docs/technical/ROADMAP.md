# Roadmapa

> DokÄ…d zmierza projekt. Planowane kierunki, odrzucone pomysĹ‚y, perspektywy dĹ‚ugoterminowe.

## 1. NajbliĹĽsze priorytety (planowane)

### Priorytet 2 â€” kreator PostgreSQL / migracja SQLite â†’ PostgreSQL

**Cel:** ograniczyÄ‡ rÄ™czne klikanie w pgAdminie. Launcher powinien automatyzowaÄ‡
caĹ‚y proces.

**Zakres:**

- [x] Sprawdzanie poĹ‚Ä…czenia (host, port, user, hasĹ‚o, uprawnienia).
- [x] Tworzenie bazy automatycznie jeĹ›li nie istnieje.
- [x] Tworzenie schematu tabel (z typami PostGIS dla geometrii).
- [x] Przenoszenie danych z SQLite / backupĂłw.
- [x] Weryfikacja importu (liczby wĹ‚aĹ›cicieli, obiektĂłw, osĂłb, powiÄ…zaĹ„).
- [x] PrzeĹ‚Ä…czenie `.env` na `DB_ENGINE=postgresql` dopiero po sukcesie.
- [x] W razie bĹ‚Ä™du - zostawiÄ‡ system na SQLite.
- [x] Log migracji.

**Stan (czerwiec 2026):** kreator zaimplementowany w
`launcher/services/postgres_migration_service.py` (22 KB, 21 importowalnych symboli,
27 testĂłw unit) + UI `launcher/ui/database_wizard.py` (36 KB).

**Testy E2E z prawdziwym PG:** `backend/tests/integration/test_postgres_migration_e2e.py`
(8 testĂłw, auto-skip gdy PG niedostÄ™pny):

```text
$env:PG_TEST_PASSWORD='twoje_haslo'
python -m pytest backend/tests/integration/test_postgres_migration_e2e.py -v
```

Wymaga: `PG_TEST_HOST`, `PG_TEST_PORT`, `PG_TEST_USER`, `PG_TEST_PASSWORD`.
Gdy brak PG (sandbox/CI) - testy sÄ… skipowane (cache'owane - 4s suite zamiast 32s).

**Testy kontraktu UI:** `backend/tests/unit/test_database_wizard_contract.py`
(21 testĂłw - atrybuty, kroki, nawigacja, izolacja importĂłw, re-eksport przez
`launcher.ui.dialogs`, smoke import bez tworzenia okien Tk).

**PozostaĹ‚e (poza zakresem P2):**

- [ ] PostGIS nie jest zainstalowany na serwerze - graceful skip w testach
  (juĹź zaimplementowane w E2E - `pytest.skip` gdy brak rozszerzenia).
- [ ] Test wydajnoĹ›ci migracji (10k+ wĹ‚aĹ›cicieli) - planowany po P5.1.
- [ ] Dual-mode runtime (backend czyta z PG lub SQLite na podstawie `DB_ENGINE`)
  - obecnie backend ma osobne Ĺ›cieĹźki (planowane w P5.1).

**UI launchera:**

```text
Kreator PostgreSQL
[SprawdĹş poĹ‚Ä…czenie]   â† ping + walidacja user/hasĹ‚o
[UtwĂłrz bazÄ™]          â† CREATE DATABASE jeĹ›li brak
[Migruj z SQLite]      â† kopiowanie tabel + danych
[PrzeĹ‚Ä…cz aplikacjÄ™]   â† zmiana .env + restart
[Testuj]               â† smoke test po migracji
```

Lub jeden przycisk: `[Skonfiguruj automatycznie]`.

**ZaĹ‚oĹĽenie:** na poczÄ…tek nie robimy instalatora PostgreSQL. JeĹ›li
PostgreSQL nie jest zainstalowany, launcher pokaĹĽe instrukcjÄ™ lub link.

**Dlaczego waĹĽne:** aktualnie system zaleĹźy od rÄ™cznej konfiguracji pgAdmina
dla PostgreSQL. Dla wiÄ™kszych zbiorĂłw SQLite nie wystarcza.

### Priorytet 2.5 Etap 2 â€” `objects.js` (refaktoryzacja JS admina)

**Cel:** wydzieliÄ‡ sekcjÄ™ obiektĂłw geograficznych z monolitu `static/admin/admin.js`
do osobnego moduĹ‚u.

**Zakres:**

- [x] `static/admin/js/objects.js` z `window.AdminObjects = Object.freeze({...})`.
- [x] Funkcje: `loadObjects` (→ `load`), `renderObjects` (wewnÄ™trzna),
  `filterObjects` (→ `filter`), `editObject` (→ `edit`), `saveObject` (→ `save`),
  `deleteObject` (→ `remove`). Publiczne API: 5 metod.
- [x] Render statusu `Nieprzypisany` / `ProtokĂłĹ‚ X â€” wĹ‚aĹ›ciciel` (zachowaÄ‡ z P1).
- [x] ZachowaÄ‡ obecny kontrakt HTML tabeli obiektĂłw + linki do protokoĹ‚Ăłw.
- [x] Testy: `test_objects_module_*` (26 testĂłw) w `test_objects_module_contract.py`.
- [x] `admin.html` ładuje `js/objects.js` po `diagnostics.js`, przed `admin.js`.
- [x] `admin.js` używa aliasu `const OBJ = window.AdminObjects` (throw `Error`
      jeśli brak - wzorzec weryfikacji kolejności ładowania).

**Stan (czerwiec 2026):** **wydzielone**. `admin.js` zmalał z 2803 do 2727 linii
(281 linii przeniesionych do `objects.js`). Anti-regresja: 7 testów
sprawdza że `admin.js` NIE zawiera już `loadObjects`/`renderObjects`/
`filterObjects`/`editObject`/`saveObject`/`deleteObject`.

**Dlaczego waĹĽne:** `admin.js` to nadal > 2700 linii. Bez dalszego wydzielania
kolejnych sekcji (wlasciciele, genealogia, demografia) dalszy rozwĂłj jest kruchy.

### Priorytet 5.1 — publikacja open source (ZROBIONE częściowo, czerwiec 2026)

**Cel:** repozytorium gotowe do pokazania.

**Zakres:**

- [x] `README.md` (sekcje: opis, szybki start, architektura, status, dokumentacja).
- [x] `.gitignore` (Python, IDE, OS, DB, env, logi, materiaĹ‚y obrony).
- [x] `docs/` (ARCHITECTURE, TESTING, DATABASE, LAUNCHER, SECURITY, LOCATIONS, ROADMAP).
- [x] `LICENSE` (MIT).
- [x] `CONTRIBUTING.md` (konwencje, TDD, sekrety, PR).
- [x] `CHANGELOG.md` (historia zmian, sekcja `1.0.0`).
- [x] CI/CD (GitHub Actions: stabilny pytest + ręczny Playwright E2E).
- [ ] Screeny / GIFy w `docs/screenshots/`.
- [ ] Tag v1.0.0 (ręcznie po decyzji release).

## 2. Ulepszenia bezpieczeĹ„stwa (po P6)

### 2.1 Rate-limit logowania (5 prĂłb / 15 min)

- Ĺšledzenie po IP + username.
- Blokada na 15 minut po 5 bĹ‚Ä™dnych prĂłbach.
- Endpoint: `POST /api/admin/login` zwraca 429 gdy limit.
- PamiÄ™Ä‡: w pamiÄ™ci (dict) lub Redis (gdyby byĹ‚).

### 2.2 Auto-wygasanie sesji + refresh

- Token waĹĽny 24h.
- Mechanizm refresh: nowy token przed wygaĹ›niÄ™ciem (sliding window).
- Endpoint: `POST /api/admin/refresh`.
- Konfigurowalne: `ADMIN_SESSION_LIFETIME_HOURS`.

### 2.3 Audit log

- Tabela `audit_log`: kto, co, kiedy, skÄ…d (IP).
- Endpoint `GET /api/admin/audit-log` (dla admina).
- Hooki w mutujÄ…cych endpointach (`POST`, `PUT`, `DELETE`).

### 2.4 2FA (TOTP)

- Opcjonalne, wĹ‚Ä…czane per-uĹĽytkownik.
- Pierwsze logowanie: enroll (QR code).
- Drugie logowanie: TOTP z Google Authenticator / Authy.

### 2.5 Usunięcie dead code

- [x] `launcher/ui/security_manager.py` - relikt Flask, wołał nieistniejące
  endpointy `/api/admin/security/*`. Usunięty w P5.1 razem z aliasami/importami
  w `launcher_app.py`, `launcher/ui/dialogs.py` i przyciskiem z `program_settings.py`.

## 3. Refaktoryzacja JS admina (po 2.5 Etap 2)

### 3.1 Etap 3 — kolejne moduły (CZĘŚCIOWO ZROBIONE czerwiec 2026)

**Wydzielone w Etap 3:**

- `owners.js` (czerwiec 2026) — sekcja właścicieli (load/render/filter/edit/remove).
  4 publiczne metody: `load`, `filter`, `edit`, `remove`.
  Modal edycji był wtedy jeszcze w `admin.js`; od Etapu 6 jest w `owner-modal.js`.
  26 testów kontraktu w `test_owners_module_contract.py`.
- `demography.js` (czerwiec 2026) — sekcja demografii (load/render/add/save/remove).
  4 publiczne metody: `load`, `add`, `save`, `remove`. Elementy modala
  pobierane samodzielnie przez `document.getElementById` (nie z `elements`).
  26 testów kontraktu w `test_demography_module_contract.py`.

**Przed Etapem 3:**

- `admin.js`: 2642 linii → **2470 linii** (po wydzieleniu obu modułów).
- 52 nowe testy (26 owners + 26 demography).

**Wydzielone w Etap 4:**

- `tree-renderer.js` (czerwiec 2026) — renderer drzewa genealogicznego
  (`AdminTreeRenderer.render`). Przenosi `TREE_CONFIG`, pozycjonowanie węzłów,
  połączenia rodzic–dziecko/małżeństwa oraz rysowanie SVG/D3 z `admin.js`.
- 14 testów kontraktu w `test_tree_renderer_module_contract.py`.
- `admin.js`: 2470 linii → **2043 linii**.

**Wydzielone w Etap 5:**

- `dashboard.js` (czerwiec 2026) — pulpit admina, zegar, backup, szybkie akcje
  i modal informacji o systemie (`AdminDashboard.load/startClock/downloadBackup/handleQuickAction`).
- 14 testów kontraktu w `test_dashboard_module_contract.py`.
- `admin.js`: 2043 linie → **1971 linii**.

**Wydzielone w Etap 6:**

- `owner-modal.js` (czerwiec 2026) — formularz dodawania/edycji właściciela,
  edytor działek rzeczywistych i działek z protokołu, zapis POST/PUT.
- `owners.js` i `dashboard.js` korzystają z `window.AdminOwnerModal.open(...)`.
- 15 testów kontraktu w `test_owner_modal_module_contract.py`.
- `admin.js`: 1971 linii → **1808 linii**.

**Wydzielone w Etap 7:**

- `genealogy-mini-tree.js` (czerwiec 2026) — kompaktowe 3-generacyjne
  mini-drzewo z profilu osoby (`AdminGenealogyMiniTree.show`). Moduł nie robi
  fetch/API; dostaje dane przez `GEN_MINI.show(person, allGenealogy)`.
- Przeniesione helpery: `getPersonById`, `formatYears`, `getNodeClass`,
  `renderTreeNode` oraz handler `window.showMiniTreeForPerson`.
- Pełne ładowanie/render/filtrowanie genealogii, `openGenealogyModal`,
  `setupPersonAutocomplete` i `saveGenealogy` nadal pozostają w `admin.js`.
- 15 testów kontraktu w `test_genealogy_mini_tree_module_contract.py`.
- `admin.js`: 1808 linii → **1579 linii**.

**Wydzielone w Etap 8:**

- `genealogy-details.js` (czerwiec 2026) — prawy panel szczegółów osoby
  genealogicznej (`AdminGenealogyDetails.show`) z kartami relacji rodzinnych.
- Przeniesione helpery: `getPersonById`, `formatLifespan`, `findGrandparents`,
  `findParents`, `findSpouses`, `findSiblings`, `findChildren`, `findCousins`,
  `createRelationCard`, `renderRelationSection`.
- Akcje edycji/usuwania/mini-drzewa przechodzą przez callbacki z `admin.js`,
  więc moduł nie używa `fetch`, `window.AdminAPI` ani bezpośrednio mini-drzewa.
- Ładowanie/lista/filtrowanie genealogii oraz modal CRUD nadal pozostają w `admin.js`.
- 16 testów kontraktu w `test_genealogy_details_module_contract.py`.
- `admin.js`: 1579 linii → **1165 linii**.

**Wydzielone w Etap 9:**

- `genealogy-modal.js` (czerwiec 2026) — modal dodawania/edycji osoby
  genealogicznej (`AdminGenealogyModal.open/save`).
- Przeniesione: `openGenealogyModal`, `saveGenealogy`, autocomplete ojca/matki/
  małżonka/protokołu i dynamiczne wiersze małżeństw.
- Moduł używa `window.AdminAPI`, `window.AdminNotifications`, ale odświeżenie listy
  po zapisie realizuje przez callback `onSaved` z `admin.js`.
- `loadGenealogy`, `renderGenealogy`, `filterGenealogy`, `editGenealogy`,
  `deleteGenealogy` pozostają w `admin.js` jako orkiestracja/lista/usuwanie.
- 17 testów kontraktu w `test_genealogy_modal_module_contract.py`.
- `admin.js`: 1165 linii → **738 linii**.

**Wydzielone w Etap 10:**

- `genealogy-list.js` (czerwiec 2026) — ładowanie, renderowanie i filtrowanie
  listy osób genealogicznych (`AdminGenealogyList.load/render/filter`).
- Przeniesione: pobieranie genealogii/protokołów, lista `personsListContainer`,
  licznik `genPersonCount`, pusty stan, wyszukiwarka, filtr domu/płci i sortowanie.
- Moduł przekazuje stan do `admin.js` przez `onDataLoaded`, a wybór osoby przez
  callback `onSelect`; szczegóły, mini-drzewo i modal CRUD zostają w osobnych modułach.
- 18 testów kontraktu w `test_genealogy_list_module_contract.py`.
- `admin.js`: 738 linii → **565 linii**.

**Cleanup w Etap 11:**

- Usunięto martwe adaptery drzewa genealogicznego z `admin.js`:
  `showGenealogyTreeFromProtocol`, `showLocalFamilyTree`, `GenealogyTreeViewer/showClientTree`.
- Usunięto latentnie błędne odwołania do `elements.treeModalTitle`, `elements.treeModal`,
  `elements.treeContainer` oraz bezpośrednią zależność `admin.js` od `AdminTreeRenderer`.
- `admin.html` nie ładuje już `js/tree-renderer.js` w panelu admina; aktywne mini-drzewo
  pozostaje w `genealogy-mini-tree.js`.
- `admin.js`: 565 linii → **457 linii**.

**Wydzielone w Etap 12:**

- `auth.js` (czerwiec 2026) — autoryzacja panelu admina
  (`AdminAuth.init/checkAuth/login/logout`). Moduł przejął status auth,
  logowanie, wylogowanie, `currentUser` i `localStorage.adminLoggedIn`.
- `admin.js` zachowuje wyłącznie shellowe callbacki `showLoginScreen` i
  `showAdminPanel` (z `DASH.load()`), a auth inicjuje przez `AUTH.init(...)`.
- `auth.js` używa `window.AdminAPI` i `window.AdminNotifications`, nie hardcoduje
  endpointów `/api/admin/*` i nie zależy od dashboardu.
- Testy: 14 nowych testów kontraktu w `test_auth_module_contract.py`; kontrakty
  admina: **226 passed**.
- Stabilna regresja po Etapie 12: **699 passed, 8 skipped, 3 warnings**.
- `admin.js`: 457 linii → **393 linie**.

**Wydzielone w Etap 13:**

- `genealogy-tree.js` (czerwiec 2026) — pełne drzewo genealogiczne w panelu admina
  (`AdminGenealogyTree.show/showFromData/render/setContainer`). Moduł zastępuje legacy
  `static/admin/genealogia_admin.js`.
- Pełne drzewo używa danych już załadowanych przez admina (`allGenealogy`), bez starego
  fetcha po protokole `fetch(/api/genealogia/${protocolKey})`.
- Renderer korzysta z istniejącego modala `treeModal` / `treeContainer`; nie tworzy już
  osobnego `genealogyModal` / `genealogy-chart`.
- `genealogy-details.js` ma dwa wejścia: mini-drzewo oraz **Pełne drzewo** przez callback
  `onShowFullTree`; `admin.js` deleguje do `GEN_TREE.showFromData(...)`.
- Legacy `genealogia_admin.js` został odpięty z `admin.html` i usunięty.
- Testy: 11 testów kontraktu w `test_genealogy_tree_module_contract.py`; kontrakty
  admina: **237 passed**.
- Stabilna regresja po Etapie 13: **710 passed, 8 skipped, 3 warnings**.
- `admin.js`: 393 linie → **398 linii**.

**Do zrobienia w przyszłych etapach:**

- `historical-points.js` — juĹĽ istnieje (`static/mapa/`), ale admin może
  mieć osobną sekcję CRUD punktów historycznych.
- `genealogy.js` - **największa i najryzykowniejsza** (loadGenealogy,
  renderGenealogy, createRelationCard, renderRelationSection,
  openGenealogyModal, saveGenealogy, editGenealogy, deleteGenealogy), odłożona.
  Mini-drzewo jest wydzielone do `genealogy-mini-tree.js`, panel szczegółów do `genealogy-details.js`, modal CRUD
  do `genealogy-modal.js`, lista/ładowanie do `genealogy-list.js`, pełne drzewo
  do `genealogy-tree.js`.

### 3.2 Docelowa struktura (PO ETAPIE 4)

```text
static/admin/js/
├── api.js
├── utils.js
├── notifications.js
├── auth.js
├── owner-modal.js     (Etap 6)  ← NOWY
├── objects.js          (Etap 2)
├── owners.js           (Etap 3)  ← NOWY
├── demography.js       (Etap 3)  ← NOWY (używa 'demography' nazwy zamiast 'demographics')
├── dashboard.js        (Etap 5)  ← NOWY
├── genealogy-mini-tree.js (Etap 7) ← NOWY
├── genealogy-tree.js    (Etap 13) ← NOWY
├── genealogy-details.js (Etap 8) ← NOWY
├── genealogy-modal.js   (Etap 9) ← NOWY
├── genealogy-list.js    (Etap 10) ← NOWY
├── diagnostics.js
├── historical-points-admin.js  (Etap 5+)
├── genealogy.js        (Etap 5+)
└── main.js
```

Po zakończeniu: `admin.js` zostaje tylko jako cienki orkiestrator (aktualnie 398 linii).

### 3.3 Refaktoryzacja `static/wlasciciele/` (P2.7)

**Stan po audycie (czerwiec 2026):** publiczne strony właścicieli mają trzy duże
monolity JS:

- `protokol.js` — 1355 linii,
- `compare.js` — 1381 linii,
- `stats-script.js` — 3222 linie.

**Etap 1 — `OwnersAPI` (zrobione):**

- Dodano `static/wlasciciele/js/api.js` jako `window.OwnersAPI = Object.freeze({...})`.
- API centralizuje URL-e: `owner`, `genealogy`, `stats`, `protocolScan`,
  `protocolScanSingle`, `mapPage`.
- `protokol.html`, `compare.html`, `stats.html` ładują `js/api.js` przed głównymi
  skryptami.
- `protokol.js` korzysta z `OwnersAPI` dla `/api/wlasciciel`, `/api/genealogia`,
  `/protokoly/...` i podstawowych linków do mapy.
- Testy: 15 kontraktów w `test_public_owners_api_module_contract.py`.
- Stabilna regresja: **725 passed, 8 skipped, 3 warnings**.

**Etap 2 — `OwnersUtils` (zrobione):**

- Dodano `static/wlasciciele/js/utils.js` jako `window.OwnersUtils = Object.freeze({...})`.
- Moduł przenosi z `protokol.js`: `escapeHtml`, `normalizeText`,
  `generateFractionHTML`, `formatArea`, `formatLength`, `formatDate`.
- `protokol.html`, `compare.html`, `stats.html` ładują `js/utils.js` po `js/api.js`,
  przed głównymi skryptami.
- `protokol.js` używa aliasu `UTILS` i nie definiuje już lokalnych helperów.
- `protokol.js`: **1359 → 1301 linii**.
- Testy: 10 kontraktów w `test_public_owners_utils_module_contract.py`.
- Stabilna regresja: **735 passed, 8 skipped, 3 warnings**.

**Etap 3 — `ProtocolImages` (zrobione):**

- Dodano `static/wlasciciele/js/protocol-images.js` jako
  `window.ProtocolImages = Object.freeze({...})`.
- Moduł obsługuje wyszukiwanie skanów, modal obrazu, Panzoom, licznik stron i
  nawigację poprzedni/następny.
- `protokol.js` deleguje skany do `IMAGES.init(...)` i `IMAGES.find()`; nie zawiera
  już lokalnego stanu `panzoomInstance`, `imageUrls`, `currentImageIndex` ani funkcji
  `findProtocolImages/openImageModal/...`.
- `protokol.html` i `compare.html` ładują `js/protocol-images.js` po `js/api.js`,
  przed głównymi skryptami.
- `protokol.js`: **1301 → 1181 linii**.
- Testy: 10 kontraktów w `test_protocol_images_module_contract.py`.
- Stabilna regresja: **745 passed, 8 skipped, 3 warnings**.

**Etap 4 — `ProtocolGenealogyTree` (zrobione):**

- Dodano `static/wlasciciele/js/protocol-genealogy-tree.js` jako
  `window.ProtocolGenealogyTree = Object.freeze({...})`.
- Moduł obsługuje pobieranie danych przez `OwnersAPI.genealogy(ownerKey)`, render
  drzewa HTML, dialog `treeDialog`, przyciski `showTreeBtn`/`closeTreeBtn`,
  suwak poziomy i polskie komunikaty ładowania/błędów.
- `protokol.js` deleguje drzewo do `TREE.init(...)` i `TREE.close()`; nie zawiera
  już lokalnych `loadGenealogyTree`, `drawGenealogyTree`, helperów renderu drzewa
  ani `fetch(API.genealogy(ownerKey))`.
- `protokol.html` i `compare.html` ładują `js/protocol-genealogy-tree.js` po
  `js/protocol-images.js`, przed głównymi skryptami.
- `protokol.js`: **1181 → 735 linii**.
- Testy: 10 kontraktów w `test_protocol_genealogy_tree_module_contract.py`.
- Stabilna regresja: **755 passed, 8 skipped, 3 warnings**.

**Etap 5A — pierwsza migracja `compare.js` do modułów publicznych (zrobione):**

- `compare.js` wymaga `window.OwnersAPI` i `window.OwnersUtils`, używa aliasów
  `API` i `UTILS`.
- Przepięto dynamiczne URL-e porównywarki na `API.mapPage()`,
  `API.protocolScan(...)`, `API.protocolScanSingle(...)`, `API.genealogy(...)`
  i `API.owner(...)`.
- Lokalny helper ułamków zastąpiono `UTILS.generateFractionHTML`.
- `compare.js`: **1381 → 1371 linii**.
- Testy: 5 kontraktów w `test_compare_public_modules_contract.py`.
- Stabilna regresja: **760 passed, 8 skipped, 3 warnings**.

**Etap 5B — drzewo genealogiczne `compare.js` przez `ProtocolGenealogyTree` (zrobione):**

- `compare.js` wymaga `window.ProtocolGenealogyTree`, używa aliasu `TREE` i deleguje
  przyciski drzewa w obu kolumnach przez `TREE.init(...)`.
- `ProtocolGenealogyTree` obsługuje konfiguracje per-przycisk/per-właściciel dzięki
  zamknięciu na `ownerKey` i przekazane elementy DOM, więc działa zarówno w
  `protokol.js`, jak i w `compare.js`.
- Usunięto lokalny renderer drzewa z `compare.js`: `drawGenealogyTree`,
  `renderTreeNode`, helpery ról rodziców/dziadków oraz lokalne fetchowanie genealogii.
- `compare.js`: **1371 → 906 linii**.
- `ProtocolGenealogyTree`: **258 → 265 linii**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **77 passed**.
- Stabilna regresja: **761 passed, 8 skipped, 3 warnings**.

**Etap 5C — skany `compare.js` przez `ProtocolImages` (zrobione):**

- `compare.js` wymaga `window.ProtocolImages`, używa aliasu `IMAGES` i deleguje
  przyciski „Pokaż oryginał” przez `IMAGES.init(...)` + `IMAGES.find(session)`.
- `ProtocolImages` obsługuje sesje per-właściciel/per-przycisk, więc wspólny modal
  skanów działa nadal w `protokol.js` oraz dla dwóch kolumn w `compare.js`.
- Usunięto lokalne `openModal`, `closeModal`, `updateModal`, `findProtocolImages`,
  lokalny `new Image()`, lokalny Panzoom i stan `panzoomInst/imgs/idx` z `compare.js`.
- `compare.js`: **906 → 814 linii**.
- `ProtocolImages`: **164 → 181 linii**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **78 passed**.
- Stabilna regresja: **762 passed, 8 skipped, 3 warnings**.

**Etap 5D — renderer kolumn `CompareRenderer` (zrobione):**

- Dodano `static/wlasciciele/js/compare-renderer.js` jako
  `window.CompareRenderer = Object.freeze({...})`.
- Moduł przejął `columnTemplate`, `fillPlotSection` i `alignCardHeights` oraz
  korzysta z `window.OwnersUtils` / `UTILS.generateFractionHTML`.
- `compare.html` ładuje `js/compare-renderer.js` po modułach wspólnych, przed
  `compare.js`.
- `compare.js` deleguje render kolumny i działek do `RENDERER.*` i nie zawiera już
  lokalnych implementacji rendererów.
- `compare.js`: **814 → 527 linii**.
- `compare-renderer.js`: **180 linii**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **82 passed**.
- Stabilna regresja: **766 passed, 8 skipped, 3 warnings**.

**Etap 5E — interakcje mapy i PDF `CompareInteractions` (zrobione):**

- Dodano `static/wlasciciele/js/compare-interactions.js` jako
  `window.CompareInteractions = Object.freeze({...})`.
- Moduł przejął linki nagłówka do mapy, linki per kolumna, przycisk domu na mapie
  oraz eksport PDF przez `html2pdf`.
- `compare.html` ładuje `js/compare-interactions.js` po `js/compare-renderer.js`,
  przed `compare.js`.
- `compare.js` deleguje mapę/PDF do `INTERACTIONS.*` i nie zawiera już lokalnych
  `ensureHtml2Pdf`, `createPDF`, budowania `highlightTopOwners`/`highlightByIds`,
  `html2pdf().from` ani bezpośredniego `window.location.href` mapy.
- `compare.js`: **527 → 345 linii**.
- `compare-interactions.js`: **169 linii**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **86 passed**.
- Stabilna regresja: **770 passed, 8 skipped, 3 warnings**.

**Kolejność dalsza:** domknięcie `compare.js` jako cienkiego orkiestratora albo
większy temat `stats-script.js`.

### 3.4 Refaktoryzacja centrum analitycznego (P2.8)

**Etap 1 — `stats-script.js` używa `OwnersAPI`/`OwnersUtils` (zrobione):**

- Dodano kontrakt `backend/tests/unit/test_stats_public_modules_contract.py` i
  potwierdzono RED: **3 failed, 1 passed** przed implementacją.
- `stats-script.js` wymaga `window.OwnersAPI` i `window.OwnersUtils`, używa aliasów
  `API` oraz `UTILS` i zachowuje czytelne polskie błędy kolejności ładowania.
- Pobieranie danych statystyk używa teraz `fetch(API.stats())`, bez hardcoded
  `fetch('/api/stats')`.
- Lokalny formatter powierzchni został usunięty z `stats-script.js`; widok używa
  `UTILS.formatArea(...)`.
- `stats-script.js`: **3222 → 3212 linii**.
- Test kontraktowy statystyk: **4 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **90 passed**.
- Stabilna regresja: **774 passed, 8 skipped, 3 warnings**.

**Etap 2 — podstawowe UI statystyk `StatsUI` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 3 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-ui.js` jako `window.StatsUI = Object.freeze({...})`.
- Moduł przejął synchronizację motywu (`initThemeSync`, `applyTheme`) oraz tryb
  pełnoekranowy (`initFullscreen`) z zachowaniem polskich komunikatów UI.
- `stats.html` ładuje `js/stats-ui.js` po `js/utils.js`, przed `stats-script.js`.
- `stats-script.js` wymaga `window.StatsUI`, używa aliasu `UI` i deleguje motyw oraz
  fullscreen do modułu.
- `stats-script.js`: **3212 → 3160 linii**.
- `stats-ui.js`: **62 linie**.
- Test kontraktowy statystyk: **8 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **94 passed**.
- Stabilna regresja: **778 passed, 8 skipped, 3 warnings**.

**Etap 3 — akcje przycisków statystyk `StatsActions` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 7 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-actions.js` jako
  `window.StatsActions = Object.freeze({...})`.
- Moduł przejął inicjalizację przycisków eksportu wykresów, TOP 10
  właścicieli/działek/rzek/dróg na mapie oraz narzędzi Excel/druk/share/porównanie.
- `StatsActions` używa `window.OwnersAPI` i `API.mapPage()` dla przekierowań do mapy.
- `stats.html` ładuje `js/stats-actions.js` po `js/stats-ui.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsActions`, używa aliasu `ACTIONS` i deleguje
  akcje przycisków przez `ACTIONS.init(...)`.
- `stats-script.js`: **3160 → 3112 linii**.
- `stats-actions.js`: **102 linie**.
- Test kontraktowy statystyk: **12 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **98 passed**.
- Stabilna regresja: **782 passed, 8 skipped, 3 warnings**.

**Etap 4 — pobieranie danych statystyk `StatsData` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 10 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-data.js` jako
  `window.StatsData = Object.freeze({...})`.
- Moduł przejął pobieranie pakietu statystyk przez `OwnersAPI.stats()` i używa
  `credentials: 'same-origin'`.
- `stats.html` ładuje `js/stats-data.js` po `js/stats-actions.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsData`, używa aliasu `DATA` i deleguje
  ładowanie danych do `DATA.load()`.
- `stats-script.js`: **3112 → 3110 linii**.
- `stats-data.js`: **37 linii**.
- Test kontraktowy statystyk: **15 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **101 passed**.
- Stabilna regresja: **785 passed, 8 skipped, 3 warnings**.

**Etap 5 — modal pomocy statystyk `StatsHelp` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 14 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-help.js` jako
  `window.StatsHelp = Object.freeze({...})`.
- Moduł przejął obsługę `help-btn`, `help-modal`, `.modal-close`, otwieranie,
  zamykanie oraz zamykanie po kliknięciu poza treść modala.
- `stats.html` ładuje `js/stats-help.js` po `js/stats-data.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsHelp`, używa aliasu `HELP` i deleguje modal
  pomocy do `HELP.init()`.
- `stats-script.js`: **3110 → 3101 linii**.
- `stats-help.js`: **33 linie**.
- Test kontraktowy statystyk: **19 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **105 passed**.
- Stabilna regresja: **789 passed, 8 skipped, 3 warnings**.

**Etap 6 — globalna wyszukiwarka statystyk `StatsSearch` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 18 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-search.js` jako
  `window.StatsSearch = Object.freeze({...})`.
- Moduł przejął `initSearch`, `performGlobalSearch`, `highlightText`,
  `clearHighlights` oraz render wyników właścicieli/działek.
- `StatsSearch` używa `window.OwnersUtils` i `UTILS.formatArea(...)`.
- `stats.html` ładuje `js/stats-search.js` po `js/stats-help.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsSearch`, używa aliasu `SEARCH` i deleguje
  inicjalizację wyszukiwarki oraz ponowne wyszukanie po zmianie filtrów rankingów.
- `stats-script.js`: **3101 → 2911 linii**.
- `stats-search.js`: **218 linii**.
- Test kontraktowy statystyk: **23 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **109 passed**.
- Stabilna regresja: **793 passed, 8 skipped, 3 warnings**.

**Etap 7 — animowane liczniki statystyk `StatsCounters` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 22 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-counters.js` jako
  `window.StatsCounters = Object.freeze({...})`.
- Moduł przejął inicjalizację liczników przez `IntersectionObserver`, animację wartości
  oraz aktualizację liczników właścicieli i działek.
- `stats.html` ładuje `js/stats-counters.js` po `js/stats-search.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsCounters`, używa aliasu `COUNTERS` i deleguje
  `COUNTERS.init()` oraz `COUNTERS.update(...)`.
- `stats-script.js`: **2911 → 2855 linii**.
- `stats-counters.js`: **69 linii**.
- Test kontraktowy statystyk: **27 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **113 passed**.
- Stabilna regresja: **797 passed, 8 skipped, 3 warnings**.

**Etap 8 — zakładki i przełączniki rankingów `StatsTabs` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 26 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-tabs.js` jako
  `window.StatsTabs = Object.freeze({...})`.
- Moduł przejął zakładki `.tab-button` / `.tab-panel`, lazy-load osi czasu,
  przełącznik typu rankingu i przełącznik rzeki/drogi.
- `stats.html` ładuje `js/stats-tabs.js` po `js/stats-counters.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsTabs`, używa aliasu `TABS` i deleguje
  inicjalizację przez `TABS.init({ loadTimeline: loadTimeline })`.
- `stats-script.js`: **2855 → 2782 linii**.
- `stats-tabs.js`: **90 linii**.
- Test kontraktowy statystyk: **31 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **117 passed**.
- Stabilna regresja: **801 passed, 8 skipped, 3 warnings**.

**Etap 9 — podstawowe metryki statystyk `StatsMetrics` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 30 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-metrics.js` jako
  `window.StatsMetrics = Object.freeze({...})`.
- Moduł przejął metryki powierzchni działek, rzek/dróg, procentu wyrysowanych działek
  i powierzchni miejscowości.
- `stats.html` ładuje `js/stats-metrics.js` po `js/stats-tabs.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsMetrics`, używa aliasu `METRICS` i deleguje
  `METRICS.updateArea(...)`, `METRICS.updateRiversRoads(...)`,
  `METRICS.updateDrawnPercentage(...)`, `METRICS.updateLocationArea(...)`.
- `stats-script.js`: **2782 → 2687 linii**.
- `stats-metrics.js`: **97 linii**.
- Test kontraktowy statystyk: **35 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **121 passed**.
- Stabilna regresja: **805 passed, 8 skipped, 3 warnings**.

**Etap 10 — statystyki właścicieli żydowskich `StatsJewish` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 34 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-jewish.js` jako
  `window.StatsJewish = Object.freeze({...})`.
- Moduł przejął pokazywanie/ukrywanie sekcji właścicieli żydowskich, aktualizację
  liczników, render tabeli właścicieli i przycisk przejścia do mapy.
- `StatsJewish` używa `window.OwnersAPI` i `API.mapPage()`.
- `stats.html` ładuje `js/stats-jewish.js` po `js/stats-metrics.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsJewish`, używa aliasu `JEWISH` i deleguje
  `JEWISH.update(statsData.jewish_stats)`.
- `stats-script.js`: **2687 → 2620 linii**.
- `stats-jewish.js`: **100 linii**.
- Test kontraktowy statystyk: **39 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **125 passed**.
- Stabilna regresja: **809 passed, 8 skipped, 3 warnings**.

**Etap 11 — ranking właścicieli `StatsRanking` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 38 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-ranking.js` jako
  `window.StatsRanking = Object.freeze({...})`.
- Moduł przejął render rankingu właścicieli, filtry własności/sortowania/kategorii
  oraz utrzymanie aktywnego wyszukiwania po zmianie filtrów.
- `StatsRanking` używa `window.OwnersUtils` i `UTILS.formatArea(...)`.
- `stats.html` ładuje `js/stats-ranking.js` po `js/stats-jewish.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsRanking`, używa aliasu `RANKING` i deleguje
  `RANKING.init(...)`.
- `stats-script.js`: **2620 → 2531 linii**.
- `stats-ranking.js`: **118 linii**.
- Test kontraktowy statystyk: **43 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **129 passed**.
- Stabilna regresja: **813 passed, 8 skipped, 3 warnings**.

**Etap 12 — ranking działek `StatsParcelsRanking` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 42 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-parcels-ranking.js` jako
  `window.StatsParcelsRanking = Object.freeze({...})`.
- Moduł przejął render rankingu działek, filtr kategorii, linki do protokołów
  właścicieli i fallback „Pokaż na mapie” dla działek bez właściciela.
- `StatsParcelsRanking` używa `window.OwnersUtils` i `UTILS.formatArea(...)`.
- `stats.html` ładuje `js/stats-parcels-ranking.js` po `js/stats-ranking.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsParcelsRanking`, używa aliasu
  `PARCELS_RANKING` i deleguje `PARCELS_RANKING.init(statsData.parcels_ranking)`.
- `stats-script.js`: **2531 → 2463 linii**.
- `stats-parcels-ranking.js`: **83 linie**.
- Test kontraktowy statystyk: **47 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **133 passed**.
- Stabilna regresja: **817 passed, 8 skipped, 3 warnings**.

**Etap 13 — rankingi infrastruktury `StatsInfrastructureRanking` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 46 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-infrastructure-ranking.js` jako
  `window.StatsInfrastructureRanking = Object.freeze({...})`.
- Moduł przejął render rankingów rzek i dróg, formatowanie długości oraz przyciski
  „Pokaż na mapie” z parametrami `highlightRivers` / `highlightRoads`.
- `StatsInfrastructureRanking` używa `window.OwnersAPI` i `API.mapPage()`.
- `stats.html` ładuje `js/stats-infrastructure-ranking.js` po
  `js/stats-parcels-ranking.js`, przed `stats-script.js`.
- `stats-script.js` wymaga `window.StatsInfrastructureRanking`, używa aliasu
  `INFRA_RANKING` i deleguje
  `INFRA_RANKING.init(statsData.rivers_ranking, statsData.roads_ranking)`.
- `stats-script.js`: **2463 → 2400 linii**.
- `stats-infrastructure-ranking.js`: **89 linii**.
- Test kontraktowy statystyk: **51 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **137 passed**.
- Stabilna regresja: **821 passed, 8 skipped, 3 warnings**.

**Etap 14 — oś czasu protokołów `StatsTimeline` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 50 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-timeline.js` jako
  `window.StatsTimeline = Object.freeze({...})`.
- Moduł przejął render osi czasu protokołów: daty, listę właścicieli, linki do
  protokołów i komunikat „kliknij, aby rozwinąć”.
- `stats.html` ładuje `js/stats-timeline.js` po
  `js/stats-infrastructure-ranking.js`, przed `stats-script.js`.
- `stats-script.js` wymaga `window.StatsTimeline`, używa aliasu `TIMELINE` i
  przekazuje do `StatsTabs` callback `TIMELINE.render(statsData?.protocols_per_day)`.
- `stats-script.js`: **2400 → 2368 linii**.
- `stats-timeline.js`: **50 linii**.
- Test kontraktowy statystyk: **55 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **141 passed**.
- Stabilna regresja: **825 passed, 8 skipped, 3 warnings**.

**Etap 15 — większe wydzielenie demografii `StatsDemographics` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 54 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-demographics.js` jako
  `window.StatsDemographics = Object.freeze({...})`.
- Moduł przejął normalizację danych demograficznych, główny wykres populacji,
  metryki wzrostu, oś wydarzeń, karty dekad/lat, analizę porównawczą, przełącznik
  źródła danych oraz modal porównania okresów.
- `StatsDemographics` dostaje przez `init` zależności `charts`, `showToast` i
  `getStatsData`, więc nadal współdzieli rejestr wykresów z orkiestratorem.
- `stats.html` ładuje `js/stats-demographics.js` po `js/stats-timeline.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsDemographics`, używa aliasu `DEMOGRAPHICS`
  i deleguje render/przełącznik/porównania do modułu.
- `stats-script.js`: **2368 → 1648 linii**.
- `stats-demographics.js`: **407 linii**.
- Test kontraktowy statystyk: **59 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **145 passed**.
- Stabilna regresja: **829 passed, 8 skipped, 3 warnings**.

**Etap 16 — większe wydzielenie genealogii `StatsGenealogy` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 58 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-genealogy.js` jako
  `window.StatsGenealogy = Object.freeze({...})`.
- Moduł przejął kafle genealogiczne, ranking nazwisk, główny wykres serii
  urodzenia/zgony/śluby z przełącznikiem oraz dodatkowe wykresy: śmiertelność
  niemowląt, długość życia, rozkład wieku zgonu i strukturę rodzin.
- `StatsGenealogy` dostaje przez `init` zależności `charts` i `getStatsData`, więc
  współdzieli rejestr wykresów z orkiestratorem.
- `stats.html` ładuje `js/stats-genealogy.js` po `js/stats-demographics.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsGenealogy`, używa aliasu `GENEALOGY`
  i deleguje `GENEALOGY.render(statsData)`.
- `stats-script.js`: **1648 → 1274 linii**.
- `stats-genealogy.js`: **229 linii**.
- Test kontraktowy statystyk: **63 passed**.
- Kontrakty publicznych modułów właścicieli + admin frontend: **149 passed**.
- Stabilna regresja: **833 passed, 8 skipped, 3 warnings**.

**Etap 17 — raporty, eksport, druk i share `StatsReports` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 62 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-reports.js` jako
  `window.StatsReports = Object.freeze({...})`.
- Moduł przejął eksport wykresów PNG, eksport do Excel przez `XLSX`, modal
  drukowania, generowanie HTML raportu i modal udostępniania z `QRCode`.
- `StatsReports` dostaje przez `init` zależności `charts`, `getStatsData` i
  `showToast`.
- `stats.html` ładuje `js/stats-reports.js` po `js/stats-genealogy.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsReports`, używa aliasu `REPORTS` i
  przekazuje funkcje raportowe do `StatsActions`.
- `stats-script.js`: **1274 → 487 linii**.
- `stats-reports.js`: **836 linii**.
- Test kontraktowy statystyk: **67 passed**.
- Kontrakty publicznych modułów właścicieli: **92 passed**.

**Etap 18 — kalendarz aktywności i insighty `StatsActivityInsights` (zrobione):**

- Rozszerzono kontrakt `test_stats_public_modules_contract.py` i potwierdzono RED:
  **5 failed, 66 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-activity-insights.js` jako
  `window.StatsActivityInsights = Object.freeze({...})`.
- Moduł przejął heatmapę aktywności spisowej (`activity-calendar-container`,
  `calendar-tooltip`) oraz mini wnioski: budynki, kapliczki, największy właściciel,
  trend własności i koncentrację Top 10.
- `stats.html` ładuje `js/stats-activity-insights.js` po `js/stats-reports.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga `window.StatsActivityInsights`, używa aliasu
  `ACTIVITY_INSIGHTS` i deleguje `renderCalendar(...)` oraz `loadInsights(...)`.
- `stats-script.js`: **487 → 371 linii**.
- `stats-activity-insights.js`: **140 linii**.
- Test kontraktowy statystyk: **71 passed**.
- Kontrakty publicznych modułów właścicieli: **96 passed**.

**Etap 19 — duże odchudzenie orkiestratora trzema modułami (zrobione):**

- Uruchomiono agentów audytu i kontraktów dla większego zakresu zmian.
- Rozszerzono kontrakt `test_stats_public_modules_contract.py` od razu o 3 moduły i
  potwierdzono RED: **13 failed, 70 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-core-charts.js` jako
  `window.StatsCoreCharts = Object.freeze({...})`; moduł przejął konfigurację
  `Chart.defaults.font.family`, wykres kategorii `pieChart` i wykres Top 10
  właścicieli `barChart`.
- Dodano `static/wlasciciele/js/stats-top-selectors.js` jako
  `window.StatsTopSelectors = Object.freeze({...})`; moduł przejął selektory TOP 10
  właścicieli, działek, rzek i dróg używane przez akcje mapy.
- Dodano `static/wlasciciele/js/stats-notifications-keyboard.js` jako
  `window.StatsNotificationsKeyboard = Object.freeze({...})`; moduł przejął toasty i
  skróty klawiaturowe Ctrl+F/D/Escape.
- `stats.html` ładuje nowe moduły po `js/stats-activity-insights.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga nowych namespace, używa aliasów `CORE_CHARTS`,
  `TOP_SELECTORS`, `NOTIFICATIONS_KEYBOARD` i deleguje całą przeniesioną logikę.
- `stats-script.js`: **371 → 204 linie**.
- `stats-core-charts.js`: **92 linie**.
- `stats-top-selectors.js`: **78 linii**.
- `stats-notifications-keyboard.js`: **74 linie**.
- Test kontraktowy statystyk: **83 passed**.
- Kontrakty publicznych modułów właścicieli: **108 passed**.

**Etap 20 — `StatsApp` jako orkiestrator, `stats-script.js` jako bootstrap (zrobione):**

- Uruchomiono agentów audytu dla kontraktu `StatsApp` i zależności modułów.
- Rozszerzono kontrakt `test_stats_public_modules_contract.py` o
  `static/wlasciciele/js/stats-app.js` oraz minimalny bootstrap `stats-script.js` i
  potwierdzono RED: **25 failed, 60 passed** przed implementacją.
- Dodano `static/wlasciciele/js/stats-app.js` jako
  `window.StatsApp = Object.freeze({ init })`.
- `StatsApp` przejął walidację namespace, aliasy modułów, stan `statsData`/`charts`,
  inicjalizację UI, ładowanie danych i kolejność renderowania sekcji.
- `stats.html` ładuje `js/stats-app.js` po `js/stats-notifications-keyboard.js`, przed
  `stats-script.js`.
- `stats-script.js` wymaga już tylko `window.StatsApp` i na `DOMContentLoaded`
  wywołuje `window.StatsApp.init()`.
- `stats-script.js`: **204 → 16 linii**.
- `stats-app.js`: **182 linie**.
- Test kontraktowy statystyk: **85 passed**.
- Kontrakty publicznych modułów właścicieli: **110 passed**.

**Etap 21 — rozbicie raportów: Excel, druk/template, share + fasada (zrobione):**

- Uruchomiono agentów audytu dla podziału `stats-reports.js`.
- Rozszerzono kontrakt `test_stats_public_modules_contract.py` o 3 moduły raportowe
  i fasadę `StatsReports`; potwierdzono RED: **9 failed, 83 passed** przed
  implementacją.
- Dodano `static/wlasciciele/js/stats-excel-export.js` jako
  `window.StatsExcelExport = Object.freeze({...})`; moduł przejął eksport wykresów
  PNG i eksport danych przez `XLSX`.
- Dodano `static/wlasciciele/js/stats-print-report.js` jako
  `window.StatsPrintReport = Object.freeze({...})`; moduł przejął modal druku,
  checkboxy sekcji, generowanie HTML raportu i `window.open(...).print()`.
- Dodano `static/wlasciciele/js/stats-share-report.js` jako
  `window.StatsShareReport = Object.freeze({...})`; moduł przejął modal share,
  QR code i kopiowanie linku.
- `stats-reports.js` jest teraz cienką fasadą delegującą do modułów Excel/Print/Share
  i zachowuje dotychczasowe publiczne API dla `StatsApp`/`StatsActions`.
- `stats.html` ładuje nowe moduły po `js/stats-genealogy.js`, przed
  `js/stats-reports.js`.
- `stats-reports.js`: **837 → 72 linie**.
- `stats-excel-export.js`: **134 linie**.
- `stats-print-report.js`: **676 linii**.
- `stats-share-report.js`: **61 linii**.
- Test kontraktowy statystyk: **92 passed**.
- Kontrakty publicznych modułów właścicieli: **117 passed**.

**Kolejność dalsza:** P2.8 uznać za praktycznie domknięte. Nie rozbijać dalej małych
modułów; ewentualnie osobny cleanup dużego template'u w `StatsPrintReport` albo
przejście do audytu dużego JS mapy.

### 3.4 Refaktoryzacja dużego JS mapy `static/mapa`

**Etap 1 — helpery, stałe i kontrola warstw `map-v2/*` (zrobione):**

- Zrobiono audyt rozmiarów JS mapy: `map-script.js` **1520 linii**, `panels.js`
  **1004 linie**, `historical_points.js` **208 linii**.
- Uruchomiono agentów audytu dla `map-script.js`, `panels.js`, `mapa.html` i
  `test_mapa_frontend_contract.py`.
- Rozszerzono kontrakt `test_mapa_frontend_contract.py` i potwierdzono RED:
  **3 failed, 17 passed** przed implementacją.
- Dodano moduły `static/mapa/map-v2/*`:
  - `constants.js` → `window.MapV2Constants`,
  - `utils.js` → `window.MapV2Utils`,
  - `geometry.js` → `window.MapV2Geometry`,
  - `ownership.js` → `window.MapV2Ownership`,
  - `layer-controls.js` → `window.MapV2LayerControls`.
- `mapa.html` ładuje moduły `map-v2/*` po `panels.js`, przed `map-script.js`.
- `map-script.js` używa modułów przez aliasy i zachowuje wrappery kontraktowe w
  publicznym `window.MapV2`, szczególnie `setMapLayerVisibility`,
  `setPointsExclusion`, `addGeojsonSource`, `addGeojsonLayer`.
- Nie zmieniono kolejności `historical_points.js` — nadal ładuje się po
  `map-script.js`.
- `map-script.js`: **1520 → 1376 linii**.
- Test kontraktu mapy: **20 passed**.
- Kontrakty mapy + publicznych modułów właścicieli/statystyk: **137 passed**.

**Kolejność dalsza:** następny duży, ale kontrolowany krok to wydzielenie definicji
źródeł/warstw MapLibre z `renderMapDataV2()` do `map-v2/layers.js`; highlight/focus
manager zostawić na kolejny etap, bo jest bardziej ryzykowny.

## 4. FunkcjonalnoĹ›ci dĹ‚ugoterminowe

### 4.1 Wiele miejscowoĹ›ci w jednej instancji

**Status:** Ĺ›wiadomie odĹ‚oĹĽone (ADR-001).

WymagaĹ‚oby:

- Globalnego ID space z prefixem miejscowoĹ›ci.
- Wielu kalibracji map (zoom do regionu).
- WspĂłlnego UI do wyboru miejscowoĹ›ci na jednej mapie.
- Refactoru modelu danych.

**Praktyczna alternatywa:** osobne instancje na rĂłĹĽnych portach.

### 4.2 PeĹ‚ny system uĹĽytkownikĂłw i rĂłl

**Status:** Ĺ›wiadomie odĹ‚oĹĽone.

Aktualnie: jeden globalny admin. W przyszĹ‚oĹ›ci:

- Tabela `users` (id, username, password_hash, role).
- Role: `viewer`, `editor`, `admin`, `superadmin`.
- Per-user uprawnienia do sekcji.

### 4.3 DuĹĽy CRUD punktĂłw historycznych w adminie

**Status:** odĹ‚oĹĽone. Aktualnie edycja tylko w launcherze
(`add_edit_location_dialog.py`).

Gdy punktĂłw bÄ™dzie > 20: potrzebny grid + filtry + drag&drop w adminie.

### 4.4 WielojÄ™zycznoĹ›Ä‡ UI (i18n)

**Status:** Ĺ›wiadomie odĹ‚oĹĽone. Projekt polskojÄ™zyczny.

JeĹ›li potrzebne: `gettext` + pliki `.po` + `babel`.

### 4.5 Integracja z zewnÄ™trznymi systemami

- **Archiwum PaĹ„stwowe online** - automatyczny import skanĂłw protokoĹ‚Ăłw.
- **Geoportal** - eksport dziaĹ‚ek jako GeoJSON do geoportalu.gov.pl.
- **Gedcom** - import/eksport genealogii w formacie Gedcom.

## 5. Decyzje architektoniczne (recap)

| # | Decyzja | Status |
|---|---------|--------|
| ADR-001 | Jedna miejscowoĹ›Ä‡ = jedna instancja | âś… PrzyjÄ™te |
| ADR-002 | Brak bundlerĂłw JS | âś… PrzyjÄ™te |
| ADR-003 | TDD | âś… PrzyjÄ™te |
| ADR-004 | Logika poza UI | âś… PrzyjÄ™te |
| ADR-005 | ModuĹ‚y JS zamiast monolitu admin.js | đź”„ W toku |

PeĹ‚ne ADRs: [ARCHITECTURE.md Â§ Decyzje](ARCHITECTURE.md#4-decyzje-architektoniczne-adrs).

## 6. Metryki sukcesu

Projekt jest "gotowy" gdy:

- [ ] 100% endpointĂłw pokrytych testami integracji.
- [ ] Launcher uruchamia peĹ‚en stack (backend + frontend) bez rÄ™cznej interwencji.
- [x] PostgreSQL kreator dziaĹ‚a end-to-end (z mockowanym PG - 8 testĂłw E2E
      auto-skip bez prawdziwego PG; logika wizarda pokryta 27 testami unit
      + 21 testami kontraktu UI).
- [ ] Dokumentacja `docs/` kompletna (8 plikĂłw).
- [ ] CI/CD (GitHub Actions) zielone.
- [ ] v1.0.0 oznaczone tagiem.

## 7. Timeline (orientacyjny)

| Kiedy | Co |
|-------|----|
| Q2 2026 | P5 (dokumentacja), P5.1 (release v1.0.0) |
| Q3 2026 | P2 (PostgreSQL kreator), P2.5 Etap 2 (objects.js), P2.5 Etap 3 (owners.js + demography.js) |
| Q4 2026 | Security hardening (rate-limit, 2FA), Audit log |
| 2027+ | WiÄ™cej miejscowoĹ›ci, wielojÄ™zycznoĹ›Ä‡, integracje |

To sÄ… **orientacyjne** ramy - realne tempo zaleĹĽy od dostÄ™pnoĹ›ci czasu.

## 8. Zobacz teĹĽ

- [TODO.md](../TODO.md) - szczegĂłĹ‚owy plan prac (zamkniÄ™te i otwarte)
- [ARCHITECTURE.md](ARCHITECTURE.md) - architektura, ADRs
- [SECURITY.md](SECURITY.md) - bezpieczeĹ„stwo (P6)
- [LOCATIONS.md](LOCATIONS.md) - model miejscowoĹ›ci
