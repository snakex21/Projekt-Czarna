/**
 * ============================================================================
 * Edytor Działek — MapLibre GL + mapbox-gl-draw
 * Przepisanie z Leaflet.PM na MapLibre GL (maj 2026)
 * ============================================================================
 */

document.addEventListener("DOMContentLoaded", function () {

  // ==========================================================================
  // 1. UI: THEME, DATA/CZAS, EXIT MODAL
  // ==========================================================================

  const savedTheme = localStorage.getItem('parcelEditorTheme');
  if (savedTheme === 'dark') {
    document.body.classList.add('dark-mode');
    const tb = document.getElementById('themeToggle');
    if (tb) tb.innerHTML = '<i class="fas fa-sun"></i>';
  }

  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      document.body.classList.toggle('dark-mode');
      const isDark = document.body.classList.contains('dark-mode');
      themeToggle.innerHTML = isDark ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
      localStorage.setItem('parcelEditorTheme', isDark ? 'dark' : 'light');
    });
  }

  const updateDateTime = () => {
    const now = new Date();
    const dEl = document.getElementById('currentDate');
    const tEl = document.getElementById('currentTime');
    if (dEl) dEl.textContent = now.toLocaleDateString('pl-PL', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    if (tEl) tEl.textContent = now.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
  };
  updateDateTime();
  setInterval(updateDateTime, 1000);

  // Exit modal
  const exitBtn = document.getElementById('exitServerBtn');
  const exitModal = document.getElementById('exitModal');
  const confirmExitBtn = document.getElementById('confirmExitBtn');
  const cancelExitBtn = document.getElementById('cancelExitBtn');
  if (exitBtn && exitModal) exitBtn.addEventListener('click', () => exitModal.classList.remove('hidden'));
  if (cancelExitBtn) cancelExitBtn.addEventListener('click', () => exitModal.classList.add('hidden'));
  if (exitModal) exitModal.addEventListener('click', e => { if (e.target === exitModal) exitModal.classList.add('hidden'); });
  if (confirmExitBtn) {
    confirmExitBtn.addEventListener('click', async () => {
      confirmExitBtn.disabled = true;
      confirmExitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Zamykanie...';
      try {
        let response = await fetch('/shutdown', { method: 'POST' });
        if (!response.ok) {
          response = await fetch('/api/shutdown', { method: 'POST' });
        }
        if (response.ok) {
          setTimeout(() => {
            document.body.innerHTML = `
              <div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#0f172a;color:#e2e8f0;font-family:Inter,sans-serif;flex-direction:column;">
                <i class="fas fa-check-circle" style="font-size:4rem;color:#48bb78;margin-bottom:1rem;"></i>
                <h1 style="margin-bottom:0.5rem;">Serwer zamknięty</h1>
                <p style="color:#94a3b8;">Ta karta zamknie się automatycznie...</p>
                <p style="color:#64748b;font-size:0.85rem;margin-top:1rem;">Zamykanie za <span id="countdown">3</span>s</p>
              </div>
            `;
            let countdown = 3;
            const countdownEl = document.getElementById('countdown');
            const timer = setInterval(() => {
              countdown--;
              if (countdownEl) countdownEl.textContent = countdown;
              if (countdown <= 0) {
                clearInterval(timer);
                window.close();
                setTimeout(() => {
                  document.body.innerHTML = `
                    <div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#0f172a;color:#e2e8f0;font-family:Inter,sans-serif;flex-direction:column;">
                      <i class="fas fa-check-circle" style="font-size:4rem;color:#48bb78;margin-bottom:1rem;"></i>
                      <h1>Serwer zamknięty</h1>
                      <p style="color:#94a3b8;">Możesz zamknąć tę kartę.</p>
                    </div>`;
                }, 1000);
              }
            }, 1000);
          }, 300);
        }
      } catch (err) {
        document.body.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#0f172a;color:#e2e8f0;font-family:Inter,sans-serif;flex-direction:column;">
            <i class="fas fa-check-circle" style="font-size:4rem;color:#48bb78;margin-bottom:1rem;"></i>
            <h1>Serwer zamknięty</h1>
            <p style="color:#94a3b8;">Możesz zamknąć tę kartę.</p>
          </div>`;
      }
    });
  }

  // ==========================================================================
  // 2. STAN APLIKACJI
  // ==========================================================================
  let currentParcelsData = {};
  let currentCategory = null;
  let editingParcelId = null;

  // Kategorie punktowe i liniowe
  const POINT_CATEGORIES = ['budynek', 'kapliczka', 'obiekt_specjalny', 'dworzec'];
  const LINE_CATEGORIES = ['droga', 'rzeka', 'obrys_miejscowosci'];
  const POLYGON_CATEGORIES = ['budowlana', 'rolna', 'las', 'pastwisko'];
  const LAND_CATEGORIES = ['rolna', 'droga', 'las', 'pastwisko', 'rzeka'];

  // ==========================================================================
  // 3. INICJALIZACJA MAPY MAPLIBRE GL
  // ==========================================================================

  const mapCalibration = window.MAP_CONFIG.calibration;
  const mapDefaults = window.MAP_CONFIG.defaults;

  // Bounds w formacie MapLibre: [[south, west], [north, east]]
  const mLatPad = (mapCalibration.ne.lat - mapCalibration.sw.lat) * 0.5;
  const mLngPad = (mapCalibration.ne.lng - mapCalibration.sw.lng) * 0.8;
  const maxBounds = [
    [mapCalibration.sw.lng - mLngPad, mapCalibration.sw.lat - mLatPad],
    [mapCalibration.ne.lng + mLngPad, mapCalibration.ne.lat + mLatPad]
  ];

  // Definicje stylów kategorii
  const CATEGORY_STYLES = {
    budowlana:  { fill: '#e67e22', stroke: '#d35400', opacity: 0.40, width: 2, type: 'polygon' },
    rolna:      { fill: '#27ae60', stroke: '#1e8449', opacity: 0.40, width: 2, type: 'polygon' },
    las:        { fill: '#1abc9c', stroke: '#16a085', opacity: 0.45, width: 1, type: 'polygon' },
    pastwisko:  { fill: '#f1c40f', stroke: '#d4ac0d', opacity: 0.45, width: 1, type: 'polygon' },
    droga:      { fill: '#8B4513', stroke: '#8B4513', opacity: 0.70, width: 3, type: 'line' },
    rzeka:      { fill: '#3498db', stroke: '#3498db', opacity: 0.80, width: 4, type: 'line' },
    obrys_miejscowosci: { fill: 'transparent', stroke: '#ff0000', opacity: 0.90, width: 3, type: 'line', dash: [10, 5] },
    budynek:    { fill: '#9b59b6', stroke: '#8e44ad', opacity: 0.60, radius: 6, type: 'point' },
    kapliczka:  { fill: '#e74c3c', stroke: '#c0392b', opacity: 0.60, radius: 6, type: 'point' },
    obiekt_specjalny: { fill: '#2c3e50', stroke: '#1a252f', opacity: 0.60, radius: 7, type: 'point' },
    dworzec:    { fill: '#e67e22', stroke: '#d35400', opacity: 0.60, radius: 7, type: 'point' },
  };

  // MapLibre style inline
  const mapStyle = {
    version: 8,
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    sources: {
      'osm-tiles': {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '&copy; OpenStreetMap',
        maxzoom: 21
      },
      'historical-map': {
        type: 'image',
        url: '/static/mapa.jpg',
        coordinates: [
          [mapCalibration.sw.lng, mapCalibration.ne.lat],
          [mapCalibration.ne.lng, mapCalibration.ne.lat],
          [mapCalibration.ne.lng, mapCalibration.sw.lat],
          [mapCalibration.sw.lng, mapCalibration.sw.lat]
        ]
      },
      'parcels': {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }
      }
    },
    layers: [
      // Background
      { id: 'background', type: 'background', paint: { 'background-color': '#f0f0f0' } },
      // OSM tiles (domyślnie włączone)
      { id: 'osm-layer', type: 'raster', source: 'osm-tiles', layout: { visibility: 'visible' } },
      // Historical map overlay
      { id: 'historical-layer', type: 'raster', source: 'historical-map', paint: { 'raster-opacity': 1.0, 'raster-fade-duration': 0 } },
      // Polygon fills - kategorie powierzchniowe
      { id: 'parcels-fill',
        type: 'fill', source: 'parcels',
        filter: ['in', ['get', 'kategoria'], ['literal', ['budowlana', 'rolna', 'las', 'pastwisko']]],
        paint: {
          'fill-color': [
            'match', ['get', 'kategoria'],
            'budowlana', '#e67e22',
            'rolna', '#27ae60',
            'las', '#1abc9c',
            'pastwisko', '#f1c40f',
            '#3388ff'
          ],
          'fill-opacity': 0.40,
          'fill-antialias': false,
          'fill-outline-color': '#000'
        }
      },
      // Polygon outlines
      { id: 'parcels-outline',
        type: 'line', source: 'parcels',
        filter: ['in', ['get', 'kategoria'], ['literal', ['budowlana', 'rolna', 'las', 'pastwisko']]],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': ['match', ['get', 'kategoria'],
            'budowlana', '#d35400', 'rolna', '#1e8449',
            'las', '#16a085', 'pastwisko', '#d4ac0d', '#000'],
          'line-width': 2
        }
      },
      // Line features (drogi, rzeki)
      { id: 'parcels-line',
        type: 'line', source: 'parcels',
        filter: ['in', ['get', 'kategoria'], ['literal', ['droga', 'rzeka']]],
        paint: {
          'line-color': ['match', ['get', 'kategoria'],
            'droga', '#8B4513', 'rzeka', '#3498db', '#000'],
          'line-width': ['match', ['get', 'kategoria'],
            'droga', 3, 'rzeka', 4, 2]
        }
      },
      // Obrys miejscowosci (dashed)
      { id: 'parcels-boundary',
        type: 'line', source: 'parcels',
        filter: ['==', ['get', 'kategoria'], 'obrys_miejscowosci'],
        paint: {
          'line-color': '#ff0000',
          'line-width': 3,
          'line-dasharray': [10, 5]
        }
      },
      // Point features (domy, kapliczki, obiekty)
      { id: 'parcels-point',
        type: 'circle', source: 'parcels',
        filter: ['in', ['get', 'kategoria'], ['literal', ['budynek', 'kapliczka', 'obiekt_specjalny', 'dworzec']]],
        paint: {
          'circle-radius': ['match', ['get', 'kategoria'],
            'budynek', 6, 'kapliczka', 6, 'obiekt_specjalny', 7, 'dworzec', 7, 6],
          'circle-color': ['match', ['get', 'kategoria'],
            'budynek', '#9b59b6', 'kapliczka', '#e74c3c', 'obiekt_specjalny', '#2c3e50', 'dworzec', '#e67e22', '#000'],
          'circle-opacity': 0.85,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#fff'
        }
      },
      // Point labels
      { id: 'parcels-labels',
        type: 'symbol', source: 'parcels',
        filter: ['in', ['get', 'kategoria'], ['literal', ['budynek', 'kapliczka', 'obiekt_specjalny', 'dworzec']]],
        layout: {
          'text-field': ['get', 'numer'],
          'text-size': 11,
          'text-offset': [0, -1.5],
          'text-anchor': 'bottom'
        },
        paint: {
          'text-color': '#000',
          'text-halo-color': '#fff',
          'text-halo-width': 1.5
        }
      }
    ]
  };

  const map = new maplibregl.Map({
    container: 'map',
    style: mapStyle,
    center: [mapDefaults.center.lng, mapDefaults.center.lat],
    zoom: mapDefaults.zoom,
    maxBounds: maxBounds,
    minZoom: 10,
    maxZoom: 21,
    attributionControl: false
  });

  // Warstwy toggle
  const osmVisibility = { visible: true };
  const histVisibility = { visible: true };

  const layerToggle = document.createElement('div');
  layerToggle.className = 'maplibregl-ctrl maplibregl-ctrl-group layer-toggle-panel';
  layerToggle.innerHTML = `
    <button id="toggle-osm" class="layer-toggle-btn active" title="Mapa drogowa (OSM)">
      <span class="layer-toggle-icon">🗺️</span><span class="layer-toggle-label">OSM</span><span class="toggle-indicator on">ON</span>
    </button>
    <button id="toggle-hist" class="layer-toggle-btn active" title="Mapa historyczna">
      <span class="layer-toggle-icon">📜</span><span class="layer-toggle-label">Historyczna</span><span class="toggle-indicator on">ON</span>
    </button>`;
  map.getContainer().appendChild(layerToggle);

  document.getElementById('toggle-osm').addEventListener('click', function () {
    osmVisibility.visible = !osmVisibility.visible;
    map.setLayoutProperty('osm-layer', 'visibility', osmVisibility.visible ? 'visible' : 'none');
    this.classList.toggle('active', osmVisibility.visible);
    this.querySelector('.toggle-indicator').textContent = osmVisibility.visible ? 'ON' : 'OFF';
    this.querySelector('.toggle-indicator').className = 'toggle-indicator ' + (osmVisibility.visible ? 'on' : 'off');
  });

  document.getElementById('toggle-hist').addEventListener('click', function () {
    histVisibility.visible = !histVisibility.visible;
    map.setLayoutProperty('historical-layer', 'visibility', histVisibility.visible ? 'visible' : 'none');
    this.classList.toggle('active', histVisibility.visible);
    this.querySelector('.toggle-indicator').textContent = histVisibility.visible ? 'ON' : 'OFF';
    this.querySelector('.toggle-indicator').className = 'toggle-indicator ' + (histVisibility.visible ? 'on' : 'off');
  });

  // Kontrolka współrzędnych
  const coordDiv = document.createElement('div');
  coordDiv.className = 'coord-display';
  coordDiv.innerHTML = 'Najedź na mapę...';
  map.getContainer().appendChild(coordDiv);
  map.on('mousemove', (e) => {
    coordDiv.innerHTML = `Lat: ${e.lngLat.lat.toFixed(6)}<br>Lng: ${e.lngLat.lng.toFixed(6)}`;
  });
  map.on('mouseout', () => { coordDiv.innerHTML = 'Najedź na mapę...'; });

  // Nawigacja
  map.addControl(new maplibregl.NavigationControl(), 'top-left');

  // ==========================================================================
  // 4. MAPBOX-GL-DRAW
  // ==========================================================================

  const draw = new MapboxDraw({
    displayControlsDefault: false,
    controls: {},  // Ukrywamy domyślne kontrolki, mamy własne
    defaultMode: 'simple_select',
    styles: [
      // Punkty
      { id: 'gl-draw-point', type: 'circle', paint: { 'circle-radius': 6, 'circle-color': '#ff00ff' } },
      { id: 'gl-draw-point-stroke', type: 'circle', paint: { 'circle-radius': 8, 'circle-color': '#fff' } },
      // Linie
      { id: 'gl-draw-line', type: 'line', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#ff00ff', 'line-width': 2 } },
      // Wielokąty
      { id: 'gl-draw-polygon-fill', type: 'fill', paint: { 'fill-color': '#ff00ff', 'fill-opacity': 0.2 } },
      { id: 'gl-draw-polygon-stroke', type: 'line', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#ff00ff', 'line-width': 2 } },
      // Wierzchołki
      { id: 'gl-draw-polygon-midpoint', type: 'circle', paint: { 'circle-radius': 3, 'circle-color': '#ff00ff' } },
      // Aktywne wierzchołki
      { id: 'gl-draw-polygon-and-line-vertex-active', type: 'circle', paint: { 'circle-radius': 6, 'circle-color': '#ff00ff', 'circle-stroke-width': 2, 'circle-stroke-color': '#fff' } },
      // Nieaktywne wierzchołki
      { id: 'gl-draw-polygon-and-line-vertex-inactive', type: 'circle', paint: { 'circle-radius': 4, 'circle-color': '#ff00ff', 'circle-stroke-width': 1, 'circle-stroke-color': '#fff' } },
      // Highlight vertex
      { id: 'gl-draw-polygon-and-line-vertex-hover', type: 'circle', paint: { 'circle-radius': 8, 'circle-color': '#ff00ff', 'circle-stroke-width': 3, 'circle-stroke-color': '#fff' } }
    ]
  });
  map.addControl(draw);

  // Ukryj domyślne przyciski draw (są brzydkie) — mapbox-gl-draw i tak ich nie ma przy controls:{}
  // Obsługa zdarzeń draw
  map.on('draw.create', handleDrawCreate);
  map.on('draw.update', handleDrawUpdate);
  map.on('draw.selectionchange', handleDrawSelectionChange);

  // ==========================================================================
  // 5. POMOCNICZE - KONWERSJA WSPÓŁRZĘDNYCH
  // ==========================================================================

  /**
   * Konwertuje geometrię z formatu API [lat, lng] na GeoJSON [lng, lat].
   */
  function sameCoord(a, b) {
    return Array.isArray(a) && Array.isArray(b) && a.length >= 2 && b.length >= 2 &&
      Number(a[0]) === Number(b[0]) && Number(a[1]) === Number(b[1]);
  }

  function cleanLngLatCoordinates(coords) {
    const cleaned = [];
    coords.forEach(c => {
      if (!Array.isArray(c) || c.length < 2) return;
      const normalized = [Number(c[0]), Number(c[1])];
      if (!Number.isFinite(normalized[0]) || !Number.isFinite(normalized[1])) return;
      if (!cleaned.length || !sameCoord(cleaned[cleaned.length - 1], normalized)) {
        cleaned.push(normalized);
      }
    });
    return cleaned;
  }

  function closePolygonRing(coords) {
    const ring = cleanLngLatCoordinates(coords);
    if (ring.length < 3) return null;
    if (!sameCoord(ring[0], ring[ring.length - 1])) {
      // GeoJSON wymaga zamkniętego pierścienia. Bez tego MapLibre przy
      // większym zoomie potrafi triangulować wypełnienie z widocznymi
      // trójkątnymi „dziurami”/odsłonięciami mapy pod spodem.
      ring.push([...ring[0]]);
    }
    return ring.length >= 4 ? ring : null;
  }

  function apiToGeoJSON(geometria, kategoria, numer) {
    if (!geometria || !geometria.length) return null;

    const cat = String(kategoria || '').toLowerCase();
    const isPoint = POINT_CATEGORIES.includes(cat);
    const isPointGeom = Array.isArray(geometria) && typeof geometria[0] === 'number' && typeof geometria[1] === 'number';

    if (isPoint || isPointGeom) {
      const pt = isPointGeom ? geometria : geometria[0];
      return {
        type: 'Feature',
        properties: { kategoria: kategoria, numer: numer },
        geometry: { type: 'Point', coordinates: [pt[1], pt[0]] }
      };
    } else if (LINE_CATEGORIES.includes(cat)) {
      const lineCoords = cleanLngLatCoordinates(geometria.map(p => [p[1], p[0]]));
      if (lineCoords.length < 2) return null;
      return {
        type: 'Feature',
        properties: { kategoria: kategoria, numer: numer },
        geometry: {
          type: 'LineString',
          coordinates: lineCoords
        }
      };
    } else {
      const ring = closePolygonRing(geometria.map(p => [p[1], p[0]]));
      if (!ring) return null;
      return {
        type: 'Feature',
        properties: { kategoria: kategoria, numer: numer },
        geometry: {
          type: 'Polygon',
          coordinates: [ring]
        }
      };
    }
  }

  /**
   * Konwertuje geometrię z GeoJSON [lng, lat] na format API [lat, lng].
   */
  function geoJSONToApi(geometry) {
    if (geometry.type === 'Point') {
      return [geometry.coordinates[1], geometry.coordinates[0]];
    } else if (geometry.type === 'LineString') {
      return geometry.coordinates.map(c => [c[1], c[0]]);
    } else if (geometry.type === 'Polygon') {
      const ring = geometry.coordinates[0] || [];
      const withoutClosingPoint = ring.length > 1 && sameCoord(ring[0], ring[ring.length - 1])
        ? ring.slice(0, -1)
        : ring;
      return withoutClosingPoint.map(c => [c[1], c[0]]);
    }
    return [];
  }

  // ==========================================================================
  // 6. POMOCNICZE - WYŚWIETLANIE
  // ==========================================================================

  function getDisplayId(fullKey, category) {
    if (category) {
      const suffix = `_${category}`;
      if (fullKey.endsWith(suffix)) return fullKey.substring(0, fullKey.length - suffix.length);
    }
    if (currentParcelsData[fullKey]) {
      const cat = currentParcelsData[fullKey].kategoria;
      if (cat) {
        const suffix = `_${cat}`;
        if (fullKey.endsWith(suffix)) return fullKey.substring(0, fullKey.length - suffix.length);
      }
    }
    const lastUnderscore = fullKey.lastIndexOf('_');
    if (lastUnderscore > 0) return fullKey.substring(0, lastUnderscore);
    return fullKey;
  }

  function formatCategoryName(cat) {
    return (cat || 'Brak danych').replace(/_/g, ' ');
  }

  /**
   * Odświeża źródło GeoJSON działek na mapie.
   */
  function refreshParcelsSource() {
    const features = [];
    Object.entries(currentParcelsData).forEach(([id, data]) => {
      const displayId = getDisplayId(id);
      const feat = apiToGeoJSON(data.geometria, data.kategoria, displayId);
      if (feat) {
        feat.id = id;
        features.push(feat);
      }
    });
    const src = map.getSource('parcels');
    if (src) src.setData({ type: 'FeatureCollection', features: features });
  }

  // ==========================================================================
  // 7. RYSOWANIE NOWYCH OBIEKTÓW
  // ==========================================================================

  const createActions = document.getElementById('create-actions');
  const dynamicActions = document.getElementById('dynamic-actions');

  // Uzupełnienie przycisków (domy, obiekt specjalny, obrys)
  (function ensureButtons() {
    if (!createActions) return;
    const existing = new Set();
    createActions.querySelectorAll('[data-category]').forEach(b => existing.add(b.dataset.category));
    const needed = { budynek: 'Dodaj dom', obiekt_specjalny: 'Dodaj obiekt spec.', obrys_miejscowosci: 'Dodaj obrys' };
    for (const [cat, label] of Object.entries(needed)) {
      if (!existing.has(cat)) {
        const b = document.createElement('button');
        b.textContent = label; b.dataset.category = cat;
        createActions.appendChild(b);
      }
    }
  })();

  if (createActions) {
    createActions.addEventListener('click', (ev) => {
      const btn = ev.target.closest('button[data-category]');
      if (!btn) return;
      ev.preventDefault();
      enterDrawingMode(btn.dataset.category);
    });
  }

  function enterDrawingMode(category) {
    currentCategory = category;

    // Podświetl aktywny przycisk
    if (createActions) {
      createActions.querySelectorAll('button[data-category]').forEach(b =>
        b.classList.toggle('active', b.dataset.category === String(category))
      );
    }
    createActions.style.display = 'none';

    const displayCat = formatCategoryName(category);
    const isPoint = POINT_CATEGORIES.includes(String(category).toLowerCase());
    const isLine = LINE_CATEGORIES.includes(String(category).toLowerCase());

    dynamicActions.innerHTML = isPoint
      ? `<span class="toolbar-label">Rysujesz: ${displayCat}</span>
         <button id="cancel-draw-btn" class="action-cancel">Anuluj</button>`
      : `<span class="toolbar-label">Rysujesz: ${displayCat}</span>
         <button id="undo-draw-btn" class="action-undo">Cofnij Punkt</button>
         <button id="finish-draw-btn" class="action-finish">Zakończ</button>
         <button id="cancel-draw-btn" class="action-cancel">Anuluj</button>`;
    dynamicActions.style.display = 'flex';

    // Tryb rysowania
    if (isPoint) {
      draw.changeMode('draw_point');
    } else if (isLine) {
      draw.changeMode('draw_line_string');
    } else {
      draw.changeMode('draw_polygon');
    }

    // Podpięcie przycisków
    document.getElementById('cancel-draw-btn').onclick = exitDrawingMode;
    if (!isPoint) {
      document.getElementById('finish-draw-btn').onclick = () => {
        // Symuluj zakończenie przez podwójne kliknięcie na mapie
        // mapbox-gl-draw nie ma bezpośredniej metody finish, więc klikamy w mapę
        map.getCanvas().dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
      };
      document.getElementById('undo-draw-btn').onclick = () => {
        // Usuń ostatni punkt - trash (backspace/delete)
        map.getCanvas().dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
      };
    }
  }

  function exitDrawingMode() {
    draw.changeMode('simple_select');
    draw.deleteAll();
    if (createActions) {
      createActions.style.display = 'flex';
      createActions.querySelectorAll('button[data-category]').forEach(b => b.classList.remove('active'));
    }
    if (dynamicActions) { dynamicActions.style.display = 'none'; dynamicActions.innerHTML = ''; }
    currentCategory = null;
  }

  function handleDrawCreate(e) {
    const features = e.features;
    if (!features.length) return;

    const feature = features[0];
    // Jeśli nie jesteśmy w trybie rysowania (np. import), pomiń
    if (!currentCategory) {
      draw.delete(feature.id);
      return;
    }

    const geometry = feature.geometry;
    const category = currentCategory;
    const displayCat = formatCategoryName(category);

    let parcelId = null;
    let isValidName = false;
    let errorMessage = '';
    const isLandCategory = LAND_CATEGORIES.includes(category);

    while (!isValidName) {
      const promptMsg = parcelId === null
        ? `Podaj nazwę/numer dla obiektu typu "${displayCat}":`
        : errorMessage;

      parcelId = prompt(promptMsg);
      if (parcelId === null || parcelId.trim() === '') {
        draw.delete(feature.id);
        exitDrawingMode();
        return;
      }
      parcelId = parcelId.trim();

      const fullKey = `${parcelId}_${category}`;
      if (currentParcelsData[fullKey]) {
        errorMessage = `Obiekt "${parcelId}" typu "${displayCat}" już istnieje!\n\nPodaj inną nazwę:`;
        isValidName = false;
        continue;
      }
      if (isLandCategory) {
        let crossDuplicate = null;
        for (const lc of LAND_CATEGORIES) {
          if (lc === category) continue;
          const crossKey = `${parcelId}_${lc}`;
          if (currentParcelsData[crossKey]) { crossDuplicate = formatCategoryName(lc); break; }
        }
        if (crossDuplicate) {
          errorMessage = `Numer "${parcelId}" jest już użyty w kategorii "${crossDuplicate}"!\n\nDziałki gruntowe nie mogą mieć tego samego numeru.\nPodaj inny numer:`;
          isValidName = false;
          continue;
        }
      }
      isValidName = true;
    }

    const geomApi = geoJSONToApi(geometry);
    const newParcel = { kategoria: category, geometria: geomApi };

    fetchJson('/api/parcel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: parcelId, parcel: newParcel }),
    })
      .then(data => {
        if (data.status === 'success') {
          const savedKey = data.full_key || `${parcelId}_${category}`;
          currentParcelsData[savedKey] = newParcel;
          draw.delete(feature.id);
          refreshParcelsSource();
          refreshParcelList();
          exitDrawingMode();
          toast(data.message || `Dodano obiekt "${parcelId}"`, 'success');
        } else {
          draw.delete(feature.id);
          exitDrawingMode();
          alert(data.message || 'Nie udało się dodać obiektu');
        }
      })
      .catch(err => {
        draw.delete(feature.id);
        exitDrawingMode();
        alert('Błąd: ' + err.message);
      });
  }

  function handleDrawUpdate(e) {
    if (!editingParcelId) return;
    const features = e.features;
    if (!features.length) return;
    const feature = features[0];
    const geomApi = geoJSONToApi(feature.geometry);
    // Zapis jest obsłużony w saveEdit()
  }

  function handleDrawSelectionChange(e) {
    if (editingParcelId) {
      const selected = draw.getSelected();
      if (!selected.features.length) {
        saveEdit();
      }
    }
  }

  // Escape = anuluj rysowanie lub edycję
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (currentCategory) {
        exitDrawingMode();
      } else if (editingParcelId) {
        cancelEdit();
      }
    }
  });

  // ==========================================================================
  // 8. EDYCJA OBIEKTÓW
  // ==========================================================================

  function enterEditMode(parcelId) {
    const parcelData = currentParcelsData[parcelId];
    if (!parcelData) return;

    editingParcelId = parcelId;

    // Utwórz feature GeoJSON dla draw
    const displayId = getDisplayId(parcelId);
    const feat = apiToGeoJSON(parcelData.geometria, parcelData.kategoria, displayId);
    if (!feat) return;

    // Usuń stary obiekt z parcels + dodaj do draw
    const savedFeatures = getAllParcelFeatures();
    const others = savedFeatures.filter(f => f.id !== parcelId);
    map.getSource('parcels').setData({ type: 'FeatureCollection', features: others });

    draw.add(feat);
    draw.changeMode('direct_select', { featureId: feat.id });

    const displayCat = formatCategoryName(parcelData.kategoria);
    createActions.style.display = 'none';
    dynamicActions.innerHTML = `
      <span class="toolbar-label">Edytujesz: ${displayId}</span>
      <span class="toolbar-hint" style="font-size:0.85em;color:#666;">💡 Kliknij poza obiekt aby zapisać, Delete aby usunąć wierzchołek</span>
      <button id="save-edit-btn" class="action-save-changes">Zapisz</button>
      <button id="cancel-edit-btn" class="action-cancel">Anuluj</button>`;
    dynamicActions.style.display = 'flex';

    document.getElementById('save-edit-btn').onclick = saveEdit;
    document.getElementById('cancel-edit-btn').onclick = cancelEdit;
  }

  function saveEdit() {
    if (!editingParcelId) return;

    const selected = draw.getSelected();
    if (!selected.features.length) {
      cancelEdit();
      return;
    }

    const feature = selected.features[0];
    const geomApi = geoJSONToApi(feature.geometry);

    fetchJson(`/api/parcel/${encodeURIComponent(editingParcelId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ geometria: geomApi }),
    })
      .then(data => {
        if (data.status === 'success') {
          currentParcelsData[editingParcelId].geometria = geomApi;
          toast(data.message || 'Zapisano zmiany geometrii', 'success');
        } else {
          alert(data.message || 'Nie udało się zapisać zmian');
        }
        finishEdit();
      })
      .catch(err => {
        alert('Błąd: ' + err.message);
        finishEdit();
      });
  }

  function cancelEdit() {
    toast('Anulowano edycję', 'info');
    finishEdit();
  }

  function finishEdit() {
    draw.deleteAll();
    draw.changeMode('simple_select');
    editingParcelId = null;
    refreshParcelsSource();
    refreshParcelList();
    createActions.style.display = 'flex';
    dynamicActions.style.display = 'none';
  }

  function getAllParcelFeatures() {
    const features = [];
    Object.entries(currentParcelsData).forEach(([id, data]) => {
      const displayId = getDisplayId(id);
      const feat = apiToGeoJSON(data.geometria, data.kategoria, displayId);
      if (feat) { feat.id = id; features.push(feat); }
    });
    return features;
  }

  // ==========================================================================
  // 9. PANEL BOCZNY - LISTA DZIAŁEK
  // ==========================================================================

  const parcelList = document.getElementById('parcel-list');
  const parcelCategories = ['rolna', 'budowlana'];

  function refreshParcelList() {
    const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab || 'parcels';
    filterAndDisplayParcels(activeTab);
  }

  function filterAndDisplayParcels(activeTab) {
    if (!parcelList) return;
    parcelList.innerHTML = '';

    const entries = Object.entries(currentParcelsData)
      .filter(([, p]) => {
        const isParcel = parcelCategories.includes(p.kategoria);
        return activeTab === 'parcels' ? isParcel : !isParcel;
      })
      .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));

    entries.forEach(([id, p]) => {
      const li = document.createElement('li');
      li.dataset.parcelId = id;
      li.dataset.parcelCategory = p.kategoria;
      const displayId = getDisplayId(id);
      const displayCat = formatCategoryName(p.kategoria);
      li.innerHTML = `
        <div class="parcel-info">
          <span class="parcel-id">${displayId}</span>
          <span class="parcel-category ${p.kategoria}">${displayCat}</span>
        </div>
        <div class="parcel-actions">
          <button title="Edytuj geometrię" class="btn-action btn-edit-geom">📐</button>
          <button title="Zmień nazwę" class="btn-action btn-rename-parcel">✏️</button>
          <button title="Zmień typ" class="btn-action btn-change-type">🔄</button>
          <button title="Usuń" class="btn-action btn-delete-parcel">❌</button>
        </div>`;

      // Kliknięcie - fokus na mapie
      li.querySelector('.parcel-info').onclick = () => {
        focusOnParcel(id);
      };

      // Hover - podświetlenie na mapie
      li.addEventListener('mouseenter', () => highlightParcel(id, true));
      li.addEventListener('mouseleave', () => highlightParcel(id, false));

      parcelList.appendChild(li);
    });
  }

  function focusOnParcel(parcelId) {
    const feat = getAllParcelFeatures().find(f => f.id === parcelId);
    if (!feat) return;

    if (feat.geometry.type === 'Point') {
      map.flyTo({ center: feat.geometry.coordinates, zoom: Math.max(map.getZoom(), 18) });
    } else {
      const bbox = turf.bbox(feat);
      map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 50, maxZoom: 19 });
    }

    // Popup
    const p = currentParcelsData[parcelId];
    if (p) {
      const displayId = getDisplayId(parcelId);
      const displayCat = formatCategoryName(p.kategoria);
      const popup = new maplibregl.Popup({ offset: 15 })
        .setHTML(`<b>ID:</b> ${displayId}<br><b>Kategoria:</b> ${displayCat}`);
      if (feat.geometry.type === 'Point') {
        popup.setLngLat(feat.geometry.coordinates).addTo(map);
      } else {
        const center = turf.center(feat).geometry.coordinates;
        popup.setLngLat(center).addTo(map);
      }
    }
  }

  function highlightParcel(parcelId, on) {
    try {
      map.setFeatureState(
        { source: 'parcels', id: parcelId },
        { highlighted: on }
      );
    } catch (e) { /* ignore */ }
  }

  // Zakładki
  document.querySelector('.sidebar-tabs')?.addEventListener('click', (e) => {
    if (e.target.matches('.tab-btn') || e.target.closest('.tab-btn')) {
      const btn = e.target.closest('.tab-btn');
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filterAndDisplayParcels(btn.dataset.tab);
    }
  });

  // Wyszukiwanie
  document.getElementById('search-filter')?.addEventListener('input', (e) => {
    const filter = e.target.value.toLowerCase();
    document.querySelectorAll('#parcel-list li').forEach(li => {
      li.style.display = li.textContent.toLowerCase().includes(filter) ? 'flex' : 'none';
    });
  });

  // Akcje na liście
  parcelList?.addEventListener('click', async (e) => {
    const btn = e.target.closest('.btn-action');
    if (!btn) return;
    const parcelId = btn.closest('li')?.dataset.parcelId;
    const currentCat = btn.closest('li')?.dataset.parcelCategory;
    if (!parcelId) return;

    if (btn.classList.contains('btn-edit-geom')) {
      enterEditMode(parcelId);
    } else if (btn.classList.contains('btn-rename-parcel')) {
      renameParcel(parcelId);
    } else if (btn.classList.contains('btn-change-type')) {
      changeParcelType(parcelId, currentCat);
    } else if (btn.classList.contains('btn-delete-parcel')) {
      deleteParcel(parcelId);
    }
  });

  // ==========================================================================
  // 10. OPERACJE CRUD
  // ==========================================================================

  async function renameParcel(oldId) {
    const oldDisplayId = getDisplayId(oldId);
    const newId = prompt(`Nowa nazwa dla "${oldDisplayId}":`, oldDisplayId);
    if (!newId || newId.trim() === '') { alert('Nazwa nie może być pusta.'); return; }
    if (newId === oldDisplayId) return;

    const pData = currentParcelsData[oldId];
    if (pData) {
      const newFullKey = `${newId}_${pData.kategoria}`;
      if (currentParcelsData[newFullKey]) { alert(`Obiekt "${newId}" już istnieje!`); return; }
    }

    try {
      const data = await fetchJson(`/api/parcel/rename/${encodeURIComponent(oldId)}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_id: newId }),
      });
      alert(data.message || 'Zmieniono nazwę obiektu');
      if (data.status === 'success') {
        const oldData = currentParcelsData[oldId];
        delete currentParcelsData[oldId];
        const newFullKey = data.full_key || `${newId}_${pData.kategoria}`;
        currentParcelsData[newFullKey] = oldData;
        refreshParcelsSource();
        refreshParcelList();
      }
    } catch (err) { alert('Błąd: ' + err.message); }
  }

  async function changeParcelType(parcelId, currentCategory) {
    const ALLOWED_POINT = POINT_CATEGORIES;
    const ALLOWED_NON_POINT = [...POLYGON_CATEGORIES, ...LINE_CATEGORIES];
    const isCurrentPoint = ALLOWED_POINT.includes(currentCategory);
    const allowed = isCurrentPoint ? ALLOWED_POINT : ALLOWED_NON_POINT;
    const optionsStr = allowed.filter(c => c !== currentCategory).map(formatCategoryName).join(', ');
    const displayId = getDisplayId(parcelId);
    const newCat = prompt(`Zmiana typu "${displayId}"\nObecny: ${formatCategoryName(currentCategory)}\n\nDostępne: ${optionsStr}\n\nWpisz nowy typ:`);
    if (!newCat) return;

    const normalized = newCat.trim().toLowerCase().replace(/\s+/g, '_');
    if (normalized === currentCategory) return;
    if (!allowed.includes(normalized)) { alert(`Niedozwolona zmiana!\nDozwolone: ${optionsStr}`); return; }

    try {
      const data = await fetchJson(`/api/parcel/${encodeURIComponent(parcelId)}/category`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kategoria: normalized }),
      });
      alert(data.message || 'Zmieniono typ obiektu');
      if (data.status === 'success') {
        const oldData = currentParcelsData[parcelId];
        delete currentParcelsData[parcelId];
        const newFullKey = data.full_key || `${getDisplayId(parcelId)}_${normalized}`;
        currentParcelsData[newFullKey] = { ...oldData, kategoria: normalized };
        refreshParcelsSource();
        refreshParcelList();
      }
    } catch (err) { alert('Błąd: ' + err.message); }
  }

  async function deleteParcel(parcelId) {
    const displayId = getDisplayId(parcelId);
    if (!confirm(`Usunąć obiekt '${displayId}'?\n\nNieodwracalne!`)) return;
    const data = await fetchJson(`/api/parcel/${encodeURIComponent(parcelId)}`, { method: 'DELETE' });
    alert(data.message || 'Usunięto obiekt');
    if (data.status === 'success') {
      delete currentParcelsData[parcelId];
      refreshParcelsSource();
      refreshParcelList();
    }
  }

  async function deleteAllParcels() {
    if (!confirm('Usunąć WSZYSTKIE obiekty?\n\nNieodwracalne!')) return;
    const userInput = prompt('Wpisz dokładnie: "USUŃ WSZYSTKO"');
    if (userInput !== 'USUŃ WSZYSTKO') { alert('Anulowano.'); return; }
    try {
      const data = await fetchJson('/api/parcels/delete_all', { method: 'DELETE' });
      alert(data.message || 'Usunięto wszystkie obiekty');
      if (data.status === 'success') location.reload();
    } catch (err) { alert('Błąd: ' + err.message); }
  }

  // ==========================================================================
  // 11. BACKUPY
  // ==========================================================================

  document.getElementById('open-backup-manager').onclick = () => {
    document.getElementById('backupModal').style.display = 'flex';
    document.getElementById('backupModal').style.alignItems = 'center';
    document.getElementById('backupModal').style.justifyContent = 'center';
    loadBackupList();
  };
  document.querySelector('.close-button').onclick = () => document.getElementById('backupModal').style.display = 'none';
  document.getElementById('create-backup-btn').addEventListener('click', () => {
    fetchJson('/backup', { method: 'POST' }).then(data => {
      toast(data.message || 'Utworzono kopię zapasową', 'success');
      if (data.status === 'success') loadBackupList();
    }).catch(err => toast('Błąd: ' + err.message, 'error'));
  });

  document.getElementById('backup-list').addEventListener('click', (e) => {
    const target = e.target;
    const filename = target.closest('li')?.dataset.filename;
    if (!filename) return;
    const headers = { 'Content-Type': 'application/json' };
    const body = JSON.stringify({ filename });

    if (target.matches('.btn-restore') && confirm(`Przywrócić "${filename}"?\n\nDane zostaną nadpisane!`)) {
      fetchJson('/restore', { method: 'POST', headers, body }).then(data => {
        alert(data.message || 'Przywrócono kopię zapasową');
        if (data.status === 'success') location.reload();
      }).catch(err => alert('Błąd: ' + err.message));
    }
    if (target.matches('.btn-delete') && confirm(`Usunąć "${filename}"?\n\nNieodwracalne!`)) {
      fetchJson('/delete_backup', { method: 'POST', headers, body }).then(data => {
        toast(data.message || 'Usunięto kopię zapasową', 'success');
        loadBackupList();
      }).catch(err => alert('Błąd: ' + err.message));
    }
  });

  function loadBackupList() {
    const backupList = document.getElementById('backup-list');
    backupList.innerHTML = '<li>Ładowanie...</li>';
    fetch('/api/backups').then(r => r.json()).then(files => {
      backupList.innerHTML = files.length === 0 ? '<li>Brak kopii.</li>' : '';
      files.forEach(file => {
        const li = document.createElement('li');
        li.dataset.filename = file;
        li.innerHTML = `<span>${file}</span>
          <div class="backup-actions">
            <button class="btn-restore">Przywróć</button>
            <button class="btn-delete">Usuń</button>
          </div>`;
        backupList.appendChild(li);
      });
    }).catch(() => backupList.innerHTML = '<li>Błąd wczytywania.</li>');
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      data = {};
    }
    if (!response.ok) {
      const detail = data.detail || data.message || `${response.status} ${response.statusText}`;
      throw new Error(detail);
    }
    return data;
  }

  document.getElementById('delete-all-parcels-btn').addEventListener('click', deleteAllParcels);

  // ==========================================================================
  // 12. TOAST / UTIL
  // ==========================================================================

  function toast(msg, type) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `toast ${type || 'success'}`;
    el.textContent = msg || 'Gotowe';
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3000);
  }

  // ==========================================================================
  // 13. INICJALIZACJA
  // ==========================================================================

  function loadAndDrawParcels() {
    fetch('/api/parcels')
      .then(r => r.json())
      .then(data => {
        currentParcelsData = data;

        // Wait for map style to be loaded
        if (map.isStyleLoaded()) {
          refreshParcelsSource();
          refreshParcelList();
        } else {
          map.once('style.load', () => {
            refreshParcelsSource();
            refreshParcelList();
          });
        }
      })
      .catch(err => console.error('Błąd ładowania działek:', err));
  }

  // Start when map is ready
  map.on('load', () => {
    loadAndDrawParcels();
    console.log('✅ Edytor działek (MapLibre GL) załadowany');
  });

});

