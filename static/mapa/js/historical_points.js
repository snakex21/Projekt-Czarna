/* global window, maplibregl */
/**
 * Moduł warstwy "Punkty historyczne" dla mapy.
 *
 * - Pobiera dane z GET /api/historical-points (FeatureCollection).
 * - Renderuje markery jako koła z popupem (opis, źródło, zdjęcia).
 * - Rejestruje się w ``window.MapV2.setMapLayerVisibility`` jako grupa
 *   ``historical-points`` (wykorzystywana przez checkbox w panels.js).
 *
 * Ładowany PO ``map-script.js`` - polega na istniejącym ``window.MapV2``
 * i obiekcie ``maplibregl`` z globalnego skryptu MapLibre.
 *
 * Eksponowane API: ``window.HistoricalPoints = { init, layerIds, reload }``.
 */
(function () {
    'use strict';

    const API_URL = '/api/historical-points';
    const SOURCE_ID = 'historical-points';
    const LAYER_CIRCLE = 'historical-points-circle';
    const LAYER_LABEL = 'historical-points-label';

    let initialized = false;

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function buildPopupHtml(props) {
        if (!props) return '<div class="hp-popup">Brak danych</div>';
        const title = escapeHtml(props.display_name || props.object_name || 'Punkt historyczny');
        const description = props.description
            ? `<div class="hp-popup-description">${escapeHtml(props.description).replace(/\n/g, '<br>')}</div>`
            : '';
        // MapLibre przechowuje ``properties.photos`` jako zserializowany string
        // (nie natywną tablicę) - dekodujemy oba warianty.
        let photos = props.photos;
        if (typeof photos === 'string') {
            try {
                const parsed = JSON.parse(photos);
                if (Array.isArray(parsed)) photos = parsed;
            } catch (_) {
                photos = [];
            }
        }
        if (!Array.isArray(photos)) photos = [];
        const photosHtml = photos.length
            ? `<div class="hp-popup-photos">${photos.map((p) => {
                const filename = escapeHtml(p.filename || '');
                const caption = escapeHtml(p.caption || '');
                const url = `/point_photos/${encodeURIComponent(filename)}`;
                return `<figure class="hp-popup-photo">
                    <img src="${url}" alt="${filename}" loading="lazy" onerror="this.parentNode.style.display='none'"/>
                    ${caption ? `<figcaption>${caption}</figcaption>` : ''}
                </figure>`;
            }).join('')}</div>`
            : '';
        const source = props.source_note
            ? `<div class="hp-popup-source"><strong>Źródło:</strong> ${escapeHtml(props.source_note)}</div>`
            : '';
        return `<div class="hp-popup">
            <h3 class="hp-popup-title">${title}</h3>
            ${description}
            ${photosHtml}
            ${source}
        </div>`;
    }

    function ensureLayers(mapInstance) {
        const api = window.MapV2;
        if (!api || !api.addGeojsonSource || !api.addGeojsonLayer) {
            return false;
        }
        api.addGeojsonSource(SOURCE_ID, { type: 'FeatureCollection', features: [] });
        api.addGeojsonLayer({
            id: LAYER_CIRCLE,
            type: 'circle',
            source: SOURCE_ID,
            minzoom: 12,
            paint: {
                'circle-color': '#8b4513',
                'circle-radius': 8,
                'circle-stroke-color': '#fff8dc',
                'circle-stroke-width': 3,
            },
        });
        api.addGeojsonLayer({
            id: LAYER_LABEL,
            type: 'symbol',
            source: SOURCE_ID,
            minzoom: 14,
            layout: {
                'text-field': ['get', 'display_name'],
                'text-size': 12,
                'text-offset': [0, 1.4],
                'text-anchor': 'top',
                'text-allow-overlap': false,
                'text-optional': true,
            },
            paint: {
                'text-color': '#3e2723',
                'text-halo-color': '#fff8dc',
                'text-halo-width': 1.5,
            },
        });
        return true;
    }

    function bindPopup(mapInstance) {
        mapInstance.on('click', LAYER_CIRCLE, (e) => {
            const feature = e.features && e.features[0];
            if (!feature) return;
            e.originalEvent?.stopPropagation?.();
            new maplibregl.Popup({ maxWidth: '360px', closeButton: true })
                .setLngLat(feature.geometry.coordinates.slice())
                .setHTML(buildPopupHtml(feature.properties))
                .addTo(mapInstance);
        });
        mapInstance.on('mouseenter', LAYER_CIRCLE, () => {
            mapInstance.getCanvas().style.cursor = 'pointer';
        });
        mapInstance.on('mouseleave', LAYER_CIRCLE, () => {
            mapInstance.getCanvas().style.cursor = '';
        });
    }

    async function fetchAndRender() {
        const api = window.MapV2;
        if (!api) return;
        try {
            const response = await fetch(API_URL, { headers: { Accept: 'application/json' } });
            if (!response.ok) {
                console.warn('[historical_points] API zwróciło', response.status);
                return;
            }
            const data = await response.json();
            if (!data || !Array.isArray(data.features)) {
                console.warn('[historical_points] Nieprawidłowa odpowiedź (brak features)');
                return;
            }
            api.addGeojsonSource(SOURCE_ID, data);
            // Poinformuj mapę, żeby ukryła te obiekty w generycznej warstwie ``points``
            // (ikona + koło fallback). Dzięki temu klik na historyczny punkt nie otwiera
            // dwóch popupów (jeden z warstwy ``points``, drugi z naszej warstwy).
            const names = data.features
                .map((f) => f.properties && f.properties.object_name)
                .filter(Boolean);
            if (typeof api.setPointsExclusion === 'function') {
                api.setPointsExclusion(names);
            } else {
                console.warn('[historical_points] setPointsExclusion niedostępne - duplikat punktów możliwy');
            }
            console.info(`[historical_points] Załadowano ${data.features.length} punktów (ukryto w warstwie points)`);
        } catch (err) {
            console.warn('[historical_points] Błąd pobierania:', err);
        }
    }

    function init() {
        if (initialized) return;
        if (!window.MapV2) {
            console.warn('[historical_points] window.MapV2 niedostępne - moduł wyłączony');
            return;
        }
        const mapInstance = window.MapV2.getMap ? window.MapV2.getMap() : null;
        if (!mapInstance) {
            console.warn('[historical_points] getMap() nie zwróciło instancji mapy');
            return;
        }
        if (!ensureLayers(mapInstance)) {
            console.warn('[historical_points] addGeojson* niedostępne');
            return;
        }
        bindPopup(mapInstance);
        fetchAndRender();
        initialized = true;
    }

    function layerIds() {
        return [LAYER_CIRCLE, LAYER_LABEL];
    }

    async function reload() {
        if (!initialized) return;
        await fetchAndRender();
    }

    window.HistoricalPoints = Object.freeze({
        init,
        layerIds,
        reload,
        SOURCE_ID,
        LAYER_CIRCLE,
        LAYER_LABEL,
    });

    // Auto-init po załadowaniu skryptu (mapa już istnieje w map-script.js).
    if (document.readyState === 'complete') {
        init();
    } else {
        window.addEventListener('load', init);
    }
})();
