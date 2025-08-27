/**
 * Plik: protokol.js
 * Opis: Skrypt obsługujący wyświetlanie protokołów właścicielskich.
 *       Zarządza pobieraniem danych, renderowaniem, modalami i generowaniem PDF.
 */

document.addEventListener('DOMContentLoaded', () => {
    // === 1. DEKLARACJA ZMIENNYCH I STAŁYCH ===
    
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
    
    // Elementy DOM - przyciski
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
    
    // Elementy DOM - drzewo genealogiczne
    const treeDialog = document.getElementById('treeDialog');
    const closeTreeBtn = document.getElementById('closeTreeBtn');
    const treeContainer = document.getElementById('treeContainer');
    
    // Stan aplikacji
    let panzoomInstance = null;
    let imageUrls = [];
    let currentImageIndex = 0;
    let ownerData = null;
    let havePlotDifferences = false;
    
    // === 2. GŁÓWNA FUNKCJA INICJALIZUJĄCA ===
    
    /**
     * Inicjalizuje aplikację - sprawdza parametry i pobiera dane
     */
    const init = () => {
        // Walidacja parametrów
        if (!ownerKey) {
            showError('Błąd: Brak klucza właściciela w adresie URL.');
            return;
        }
        
        // Ustawienie daty w stopce
        const currentDateEl = document.getElementById('currentDate');
        if (currentDateEl) {
            currentDateEl.textContent = new Date().toLocaleDateString('pl-PL');
        }
        
        // Pobieranie danych
        fetchOwnerData();
        findProtocolImages();
        setupEventListeners();
        setupThemeLogic();
    };
    
    // === 3. FUNKCJE KOMUNIKACJI Z API ===
    
    /**
     * Pobiera dane właściciela z API
     */
    const fetchOwnerData = async () => {
        try {
            const response = await fetch(`/api/wlasciciel/${ownerKey}`);
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
    
    /**
     * Wyszukuje skany protokołu
     */
    const findProtocolImages = async () => {
        const basePath = `/assets/protokoly/${ownerKey}/`;
        const found = [];
        let i = 1;
        
        const checkNext = () => {
            const img = new Image();
            img.src = `${basePath}${i}.jpg`;
            
            img.onload = () => {
                found.push(img.src);
                i++;
                checkNext();
            };
            
            img.onerror = () => {
                if (i === 1 && found.length === 0) {
                    // Sprawdź pojedynczy plik
                    const singleImg = new Image();
                    singleImg.src = `/assets/protokoly/${ownerKey}.jpg`;
                    
                    singleImg.onload = () => {
                        found.push(singleImg.src);
                        finishImageSearch(found);
                    };
                    
                    singleImg.onerror = () => finishImageSearch(found);
                } else {
                    finishImageSearch(found);
                }
            };
        };
        
        checkNext();
    };
    
    /**
     * Kończy wyszukiwanie obrazów
     */
    const finishImageSearch = (foundImages) => {
        imageUrls = foundImages;
        if (imageUrls.length > 0) {
            showOriginalBtn.classList.remove('hidden');
        }
    };
    
    // === 4. FUNKCJE RENDERUJĄCE I MANIPULUJĄCE DOM ===
    
    /**
     * Renderuje dane właściciela na stronie
     */
    const renderOwnerData = (data) => {
        // Ustawienie tytułu strony
        document.title = `Protokół - ${data.nazwa_wlasciciela || 'Nieznany'}`;
        
        // Podstawowe dane
        fillField(orderNumberEl, data.numer_protokolu);
        fillField(protocolDateEl, formatDate(data.data_protokolu));
        fillField(protocolLocationEl, data.miejsce_protokolu);
        
        // Dane właściciela
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
        
        // Genealogia
        if (data.genealogia) {
            fillField(genealogyEl, data.genealogia);
            document.getElementById('genealogySection').classList.remove('hidden');
            
            if (data.ma_drzewo_genealogiczne) {
                showTreeBtn.classList.remove('hidden');
            }
        }
        
        // Treść protokołu
        fillField(ownershipHistoryEl, generateFractionHTML(data.pelna_historia));
        
        // Sekcje opcjonalne
        showOptionalSection('wspolwlasnoscSection', 'wspolwlasnosc', data.wspolwlasnosc);
        showOptionalSection('powiazaniaTransakcjeSection', 'powiazaniaTransakcje', data.powiazania_i_transakcje_html);
        showOptionalSection('interpretacjaWnioskiSection', 'interpretacjaWnioski', data.interpretacja_i_wnioski);
        
        // Działki
        renderPlots(data);
    };
    
    /**
     * Renderuje sekcje działek
     */
    const renderPlots = (data) => {
        const protokolPlots = data.dzialki_protokol || [];
        const rzeczywistePlots = data.dzialki_rzeczywiste || [];
        
        const arePlotListsEqual = (listA, listB) => {
            if (listA.length !== listB.length) return false;
            const idsA = new Set(listA.map(p => p.id));
            const idsB = new Set(listB.map(p => p.id));
            return idsA.size === idsB.size && [...idsA].every(id => idsB.has(id));
        };
        
        const haveDifferences = !arePlotListsEqual(protokolPlots, rzeczywistePlots);
        havePlotDifferences = haveDifferences;
        
        if (haveDifferences) {
            // Pokazujemy przełącznik i oba widoki
            document.querySelector('.view-switcher').classList.remove('hidden');
            updatePlotSection('rzeczywistePlots', rzeczywistePlots);
            updatePlotSection('protokolPlots', protokolPlots);
        } else {
            // Pokazujemy tylko jeden widok
            document.querySelector('.view-switcher').classList.add('hidden');
            const viewRzeczywiste = document.getElementById('view-rzeczywiste');
            viewRzeczywiste.querySelector('.card-header h3').innerHTML = 
                '<i class="fas fa-layer-group"></i> Działki';
            updatePlotSection('rzeczywistePlots', rzeczywistePlots);
            document.getElementById('view-protokol').classList.add('hidden');
        }
        
        // Konfiguracja przycisków mapy
        setupMapLinks(rzeczywistePlots, protokolPlots, haveDifferences);
    };
    
    /**
     * Aktualizuje sekcję działek
     */
    const updatePlotSection = (containerId, plots) => {
        const container = document.getElementById(containerId);
        if (!container || !plots || plots.length === 0) return;
        
        const numbersDiv = container.querySelector('.plot-numbers');
        const summaryDiv = container.querySelector('.plot-summary');
        const detailsDiv = document.getElementById(
            containerId === 'rzeczywistePlots' ? 'rzeczywiste-details' : 'protokol-details'
        );
        
        // Numery działek
        numbersDiv.innerHTML = plots.map(p => generateFractionHTML(p.nazwa_lub_numer)).join(', ');
        
        // Podsumowanie
        const categoryCounts = plots.reduce((acc, p) => {
            const k = p.kategoria || 'nieznana';
            acc[k] = (acc[k] || 0) + 1;
            return acc;
        }, {});
        
        summaryDiv.textContent = `(w tym: ${Object.entries(categoryCounts)
            .map(([k, c]) => `${c} ${k}`).join(', ')})`;
        
        // Szczegóły
        const plotsByCat = plots.reduce((acc, p) => {
            const k = p.kategoria || 'nieznana';
            (acc[k] = acc[k] || []).push(p);
            return acc;
        }, {});
        
        detailsDiv.innerHTML = Object.entries(plotsByCat).map(([k, list]) => `
            <div class="plot-category-block">
                <h4>${k.charAt(0).toUpperCase() + k.slice(1)} (${list.length}):</h4>
                <div class="plot-numbers">
                    ${list.map(p => generateFractionHTML(p.nazwa_lub_numer)).join(', ')}
                </div>
            </div>
        `).join('');
    };
    
    /**
     * Konfiguruje linki do mapy
     */
    const setupMapLinks = (rzeczywistePlots, protokolPlots, haveDifferences) => {
        const mapLinkReal = document.getElementById('mapLinkReal');
        const mapLinkProtocol = document.getElementById('mapLinkProtocol');
        const mapLinkBoth = document.getElementById('mapLinkBoth');
        const mapUrl = '../mapa/mapa.html';
        
        if (!haveDifferences && rzeczywistePlots.length > 0) {
            // Jeden przycisk gdy stany są identyczne
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
    
    // === 5. OBSŁUGA ZDARZEŃ (EVENT LISTENERS) ===
    
    /**
     * Konfiguruje wszystkie event listenery
     */
    const setupEventListeners = () => {
        // Logika pełnego ekranu
        setupFullscreen();       
        // Przyciski główne
        downloadPdfBtn.addEventListener('click', generatePDF);
        showOriginalBtn.addEventListener('click', openImageModal);
        backToMapBtn.addEventListener('click', () => {
            window.location.href = '../mapa/mapa.html';
        });
        
        // Przycisk domu na mapie
        showHouseOnMapBtn.addEventListener('click', () => {
            if (!ownerData) return;
            
            const mapUrl = '../mapa/mapa.html';
            const allIds = [ownerData.dom_obiekt_id];
            
            // Dodaj działki
            if (ownerData.dzialki_rzeczywiste) {
                allIds.push(...ownerData.dzialki_rzeczywiste.map(p => p.id));
            }
            if (ownerData.dzialki_protokol) {
                allIds.push(...ownerData.dzialki_protokol.map(p => p.id));
            }
            
            const uniqueIds = [...new Set(allIds)].join(',');
            window.location.href = `${mapUrl}?highlightByIds=${uniqueIds}`;
        });
        
        // Przełącznik widoków
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
        
        // Modal skanów
        closeModalBtn.addEventListener('click', closeImageModal);
        imageModal.addEventListener('click', (e) => {
            if (e.target === imageModal) closeImageModal();
        });
        prevBtn.addEventListener('click', showPrevImage);
        nextBtn.addEventListener('click', showNextImage);
        
        // Drzewo genealogiczne
        showTreeBtn.addEventListener('click', loadGenealogyTree);
        closeTreeBtn.addEventListener('click', () => {
            treeDialog.close();
            treeContainer.innerHTML = '';
        });
        
        // Skróty klawiszowe
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (!imageModal.classList.contains('hidden')) {
                    closeImageModal();
                } else if (treeDialog.open) {
                    treeDialog.close();
                }
            }
        });
    };
    
    // === 6. FUNKCJE OBSŁUGI MODALI ===
    
    /**
     * Otwiera modal ze skanami
     */
    const openImageModal = () => {
        if (imageUrls.length === 0) return;
        
        currentImageIndex = 0;
        updateModalContent();
        imageModal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        
        // Inicjalizacja Panzoom
        panzoomInstance = Panzoom(modalImage, {
            maxScale: 5,
            minScale: 0.5
        });
        
        modalImage.parentElement.addEventListener('wheel', panzoomInstance.zoomWithWheel);
    };
    
    /**
     * Zamyka modal ze skanami
     */
    const closeImageModal = () => {
        imageModal.classList.add('hidden');
        document.body.style.overflow = 'auto';
        
        if (panzoomInstance) {
            panzoomInstance.destroy();
            panzoomInstance = null;
        }
    };
    
    /**
     * Aktualizuje zawartość modala
     */
    const updateModalContent = () => {
        modalImage.src = imageUrls[currentImageIndex];
        pageCounter.textContent = `Strona ${currentImageIndex + 1} / ${imageUrls.length}`;
        
        prevBtn.disabled = currentImageIndex === 0;
        nextBtn.disabled = currentImageIndex === imageUrls.length - 1;
        
        const navControls = document.querySelector('.modal-nav-controls');
        navControls.style.display = imageUrls.length > 1 ? 'flex' : 'none';
    };
    
    /**
     * Pokazuje następny obraz
     */
    const showNextImage = () => {
        if (currentImageIndex < imageUrls.length - 1) {
            currentImageIndex++;
            updateModalContent();
            if (panzoomInstance) panzoomInstance.reset();
        }
    };
    
    /**
     * Pokazuje poprzedni obraz
     */
    const showPrevImage = () => {
        if (currentImageIndex > 0) {
            currentImageIndex--;
            updateModalContent();
            if (panzoomInstance) panzoomInstance.reset();
        }
    };
    
    // === 7. FUNKCJE DRZEWA GENEALOGICZNEGO ===
    
    /**
     * Ładuje i wyświetla drzewo genealogiczne
     */
    const loadGenealogyTree = async () => {
        showTreeBtn.disabled = true;
        showTreeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Ładowanie...';
        
        try {
            const response = await fetch(`/api/genealogia/${ownerKey}`);
            const treeData = await response.json();
            
            drawGenealogyTree(treeData);
        } catch (error) {
            console.error('Błąd ładowania drzewa:', error);
            alert('Nie udało się załadować drzewa genealogicznego');
        } finally {
            showTreeBtn.disabled = false;
            showTreeBtn.innerHTML = '<i class="fas fa-project-diagram"></i> Pokaż drzewo genealogiczne';
        }
    };
    
    /**
     * Rysuje drzewo genealogiczne używając D3.js
     */
    const drawGenealogyTree = (treeData) => {
        if (!treeData.persons || treeData.persons.length === 0) {
            alert('Brak danych genealogicznych do wyświetlenia');
            return;
        }

        // Stałe konfiguracyjne dla layoutu drzewa
        const NODE_WIDTH = 200;
        const NODE_HEIGHT = 120;
        const HORIZONTAL_SPACING = 80;
        const VERTICAL_SPACING = 180;
        const MARRIAGE_LINE_OFFSET = 20;
        const MARGIN = 50;
        const LEGEND_HEIGHT = 120;

        // Przygotowanie mapy osób
        const persons = new Map();
        treeData.persons.forEach(p => {
            persons.set(p.id, {
                id: p.id,
                name: p.name,
                gender: p.gender,
                birthYear: p.birthDate?.year,
                deathYear: p.deathDate?.year,
                fatherId: p.fatherId,
                motherId: p.motherId,
                spouseIds: p.spouseIds || [],
                protocolKey: p.protocolKey,
                notes: p.notes,
                houseNumber: p.houseNumber,
                isRoot: p.id === treeData.rootId
            });
        });

        /**
         * Funkcja obliczająca generacje - od najstarszych do najmłodszych
         */
        function calculateGenerations() {
            const generations = new Map();   // id → nr generacji

            function assignGeneration(personId, level) {
                const current = generations.get(personId);
                // Zostaw, jeśli ktoś jest już głębiej (większy level)
                if (current !== undefined && current >= level) return;

                generations.set(personId, level);

                const person = persons.get(personId);
                if (!person) return;

                // Małżonkowie – ten sam poziom
                (person.spouseIds || []).forEach(spId => assignGeneration(spId, level));

                // Dzieci – poziom niżej
                persons.forEach(child => {
                    if (child.fatherId === personId || child.motherId === personId) {
                        assignGeneration(child.id, level + 1);
                    }
                });
            }

            // Start: wszystkie osoby bez rodziców
            persons.forEach((p, id) => {
                if (!p.fatherId && !p.motherId) assignGeneration(id, 0);
            });

            return generations;
        }

        /**
         * Funkcja grupująca pary małżeńskie
         */
        function createMarriageGroups() {
            const marriages = new Map();
            const processed = new Set();
            
            persons.forEach((person, id) => {
                if (processed.has(id)) return;
                
                const spouses = person.spouseIds.filter(spouseId => persons.has(spouseId));
                if (spouses.length > 0) {
                    spouses.forEach(spouseId => {
                        if (!processed.has(spouseId)) {
                            const marriageKey = [id, spouseId].sort().join('-');
                            marriages.set(marriageKey, {
                                person1: person,
                                person2: persons.get(spouseId),
                                id: `marriage-${marriageKey}`
                            });
                            processed.add(id);
                            processed.add(spouseId);
                        }
                    });
                }
            });
            
            return marriages;
        }

        // Obliczanie generacji i małżeństw
        const generations = calculateGenerations();
        const marriages = createMarriageGroups();
        
        // Pogrupowanie osób według generacji
        const generationGroups = new Map();
        persons.forEach((person, id) => {
            const gen = generations.get(id) || 0;
            if (!generationGroups.has(gen)) {
                generationGroups.set(gen, []);
            }
            generationGroups.get(gen).push({...person, generation: gen});
        });

        // Sortowanie generacji
        const sortedGenerations = Array.from(generationGroups.entries()).sort((a, b) => a[0] - b[0]);
        
        // Pozycjonowanie węzłów z układem rodzinnym
        const nodePositions = new Map();
        let maxWidth = 0;
        
        sortedGenerations.forEach(([genLevel, personsInGen], genIndex) => {
            // Grupowanie osób w pary małżeńskie i pojedyncze
            const arranged = [];
            const processed = new Set();
            
            // Najpierw znajdź pary małżeńskie w tej generacji
            marriages.forEach((marriage, marriageId) => {
                const p1Gen = generations.get(marriage.person1.id);
                const p2Gen = generations.get(marriage.person2.id);
                
                if (p1Gen === genLevel && p2Gen === genLevel) {
                    arranged.push({
                        type: 'marriage',
                        persons: [marriage.person1, marriage.person2],
                        width: NODE_WIDTH * 2 + MARRIAGE_LINE_OFFSET
                    });
                    processed.add(marriage.person1.id);
                    processed.add(marriage.person2.id);
                }
            });
            
            // Potem dodaj pojedyncze osoby
            personsInGen.forEach(person => {
                if (!processed.has(person.id)) {
                    arranged.push({
                        type: 'single',
                        persons: [person],
                        width: NODE_WIDTH
                    });
                }
            });
            
            // Oblicz szerokość tej generacji
            const totalWidth = arranged.reduce((sum, group) => sum + group.width + HORIZONTAL_SPACING, 0) - HORIZONTAL_SPACING;
            
            if (totalWidth > maxWidth) {
                maxWidth = totalWidth;
            }
            
            // Pozycjonuj grupy w tej generacji
            let currentX = MARGIN;
            const y = MARGIN + LEGEND_HEIGHT + genIndex * (NODE_HEIGHT + VERTICAL_SPACING);
            
            arranged.forEach(group => {
                if (group.type === 'marriage') {
                    // Para małżeńska
                    nodePositions.set(group.persons[0].id, {
                        x: currentX,
                        y: y,
                        person: group.persons[0]
                    });
                    nodePositions.set(group.persons[1].id, {
                        x: currentX + NODE_WIDTH + MARRIAGE_LINE_OFFSET,
                        y: y,
                        person: group.persons[1]
                    });
                } else {
                    // Pojedyncza osoba
                    nodePositions.set(group.persons[0].id, {
                        x: currentX,
                        y: y,
                        person: group.persons[0]
                    });
                }
                currentX += group.width + HORIZONTAL_SPACING;
            });
        });

        // Obliczanie wymiarów SVG
        const svgWidth = Math.max(maxWidth + 2 * MARGIN, 1000);
        const svgHeight = MARGIN + LEGEND_HEIGHT + sortedGenerations.length * (NODE_HEIGHT + VERTICAL_SPACING) + MARGIN;

        
        // Wyczyszczenie kontenera
        treeContainer.innerHTML = '';

        // Utworzenie SVG przy użyciu D3.js
        const svg = d3.create('svg')
            .attr('width', '100%')
            .attr('height', '100%')
            .attr('viewBox', `0 0 ${svgWidth} ${svgHeight}`)
            .style('background', '#fafafa')
            .call(d3.zoom()
                .scaleExtent([0.1, 3])
                .on('zoom', (event) => {
                    g.attr('transform', event.transform);
                }));

        const g = svg.append('g');

        /**
         * Funkcja tworząca połączenia rodzic-dziecko
         */
        function createParentChildConnections() {
            const connections = [];
            
            nodePositions.forEach((childPos, childId) => {
                const child = childPos.person;
                
                // Znajdź rodziców
                const fatherPos = child.fatherId ? nodePositions.get(child.fatherId) : null;
                const motherPos = child.motherId ? nodePositions.get(child.motherId) : null;
                
                if (fatherPos || motherPos) {
                    let parentCenterX, parentY;
                    
                    if (fatherPos && motherPos) {
                        // Oboje rodzice - połączenie z punktu między nimi
                        parentCenterX = (fatherPos.x + NODE_WIDTH/2 + motherPos.x + NODE_WIDTH/2) / 2;
                        parentY = Math.max(fatherPos.y, motherPos.y) + NODE_HEIGHT;
                    } else if (fatherPos) {
                        // Tylko ojciec
                        parentCenterX = fatherPos.x + NODE_WIDTH/2;
                        parentY = fatherPos.y + NODE_HEIGHT;
                    } else if (motherPos) {
                        // Tylko matka
                        parentCenterX = motherPos.x + NODE_WIDTH/2;
                        parentY = motherPos.y + NODE_HEIGHT;
                    }
                    
                    // Dodaj połączenie
                    const childCenterX = childPos.x + NODE_WIDTH/2;
                    const childY = childPos.y;
                    const midY = parentY + (childY - parentY) / 2;
                    
                    connections.push({
                        path: `M${parentCenterX},${parentY} L${parentCenterX},${midY} L${childCenterX},${midY} L${childCenterX},${childY}`,
                        type: 'parent-child'
                    });
                }
            });
            
            return connections;
        }

        // Rysowanie linii połączeń rodzic-dziecko
        const parentChildConnections = createParentChildConnections();
        g.selectAll('.parent-child-connection')
            .data(parentChildConnections)
            .enter()
            .append('path')
            .attr('class', 'parent-child-connection')
            .attr('d', d => d.path)
            .attr('stroke', '#666')
            .attr('stroke-width', 2)
            .attr('fill', 'none')
            .attr('stroke-dasharray', '5,5');

        // Rysowanie linii małżeństw
        marriages.forEach((marriage, marriageId) => {
            const pos1 = nodePositions.get(marriage.person1.id);
            const pos2 = nodePositions.get(marriage.person2.id);
            
            if (pos1 && pos2 && Math.abs(pos1.y - pos2.y) < 10) {
                // Linia małżeństwa
                g.append('line')
                    .attr('class', 'marriage-line')
                    .attr('x1', pos1.x + NODE_WIDTH)
                    .attr('y1', pos1.y + NODE_HEIGHT/2)
                    .attr('x2', pos2.x)
                    .attr('y2', pos2.y + NODE_HEIGHT/2)
                    .attr('stroke', '#e74c3c')
                    .attr('stroke-width', 4);
                    
                // Symbol małżeństwa
                g.append('text')
                    .attr('x', (pos1.x + NODE_WIDTH + pos2.x) / 2)
                    .attr('y', pos1.y + NODE_HEIGHT/2 - 8)
                    .attr('text-anchor', 'middle')
                    .attr('font-size', '20px')
                    .attr('fill', '#e74c3c')
                    .text('💕');
            }
        });

        // Rysowanie węzłów osób
        const nodeGroups = g.selectAll('.person-node')
            .data(Array.from(nodePositions.entries()))
            .enter()
            .append('g')
            .attr('class', 'person-node')
            .attr('transform', d => `translate(${d[1].x}, ${d[1].y})`);

        // Prostokąty węzłów z kolorami według płci i statusu
        nodeGroups.append('rect')
            .attr('width', NODE_WIDTH)
            .attr('height', NODE_HEIGHT)
            .attr('rx', 10)
            .attr('ry', 10)
            .attr('fill', d => {
                const person = d[1].person;
                if (person.isRoot) return '#ffeb3b';
                return person.gender === 'M' ? '#e3f2fd' : '#fce4ec';
            })
            .attr('stroke', d => {
                const person = d[1].person;
                if (person.isRoot) return '#f57f17';
                return person.gender === 'M' ? '#1976d2' : '#c2185b';
            })
            .attr('stroke-width', d => d[1].person.isRoot ? 3 : 2)
            .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))');

        // Nazwiska
        nodeGroups.append('text')
            .attr('x', NODE_WIDTH / 2)
            .attr('y', 25)
            .attr('text-anchor', 'middle')
            .attr('font-size', '14px')
            .attr('font-weight', 'bold')
            .attr('fill', '#333')
            .text(d => d[1].person.name);

        // Daty życia
        nodeGroups.append('text')
            .attr('x', NODE_WIDTH / 2)
            .attr('y', 50)
            .attr('text-anchor', 'middle')
            .attr('font-size', '12px')
            .attr('fill', '#666')
            .text(d => {
                const person = d[1].person;
                const birth = person.birthYear;
                const death = person.deathYear;
                
                if (birth && death) return `${birth} - ${death}`;
                if (birth) return `ur. ${birth}`;
                if (death) return `zm. ${death}`;
                return '';
            });

        // Numer domu
        nodeGroups.append('text')
            .attr('x', NODE_WIDTH / 2)
            .attr('y', 70)
            .attr('text-anchor', 'middle')
            .attr('font-size', '11px')
            .attr('fill', '#888')
            .text(d => d[1].person.houseNumber ? `Dom: ${d[1].person.houseNumber}` : '');

        // Link do protokołu (dla osób z kluczem protokołu)
        nodeGroups.filter(d => d[1].person.protocolKey && !d[1].person.isRoot)
            .append('g')
            .attr('class', 'protocol-link')
            .style('cursor', 'pointer')
            .on('click', (event, d) => {
                window.open(`../wlasciciele/protokol.html?ownerId=${d[1].person.protocolKey}`, '_blank');
            })
            .append('text')
            .attr('x', NODE_WIDTH / 2)
            .attr('y', NODE_HEIGHT - 15)
            .attr('text-anchor', 'middle')
            .attr('font-size', '10px')
            .attr('fill', '#007bff')
            .attr('text-decoration', 'underline')
            .text('📜 Zobacz protokół');

        // Symbol płci
        nodeGroups.append('text')
            .attr('x', NODE_WIDTH - 20)
            .attr('y', 25)
            .attr('text-anchor', 'middle')
            .attr('font-size', '18px')
            .text(d => d[1].person.gender === 'M' ? '♂' : '♀')
            .attr('fill', d => d[1].person.gender === 'M' ? '#1976d2' : '#c2185b');

        // Tworzenie legendy
        const legend = g.append('g')
            .attr('class', 'legend')
            .attr('transform', `translate(${MARGIN}, ${MARGIN})`);

        // Tło legendy
        legend.append('rect')
            .attr('width', 350)
            .attr('height', LEGEND_HEIGHT - 20)
            .attr('fill', 'white')
            .attr('stroke', '#ccc')
            .attr('stroke-width', 2)
            .attr('rx', 8)
            .attr('ry', 8)
            .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))');

        // Tytuł legendy
        legend.append('text')
            .attr('x', 15)
            .attr('y', 20)
            .attr('font-size', '14px')
            .attr('font-weight', 'bold')
            .attr('fill', '#333')
            .text('Legenda:');

        // Elementy legendy
        const legendItems = [
            { text: '💕 - Małżeństwo', y: 35 },
            { text: '📜 - Kliknij aby zobaczyć protokół', y: 50 },
            { text: '♂ - Mężczyzna, ♀ - Kobieta', y: 65 },
            { text: 'Żółte tło - główna osoba protokołu', y: 80 }
        ];

        legendItems.forEach(item => {
            legend.append('text')
                .attr('x', 15)
                .attr('y', item.y)
                .attr('font-size', '11px')
                .attr('fill', '#555')
                .text(item.text);
        });

        // Dodanie SVG do kontenera
        treeContainer.appendChild(svg.node());

        // Pokazanie dialogu
        treeDialog.showModal();

        // Obsługa klawisza ESC
        function handleKeyPress(event) {
            if (event.key === 'Escape') {
                treeDialog.close();
                treeContainer.innerHTML = '';
                document.removeEventListener('keydown', handleKeyPress);
            }
        }
        document.addEventListener('keydown', handleKeyPress);
    };
    
    // === 8. FUNKCJE GENEROWANIA PDF ===
    
    /**
     * Generuje PDF z protokołu
     */
    const generatePDF = async () => {
    const ownerName = ownerData?.nazwa_wlasciciela || 'protokol';
    const fileName = `Protokol_${ownerName.replace(/[^\p{L}\p{N}_-]+/gu, '_')}.pdf`;

    // 1) Wejdź w tryb PDF (bez animacji/przezroczystości – wymaga CSS .pdf-export)
    document.body.classList.add('pdf-export');

    // 2) Ukryj elementy interaktywne i zapamiętaj ich stan
    const elementsToHide = document.querySelectorAll(
        '.action-btn, .header-btn, .switch-btn, .details-toggle-btn, .view-switcher, .map-links-section, .top-header, .app-footer'
    );
    const originalDisplays = new Map();
    elementsToHide.forEach(el => originalDisplays.set(el, el.style.display));
    elementsToHide.forEach(el => el.style.display = 'none');

    // 3) Odsłoń szczegóły działek; zapamiętaj które były ukryte
    const initiallyHiddenDetails = [...document.querySelectorAll('.plot-details-list.hidden')];
    document.querySelectorAll('.plot-details-list').forEach(el => el.classList.remove('hidden'));

    // 4) Pokaż odpowiednie widoki działek (tak jak na ekranie)
    const viewRzeczywiste = document.getElementById('view-rzeczywiste');
    const viewProtokol = document.getElementById('view-protokol');
    const wasRzeczywisteHidden = viewRzeczywiste?.classList.contains('hidden');
    const wasProtokolHidden = viewProtokol?.classList.contains('hidden');

    // Ustal, czy są różnice (użyj zmiennej z renderu, a jeśli jej nie ma – policz teraz)
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
        viewProtokol?.classList.add('hidden'); // nie pokazuj pustego „wg Protokołu”
    }

    // 5) Poczekaj aż styl/Fonty się zastosują
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    if (document.fonts?.ready) { try { await document.fonts.ready; } catch(e) {} }
    await new Promise(r => setTimeout(r, 50));

    // 6) Parametry PDF (białe tło, wysoka skala)
    const opt = {
        margin: 10,
        filename: fileName,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: {
        scale: 2,            // podnieś do 3, jeśli chcesz jeszcze ostrzej
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
        // 7) Przywróć stan strony (bez przeładowania)
        elementsToHide.forEach(el => el.style.display = originalDisplays.get(el) || '');
        initiallyHiddenDetails.forEach(el => el.classList.add('hidden'));

        if (wasRzeczywisteHidden) viewRzeczywiste?.classList.add('hidden'); else viewRzeczywiste?.classList.remove('hidden');
        if (wasProtokolHidden) viewProtokol?.classList.add('hidden'); else viewProtokol?.classList.remove('hidden');

        document.body.classList.remove('pdf-export');
    }
    };
    
    // === 9. FUNKCJE POMOCNICZE ===
    
    /**
     * Wypełnia pole wartością
     */
    const fillField = (element, value) => {
        if (element) {
            element.innerHTML = value || '—';
        }
    };
    
    /**
     * Pokazuje sekcję opcjonalną jeśli ma zawartość
     */
    const showOptionalSection = (sectionId, fieldId, value) => {
        if (value && value.trim()) {
            const section = document.getElementById(sectionId);
            const field = document.getElementById(fieldId);
            
            if (section && field) {
                section.classList.remove('hidden');
                field.innerHTML = generateFractionHTML(value);
            }
        }
    };
    
    /**
     * Formatuje datę
     */
    const formatDate = (dateString) => {
        if (!dateString) return '—';
        const date = new Date(dateString);
        return date.toLocaleDateString('pl-PL');
    };
    
    /**
     * Generuje HTML dla ułamków
     */
    const generateFractionHTML = (text) => {
        if (!text) return '';
        
        return text
            .replace(/(\d+)\/(\d+)/g, 
                `<span class="fraction">
                    <span class="numerator">$1</span>
                    <span class="denominator">$2</span>
                </span>`)
            .replace(/(?<!\/)\b(\d+)\b(?![\/<])/g, 
                `<span class="whole-number">$1</span>`);
    };
    
    /**
     * Wyświetla komunikat o błędzie
     */
    const showError = (message) => {
        document.body.innerHTML = `
            <div style="display: flex; justify-content: center; align-items: center; height: 100vh; font-family: Inter, sans-serif;">
                <div style="text-align: center; padding: 2rem; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                    <i class="fas fa-exclamation-triangle" style="font-size: 3rem; color: #e53e3e; margin-bottom: 1rem;"></i>
                    <h1 style="color: #2d3748; margin-bottom: 0.5rem;">${message}</h1>
                    <a href="../mapa/mapa.html" style="color: #667eea; text-decoration: none; font-weight: 500;">
                        ← Wróć do mapy
                    </a>
                </div>
            </div>
        `;
    };

    /**
     * Zarządza logiką zmiany i zapamiętywania motywu kolorystycznego.
     */
    const setupThemeLogic = () => {
        const themeToggleBtn = document.getElementById('themeToggleBtn');
        if (!themeToggleBtn) return;

        const icon = themeToggleBtn.querySelector('i');

        // Funkcja do zastosowania motywu i aktualizacji ikony
        const applyTheme = (theme) => {
            document.body.classList.toggle('dark-mode', theme === 'dark');
            if (icon) {
                icon.className = theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
            }
        };

        // Odczytanie zapisanego motywu i jego zastosowanie
        const savedTheme = localStorage.getItem('mapTheme') || 'light';
        applyTheme(savedTheme);

        // Listener do zmiany motywu przez użytkownika
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('mapTheme', newTheme);
            applyTheme(newTheme);
        });
    };
    /**
     * Zarządza trybem pełnoekranowym.
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

    // === 10. INICJALIZACJA APLIKACJI ===
    init();
});