/** Panel działek i obiektów specjalnych. */
(function () {
    'use strict';

    function create(deps = {}) {
        const rebuildDomCaches = deps.rebuildDomCaches || function () {};

        function setupParcelPanel(allParcelsData) {
            allParcelsData = Array.isArray(allParcelsData) ? allParcelsData : [];
            const searchInput = document.getElementById('parcelSearch');
            const dzialkiContainer = document.getElementById('dzialki_panel');
            const obiektyContainer = document.getElementById('obiekty_panel');
            const tabs = document.querySelectorAll('.tab-btn');
            const categoryFilters = document.getElementById('parcel-category-filters');

            const render = () => {
                if (!dzialkiContainer || !obiektyContainer) return;
                dzialkiContainer.innerHTML = '';
                obiektyContainer.innerHTML = '';

                const term = (searchInput?.value || '').toLowerCase();
                if (term === '') window.MapV2.clearTemporaryHighlight();

                const sorted = [...allParcelsData].sort((a, b) =>
                    safeText(a.properties?.numer_obiektu).localeCompare(
                        safeText(b.properties?.numer_obiektu), 'pl', { numeric: true }));

                const filtered = sorted.filter(p =>
                    safeText(p.properties?.numer_obiektu).toLowerCase().includes(term));

                const activeCats = Array.from(
                    document.querySelectorAll('#parcel-category-filters input:checked')
                ).map(cb => cb.dataset.category);

                filtered.forEach(p => {
                    const k = p.properties?.kategoria;
                    const dzialkiCats = ['budowlana', 'rolna', 'las', 'pastwisko'];
                    const infraCats = ['droga', 'rzeka'];
                    if (!dzialkiCats.includes(k) && !infraCats.includes(k)) return;
                    if (dzialkiCats.includes(k) && !activeCats.includes(k)) return;

                    const item = createParcelItem(p);
                    if (dzialkiCats.includes(k)) dzialkiContainer.appendChild(item);
                    else obiektyContainer.appendChild(item);
                });

                if (term.length > 0) {
                    const exact = sorted.filter(p =>
                        safeText(p.properties?.numer_obiektu).toLowerCase() === term);
                    if (exact.length) {
                        window.MapV2.highlightFeatures(exact.map(p => p.id), 'orange', { temporary: true });
                    }
                }

                const totalEl = document.getElementById('total-parcels');
                if (totalEl) {
                    totalEl.textContent = allParcelsData.filter(p =>
                        p.properties?.kategoria !== 'obrys_miejscowosci').length;
                }

                rebuildDomCaches();
            };

            if (searchInput) {
                searchInput.addEventListener('input', () => {
                    const activeTab = document.querySelector('.tab-btn.active');
                    const tabType = activeTab?.dataset.tab;
                    if (tabType === 'special') {
                        renderSpecialObjects(allParcelsData, searchInput.value);
                        const term = searchInput.value.toLowerCase().trim();
                        if (term.length > 0) {
                            const exact = allParcelsData.filter(p => {
                                const k = p.properties?.kategoria;
                                const isSpec = ['kapliczka', 'budynek', 'obiekt_specjalny'].includes(k);
                                return isSpec && safeText(p.properties?.numer_obiektu).toLowerCase() === term;
                            });
                            if (exact.length) {
                                window.MapV2.highlightFeatures(exact.map(p => p.id), 'orange', { temporary: true });
                            }
                        } else {
                            window.MapV2.clearTemporaryHighlight();
                        }
                    } else {
                        render();
                    }
                });
            }

            tabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    tabs.forEach(t => t.classList.remove('active'));
                    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                    tab.classList.add('active');
                    const tabContent = document.getElementById(tab.dataset.tab + '-tab');
                    if (tabContent) tabContent.classList.add('active');
                    if (categoryFilters) {
                        categoryFilters.style.display = tab.dataset.tab === 'parcels' ? 'flex' : 'none';
                    }
                    if (searchInput) searchInput.value = '';
                    window.MapV2.clearTemporaryHighlight();
                    if (tab.dataset.tab === 'special') {
                        renderSpecialObjects(allParcelsData, '');
                    } else {
                        render();
                    }
                });
            });

            if (categoryFilters) {
                categoryFilters.querySelectorAll('input').forEach(cb =>
                    cb.addEventListener('change', render));
            }

            setupParcelInteractions(dzialkiContainer);
            setupParcelInteractions(obiektyContainer);
            renderSpecialObjects(allParcelsData, '');
            render();
        }

        function createParcelItem(parcel) {
            const item = document.createElement('div');
            item.className = 'parcel-item';
            item.innerHTML = `
                <div class="parcel-info">
                    <span class="parcel-number">${escapeHtml(parcel.properties?.numer_obiektu)}</span>
                    <span class="parcel-category filter-badge ${escapeHtml(parcel.properties?.kategoria)}">
                        ${escapeHtml(parcel.properties?.kategoria)}
                    </span>
                </div>
                <button class="parcel-show-btn" title="Pokaż na mapie">
                    <i class="fas fa-crosshairs"></i>
                </button>`;
            item.dataset.featureId = parcel.id;

            item.querySelector('.parcel-show-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                window.MapV2.focusFeature(parcel.id, { openPopup: true });
            });
            return item;
        }

        function setupParcelInteractions(container) {
            if (!container) return;
            container.addEventListener('mouseover', (e) => {
                const item = e.target.closest('.parcel-item');
                if (item) window.MapV2.setHoverFeature(parseInt(item.dataset.featureId), true);
            });
            container.addEventListener('mouseout', (e) => {
                const item = e.target.closest('.parcel-item');
                if (item) window.MapV2.setHoverFeature(parseInt(item.dataset.featureId), false);
            });
            container.addEventListener('click', (e) => {
                const item = e.target.closest('.parcel-item');
                if (item) window.MapV2.focusFeature(parseInt(item.dataset.featureId), { openPopup: true });
            });
        }

        function renderSpecialObjects(allParcelsData, searchTerm) {
            const specialTab = document.getElementById('special-tab');
            const container = specialTab?.querySelector('.special-objects-list');
            if (!container) return;

            container.innerHTML = '';
            const term = (searchTerm || '').toLowerCase().trim();

            const cats = {
                kapliczka: { icon: '⛪', label: 'Kapliczki', items: [] },
                budynek: { icon: '🏠', label: 'Domy', items: [] },
                obiekt_specjalny: { icon: '⭐', label: 'Obiekty specjalne', items: [] },
            };

            allParcelsData.forEach(f => {
                const k = f.properties?.kategoria;
                if (!cats[k]) return;
                const numer = safeText(f.properties?.numer_obiektu).toLowerCase();
                const wlas = (f.properties?.wlasciciele || []).map(w => safeText(w.nazwa).toLowerCase()).join(' ');
                if (term === '' || numer.includes(term) || wlas.includes(term)) {
                    cats[k].items.push(f);
                }
            });

            Object.values(cats).forEach(cat => {
                if (!cat.items.length) return;
                container.appendChild(createSpecialCategorySection(cat));
            });

            const total = Object.values(cats).reduce((s, c) => s + c.items.length, 0);
            if (total === 0 && term !== '') {
                container.innerHTML = `
                <div style="text-align:center;padding:20px;color:var(--text-secondary);">
                    <i class="fas fa-search" style="font-size:2rem;margin-bottom:10px;"></i>
                    <p>Nie znaleziono obiektów dla: "${escapeHtml(searchTerm)}"</p>
                </div>`;
            }
        }

        function createSpecialCategorySection(category) {
            const section = document.createElement('div');
            section.className = 'special-category-section';
            section.innerHTML = `
            <h4 class="special-category-header">
                <span>${category.icon}</span>
                <span>${category.label} (${category.items.length})</span>
            </h4>
            <div class="special-items-list"></div>`;
            const list = section.querySelector('.special-items-list');

            category.items.sort((a, b) => {
                const na = parseInt(a.properties?.numer_obiektu) || 0;
                const nb = parseInt(b.properties?.numer_obiektu) || 0;
                return na - nb;
            });

            category.items.forEach(item => list.appendChild(createSpecialObjectItem(item, category.icon)));
            return section;
        }

        function createSpecialObjectItem(item, icon) {
            const el = document.createElement('div');
            el.className = 'special-item';
            el.dataset.featureId = item.id;

            const owners = item.properties?.wlasciciele || [];
            const ownerNames = owners.map(o => o.nazwa).join(', ') || 'Brak właściciela';

            el.innerHTML = `
            <div class="special-item-content">
                <div class="special-item-header">
                    <span class="special-item-icon">${icon}</span>
                    <span class="special-item-number">${escapeHtml(item.properties?.numer_obiektu || 'Bez numeru')}</span>
                </div>
                <div class="special-item-owners">${escapeHtml(ownerNames)}</div>
            </div>
            <button class="special-show-btn" title="Pokaż na mapie">
                <i class="fas fa-crosshairs"></i>
            </button>`;

            el.querySelector('.special-show-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                window.MapV2.focusFeature(item.id, { openPopup: true });
            });

            el.addEventListener('click', () => {
                if (owners.length === 0) {
                    alert('Ten obiekt nie ma przypisanego właściciela.');
                    return;
                }
                if (owners.length === 1) {
                    const key = owners[0].unikalny_klucz;
                    if (key) window.location.href = `../wlasciciele/protokol.html?ownerId=${key}`;
                    else alert('Brak klucza właściciela dla tego obiektu.');
                } else {
                    window.MapV2.showOwnerSelectionPopup(owners, item.id);
                }
            });

            el.addEventListener('mouseenter', () => window.MapV2.setHoverFeature(item.id, true));
            el.addEventListener('mouseleave', () => window.MapV2.setHoverFeature(item.id, false));
            return el;
        }

        return Object.freeze({
            setupParcelPanel,
            createParcelItem,
            renderSpecialObjects,
        });
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

    window.PanelParcels = Object.freeze({ create });
})();
