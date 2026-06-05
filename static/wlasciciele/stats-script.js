/* ==========================================================================
   Plik: stats-script.js
   Opis: Bootstrap Centrum Analitycznego.
   ========================================================================== */

(function () {
  'use strict';

  if (!window.StatsApp) {
    throw new Error('stats-script.js wymaga js/stats-app.js załadowanego wcześniej');
  }

  document.addEventListener('DOMContentLoaded', () => {
    window.StatsApp.init();
  });
})();
