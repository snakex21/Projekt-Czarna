/**
 * Statystyki właścicieli żydowskich centrum analitycznego (P2.8 Etap 10).
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
 *   11. js/stats-jewish.js  ← ten plik
 *   12. stats-script.js
 *
 * Dostęp przez `window.StatsJewish`.
 */
(function () {
  'use strict';

  if (!window.OwnersAPI) {
    throw new Error('stats-jewish.js wymaga js/api.js załadowanego wcześniej');
  }

  const API = window.OwnersAPI;

  function update(jewishStats) {
    const section = document.getElementById('jewish-stats-section');
    if (!jewishStats || jewishStats.owners_count === 0) {
      if (section) section.style.display = 'none';
      return;
    }

    if (section) section.style.display = 'block';

    const ownersCount = document.getElementById('jewish-owners-count');
    const parcelsCount = document.getElementById('jewish-parcels-count');
    const totalArea = document.getElementById('jewish-total-area');

    if (ownersCount) ownersCount.textContent = jewishStats.owners_count || 0;
    if (parcelsCount) parcelsCount.textContent = jewishStats.parcels_count || 0;
    if (totalArea) totalArea.textContent = `${jewishStats.total_area_ha || 0} ha`;

    _renderOwnersTable(jewishStats);
    _bindMapButton(jewishStats);
  }

  function _renderOwnersTable(jewishStats) {
    const tableContainer = document.getElementById('jewish-owners-table-container');
    if (!tableContainer || !jewishStats.owners || jewishStats.owners.length === 0) return;

    let tableHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Właściciel</th>
            <th>Nr prot.</th>
            <th>Działek</th>
            <th>Pow. (ha)</th>
          </tr>
        </thead>
        <tbody>
    `;

    jewishStats.owners.forEach(owner => {
      const areaHa = (owner.total_area_m2 / 10000).toFixed(2);
      tableHTML += `
        <tr>
          <td><a href="/wlasciciele/protokol.html?ownerId=${owner.unikalny_klucz}">${owner.nazwa_wlasciciela}</a></td>
          <td>${owner.numer_protokolu}</td>
          <td>${owner.parcels_count}</td>
          <td>${areaHa} ha</td>
        </tr>
      `;
    });

    tableHTML += `
        </tbody>
      </table>
    `;
    tableContainer.innerHTML = tableHTML;
  }

  function _bindMapButton(jewishStats) {
    const showButton = document.getElementById('show-jewish-parcels');
    if (!showButton) return;

    showButton.onclick = () => {
      const ownership = 'real';
      const ownerKeys = jewishStats.owners.map(owner => owner.unikalny_klucz).join(',');
      window.location.href = `${API.mapPage()}?highlightTopOwners=${encodeURIComponent(ownerKeys)}&ownership=${ownership}`;
    };
  }

  window.StatsJewish = Object.freeze({
    update: update,
  });
})();
