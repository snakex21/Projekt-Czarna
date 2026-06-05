/** Stan i operacje highlightów działek/obiektów MapLibre. */
(function () {
    'use strict';

    function create(deps) {
        const getMap = deps.getMap;
        const fitToFeatures = deps.fitToFeatures;
        const addLpMarker = deps.addLpMarker;
        const clearLpMarkers = deps.clearLpMarkers;
        const hideHighlightTooltip = deps.hideHighlightTooltip;
        const clearOwnerColored = deps.clearOwnerColored;
        const clearFocusMode = deps.clearFocusMode;

        const highlightFeatureIds = new Set();   // trwałe podświetlenie
        let highlightColor = '#ffc107';
        const ownerHoverIds = new Set();         // hover karty właściciela
        const temporaryHighlightIds = new Set(); // search exact match
        let hoveredFromPanelId = null;           // hover z panelu
        const highlightOwnerInfo = new Map();    // feature id → dane tooltipu

        function setFeatureStateInKnownSources(id, stateUpdate) {
            const map = getMap();
            if (!map) return;
            try { map.setFeatureState({ source: 'parcels', id }, stateUpdate); } catch {}
            try { map.setFeatureState({ source: 'points', id }, stateUpdate); } catch {}
        }

        function highlightFeatures(ids, color, opts = {}) {
            clearAllHighlights({ keepHistorical: true });
            if (!Array.isArray(ids) || !ids.length) return;

            highlightColor = color || '#ffc107';
            const stateKey = opts.temporary ? 'tempHighlight' : 'highlight';
            const targetSet = opts.temporary ? temporaryHighlightIds : highlightFeatureIds;
            targetSet.clear();

            const ownerLp = opts.ownerLp != null ? opts.ownerLp : null;
            const isProtocol = !!opts.isProtocol;

            if (!opts.temporary && opts.ownerName) {
                for (const id of ids) {
                    const n = Number(id);
                    if (Number.isFinite(n)) highlightOwnerInfo.set(n, {
                        ownerName: opts.ownerName,
                        ownershipType: opts.ownershipType || (isProtocol ? 'Wg Protokołu' : 'Rzeczywiste'),
                        ownerLp,
                    });
                }
            }

            for (const id of ids) {
                const numId = Number(id);
                if (!Number.isFinite(numId)) continue;
                targetSet.add(numId);
                const stateUpdate = { [stateKey]: true };
                if (!opts.temporary) {
                    stateUpdate.highlightColor = highlightColor;
                    stateUpdate.isProtocol = isProtocol;
                    if (ownerLp != null) stateUpdate.ownerLp = ownerLp;
                }
                setFeatureStateInKnownSources(numId, stateUpdate);

                if (!opts.temporary && ownerLp != null) {
                    addLpMarker(numId, ownerLp, highlightColor, isProtocol);
                }
            }

            if (!opts.skipFit) {
                fitToFeatures(ids);
            }

            const ctrl = document.getElementById('highlight-controls');
            if (ctrl && !opts.temporary) ctrl.classList.remove('hidden');
            const cnt = document.getElementById('selected-count');
            if (cnt && !opts.temporary) cnt.textContent = ids.length;
        }

        function clearTemporaryHighlight() {
            for (const id of temporaryHighlightIds) {
                setFeatureStateInKnownSources(id, { tempHighlight: false });
            }
            temporaryHighlightIds.clear();
        }

        function clearAllHighlights({ keepHistorical } = {}) {
            for (const id of highlightFeatureIds) {
                setFeatureStateInKnownSources(id, { highlight: false, isProtocol: false, ownerLp: null });
            }
            highlightFeatureIds.clear();
            highlightOwnerInfo.clear();
            clearLpMarkers();
            hideHighlightTooltip();
            clearTemporaryHighlight();
            setOwnerHoverHighlight(null, false);
            clearOwnerColored();
            clearFocusMode();

            if (!keepHistorical) {
                const ctrl = document.getElementById('highlight-controls');
                if (ctrl) ctrl.classList.add('hidden');
                const cnt = document.getElementById('selected-count');
                if (cnt) cnt.textContent = 0;

                const url = new URL(window.location);
                ['highlightByIds', 'highlightTopOwners', 'highlightParcels', 'highlightParcel',
                 'highlightRivers', 'highlightRoads', 'findHouseNumber', 'ownerName', 'ownership']
                    .forEach(k => url.searchParams.delete(k));
                history.replaceState({}, '', url);
            }
        }

        function setOwnerHoverHighlight(ids, on) {
            if (!on) {
                for (const id of ownerHoverIds) {
                    setFeatureStateInKnownSources(id, { ownerHover: false });
                }
                ownerHoverIds.clear();
                return;
            }
            if (!Array.isArray(ids)) return;
            for (const id of ids) {
                const n = Number(id);
                if (!Number.isFinite(n)) continue;
                ownerHoverIds.add(n);
                setFeatureStateInKnownSources(n, { ownerHover: true });
            }
        }

        function setHoverFeature(featureId, on) {
            const id = Number(featureId);
            if (!Number.isFinite(id)) return;
            if (on) {
                if (hoveredFromPanelId !== null && hoveredFromPanelId !== id) {
                    setFeatureStateInKnownSources(hoveredFromPanelId, { hover: false });
                }
                hoveredFromPanelId = id;
                setFeatureStateInKnownSources(id, { hover: true });
            } else {
                setFeatureStateInKnownSources(id, { hover: false });
                if (hoveredFromPanelId === id) hoveredFromPanelId = null;
            }
        }

        function markSingleFeature(featureId, color = 'fuchsia') {
            clearAllHighlights({ keepHistorical: true });
            const id = Number(featureId);
            if (!Number.isFinite(id)) return;
            highlightFeatureIds.add(id);
            setFeatureStateInKnownSources(id, { highlight: true, highlightColor: color });
            document.getElementById('highlight-controls')?.classList.remove('hidden');
            const cnt = document.getElementById('selected-count');
            if (cnt) cnt.textContent = 1;
        }

        function getHighlightInfo(id) {
            return highlightOwnerInfo.get(Number(id));
        }

        function setHighlightInfo(id, info) {
            const numericId = Number(id);
            if (Number.isFinite(numericId) && info) highlightOwnerInfo.set(numericId, info);
        }

        return Object.freeze({
            highlightFeatures,
            clearTemporaryHighlight,
            clearAllHighlights,
            setOwnerHoverHighlight,
            setHoverFeature,
            markSingleFeature,
            getHighlightInfo,
            setHighlightInfo,
        });
    }

    window.MapHighlights = Object.freeze({ create });
})();
