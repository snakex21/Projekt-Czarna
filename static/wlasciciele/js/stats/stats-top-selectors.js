/**
 * Selektory TOP 10 dla akcji centrum analitycznego (P2.8 Etap 19).
 *
 * Dostęp przez window.StatsTopSelectors.
 */
(function () {
  'use strict';

  let getStatsData = () => null;

  function init(callbacks) {
    callbacks = callbacks || {};
    getStatsData = callbacks.getStatsData || getStatsData;
  }

/**
 * Zwraca Top 10 właścicieli dla zadanych filtrów.
 * @param {'real'|'protocol'} ownership
 * @param {string} category
 */
function getTop10Owners(ownership, category) {
  const statsData = getStatsData();
  const data = ownership === 'real' ? statsData.rankings_real : statsData.rankings_protocol;
  let rankingData = category === 'all' ? data.all_plots : data[category];
  const sortBy = document.querySelector('input[name="sort-by"]:checked')?.value || 'count';

  if (rankingData) {
    rankingData = [...rankingData].sort((a, b) => {
      if (sortBy === 'area') {
        return (b.total_area_m2 || 0) - (a.total_area_m2 || 0);
      } else {
        return (b.plot_count || 0) - (a.plot_count || 0);
      }
    });
  }

  return rankingData?.slice(0, 10) || [];
}

/**
 * Zwraca Top 10 działek według powierzchni.
 */
function getTop10Parcels() {
  const category = document.getElementById('parcel-category-filter')?.value || 'all';
  const statsData = getStatsData();
  const parcelsData = statsData?.parcels_ranking;
  if (!parcelsData) return [];

  const rankingData = category === 'all' ? parcelsData.all : parcelsData[category];
  return (rankingData || []).slice(0, 10);
}

/**
 * Zwraca Top 10 rzek według długości.
 */
function getTop10Rivers() {
  const statsData = getStatsData();
  return (statsData?.rivers_ranking || []).slice(0, 10);
}

/**
 * Zwraca Top 10 dróg według długości.
 */
function getTop10Roads() {
  const statsData = getStatsData();
  return (statsData?.roads_ranking || []).slice(0, 10);
}



  window.StatsTopSelectors = Object.freeze({
    init: init,
    getTop10Owners: getTop10Owners,
    getTop10Parcels: getTop10Parcels,
    getTop10Rivers: getTop10Rivers,
    getTop10Roads: getTop10Roads,
  });
})();
