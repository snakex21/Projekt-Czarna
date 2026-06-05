/** Układ paneli, modale toolbaru, motyw i skróty klawiaturowe mapy. */
(function () {
    'use strict';

    function create() {
        function setupPanelToggles() {
            const toggleButtons = document.querySelectorAll('.panel-toggle');
            const expandHandles = document.querySelectorAll('.panel-expand-handle');
            const mapWrapper = document.getElementById('map-wrapper');

            const updateMapState = () => {
                const left = document.getElementById('owners-panel');
                const right = document.getElementById('parcels-panel');
                if (!left || !right || !mapWrapper) return;
                const lc = left.classList.contains('collapsed');
                const rc = right.classList.contains('collapsed');
                mapWrapper.classList.remove('full-width', 'expanded-left', 'expanded-right');
                if (lc && rc) mapWrapper.classList.add('full-width');
                else if (lc) mapWrapper.classList.add('expanded-left');
                else if (rc) mapWrapper.classList.add('expanded-right');
                setTimeout(() => window.MapV2.invalidateSize(), 350);
            };

            const isMobile = window.matchMedia('(max-width: 768px)').matches;
            if (isMobile) {
                const left = document.getElementById('owners-panel');
                const right = document.getElementById('parcels-panel');
                const lh = document.querySelector('.panel-expand-handle.left-handle');
                const rh = document.querySelector('.panel-expand-handle.right-handle');
                left?.classList.add('collapsed');
                right?.classList.add('collapsed');
                lh?.classList.add('handle-visible');
                rh?.classList.add('handle-visible');
            }

            toggleButtons.forEach(btn => {
                btn.addEventListener('click', () => {
                    const t = btn.dataset.panel;
                    const panel = document.getElementById(t === 'owners' ? 'owners-panel' : 'parcels-panel');
                    const handle = document.querySelector(`.panel-expand-handle[data-panel="${t}"]`);
                    panel?.classList.add('collapsed');
                    handle?.classList.add('handle-visible');
                    const icon = btn.querySelector('i');
                    if (icon) icon.className = t === 'owners' ? 'fas fa-chevron-right' : 'fas fa-chevron-left';
                    updateMapState();
                });
            });

            expandHandles.forEach(handle => {
                handle.addEventListener('click', () => {
                    const t = handle.dataset.panel;
                    const panel = document.getElementById(t === 'owners' ? 'owners-panel' : 'parcels-panel');
                    panel?.classList.remove('collapsed');
                    handle.classList.remove('handle-visible');
                    const tBtn = panel?.querySelector('.panel-toggle');
                    if (tBtn) {
                        const icon = tBtn.querySelector('i');
                        if (icon) icon.className = t === 'owners' ? 'fas fa-chevron-left' : 'fas fa-chevron-right';
                    }
                    updateMapState();
                });
            });
        }

        function setupToolbarActions() {
            const helpBtn = document.getElementById('help-btn');
            const settingsBtn = document.getElementById('settings-btn');
            const helpModal = document.getElementById('help-modal');
            const settingsModal = document.getElementById('settings-modal');
            const themeToggle = document.getElementById('theme-toggle');
            const resetViewBtn = document.getElementById('reset-view-btn');

            if (helpBtn && helpModal) helpBtn.addEventListener('click', () => helpModal.style.display = 'flex');
            if (settingsBtn && settingsModal) settingsBtn.addEventListener('click', () => settingsModal.style.display = 'flex');

            [helpModal, settingsModal].forEach(modal => {
                if (!modal) return;
                modal.querySelector('.modal-close')?.addEventListener('click', () => modal.style.display = 'none');
                modal.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });
            });

            if (themeToggle) {
                const apply = (theme) => {
                    document.documentElement.classList.toggle('dark-mode', theme === 'dark');
                    document.body.classList.toggle('dark-mode', theme === 'dark');
                    themeToggle.checked = (theme === 'dark');
                };
                apply(localStorage.getItem('mapTheme') || 'light');
                themeToggle.addEventListener('change', () => {
                    const t = themeToggle.checked ? 'dark' : 'light';
                    localStorage.setItem('mapTheme', t);
                    apply(t);
                });
            }

            if (resetViewBtn) {
                resetViewBtn.addEventListener('click', () => {
                    document.getElementById('owners-panel')?.classList.add('collapsed');
                    document.getElementById('parcels-panel')?.classList.add('collapsed');
                    document.querySelector('.panel-expand-handle.left-handle')?.classList.add('handle-visible');
                    document.querySelector('.panel-expand-handle.right-handle')?.classList.add('handle-visible');
                    window.MapV2.clearAllHighlights();
                    // Po zwinięciu paneli mapa zmienia rozmiar — czekamy na transition.
                    setTimeout(() => {
                        window.MapV2.invalidateSize();
                        window.MapV2.fitToAll();
                    }, 380);
                    if (settingsModal) settingsModal.style.display = 'none';
                });
            }

            document.addEventListener('keydown', e => {
                const ae = document.activeElement;
                if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA')) {
                    if (e.key !== 'Escape') return;
                }
                if (e.ctrlKey && e.key === 'f') {
                    e.preventDefault();
                    document.getElementById('universal-search')?.focus();
                }
                if (e.key === '+') { e.preventDefault(); window.MapV2.zoomIn(); }
                if (e.key === '-') { e.preventDefault(); window.MapV2.zoomOut(); }
                if (e.key === 'Escape') {
                    e.preventDefault();
                    if (helpModal && helpModal.style.display === 'flex') helpModal.style.display = 'none';
                    else if (settingsModal && settingsModal.style.display === 'flex') settingsModal.style.display = 'none';
                    else {
                        const cb = document.getElementById('clearHighlightBtn');
                        if (cb && !cb.parentElement.classList.contains('hidden')) cb.click();
                    }
                }
            });
        }

        function setupClearHighlightButton() {
            const btn = document.getElementById('clearHighlightBtn');
            if (btn) btn.addEventListener('click', () => window.MapV2.clearAllHighlights());
        }

        return Object.freeze({
            setupPanelToggles,
            setupToolbarActions,
            setupClearHighlightButton,
        });
    }

    window.PanelLayout = Object.freeze({ create });
})();
