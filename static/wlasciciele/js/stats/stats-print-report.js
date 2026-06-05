/** Drukowanie i szablon raportu centrum analitycznego. */
(function () {
  'use strict';

  let getStatsData = () => null;
  let showToast = () => {};

  function init(callbacks) {
    callbacks = callbacks || {};
    getStatsData = callbacks.getStatsData || getStatsData;
    showToast = callbacks.showToast || showToast;
    window.closePrintModal = closePrintModal;
    window.generatePrintReport = generatePrintReport;
  }

  function printReport() {
    const modal = document.getElementById('print-modal');
    if (modal) modal.classList.add('active');
  }

  function closePrintModal() {
    const modal = document.getElementById('print-modal');
    if (modal) modal.classList.remove('active');
  }

  function getSelectedSections() {
    return {
      general: document.getElementById('print-general')?.checked,
      rankings: document.getElementById('print-rankings')?.checked,
      categories: document.getElementById('print-categories')?.checked,
      demographics: document.getElementById('print-demographics')?.checked,
      genealogy: document.getElementById('print-genealogy')?.checked,
      insights: document.getElementById('print-insights')?.checked,
      rankingsCount: document.getElementById('print-rankings-count')?.checked,
      parcels: document.getElementById('print-parcels')?.checked,
      rivers: document.getElementById('print-rivers')?.checked,
      roads: document.getElementById('print-roads')?.checked,
      jewishStats: document.getElementById('print-jewish-stats')?.checked,
      digitalization: document.getElementById('print-digitalization')?.checked,
    };
  }

  function generatePrintReport() {
    const sections = getSelectedSections();
    if (!Object.values(sections).some(v => v)) {
      showToast('warning', 'Wybierz sekcje', 'Zaznacz przynajmniej jedną sekcję do wydruku');
      return;
    }

    closePrintModal();
    const reportHTML = generateReportHTML(sections);
    const printWindow = window.open('', '_blank', 'width=1024,height=768');
    printWindow.document.write(reportHTML);
    printWindow.document.close();
    printWindow.onload = function () {
      printWindow.print();
    };
    showToast('success', 'Raport wygenerowany', 'Raport został otwarty w nowym oknie');
  }

  function generateReportHTML(sections) {
    const statsData = getStatsData();
    const context = getReportContext();
    return [
      renderReportDocumentStart(context),
      sections.general ? renderGeneralSection(statsData) : '',
      sections.rankings ? renderRankingsSection(statsData) : '',
      sections.categories ? renderCategoriesSection(statsData) : '',
      sections.demographics ? renderDemographicsSection(statsData) : '',
      sections.genealogy ? renderGenealogySection(statsData) : '',
      sections.insights ? renderInsightsSection() : '',
      sections.rankingsCount ? renderRankingsCountSection(statsData) : '',
      sections.parcels ? renderParcelsSection(statsData) : '',
      sections.rivers ? renderRiversSection(statsData) : '',
      sections.roads ? renderRoadsSection(statsData) : '',
      sections.jewishStats ? renderJewishStatsSection(statsData) : '',
      sections.digitalization ? renderDigitalizationSection(statsData) : '',
      renderReportFooter(context),
    ].join('');
}

  function getReportContext() {
    return {
      locationFullName: window.LOCATION_FULL_NAME || 'Gmina Czarna',
      year: window.LOCATION_YEAR || '1882',
      generatedAt: new Date().toLocaleString('pl-PL'),
      currentYear: new Date().getFullYear(),
    };
  }

  function renderReportDocumentStart(context) {
    return `<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Raport Analityczny - ${context.locationFullName}</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #1e293b; padding: 2rem; background: #ffffff; }
    .report-header { text-align: center; margin-bottom: 3rem; padding-bottom: 2rem; border-bottom: 3px solid #667eea; }
    .report-header h1 { font-size: 2.5rem; color: #667eea; margin-bottom: 0.5rem; }
    .report-header p { font-size: 1.1rem; color: #64748b; }
    .report-section { margin-bottom: 3rem; page-break-inside: avoid; }
    .section-title { font-size: 1.8rem; color: #667eea; margin-bottom: 1.5rem; padding-bottom: 0.5rem; border-bottom: 2px solid #e2e8f0; display: flex; align-items: center; gap: 0.5rem; }
    .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
    .stat-card { background: #f8fafc; padding: 1.5rem; border-radius: 12px; border-left: 4px solid #667eea; }
    .stat-label { font-size: 0.875rem; color: #64748b; margin-bottom: 0.5rem; }
    .stat-value { font-size: 2rem; font-weight: 700; color: #1e293b; }
    .ranking-table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    .ranking-table th { background: #667eea; color: white; padding: 12px; text-align: left; font-weight: 600; }
    .ranking-table td { padding: 12px; border-bottom: 1px solid #e2e8f0; }
    .ranking-table tr:nth-child(even) { background: #f8fafc; }
    .ranking-position { font-weight: 700; color: #667eea; font-size: 1.2rem; }
    .footer { margin-top: 4rem; padding-top: 2rem; border-top: 2px solid #e2e8f0; text-align: center; color: #64748b; font-size: 0.875rem; }
    @media print { body { padding: 1rem; } .report-section { page-break-inside: avoid; } @page { margin: 1.5cm; } }
  </style>
</head>
<body>
  <div class="report-header">
    <h1><i class="fas fa-chart-line"></i> Raport Analityczny</h1>
    <p>${context.locationFullName} - Dane Katastralne ${context.year}</p>
    <p style="font-size: 0.9rem; margin-top: 0.5rem;">Wygenerowano: ${context.generatedAt}</p>
  </div>
`;
  }

  function renderGeneralSection(statsData) {
    if (!statsData?.general_stats) return '';
    const stats = statsData.general_stats;
    const areaStats = statsData.area_stats || {};
    const totalAreaHa = areaStats.total_area_ha || 0;
    const avgPlotHa = (areaStats.avg_area_ares || 0) / 100;
    return `
  <div class="report-section">
    <h2 class="section-title"><i class="fas fa-chart-pie"></i> Statystyki Ogólne</h2>
    <div class="stat-grid">
      ${renderStatCard('Liczba właścicieli', stats.total_owners || 0)}
      ${renderStatCard('Liczba działek', stats.total_plots || 0)}
      ${renderStatCard('Całkowita powierzchnia', `${totalAreaHa.toFixed(2)} ha`)}
      ${renderStatCard('Średnia wielkość działki', `${avgPlotHa.toFixed(2)} ha`)}
    </div>
  </div>
`;
  }

  function renderRankingsSection(statsData) {
    const source = statsData?.rankings_real?.all_plots;
    if (!source) return '';
    const rows = [...source]
      .sort((a, b) => ownerAreaM2(b) - ownerAreaM2(a))
      .slice(0, 10)
      .map((owner, idx) => `
        <tr>
          <td class="ranking-position">${idx + 1}</td>
          <td>${owner.nazwa_wlasciciela || 'Nieznany'}</td>
          <td>${owner.plot_count || 0}</td>
          <td>${areaHa(ownerAreaM2(owner))} ha</td>
        </tr>`).join('');
    return renderTableSection('fas fa-trophy', 'Top 10 Właścicieli (według powierzchni)', ['#', 'Właściciel', 'Liczba działek', 'Powierzchnia (ha)'], rows);
  }

  function renderCategoriesSection(statsData) {
    const categories = statsData?.category_counts;
    if (!categories) return '';
    const rows = Object.entries(categories).map(([cat, count]) => `
        <tr>
          <td style="text-transform: capitalize;">${cat}</td>
          <td>${count}</td>
        </tr>`).join('');
    return renderTableSection('fas fa-layer-group', 'Kategorie Działek', ['Kategoria', 'Liczba działek'], rows);
  }

  function renderDemographicsSection(statsData) {
    if (!statsData?.demografia?.length) return '';
    const rows = statsData.demografia.map(d => `
        <tr>
          <td>${d.rok}</td>
          <td>${d.populacja_ogolem || '-'}</td>
          <td>${d.katolicy || '-'}</td>
          <td>${d.zydzi || '-'}</td>
          <td>${d.inni || '-'}</td>
        </tr>`).join('');
    return renderTableSection('fas fa-users-cog', 'Demografia', ['Rok', 'Populacja ogółem', 'Katolicy', 'Żydzi', 'Inni'], rows);
  }

  function renderGenealogySection(statsData) {
    const gen = statsData?.genealogy_stats;
    if (!gen) return '';
    return `
  <div class="report-section">
    <h2 class="section-title"><i class="fas fa-sitemap"></i> Statystyki Genealogiczne</h2>
    <div class="stat-grid">
      ${renderStatCard('Liczba osób w bazie', gen.total_people || 0)}
      ${renderStatCard('Mężczyźni / Kobiety', `${gen.male_count || 0} / ${gen.female_count || 0}`)}
    </div>
    ${renderDecadeTable('Urodzenia wg dekad', gen.births_by_decade, 'Liczba urodzeń')}
    ${renderDecadeTable('Zgony wg dekad', gen.deaths_by_decade, 'Liczba zgonów')}
    ${renderDecadeTable('Śluby wg dekad', gen.marriages_by_decade, 'Liczba ślubów')}
  </div>
`;
  }

  function renderInsightsSection() {
    const biggestOwner = document.getElementById('biggest-owner')?.textContent || 'Brak danych';
    const ownershipTrend = document.getElementById('ownership-trend')?.textContent || 'Brak danych';
    const concentration = document.getElementById('concentration')?.textContent || 'Brak danych';
    return `
  <div class="report-section">
    <h2 class="section-title"><i class="fas fa-lightbulb"></i> Wnioski Analityczne</h2>
    <div style="background: #f8fafc; padding: 1.5rem; border-radius: 12px; border-left: 4px solid #667eea;">
      <p style="margin-bottom: 1rem;"><strong>Największy właściciel:</strong> ${biggestOwner}</p>
      <p style="margin-bottom: 1rem;"><strong>Trend własności:</strong> ${ownershipTrend}</p>
      <p><strong>Koncentracja:</strong> ${concentration}</p>
    </div>
  </div>
`;
  }

  function renderRankingsCountSection(statsData) {
    const source = statsData?.rankings_real?.all_plots;
    if (!source) return '';
    const rows = [...source]
      .sort((a, b) => (b.plot_count || 0) - (a.plot_count || 0))
      .slice(0, 10)
      .map((owner, idx) => `
        <tr>
          <td class="ranking-position">${idx + 1}</td>
          <td>${owner.nazwa_wlasciciela || 'Nieznany'}</td>
          <td>${owner.plot_count || 0}</td>
          <td>${areaHa(ownerAreaM2(owner))} ha</td>
        </tr>`).join('');
    return renderTableSection('fas fa-list-ol', 'Top 10 Właścicieli (według ilości działek)', ['#', 'Właściciel', 'Liczba działek', 'Powierzchnia (ha)'], rows);
  }

  function renderParcelsSection(statsData) {
    const source = statsData?.parcels_ranking?.all;
    if (!source) return '';
    const rows = source.slice(0, 10).map((parcel, idx) => `
        <tr>
          <td class="ranking-position">${idx + 1}</td>
          <td>${parcel.parcel_number || '-'}</td>
          <td style="text-transform: capitalize;">${parcel.kategoria || parcel.category || '-'}</td>
          <td>${areaHa(parcel.area_m2 || parcel.area || 0)} ha</td>
          <td>${parcel.nazwa_wlasciciela || parcel.owner_name || '-'}</td>
        </tr>`).join('');
    return renderTableSection('fas fa-map', 'Top 10 Największych Działek', ['#', 'Numer działki', 'Kategoria', 'Powierzchnia (ha)', 'Właściciel'], rows);
  }

  function renderRiversSection(statsData) {
    if (!statsData?.rivers_ranking) return '';
    const rows = statsData.rivers_ranking.slice(0, 10).map((river, idx) => `
        <tr>
          <td class="ranking-position">${idx + 1}</td>
          <td>${river.river_name || river.nazwa || '-'}</td>
          <td>${(river.length_m || river.dlugosc || 0).toFixed(2)} m</td>
        </tr>`).join('');
    return renderTableSection('fas fa-water', 'Top 10 Najdłuższych Rzek', ['#', 'Nazwa rzeki', 'Długość (m)'], rows);
  }

  function renderRoadsSection(statsData) {
    if (!statsData?.roads_ranking) return '';
    const rows = statsData.roads_ranking.slice(0, 10).map((road, idx) => `
        <tr>
          <td class="ranking-position">${idx + 1}</td>
          <td>${road.road_number || '-'}</td>
          <td>${(road.length_m || 0).toFixed(2)} m</td>
        </tr>`).join('');
    return renderTableSection('fas fa-road', 'Top 10 Najdłuższych Dróg', ['#', 'Numer drogi', 'Długość (m)'], rows);
  }

  function renderJewishStatsSection(statsData) {
    const jewishStats = statsData?.jewish_stats;
    if (!jewishStats || jewishStats.owners_count <= 0) return '';
    return `
  <div class="report-section">
    <h2 class="section-title"><i class="fas fa-star-of-david"></i> Statystyki Właścicieli Żydowskich</h2>
    <div class="stat-grid">
      ${renderStatCard('Liczba właścicieli', jewishStats.owners_count || 0)}
      ${renderStatCard('Liczba działek', jewishStats.parcels_count || 0)}
      ${renderStatCard('Łączna powierzchnia', `${jewishStats.total_area_ha || 0} ha`)}
    </div>
    ${renderJewishOwnersTable(jewishStats.owners)}
  </div>
`;
  }

  function renderDigitalizationSection(statsData) {
    const drawnStats = statsData?.drawn_percentage;
    const locationArea = statsData?.location_area;
    if (!drawnStats && !locationArea) return '';
    return `
  <div class="report-section">
    <h2 class="section-title"><i class="fas fa-tasks"></i> Postęp Digitalizacji</h2>
    ${renderDrawnStats(drawnStats)}
    ${renderLocationArea(locationArea)}
  </div>
`;
  }

  function renderReportFooter(context) {
    return `
  <div class="footer">
    <p>Raport wygenerowany automatycznie przez Centrum Analityczne - ${context.locationFullName}</p>
    <p>© ${context.currentYear} Projekt Czarna - Historyczna Baza Danych Katastralnych</p>
  </div>
</body>
</html>`;
  }

  function renderStatCard(label, value) {
    return `<div class="stat-card"><div class="stat-label">${label}</div><div class="stat-value">${value}</div></div>`;
  }

  function renderTableSection(iconClass, title, headers, rows) {
    return `
  <div class="report-section">
    <h2 class="section-title"><i class="${iconClass}"></i> ${title}</h2>
    <table class="ranking-table">
      <thead><tr>${headers.map(header => `<th>${header}</th>`).join('')}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>
`;
  }

  function renderDecadeTable(title, series, valueHeader) {
    if (!series?.labels?.length) return '';
    const rows = series.labels.map((label, idx) => `
        <tr><td>${label}</td><td>${series.data[idx] || 0}</td></tr>`).join('');
    return `
    <h3 style="margin: 2rem 0 1rem; color: #667eea;">${title}</h3>
    <table class="ranking-table">
      <thead><tr><th>Dekada</th><th>${valueHeader}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }

  function renderJewishOwnersTable(owners) {
    if (!owners?.length) return '';
    const rows = owners.map((owner, idx) => `
        <tr>
          <td class="ranking-position">${idx + 1}</td>
          <td>${owner.nazwa_wlasciciela || 'Nieznany'}</td>
          <td>${owner.numer_protokolu || '-'}</td>
          <td>${owner.parcels_count || 0}</td>
          <td>${areaHa(owner.total_area_m2 || 0)} ha</td>
        </tr>`).join('');
    return `<h3 style="margin: 2rem 0 1rem; color: #667eea;">Lista właścicieli</h3>
    <table class="ranking-table">
      <thead><tr><th>#</th><th>Właściciel</th><th>Numer protokółu</th><th>Liczba działek</th><th>Powierzchnia (ha)</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }

  function renderDrawnStats(drawnStats) {
    if (!drawnStats) return '';
    return `
    <h3 style="margin: 1.5rem 0 1rem; color: #667eea;">Wyrysowane działki</h3>
    <div class="stat-grid">
      ${renderStatCard('Wyrysowano', drawnStats.drawn_count || 0)}
      ${renderStatCard('Z właścicielami', drawnStats.protocol_count || 0)}
      ${renderStatCard('Procent ukończenia', `${drawnStats.percentage || 0}%`)}
      ${renderStatCard('Pozostało', drawnStats.missing_count || 0)}
    </div>`;
  }

  function renderLocationArea(locationArea) {
    if (!locationArea) return '';
    return `
    <h3 style="margin: 1.5rem 0 1rem; color: #667eea;">Powierzchnia miejscowości</h3>
    <div class="stat-grid">
      ${renderStatCard('Powierzchnia w hektarach', `${locationArea.area_hectares || '-'} ha`)}
      ${renderStatCard('Powierzchnia w km²', `${locationArea.area_km2 || '-'} km²`)}
    </div>`;
  }

  function ownerAreaM2(owner) {
    return owner.total_area_m2 || owner.total_area || 0;
  }

  function areaHa(areaM2) {
    return ((areaM2 || 0) / 10000).toFixed(2);
  }

  window.StatsPrintReport = Object.freeze({
    init: init,
    printReport: printReport,
    closePrintModal: closePrintModal,
    generatePrintReport: generatePrintReport,
    generateReportHTML: generateReportHTML,
  });
})();
