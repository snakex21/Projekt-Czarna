/* ==========================================================================
   Plik: panels.js
   Opis: Orkiestrator paneli właścicieli i działek dla MapLibre.
         Komunikuje się z mapą wyłącznie przez globalne API w window.MapV2.
   ========================================================================== */

(function () {
    'use strict';

    const panelLegend = window.PanelLegend.create();
    const panelLayout = window.PanelLayout.create();
    const panelOwners = window.PanelOwners.create({ rebuildDomCaches });
    const panelParcels = window.PanelParcels.create({ rebuildDomCaches });
    const panelSearch = window.PanelSearch.create();

    // Cache DOM dla synchronizacji hover mapa↔panele.
    const parcelButtonsByFeatureId = new Map();
    const ownerCardsByKey = new Map();

    window.PanelsV2 = {
        init,
        rebuildDomCaches,
        highlightOwnerByFeatureHover,
        clearHoverHighlights,
        scrollToParcelButton,
    };

    function init({ owners, parcels }) {
        window.__owners = owners;
        window.__parcels = parcels;

        panelOwners.setupOwnerPanel(owners);
        panelParcels.setupParcelPanel(parcels);
        panelLegend.setupLegend();
        panelLayout.setupPanelToggles();
        panelLayout.setupToolbarActions();
        panelSearch.setupUniversalSearch(owners, parcels);
        panelSearch.setupMobileSearch(owners, parcels);
        panelLayout.setupClearHighlightButton();

        rebuildDomCaches();
        setTimeout(rebuildDomCaches, 600);
    }

    function rebuildDomCaches() {
        parcelButtonsByFeatureId.clear();
        ownerCardsByKey.clear();
        document.querySelectorAll('.parcel-item[data-feature-id]').forEach(el => {
            const id = el.dataset.featureId;
            if (id) parcelButtonsByFeatureId.set(id, el);
        });
        document.querySelectorAll('.special-item[data-feature-id]').forEach(el => {
            const id = el.dataset.featureId;
            if (id) parcelButtonsByFeatureId.set(id, el);
        });
        document.querySelectorAll('.owner-card[data-owner-key]').forEach(el => {
            const k = el.dataset.ownerKey;
            if (k) ownerCardsByKey.set(k, el);
        });
    }

    /**
     * Wywoływane przez mapę gdy hover nad działką → podświetla kartę właściciela i pozycję działki w panelu.
     */
    function highlightOwnerByFeatureHover(featureId, wlasciciele) {
        const btn = parcelButtonsByFeatureId.get(String(featureId));
        if (btn) {
            btn.classList.add('highlighted-by-map');
            checkElementVisibility(btn);
        }
        if (Array.isArray(wlasciciele)) {
            for (const w of wlasciciele) {
                const card = ownerCardsByKey.get(w.unikalny_klucz);
                if (card) card.classList.add('highlighted-by-map');
            }
        }
    }

    function clearHoverHighlights() {
        parcelButtonsByFeatureId.forEach(btn => {
            if (btn.classList.contains('highlighted-by-map')) {
                btn.classList.remove('highlighted-by-map');
                btn.closest('.tab-content-right')?.classList.remove('highlight-indicator-top', 'highlight-indicator-bottom');
            }
        });
        ownerCardsByKey.forEach(card => card.classList.remove('highlighted-by-map'));
    }

    function scrollToParcelButton(featureId) {
        const btn = parcelButtonsByFeatureId.get(String(featureId));
        if (btn) checkElementVisibility(btn);
    }

    function checkElementVisibility(element) {
        const container = element.closest('.tab-content-right');
        if (!container) return;
        container.classList.remove('highlight-indicator-top', 'highlight-indicator-bottom');
        const cr = container.getBoundingClientRect();
        const er = element.getBoundingClientRect();
        const fully = er.top >= cr.top && er.bottom <= cr.bottom;
        if (!fully) {
            if (er.top < cr.top) container.classList.add('highlight-indicator-top');
            else if (er.bottom > cr.bottom) container.classList.add('highlight-indicator-bottom');
        }
    }
})();
