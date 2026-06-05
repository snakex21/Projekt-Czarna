# MiejscowoĹ›ci

> Model danych per-miejscowoĹ›Ä‡, tworzenie, przeĹ‚Ä…czanie, perspektywy rozwoju.

## 1. Decyzja: jedna miejscowoĹ›Ä‡ = jedna instancja

> CaĹ‚y projekt jest zbudowany wokĂłĹ‚ **jednej aktywnej miejscowoĹ›ci** w danym
> momencie. RĂłĹĽne miejscowoĹ›ci to rĂłĹĽne instancje programu.

**Uzasadnienie** (peĹ‚na dyskusja w [ARCHITECTURE.md Â§ ADR-001](ARCHITECTURE.md#adr-001-jedna-miejscowoĹ›Ä‡--jedna-instancja)):

- Projekt mocno osadzony w polskim kontekĹ›cie historyczno-katastralnym
  (protokoĹ‚y, wĹ‚asnoĹ›Ä‡ rzeczywista, ksiÄ™gi metrykalne).
- Terminologia typu `protokĂłĹ‚`, `dzialki`, `wlasciciele` jest specyficzna
  regionalnie.
- RĂłĹĽne miejscowoĹ›ci mogÄ… mieÄ‡ rĂłĹĽne typy dokumentĂłw, kalibracji map,
  struktury wĹ‚asnoĹ›ci.
- Wiele miejscowoĹ›ci naraz komplikuje ID, kalibracje map, statystyki,
  backupy, admina.

**Praktyczny wariant przyszĹ‚oĹ›ciowy:**

```text
Mapa Czarna       â†’ port / endpoint A
Mapa InnaWieĹ›     â†’ port / endpoint B
Mapa KolejnaWieĹ›  â†’ port / endpoint C
```

Osobne instancje programu dla rĂłĹĽnych miejscowoĹ›ci, z osobnymi katalogami
danych i konfiguracjÄ….

## 2. Struktura katalogu miejscowoĹ›ci

```text
data/locations/
â””â”€â”€ Czarna/                       # jedna miejscowoĹ›Ä‡
    â”śâ”€â”€ .env                      # konfiguracja (w .gitignore)
    â”śâ”€â”€ parcels_data.json         # geometria dziaĹ‚ek
    â”śâ”€â”€ owner_data.json           # wĹ‚aĹ›ciciele (cache)
    â”śâ”€â”€ demografia.json           # statystyki
    â”śâ”€â”€ genealogia.json           # drzewo genealogiczne
    â”śâ”€â”€ historical_points.json    # markery na mapie (P3)
    â”śâ”€â”€ map_config.json           # kalibracja mapy
    â”śâ”€â”€ point_photos/             # zdjÄ™cia markerĂłw (P3.1)
    â”śâ”€â”€ history_photos/           # galeria miejscowoĹ›ci
    â”śâ”€â”€ protokoly/                # pliki protokoĹ‚Ăłw
    â”śâ”€â”€ mapa.jpg                  # raster mapy
    â”śâ”€â”€ favicon.jpeg
    â””â”€â”€ custom_icon.png           # ikona launchera
```

## 3. Rejestr miejscowoĹ›ci (`data/locations.db`)

Launcher ma wĹ‚asnÄ… bazÄ™ SQLite z listÄ… miejscowoĹ›ci:

```sql
CREATE TABLE locations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    active INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE launcher_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

Aktywna miejscowoĹ›Ä‡ ma `active=1`. Launcher czyta to przy starcie
i ustawia `ACTIVE_LOCATION` env dla procesu backendu.

## 4. Schemat `historical_points.json` (Priorytet 3)

```json
{
  "version": 1,
  "points": [
    {
      "object_name": "dworzec kolejowy",
      "display_name": "Dworzec kolejowy w Czarnej",
      "description": "Budynek dworca z 1905 roku...",
      "source_note": "Archiwum PaĹ„stwowe w Rzeszowie, sygn. 123/45",
      "photos": [
        {
          "filename": "dworzec_czarna.png",
          "caption": "Dworzec kolejowy w Czarnej, ok. 1935 r."
        }
      ]
    }
  ]
}
```

Pola:

- `object_name` - klucz Ĺ‚Ä…czÄ…cy z obiektem geograficznym (z `parcels_data.json`).
- `display_name` - nazwa wyĹ›wietlana w popupie.
- `description` - opis wieloliniowy.
- `source_note` - ĹşrĂłdĹ‚o historyczne.
- `photos` - lista zdjÄ™Ä‡ z podpisami (caption).

## 5. Tworzenie nowej miejscowoĹ›ci

Przez launcher (`location_migration_service.create_and_migrate_location_database`):

1. UĹĽytkownik podaje nazwÄ™ + opcjonalnie wybiera ĹşrĂłdĹ‚o danych (backup,
   import z innej miejscowoĹ›ci, pusty szablon).
2. Serwis tworzy katalog `data/locations/<Nazwa>/` z domyĹ›lnÄ… strukturÄ….
3. JeĹ›li wybrano szablon - kopiuje `parcels_data.json`, `owner_data.json`
   itd. do nowego katalogu.
4. Generuje `mapa.jpg` placeholder (jeĹ›li brak).
5. Rejestruje w `data/locations.db`.
6. (Opcjonalnie) aktywuje jako bieĹĽÄ…cÄ… miejscowoĹ›Ä‡.

## 6. Aktywacja miejscowoĹ›ci

Aktywacja = zmiana `ACTIVE_LOCATION` env + restart backendu.

```text
[UĹĽytkownik] â†’ wybiera miejscowoĹ›Ä‡ w launcherze
   â†“
[env_runtime.write_env_config()] zapisuje ACTIVE_LOCATION=NowaMiejscowosc
   â†“
[process_manager] zatrzymuje stary backend
   â†“
[process_manager] startuje nowy backend z nowym env
   â†“
[backend/main.py] czyta nowy ACTIVE_LOCATION, uĹĽywa nowego katalogu
```

## 7. Konwencja: jedna aktywna miejscowoĹ›Ä‡ na instancjÄ™

RozrĂłĹĽniamy:

- **Aktywna miejscowoĹ›Ä‡** - wybrana w launcherze, wskazywana przez
  `ACTIVE_LOCATION`. Backend jÄ… obsĹ‚uguje.
- **PozostaĹ‚e miejscowoĹ›ci** - katalogi `data/locations/*/`. Nie sÄ…
  Ĺ‚adowane przez bieĹĽÄ…cy backend. DostÄ™pne po przeĹ‚Ä…czeniu.

Konsekwencja: **migracja danych miÄ™dzy miejscowoĹ›ciami** to kopia plikĂłw
JSON, nie eksport z bazy. Pliki sÄ… niezaleĹĽne.

## 8. Migracja a aktywacja

| Akcja | Skutek |
|-------|--------|
| Tworzenie miejscowoĹ›ci | Nowy katalog + wpis w rejestrze. NIE aktywuje. |
| Aktywacja | Zmiana ACTIVE_LOCATION + restart. Backend przeĹ‚adowuje dane. |
| Usuwanie | UsuniÄ™cie katalogu + wpisu w rejestrze. Wymaga potwierdzenia. |
| Backup | Kopia katalogu miejscowoĹ›ci (zip / katalog). |

## 9. Perspektywy rozwoju

### 9.1 Wiele miejscowoĹ›ci na jednej mapie (Ĺ›wiadomie odĹ‚oĹĽone)

Patrz ADR-001. WymagaĹ‚oby:

- Globalnego ID space z prefixem miejscowoĹ›ci.
- Ĺadowania wielu kalibracji map.
- WspĂłlnego UI do filtrowania po miejscowoĹ›ci.
- Refactoru modelu danych.

**Decyzja:** nie robimy. Wydzielamy osobne instancje zamiast wielkiej mapy.

### 9.2 WielojÄ™zycznoĹ›Ä‡ UI (Ĺ›wiadomie odĹ‚oĹĽone)

Projekt jest polskojÄ™zyczny. Wiele tĹ‚umaczeĹ„ niepotrzebnych w kontekĹ›cie
katastralnym. W razie potrzeby - `gettext` + pliki `.po`.

### 9.3 WspĂłĹ‚dzielenie danych miÄ™dzy miejscowoĹ›ciami

Np. ta sama osoba wystÄ™puje w dwĂłch miejscowoĹ›ciach (maĹ‚ĹĽeĹ„stwo).
Aktualnie: kaĹĽda miejscowoĹ›Ä‡ ma wĹ‚asny rekord.

W przyszĹ‚oĹ›ci: wspĂłlna tabela `osoby` + per-miejscowoĹ›Ä‡ powiÄ…zania.

## 10. Testy

W `backend/tests/unit/test_historical_points_service.py` (32 testy):

- Walidacja schematu `historical_points.json`.
- I/O: zapis/odczyt z katalogu miejscowoĹ›ci.
- Helpery: `list_special_objects`, `list_history_photos`, `list_point_photos`.
- Filtrowanie, sortowanie, edge cases (pusty, brak katalogu).

W `backend/tests/integration/test_historical_points.py` (9 testĂłw):

- Endpoint `GET /api/historical-points` zwraca FeatureCollection.
- Filtrowanie po miejscowoĹ›ci, sanityzacja danych.

## 11. Zobacz teĹĽ

- [ARCHITECTURE.md](ARCHITECTURE.md) - architektura, ADR-001
- [LAUNCHER.md](LAUNCHER.md) - GUI launchera, zarzÄ…dzanie miejscowoĹ›ciami
- [DATABASE.md](DATABASE.md) - tryby DB, pliki per-miejscowoĹ›Ä‡
- [TODO.md](../TODO.md) - status priorytetĂłw
- [PROJECT_SKILL.md](../PROJECT_SKILL.md) - konwencje
