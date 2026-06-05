/**
 * Zakładki i przełączniki rankingów centrum analitycznego (P2.8 Etap 8).
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
 *   9. js/stats-tabs.js  ← ten plik
 *   10. stats-script.js
 *
 * Dostęp przez `window.StatsTabs`.
 */
(function () {
  'use strict';

  function init(options) {
    _initTabs(options.loadTimeline);
    _initRankingTypeSelector();
    _initInfrastructureTypeSelector();
  }

  function _initTabs(loadTimeline) {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabButtons.forEach(button => {
      button.addEventListener('click', () => {
        const targetTab = button.dataset.tab;

        tabButtons.forEach(btn => btn.classList.remove('active'));
        tabPanels.forEach(panel => panel.classList.remove('active'));

        button.classList.add('active');
        document.getElementById(targetTab)?.classList.add('active');

        if (targetTab === 'timeline' && !button.dataset.loaded) {
          loadTimeline();
          button.dataset.loaded = 'true';
        }
      });
    });
  }

  function _initRankingTypeSelector() {
    const rankingTypeInputs = document.querySelectorAll('input[name="ranking-type"]');

    rankingTypeInputs.forEach(input => {
      input.addEventListener('change', () => {
        switchRankingView(input.value);
      });
    });
  }

  function _initInfrastructureTypeSelector() {
    const inputs = document.querySelectorAll('input[name="infra-type"]');
    inputs.forEach(input => {
      input.addEventListener('change', () => {
        const isRivers = input.value === 'rivers';
        document.getElementById('infra-view-rivers').style.display = isRivers ? 'block' : 'none';
        document.getElementById('infra-view-roads').style.display = isRivers ? 'none' : 'block';
      });
    });
  }

  function switchRankingView(type) {
    const views = {
      'owners': document.getElementById('ranking-view-owners'),
      'parcels': document.getElementById('ranking-view-parcels'),
      'infrastructure': document.getElementById('ranking-view-infrastructure')
    };

    Object.values(views).forEach(view => {
      if (view) view.style.display = 'none';
    });

    if (views[type]) {
      views[type].style.display = 'block';
    }
  }

  window.StatsTabs = Object.freeze({
    init: init,
    switchRankingView: switchRankingView,
  });
})();
