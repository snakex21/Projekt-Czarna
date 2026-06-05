/** Tooltipy highlightów i plakietki Lp. na mapie. */
(function () {
    'use strict';

    function create(deps) {
        const getMap = deps.getMap;
        const getFeatureById = deps.getFeatureById;
        const featureCenter = deps.featureCenter;
        const lpMarkers = new Map();
        let highlightTooltip = null;

        function getHighlightTooltip() {
            if (highlightTooltip) return highlightTooltip;
            const el = document.createElement('div');
            el.className = 'maplibre-highlight-tooltip';
            el.style.cssText = [
                'position:absolute', 'pointer-events:none', 'z-index:5',
                'background:rgba(20,20,20,0.92)', 'color:#fff',
                'padding:6px 10px', 'border-radius:6px', 'font-size:12px',
                'font-weight:500', 'line-height:1.35', 'box-shadow:0 4px 12px rgba(0,0,0,0.3)',
                'border:1px solid rgba(255,255,255,0.15)', 'display:none', 'max-width:260px',
                'transition:opacity 0.12s'
            ].join(';');
            document.getElementById('map')?.appendChild(el);
            highlightTooltip = el;
            return el;
        }

        function showHighlightTooltip(point, info) {
            if (!info) { hideHighlightTooltip(); return; }
            const el = getHighlightTooltip();
            const lp = info.ownerLp != null ? ` <span style="opacity:.7">Lp.${info.ownerLp}</span>` : '';
            const typeBadge = info.ownershipType === 'Wg Protokołu'
                ? '<span style="background:#a855f7;padding:1px 6px;border-radius:8px;font-size:10px;text-transform:uppercase;letter-spacing:0.5px">Wg protokołu</span>'
                : '<span style="background:#22c55e;padding:1px 6px;border-radius:8px;font-size:10px;text-transform:uppercase;letter-spacing:0.5px">Rzeczywiste</span>';
            el.innerHTML = `<div style="margin-bottom:3px">${typeBadge}</div><div><b>${info.ownerName || '—'}</b>${lp}</div>`;
            el.style.left = (point.x + 14) + 'px';
            el.style.top = (point.y + 14) + 'px';
            el.style.display = 'block';
        }

        function hideHighlightTooltip() {
            if (highlightTooltip) highlightTooltip.style.display = 'none';
        }

        function addLpMarker(featureId, lp, color, isProtocol) {
            if (lp == null || lp === '') return;
            const markerKey = Number(featureId);
            if (!Number.isFinite(markerKey)) return;

            // Ta sama działka może pojawić się kilka razy w danych właściciela.
            if (lpMarkers.has(markerKey)) return;

            const map = getMap();
            const f = getFeatureById(featureId);
            if (!map || !f) return;
            const center = featureCenter(f);
            if (!center) return;

            const el = document.createElement('div');
            el.className = 'lp-marker';
            el.style.cssText = [
                'pointer-events:none',
                'font:600 11px/1 -apple-system,Segoe UI,sans-serif',
                'color:#fff',
                'padding:3px 7px',
                'border-radius:10px',
                'white-space:nowrap',
                'box-shadow:0 1px 4px rgba(0,0,0,0.5)',
                'text-shadow:0 1px 2px rgba(0,0,0,0.5)',
                `background:${isProtocol
                    ? `repeating-linear-gradient(45deg, ${color} 0 6px, rgba(0,0,0,0.35) 6px 10px)`
                    : color}`,
                'border:1.5px solid #fff',
                'transform:translateY(-14px)',
            ].join(';');
            el.textContent = `Lp.${lp}`;

            const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
                .setLngLat(center)
                .addTo(map);
            lpMarkers.set(markerKey, marker);
        }

        function clearLpMarkers() {
            for (const marker of lpMarkers.values()) {
                try { marker.remove(); } catch {}
            }
            lpMarkers.clear();
        }

        return Object.freeze({
            showHighlightTooltip,
            hideHighlightTooltip,
            addLpMarker,
            clearLpMarkers,
        });
    }

    window.MapHighlightMarkers = Object.freeze({ create });
})();
