# Ranking Działek według Powierzchni

## Opis funkcjonalności

Dodano nowy ranking pokazujący największe działki według powierzchni, wyświetlany na stronie statystyk w zakładce "Rankingi".

## Interfejs użytkownika

### Lokalizacja
Ranking znajduje się w zakładce **"Rankingi"**, poniżej rankingu właścicieli.

### Tytuł sekcji
**"TOP 50 Największych Działek"**

### Elementy wyświetlane dla każdej działki:

1. **Pozycja w rankingu** (1-50)
   - Złoty medal 🥇 dla 1. miejsca
   - Srebrny medal 🥈 dla 2. miejsca
   - Brązowy medal 🥉 dla 3. miejsca

2. **Numer działki** - główna nazwa (np. "100", "201/1")

3. **Właściciel** - wyświetlany jako link do protokołu właściciela
   - Jeśli właściciel nieznany: "Brak właściciela"
   - Link: klikalne przekierowanie do protokołu

4. **Powierzchnia** - wyświetlana w odpowiednich jednostkach:
   - m² (dla działek < 100 m²)
   - ary (dla działek 100 m² - 1 ha)
   - hektary (dla działek ≥ 1 ha)

### Filtrowanie

Filtr kategorii w nagłówku sekcji:
- **Wszystkie kategorie** (domyślnie)
- **Rolne**
- **Budowlane**
- **Lasy**
- **Pastwiska**

## Przykładowy wygląd

```
TOP 50 Największych Działek                    [Filtr: Wszystkie kategorie ▼]

🥇 1.  Działka 100
       Jan Kowalski (link)                     1.25 ha

🥈 2.  Działka 201/1  
       Anna Nowak (link)                       0.99 ha

🥉 3.  Działka 45
       Piotr Wiśniewski (link)                 87.50 arów

4.   Działka 302
     Maria Kowalczyk (link)                    75.20 arów

5.   Działka 12
     Brak właściciela                          5,400 m²
```

## Backend - Endpoint API

### Nowe pole w `/api/stats`

```json
{
  "parcels_ranking": {
    "all": [
      {
        "parcel_number": "100",
        "kategoria": "rolna",
        "area_m2": 12500.5,
        "nazwa_wlasciciela": "Jan Kowalski",
        "unikalny_klucz": "JK001"
      }
    ],
    "rolna": [...],
    "budowlana": [...],
    "las": [...],
    "pastwisko": [...]
  }
}
```

### Zapytanie SQL

```sql
SELECT 
    o.nazwa_lub_numer as parcel_number,
    o.kategoria,
    COALESCE(ST_Area(o.geometria::geography), 0) as area_m2,
    w.nazwa_wlasciciela,
    w.unikalny_klucz
FROM obiekty_geograficzne o
LEFT JOIN dzialki_wlasciciele dw ON o.id = dw.obiekt_id
LEFT JOIN wlasciciele w ON dw.wlasciciel_id = w.id
WHERE o.geometria IS NOT NULL
ORDER BY area_m2 DESC
LIMIT 100;
```

## Frontend - JavaScript

### Nowe funkcje

1. **`loadParcelsRanking(parcelsData)`**
   - Inicjalizuje ranking działek
   - Podpina event listener do filtru kategorii

2. **`displayParcelsRanking(parcelsData, container)`**
   - Renderuje HTML listy rankingowej
   - Formatuje powierzchnię za pomocą `formatArea()`
   - Tworzy linki do protokołów właścicieli

### Integracja

Funkcja `loadParcelsRanking()` jest wywoływana w `loadStatistics()` po załadowaniu danych z API.

## Zmiany w plikach

### Zmodyfikowane:
- `backend/app.py` - dodano endpoint i ranking działek
- `wlasciciele/stats.html` - dodano sekcję HTML rankingu
- `wlasciciele/stats-script.js` - dodano funkcje JS
- `wlasciciele/stats-style.css` - poprawiono style nagłówków
- `backend/tests/test_stats_shape.py` - dodano testy dla parcels_ranking

## Użycie PostGIS

Ranking wykorzystuje PostGIS do obliczania powierzchni:
```sql
ST_Area(o.geometria::geography)
```

Konwersja `::geography` zapewnia dokładne obliczenia w metrach kwadratowych na podstawie rzeczywistych współrzędnych geograficznych.

## Cechy specjalne

✅ Top 50 największych działek  
✅ Filtrowanie według kategorii  
✅ Linki do protokołów właścicieli  
✅ Inteligentne formatowanie jednostek (m²/ary/ha)  
✅ Obsługa działek bez właściciela  
✅ Kolorowe oznaczenia podium (złoto/srebro/brąz)  
✅ Responsywny layout  

## Kompatybilność

- Współpracuje z istniejącym rankingiem właścicieli
- Używa tej samej funkcji `formatArea()` do formatowania
- Zachowuje spójny design z resztą aplikacji
- Nie wymaga dodatkowych zależności
