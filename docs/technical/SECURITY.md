# Bezpieczeństwo

> Polityka bezpieczeństwa admina, tryb sieciowy, hardening, znane ograniczenia.

## 1. Kontekst

Projekt obsługuje panel administracyjny z możliwością modyfikacji danych
(CRUD obiektów, właścicieli, genealogii, diagnostyki). W trybie sieciowym
(LAN) backend nasłuchuje na `0.0.0.0` - potencjalnie dostępny z innych
urządzeń w sieci. Priorytet 6 zamknął najważniejsze luki.

## 2. Model zagrożeń

### 2.1 Zagrożenia rozważone

| Zagrożenie | Wpływ | Mitygacja |
|------------|-------|-----------|
| Dostęp do panelu admina bez hasła | **Krytyczny** - modyfikacja danych | Cookie session + Werkzeug hash hasła (P6.1-6.4) |
| Backdoor w `verify_password` (SHA-256 vs Werkzeug) | **Krytyczny** - hasła nieaktywne | P6.3 naprawił detekcję formatu |
| Domyślne hasło `admin123` w produkcji | Wysoki | Ostrzeżenie w `/auth-status` (P6.2) + w launcherze (P6.5) |
| Domyślny `SECRET_KEY` w produkcji | Wysoki | `assert_safe_secret_key` (P6.6) - blokuje startup |
| Tryb sieciowy bez auth | Wysoki | Ostrzeżenie w `start_network_server` (P6.7) |
| CORS wildcard z credentials | Średni | `get_cors_allowed_origins` z env (P6.8) |

### 2.2 Zagrożenia poza zakresem (znane ograniczenia)

- **Brak HTTPS.** Zakładamy reverse proxy (nginx/Caddy) w produkcji.
  Backend w trybie dev/test działa po HTTP.
- **Brak rate-limit na logowanie.** Brute-force atak możliwy. Do rozważenia.
- **Brak automatycznego wygasania sesji admina.** Token ważny 24h. Brak
  odświeżania - po wygaśnięciu trzeba zalogować się ponownie.
- **Brak 2FA.** Hasło to jedyny czynnik.
- **Historycznie:** `launcher/ui/security_manager.py` był dead code z czasów Flask
  i wołał nieistniejące endpointy `/api/admin/security/*`. Usunięty w P5.1;
  aktualny status bezpieczeństwa jest w zakładce Diagnostyka launchera.

## 3. Mechanizmy bezpieczeństwa

### 3.1 Cookie session (HttpOnly, SameSite=Lax)

```python
# backend/auth/routes.py
response.set_cookie(
    key="admin_session",
    value=token,
    httponly=True,
    samesite="lax",
    secure=IS_PRODUCTION,  # True w produkcji (HTTPS)
    max_age=24 * 60 * 60,  # 24h
)
```

- `HttpOnly` - JS nie ma dostępu (ochrona przed XSS).
- `SameSite=Lax` - ochrona przed CSRF.
- `Secure` - tylko HTTPS w produkcji.
- 24h ważność.

### 3.2 Hasło admina - format

Hasło jest haszowane w launcherze (Werkzeug `scrypt`) i zapisywane w
`backend/.env` jako `ADMIN_PASSWORD_HASH=scrypt:32768:8:1$...$...`.

Backend `verify_password` akceptuje:

- **Pusty / None** → fallback do `sha256("admin123")` (dev convenience).
- **64 znaki hex** → SHA-256 (legacy / ustawienie ręczne).
- **`scrypt:...$...$...`** (≥2 `$` + `:`) → Werkzeug.

Detekcja formatu w `backend/auth/routes.py`:

```python
def _looks_like_werkzeug_hash(h: str) -> bool:
    return ":" in h and h.count("$") >= 2
```

### 3.3 Zmiana hasła

`POST /api/admin/change-password` (P6.4):

- Wymaga zalogowania (`admin_required`).
- Sprawdza obecne hasło.
- Waliduje: min 8 znaków, różne od obecnego.
- Zapisuje nowy hash przez `launcher/services/admin_config_service.py::save_admin_password_hash()`.
- Aktualizuje `config.ADMIN_PASSWORD_HASH` w pamięci (bieżący proces widzi zmianę).

### 3.4 Walidacja startup (P6.6)

W `lifespan` (`backend/main.py`):

```python
from .auth.security import assert_safe_secret_key, is_production_mode
assert_safe_secret_key(is_production_mode(), SECRET_KEY)
```

Produkcja + fallback `SECRET_KEY` → `ValueError` (backend nie startuje).
W dev przechodzi bezwarunkowo.

### 3.5 Ostrzeżenie w trybie sieciowym (P6.7)

`launcher/services/network_runtime.py::_log_network_security_warnings()`:

```python
from backend.auth.security import get_network_security_warnings
warnings = get_network_security_warnings()
for w in warnings:
    process_mgr.app.log(w + "\n")
```

Wywoływane przy każdym `start_network_server()`. Gdy
`ADMIN_AUTH_ENABLED=False` - loguje się ostrzeżenie do konsoli serwera.

### 3.6 CORS hardening (P6.8)

`backend/auth/security.py::get_cors_allowed_origins()`:

- Czyta env `CORS_ALLOWED_ORIGINS` (lista po przecinku).
- W dev (PRODUCTION=False) + brak env → `["*"]`.
- W produkcji + brak env → `ValueError` (bezpieczeństwo).
- W produkcji z env → lista z env.

Wymagana akcja dla admina: ustawić `CORS_ALLOWED_ORIGINS` w `.env` przed
publikacją.

## 4. Konfiguracja produkcyjna

### 4.1 Wymagane env vars w produkcji

```bash
# backend/.env
PRODUCTION=1                                    # włącza tryb produkcyjny
ENVIRONMENT=production                          # alternatywa

FLASK_SECRET_KEY=<losowy ciąg 32+ znaków>       # NIE "dev-secret-change-me"!
ADMIN_AUTH_ENABLED=1                            # włącz autoryzację
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=scrypt:32768:8:1$...$...    # hasło ZMIENIONE z domyślnego

CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
```

### 4.2 Przed publikacją - checklist

- [ ] `PRODUCTION=1` w `.env`.
- [ ] `FLASK_SECRET_KEY` to losowy 32+ znakowy ciąg.
- [ ] `ADMIN_PASSWORD_HASH` to hash **innego** hasła niż `admin123`.
- [ ] `CORS_ALLOWED_ORIGINS` zawiera tylko zaufane domeny.
- [ ] HTTPS przez reverse proxy (nginx/Caddy).
- [ ] Firewall zezwala na port backendu tylko z zaufanych IP.
- [ ] Backup `.env` w bezpiecznym miejscu.

Launcherowa karta "Bezpieczeństwo admina" (P6.5) automatycznie pokaże
status tych wymagań.

## 5. Sekrety w repozytorium

- `backend/.env` - **w `.gitignore`**. Nigdy nie commituj.
- `data/locations/*/.env` - **w `.gitignore`**.
- Hashe haseł - w `.env` (też w `.gitignore`).
- Przykładowy `.env.example` - commituj (z pustymi wartościami).

## 6. Co robić w razie incydentu

### 6.1 Podejrzenie wycieku hasła

1. Zatrzymaj backend (`⏹️ Zatrzymaj` w launcherze).
2. Zmień hasło w launcherze (`Ustawienia Administratora`).
3. Sprawdź logi serwera pod kątem podejrzanych zmian.
4. Sprawdź `.env` - czy ktoś nie modyfikował.
5. Jeśli to poważne - rotuj też `SECRET_KEY` (unieważnia wszystkie sesje).

### 6.2 Wykrycie nieautoryzowanej modyfikacji danych

1. Sprawdź `data/locations/<miejscowość>/parcels_data.json` i inne pliki
   pod kątem ostatnich zmian (timestamp + zawartość).
2. Sprawdź logi serwera (zakładka "Serwer" w launcherze) - kto co zmieniał.
3. Przywróć z backupu (jeśli masz).
4. Zmień hasło (jak 6.1).
5. Wyłącz tryb sieciowy jeśli zbędny.

## 7. Testy bezpieczeństwa

W `backend/tests/unit/test_auth_security.py` (23 testy):

- `is_default_admin_password` - wykrywa `sha256("admin123")` i pusty hash.
- `is_default_secret_key` - wykrywa `"dev-secret-change-me"`.
- `is_production_mode` - czyta `PRODUCTION=1` i `ENVIRONMENT=production`.
- `get_admin_security_status` - pełny raport z ostrzeżeniami.
- `assert_safe_secret_key` - blokuje produkcję z fallbackiem.
- `get_network_security_warnings` - ostrzeżenie dla trybu LAN.
- `get_cors_allowed_origins` - walidacja i parsowanie env.

W `backend/tests/integration/test_auth_status_router.py` (11 testów):

- `GET /api/admin/auth-status` - kształt JSON, wsteczna kompatybilność `enabled`.
- `POST /api/admin/change-password` - walidacja, sukces, zapis do .env.

W `backend/tests/unit/test_verify_password.py` (7 testów):

- Detekcja formatu hasła (pusty, SHA-256 hex, Werkzeug).
- Fallback na `admin123` gdy brak hasha.

## 8. Przyszłe ulepszenia (poza P6)

- [ ] Rate-limit logowania (np. 5 prób / 15 min).
- [ ] Auto-wygasanie sesji (token refresh).
- [ ] Opcjonalne 2FA (TOTP).
- [ ] Audit log (kto, co, kiedy zmienił).
- [ ] HTTPS wsparcie bezpośrednio w uvicorn (opcjonalne).
- [x] Usunięcie dead code `launcher/ui/security_manager.py` (P5.1).

## 9. Zobacz też

- [ARCHITECTURE.md](ARCHITECTURE.md) - architektura
- [LAUNCHER.md](LAUNCHER.md) - GUI launchera (karta "Bezpieczeństwo admina")
- [TESTING.md](TESTING.md) - testy bezpieczeństwa
- [TODO.md](../TODO.md) - status Priorytetu 6
