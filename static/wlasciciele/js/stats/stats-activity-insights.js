/**
 * Kalendarz aktywności spisowej i podstawowe insighty centrum analitycznego (P2.8 Etap 18).
 *
 * Kolejność ładowania:
 *   1. js/stats-reports.js
 *   2. js/stats-activity-insights.js  ← ten plik
 *   3. stats-script.js
 *
 * Dostęp przez window.StatsActivityInsights.
 */
(function () {
  'use strict';

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
  const endDate = new Date(protocolsData[protocolsData.length - 1].protocol_date);

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
  document.getElementById('stat-buildings').textContent = counts.budynek || 0;
  document.getElementById('stat-chapels').textContent = counts.kapliczka || 0;
  document.getElementById('stat-special').textContent = counts.obiekt_specjalny || 0;

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



  window.StatsActivityInsights = Object.freeze({
    renderCalendar: renderActivityCalendar,
    loadInsights: loadInsights,
  });
})();
