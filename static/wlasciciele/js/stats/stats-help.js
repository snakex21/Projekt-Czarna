/**
 * Modal pomocy centrum analitycznego (P2.8 Etap 5).
 *
 * Kolejność ładowania:
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/stats-ui.js
 *   4. js/stats-actions.js
 *   5. js/stats-data.js
 *   6. js/stats-help.js  ← ten plik
 *   7. stats-script.js
 *
 * Dostęp przez `window.StatsHelp`.
 */
(function () {
  'use strict';

  function init() {
    const helpBtn = document.getElementById('help-btn');
    const modal = document.getElementById('help-modal');
    const closeBtn = modal?.querySelector('.modal-close');

    helpBtn?.addEventListener('click', () => modal.classList.add('active'));
    closeBtn?.addEventListener('click', () => modal.classList.remove('active'));
    modal?.addEventListener('click', (event) => {
      if (event.target === modal) modal.classList.remove('active');
    });
  }

  window.StatsHelp = Object.freeze({
    init: init,
  });
})();
