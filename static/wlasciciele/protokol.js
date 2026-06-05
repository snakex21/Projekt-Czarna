/* ==========================================================================
   Plik: protokol.js
   Opis: Główny skrypt obsługujący wyświetlanie protokołów katastralnych.
         Zarządza pobieraniem danych, renderowaniem interfejsu, modalami
         oraz generowaniem PDF i wizualizacją drzewa genealogicznego.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    if (!window.OwnersAPI) {
        throw new Error('protokol.js wymaga js/api.js załadowanego wcześniej');
    }
    if (!window.OwnersUtils) {
        throw new Error('protokol.js wymaga js/utils.js załadowanego wcześniej');
    }
    if (!window.ProtocolImages) {
        throw new Error('protokol.js wymaga js/protocol-images.js załadowanego wcześniej');
    }
    if (!window.ProtocolGenealogyTree) {
        throw new Error('protokol.js wymaga js/protocol-genealogy-tree.js załadowanego wcześniej');
    }
    const API = window.OwnersAPI;
    const UTILS = window.OwnersUtils;
    const IMAGES = window.ProtocolImages;
    const TREE = window.ProtocolGenealogyTree;
    var escapeHtml = UTILS.escapeHtml;
    var normalizeText = UTILS.normalizeText;
    var generateFractionHTML = UTILS.generateFractionHTML;
    var formatArea = UTILS.formatArea;
    var formatLength = UTILS.formatLength;
    var formatDate = UTILS.formatDate;

    /* ==========================================================================
       DEKLARACJA ZMIENNYCH I STAŁYCH
       ========================================================================== */

    // Parametry URL
    const urlParams = new URLSearchParams(window.location.search);
    const ownerKey = urlParams.get('ownerId');

    // Elementy DOM - podstawowe
    const orderNumberEl = document.getElementById('orderNumber');
    const protocolDateEl = document.getElementById('protocolDate');
    const protocolLocationEl = document.getElementById('protocolLocation');
    const ownerNameEl = document.getElementById('ownerName');
    const genealogyEl = document.getElementById('genealogy');
    const ownershipHistoryEl = document.getElementById('ownershipHistory');

    // Elementy DOM - przyciski akcji
    const downloadPdfBtn = document.getElementById('downloadPdfBtn');
    const showOriginalBtn = document.getElementById('showOriginalBtn');
    const backToMapBtn = document.getElementById('backToMapBtn');
    const fullscreenBtn = document.getElementById('fullscreenBtn');
    const showHouseOnMapBtn = document.getElementById('showHouseOnMapBtn');
    const showTreeBtn = document.getElementById('showTreeBtn');

    // Elementy DOM - modal skanów
    const imageModal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImageSrc');
    const closeModalBtn = document.querySelector('.modal-close-btn');
    const prevBtn = document.getElementById('prevImageBtn');
    const nextBtn = document.getElementById('nextImageBtn');
    const pageCounter = document.getElementById('pageCounter');

    // Elementy DOM - dialog drzewa genealogicznego
    const treeDialog = document.getElementById('treeDialog');
    const closeTreeBtn = document.getElementById('closeTreeBtn');
    const treeContainer = document.getElementById('treeContainer');

    // Stan aplikacji
    let ownerData = null;
    let havePlotDifferences = false;

    /* ==========================================================================
       INICJALIZACJA APLIKACJI
       ========================================================================== */

    /**
     * Główna funkcja inicjalizująca - waliduje parametry i uruchamia komponenty
     */
    const init = () => {
        // Walidacja parametrów URL
        if (!ownerKey) {
            showError('Błąd: Brak klucza właściciela w adresie URL.');
            return;
        }

        // Ustawienie aktualnej daty
        const currentDateEl = document.getElementById('currentDate');
        if (currentDateEl) {
            currentDateEl.textContent = new Date().toLocaleDateString('pl-PL');
        }

        // Inicjalizacja komponentów
        IMAGES.init({
            ownerKey,
            elements: {
                showOriginalBtn,
                imageModal,
                modalImage,
                closeModalBtn,
                prevBtn,
                nextBtn,
                pageCounter
            }
        });
        TREE.init({
            ownerKey,
            elements: {
                showTreeBtn,
                treeDialog,
                closeTreeBtn,
                treeContainer
            }
        });
        fetchOwnerData();
        IMAGES.find();
        setupEventListeners();
        setupThemeLogic();
    };

    /* ==========================================================================
       KOMUNIKACJA Z API
       ========================================================================== */

    /**
     * Pobiera dane właściciela z serwera
     */
    const fetchOwnerData = async () => {
        try {
            const response = await fetch(API.owner(ownerKey));
            const data = await response.json();

            if (data.error) {
                showError(data.error);
                return;
            }

            ownerData = data;
            renderOwnerData(data);
        } catch (error) {
            console.error('Błąd pobierania danych:', error);
            showError('Nie udało się pobrać danych protokołu.');
        }
    };

    /* ==========================================================================
       RENDEROWANIE DANYCH
       ========================================================================== */

    /**
     * Renderuje kompletne dane właściciela w interfejsie
     */
    const renderOwnerData = (data) => {
        // Aktualizacja tytułu strony
        document.title = `Protokół - ${data.nazwa_wlasciciela || 'Nieznany'}`;

        // Metadane protokołu
        fillField(orderNumberEl, data.numer_protokolu);
        fillField(protocolDateEl, formatDate(data.data_protokolu));
        fillField(protocolLocationEl, data.miejsce_protokolu);

        // Dynamiczne ustawienie gminy katastralnej w tytule
        const protocolLocationTitle = document.getElementById('protocol-location-title');
        if (protocolLocationTitle && data.gmina_katastralna) {
            protocolLocationTitle.textContent = `w gminie katastralnej ${data.gmina_katastralna}`;
        }

        // Informacje o właścicielu
        const ownerHtml = `
            <div>
                <div class="owner-name-main">${data.nazwa_wlasciciela || ''}</div>
                ${data.numer_domu ? `
                    <div class="owner-secondary-info">
                        Dom: <span class="owner-details-value">${generateFractionHTML(data.numer_domu)}</span>
                    </div>
                ` : ''}
            </div>
        `;
        ownerNameEl.innerHTML = ownerHtml;

        // Przycisk domu na mapie
        if (data.dom_obiekt_id) {
            showHouseOnMapBtn.classList.remove('hidden');
        }

        // Sekcja genealogii
        if (data.genealogia) {
            fillFieldWithFractions(genealogyEl, data.genealogia);
            document.getElementById('genealogySection').classList.remove('hidden');

            if (data.ma_drzewo_genealogiczne) {
                showTreeBtn.classList.remove('hidden');
            }
        }

        // Treść protokołu
        fillFieldWithFractions(ownershipHistoryEl, data.pelna_historia);

        // Sekcje opcjonalne
        showOptionalSection('wspolwlasnoscSection', 'wspolwlasnosc', data.wspolwlasnosc);
        showOptionalSection('powiazaniaTransakcjeSection', 'powiazaniaTransakcje', data.powiazania_i_transakcje_html);
        showOptionalSection('interpretacjaWnioskiSection', 'interpretacjaWnioski', data.interpretacja_i_wnioski);

        // Renderowanie działek
        renderPlots(data);
    };

    /**
     * Renderuje sekcje działek z porównaniem stanów
     */
    const renderPlots = (data) => {
        const protokolPlots = data.dzialki_protokol || [];
        const rzeczywistePlots = data.dzialki_rzeczywiste || [];

        // Funkcja porównująca listy działek
        const arePlotListsEqual = (listA, listB) => {
            if (listA.length !== listB.length) return false;
            const idsA = new Set(listA.map(p => p.id));
            const idsB = new Set(listB.map(p => p.id));
            return idsA.size === idsB.size && [...idsA].every(id => idsB.has(id));
        };

        const haveDifferences = !arePlotListsEqual(protokolPlots, rzeczywistePlots);
        havePlotDifferences = haveDifferences;

        if (haveDifferences) {
            // Wyświetlenie przełącznika i obu widoków
            document.querySelector('.view-switcher').classList.remove('hidden');
            updatePlotSection('rzeczywistePlots', rzeczywistePlots);
            updatePlotSection('protokolPlots', protokolPlots);
        } else {
            // Wyświetlenie pojedynczego widoku
            document.querySelector('.view-switcher').classList.add('hidden');
            const viewRzeczywiste = document.getElementById('view-rzeczywiste');
            viewRzeczywiste.querySelector('.card-header h3').innerHTML =
                '<i class="fas fa-layer-group"></i> Działki';
            updatePlotSection('rzeczywistePlots', rzeczywistePlots);
            document.getElementById('view-protokol').classList.add('hidden');
        }

        // Konfiguracja linków do mapy
        setupMapLinks(rzeczywistePlots, protokolPlots, haveDifferences);
    };

    /**
     * Zwraca ikonę i kolor dla kategorii działki
     */
    const getCategoryStyle = (category) => {
        const styles = {
            'rolna': { icon: 'fa-seedling', color: '#48bb78', bgColor: '#f0fff4' },
            'las': { icon: 'fa-tree', color: '#38a169', bgColor: '#e6fffa' },
            'pastwisko': { icon: 'fa-horse', color: '#ed8936', bgColor: '#fffaf0' },
            'łąka': { icon: 'fa-spa', color: '#68d391', bgColor: '#f0fff4' },
            'budowlana': { icon: 'fa-building', color: '#4299e1', bgColor: '#ebf8ff' },
            'dom': { icon: 'fa-home', color: '#e53e3e', bgColor: '#fff5f5' },
            'budynek': { icon: 'fa-warehouse', color: '#dd6b20', bgColor: '#fffaf0' },
            'ogród': { icon: 'fa-leaf', color: '#9f7aea', bgColor: '#faf5ff' },
            'sad': { icon: 'fa-apple-alt', color: '#f56565', bgColor: '#fff5f5' },
            'droga': { icon: 'fa-road', color: '#805ad5', bgColor: '#faf5ff' },
            'rzeka': { icon: 'fa-water', color: '#3182ce', bgColor: '#ebf8ff' },
            'nieznana': { icon: 'fa-question-circle', color: '#a0aec0', bgColor: '#f7fafc' }
        };
        return styles[category] || styles['nieznana'];
    };

    /**
     * Aktualizuje pojedynczą sekcję działek
     */
    const updatePlotSection = (containerId, plots) => {
        const container = document.getElementById(containerId);
        if (!container || !plots || plots.length === 0) return;

        const numbersDiv = container.querySelector('.plot-numbers');
        const summaryDiv = container.querySelector('.plot-summary');
        const detailsDiv = document.getElementById(
            containerId === 'rzeczywistePlots' ? 'rzeczywiste-details' : 'protokol-details'
        );

        const filteredPlots = plots;

        // Lista numerów działek - PROSTY FORMAT
        numbersDiv.innerHTML = filteredPlots.map(p => generateFractionHTML(p.nazwa_lub_numer)).join(', ');

        // Obliczanie łącznej powierzchni (bez dróg i rzek)
        const plotsWithArea = filteredPlots.filter(p => !['droga', 'rzeka'].includes(p.kategoria));
        const roadsAndRivers = filteredPlots.filter(p => ['droga', 'rzeka'].includes(p.kategoria));
        const totalArea = plotsWithArea.reduce((sum, p) => sum + (p.powierzchnia_m2 || 0), 0);

        // Podsumowanie kategorii z powierzchnią/długością
        const categoryStats = filteredPlots.reduce((acc, p) => {
            const k = p.kategoria || 'nieznana';
            const isRoadOrRiver = ['droga', 'rzeka'].includes(k);

            if (!acc[k]) {
                acc[k] = { count: 0, area: 0, length: 0, plots: [] };
            }
            acc[k].count += 1;

            if (isRoadOrRiver) {
                acc[k].length += (p.dlugosc_m || 0);
            } else {
                acc[k].area += (p.powierzchnia_m2 || 0);
            }

            acc[k].plots.push(p);
            return acc;
        }, {});

        // PROSTY TEKST przed rozwinięciem z łączną powierzchnią i procentami
        const summaryParts = Object.entries(categoryStats)
            .map(([category, stats]) => {
                const isRoadOrRiver = ['droga', 'rzeka'].includes(category);
                const measurement = isRoadOrRiver ? formatLength(stats.length) : formatArea(stats.area);
                const percentage = !isRoadOrRiver && totalArea > 0
                    ? `, ${((stats.area / totalArea) * 100).toFixed(1)}%`
                    : '';
                return `${stats.count} ${category} (${measurement}${percentage})`;
            })
            .join(', ');

        const areaCount = plotsWithArea.length;
        const roadCount = roadsAndRivers.length;
        const countText = roadCount > 0
            ? `${areaCount} ${areaCount === 1 ? 'działka' : areaCount < 5 ? 'działki' : 'działek'} + ${roadCount} ${roadCount === 1 ? 'droga' : 'drogi'}`
            : `${areaCount} ${areaCount === 1 ? 'działka' : areaCount < 5 ? 'działki' : 'działek'}`;

        summaryDiv.innerHTML = `
            <div style="margin-bottom: 0.5rem; font-weight: 600; color: var(--primary-color);">
                Łączna powierzchnia: ${formatArea(totalArea)} (${countText})
            </div>
            <div style="color: var(--text-secondary);">
                (w tym: ${summaryParts})
            </div>
        `;

        // ŁADNE KARTY w szczegółach (po rozwinięciu) z progress barami
        const categoriesHTML = Object.entries(categoryStats)
            .sort((a, b) => b[1].area - a[1].area)
            .map(([category, stats]) => {
                const style = getCategoryStyle(category);
                const isRoadOrRiver = ['droga', 'rzeka'].includes(category);
                const percentage = !isRoadOrRiver && totalArea > 0 ? ((stats.area / totalArea) * 100).toFixed(1) : 0;

                // Dla dróg/rzek liczymy łączną długość, dla reszty powierzchnię
                const categoryTotal = isRoadOrRiver ? stats.length : stats.area;
                const formattedTotal = isRoadOrRiver ? formatLength(categoryTotal) : formatArea(categoryTotal);

                return `
                    <div class="area-category-item" style="margin-bottom: 0.75rem;">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                <i class="fas ${style.icon}" style="color: ${style.color}; font-size: 1rem;"></i>
                                <span style="font-weight: 600; text-transform: capitalize;">${category}</span>
                                <span style="color: var(--text-secondary); font-size: 0.9em;">(${stats.count})</span>
                            </div>
                            <span style="font-weight: 700; color: ${style.color};">${formattedTotal}</span>
                        </div>
                        ${!isRoadOrRiver ? `
                            <div style="background: #e2e8f0; border-radius: 8px; height: 8px; overflow: hidden; margin-bottom: 0.3rem;">
                                <div style="background: ${style.color}; width: ${percentage}%; height: 100%; border-radius: 8px; transition: width 0.5s ease;"></div>
                            </div>
                            <div style="text-align: right; font-size: 0.8em; color: var(--text-secondary);">
                                ${percentage}%
                            </div>
                        ` : '<div style="text-align: right; font-size: 0.8em; color: var(--text-secondary); font-style: italic;">długość</div>'}
                    </div>
                    <div class="plot-category-block" style="background: ${style.bgColor}; border-left: 3px solid ${style.color}; padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem;">
                        <div class="plot-numbers" style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                            ${stats.plots.map(p => {
                    const isRR = ['droga', 'rzeka'].includes(p.kategoria);
                    const measurement = isRR ? formatLength(p.dlugosc_m) : formatArea(p.powierzchnia_m2);

                    return `
                                    <div class="plot-item-card" style="background: white; border: 1px solid ${style.color}40; border-radius: 5px; padding: 0.35rem 0.6rem; display: inline-flex; align-items: center; gap: 0.4rem; transition: all 0.2s ease; cursor: default;">
                                        <span style="font-weight: 600; color: ${style.color}; font-size: 0.9rem;">${generateFractionHTML(p.nazwa_lub_numer)}</span>
                                        <span style="color: var(--text-secondary); font-size: 0.8em; border-left: 1px solid #e2e8f0; padding-left: 0.4rem;">
                                            ${measurement}
                                        </span>
                                    </div>
                                `;
                }).join('')}
                        </div>
                    </div>
                `;
            }).join('');

        detailsDiv.innerHTML = `
            <div class="area-summary-card" style="background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%); border: 2px solid #667eea30; border-radius: 10px; padding: 1rem; margin-bottom: 1rem;">
                <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); width: 45px; height: 45px; border-radius: 10px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);">
                        <i class="fas fa-chart-area" style="color: white; font-size: 1.4rem;"></i>
                    </div>
                    <div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary); font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">Łączna powierzchnia</div>
                        <div style="font-size: 1.5rem; font-weight: 700; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; line-height: 1.2;">
                            ${formatArea(totalArea)}
                        </div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">
                            ${countText}
                        </div>
                    </div>
                </div>
                <div class="category-breakdown">
                    ${categoriesHTML}
                </div>
            </div>
        `;
    };

    /**
     * Konfiguruje przyciski nawigacji do mapy
     */
    const setupMapLinks = (rzeczywistePlots, protokolPlots, haveDifferences) => {
        const mapLinkReal = document.getElementById('mapLinkReal');
        const mapLinkProtocol = document.getElementById('mapLinkProtocol');
        const mapLinkBoth = document.getElementById('mapLinkBoth');
        const mapUrl = API.mapPage();

        if (!haveDifferences && rzeczywistePlots.length > 0) {
            // Pojedynczy przycisk dla identycznych stanów
            const plotIds = rzeczywistePlots.map(p => p.id).join(',');
            mapLinkReal.href = `${mapUrl}?highlightByIds=${plotIds}`;
            mapLinkReal.innerHTML = '<i class="fas fa-map-marked-alt"></i> Pokaż na mapie';
            mapLinkReal.classList.remove('hidden');
        } else {
            // Osobne przyciski dla różnych stanów
            if (rzeczywistePlots.length > 0) {
                const plotIds = rzeczywistePlots.map(p => p.id).join(',');
                mapLinkReal.href = `${mapUrl}?highlightByIds=${plotIds}`;
                mapLinkReal.classList.remove('hidden');
            }

            if (protokolPlots.length > 0) {
                const plotIds = protokolPlots.map(p => p.id).join(',');
                mapLinkProtocol.href = `${mapUrl}?highlightByIds=${plotIds}`;
                mapLinkProtocol.classList.remove('hidden');
            }

            if (rzeczywistePlots.length > 0 && protokolPlots.length > 0) {
                const allIds = [...new Set([
                    ...rzeczywistePlots.map(p => p.id),
                    ...protokolPlots.map(p => p.id)
                ])].join(',');
                mapLinkBoth.href = `${mapUrl}?highlightByIds=${allIds}`;
                mapLinkBoth.classList.remove('hidden');
            }
        }
    };

    /* ==========================================================================
       OBSŁUGA ZDARZEŃ
       ========================================================================== */

    /**
     * Konfiguruje wszystkie handlery zdarzeń
     */
    const setupEventListeners = () => {
        // Inicjalizacja trybu pełnoekranowego
        setupFullscreen();

        // Przyciski główne
        downloadPdfBtn.addEventListener('click', generatePDF);
        backToMapBtn.addEventListener('click', () => {
            window.location.href = API.mapPage();
        });

        // Przycisk domu na mapie
        showHouseOnMapBtn.addEventListener('click', () => {
            if (!ownerData || !ownerData.dom_obiekt_id) return;

            const mapUrl = API.mapPage();
            // Pokazujemy TYLKO dom, bez działek, i zoomujemy na nim
            window.location.href = `${mapUrl}?highlightByIds=${ownerData.dom_obiekt_id}&zoomToFit=true`;
        });

        // Przełącznik widoków działek
        const btnRzeczywiste = document.getElementById('btn-view-rzeczywiste');
        const btnProtokol = document.getElementById('btn-view-protokol');

        btnRzeczywiste.addEventListener('click', () => {
            document.getElementById('view-rzeczywiste').classList.remove('hidden');
            document.getElementById('view-protokol').classList.add('hidden');
            btnRzeczywiste.classList.add('active');
            btnProtokol.classList.remove('active');
        });

        btnProtokol.addEventListener('click', () => {
            document.getElementById('view-protokol').classList.remove('hidden');
            document.getElementById('view-rzeczywiste').classList.add('hidden');
            btnProtokol.classList.add('active');
            btnRzeczywiste.classList.remove('active');
        });

        // Przyciski rozwijania szczegółów
        document.querySelectorAll('.details-toggle-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const targetId = btn.dataset.target;
                const targetEl = document.getElementById(targetId);
                const icon = btn.querySelector('i');

                if (targetEl.classList.contains('hidden')) {
                    targetEl.classList.remove('hidden');
                    icon.className = 'fas fa-chevron-up';
                } else {
                    targetEl.classList.add('hidden');
                    icon.className = 'fas fa-chevron-down';
                }
            });
        });

        // Skróty klawiszowe
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (!imageModal.classList.contains('hidden')) {
                    IMAGES.close();
                } else if (treeDialog.open) {
                    TREE.close();
                }
            }
        });
    };

    /* ==========================================================================
       GENEROWANIE PDF
       ========================================================================== */

    /**
     * Generuje PDF z treścią protokołu
     */
    const generatePDF = async () => {
        const ownerName = ownerData?.nazwa_wlasciciela || 'protokol';
        const fileName = `Protokol_${ownerName.replace(/[^\p{L}\p{N}_-]+/gu, '_')}.pdf`;

        // Przygotowanie strony do eksportu
        document.body.classList.add('pdf-export');

        // Ukrycie elementów interaktywnych
        const elementsToHide = document.querySelectorAll(
            '.action-btn, .header-btn, .switch-btn, .details-toggle-btn, .view-switcher, .map-links-section, .top-header, .app-footer'
        );
        const originalDisplays = new Map();
        elementsToHide.forEach(el => originalDisplays.set(el, el.style.display));
        elementsToHide.forEach(el => el.style.display = 'none');

        // Rozwinięcie szczegółów działek
        const initiallyHiddenDetails = [...document.querySelectorAll('.plot-details-list.hidden')];
        document.querySelectorAll('.plot-details-list').forEach(el => el.classList.remove('hidden'));

        // Zarządzanie widokami działek
        const viewRzeczywiste = document.getElementById('view-rzeczywiste');
        const viewProtokol = document.getElementById('view-protokol');
        const wasRzeczywisteHidden = viewRzeczywiste?.classList.contains('hidden');
        const wasProtokolHidden = viewProtokol?.classList.contains('hidden');

        // Obliczenie różnic
        const computeHaveDifferences = () => {
            const A = ownerData?.dzialki_protokol || [];
            const B = ownerData?.dzialki_rzeczywiste || [];
            if (A.length !== B.length) return true;
            const idsA = new Set(A.map(p => p.id));
            const idsB = new Set(B.map(p => p.id));
            if (idsA.size !== idsB.size) return true;
            for (const id of idsA) if (!idsB.has(id)) return true;
            return false;
        };
        const differences = (typeof havePlotDifferences !== 'undefined')
            ? havePlotDifferences
            : computeHaveDifferences();

        if (differences) {
            viewRzeczywiste?.classList.remove('hidden');
            viewProtokol?.classList.remove('hidden');
        } else {
            viewRzeczywiste?.classList.remove('hidden');
            viewProtokol?.classList.add('hidden');
        }

        // Oczekiwanie na wyrenderowanie
        await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
        if (document.fonts?.ready) { try { await document.fonts.ready; } catch (e) { } }
        await new Promise(r => setTimeout(r, 50));

        // Konfiguracja PDF
        const opt = {
            margin: 10,
            filename: fileName,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: {
                scale: 2,
                useCORS: true,
                backgroundColor: '#ffffff',
                scrollY: 0
            },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
            pagebreak: { avoid: '.content-card' }
        };

        const content = document.querySelector('.main-content');

        try {
            await html2pdf().from(content).set(opt).save();
        } finally {
            // Przywrócenie stanu strony
            elementsToHide.forEach(el => el.style.display = originalDisplays.get(el) || '');
            initiallyHiddenDetails.forEach(el => el.classList.add('hidden'));

            if (wasRzeczywisteHidden) viewRzeczywiste?.classList.add('hidden');
            else viewRzeczywiste?.classList.remove('hidden');
            if (wasProtokolHidden) viewProtokol?.classList.add('hidden');
            else viewProtokol?.classList.remove('hidden');

            document.body.classList.remove('pdf-export');
        }
    };

    /* ==========================================================================
       FUNKCJE POMOCNICZE
       ========================================================================== */

    /**
     * Wypełnia pole tekstem z obsługą wartości domyślnej
     */
    const fillField = (element, value) => {
        // Ustawia surowy tekst w elemencie — bez formatowania ułamków.
        // Dla pól, które mają zawierać ułamki, użyj fillFieldWithFractions.
        if (element) {
            element.innerHTML = value
                ? escapeHtml(normalizeText(value)).replace(/\n/g, '<br>')
                : '—';
        }
    };

    const fillFieldWithFractions = (element, value) => {
        if (element) {
            element.innerHTML = value
                ? generateFractionHTML(escapeHtml(normalizeText(value)))
                : '—';
        }
    };

    /**
     * Wyświetla sekcję opcjonalną jeśli zawiera treść
     */
    const showOptionalSection = (sectionId, fieldId, value) => {
        if (value && value.trim()) {
            const section = document.getElementById(sectionId);
            const field = document.getElementById(fieldId);

            if (section && field) {
                section.classList.remove('hidden');
                if (fieldId === 'powiazaniaTransakcje') {
                    // Backend już dostarcza bezpieczne HTML z linkami — nie escape'ujemy,
                    // ale nadal formatujemy ułamki.
                    field.innerHTML = generateFractionHTML(normalizeText(value));
                } else {
                    field.innerHTML = generateFractionHTML(escapeHtml(normalizeText(value)));
                }
            }
        }
    };

    /**
     * Wyświetla komunikat błędu
     */
    const showError = (message) => {
        document.body.innerHTML = `
            <div style="display: flex; justify-content: center; align-items: center; height: 100vh; font-family: Inter, sans-serif;">
                <div style="text-align: center; padding: 2rem; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                    <i class="fas fa-exclamation-triangle" style="font-size: 3rem; color: #e53e3e; margin-bottom: 1rem;"></i>
                    <h1 style="color: #2d3748; margin-bottom: 0.5rem;">${message}</h1>
                    <a href="${API.mapPage()}" style="color: #667eea; text-decoration: none; font-weight: 500;">
                        ← Wróć do mapy
                    </a>
                </div>
            </div>
        `;
    };

    /**
     * Zarządza motywem kolorystycznym
     */
    const setupThemeLogic = () => {
        const themeToggleBtn = document.getElementById('themeToggleBtn');
        if (!themeToggleBtn) return;

        const icon = themeToggleBtn.querySelector('i');

        // Aplikacja motywu
        const applyTheme = (theme) => {
            document.body.classList.toggle('dark-mode', theme === 'dark');
            if (icon) {
                icon.className = theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
            }
        };

        // Odczyt zapisanego motywu
        const savedTheme = localStorage.getItem('mapTheme') || 'light';
        applyTheme(savedTheme);

        // Obsługa zmiany motywu
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('mapTheme', newTheme);
            applyTheme(newTheme);
        });
    };

    /**
     * Zarządza trybem pełnoekranowym
     */
    const setupFullscreen = () => {
        if (!fullscreenBtn) return;
        const icon = fullscreenBtn.querySelector('i');

        fullscreenBtn.addEventListener('click', () => {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen();
            } else if (document.exitFullscreen) {
                document.exitFullscreen();
            }
        });

        document.addEventListener('fullscreenchange', () => {
            if (icon) {
                icon.className = document.fullscreenElement ? 'fas fa-compress' : 'fas fa-expand';
            }
        });
    };

    /* ==========================================================================
       URUCHOMIENIE APLIKACJI
       ========================================================================== */
    init();
});
