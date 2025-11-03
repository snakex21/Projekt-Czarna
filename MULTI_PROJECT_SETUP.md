# System Multi-Projekt - Dokumentacja

## Przegląd

System został rozbudowany o obsługę wielu instancji/projektów miejscowości. Każdy projekt ma własne dane, metadane i może być niezależnie zarządzany.

## Architektura

### 1. Backend (Flask)

#### Tabela `projects`
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
```

#### Nowe Endpointy API

- `GET /api/project-info` - Informacje o aktualnie aktywnym projekcie
- `GET /api/projects` - Lista wszystkich projektów
- `GET /api/projects/{id}` - Szczegóły projektu
- `POST /api/projects` - Tworzenie nowego projektu
- `PUT /api/projects/{id}` - Aktualizacja metadanych projektu
- `DELETE /api/projects/{id}` - Usunięcie projektu
- `POST /api/projects/switch/{code}` - Przełączenie aktywnego projektu

### 2. Struktura Folderów

```
projekt-czarna/
├── backend/
│   ├── app.py                    # Rozbudowany o zarządzanie projektami
│   ├── init_projects_table.py    # Skrypt inicjalizacji
│   └── .active_project           # Plik z kodem aktywnego projektu
├── projects/
│   ├── czarna/
│   │   ├── data/
│   │   │   ├── database.json
│   │   │   ├── demografia.json
│   │   │   ├── genealogia.json
│   │   │   └── parcels.json
│   │   ├── geojson/
│   │   └── backups/
│   └── borowa/                   # Przykład kolejnego projektu
│       ├── data/
│       ├── geojson/
│       └── backups/
├── static/
│   └── js/
│       └── project-loader.js     # Moduł ładowania info o projekcie
└── launcher/
    └── launcher_app.py           # Rozbudowany o zarządzanie projektami
```

### 3. Frontend - Dynamiczne Ładowanie

#### Moduł `project-loader.js`

Automatycznie ładuje informacje o aktywnym projekcie i aktualizuje elementy DOM:

```javascript
// Automatyczne ładowanie przy starcie strony
await loadProjectInfo();

// Aktualizacja elementów z atrybutami data-project-field
<h1 data-project-field="nazwa"></h1>

// Formatowanie tekstu z placeholderami
formatProjectText("Mapa {nazwa} z {kontekst_czasowy}");
```

#### Aktualizacja HTML

Dodaj do każdej strony przed zamknięciem `</body>`:

```html
<script src="/static/js/project-loader.js"></script>
```

Użyj atrybutów dla dynamicznych elementów:

```html
<h1 data-project-field="nazwa"></h1>
<p data-project-field="opis"></p>
<span data-project-field="kontekst_czasowy"></span>
```

### 4. Launcher - Zarządzanie Projektami

#### Funkcje

- **Wybór projektu** - Dropdown w nagłówku launchera
- **Zarządzanie projektami** - Przycisk ⚙️ otwiera menedżer
- **Tworzenie projektów** - Formularz z metadanymi
- **Edycja projektów** - Aktualizacja istniejących projektów
- **Przełączanie** - Zmiana aktywnego projektu

#### Workflow

1. Użytkownik otwiera launcher
2. Widzi aktualnie aktywny projekt w nagłówku
3. Klika przycisk ⚙️ aby otworzyć menedżer projektów
4. Może utworzyć nowy projekt lub przełączyć się na istniejący
5. Po przełączeniu projektu - restart serwera backend

## Instalacja i Migracja

### Krok 1: Inicjalizacja Tabeli Projects

```bash
cd backend
python init_projects_table.py
```

Ten skrypt:
- Tworzy tabelę `projects`
- Tworzy strukturę folderów `projects/czarna/`
- Kopiuje istniejące dane do nowej struktury
- Dodaje wpis dla projektu "Czarna"
- Ustawia "Czarna" jako aktywny projekt

### Krok 2: Restart Serwera

```bash
python app.py
```

Serwer automatycznie:
- Wczyta aktywny projekt z pliku `.active_project`
- Załaduje konfigurację projektu
- Będzie serwował dane z właściwego projektu

### Krok 3: Sprawdzenie API

```bash
curl http://localhost:5000/api/project-info
```

Powinno zwrócić:
```json
{
  "status": "success",
  "project": {
    "short_code": "czarna",
    "nazwa": "Czarna",
    "pelna_nazwa": "Gmina Czarna - System Mapy Katastralnej",
    "kontekst_czasowy": "XIX wiek",
    "rok_zrodlowy": 1880,
    ...
  }
}
```

## Tworzenie Nowego Projektu

### Przez Launcher (Zalecane)

1. Uruchom launcher: `python launcher/launcher_app.py`
2. Kliknij przycisk ⚙️ obok nazwy projektu
3. W oknie zarządzania kliknij "➕ Nowy Projekt"
4. Wypełnij formularz:
   - Kod projektu (np. "borowa") - tylko litery i cyfry
   - Nazwa (np. "Borowa")
   - Pełna nazwa
   - Kontekst czasowy (np. "XX wiek")
   - Region, województwo, etc.
5. Kliknij "💾 Zapisz"
6. Wybierz nowy projekt i kliknij "✔️ Ustaw jako Aktywny"
7. Zrestartuj serwer backend

### Przez API

```bash
curl -X POST http://localhost:5000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "short_code": "borowa",
    "nazwa": "Borowa",
    "pelna_nazwa": "Gmina Borowa",
    "kontekst_czasowy": "XX wiek",
    "rok_zrodlowy": 1920,
    "region": "Powiat Mielecki",
    "wojewodztwo": "Podkarpackie",
    "status": "aktywny"
  }'
```

## Przełączanie Między Projektami

### Przez Launcher

1. Otwórz menedżer projektów (przycisk ⚙️)
2. Wybierz projekt z listy
3. Kliknij "✔️ Ustaw jako Aktywny"
4. Zrestartuj serwer backend

### Przez API

```bash
curl -X POST http://localhost:5000/api/projects/switch/borowa
```

Następnie restart serwera.

## Izolacja Danych

**KRYTYCZNE ZASADY:**

1. Każdy projekt ma **własne foldery** w `projects/{kod}/`
2. Dane między projektami **NIE MIESZAJĄ SIĘ**
3. Wszystkie zapytania do bazy działają w kontekście aktywnego projektu
4. Backupy są **osobne dla każdego projektu**
5. GeoJSON i pliki danych są **izolowane per projekt**

## Backward Compatibility

System jest w pełni kompatybilny wstecz:

- Istniejące dane "Czarna" działają bez zmian
- Jeśli nie ma tabeli `projects`, system używa domyślnej konfiguracji
- Frontend z fallbackiem na "Czarna" jeśli API nie odpowiada
- Wszystkie istniejące funkcje pozostają bez zmian

## Testowanie

### Test 1: Import Istniejących Danych

```bash
cd backend
python init_projects_table.py
# Sprawdź: projects/czarna/data/ zawiera skopiowane pliki
```

### Test 2: Utworzenie Nowego Projektu

```bash
# Przez launcher lub API
# Sprawdź: projects/borowa/ została utworzona
```

### Test 3: Przełączanie

```bash
# Ustaw projekt "borowa" jako aktywny
curl -X POST http://localhost:5000/api/projects/switch/borowa
# Restart serwera
# Sprawdź: GET /api/project-info zwraca dane Borowej
```

### Test 4: Frontend

1. Otwórz http://localhost:5000/mapa/mapa.html
2. Sprawdź w konsoli: "✅ Projekt załadowany: Czarna"
3. Sprawdź tytuł strony i nagłówki - powinny zawierać nazwę projektu

## Rozwiązywanie Problemów

### Problem: Serwer nie startuje po migracji

**Rozwiązanie:**
```bash
# Sprawdź czy tabela projects istnieje
psql -U postgres -d mapa_czarna_db -c "SELECT * FROM projects;"

# Jeśli nie istnieje, uruchom ponownie:
python backend/init_projects_table.py
```

### Problem: Frontend pokazuje "Czarna" zamiast właściwego projektu

**Rozwiązanie:**
1. Sprawdź czy projekt-loader.js jest załadowany:
   ```html
   <script src="/static/js/project-loader.js"></script>
   ```
2. Sprawdź konsolę przeglądarki - powinien być log: "✅ Projekt załadowany: ..."
3. Sprawdź API: `curl http://localhost:5000/api/project-info`

### Problem: Nie można przełączyć projektu

**Rozwiązanie:**
1. Sprawdź plik `.active_project`:
   ```bash
   cat backend/.active_project
   ```
2. Upewnij się, że projekt istnieje w bazie:
   ```sql
   SELECT * FROM projects WHERE short_code = 'nazwa_projektu';
   ```
3. Zrestartuj serwer po przełączeniu

## Roadmap

### Wersja 1.0 (Aktualna)
- ✅ Tabela projects
- ✅ API zarządzania projektami
- ✅ Przełączanie projektów
- ✅ Launcher z menedżerem projektów
- ✅ Frontend project-loader.js

### Wersja 2.0 (Planowana)
- ⏳ Separate databases per project (zamiast shared DB)
- ⏳ Import/Export projektów
- ⏳ Szablon projektów
- ⏳ Multi-user support (różni użytkownicy = różne projekty)

## Kontakt i Wsparcie

W razie problemów sprawdź:
1. Logi serwera backend
2. Konsolę przeglądarki
3. Plik `.active_project` w folderze backend
4. Czy tabela `projects` istnieje w bazie danych
