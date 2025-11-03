# 📁 System Multi-Projekt - README

## 🎯 Cel

System został rozbudowany o możliwość obsługi wielu instancji/projektów miejscowości z dynamicznym przełączaniem i edycją metadanych. Działa jak Photoshop - **jeden kod, wiele projektów do wyboru**.

## ✨ Funkcje

- ✅ **Zarządzanie wieloma projektami** - Czarna, Borowa, inne gminy
- ✅ **Dynamiczne przełączanie** - Jeden serwer, wiele instancji danych
- ✅ **Edycja metadanych** - Nazwa, kontekst czasowy, region, etc.
- ✅ **GUI w launcherze** - Intuicyjna obsługa projektów
- ✅ **API REST** - Pełna kontrola przez HTTP
- ✅ **Automatyczna aktualizacja UI** - Frontend dostosowuje się do projektu
- ✅ **Izolacja danych** - Projekty się nie mieszają
- ✅ **Backward compatibility** - Stare dane działają bez zmian

## 🚀 Szybki Start (3 kroki)

### 1. Inicjalizacja

```bash
cd backend
python init_projects_table.py
```

To utworzy:
- Tabelę `projects` w bazie
- Folder `projects/czarna/` z migracją danych
- Wpis dla projektu "Czarna"

### 2. Uruchom Serwer

```bash
python app.py
```

Serwer wczyta projekt "Czarna" jako aktywny.

### 3. Sprawdź

```bash
# API
curl http://localhost:5000/api/project-info

# Lub otwórz w przeglądarce
http://localhost:5000/mapa/mapa.html
```

## 📦 Nowe Pliki

```
backend/
├── init_projects_table.py    # Inicjalizacja systemu
├── switch_project.py          # CLI do przełączania
└── .active_project            # Aktywny projekt (auto)

static/
└── js/
    └── project-loader.js      # Frontend loader

projects/                      # Dane projektów
├── czarna/
│   ├── data/
│   ├── geojson/
│   └── backups/
└── [inne projekty]/

Dokumentacja:
├── MULTI_PROJECT_SETUP.md     # Pełna dokumentacja
├── MIGRATION_GUIDE.md         # Przewodnik migracji
├── CHANGES_SUMMARY.md         # Podsumowanie zmian
└── MULTI_PROJECT_README.md    # Ten plik
```

## 🎨 Launcher - Zarządzanie GUI

### Widok Główny

```
┌────────────────────────────────────────────────────────┐
│ 🗺️ System Zarządzania Mapą Katastralną                │
│                              📁 Projekt: Czarna ⚙️      │
└────────────────────────────────────────────────────────┘
```

### Menedżer Projektów (przycisk ⚙️)

```
╔══════════════════════════════════════════════════════╗
║  📁 Zarządzanie Projektami          [➕ Nowy] [🔄]  ║
╠══════════════════════════════════════════════════════╣
║  ⭐ czarna    │ Czarna    │ XIX wiek │ aktywny       ║
║     borowa    │ Borowa    │ XX wiek  │ aktywny       ║
║     laski     │ Laski     │ XIX wiek │ archiwum      ║
╠══════════════════════════════════════════════════════╣
║  [✔️ Ustaw jako Aktywny] [✏️ Edytuj] [🗑️ Usuń]      ║
╚══════════════════════════════════════════════════════╝
```

### Edytor Projektu

```
╔════════════════════════════════════════════════╗
║  ➕ Nowy Projekt                               ║
╠════════════════════════════════════════════════╣
║  Podstawowe:                                   ║
║  Kod projektu: [borowa_______________]         ║
║  Nazwa:        [Borowa_______________]         ║
║  Pełna nazwa:  [Gmina Borowa_________]         ║
║                                                ║
║  Kontekst Czasowy:                             ║
║  Wiek/Epoka:   [XX wiek_____________]          ║
║  Rok źródłowy: [1920________________]          ║
║                                                ║
║  Lokalizacja:                                  ║
║  Region:       [Powiat Mielecki_____]          ║
║  Województwo:  [Podkarpackie________]          ║
║                                                ║
║  [💾 Zapisz]           [❌ Anuluj]             ║
╚════════════════════════════════════════════════╝
```

## 🔧 CLI - Narzędzia

### Przełączanie projektu

```bash
# Lista projektów
python backend/switch_project.py list

# Przełącz na "borowa"
python backend/switch_project.py switch borowa

# Aktywny projekt
python backend/switch_project.py current
```

Output:
```
======================================================================
  PROJEKT PRZEŁĄCZONY
======================================================================
Nowy aktywny projekt: Borowa (borowa)
Kontekst: XX wiek
Region: Powiat Mielecki
======================================================================

⚠️  WAŻNE: Zrestartuj serwer backend, aby zmiany zostały zastosowane!
```

## 🌐 API Endpoints

### Info o aktywnym projekcie
```bash
GET /api/project-info

Response:
{
  "status": "success",
  "project": {
    "short_code": "czarna",
    "nazwa": "Czarna",
    "pelna_nazwa": "Gmina Czarna",
    "kontekst_czasowy": "XIX wiek",
    "rok_zrodlowy": 1880,
    ...
  }
}
```

### Lista projektów
```bash
GET /api/projects

Response:
{
  "status": "success",
  "projects": [...],
  "active_project": "czarna"
}
```

### Tworzenie projektu
```bash
POST /api/projects
Content-Type: application/json

{
  "short_code": "borowa",
  "nazwa": "Borowa",
  "kontekst_czasowy": "XX wiek",
  "rok_zrodlowy": 1920
}
```

### Przełączanie
```bash
POST /api/projects/switch/borowa
```

### Aktualizacja
```bash
PUT /api/projects/1
Content-Type: application/json

{
  "nazwa": "Czarna (zaktualizowana)",
  "uwagi": "Nowe informacje..."
}
```

### Usuwanie
```bash
DELETE /api/projects/1
```

## 💻 Frontend - Integracja

### Krok 1: Dodaj skrypt

```html
<script src="/static/js/project-loader.js"></script>
```

### Krok 2: Użyj atrybutów

```html
<!-- Automatyczna zamiana "Czarna" i "XIX w." -->
<h1 class="app-title">Mapa Katastralna Czarna z XIX w.</h1>

<!-- Lub precyzyjne atrybuty -->
<h1 data-project-field="nazwa"></h1>
<p>Kontekst: <span data-project-field="kontekst_czasowy"></span></p>
```

### Krok 3: Reaguj na zdarzenia

```javascript
document.addEventListener('projectLoaded', (event) => {
    const project = event.detail;
    console.log('Załadowano:', project.nazwa);
    // Dostosuj UI
});
```

## 📊 Baza Danych

### Tabela projects

```sql
CREATE TABLE projects (
    id                   SERIAL PRIMARY KEY,
    short_code           VARCHAR(50) UNIQUE NOT NULL,
    nazwa                VARCHAR(200) NOT NULL,
    pelna_nazwa          VARCHAR(500),
    opis                 TEXT,
    kontekst_czasowy     VARCHAR(200),
    rok_zrodlowy         INTEGER,
    okres_danych         VARCHAR(100),
    region               VARCHAR(200),
    wojewodztwo          VARCHAR(100),
    jezyk_zrodel         VARCHAR(100),
    uwagi                TEXT,
    status               VARCHAR(50) DEFAULT 'aktywny',
    data_utworzenia      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ostatnia_modyfikacja TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Przykładowe dane

```sql
INSERT INTO projects (short_code, nazwa, kontekst_czasowy, rok_zrodlowy) VALUES
    ('czarna', 'Czarna', 'XIX wiek', 1880),
    ('borowa', 'Borowa', 'XX wiek', 1920),
    ('laski', 'Laski', 'XIX wiek', 1870);
```

## 🗂️ Struktura Folderów

```
projects/
├── czarna/
│   ├── data/
│   │   ├── database.json      # Właściciele
│   │   ├── demografia.json    # Demografia
│   │   ├── genealogia.json    # Genealogia
│   │   └── parcels.json       # Działki
│   ├── geojson/
│   │   └── parcels.geojson    # GeoJSON działek
│   └── backups/               # Backupy projektu
│       └── backup_20241103.zip
│
└── borowa/
    ├── data/
    ├── geojson/
    └── backups/
```

## 🧪 Testy

```bash
# Test 1: Inicjalizacja
cd backend
python init_projects_table.py
# ✅ Sprawdź: projects/czarna/ istnieje

# Test 2: API
curl http://localhost:5000/api/projects
curl http://localhost:5000/api/project-info
# ✅ Sprawdź: Zwraca dane Czarnej

# Test 3: Przełączanie
python backend/switch_project.py list
python backend/switch_project.py switch borowa
# ✅ Sprawdź: .active_project = "borowa"

# Test 4: Frontend
# Otwórz: http://localhost:5000/mapa/mapa.html
# ✅ Konsola: "✅ Projekt załadowany: Czarna"
```

## 🔄 Workflow Typowy

### Scenariusz: Dodanie nowego projektu "Borowa"

1. **Uruchom launcher**
   ```bash
   python launcher/launcher_app.py
   ```

2. **Otwórz menedżer** - Kliknij ⚙️ obok "Czarna"

3. **Utwórz projekt** - Kliknij "➕ Nowy Projekt"
   - Kod: `borowa`
   - Nazwa: `Borowa`
   - Kontekst: `XX wiek`
   - Rok: `1920`
   - Zapisz

4. **Import danych** - Skopiuj pliki do `projects/borowa/data/`

5. **Przełącz projekt**
   - W menedżerze wybierz "borowa"
   - Kliknij "✔️ Ustaw jako Aktywny"
   - Zrestartuj serwer

6. **Sprawdź**
   ```bash
   curl http://localhost:5000/api/project-info
   # Powinno zwrócić dane Borowej
   ```

## 📚 Dokumentacja

- **`MULTI_PROJECT_SETUP.md`** - Pełna dokumentacja techniczna
- **`MIGRATION_GUIDE.md`** - Przewodnik krok po kroku
- **`CHANGES_SUMMARY.md`** - Lista wszystkich zmian
- **`MULTI_PROJECT_README.md`** - Ten plik

## ❓ FAQ

### Q: Czy stare dane będą działać?
**A:** Tak! System jest w pełni kompatybilny wstecz.

### Q: Co się stanie jeśli nie uruchomię migracji?
**A:** System użyje domyślnego projektu "czarna" z hardkodowanymi wartościami.

### Q: Czy mogę mieć kilka projektów jednocześnie?
**A:** Tak, ale tylko jeden jest aktywny na raz. Przełączanie wymaga restartu serwera.

### Q: Gdzie są dane projektów?
**A:** W folderze `projects/{kod_projektu}/data/`

### Q: Jak usunąć projekt?
**A:** W launcherze → Menedżer → Wybierz projekt → Usuń (tylko nieaktywne!)

### Q: Czy frontend automatycznie się dostosuje?
**A:** Tak, jeśli dodano `project-loader.js` do strony HTML.

## 🐛 Rozwiązywanie Problemów

### Problem: "Projekt nie znaleziony"
```bash
# Sprawdź czy projekt istnieje w bazie
psql -U postgres -d mapa_czarna_db -c "SELECT * FROM projects;"
```

### Problem: Frontend pokazuje "Czarna" zamiast aktywnego projektu
```bash
# Sprawdź czy project-loader.js jest załadowany
# Otwórz konsolę przeglądarki (F12) i szukaj:
# "✅ Projekt załadowany: ..."
```

### Problem: Nie mogę przełączyć projektu
```bash
# Sprawdź plik .active_project
cat backend/.active_project

# Zmień ręcznie
echo "borowa" > backend/.active_project

# Zrestartuj serwer
```

## 🎉 Gratulacje!

System multi-projekt jest gotowy do użycia. Możesz teraz:
- ✅ Zarządzać wieloma miejscowościami
- ✅ Dynamicznie przełączać projekty
- ✅ Edytować metadane przez GUI
- ✅ Używać API do automatyzacji
- ✅ Zachować pełną izolację danych

**Powodzenia!** 🚀
