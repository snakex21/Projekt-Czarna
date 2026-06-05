/** Interakcje hover/click warstw MapLibre dla mapy katastralnej. */
(function () {
    'use strict';

    function create(deps) {
        const getMap = deps.getMap;
        const getHoveredParcelId = deps.getHoveredParcelId;
        const setHoveredParcelId = deps.setHoveredParcelId;
        const getFeatureById = deps.getFeatureById;
        const parseMaybeJson = deps.parseMaybeJson;
        const getHighlightInfo = deps.getHighlightInfo;
        const showHighlightTooltip = deps.showHighlightTooltip;
        const hideHighlightTooltip = deps.hideHighlightTooltip;
        const handleObjectClick = deps.handleObjectClick;

        function setupHoverInteractions() {
            const map = getMap();
            if (!map) return;

            map.on('mousemove', 'parcels-fill', (e) => {
                if (!e.features.length) return;
                const id = e.features[0].id;
                const hoveredParcelId = getHoveredParcelId();
                if (hoveredParcelId !== null && hoveredParcelId !== id) {
                    map.setFeatureState({ source: 'parcels', id: hoveredParcelId }, { hover: false });
                    window.PanelsV2?.clearHoverHighlights();
                }
                setHoveredParcelId(id);
                map.setFeatureState({ source: 'parcels', id }, { hover: true });
                map.getCanvas().style.cursor = 'pointer';

                const f = getFeatureById(id);
                const wl = parseMaybeJson(f?.properties?.wlasciciele) || parseMaybeJson(e.features[0].properties?.wlasciciele);
                window.PanelsV2?.highlightOwnerByFeatureHover(id, wl);

                const info = getHighlightInfo(id);
                if (info) showHighlightTooltip(e.point, info);
                else hideHighlightTooltip();
            });

            map.on('mouseleave', 'parcels-fill', () => {
                const hoveredParcelId = getHoveredParcelId();
                if (hoveredParcelId !== null) {
                    map.setFeatureState({ source: 'parcels', id: hoveredParcelId }, { hover: false });
                    setHoveredParcelId(null);
                }
                map.getCanvas().style.cursor = '';
                window.PanelsV2?.clearHoverHighlights();
                hideHighlightTooltip();
            });

            map.on('mouseenter', 'points-icons', () => map.getCanvas().style.cursor = 'pointer');
            map.on('mouseleave', 'points-icons', () => map.getCanvas().style.cursor = '');
            map.on('mouseenter', 'points-circle-fallback', () => map.getCanvas().style.cursor = 'pointer');
            map.on('mouseleave', 'points-circle-fallback', () => map.getCanvas().style.cursor = '');
            map.on('mouseenter', 'points-clusters', () => map.getCanvas().style.cursor = 'pointer');
            map.on('mouseleave', 'points-clusters', () => map.getCanvas().style.cursor = '');
        }

        function setupClickInteractions() {
            const map = getMap();
            if (!map) return;

            map.on('click', 'parcels-fill', (e) => {
                if (!e.features.length) return;
                handleObjectClick(e.features[0], e.lngLat);
            });
            // Klik rejestrujemy WYŁĄCZNIE na ``points-circle-fallback`` (zawsze renderowany),
            // nie na ``points-icons`` - inaczej po załadowaniu ikon oba handlery odpalają
            // się dla tego samego punktu, dając podwójny popup.
            map.on('click', 'points-circle-fallback', (e) => {
                if (!e.features.length) return;
                handleObjectClick(e.features[0], e.lngLat);
            });
            map.on('click', 'points-clusters', (e) => {
                const f = map.queryRenderedFeatures(e.point, { layers: ['points-clusters'] })[0];
                if (!f) return;
                const cid = f.properties.cluster_id;
                map.getSource('points').getClusterExpansionZoom(cid).then(zoom => {
                    map.easeTo({ center: f.geometry.coordinates, zoom, duration: 600, essential: true });
                });
            });
        }

        return Object.freeze({
            setupHoverInteractions,
            setupClickInteractions,
        });
    }

    window.MapInteractions = Object.freeze({ create });
})();
