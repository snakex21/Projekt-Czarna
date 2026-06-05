/**
 * Pobieranie danych centrum analitycznego (P2.8 Etap 4).
 *
 * Kolejność ładowania:
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/stats-ui.js
 *   4. js/stats-actions.js
 *   5. js/stats-data.js  ← ten plik
 *   6. stats-script.js
 *
 * Dostęp przez `window.StatsData`.
 */
(function () {
  'use strict';

  if (!window.OwnersAPI) {
    throw new Error('stats-data.js wymaga js/api.js załadowanego wcześniej');
  }

  const API = window.OwnersAPI;

  async function load() {
    const response = await fetch(API.stats(), {
      credentials: 'same-origin',
    });
    if (!response.ok) {
      const message = await response.text().catch(() => '');
      throw new Error(`API ${API.stats()} zwróciło ${response.status}: ${message.slice(0, 200)}`);
    }
    return response.json();
  }

  window.StatsData = Object.freeze({
    load: load,
  });
})();
