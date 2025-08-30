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
  let currentCategory = null;     // Aktywna kategoria rysowania

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
    const isPoint = POINT_CATEGORIES.includes(String(category || "").toLowerCase());

    // Konfiguracja paska akcji
    dynamicActions.innerHTML = isPoint
      ? `<span class="toolbar-label">Rysujesz: ${category}</span>
         <button id="cancel-btn" class="action-cancel">Anuluj</button>`
      : `<span class="toolbar-label">Rysujesz: ${category}</span>
         <button id="undo-btn" class="action-undo">Cofnij Punkt</button>
         <button id="finish-btn" class="action-finish">Zakończ</button>
         <button id="cancel-btn" class="action-cancel">Anuluj</button>`;
    dynamicActions.style.display = "flex";

    // Włączenie trybu rysowania
    if (isPoint) {
      map.pm.enableDraw("Marker");
    } else {
      map.pm.enableDraw("Polygon", {
        templineStyle: { color: "magenta", weight: 2 },
        hintlineStyle: { color: "magenta", dashArray: "5,5" },
        pathOptions: { color: "magenta" },
      });
    }

    map.on("pm:create", handleDrawingFinish);

    // Podpięcie kontrolek
    const cancelBtn = document.getElementById("cancel-btn");
    if (cancelBtn) cancelBtn.onclick = exitDrawingMode;

    if (!isPoint) {
      const undoBtn = document.getElementById("undo-btn");
      const finishBtn = document.getElementById("finish-btn");
      if (undoBtn && map.pm.Draw.Polygon?._removeLastVertex) {
        undoBtn.onclick = () => map.pm.Draw.Polygon._removeLastVertex();
      }
      if (finishBtn && map.pm.Draw.Polygon?._finishShape) {
        finishBtn.onclick = () => map.pm.Draw.Polygon._finishShape();
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

    const parcelId = prompt(`Podaj nazwę/numer dla obiektu typu "${category}":`);

    if (!parcelId) {
      try { layer.remove(); } catch (err) {}
      activeDrawingLayer = null;
      exitDrawingMode();
      return;
    }

    if (currentParcelsData[parcelId]) {
      alert(`Błąd: Działka o ID '${parcelId}' już istnieje!`);
      try { layer.remove(); } catch (err) {}
      activeDrawingLayer = null;
      exitDrawingMode();
      return;
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

    const newParcel = { kategoria: category, geometria: geometryToSave };

    // Zapis do serwera
    fetch("/api/parcel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: parcelId, parcel: newParcel }),
    })
      .then((res) => res.json())
      .then((data) => {
        alert(data.message);
        if (data.status === "success") location.reload();
        else exitDrawingMode();
      })
      .catch(() => exitDrawingMode());
  }

  /**
   * Wyłącza tryb rysowania i przywraca interfejs.
   */
  function exitDrawingMode() {
    try { map.pm.disableDraw("Marker"); } catch (e) {}
    try { map.pm.disableDraw("Polygon"); } catch (e) {}

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
    layer.pm.enable({ allowSelfIntersection: true });

    // Zmiana interfejsu
    createActions.style.display = "none";
    dynamicActions.innerHTML = `
      <span class="toolbar-label">Edytujesz geometrię: ${parcelId}</span>
      <button id="save-edit-btn" class="action-save-changes">Zapisz Zmiany</button>
      <button id="cancel-edit-btn" class="action-cancel">Anuluj Edycję</button>`;
    dynamicActions.style.display = "flex";

    document.getElementById("save-edit-btn").onclick = () => saveEdit(parcelId);
    document.getElementById("cancel-edit-btn").onclick = exitEditMode;
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
        exitEditMode();
        if (data.status === "success") location.reload();
      });
  }

  /**
   * Wyłącza tryb edycji.
   */
  function exitEditMode() {
    if (editedLayer) editedLayer.pm.disable();
    editedLayer = null;
    
    createActions.style.display = "flex";
    dynamicActions.style.display = "none";
  }

  // ==========================================================================
  // RENDEROWANIE DZIAŁEK
  // ==========================================================================

  /**
   * Pobiera i renderuje działki na mapie.
   */
  function loadAndDrawParcels() {
    // Style dla kategorii
    const categoryStyles = {
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

    // Pobranie danych
    fetch("/api/parcels")
      .then((r) => r.json())
      .then((data) => {
        currentParcelsData = data;
        parcelLayerGroup.clearLayers();
        
        // Renderowanie każdej działki
        Object.entries(data).forEach(([id, p]) => {
          const g = p.geometria;
          if (!g || !g.length) return;

          const POINT_CATEGORIES = ["budynek", "kapliczka", "obiekt_specjalny", "dworzec"];
          const isPointCategory = POINT_CATEGORIES.includes(String(p.kategoria || "").toLowerCase());
          const isPointGeom = Array.isArray(g) && typeof g[0] === "number" && typeof g[1] === "number";
          const isArrayOfPairs = Array.isArray(g) && Array.isArray(g[0]) && typeof g[0][0] === "number";

          let layer;
          const styleOptions = categoryStyles[p.kategoria] || categoryStyles["default"];

          // Tworzenie warstwy
          if (isPointCategory || isPointGeom) {
            const [lat, lng] = g;
            layer = L.marker([lat, lng]);
          } else if (["droga", "rzeka"].includes(String(p.kategoria).toLowerCase())) {
            const latLngs = isArrayOfPairs ? g : [];
            layer = L.polyline(latLngs, styleOptions);
          } else {
            const latLngs = isArrayOfPairs ? g : [];
            layer = L.polygon(latLngs, styleOptions);
          }

          // Metadane i popup
          layer.parcelId = id;
          layer.parcelCategory = p.kategoria;
          if (layer.setStyle) layer.originalStyle = styleOptions;

          layer
            .bindPopup(`<b>ID:</b> ${id}<br><b>Kategoria:</b> ${p.kategoria || "Brak danych"}`)
            .addTo(parcelLayerGroup);
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
        li.innerHTML = `
          <div class="parcel-info">
            <span class="parcel-id">${id}</span>
            <span class="parcel-category">${p.kategoria || "-"}</span>
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
      .join(', ');

    const newCategory = prompt(
      `Zmiana typu obiektu "${parcelId}"\n` +
      `Obecny typ: ${currentCategory}\n\n` +
      `Możliwe typy: ${allowedOptionsString}\n\n` +
      `Wpisz nowy typ:`
    );

    if (!newCategory || newCategory.trim() === "") return;
    if (newCategory === currentCategory) return;

    if (!allowedTargetCategories.includes(newCategory)) {
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
        body: JSON.stringify({ kategoria: newCategory }),
      });
      const data = await response.json();
      alert(data.message);
      if (data.status === "success") location.reload();
    } catch (err) {
      alert("Błąd zmiany typu: " + err.message);
    }
  }

  /**
   * Zmienia nazwę działki.
   */
  async function renameParcel(oldId) {
    const newId = prompt(`Nowa nazwa dla "${oldId}":`, oldId);

    if (!newId || newId.trim() === "") {
      alert("Nazwa nie może być pusta.");
      return;
    }
    
    if (newId === oldId) return;

    if (currentParcelsData[newId]) {
      alert(`Błąd: Obiekt "${newId}" już istnieje!`);
      return;
    }

    try {
      const response = await fetch(`/api/parcel/rename/${encodeURIComponent(oldId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_id: newId }),
      });

      const data = await response.json();
      alert(data.message);
      if (data.status === "success") location.reload();
    } catch (err) {
      alert("Błąd sieciowy: " + err.message);
    }
  }

  /**
   * Usuwa działkę po potwierdzeniu.
   */
  async function deleteParcel(parcelId) {
    if (!confirm(`Usunąć obiekt '${parcelId}'?\n\nNieodwracalne!`))
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