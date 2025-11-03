# System Multi-Projekt - Podsumowanie Zmian

## Nowe Pliki

### Backend
1. **`backend/init_projects_table.py`** - Skrypt inicjalizacji systemu multi-projekt
   - Tworzy tabelę `projects`
   - Migruje dane Czarnej do nowej struktury
   - Tworzy folder `projects/czarna/`

2. **`backend/.active_project`** - Plik konfiguracyjny (tworzony automatycznie)
   - Przechowuje kod aktywnego projektu
   - Format: jedna linia z kodem (np. "czarna")

### Frontend
3. **`static/js/project-loader.js`** - Moduł ładowania metadanych projektu
   - Automatyczne pobieranie z API `/api/project-info`
   - Zamiana zhardkodowanych referencji do "Czarna"
   - Funkcje: `loadProjectInfo()`, `updateProjectElements()`, `formatProjectText()`

### Dokumentacja
4. **`MULTI_PROJECT_SETUP.md`** - Kompletna dokumentacja techniczna
5. **`MIGRATION_GUIDE.md`** - Przewodnik migracji krok po kroku
6. **`CHANGES_SUMMARY.md`** - Ten plik

## Zmodyfikowane Pliki

### Backend

#### `backend/app.py`
**Dodane:**
- Sekcja "ZARZĄDZANIE PROJEKTAMI - MULTI-PROJECT SUPPORT" (linie ~102-183)
  - `ACTIVE_PROJECT` - globalna zmienna z aktywnym projektem
  - `load_active_project()` - odczyt z pliku `.active_project`
  - `save_active_project()` - zapis aktywnego projektu
  - `get_project_info()` - pobieranie metadanych z bazy
  - `initialize_active_project()` - inicjalizacja przy starcie

- Wywołanie `initialize_active_project()` po `load_system_config()`

- Nowe endpointy API (linie ~1023-1293):
  - `GET /api/project-info` - Info o aktywnym projekcie
  - `GET /api/projects` - Lista wszystkich projektów
  - `GET /api/projects/<id>` - Szczegóły projektu
  - `POST /api/projects` - Tworzenie projektu
  - `PUT /api/projects/<id>` - Aktualizacja projektu
  - `DELETE /api/projects/<id>` - Usunięcie projektu
  - `POST /api/projects/switch/<code>` - Przełączenie projektu

- Route dla plików statycznych:
  - `GET /static/<filename>` - Serwowanie plików z folderu `static/`

### Launcher

#### `launcher/launcher_app.py`

**Dodane w klasie AppLauncher:**

1. **W metodzie `create_widgets()`** (linie ~444-470):
   - Sekcja wyboru projektu w nagłówku
   - Label z nazwą aktywnego projektu
   - Przycisk ⚙️ otwierający menedżer projektów

2. **Nowe metody** (linie ~1084-1102):
   - `open_project_manager()` - Otwiera okno zarządzania
   - `refresh_active_project_display()` - Odświeża wyświetlanie

**Nowe klasy dialogowe** (linie ~2676-3136):

3. **`ProjectManager`** - Okno zarządzania projektami
   - `create_widgets()` - UI z listą projektów
   - `load_projects()` - Pobiera projekty z bazy
   - `set_active_project()` - Ustawia aktywny projekt
   - `create_new_project()` - Otwiera edytor dla nowego projektu
   - `edit_project()` - Edycja istniejącego
   - `delete_project()` - Usuwanie projektu

4. **`ProjectEditor`** - Okno edycji/tworzenia projektu
   - Formularz z wszystkimi metadanymi
   - Scroll dla długich formularzy
   - Walidacja danych
   - Zapis do bazy
   - Automatyczne tworzenie struktury folderów

## Nowa Struktura Bazy Danych

### Tabela `projects`

```sql
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    short_code VARCHAR(50) UNIQUE NOT NULL,
    nazwa VARCHAR(200) NOT NULL,
    pelna_nazwa VARCHAR(500),
    opis TEXT,
    kontekst_czasowy VARCHAR(200),
    rok_zrodlowy INTEGER,
    okres_danych VARCHAR(100),
    region VARCHAR(200),
    wojewodztwo VARCHAR(100),
    jezyk_zrodel VARCHAR(100),
    uwagi TEXT,
    status VARCHAR(50) DEFAULT 'aktywny',
    data_utworzenia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ostatnia_modyfikacja TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_projects_short_code ON projects(short_code);
CREATE INDEX idx_projects_status ON projects(status);
```

### Przykładowy Rekord (Czarna)

```sql
INSERT INTO projects VALUES (
    1,
    'czarna',
    'Czarna',
    'Gmina Czarna - System Mapy Katastralnej',
    'Interaktywna mapa katastralina gminy Czarna z XIX wieku...',
    'XIX wiek',
    1880,
    '1850-1900',
    'Powiat Mielecki',
    'Podkarpackie',
    'Polski',
    'Dane pochodzą z archiwum państwowego w Mielcu...',
    'aktywny',
    NOW(),
    NOW()
);
```

## Nowa Struktura Folderów

```
projekty/
└── czarna/
    ├── data/
    │   ├── database.json      (owner_data_to_import.json)
    │   ├── demografia.json
    │   ├── genealogia.json
    │   └── parcels.json       (parcels_data.json)
    ├── geojson/
    └── backups/
```

Każdy nowy projekt otrzymuje identyczną strukturę.

## API - Przykłady Użycia

### Pobierz info o aktywnym projekcie
```bash
curl http://localhost:5000/api/project-info
```

### Lista wszystkich projektów
```bash
curl http://localhost:5000/api/projects
```

### Utwórz nowy projekt
```bash
curl -X POST http://localhost:5000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "short_code": "borowa",
    "nazwa": "Borowa",
    "kontekst_czasowy": "XX wiek",
    "rok_zrodlowy": 1920
  }'
```

### Przełącz projekt
```bash
curl -X POST http://localhost:5000/api/projects/switch/borowa
```

### Aktualizuj projekt
```bash
curl -X PUT http://localhost:5000/api/projects/1 \
  -H "Content-Type: application/json" \
  -d '{"nazwa": "Czarna (zaktualizowana)"}'
```

## Frontend - Integracja

### Krok 1: Dodaj skrypt do HTML

Przed `</body>`:
```html
<script src="/static/js/project-loader.js"></script>
```

### Krok 2: Użyj atrybutów dla dynamicznych elementów

```html
<!-- Automatyczne podstawienie -->
<h1 class="app-title">Mapa Katastralna Czarna z XIX w.</h1>

<!-- Lub z atrybutami -->
<h1 data-project-field="nazwa"></h1>
<p data-project-field="opis"></p>
```

### Krok 3: Nasłuchuj na zdarzenie załadowania

```javascript
document.addEventListener('projectLoaded', (event) => {
    const project = event.detail;
    console.log('Projekt:', project.nazwa);
    // Dostosuj UI
});
```

## Testy

### 1. Inicjalizacja
```bash
cd backend
python init_projects_table.py
# Sprawdź: projects/czarna/ został utworzony
```

### 2. API
```bash
curl http://localhost:5000/api/projects
curl http://localhost:5000/api/project-info
```

### 3. Launcher
```bash
python launcher/launcher_app.py
# Sprawdź: Widoczna nazwa projektu w nagłówku
# Kliknij ⚙️ - powinno otworzyć menedżer
```

### 4. Frontend
```bash
# Uruchom serwer
python backend/app.py

# Otwórz w przeglądarce
http://localhost:5000/mapa/mapa.html

# W konsoli (F12) sprawdź:
# "✅ Projekt załadowany: Czarna"
```

## Backward Compatibility

✅ **System działa z istniejącymi danymi bez zmian**
- Jeśli brak tabeli `projects` - używa domyślnych wartości
- Jeśli brak pliku `.active_project` - domyślnie "czarna"
- Frontend z fallbackiem na "Czarna" jeśli API nie odpowiada
- Wszystkie istniejące funkcje bez modyfikacji

## Breaking Changes

**BRAK** - System jest w pełni kompatybilny wstecz.

## Co Działa Po Migracji

✅ Wszystkie istniejące funkcje systemu
✅ API właścicieli, działek, genealogii
✅ Mapa, statystyki, admin panel
✅ Edytory (właściciele, działki, genealogia)
✅ Backupy
✅ Testy

## Nowe Możliwości

✅ Zarządzanie wieloma projektami
✅ Dynamiczne przełączanie między projektami
✅ Automatyczna aktualizacja metadanych w UI
✅ API do zarządzania projektami
✅ GUI launcher z menedżerem projektów
✅ Izolacja danych między projektami

## Wsparcie

Dokumentacja:
- `MULTI_PROJECT_SETUP.md` - Pełna dokumentacja techniczna
- `MIGRATION_GUIDE.md` - Przewodnik migracji krok po kroku
- `CHANGES_SUMMARY.md` - Podsumowanie zmian (ten plik)

## Autorzy

System multi-projekt zaprojektowany i zaimplementowany zgodnie z wymaganiami ticketu.

## Wersja

**v1.0** - Pierwsza wersja systemu multi-projekt
- Data: 2024
- Status: ✅ Gotowy do użycia
