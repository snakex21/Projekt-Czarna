# Instrukcja uruchomienia i testowania nowych statystyk

## 🚀 Szybki start

### Opcja 1: Testowy serwer (bez bazy danych - REKOMENDOWANE)

```bash
cd /home/engine/project
./start_test_servers.sh
```

Następnie otwórz w przeglądarce:
**http://127.0.0.1:8000/wlasciciele/stats.html**

### Opcja 2: Pełny serwer (wymaga PostgreSQL)

```bash
cd /home/engine/project
./start_server.sh
```

## 📊 Co testować

Po otwarciu strony statystyk:

1. **Przejdź do zakładki "Rankingi"** (druga zakładka)

2. **Przewiń w dół** - zobaczysz trzy nowe sekcje:

### ✅ Sekcja 1: Własność ziemi według właścicieli
- Ranking właścicieli według powierzchni ziemi
- Przełączanie jednostek: **ha / a / m²** (przyciski na górze)
- Kliknięcie na właściciela przenosi do jego profilu
- Medal dla TOP 3 (złoto/srebro/brąz)

### ✅ Sekcja 2: Największe działki
- Ranking największych działek
- Pokazuje numer, kategorię, właściciela i powierzchnię
- Ikony kategorii (🌱 rolna, 🏠 budowlana, 🌲 las, ⛰️ pastwisko)
- Przycisk eksportu do Excel

### ✅ Sekcja 3: Statystyki rzek i dróg
- Dwie karty obok siebie: rzeki i drogi
- Dla każdej kategorii:
  - Najdłuższa
  - Najkrótsza  
  - Średnia długość
  - Liczba obiektów
- Lista z długościami (automatyczne formatowanie km/m)

## 🧪 Dane testowe

Testowy serwer generuje losowe dane:
- 10 właścicieli z powierzchnią 0.5 - 50 ha
- 20 działek o różnych powierzchniach
- 5 rzek
- 8 dróg

Dane są generowane przy każdym odświeżeniu strony.

## 🔧 Debugowanie

### Sprawdź czy serwery działają:

```bash
# Backend
curl http://127.0.0.1:5000/api/stats

# Frontend  
curl http://127.0.0.1:8000/wlasciciele/stats.html
```

### Sprawdź logi:

```bash
# Backend
tail -f backend/test_server.log

# Frontend
tail -f frontend_server.log
```

### Sprawdź procesy:

```bash
ps aux | grep python3
```

### Zatrzymaj serwery:

```bash
pkill -f 'python3 test_server.py'
pkill -f 'python3 -m http.server'
```

## 📝 Struktura API

Nowe pola w `/api/stats`:

```json
{
  "land_ownership": [
    {
      "nazwa_wlasciciela": "Kowalski A",
      "unikalny_klucz": "owner_1",
      "numer_protokolu": "100",
      "area_sqm": 483152.0,
      "area_ares": 4831.52,
      "area_hectares": 48.32
    }
  ],
  "parcel_rankings": [
    {
      "id": 1,
      "numer": "100",
      "kategoria": "rolna",
      "wlasciciele": "Kowalski",
      "area_sqm": 95234.0,
      "area_hectares": 9.52
    }
  ],
  "rivers_roads_stats": {
    "rivers": {
      "longest": {"nazwa": "Rzeka A", "length_m": 14523, "length_km": 14.52},
      "shortest": {"nazwa": "Rzeka E", "length_m": 523, "length_km": 0.52},
      "average": 8234.5,
      "total_count": 5,
      "items": [...]
    },
    "roads": {
      "longest": {...},
      "shortest": {...},
      "average": 3234.5,
      "total_count": 8,
      "items": [...]
    }
  }
}
```

## 🎨 Stylowanie

Wszystkie nowe sekcje używają istniejących klas CSS:
- `.dashboard-card` - kontener sekcji
- `.ranking-list` - lista rankingowa
- `.ranking-item` - pojedynczy element
- `.mini-stat` - mini statystyki
- `.segmented` - przełącznik jednostek

**Nie ma zmian w szerokości** - wszystkie sekcje mają spójną szerokość z resztą strony.

## ✅ Weryfikacja

Sprawdź czy:
- [ ] Wszystkie trzy sekcje są widoczne w zakładce "Rankingi"
- [ ] Przełączanie jednostek (ha/a/m²) działa
- [ ] Dane są poprawnie sformatowane
- [ ] Nie ma błędów w konsoli przeglądarki (F12)
- [ ] Nie ma poziomego scrollowania
- [ ] Szerokość sekcji jest spójna z resztą strony
- [ ] Medal TOP 3 jest widoczny w rankingach
- [ ] Długości rzek/dróg są poprawnie formatowane (km dla długich, m dla krótkich)

## 🐛 Znane problemy

### Problem: "Brak danych"
**Rozwiązanie:** To normalne jeśli baza danych jest pusta. Użyj testowego serwera.

### Problem: Błąd CORS
**Rozwiązanie:** Upewnij się że używasz http://127.0.0.1:8000, nie file://

### Problem: 404 Not Found
**Rozwiązanie:** Sprawdź czy oba serwery są uruchomione (backend i frontend)

## 📚 Dokumentacja

- `IMPLEMENTATION_SUMMARY.md` - szczegóły implementacji
- `BUGFIX_SUMMARY.md` - naprawione błędy
- `FIX_VERIFICATION.md` - weryfikacja naprawy

## 💾 Przywracanie produkcyjnego serwera

Aby używać prawdziwej bazy danych PostgreSQL:

1. Upewnij się że PostgreSQL działa
2. Skonfiguruj `.env` w katalogu backend:
   ```
   DB_HOST=localhost
   DB_NAME=mapa_czarna_db
   DB_USER=postgres
   DB_PASSWORD=twoje_haslo
   DB_PORT=5432
   ```
3. Uruchom: `./start_server.sh`

---

**Autor implementacji:** AI Assistant  
**Data:** 2024  
**Ticket:** Add land ownership & parcel/river rankings to statistics
