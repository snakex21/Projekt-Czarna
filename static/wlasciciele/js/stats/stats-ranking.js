/**
 * Ranking właścicieli centrum analitycznego (P2.8 Etap 11).
 *
 * Kolejność ładowania:
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/stats-ui.js
 *   4. js/stats-actions.js
 *   5. js/stats-data.js
 *   6. js/stats-help.js
 *   7. js/stats-search.js
 *   8. js/stats-counters.js
 *   9. js/stats-tabs.js
 *   10. js/stats-metrics.js
 *   11. js/stats-jewish.js
 *   12. js/stats-ranking.js  ← ten plik
 *   13. stats-script.js
 *
 * Dostęp przez `window.StatsRanking`.
 */
(function () {
  'use strict';

  if (!window.OwnersUtils) {
    throw new Error('stats-ranking.js wymaga js/utils.js załadowanego wcześniej');
  }

  const UTILS = window.OwnersUtils;
  let callbacks = {
    getStatsData: () => null,
    performSearch: () => undefined,
  };

  function init(data, options) {
    callbacks = options;
    const container = document.getElementById('ranking-list');
    if (!container) return;

    display(data.rankings_real.all_plots || [], container);

    document.querySelectorAll('input[name="ownership"]').forEach(radio => {
      radio.addEventListener('change', filter);
    });
    document.querySelectorAll('input[name="sort-by"]').forEach(radio => {
      radio.addEventListener('change', filter);
    });
    document.getElementById('category-filter')?.addEventListener('change', filter);
  }

  function display(rankingData, container) {
    const sortBy = document.querySelector('input[name="sort-by"]:checked')?.value || 'count';

    container.innerHTML = (rankingData || []).slice(0, 50).map((owner, index) => {
      const pos = index + 1;
      const cls = pos === 1 ? 'gold' : pos === 2 ? 'silver' : pos === 3 ? 'bronze' : '';
      const protocolNumber = owner.numer_protokolu ?? '-';
      const areaM2 = owner.total_area_m2 || 0;
      const plotCount = owner.plot_count || 0;

      let primaryVal;
      let secondaryVal;
      if (sortBy === 'area') {
        primaryVal = UTILS.formatArea(areaM2);
        secondaryVal = `${plotCount} działek`;
      } else {
        primaryVal = plotCount;
        secondaryVal = UTILS.formatArea(areaM2);
      }

      return `
        <a href="../wlasciciele/protokol.html?ownerId=${owner.unikalny_klucz}" class="ranking-item">
          <div class="ranking-position-badge ${cls}">${pos}</div>
          <div class="ranking-content">
            <div class="ranking-title">${owner.nazwa_wlasciciela}</div>
            <div class="ranking-meta">
              <i class="fas fa-file-contract"></i> Protokół ${protocolNumber}
            </div>
          </div>
          <div class="ranking-metrics">
            <div class="metric-primary">${primaryVal}</div>
            <div class="metric-secondary">${secondaryVal}</div>
          </div>
        </a>`;
    }).join('');
  }

  function filter() {
    const statsData = callbacks.getStatsData();
    if (!statsData) return;

    const ownership = document.querySelector('input[name="ownership"]:checked')?.value || 'real';
    const category = document.getElementById('category-filter')?.value || 'all';
    const sortBy = document.querySelector('input[name="sort-by"]:checked')?.value || 'count';
    const container = document.getElementById('ranking-list');

    const dataSet = ownership === 'real' ? statsData.rankings_real : statsData.rankings_protocol;
    let rankingData = category === 'all' ? dataSet.all_plots : dataSet[category];
    if (!rankingData) rankingData = [];

    rankingData = [...rankingData].sort((a, b) => {
      if (sortBy === 'area') {
        return (b.total_area_m2 || 0) - (a.total_area_m2 || 0);
      }
      return (b.plot_count || 0) - (a.plot_count || 0);
    });

    display(rankingData, container);

    const searchQuery = document.getElementById('global-search')?.value || '';
    callbacks.performSearch(searchQuery);
  }

  window.StatsRanking = Object.freeze({
    init: init,
    display: display,
    filter: filter,
  });
})();
