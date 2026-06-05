/**
 * Podstawowe wykresy centrum analitycznego (P2.8 Etap 19).
 *
 * Dostęp przez `window.StatsCoreCharts`.
 */
(function () {
  'use strict';

  let charts = {};

  function init(callbacks) {
    callbacks = callbacks || {};
    charts = callbacks.charts || {};
    Chart.defaults.font.family = "'Inter', sans-serif";
  }

  /**
   * Tworzy wykresy: kołowy struktur kategorii oraz poziomy słupkowy Top 10.
   * @param {*} data
   */
  function createCharts(data) {
    // Doughnut – struktura kategorii
    const pieCtx = document.getElementById('pieChart')?.getContext('2d');
    if (pieCtx && data.category_counts) {
      const c = data.category_counts;
      const inne = (c.droga || 0) + (c.rzeka || 0) + (c.obiekt_specjalny || 0);

      charts.pie = new Chart(pieCtx, {
        type: 'doughnut',
        data: {
          labels: ['Rolne', 'Budowlane', 'Lasy', 'Pastwiska', 'Inne'],
          datasets: [{
            data: [c.rolna || 0, c.budowlana || 0, c.las || 0, c.pastwisko || 0, inne],
            backgroundColor: ['#10b981', '#f59e0b', '#3b82f6', '#8b5cf6', '#ef4444']
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } }
        }
      });
    }

    // Bar – Top 10 właścicieli (rzeczywiste)
    const barCtx = document.getElementById('barChart')?.getContext('2d');
    if (barCtx && data?.rankings_real?.all_plots) {
      const top10 = data.rankings_real.all_plots.slice(0, 10).reverse();

      charts.bar = new Chart(barCtx, {
        type: 'bar',
        data: {
          labels: top10.map(o => o.nazwa_wlasciciela),
          datasets: [{
            label: 'Liczba działek',
            data: top10.map(o => o.plot_count),
            backgroundColor: 'rgba(102,126,234,0.8)',
            borderColor: '#667eea',
            borderWidth: 1,
            borderRadius: 5
          }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { title: (items) => items[0].label } }
          },
          scales: {
            x: { beginAtZero: true, title: { display: true, text: 'Liczba działek' } },
            y: {
              ticks: {
                autoSkip: false,
                callback: function (value) {
                  const label = this.getLabelForValue(value);
                  return (label.length > 25) ? label.substring(0, 22) + '…' : label;
                }
              }
            }
          }
        }
      });
    }
  }

  window.StatsCoreCharts = Object.freeze({
    init: init,
    createCharts: createCharts,
  });
})();
