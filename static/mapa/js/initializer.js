/** Inicjalizacja MapLibre, ikon punktów i suwaka przezroczystości mapy historycznej. */
(function () {
    'use strict';

    function create(deps) {
        const getHistoricalOpacity = deps.getHistoricalOpacity;
        const setHistoricalOpacityState = deps.setHistoricalOpacityState;
        const historicalMapUrl = deps.historicalMapUrl;

        function initializeMap() {
            const calibration = window.MAP_CONFIG?.calibration || {
                sw: { lat: 50.0445232994271194, lng: 21.2118218969993393 },
                ne: { lat: 50.0766374787729518, lng: 21.2672168223566409 }
            };
            const defaults = window.MAP_CONFIG?.defaults || {
                center: { lat: 50.0605803891, lng: 21.2395193597 },
                zoom: 14
            };

            const map = new maplibregl.Map({
                container: 'map',
                style: {
                    version: 8,
                    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
                    sources: {
                        satellite: {
                            type: 'raster',
                            tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
                            tileSize: 256,
                            maxzoom: 19,
                            attribution: 'Tiles &copy; Esri'
                        },
                        osm: {
                            type: 'raster',
                            tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png', 'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png', 'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png'],
                            tileSize: 256,
                            maxzoom: 19,
                            attribution: '&copy; OpenStreetMap contributors'
                        },
                        historical: {
                            type: 'image',
                            url: historicalMapUrl,
                            coordinates: [
                                [calibration.sw.lng, calibration.ne.lat],
                                [calibration.ne.lng, calibration.ne.lat],
                                [calibration.ne.lng, calibration.sw.lat],
                                [calibration.sw.lng, calibration.sw.lat],
                            ]
                        }
                    },
                    layers: [
                        { id: 'satellite-layer', type: 'raster', source: 'satellite' },
                        { id: 'osm-layer', type: 'raster', source: 'osm', layout: { visibility: 'none' } },
                        { id: 'historical-layer', type: 'raster', source: 'historical', paint: { 'raster-opacity': getHistoricalOpacity() } }
                    ]
                },
                center: [defaults.center.lng, defaults.center.lat],
                zoom: defaults.zoom,
                minZoom: 12,
                maxZoom: 22,
                maxBounds: [
                    [calibration.sw.lng - 0.02, calibration.sw.lat - 0.02],
                    [calibration.ne.lng + 0.02, calibration.ne.lat + 0.02]
                ],
                attributionControl: false,
                renderWorldCopies: false,
            });

            map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-left');
            map.addControl(new maplibregl.AttributionControl({ compact: true }));

            map.on('error', (event) => {
                const message = event?.error?.message || String(event?.error || '');
                if (message.toLowerCase().includes('image') || message.includes('historical')) {
                    console.warn('⚠️ Nie udało się załadować mapy historycznej:', message, historicalMapUrl);
                }
            });

            map.on('mousemove', (e) => {
                const div = document.getElementById('mouse-coordinates');
                if (div) div.innerHTML = `${e.lngLat.lat.toFixed(5)}, ${e.lngLat.lng.toFixed(5)}`;
            });

            setupHistoricalOpacityControl(map);
            return map;
        }

        function loadPointIcons(map) {
            if (!map) return;
            // Te same ikony co w v1 (Flaticon CDN). MapLibre wymaga PNG/SVG-bitmap.
            const icons = {
                'icon-budynek': 'https://cdn-icons-png.flaticon.com/512/25/25694.png',
                'icon-kapliczka': 'https://cdn-icons-png.flaticon.com/512/2133/2133353.png',
                'icon-obiekt-specjalny': 'https://cdn-icons-png.flaticon.com/512/785/785432.png',
            };
            Object.entries(icons).forEach(([name, url]) => {
                if (map.hasImage(name)) return;
                map.loadImage(url).then(img => {
                    if (img && !map.hasImage(name)) {
                        map.addImage(name, img.data, { pixelRatio: 2 });
                    }
                }).catch(err => {
                    console.warn(`Nie udało się załadować ikony ${name}:`, err);
                });
            });
        }

        function setupHistoricalOpacityControl(map) {
            const slider = document.getElementById('opacitySlider')
                || document.getElementById('historical-opacity')
                || document.getElementById('historical-opacity-slider');
            if (!slider) return;
            slider.addEventListener('input', (e) => {
                const v = Number(e.target.value);
                const opacity = v > 1 ? v / 100 : v;
                setHistoricalOpacityState(opacity);
                if (map.getLayer('historical-layer')) {
                    map.setPaintProperty('historical-layer', 'raster-opacity', opacity);
                }
                const pct = document.getElementById('opacityPercentage') || document.getElementById('opacity-percentage');
                if (pct) pct.textContent = Math.round(opacity * 100);
            });
        }

        return Object.freeze({
            initializeMap,
            loadPointIcons,
            setupHistoricalOpacityControl,
        });
    }

    window.MapInitializer = Object.freeze({ create });
})();
