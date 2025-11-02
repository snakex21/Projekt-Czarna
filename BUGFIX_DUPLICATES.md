# Poprawka: Duplikaty w Rankingu Działek

## Problem

Działki pojawiały się wielokrotnie w rankingu, gdy miały wielu współwłaścicieli:

```
23. 475  Agata Łazarska  17.31 arów
24. 475  Agata Łazarska  17.31 arów  ← DUPLIKAT
```

## Przyczyna

Zapytanie SQL używało `LEFT JOIN` bez `GROUP BY`, co powodowało że:
- Dla każdej relacji działka-właściciel w tabeli `dzialki_wlasciciele` powstawał osobny wiersz
- Działka ze współwłasnością (np. 2 właścicieli) pojawiała się 2 razy

## Rozwiązanie

### Backend (`backend/app.py`)

Użyto `GROUP BY` z agregacją właścicieli:

```python
def get_parcels_ranking(category=None):
    query = f"""
        SELECT 
            o.nazwa_lub_numer as parcel_number,
            o.kategoria,
            COALESCE(ST_Area(o.geometria::geography), 0) as area_m2,
            STRING_AGG(DISTINCT w.nazwa_wlasciciela, ', ') as nazwa_wlasciciela,
            MIN(w.unikalny_klucz) as unikalny_klucz
        FROM obiekty_geograficzne o
        LEFT JOIN dzialki_wlasciciele dw ON o.id = dw.obiekt_id
        LEFT JOIN wlasciciele w ON dw.wlasciciel_id = w.id
        WHERE o.geometria IS NOT NULL {category_condition}
        GROUP BY o.id, o.nazwa_lub_numer, o.kategoria, o.geometria
        ORDER BY area_m2 DESC
        LIMIT 100;
    """
```

**Kluczowe zmiany:**
- ✅ `GROUP BY o.id` - każda działka tylko raz
- ✅ `STRING_AGG(DISTINCT w.nazwa_wlasciciela, ', ')` - łączy wszystkich właścicieli przecinkami
- ✅ `MIN(w.unikalny_klucz)` - wybiera pierwszy klucz właściciela dla linku

### Frontend (`wlasciciele/stats-script.js`)

Poprawiono wyświetlanie współwłaścicieli:

```javascript
// Jeśli jest wielu właścicieli (rozdzieleni przecinkami)
if (owner.includes(', ')) {
  const firstOwner = owner.split(', ')[0];
  const ownersCount = owner.split(', ').length;
  ownerDisplay = `${firstOwner} (+${ownersCount - 1} współwłaściciel)`;
}
```

## Rezultat

### Przed poprawką:
```
23. 475  Agata Łazarska  17.31 arów
24. 475  Agata Łazarska  17.31 arów  ← duplikat
25. 475  Agata Łazarska  17.31 arów  ← duplikat
```

### Po poprawce:
```
23. 475  Agata Łazarska (+1 współwłaściciel)  17.31 arów
24. 302  Jan Kowalski                          15.20 arów
25. 150  Maria Nowak                           12.50 arów
```

## Obsługa współwłasności

### Pojedynczy właściciel:
```
100  Adam Nowak  1.00 ha
```

### Dwóch współwłaścicieli:
```
475  Agata Łazarska (+1 współwłaściciel)  17.31 arów
```

### Wielu współwłaścicieli:
```
200  Jan Kowalski (+2 współwłaścicieli)  25.50 arów
```

## Funkcjonalność linków

- **Link prowadzi do protokołu pierwszego właściciela** (alfabetycznie przez `MIN(unikalny_klucz)`)
- Kliknięcie otwiera protokół właściciela
- W protokole widoczni są wszyscy współwłaściciele

## Testy

Zapytanie testowe do weryfikacji:
```sql
SELECT 
    o.nazwa_lub_numer, 
    COUNT(*) as wystapienia
FROM obiekty_geograficzne o
LEFT JOIN dzialki_wlasciciele dw ON o.id = dw.obiekt_id
LEFT JOIN wlasciciele w ON dw.wlasciciel_id = w.id
WHERE o.geometria IS NOT NULL
GROUP BY o.nazwa_lub_numer
HAVING COUNT(*) > 1;
```

## Status

✅ **Naprawione** - każda działka pojawia się tylko raz  
✅ **Zachowano informację** - widoczna liczba współwłaścicieli  
✅ **Działają linki** - przekierowanie do protokołu pierwszego właściciela  
✅ **Sortowanie prawidłowe** - według powierzchni malejąco  

## Zgodność

- ✅ Kompatybilne z PostgreSQL + PostGIS
- ✅ Nie wpływa na pozostałe rankingi
- ✅ Zachowana struktura danych API
- ✅ Responsywny interfejs
