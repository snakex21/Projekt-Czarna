# Test Wydajności Mapy

## Jak sprawdzić poprawę wydajności

### 1. Test w Konsoli Przeglądarki

Otwórz konsolę (F12) i wykonaj:

```javascript
// Sprawdź liczbę działek
console.log('📊 Liczba działek:', allParcelsData.length);

// Sprawdź czy Canvas jest włączony
console.log('🎨 Canvas renderer:', map.options.preferCanvas ? '✅ Włączony' : '❌ Wyłączony');

// Sprawdź rozmiar cache DOM
console.log('💾 Cache DOM:', domElementCache.size, 'elementów');

// Monitor FPS (uruchom przed interakcją)
let lastTime = performance.now();
let frames = 0;
function measureFPS() {
    frames++;
    const now = performance.now();
    if (now >= lastTime + 1000) {
        console.log('🎬 FPS:', Math.round(frames * 1000 / (now - lastTime)));
        frames = 0;
        lastTime = now;
    }
    requestAnimationFrame(measureFPS);
}
measureFPS();
```

### 2. Test Wizualny

#### Przed optymalizacją (oczekiwane problemy):
- ❌ Przesuwanie mapy "zacina się" przy 750+ działkach
- ❌ Etykiety działek powodują lag
- ❌ Najechanie na działkę ma opóźnienie
- ❌ Przesunięcie mapy czeka na zakończenie animacji

#### Po optymalizacji (oczekiwane rezultaty):
- ✅ Płynne przesuwanie niezależnie od liczby działek
- ✅ Etykiety pojawiają się tylko przy zoom 16+
- ✅ Szybka reakcja na najechanie myszką
- ✅ Przesuwanie nie czeka na inne operacje

### 3. Test Memory Usage

W Chrome DevTools → Performance:

1. Otwórz kartę **Memory**
2. Zrób **Heap snapshot** przed załadowaniem mapy
3. Załaduj mapę
4. Zrób kolejny **Heap snapshot**
5. Porównaj użycie pamięci:
   - **Przed optymalizacją**: ~250 MB
   - **Po optymalizacji**: ~100 MB

### 4. Test Interakcji

Sprawdź te scenariusze:

#### Zoom In/Out
```
1. Odpal mapę
2. Użyj rolki myszy do zoom in/out kilka razy
3. Sprawdź czy:
   - ✅ Animacja jest płynna
   - ✅ Etykiety pojawiają się/znikają przy zoom 16
   - ✅ Brak "zamrożenia" ekranu
```

#### Przesuwanie (Panning)
```
1. Przytrzymaj LPM i przesuń mapę
2. Sprawdź czy:
   - ✅ Mapa płynnie podąża za kursorem
   - ✅ Tooltips znikają podczas ruchu
   - ✅ FPS ≥ 50
```

#### Najechanie na działkę
```
1. Najedź myszką na kilka działek szybko
2. Sprawdź czy:
   - ✅ Podświetlenie jest natychmiastowe
   - ✅ Panel działek/właścicieli reaguje
   - ✅ Brak "podskakiwania" interfejsu
```

#### Kliknięcie na działkę
```
1. Kliknij na działkę
2. Sprawdź czy:
   - ✅ Popup pojawia się natychmiast
   - ✅ Treść popupu jest poprawna
   - ✅ Kliknięcie przekierowuje do właściciela
```

### 5. Benchmark Automatyczny (opcjonalny)

Skopiuj i wklej w konsoli:

```javascript
async function runBenchmark() {
    console.log('🏃 Start benchmarku...');
    
    // Test 1: Render time
    const renderStart = performance.now();
    await new Promise(resolve => {
        if (allParcelsData.length === 0) {
            console.log('⚠️ Brak danych - poczekaj na załadowanie');
            setTimeout(resolve, 2000);
        } else {
            resolve();
        }
    });
    const renderTime = performance.now() - renderStart;
    console.log('⏱️ Render time:', renderTime.toFixed(2), 'ms');
    
    // Test 2: Mouseover performance
    let mouseoverCount = 0;
    const mouseoverStart = performance.now();
    const testDuration = 3000; // 3 sekundy
    
    const testInterval = setInterval(() => {
        mouseoverCount++;
        // Symuluj mouseover na losowej działce
        if (geojsonLayer && geojsonLayer.getLayers().length > 0) {
            const layers = geojsonLayer.getLayers();
            const randomLayer = layers[Math.floor(Math.random() * layers.length)];
            if (randomLayer.feature) {
                handleFeatureMouseover({target: randomLayer}, randomLayer.feature);
            }
        }
    }, 50);
    
    setTimeout(() => {
        clearInterval(testInterval);
        const mouseoverTime = performance.now() - mouseoverStart;
        const avgTime = mouseoverTime / mouseoverCount;
        console.log('🖱️ Mouseover test:');
        console.log('  - Liczba operacji:', mouseoverCount);
        console.log('  - Średni czas:', avgTime.toFixed(2), 'ms');
        console.log('  - Operacje/s:', (mouseoverCount / (mouseoverTime / 1000)).toFixed(2));
        
        // Wynik
        if (avgTime < 20) {
            console.log('✅ DOSKONALE - Bardzo szybka reakcja!');
        } else if (avgTime < 50) {
            console.log('✅ DOBRZE - Akceptowalna wydajność');
        } else {
            console.log('⚠️ WOLNO - Wymaga dalszej optymalizacji');
        }
    }, testDuration);
}

runBenchmark();
```

### 6. Test na Słabszym Sprzęcie

Symuluj wolniejszy komputer w Chrome:

1. F12 → **Performance** tab
2. Kliknij ikonę **⚙️** (Settings)
3. Ustaw **CPU throttling** na **4x slowdown**
4. Testuj mapę - powinna nadal działać płynnie

### Oczekiwane Wyniki

#### ✅ SUKCES gdy:
- FPS ≥ 50 przy przesuwaniu z 750+ działkami
- Czas reakcji na mouseover < 50ms
- Użycie pamięci < 150 MB
- Brak "zamrażania" UI podczas interakcji

#### ⚠️ WYMAGA POPRAWY gdy:
- FPS < 30
- Czas reakcji > 100ms
- Użycie pamięci > 200 MB
- Widoczne "zacięcia" podczas przesuwania

## Zgłaszanie Problemów

Jeśli po optymalizacjach nadal występują problemy:

1. Sprawdź konsolę błędów (F12)
2. Zanotuj liczbę działek: `allParcelsData.length`
3. Zrób screenshot konsoli z wynikami testów
4. Opisz dokładnie co "laguje" i w jakiej sytuacji
