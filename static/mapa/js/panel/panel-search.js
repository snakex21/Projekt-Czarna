/** Wyszukiwarka desktop/mobile dla publicznej mapy. */
(function () {
    'use strict';

    function create() {
        function performSearch(term, allOwnersData, allParcelsData) {
            allOwnersData = Array.isArray(allOwnersData) ? allOwnersData : [];
            allParcelsData = Array.isArray(allParcelsData) ? allParcelsData : [];
            const ownerR = allOwnersData
                .filter(o => safeText(o.nazwa_wlasciciela).toLowerCase().includes(term) ||
                    String(o.numer_protokolu).includes(term))
                .map(o => ({ id: o.unikalny_klucz, name: o.nazwa_wlasciciela, lp: o.numer_protokolu, type: 'owner' }));
            const parcelR = allParcelsData
                .filter(p => safeText(p.properties?.numer_obiektu).toLowerCase().includes(term))
                .map(p => ({ id: p.id, number: p.properties?.numer_obiektu, category: p.properties?.kategoria, type: 'parcel' }));
            return [...ownerR, ...parcelR].slice(0, 10);
        }

        function createSearchResultItem(item) {
            const el = document.createElement('div');
            el.className = 'search-result-item';
            el.dataset.id = item.id;
            el.dataset.type = item.type;
            let iconHtml = '', text, meta;
            if (item.type === 'owner') {
                text = item.name;
                meta = `Właściciel (Lp. ${item.lp})`;
            } else {
                iconHtml = '<i class="result-icon fas fa-map-marker-alt"></i>';
                text = `Działka nr ${item.number}`;
                meta = item.category;
            }
            el.innerHTML = `${iconHtml}<span class="result-text">${escapeHtml(text)}</span><span class="result-meta">${escapeHtml(meta || '')}</span>`;
            return el;
        }

        function setupUniversalSearch(allOwnersData, allParcelsData) {
            const input = document.getElementById('universal-search');
            const results = document.getElementById('universal-search-results');
            if (!input || !results) return;

            const debounced = debounce(() => {
                const term = input.value.toLowerCase().trim();
                if (term.length < 2) { results.style.display = 'none'; return; }
                const data = performSearch(term, allOwnersData, allParcelsData);
                results.innerHTML = '';
                if (!data.length) { results.style.display = 'none'; return; }
                data.forEach(item => results.appendChild(createSearchResultItem(item)));
                results.style.display = 'block';
            }, 300);
            input.addEventListener('input', debounced);

            results.addEventListener('click', e => {
                const item = e.target.closest('.search-result-item');
                if (!item) return;
                const { id, type } = item.dataset;
                if (type === 'owner') {
                    handleOwnerSearchResult(id);
                } else {
                    window.MapV2.focusFeature(parseInt(id), { openPopup: true });
                }
                input.value = '';
                results.style.display = 'none';
            });
            document.addEventListener('click', e => {
                if (!results.contains(e.target) && e.target !== input) results.style.display = 'none';
            });
        }

        function setupMobileSearch(allOwnersData, allParcelsData) {
            const trigger = document.getElementById('mobile-search-trigger');
            const overlay = document.getElementById('mobile-search-overlay');
            const closeBtn = document.getElementById('close-mobile-search');
            const input = document.getElementById('mobile-universal-search');
            const results = document.getElementById('mobile-search-results');
            if (!trigger || !overlay || !closeBtn || !input || !results) return;

            const placeholder = `<div class="search-placeholder"><i class="fas fa-search"></i><p>Wpisz co najmniej 2 znaki, aby wyszukać</p></div>`;
            const open = () => { overlay.classList.add('active'); setTimeout(() => input.focus(), 100); };
            const close = () => { overlay.classList.remove('active'); input.value = ''; results.innerHTML = placeholder; };

            trigger.addEventListener('click', e => { e.preventDefault(); open(); });
            closeBtn.addEventListener('click', close);

            input.addEventListener('input', debounce(() => {
                const term = input.value.toLowerCase().trim();
                if (term.length < 2) { results.innerHTML = placeholder; return; }
                const data = performSearch(term, allOwnersData, allParcelsData);
                results.innerHTML = '';
                if (!data.length) {
                    results.innerHTML = `<div class="search-placeholder"><i class="fas fa-frown"></i><p>Nie znaleziono wyników dla "${escapeHtml(term)}"</p></div>`;
                    return;
                }
                data.forEach(item => results.appendChild(createSearchResultItem(item)));
            }, 300));

            results.addEventListener('click', e => {
                const item = e.target.closest('.search-result-item');
                if (!item) return;
                const { id, type } = item.dataset;
                if (type === 'owner') {
                    handleOwnerSearchResult(id);
                    const panel = document.getElementById('owners-panel');
                    if (panel?.classList.contains('collapsed')) {
                        document.querySelector('.panel-expand-handle.left-handle')?.click();
                    }
                } else {
                    window.MapV2.focusFeature(parseInt(id), { openPopup: true });
                }
                close();
            });
        }

        function handleOwnerSearchResult(ownerKey) {
            const card = document.querySelector(`.owner-card[data-owner-key="${ownerKey}"]`);
            if (card) {
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                card.style.transition = 'all 0.2s ease';
                card.style.transform = 'scale(1.05)';
                setTimeout(() => card.style.transform = 'scale(1)', 1000);
            }
        }

        return Object.freeze({
            setupUniversalSearch,
            setupMobileSearch,
            performSearch,
            createSearchResultItem,
        });
    }

    function debounce(fn, wait) {
        let t;
        return function (...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), wait);
        };
    }

    function safeText(value) {
        return String(value ?? '');
    }

    function escapeHtml(s) {
        return String(s ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    window.PanelSearch = Object.freeze({ create });
})();
