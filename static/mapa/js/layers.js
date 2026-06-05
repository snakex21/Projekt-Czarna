/** Źródła i definicje warstw MapLibre dla mapy katastralnej. */
(function () {
    'use strict';

    const NON_OUTLINE_FILTER = ['!=', ['get', 'kategoria'], 'obrys_miejscowosci'];

    function splitFeatures(features) {
        const polygons = { type: 'FeatureCollection', features: [] };
        const lines = { type: 'FeatureCollection', features: [] };
        const points = { type: 'FeatureCollection', features: [] };

        for (const f of features || []) {
            if (!f.geometry) continue;
            const t = f.geometry.type;
            if (t === 'Polygon' || t === 'MultiPolygon') polygons.features.push(f);
            else if (t === 'LineString' || t === 'MultiLineString') lines.features.push(f);
            else if (t === 'Point') points.features.push(f);
        }

        return { polygons, lines, points };
    }

    function addCoreSources(map, collections) {
        // Uwaga: NIE używamy promoteId - GeoJSON features mają id na top-level (z API).
        map.addSource('parcels', { type: 'geojson', data: collections.polygons, buffer: 64, tolerance: 0.5, maxzoom: 18 });
        map.addSource('lines', { type: 'geojson', data: collections.lines, buffer: 64, tolerance: 0.5, maxzoom: 18 });
        map.addSource('points', { type: 'geojson', data: collections.points, cluster: true, clusterMaxZoom: 16, clusterRadius: 50, buffer: 64, tolerance: 0.5, maxzoom: 18 });
    }

    function addCoreLayers(map, deps) {
        const PARCEL_COLORS = deps.PARCEL_COLORS;
        const PARCEL_FILL_OPACITY = deps.PARCEL_FILL_OPACITY;

        map.addLayer({
            id: 'parcels-fill', type: 'fill', source: 'parcels', filter: NON_OUTLINE_FILTER,
            paint: {
                'fill-color': [
                    'case',
                    ['boolean', ['feature-state', 'ownerColored'], false], ['coalesce', ['feature-state', 'ownerColor'], '#3388ff'],
                    ['boolean', ['feature-state', 'highlight'], false], ['coalesce', ['feature-state', 'highlightColor'], '#ffc107'],
                    ['boolean', ['feature-state', 'ownerHover'], false], '#a855f7',
                    ['boolean', ['feature-state', 'tempHighlight'], false], 'orange',
                    ['match', ['get', 'kategoria'],
                        'budowlana', PARCEL_COLORS.budowlana,
                        'rolna', PARCEL_COLORS.rolna,
                        'las', PARCEL_COLORS.las,
                        'pastwisko', PARCEL_COLORS.pastwisko,
                        'obiekt_specjalny', PARCEL_COLORS.obiekt_specjalny,
                        PARCEL_COLORS.default]
                ],
                'fill-opacity': [
                    'case',
                    ['boolean', ['feature-state', 'dimmed'], false], 0.05,
                    ['all', ['boolean', ['feature-state', 'highlight'], false], ['boolean', ['feature-state', 'isProtocol'], false]], 0.22,
                    ['boolean', ['feature-state', 'ownerColored'], false], 0.6,
                    ['boolean', ['feature-state', 'highlight'], false], 0.55,
                    ['boolean', ['feature-state', 'ownerHover'], false], 0.45,
                    ['boolean', ['feature-state', 'tempHighlight'], false], 0.4,
                    ['boolean', ['feature-state', 'hover'], false], 0.55,
                    ['match', ['get', 'kategoria'],
                        'las', PARCEL_FILL_OPACITY.las,
                        'pastwisko', PARCEL_FILL_OPACITY.pastwisko,
                        'budowlana', 0.18,
                        'rolna', 0.22,
                        PARCEL_FILL_OPACITY.default]
                ]
            }
        });

        map.addLayer({
            id: 'parcels-line-halo', type: 'line', source: 'parcels', filter: NON_OUTLINE_FILTER,
            paint: {
                'line-color': '#111111',
                'line-width': ['interpolate', ['linear'], ['zoom'], 12, 1.2, 15, 1.8, 18, 3.0, 22, 4.5],
                'line-opacity': ['case', ['boolean', ['feature-state', 'dimmed'], false], 0.16, 0.45]
            }
        });

        map.addLayer({
            id: 'parcels-line', type: 'line', source: 'parcels', filter: NON_OUTLINE_FILTER,
            paint: {
                'line-color': [
                    'case',
                    ['boolean', ['feature-state', 'ownerColored'], false], ['coalesce', ['feature-state', 'ownerColor'], '#3388ff'],
                    ['boolean', ['feature-state', 'highlight'], false], ['coalesce', ['feature-state', 'highlightColor'], '#ffc107'],
                    ['boolean', ['feature-state', 'ownerHover'], false], '#a855f7',
                    ['boolean', ['feature-state', 'tempHighlight'], false], 'orange',
                    ['boolean', ['feature-state', 'hover'], false], '#ff0000',
                    ['match', ['get', 'kategoria'],
                        'budowlana', PARCEL_COLORS.budowlana,
                        'rolna', PARCEL_COLORS.rolna,
                        'las', '#16a085',
                        'pastwisko', '#f1c40f',
                        'obrys_miejscowosci', PARCEL_COLORS.obrys_miejscowosci,
                        'obiekt_specjalny', PARCEL_COLORS.obiekt_specjalny,
                        PARCEL_COLORS.default]
                ],
                'line-width': [
                    'case',
                    ['boolean', ['feature-state', 'ownerColored'], false], 3,
                    ['all', ['boolean', ['feature-state', 'highlight'], false], ['boolean', ['feature-state', 'isProtocol'], false]], 5,
                    ['boolean', ['feature-state', 'highlight'], false], 4,
                    ['boolean', ['feature-state', 'ownerHover'], false], 4,
                    ['boolean', ['feature-state', 'tempHighlight'], false], 4,
                    ['boolean', ['feature-state', 'hover'], false], 4,
                    3
                ],
                'line-opacity': ['case', ['boolean', ['feature-state', 'dimmed'], false], 0.2, 1]
            }
        });

        map.addLayer({
            id: 'settlement-outline', type: 'line', source: 'parcels',
            filter: ['==', ['get', 'kategoria'], 'obrys_miejscowosci'],
            paint: { 'line-color': '#ef4444', 'line-width': 2, 'line-opacity': 0.65, 'line-dasharray': ['literal', [3, 1.5]] }
        });

        map.addLayer({
            id: 'lines-layer', type: 'line', source: 'lines',
            paint: {
                'line-color': ['case', ['boolean', ['feature-state', 'highlight'], false], ['coalesce', ['feature-state', 'highlightColor'], '#ffc107'], ['match', ['get', 'kategoria'], 'droga', PARCEL_COLORS.droga, 'rzeka', PARCEL_COLORS.rzeka, PARCEL_COLORS.default]],
                'line-width': ['case', ['boolean', ['feature-state', 'highlight'], false], 6, ['match', ['get', 'kategoria'], 'rzeka', 4, 'droga', 3, 2]],
                'line-opacity': ['case', ['boolean', ['feature-state', 'dimmed'], false], 0.2, 1]
            }
        });

        map.addLayer({
            id: 'parcels-labels', type: 'symbol', source: 'parcels', filter: NON_OUTLINE_FILTER,
            layout: { 'text-field': ['get', 'numer_obiektu'], 'text-size': 12, 'text-allow-overlap': true, 'text-ignore-placement': true, 'symbol-placement': 'point', 'text-anchor': 'center' },
            paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1.5 }
        });

        map.addLayer({
            id: 'points-clusters', type: 'circle', source: 'points', filter: ['has', 'point_count'],
            paint: { 'circle-color': '#4363D8', 'circle-radius': ['step', ['get', 'point_count'], 18, 10, 22, 50, 28], 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 }
        });
        map.addLayer({
            id: 'points-cluster-count', type: 'symbol', source: 'points', filter: ['has', 'point_count'],
            layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12 },
            paint: { 'text-color': '#ffffff' }
        });

        map.addLayer({
            id: 'points-circle-fallback', type: 'circle', source: 'points',
            filter: ['all', ['!', ['has', 'point_count']], ['!', ['has', 'icons_loaded']]],
            minzoom: 13,
            paint: { 'circle-color': ['match', ['get', 'kategoria'], 'budynek', '#e67e22', 'kapliczka', '#9b59b6', 'obiekt_specjalny', '#2c3e50', '#3388ff'], 'circle-radius': 7, 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 }
        });

        map.addLayer({
            id: 'points-icons', type: 'symbol', source: 'points', filter: ['!', ['has', 'point_count']], minzoom: 13,
            layout: {
                'icon-image': ['match', ['get', 'kategoria'], 'budynek', 'icon-budynek', 'kapliczka', 'icon-kapliczka', 'obiekt_specjalny', 'icon-obiekt-specjalny', 'icon-budynek'],
                'icon-size': ['match', ['get', 'kategoria'], 'budynek', 0.18, 'kapliczka', 0.16, 'obiekt_specjalny', 0.18, 0.16],
                'icon-allow-overlap': true,
                'icon-ignore-placement': true,
                'icon-anchor': 'center'
            },
            paint: { 'icon-opacity': ['case', ['boolean', ['feature-state', 'dimmed'], false], 0.25, 1] }
        });

        map.addLayer({
            id: 'points-halo', type: 'circle', source: 'points', filter: ['!', ['has', 'point_count']], minzoom: 13,
            paint: {
                'circle-color': ['case', ['boolean', ['feature-state', 'highlight'], false], ['coalesce', ['feature-state', 'highlightColor'], '#ffc107'], ['boolean', ['feature-state', 'ownerHover'], false], '#a855f7', ['boolean', ['feature-state', 'hover'], false], '#ff0000', 'transparent'],
                'circle-radius': 16,
                'circle-opacity': ['case', ['any', ['boolean', ['feature-state', 'highlight'], false], ['boolean', ['feature-state', 'ownerHover'], false], ['boolean', ['feature-state', 'hover'], false]], 0.55, 0],
                'circle-stroke-color': '#fff',
                'circle-stroke-width': 2,
                'circle-stroke-opacity': ['case', ['any', ['boolean', ['feature-state', 'highlight'], false], ['boolean', ['feature-state', 'ownerHover'], false], ['boolean', ['feature-state', 'hover'], false]], 0.9, 0]
            }
        });

        map.addLayer({
            id: 'points-labels', type: 'symbol', source: 'points', filter: ['!', ['has', 'point_count']], minzoom: 15,
            layout: { 'text-field': ['get', 'numer_obiektu'], 'text-size': 11, 'text-offset': [0, 1.2], 'text-anchor': 'top', 'text-allow-overlap': true, 'text-optional': true },
            paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1.5 }
        });
    }

    window.MapLayers = Object.freeze({
        splitFeatures,
        addCoreSources,
        addCoreLayers,
    });
})();
