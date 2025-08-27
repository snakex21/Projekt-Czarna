/**
 * Plik: map-script.js
 * Opis: Główny skrypt aplikacji interaktywnej mapy katastralnej.
 *       Zarządza inicjalizacją mapy, wczytywaniem i renderowaniem danych,
 *       obsługą interfejsu użytkownika oraz interakcjami na mapie.
 */

document.addEventListener("DOMContentLoaded", initializeApp);

// === 1. DEKLARACJA ZMIENNYCH I STAŁYCH ===

// Główne obiekty aplikacji
let map = null;                    
let allOwnersData = [];            
let allParcelsData = [];           
let geojsonLayer = null;           
let layersByCategory = {};         

// Stan interfejsu użytkownika
let isInCompareMode = false;       
let selectedForCompare = [];       

// Warstwy podświetlania
let highlightedLayer = null;       
let ownerHighlightLayer = null;    

// Paleta kolorów do wyróżniania właścicieli
const HIGHLIGHT_COLORS = [
    "#E6194B", "#F58231", "#FFE119", "#BFDF45", "#3CB44B", 
    "#42D4F4", "#4363D8", "#911EB4", "#F032E6", "#A9A9A9"
];

// === 2. GŁÓWNA FUNKCJA INICJALIZUJĄCA ===

/**
 * Główny punkt wejścia aplikacji. Uruchamiana po załadowaniu DOM.
 */
function initializeApp() {
    console.log("🚀 Aplikacja startuje...");

    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }
    
    initializeMap();
    setupUIEventListeners();
    fetchDataAndBuildInterface();
}

/**
 * Rejestruje główne event listenery dla elementów interfejsu.
 */
function setupUIEventListeners() {
    setupPanelToggles();
    setupToolbarActions();
    setupUniversalSearch();
}

// === 3. INICJALIZACJA I KONFIGURACJA MAPY ===

/**
 * Inicjalizuje mapę Leaflet z podstawowymi ustawieniami.
 * Konfiguruje granice, zoom, warstwy podkładowe, nakładki oraz przełącznik warstw.
 */
function initializeMap() {
    // --- Krok 1: Definicja warstw podkładowych (bazowych) ---
    const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });

    const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    });
    
    const minimalistLayer = L.tileLayer('', {
        attribution: 'Projekt Interaktywna Mapa Katastralna'
    });

    // --- Krok 2: Definicja warstw nakładkowych (overlays) ---

    // NOWE: Współrzędne dla historycznej mapy w przybliżonej lokalizacji Czarnej
    // 50°3′41″N, 21°14′46″E to ok. 50.0614, 21.2461 w stopniach dziesiętnych
    // Definiujemy obszar o boku ok. 4.5 km wokół tego punktu.
    const historicalBounds = [
        [50.0414, 21.2261], // Południowo-zachodni róg
        [50.0814, 21.2661]  // Północno-wschodni róg
    ];

    const historicalMapOverlay = L.imageOverlay("mapa.jpg", historicalBounds);

    geojsonLayer = L.geoJSON(); 

    // --- Krok 3: Inicjalizacja mapy ---

    // Definiujemy nowe, szersze granice, aby można było trochę oddalić mapę
    const maxBounds = L.latLngBounds(
        [50.0, 21.15], 
        [50.12, 21.35]
    );

    map = L.map("map", {
        layers: [satelliteLayer, historicalMapOverlay, geojsonLayer],
        maxBounds: maxBounds,
        minZoom: 12, // Zwiększamy minimalne przybliżenie, by nie oddalić się za bardzo
        maxZoom: 18  // Zwiększamy maksymalne przybliżenie dla szczegółów
    }).setView([50.0614, 21.2461], 14); // Ustawiamy widok na centrum Czarnej z odpowiednim zoomem

    // --- Krok 4: Konfiguracja przełącznika warstw ---

    const baseMaps = {
        "Satelita": satelliteLayer,
        "Mapa drogowa": osmLayer,
        "Tylko działki (tło minimalistyczne)": minimalistLayer
    };

    const overlayMaps = {
        "Narysowane obiekty (działki, drogi)": geojsonLayer,
        "Podkład mapy historycznej z XIX w.": historicalMapOverlay
    };

    L.control.layers(baseMaps, overlayMaps, { 
        position: 'topright', // Pozycja przełącznika na mapie
        collapsed: true       // Czy przełącznik ma być domyślnie zwinięty
    }).addTo(map);

    // --- Krok 5: Dodatkowe funkcje mapy (tak jak wcześniej) ---

    map.on("mousemove", (e) => {
        const coordsDiv = document.getElementById("mouse-coordinates");
        if (coordsDiv) {
            coordsDiv.innerHTML = `${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}`;
        }
    });

    console.log("✅ Mapa zainicjalizowana z przełącznikiem warstw");
}

// === 4. FUNKCJE KOMUNIKACJI Z API ===

/**
 * Pobiera dane z API i buduje interfejs użytkownika.
 * Wykonuje równoległe zapytania dla działek i właścicieli.
 */
function fetchDataAndBuildInterface() {
    console.log("📡 Rozpoczynam pobieranie danych z API...");

    const ownersBox = document.getElementById("ownersList");
    const dzialkiBox = document.getElementById("dzialki_panel");
    const obiektyBox = document.getElementById("obiekty_panel");
    const legendBox = document.getElementById("legend");

    const showLoading = (el, label = "Ładowanie…") => {
        if (!el) return;
        el.dataset._prevHtml = el.innerHTML;
        el.innerHTML = `
            <div class="loading-inline">
                <span class="spinner" aria-hidden="true"></span>
                <span class="loading-text">${label}</span>
            </div>`;
    };

    const clearLoading = (el) => {
        if (!el || !el.dataset._prevHtml) return;
        el.innerHTML = el.dataset._prevHtml;
        delete el.dataset._prevHtml;
    };

    const showError = (el, msg = "Nie udało się wczytać danych.") => {
        if (!el) return;
        el.innerHTML = `<div class="loading-error" role="alert">${msg}</div>`;
    };

    showLoading(ownersBox, "Ładowanie listy właścicieli…");
    showLoading(dzialkiBox, "Ładowanie listy działek…");
    showLoading(obiektyBox, "Ładowanie obiektów…");
    if (legendBox) showLoading(legendBox, "Ładowanie legendy…");

    Promise.all([
        fetch("/api/dzialki").then(res => res.json()),
        fetch("/api/wlasciciele").then(res => res.json()),
    ])
    .then(([dzialkiData, wlascicieleResponse]) => {
        console.log("✅ Pobrano dane pomyślnie!");

        clearLoading(ownersBox);
        clearLoading(dzialkiBox);
        clearLoading(obiektyBox);
        if (legendBox) clearLoading(legendBox);

        allOwnersData = wlascicieleResponse.owners;
        // JEDNA NOWA LINIJKA: Transformujemy współrzędne działek przed ich użyciem
        allParcelsData = transformGeojsonData(dzialkiData.features);

        const metadata = wlascicieleResponse.metadata;
        const sortByOrderBtn = document.getElementById("sortByOrderBtn");
        if (sortByOrderBtn && metadata?.zakres_lp) {
            sortByOrderBtn.textContent = `Numeru Protokołu (${metadata.zakres_lp.min}-${metadata.zakres_lp.max})`;
        }

        renderMapObjects(allParcelsData);
        setupOwnerPanel();
        setupParcelPanel();
        setupLegend();

        handleUrlParameters();
        handleShowHouseByOwnerKeyFromURL();
    })
    .catch((error) => {
        console.error("❌ KRYTYCZNY BŁĄD:", error);
        showError(ownersBox, "Błąd wczytywania właścicieli.");
        showError(dzialkiBox, "Błąd wczytywania działek.");
        showError(obiektyBox, "Błąd wczytywania obiektów.");
        if (legendBox) showError(legendBox, "Błąd wczytywania legendy.");
    });
}

/**
 * Transformuje współrzędne obiektów GeoJSON z pierwotnego, 
 * arbitralnego systemu na rzeczywiste współrzędne geograficzne.
 * @param {Array} features - Tablica obiektów GeoJSON.
 * @returns {Array} - Tablica obiektów z przekształconymi współrzędnymi.
 */
function transformGeojsonData(features) {
    // Definicja granic starego i nowego systemu współrzędnych
    const oldBounds = { lat: { min: -10, max: 0 }, lng: { min: 0, max: 10 } };
    const newBounds = { lat: { min: 50.0414, max: 50.0814 }, lng: { min: 21.2261, max: 21.2661 } };

    // Obliczenie zakresów dla obu systemów
    const oldLatSpan = oldBounds.lat.max - oldBounds.lat.min;
    const oldLngSpan = oldBounds.lng.max - oldBounds.lng.min;
    const newLatSpan = newBounds.lat.max - newBounds.lat.min;
    const newLngSpan = newBounds.lng.max - newBounds.lng.min;

    // Funkcja transformująca pojedynczą parę współrzędnych [lng, lat]
    const transformCoords = (coords) => {
        const [oldLng, oldLat] = coords;
        const newLat = newBounds.lat.min + ((oldLat - oldBounds.lat.min) / oldLatSpan) * newLatSpan;
        const newLng = newBounds.lng.min + ((oldLng - oldBounds.lng.min) / oldLngSpan) * newLngSpan;
        return [newLng, newLat];
    };

    // Przetworzenie każdego obiektu w danych
    features.forEach(feature => {
        const geomType = feature.geometry.type;
        const coords = feature.geometry.coordinates;

        if (geomType === 'Point') {
            feature.geometry.coordinates = transformCoords(coords);
        } else if (geomType === 'LineString' || geomType === 'MultiPoint') {
            feature.geometry.coordinates = coords.map(transformCoords);
        } else if (geomType === 'Polygon' || geomType === 'MultiLineString') {
            feature.geometry.coordinates = coords.map(ring => ring.map(transformCoords));
        } else if (geomType === 'MultiPolygon') {
            feature.geometry.coordinates = coords.map(polygon => polygon.map(ring => ring.map(transformCoords)));
        }
    });

    return features;
}

// === 5. FUNKCJE RENDERUJĄCE I MANIPULUJĄCE DOM ===

/**
 * Renderuje obiekty GeoJSON na mapie z odpowiednimi stylami.
 * @param {Array} parcels - Tablica obiektów GeoJSON do wyrenderowania.
 */
function renderMapObjects(parcels) {
    if (!parcels) {
        console.error("❌ Brak danych obiektów do narysowania.");
        return;
    }
    console.log(`🗺️ Rysowanie ${parcels.length} obiektów...`);

    const STYLES = {
        budowlana: { color: "#e67e22", weight: 2 },
        rolna: { color: "#27ae60", weight: 2 },
        las: {
            color: "#16a085",
            weight: 1,
            fillColor: "#1abc9c",
            fillOpacity: 0.5,
        },
        droga: { color: "#8e44ad", weight: 3 },
        rzeka: { color: "#3498db", weight: 4 },
        pastwisko: {
            color: "#f1c40f",
            weight: 1,
            fillColor: "#f1c40f",
            fillOpacity: 0.4,
        },
        obiekt_specjalny: { color: "#2c3e50", weight: 2 },
        default: { color: "#3388ff", weight: 2 },
    };

    const ICONS = {
        budynek: L.icon({
            iconUrl: "https://cdn-icons-png.flaticon.com/512/25/25694.png",
            iconSize: [32, 32],
        }),
        kapliczka: L.icon({
            iconUrl: "https://cdn-icons-png.flaticon.com/512/2133/2133353.png",
            iconSize: [32, 32],
        }),
        obiekt_specjalny: L.icon({
            iconUrl: "https://cdn-icons-png.flaticon.com/512/785/785432.png",
            iconSize: [32, 32],
        }),
    };

    if (geojsonLayer) {
        map.removeLayer(geojsonLayer);
    }

    geojsonLayer = L.geoJSON(parcels, {
        style: (feature) => STYLES[feature.properties.kategoria] || STYLES.default,
        
        pointToLayer: (feature, latlng) =>
            L.marker(latlng, { icon: ICONS[feature.properties.kategoria] }),
        
        onEachFeature: (feature, layer) => {
            const props = feature.properties;
            const kategoria = props.kategoria || "default";
            
            if (!layersByCategory[kategoria]) {
                layersByCategory[kategoria] = [];
            }
            layersByCategory[kategoria].push(layer);

            let popupContent = `<b>Typ:</b> ${props.kategoria}<br><b>Nazwa/Numer:</b> ${props.numer_obiektu}`;
            if (props.wlasciciele?.length > 0) {
                popupContent += `<br><b>Właściciele:</b> ${props.wlasciciele.map(w => w.nazwa).join(", ")}`;
            }
            layer.bindPopup(popupContent);

            // --- NOWA SEKCJA: DODAWANIE ETYKIET DO OBIEKTÓW ---
            // Sprawdzamy, czy obiekt ma numer i nie jest punktem (np. domem)
            if (props.numer_obiektu && feature.geometry.type !== 'Point') {
                layer.bindTooltip(props.numer_obiektu.toString(), {
                    permanent: true,      // Etykieta widoczna cały czas, a nie tylko po najechaniu
                    direction: 'center',  // Wyśrodkowanie etykiety wewnątrz obiektu
                    className: 'parcel-label' // Dedykowana klasa CSS do stylizacji
                });
            }
            // --- KONIEC NOWEJ SEKCJI ---

            layer.on({
                mouseover: (e) => handleFeatureMouseover(e, feature),
                mouseout: (e) => handleFeatureMouseout(e),
                click: (e) => handleObjectClick(e.target.feature.properties.wlasciciele, e.latlng)
            });
        },
    }).addTo(map);

    console.log("✅ Zakończono rysowanie obiektów");
}

/**
 * Konfiguruje panel właścicieli z funkcjami wyszukiwania i sortowania.
 */
function setupOwnerPanel() {
    const ownerContainer = document.getElementById("ownersList");
    const searchInput = document.getElementById("ownerSearch");
    const compareBtn = document.getElementById("compareModeBtn");
    let currentSort = "byOrder";

    const render = (owners) => {
        document.getElementById('visible-count').textContent = owners.length;
        ownerContainer.innerHTML = "";
        
        owners.forEach(owner => {
            const card = createOwnerCard(owner);
            ownerContainer.appendChild(card);
        });
    };

    const createOwnerCard = (owner) => {
        const card = document.createElement("div");
        card.className = "owner-card";
        card.dataset.ownerKey = owner.unikalny_klucz;

        card.innerHTML = `
            <div class="owner-info">
                <div class="owner-details">
                    <div class="owner-name">${owner.nazwa_wlasciciela}</div>
                    <div class="owner-meta">
                        <span><i class="fas fa-hashtag"></i> ${owner.numer_protokolu || "N/A"}</span>
                        <span><i class="fas fa-map"></i> ${(owner.dzialki_rzeczywiste || []).length} działek</span>
                    </div>
                </div>
                <div class="owner-actions">
                    <button class="action-btn" data-type="rzeczywiste" title="Pokaż działki rzeczywiste">
                        <i class="fas fa-map-marked-alt"></i>
                    </button>
                    <button class="action-btn" data-type="protokol" title="Pokaż działki wg protokołu" style="display: none;">
                        <i class="fas fa-file-alt"></i>
                    </button>
                    <button class="action-btn switch-btn" title="Zmień widok działek">
                        <i class="fas fa-exchange-alt"></i>
                    </button>
                </div>
            </div>
        `;

        setupOwnerCardEvents(card, owner);
        return card;
    };

    const setupOwnerCardEvents = (card, owner) => {
        card.querySelector(".owner-details").onclick = () => {
            handleOwnerClick(owner.unikalny_klucz);
        };

        const btnRzeczywiste = card.querySelector('.action-btn[data-type="rzeczywiste"]');
        const btnProtokol = card.querySelector('.action-btn[data-type="protokol"]');
        const btnSwitch = card.querySelector(".switch-btn");

        const maDzialkiRzeczywiste = owner.dzialki_rzeczywiste?.length > 0;
        const maDzialkiProtokol = owner.dzialki_protokol?.length > 0;

        if (maDzialkiRzeczywiste) {
            btnRzeczywiste.onclick = (e) => {
                e.stopPropagation();
                const ids = owner.dzialki_rzeczywiste.map(p => p.id);
                highlightFeaturesByIds(ids, 'fuchsia');
            };
        } else {
            btnRzeczywiste.style.display = "none";
        }

        if (maDzialkiProtokol) {
            btnProtokol.onclick = (e) => {
                e.stopPropagation();
                const ids = owner.dzialki_protokol.map(p => p.id);
                highlightFeaturesByIds(ids, '#ffc107');
            };
        } else {
            btnProtokol.style.display = "none";
        }

        if (maDzialkiRzeczywiste && maDzialkiProtokol) {
            btnSwitch.style.display = "inline-flex";
            btnSwitch.onclick = (e) => {
                e.stopPropagation();
                const isRzeczywisteVisible = btnRzeczywiste.style.display !== "none";
                btnRzeczywiste.style.display = isRzeczywisteVisible ? "none" : "inline-flex";
                btnProtokol.style.display = isRzeczywisteVisible ? "inline-flex" : "none";
            };
        } else {
            btnSwitch.style.display = "none";
        }

        card.onmouseover = () => highlightOwnerParcels(owner, true);
        card.onmouseout = () => highlightOwnerParcels(owner, false);
    };

    const highlightOwnerParcels = (owner, highlight) => {
        if (!geojsonLayer) return;
        
        geojsonLayer.eachLayer(layer => {
            const ownersOnParcel = layer.feature.properties.wlasciciele;
            const isOwnerMatch = ownersOnParcel?.some(o => o.id === owner.id);
            
            if (isOwnerMatch && layer.setStyle) {
                if (highlight) {
                    layer.setStyle({ weight: 5, color: "lime" });
                    layer.bringToFront();
                } else {
                    geojsonLayer.resetStyle(layer);
                }
            }
        });
    };

    const sortAndFilter = () => {
        let data = [...allOwnersData];
        
        if (currentSort === "byName") {
            data.sort((a, b) => a.nazwa_wlasciciela.localeCompare(b.nazwa_wlasciciela, "pl"));
        } else if (currentSort === "byParcels") {
            data.sort((a, b) => (b.dzialki_rzeczywiste?.length || 0) - (a.dzialki_rzeczywiste?.length || 0));
        } else {
            data.sort((a, b) => (a.numer_protokolu || 9999) - (b.numer_protokolu || 9999));
        }

        const term = searchInput.value.toLowerCase();
        const filtered = data.filter(o => {
            const ownerName = o.nazwa_wlasciciela.toLowerCase();
            const protocolNumber = o.numer_protokolu ? String(o.numer_protokolu) : "";
            return ownerName.includes(term) || protocolNumber.includes(term);
        });

        render(filtered);
    };

    const handleOwnerClick = (ownerKey) => {
        if (!isInCompareMode) {
            window.location.href = `../wlasciciele/protokol.html?ownerId=${ownerKey}`;
        } else {
            handleCompareMode(ownerKey);
        }
    };

    const handleCompareMode = (ownerKey) => {
        const card = ownerContainer.querySelector(`[data-owner-key="${ownerKey}"]`);
        
        if (selectedForCompare.includes(ownerKey)) {
            selectedForCompare = selectedForCompare.filter(k => k !== ownerKey);
            card.classList.remove("selected-for-compare");
        } else if (selectedForCompare.length < 2) {
            selectedForCompare.push(ownerKey);
            card.classList.add("selected-for-compare");
        }
        
        if (selectedForCompare.length === 2) {
            window.location.href = `../wlasciciele/compare.html?owners=${selectedForCompare.join(",")}`;
        }
    };

    setupOwnerPanelEventListeners();
    sortAndFilter();
    
    const totalOwnersElement = document.getElementById('total-owners');
    if (totalOwnersElement) {
        totalOwnersElement.textContent = allOwnersData.length;
    }

    function setupOwnerPanelEventListeners() {
        if (compareBtn) {
            compareBtn.addEventListener("click", () => {
                isInCompareMode = !isInCompareMode;
                compareBtn.classList.toggle("active", isInCompareMode);
                
                const compareInfo = document.querySelector('.compare-info');
                if (compareInfo) {
                    compareInfo.style.display = isInCompareMode ? 'block' : 'none';
                }
                
                if (!isInCompareMode) {
                    selectedForCompare = [];
                    ownerContainer.querySelectorAll(".selected-for-compare")
                        .forEach(el => el.classList.remove("selected-for-compare"));
                }
            });
        }

        const filterButtons = document.querySelectorAll('.filter-btn');
        filterButtons.forEach(btn => {
            btn.addEventListener("click", () => {
                filterButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                const sortType = btn.dataset.sort;
                currentSort = sortType === 'name' ? "byName" 
                           : sortType === 'parcels' ? "byParcels" 
                           : "byOrder";
                
                sortAndFilter();
            });
        });
        
        if (searchInput) {
            searchInput.addEventListener("input", sortAndFilter);
            
            const clearBtn = searchInput.parentElement.querySelector('.clear-search');
            if (clearBtn) {
                searchInput.addEventListener('input', () => {
                    clearBtn.style.display = searchInput.value ? 'block' : 'none';
                });
                
                clearBtn.addEventListener('click', () => {
                    searchInput.value = '';
                    clearBtn.style.display = 'none';
                    sortAndFilter();
                });
            }
        }
    }
}

/**
 * Konfiguruje panel działek z wyszukiwaniem i filtrowaniem.
 */
function setupParcelPanel() {
    const searchInput = document.getElementById("parcelSearch");
    const dzialkiContainer = document.getElementById("dzialki_panel");
    const obiektyContainer = document.getElementById("obiekty_panel");
    const tabs = document.querySelectorAll(".tab-btn");
    const categoryFilters = document.getElementById("parcel-category-filters");

    const render = () => {
        dzialkiContainer.innerHTML = "";
        obiektyContainer.innerHTML = "";
        
        const searchTerm = searchInput.value.toLowerCase();
        
        if (searchTerm === "" && geojsonLayer) {
            geojsonLayer.eachLayer(layer => geojsonLayer.resetStyle(layer));
        }

        const sortedParcels = [...allParcelsData].sort((a, b) =>
            (a.properties.numer_obiektu || "").localeCompare(
                (b.properties.numer_obiektu || ""),
                "pl",
                { numeric: true }
            )
        );

        const filteredList = sortedParcels.filter(p =>
            (p.properties.numer_obiektu || "").toLowerCase().includes(searchTerm)
        );

        const activeCategories = Array.from(
            document.querySelectorAll('#parcel-category-filters input:checked')
        ).map(cb => cb.dataset.category);

        filteredList.forEach(p => {
            const kategoria = p.properties.kategoria; 
            // Definiujemy, które kategorie trafiają do poszczególnych zakładek
            const dzialkiCategories = ["budowlana", "rolna", "las", "pastwisko"];
            const infrastrukturaCategories = ["droga", "rzeka"];
            
            // Obiekty specjalne (dom, kapliczka) są obsługiwane przez renderSpecialObjects(), więc je pomijamy
            if (!dzialkiCategories.includes(kategoria) && !infrastrukturaCategories.includes(kategoria)) {
                return; // Pomiń obiekty specjalne w tym miejscu
            }
            
            // Logika filtrowania dla zakładki "Działki"
            if (dzialkiCategories.includes(kategoria) && !activeCategories.includes(kategoria)) {
              return; // Pomiń, jeśli kategoria działki jest odznaczona w filtrach
            }

            const item = createParcelItem(p);
            
            // Kategoryzacja do odpowiednich kontenerów
            if (dzialkiCategories.includes(kategoria)) {
              dzialkiContainer.appendChild(item);
            } else { // W domyśle, jeśli to kategoria infrastruktury
              obiektyContainer.appendChild(item);
            }
        });

        if (searchTerm.length > 0) {
            const exactMatches = sortedParcels.filter(
                p => p.properties.numer_obiektu.toLowerCase() === searchTerm
            );
            exactMatches.forEach(p => findAndHighlightLayer(p.id, true, "orange"));
        }
        
        const totalParcelsElement = document.getElementById('total-parcels');
        if (totalParcelsElement) {
            totalParcelsElement.textContent = allParcelsData.length;
        }
    };

    const createParcelItem = (parcel) => {
        const item = document.createElement("div");
        item.className = "parcel-item";
        item.innerHTML = `
            <span class="parcel-number">${parcel.properties.numer_obiektu}</span>
            <span class="parcel-category filter-badge ${parcel.properties.kategoria}">
                ${parcel.properties.kategoria}
            </span>
        `;
        item.dataset.featureId = parcel.id;
        return item;
    };

    if (searchInput) {
        searchInput.addEventListener("input", render);
    }
    
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
            
            tab.classList.add("active");
            const tabId = tab.dataset.tab + '-tab';
            const tabContent = document.getElementById(tabId);
            if (tabContent) {
                tabContent.classList.add("active");
            }
            
            if (categoryFilters) {
                categoryFilters.style.display = tab.dataset.tab === 'parcels' ? 'flex' : 'none';
            }
        });
    });
    
    if (categoryFilters) {
        categoryFilters.querySelectorAll('input').forEach(checkbox => {
            checkbox.addEventListener('change', render);
        });
    }

    setupParcelInteractions(dzialkiContainer);
    setupParcelInteractions(obiektyContainer);
    renderSpecialObjects();
    render();
}

/**
 * Renderuje sekcję obiektów specjalnych.
 */
function renderSpecialObjects() {
    const specialTab = document.getElementById('special-tab');
    const specialContainer = specialTab?.querySelector('.special-objects-list');
    
    if (!specialContainer) return;
    
    specialContainer.innerHTML = '';
    
    const specialCategories = {
        'kapliczka': { icon: '⛪', label: 'Kapliczki', items: [] },
        'budynek': { icon: '🏠', label: 'Domy', items: [] },
        'obiekt_specjalny': { icon: '⭐', label: 'Obiekty specjalne', items: [] }
    };
    
    allParcelsData.forEach(feature => {
        const kategoria = feature.properties.kategoria;
        if (specialCategories[kategoria]) {
            specialCategories[kategoria].items.push(feature);
        }
    });
    
    Object.entries(specialCategories).forEach(([key, category]) => {
        if (category.items.length === 0) return;
        
        const section = createSpecialCategorySection(category);
        specialContainer.appendChild(section);
    });
}

/**
 * Konfiguruje legendę mapy z możliwością włączania/wyłączania kategorii.
 */
function setupLegend() {
    const legendEl = document.getElementById("legend");
    if (!legendEl) return;

    const legendContainer = legendEl.querySelector("ul");
    const legendHeader = legendEl.querySelector(".legend-header");
    const legendContent = legendEl.querySelector(".legend-content");
    const legendToggle = legendEl.querySelector(".legend-toggle");
    
    if (!legendContainer || !legendHeader || !legendContent || !legendToggle) return;

    setupLegendToggle(legendHeader, legendContent, legendToggle);

    const STYLES = {
        budowlana: { color: "#e67e22" },
        rolna: { color: "#27ae60" },
        las: { fillColor: "#1abc9c" },
        droga: { color: "#8e44ad" },
        rzeka: { color: "#3498db" },
        budynek: { color: "#333" },
        kapliczka: { color: "#c0392b" },
        pastwisko: { fillColor: "#f1c40f" },
        obiekt_specjalny: { color: "#2c3e50" },
    };

    const legendItems = {
        budowlana: "Działka Budowlana",
        rolna: "Działka Rolna",
        las: "Las",
        pastwisko: "Pastwisko",
        droga: "Droga",
        rzeka: "Rzeka",
        budynek: "Budynek",
        kapliczka: "Kapliczka",
        obiekt_specjalny: "Obiekt Specjalny",
    };

    legendContainer.innerHTML = "";
    Object.entries(legendItems).forEach(([kategoria, label]) => {
        const legendItem = createLegendItem(kategoria, label, STYLES[kategoria]);
        legendContainer.appendChild(legendItem);
    });
}

// === 6. OBSŁUGA ZDARZEŃ (EVENT LISTENERS) ===

/**
 * Konfiguruje przełączanie paneli bocznych (zwijanie/rozwijanie).
 * Używa klas CSS do zarządzania widocznością uchwytów.
 */
function setupPanelToggles() {
    const toggleButtons = document.querySelectorAll('.panel-toggle');
    const expandHandles = document.querySelectorAll('.panel-expand-handle');
    const mapWrapper = document.getElementById('map-wrapper');

    const updateMapState = () => {
        const leftPanel = document.getElementById('owners-panel');
        const rightPanel = document.getElementById('parcels-panel');

        if (leftPanel.classList.contains('collapsed') && rightPanel.classList.contains('collapsed')) {
            mapWrapper.classList.add('full-width');
            mapWrapper.classList.remove('expanded-left', 'expanded-right');
        } else if (leftPanel.classList.contains('collapsed')) {
            mapWrapper.classList.add('expanded-left');
            mapWrapper.classList.remove('full-width', 'expanded-right');
        } else if (rightPanel.classList.contains('collapsed')) {
            mapWrapper.classList.add('expanded-right');
            mapWrapper.classList.remove('full-width', 'expanded-left');
        } else {
            mapWrapper.classList.remove('full-width', 'expanded-left', 'expanded-right');
        }

        setTimeout(() => map.invalidateSize(), 350);
    };

    toggleButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const panelType = btn.dataset.panel;
            const panel = document.getElementById(panelType === 'owners' ? 'owners-panel' : 'parcels-panel');
            const handle = document.querySelector(`.panel-expand-handle[data-panel="${panelType}"]`);

            panel.classList.add('collapsed');
            if (handle) {
                handle.classList.add('handle-visible'); // Używamy klasy zamiast stylu
            }

            const icon = btn.querySelector('i');
            icon.className = panelType === 'owners' ? 'fas fa-chevron-right' : 'fas fa-chevron-left';

            updateMapState();
        });
    });

    expandHandles.forEach(handle => {
        handle.addEventListener('click', () => {
            const panelType = handle.dataset.panel;
            const panel = document.getElementById(panelType === 'owners' ? 'owners-panel' : 'parcels-panel');

            panel.classList.remove('collapsed');
            handle.classList.remove('handle-visible'); // Używamy klasy zamiast stylu

            const toggleBtn = panel.querySelector('.panel-toggle');
            if (toggleBtn) {
                const icon = toggleBtn.querySelector('i');
                icon.className = panelType === 'owners' ? 'fas fa-chevron-left' : 'fas fa-chevron-right';
            }

            updateMapState();
        });
    });
}

/**
 * Konfiguruje akcje toolbara i ustawienia aplikacji.
 */
function setupToolbarActions() {
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    const helpBtn = document.getElementById('help-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const helpModal = document.getElementById('help-modal');
    const settingsModal = document.getElementById('settings-modal');
    const themeToggle = document.getElementById('theme-toggle');
    const resetViewBtn = document.getElementById('reset-view-btn');

    setupFullscreen(fullscreenBtn);
    setupModals(helpBtn, settingsBtn, helpModal, settingsModal);
    setupTheme(themeToggle);
    
    if (resetViewBtn) {
        resetViewBtn.addEventListener('click', resetView);
    }

    setupKeyboardShortcuts(helpModal, settingsModal);
}

/**
 * Konfiguruje uniwersalną wyszukiwarkę.
 */
function setupUniversalSearch() {
    const searchInput = document.getElementById('universal-search');
    const resultsContainer = document.getElementById('universal-search-results');

    const renderResults = (results) => {
        resultsContainer.innerHTML = '';
        
        if (results.length === 0) {
            resultsContainer.style.display = 'none';
            return;
        }

        results.forEach(item => {
            const itemEl = createSearchResultItem(item);
            resultsContainer.appendChild(itemEl);
        });

        resultsContainer.style.display = 'block';
    };

    const createSearchResultItem = (item) => {
        const itemEl = document.createElement('div');
        itemEl.className = 'search-result-item';
        itemEl.dataset.id = item.id;
        itemEl.dataset.type = item.type;

        // ZMIANA: Zaczynamy od pustego HTML dla ikony
        let iconHtml = ''; 
        let text, meta;

        if (item.type === 'owner') {
            text = item.name;
            meta = `Właściciel (Lp. ${item.lp})`;
            // Dla właściciela nie dodajemy ikony, więc iconHtml pozostaje puste
        } else {
            // Ikonę dodajemy tylko dla działek
            iconHtml = '<i class="result-icon fas fa-map-marker-alt"></i>';
            text = `Działka nr ${item.number}`;
            meta = item.category;
        }

        // ZMIANA: Wstawiamy zmienną iconHtml, która będzie pusta dla właścicieli
        itemEl.innerHTML = `
            ${iconHtml}
            <span class="result-text">${text}</span>
            <span class="result-meta">${meta}</span>
        `;
        
        return itemEl;
    };

    const performSearch = (term) => {
        const ownerResults = allOwnersData
            .filter(owner => 
                owner.nazwa_wlasciciela.toLowerCase().includes(term) ||
                String(owner.numer_protokolu).includes(term)
            )
            .map(owner => ({
                id: owner.unikalny_klucz,
                name: owner.nazwa_wlasciciela,
                lp: owner.numer_protokolu,
                type: 'owner'
            }));

        const parcelResults = allParcelsData
            .filter(p => (p.properties.numer_obiektu || "").toLowerCase().includes(term))
            .map(p => ({
                id: p.id,
                number: p.properties.numer_obiektu,
                category: p.properties.kategoria,
                type: 'parcel'
            }));
        
        return [...ownerResults, ...parcelResults].slice(0, 10);
    };

    searchInput.addEventListener('input', () => {
        const term = searchInput.value.toLowerCase().trim();

        if (term.length < 2) {
            resultsContainer.style.display = 'none';
            return;
        }

        const results = performSearch(term);
        renderResults(results);
    });

    resultsContainer.addEventListener('click', e => {
        const item = e.target.closest('.search-result-item');
        if (!item) return;

        const { id, type } = item.dataset;

        if (type === 'owner') {
            handleOwnerSearchResult(id);
        } else {
            handleParcelSearchResult(parseInt(id));
        }
        
        searchInput.value = '';
        resultsContainer.style.display = 'none';
    });

    document.addEventListener('click', e => {
        if (!resultsContainer.contains(e.target) && e.target !== searchInput) {
            resultsContainer.style.display = 'none';
        }
    });
}

/**
 * Obsługuje najechanie myszą na obiekt na mapie.
 * @param {Event} e - Zdarzenie mouseover.
 * @param {Object} feature - Obiekt GeoJSON.
 */
function handleFeatureMouseover(e, feature) {
    if (e.target.setStyle) {
        e.target.setStyle({ weight: 5, color: "red" });
    }

    const parcelButton = document.querySelector(`.parcelButton[data-feature-id="${feature.id}"]`);
    if (parcelButton) {
        parcelButton.classList.add("highlighted-by-map");
        checkElementVisibility(parcelButton);
    }

    const props = feature.properties;
    const realOwners = (props.wlasciciele || []).filter(owner => {
        const ownerData = allOwnersData.find(o => o.id === owner.id);
        return ownerData && (ownerData.dzialki_rzeczywiste || []).some(
            dzialka => dzialka.id === feature.id
        );
    });

    realOwners.forEach(owner => {
        const ownerTile = document.querySelector(`.ownerIcon[data-owner-key="${owner.unikalny_klucz}"]`);
        if (ownerTile) {
            ownerTile.classList.add("highlighted-by-map");
        }
    });
}

/**
 * Obsługuje zjechanie myszą z obiektu na mapie.
 * @param {Event} e - Zdarzenie mouseout.
 */
function handleFeatureMouseout(e) {
    geojsonLayer.resetStyle(e.target);

    const parcelButton = document.querySelector('.parcelButton.highlighted-by-map');
    if (parcelButton) {
        parcelButton.classList.remove("highlighted-by-map");
        const container = parcelButton.closest('.tab-content-right');
        if (container) {
            container.classList.remove('highlight-indicator-top', 'highlight-indicator-bottom');
        }
    }

    document.querySelectorAll(".ownerIcon.highlighted-by-map").forEach(tile => {
        tile.classList.remove("highlighted-by-map");
    });
}

/**
 * Konfiguruje interakcje dla kontenera działek.
 * @param {HTMLElement} container - Kontener z listą działek.
 */
function setupParcelInteractions(container) {
    if (!container) return;
    
    container.addEventListener("mouseover", (e) => {
        const item = e.target.closest(".parcel-item");
        if (item) {
            findAndHighlightLayer(parseInt(item.dataset.featureId), true);
        }
    });
    
    container.addEventListener("mouseout", (e) => {
        const item = e.target.closest(".parcel-item");
        if (item) {
            findAndHighlightLayer(parseInt(item.dataset.featureId), false);
        }
    });
    
    container.addEventListener("click", (e) => {
        const item = e.target.closest(".parcel-item");
        if (item) {
            const featureId = parseInt(item.dataset.featureId);
            const layer = findLayerById(featureId);
            if (!layer) return;

            if (layer.getBounds) {
                map.fitBounds(layer.getBounds());
            } else if (layer.getLatLng) {
                map.panTo(layer.getLatLng());
            }

            const wlasciciele = layer.feature.properties.wlasciciele;
            handleObjectClick(wlasciciele, layer);
        }
    });
}

// Przycisk czyszczenia podświetlenia
const clearHighlightBtn = document.getElementById("clearHighlightBtn");
if (clearHighlightBtn) {
    clearHighlightBtn.addEventListener("click", clearAllHighlights);
}

// === 7. FUNKCJE PODŚWIETLANIA I WYRÓŻNIANIA ===

/**
 * Podświetla obiekty na mapie według ID.
 * @param {number[]} featureIds - Tablica ID obiektów.
 * @param {string} color - Kolor podświetlenia.
 */
function highlightFeaturesByIds(featureIds, color) {
    if (highlightedLayer) {
        map.removeLayer(highlightedLayer);
    }
    
    highlightedLayer = new L.FeatureGroup();

    const highlightStyle = {
        color: color,
        weight: 5,
        fillColor: color,
        fillOpacity: 0.5,
    };

    geojsonLayer.eachLayer(layer => {
        if (featureIds.includes(layer.feature.id)) {
            let clonedLayer;
            
            if (layer instanceof L.Polygon) {
                clonedLayer = L.polygon(layer.getLatLngs(), highlightStyle);
            } else if (layer instanceof L.Polyline) {
                clonedLayer = L.polyline(layer.getLatLngs(), { ...highlightStyle, fill: false });
            } else if (layer instanceof L.Marker) {
                clonedLayer = L.circleMarker(layer.getLatLng(), { radius: 10, ...highlightStyle });
            }
            
            if (clonedLayer) {
                highlightedLayer.addLayer(clonedLayer);
            }
        }
    });

    if (highlightedLayer.getLayers().length > 0) {
        highlightedLayer.addTo(map);
        map.fitBounds(highlightedLayer.getBounds());
        document.getElementById("highlight-controls").classList.remove("hidden");
    }

    document.getElementById('selected-count').textContent = highlightedLayer.getLayers().length;
}

/**
 * Podświetla działki należące do właścicieli z unikalnym kolorowaniem.
 * @param {string[]} uniqueOwnerKeys - Klucze właścicieli.
 * @param {string} ownershipType - Typ własności ('wszystkie', 'rzeczywista', 'protokol').
 */
function highlightAndColorOwners(uniqueOwnerKeys, ownershipType = 'wszystkie') {
    if (ownerHighlightLayer) {
        map.removeLayer(ownerHighlightLayer);
    }
    
    const ownerHighlightLegend = document.getElementById("owner-highlight-legend");
    ownerHighlightLegend.classList.add("hidden");

    if (uniqueOwnerKeys.length === 0 || !geojsonLayer) return;

    const ownerColorMap = assignColorsToOwners(uniqueOwnerKeys, ownershipType);
    ownerHighlightLayer = new L.FeatureGroup();

    geojsonLayer.eachLayer(layer => {
        processLayerForOwnerHighlight(layer, ownerColorMap, ownershipType);
    });
    
    if (ownerHighlightLayer.getLayers().length > 0) {
        ownerHighlightLayer.addTo(map);
        map.fitBounds(ownerHighlightLayer.getBounds());
        createOwnerHighlightLegend(uniqueOwnerKeys, ownerColorMap, ownerHighlightLegend);
        document.getElementById("highlight-controls").classList.remove("hidden");
    }
}

/**
 * Czyści wszystkie podświetlenia na mapie.
 */
function clearAllHighlights() {
    if (highlightedLayer) {
        map.removeLayer(highlightedLayer);
        highlightedLayer = null;
    }
    
    if (ownerHighlightLayer) {
        map.removeLayer(ownerHighlightLayer);
        ownerHighlightLayer = null;
    }

    document.getElementById("highlight-controls")?.classList.add("hidden");
    document.getElementById("owner-highlight-legend")?.classList.add("hidden");

    if (geojsonLayer) {
        geojsonLayer.eachLayer(layer => geojsonLayer.resetStyle(layer));
    }

    const url = new URL(window.location);
    url.searchParams.delete("parcels");
    url.searchParams.delete("highlightTopOwners");
    url.searchParams.delete("highlightByIds");
    history.pushState({}, "", url);

    document.getElementById('selected-count').textContent = 0;
}

// === 8. FUNKCJE OBSŁUGI PARAMETRÓW URL ===

/**
 * Przetwarza parametry z URL i wykonuje odpowiednie akcje.
 */
function handleUrlParameters() {
    const params = new URLSearchParams(window.location.search);
    const idsToHighlight = new Set();
    let popupInfo = null;

    const idsParam = params.get("highlightByIds");
    if (idsParam) {
        idsParam.split(',')
            .map(id => parseInt(id.trim()))
            .filter(id => !isNaN(id))
            .forEach(id => idsToHighlight.add(id));
    }

    const ownersParam = params.get("highlightTopOwners");
    if (ownersParam) {
        const ownershipType = params.get("ownership") || "wszystkie";
        const uniqueOwnerKeys = [...new Set(
            ownersParam.split(",").map(key => key.trim()).filter(Boolean)
        )];
        
        if (uniqueOwnerKeys.length > 0) {
            highlightAndColorOwners(uniqueOwnerKeys, ownershipType);
        }
    }
    
    const houseNumberParam = params.get("findHouseNumber");
    if (houseNumberParam) {
        const ownerName = params.get("ownerName") || '';
        const houseFeature = findHouseFeature(houseNumberParam);

        if (houseFeature) {
            idsToHighlight.add(houseFeature.id);
            popupInfo = {
                latlng: getCenterOfFeature(houseFeature),
                content: `
                    <div style="text-align: center;">
                        <h3>🏠 Dom nr ${houseNumberParam}</h3>
                        ${ownerName ? `<p><b>Właściciel:</b> ${ownerName}</p>` : ''}
                    </div>`
            };
        } else {
            console.warn(`Nie znaleziono domu o numerze ${houseNumberParam}`);
        }
    }

    if (idsToHighlight.size > 0) {
        highlightFeaturesByIds(Array.from(idsToHighlight), 'fuchsia');
    }
    
    if (popupInfo) {
        map.setView(popupInfo.latlng, 11);
        L.popup()
            .setLatLng(popupInfo.latlng)
            .setContent(popupInfo.content)
            .openOn(map);
    }
}

/**
 * Obsługuje pokazywanie domu właściciela z parametrów URL.
 */
async function handleShowHouseByOwnerKeyFromURL() {
    const params = new URLSearchParams(location.search);
    const ownerKey = params.get('ownerKey');
    const showWhat = params.get('show');
    
    if (!ownerKey || showWhat !== 'house') return;

    let ownerData = null;
    try {
        const resp = await fetch(`/api/wlasciciel/${encodeURIComponent(ownerKey)}`);
        if (!resp.ok) return;
        ownerData = await resp.json();
    } catch (e) {
        console.error('Błąd pobierania właściciela:', e);
        return;
    }
    
    if (!ownerData) return;

    try { 
        await whenGeoJSONIsReady(); 
    } catch (_) {}

    const ownerName = ownerData.nazwa_wlasciciela || '';
    const houseNo = ownerData.dom_numer || ownerData.numer_domu || '';
    const objectId = ownerData.dom_obiekt_id;

    const popupHtml = `
        <div>
            <b>🏠 Dom nr ${houseNo || '—'}</b><br/>
            <span>Właściciel: ${ownerName}</span>
        </div>`;

    if (objectId && focusFeatureById(objectId, popupHtml)) return;
    if (houseNo && focusHouseByNumberAndOwner(houseNo, ownerData.id, ownerName)) return;
    
    if (houseNo) {
        let candidateId = null;
        map.eachLayer(l => {
            if (!l || !l.feature) return;
            const p = l.feature.properties || {};
            if ((p.kategoria === 'budynek' || p.kategoria === 'dom') &&
                String(p.numer_obiektu || '').trim() === String(houseNo).trim()) {
                candidateId = l.feature.id;
            }
        });
        if (candidateId != null) {
            focusFeatureById(candidateId, popupHtml);
        }
    }
}

// === 9. FUNKCJE POMOCNICZE ===

/**
 * Czeka aż warstwy GeoJSON będą gotowe na mapie.
 * @param {number} maxTries - Maksymalna liczba prób.
 * @param {number} delayMs - Opóźnienie między próbami.
 * @returns {Promise}
 */
function whenGeoJSONIsReady(maxTries = 30, delayMs = 150) {
    return new Promise((resolve, reject) => {
        let tries = 0;
        const tick = () => {
            let hasFeatureLayer = false;
            map.eachLayer(l => { 
                if (l && l.feature) hasFeatureLayer = true; 
            });
            
            if (hasFeatureLayer) return resolve();
            if (++tries >= maxTries) return reject(new Error('GeoJSON layers not ready'));
            setTimeout(tick, delayMs);
        };
        tick();
    });
}

/**
 * Znajduje i podświetla obiekt według ID.
 * @param {string|number} objectId - ID obiektu.
 * @param {string} popupHtml - HTML dla popup.
 * @returns {boolean} Czy znaleziono obiekt.
 */
function focusFeatureById(objectId, popupHtml) {
    let found = false;
    
    map.eachLayer(layer => {
        if (!layer || !layer.feature) return;
        
        if (String(layer.feature.id) === String(objectId)) {
            found = true;
            
            try {
                if (layer.getBounds) {
                    map.fitBounds(layer.getBounds(), { maxZoom: 19, padding: [20, 20] });
                } else if (layer.getLatLng) {
                    map.setView(layer.getLatLng(), 19);
                }
                
                if (layer.setStyle && layer.feature.geometry?.type !== 'Point') {
                    layer.setStyle({ 
                        color: 'fuchsia', 
                        weight: 4, 
                        fillColor: 'fuchsia', 
                        fillOpacity: 0.35 
                    });
                    if (layer.bringToFront) layer.bringToFront();
                }
                
                if (popupHtml) {
                    layer.bindPopup(popupHtml, { maxWidth: 320 }).openPopup();
                }
            } catch (e) {
                console.warn('Nie udało się podświetlić obiektu:', e);
            }
        }
    });
    
    return found;
}

/**
 * Znajduje dom według numeru i właściciela.
 * @param {string} houseNumber - Numer domu.
 * @param {string} ownerId - ID właściciela.
 * @param {string} ownerName - Nazwa właściciela.
 * @returns {boolean} Czy znaleziono dom.
 */
function focusHouseByNumberAndOwner(houseNumber, ownerId, ownerName) {
    let match = null;
    
    map.eachLayer(layer => {
        if (!layer || !layer.feature) return;
        
        const f = layer.feature;
        const p = f.properties || {};
        const isHouseCat = (p.kategoria === 'budynek' || p.kategoria === 'dom');
        const sameNumber = String(p.numer_obiektu || '').trim() === String(houseNumber).trim();
        const owners = Array.isArray(p.wlasciciele) ? p.wlasciciele : [];
        const hasOwner = owners.some(o => String(o.id) === String(ownerId));

        if (isHouseCat && sameNumber && (hasOwner || owners.length === 0)) {
            match = f.id;
        }
    });
    
    if (match != null) {
        const html = `
            <div>
                <b>🏠 Dom nr ${houseNumber}</b><br/>
                <span>Właściciel: ${ownerName || 'nieznany'}</span>
            </div>`;
        return focusFeatureById(match, html);
    }
    
    return false;
}

/**
 * Znajduje obiekt domu według numeru.
 * @param {string} houseNumber - Numer domu.
 * @returns {Object|null} Obiekt GeoJSON lub null.
 */
function findHouseFeature(houseNumber) {
    const searchNumber = String(houseNumber).trim().toLowerCase();
    
    for (const feature of allParcelsData) {
        const props = feature.properties;
        const isHouse = props.kategoria === 'budynek' || props.kategoria === 'dom';
        const numberMatch = (props.numer_obiektu || '').toLowerCase() === searchNumber;

        if (isHouse && numberMatch) {
            return feature;
        }
    }
    
    return null;
}

/**
 * Oblicza środek geometrii obiektu.
 * @param {Object} feature - Obiekt GeoJSON.
 * @returns {L.LatLng} Współrzędne środka.
 */
function getCenterOfFeature(feature) {
    const layer = findLayerById(feature.id);
    if (layer) {
        return getCenterOfLayer(layer);
    }
    
    const coords = feature.geometry.coordinates;
    if (feature.geometry.type === 'Point') {
        return L.latLng(coords[1], coords[0]);
    } else {
        return L.latLng(coords[0][0][1], coords[0][0][0]);
    }
}

/**
 * Znajduje warstwę według ID.
 * @param {number} featureId - ID obiektu.
 * @returns {L.Layer|null} Warstwa lub null.
 */
function findLayerById(featureId) {
    let foundLayer = null;
    
    if (geojsonLayer) {
        geojsonLayer.eachLayer(layer => {
            if (layer.feature.id === featureId) {
                foundLayer = layer;
            }
        });
    }
    
    return foundLayer;
}

/**
 * Oblicza środek warstwy.
 * @param {L.Layer} layer - Warstwa Leaflet.
 * @returns {L.LatLng} Współrzędne środka.
 */
function getCenterOfLayer(layer) {
    if (layer.getBounds) return layer.getBounds().getCenter();
    if (layer.getLatLng) return layer.getLatLng();
    return map.getCenter();
}

/**
 * Ustawia widok na warstwę.
 * @param {L.Layer} layer - Warstwa do wyświetlenia.
 */
function focusOnLayer(layer) {
    if (!layer) return;

    if (layer.getBounds) {
        map.fitBounds(layer.getBounds());
    } else if (layer.getLatLng) {
        map.setView(layer.getLatLng(), Math.max(map.getZoom(), 11));
    }
}

/**
 * Podświetla lub usuwa podświetlenie warstwy.
 * @param {number} featureId - ID obiektu.
 * @param {boolean} shouldHighlight - Czy podświetlić.
 * @param {string} highlightColor - Kolor podświetlenia.
 */
function findAndHighlightLayer(featureId, shouldHighlight, highlightColor = "lime") {
    if (document.getElementById("parcelSearch").value.length > 0 && highlightColor === "lime") {
        return;
    }
    
    const layer = findLayerById(featureId);
    if (layer) {
        if (shouldHighlight) {
            if (layer.setStyle) layer.setStyle({ weight: 5, color: highlightColor });
            if (layer.bringToFront) layer.bringToFront();
        } else {
            if (layer.setStyle) geojsonLayer.resetStyle(layer);
        }
    }
}

/**
 * Obsługuje kliknięcie na obiekt - pokazuje właścicieli.
 * @param {Array} wlasciciele - Lista właścicieli.
 * @param {L.LatLng|L.Layer} latlngOrLayer - Współrzędne lub warstwa.
 */
function handleObjectClick(wlasciciele, latlngOrLayer) {
    if (!wlasciciele || wlasciciele.length === 0) {
        if (latlngOrLayer instanceof L.Layer) {
            focusOnLayer(latlngOrLayer);
            if (latlngOrLayer.getPopup()) {
                latlngOrLayer.openPopup();
            }
        }
        return;
    }

    if (wlasciciele.length === 1) {
        map.closePopup();
        window.location.href = `../wlasciciele/protokol.html?ownerId=${wlasciciele[0].unikalny_klucz}`;
    } else {
        const latlng = latlngOrLayer instanceof L.LatLng ? latlngOrLayer : getCenterOfLayer(latlngOrLayer);
        showOwnerSelectionPopup(wlasciciele, latlng);
    }
}

/**
 * Wyświetla popup z listą właścicieli do wyboru.
 * @param {Array} wlasciciele - Lista właścicieli.
 * @param {L.LatLng} latlng - Współrzędne popup.
 */
function showOwnerSelectionPopup(wlasciciele, latlng) {
    let listaHtml = "<h3>Ta działka ma wielu właścicieli.<br>Wybierz protokół:</h3><ul>";

    wlasciciele.forEach(w => {
        const ownerDetails = allOwnersData.find(o => o.id === w.id);
        const lp = ownerDetails ? ownerDetails.numer_protokolu : "N/A";
        listaHtml += `
            <li>
                <a href="#" class="protocol-link-in-popup" 
                   data-url="../wlasciciele/protokol.html?ownerId=${w.unikalny_klucz}">
                   ${w.nazwa} (Lp. ${lp})
                </a>
            </li>`;
    });
    listaHtml += "</ul>";

    const popup = L.popup().setLatLng(latlng).setContent(listaHtml).openOn(map);

    popup.on("contentupdate", () => {
        const links = popup.getElement().querySelectorAll(".protocol-link-in-popup");
        links.forEach(link => {
            link.addEventListener("click", e => {
                e.preventDefault();
                map.closePopup();
                setTimeout(() => {
                    window.location.href = e.target.dataset.url;
                }, 100);
            });
        });
    });

    popup.update();
}

/**
 * Sprawdza widoczność elementu w kontenerze i dodaje wskaźniki.
 * @param {HTMLElement} element - Element do sprawdzenia.
 */
function checkElementVisibility(element) {
    const container = element.closest('.tab-content-right');
    if (!container) return;
    
    container.classList.remove('highlight-indicator-top', 'highlight-indicator-bottom');
    
    const containerRect = container.getBoundingClientRect();
    const elementRect = element.getBoundingClientRect();
    
    const isFullyVisible = 
        elementRect.top >= containerRect.top && 
        elementRect.bottom <= containerRect.bottom;
    
    if (!isFullyVisible) {
        if (elementRect.top < containerRect.top) {
            container.classList.add('highlight-indicator-top');
        } else if (elementRect.bottom > containerRect.bottom) {
            container.classList.add('highlight-indicator-bottom');
        }
    }
}

/**
 * Tworzy sekcję dla kategorii obiektów specjalnych.
 * @param {Object} category - Dane kategorii.
 * @returns {HTMLElement} Element sekcji.
 */
function createSpecialCategorySection(category) {
    const section = document.createElement('div');
    section.className = 'special-category-section';
    section.innerHTML = `
        <h4 class="special-category-header">
            <span>${category.icon}</span>
            <span>${category.label} (${category.items.length})</span>
        </h4>
        <div class="special-items-list"></div>
    `;
    
    const itemsList = section.querySelector('.special-items-list');
    
    category.items.sort((a, b) => {
        const numA = parseInt(a.properties.numer_obiektu) || 0;
        const numB = parseInt(b.properties.numer_obiektu) || 0;
        return numA - numB;
    });
    
    category.items.forEach(item => {
        const itemEl = createSpecialObjectItem(item, category.icon);
        itemsList.appendChild(itemEl);
    });
    
    return section;
}

/**
 * Tworzy element obiektu specjalnego.
 * @param {Object} item - Dane obiektu.
 * @param {string} icon - Ikona kategorii.
 * @returns {HTMLElement} Element obiektu.
 */
function createSpecialObjectItem(item, icon) {
    const itemEl = document.createElement('div');
    itemEl.className = 'special-item';
    itemEl.dataset.featureId = item.id;
    
    const owners = item.properties.wlasciciele || [];
    const ownerNames = owners.map(o => o.nazwa).join(', ') || 'Brak właściciela';
    
    itemEl.innerHTML = `
        <div class="special-item-header">
            <span class="special-item-icon">${icon}</span>
            <span class="special-item-number">${item.properties.numer_obiektu || 'Bez numeru'}</span>
        </div>
        <div class="special-item-owners">${ownerNames}</div>
    `;
    
    itemEl.addEventListener('click', () => {
        const layer = findLayerById(item.id);
        if (layer) {
            focusOnLayer(layer);
            if (layer.openPopup) layer.openPopup();
        }
    });
    
    itemEl.addEventListener('mouseenter', () => {
        findAndHighlightLayer(item.id, true, 'red');
    });
    
    itemEl.addEventListener('mouseleave', () => {
        findAndHighlightLayer(item.id, false);
    });
    
    return itemEl;
}

/**
 * Konfiguruje zwijanie/rozwijanie legendy.
 */
function setupLegendToggle(header, content, toggle) {
    let isCollapsed = false;
    
    header.addEventListener("click", () => {
        isCollapsed = !isCollapsed;
        
        if (isCollapsed) {
            content.style.display = "none";
            toggle.querySelector('i').className = 'fas fa-chevron-up';
            header.style.borderRadius = "12px";
        } else {
            content.style.display = "block";
            toggle.querySelector('i').className = 'fas fa-chevron-down';
            header.style.borderRadius = "12px 12px 0 0";
        }
    });
}

/**
 * Tworzy element legendy.
 * @param {string} kategoria - Kategoria obiektu.
 * @param {string} label - Etykieta tekstowa.
 * @param {Object} style - Styl obiektu.
 * @returns {HTMLElement} Element legendy.
 */
function createLegendItem(kategoria, label, style) {
    const li = document.createElement("li");
    li.dataset.kategoria = kategoria;
    li.className = "legend-item";
    
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.className = "legend-checkbox";
    checkbox.id = `legend-${kategoria}`;
    
    const colorBox = document.createElement("span");
    colorBox.className = "legend-color-box";
    colorBox.style.backgroundColor = style?.fillColor || style?.color || "#ccc";
    
    const labelEl = document.createElement("label");
    labelEl.htmlFor = `legend-${kategoria}`;
    labelEl.className = "legend-label";
    labelEl.textContent = label;
    
    li.appendChild(checkbox);
    li.appendChild(colorBox);
    li.appendChild(labelEl);

    checkbox.addEventListener("change", () => {
        const layers = layersByCategory[kategoria];
        
        if (layers) {
            if (checkbox.checked) {
                layers.forEach(layer => map.addLayer(layer));
                li.classList.remove("inactive");
            } else {
                layers.forEach(layer => map.removeLayer(layer));
                li.classList.add("inactive");
            }
        }
    });
    
    return li;
}

/**
 * Przypisuje kolory do właścicieli.
 * @param {string[]} ownerKeys - Klucze właścicieli.
 * @param {string} ownershipType - Typ własności.
 * @returns {Object} Mapa kolorów.
 */
function assignColorsToOwners(ownerKeys, ownershipType) {
    const colorMap = {};
    let colorIndex = 0;
    
    ownerKeys.forEach(key => {
        if (ownershipType === "wszystkie") {
            colorMap[key] = {
                rzeczywista: HIGHLIGHT_COLORS[colorIndex % HIGHLIGHT_COLORS.length],
                protokol: HIGHLIGHT_COLORS[(colorIndex + 1) % HIGHLIGHT_COLORS.length],
            };
            colorIndex += 2;
        } else {
            colorMap[key] = HIGHLIGHT_COLORS[colorIndex % HIGHLIGHT_COLORS.length];
            colorIndex++;
        }
    });
    
    return colorMap;
}

/**
 * Przetwarza warstwę dla podświetlenia właściciela.
 */
function processLayerForOwnerHighlight(layer, ownerColorMap, ownershipType) {
    const parcelOwners = layer.feature.properties.wlasciciele;
    if (!parcelOwners) return;

    const matchedOwner = parcelOwners.find(o => ownerColorMap[o.unikalny_klucz]);
    if (!matchedOwner) return;

    const ownerKey = matchedOwner.unikalny_klucz;
    const isReal = matchedOwner.typ_posiadania === "własność rzeczywista";

    if ((ownershipType === "rzeczywista" && !isReal) || 
        (ownershipType === "protokol" && isReal)) {
        return;
    }
    
    const color = (typeof ownerColorMap[ownerKey] === "object")
        ? (isReal ? ownerColorMap[ownerKey].rzeczywista : ownerColorMap[ownerKey].protokol)
        : ownerColorMap[ownerKey];
        
    let clonedLayer;
    if (layer instanceof L.Polygon) {
        clonedLayer = L.polygon(layer.getLatLngs(), { 
            color, 
            weight: 3, 
            fillColor: color, 
            fillOpacity: 0.6 
        });
    } else if (layer instanceof L.Polyline) {
        clonedLayer = L.polyline(layer.getLatLngs(), { 
            color, 
            weight: 5 
        });
    } else if (layer instanceof L.Marker) {
        clonedLayer = L.circleMarker(layer.getLatLng(), { 
            radius: 10, 
            color: 'black', 
            weight: 2, 
            fillColor: color, 
            fillOpacity: 1 
        });
    }

    if (clonedLayer) {
        ownerHighlightLayer.addLayer(clonedLayer);
    }
}

/**
 * Tworzy legendę dla podświetlonych właścicieli.
 */
function createOwnerHighlightLegend(ownerKeys, colorMap, legendElement) {
    const legendList = legendElement.querySelector("ul");
    legendList.innerHTML = "";

    ownerKeys.forEach(ownerKey => {
        const owner = allOwnersData.find(o => o.unikalny_klucz === ownerKey);
        if (!owner) return;
        
        const colorData = colorMap[ownerKey];
        if (typeof colorData === "object") {
            legendList.innerHTML += `
                <li>
                    <span class="legend-color-box" style="background-color: ${colorData.rzeczywista};"></span>
                    <span>${owner.nazwa_wlasciciela} (Rzeczywiste)</span>
                </li>
                <li>
                    <span class="legend-color-box" style="background-color: ${colorData.protokol};"></span>
                    <span>${owner.nazwa_wlasciciela} (Wg Protokołu)</span>
                </li>`;
        } else {
            legendList.innerHTML += `
                <li>
                    <span class="legend-color-box" style="background-color: ${colorData};"></span>
                    <span>${owner.nazwa_wlasciciela}</span>
                </li>`;
        }
    });

    legendElement.classList.remove("hidden");
}

/**
 * Konfiguruje funkcjonalność pełnego ekranu.
 */
function setupFullscreen(btn) {
    btn.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
            btn.innerHTML = '<i class="fas fa-compress"></i>';
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
                btn.innerHTML = '<i class="fas fa-expand"></i>';
            }
        }
    });
}

/**
 * Konfiguruje okna modalne.
 */
function setupModals(helpBtn, settingsBtn, helpModal, settingsModal) {
    const openModal = modal => modal.style.display = 'flex';
    const closeModal = modal => modal.style.display = 'none';

    helpBtn.addEventListener('click', () => openModal(helpModal));
    settingsBtn.addEventListener('click', () => openModal(settingsModal));

    [helpModal, settingsModal].forEach(modal => {
        modal.querySelector('.modal-close').addEventListener('click', () => closeModal(modal));
        modal.addEventListener('click', e => {
            if (e.target === modal) closeModal(modal);
        });
    });
}

/**
 * Konfiguruje przełącznik motywu.
 */
function setupTheme(toggle) {
    // Funkcja do zastosowania motywu na stronie
    const applyTheme = (theme) => {
        document.body.classList.toggle('dark-mode', theme === 'dark');
        toggle.checked = (theme === 'dark');
    };

    // Odczytanie zapisanego motywu i jego zastosowanie
    const savedTheme = localStorage.getItem('mapTheme') || 'light';
    applyTheme(savedTheme);

    // Listener do zmiany motywu przez użytkownika
    toggle.addEventListener('change', () => {
        const newTheme = toggle.checked ? 'dark' : 'light';
        localStorage.setItem('mapTheme', newTheme);
        applyTheme(newTheme);
    });
}

/**
 * Resetuje widok aplikacji.
 */
function resetView() {
    document.getElementById('owners-panel').classList.add('collapsed');
    document.getElementById('parcels-panel').classList.add('collapsed');
    
    // Używamy klas do pokazania uchwytów, spójnie z nową logiką
    document.querySelector('.panel-expand-handle.left-handle').classList.add('handle-visible');
    document.querySelector('.panel-expand-handle.right-handle').classList.add('handle-visible');

    clearAllHighlights();
    
    if (geojsonLayer && geojsonLayer.getLayers().length > 0) {
        map.fitBounds(geojsonLayer.getBounds());
    }
    
    const settingsModal = document.getElementById('settings-modal');
    if (settingsModal) {
        settingsModal.style.display = 'none';
    }
}

/**
 * Konfiguruje skróty klawiszowe.
 */
function setupKeyboardShortcuts(helpModal, settingsModal) {
    document.addEventListener('keydown', event => {
        const activeElement = document.activeElement;
        if (activeElement && 
            (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
            if (event.key !== 'Escape') return;
        }

        if (event.ctrlKey && event.key === 'f') {
            event.preventDefault();
            document.getElementById('universal-search').focus();
        }

        if (event.key === '+') {
            event.preventDefault();
            map.zoomIn();
        }
        
        if (event.key === '-') {
            event.preventDefault();
            map.zoomOut();
        }
        
        if (event.key === 'Escape') {
            event.preventDefault();
            
            if (helpModal.style.display === 'flex') {
                helpModal.style.display = 'none';
            } else if (settingsModal.style.display === 'flex') {
                settingsModal.style.display = 'none';
            } else {
                const clearBtn = document.getElementById('clearHighlightBtn');
                if (clearBtn && !clearBtn.parentElement.classList.contains('hidden')) {
                    clearBtn.click();
                }
            }
        }
    });
}

/**
 * Obsługuje kliknięcie na wynik wyszukiwania właściciela.
 * @param {string} ownerKey - Klucz właściciela.
 */
function handleOwnerSearchResult(ownerKey) {
    const ownerCard = document.querySelector(`.owner-card[data-owner-key="${ownerKey}"]`);
    if (ownerCard) {
        ownerCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        ownerCard.style.transition = 'all 0.2s ease';
        ownerCard.style.transform = 'scale(1.05)';
        setTimeout(() => { 
            ownerCard.style.transform = 'scale(1)'; 
        }, 1000);
    }
}

/**
 * Obsługuje kliknięcie na wynik wyszukiwania działki.
 * @param {number} parcelId - ID działki.
 */
function handleParcelSearchResult(parcelId) {
    const layer = findLayerById(parcelId);
    if (layer) {
        focusOnLayer(layer);
        if (layer.openPopup) {
            layer.openPopup();
        }
    }
}