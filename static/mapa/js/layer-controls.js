/** Sterowanie widocznością i dodatkowymi warstwami mapy. */
(function () {
    'use strict';

    function create(deps) {
        const hiddenCategories = new Set();
        const getMap = deps.getMap;
        const setHistoricalOpacityState = deps.setHistoricalOpacityState;

        function setCategoryVisibility(kategoria, visible) {
            const map = getMap();
            if (!map) return;
            if (visible) hiddenCategories.delete(kategoria);
            else hiddenCategories.add(kategoria);

            const nonOutline = ['!=', ['get', 'kategoria'], 'obrys_miejscowosci'];
            const buildFilter = (baseFilter, forceNonOutline = false) => {
                const hidden = [...hiddenCategories];
                let filter = baseFilter || null;
                if (forceNonOutline) filter = filter ? ['all', filter, nonOutline] : nonOutline;
                if (!hidden.length) return filter;
                const cat = ['get', 'kategoria'];
                const noneOfHidden = ['all', ...hidden.map(h => ['!=', cat, h])];
                if (!filter) return noneOfHidden;
                return ['all', filter, noneOfHidden];
            };

            const safeSetFilter = (id, filter) => { if (map.getLayer(id)) map.setFilter(id, filter); };
            safeSetFilter('parcels-fill', buildFilter(null, true));
            safeSetFilter('parcels-line-halo', buildFilter(null, true));
            safeSetFilter('parcels-line', buildFilter(null, true));
            safeSetFilter('parcels-labels', buildFilter(nonOutline));
            if (map.getLayer('settlement-outline')) {
                map.setLayoutProperty('settlement-outline', 'visibility', hiddenCategories.has('obrys_miejscowosci') ? 'none' : 'visible');
            }
            safeSetFilter('lines-layer', buildFilter(null));
            const pointBase = ['!', ['has', 'point_count']];
            safeSetFilter('points-circle-fallback', buildFilter(pointBase));
            safeSetFilter('points-icons', buildFilter(pointBase));
            safeSetFilter('points-halo', buildFilter(pointBase));
            safeSetFilter('points-labels', buildFilter(pointBase));
        }

        function setBaseLayer(type) {
            const map = getMap();
            if (!map) return;
            if (map.getLayer('satellite-layer')) map.setLayoutProperty('satellite-layer', 'visibility', type === 'satellite' ? 'visible' : 'none');
            if (map.getLayer('osm-layer')) map.setLayoutProperty('osm-layer', 'visibility', type === 'osm' ? 'visible' : 'none');
        }

        function setMapLayerVisibility(group, visible) {
            const map = getMap();
            if (!map) return;
            const v = visible ? 'visible' : 'none';
            const safe = (id) => { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', v); };
            if (group === 'historical') safe('historical-layer');
            if (group === 'parcels') ['parcels-fill', 'parcels-line-halo', 'parcels-line', 'settlement-outline', 'lines-layer'].forEach(safe);
            if (group === 'labels') ['parcels-labels', 'points-labels'].forEach(safe);
            if (group === 'points') ['points-clusters', 'points-cluster-count', 'points-circle-fallback', 'points-icons', 'points-halo'].forEach(safe);
            if (group === 'historical-points') (window.HistoricalPoints?.layerIds?.() || []).forEach(safe);
        }

        function addGeojsonSource(sourceId, data) {
            const map = getMap();
            if (!map) return;
            if (map.getSource(sourceId)) map.getSource(sourceId).setData(data);
            else map.addSource(sourceId, { type: 'geojson', data });
        }

        function addGeojsonLayer(spec) {
            const map = getMap();
            if (!map || !spec || !spec.id) return false;
            if (map.getLayer(spec.id)) return false;
            map.addLayer(spec);
            return true;
        }

        function setHistoricalOpacity(opacity) {
            const map = getMap();
            const nextOpacity = Math.max(0, Math.min(1, Number(opacity) || 0));
            setHistoricalOpacityState(nextOpacity);
            if (map?.getLayer('historical-layer')) map.setPaintProperty('historical-layer', 'raster-opacity', nextOpacity);
        }

        function setPointsExclusion(excludeNames) {
            const map = getMap();
            if (!map) return;
            const base = ['!', ['has', 'point_count']];
            const list = Array.isArray(excludeNames) ? excludeNames.filter(Boolean) : [];
            const filter = list.length ? ['all', base, ['!', ['in', ['get', 'numer_obiektu'], ['literal', list]]]] : base;
            ['points-icons', 'points-circle-fallback', 'points-halo', 'points-labels'].forEach((id) => {
                if (map.getLayer(id)) map.setFilter(id, filter);
            });
        }

        return Object.freeze({
            setCategoryVisibility,
            setBaseLayer,
            setMapLayerVisibility,
            addGeojsonSource,
            addGeojsonLayer,
            setHistoricalOpacity,
            setPointsExclusion,
        });
    }

    window.MapLayerControls = Object.freeze({ create });
})();
