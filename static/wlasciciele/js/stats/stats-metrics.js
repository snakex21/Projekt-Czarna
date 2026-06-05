/**
 * Podstawowe metryki centrum analitycznego (P2.8 Etap 9).
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
 *   10. js/stats-metrics.js  ← ten plik
 *   11. stats-script.js
 *
 * Dostęp przez `window.StatsMetrics`.
 */
(function () {
  'use strict';

  function updateArea(areaStats) {
    if (!areaStats) return;

    const totalHa = document.getElementById('stat-total-area-ha');
    const avgAres = document.getElementById('stat-avg-area-ares');
    const minM2 = document.getElementById('stat-min-area-m2');
    const maxHa = document.getElementById('stat-max-area-ha');

    if (totalHa) totalHa.textContent = `${areaStats.total_area_ha.toFixed(2)} ha`;
    if (avgAres) avgAres.textContent = `${areaStats.avg_area_ares.toFixed(2)} arów`;
    if (minM2) minM2.textContent = `${Math.round(areaStats.min_area_m2)} m²`;
    if (maxHa) {
      const maxHaValue = areaStats.max_area_m2 / 10000;
      maxHa.textContent = maxHaValue < 1
        ? `${Math.round(areaStats.max_area_m2)} m²`
        : `${maxHaValue.toFixed(2)} ha`;
    }
  }

  function updateRiversRoads(riversStats, roadsStats) {
    if (riversStats) {
      const riversCount = document.getElementById('stat-rivers-count');
      const riverMax = document.getElementById('stat-river-max');
      const riverAvg = document.getElementById('stat-river-avg');
      const riverMin = document.getElementById('stat-river-min');

      if (riversCount) riversCount.textContent = riversStats.total_count;
      if (riverMax) riverMax.textContent = `${Math.round(riversStats.max_length_m)} m`;
      if (riverAvg) riverAvg.textContent = `${Math.round(riversStats.avg_length_m)} m`;
      if (riverMin) riverMin.textContent = `${Math.round(riversStats.min_length_m)} m`;
    }

    if (roadsStats) {
      const roadsCount = document.getElementById('stat-roads-count');
      const roadMax = document.getElementById('stat-road-max');
      const roadAvg = document.getElementById('stat-road-avg');
      const roadMin = document.getElementById('stat-road-min');

      if (roadsCount) roadsCount.textContent = roadsStats.total_count;
      if (roadMax) roadMax.textContent = `${Math.round(roadsStats.max_length_m)} m`;
      if (roadAvg) roadAvg.textContent = `${Math.round(roadsStats.avg_length_m)} m`;
      if (roadMin) roadMin.textContent = `${Math.round(roadsStats.min_length_m)} m`;
    }
  }

  function updateDrawnPercentage(drawnStats) {
    if (!drawnStats) return;

    const drawnCount = document.getElementById('drawn-count');
    const protocolCount = document.getElementById('protocol-count');
    const drawnPercentage = document.getElementById('drawn-percentage');
    const missingCount = document.getElementById('missing-count');

    if (drawnCount) drawnCount.textContent = drawnStats.drawn_count || 0;
    if (protocolCount) protocolCount.textContent = drawnStats.protocol_count || 0;
    if (drawnPercentage) drawnPercentage.textContent = `${drawnStats.percentage || 0}%`;
    if (missingCount) missingCount.textContent = drawnStats.missing_count || 0;
  }

  function updateLocationArea(areaStats) {
    if (!areaStats) return;

    const areaHa = document.getElementById('location-area-ha');
    const areaKm2 = document.getElementById('location-area-km2');

    if (areaHa) areaHa.textContent = areaStats.area_hectares ? `${areaStats.area_hectares} ha` : '-';
    if (areaKm2) areaKm2.textContent = areaStats.area_km2 ? `${areaStats.area_km2} km²` : '-';
  }

  window.StatsMetrics = Object.freeze({
    updateArea: updateArea,
    updateRiversRoads: updateRiversRoads,
    updateDrawnPercentage: updateDrawnPercentage,
    updateLocationArea: updateLocationArea,
  });
})();
