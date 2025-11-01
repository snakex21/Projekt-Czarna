# Funkcjonalność: Statystyki Powierzchni Działek i Ranking Właścicieli

## Przegląd

Dodano kompleksowy system statystyk powierzchni działek oraz ranking właścicieli według łącznej powierzchni ich posiadłości w module "Centrum Analityczne" (`stats.html`).

## Funkcje dla użytkownika

### 1. Statystyki Powierzchni (zakładka "Przegląd")

W zakładce "Przegląd" dodano nową kartę wyświetlającą:

- **Łączna powierzchnia** - suma powierzchni wszystkich działek (w hektarach)
- **Średnia powierzchnia** - średnia wielkość działki (w arach)
- **Najmniejsza działka** - najmniejsza zmierzona powierzchnia (w m²)
- **Największa działka** - największa zmierzona powierzchnia (w ha lub m²)

### 2. Ranking według Powierzchni (zakładka "Rankingi")

Dodano nowy przełącznik **"Sortowanie"** z opcjami:

- **Liczba działek** (domyślnie) - tradycyjne sortowanie według ilości posiadanych działek
- **Powierzchnia** - sortowanie według łącznej powierzchni wszystkich działek właściciela

### 3. Rozszerzone Informacje w Rankingu

Każda pozycja rankingu zawiera teraz:

- **Nazwę właściciela** - z linkiem do protokołu
- **Numer protokołu** - identyfikator dokumentu właściciela
- **Numery działek** - lista działek należących do właściciela (np. "12, 13, 14, 15, 16...")
- **Główną wartość** - liczba działek lub powierzchnia (zależnie od sortowania)
- **Wartość dodatkową** - powierzchnia lub liczba działek (jako uzupełnienie)

### 4. Integracja z Mapą

Przycisk **"Pokaż TOP 10 na mapie"** respektuje wybrane sortowanie:
- Przy sortowaniu po liczbie działek: pokazuje właścicieli z największą liczbą działek
- Przy sortowaniu po powierzchni: pokazuje właścicieli z największą łączną powierzchnią

## Jednostki Powierzchni

System automatycznie dobiera najbardziej czytelną jednostkę:

| Powierzchnia | Jednostka | Przykład |
|--------------|-----------|----------|
| < 100 m² | metry kwadratowe | 85 m² |
| 100 m² - 1 ha | ary | 12.50 arów |
| ≥ 1 ha | hektary | 5.75 ha |

**Przeliczniki:**
- 1 ar = 100 m²
- 1 hektar (ha) = 100 arów = 10,000 m²

## Techniczne Szczegóły

### API Endpoint: `/api/stats`

Dodano nowe pola w odpowiedzi JSON:

```json
{
  "area_stats": {
    "total_area_m2": 5234500.75,
    "total_area_ha": 523.45,
    "total_area_ares": 52345.01,
    "avg_area_m2": 11760.34,
    "avg_area_ha": 1.176,
    "avg_area_ares": 117.6,
    "min_area_m2": 125.5,
    "max_area_m2": 85000.0
  },
  "rankings_real": {
    "all_plots": [
      {
        "nazwa_wlasciciela": "Jan Kowalski",
        "plot_count": 25,
        "total_area_m2": 125000.5,
        "plot_numbers": ["12", "13", "14", "15", "16"]
      }
    ]
  }
}
```

### Obliczanie Powierzchni

- Wykorzystuje PostGIS funkcję `ST_Area(geometria::geography)`
- Obliczenia w rzeczywistych jednostkach geograficznych (metry)
- Dokładność zależna od jakości danych geometrycznych w bazie

### Testowanie

Zaktualizowane testy w `backend/tests/`:
- `test_stats.py` - podstawowe testy endpointu
- `test_stats_shape.py` - weryfikacja struktury danych i nowych pól

Uruchomienie testów:
```bash
cd backend
pytest tests/test_stats*.py -v
```

## Kompatybilność

- ✅ Zachowana pełna kompatybilność z istniejącymi funkcjami
- ✅ Wszystkie dotychczasowe filtry działają poprawnie
- ✅ Motyw jasny/ciemny wspierany
- ✅ Responsywny design dla różnych rozdzielczości

## Przykładowe Użycie

1. **Znajdź właściciela z największą powierzchnią:**
   - Otwórz "Centrum Analityczne" (stats.html)
   - Przejdź do zakładki "Rankingi"
   - Wybierz "Sortowanie: Powierzchnia"
   - Zobacz TOP 50 właścicieli według powierzchni

2. **Sprawdź statystyki powierzchni:**
   - W zakładce "Przegląd"
   - Zobacz kartę "Powierzchnia działek"
   - Poznaj łączną powierzchnię wszystkich działek

3. **Pokaż największych właścicieli na mapie:**
   - W zakładce "Rankingi"
   - Wybierz sortowanie według powierzchni
   - Kliknij "Pokaż TOP 10 na mapie"
   - Zostaniesz przekierowany do mapy z podświetlonymi działkami
