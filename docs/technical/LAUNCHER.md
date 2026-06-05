# Launcher (Centrum Zarządzania)

> GUI do konfiguracji, zarządzania miejscowościami, uruchamiania serwera.

## 1. Czym jest launcher

`launcher/launcher_app.py` to aplikacja Tkinter będąca **jedynym zalecanym
sposobem obsługi** projektu. Wszystkie inne narzędzia (edycja bazy, migracja,
restart serwera) są dostępne z poziomu launchera.

### Filozofia

> Cały program opiera się na GUI — bez ręcznej edycji JSON / .env / SQL.

Konsekwencje:

- Wszystkie akcje administracyjne mają odpowiednik w GUI.
- Pliki `.env` i JSON są edytowane tylko przez launcher (z wyjątkiem `tests/`).
- W skrajnych przypadkach (debug) można edytować ręcznie, ale launcher
  ostrzega i wymaga potwierdzenia.

## 2. Uruchomienie

```bash
python launcher/launcher_app.py
```

Wymagania:

- Python 3.11+
- Tkinter (wbudowany w Python, na Windows OK; na Linux może wymagać
  `sudo apt install python3-tk`).
- Ekran (X11 / Wayland / macOS / Windows).

## 3. Główne okno

Launcher to `Toplevel` z `ttk.Notebook` (zakładki):

| Zakładka | Funkcja |
|----------|---------|
| **Aktywna miejscowość** | Wybór miejscowości + aktywacja (zapis do `data/locations.db`) |
| **Serwer** | Start/Stop backendu (lokalny lub sieciowy) + logi |
| **Centrum Zarządzania** | Kreator PostgreSQL, bazy danych, kalibracja mapy (planowane) |
| **Ustawienia Administratora** | Hasło admina, logi, konfiguracja sieci |
| **Zaawansowane** | Kreator baz, edytor właścicieli/działek/genealogii |
| **Diagnostyka** | Szybka diagnostyka + jakość danych + bezpieczeństwo admina |

## 4. Architektura launchera

### 4.1 Struktura katalogów

```text
launcher/
├── launcher_app.py        # główne okno + klasy dialogów
├── services/              # logika (BEZ I/O w UI)
│   ├── process_manager.py # subprocess + zarządzanie procesami
│   ├── env_runtime.py     # odczyt/zapis .env
│   ├── network_runtime.py # tryb sieciowy (LAN)
│   ├── firewall_runtime.py# reguły Windows Firewall
│   ├── admin_config_service.py  # hasło admina (Werkzeug)
│   ├── location_migration_service.py  # tworzenie miejscowości
│   ├── historical_points_service.py  # markery (P3)
│   └── shutdown_runtime.py # housekeeping przy zamykaniu
├── ui/                    # dialogi (wyłącznie delegacja)
│   ├── add_edit_location_dialog.py  # edycja miejscowości (zakładki)
│   ├── location_manager.py
│   ├── program_settings.py          # okno ustawień (P4 + P6.5)
│   ├── env_editor.py
│   ├── network_dialogs.py
│   └── (security_manager.py usunięty w P5.1 - relikt Flask)
├── config/                # ścieżki, stałe, ustawienia
│   ├── paths.py           # BASE_DIR, BACKEND_DIR, DATA_DIR
│   ├── settings.py        # SCRIPTS, URLS
│   └── ui_settings.py     # motyw, kolory, fonty
└── utils/                 # pomocnicze
    ├── process_env.py     # budowanie env dla subprocess
    └── process_command.py # budowanie komendy dla subprocess
```

### 4.2 Zasada podziału

```text
launcher/ui/*        →   launcher/services/*    (logika)
launcher/services/*  →   backend/services/*     (współdzielona logika)
launcher/ui/*        →   backend/routers/*      ❌ (ZAKAZ - UI w launcherze nie woła API)
backend/*            →   launcher/*             ❌ (ZAKAZ - cykliczność)
```

**Konsekwencja:** każda klasa UI testuje się przez **kontrakt na kodzie**
(regex na string źródłowy), nie przez podnoszenie okna. To dlatego
mamy `test_<dialog>_contract.py` z testami typu
"klasa X musi wywołać metodę Y z argumentami Z".

### 4.3 Process manager

`launcher/services/process_manager.py` to serce launchera. Zarządza
procesami backendu przez `subprocess.Popen`:

```python
process = subprocess.Popen(
    [sys.executable, "-X", "utf8", "-u", "-m", "uvicorn",
     "backend.main:app", "--host", "127.0.0.1", "--port", "5000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    cwd=str(BASE_DIR),
    encoding="utf-8",
    errors="replace",
    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    env=env,  # przygotowane przez prepare_process_env
)
```

Kluczowe cechy:

- `creationflags=CREATE_NO_WINDOW` (Windows) - brak konsoli w tle.
- `CREATE_NEW_PROCESS_GROUP` - można ubić grupę razem.
- `stdout=PIPE, stderr=STDOUT` - oba strumienie w jednym logu.
- `encoding="utf-8", errors="replace"` - polskie znaki nie crashują.
- Output czytany w wątku (`threading.Thread`) i logowany do konsoli w Ttk.

### 4.4 Network runtime

`launcher/services/network_runtime.py` obsługuje tryb sieciowy (LAN):

- Dodaje regułę Windows Firewall dla portu backendu
  (przez `firewall_runtime`).
- Binduje na `0.0.0.0` zamiast `127.0.0.1`.
- Wyświetla dialog z adresami IP do połączenia z innych urządzeń.
- **Priorytet 6.7:** loguje ostrzeżenie gdy `ADMIN_AUTH_ENABLED=False`.

## 5. Konfiguracja per-miejscowość

Każda miejscowość ma swój `.env` w `data/locations/<Nazwa>/.env`:

```bash
ACTIVE_LOCATION=Czarna
DB_ENGINE=sqlite
DB_PATH=C:\...\data\czarna.db
LAUNCHER_PORT=5000
ADMIN_AUTH_ENABLED=1
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=scrypt:32768:8:1$...$...
```

Launcher czyta `.env` przez `env_runtime.read_env_config()` i przygotowuje
środowisko dla procesu backendu (`prepare_process_env()`).

## 6. Zarządzanie miejscowościami

`launcher/ui/location_manager.py` + `launcher/services/location_migration_service.py`:

- **Lista miejscowości** (z `data/locations.db`).
- **Aktywacja** (zmiana `ACTIVE_LOCATION` + restart backendu).
- **Tworzenie nowej** (`create_and_migrate_location_database()`).
- **Edycja** (`add_edit_location_dialog.py` - 6 zakładek).
- **Usuwanie** (z potwierdzeniem + opcją backupu).

### 6.1 Zakładki edycji miejscowości

1. **Podstawowe** - nazwa, gmina, powiat, region, lata.
2. **Protokół** - konfiguracja strony protokołu.
3. **Strona główna** - zawartość strony głównej (HTML).
4. **Historia** - treść opisowa miejscowości.
5. **Zdjęcia** - galeria miejscowości.
6. **Punkty historyczne** (P3) - markery na mapie + zdjęcia.

Każda zakładka deleguje do serwisu. UI nie pisze bezpośrednio do plików.

## 7. Bezpieczeństwo (interakcja z Priorytetem 6)

### 7.1 Hasło admina

- Launcher ma własną logikę hashowania (Werkzeug) w
  `admin_config_service.hash_admin_password()`.
- Wcześniej (P6.3) był bug: backend czytał tylko SHA-256 hex, ale launcher
  pisał `scrypt:...`. Naprawione.
- Endpoint `POST /api/admin/change-password` (P6.4) używa
  `save_admin_password_hash()` z launchera do zapisu do `.env`.

### 7.2 Tryb sieciowy (P6.7)

Launcher wyświetla ostrzeżenie w konsoli serwera gdy:
- `ADMIN_AUTH_ENABLED=False` (każdy w LAN może modyfikować dane).
- `SECRET_KEY` to fallback (dev-secret-change-me).

## 8. Diagnostyka (Priorytet 4 + 6.5)

`launcher/ui/program_settings.py` ma zakładkę **Diagnostyka** z trzema kartami:

1. **Szybka diagnostyka systemu** - silnik DB, ścieżki, health.
2. **Jakość danych** (P4) - 9 metryk z `GET /api/admin/diagnostics` + agregat.
3. **Bezpieczeństwo admina** (P6.5) - status z `GET /api/admin/auth-status`.

Każda karta ma przycisk **🔄 Odśwież** + pole tekstowe z wynikiem. Fetch
w wątku tła (`threading.Thread`) żeby nie blokować UI; wynik wpisywany
przez `self.diagnostics_tab.after(0, ...)`.

## 9. Znane problemy

### 9.1 Dead code

`launcher/ui/security_manager.py` był reliktem po Flasku i wołał nieistniejące
endpointy `/api/admin/security/*`. Został usunięty w P5.1. Aktualna diagnostyka
bezpieczeństwa admina jest w `program_settings.py` (zakładka Diagnostyka).

### 9.2 Brak logów w pliku

Logi launchera są tylko w konsoli (okno Ttk Notebook). Brak
obrotu logów, brak zapisu do pliku. Planowane jako future enhancement.

### 9.3 Brak auto-restartu backendu

Jeśli backend padnie (np. błąd w kodzie), launcher nie restartuje
go automatycznie. Trzeba kliknąć ⏹️ Zatrzymaj → ▶️ Uruchom.

## 10. Rozszerzanie launchera

### 10.1 Nowa zakładka

1. Dodaj `self.<feature>_tab = ttk.Frame(self.notebook)` w `__init__`.
2. Zarejestruj `self.notebook.add(self.<feature>_tab, text="...")`.
3. Zaimplementuj `_build_<feature>_tab(self)`.
4. Test kontraktu w `backend/tests/unit/test_launcher_ui_imports.py`.

### 10.2 Nowa akcja (przycisk)

1. Dodaj przycisk w `_build_<feature>_tab`.
2. Przypisz `command=self._on_<action>`.
3. Implementuj `_on_<action>` (krótki handler delegujący do service).
4. Test kontraktu: regex na `_build_*` sprawdza że przycisk istnieje
   i ma `command=`.

### 10.3 Nowy serwis

1. Utwórz `launcher/services/<feature>.py` z czystą logiką.
2. Unikaj importów z `launcher.ui` (cykliczność).
3. Testy w `backend/tests/unit/test_<service>.py`.
4. UI importuje i woła, nigdy odwrotnie.

## 11. Zobacz też

- [ARCHITECTURE.md](ARCHITECTURE.md) - architektura
- [SECURITY.md](SECURITY.md) - bezpieczeństwo admina
- [DATABASE.md](DATABASE.md) - baza danych
- [LOCATIONS.md](LOCATIONS.md) - model miejscowości
- [TODO.md](../TODO.md) - status priorytetów
- [PROJECT_SKILL.md](../PROJECT_SKILL.md) - konwencje kodu
