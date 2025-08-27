/**
 * Plik: parcel_editor.js
 * Opis: Główny skrypt aplikacji do edycji działek na mapie interaktywnej.
 *       Obsługuje rysowanie, edycję i zarządzanie obiektami geograficznymi
 *       z wykorzystaniem bibliotek Leaflet i Leaflet.PM (Geoman).
 */

document.addEventListener("DOMContentLoaded", function () {
  /**
   * === SEKCJA: INICJALIZACJA STANU APLIKACJI ===
   * Zmienne globalne przechowujące stan aplikacji podczas jej działania.
   */
  let currentParcelsData = {};    // Obiekt ze wszystkimi działkami pobranymi z serwera
  let activeDrawingLayer = null;  // Warstwa aktualnie rysowana
  let editedLayer = null;         // Warstwa w trakcie edycji
  let currentCategory = null;     // Aktualnie rysowana kategoria (punkt/poligon)

  /**
   * === SEKCJA: KONFIGURACJA MAPY LEAFLET ===
   * Ustawienia granic, poziomów powiększenia i obrazu podkładu.
   */
  const southWest = L.latLng(-10.5, 0.5);
  const northEast = L.latLng(0.5, 10.5);
  const bounds = L.latLngBounds(southWest, northEast);
  
  // Inicjalizacja głównego obiektu mapy z ograniczeniami
  const map = L.map("map", {
    maxBounds: bounds,
    minZoom: 1,
    maxZoom: 13,
  }).setView([-5, 5], 9);
  
  // Dodanie obrazu mapy historycznej jako warstwy podkładowej
  L.imageOverlay("/static/mapa.jpg", [
    [-10, 0],
    [0, 10],
  ]).addTo(map);

  /**
   * Funkcje pomocnicze do konwersji współrzędnych.
   * Obecnie są to funkcje tożsamościowe, przygotowane na przyszłe transformacje.
   */
  const toLatLng = ([x, y]) => [x, y];
  const toDataCoords = ([lat, lng]) => [lat, lng];

  /**
   * Funkcja throttle ograniczająca częstotliwość wywołań.
   * @param {Function} func - Funkcja do ograniczenia
   * @param {number} limit - Minimalny czas między wywołaniami w ms
   * @returns {Function} - Funkcja z ograniczeniem wywołań
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

  /**
   * === SEKCJA: KONTROLKA WSPÓŁRZĘDNYCH ===
   * Niestandardowa kontrolka Leaflet wyświetlająca współrzędne kursora.
   */
  const CoordinatesControl = L.Control.extend({
    onAdd: function (map) {
      // Tworzenie elementu DOM dla kontrolki
      this._div = L.DomUtil.create("div", "leaflet-control-coordinates");
      this._div.innerHTML = "Najedź na mapę...";
      return this._div;
    },
    update: function (latlng) {
      if (latlng) {
        // Formatowanie współrzędnych z dokładnością do 3 miejsc po przecinku
        const x = latlng.lng.toFixed(3);
        const y = latlng.lat.toFixed(3);
        this._div.innerHTML = `X: ${x}<br>Y: ${y}`;
      } else {
        this._div.innerHTML = "Najedź na mapę...";
      }
    },
  });
  
  // Dodanie kontrolki do mapy
  const coordDisplay = new CoordinatesControl({ position: "bottomright" });
  coordDisplay.addTo(map);

  // Aktualizacja współrzędnych przy ruchu myszy (z ograniczeniem częstotliwości)
  map.on(
    "mousemove",
    throttle((e) => {
      coordDisplay.update(e.latlng);
    }, 100),
  );

  // Czyszczenie wyświetlacza gdy kursor opuści mapę
  map.on("mouseout", () => coordDisplay.update());

  /**
   * === SEKCJA: KONFIGURACJA LEAFLET.PM (GEOMAN) ===
   * Inicjalizacja narzędzi do rysowania i edycji geometrii.
   */
  map.pm.setLang("pl");  // Ustawienie języka polskiego
  
  // Wyłączenie domyślnych kontrolek - używamy własnego interfejsu
  map.pm.addControls({
    position: "topleft",
    drawControls: false,
    editControls: false,
  });

  // Grupa warstw dla wszystkich działek
  const parcelLayerGroup = L.layerGroup().addTo(map);

  /**
   * === SEKCJA: REFERENCJE DO ELEMENTÓW DOM ===
   */
  const createActions = document.getElementById("create-actions");
  const dynamicActions = document.getElementById("dynamic-actions");
  const parcelList = document.getElementById("parcel-list");

  // --- Uzupełnienie przycisków rysowania kategorii punktowych (jeśli brak) ---
  (function ensurePointCategoryButtons() {
    if (!createActions) return;

    // Sprawdź, czy istnieje już przycisk dla 'budynek' i 'obiekt_specjalny'
    const hasBudynek = !!createActions.querySelector('button[data-category="budynek"]');
    const hasSpec = !!createActions.querySelector('button[data-category="obiekt_specjalny"]');

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

  // Delegacja klików: start rysowania po kliknięciu przycisku kategorii
  if (createActions) {
    createActions.addEventListener("click", (ev) => {
      const btn = ev.target.closest('button[data-category]');
      if (!btn) return;
      ev.preventDefault();
      enterDrawingMode(btn.dataset.category);
    });
  }
  /**
   * === SEKCJA: FUNKCJE TRYBU RYSOWANIA ===
   */
  
  /**
   * Włącza tryb rysowania nowej działki określonej kategorii.
   * @param {string} category - Kategoria obiektu do narysowania
   */
  function enterDrawingMode(category) {
    // Zapamiętanie aktywnej kategorii i podświetlenie przycisku
    currentCategory = category;
    if (createActions) {
      const btns = createActions.querySelectorAll('button[data-category]');
      btns.forEach((b) => b.classList.toggle('active', b.dataset.category === String(category)));
    }

    // Ukrycie standardowego paska narzędzi
    createActions.style.display = "none";

    // Czy rysujemy punkt (Marker)?
    const POINT_CATEGORIES = ["budynek", "kapliczka", "obiekt_specjalny", "dworzec"];
    const isPoint = POINT_CATEGORIES.includes(String(category || "").toLowerCase());

    // Pasek akcji (dla punktu nie potrzebujemy „Cofnij/Zakończ”)
    dynamicActions.innerHTML = isPoint
      ? `
        <span class="toolbar-label">Rysujesz: ${category}</span>
        <button id="cancel-btn" class="action-cancel">Anuluj</button>`
      : `
        <span class="toolbar-label">Rysujesz: ${category}</span>
        <button id="undo-btn" class="action-undo">Cofnij Punkt</button>
        <button id="finish-btn" class="action-finish">Zakończ</button>
        <button id="cancel-btn" class="action-cancel">Anuluj</button>`;
    dynamicActions.style.display = "flex";

    // Włączenie odpowiedniego trybu rysowania
    if (isPoint) {
      map.pm.enableDraw("Marker");
    } else {
      map.pm.enableDraw("Polygon", {
        templineStyle: { color: "magenta", weight: 2 },
        hintlineStyle: { color: "magenta", dashArray: "5,5" },
        pathOptions: { color: "magenta" },
      });
    }

    // Nasłuch zakończenia tworzenia geometrii
    map.on("pm:create", handleDrawingFinish);

    // Podpięcie kontrolek
    const cancelBtn = document.getElementById("cancel-btn");
    if (cancelBtn) cancelBtn.onclick = exitDrawingMode;

    if (!isPoint) {
      const undoBtn = document.getElementById("undo-btn");
      const finishBtn = document.getElementById("finish-btn");
      if (undoBtn && map.pm.Draw.Polygon && map.pm.Draw.Polygon._removeLastVertex) {
        undoBtn.onclick = () => map.pm.Draw.Polygon._removeLastVertex();
      }
      if (finishBtn && map.pm.Draw.Polygon && map.pm.Draw.Polygon._finishShape) {
        finishBtn.onclick = () => map.pm.Draw.Polygon._finishShape();
      }
    }
  }

  /**
   * Obsługuje zakończenie rysowania nowej działki.
   * Prosi o ID, waliduje dane i wysyła do serwera.
   * @param {Event} e - Zdarzenie zakończenia rysowania z Leaflet.PM
   */
  function handleDrawingFinish(e) {
    const layer = e.layer;
    activeDrawingLayer = layer;

    const category = document.querySelector("#create-actions button.active")
      ?.dataset.category || "rolna";

    const parcelId = prompt(`Podaj nazwę / numer dla obiektu typu "${category}":`);

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
   * Anuluje tryb rysowania i usuwa niezapisane warstwy.
   */
  function cancelDrawingMode() {
    // Usunięcie wszystkich warstw będących w trakcie rysowania
    map.pm.getGeomanDrawLayers().forEach((layer) => layer.remove());
    exitDrawingMode();
  }

  /**
   * Wyłącza tryb rysowania i przywraca standardowy interfejs.
   */
  function exitDrawingMode() {
    // Wyłączenie trybów rysowania (na wszelki wypadek oba)
    try { map.pm.disableDraw("Marker"); } catch (e) {}
    try { map.pm.disableDraw("Polygon"); } catch (e) {}

    // Odpięcie nasłuchu tworzenia
    map.off("pm:create", handleDrawingFinish);

    // Usunięcie ewentualnych „niedomkniętych” warstw rysowania
    try {
      if (map.pm && typeof map.pm.getGeomanDrawLayers === "function") {
        map.pm.getGeomanDrawLayers().forEach((layer) => {
          try { layer.remove(); } catch (e) {}
        });
      }
    } catch (e) {}

    // Reset UI
    if (createActions) {
      createActions.style.display = "flex";
      const btns = createActions.querySelectorAll('button[data-category]');
      btns.forEach((b) => b.classList.remove('active'));
    }
    if (dynamicActions) {
      dynamicActions.style.display = "none";
      dynamicActions.innerHTML = "";
    }

    // Reset stanu
    activeDrawingLayer = null;
    currentCategory = null;
  }


  /**
   * === SEKCJA: FUNKCJE TRYBU EDYCJI ===
   */

  /**
   * Włącza tryb edycji dla wybranej działki.
   * @param {string} parcelId - ID działki do edycji
   */
  function enterEditMode(parcelId) {
    const layer = findLayerById(parcelId);
    if (!layer) return;

    editedLayer = layer;
    // Włączenie edycji warstwy z opcją samoprzecinania
    layer.pm.enable({ allowSelfIntersection: true });

    // Zmiana interfejsu na tryb edycji
    createActions.style.display = "none";
    dynamicActions.innerHTML = `
            <span class="toolbar-label">Edytujesz: ${parcelId}</span>
            <button id="save-edit-btn" class="action-save-changes">Zapisz Zmiany</button>
            <button id="cancel-edit-btn" class="action-cancel">Anuluj Edycję</button>`;
    dynamicActions.style.display = "flex";

    // Obsługa przycisków edycji
    document.getElementById("save-edit-btn").onclick = () => saveEdit(parcelId);
    document.getElementById("cancel-edit-btn").onclick = exitEditMode;
  }

  /**
   * Zapisuje zmiany w edytowanej działce do serwera.
   * @param {string} parcelId - ID edytowanej działki
   */
  function saveEdit(parcelId) {
    let geometryToSave;

    if (editedLayer && editedLayer.getLatLng && !editedLayer.getLatLngs) {
      // Marker: [lat, lng]
      const ll = editedLayer.getLatLng();
      geometryToSave = [ll.lat, ll.lng];
    } else if (editedLayer && editedLayer.getLatLngs) {
      // Linia/Poligon: [[lat,lng], ...]
      const latLngs = editedLayer.getLatLngs();
      const ring = Array.isArray(latLngs[0]) ? latLngs[0] : latLngs; // obsługa Polyline/Polygon
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
   * Wyłącza tryb edycji i przywraca standardowy interfejs.
   */
  function exitEditMode() {
    // Wyłączenie edycji na warstwie
    if (editedLayer) editedLayer.pm.disable();
    editedLayer = null;
    
    // Przywrócenie standardowego interfejsu
    createActions.style.display = "flex";
    dynamicActions.style.display = "none";
  }

  /**
   * === SEKCJA: ŁADOWANIE I RENDEROWANIE DZIAŁEK ===
   */

  /**
   * Główna funkcja ładująca wszystkie działki z serwera i rysująca je na mapie.
   * Przypisuje style wizualne na podstawie kategorii obiektów.
   */
  function loadAndDrawParcels() {
    // Obiekt definiujący style dla każdej kategorii działek
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
        fill: false  // Drogi renderowane jako linie bez wypełnienia
      },
      rzeka: { 
        color: "#3498db", 
        weight: 4, 
        fill: false  // Rzeki renderowane jako linie bez wypełnienia
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
      },  // Styl domyślny dla nierozpoznanych kategorii
    };

    // Pobranie danych działek z API
    fetch("/api/parcels")
      .then((r) => r.json())
      .then((data) => {
        // Zapisanie danych lokalnie i wyczyszczenie starej warstwy
        currentParcelsData = data;
        parcelLayerGroup.clearLayers();
        
        // Iteracja po wszystkich działkach i dodanie ich do mapy
        Object.entries(data).forEach(([id, p]) => {
          const g = p.geometria;
          if (!g || !g.length) return;

          // Kategorie punktowe (pinezki)
          const POINT_CATEGORIES = ["budynek", "kapliczka", "obiekt_specjalny", "dworzec"];
          const isPointCategory = POINT_CATEGORIES.includes(String(p.kategoria || "").toLowerCase());

          // Rozpoznanie kształtu po strukturze geometrii
          const isPointGeom = Array.isArray(g) && typeof g[0] === "number" && typeof g[1] === "number";
          const isArrayOfPairs = Array.isArray(g) && Array.isArray(g[0]) && typeof g[0][0] === "number";

          let layer;
          const styleOptions = categoryStyles[p.kategoria] || categoryStyles["default"];

          if (isPointCategory || isPointGeom) {
            // Punkt: [lat, lng]
            const [lat, lng] = g;
            layer = L.marker([lat, lng]);  // pinezka
          } else if (String(p.kategoria).toLowerCase() === "droga" || String(p.kategoria).toLowerCase() === "rzeka") {
            // Linia: [[lat,lng], ...]
            const latLngs = isArrayOfPairs ? g.map(toLatLng) : [];
            layer = L.polyline(latLngs, styleOptions);
          } else {
            // Poligon: [[lat,lng], ...]
            const latLngs = isArrayOfPairs ? g.map(toLatLng) : [];
            layer = L.polygon(latLngs, styleOptions);
          }

          // Meta do identyfikacji i ewentualne style
          layer.parcelId = id;
          if (layer.setStyle) layer.originalStyle = styleOptions;

          // Popup i dodanie do grupy
          layer
            .bindPopup(
              `<b>ID:</b> ${id}<br><b>Kategoria:</b> ${p.kategoria || "Brak danych"}`
            )
            .addTo(parcelLayerGroup);
        });
        
        // Zastosowanie domyślnego filtrowania
        filterAndDisplayParcels("parcels");
      });
  }

  /**
   * Filtruje działki według kategorii dla wyświetlenia w odpowiedniej zakładce.
   * @param {string} activeTab - Nazwa aktywnej zakładki ("parcels" lub inne)
   */
  function filterAndDisplayParcels(activeTab) {
    // Kategorie uznawane za działki właściwe
    const parcelCategories = ["rolna", "budowlana"];

    // Filtrowanie danych na podstawie kategorii
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
   * Aktualizuje listę działek w panelu bocznym z interaktywnością.
   * @param {Object} parcelsToShow - Obiekty do wyświetlenia w liście
   */
  function updateParcelList(parcelsToShow) {
    // Wyczyszczenie istniejącej listy
    parcelList.innerHTML = "";
    
    // Sortowanie alfanumeryczne i renderowanie elementów listy
    Object.entries(parcelsToShow)
      .sort(([idA, idB]) =>
        idA.localeCompare(idB, undefined, {
          numeric: true,
          sensitivity: "base",
        }),
      )
      .forEach(([id, p]) => {
        const li = document.createElement("li");
        li.dataset.parcelId = id;
        li.innerHTML = `
          <div class="parcel-info">
            <span class="parcel-id">${id}</span>
            <span class="parcel-category">${p.kategoria || "-"}</span>
          </div>
          <div class="parcel-actions">
            <button title="Edytuj geometrię" class="btn-action btn-edit-geom">✏️</button>
            <button title="Zmień ID" class="btn-action btn-change-id">🏷️</button>
            <button title="Usuń" class="btn-action btn-delete-parcel">❌</button>
          </div>`;

        // fokus po kliknięciu
        const infoDiv = li.querySelector(".parcel-info");
        infoDiv.onclick = () => {
          const layer = findLayerById(id);
          if (!layer) return;

          // Marker: centrowanie i zoom; linia/poligon: fitBounds
          if (layer.getLatLng) {
            map.setView(layer.getLatLng(), Math.max(map.getZoom(), 17));
          } else if (layer.getBounds) {
            map.fitBounds(layer.getBounds().pad(0.1));
          }
          layer.openPopup && layer.openPopup();
        };

        // podświetlanie (tylko obiekty, które wspierają style)
        li.addEventListener("mouseenter", () => {
          const layer = findLayerById(id);
          if (layer && layer.setStyle) {
            layer.setStyle({ fillColor: "#FFFF00", fillOpacity: 0.7 });
            layer.bringToFront && layer.bringToFront();
          }
        });

        // przywracanie stylu (jeśli istniał)
        li.addEventListener("mouseleave", () => {
          const layer = findLayerById(id);
          if (layer && layer.setStyle && layer.originalStyle) {
            layer.setStyle(layer.originalStyle);
          }
        });

        parcelList.appendChild(li);
      });
  }

  /**
   * === SEKCJA: OBSŁUGA ZDARZEŃ INTERFEJSU UŻYTKOWNIKA ===
   */

  /**
   * Obsługa przełączania zakładek w panelu bocznym.
   */
  document.querySelector(".sidebar-tabs").addEventListener("click", (e) => {
    if (e.target.matches(".tab-btn")) {
      // Aktualizacja klasy active na zakładkach
      document
        .querySelectorAll(".tab-btn")
        .forEach((btn) => btn.classList.remove("active"));
      e.target.classList.add("active");
      
      // Zastosowanie filtrowania dla nowej zakładki
      filterAndDisplayParcels(e.target.dataset.tab);
    }
  });

  /**
   * Obsługa wyszukiwania/filtrowania działek w czasie rzeczywistym.
   */
  document.getElementById("search-filter").addEventListener("input", (e) => {
    const filter = e.target.value.toLowerCase();
    
    // Pokazywanie/ukrywanie elementów listy na podstawie wyszukiwania
    document.querySelectorAll("#parcel-list li").forEach((li) => {
      li.style.display = li.textContent.toLowerCase().includes(filter)
        ? "flex"
        : "none";
    });
  });

  /**
   * Obsługa przycisków rozpoczęcia rysowania nowych obiektów.
   */
  createActions.addEventListener("click", (e) => {
    if (e.target.matches("button")) {
      // Oznaczenie aktywnego przycisku kategorii
      document
        .querySelectorAll("#create-actions button")
        .forEach((b) => b.classList.remove("active"));
      e.target.classList.add("active");
      
      // Włączenie trybu rysowania dla wybranej kategorii
      enterDrawingMode(e.target.dataset.category);
    }
  });

  /**
   * Delegacja zdarzeń dla akcji na liście działek.
   * Obsługuje edycję, zmianę ID i usuwanie.
   */
  parcelList.addEventListener("click", async (e) => {
    const button = e.target.closest(".btn-action");
    if (!button) return;

    const parcelId = button.closest("li")?.dataset.parcelId;
    if (!parcelId) return;

    // Rozpoznanie typu akcji na podstawie klasy przycisku
    if (button.classList.contains("btn-edit-geom")) {
      enterEditMode(parcelId);
    } else if (button.classList.contains("btn-change-id")) {
      renameParcel(parcelId);
    } else if (button.classList.contains("btn-delete-parcel")) {
      deleteParcel(parcelId);
    }
  });

  /**
   * === SEKCJA: FUNKCJE POMOCNICZE ===
   */

  /**
   * Znajduje warstwę na mapie po ID działki.
   * @param {string} id - ID szukanej działki
   * @returns {Layer|undefined} - Znaleziona warstwa lub undefined
   */
  function findLayerById(id) {
    return parcelLayerGroup.getLayers().find((layer) => layer.parcelId === id);
  }

  /**
   * Zmienia ID istniejącej działki po walidacji.
   * @param {string} oldId - Obecne ID działki do zmiany
   */
  async function renameParcel(oldId) {
    const newId = prompt(`Nowa nazwa/numer dla '${oldId}':`, oldId);
    
    // Walidacja wprowadzonego ID
    if (!newId || newId === oldId) return;
    
    // Sprawdzenie czy nowe ID nie jest już zajęte
    if (currentParcelsData[newId]) {
      return alert(`Błąd: ID '${newId}' jest już zajęte!`);
    }

    // Wysłanie żądania zmiany ID do API
    fetch(`/api/parcel/rename/${oldId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_id: newId }),
    })
      .then((r) => r.json())
      .then((data) => {
        alert(data.message);
        if (data.status === "success") location.reload();
      });
  }

  /**
   * Usuwa działkę po potwierdzeniu przez użytkownika.
   * @param {string} parcelId - ID działki do usunięcia
   */
  async function deleteParcel(parcelId) {
    // Potwierdzenie operacji przez użytkownika
    if (!confirm(`Usunąć obiekt '${parcelId}'? Tej operacji nie można cofnąć.`))
      return;

    // Wysłanie żądania usunięcia do API
    const response = await fetch(`/api/parcel/${parcelId}`, {
      method: "DELETE",
    });
    const data = await response.json();
    alert(data.message);
    
    // Aktualizacja lokalnego stanu po pomyślnym usunięciu
    if (data.status === "success") {
      // Usunięcie warstwy z mapy
      findLayerById(parcelId)?.remove();
      
      // Usunięcie elementu z listy DOM
      document
        .querySelector(`#parcel-list li[data-parcel-id="${parcelId}"]`)
        ?.remove();
      
      // Usunięcie z lokalnych danych
      delete currentParcelsData[parcelId];
    }
  }

  /**
   * === SEKCJA: OBSŁUGA KOPII ZAPASOWYCH ===
   */

  /**
   * Otwiera modal menedżera kopii zapasowych i ładuje listę.
   */
  document.getElementById("open-backup-manager").onclick = () => {
    document.getElementById("backupModal").style.display = "block";
    loadBackupList();  // Odświeżenie listy przy każdym otwarciu
  };

  /**
   * Zamyka modal menedżera kopii zapasowych.
   */
  document.querySelector(".close-button").onclick = () => {
    document.getElementById("backupModal").style.display = "none";
  };

  /**
   * Obsługa tworzenia nowej kopii zapasowej.
   */
  document.getElementById("create-backup-btn").addEventListener("click", () => {
    // Wysłanie żądania utworzenia kopii do API
    fetch("/backup", { method: "POST" })
      .then((res) => res.json())
      .then((data) => {
        alert(data.message);
        // Odświeżenie listy po pomyślnym utworzeniu
        if (data.status === "success") loadBackupList();
      });
  });

  /**
   * Delegacja zdarzeń dla akcji na liście kopii zapasowych.
   * Obsługuje przywracanie i usuwanie kopii.
   */
  document.getElementById("backup-list").addEventListener("click", (e) => {
    const target = e.target;
    const filename = target.closest("li")?.dataset.filename;
    if (!filename) return;

    const headers = { "Content-Type": "application/json" };
    const body = JSON.stringify({ filename });

    // Obsługa przywracania kopii zapasowej
    if (
      target.matches(".btn-restore") &&
      confirm(`Przywrócić plik "${filename}"?`)
    ) {
      fetch("/restore", { method: "POST", headers, body })
        .then((res) => res.json())
        .then((data) => {
          alert(data.message);
          // Odświeżenie strony po pomyślnym przywróceniu
          if (data.status === "success") {
            location.reload();
          }
        });
    }

    // Obsługa usuwania kopii zapasowej
    if (
      target.matches(".btn-delete") &&
      confirm(`Usunąć plik "${filename}"? Tej operacji nie można cofnąć.`)
    ) {
      fetch("/delete_backup", { method: "POST", headers, body })
        .then(async (res) => {
          const payload = await res.json().catch(() => null);
          if (!res.ok) {
            const msg = payload?.message || "Błąd usuwania kopii zapasowej.";
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
   * Ładuje i wyświetla listę dostępnych kopii zapasowych.
   */
  function loadBackupList() {
    const backupList = document.getElementById("backup-list");
    
    // Wyświetlenie komunikatu ładowania
    backupList.innerHTML = "<li>Ładowanie...</li>";
    
    // Pobranie listy plików z API
    fetch("/api/backups")
      .then((r) => r.json())
      .then((files) => {
        // Renderowanie listy lub komunikatu o braku kopii
        backupList.innerHTML =
          files.length === 0 ? "<li>Brak kopii zapasowych.</li>" : "";
        
        // Tworzenie elementów listy dla każdego pliku
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
      .catch(
        // Obsługa błędów podczas ładowania listy
        (error) => (backupList.innerHTML = "<li>Błąd wczytywania listy.</li>"),
      );
  }

  /**
   * === SEKCJA: OBSŁUGA ZAMYKANIA APLIKACJI ===
   */

  /**
   * Obsługa przycisku zamykania aplikacji.
   * Wysyła żądanie zamknięcia serwera i wyświetla komunikat pożegnalny.
   */
  document.getElementById("shutdown-app-btn").addEventListener("click", () => {
    // Potwierdzenie zamiaru zamknięcia przez użytkownika
    if (
      !confirm(
        "Czy na pewno chcesz zamknąć aplikację? Serwer zostanie wyłączony.",
      )
    ) {
      return;
    }

    // Wysłanie żądania zamknięcia do serwera
    fetch("/api/shutdown", { method: "POST" })
      .then((response) => {
        if (response.ok) {
          // Wyświetlenie komunikatu pożegnalnego
          document.body.innerHTML = `
            <div style="text-align:center; padding-top:100px; font-size:1.5em; color:#333;">
              <h1>Serwer został wyłączony. Do zobaczenia!</h1>
            </div>`;
          // Próba automatycznego zamknięcia karty przeglądarki
          setTimeout(() => window.close(), 700);
        } else {
          alert("Wystąpił błąd podczas zamykania serwera.");
        }
      })
      .catch((error) => {
        // Błąd komunikacji jest normalny gdy serwer się nagle zamyka.
        // Wyświetlamy komunikat pożegnalny mimo wszystko.
        console.warn(
          "Wystąpił błąd komunikacji podczas zamykania (to może być normalne):",
          error,
        );
        document.body.innerHTML = `
          <div style="text-align:center; padding-top:100px; font-size:1.5em; color:#333;">
            <h1>Serwer został wyłączony. Do zobaczenia!</h1>
          </div>`;
        setTimeout(() => window.close(), 700);
      });
  });

  /**
   * === INICJALIZACJA APLIKACJI ===
   * Załadowanie wszystkich działek przy starcie aplikacji.
   */
  loadAndDrawParcels();
});