/** Legenda warstw i kategorii dla publicznej mapy. */
(function () {
    'use strict';

    function create() {
        const legendVisibilityByCategory = {};

        function setupLegend() {
            const legendEl = document.getElementById('legend');
            if (!legendEl) return;
            const container = legendEl.querySelector('ul');
            const header = legendEl.querySelector('.legend-header');
            const content = legendEl.querySelector('.legend-content');
            const toggle = legendEl.querySelector('.legend-toggle');
            if (!container || !header || !content || !toggle) return;

            header.addEventListener('click', () => {
                legendEl.classList.toggle('collapsed');
                const collapsed = legendEl.classList.contains('collapsed');
                toggle.querySelector('i').className = collapsed ? 'fas fa-chevron-up' : 'fas fa-chevron-down';
            });

            const STYLES = {
                budowlana: { color: '#e67e22' },
                rolna: { color: '#27ae60' },
                las: { fillColor: '#1abc9c' },
                droga: { color: '#8B4513' },
                rzeka: { color: '#3498db' },
                budynek: { color: '#e67e22' },
                kapliczka: { color: '#9b59b6' },
                pastwisko: { fillColor: '#f1c40f' },
                obrys_miejscowosci: { color: '#ff0000' },
                obiekt_specjalny: { color: '#2c3e50' },
            };
            const items = {
                budowlana: 'Działka Budowlana',
                rolna: 'Działka Rolna',
                las: 'Las',
                pastwisko: 'Pastwisko',
                droga: 'Droga',
                rzeka: 'Rzeka',
                budynek: 'Budynek',
                kapliczka: 'Kapliczka',
                obrys_miejscowosci: 'Obrys Miejscowości',
                obiekt_specjalny: 'Obiekt Specjalny',
            };

            container.innerHTML = '';
            container.appendChild(createBaseLayerControls());
            container.appendChild(createMapLayerControls());
            Object.entries(items).forEach(([k, label]) => {
                container.appendChild(createLegendItem(k, label, STYLES[k]));
            });
        }

        function createBaseLayerControls() {
            const wrap = document.createElement('li');
            wrap.className = 'legend-section legend-base-controls';
            wrap.innerHTML = `
            <div class="legend-section-title"><i class="fas fa-map"></i> Podkład</div>
            <label class="legend-radio-row"><input type="radio" name="base-map" value="satellite" checked> Satelita</label>
            <label class="legend-radio-row"><input type="radio" name="base-map" value="osm"> Mapa drogowa</label>
            <label class="legend-radio-row"><input type="radio" name="base-map" value="none"> Tylko działki</label>
            <hr class="legend-separator-inline">`;
            wrap.querySelectorAll('input[name="base-map"]').forEach(r => {
                r.addEventListener('change', () => {
                    if (r.checked) window.MapV2.setBaseLayer(r.value);
                });
            });
            return wrap;
        }

        function createMapLayerControls() {
            const wrap = document.createElement('li');
            wrap.className = 'legend-section legend-overlay-controls';
            wrap.innerHTML = `
            <div class="legend-section-title"><i class="fas fa-layer-group"></i> Widoczność</div>
            <label class="legend-checkbox-row"><input type="checkbox" data-group="historical" checked> Mapa historyczna</label>
            <label class="legend-checkbox-row"><input type="checkbox" data-group="parcels" checked> Granice działek i obiekty</label>
            <label class="legend-checkbox-row"><input type="checkbox" data-group="labels" checked> Numery działek/domów</label>
            <label class="legend-checkbox-row"><input type="checkbox" data-group="points" checked> Domy, kapliczki i klastry</label>
            <label class="legend-checkbox-row"><input type="checkbox" data-group="historical-points" checked> Punkty historyczne (dworzec, dróżnica…)</label>
            <div class="legend-opacity-row">
                <div class="legend-opacity-head"><i class="fas fa-adjust"></i> Przezroczystość mapy XIX w.</div>
                <input type="range" min="0" max="100" value="100" class="opacity-slider legend-opacity-slider" id="opacitySlider">
                <div class="legend-opacity-value"><span id="opacityPercentage">100</span>%</div>
            </div>
            <hr class="legend-separator-inline">`;
            wrap.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                cb.addEventListener('change', () => {
                    window.MapV2.setMapLayerVisibility(cb.dataset.group, cb.checked);
                });
            });
            const opacity = wrap.querySelector('#opacitySlider');
            const percentage = wrap.querySelector('#opacityPercentage');
            opacity?.addEventListener('input', () => {
                const value = Number(opacity.value);
                if (percentage) percentage.textContent = value;
                window.MapV2.setHistoricalOpacity(value / 100);
            });
            return wrap;
        }

        function createLegendItem(kategoria, label, style) {
            const li = document.createElement('li');
            li.dataset.kategoria = kategoria;
            li.className = 'legend-item';

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = true;
            cb.className = 'legend-checkbox';
            cb.id = `legend-${kategoria}`;
            legendVisibilityByCategory[kategoria] = true;

            const colorBox = document.createElement('span');
            colorBox.className = 'legend-color-box';
            colorBox.style.backgroundColor = style?.fillColor || style?.color || '#ccc';

            const lbl = document.createElement('label');
            lbl.htmlFor = `legend-${kategoria}`;
            lbl.className = 'legend-label';
            lbl.textContent = label;

            li.appendChild(cb);
            li.appendChild(colorBox);
            li.appendChild(lbl);

            cb.addEventListener('change', () => {
                legendVisibilityByCategory[kategoria] = cb.checked;
                li.classList.toggle('inactive', !cb.checked);
                window.MapV2.setCategoryVisibility(kategoria, cb.checked);
            });
            return li;
        }

        return Object.freeze({
            setupLegend,
            createBaseLayerControls,
            createMapLayerControls,
            createLegendItem,
        });
    }

    window.PanelLegend = Object.freeze({ create });
})();
