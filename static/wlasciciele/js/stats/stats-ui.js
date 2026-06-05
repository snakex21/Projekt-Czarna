/**
 * Podstawowe interakcje UI centrum analitycznego (P2.8 Etap 2).
 *
 * Kolejność ładowania:
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/stats-ui.js  ← ten plik
 *   4. stats-script.js
 *
 * Dostęp przez `window.StatsUI`.
 */
(function () {
  'use strict';

  function applyTheme(theme) {
    const isDark = theme === 'dark';
    document.body.classList.toggle('dark-mode', isDark);
    const icon = document.querySelector('#theme-toggle i');
    if (icon) icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
  }

  function initThemeSync(showToast) {
    const savedTheme = localStorage.getItem('mapTheme') || 'light';
    applyTheme(savedTheme);

    window.addEventListener('storage', (event) => {
      if (event.key === 'mapTheme') applyTheme(event.newValue);
    });

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => {
        const currentTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('mapTheme', newTheme);
        applyTheme(newTheme);
        if (showToast) {
          showToast('success', 'Motyw zmieniony', `Przełączono na tryb ${newTheme === 'dark' ? 'ciemny' : 'jasny'}`);
        }
      });
    }
  }

  function initFullscreen() {
    const btn = document.getElementById('fullscreen-toggle');
    btn?.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
        btn.querySelector('i').className = 'fas fa-compress';
      } else {
        document.exitFullscreen();
        btn.querySelector('i').className = 'fas fa-expand';
      }
    });
  }

  window.StatsUI = Object.freeze({
    initThemeSync: initThemeSync,
    applyTheme: applyTheme,
    initFullscreen: initFullscreen,
  });
})();
