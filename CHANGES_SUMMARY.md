# Podsumowanie zmian - Statystyki powierzchni działek i ranking właścicieli

## Zaimplementowane funkcjonalności

### 1. Statystyki powierzchni działek w zakładce "Przegląd"
- **Łączna powierzchnia** - wyświetlana w hektarach (ha)
- **Średnia powierzchnia** - wyświetlana w arach
- **Najmniejsza działka** - w metrach kwadratowych (m²)
- **Największa działka** - w hektarach lub m² (dynamicznie)

### 2. Ranking właścicieli według powierzchni
- Dodano nowy **przełącznik sortowania** w zakładce "Rankingi":
  - **Liczba działek** (domyślnie) - sortowanie według ilości posiadanych działek
  - **Powierzchnia** - sortowanie według łącznej powierzchni działek
  
### 3. Rozszerzone informacje w rankingu
- **Numery działek** - wyświetlane przy każdym właścicielu (pierwsze 5, jeśli więcej to "...")
- **Link do protokołu** - cała pozycja rankingu jest klikalnym linkiem do protokołu właściciela
- **Dynamiczne wyświetlanie wartości**:
  - Przy sortowaniu po liczbie: główna wartość = liczba działek, dodatkowa = powierzchnia
  - Przy sortowaniu po powierzchni: główna wartość = powierzchnia, dodatkowa = liczba działek

## Zmiany techniczne

### Backend (`backend/app.py`)

#### 1. Nowe pole w zapytaniu rankingowym:
```python
COALESCE(SUM(ST_Area(o.geometria::geography)), 0) as total_area_m2,
json_agg(o.nazwa_lub_numer ORDER BY o.nazwa_lub_numer) as plot_numbers
```

#### 2. Nowe statystyki powierzchni:
```python
area_stats = {
    'total_area_m2': float,
    'total_area_ha': float,
    'total_area_ares': float,
    'avg_area_m2': float,
    'avg_area_ha': float,
    'avg_area_ares': float,
    'min_area_m2': float,
    'max_area_m2': float
}
```

### Frontend

#### HTML (`wlasciciele/stats.html`)
- Dodano nową kartę "Powierzchnia działek" w zakładce "Przegląd"
- Dodano przełącznik "Sortowanie" w zakładce "Rankingi"

#### JavaScript (`wlasciciele/stats-script.js`)
- `updateAreaStats()` - funkcja aktualizująca wyświetlanie statystyk powierzchni
- `formatArea()` - funkcja formatująca powierzchnię z automatycznym doborem jednostek (m²/ary/ha)
- `displayRanking()` - rozszerzona o wyświetlanie powierzchni i numerów działek
- `filterRankings()` - rozszerzona o sortowanie według powierzchni
- `getTop10Owners()` - rozszerzona o sortowanie według powierzchni dla funkcji "Pokaż TOP 10 na mapie"

## Przykładowy output API

Zobacz plik `test_stats_output.json` dla przykładowej struktury danych zwracanych przez API `/api/stats`.

## Użyte jednostki powierzchni

1. **Metry kwadratowe (m²)** - dla małych działek (< 100 m²)
2. **Ary** - dla średnich działek (100 m² - 1 ha), gdzie 1 ar = 100 m²
3. **Hektary (ha)** - dla dużych działek (≥ 1 ha), gdzie 1 ha = 10 000 m²

## Kompatybilność

- Wykorzystuje PostGIS `ST_Area(geometria::geography)` dla dokładnych obliczeń powierzchni
- Wszystkie dotychczasowe funkcjonalności zachowane bez zmian
- Ranking działa z istniejącymi filtrami (typ własności, kategoria)
