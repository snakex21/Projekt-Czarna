/**
 * Plik: stats-script.js
 * Opis: Skrypt obsługujący stronę statystyk w stylu mapy katastralnej
 */

// =============================================================================
// INICJALIZACJA
// =============================================================================
document.addEventListener('DOMContentLoaded', () => {
    // Synchronizacja motywu
    initThemeSync();
    
    // Inicjalizacja UI
    initUI();
    
    // Ładowanie danych
    loadStatistics();
    
    // Animacje liczników
    initCounters();
    
    // Skróty klawiszowe
    initKeyboardShortcuts();
});

// =============================================================================
// SYNCHRONIZACJA MOTYWU
// =============================================================================
function initThemeSync() {
    // Odczyt motywu z localStorage (używamy klucza 'mapTheme' dla spójności)
    const savedTheme = localStorage.getItem('mapTheme') || 'light';
    applyTheme(savedTheme);

    // Nasłuchiwanie zmian w innych zakładkach
    window.addEventListener('storage', (e) => {
        if (e.key === 'mapTheme') {
            applyTheme(e.newValue);
        }
    });

    // Przycisk zmiany motywu
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            // Zapisz w localStorage (używamy klucza 'mapTheme')
            localStorage.setItem('mapTheme', newTheme);

            // Zastosuj motyw
            applyTheme(newTheme);

            // Pokaż powiadomienie
            showToast('success', 'Motyw zmieniony', `Przełączono na tryb ${newTheme === 'dark' ? 'ciemny' : 'jasny'}`);
        });
    }
}

function applyTheme(theme) {
    const isDark = theme === 'dark';
    document.body.classList.toggle('dark-mode', isDark);

    // Zmień ikonę
    const icon = document.querySelector('#theme-toggle i');
    if (icon) {
        icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
    }
}

// =============================================================================
// INICJALIZACJA UI
// =============================================================================
function initUI() {
    // Zakładki
    initTabs();
    
    // Wyszukiwarka
    initSearch();
    
    // Przyciski akcji
    initActionButtons();
    
    // Modal pomocy
    initHelpModal();
    
    // Pełny ekran
    initFullscreen();
}

function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanels = document.querySelectorAll('.tab-panel');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.dataset.tab;
            
            // Usuń aktywne klasy
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanels.forEach(panel => panel.classList.remove('active'));
            
            // Dodaj aktywne klasy
            button.classList.add('active');
            document.getElementById(targetTab).classList.add('active');
            
            // Załaduj dane dla zakładki jeśli potrzeba
            if (targetTab === 'timeline' && !button.dataset.loaded) {
                loadTimeline();
                button.dataset.loaded = 'true';
            }
        });
    });
}

function initSearch() {
    const searchToggle = document.getElementById('search-toggle');
    const searchBar = document.getElementById('search-bar');
    const searchClose = document.getElementById('search-close');
    const searchInput = document.getElementById('global-search');

    searchToggle?.addEventListener('click', () => {
        searchBar.classList.toggle('active');
        if (searchBar.classList.contains('active')) {
            searchInput.focus();
        }
    });

    searchClose?.addEventListener('click', () => {
        searchBar.classList.remove('active');
        searchInput.value = '';
        performGlobalSearch(''); // Wyczyść wyszukiwanie
    });

    searchInput?.addEventListener('input', (e) => {
        performGlobalSearch(e.target.value);
    });
}

function performGlobalSearch(query) {
    const normalizedQuery = query.trim().toLowerCase();
    const activePanel = document.querySelector('.tab-panel.active');
    if (!activePanel) return;

    // Najpierw usuń poprzednie podświetlenia i komunikaty
    clearHighlights(activePanel);
    const existingNoResults = activePanel.querySelector('.no-results-message');
    if (existingNoResults) existingNoResults.remove();

    // Jeśli zapytanie jest puste, pokaż wszystko i zakończ
    if (!normalizedQuery) {
        activePanel.querySelectorAll('.ranking-item, .timeline-item, .demo-year-card').forEach(item => {
            item.style.display = '';
        });
        return;
    }

    const searchableItems = activePanel.querySelectorAll('.ranking-item, .timeline-item, .demo-year-card');
    let foundSomething = false;

    searchableItems.forEach(item => {
        const itemText = item.textContent.toLowerCase();
        if (itemText.includes(normalizedQuery)) {
            item.style.display = '';
            highlightText(item, normalizedQuery);
            foundSomething = true;
        } else {
            item.style.display = 'none';
        }
    });

    // Pokaż komunikat, jeśli nic nie znaleziono
    if (!foundSomething) {
        const noResultsMessage = document.createElement('div');
        noResultsMessage.className = 'no-results-message';
        noResultsMessage.innerHTML = `<i class="fas fa-search"></i><h3>Brak wyników</h3><p>Nie znaleziono wyników dla frazy "${query}"</p>`;
        
        // Znajdź odpowiedni kontener do wstawienia komunikatu
        const targetContainer = activePanel.querySelector('.ranking-list') || activePanel.querySelector('.timeline') || activePanel.querySelector('.demo-cards-grid') || activePanel;
        targetContainer.appendChild(noResultsMessage);
    }
}

function highlightText(element, query) {
    const regex = new RegExp(query, 'gi');
    
    // Używamy rekurencyjnej funkcji, aby ominąć tagi HTML i podświetlać tylko tekst
    function walkAndHighlight(node) {
        if (node.nodeType === 3) { // Węzeł tekstowy
            const text = node.textContent;
            const match = text.match(regex);
            if (match) {
                const span = document.createElement('span');
                span.innerHTML = text.replace(regex, (match) => `<mark class="search-highlight">${match}</mark>`);
                node.parentNode.replaceChild(span, node);
            }
        } else if (node.nodeType === 1 && node.nodeName !== 'MARK') { // Węzeł elementu
            Array.from(node.childNodes).forEach(walkAndHighlight);
        }
    }
    
    walkAndHighlight(element);
}

function clearHighlights(container) {
    const highlights = container.querySelectorAll('mark.search-highlight');
    highlights.forEach(mark => {
        // Zastępujemy element <mark> jego własną zawartością tekstową
        // To jest bezpieczniejsze niż manipulowanie węzłami rodzica.
        if (mark.parentNode) {
            mark.outerHTML = mark.innerHTML;
        }
    });

    // Po usunięciu wszystkich <mark>, normalizujemy strukturę,
    // aby połączyć sąsiadujące ze sobą węzły tekstowe.
    container.normalize();
}

function initActionButtons() {
    // Eksport wykresów
    document.getElementById('export-chart1')?.addEventListener('click', () => {
        exportChart('pieChart');
    });
    
    document.getElementById('export-chart2')?.addEventListener('click', () => {
        exportChart('barChart');
    });
    
    // Pokaż na mapie
    document.getElementById('show-on-map')?.addEventListener('click', () => {
        const ownership = document.querySelector('input[name="ownership"]:checked').value;
        const category = document.getElementById('category-filter').value;
        
        // Pobierz top 10 z aktualnego rankingu
        const topOwners = getTop10Owners(ownership, category);
        const ownerKeys = topOwners.map(o => o.unikalny_klucz).join(',');
        
        window.location.href = `../mapa/mapa.html?highlightTopOwners=${encodeURIComponent(ownerKeys)}&ownership=${ownership}`;
    });
    
    // Narzędzia analizy
    document.getElementById('export-btn')?.addEventListener('click', exportToExcel);
    document.getElementById('print-btn')?.addEventListener('click', printReport);
    document.getElementById('share-btn')?.addEventListener('click', shareReport);
    
    // Feedback
    document.getElementById('feedback-btn')?.addEventListener('click', () => {
        showToast('info', 'Opinie', 'Funkcja opinii będzie dostępna wkrótce');
    });
}

function initHelpModal() {
    const helpBtn = document.getElementById('help-btn');
    const modal = document.getElementById('help-modal');
    const closeBtn = modal?.querySelector('.modal-close');
    
    helpBtn?.addEventListener('click', () => {
        modal.classList.add('active');
    });
    
    closeBtn?.addEventListener('click', () => {
        modal.classList.remove('active');
    });
    
    modal?.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
}

function initFullscreen() {
    const fullscreenBtn = document.getElementById('fullscreen-toggle');
    
    fullscreenBtn?.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
            fullscreenBtn.querySelector('i').className = 'fas fa-compress';
        } else {
            document.exitFullscreen();
            fullscreenBtn.querySelector('i').className = 'fas fa-expand';
        }
    });
}

// =============================================================================
// ŁADOWANIE DANYCH
// =============================================================================
let statsData = null;

async function loadStatistics() {
    try {
        const response = await fetch('/api/stats');
        statsData = await response.json();
        
        // Aktualizuj liczniki
        updateCounters(statsData.general_stats);
        
        // Wykresy
        createCharts(statsData);
        
        // Rankingi
        loadRankings(statsData);
        
        // Demografia
        loadDemographics(statsData.demografia);
        
        // Aktywność
        renderActivityCalendar(statsData.protocols_per_day);

        // NOWA SEKCJA: Statystyki genealogiczne
        loadGenealogyStats(statsData);
    
        // Analiza
        loadInsights(statsData);
        
    } catch (error) {
        console.error('Błąd ładowania statystyk:', error);
        showToast('error', 'Błąd', 'Nie udało się załadować danych');
    }
}

// =============================================================================
// LICZNIKI ANIMOWANE
// =============================================================================
function initCounters() {
    const counters = document.querySelectorAll('.counter');
    
    const observerOptions = {
        threshold: 0.5
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const counter = entry.target;
                const target = parseInt(counter.dataset.target);
                animateCounter(counter, target);
                observer.unobserve(counter);
            }
        });
    }, observerOptions);
    
    counters.forEach(counter => observer.observe(counter));
}

function animateCounter(element, target) {
    let current = 0;
    const increment = target / 50;
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target.toLocaleString('pl-PL');
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current).toLocaleString('pl-PL');
        }
    }, 30);
}

function updateCounters(stats) {
    // Główne liczniki
    const ownersCounter = document.querySelector('#total-owners .counter');
    const plotsCounter = document.querySelector('#total-plots .counter');
    
    if (ownersCounter) {
        ownersCounter.dataset.target = stats.total_owners;
        animateCounter(ownersCounter, stats.total_owners);
    }
    
    if (plotsCounter) {
        plotsCounter.dataset.target = stats.total_plots;
        animateCounter(plotsCounter, stats.total_plots);
    }
}

// =============================================================================
// WYKRESY
// =============================================================================
let charts = {};

function createCharts(data) {
    // Wykres kołowy - struktura własności
    const pieCtx = document.getElementById('pieChart')?.getContext('2d');
    if (pieCtx && data.category_counts) {
        const counts = data.category_counts;
        const inneCount = (counts.droga || 0) + (counts.rzeka || 0) + (counts.obiekt_specjalny || 0);

        charts.pie = new Chart(pieCtx, {
            type: 'doughnut',
            data: {
                labels: ['Rolne', 'Budowlane', 'Lasy', 'Pastwiska', 'Inne'],
                datasets: [{
                    data: [
                        counts.rolna || 0,
                        counts.budowlana || 0,
                        counts.las || 0,
                        counts.pastwisko || 0,
                        inneCount
                    ],
                    backgroundColor: [
                        '#10b981',
                        '#f59e0b',
                        '#3b82f6',
                        '#8b5cf6',
                        '#ef4444'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    // Wykres słupkowy - Top 10 właścicieli
    const barCtx = document.getElementById('barChart')?.getContext('2d');
    if (barCtx && data.rankings_real.all_plots) {
        const top10 = data.rankings_real.all_plots.slice(0, 10).reverse(); // Odwracamy, by największy był na górze
        
        charts.bar = new Chart(barCtx, {
            type: 'bar',
            data: {
                labels: top10.map(o => o.nazwa_wlasciciela),
                datasets: [{
                    label: 'Liczba działek',
                    data: top10.map(o => o.plot_count),
                    backgroundColor: 'rgba(102, 126, 234, 0.8)',
                    borderColor: '#667eea',
                    borderWidth: 1,
                    borderRadius: 5
                }]
            },
            options: {
                indexAxis: 'y', // Ustawienie osi Y jako głównej osi dla etykiet
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            title: (tooltipItems) => {
                                // Pełna nazwa w podpowiedzi
                                return tooltipItems[0].label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Liczba działek'
                        }
                    },
                    y: {
                        ticks: {
                            autoSkip: false, // Pokaż wszystkie etykiety
                            callback: function(value, index, values) {
                                const label = this.getLabelForValue(value);
                                // Skracaj etykiety na osi, jeśli są za długie
                                return (label.length > 25) ? label.substring(0, 22) + '...' : label;
                            }
                        }
                    }
                }
            }
        });
    }
}

// =============================================================================
// RANKINGI
// =============================================================================
function loadRankings(data) {
    const container = document.getElementById('ranking-list');
    if (!container) return;
    
    // Domyślnie pokaż ranking rzeczywisty, wszystkie kategorie
    displayRanking(data.rankings_real.all_plots || [], container);
    
    // Obsługa filtrów
    document.querySelectorAll('input[name="ownership"]').forEach(radio => {
        radio.addEventListener('change', () => {
            filterRankings();
        });
    });
    
    document.getElementById('category-filter')?.addEventListener('change', filterRankings);
}

function displayRanking(rankingData, container) {
    container.innerHTML = rankingData.slice(0, 50).map((owner, index) => {
        const position = index + 1;
        let positionClass = '';
        if (position === 1) positionClass = 'gold';
        else if (position === 2) positionClass = 'silver';
        else if (position === 3) positionClass = 'bronze';
        
        return `
            <a href="../wlasciciele/protokol.html?ownerId=${owner.unikalny_klucz}" class="ranking-item">
                <div class="ranking-position ${positionClass}">${position}</div>
                <div class="ranking-info">
                    <div class="ranking-name">${owner.nazwa_wlasciciela}</div>
                    <div class="ranking-meta">Protokół nr ${owner.numer_protokolu || 'Brak'}</div>
                </div>
                <div class="ranking-value">${owner.plot_count}</div>
            </a>
        `;
    }).join('');
}

function filterRankings() {
    if (!statsData) return;

    const ownership = document.querySelector('input[name="ownership"]:checked').value;
    const category = document.getElementById('category-filter').value;
    const container = document.getElementById('ranking-list');
    
    const dataSet = ownership === 'real' ? statsData.rankings_real : statsData.rankings_protocol;
    let rankingData = category === 'all' ? dataSet.all_plots : dataSet[category];

    if (!rankingData) {
        rankingData = [];
    }
    
    displayRanking(rankingData, container);

    // Po przefiltrowaniu, zastosuj ponownie wyszukiwanie tekstowe
    const searchQuery = document.getElementById('global-search').value;
    performGlobalSearch(searchQuery);
}

// =============================================================================
// OŚ CZASU
// =============================================================================
function loadTimeline() {
    if (!statsData?.protocols_per_day) return;

    const container = document.getElementById('timeline-content');
    container.innerHTML = statsData.protocols_per_day.map(item => {
        const date = new Date(item.protocol_date);
        const formattedDate = date.toLocaleDateString('pl-PL', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });

        // Tworzenie listy właścicieli jako linków (bez otwierania w nowej karcie)
        const ownersListHtml = item.owners.map(owner => `
            <li>
                <a href="../wlasciciele/protokol.html?ownerId=${owner.unikalny_klucz}">
                    ${owner.nazwa_wlasciciela}
                </a>
            </li>
        `).join('');

        return `
            <div class="timeline-item">
                <div class="timeline-marker"></div>
                <div class="timeline-content">
                    <div class="timeline-date">${formattedDate}</div>
                    <details>
                        <summary class="timeline-title">${item.protocol_count} protokołów (kliknij, aby rozwinąć)</summary>
                        <ul class="timeline-owners-list">${ownersListHtml}</ul>
                    </details>
                </div>
            </div>
        `;
    }).join('');
}

// =============================================================================
// DEMOGRAFIA
// =============================================================================
function loadDemographics(demografiaData) {
    if (!demografiaData || demografiaData.length === 0) return;
    
    // Wykres demograficzny
    const ctx = document.getElementById('demographicsChart')?.getContext('2d');
    if (ctx) {
        charts.demographics = new Chart(ctx, {
            type: 'line',
            data: {
                labels: demografiaData.map(d => d.rok),
                datasets: [{
                    label: 'Populacja ogółem',
                    data: demografiaData.map(d => d.populacja_ogolem || 0),
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true
                    }
                }
            }
        });
    }
    
    // Karty demograficzne
    const container = document.getElementById('demo-cards');
    if (container) {
        container.innerHTML = demografiaData.map(entry => `
            <div class="demo-card">
                <div class="demo-year">${entry.rok}</div>
                <div class="demo-population">Populacja: ${entry.populacja_ogolem || 'N/A'}</div>
                ${entry.katolicy ? `<div>Katolicy: ${entry.katolicy}</div>` : ''}
                ${entry.zydzi ? `<div>Żydzi: ${entry.zydzi}</div>` : ''}
                ${entry.opis ? `<div class="demo-note">${entry.opis}</div>` : ''}
            </div>
        `).join('');
    }
}

// =============================================================================
// MAPA AKTYWNOŚCI
// =============================================================================
function renderActivityCalendar(protocolsData) {
    if (!protocolsData || protocolsData.length === 0) return;

    const container = document.getElementById('activity-calendar-container');
    if (!container) return;

    // Przetwarzanie danych
    const dataMap = new Map();
    protocolsData.forEach(item => {
        const date = new Date(item.protocol_date).toISOString().split('T')[0];
        dataMap.set(date, item.protocol_count);
    });

    const maxCount = Math.max(...dataMap.values());
    const startDate = new Date(protocolsData[0].protocol_date);
    const endDate = new Date(protocolsData[protocolsData.length - 1].protocol_date);

    // Tworzenie siatki kalendarza
    let calendarHtml = '<div class="activity-calendar">';
    let currentDate = new Date(startDate);
    currentDate.setDate(startDate.getDate() - startDate.getDay());

    while (currentDate <= endDate) {
        const dateString = currentDate.toISOString().split('T')[0];
        const count = dataMap.get(dateString) || 0;
        let level = 0;
        if (count > 0) {
            level = Math.ceil((count / maxCount) * 4);
        }
        const tooltipText = `${currentDate.toLocaleDateString('pl-PL')}: ${count} protokołów`;
        
        // Usunęliśmy statyczny tooltip z HTML
        calendarHtml += `<div class="day-cell" data-tooltip="${tooltipText}" data-level="${level}"></div>`;
        currentDate.setDate(currentDate.getDate() + 1);
    }
    calendarHtml += '</div>';

    // Tworzenie legendy
    const legendHtml = `
        <div class="activity-legend">
            <span>Mniej</span>
            <div class="legend-item">
                <div class="day-cell" data-level="1"></div><div class="day-cell" data-level="2"></div><div class="day-cell" data-level="3"></div><div class="day-cell" data-level="4"></div>
            </div>
            <span>Więcej</span>
        </div>
    `;

    container.innerHTML = calendarHtml + legendHtml;

    // Logika dynamicznego tooltipa
    const calendar = container.querySelector('.activity-calendar');
    let tooltip = document.getElementById('calendar-tooltip');
    
    // Stwórz element tooltipa, jeśli jeszcze nie istnieje
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'calendar-tooltip';
        document.body.appendChild(tooltip);
    }
    
    calendar.addEventListener('mouseover', (e) => {
        if (e.target.classList.contains('day-cell') && e.target.dataset.tooltip) {
            const cell = e.target;
            tooltip.textContent = cell.dataset.tooltip;
            tooltip.classList.add('visible');

            const cellRect = cell.getBoundingClientRect();
            const tooltipRect = tooltip.getBoundingClientRect();

            // Pozycjonuj nad komórką
            let top = cellRect.top - tooltipRect.height - 8;
            let left = cellRect.left + (cellRect.width / 2) - (tooltipRect.width / 2);

            // Sprawdź, czy nie wychodzi poza lewą/prawą krawędź okna
            if (left < 0) left = 5;
            if (left + tooltipRect.width > window.innerWidth) left = window.innerWidth - tooltipRect.width - 5;
            
            tooltip.style.left = `${left}px`;
            tooltip.style.top = `${top}px`;
        }
    });

    calendar.addEventListener('mouseout', (e) => {
        if (e.target.classList.contains('day-cell')) {
            tooltip.classList.remove('visible');
        }
    });
}

// =============================================================================
// ANALIZA I WNIOSKI
// =============================================================================
function loadInsights(data) {
    // Mini statystyki
    const counts = data.category_counts || {};
    document.getElementById('stat-forests').textContent = counts.las || 0;
    document.getElementById('stat-rivers').textContent = counts.rzeka || 0;
    document.getElementById('stat-buildings').textContent = counts.budynek || 0;
    document.getElementById('stat-chapels').textContent = counts.kapliczka || 0;

    // Największy właściciel
    if (data.rankings_real.all_plots?.[0]) {
        const biggest = data.rankings_real.all_plots[0];
        document.getElementById('biggest-owner').textContent = 
            `${biggest.nazwa_wlasciciela} - ${biggest.plot_count} działek`;
    }
    
    // Trend własności
    document.getElementById('ownership-trend').textContent = 
        `${data.general_stats.total_owners} właścicieli kontroluje ${data.general_stats.total_plots} działek`;
    
    // Koncentracja
    const top10Count = data.rankings_real.all_plots?.slice(0, 10)
        .reduce((sum, o) => sum + o.plot_count, 0) || 0;
    const concentration = ((top10Count / data.general_stats.total_plots) * 100).toFixed(1);
    document.getElementById('concentration').textContent = 
        `Top 10 właścicieli posiada ${concentration}% wszystkich działek`;
}

// =============================================================================
// STATYSTYKI GENEALOGICZNE (NOWA SEKCJA)
// =============================================================================
function loadGenealogyStats(data) {
    const stats = data.genealogy_stats;
    if (!stats) return;

    // Aktualizacja kluczowych wskaźników
    const totalPeopleEl = document.getElementById('stat-total-people');
    const genderRatioEl = document.getElementById('stat-gender-ratio');

    if (totalPeopleEl) totalPeopleEl.textContent = stats.total_people;
    if (genderRatioEl) genderRatioEl.textContent = `${stats.male_count} / ${stats.female_count}`;

    // Renderowanie listy najpopularniejszych nazwisk
    const surnamesContainer = document.getElementById('top-surnames-list');
    if (surnamesContainer) {
        surnamesContainer.innerHTML = stats.top_surnames.map((surname, index) => {
            const position = index + 1;
            let positionClass = '';
            if (position === 1) positionClass = 'gold';
            else if (position === 2) positionClass = 'silver';
            else if (position === 3) positionClass = 'bronze';

            return `
                <div class="ranking-item">
                    <div class="ranking-position ${positionClass}">${position}</div>
                    <div class="ranking-info">
                        <div class="ranking-name">${surname.name}</div>
                    </div>
                    <div class="surname-count">${surname.count}</div>
                </div>
            `;
        }).join('');
    }

    // Tworzenie wykresu urodzeń wg dekad
    const chartCtx = document.getElementById('genealogy-births-chart')?.getContext('2d');
    if (chartCtx) {
        if (charts.genealogyBirths) {
            charts.genealogyBirths.destroy();
        }

        const gradient = chartCtx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(118, 75, 162, 0.6)');
        gradient.addColorStop(1, 'rgba(102, 126, 234, 0.1)');

        charts.genealogyBirths = new Chart(chartCtx, {
            type: 'bar',
            data: {
                labels: stats.births_by_decade.labels,
                datasets: [{
                    label: 'Liczba urodzeń',
                    data: stats.births_by_decade.data,
                    backgroundColor: gradient,
                    borderColor: '#764ba2',
                    borderWidth: 2,
                    borderRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Liczba osób'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Dekada'
                        }
                    }
                }
            }
        });
    }
}

// =============================================================================
// NARZĘDZIA
// =============================================================================
function exportChart(chartId) {
    const chart = charts[chartId === 'pieChart' ? 'pie' : 'bar'];
    if (!chart) return;
    
    const url = chart.toBase64Image();
    const link = document.createElement('a');
    link.download = `wykres-${chartId}-${Date.now()}.png`;
    link.href = url;
    link.click();
    
    showToast('success', 'Eksport', 'Wykres został pobrany');
}

function exportToExcel() {
    if (!statsData) {
        showToast('error', 'Błąd', 'Dane nie zostały jeszcze załadowane.');
        return;
    }

    try {
        // Pokaż informację o rozpoczęciu
        showToast('info', 'Eksport', 'Rozpoczęto generowanie pliku Excel...');

        // 1. Utwórz nowy skoroszyt
        const wb = XLSX.utils.book_new();

        // 2. Przygotuj dane dla każdego arkusza
        
        // --- Arkusz 1: Podsumowanie ---
        const summaryData = [
            ["Kluczowa Statystyka", "Wartość"],
            ["Całkowita liczba właścicieli", statsData.general_stats.total_owners],
            ["Całkowita liczba działek", statsData.general_stats.total_plots],
            ...Object.entries(statsData.category_counts).map(([key, value]) => [`Liczba działek - ${key}`, value])
        ];
        const wsSummary = XLSX.utils.aoa_to_sheet(summaryData);
        XLSX.utils.book_append_sheet(wb, wsSummary, "Podsumowanie");
        
        // --- Arkusz 2: Rankingi Rzeczywiste ---
        let realRankingsData = [];
        for (const category in statsData.rankings_real) {
            statsData.rankings_real[category].forEach((owner, index) => {
                realRankingsData.push({
                    "Kategoria": category,
                    "Pozycja": index + 1,
                    "Właściciel": owner.nazwa_wlasciciela,
                    "Numer Protokołu": owner.numer_protokolu,
                    "Liczba Działek": owner.plot_count
                });
            });
        }
        const wsRealRankings = XLSX.utils.json_to_sheet(realRankingsData);
        XLSX.utils.book_append_sheet(wb, wsRealRankings, "Rankingi Rzeczywiste");

        // --- Arkusz 3: Rankingi z Protokołu ---
        let protocolRankingsData = [];
        for (const category in statsData.rankings_protocol) {
            statsData.rankings_protocol[category].forEach((owner, index) => {
                protocolRankingsData.push({
                    "Kategoria": category,
                    "Pozycja": index + 1,
                    "Właściciel": owner.nazwa_wlasciciela,
                    "Numer Protokołu": owner.numer_protokolu,
                    "Liczba Działek": owner.plot_count
                });
            });
        }
        const wsProtocolRankings = XLSX.utils.json_to_sheet(protocolRankingsData);
        XLSX.utils.book_append_sheet(wb, wsProtocolRankings, "Rankingi z Protokołu");

        // --- Arkusz 4: Demografia ---
        const wsDemographics = XLSX.utils.json_to_sheet(statsData.demografia);
        XLSX.utils.book_append_sheet(wb, wsDemographics, "Demografia");

        // --- Arkusz 5: Genealogia ---
        const genealogyData = [
            ["Najpopularniejsze Nazwiska"],
            ["Pozycja", "Nazwisko", "Liczba wystąpień"],
            ...statsData.genealogy_stats.top_surnames.map((s, i) => [i + 1, s.name, s.count]),
            [], // Pusta linia jako separator
            ["Urodzenia wg Dekad"],
            ["Dekada", "Liczba urodzeń"],
            ...statsData.genealogy_stats.births_by_decade.labels.map((label, i) => [
                label, statsData.genealogy_stats.births_by_decade.data[i]
            ])
        ];
        const wsGenealogy = XLSX.utils.aoa_to_sheet(genealogyData);
        XLSX.utils.book_append_sheet(wb, wsGenealogy, "Genealogia");

        // --- Arkusz 6: Aktywność Spisowa ---
        const activityData = statsData.protocols_per_day.map(day => ({
            "Data": new Date(day.protocol_date).toLocaleDateString('pl-PL'),
            "Liczba protokołów": day.protocol_count,
            "Właściciele": day.owners.map(o => o.nazwa_wlasciciela).join(', ')
        }));
        const wsActivity = XLSX.utils.json_to_sheet(activityData);
        XLSX.utils.book_append_sheet(wb, wsActivity, "Aktywność Spisowa");

        // 3. Wygeneruj i pobierz plik
        const today = new Date().toISOString().slice(0, 10);
        const fileName = `statystyki_gmina_czarna_${today}.xlsx`;
        XLSX.writeFile(wb, fileName);
        
        showToast('success', 'Eksport zakończony', `Plik ${fileName} został pobrany.`);

    } catch (error) {
        console.error("Błąd podczas eksportu do Excel:", error);
        showToast('error', 'Błąd eksportu', 'Wystąpił nieoczekiwany problem.');
    }
}

function printReport() {
    window.print();
    showToast('info', 'Drukowanie', 'Przygotowano raport do druku');
}

function shareReport() {
    if (navigator.share) {
        navigator.share({
            title: 'Statystyki Gminy Czarna',
            text: 'Zobacz statystyki właścicieli gruntów z XIX wieku',
            url: window.location.href
        });
    } else {
        // Kopiuj link
        navigator.clipboard.writeText(window.location.href);
        showToast('success', 'Udostępnianie', 'Link skopiowany do schowka');
    }
}

function getTop10Owners(ownership, category) {
    const data = ownership === 'real' ? statsData.rankings_real : statsData.rankings_protocol;
    const rankingData = category === 'all' ? data.all_plots : data[category];
    return rankingData?.slice(0, 10) || [];
}

// =============================================================================
// POWIADOMIENIA TOAST
// =============================================================================
function showToast(type, title, message) {
    const container = document.getElementById('toast-container');
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-icon">
            <i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'times' : 'info'}"></i>
        </div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'toastOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// =============================================================================
// SKRÓTY KLAWISZOWE
// =============================================================================
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+F - Wyszukiwanie
        if (e.ctrlKey && e.key === 'f') {
            e.preventDefault();
            document.getElementById('search-toggle')?.click();
        }
        
        // D - Tryb ciemny
        if (e.key === 'd' && !e.target.matches('input, textarea')) {
            document.getElementById('theme-toggle')?.click();
        }
        
        // Esc - Zamknij modal/wyszukiwanie
        if (e.key === 'Escape') {
            document.querySelector('.modal.active')?.classList.remove('active');
            document.getElementById('search-bar')?.classList.remove('active');
        }
    });
}

// =============================================================================
// ULEPSZONA FUNKCJA DEMOGRAFII
// =============================================================================
function loadDemographics(demografiaData) {
    if (!demografiaData || demografiaData.length === 0) {
        document.getElementById('demographics').innerHTML = `
            <div class="no-data-message">
                <i class="fas fa-inbox fa-3x"></i>
                <h3>Brak danych demograficznych</h3>
                <p>Dane demograficzne nie są jeszcze dostępne dla tego okresu.</p>
            </div>
        `;
        return;
    }
    
    // Sortuj dane chronologicznie
    demografiaData.sort((a, b) => a.rok - b.rok);
    
    // Oblicz statystyki
    const firstYear = demografiaData[0];
    const lastYear = demografiaData[demografiaData.length - 1];
    const growthPercent = ((lastYear.populacja_ogolem - firstYear.populacja_ogolem) / firstYear.populacja_ogolem * 100).toFixed(1);
    const yearSpan = lastYear.rok - firstYear.rok;
    
    // Aktualizuj podsumowanie
    document.getElementById('demo-growth').textContent = growthPercent > 0 ? `+${growthPercent}%` : `${growthPercent}%`;
    document.getElementById('demo-years').textContent = `${yearSpan} lat`;
    
    // Główny wykres
    createDemographicsChart(demografiaData);
    
    // Timeline wydarzeń
    createDemographicsTimeline(demografiaData);
    
    // Karty szczegółowe
    createDemographicsCards(demografiaData);
    
    // Analiza porównawcza
    createComparisonAnalysis(demografiaData);
}

function createDemographicsChart(data) {
    const ctx = document.getElementById('demographicsChart')?.getContext('2d');
    if (!ctx) return;
    
    // Przygotuj dane dla wykresów
    const years = data.map(d => d.rok);
    const totalPopulation = data.map(d => d.populacja_ogolem || 0);
    const catholics = data.map(d => d.katolicy || 0);
    const jewish = data.map(d => d.zydzi || 0);
    const others = data.map(d => d.inni || 0);
    
    // Usuń poprzedni wykres jeśli istnieje
    if (charts.demographics) {
        charts.demographics.destroy();
    }
    
    charts.demographics = new Chart(ctx, {
        type: 'line',
        data: {
            labels: years,
            datasets: [
                {
                    label: 'Populacja ogółem',
                    data: totalPopulation,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    pointBackgroundColor: '#667eea',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                },
                {
                    label: 'Katolicy',
                    data: catholics,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: false,
                    hidden: catholics.every(v => v === 0),
                    pointRadius: 5,
                    pointHoverRadius: 7
                },
                {
                    label: 'Żydzi',
                    data: jewish,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: false,
                    hidden: jewish.every(v => v === 0),
                    pointRadius: 5,
                    pointHoverRadius: 7
                },
                {
                    label: 'Inni',
                    data: others,
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: false,
                    hidden: others.every(v => v === 0),
                    pointRadius: 5,
                    pointHoverRadius: 7
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 15
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        title: (context) => `Rok ${context[0].label}`,
                        label: (context) => {
                            const label = context.dataset.label;
                            const value = context.parsed.y;
                            const percentage = totalPopulation[context.dataIndex] > 0 
                                ? ((value / totalPopulation[context.dataIndex]) * 100).toFixed(1)
                                : 0;
                            return `${label}: ${value} osób${percentage > 0 ? ` (${percentage}%)` : ''}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Liczba mieszkańców'
                    },
                    grid: {
                        drawBorder: false
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Rok'
                    },
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

function createDemographicsTimeline(data) {
    const container = document.getElementById('demo-timeline-track');
    if (!container) return;

    // Funkcja pomocnicza do wybierania ikony na podstawie opisu
    const getIconForEvent = (description) => {
        const desc = description.toLowerCase();
        if (desc.includes('kolei')) return '🚂';
        if (desc.includes('budow')) return '🏗️';
        if (desc.includes('wojn')) return '⚔️';
        if (desc.includes('epidemi') || desc.includes('chorob')) return '🏥';
        return '📅'; // Domyślna ikona
    };

    // Dynamiczne tworzenie listy wydarzeń z danych demograficznych
    const events = data
        .filter(entry => entry.opis && entry.opis.trim() !== '')
        .map(entry => ({
            year: entry.rok,
            text: entry.opis,
            icon: getIconForEvent(entry.opis),
            major: true
        }));

    if (events.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">Brak zdefiniowanych kluczowych wydarzeń w danych.</p>';
        return;
    }

    // Jeśli jest tylko jedno wydarzenie, wyśrodkuj je
    if (events.length === 1) {
        const event = events[0];
        container.innerHTML = `
            <div class="timeline-event ${event.major ? 'major' : ''}" 
                 style="left: 50%;">
                <span>${event.icon}</span>
                <span>${event.year}</span>
                <div class="timeline-event-tooltip">
                    ${event.text}
                </div>
            </div>
        `;
        return;
    }

    const minEventYear = Math.min(...events.map(e => e.year));
    const maxEventYear = Math.max(...events.map(e => e.year));
    const yearRange = (maxEventYear - minEventYear) > 0 ? (maxEventYear - minEventYear) : 1;

    container.innerHTML = events
        .map(event => {
            const positionPercent = ((event.year - minEventYear) / yearRange) * 100;

            return `
                <div class="timeline-event ${event.major ? 'major' : ''}" 
                     style="left: ${positionPercent}%">
                    <span>${event.icon}</span>
                    <span>${event.year}</span>
                    <div class="timeline-event-tooltip">
                        ${event.text}
                    </div>
                </div>
            `;
        }).join('');
}

function createDemographicsCards(data) {
    const container = document.getElementById('demo-cards');
    if (!container) return;
    
    container.innerHTML = data.map((entry, index) => {
        // Oblicz zmiany
        let changePercent = 0;
        let changeType = '';
        if (index > 0 && entry.populacja_ogolem && data[index - 1].populacja_ogolem) {
            changePercent = ((entry.populacja_ogolem - data[index - 1].populacja_ogolem) / data[index - 1].populacja_ogolem * 100).toFixed(1);
            changeType = changePercent > 0 ? 'positive' : 'negative';
        }
        
        // Oblicz procenty wyznań
        const total = entry.populacja_ogolem || 1;
        const catholicPercent = entry.katolicy ? (entry.katolicy / total * 100).toFixed(1) : 0;
        const jewishPercent = entry.zydzi ? (entry.zydzi / total * 100).toFixed(1) : 0;
        const otherPercent = entry.inni ? (entry.inni / total * 100).toFixed(1) : 0;
        
        // Określ ikony wydarzeń
        const eventIcons = {
            'kolej': '🚂',
            'budowa': '🏗️',
            'wojna': '⚔️',
            'epidemia': '🏥'
        };
        
        let eventIcon = '📅';
        let eventText = entry.opis || '';
        
        if (eventText.toLowerCase().includes('kolei')) eventIcon = eventIcons.kolej;
        else if (eventText.toLowerCase().includes('budow')) eventIcon = eventIcons.budowa;
        
        return `
            <div class="demo-year-card">
                <div class="demo-card-header">
                    <div class="demo-year">${entry.rok}</div>
                    <div class="demo-total-population">
                        <i class="fas fa-users"></i>
                        <span>${entry.populacja_ogolem || 'Brak danych'} mieszkańców</span>
                    </div>
                </div>
                
                <div class="demo-card-body">
                    ${(entry.katolicy || entry.zydzi || entry.inni) ? `
                        <div class="demo-religions">
                            ${entry.katolicy ? `
                                <div class="religion-item">
                                    <div class="religion-header">
                                        <span class="religion-name">
                                            <span class="religion-icon catholic">✝</span>
                                            Katolicy
                                        </span>
                                        <span class="religion-value">${entry.katolicy}</span>
                                    </div>
                                    <div class="religion-bar">
                                        <div class="religion-fill catholic" style="width: ${catholicPercent}%"></div>
                                    </div>
                                </div>
                            ` : ''}
                            
                            ${entry.zydzi ? `
                                <div class="religion-item">
                                    <div class="religion-header">
                                        <span class="religion-name">
                                            <span class="religion-icon jewish">✡</span>
                                            Żydzi
                                        </span>
                                        <span class="religion-value">${entry.zydzi}</span>
                                    </div>
                                    <div class="religion-bar">
                                        <div class="religion-fill jewish" style="width: ${jewishPercent}%"></div>
                                    </div>
                                </div>
                            ` : ''}
                            
                            ${entry.inni ? `
                                <div class="religion-item">
                                    <div class="religion-header">
                                        <span class="religion-name">
                                            <span class="religion-icon other">☪</span>
                                            Inni
                                        </span>
                                        <span class="religion-value">${entry.inni}</span>
                                    </div>
                                    <div class="religion-bar">
                                        <div class="religion-fill other" style="width: ${otherPercent}%"></div>
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                    
                    ${eventText ? `
                        <div class="demo-event">
                            <span class="event-icon">${eventIcon}</span>
                            <span class="event-text">${eventText}</span>
                        </div>
                    ` : ''}
                    
                    ${changePercent !== 0 ? `
                        <div class="demo-change ${changeType}">
                            <i class="fas fa-arrow-${changePercent > 0 ? 'up' : 'down'}"></i>
                            <span>${Math.abs(changePercent)}% ${changePercent > 0 ? 'wzrost' : 'spadek'}</span>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    // Animuj paski postępu
    setTimeout(() => {
        document.querySelectorAll('.religion-fill').forEach(fill => {
            const width = fill.style.width;
            fill.style.width = '0';
            setTimeout(() => {
                fill.style.width = width;
            }, 100);
        });
    }, 100);
}

function createComparisonAnalysis(data) {
    const container = document.getElementById('demo-comparison');
    if (!container || data.length < 2) return;
    
    const firstYear = data[0];
    const lastYear = data[data.length - 1];
    
    // Oblicz statystyki
    const totalGrowth = lastYear.populacja_ogolem - firstYear.populacja_ogolem;
    const avgGrowthPerYear = (totalGrowth / (lastYear.rok - firstYear.rok)).toFixed(1);
    const maxPopulation = Math.max(...data.map(d => d.populacja_ogolem || 0));
    const minPopulation = Math.min(...data.filter(d => d.populacja_ogolem).map(d => d.populacja_ogolem));
    
    const comparisonHTML = `
        <div class="comparison-cards">
            <div class="comparison-card">
                <div class="comparison-icon">
                    <i class="fas fa-chart-line"></i>
                </div>
                <div class="comparison-value">+${totalGrowth}</div>
                <div class="comparison-label">Wzrost całkowity</div>
            </div>
            
            <div class="comparison-card">
                <div class="comparison-icon">
                    <i class="fas fa-calendar-alt"></i>
                </div>
                <div class="comparison-value">${avgGrowthPerYear}</div>
                <div class="comparison-label">Średni wzrost/rok</div>
            </div>
            
            <div class="comparison-card">
                <div class="comparison-icon">
                    <i class="fas fa-arrow-up"></i>
                </div>
                <div class="comparison-value">${maxPopulation}</div>
                <div class="comparison-label">Maksymalna populacja</div>
            </div>
            
            <div class="comparison-card">
                <div class="comparison-icon">
                    <i class="fas fa-arrow-down"></i>
                </div>
                <div class="comparison-value">${minPopulation}</div>
                <div class="comparison-label">Minimalna populacja</div>
            </div>
        </div>
    `;
    
    container.querySelector('.comparison-cards').innerHTML = comparisonHTML;
}

