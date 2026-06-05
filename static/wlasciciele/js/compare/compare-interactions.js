/**
 * Interakcje porównywarki protokołów (P2.7 Etap 5E).
 *
 * Moduł obsługuje linki do mapy i eksport PDF kolumn porównania.
 * Korzysta z `window.OwnersAPI`.
 */
(function () {
    'use strict';

    const API = window.OwnersAPI;
    let pdfLibPromise = null;

    function setupHeaderMapLinks(ownerKeys, elements) {
        const config = elements || {};
        const mapUrl = API.mapPage();
        const ownersParam = ownerKeys.join(',');

        if (config.mapLinkReal) {
            config.mapLinkReal.href = `${mapUrl}?${new URLSearchParams({ highlightTopOwners: ownersParam, ownership: 'rzeczywista' })}`;
        }
        if (config.mapLinkProtocol) {
            config.mapLinkProtocol.href = `${mapUrl}?${new URLSearchParams({ highlightTopOwners: ownersParam, ownership: 'protokol' })}`;
        }
        if (config.mapLinkBoth) {
            config.mapLinkBoth.href = `${mapUrl}?${new URLSearchParams({ highlightTopOwners: ownersParam, ownership: 'wszystkie' })}`;
        }
    }

    function bindColumnMapLinks(data, colEl) {
        const mapUrl = API.mapPage();
        const showHouseBtn = colEl.querySelector(`#showHouseOnMapBtn-${data.unikalny_klucz}`);
        if (data.dom_obiekt_id && showHouseBtn) {
            showHouseBtn.classList.remove('hidden');
            showHouseBtn.addEventListener('click', () => {
                const plotIds = (data.dzialki_wszystkie || []).map(p => p.id);
                const allIdsToHighlight = [data.dom_obiekt_id, ...plotIds];
                const uniqueIds = [...new Set(allIdsToHighlight)].join(',');
                const params = new URLSearchParams({ highlightByIds: uniqueIds });
                window.location.href = `${mapUrl}?${params.toString()}`;
            });
        }

        const realIds = (data.dzialki_rzeczywiste || []).map(p => p.id);
        const protocolIds = (data.dzialki_protokol || []).map(p => p.id);
        const allIds = [...new Set([...realIds, ...protocolIds])];

        setMapButton(colEl, `#mapLinkReal-${data.unikalny_klucz}`, realIds, mapUrl);
        setMapButton(colEl, `#mapLinkProtocol-${data.unikalny_klucz}`, protocolIds, mapUrl);
        setMapButton(colEl, `#mapLinkBoth-${data.unikalny_klucz}`, allIds, mapUrl);
    }

    function setMapButton(colEl, selector, ids, mapUrl) {
        const button = colEl.querySelector(selector);
        if (button && ids.length > 0) {
            button.href = `${mapUrl}?${new URLSearchParams({ highlightByIds: ids.join(',') })}`;
            button.classList.remove('hidden');
        }
    }

    function ensureHtml2Pdf() {
        if (typeof html2pdf !== 'undefined') return Promise.resolve();
        if (pdfLibPromise) return pdfLibPromise;
        pdfLibPromise = new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js';
            script.onload = () => resolve();
            script.onerror = () => reject();
            document.head.appendChild(script);
        });
        return pdfLibPromise;
    }

    async function createPDF(columnEl, ownerName = 'protokol', ownerData = null) {
        try {
            await ensureHtml2Pdf();
        } catch {
            return alert('Nie udało się załadować modułu PDF.');
        }

        document.body.classList.add('pdf-export');

        const elementsToHide = columnEl.querySelectorAll(
            '.action-btn, .switch-btn, .details-toggle-btn, .view-switcher'
        );
        const originalDisplays = new Map();
        elementsToHide.forEach(el => originalDisplays.set(el, el.style.display));
        elementsToHide.forEach(el => el.style.display = 'none');

        const allViews = Array.from(columnEl.querySelectorAll('.view-container'));
        const viewStates = allViews.map(el => ({
            el,
            hadHiddenClass: el.classList.contains('hidden'),
            prevDisplay: el.style.display,
        }));

        const isVisible = el => !el.classList.contains('hidden') && getComputedStyle(el).display !== 'none';
        let visibleViews = allViews.filter(isVisible);

        if (ownerData) {
            const real = ownerData.dzialki_rzeczywiste || [];
            const protocol = ownerData.dzialki_protokol || [];
            if (listsEqualById(real, protocol)) {
                const protocolView = columnEl.querySelector(`#view-protokol-${ownerData.unikalny_klucz}`);
                if (protocolView && isVisible(protocolView)) {
                    protocolView.classList.add('hidden');
                    visibleViews = allViews.filter(isVisible);
                }
            }
        }

        const detailsOpened = [];
        visibleViews.forEach(view => {
            view.querySelectorAll('.plot-details-list.hidden').forEach(details => {
                detailsOpened.push(details);
                details.classList.remove('hidden');
            });
        });

        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        if (document.fonts?.ready) {
            try { await document.fonts.ready; } catch (error) { }
        }
        await new Promise(resolve => setTimeout(resolve, 50));

        const options = {
            margin: 10,
            filename: `Protokol_${String(ownerName).replace(/[^\p{L}\p{N}_-]+/gu, '_')}.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: {
                scale: 2,
                useCORS: true,
                backgroundColor: '#ffffff',
                scrollY: 0,
            },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
            pagebreak: {
                mode: ['css', 'avoid-all'],
                avoid: ['.plot-category-block', '.content-card'],
            },
        };

        try {
            await html2pdf().from(columnEl).set(options).save();
        } finally {
            elementsToHide.forEach(el => el.style.display = originalDisplays.get(el) || '');
            detailsOpened.forEach(details => details.classList.add('hidden'));
            viewStates.forEach(state => {
                state.el.style.display = state.prevDisplay;
                state.el.classList.toggle('hidden', state.hadHiddenClass);
            });
            document.body.classList.remove('pdf-export');
        }
    }

    function listsEqualById(left, right) {
        if (left.length !== right.length) return false;
        const leftIds = new Set(left.map(item => item.id));
        for (const item of right) {
            if (!leftIds.has(item.id)) return false;
        }
        return true;
    }

    window.CompareInteractions = Object.freeze({
        setupHeaderMapLinks: setupHeaderMapLinks,
        bindColumnMapLinks: bindColumnMapLinks,
        createPDF: createPDF,
    });
})();
