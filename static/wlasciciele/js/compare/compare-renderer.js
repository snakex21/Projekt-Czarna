/**
 * Renderer kolumn porównania protokołów (P2.7 Etap 5D).
 *
 * Moduł buduje HTML kolumny, wypełnia sekcje działek i wyrównuje wysokości kart.
 * Korzysta z `window.OwnersUtils`.
 */
(function () {
    'use strict';

    const UTILS = window.OwnersUtils;
    const generateFractionHTML = UTILS.generateFractionHTML;

    function columnTemplate(d) {
        const uid = d.unikalny_klucz;
        const genealogyButtonHTML = d.ma_drzewo_genealogiczne
            ? `<button id="showTreeBtn-${uid}" class="action-btn tree-btn">
                <i class="fas fa-project-diagram"></i> Drzewo genealogiczne
               </button>`
            : '';

        return `
            <div class="protocol-header-card">
                <div class="protocol-number-badge">L.p. ${d.numer_protokolu || '—'}</div>
                <h2 class="protocol-main-title">
                    Protokół dochodzeń miejscowych
                    <span class="protocol-location">${d.gmina_katastralna ? `w gminie katastralnej ${d.gmina_katastralna}` : ''}</span>
                </h2>
                <div class="protocol-actions">
                    <button id="downloadPdfBtn-${uid}" class="action-btn"><i class="fas fa-file-pdf"></i> Pobierz PDF</button>
                    ${genealogyButtonHTML}
                    <button id="showOriginalBtn-${uid}" class="action-btn"><i class="fas fa-images"></i> Oryginał</button>
                </div>
            </div>

            <div class="content-card owner-card-section">
                <div class="card-header"><h3><i class="fas fa-user"></i> Dane Właściciela</h3></div>
                <div class="card-body">
                    <div class="owner-info"><div>
                        <div class="owner-name-main">${d.nazwa_wlasciciela || ''}</div>
                        ${d.numer_domu ? `<div class="owner-secondary-info">Dom: <span class="owner-details-value">${generateFractionHTML(d.numer_domu)}</span></div>` : ''}
                    </div></div>
                    <button id="showHouseOnMapBtn-${uid}" class="action-btn map-btn hidden"><i class="fas fa-home"></i> Pokaż dom na mapie</button>
                </div>
            </div>

            ${d.genealogia ? `
            <div class="content-card genealogy-section">
                <div class="card-header"><h3><i class="fas fa-sitemap"></i> Genealogia</h3></div>
                <div class="card-body"><div class="info-content">${d.genealogia}</div></div>
            </div>` : ''}

            <div class="view-switcher" data-target-id="${uid}">
                <button class="switch-btn active" data-view="rzeczywiste"><i class="fas fa-check-circle"></i> Stan Rzeczywisty</button>
                <button class="switch-btn" data-view="protokol"><i class="fas fa-file-alt"></i> Stan wg Protokołu</button>
            </div>

            ${plotSectionTemplate('rzeczywiste', uid, 'Działki Rzeczywiste', false)}
            ${plotSectionTemplate('protokol', uid, 'Działki wg Protokołu', true)}

            <div class="content-card map-links-section">
                <div class="card-header"><h3><i class="fas fa-map-marked-alt"></i> Wizualizacja na mapie</h3></div>
                <div class="card-body"><div class="map-buttons-container">
                    <a href="#" id="mapLinkReal-${uid}" class="action-btn map-view-btn hidden"><i class="fas fa-check-circle"></i> Pokaż stan rzeczywisty</a>
                    <a href="#" id="mapLinkProtocol-${uid}" class="action-btn map-view-btn protocol-btn hidden"><i class="fas fa-file-alt"></i> Pokaż stan wg protokołu</a>
                    <a href="#" id="mapLinkBoth-${uid}" class="action-btn map-view-btn both-btn hidden"><i class="fas fa-layer-group"></i> Pokaż oba stany</a>
                </div></div>
            </div>

            <div class="content-card protocol-content-section">
                <div class="card-header"><h3><i class="fas fa-scroll"></i> Treść protokołu</h3></div>
                <div class="card-body"><div class="info-content">${generateFractionHTML(d.pelna_historia || '')}</div></div>
            </div>

            ${optionalSection(uid, 'wspolwlasnoscSection', d.wspolwlasnosc, 'fa-users', 'Współwłasność / Służebność')}
            ${optionalSection(uid, 'powiazaniaTransakcjeSection', d.powiazania_i_transakcje_html, 'fa-exchange-alt', 'Powiązania i transakcje')}
            ${optionalSection(uid, 'interpretacjaWnioskiSection', d.interpretacja_i_wnioski, 'fa-lightbulb', 'Interpretacja i wnioski')}
        `;
    }

    function plotSectionTemplate(type, uid, title, hidden) {
        return `
            <div id="view-${type}-${uid}" class="view-container${hidden ? ' hidden' : ''}">
                <div class="content-card plots-section">
                    <div class="card-header">
                        <h3><i class="fas fa-layer-group"></i> ${title}</h3>
                        <button class="details-toggle-btn" data-target="${type}-details-${uid}"><i class="fas fa-chevron-down"></i></button>
                    </div>
                    <div class="card-body">
                        <div class="plots-summary"><div class="plot-numbers"></div><div class="plot-summary"></div></div>
                        <div class="plot-details-list hidden" id="${type}-details-${uid}"></div>
                    </div>
                </div>
            </div>`;
    }

    function optionalSection(uid, sectionId, value, icon, title) {
        if (!value) return '';
        return `
            <div class="content-card" id="${sectionId}-${uid}">
                <div class="card-header"><h3><i class="fas ${icon}"></i> ${title}</h3></div>
                <div class="card-body"><div class="info-content">${generateFractionHTML(value)}</div></div>
            </div>`;
    }

    function fillPlotSection(containerId, plots) {
        const container = document.querySelector(`#${containerId}`);
        if (!container) return;

        const plotsSection = container.querySelector('.plots-section');
        if (!plotsSection) return;

        const filteredPlots = plots || [];
        if (!filteredPlots || filteredPlots.length === 0) {
            container.style.display = 'none';
            return;
        }
        container.style.display = 'block';

        const summaryEl = plotsSection.querySelector('.plots-summary');
        const numbersDiv = summaryEl.querySelector('.plot-numbers');
        const summaryDiv = summaryEl.querySelector('.plot-summary');
        const detailsList = plotsSection.querySelector('.plot-details-list');

        numbersDiv.innerHTML = filteredPlots.map(p => generateFractionHTML(p.nazwa_lub_numer)).join(', ');

        const counts = filteredPlots.reduce((acc, p) => {
            const key = p.kategoria || 'nieznana';
            acc[key] = (acc[key] || 0) + 1;
            return acc;
        }, {});
        summaryDiv.textContent = `(w tym: ${Object.entries(counts).map(([key, count]) => `${count} ${key}`).join(', ')})`;

        const byCategory = filteredPlots.reduce((acc, p) => {
            const key = p.kategoria || 'nieznana';
            (acc[key] = acc[key] || []).push(p);
            return acc;
        }, {});

        detailsList.innerHTML = Object.entries(byCategory)
            .map(([key, list]) => `
                <div class="plot-category-block">
                    <h4>${key.charAt(0).toUpperCase() + key.slice(1)} (${list.length}):</h4>
                    <div class="plot-numbers">${list.map(p => generateFractionHTML(p.nazwa_lub_numer)).join(', ')}</div>
                </div>`)
            .join('');
    }

    function alignCardHeights() {
        if (window.innerWidth < 1200) {
            document.querySelectorAll('.compare-container .protocol-column > *')
                .forEach(el => (el.style.minHeight = ''));
            return;
        }

        const cols = document.querySelectorAll('.compare-container .protocol-column');
        if (cols.length < 2) return;

        const [left, right] = cols;
        const leftKids = Array.from(left.children);
        const rightKids = Array.from(right.children);

        leftKids.forEach(el => (el.style.minHeight = ''));
        rightKids.forEach(el => (el.style.minHeight = ''));

        const maxLength = Math.max(leftKids.length, rightKids.length);
        for (let i = 0; i < maxLength; i++) {
            const maxHeight = Math.max(leftKids[i]?.offsetHeight || 0, rightKids[i]?.offsetHeight || 0);
            if (maxHeight > 0) {
                if (leftKids[i]) leftKids[i].style.minHeight = `${maxHeight}px`;
                if (rightKids[i]) rightKids[i].style.minHeight = `${maxHeight}px`;
            }
        }
    }

    window.CompareRenderer = Object.freeze({
        columnTemplate: columnTemplate,
        fillPlotSection: fillPlotSection,
        alignCardHeights: alignCardHeights,
    });
})();
