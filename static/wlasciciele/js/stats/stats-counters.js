/**
 * Animowane liczniki centrum analitycznego (P2.8 Etap 7).
 *
 * Kolejność ładowania:
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/stats-ui.js
 *   4. js/stats-actions.js
 *   5. js/stats-data.js
 *   6. js/stats-help.js
 *   7. js/stats-search.js
 *   8. js/stats-counters.js  ← ten plik
 *   9. stats-script.js
 *
 * Dostęp przez `window.StatsCounters`.
 */
(function () {
  'use strict';

  function init() {
    const counters = document.querySelectorAll('.counter');
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const counter = entry.target;
          const target = parseInt(counter.dataset.target, 10) || 0;
          animate(counter, target);
          observer.unobserve(counter);
        }
      });
    }, { threshold: 0.5 });

    counters.forEach(counter => observer.observe(counter));
  }

  function animate(element, target) {
    let current = 0;
    const increment = target / 50;
    const timer = setInterval(() => {
      current += increment;
      if (current >= target) {
        element.textContent = target.toLocaleString('pl-PL');
        clearInterval(timer);
      } else {
        element.textContent = Math.floor(current).toLocaleString('pl-PL');
      }
    }, 30);
  }

  function update(stats) {
    const ownersCounter = document.querySelector('#total-owners .counter');
    const plotsCounter = document.querySelector('#total-plots .counter');

    if (ownersCounter) {
      ownersCounter.dataset.target = stats.total_owners;
      animate(ownersCounter, stats.total_owners);
    }
    if (plotsCounter) {
      plotsCounter.dataset.target = stats.total_plots;
      animate(plotsCounter, stats.total_plots);
    }
  }

  window.StatsCounters = Object.freeze({
    init: init,
    animate: animate,
    update: update,
  });
})();
