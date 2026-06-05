/**
 * Statystyki genealogiczne centrum analitycznego (P2.8 Etap 16).
 *
 * Dostęp przez `window.StatsGenealogy`.
 */
(function () {
  'use strict';

  let callbacks = {
    charts: {},
    getStatsData: () => null,
  };

  function init(options) {
    callbacks = options;
  }

  function render(data) {
    const stats = data.genealogy_stats;
    if (!stats) return;

    const totalPeopleEl = document.getElementById('stat-total-people');
    const genderRatioEl = document.getElementById('stat-gender-ratio');
    if (totalPeopleEl) totalPeopleEl.textContent = stats.total_people;
    if (genderRatioEl) genderRatioEl.textContent = `${stats.male_count} / ${stats.female_count}`;

    _renderTopSurnames(stats.top_surnames || []);
    _renderMainSeriesChart(stats);
    _initSeriesToggle(stats);
    _renderExtendedCharts(stats);
  }

  function updateSeries(series) {
    const statsData = callbacks.getStatsData();
    if (!callbacks.charts.genealogyBirths || !statsData?.genealogy_stats) return;

    const stats = statsData.genealogy_stats;
    const map = {
      'births': { key: 'births_by_decade', label: 'Liczba urodzeń', color: '#764ba2' },
      'deaths': { key: 'deaths_by_decade', label: 'Liczba zgonów', color: '#ef4444' },
      'marriages': { key: 'marriages_by_decade', label: 'Liczba ślubów', color: '#10b981' }
    };

    const config = map[series] || map.births;
    const dataSet = stats[config.key] || { labels: [], data: [] };
    const chart = callbacks.charts.genealogyBirths;
    chart.data.labels = dataSet.labels.map(label => label.replace(/(\d{4})s/, 'Lata $1'));
    chart.data.datasets[0].data = dataSet.data;
    chart.data.datasets[0].label = config.label;
    chart.data.datasets[0].borderColor = config.color;
    chart.data.datasets[0].backgroundColor = _seriesGradient(chart.ctx, series);
    chart.update();
  }

  function _renderTopSurnames(surnames) {
    const container = document.getElementById('top-surnames-list');
    if (!container) return;

    container.innerHTML = surnames.map((surname, index) => {
      const pos = index + 1;
      const cls = pos === 1 ? 'gold' : pos === 2 ? 'silver' : pos === 3 ? 'bronze' : '';
      return `
        <div class="ranking-item">
          <div class="ranking-position ${cls}">${pos}</div>
          <div class="ranking-info"><div class="ranking-name">${surname.name}</div></div>
          <div class="surname-count">${surname.count}</div>
        </div>`;
    }).join('');
  }

  function _renderMainSeriesChart(stats) {
    const chartCtx = document.getElementById('genealogy-births-chart')?.getContext('2d');
    if (!chartCtx) return;

    if (callbacks.charts.genealogyBirths) callbacks.charts.genealogyBirths.destroy();
    callbacks.charts.genealogyBirths = new Chart(chartCtx, {
      type: 'bar',
      data: {
        labels: (stats.births_by_decade?.labels || []).map(label => label.replace(/(\d{4})s/, 'Lata $1')),
        datasets: [{
          label: 'Liczba urodzeń',
          data: stats.births_by_decade?.data || [],
          backgroundColor: _seriesGradient(chartCtx, 'births'),
          borderColor: '#764ba2',
          borderWidth: 2,
          borderRadius: 5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Liczba osób / zdarzeń' } },
          x: { title: { display: true, text: 'Dekada' } }
        }
      }
    });
  }

  function _initSeriesToggle(stats) {
    const toggle = document.getElementById('genealogy-series-toggle');
    if (!toggle) return;

    console.log('🔍 Dane genealogiczne:', {
      births: stats.births_by_decade,
      deaths: stats.deaths_by_decade,
      marriages: stats.marriages_by_decade
    });

    toggle.addEventListener('change', event => {
      const target = event.target;
      if (target?.name === 'gen-series') {
        console.log('🔄 Przełączanie na:', target.value);
        updateSeries(target.value);
      }
    });
  }

  function _renderExtendedCharts(stats) {
    if (stats.infant_mortality && Object.keys(stats.infant_mortality).length > 0) {
      _renderInfantMortalityChart(stats.infant_mortality);
    }
    if (stats.lifespan_by_generation && Object.keys(stats.lifespan_by_generation).length > 0) {
      _renderLifespanChart(stats.lifespan_by_generation);
    }
    if (stats.death_age_distribution && Object.keys(stats.death_age_distribution).length > 0) {
      _renderDeathAgeChart(stats.death_age_distribution);
    }
    if (stats.family_structure && Object.keys(stats.family_structure).length > 0) {
      _renderFamilyStructureChart(stats.family_structure);
    }
  }

  function _seriesGradient(ctx, series) {
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    if (series === 'deaths') {
      gradient.addColorStop(0, 'rgba(239,68,68,0.6)');
      gradient.addColorStop(1, 'rgba(239,68,68,0.1)');
    } else if (series === 'marriages') {
      gradient.addColorStop(0, 'rgba(16,185,129,0.6)');
      gradient.addColorStop(1, 'rgba(16,185,129,0.1)');
    } else {
      gradient.addColorStop(0, 'rgba(118,75,162,0.6)');
      gradient.addColorStop(1, 'rgba(102,126,234,0.1)');
    }
    return gradient;
  }

  function _renderInfantMortalityChart(data) {
    document.getElementById('stat-infant-deaths').textContent = data.infant_deaths || 0;
    document.getElementById('stat-infant-mortality-rate').textContent = `${data.mortality_rate || 0}%`;

    const ctx = document.getElementById('infant-mortality-chart')?.getContext('2d');
    if (!ctx) return;
    if (callbacks.charts.infantMortality) callbacks.charts.infantMortality.destroy();

    callbacks.charts.infantMortality = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.by_decade?.labels || [],
        datasets: [{ label: 'Zgony niemowląt', data: data.by_decade?.data || [], backgroundColor: _redGradient(ctx), borderColor: '#ef4444', borderWidth: 2, borderRadius: 5 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => `Zgony niemowląt: ${context.parsed.y}` } } }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Liczba zgonów' } }, x: { title: { display: true, text: 'Dekada' } } } }
    });
  }

  function _renderLifespanChart(data) {
    document.getElementById('stat-avg-lifespan').textContent = `${data.avg_lifespan || 0} lat`;
    document.getElementById('stat-lifespan-records').textContent = data.total_records || 0;

    const ctx = document.getElementById('lifespan-chart')?.getContext('2d');
    if (!ctx) return;
    if (callbacks.charts.lifespan) callbacks.charts.lifespan.destroy();

    callbacks.charts.lifespan = new Chart(ctx, {
      type: 'line',
      data: { labels: data.labels || [], datasets: [{ label: 'Średni wiek śmierci (lata)', data: data.data || [], borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.1)', borderWidth: 3, tension: 0.4, fill: true, pointRadius: 6, pointHoverRadius: 8, pointBackgroundColor: '#10b981', pointBorderColor: '#fff', pointBorderWidth: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true, position: 'top' }, tooltip: { callbacks: { label: context => `Średni wiek: ${context.parsed.y} lat` } } }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Wiek (lata)' }, suggestedMax: 80 }, x: { title: { display: true, text: 'Dekada urodzenia' } } } }
    });
  }

  function _renderDeathAgeChart(data) {
    document.getElementById('stat-total-deaths').textContent = data.total_deaths || 0;

    const ctx = document.getElementById('death-age-chart')?.getContext('2d');
    if (!ctx) return;
    if (callbacks.charts.deathAge) callbacks.charts.deathAge.destroy();

    const colors = ['#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16', '#22c55e', '#10b981', '#14b8a6', '#06b6d4', '#0ea5e9', '#3b82f6'];
    callbacks.charts.deathAge = new Chart(ctx, {
      type: 'bar',
      data: { labels: data.labels || [], datasets: [{ label: 'Liczba zgonów', data: data.data || [], backgroundColor: colors, borderColor: colors.map(color => color), borderWidth: 1, borderRadius: 5 }] },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => { const total = context.dataset.data.reduce((a, b) => a + b, 0); const percent = ((context.parsed.x / total) * 100).toFixed(1); return `Zgony: ${context.parsed.x} (${percent}%)`; } } } }, scales: { x: { beginAtZero: true, title: { display: true, text: 'Liczba zgonów' } }, y: { title: { display: true, text: 'Przedział wiekowy' } } } }
    });
  }

  function _renderFamilyStructureChart(data) {
    document.getElementById('stat-avg-children').textContent = data.avg_children_per_parent || 0;
    document.getElementById('stat-avg-household').textContent = data.avg_household_size || 0;
    document.getElementById('stat-total-families').textContent = data.total_families || 0;

    const ctx = document.getElementById('family-structure-chart')?.getContext('2d');
    if (!ctx) return;
    if (callbacks.charts.familyStructure) callbacks.charts.familyStructure.destroy();

    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(139,92,246,0.6)');
    gradient.addColorStop(1, 'rgba(139,92,246,0.1)');
    callbacks.charts.familyStructure = new Chart(ctx, {
      type: 'bar',
      data: { labels: data.family_size_distribution?.labels || [], datasets: [{ label: 'Liczba rodzin', data: data.family_size_distribution?.data || [], backgroundColor: gradient, borderColor: '#8b5cf6', borderWidth: 2, borderRadius: 5 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => `Rodzin: ${context.parsed.y}` } } }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Liczba rodzin' } }, x: { title: { display: true, text: 'Wielkość rodziny' } } } }
    });
  }

  function _redGradient(ctx) {
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(239,68,68,0.6)');
    gradient.addColorStop(1, 'rgba(239,68,68,0.1)');
    return gradient;
  }

  window.StatsGenealogy = Object.freeze({
    init: init,
    render: render,
    updateSeries: updateSeries,
  });
})();
