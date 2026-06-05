/**
 * Akcje przycisków centrum analitycznego (P2.8 Etap 3).
 *
 * Kolejność ładowania:
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/stats-ui.js
 *   4. js/stats-actions.js  ← ten plik
 *   5. stats-script.js
 *
 * Dostęp przez `window.StatsActions`.
 */
(function () {
  'use strict';

  if (!window.OwnersAPI) {
    throw new Error('stats-actions.js wymaga js/api.js załadowanego wcześniej');
  }

  const API = window.OwnersAPI;

  function _goToMap(query) {
    window.location.href = query ? `${API.mapPage()}?${query}` : API.mapPage();
  }

  function _bindExportCharts(callbacks) {
    document.getElementById('export-chart1')?.addEventListener('click', () => callbacks.exportChart('pieChart'));
    document.getElementById('export-chart2')?.addEventListener('click', () => callbacks.exportChart('barChart'));
  }

  function _bindOwnersOnMap(callbacks) {
    document.getElementById('show-on-map')?.addEventListener('click', () => {
      const ownership = document.querySelector('input[name="ownership"]:checked')?.value || 'real';
      const category = document.getElementById('category-filter')?.value || 'all';
      const topOwners = callbacks.getTop10Owners(ownership, category);
      const ownerKeys = topOwners.map(owner => owner.unikalny_klucz).join(',');
      _goToMap(`highlightTopOwners=${encodeURIComponent(ownerKeys)}&ownership=${ownership}`);
    });
  }

  function _bindParcelsOnMap(callbacks) {
    document.getElementById('show-parcels-on-map')?.addEventListener('click', () => {
      const topParcels = callbacks.getTop10Parcels();
      const parcelNumbers = topParcels.map(parcel => parcel.parcel_number).join(',');
      if (parcelNumbers) {
        _goToMap(`highlightParcels=${encodeURIComponent(parcelNumbers)}`);
        callbacks.showToast('success', 'Przekierowanie', 'Pokazywanie TOP 10 działek na mapie');
      } else {
        _goToMap('');
        callbacks.showToast('info', 'Przekierowanie', 'Przejście do mapy');
      }
    });
  }

  function _bindRiversOnMap(callbacks) {
    document.getElementById('show-rivers-on-map')?.addEventListener('click', () => {
      const topRivers = callbacks.getTop10Rivers();
      const riverNames = topRivers.map(river => river.river_name).join(',');
      if (riverNames) {
        _goToMap(`highlightRivers=${encodeURIComponent(riverNames)}`);
        callbacks.showToast('success', 'Przekierowanie', 'Pokazywanie TOP 10 rzek na mapie');
      } else {
        _goToMap('');
        callbacks.showToast('info', 'Przekierowanie', 'Przejście do mapy');
      }
    });
  }

  function _bindRoadsOnMap(callbacks) {
    document.getElementById('show-roads-on-map')?.addEventListener('click', () => {
      const topRoads = callbacks.getTop10Roads();
      const roadNames = topRoads.map(road => road.road_name).join(',');
      if (roadNames) {
        _goToMap(`highlightRoads=${encodeURIComponent(roadNames)}`);
        callbacks.showToast('success', 'Przekierowanie', 'Pokazywanie TOP 10 dróg na mapie');
      } else {
        _goToMap('');
        callbacks.showToast('info', 'Przekierowanie', 'Przejście do mapy');
      }
    });
  }

  function _bindAnalyticalTools(callbacks) {
    document.getElementById('compare-btn')?.addEventListener('click', callbacks.openPeriodComparison);
    document.getElementById('export-btn')?.addEventListener('click', callbacks.exportToExcel);
    document.getElementById('print-btn')?.addEventListener('click', callbacks.printReport);
    document.getElementById('share-btn')?.addEventListener('click', callbacks.shareReport);
  }

  function init(callbacks) {
    _bindExportCharts(callbacks);
    _bindOwnersOnMap(callbacks);
    _bindParcelsOnMap(callbacks);
    _bindRiversOnMap(callbacks);
    _bindRoadsOnMap(callbacks);
    _bindAnalyticalTools(callbacks);
  }

  window.StatsActions = Object.freeze({
    init: init,
  });
})();
