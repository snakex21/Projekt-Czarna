/**
 * Ranking działek według powierzchni w centrum analitycznym (P2.8 Etap 12).
 *
 * Dostęp przez `window.StatsParcelsRanking`.
 */
(function () {
  'use strict';

  if (!window.OwnersUtils) {
    throw new Error('stats-parcels-ranking.js wymaga js/utils.js załadowanego wcześniej');
  }

  const UTILS = window.OwnersUtils;

  function init(parcelsData) {
    if (!parcelsData) return;

    const container = document.getElementById('parcels-ranking-list');
    if (!container) return;

    display(parcelsData.all || [], container);

    const categoryFilter = document.getElementById('parcel-category-filter');
    if (categoryFilter) {
      categoryFilter.addEventListener('change', () => {
        const category = categoryFilter.value || 'all';
        const rankingData = category === 'all' ? parcelsData.all : parcelsData[category];
        display(rankingData || [], container);
      });
    }
  }

  function display(parcelsData, container) {
    container.innerHTML = (parcelsData || []).slice(0, 50).map((parcel, index) => {
      const pos = index + 1;
      const cls = pos === 1 ? 'gold' : pos === 2 ? 'silver' : pos === 3 ? 'bronze' : '';
      const owner = parcel.nazwa_wlasciciela || 'Brak właściciela';
      const areaM2 = parcel.area_m2 || 0;
      const ownerDisplay = _formatOwnerDisplay(parcel, owner);

      return `
        <div class="ranking-item" style="cursor: default;">
          <div class="ranking-position-badge ${cls}">${pos}</div>
          <div class="ranking-content">
            <div class="ranking-title">Działka nr ${parcel.parcel_number}</div>
            <div class="ranking-meta">
               <i class="fas fa-user-tag"></i> ${ownerDisplay}
            </div>
          </div>
          <div class="ranking-metrics">
            <div class="metric-primary">${UTILS.formatArea(areaM2)}</div>
            <div class="metric-secondary">Powierzchnia</div>
          </div>
          ${parcel.unikalny_klucz ? '' : _renderMapButton(parcel)}
        </div>`;
    }).join('');
  }

  function _formatOwnerDisplay(parcel, owner) {
    if (owner.includes(', ')) {
      const firstOwner = owner.split(', ')[0];
      const count = owner.split(', ').length - 1;
      const label = firstOwner + ` (+${count})`;
      return _ownerLink(parcel, label);
    }

    return _ownerLink(parcel, owner);
  }

  function _ownerLink(parcel, label) {
    if (!parcel.unikalny_klucz) return label;
    return `<a href="../wlasciciele/protokol.html?ownerId=${parcel.unikalny_klucz}" style="color: inherit; text-decoration: underline;">${label}</a>`;
  }

  function _renderMapButton(parcel) {
    return `<button class="btn-icon" onclick="window.location.href='../mapa/mapa.html?highlightParcel=${parcel.parcel_number}'" title="Pokaż na mapie" style="margin-left:auto"><i class="fas fa-map-marker-alt"></i></button>`;
  }

  window.StatsParcelsRanking = Object.freeze({
    init: init,
    display: display,
  });
})();
