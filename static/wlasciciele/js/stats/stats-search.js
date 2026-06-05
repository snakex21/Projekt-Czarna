/**
 * Globalna wyszukiwarka centrum analitycznego (P2.8 Etap 6).
 *
 * Kolejność ładowania:
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/stats-ui.js
 *   4. js/stats-actions.js
 *   5. js/stats-data.js
 *   6. js/stats-help.js
 *   7. js/stats-search.js  ← ten plik
 *   8. stats-script.js
 *
 * Dostęp przez `window.StatsSearch`.
 */
(function () {
  'use strict';

  if (!window.OwnersUtils) {
    throw new Error('stats-search.js wymaga js/utils.js załadowanego wcześniej');
  }

  const UTILS = window.OwnersUtils;
  let getStatsData = () => null;

  function _getResultsContainer() {
    return document.querySelector('.search-results-container');
  }

  function _clearResults(resultsContainer) {
    resultsContainer.classList.remove('visible');
    resultsContainer.innerHTML = '';
  }

  function init(options) {
    getStatsData = options.getStatsData;
    const searchToggle = document.getElementById('search-toggle');
    const searchBar = document.getElementById('search-bar');
    const searchClose = document.getElementById('search-close');
    const searchInput = document.getElementById('global-search');
    const searchContainer = document.querySelector('.search-container');

    let resultsContainer = _getResultsContainer();
    if (!resultsContainer) {
      resultsContainer = document.createElement('div');
      resultsContainer.className = 'search-results-container';
      searchContainer.appendChild(resultsContainer);
    }

    searchToggle?.addEventListener('click', () => {
      searchBar.classList.toggle('active');
      if (searchBar.classList.contains('active')) {
        searchInput?.focus();
      } else {
        resultsContainer.classList.remove('visible');
      }
    });

    searchClose?.addEventListener('click', () => {
      searchBar.classList.remove('active');
      if (searchInput) searchInput.value = '';
      _clearResults(resultsContainer);
    });

    searchInput?.addEventListener('input', (event) => {
      const query = event.target.value.trim();
      if (query.length > 1) {
        perform(query);
      } else {
        _clearResults(resultsContainer);
      }
    });

    document.addEventListener('click', (event) => {
      if (!searchContainer.contains(event.target) && !searchToggle.contains(event.target)) {
        resultsContainer.classList.remove('visible');
      }
    });
  }

  function perform(query) {
    const statsData = getStatsData();
    if (!statsData) return;

    const normalizedQuery = query.toLowerCase();
    const resultsContainer = _getResultsContainer();

    if (!resultsContainer) {
      console.warn('Search results container not found, skipping render');
      return;
    }

    resultsContainer.innerHTML = '';

    const results = {
      owners: [],
      parcels: []
    };

    if (statsData.rankings_real && statsData.rankings_real.all_plots) {
      results.owners = statsData.rankings_real.all_plots.filter(owner => {
        const name = (owner.nazwa_wlasciciela || '').toLowerCase();
        return name.includes(normalizedQuery);
      }).slice(0, 5);
    }

    if (statsData.parcels_ranking && statsData.parcels_ranking.all) {
      results.parcels = statsData.parcels_ranking.all.filter(parcel => {
        return (parcel.parcel_number || '').toString().includes(normalizedQuery);
      }).slice(0, 5);
    }

    if (results.owners.length === 0 && results.parcels.length === 0) {
      resultsContainer.innerHTML = `
        <div class="no-results">
          <i class="fas fa-search"></i>
          <p>Nie znaleziono wyników dla "${query}"</p>
        </div>
      `;
    } else {
      _renderOwners(results.owners, resultsContainer);
      _renderParcels(results.parcels, resultsContainer);
    }

    resultsContainer.classList.add('visible');
  }

  function _renderOwners(owners, resultsContainer) {
    if (owners.length === 0) return;

    const category = document.createElement('div');
    category.className = 'search-result-category';
    category.textContent = 'Właściciele';
    resultsContainer.appendChild(category);

    owners.forEach(owner => {
      const item = document.createElement('div');
      item.className = 'search-result-item';
      const areaDisplay = UTILS.formatArea(owner.total_area_m2 || 0);
      item.innerHTML = `
        <div class="result-icon"><i class="fas fa-user"></i></div>
        <div class="result-content">
          <span class="result-title">${owner.nazwa_wlasciciela}</span>
          <span class="result-subtitle">
            Klucz: ${owner.unikalny_klucz} | Działek: ${owner.plot_count} | Pow: ${areaDisplay}
          </span>
        </div>
      `;
      item.addEventListener('click', () => {
        window.location.href = `../wlasciciele/protokol.html?ownerId=${owner.unikalny_klucz}`;
      });
      resultsContainer.appendChild(item);
    });
  }

  function _renderParcels(parcels, resultsContainer) {
    if (parcels.length === 0) return;

    const category = document.createElement('div');
    category.className = 'search-result-category';
    category.textContent = 'Działki';
    resultsContainer.appendChild(category);

    parcels.forEach(parcel => {
      const areaM2 = parcel.area_m2 || parcel.area || 0;
      const areaDisplay = UTILS.formatArea(areaM2);
      const item = document.createElement('div');
      item.className = 'search-result-item';
      item.innerHTML = `
        <div class="result-icon"><i class="fas fa-map-marker-alt"></i></div>
        <div class="result-content">
          <span class="result-title">Działka nr ${parcel.parcel_number}</span>
          <span class="result-subtitle">Powierzchnia: ${areaDisplay}</span>
        </div>
      `;
      item.addEventListener('click', () => {
        if (parcel.unikalny_klucz) {
          window.location.href = `../wlasciciele/protokol.html?ownerId=${parcel.unikalny_klucz}`;
        } else {
          window.location.href = `../mapa/mapa.html?highlightParcel=${parcel.parcel_number}`;
        }
      });
      resultsContainer.appendChild(item);
    });
  }

  function highlightText(element, query) {
    const regex = new RegExp(query, 'gi');

    function walk(node) {
      if (node.nodeType === 3) {
        const text = node.textContent;
        if (regex.test(text)) {
          const span = document.createElement('span');
          span.innerHTML = text.replace(regex, match => `<mark class="search-highlight">${match}</mark>`);
          node.parentNode.replaceChild(span, node);
        }
      } else if (node.nodeType === 1 && node.nodeName !== 'MARK') {
        Array.from(node.childNodes).forEach(walk);
      }
    }

    walk(element);
  }

  function clearHighlights(container) {
    const highlights = container.querySelectorAll('mark.search-highlight');
    highlights.forEach(mark => { if (mark.parentNode) mark.outerHTML = mark.innerHTML; });
    container.normalize();
  }

  window.StatsSearch = Object.freeze({
    init: init,
    perform: perform,
    highlightText: highlightText,
    clearHighlights: clearHighlights,
  });
})();
