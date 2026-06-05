/**
 * Demografia centrum analitycznego (P2.8 Etap 15).
 *
 * Dostęp przez `window.StatsDemographics`.
 */
(function () {
  'use strict';

  let callbacks = {
    charts: {},
    showToast: () => undefined,
    getStatsData: () => null,
  };

  function init(options) {
    callbacks = options;
    window.performComparison = performComparison;
    window.closeComparisonModal = closeComparison;
  }

  function render(demografiaData, source) {
    if (!demografiaData || demografiaData.length === 0) {
      document.getElementById('demographics').innerHTML = `
        <div class="no-data-message">
          <i class="fas fa-inbox fa-3x"></i>
          <h3>Brak danych demograficznych</h3>
          <p>Dane demograficzne nie są jeszcze dostępne dla tego okresu.</p>
        </div>`;
      return;
    }

    const data = demografiaData
      .map(d => ({
        ...d,
        rok: Number(d.rok) || 0,
        populacja_ogolem: Number(d.populacja_ogolem) || ((Number(d.katolicy) || 0) + (Number(d.zydzi) || 0) + (Number(d.inni) || 0)),
        katolicy: Number(d.katolicy) || 0,
        zydzi: Number(d.zydzi) || 0,
        inni: Number(d.inni) || 0,
      }))
      .filter(d => d.rok > 0 && d.populacja_ogolem > 0)
      .sort((a, b) => a.rok - b.rok);

    if (data.length === 0) {
      document.getElementById('demo-growth').textContent = '0%';
      document.getElementById('demo-years').textContent = '0 lat';
      return;
    }

    _updateQuickStats(data);
    _createChart(data);
    if (source !== 'metrical') {
      _createTimeline(data);
    } else {
      document.getElementById('demo-timeline-track').innerHTML = '';
    }
    _createCards(data, source);
    _createComparisonAnalysis(data);
  }

  function initSourceToggle(metricalData, officialData) {
    document.querySelectorAll('input[name="demo-source"]').forEach(radio => {
      radio.addEventListener('change', event => {
        const source = event.target.value;
        if (source === 'metrical') {
          render(metricalData, 'metrical');
          _updateHeader('metrical');
          callbacks.showToast('info', 'Zmieniono źródło', 'Wykresy oparte na księgach metrykalnych');
        } else {
          render(officialData, 'official');
          _updateHeader('official');
          callbacks.showToast('info', 'Zmieniono źródło', 'Wykresy oparte na danych oficjalnych');
        }
      });
    });
  }

  function openComparison() {
    const statsData = callbacks.getStatsData();
    if (!statsData?.demografia || statsData.demografia.length < 2) {
      callbacks.showToast('error', 'Brak danych', 'Potrzeba co najmniej 2 lata danych demograficznych do porównania');
      return;
    }
    _createComparisonModal();
  }

  function performComparison() {
    const statsData = callbacks.getStatsData();
    const source1 = document.getElementById('source1').value;
    const year1 = parseInt(document.getElementById('period1').value);
    const source2 = document.getElementById('source2').value;
    const year2 = parseInt(document.getElementById('period2').value);

    if (!year1 || !year2) {
      callbacks.showToast('error', 'Błąd', 'Wybierz oba okresy do porównania');
      return;
    }
    if (year1 === year2 && source1 === source2) {
      callbacks.showToast('error', 'Błąd', 'Wybierz różne okresy lub źródła do porównania');
      return;
    }

    const dataSet1 = source1 === 'metrical' ? statsData.demografia : statsData.demografia_official;
    const dataSet2 = source2 === 'metrical' ? statsData.demografia : statsData.demografia_official;
    const data1 = dataSet1.find(d => d.rok === year1);
    const data2 = dataSet2.find(d => d.rok === year2);

    if (!data1 || !data2) {
      callbacks.showToast('error', 'Błąd', 'Nie znaleziono danych dla wybranych okresów');
      return;
    }

    data1._label = `${year1} (${source1 === 'metrical' ? 'Metrykalne' : 'Oficjalne'})`;
    data2._label = `${year2} (${source2 === 'metrical' ? 'Metrykalne' : 'Oficjalne'})`;
    _displayComparisonResults(data1, data2);
  }

  function closeComparison() {
    document.getElementById('comparison-modal')?.remove();
    if (callbacks.charts.comparison) {
      callbacks.charts.comparison.destroy();
      delete callbacks.charts.comparison;
    }
  }

  function _updateQuickStats(data) {
    const firstYear = data[0];
    const lastYear = data[data.length - 1];
    const growthRaw = firstYear.populacja_ogolem > 0
      ? ((lastYear.populacja_ogolem - firstYear.populacja_ogolem) / firstYear.populacja_ogolem * 100)
      : 0;
    const growthPercent = Number.isFinite(growthRaw) ? growthRaw.toFixed(1) : '0.0';
    document.getElementById('demo-growth').textContent = growthPercent > 0 ? `+${growthPercent}%` : `${growthPercent}%`;
    document.getElementById('demo-years').textContent = `${lastYear.rok - firstYear.rok} lat`;
  }

  function _createChart(data) {
    const ctx = document.getElementById('demographicsChart')?.getContext('2d');
    if (!ctx) return;

    const years = data.map(d => d.rok);
    const total = data.map(d => d.populacja_ogolem || 0);
    const catholics = data.map(d => d.katolicy || 0);
    const jewish = data.map(d => d.zydzi || 0);
    const others = data.map(d => d.inni || 0);

    if (callbacks.charts.demographics) callbacks.charts.demographics.destroy();
    callbacks.charts.demographics = new Chart(ctx, {
      type: 'line',
      data: {
        labels: years,
        datasets: [
          { label: 'Populacja ogółem', data: total, borderColor: '#667eea', backgroundColor: 'rgba(102,126,234,0.1)', borderWidth: 3, tension: 0.4, fill: true, pointRadius: 6, pointHoverRadius: 8, pointBackgroundColor: '#667eea', pointBorderColor: '#fff', pointBorderWidth: 2 },
          { label: 'Katolicy', data: catholics, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.1)', borderWidth: 2, tension: 0.4, fill: false, hidden: catholics.every(v => v === 0), pointRadius: 5, pointHoverRadius: 7 },
          { label: 'Żydzi', data: jewish, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)', borderWidth: 2, tension: 0.4, fill: false, hidden: jewish.every(v => v === 0), pointRadius: 5, pointHoverRadius: 7 },
          { label: 'Inni', data: others, borderColor: '#8b5cf6', backgroundColor: 'rgba(139,92,246,0.1)', borderWidth: 2, tension: 0.4, fill: false, hidden: others.every(v => v === 0), pointRadius: 5, pointHoverRadius: 7 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        onClick: (event, elements) => {
          if (elements && elements.length > 0) _scrollToYear(years[elements[0].index]);
        },
        plugins: {
          legend: { position: 'top', labels: { usePointStyle: true, padding: 15 } },
          tooltip: {
            backgroundColor: 'rgba(0,0,0,0.8)', padding: 12, cornerRadius: 8,
            callbacks: {
              title: ctxItems => `Rok ${ctxItems[0].label}`,
              label: ctxItem => {
                const value = ctxItem.parsed.y;
                const totalValue = total[ctxItem.dataIndex] || 0;
                const pct = totalValue > 0 ? ((value / totalValue) * 100).toFixed(1) : 0;
                return `${ctxItem.dataset.label}: ${value} osób${pct > 0 ? ` (${pct}%)` : ''}`;
              }
            }
          }
        },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Liczba mieszkańców' }, grid: { drawBorder: false } },
          x: { title: { display: true, text: 'Rok' }, grid: { display: false } }
        }
      }
    });
  }

  function _createTimeline(data) {
    const container = document.getElementById('demo-timeline-track');
    if (!container) return;

    const events = data
      .filter(entry => entry.opis && entry.opis.trim() !== '')
      .map(entry => ({ year: entry.rok, text: entry.opis, icon: _getIconForEvent(entry.opis), major: true }));

    if (events.length === 0) {
      container.innerHTML = '<p style="text-align:center; color: var(--text-secondary);">Brak zdefiniowanych kluczowych wydarzeń w danych.</p>';
      return;
    }
    if (events.length === 1) {
      const event = events[0];
      container.innerHTML = `<div class="timeline-event ${event.major ? 'major' : ''}" style="left: 50%;"><span>${event.icon}</span><span>${event.year}</span><div class="timeline-event-tooltip">${event.text}</div></div>`;
      return;
    }

    const minYear = Math.min(...events.map(event => event.year));
    const maxYear = Math.max(...events.map(event => event.year));
    const span = Math.max(1, maxYear - minYear);
    container.innerHTML = events.map(event => {
      const left = 8 + (((event.year - minYear) / span) * 84);
      return `<div class="timeline-event ${event.major ? 'major' : ''}" style="left: ${left}%"><span>${event.icon}</span><span>${event.year}</span><div class="timeline-event-tooltip">${event.text}</div></div>`;
    }).join('');
  }

  function _getIconForEvent(text) {
    const normalized = text.toLowerCase();
    if (normalized.includes('kolei')) return '🚂';
    if (normalized.includes('budow')) return '🏗️';
    if (normalized.includes('wojn')) return '⚔️';
    if (normalized.includes('epidemi') || normalized.includes('chorob')) return '🏥';
    return '📅';
  }

  function _createCards(data, source) {
    const container = document.getElementById('demo-cards');
    if (!container) return;

    const dataMap = new Map(data.map(entry => [entry.rok, entry]));
    const decades = {};
    data.forEach(entry => {
      const decadeStart = Math.floor(entry.rok / 10) * 10;
      if (!decades[decadeStart]) decades[decadeStart] = [];
      decades[decadeStart].push(entry);
    });

    container.innerHTML = Object.keys(decades).map(Number).sort((a, b) => a - b).map(decadeStart => {
      const decadeData = decades[decadeStart].sort((a, b) => a.rok - b.rok);
      const cardsHtml = decadeData.map(entry => _renderYearCard(entry, dataMap, source)).join('');
      return `
        <details class="decade-group">
          <summary class="decade-summary">
             <div class="decade-label">Lata ${decadeStart}-${decadeStart + 9}</div>
             <div class="decade-count">${decadeData.length} ${decadeData.length === 1 ? 'rok' : (decadeData.length >= 2 && decadeData.length <= 4 ? 'lata' : 'lat')}</div>
          </summary>
          <div class="decade-content">${cardsHtml}</div>
        </details>`;
    }).join('');
  }

  function _renderYearCard(entry, dataMap, source) {
    const prevYearData = dataMap.get(entry.rok - 1);
    let changePercent = 0;
    if (prevYearData && prevYearData.populacja_ogolem > 0) {
      changePercent = ((entry.populacja_ogolem - prevYearData.populacja_ogolem) / prevYearData.populacja_ogolem * 100).toFixed(1);
    }

    const changeClass = changePercent > 0 ? 'text-green-500' : (changePercent < 0 ? 'text-red-500' : 'text-gray-400');
    const changeIcon = changePercent > 0 ? '↗' : (changePercent < 0 ? '↘' : '—');
    const changeDisplay = prevYearData ? `${changeIcon} ${Math.abs(changePercent)}% vs ${entry.rok - 1}` : `${changeIcon} —`;
    const total = entry.populacja_ogolem || 0;
    const religionsHtml = _renderReligions(entry, total, source);
    const eventHtml = source !== 'metrical' && entry.opis ? `<div class="demo-event-badge" title="${entry.opis}"><span>${_getIconForEvent(entry.opis)}</span> ${entry.opis}</div>` : '';

    return `
      <div class="demo-year-card" id="card-${entry.rok}">
        <div class="demo-card-header">
           <div class="demo-year">${entry.rok}</div>
           <div class="demo-total-population"><i class="fas fa-users"></i> <span>${total} mieszkańców</span></div>
        </div>
        <div class="demo-card-body">
           ${religionsHtml}
           ${eventHtml}
           <div class="demo-change-badge ${changeClass}">${changeDisplay}</div>
        </div>
      </div>`;
  }

  function _renderReligions(entry, total, source) {
    if (!entry.katolicy && !entry.zydzi && !entry.inni) {
      return source === 'metrical' ? '' : '<div class="demo-no-religions"><i class="fas fa-inbox"></i> Brak szczegółu wyznaniowego</div>';
    }
    const catholicPercent = total > 0 && entry.katolicy ? (entry.katolicy / total * 100).toFixed(1) : 0;
    const jewishPercent = total > 0 && entry.zydzi ? (entry.zydzi / total * 100).toFixed(1) : 0;
    const otherPercent = total > 0 && entry.inni ? (entry.inni / total * 100).toFixed(1) : 0;
    const catholic = entry.katolicy ? `<div class="religion-item"><div class="religion-header"><span class="religion-name"><span class="religion-icon catholic">✝</span>Katolicy</span><span class="religion-value">${entry.katolicy}</span></div><div class="religion-bar"><div class="religion-fill catholic" style="width:${catholicPercent}%"></div></div></div>` : '';
    const jewish = entry.zydzi ? `<div class="religion-item"><div class="religion-header"><span class="religion-name"><span class="religion-icon jewish">✡</span>Żydzi</span><span class="religion-value">${entry.zydzi}</span></div><div class="religion-bar"><div class="religion-fill jewish" style="width:${jewishPercent}%"></div></div></div>` : '';
    const other = entry.inni ? `<div class="religion-item"><div class="religion-header"><span class="religion-name"><span class="religion-icon other">?</span>Inni</span><span class="religion-value">${entry.inni}</span></div><div class="religion-bar"><div class="religion-fill other" style="width:${otherPercent}%"></div></div></div>` : '';
    return `<div class="demo-religions">${catholic}${jewish}${other}</div>`;
  }

  function _createComparisonAnalysis(data) {
    const container = document.getElementById('demographics');
    if (!container || data.length < 2) return;
    const valid = data.filter(entry => Number(entry.populacja_ogolem) > 0 && Number(entry.rok) > 0);
    if (valid.length < 2) return;

    const first = valid[0];
    const last = valid[valid.length - 1];
    const totalGrowth = (last.populacja_ogolem || 0) - (first.populacja_ogolem || 0);
    const years = Math.max(1, last.rok - first.rok);
    const avgPerYear = (totalGrowth / years).toFixed(1);
    const populations = valid.map(entry => Number(entry.populacja_ogolem) || 0).filter(value => value > 0);
    const maxPopulation = populations.length ? Math.max(...populations) : 0;
    const minPopulation = populations.length ? Math.min(...populations) : 0;

    const html = `<div class="comparison-cards"><div class="comparison-card"><div class="comparison-icon"><i class="fas fa-chart-line"></i></div><div class="comparison-value">${totalGrowth > 0 ? '+' : ''}${totalGrowth}</div><div class="comparison-label">Wzrost całkowity</div></div><div class="comparison-card"><div class="comparison-icon"><i class="fas fa-calendar-alt"></i></div><div class="comparison-value">${avgPerYear}</div><div class="comparison-label">Średni wzrost/rok</div></div><div class="comparison-card"><div class="comparison-icon"><i class="fas fa-arrow-up"></i></div><div class="comparison-value">${maxPopulation}</div><div class="comparison-label">Maksymalna populacja</div></div><div class="comparison-card"><div class="comparison-icon"><i class="fas fa-arrow-down"></i></div><div class="comparison-value">${minPopulation}</div><div class="comparison-label">Minimalna populacja</div></div></div>`;
    container.querySelector('.comparison-cards')?.replaceWith(document.createRange().createContextualFragment(html));
  }

  function _createComparisonModal() {
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.id = 'comparison-modal';
    modal.innerHTML = `
      <div class="modal-content" style="max-width: 950px; border: 1px solid rgba(255,255,255,0.15);">
        <div class="modal-header" style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 20px;"><h2><i class="fas fa-balance-scale-left"></i> Porównaj okresy demograficzne</h2><button class="modal-close" onclick="closeComparisonModal()">&times;</button></div>
        <div class="modal-body" style="padding-top: 25px;">
          <div class="comparison-setup"><div class="comparison-grid">${_periodSetupHtml(1, false)}<div class="comparison-vs">VS</div>${_periodSetupHtml(2, true)}</div><div class="comparison-action"><button class="btn-primary btn-large" onclick="performComparison()" id="compare-execute"><i class="fas fa-sync-alt"></i> Analizuj i porównaj</button></div></div>
          <div id="comparison-results" style="display: none; margin-top: 3rem; border-top: 2px dashed rgba(255,255,255,0.1); padding-top: 2rem;"><div class="comparison-charts" style="background: rgba(0,0,0,0.2); padding: 20px; border-radius: 12px;"><canvas id="comparison-chart" style="max-height: 400px;"></canvas></div><div class="comparison-summary" id="comparison-summary"></div></div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    _updateYearOptions('source1', 'period1');
    _updateYearOptions('source2', 'period2');
    document.getElementById('source1').addEventListener('change', () => _updateYearOptions('source1', 'period1'));
    document.getElementById('source2').addEventListener('change', () => _updateYearOptions('source2', 'period2'));
  }

  function _periodSetupHtml(index, officialSelected) {
    return `<div class="period-setup-card"><div class="setup-title"><i class="fas fa-layer-group"></i> ${index === 1 ? 'Pierwszy' : 'Drugi'} okres</div><div class="setup-controls"><div class="control-item"><label><i class="fas fa-server"></i> Baza danych</label><select id="source${index}" class="period-select"><option value="metrical">📜 Metrykalne</option><option value="official" ${officialSelected ? 'selected' : ''}>🏛️ Oficjalne</option></select></div><div class="control-item"><label><i class="fas fa-clock"></i> Rok spisu</label><select id="period${index}" class="period-select"><option value="">Wybierz...</option></select></div></div></div>`;
  }

  function _updateYearOptions(sourceId, selectId) {
    const statsData = callbacks.getStatsData();
    const source = document.getElementById(sourceId).value;
    const select = document.getElementById(selectId);
    const data = source === 'metrical' ? statsData.demografia : statsData.demografia_official;
    const years = (data || []).map(entry => entry.rok).sort((a, b) => b - a);
    select.innerHTML = '<option value="">Wybierz rok...</option>' + years.map(year => `<option value="${year}">${year}</option>`).join('');
  }

  function _displayComparisonResults(data1, data2) {
    const resultsDiv = document.getElementById('comparison-results');
    resultsDiv.style.display = 'block';
    _createComparisonChart(data1, data2);
    document.getElementById('comparison-summary').innerHTML = _generateComparisonSummary(data1, data2);
    callbacks.showToast('success', 'Porównanie', `Wygenerowano porównanie okresów`);
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function _createComparisonChart(data1, data2) {
    const ctx = document.getElementById('comparison-chart').getContext('2d');
    if (callbacks.charts.comparison) callbacks.charts.comparison.destroy();
    callbacks.charts.comparison = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Populacja ogółem', 'Katolicy', 'Żydzi', 'Inni'],
        datasets: [
          { label: data1._label, data: [data1.populacja_ogolem || 0, data1.katolicy || 0, data1.zydzi || 0, data1.inni || 0], backgroundColor: 'rgba(102, 126, 234, 0.8)', borderColor: '#667eea', borderWidth: 1 },
          { label: data2._label, data: [data2.populacja_ogolem || 0, data2.katolicy || 0, data2.zydzi || 0, data2.inni || 0], backgroundColor: 'rgba(139, 92, 246, 0.8)', borderColor: '#8b5cf6', borderWidth: 1 }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: `Porównanie: ${data1._label} vs ${data2._label}` }, legend: { position: 'top' } }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Liczba osób' } } } }
    });
  }

  function _generateComparisonSummary(data1, data2) {
    const pop1 = data1.populacja_ogolem || 0;
    const pop2 = data2.populacja_ogolem || 0;
    const change = pop2 - pop1;
    const changePercent = pop1 > 0 ? ((change / pop1) * 100).toFixed(1) : 0;
    return `<div class="summary-grid"><div class="summary-card"><div class="summary-label">${data1._label}</div><div class="summary-value">${pop1}</div><div class="summary-sub">Populacja ogółem</div></div><div class="summary-card"><div class="summary-label">${data2._label}</div><div class="summary-value">${pop2}</div><div class="summary-sub">Populacja ogółem</div></div><div class="summary-card highlight ${change >= 0 ? 'positive' : 'negative'}"><div class="summary-label">Zmiana netto</div><div class="summary-value">${change >= 0 ? '+' : ''}${change}</div><div class="summary-sub">${changePercent}%</div></div></div>`;
  }

  function _updateHeader(source) {
    const titleEl = document.querySelector('.demo-summary h3');
    const subtitleEl = document.querySelector('.demo-summary .demo-subtitle');
    if (source === 'metrical') {
      titleEl.innerHTML = '<i class="fas fa-chart-line"></i> Dynamika populacji (wg ksiąg metrykalnych)';
      subtitleEl.textContent = 'Szacunek na podstawie rejestrów urodzeń i zgonów w bazie';
    } else {
      titleEl.innerHTML = '<i class="fas fa-book"></i> Dynamika populacji (Dane Oficjalne)';
      subtitleEl.textContent = 'Dane historyczne z tabel i spisów powszechnych';
    }
  }

  function _scrollToYear(year) {
    const card = document.getElementById(`card-${year}`);
    if (!card) return;
    const details = card.closest('details');
    if (details && !details.open) details.open = true;
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    document.querySelectorAll('.demo-year-card.highlight').forEach(element => element.classList.remove('highlight'));
    card.classList.add('highlight');
    setTimeout(() => card.classList.remove('highlight'), 2000);
  }

  window.StatsDemographics = Object.freeze({
    init: init,
    render: render,
    initSourceToggle: initSourceToggle,
    openComparison: openComparison,
    performComparison: performComparison,
    closeComparison: closeComparison,
  });
})();
