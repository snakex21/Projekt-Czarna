/* ==========================================================================
   Plik: stats-script.js
   Opis: Główny skrypt "Centrum Analityczne" – wizualizacja i analiza danych
         katastralnych Gminy Czarna z XIX w.
   ========================================================================== */

/* ==========================================================================
   INICJALIZACJA APLIKACJI
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  initThemeSync();           // Synchronizacja motywu (lokalna i między kartami)
  initUI();                  // Interfejs (zakładki, wyszukiwarka, przyciski, modal, fullscreen)
  loadStatistics();          // Pobranie i rendering danych
  initCounters();            // Animowane liczniki
  initKeyboardShortcuts();   // Skróty klawiaturowe
});

/* ==========================================================================
   ZMIENNE GLOBALNE
   ========================================================================== */

/** Dane statystyczne pobrane z API */
let statsData = null;

/** Rejestr instancji Chart.js */
let charts = {};

/* ==========================================================================
   MOTYW / THEME
   ========================================================================== */

/**
 * Synchronizuje motyw z localStorage i nasłuchuje zmian z innych kart.
 */
function initThemeSync() {
  const savedTheme = localStorage.getItem('mapTheme') || 'light';
  applyTheme(savedTheme);

  // Synchronizacja między kartami
  window.addEventListener('storage', (e) => {
    if (e.key === 'mapTheme') applyTheme(e.newValue);
  });

  // Przełącznik motywu
  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const currentTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('mapTheme', newTheme);
      applyTheme(newTheme);
      showToast('success', 'Motyw zmieniony', `Przełączono na tryb ${newTheme === 'dark' ? 'ciemny' : 'jasny'}`);
    });
  }
}

/**
 * Aplikuje klasę motywu do <body> i aktualizuje ikonę.
 * @param {'light'|'dark'} theme
 */
function applyTheme(theme) {
  const isDark = theme === 'dark';
  document.body.classList.toggle('dark-mode', isDark);
  const icon = document.querySelector('#theme-toggle i');
  if (icon) icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
}

/* ==========================================================================
   INTERFEJS UŻYTKOWNIKA
   ========================================================================== */

/**
 * Inicjalizuje elementy UI: zakładki, wyszukiwarka, akcje, modal, fullscreen.
 */
function initUI() {
  initTabs();
  initSearch();
  initActionButtons();
  initHelpModal();
  initFullscreen();
}

/**
 * Zakładki – przełączanie widoków + leniwe ładowanie Timeline.
 */
function initTabs() {
  const tabButtons = document.querySelectorAll('.tab-button');
  const tabPanels = document.querySelectorAll('.tab-panel');

  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      const targetTab = button.dataset.tab;

      tabButtons.forEach(btn => btn.classList.remove('active'));
      tabPanels.forEach(panel => panel.classList.remove('active'));

      button.classList.add('active');
      document.getElementById(targetTab)?.classList.add('active');

      // Lazy-load chronologii
      if (targetTab === 'timeline' && !button.dataset.loaded) {
        loadTimeline();
        button.dataset.loaded = 'true';
      }
    });
  });
}

/**
 * Globalna wyszukiwarka – pokaz/ukryj, filtracja, czyszczenie.
 */
function initSearch() {
  const searchToggle = document.getElementById('search-toggle');
  const searchBar = document.getElementById('search-bar');
  const searchClose = document.getElementById('search-close');
  const searchInput = document.getElementById('global-search');

  searchToggle?.addEventListener('click', () => {
    searchBar.classList.toggle('active');
    if (searchBar.classList.contains('active')) searchInput?.focus();
  });

  searchClose?.addEventListener('click', () => {
    searchBar.classList.remove('active');
    if (searchInput) searchInput.value = '';
    performGlobalSearch('');
  });

  searchInput?.addEventListener('input', (e) => {
    performGlobalSearch(e.target.value);
  });
}

/**
 * Wyszukiwanie w aktywnej zakładce – podświetlanie + hide/show.
 * @param {string} query
 */
function performGlobalSearch(query) {
  const normalizedQuery = query.trim().toLowerCase();
  const activePanel = document.querySelector('.tab-panel.active');
  if (!activePanel) return;

  clearHighlights(activePanel);
  activePanel.querySelector('.no-results-message')?.remove();

  // Bez frazy – przywróć widoczność
  if (!normalizedQuery) {
    activePanel.querySelectorAll('.ranking-item, .timeline-item, .demo-year-card')
      .forEach(item => item.style.display = '');
    return;
  }

  const searchable = activePanel.querySelectorAll('.ranking-item, .timeline-item, .demo-year-card');
  let found = 0;

  searchable.forEach(item => {
    const txt = item.textContent.toLowerCase();
    if (txt.includes(normalizedQuery)) {
      item.style.display = '';
      highlightText(item, normalizedQuery);
      found++;
    } else {
      item.style.display = 'none';
    }
  });

  if (!found) {
    const noResults = document.createElement('div');
    noResults.className = 'no-results-message';
    noResults.innerHTML = `
      <i class="fas fa-search"></i>
      <h3>Brak wyników</h3>
      <p>Nie znaleziono wyników dla frazy "${query}"</p>`;
    const targetContainer =
      activePanel.querySelector('.ranking-list') ||
      activePanel.querySelector('.timeline') ||
      activePanel.querySelector('.demo-cards-grid') ||
      activePanel;
    targetContainer.appendChild(noResults);
  }
}

/**
 * Podświetla dopasowania węzłów tekstowych elementu.
 * @param {Element} element
 * @param {string} query
 */
function highlightText(element, query) {
  const regex = new RegExp(query, 'gi');

  function walk(node) {
    if (node.nodeType === 3) {
      const text = node.textContent;
      if (regex.test(text)) {
        const span = document.createElement('span');
        span.innerHTML = text.replace(regex, m => `<mark class="search-highlight">${m}</mark>`);
        node.parentNode.replaceChild(span, node);
      }
    } else if (node.nodeType === 1 && node.nodeName !== 'MARK') {
      Array.from(node.childNodes).forEach(walk);
    }
  }

  walk(element);
}

/**
 * Usuwa podświetlenia w kontenerze.
 * @param {Element} container
 */
function clearHighlights(container) {
  const highlights = container.querySelectorAll('mark.search-highlight');
  highlights.forEach(mark => { if (mark.parentNode) mark.outerHTML = mark.innerHTML; });
  container.normalize();
}

/**
 * Przyciski akcji: eksport wykresów, pokaz na mapie, eksport Excel, druk, share.
 */
function initActionButtons() {
  // Eksport wykresów
  document.getElementById('export-chart1')?.addEventListener('click', () => exportChart('pieChart'));
  document.getElementById('export-chart2')?.addEventListener('click', () => exportChart('barChart'));

  // Przekierowanie do mapy (podświetl Top 10)
  document.getElementById('show-on-map')?.addEventListener('click', () => {
    const ownership = document.querySelector('input[name="ownership"]:checked')?.value || 'real';
    const category = document.getElementById('category-filter')?.value || 'all';
    const topOwners = getTop10Owners(ownership, category);
    const ownerKeys = topOwners.map(o => o.unikalny_klucz).join(',');
    window.location.href = `../mapa/mapa.html?highlightTopOwners=${encodeURIComponent(ownerKeys)}&ownership=${ownership}`;
  });

  // Narzędzia analityczne
  document.getElementById('compare-btn')?.addEventListener('click', openPeriodComparison);  // ← DODAJ TU
  document.getElementById('export-btn')?.addEventListener('click', exportToExcel);
  document.getElementById('print-btn')?.addEventListener('click', printReport);
  document.getElementById('share-btn')?.addEventListener('click', shareReport);
}

/**
 * Modal pomocy (otwieranie/zamykanie + klik poza treść).
 */
function initHelpModal() {
  const helpBtn = document.getElementById('help-btn');
  const modal = document.getElementById('help-modal');
  const closeBtn = modal?.querySelector('.modal-close');

  helpBtn?.addEventListener('click', () => modal.classList.add('active'));
  closeBtn?.addEventListener('click', () => modal.classList.remove('active'));
  modal?.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('active'); });
}

/**
 * Tryb pełnoekranowy – przełączanie i aktualizacja ikony.
 */
function initFullscreen() {
  const btn = document.getElementById('fullscreen-toggle');
  btn?.addEventListener('click', () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      btn.querySelector('i').className = 'fas fa-compress';
    } else {
      document.exitFullscreen();
      btn.querySelector('i').className = 'fas fa-expand';
    }
  });
}

/* ==========================================================================
   POBRANIE DANYCH
   ========================================================================== */

/**
 * Ładuje pakiet statystyk i uruchamia renderery sekcji.
 */
async function loadStatistics() {
  try {
    const response = await fetch('/api/stats');
    statsData = await response.json();

    updateCounters(statsData.general_stats);
    createCharts(statsData);
    loadRankings(statsData);
    loadDemographics(statsData.demografia);
    renderActivityCalendar(statsData.protocols_per_day);
    loadGenealogyStats(statsData);
    loadInsights(statsData);

  } catch (err) {
    console.error('Błąd ładowania statystyk:', err);
    showToast('error', 'Błąd', 'Nie udało się załadować danych');
  }
}

/* ==========================================================================
   LICZNIKI (ANIMACJE)
   ========================================================================== */

/**
 * Uruchamia animacje liczników przy wejściu w viewport.
 */
function initCounters() {
  const counters = document.querySelectorAll('.counter');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const counter = entry.target;
        const target = parseInt(counter.dataset.target, 10) || 0;
        animateCounter(counter, target);
        observer.unobserve(counter);
      }
    });
  }, { threshold: 0.5 });

  counters.forEach(c => observer.observe(c));
}

/**
 * Prostoliniowa animacja wartości licznika do zadanego celu.
 * @param {HTMLElement} element
 * @param {number} target
 */
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

/**
 * Ustawia wartości liczników i uruchamia animacje.
 * @param {{total_owners:number,total_plots:number}} stats
 */
function updateCounters(stats) {
  const ownersCounter = document.querySelector('#total-owners .counter');
  const plotsCounter  = document.querySelector('#total-plots .counter');

  if (ownersCounter) {
    ownersCounter.dataset.target = stats.total_owners;
    animateCounter(ownersCounter, stats.total_owners);
  }
  if (plotsCounter) {
    plotsCounter.dataset.target = stats.total_plots;
    animateCounter(plotsCounter, stats.total_plots);
  }
}

/* ==========================================================================
   WYKRESY (Chart.js)
   ========================================================================== */

/**
 * Tworzy wykresy: kołowy struktur kategorii oraz poziomy słupkowy Top 10.
 * @param {*} data
 */
function createCharts(data) {
  // Doughnut – struktura kategorii
  const pieCtx = document.getElementById('pieChart')?.getContext('2d');
  if (pieCtx && data.category_counts) {
    const c = data.category_counts;
    const inne = (c.droga || 0) + (c.rzeka || 0) + (c.obiekt_specjalny || 0);

    charts.pie = new Chart(pieCtx, {
      type: 'doughnut',
      data: {
        labels: ['Rolne', 'Budowlane', 'Lasy', 'Pastwiska', 'Inne'],
        datasets: [{
          data: [c.rolna || 0, c.budowlana || 0, c.las || 0, c.pastwisko || 0, inne],
          backgroundColor: ['#10b981', '#f59e0b', '#3b82f6', '#8b5cf6', '#ef4444']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } }
      }
    });
  }

  // Bar – Top 10 właścicieli (rzeczywiste)
  const barCtx = document.getElementById('barChart')?.getContext('2d');
  if (barCtx && data?.rankings_real?.all_plots) {
    const top10 = data.rankings_real.all_plots.slice(0, 10).reverse();

    charts.bar = new Chart(barCtx, {
      type: 'bar',
      data: {
        labels: top10.map(o => o.nazwa_wlasciciela),
        datasets: [{
          label: 'Liczba działek',
          data: top10.map(o => o.plot_count),
          backgroundColor: 'rgba(102,126,234,0.8)',
          borderColor: '#667eea',
          borderWidth: 1,
          borderRadius: 5
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { title: (items) => items[0].label } }
        },
        scales: {
          x: { beginAtZero: true, title: { display: true, text: 'Liczba działek' } },
          y: {
            ticks: {
              autoSkip: false,
              callback: function (value) {
                const label = this.getLabelForValue(value);
                return (label.length > 25) ? label.substring(0, 22) + '…' : label;
              }
            }
          }
        }
      }
    });
  }
}

/* ==========================================================================
   RANKINGI WŁAŚCICIELI
   ========================================================================== */

/**
 * Renderuje listę rankingową + podpina filtry.
 * @param {*} data
 */
function loadRankings(data) {
  const container = document.getElementById('ranking-list');
  if (!container) return;

  displayRanking(data.rankings_real.all_plots || [], container);

  // Filtry
  document.querySelectorAll('input[name="ownership"]').forEach(r => {
    r.addEventListener('change', filterRankings);
  });
  document.getElementById('category-filter')?.addEventListener('change', filterRankings);
}

/**
 * Buduje HTML listy rankingowej (pierwsze 50 pozycji).
 * @param {Array} rankingData
 * @param {HTMLElement} container
 */
function displayRanking(rankingData, container) {
  container.innerHTML = (rankingData || []).slice(0, 50).map((owner, i) => {
    const pos = i + 1;
    const cls = pos === 1 ? 'gold' : pos === 2 ? 'silver' : pos === 3 ? 'bronze' : '';
    const prot = owner.numer_protokolu ?? 'Brak';
    return `
      <a href="../wlasciciele/protokol.html?ownerId=${owner.unikalny_klucz}" class="ranking-item">
        <div class="ranking-position ${cls}">${pos}</div>
        <div class="ranking-info">
          <div class="ranking-name">${owner.nazwa_wlasciciela}</div>
          <div class="ranking-meta">Protokół nr ${prot}</div>
        </div>
        <div class="ranking-value">${owner.plot_count}</div>
      </a>`;
  }).join('');
}

/**
 * Zmienia zestaw rankingowy zgodnie z radiobuttonami i selectem.
 */
function filterRankings() {
  if (!statsData) return;
  const ownership = document.querySelector('input[name="ownership"]:checked')?.value || 'real';
  const category = document.getElementById('category-filter')?.value || 'all';
  const container = document.getElementById('ranking-list');

  const dataSet = ownership === 'real' ? statsData.rankings_real : statsData.rankings_protocol;
  let rankingData = category === 'all' ? dataSet.all_plots : dataSet[category];
  if (!rankingData) rankingData = [];

  displayRanking(rankingData, container);

  // Zachowaj aktywne filtrowanie tekstowe
  const searchQuery = document.getElementById('global-search')?.value || '';
  performGlobalSearch(searchQuery);
}

/* ==========================================================================
   OŚ CZASU (Timeline protokołów)
   ========================================================================== */

/**
 * Renderuje linię czasu grupowaną po datach protokołów.
 */
function loadTimeline() {
  if (!statsData?.protocols_per_day) return;
  const container = document.getElementById('timeline-content');

  container.innerHTML = statsData.protocols_per_day.map(item => {
    const date = new Date(item.protocol_date);
    const formatted = date.toLocaleDateString('pl-PL', { year: 'numeric', month: 'long', day: 'numeric' });

    const ownersList = (item.owners || []).map(owner => `
      <li>
        <a href="../wlasciciele/protokol.html?ownerId=${owner.unikalny_klucz}">
          ${owner.nazwa_wlasciciela}
        </a>
      </li>`).join('');

    return `
      <div class="timeline-item">
        <div class="timeline-marker"></div>
        <div class="timeline-content">
          <div class="timeline-date">${formatted}</div>
          <details>
            <summary class="timeline-title">${item.protocol_count} protokołów (kliknij, aby rozwinąć)</summary>
            <ul class="timeline-owners-list">${ownersList}</ul>
          </details>
        </div>
      </div>`;
  }).join('');
}

/* ==========================================================================
   DEMOGRAFIA
   ========================================================================== */

/**
 * Wczytuje i przedstawia zestaw demograficzny: wykres, karty, linię zdarzeń, porównania.
 * @param {Array} demografiaData
 */
function loadDemographics(demografiaData) {
  if (!demografiaData || demografiaData.length === 0) {
    document.getElementById('demographics').innerHTML = `
      <div class="no-data-message">
        <i class="fas fa-inbox fa-3x"></i>
        <h3>Brak danych demograficznych</h3>
        <p>Dane demograficzne nie są jeszcze dostępne dla tego okresu.</p>
      </div>`;
    return;
  }

  demografiaData.sort((a, b) => a.rok - b.rok);

  // Podstawowe metryki
  const firstYear = demografiaData[0];
  const lastYear  = demografiaData[demografiaData.length - 1];
  const growthPercent = ((lastYear.populacja_ogolem - firstYear.populacja_ogolem) / firstYear.populacja_ogolem * 100).toFixed(1);
  const yearSpan = lastYear.rok - firstYear.rok;

  document.getElementById('demo-growth').textContent = (growthPercent > 0 ? `+${growthPercent}%` : `${growthPercent}%`);
  document.getElementById('demo-years').textContent = `${yearSpan} lat`;

  createDemographicsChart(demografiaData);
  createDemographicsTimeline(demografiaData);
  createDemographicsCards(demografiaData);
  createComparisonAnalysis(demografiaData);
}

/**
 * Wykres linii populacji oraz grup wyznaniowych.
 * @param {Array} data
 */
function createDemographicsChart(data) {
  const ctx = document.getElementById('demographicsChart')?.getContext('2d');
  if (!ctx) return;

  const years = data.map(d => d.rok);
  const total = data.map(d => d.populacja_ogolem || 0);
  const catholics = data.map(d => d.katolicy || 0);
  const jewish    = data.map(d => d.zydzi || 0);
  const others    = data.map(d => d.inni || 0);

  if (charts.demographics) charts.demographics.destroy();

  charts.demographics = new Chart(ctx, {
    type: 'line',
    data: {
      labels: years,
      datasets: [
        {
          label: 'Populacja ogółem',
          data: total,
          borderColor: '#667eea',
          backgroundColor: 'rgba(102,126,234,0.1)',
          borderWidth: 3, tension: 0.4, fill: true,
          pointRadius: 6, pointHoverRadius: 8,
          pointBackgroundColor: '#667eea',
          pointBorderColor: '#fff', pointBorderWidth: 2
        },
        {
          label: 'Katolicy',
          data: catholics,
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245,158,11,0.1)',
          borderWidth: 2, tension: 0.4, fill: false,
          hidden: catholics.every(v => v === 0),
          pointRadius: 5, pointHoverRadius: 7
        },
        {
          label: 'Żydzi',
          data: jewish,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.1)',
          borderWidth: 2, tension: 0.4, fill: false,
          hidden: jewish.every(v => v === 0),
          pointRadius: 5, pointHoverRadius: 7
        },
        {
          label: 'Inni',
          data: others,
          borderColor: '#8b5cf6',
          backgroundColor: 'rgba(139,92,246,0.1)',
          borderWidth: 2, tension: 0.4, fill: false,
          hidden: others.every(v => v === 0),
          pointRadius: 5, pointHoverRadius: 7
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { usePointStyle: true, padding: 15 } },
        tooltip: {
          backgroundColor: 'rgba(0,0,0,0.8)', padding: 12, cornerRadius: 8,
          callbacks: {
            title: (ctx) => `Rok ${ctx[0].label}`,
            label: (ctx) => {
              const label = ctx.dataset.label;
              const value = ctx.parsed.y;
              const totalValue = total[ctx.dataIndex] || 0;
              const pct = totalValue > 0 ? ((value / totalValue) * 100).toFixed(1) : 0;
              return `${label}: ${value} osób${pct > 0 ? ` (${pct}%)` : ''}`;
            }
          }
        }
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'Liczba mieszkańców' }, grid: { drawBorder: false } },
        x: { title: { display: true, text: 'Rok' }, grid: { display: false } }
      }
    }
  });
}

/**
 * Paski wydarzeń na osi czasu demografii (ikony + tooltip).
 * @param {Array} data
 */
function createDemographicsTimeline(data) {
  const container = document.getElementById('demo-timeline-track');
  if (!container) return;

  const getIconForEvent = (d) => {
    const s = d.toLowerCase();
    if (s.includes('kolei')) return '🚂';
    if (s.includes('budow')) return '🏗️';
    if (s.includes('wojn')) return '⚔️';
    if (s.includes('epidemi') || s.includes('chorob')) return '🏥';
    return '📅';
  };

  const events = data
    .filter(e => e.opis && e.opis.trim() !== '')
    .map(e => ({ year: e.rok, text: e.opis, icon: getIconForEvent(e.opis), major: true }));

  if (events.length === 0) {
    container.innerHTML = '<p style="text-align:center; color: var(--text-secondary);">Brak zdefiniowanych kluczowych wydarzeń w danych.</p>';
    return;
  }
  if (events.length === 1) {
    const ev = events[0];
    container.innerHTML = `
      <div class="timeline-event ${ev.major ? 'major' : ''}" style="left: 50%;">
        <span>${ev.icon}</span><span>${ev.year}</span>
        <div class="timeline-event-tooltip">${ev.text}</div>
      </div>`;
    return;
  }

  const minYear = Math.min(...events.map(e => e.year));
  const maxYear = Math.max(...events.map(e => e.year));
  const span = Math.max(1, maxYear - minYear);

  container.innerHTML = events.map(ev => {
    const left = ((ev.year - minYear) / span) * 100;
    return `
      <div class="timeline-event ${ev.major ? 'major' : ''}" style="left: ${left}%">
        <span>${ev.icon}</span><span>${ev.year}</span>
        <div class="timeline-event-tooltip">${ev.text}</div>
      </div>`;
  }).join('');
}

/**
 * Karty demograficzne per rok (udziały % + prosta dynamika).
 * @param {Array} data
 */
function createDemographicsCards(data) {
  const container = document.getElementById('demo-cards');
  if (!container) return;

  container.innerHTML = data.map((entry, idx) => {
    let changePercent = 0;
    if (idx > 0 && entry.populacja_ogolem && data[idx - 1].populacja_ogolem) {
      changePercent = ((entry.populacja_ogolem - data[idx - 1].populacja_ogolem) / data[idx - 1].populacja_ogolem * 100).toFixed(1);
    }
    const changeType = changePercent > 0 ? 'positive' : (changePercent < 0 ? 'negative' : '');

    const total = entry.populacja_ogolem || 1;
    const catholicPercent = entry.katolicy ? (entry.katolicy / total * 100).toFixed(1) : 0;
    const jewishPercent   = entry.zydzi    ? (entry.zydzi    / total * 100).toFixed(1) : 0;
    const otherPercent    = entry.inni     ? (entry.inni     / total * 100).toFixed(1) : 0;

    let eventIcon = '📅';
    const eventText = entry.opis || '';
    if (eventText.toLowerCase().includes('kolei')) eventIcon = '🚂';
    else if (eventText.toLowerCase().includes('budow')) eventIcon = '🏗️';

    return `
      <div class="demo-year-card">
        <div class="demo-card-header">
          <div class="demo-year">${entry.rok}</div>
          <div class="demo-total-population"><i class="fas fa-users"></i>
            <span>${entry.populacja_ogolem || 'Brak danych'} mieszkańców</span>
          </div>
        </div>

        <div class="demo-card-body">
          ${(entry.katolicy || entry.zydzi || entry.inni) ? `
            <div class="demo-religions">
              ${entry.katolicy ? `
                <div class="religion-item">
                  <div class="religion-header">
                    <span class="religion-name"><span class="religion-icon catholic">✝</span>Katolicy</span>
                    <span class="religion-value">${entry.katolicy}</span>
                  </div>
                  <div class="religion-bar"><div class="religion-fill catholic" style="width:${catholicPercent}%"></div></div>
                </div>` : ''}

              ${entry.zydzi ? `
                <div class="religion-item">
                  <div class="religion-header">
                    <span class="religion-name"><span class="religion-icon jewish">✡</span>Żydzi</span>
                    <span class="religion-value">${entry.zydzi}</span>
                  </div>
                  <div class="religion-bar"><div class="religion-fill jewish" style="width:${jewishPercent}%"></div></div>
                </div>` : ''}

              ${entry.inni ? `
                <div class="religion-item">
                  <div class="religion-header">
                    <span class="religion-name"><span class="religion-icon other">◎</span>Inni</span>
                    <span class="religion-value">${entry.inni}</span>
                  </div>
                  <div class="religion-bar"><div class="religion-fill other" style="width:${otherPercent}%"></div></div>
                </div>` : ''}
            </div>` : `
            <div class="no-data-message small">
              <i class="fas fa-inbox"></i> Brak szczegółu wyznaniowego
            </div>`}
        </div>

        <div class="demo-card-footer">
          <div class="demo-change ${changeType}">
            <i class="fas fa-chart-line"></i>
            <span>${idx > 0 ? (changePercent > 0 ? `+${changePercent}% vs ${data[idx-1].rok}` : `${changePercent}% vs ${data[idx-1].rok}`) : '—'}</span>
          </div>
          ${eventText ? `
            <div class="demo-event">
              <span class="event-icon">${eventIcon}</span>
              <span class="event-text">${eventText}</span>
            </div>` : ''}
        </div>
      </div>`;
  }).join('');
}

/**
 * Porównania i metryki zagregowane dla demografii (karty porównawcze).
 * @param {Array} data
 */
function createComparisonAnalysis(data) {
  const container = document.getElementById('demographics');
  if (!container || data.length < 2) return;

  const first = data[0];
  const last  = data[data.length - 1];

  const totalGrowth = (last.populacja_ogolem || 0) - (first.populacja_ogolem || 0);
  const years = Math.max(1, last.rok - first.rok);
  const avgPerYear = (totalGrowth / years).toFixed(1);
  const maxPopulation = Math.max(...data.map(d => d.populacja_ogolem || 0));
  const minPopulation = Math.min(...data.filter(d => d.populacja_ogolem).map(d => d.populacja_ogolem));

  const html = `
    <div class="comparison-cards">
      <div class="comparison-card">
        <div class="comparison-icon"><i class="fas fa-chart-line"></i></div>
        <div class="comparison-value">${totalGrowth > 0 ? '+' : ''}${totalGrowth}</div>
        <div class="comparison-label">Wzrost całkowity</div>
      </div>
      <div class="comparison-card">
        <div class="comparison-icon"><i class="fas fa-calendar-alt"></i></div>
        <div class="comparison-value">${avgPerYear}</div>
        <div class="comparison-label">Średni wzrost/rok</div>
      </div>
      <div class="comparison-card">
        <div class="comparison-icon"><i class="fas fa-arrow-up"></i></div>
        <div class="comparison-value">${maxPopulation}</div>
        <div class="comparison-label">Maksymalna populacja</div>
      </div>
      <div class="comparison-card">
        <div class="comparison-icon"><i class="fas fa-arrow-down"></i></div>
        <div class="comparison-value">${minPopulation}</div>
        <div class="comparison-label">Minimalna populacja</div>
      </div>
    </div>`;
  container.querySelector('.comparison-cards')?.replaceWith(document.createRange().createContextualFragment(html));
}

/* ==========================================================================
   KALENDARZ AKTYWNOŚCI (protokół/dzień)
   ========================================================================== */

/**
 * Renderuje kalendarz aktywności spisowej (heatmapa tygodniowa).
 * @param {Array<{protocol_date:string,protocol_count:number}>} protocolsData
 */
function renderActivityCalendar(protocolsData) {
  if (!protocolsData || protocolsData.length === 0) return;

  const container = document.getElementById('activity-calendar-container');
  if (!container) return;

  // Map: ISO-date -> count
  const dataMap = new Map();
  protocolsData.forEach(item => {
    const d = new Date(item.protocol_date).toISOString().split('T')[0];
    dataMap.set(d, item.protocol_count);
  });

  const maxCount = Math.max(...Array.from(dataMap.values()));
  const startDate = new Date(protocolsData[0].protocol_date);
  const endDate   = new Date(protocolsData[protocolsData.length - 1].protocol_date);

  let html = '<div class="activity-calendar">';
  const current = new Date(startDate);
  // Wyrównaj do początku tygodnia
  current.setDate(startDate.getDate() - startDate.getDay());

  while (current <= endDate) {
    const iso = current.toISOString().split('T')[0];
    const count = dataMap.get(iso) || 0;
    const level = count > 0 ? Math.ceil((count / maxCount) * 4) : 0;
    const tooltip = `${current.toLocaleDateString('pl-PL')}: ${count} protokołów`;
    html += `<div class="day-cell" data-tooltip="${tooltip}" data-level="${level}"></div>`;
    current.setDate(current.getDate() + 1);
  }
  html += '</div>';

  const legend = `
    <div class="activity-legend">
      <span>Mniej</span>
      <div class="legend-item">
        <div class="day-cell" data-level="1"></div>
        <div class="day-cell" data-level="2"></div>
        <div class="day-cell" data-level="3"></div>
        <div class="day-cell" data-level="4"></div>
      </div>
      <span>Więcej</span>
    </div>`;

  container.innerHTML = html + legend;

  // Tooltip dynamiczny
  const calendar = container.querySelector('.activity-calendar');
  let tooltipEl = document.getElementById('calendar-tooltip');
  if (!tooltipEl) {
    tooltipEl = document.createElement('div');
    tooltipEl.id = 'calendar-tooltip';
    document.body.appendChild(tooltipEl);
  }

  calendar.addEventListener('mouseover', (e) => {
    if (e.target.classList.contains('day-cell') && e.target.dataset.tooltip) {
      const cell = e.target;
      tooltipEl.textContent = cell.dataset.tooltip;
      tooltipEl.classList.add('visible');

      const cellRect = cell.getBoundingClientRect();
      const tipRect = tooltipEl.getBoundingClientRect();

      let top = cellRect.top - tipRect.height - 8;
      let left = cellRect.left + (cellRect.width / 2) - (tipRect.width / 2);
      if (left < 0) left = 5;
      if (left + tipRect.width > window.innerWidth) left = window.innerWidth - tipRect.width - 5;

      tooltipEl.style.left = `${left}px`;
      tooltipEl.style.top = `${top}px`;
    }
  });

  calendar.addEventListener('mouseout', (e) => {
    if (e.target.classList.contains('day-cell')) tooltipEl.classList.remove('visible');
  });
}

/* ==========================================================================
   ANALIZA I WNIOSKI
   ========================================================================== */

/**
 * Aktualizuje sekcję insightów (mini statystyki, największy właściciel, koncentracja).
 * @param {*} data
 */
function loadInsights(data) {
  const counts = data.category_counts || {};
  document.getElementById('stat-forests')  .textContent = counts.las || 0;
  document.getElementById('stat-rivers')   .textContent = counts.rzeka || 0;
  document.getElementById('stat-buildings').textContent = counts.budynek || 0;
  document.getElementById('stat-chapels')  .textContent = counts.kapliczka || 0;

  // Największy właściciel
  const first = data.rankings_real?.all_plots?.[0];
  if (first) {
    document.getElementById('biggest-owner').textContent = `${first.nazwa_wlasciciela} - ${first.plot_count} działek`;
  }

  // Trend własności
  document.getElementById('ownership-trend').textContent =
    `${data.general_stats.total_owners} właścicieli kontroluje ${data.general_stats.total_plots} działek`;

  // Koncentracja – udział Top 10
  const top10Count = (data.rankings_real?.all_plots || []).slice(0, 10)
    .reduce((sum, o) => sum + o.plot_count, 0);
  const concentration = data.general_stats.total_plots > 0
    ? ((top10Count / data.general_stats.total_plots) * 100).toFixed(1) : '0.0';
  document.getElementById('concentration').textContent =
    `Top 10 właścicieli posiada ${concentration}% wszystkich działek`;
}

/* ==========================================================================
   STATYSTYKI GENEALOGICZNE
   ========================================================================== */

/**
 * Kafle i wykres genealogii + przełącznik serii (Urodzenia / Zgony / Śluby).
 * @param {*} data
 */
function loadGenealogyStats(data) {
  const stats = data.genealogy_stats;
  if (!stats) return;

  // ——— Wskaźniki (liczba osób, stosunek płci)
  const totalPeopleEl = document.getElementById('stat-total-people');
  const genderRatioEl = document.getElementById('stat-gender-ratio');
  if (totalPeopleEl) totalPeopleEl.textContent = stats.total_people;
  if (genderRatioEl) genderRatioEl.textContent = `${stats.male_count} / ${stats.female_count}`;

  // ——— Ranking nazwisk (Top 10)
  const surnamesContainer = document.getElementById('top-surnames-list');
  if (surnamesContainer) {
    surnamesContainer.innerHTML = (stats.top_surnames || []).map((surname, index) => {
      const pos = index + 1;
      const cls = pos === 1 ? 'gold' : pos === 2 ? 'silver' : pos === 3 ? 'bronze' : '';
      return `
        <div class="ranking-item">
          <div class="ranking-position ${cls}">${pos}</div>
          <div class="ranking-info"><div class="ranking-name">${surname.name}</div></div>
          <div class="surname-count">${surname.count}</div>
        </div>`;
    }).join('');
  }

  // ——— Wykres serii genealogicznych (domyślnie: URODZENIA)
  const chartCtx = document.getElementById('genealogy-births-chart')?.getContext('2d'); // zostawiamy istniejący ID
  if (!chartCtx) return;

  // Gradient tła
  const gradient = chartCtx.createLinearGradient(0, 0, 0, 400);
  gradient.addColorStop(0, 'rgba(118,75,162,0.6)');
  gradient.addColorStop(1, 'rgba(102,126,234,0.1)');

  if (charts.genealogyBirths) charts.genealogyBirths.destroy();
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
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'Liczba osób / zdarzeń' } },
        x: { title: { display: true, text: 'Dekada' } }
      }
    }
  });

  // ——— Przełącznik (radio) – delegacja zdarzeń
  const toggle = document.getElementById('genealogy-series-toggle');
  if (toggle) {
    // Wygaszaj niedostępne, jeśli brak danych
    const deathsEmpty = (stats.deaths_by_decade?.labels?.length || 0) === 0;
    const marriagesEmpty = (stats.marriages_by_decade?.labels?.length || 0) === 0;
    const deathsInput = document.getElementById('gen-series-deaths');
    const marriagesInput = document.getElementById('gen-series-marriages');
    if (deathsInput) deathsInput.disabled = deathsEmpty;
    if (marriagesInput) marriagesInput.disabled = marriagesEmpty;

    toggle.addEventListener('change', (e) => {
      const target = e.target;
      if (target?.name === 'gen-series') {
        updateGenealogySeries(target.value);
      }
    });
  }
}

/**
 * Aktualizuje serię wykresu genealogii zgodnie z przełącznikiem.
 * @param {'births'|'deaths'|'marriages'} series
 */
function updateGenealogySeries(series) {
  if (!charts.genealogyBirths || !statsData?.genealogy_stats) return;

  const s = statsData.genealogy_stats;
  const map = {
    'births':    { key: 'births_by_decade',    label: 'Liczba urodzeń',   color: '#764ba2' },
    'deaths':    { key: 'deaths_by_decade',    label: 'Liczba zgonów',    color: '#ef4444' },
    'marriages': { key: 'marriages_by_decade', label: 'Liczba ślubów',    color: '#10b981' }
  };

  const cfg = map[series] || map.births;
  const ds = s[cfg.key] || { labels: [], data: [] };

  const chart = charts.genealogyBirths;
  chart.data.labels = ds.labels;
  chart.data.datasets[0].data = ds.data;
  chart.data.datasets[0].label = cfg.label;
  chart.data.datasets[0].borderColor = cfg.color;
  chart.update();
}


/* ==========================================================================
   EKSPORT / UDOSTĘPNIANIE
   ========================================================================== */

/**
 * Pobiera obraz bieżącego wykresu (PNG).
 * @param {'pieChart'|'barChart'} chartId
 */
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

/**
 * Eksport całego zestawu do Excela (SheetJS).
 */
function exportToExcel() {
  if (!statsData) {
    showToast('error', 'Błąd', 'Dane nie zostały jeszcze załadowane.');
    return;
  }

  try {
    showToast('info', 'Eksport', 'Rozpoczęto generowanie pliku Excel.');
    const wb = XLSX.utils.book_new();

    // Podsumowanie
    const summary = [
      ['Kluczowa statystyka', 'Wartość'],
      ['Całkowita liczba właścicieli', statsData.general_stats.total_owners],
      ['Całkowita liczba działek', statsData.general_stats.total_plots],
      ...Object.entries(statsData.category_counts || {}).map(([k, v]) => [`Liczba działek – ${k}`, v])
    ];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(summary), 'Podsumowanie');

    // Rankingi (rzeczywiste)
    const realRows = [];
    for (const category in (statsData.rankings_real || {})) {
      (statsData.rankings_real[category] || []).forEach((o, idx) => {
        realRows.push({
          'Kategoria': category,
          'Pozycja': idx + 1,
          'Właściciel': o.nazwa_wlasciciela,
          'Protokół': o.numer_protokolu ?? '',
          'Liczba działek': o.plot_count
        });
      });
    }
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(realRows), 'Rankingi (real)');

    // Rankingi (protokół)
    const protoRows = [];
    for (const category in (statsData.rankings_protocol || {})) {
      (statsData.rankings_protocol[category] || []).forEach((o, idx) => {
        protoRows.push({
          'Kategoria': category,
          'Pozycja': idx + 1,
          'Właściciel': o.nazwa_wlasciciela,
          'Protokół': o.numer_protokolu ?? '',
          'Liczba działek': o.plot_count
        });
      });
    }
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(protoRows), 'Rankingi (protokół)');

    // Demografia
    const demoRows = (statsData.demografia || []).map(d => ({
      'Rok': d.rok,
      'Populacja': d.populacja_ogolem,
      'Katolicy': d.katolicy ?? '',
      'Żydzi': d.zydzi ?? '',
      'Inni': d.inni ?? '',
      'Opis': d.opis ?? ''
    }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(demoRows), 'Demografia');

    // Genealogia – urodzenia wg dekad
    const genAoa = [
      ['Urodzenia wg Dekad'],
      ['Dekada', 'Liczba urodzeń'],
      ...(statsData.genealogy_stats?.births_by_decade?.labels || []).map((label, i) => [
        label, (statsData.genealogy_stats?.births_by_decade?.data || [])[i] ?? 0
      ])
    ];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(genAoa), 'Genealogia');

    // Aktywność spisowa
    const activityRows = (statsData.protocols_per_day || []).map(day => ({
      'Data': new Date(day.protocol_date).toLocaleDateString('pl-PL'),
      'Liczba protokołów': day.protocol_count,
      'Właściciele': (day.owners || []).map(o => o.nazwa_wlasciciela).join(', ')
    }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(activityRows), 'Aktywność spisowa');

    const today = new Date().toISOString().slice(0, 10);
    const fileName = `statystyki_gmina_czarna_${today}.xlsx`;
    XLSX.writeFile(wb, fileName);
    showToast('success', 'Eksport zakończony', `Plik ${fileName} został pobrany.`);

  } catch (error) {
    console.error('Błąd podczas eksportu do Excel:', error);
    showToast('error', 'Błąd eksportu', 'Wystąpił nieoczekiwany problem.');
  }
}

/** Drukuj raport (tryb print CSS) */
function printReport() {
  window.print();
  showToast('info', 'Drukowanie', 'Przygotowano raport do druku');
}

/** Web Share API / fallback do schowka */
function shareReport() {
  if (navigator.share) {
    navigator.share({
      title: 'Statystyki Gminy Czarna',
      text: 'Zobacz statystyki właścicieli gruntów z XIX wieku',
      url: window.location.href
    });
  } else {
    navigator.clipboard.writeText(window.location.href);
    showToast('success', 'Udostępnianie', 'Link skopiowany do schowka');
  }
}

/**
 * Zwraca Top 10 właścicieli dla zadanych filtrów.
 * @param {'real'|'protocol'} ownership
 * @param {string} category
 */
function getTop10Owners(ownership, category) {
  const data = ownership === 'real' ? statsData.rankings_real : statsData.rankings_protocol;
  const rankingData = category === 'all' ? data.all_plots : data[category];
  return rankingData?.slice(0, 10) || [];
}

/**
 * Otwiera modal porównania okresów demograficznych.
 */
function openPeriodComparison() {
  if (!statsData?.demografia || statsData.demografia.length < 2) {
    showToast('error', 'Brak danych', 'Potrzeba co najmniej 2 lata danych demograficznych do porównania');
    return;
  }

  createComparisonModal();
}

/**
 * Tworzy modal do porównania okresów.
 */
function createComparisonModal() {
  const modal = document.createElement('div');
  modal.className = 'modal active';
  modal.id = 'comparison-modal';
  
  const availableYears = statsData.demografia.map(d => d.rok).sort((a, b) => a - b);
  
  modal.innerHTML = `
    <div class="modal-content">
      <div class="modal-header">
        <h2><i class="fas fa-balance-scale"></i> Porównaj okresy demograficzne</h2>
        <button class="modal-close" onclick="closeComparisonModal()">&times;</button>
      </div>
      <div class="modal-body">
        <div class="comparison-setup">
          <div class="period-selector">
            <label for="period1">Pierwszy okres:</label>
            <select id="period1" class="period-select">
              <option value="">Wybierz rok...</option>
              ${availableYears.map(year => `<option value="${year}">${year}</option>`).join('')}
            </select>
          </div>
          <div class="period-selector">
            <label for="period2">Drugi okres:</label>
            <select id="period2" class="period-select">
              <option value="">Wybierz rok...</option>
              ${availableYears.map(year => `<option value="${year}">${year}</option>`).join('')}
            </select>
          </div>
          <button class="btn-primary" onclick="performComparison()" id="compare-execute">
            <i class="fas fa-chart-bar"></i> Porównaj
          </button>
        </div>
        <div id="comparison-results" style="display: none;">
          <div class="comparison-charts">
            <canvas id="comparison-chart" style="max-height: 400px;"></canvas>
          </div>
          <div class="comparison-summary" id="comparison-summary"></div>
        </div>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
}

/**
 * Wykonuje porównanie wybranych okresów.
 */
function performComparison() {
  const year1 = parseInt(document.getElementById('period1').value);
  const year2 = parseInt(document.getElementById('period2').value);
  
  if (!year1 || !year2) {
    showToast('error', 'Błąd', 'Wybierz oba okresy do porównania');
    return;
  }
  
  if (year1 === year2) {
    showToast('error', 'Błąd', 'Wybierz różne okresy do porównania');
    return;
  }
  
  const data1 = statsData.demografia.find(d => d.rok === year1);
  const data2 = statsData.demografia.find(d => d.rok === year2);
  
  if (!data1 || !data2) {
    showToast('error', 'Błąd', 'Nie znaleziono danych dla wybranych okresów');
    return;
  }
  
  displayComparisonResults(data1, data2);
}

/**
 * Wyświetla wyniki porównania.
 */
function displayComparisonResults(data1, data2) {
  const resultsDiv = document.getElementById('comparison-results');
  resultsDiv.style.display = 'block';
  
  // Wykres porównawczy
  createComparisonChart(data1, data2);
  
  // Podsumowanie tekstowe
  const summary = generateComparisonSummary(data1, data2);
  document.getElementById('comparison-summary').innerHTML = summary;
  
  showToast('success', 'Porównanie', `Porównano lata ${data1.rok} i ${data2.rok}`);
}

/**
 * Tworzy wykres porównawczy.
 */
function createComparisonChart(data1, data2) {
  const ctx = document.getElementById('comparison-chart').getContext('2d');
  
  // Zniszcz poprzedni wykres jeśli istnieje
  if (charts.comparison) {
    charts.comparison.destroy();
  }
  
  const categories = ['Populacja ogółem', 'Katolicy', 'Żydzi', 'Inni'];
  const values1 = [
    data1.populacja_ogolem || 0,
    data1.katolicy || 0,
    data1.zydzi || 0,
    data1.inni || 0
  ];
  const values2 = [
    data2.populacja_ogolem || 0,
    data2.katolicy || 0,
    data2.zydzi || 0,
    data2.inni || 0
  ];
  
  charts.comparison = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: categories,
      datasets: [
        {
          label: `Rok ${data1.rok}`,
          data: values1,
          backgroundColor: 'rgba(102, 126, 234, 0.8)',
          borderColor: '#667eea',
          borderWidth: 1
        },
        {
          label: `Rok ${data2.rok}`,
          data: values2,
          backgroundColor: 'rgba(118, 75, 162, 0.8)',
          borderColor: '#764ba2',
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: `Porównanie demograficzne: ${data1.rok} vs ${data2.rok}`
        },
        legend: {
          position: 'top'
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: 'Liczba osób'
          }
        }
      }
    }
  });
}

/**
 * Generuje podsumowanie porównania.
 */
function generateComparisonSummary(data1, data2) {
  const pop1 = data1.populacja_ogolem || 0;
  const pop2 = data2.populacja_ogolem || 0;
  const change = pop2 - pop1;
  const changePercent = pop1 > 0 ? ((change / pop1) * 100).toFixed(1) : 0;
  
  const yearDiff = data2.rok - data1.rok;
  const avgPerYear = yearDiff > 0 ? (change / yearDiff).toFixed(1) : 0;
  
  return `
    <div class="summary-grid">
      <div class="summary-card">
        <h4>Zmiana populacji</h4>
        <div class="summary-value ${change >= 0 ? 'positive' : 'negative'}">
          ${change >= 0 ? '+' : ''}${change} osób
        </div>
        <div class="summary-detail">${changePercent >= 0 ? '+' : ''}${changePercent}% przez ${yearDiff} lat</div>
      </div>
      <div class="summary-card">
        <h4>Średni wzrost roczny</h4>
        <div class="summary-value">${avgPerYear} osób/rok</div>
      </div>
      <div class="summary-card">
        <h4>Struktura wyznaniowa ${data1.rok}</h4>
        <div class="summary-detail">
          Katolicy: ${data1.katolicy || 0}<br>
          Żydzi: ${data1.zydzi || 0}<br>
          Inni: ${data1.inni || 0}
        </div>
      </div>
      <div class="summary-card">
        <h4>Struktura wyznaniowa ${data2.rok}</h4>
        <div class="summary-detail">
          Katolicy: ${data2.katolicy || 0}<br>
          Żydzi: ${data2.zydzi || 0}<br>
          Inni: ${data2.inni || 0}
        </div>
      </div>
    </div>
  `;
}

/**
 * Zamyka modal porównania.
 */
function closeComparisonModal() {
  const modal = document.getElementById('comparison-modal');
  if (modal) {
    modal.remove();
  }
  if (charts.comparison) {
    charts.comparison.destroy();
    delete charts.comparison;
  }
}

/* ==========================================================================
   POWIADOMIENIA (Toast)
   ========================================================================== */

/**
 * Prosty system toastów (kontener #toast-container w HTML).
 * @param {'success'|'error'|'info'} type
 * @param {string} title
 * @param {string} message
 */
function showToast(type, title, message) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <div class="toast-icon">
      <i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'times' : 'info'}"></i>
    </div>
    <div class="toast-content">
      <div class="toast-title">${title}</div>
      <div class="toast-message">${message}</div>
    </div>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'toastOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

/* ==========================================================================
   SKRÓTY KLAWISZOWE
   ========================================================================== */

/**
 * Podstawowe skróty: Ctrl+F (search), D (dark), Esc (zamknij).
 */
function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ctrl+F – szybkie wyszukiwanie
    if (e.ctrlKey && (e.key === 'f' || e.key === 'F')) {
      e.preventDefault();
      document.getElementById('search-toggle')?.click();
    }
    // D – przełącz tryb ciemny (jeśli fokus nie w input/textarea)
    if ((e.key === 'd' || e.key === 'D') && !e.target.matches('input, textarea')) {
      document.getElementById('theme-toggle')?.click();
      }
      // Esc – zamknij modal / wyszukiwarkę
      if (e.key === 'Escape') {
      document.querySelector('.modal.active')?.classList.remove('active');
      document.getElementById('search-bar')?.classList.remove('active');
      }
      });
      }

      /**
      * Pobiera i wyświetla 4 nowe statystyki demograficzne.
      */
      async function loadGenealogyDemographicStats() {
      try {
      console.log('📊 Ładowanie statystyk demograficznych...');
      const response = await fetch('/api/genealogy/demographic-stats');

      if (!response.ok) {
      throw new Error(`Błąd HTTP: ${response.status}`);
      }

      const data = await response.json();
      console.log('📦 Otrzymane statystyki demograficzne:', data);

      // Renderowanie wszystkich 4 statystyk
      renderInfantMortality(data.infant_mortality);
      renderLifeExpectancy(data.life_expectancy);
      renderSeasonality(data.seasonality);
      renderFamilyStructure(data.family_structure);

      } catch (error) {
      console.error('❌ Błąd podczas ładowania statystyk demograficznych:', error);
      showToast('error', 'Błąd', 'Nie udało się załadować statystyk demograficznych');
      }
      }

      /**
      * Renderuje wykres śmiertelności niemowląt.
      */
      function renderInfantMortality(data) {
      // Aktualizacja statystyk
      document.getElementById('infant-mortality-rate').textContent = `${data.mortality_rate}%`;
      document.getElementById('total-births').textContent = data.total_births;
      document.getElementById('infant-deaths').textContent = data.infant_deaths;

      // Przygotowanie danych dla wykresu
      const labels = data.by_category.map(item => item.category);
      const counts = data.by_category.map(item => item.count);

      const ctx = document.getElementById('infant-mortality-chart')?.getContext('2d');
      if (!ctx) return;

      // Niszczenie poprzedniego wykresu jeśli istnieje
      if (charts.infantMortality) charts.infantMortality.destroy();

      charts.infantMortality = new Chart(ctx, {
      type: 'bar',
      data: {
      labels: labels,
      datasets: [{
       label: 'Liczba zgonów',
       data: counts,
       backgroundColor: [
         'rgba(239, 68, 68, 0.8)',   // Czerwony
         'rgba(245, 158, 11, 0.8)',  // Pomarańczowy
         'rgba(251, 191, 36, 0.8)',  // Żółty
         'rgba(163, 230, 53, 0.8)'   // Zielony
       ],
       borderColor: [
         'rgb(239, 68, 68)',
         'rgb(245, 158, 11)',
         'rgb(251, 191, 36)',
         'rgb(163, 230, 53)'
       ],
       borderWidth: 2,
       borderRadius: 6
      }]
      },
      options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
       legend: { display: false },
       tooltip: {
         callbacks: {
           label: function(context) {
             return `Zgony: ${context.parsed.y}`;
           }
         }
       }
      },
      scales: {
       y: {
         beginAtZero: true,
         title: { display: true, text: 'Liczba zgonów' }
       },
       x: {
         title: { display: true, text: 'Grupa wiekowa' }
       }
      }
      }
      });
      }

      /**
      * Renderuje wykres długości życia według pokoleń.
      */
      function renderLifeExpectancy(data) {
      const labels = data.map(item => item.decade_label);
      const ages = data.map(item => item.average_age);
      const counts = data.map(item => item.count);

      const ctx = document.getElementById('life-expectancy-chart')?.getContext('2d');
      if (!ctx) return;

      if (charts.lifeExpectancy) charts.lifeExpectancy.destroy();

      charts.lifeExpectancy = new Chart(ctx, {
      type: 'line',
      data: {
      labels: labels,
      datasets: [{
       label: 'Średnia długość życia',
       data: ages,
       borderColor: 'rgb(75, 192, 192)',
       backgroundColor: 'rgba(75, 192, 192, 0.2)',
       borderWidth: 3,
       fill: true,
       tension: 0.4,
       pointRadius: 5,
       pointHoverRadius: 8
      }]
      },
      options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
       legend: { display: false },
       tooltip: {
         callbacks: {
           label: function(context) {
             return `Średni wiek: ${context.parsed.y} lat (osób: ${counts[context.dataIndex]})`;
           }
         }
       }
      },
      scales: {
       y: {
         beginAtZero: false,
         title: { display: true, text: 'Średni wiek (lata)' }
       },
       x: {
         title: { display: true, text: 'Dekada urodzenia' }
       }
      }
      }
      });
      }

      /**
      * Renderuje wykresy sezonowości urodzeń i zgonów.
      */
      function renderSeasonality(data) {
      // Sezonowość urodzeń
      const birthCtx = document.getElementById('birth-seasonality-chart')?.getContext('2d');
      if (birthCtx) {
      if (charts.birthSeasonality) charts.birthSeasonality.destroy();

      charts.birthSeasonality = new Chart(birthCtx, {
      type: 'bar',
      data: {
       labels: data.births.map(item => item.month),
       datasets: [{
         label: 'Liczba urodzeń',
         data: data.births.map(item => item.count),
         backgroundColor: 'rgba(54, 162, 235, 0.8)',
         borderColor: 'rgb(54, 162, 235)',
         borderWidth: 2,
         borderRadius: 4
       }]
      },
      options: {
       responsive: true,
       maintainAspectRatio: false,
       plugins: {
         legend: { display: false }
       },
       scales: {
         y: { beginAtZero: true, title: { display: true, text: 'Liczba urodzeń' } },
         x: { title: { display: true, text: 'Miesiąc' } }
       }
      }
      });
      }

      // Sezonowość zgonów
      const deathCtx = document.getElementById('death-seasonality-chart')?.getContext('2d');
      if (deathCtx) {
      if (charts.deathSeasonality) charts.deathSeasonality.destroy();

      charts.deathSeasonality = new Chart(deathCtx, {
      type: 'bar',
      data: {
       labels: data.deaths.map(item => item.month),
       datasets: [{
         label: 'Liczba zgonów',
         data: data.deaths.map(item => item.count),
         backgroundColor: 'rgba(255, 99, 132, 0.8)',
         borderColor: 'rgb(255, 99, 132)',
         borderWidth: 2,
         borderRadius: 4
       }]
      },
      options: {
       responsive: true,
       maintainAspectRatio: false,
       plugins: {
         legend: { display: false }
       },
       scales: {
         y: { beginAtZero: true, title: { display: true, text: 'Liczba zgonów' } },
         x: { title: { display: true, text: 'Miesiąc' } }
       }
      }
      });
      }
      }

      /**
      * Renderuje wykres struktury rodzin i statystyki.
      */
      function renderFamilyStructure(data) {
      // Aktualizacja statystyk
      document.getElementById('avg-children').textContent = data.average_children;
      document.getElementById('total-families').textContent = data.total_families;
      document.getElementById('total-households').textContent = data.household_stats.total_households;
      document.getElementById('avg-household-size').textContent = data.household_stats.average_size;

      // Wykres rozkładu wielkości rodzin
      const ctx = document.getElementById('family-structure-chart')?.getContext('2d');
      if (!ctx) return;

      const labels = data.size_distribution.map(item => item.category);
      const counts = data.size_distribution.map(item => item.count);

      if (charts.familyStructure) charts.familyStructure.destroy();

      charts.familyStructure = new Chart(ctx, {
      type: 'doughnut',
      data: {
      labels: labels,
      datasets: [{
       data: counts,
       backgroundColor: [
         'rgba(255, 206, 86, 0.8)',   // Żółty
         'rgba(75, 192, 192, 0.8)',    // Zielony
         'rgba(54, 162, 235, 0.8)',    // Niebieski
         'rgba(153, 102, 255, 0.8)',   // Fioletowy
         'rgba(255, 159, 64, 0.8)'     // Pomarańczowy
       ],
       borderColor: [
         'rgb(255, 206, 86)',
         'rgb(75, 192, 192)',
         'rgb(54, 162, 235)',
         'rgb(153, 102, 255)',
         'rgb(255, 159, 64)'
       ],
       borderWidth: 2
      }]
      },
      options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
       legend: {
         position: 'bottom',
         labels: {
           padding: 15,
           font: { size: 12 }
         }
       },
       tooltip: {
         callbacks: {
           label: function(context) {
             const total = context.dataset.data.reduce((a, b) => a + b, 0);
             const percentage = ((context.parsed / total) * 100).toFixed(1);
             return `${context.label}: ${context.parsed} rodzin (${percentage}%)`;
           }
         }
       }
      }
      }
      });
      }
