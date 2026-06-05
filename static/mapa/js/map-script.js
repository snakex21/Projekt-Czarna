/* ==========================================================================
   Plik: map-script.js
   Opis: MapLibre GL JS — silnik mapy katastralnej (Faza 2 rdzeń).
         Eksponuje API window.MapAPI oraz alias window.MapV2 dla panels.js.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', initializeAppV2);

const MAP_CONSTANTS = window.MapConstants;
const MAP_UTILS = window.MapUtils;
const MAP_GEOMETRY = window.MapGeometry;
const MAP_OWNERSHIP = window.MapOwnership;
const MAP_LAYERS = window.MapLayers;
const MAP_INITIALIZER = window.MapInitializer;
const MAP_INTERACTIONS = window.MapInteractions;
const MAP_URL_PARAMETERS = window.MapUrlParameters;
const MAP_POPUPS = window.MapPopups;
const MAP_HIGHLIGHTS = window.MapHighlights;

const PARCEL_COLORS = MAP_CONSTANTS.PARCEL_COLORS;
const PARCEL_FILL_OPACITY = MAP_CONSTANTS.PARCEL_FILL_OPACITY;
const HIGHLIGHT_PALETTE = MAP_CONSTANTS.HIGHLIGHT_PALETTE;
const featureBBox = MAP_GEOMETRY.featureBBox;
const featureCenter = MAP_GEOMETRY.featureCenter;
const parseMaybeJson = MAP_UTILS.parseMaybeJson;
const uniqueOwners = MAP_UTILS.uniqueOwners;
const escapeHtml = MAP_UTILS.escapeHtml;
const isRealOwnershipType = MAP_OWNERSHIP.isRealOwnershipType;
const findMatchingOwner = MAP_OWNERSHIP.findMatchingOwner;

let map = null;
let allOwnersData = [];
let allParcelsData = [];
let historicalOpacity = 1.0;
const HISTORICAL_MAP_URL = `/mapa/mapa.jpg?v=${Date.now()}`;
const layerControls = window.MapLayerControls.create({
    getMap: () => map,
    setHistoricalOpacityState: (opacity) => { historicalOpacity = opacity; },
});
const mapInitializer = window.MapInitializer.create({
    getHistoricalOpacity: () => historicalOpacity,
    setHistoricalOpacityState: (opacity) => { historicalOpacity = opacity; },
    historicalMapUrl: HISTORICAL_MAP_URL,
});

// Cache features po id — paneli i URL parametry mogą szybko sięgnąć po geometrię.
const featuresById = new Map();

const highlightMarkers = window.MapHighlightMarkers.create({
    getMap: () => map,
    getFeatureById: (id) => featuresById.get(String(id)),
    featureCenter,
});
const mapHighlights = window.MapHighlights.create({
    getMap: () => map,
    fitToFeatures,
    addLpMarker: highlightMarkers.addLpMarker,
    clearLpMarkers: highlightMarkers.clearLpMarkers,
    hideHighlightTooltip: highlightMarkers.hideHighlightTooltip,
    clearOwnerColored,
    clearFocusMode,
});
const highlightFeatures = mapHighlights.highlightFeatures;
const clearTemporaryHighlight = mapHighlights.clearTemporaryHighlight;
const clearAllHighlights = mapHighlights.clearAllHighlights;
const setOwnerHoverHighlight = mapHighlights.setOwnerHoverHighlight;
const setHoverFeature = mapHighlights.setHoverFeature;
const markSingleFeature = mapHighlights.markSingleFeature;
const mapPopups = window.MapPopups.create({
    getMap: () => map,
    getOwners: () => allOwnersData,
    uniqueOwners,
    parseMaybeJson,
    escapeHtml,
});
const mapInteractions = window.MapInteractions.create({
    getMap: () => map,
    getHoveredParcelId: () => hoveredParcelId,
    setHoveredParcelId: (id) => { hoveredParcelId = id; },
    getFeatureById: (id) => featuresById.get(String(id)),
    parseMaybeJson,
    getHighlightInfo: mapHighlights.getHighlightInfo,
    showHighlightTooltip: highlightMarkers.showHighlightTooltip,
    hideHighlightTooltip: highlightMarkers.hideHighlightTooltip,
    handleObjectClick: mapPopups.handleObjectClick,
});
const urlParameters = window.MapUrlParameters.create({
    getParcels: () => allParcelsData,
    getFeatureById: (id) => featuresById.get(String(id)),
    getMap: () => map,
    highlightFeatures,
    highlightOwners,
    highlightRivers,
    highlightRoads,
    featureCenter,
    escapeHtml,
});

// Faza 3: kolorowanie wielu właścicieli (highlightTopOwners) i focus mode (dimming).
// Dla każdej działki możemy zapisać per-feature-state "ownerColor" (string) — paint expression
// pickuje go zamiast standardowego koloru kategorii.
let ownerColoredIds = new Set();
let focusedIds = null;                 // null = brak focus mode; Set = działki w fokusie (reszta dimmed)

function initializeAppV2() {
    console.log('🚀 MapLibre v2 startuje');
    map = mapInitializer.initializeMap();
    console.log('✅ Mapa MapLibre zainicjalizowana');
    fetchDataAndBuildV2();
}

function fetchDataAndBuildV2() {
    Promise.all([
        fetch('/api/dzialki').then(r => r.json()),
        fetch('/api/wlasciciele').then(r => r.json()),
    ]).then(([dzialki, wlasciciele]) => {
        allParcelsData = dzialki.features || dzialki;
        allOwnersData = wlasciciele.owners || wlasciciele;

        // Index features po id dla szybkiego dostępu z paneli/URL.
        featuresById.clear();
        for (const f of allParcelsData) {
            const id = f.id ?? f.properties?.id;
            if (id != null) {
                f.id = id;
                featuresById.set(String(id), f);
            }
        }

        if (map.isStyleLoaded()) {
            renderMapDataV2();
        } else {
            map.once('load', renderMapDataV2);
        }

        // Inicjalizacja paneli — czekamy aż mapa jest gotowa, ale panele i tak operują na danych.
        if (window.PanelsV2) {
            window.PanelsV2.init({ owners: allOwnersData, parcels: allParcelsData });
        }

        // Overlay ładowania zniknie dopiero gdy mapa jest w pełni wyrenderowana
        // (wszystkie źródła, warstwy, kafelki). Ukrywamy go z renderMapDataV2
        // po zdarzeniu 'idle' MapLibre.
    }).catch(err => {
        console.error('❌ Błąd ładowania danych', err);
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.style.display = 'none';
    });
}

function renderMapDataV2() {
    if (!allParcelsData?.length) {
        console.error('❌ Brak działek');
        return;
    }

    const collections = MAP_LAYERS.splitFeatures(allParcelsData);
    MAP_LAYERS.addCoreSources(map, collections);
    MAP_LAYERS.addCoreLayers(map, { PARCEL_COLORS, PARCEL_FILL_OPACITY });

    mapInteractions.setupHoverInteractions();
    mapInteractions.setupClickInteractions();
    setupKeyboardZoomAnimation();

    // Ikony dla domów / kapliczek / obiektów specjalnych — ładowane z CDN, dodawane
    // jako sprite'y MapLibre. Po załadowaniu wymieniamy `circle` na `symbol` z icon-image.
    mapInitializer.loadPointIcons(map);

    // Stosujemy parametry URL po wyrenderowaniu — Faza 3 rozszerzy to.
    setTimeout(urlParameters.handleUrlParameters, 100);

    console.log(`✅ MapLibre: ${collections.polygons.features.length} poligonów, ${collections.lines.features.length} linii, ${collections.points.features.length} punktów`);

    // Ukryj overlay ładowania dopiero gdy mapa zakończy renderowanie wszystkich warstw.
    let overlayHidden = false;
    const hideOverlay = () => {
        if (overlayHidden) return;
        overlayHidden = true;
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.style.display = 'none';
    };
    map.once('idle', hideOverlay);
    // Fallback: jeśli idle nie przyjdzie w ciągu 8 sekund, i tak pokaż mapę.
    setTimeout(hideOverlay, 8000);
}

let hoveredParcelId = null;

/* ==========================================================================
   API: window.MapAPI + alias window.MapV2
   ========================================================================== */

window.MapAPI = Object.freeze({
    highlightFeatures,
    clearTemporaryHighlight,
    clearAllHighlights,
    setOwnerHoverHighlight,
    setHoverFeature,
    focusFeature,
    fitToAll,
    showOwnerSelectionPopup: (owners, featureId) => {
        const f = featuresById.get(String(featureId));
        const center = featureCenter(f) || map.getCenter();
        mapPopups.showOwnerSelectionPopup(uniqueOwners(owners), center);
    },
    setCategoryVisibility,
    setBaseLayer,
    setMapLayerVisibility,
    setHistoricalOpacity,
    setPointsExclusion,
    addGeojsonSource,
    addGeojsonLayer,
    getMap: () => map,
    invalidateSize: () => map?.resize(),
    zoomIn: () => map?.zoomIn({ duration: 300 }),
    zoomOut: () => map?.zoomOut({ duration: 300 }),
    // Faza 3
    highlightOwners,           // wielu właścicieli z różnymi kolorami
    highlightRivers,           // rzeki po nazwach
    highlightRoads,            // drogi po nazwach
    setFocusMode,              // dim wszystkie poza listą id
    clearFocusMode,
});
window.MapV2 = window.MapAPI;

function focusFeature(featureId, opts = {}) {
    const f = featuresById.get(String(featureId));
    if (!f) return false;

    if (opts.mark !== false) {
        mapHighlights.markSingleFeature(featureId, opts.markColor || 'fuchsia');
    }

    const bbox = featureBBox(f);
    if (bbox) {
        const isPoint = f.geometry.type === 'Point';
        if (isPoint) {
            map.easeTo({
                center: [bbox[0], bbox[1]],
                zoom: Math.max(map.getZoom(), 17),
                duration: 700,
                essential: true,
            });
        } else {
            map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], {
                padding: 60,
                maxZoom: 19,
                duration: 700,
                essential: true,
            });
        }
    }
    if (opts.openPopup) {
        const center = featureCenter(f) || map.getCenter();
        mapPopups.handleObjectClick(f, center);
    }
    return true;
}

function fitToAll() {
    if (!allParcelsData.length) return;
    let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
    for (const f of allParcelsData) {
        const bb = featureBBox(f);
        if (!bb) continue;
        if (bb[0] < minLng) minLng = bb[0];
        if (bb[1] < minLat) minLat = bb[1];
        if (bb[2] > maxLng) maxLng = bb[2];
        if (bb[3] > maxLat) maxLat = bb[3];
    }
    if (Number.isFinite(minLng)) {
        map.fitBounds([[minLng, minLat], [maxLng, maxLat]], {
            padding: 60, duration: 800, essential: true,
        });
    }
}

function fitToFeatures(ids) {
    let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
    for (const id of ids) {
        const f = featuresById.get(String(id));
        if (!f) continue;
        const bb = featureBBox(f);
        if (!bb) continue;
        if (bb[0] < minLng) minLng = bb[0];
        if (bb[1] < minLat) minLat = bb[1];
        if (bb[2] > maxLng) maxLng = bb[2];
        if (bb[3] > maxLat) maxLat = bb[3];
    }
    if (Number.isFinite(minLng)) {
        map.fitBounds([[minLng, minLat], [maxLng, maxLat]], {
            padding: 80, maxZoom: 18, duration: 800, essential: true,
        });
    }
}

function setCategoryVisibility(kategoria, visible) {
    return layerControls.setCategoryVisibility(kategoria, visible);
}

function setBaseLayer(type) {
    return layerControls.setBaseLayer(type);
}

function setMapLayerVisibility(group, visible) {
    // Wrapper kontraktowy: obsługuje 'historical-points' przez HistoricalPoints.layerIds().
    return layerControls.setMapLayerVisibility(group, visible);
}

function addGeojsonSource(sourceId, data) {
    return layerControls.addGeojsonSource(sourceId, data);
}

function addGeojsonLayer(spec) {
    return layerControls.addGeojsonLayer(spec);
}

function setHistoricalOpacity(opacity) {
    return layerControls.setHistoricalOpacity(opacity);
}

function setPointsExclusion(excludeNames) {
    // Wrapper kontraktowy: filtr delegowany nadal porównuje po 'numer_obiektu'.
    return layerControls.setPointsExclusion(excludeNames);
}

function highlightOwners(ownerKeys, ownershipType = 'wszystkie') {
    clearOwnerColored();
    clearAllHighlights({ keepHistorical: true });

    if (!Array.isArray(ownerKeys) || !ownerKeys.length) return;

    const colorMap = {};
    let i = 0;
    for (const k of ownerKeys) {
        if (ownershipType === 'wszystkie') {
            colorMap[k] = {
                rzeczywista: HIGHLIGHT_PALETTE[i % HIGHLIGHT_PALETTE.length],
                protokol: HIGHLIGHT_PALETTE[(i + 1) % HIGHLIGHT_PALETTE.length],
            };
            i += 2;
        } else {
            colorMap[k] = HIGHLIGHT_PALETTE[i % HIGHLIGHT_PALETTE.length];
            i++;
        }
    }

    const selectedIds = [];

    const lpByOwnerKey = new Map();
    for (const o of allOwnersData) {
        if (o.unikalny_klucz && o.numer_protokolu != null) {
            lpByOwnerKey.set(o.unikalny_klucz, o.numer_protokolu);
        }
    }

    for (const f of allParcelsData) {
        const owners = f.properties?.wlasciciele;
        if (!Array.isArray(owners) || !owners.length) continue;

        const matched = findMatchingOwner(owners, colorMap, ownershipType);
        if (!matched) continue;

        const cm = colorMap[matched.unikalny_klucz];
        const isReal = isRealOwnershipType(matched.typ_posiadania);
        const color = (typeof cm === 'object')
            ? (isReal ? cm.rzeczywista : cm.protokol)
            : cm;

        const id = Number(f.id);
        if (!Number.isFinite(id)) continue;
        const ownerLp = lpByOwnerKey.get(matched.unikalny_klucz);
        ownerColoredIds.add(id);
        selectedIds.push(id);
        const stateUpdate = { ownerColored: true, ownerColor: color };
        if (ownerLp != null) stateUpdate.ownerLp = ownerLp;
        try { map.setFeatureState({ source: 'parcels', id }, stateUpdate); } catch {}
        try { map.setFeatureState({ source: 'points', id }, stateUpdate); } catch {}

        if (ownerLp != null) {
            highlightMarkers.addLpMarker(id, ownerLp, color, !isReal);
        }

        const ownerObj = allOwnersData.find(o => o.unikalny_klucz === matched.unikalny_klucz);
        mapHighlights.setHighlightInfo(id, {
            ownerName: ownerObj?.nazwa_wlasciciela || matched.nazwa || matched.unikalny_klucz,
            ownershipType: isReal ? 'Rzeczywiste' : 'Wg Protokołu',
            ownerLp,
        });
    }

    if (selectedIds.length) {
        setFocusMode(selectedIds);
        fitToFeatures(selectedIds);
        createOwnerHighlightLegend(ownerKeys, colorMap);
        document.getElementById('highlight-controls')?.classList.remove('hidden');
    }
}

function clearOwnerColored() {
    for (const id of ownerColoredIds) {
        try { map.setFeatureState({ source: 'parcels', id }, { ownerColored: false, ownerColor: null, ownerLp: null }); } catch {}
        try { map.setFeatureState({ source: 'points', id }, { ownerColored: false, ownerColor: null, ownerLp: null }); } catch {}
    }
    ownerColoredIds.clear();
    highlightMarkers.clearLpMarkers();
    removeOwnerHighlightLegend();
}

function createOwnerHighlightLegend(ownerKeys, colorMap) {
    const legendEl = document.getElementById('legend');
    if (!legendEl) return;
    const list = legendEl.querySelector('.legend-list');
    if (!list) return;

    list.querySelectorAll('.legend-item-owner').forEach(el => el.remove());
    list.querySelector('.legend-separator')?.remove();

    if (!ownerKeys.length) return;

    const sep = document.createElement('hr');
    sep.className = 'legend-separator';
    sep.style.cssText = 'margin:10px 0;border:none;border-top:1px solid var(--border-color);';
    list.appendChild(sep);

    for (const key of ownerKeys) {
        const owner = allOwnersData.find(o => o.unikalny_klucz === key);
        if (!owner) continue;
        const cm = colorMap[key];
        if (typeof cm === 'object') {
            list.appendChild(buildOwnerLegendItem(`${owner.nazwa_wlasciciela} (Rzeczywiste)`, cm.rzeczywista));
            list.appendChild(buildOwnerLegendItem(`${owner.nazwa_wlasciciela} (Wg Protokołu)`, cm.protokol));
        } else {
            list.appendChild(buildOwnerLegendItem(owner.nazwa_wlasciciela, cm));
        }
    }
}

function removeOwnerHighlightLegend() {
    const list = document.getElementById('legend')?.querySelector('.legend-list');
    if (!list) return;
    list.querySelectorAll('.legend-item-owner').forEach(el => el.remove());
    list.querySelector('.legend-separator')?.remove();
}

function buildOwnerLegendItem(label, color) {
    const li = document.createElement('li');
    li.className = 'legend-item legend-item-owner';
    li.style.opacity = '1';
    const box = document.createElement('span');
    box.className = 'legend-color-box';
    box.style.backgroundColor = color;
    const sp = document.createElement('span');
    sp.className = 'legend-label';
    sp.textContent = label;
    sp.style.fontWeight = '600';
    sp.style.color = 'var(--accent-color)';
    li.appendChild(box);
    li.appendChild(sp);
    return li;
}

function highlightRivers(names) {
    if (!Array.isArray(names) || !names.length) return;
    const ids = allParcelsData
        .filter(f => f.properties?.kategoria === 'rzeka' &&
            names.includes(String(f.properties.numer_obiektu || '').trim()))
        .map(f => f.id);
    if (ids.length) highlightFeatures(ids, '#0000FF');
}

function highlightRoads(names) {
    if (!Array.isArray(names) || !names.length) return;
    const ids = allParcelsData
        .filter(f => f.properties?.kategoria === 'droga' &&
            names.includes(String(f.properties.numer_obiektu || '').trim()))
        .map(f => f.id);
    if (ids.length) highlightFeatures(ids, '#FFA500');
}

/**
 * Tryb fokusu — działki z listy są w kolorach, reszta przyciemniona.
 * @param {Array<number>} ids
 */
function setFocusMode(ids) {
    if (!Array.isArray(ids) || !ids.length) return;
    const focused = new Set(ids.map(Number).filter(n => Number.isFinite(n)));
    focusedIds = focused;

    document.getElementById('map')?.classList.add('selection-focus-mode');

    // Każda działka, która NIE jest w focused, dostaje stan `dimmed`.
    for (const f of allParcelsData) {
        const id = Number(f.id);
        if (!Number.isFinite(id)) continue;
        if (focused.has(id)) {
            try { map.setFeatureState({ source: 'parcels', id }, { dimmed: false }); } catch {}
            try { map.setFeatureState({ source: 'points', id }, { dimmed: false }); } catch {}
        } else {
            try { map.setFeatureState({ source: 'parcels', id }, { dimmed: true }); } catch {}
            try { map.setFeatureState({ source: 'points', id }, { dimmed: true }); } catch {}
        }
    }
}

function clearFocusMode() {
    if (!focusedIds) return;
    document.getElementById('map')?.classList.remove('selection-focus-mode');
    for (const f of allParcelsData) {
        const id = Number(f.id);
        if (!Number.isFinite(id)) continue;
        try { map.setFeatureState({ source: 'parcels', id }, { dimmed: false }); } catch {}
        try { map.setFeatureState({ source: 'points', id }, { dimmed: false }); } catch {}
    }
    focusedIds = null;
}

function setupKeyboardZoomAnimation() {
    // MapLibre domyślnie animuje keyboard zoom, ale chcemy spójność czasów
    // z naszymi innymi animacjami (700-800ms). Tu nic dodatkowego nie trzeba —
    // ten hook zostawiam jako miejsce na ewentualne tweaki.
}
