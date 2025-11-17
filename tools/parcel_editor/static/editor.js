/**
 * ============================================================================
 * Aplikacja: Edytor Działek na Mapie Interaktywnej
 * Opis: Główny moduł obsługujący rysowanie, edycję i zarządzanie obiektami
 *       geograficznymi z wykorzystaniem bibliotek Leaflet i Leaflet.PM
 * ============================================================================
 */

document.addEventListener("DOMContentLoaded", function () {
  
  // ==========================================================================
  // STAN APLIKACJI
  // ==========================================================================
  let currentParcelsData = {};    // Wszystkie działki z serwera
  let activeDrawingLayer = null;  // Warstwa aktualnie rysowana
  let editedLayer = null;         // Warstwa w trakcie edycji
  let originalGeometry = null;    // Oryginalna geometria przed edycją
  let currentCategory = null;     // Aktywna kategoria rysowania
  let snapEnabled = true;         // Stan magnesu (snap)

  // ==========================================================================
  // INICJALIZACJA MAPY LEAFLET
  // ==========================================================================
  
  // Wczytanie konfiguracji z obiektu globalnego
  const mapDefaults = window.MAP_CONFIG.defaults;
  const mapCalibration = window.MAP_CONFIG.calibration;

  // Granice mapy z marginesem
  const sw = mapCalibration.sw;
  const ne = mapCalibration.ne;
  const latPadding = (ne.lat - sw.lat) * 0.1;
  const lngPadding = (ne.lng - sw.lng) * 0.2;
  const southWest = L.latLng(sw.lat - latPadding, sw.lng - lngPadding);
  const northEast = L.latLng(ne.lat + latPadding, ne.lng + lngPadding);
  const bounds = L.latLngBounds(southWest, northEast);
  
  // Utworzenie mapy
  const map = L.map("map", {
    maxBounds: bounds,
    maxBoundsViscosity: 0.7,
    minZoom: 10,
    maxZoom: 21,
    zoomSnap: 0.25,
    zoomDelta: 0.25,
  }).setView([mapDefaults.center.lat, mapDefaults.center.lng], mapDefaults.zoom);
  
  // ==========================================================================
  // WARSTWY MAPY
  // ==========================================================================
  
  // Warstwa 1: Mapa historyczna
  const imageBounds = [
    [mapCalibration.sw.lat, mapCalibration.sw.lng], 
    [mapCalibration.ne.lat, mapCalibration.ne.lng]
  ];
  const historicalMapLayer = L.imageOverlay("/static/mapa.jpg", imageBounds);

  // Warstwa 2: OpenStreetMap
  const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    opacity: 0.7,
    maxZoom: 21
  });

  // Warstwa 3: Obiekty narysowane
  const parcelLayerGroup = L.layerGroup();

  // Kontrolka warstw
  const overlays = {
    "Mapa Historyczna": historicalMapLayer,
    "Mapa Drogowa (OSM)": osmLayer,
    "Narysowane Obiekty": parcelLayerGroup
  };

  // Domyślnie włączone warstwy
  historicalMapLayer.addTo(map);
  parcelLayerGroup.addTo(map);

  L.control.layers({}, overlays, { 
    position: 'topright',
    collapsed: true
  }).addTo(map);

  // ==========================================================================
  // FUNKCJE POMOCNICZE
  // ==========================================================================

  /**
   * Wyciąga numer działki z pełnego klucza (format: numer_kategoria).
   * Przykład: "5_budynek" -> "5", "123_budowlana" -> "123", "dworzec_obiekt_specjalny" -> "dworzec"
   */
  function getDisplayId(fullKey, category = null) {
    // Jeśli znamy kategorię, usuń ją z końca klucza
    if (category) {
      const suffix = `_${category}`;
      if (fullKey.endsWith(suffix)) {
        return fullKey.substring(0, fullKey.length - suffix.length);
      }
    }

    // Jeśli nie ma kategorii, spróbuj znaleźć ją w danych
    if (currentParcelsData[fullKey]) {
      const cat = currentParcelsData[fullKey].kategoria;
      if (cat) {
        const suffix = `_${cat}`;
        if (fullKey.endsWith(suffix)) {
          return fullKey.substring(0, fullKey.length - suffix.length);
        }
      }
    }

    // Fallback - usuń od ostatniego podkreślnika
    const lastUnderscoreIndex = fullKey.lastIndexOf('_');
    if (lastUnderscoreIndex > 0) {
      return fullKey.substring(0, lastUnderscoreIndex);
    }
    return fullKey;
  }

  /**
   * Formatuje nazwę kategorii do wyświetlania (zamienia podkreślniki na spacje).
   * Przykład: "obiekt_specjalny" -> "obiekt specjalny"
   */
  function formatCategoryName(category) {
    if (!category) return "Brak danych";
    return category.replace(/_/g, ' ');
  }

  /**
   * Ogranicza częstotliwość wywołań funkcji.
   */
  function throttle(func, limit) {
    let inThrottle;
    return function () {
      const args = arguments;
      const context = this;
      if (!inThrottle) {
        func.apply(context, args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  }
  
  // ==========================================================================
  // KONTROLKA WSPÓŁRZĘDNYCH
  // ==========================================================================
  const CoordinatesControl = L.Control.extend({
    onAdd: function (map) {
      this._div = L.DomUtil.create("div", "leaflet-control-coordinates");
      this._div.innerHTML = "Najedź na mapę...";
      return this._div;
    },
    update: function (latlng) {
      if (latlng) {
        const lat = latlng.lat.toFixed(6);
        const lng = latlng.lng.toFixed(6);
        this._div.innerHTML = `Lat: ${lat}<br>Lng: ${lng}`;
      } else {
        this._div.innerHTML = "Najedź na mapę...";
      }
    },
  });
  
  const coordDisplay = new CoordinatesControl({ position: "bottomright" });
  coordDisplay.addTo(map);

  map.on("mousemove", throttle((e) => coordDisplay.update(e.latlng), 100));
  map.on("mouseout", () => coordDisplay.update());

  // ==========================================================================
  // KONFIGURACJA LEAFLET.PM
  // ==========================================================================
  map.pm.setLang("pl");
  map.pm.addControls({
    position: "topleft",
    drawControls: false,
    editControls: false,
  });

  // ==========================================================================
  // ELEMENTY DOM
  // ==========================================================================
  const createActions = document.getElementById("create-actions");
  const dynamicActions = document.getElementById("dynamic-actions");
  const parcelList = document.getElementById("parcel-list");

  // Uzupełnienie przycisków kategorii punktowych
  (function ensurePointCategoryButtons() {
    if (!createActions) return;

    const hasBudynek = !!createActions.querySelector('[data-category="budynek"]');
    const hasSpec = !!createActions.querySelector('[data-category="obiekt_specjalny"]');
    const hasBoundary = !!createActions.querySelector('[data-category="obrys_miejscowosci"]');

    const frag = document.createDocumentFragment();

    if (!hasBudynek) {
      const b = document.createElement("button");
      b.textContent = "Dodaj dom";
      b.dataset.category = "budynek";
      frag.appendChild(b);
    }

    if (!hasSpec) {
      const b2 = document.createElement("button");
      b2.textContent = "Dodaj obiekt specjalny";
      b2.dataset.category = "obiekt_specjalny";
      frag.appendChild(b2);
    }

    if (!hasBoundary) {
      const b3 = document.createElement("button");
      b3.textContent = "Dodaj obrys miejscowości";
      b3.dataset.category = "obrys_miejscowosci";
      frag.appendChild(b3);
    }

    if (frag.childNodes.length) {
      createActions.appendChild(frag);
    }
  })();

  // Delegacja zdarzeń dla przycisków kategorii
  if (createActions) {
    createActions.addEventListener("click", (ev) => {
      const btn = ev.target.closest('button[data-category]');
      if (!btn) return;
      ev.preventDefault();
      enterDrawingMode(btn.dataset.category);
    });
  }

  // ==========================================================================
  // TRYB RYSOWANIA
  // ==========================================================================
  
  /**
   * Włącza tryb rysowania dla wybranej kategorii.
   */
  function enterDrawingMode(category) {
    currentCategory = category;

    // Oznaczenie aktywnego przycisku
    if (createActions) {
      const btns = createActions.querySelectorAll('button[data-category]');
      btns.forEach((b) => b.classList.toggle('active', b.dataset.category === String(category)));
    }

    createActions.style.display = "none";

    // Sprawdzenie typu geometrii
    const POINT_CATEGORIES = ["budynek", "kapliczka", "obiekt_specjalny", "dworzec"];
    const LINE_CATEGORIES = ["droga", "rzeka", "obrys_miejscowosci"];
    const isPoint = POINT_CATEGORIES.includes(String(category || "").toLowerCase());
    const isLine = LINE_CATEGORIES.includes(String(category || "").toLowerCase());

    // Konfiguracja paska akcji - wszędzie dodajemy przycisk magnetyzmu
    const displayCategory = formatCategoryName(category);
    dynamicActions.innerHTML = isPoint
      ? `<span class="toolbar-label">Rysujesz: ${displayCategory}</span>
         <button id="snap-toggle-btn" class="action-snap ${snapEnabled ? 'active' : ''}">🧲 Magnes</button>
         <button id="cancel-btn" class="action-cancel">Anuluj</button>`
      : `<span class="toolbar-label">Rysujesz: ${displayCategory}</span>
         <button id="undo-btn" class="action-undo">Cofnij Punkt</button>
         <button id="snap-toggle-btn" class="action-snap ${snapEnabled ? 'active' : ''}">🧲 Magnes</button>
         <button id="finish-btn" class="action-finish">Zakończ</button>
         <button id="cancel-btn" class="action-cancel">Anuluj</button>`;
    dynamicActions.style.display = "flex";

    // Włączenie trybu rysowania
    if (isPoint) {
      map.pm.enableDraw("Marker", {
        snappable: snapEnabled,
        snapDistance: 20,
      });
    } else if (isLine) {
      map.pm.enableDraw("Line", {
        snappable: snapEnabled,
        snapDistance: 20,
        templineStyle: { color: "magenta", weight: 2 },
        hintlineStyle: { color: "magenta", dashArray: "5,5" },
        pathOptions: { color: "magenta" },
      });
    } else {
      map.pm.enableDraw("Polygon", {
        snappable: snapEnabled,
        snapDistance: 20,
        templineStyle: { color: "magenta", weight: 2 },
        hintlineStyle: { color: "magenta", dashArray: "5,5" },
        pathOptions: { color: "magenta" },
      });
    }

    map.on("pm:create", handleDrawingFinish);

    // Podpięcie kontrolek
    const cancelBtn = document.getElementById("cancel-btn");
    if (cancelBtn) cancelBtn.onclick = exitDrawingMode;

    const snapToggleBtn = document.getElementById("snap-toggle-btn");
    if (snapToggleBtn) {
      snapToggleBtn.onclick = () => {
        snapEnabled = !snapEnabled;
        snapToggleBtn.classList.toggle('active', snapEnabled);

        // Zaktualizuj ustawienia snap w Leaflet.PM dla aktywnego trybu rysowania
        if (isLine && map.pm.Draw.Line?._layer) {
          map.pm.Draw.Line._layer.options.snappable = snapEnabled;
        } else if (!isLine && !isPoint && map.pm.Draw.Polygon?._layer) {
          map.pm.Draw.Polygon._layer.options.snappable = snapEnabled;
        }
        // Zaktualizuj snap dla bieżącego trybu
        map.pm.setGlobalOptions({ snappable: snapEnabled, snapDistance: 20 });
      };
    }

    if (!isPoint) {
      const undoBtn = document.getElementById("undo-btn");
      const finishBtn = document.getElementById("finish-btn");

      if (isLine) {
        if (undoBtn && map.pm.Draw.Line?._removeLastVertex) {
          undoBtn.onclick = () => map.pm.Draw.Line._removeLastVertex();
        }
        if (finishBtn && map.pm.Draw.Line?._finishShape) {
          finishBtn.onclick = () => map.pm.Draw.Line._finishShape();
        }
      } else {
        if (undoBtn && map.pm.Draw.Polygon?._removeLastVertex) {
          undoBtn.onclick = () => map.pm.Draw.Polygon._removeLastVertex();
        }
        if (finishBtn && map.pm.Draw.Polygon?._finishShape) {
          finishBtn.onclick = () => map.pm.Draw.Polygon._finishShape();
        }
      }
    }
  }

  /**
   * Obsługuje zakończenie rysowania i zapisuje nową działkę.
   */
  function handleDrawingFinish(e) {
    const layer = e.layer;
    activeDrawingLayer = layer;

    const category = document.querySelector("#create-actions button.active")
      ?.dataset.category || "rolna";
    const displayCategory = formatCategoryName(category);

    let parcelId = null;
    let isValidName = false;
    let errorMessage = "";

    // Grupa działek gruntowych - nie mogą mieć tego samego numeru między sobą
    const LAND_CATEGORIES = ["rolna", "droga", "las", "pastwisko", "rzeka"];
    const isLandCategory = LAND_CATEGORIES.includes(category);

    // Pętla pytająca o nazwę - powtarza się przy duplikatach
    while (!isValidName) {
      const promptMessage = parcelId === null
        ? `Podaj nazwę/numer dla obiektu typu "${displayCategory}":`
        : errorMessage;

      parcelId = prompt(promptMessage);

      // Użytkownik anulował lub wpisał pustą nazwę
      if (parcelId === null || parcelId.trim() === "") {
        try { layer.remove(); } catch (err) {}
        activeDrawingLayer = null;
        exitDrawingMode();
        return;
      }

      parcelId = parcelId.trim();

      // Sprawdzenie dokładnego duplikatu (ta sama nazwa i kategoria)
      const fullKey = `${parcelId}_${category}`;
      if (currentParcelsData[fullKey]) {
        errorMessage = `Obiekt "${parcelId}" typu "${displayCategory}" już istnieje!\n\nPodaj inną nazwę lub kliknij Anuluj, aby usunąć rysunek:`;
        isValidName = false;
        continue;
      }

      // Sprawdzenie krzyżowe TYLKO dla działek gruntowych
      if (isLandCategory) {
        let crossDuplicate = null;
        for (const landCat of LAND_CATEGORIES) {
          if (landCat === category) continue; // Pomiń tę samą kategorię (już sprawdzona wyżej)
          const crossKey = `${parcelId}_${landCat}`;
          if (currentParcelsData[crossKey]) {
            crossDuplicate = formatCategoryName(landCat);
            break;
          }
        }

        if (crossDuplicate) {
          errorMessage = `Numer "${parcelId}" jest już użyty w kategorii "${crossDuplicate}"!\n\nDziałki gruntowe (rolna, droga, las, pastwisko, rzeka) nie mogą mieć tego samego numeru.\n\nMożesz użyć np. "${parcelId}/1" lub inny numer.\nKliknij Anuluj, aby usunąć rysunek:`;
          isValidName = false;
          continue;
        }
      }

      // Nazwa jest unikalna
      isValidName = true;
    }

    // Przygotowanie geometrii
    let geometryToSave;
    if (layer instanceof L.Marker) {
      const ll = layer.getLatLng();
      geometryToSave = [ll.lat, ll.lng];
    } else if (typeof layer.getLatLngs === "function") {
      const latLngs = layer.getLatLngs();
      const ring = Array.isArray(latLngs[0]) ? latLngs[0] : latLngs;
      geometryToSave = ring.map((ll) => [ll.lat, ll.lng]);
    } else {
      alert("Nieznany typ geometrii.");
      try { layer.remove(); } catch (err) {}
      activeDrawingLayer = null;
      exitDrawingMode();
      return;
    }

    const fullKey = `${parcelId}_${category}`;
    const newParcel = { kategoria: category, geometria: geometryToSave };

    // Zapis do serwera
    fetch("/api/parcel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: parcelId, parcel: newParcel }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "success") {
          // Dodaj działkę do lokalnych danych
          const savedFullKey = data.full_key || fullKey;
          currentParcelsData[savedFullKey] = newParcel;

          // Usuń tymczasową warstwę z rysowania
          try { layer.remove(); } catch (err) {}

          // Dodaj ostateczną warstwę na mapę
          addParcelToMap(savedFullKey, newParcel);

          // Pobierz aktywną zakładkę
          const activeTab = document.querySelector(".tab-btn.active")?.dataset.tab || "parcels";

          // Zaktualizuj listę działek
          filterAndDisplayParcels(activeTab);

          // Wyjdź z trybu rysowania
          exitDrawingMode();

          // Pokaż komunikat sukcesu
          alert(data.message);
        } else {
          alert(data.message);
          exitDrawingMode();
        }
      })
      .catch((err) => {
        alert("Błąd podczas zapisywania: " + err.message);
        exitDrawingMode();
      });
  }

  /**
   * Wyłącza tryb rysowania i przywraca interfejs.
   */
  function exitDrawingMode() {
    try { map.pm.disableDraw("Marker"); } catch (e) {}
    try { map.pm.disableDraw("Polygon"); } catch (e) {}
    try { map.pm.disableDraw("Line"); } catch (e) {}

    map.off("pm:create", handleDrawingFinish);

    // Czyszczenie niedomkniętych warstw
    try {
      if (map.pm?.getGeomanDrawLayers) {
        map.pm.getGeomanDrawLayers().forEach((layer) => {
          try { layer.remove(); } catch (e) {}
        });
      }
    } catch (e) {}

    // Reset interfejsu
    if (createActions) {
      createActions.style.display = "flex";
      const btns = createActions.querySelectorAll('button[data-category]');
      btns.forEach((b) => b.classList.remove('active'));
    }
    if (dynamicActions) {
      dynamicActions.style.display = "none";
      dynamicActions.innerHTML = "";
    }

    activeDrawingLayer = null;
    currentCategory = null;
  }

  // ==========================================================================
  // TRYB EDYCJI
  // ==========================================================================

  /**
   * Włącza tryb edycji geometrii działki.
   */
  function enterEditMode(parcelId) {
    const layer = findLayerById(parcelId);
    if (!layer) return;

    editedLayer = layer;
    const parcelData = currentParcelsData[parcelId];
    const isLine = layer instanceof L.Polyline && !(layer instanceof L.Polygon);

    // Zapisz oryginalną geometrię przed edycją
    if (layer.getLatLng && !layer.getLatLngs) {
      // Punkt
      const ll = layer.getLatLng();
      originalGeometry = { lat: ll.lat, lng: ll.lng };
    } else if (layer.getLatLngs) {
      // Linia lub wielokąt
      const latLngs = layer.getLatLngs();
      // Deep copy żeby zmiany nie wpłynęły na oryginał
      originalGeometry = JSON.parse(JSON.stringify(latLngs));
    }

    layer.pm.enable({ allowSelfIntersection: true });

    // Dodaj obsługę prawego kliknięcia na wierzchołki
    const setupVertexRemoval = () => {
      const vertexMarkers = layer.pm._vertexLayers || layer.pm._markers || [];

      vertexMarkers.forEach((marker, index) => {
        // Sprawdź czy marker ma metody potrzebne do obsługi zdarzeń
        if (!marker || typeof marker.off !== 'function' || typeof marker.on !== 'function') {
          return;
        }

        marker.off('contextmenu'); // Usuń poprzednie handlery
        marker.on('contextmenu', (e) => {
          L.DomEvent.stopPropagation(e);
          L.DomEvent.preventDefault(e);

          if (isLine) {
            // Dla linii - usuń ten punkt i wszystkie kolejne (ucięcie)
            const coords = layer.getLatLngs();
            if (index === 0 && coords.length === 1) {
              alert("Nie możesz usunąć ostatniego punktu!");
              return;
            }
            // Zachowaj tylko punkty od początku do klikniętego (włącznie z poprzednim)
            const newCoords = coords.slice(0, index);
            if (newCoords.length < 2) {
              alert("Linia musi mieć co najmniej 2 punkty!");
              return;
            }
            layer.setLatLngs(newCoords);
          } else {
            // Dla wielokątów - usuń tylko ten punkt
            const coords = layer.getLatLngs()[0] || layer.getLatLngs();
            if (coords.length <= 3) {
              alert("Wielokąt musi mieć co najmniej 3 punkty!");
              return;
            }
            coords.splice(index, 1);
            layer.setLatLngs(coords);
          }

          // Odśwież tryb edycji aby zaktualizować markery
          layer.pm.disable();
          layer.pm.enable({ allowSelfIntersection: true });
          setupVertexRemoval();
        });
      });
    };

    // Ustaw handlery po krótkiej chwili (aby markery były gotowe)
    setTimeout(setupVertexRemoval, 100);

    // Ponownie ustaw przy każdej zmianie geometrii
    layer.on('pm:edit', setupVertexRemoval);

    // Zmiana interfejsu
    const displayId = getDisplayId(parcelId);
    createActions.style.display = "none";
    dynamicActions.innerHTML = `
      <span class="toolbar-label">Edytujesz geometrię: ${displayId}</span>
      <span class="toolbar-hint" style="font-size: 0.85em; color: #666;">💡 Prawy klik na punkt: ${isLine ? 'ucina od tego punktu do końca' : 'usuwa punkt'}</span>
      <button id="save-edit-btn" class="action-save-changes">Zapisz Zmiany</button>
      <button id="cancel-edit-btn" class="action-cancel">Anuluj Edycję</button>`;
    dynamicActions.style.display = "flex";

    document.getElementById("save-edit-btn").onclick = () => saveEdit(parcelId);
    document.getElementById("cancel-edit-btn").onclick = cancelEdit;
  }

  /**
   * Zapisuje zmiany w geometrii działki.
   */
  function saveEdit(parcelId) {
    let geometryToSave;

    if (editedLayer?.getLatLng && !editedLayer.getLatLngs) {
      const ll = editedLayer.getLatLng();
      geometryToSave = [ll.lat, ll.lng];
    } else if (editedLayer?.getLatLngs) {
      const latLngs = editedLayer.getLatLngs();
      const ring = Array.isArray(latLngs[0]) ? latLngs[0] : latLngs;
      geometryToSave = ring.map((ll) => [ll.lat, ll.lng]);
    } else {
      alert("Nieznany typ geometrii.");
      return;
    }

    fetch(`/api/parcel/${parcelId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ geometria: geometryToSave }),
    })
      .then((res) => res.json())
      .then((data) => {
        alert(data.message);
        if (data.status === "success") {
          // Zaktualizuj dane lokalne
          currentParcelsData[parcelId].geometria = geometryToSave;
          // Odśwież warstwę na mapie
          refreshLayer(parcelId, currentParcelsData[parcelId]);
        }
        exitEditMode();
      });
  }

  /**
   * Anuluje edycję i przywraca oryginalną geometrię.
   */
  function cancelEdit() {
    if (editedLayer && originalGeometry) {
      // Przywróć oryginalną geometrię
      if (editedLayer.getLatLng && !editedLayer.getLatLngs) {
        // Punkt
        editedLayer.setLatLng([originalGeometry.lat, originalGeometry.lng]);
      } else if (editedLayer.getLatLngs) {
        // Linia lub wielokąt
        editedLayer.setLatLngs(originalGeometry);
      }
    }
    exitEditMode();
  }

  /**
   * Wyłącza tryb edycji.
   */
  function exitEditMode() {
    if (editedLayer) {
      // Usuń event listenery
      editedLayer.off('pm:edit');

      // Wyłącz tryb edycji
      editedLayer.pm.disable();

      // Usuń contextmenu z wierzchołków
      const vertexMarkers = editedLayer.pm._vertexLayers || editedLayer.pm._markers || [];
      vertexMarkers.forEach(marker => {
        if (marker && typeof marker.off === 'function') {
          marker.off('contextmenu');
        }
      });
    }
    editedLayer = null;
    originalGeometry = null;

    createActions.style.display = "flex";
    dynamicActions.style.display = "none";
  }

  // ==========================================================================
  // RENDEROWANIE DZIAŁEK
  // ==========================================================================

  /**
   * Zwraca obiekt ze stylami dla kategorii.
   */
  function getCategoryStyles() {
    return {
      budowlana: {
        color: "#e67e22",
        weight: 2,
        fillColor: "#e67e22",
        fillOpacity: 0.4,
      },
      rolna: {
        color: "#27ae60",
        weight: 2,
        fillColor: "#27ae60",
        fillOpacity: 0.4,
      },
      droga: {
        color: "#88540b",
        weight: 3,
        fill: false
      },
      rzeka: {
        color: "#3498db",
        weight: 4,
        fill: false
      },
      obrys_miejscowosci: {
        color: "#ff0000",
        weight: 3,
        fill: false,
        dashArray: "10, 5"
      },
      las: {
        color: "#16a085",
        weight: 1,
        fillColor: "#1abc9c",
        fillOpacity: 0.5,
      },
      pastwisko: {
        color: "#f1c40f",
        weight: 1,
        fillColor: "#f1c40f",
        fillOpacity: 0.5,
      },
      budynek: {
        color: "#9b59b6",
        weight: 1,
        fillColor: "#9b59b6",
        fillOpacity: 0.6,
      },
      kapliczka: {
        color: "#e74c3c",
        weight: 1,
        fillColor: "#e74c3c",
        fillOpacity: 0.6,
      },
      default: {
        color: "#3388ff",
        weight: 2,
        fillColor: "#3388ff",
        fillOpacity: 0.3,
      },
    };
  }

  /**
   * Dodaje pojedynczą działkę do mapy.
   */
  function addParcelToMap(id, parcelData) {
    const categoryStyles = getCategoryStyles();
    const g = parcelData.geometria;
    if (!g || !g.length) return null;

    const POINT_CATEGORIES = ["budynek", "kapliczka", "obiekt_specjalny", "dworzec"];
    const isPointCategory = POINT_CATEGORIES.includes(String(parcelData.kategoria || "").toLowerCase());
    const isPointGeom = Array.isArray(g) && typeof g[0] === "number" && typeof g[1] === "number";
    const isArrayOfPairs = Array.isArray(g) && Array.isArray(g[0]) && typeof g[0][0] === "number";

    let layer;
    const styleOptions = categoryStyles[parcelData.kategoria] || categoryStyles["default"];

    // Tworzenie warstwy
    if (isPointCategory || isPointGeom) {
      const [lat, lng] = g;
      layer = L.marker([lat, lng]);
    } else if (["droga", "rzeka", "obrys_miejscowosci"].includes(String(parcelData.kategoria).toLowerCase())) {
      const latLngs = isArrayOfPairs ? g : [];
      layer = L.polyline(latLngs, styleOptions);
    } else {
      const latLngs = isArrayOfPairs ? g : [];
      layer = L.polygon(latLngs, styleOptions);
    }

    // Metadane i popup
    layer.parcelId = id;
    layer.parcelCategory = parcelData.kategoria;
    if (layer.setStyle) layer.originalStyle = styleOptions;

    const displayId = getDisplayId(id);
    const displayCategory = formatCategoryName(parcelData.kategoria);
    layer
      .bindPopup(`<b>ID:</b> ${displayId}<br><b>Kategoria:</b> ${displayCategory}`)
      .addTo(parcelLayerGroup);

    return layer;
  }

  /**
   * Pobiera i renderuje działki na mapie.
   */
  function loadAndDrawParcels() {
    // Pobranie danych
    fetch("/api/parcels")
      .then((r) => r.json())
      .then((data) => {
        currentParcelsData = data;
        parcelLayerGroup.clearLayers();

        // Renderowanie każdej działki
        Object.entries(data).forEach(([id, p]) => {
          addParcelToMap(id, p);
        });

        filterAndDisplayParcels("parcels");
      });
  }

  /**
   * Filtruje działki według kategorii.
   */
  function filterAndDisplayParcels(activeTab) {
    const parcelCategories = ["rolna", "budowlana"];

    const filteredData = Object.entries(currentParcelsData)
      .filter(([id, p]) => {
        const isParcel = parcelCategories.includes(p.kategoria);
        return activeTab === "parcels" ? isParcel : !isParcel;
      })
      .reduce((obj, [key, val]) => {
        obj[key] = val;
        return obj;
      }, {});

    updateParcelList(filteredData);
  }

  /**
   * Aktualizuje listę działek w panelu.
   */
  function updateParcelList(parcelsToShow) {
    parcelList.innerHTML = "";
    
    // Sortowanie alfanumeryczne
    Object.entries(parcelsToShow)
      .sort(([idA], [idB]) =>
        idA.localeCompare(idB, undefined, {
          numeric: true,
          sensitivity: "base",
        }),
      )
      .forEach(([id, p]) => {
        const li = document.createElement("li");
        li.dataset.parcelId = id;
        li.dataset.parcelCategory = p.kategoria;
        const displayId = getDisplayId(id);
        const displayCategory = formatCategoryName(p.kategoria);
        li.innerHTML = `
          <div class="parcel-info">
            <span class="parcel-id">${displayId}</span>
            <span class="parcel-category">${displayCategory}</span>
          </div>
          <div class="parcel-actions">
            <button title="Edytuj geometrię" class="btn-action btn-edit-geom">📐</button>
            <button title="Zmień nazwę/numer" class="btn-action btn-rename-parcel">✏️</button>
            <button title="Zmień typ" class="btn-action btn-change-type">🔄</button>
            <button title="Usuń" class="btn-action btn-delete-parcel">❌</button>
          </div>`;

        // Fokus na kliknięcie
        const infoDiv = li.querySelector(".parcel-info");
        infoDiv.onclick = () => {
          const layer = findLayerById(id);
          if (!layer) return;

          if (layer.getLatLng) {
            map.setView(layer.getLatLng(), Math.max(map.getZoom(), 17));
          } else if (layer.getBounds) {
            map.fitBounds(layer.getBounds().pad(0.1));
          }
          layer.openPopup && layer.openPopup();
        };

        // Podświetlanie przy najechaniu
        li.addEventListener("mouseenter", () => {
          const layer = findLayerById(id);
          if (layer?.setStyle) {
            layer.setStyle({ fillColor: "#FFFF00", fillOpacity: 0.7 });
            layer.bringToFront && layer.bringToFront();
          }
        });

        li.addEventListener("mouseleave", () => {
          const layer = findLayerById(id);
          if (layer?.setStyle && layer.originalStyle) {
            layer.setStyle(layer.originalStyle);
          }
        });

        parcelList.appendChild(li);
      });
  }

  // ==========================================================================
  // OBSŁUGA INTERFEJSU
  // ==========================================================================

  // Przełączanie zakładek
  document.querySelector(".sidebar-tabs").addEventListener("click", (e) => {
    if (e.target.matches(".tab-btn")) {
      document.querySelectorAll(".tab-btn")
        .forEach((btn) => btn.classList.remove("active"));
      e.target.classList.add("active");
      filterAndDisplayParcels(e.target.dataset.tab);
    }
  });

  // Wyszukiwanie działek
  document.getElementById("search-filter").addEventListener("input", (e) => {
    const filter = e.target.value.toLowerCase();
    document.querySelectorAll("#parcel-list li").forEach((li) => {
      li.style.display = li.textContent.toLowerCase().includes(filter)
        ? "flex"
        : "none";
    });
  });

  // Delegacja akcji na liście działek
  parcelList.addEventListener("click", async (e) => {
    const button = e.target.closest(".btn-action");
    if (!button) return;

    const parcelId = button.closest("li")?.dataset.parcelId;
    const currentCategory = button.closest("li")?.dataset.parcelCategory;
    if (!parcelId) return;

    if (button.classList.contains("btn-edit-geom")) {
      enterEditMode(parcelId);
    } else if (button.classList.contains("btn-rename-parcel")) {
      renameParcel(parcelId);
    } else if (button.classList.contains("btn-change-type")) {
      changeParcelType(parcelId, currentCategory);
    } else if (button.classList.contains("btn-delete-parcel")) {
      deleteParcel(parcelId);
    }
  });

  // ==========================================================================
  // FUNKCJE POMOCNICZE - OPERACJE NA DZIAŁKACH
  // ==========================================================================

  /**
   * Znajduje warstwę po ID działki.
   */
  function findLayerById(id) {
    return parcelLayerGroup.getLayers().find((layer) => layer.parcelId === id);
  }

  /**
   * Odświeża pojedynczą warstwę bez przeładowania strony.
   */
  function refreshLayer(parcelId, newData) {
    // Usuń starą warstwę
    const oldLayer = findLayerById(parcelId);
    if (oldLayer) {
      try { oldLayer.remove(); } catch (e) {}
    }

    // Dodaj nową warstwę
    if (newData) {
      addParcelToMap(parcelId, newData);
    }
  }

  /**
   * Odświeża listę działek w panelu bocznym.
   */
  function refreshParcelList() {
    const activeTab = document.querySelector(".tab-btn.active")?.dataset.tab || "parcels";
    filterAndDisplayParcels(activeTab);
  }

  /**
   * Zmienia typ działki z walidacją geometrii.
   */
  async function changeParcelType(parcelId, currentCategory) {
    const POINT_CATEGORIES = ["budynek", "kapliczka", "obiekt_specjalny", "dworzec"];
    const NON_POINT_CATEGORIES = ["budowlana", "rolna", "droga", "rzeka", "las", "pastwisko"];

    let allowedTargetCategories;
    const isCurrentPoint = POINT_CATEGORIES.includes(currentCategory);

    // Określ dozwolone kategorie
    if (isCurrentPoint) {
      allowedTargetCategories = POINT_CATEGORIES;
    } else if (NON_POINT_CATEGORIES.includes(currentCategory)) {
      allowedTargetCategories = NON_POINT_CATEGORIES;
    } else {
      alert(`Kategoria "${currentCategory}" jest nieznana.`);
      return;
    }
    
    const allowedOptionsString = allowedTargetCategories
      .filter(cat => cat !== currentCategory)
      .map(cat => formatCategoryName(cat))
      .join(', ');

    const displayId = getDisplayId(parcelId);
    const displayCurrentCategory = formatCategoryName(currentCategory);
    const newCategory = prompt(
      `Zmiana typu obiektu "${displayId}"\n` +
      `Obecny typ: ${displayCurrentCategory}\n\n` +
      `Możliwe typy: ${allowedOptionsString}\n\n` +
      `Wpisz nowy typ:`
    );

    if (!newCategory || newCategory.trim() === "") return;

    // Normalizuj wprowadzoną wartość (zamień spacje na podkreślniki)
    const normalizedNewCategory = newCategory.trim().toLowerCase().replace(/\s+/g, '_');

    if (normalizedNewCategory === currentCategory) return;

    if (!allowedTargetCategories.includes(normalizedNewCategory)) {
      alert(
        `Błąd: Niedozwolona zmiana!\n` +
        `Dozwolone: ${allowedOptionsString}`
      );
      return;
    }

    // Wysłanie do API
    try {
      const response = await fetch(`/api/parcel/${encodeURIComponent(parcelId)}/category`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kategoria: normalizedNewCategory }),
      });
      const data = await response.json();
      alert(data.message);
      if (data.status === "success") {
        // Klucz się zmienił - usuń stary
        const oldData = currentParcelsData[parcelId];
        delete currentParcelsData[parcelId];

        // Dodaj nowy
        const newFullKey = data.full_key || `${getDisplayId(parcelId)}_${normalizedNewCategory}`;
        const newData = { ...oldData, kategoria: normalizedNewCategory };
        currentParcelsData[newFullKey] = newData;

        // Odśwież warstwę i listę
        refreshLayer(parcelId, null); // Usuń starą
        refreshLayer(newFullKey, newData); // Dodaj nową
        refreshParcelList();
      }
    } catch (err) {
      alert("Błąd zmiany typu: " + err.message);
    }
  }

  /**
   * Zmienia nazwę działki.
   */
  async function renameParcel(oldId) {
    const oldDisplayId = getDisplayId(oldId);
    const newId = prompt(`Nowa nazwa dla "${oldDisplayId}":`, oldDisplayId);

    if (!newId || newId.trim() === "") {
      alert("Nazwa nie może być pusta.");
      return;
    }

    if (newId === oldDisplayId) return;

    // Pobierz kategorię z istniejącej działki
    const parcelData = currentParcelsData[oldId];
    if (parcelData) {
      const category = parcelData.kategoria;
      const newFullKey = `${newId}_${category}`;

      if (currentParcelsData[newFullKey]) {
        alert(`Błąd: Obiekt "${newId}" typu "${category}" już istnieje!`);
        return;
      }
    }

    try {
      const response = await fetch(`/api/parcel/rename/${encodeURIComponent(oldId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_id: newId }),
      });

      const data = await response.json();
      alert(data.message);
      if (data.status === "success") {
        // Klucz się zmienił - przenieś dane
        const oldData = currentParcelsData[oldId];
        delete currentParcelsData[oldId];

        const newFullKey = data.full_key || `${newId}_${parcelData.kategoria}`;
        currentParcelsData[newFullKey] = oldData;

        // Odśwież warstwę i listę
        refreshLayer(oldId, null); // Usuń starą
        refreshLayer(newFullKey, oldData); // Dodaj nową
        refreshParcelList();
      }
    } catch (err) {
      alert("Błąd sieciowy: " + err.message);
    }
  }

  /**
   * Usuwa działkę po potwierdzeniu.
   */
  async function deleteParcel(parcelId) {
    const displayId = getDisplayId(parcelId);
    if (!confirm(`Usunąć obiekt '${displayId}'?\n\nNieodwracalne!`))
      return;

    const response = await fetch(`/api/parcel/${parcelId}`, {
      method: "DELETE",
    });
    const data = await response.json();
    alert(data.message);
    
    if (data.status === "success") {
      findLayerById(parcelId)?.remove();
      document.querySelector(`#parcel-list li[data-parcel-id="${parcelId}"]`)?.remove();
      delete currentParcelsData[parcelId];
    }
  }

  /**
   * Usuwa wszystkie obiekty z podwójnym potwierdzeniem.
   */
  async function deleteAllParcels() {
    if (!confirm("Usunąć WSZYSTKIE obiekty?\n\nNieodwracalne!")) return;

    const confirmText = "USUŃ WSZYSTKO";
    const userInput = prompt(`Wpisz dokładnie: "${confirmText}"`);

    if (userInput !== confirmText) {
      alert("Anulowano - niepoprawny tekst.");
      return;
    }

    try {
      const response = await fetch('/api/parcels/delete_all', { method: 'DELETE' });
      const data = await response.json();
      alert(data.message);
      if (data.status === 'success') location.reload();
    } catch (err) {
      alert("Błąd: " + err.message);
    }
  }

  // ==========================================================================
  // SYSTEM KOPII ZAPASOWYCH
  // ==========================================================================

  // Otwieranie modala
  document.getElementById("open-backup-manager").onclick = () => {
    document.getElementById("backupModal").style.display = "block";
    loadBackupList();
  };

  // Zamykanie modala
  document.querySelector(".close-button").onclick = () => {
    document.getElementById("backupModal").style.display = "none";
  };

  // Tworzenie kopii
  document.getElementById("create-backup-btn").addEventListener("click", () => {
    fetch("/backup", { method: "POST" })
      .then((res) => res.json())
      .then((data) => {
        alert(data.message);
        if (data.status === "success") loadBackupList();
      });
  });

  // Delegacja akcji kopii
  document.getElementById("backup-list").addEventListener("click", (e) => {
    const target = e.target;
    const filename = target.closest("li")?.dataset.filename;
    if (!filename) return;

    const headers = { "Content-Type": "application/json" };
    const body = JSON.stringify({ filename });

    // Przywracanie
    if (target.matches(".btn-restore") && 
        confirm(`Przywrócić "${filename}"?\n\nDane zostaną nadpisane!`)) {
      fetch("/restore", { method: "POST", headers, body })
        .then((res) => res.json())
        .then((data) => {
          alert(data.message);
          if (data.status === "success") location.reload();
        });
    }

    // Usuwanie
    if (target.matches(".btn-delete") && 
        confirm(`Usunąć "${filename}"?\n\nNieodwracalne!`)) {
      fetch("/delete_backup", { method: "POST", headers, body })
        .then(async (res) => {
          const payload = await res.json().catch(() => null);
          if (!res.ok) {
            const msg = payload?.message || "Błąd usuwania.";
            throw new Error(msg);
          }
          return payload;
        })
        .then((data) => {
          alert(data.message);
          loadBackupList();
        })
        .catch((err) => alert(err.message));
    }
  });

  /**
   * Ładuje listę kopii zapasowych.
   */
  function loadBackupList() {
    const backupList = document.getElementById("backup-list");
    backupList.innerHTML = "<li>Ładowanie...</li>";
    
    fetch("/api/backups")
      .then((r) => r.json())
      .then((files) => {
        backupList.innerHTML = files.length === 0 
          ? "<li>Brak kopii.</li>" 
          : "";
        
        files.forEach((file) => {
          const li = document.createElement("li");
          li.dataset.filename = file;
          li.innerHTML = `
            <span>${file}</span>
            <div class="backup-actions">
              <button class="btn-restore">Przywróć</button>
              <button class="btn-delete">Usuń</button>
            </div>`;
          backupList.appendChild(li);
        });
      })
      .catch(() => backupList.innerHTML = "<li>Błąd wczytywania.</li>");
  }

  // ==========================================================================
  // ZAMYKANIE APLIKACJI
  // ==========================================================================
  document.getElementById("shutdown-app-btn").addEventListener("click", () => {
    if (!confirm("Zamknąć aplikację?\n\nSerwer zostanie wyłączony!")) return;

    fetch("/api/shutdown", { method: "POST" })
      .then((response) => {
        if (response.ok) {
          document.body.innerHTML = `
            <div style="text-align:center; padding-top:100px; font-size:1.5em; color:#333;">
              <h1>Serwer wyłączony. Do zobaczenia!</h1>
            </div>`;
          setTimeout(() => window.close(), 700);
        } else {
          alert("Błąd zamykania serwera.");
        }
      })
      .catch((error) => {
        console.warn("Błąd komunikacji:", error);
        document.body.innerHTML = `
          <div style="text-align:center; padding-top:100px; font-size:1.5em; color:#333;">
            <h1>Serwer wyłączony. Do zobaczenia!</h1>
          </div>`;
        setTimeout(() => window.close(), 700);
      });
  });

  // Usuwanie wszystkich
  document.getElementById('delete-all-parcels-btn').addEventListener('click', deleteAllParcels);

  // ==========================================================================
  // INICJALIZACJA APLIKACJI
  // ==========================================================================
  loadAndDrawParcels();
  
  console.log("✅ Edytor działek załadowany");
  console.log("📍 Współrzędne: 50.0614 N, 21.2461 E");
  console.log("🔍 Maksymalny zoom: 21");
});