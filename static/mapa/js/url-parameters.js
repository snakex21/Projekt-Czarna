/** Obsługa parametrów URL sterujących podświetleniami i widokiem mapy. */
(function () {
    'use strict';

    function create(deps) {
        const getParcels = deps.getParcels;
        const getFeatureById = deps.getFeatureById;
        const getMap = deps.getMap;
        const highlightFeatures = deps.highlightFeatures;
        const highlightOwners = deps.highlightOwners;
        const highlightRivers = deps.highlightRivers;
        const highlightRoads = deps.highlightRoads;
        const featureCenter = deps.featureCenter;
        const escapeHtml = deps.escapeHtml;

        function handleUrlParameters() {
            const params = new URLSearchParams(window.location.search);
            const allParcelsData = getParcels();

            const idsParam = params.get('highlightByIds');
            if (idsParam) {
                const ids = idsParam.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
                if (ids.length) highlightFeatures(ids, 'fuchsia');
            }

            // highlightTopOwners — wielu właścicieli, kolorowanie z palety.
            const ownersParam = params.get('highlightTopOwners');
            if (ownersParam) {
                let ownership = params.get('ownership') || 'wszystkie';
                if (ownership === 'real') ownership = 'rzeczywista';
                if (ownership === 'protocol') ownership = 'protokol';
                const keys = [...new Set(ownersParam.split(',').map(s => s.trim()).filter(Boolean))];
                if (keys.length) highlightOwners(keys, ownership);
            }

            const parcelsParam = params.get('highlightParcels') || params.get('highlightParcel');
            if (parcelsParam) {
                const numbers = parcelsParam.split(',').map(s => s.trim()).filter(Boolean);
                const ids = allParcelsData
                    .filter(p => numbers.includes(String(p.properties.numer_obiektu)))
                    .map(p => p.id);
                if (ids.length) highlightFeatures(ids, '#FF0000');
            }

            const riversParam = params.get('highlightRivers');
            if (riversParam) {
                const names = [...new Set(riversParam.split(',').map(s => s.trim()).filter(Boolean))];
                highlightRivers(names);
            }

            const roadsParam = params.get('highlightRoads');
            if (roadsParam) {
                const names = [...new Set(roadsParam.split(',').map(s => s.trim()).filter(Boolean))];
                highlightRoads(names);
            }

            const houseNumberParam = params.get('findHouseNumber');
            if (houseNumberParam) {
                const ownerName = params.get('ownerName') || '';
                const search = String(houseNumberParam).trim().toLowerCase();
                const f = allParcelsData.find(p =>
                    (p.properties.kategoria === 'budynek' || p.properties.kategoria === 'dom') &&
                    (p.properties.numer_obiektu || '').toLowerCase() === search);
                if (f) {
                    highlightFeatures([f.id], 'fuchsia');
                    const center = featureCenter(f);
                    const map = getMap();
                    if (center && map) {
                        new maplibregl.Popup({ maxWidth: '320px' })
                            .setLngLat(center)
                            .setHTML(`<div style="text-align:center;"><h3>🏠 Dom nr ${escapeHtml(houseNumberParam)}</h3>${ownerName ? `<p><b>Właściciel:</b> ${escapeHtml(ownerName)}</p>` : ''}</div>`)
                            .addTo(map);
                    }
                }
            }

            // ownerKey + show=house — pokaż dom konkretnego właściciela.
            const ownerKeyParam = params.get('ownerKey');
            const showParam = params.get('show');
            if (ownerKeyParam && showParam === 'house') {
                showHouseByOwnerKey(ownerKeyParam);
            }
        }

        async function showHouseByOwnerKey(ownerKey) {
            try {
                const resp = await fetch(`/api/wlasciciel/${encodeURIComponent(ownerKey)}`);
                if (!resp.ok) return;
                const ownerData = await resp.json();
                if (!ownerData) return;

                const houseNo = ownerData.dom_numer || ownerData.numer_domu;
                const objectId = ownerData.dom_obiekt_id;
                const ownerName = ownerData.nazwa_wlasciciela || '';

                let target = null;
                if (objectId != null) target = getFeatureById(objectId);
                if (!target && houseNo) {
                    target = getParcels().find(f => {
                        const k = f.properties?.kategoria;
                        if (k !== 'budynek' && k !== 'dom') return false;
                        if (String(f.properties?.numer_obiektu || '').trim() !== String(houseNo).trim()) return false;
                        const owners = f.properties?.wlasciciele;
                        if (!Array.isArray(owners) || !owners.length) return true;
                        return owners.some(o => String(o.id) === String(ownerData.id) || o.unikalny_klucz === ownerKey);
                    });
                }
                if (!target) return;

                highlightFeatures([target.id], 'fuchsia');
                const center = featureCenter(target);
                const map = getMap();
                if (center && map) {
                    new maplibregl.Popup({ maxWidth: '320px' })
                        .setLngLat(center)
                        .setHTML(`<div><b>🏠 Dom nr ${escapeHtml(houseNo || '—')}</b><br><span>Właściciel: ${escapeHtml(ownerName || 'nieznany')}</span></div>`)
                        .addTo(map);
                }
            } catch (e) {
                console.warn('showHouseByOwnerKey błąd:', e);
            }
        }

        return Object.freeze({
            handleUrlParameters,
            showHouseByOwnerKey,
        });
    }

    window.MapUrlParameters = Object.freeze({ create });
})();
