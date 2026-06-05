/** Popupy działek i wyboru protokołu właściciela. */
(function () {
    'use strict';

    function create(deps) {
        const getMap = deps.getMap;
        const getOwners = deps.getOwners;
        const uniqueOwners = deps.uniqueOwners;
        const parseMaybeJson = deps.parseMaybeJson;
        const escapeHtml = deps.escapeHtml;

        function handleObjectClick(feature, lngLat) {
            const map = getMap();
            if (!map) return;
            const props = feature.properties || {};
            const owners = uniqueOwners(parseMaybeJson(props.wlasciciele));
            const html = buildFeaturePopupHtml(props, owners);
            new maplibregl.Popup({ maxWidth: '340px', closeButton: true })
                .setLngLat(lngLat)
                .setHTML(html)
                .addTo(map);
        }

        function showOwnerSelectionPopup(wlasciciele, lngLat) {
            const map = getMap();
            if (!map) return;
            const allOwnersData = getOwners();
            let html = '<h3>Ta działka ma wielu właścicieli.<br>Wybierz protokół:</h3><ul>';
            for (const w of wlasciciele) {
                const owner = allOwnersData.find(o => o.id === w.id || o.unikalny_klucz === w.unikalny_klucz);
                const lp = owner ? owner.numer_protokolu : 'N/A';
                html += `<li><a href="#" class="protocol-link-in-popup" data-key="${escapeHtml(w.unikalny_klucz || '')}">${escapeHtml(w.nazwa)} (Lp. ${escapeHtml(String(lp))})</a></li>`;
            }
            html += '</ul>';
            const popup = new maplibregl.Popup({ maxWidth: '320px' }).setLngLat(lngLat).setHTML(html).addTo(map);
            setTimeout(() => {
                popup.getElement()?.querySelectorAll('.protocol-link-in-popup').forEach(link => {
                    link.addEventListener('click', e => {
                        e.preventDefault();
                        const k = link.getAttribute('data-key');
                        popup.remove();
                        if (k) window.location.href = `../wlasciciele/protokol.html?ownerId=${encodeURIComponent(k)}`;
                    });
                });
            }, 0);
        }

        function buildFeaturePopupHtml(props, wlasciciele) {
            const allOwnersData = getOwners();
            const kat = (props.kategoria || '').replace(/_/g, ' ');
            const numer = props.numer_obiektu || '—';
            let html = `<div class="map-popup">
        <div class="map-popup-title">${escapeHtml(numer)}</div>
        <div class="map-popup-meta"><b>Typ:</b> ${escapeHtml(kat)}</div>`;

            if (wlasciciele.length === 1) {
                const w = wlasciciele[0];
                const url = `../wlasciciele/protokol.html?ownerId=${encodeURIComponent(w.unikalny_klucz || '')}`;
                html += `<div class="map-popup-owners"><b>Właściciel:</b> ${escapeHtml(w.nazwa)}</div>
            <a class="map-popup-btn" href="${url}"><i class="fas fa-file-alt"></i> Otwórz protokół</a>`;
            } else if (wlasciciele.length > 1) {
                html += `<div class="map-popup-owners"><b>Właściciele (${wlasciciele.length}):</b></div>
            <ul class="map-popup-list">`;
                for (const w of wlasciciele) {
                    const url = `../wlasciciele/protokol.html?ownerId=${encodeURIComponent(w.unikalny_klucz || '')}`;
                    const owner = allOwnersData.find(o => o.unikalny_klucz === w.unikalny_klucz || o.id === w.id);
                    const lp = owner?.numer_protokolu;
                    html += `<li><a href="${url}">${escapeHtml(w.nazwa)}${lp ? ` <span class="map-popup-lp">Lp. ${escapeHtml(String(lp))}</span>` : ''}</a></li>`;
                }
                html += `</ul>`;
            }

            html += `</div>`;
            return html;
        }

        return Object.freeze({
            handleObjectClick,
            showOwnerSelectionPopup,
            buildFeaturePopupHtml,
        });
    }

    window.MapPopups = Object.freeze({ create });
})();
