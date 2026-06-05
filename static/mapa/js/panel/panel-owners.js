/** Panel właścicieli: lista, sortowanie, wyszukiwanie i tryb porównania. */
(function () {
    'use strict';

    function create(deps = {}) {
        const rebuildDomCaches = deps.rebuildDomCaches || function () {};
        let isInCompareMode = false;
        let selectedForCompare = [];

        function setupOwnerPanel(allOwnersData) {
            allOwnersData = Array.isArray(allOwnersData) ? allOwnersData : [];
            allOwnersData = allOwnersData.filter(owner => {
                const hasName = safeText(owner?.nazwa_wlasciciela).trim().length > 0;
                const hasParcels = (owner?.dzialki_rzeczywiste?.length || 0) > 0 || (owner?.dzialki_protokol?.length || 0) > 0;
                return hasName || hasParcels;
            });
            const ownerContainer = document.getElementById('ownersList');
            const searchInput = document.getElementById('ownerSearch');
            const compareBtn = document.getElementById('compareModeBtn');
            if (!ownerContainer) return;

            let currentSort = 'byOrder';

            const render = (owners) => {
                const visibleCountEl = document.getElementById('visible-count');
                if (visibleCountEl) visibleCountEl.textContent = owners.length;
                ownerContainer.innerHTML = '';
                owners.forEach(o => ownerContainer.appendChild(createOwnerCard(o, ownerContainer)));
                rebuildDomCaches();
            };

            const sortAndFilter = () => {
                let data = [...allOwnersData];
                if (currentSort === 'byName') {
                    data.sort((a, b) => safeText(a.nazwa_wlasciciela).localeCompare(safeText(b.nazwa_wlasciciela), 'pl'));
                } else if (currentSort === 'byParcels') {
                    data.sort((a, b) => (b.dzialki_rzeczywiste?.length || 0) - (a.dzialki_rzeczywiste?.length || 0));
                } else {
                    data.sort((a, b) => (a.numer_protokolu || 9999) - (b.numer_protokolu || 9999));
                }
                const term = (searchInput?.value || '').toLowerCase();
                const filtered = data.filter(o => {
                    const name = safeText(o.nazwa_wlasciciela).toLowerCase();
                    const lp = o.numer_protokolu ? String(o.numer_protokolu) : '';
                    return name.includes(term) || lp.includes(term);
                });
                render(filtered);
            };

            if (compareBtn) {
                compareBtn.addEventListener('click', () => {
                    isInCompareMode = !isInCompareMode;
                    compareBtn.classList.toggle('active', isInCompareMode);
                    const compareInfo = document.querySelector('.compare-info');
                    if (compareInfo) compareInfo.style.display = isInCompareMode ? 'block' : 'none';
                    if (!isInCompareMode) {
                        selectedForCompare = [];
                        ownerContainer.querySelectorAll('.selected-for-compare')
                            .forEach(el => el.classList.remove('selected-for-compare'));
                    }
                });
            }

            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    const t = btn.dataset.sort;
                    currentSort = t === 'name' ? 'byName' : t === 'parcels' ? 'byParcels' : 'byOrder';
                    sortAndFilter();
                });
            });

            if (searchInput) {
                searchInput.addEventListener('input', sortAndFilter);
                const clearBtn = searchInput.parentElement.querySelector('.clear-search');
                if (clearBtn) {
                    searchInput.addEventListener('input', () => {
                        clearBtn.style.display = searchInput.value ? 'block' : 'none';
                    });
                    clearBtn.addEventListener('click', () => {
                        searchInput.value = '';
                        clearBtn.style.display = 'none';
                        sortAndFilter();
                    });
                }
            }

            sortAndFilter();

            const totalEl = document.getElementById('total-owners');
            if (totalEl) totalEl.textContent = allOwnersData.length;
        }

        function createOwnerCard(owner, ownerContainer) {
            const card = document.createElement('div');
            card.className = 'owner-card';
            card.dataset.ownerKey = owner.unikalny_klucz || '';

            card.innerHTML = `
                <div class="owner-info">
                    <div class="owner-details">
                        <div class="owner-name">${escapeHtml(safeText(owner.nazwa_wlasciciela).trim() || 'Nieznany właściciel')}</div>
                        <div class="owner-meta">
                            <span><i class="fas fa-hashtag"></i> ${owner.numer_protokolu || 'N/A'}</span>
                            <span><i class="fas fa-map"></i> ${(owner.dzialki_rzeczywiste || []).length} działek</span>
                        </div>
                    </div>
                    <div class="owner-actions">
                        <button class="action-btn" data-type="rzeczywiste" title="Pokaż działki rzeczywiste">
                            <i class="fas fa-map-marked-alt"></i>
                        </button>
                        <button class="action-btn" data-type="protokol" title="Pokaż działki wg protokołu" style="display: none;">
                            <i class="fas fa-file-alt"></i>
                        </button>
                        <button class="action-btn switch-btn" title="Zmień widok działek">
                            <i class="fas fa-exchange-alt"></i>
                        </button>
                    </div>
                </div>`;

            setupOwnerCardEvents(card, owner, ownerContainer);
            return card;
        }

        function setupOwnerCardEvents(card, owner, ownerContainer) {
            card.querySelector('.owner-details').onclick = () => handleOwnerClick(owner.unikalny_klucz, ownerContainer);

            const btnRzecz = card.querySelector('.action-btn[data-type="rzeczywiste"]');
            const btnProt = card.querySelector('.action-btn[data-type="protokol"]');
            const btnSwitch = card.querySelector('.switch-btn');

            const maRzecz = owner.dzialki_rzeczywiste?.length > 0;
            const maProt = owner.dzialki_protokol?.length > 0;

            if (maRzecz) {
                btnRzecz.onclick = (e) => {
                    e.stopPropagation();
                    const ids = owner.dzialki_rzeczywiste.map(p => p.id);
                    window.MapV2.highlightFeatures(ids, 'fuchsia', {
                        ownerName: owner.nazwa_wlasciciela,
                        ownershipType: 'Rzeczywiste',
                        ownerLp: owner.numer_protokolu,
                        isProtocol: false,
                    });
                };
            } else {
                btnRzecz.style.display = 'none';
            }

            if (maProt) {
                btnProt.onclick = (e) => {
                    e.stopPropagation();
                    const ids = owner.dzialki_protokol.map(p => p.id);
                    window.MapV2.highlightFeatures(ids, 'fuchsia', {
                        ownerName: owner.nazwa_wlasciciela,
                        ownershipType: 'Wg Protokołu',
                        ownerLp: owner.numer_protokolu,
                        isProtocol: true,
                    });
                };
            } else {
                btnProt.style.display = 'none';
            }

            if (maRzecz && maProt) {
                btnSwitch.style.display = 'inline-flex';
                btnSwitch.onclick = (e) => {
                    e.stopPropagation();
                    const isRz = btnRzecz.style.display !== 'none';
                    btnRzecz.style.display = isRz ? 'none' : 'inline-flex';
                    btnProt.style.display = isRz ? 'inline-flex' : 'none';
                };
            } else {
                btnSwitch.style.display = 'none';
            }

            card.onmouseover = () => {
                const ids = collectOwnerParcelIds(owner);
                if (ids.length) window.MapV2.setOwnerHoverHighlight(ids, true);
            };
            card.onmouseout = () => window.MapV2.setOwnerHoverHighlight(null, false);
        }

        function collectOwnerParcelIds(owner) {
            const ids = new Set();
            (owner.dzialki_rzeczywiste || []).forEach(p => p.id != null && ids.add(p.id));
            (owner.dzialki_protokol || []).forEach(p => p.id != null && ids.add(p.id));
            return [...ids];
        }

        function handleOwnerClick(ownerKey, ownerContainer) {
            if (!isInCompareMode) {
                window.location.href = `../wlasciciele/protokol.html?ownerId=${ownerKey}`;
            } else {
                handleCompareMode(ownerKey, ownerContainer);
            }
        }

        function handleCompareMode(ownerKey, ownerContainer) {
            const card = ownerContainer.querySelector(`[data-owner-key="${ownerKey}"]`);
            if (!card) return;
            if (selectedForCompare.includes(ownerKey)) {
                selectedForCompare = selectedForCompare.filter(k => k !== ownerKey);
                card.classList.remove('selected-for-compare');
            } else if (selectedForCompare.length < 2) {
                selectedForCompare.push(ownerKey);
                card.classList.add('selected-for-compare');
            }
            if (selectedForCompare.length === 2) {
                window.location.href = `../wlasciciele/compare.html?owners=${selectedForCompare.join(',')}`;
            }
        }

        return Object.freeze({
            setupOwnerPanel,
            createOwnerCard,
            setupOwnerCardEvents,
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

    window.PanelOwners = Object.freeze({ create });
})();
