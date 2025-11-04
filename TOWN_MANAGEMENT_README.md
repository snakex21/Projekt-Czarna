# Zarządzanie Miejscowościami - Dokumentacja

## Przegląd

System mapy katastralnej został rozszerzony o funkcjonalność zarządzania wieloma miejscowościami. Każda miejscowość ma własny folder z danymi i konfiguracją.

## Struktura

### Plik konfiguracyjny miejscowości
`backup/miejscowosci.json` zawiera listę wszystkich miejscowości:

```json
[
  {
    "id": 1,
    "nazwa": "czarna",
    "pelna_nazwa": "Czarna",
    "powiat": "Dębica",
    "region": "Podkarpackie",
    "aktywna": true
  }
]
```

### Struktura folderów
```
backup/
├── miejscowosci.json
├── czarna/
│   ├── .env
│   ├── owner_data_to_import.json
│   ├── parcels_data.json
│   ├── genealogia.json
│   ├── demografia.json
│   └── map_config.json
└── inna_miejscowosc/
    ├── .env
    ├── owner_data_to_import.json
    └── ...
```

## Funkcjonalność w Launcher

### Panel wyboru miejscowości
Na górze głównego okna znajduje się sekcja "Wybór Miejscowości" z:
- **Dropdown** - wybór aktywnej miejscowości
- **Przycisk "Odśwież"** - odświeża listę miejscowości
- **Przycisk "Zarządzaj miejscowościami"** - otwiera okno zarządzania

### Okno "Zarządzaj miejscowościami"
Zawiera tabelę z kolumnami:
- ID
- Nazwa (nazwa folderu)
- Pełna Nazwa
- Powiat
- Region
- Aktywna (✓ oznacza aktywną miejscowość)

Dostępne operacje:
- **Dodaj nową miejscowość** - tworzy nowy folder i wpis
- **Edytuj** - modyfikuje dane miejscowości (zmienia nazwę folderu jeśli trzeba)
- **Usuń** - usuwa miejscowość i jej folder
- **Ustaw jako aktywną** - zmienia aktywną miejscowość
- **Odśwież** - odświeża listę

### Menedżer kopii zapasowych
Rozszerzony o opcję wyboru miejscowości:
- **Aktywna miejscowość** - backup tylko aktywnej
- **Konkretna miejscowość** - wybór z listy
- **Wszystkie miejscowości** - backup wszystkich

Opcje backupu:
- Właściciele i Demografia
- Działki (geometria)
- Konfiguracja Mapy
- Genealogia
- Skany Protokołów
- **Konfiguracja .env** (nowa opcja)

## Plik .env per miejscowość

Każda miejscowość ma własny plik `.env` w swoim folderze. Przy uruchomieniu serwera:
1. Launcher kopiuje `.env` z folderu aktywnej miejscowości do `backend/.env`
2. Serwer Flask ładuje konfigurację z tego pliku
3. Każda miejscowość może mieć osobną bazę danych

## Migracja istniejących danych

Przy pierwszym uruchomieniu:
1. System tworzy domyślną miejscowość "czarna"
2. Przenosi istniejące pliki JSON do folderu `backup/czarna/`
3. Ustawia "czarna" jako aktywną miejscowość

## API funkcji

### Funkcje zarządzania miejscowościami
```python
load_towns()                    # Wczytuje listę miejscowości
save_towns(towns)              # Zapisuje listę miejscowości
get_active_town()              # Zwraca aktywną miejscowość (dict)
get_active_town_folder()       # Zwraca ścieżkę folderu aktywnej miejscowości
get_active_town_env_path()     # Zwraca ścieżkę .env aktywnej miejscowości
get_data_files()               # Zwraca DATA_FILES dla aktywnej miejscowości
```

## Uwagi

1. **Zmiana miejscowości** - po zmianie aktywnej miejscowości należy zrestartować serwer
2. **Edycja miejscowości** - zmiana nazwy miejscowości zmienia nazwę folderu
3. **Usuwanie miejscowości** - usuwa cały folder z danymi (nieodwracalne!)
4. **Bazy danych** - każda miejscowość może mieć osobną bazę (zalecane)
