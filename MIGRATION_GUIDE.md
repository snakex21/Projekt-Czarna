# Przewodnik Migracji do Systemu Multi-Projekt

## Szybki Start

### 1. Inicjalizacja (wykonaj raz)

```bash
cd backend
python init_projects_table.py
```

To utworzy:
- Tabelę `projects` w bazie danych
- Strukturę folderów `projects/czarna/`
- Przeniesie istniejące dane z `backup/` do `projects/czarna/data/`
- Ustawi "Czarna" jako domyślny aktywny projekt

### 2. Uruchom Serwer

```bash
cd backend
python app.py
```

Serwer automatycznie wczyta projekt "Czarna" jako aktywny.

### 3. Sprawdź API

Otwórz w przeglądarce lub curl:
```bash
curl http://localhost:5000/api/project-info
```

Powinieneś zobaczyć:
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

## Dodawanie Nowego Projektu

### Opcja A: Przez Launcher (Łatwiejsze)

1. Uruchom: `python launcher/launcher_app.py`
2. W prawym górnym rogu widoczny jest aktywny projekt
3. Kliknij przycisk ⚙️ obok nazwy projektu
4. W oknie "Zarządzanie Projektami" kliknij "➕ Nowy Projekt"
5. Wypełnij formularz:
   ```
   Kod projektu: borowa
   Nazwa: Borowa
   Pełna nazwa: Gmina Borowa
   Kontekst czasowy: XX wiek
   Rok źródłowy: 1920
   Region: Powiat Mielecki
   Województwo: Podkarpackie
   ```
6. Kliknij "💾 Zapisz"
7. W liście projektów wybierz "borowa"
8. Kliknij "✔️ Ustaw jako Aktywny"
9. Zrestartuj serwer backend

### Opcja B: Przez API

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
    "wojewodztwo": "Podkarpackie"
  }'
```

Następnie przełącz:
```bash
curl -X POST http://localhost:5000/api/projects/switch/borowa
```

I zrestartuj serwer.

## Aktualizacja Stron HTML

Dodaj do każdej strony HTML przed zamknięciem `</body>`:

```html
<script src="/static/js/project-loader.js"></script>
```

### Przykład: mapa.html

**Przed:**
```html
<h1>Mapa Katastralna Czarna z XIX w.</h1>
```

**Po:**
```html
<h1 class="app-title">Mapa Katastralna Czarna z XIX w.</h1>
<script src="/static/js/project-loader.js"></script>
```

Script automatycznie zamieni "Czarna" i "XIX w." na dane z aktywnego projektu.

### Wykorzystanie Atrybutów

Dla większej kontroli użyj atrybutów:

```html
<h1 data-project-field="pelna_nazwa"></h1>
<p>Kontekst: <span data-project-field="kontekst_czasowy"></span></p>
<p>Region: <span data-project-field="region"></span></p>
```

## Przełączanie Projektów

### 1. Przez Launcher
- Otwórz menedżer projektów (⚙️)
- Wybierz projekt
- Kliknij "✔️ Ustaw jako Aktywny"
- Zrestartuj serwer

### 2. Przez API
```bash
# Przełącz na "borowa"
curl -X POST http://localhost:5000/api/projects/switch/borowa

# Zrestartuj serwer
# Sprawdź aktywny projekt
curl http://localhost:5000/api/project-info
```

### 3. Ręcznie
```bash
echo "borowa" > backend/.active_project
# Zrestartuj serwer
```

## Struktura Plików Po Migracji

```
projekt-czarna/
├── backend/
│   ├── .active_project          ← "czarna" lub inny kod
│   ├── app.py                   ← Rozbudowany
│   └── init_projects_table.py   ← Nowy skrypt
├── projects/                    ← Nowy folder
│   ├── czarna/
│   │   ├── data/
│   │   │   ├── database.json
│   │   │   ├── demografia.json
│   │   │   ├── genealogia.json
│   │   │   └── parcels.json
│   │   ├── geojson/
│   │   └── backups/
│   └── borowa/                  ← Nowy projekt
│       ├── data/
│       ├── geojson/
│       └── backups/
├── static/
│   └── js/
│       └── project-loader.js    ← Nowy moduł
└── backup/                      ← Stare dane (backup)
```

## Testowanie

### Test 1: Sprawdź Tabelę
```sql
psql -U postgres -d mapa_czarna_db
SELECT * FROM projects;
```

### Test 2: Sprawdź API
```bash
# Lista projektów
curl http://localhost:5000/api/projects

# Aktywny projekt
curl http://localhost:5000/api/project-info
```

### Test 3: Frontend
1. Otwórz http://localhost:5000/mapa/mapa.html
2. Otwórz konsolę przeglądarki (F12)
3. Sprawdź logi:
   ```
   🔄 Ładowanie informacji o projekcie...
   ✅ Załadowano informacje o projekcie: Czarna
   ✅ Projekt załadowany: Czarna
   ```
4. Sprawdź czy tytuł strony i nagłówki zawierają nazwę projektu

## Co Dalej?

1. **Dodaj więcej projektów** - przez launcher lub API
2. **Dostosuj strony HTML** - dodaj `project-loader.js`
3. **Import danych** - dla nowych projektów skopiuj pliki do `projects/{kod}/data/`
4. **Testuj przełączanie** - sprawdź izolację danych między projektami

## Problemy?

Zobacz: `MULTI_PROJECT_SETUP.md` sekcja "Rozwiązywanie Problemów"
