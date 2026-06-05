/**
 * Rankingi infrastruktury centrum analitycznego (P2.8 Etap 13).
 *
 * Dostęp przez `window.StatsInfrastructureRanking`.
 */
(function () {
  'use strict';

  if (!window.OwnersAPI) {
    throw new Error('stats-infrastructure-ranking.js wymaga js/api.js załadowanego wcześniej');
  }

  const API = window.OwnersAPI;

  function init(riversData, roadsData) {
    displayRivers(riversData);
    displayRoads(roadsData);
  }

  function displayRivers(riversData) {
    const container = document.getElementById('rivers-ranking-list');
    if (!container || !riversData) return;

    container.innerHTML = riversData.slice(0, 50).map((river, index) => {
      const pos = index + 1;
      const cls = _positionClass(pos);
      const lengthDisplay = _formatLength(river.length_m || 0);
      const riverName = river.river_name || 'Bez nazwy';

      return `
        <div class="ranking-item" style="cursor: default;">
          <div class="ranking-position-badge ${cls}">${pos}</div>
          <div class="ranking-content">
            <div class="ranking-title">${riverName}</div>
            <div class="ranking-meta"><i class="fas fa-water"></i> Rzeka</div>
          </div>
          <div class="ranking-metrics">
            <div class="metric-primary">${lengthDisplay}</div>
            <div class="metric-secondary">Długość</div>
          </div>
          <button class="btn-icon" onclick="window.location.href='${API.mapPage()}?highlightRivers=${encodeURIComponent(river.river_name)}'" title="Pokaż na mapie" style="margin-left:auto"><i class="fas fa-map"></i></button>
        </div>`;
    }).join('');
  }

  function displayRoads(roadsData) {
    const container = document.getElementById('roads-ranking-list');
    if (!container || !roadsData) return;

    container.innerHTML = roadsData.slice(0, 50).map((road, index) => {
      const pos = index + 1;
      const cls = _positionClass(pos);
      const lengthDisplay = _formatLength(road.length_m || 0);
      const roadNumber = road.road_number || 'Bez nazwy';

      return `
        <div class="ranking-item" style="cursor: default;">
          <div class="ranking-position-badge ${cls}">${pos}</div>
          <div class="ranking-content">
            <div class="ranking-title">${roadNumber}</div>
            <div class="ranking-meta"><i class="fas fa-road"></i> Droga</div>
          </div>
          <div class="ranking-metrics">
            <div class="metric-primary">${lengthDisplay}</div>
            <div class="metric-secondary">Długość</div>
          </div>
          <button class="btn-icon" onclick="window.location.href='${API.mapPage()}?highlightRoads=${encodeURIComponent(road.road_number)}'" title="Pokaż na mapie" style="margin-left:auto"><i class="fas fa-map"></i></button>
        </div>`;
    }).join('');
  }

  function _positionClass(pos) {
    if (pos === 1) return 'gold';
    if (pos === 2) return 'silver';
    if (pos === 3) return 'bronze';
    return '';
  }

  function _formatLength(lengthM) {
    const lengthKm = lengthM / 1000;
    return lengthKm >= 1 ? `${lengthKm.toFixed(2)} km` : `${Math.round(lengthM)} m`;
  }

  window.StatsInfrastructureRanking = Object.freeze({
    init: init,
    displayRivers: displayRivers,
    displayRoads: displayRoads,
  });
})();
