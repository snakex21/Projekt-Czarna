# Testowanie

> Konwencje, struktura, jak uruchomić i pisać testy.

## 1. Statystyki

**Stan na czerwiec 2026:** stabilna regresja CI: **833 testów przechodzi + 8 skipped**
(PostgreSQL E2E auto-skip bez konfiguracji PG). Kilka pre-existing testów
środowiskowych/flaky jest pomijanych w CI do czasu osobnej naprawy.

Po P2.8 Etap 16 szybki kontrakt centrum analitycznego ma **63 passed**, a pakiet
kontraktów publicznych modułów właścicieli + admin frontend ma **149 passed**.

```text
backend/tests/unit/         ~250 testów  (logika, serwisy, utility, UI contract)
backend/tests/integration/  ~150 testów  (routery FastAPI + endpointy)
backend/tests/e2e/          ~70 testów   (Playwright - przeglądarka)
```

## 2. Jak uruchomić

### Cały pakiet

```bash
# Stabilny zestaw CI
python -m pytest backend/tests/ \
  --ignore=backend/tests/integration/test_add_edit_location_dialog_photos.py \
  --ignore=backend/tests/unit/test_add_edit_location_dialog_photos.py \
  --ignore=backend/tests/unit/test_db_helpers.py \
  --ignore=backend/tests/unit/test_diagnostics_service.py

# Szybko (unit + integration; może ujawnić znane flaky opisane wyżej)
python -m pytest backend/tests/unit/ backend/tests/integration/

# Verbose z listą wszystkich testów
python -m pytest backend/tests/ -v

# Z zatrzymaniem na pierwszym failu
python -m pytest backend/tests/ -x

# Z raportem coverage
python -m pytest backend/tests/ --cov=backend --cov-report=html
```

### Konkretny moduł

```bash
# Serwis diagnostyki
python -m pytest backend/tests/unit/test_diagnostics_service.py

# Kontrakt publicznego centrum analitycznego właścicieli
python -m pytest backend/tests/unit/test_stats_public_modules_contract.py -q --no-header

# Kontrakty publicznych modułów właścicieli + admin frontend
python -m pytest backend/tests/unit/test_stats_public_modules_contract.py \
  backend/tests/unit/test_public_owners_api_module_contract.py \
  backend/tests/unit/test_public_owners_utils_module_contract.py \
  backend/tests/unit/test_protocol_images_module_contract.py \
  backend/tests/unit/test_protocol_genealogy_tree_module_contract.py \
  backend/tests/unit/test_compare_public_modules_contract.py \
  backend/tests/integration/test_admin_frontend_contract.py -q --no-header

# Konkretna klasa
python -m pytest backend/tests/unit/test_auth_security.py::TestAssertSafeSecretKey

# Konkretny test
python -m pytest backend/tests/integration/test_admin_frontend_contract.py::test_diagnostics_module_registers_window_admin_diagnostics
```

### Testy E2E (wymaga serwera)

```bash
# Terminal 1: backend
python -m uvicorn backend.main:app --host 127.0.0.1 --port 5000

# Terminal 2: Playwright
python -m pytest backend/tests/e2e/ -v
```

## 3. Struktura katalogów

```text
backend/tests/
├── conftest.py              # root fixtures (DB env, http client)
├── unit/
│   ├── conftest.py          # SQLite test DB + import backend.main
│   ├── test_<service>.py    # testy serwisów i utility
│   ├── test_<feature>_contract.py  # testy kontraktu UI (regex na .py)
│   └── test_<router>.py     # czasem testy routerów przez import
├── integration/
│   ├── conftest.py          # FastAPI app + admin client fixtures
│   ├── test_<router>.py     # testy endpointów przez TestClient
│   └── test_admin_frontend_contract.py  # testy kontraktu HTML/JS/CSS
└── e2e/
    └── test_*.py            # Playwright (przeglądarka)
```

## 4. Konwencje TDD

### 4.1 Czerwony → Zielony → Refactor

Każdy nowy ficzer:

1. **Czerwony:** napisz test (lub kilka), uruchom `pytest`, potwierdź `FAILED`.
2. **Zielony:** napisz minimalną implementację, uruchom test, potwierdź `PASSED`.
3. **Regresja:** uruchom cały pakiet, upewnij się że nic nie złamałeś.
4. **Refactor:** jeśli brzydko, popraw. Testy są siatką bezpieczeństwa.

### 4.2 Nazewnictwo

- Plik: `test_<feature>_<aspect>.py` (np. `test_diagnostics_service.py`,
  `test_admin_frontend_contract.py`).
- Funkcja: `test_<what>_<expected_when_condition>` (np.
  `test_auth_status_warns_when_default_password`,
  `test_refresh_security_fetches_from_auth_status_endpoint`).
- Klasy: `Test<Feature>` lub `Test<Feature><Aspect>` (np. `TestAssertSafeSecretKey`,
  `TestListPointPhotos`).

### 4.3 Asercje

- **Preferuj jawne asercje z komunikatem:**

  ```python
  assert "diagnostics" in source, (
      "admin.js powinien obsługiwać case 'diagnostics' w loadSectionData"
  )
  ```

- **Wyjątki:**

  ```python
  with pytest.raises(ValueError) as exc_info:
      assert_safe_secret_key(is_production=True, secret_key="dev-secret-change-me")
  assert "SECRET_KEY" in str(exc_info.value)
  ```

- **Nie asercje boolean:** zamiast `assert result` → `assert result is True` lub
  `assert result == expected_value`.

### 4.4 Mocki

- **Czas, pliki, env:** `monkeypatch.setattr()` i `monkeypatch.setenv()`.
- **Tkinter w testach UI:** klasa `_FakeVar` (minimalistyczny StringVar) + proste
  atrybuty zamiast prawdziwych widgetów.
- **HTTP w testach integracji:** `TestClient(app)` z `fastapi.testclient`.
- **HTTP w testach UI launcherze:** `urllib.request` mockowany przez
  `monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)`.

### 4.5 Testy kontraktu UI

Testy UI nie wywołują kodu - weryfikują **źródło** (regex na string):

```python
def test_diagnostics_module_registers_window_admin_diagnostics():
    """js/diagnostics.js publikuje window.AdminDiagnostics jako Object.freeze."""
    assert ADMIN_DIAGNOSTICS_JS.exists(), "Brak pliku static/admin/js/diagnostics.js"
    source = ADMIN_DIAGNOSTICS_JS.read_text(encoding="utf-8")
    assert "window.AdminDiagnostics" in source
    assert "Object.freeze" in source
```

To tani sposób na wykrycie regresji bez podnoszenia przeglądarki.
Pełna weryfikacja: E2E z Playwright.

## 5. Fixtures (conftest.py)

### Root (`backend/tests/conftest.py`)

- **DB testowa:** `tempfile.mkdtemp(prefix="mapa_unit_db_")` + kopia `data/czarna.db`
  → env `DB_ENGINE=sqlite`, `DB_PATH=...`.
- **Czyszczenie:** `atexit.register(shutil.rmtree)`.

### Unit (`backend/tests/unit/conftest.py`)

- **Import `backend.main` po ustawieniu env** (DB musi być skonfigurowana
  przed importem).
- **`client`** fixture: `TestClient(app)`.

### Integration (`backend/tests/integration/conftest.py`)

- **`admin_client`** fixture: klient FastAPI zalogowany jako admin (cookie session).
- **`client`** fixture: klient bez logowania (do testów publicznych endpointów).
- **`monkeypatch`** dla `config.ADMIN_AUTH_ENABLED`, `config.SECRET_KEY`, itd.

## 6. Anti-patterns (do unikania)

### ❌ Hardcoded sleep

```python
# Źle - kruche, flaky
time.sleep(2)
assert server_ready()
```

Lepiej: polling, callback, lub test integracji z prawdziwym serwerem.

### ❌ Test zależny od kolejności

```python
# Źle - test A modyfikuje globalny stan, test B tego wymaga
def test_a():
    global_db["foo"] = 1
def test_b():
    assert global_db["foo"] == 1  # ❌
```

Lepiej: fixtures z `scope="function"` (default), lub jawne setup w każdym teście.

### ❌ Test bez asercji

```python
# Źle - nic nie sprawdza
def test_something():
    result = do_something()
    # brak asercji!
```

pytest zgłosi warning "no assertions". Zawsze asercja.

### ❌ Catch-all `except Exception`

```python
# Źle - łapie też nasze własne błędy w teście
try:
    do_something()
except Exception:
    pass
```

Lepiej: `pytest.raises(SpecificError)` lub pozwól wyjątkowi się propagować.

## 7. Przykład pełnego cyklu TDD

**Cel:** dodać `get_network_security_warnings()` w `backend/auth/security.py`.

### Krok 1: Test (czerwony)

```python
# backend/tests/unit/test_auth_security.py
def test_network_warnings_present_when_auth_disabled(monkeypatch):
    """ADMIN_AUTH_ENABLED=False → ostrzeżenie zwrócone."""
    monkeypatch.setattr(sec.config, "ADMIN_AUTH_ENABLED", False)
    warnings = sec.get_network_security_warnings()
    assert len(warnings) >= 1
    joined = " ".join(warnings).lower()
    assert "uwierzytelnian" in joined or "auth" in joined
```

`pytest backend/tests/unit/test_auth_security.py` → `ImportError: cannot import name 'get_network_security_warnings'`

### Krok 2: Implementacja (zielony)

```python
# backend/auth/security.py
def get_network_security_warnings() -> list:
    """Ostrzeżenia dla trybu sieciowego (Priorytet 6.7)."""
    warnings: list = []
    auth_enabled = getattr(config, "ADMIN_AUTH_ENABLED", False)
    if not auth_enabled:
        warnings.append(
            "🚨 Backend udostępniony w sieci BEZ uwierzytelniania admina. "
            "Każdy w sieci LAN może modyfikować dane przez /api/admin/*. "
            "Ustaw ADMIN_AUTH_ENABLED=1 i skonfiguruj hasło w backend/.env."
        )
    return warnings
```

`pytest backend/tests/unit/test_auth_security.py` → `1 passed`.

### Krok 3: Regresja (cały pakiet)

```bash
python -m pytest backend/tests/unit/ backend/tests/integration/
# 468 passed in 8.24s
```

### Krok 4: Refactor (opcjonalnie)

Popraw nazwę, komentarze, dodaj edge case. Testy są siatką.

## 8. Continuous Integration (planowane)

W przyszłości: GitHub Actions z `python -m pytest backend/tests/ -q`
jako required check przed merge.

## 9. Debugging

### Jedyny test

```bash
python -m pytest backend/tests/unit/test_auth_security.py::test_x -v
```

### W pdb

```bash
python -m pytest backend/tests/unit/test_auth_security.py --pdb
```

### Print w teście

```python
def test_x():
    result = do_something()
    print(f"DEBUG: result = {result!r}")  # widoczne z -s
    assert result == expected
```

```bash
python -m pytest ... -s
```

## 10. Zobacz też

- [ARCHITECTURE.md](ARCHITECTURE.md) - architektura
- [SECURITY.md](SECURITY.md) - testy bezpieczeństwa
- [TODO.md](../TODO.md) - status priorytetów
- [PROJECT_SKILL.md](../PROJECT_SKILL.md) - konwencje kodu
