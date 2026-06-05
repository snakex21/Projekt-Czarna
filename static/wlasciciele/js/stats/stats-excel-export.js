/**
 * Eksport wykres?w i danych Excel centrum analitycznego (P2.8 Etap 21).
 *
 * Dost?p przez `window.StatsExcelExport`.
 */
(function () {
  'use strict';

  let charts = {};
  let getStatsData = () => null;
  let showToast = () => {};

  function init(callbacks) {
    callbacks = callbacks || {};
    charts = callbacks.charts || {};
    getStatsData = callbacks.getStatsData || getStatsData;
    showToast = callbacks.showToast || showToast;
  }

/**
 * Pobiera obraz bieżącego wykresu (PNG).
 * @param {'pieChart'|'barChart'} chartId
 */
function exportChart(chartId) {
  const chart = charts[chartId === 'pieChart' ? 'pie' : 'bar'];
  if (!chart) return;
  const url = chart.toBase64Image();
  const link = document.createElement('a');
  link.download = `wykres-${chartId}-${Date.now()}.png`;
  link.href = url;
  link.click();
  showToast('success', 'Eksport', 'Wykres został pobrany');
}

/**
 * Eksport całego zestawu do Excela (SheetJS).
 */
function exportToExcel() {
  const statsData = getStatsData();

  if (!statsData) {
    showToast('error', 'Błąd', 'Dane nie zostały jeszcze załadowane.');
    return;
  }

  try {
    showToast('info', 'Eksport', 'Rozpoczęto generowanie pliku Excel.');
    const wb = XLSX.utils.book_new();

    // Podsumowanie
    const summary = [
      ['Kluczowa statystyka', 'Wartość'],
      ['Całkowita liczba właścicieli', statsData.general_stats.total_owners],
      ['Całkowita liczba działek', statsData.general_stats.total_plots],
      ...Object.entries(statsData.category_counts || {}).map(([k, v]) => [`Liczba działek – ${k}`, v])
    ];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(summary), 'Podsumowanie');

    // Rankingi (rzeczywiste)
    const realRows = [];
    for (const category in (statsData.rankings_real || {})) {
      (statsData.rankings_real[category] || []).forEach((o, idx) => {
        realRows.push({
          'Kategoria': category,
          'Pozycja': idx + 1,
          'Właściciel': o.nazwa_wlasciciela,
          'Protokół': o.numer_protokolu ?? '',
          'Liczba działek': o.plot_count
        });
      });
    }
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(realRows), 'Rankingi (real)');

    // Rankingi (protokół)
    const protoRows = [];
    for (const category in (statsData.rankings_protocol || {})) {
      (statsData.rankings_protocol[category] || []).forEach((o, idx) => {
        protoRows.push({
          'Kategoria': category,
          'Pozycja': idx + 1,
          'Właściciel': o.nazwa_wlasciciela,
          'Protokół': o.numer_protokolu ?? '',
          'Liczba działek': o.plot_count
        });
      });
    }
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(protoRows), 'Rankingi (protokół)');

    // Demografia
    const demoRows = (statsData.demografia || []).map(d => ({
      'Rok': d.rok,
      'Populacja': d.populacja_ogolem,
      'Katolicy': d.katolicy ?? '',
      'Żydzi': d.zydzi ?? '',
      'Inni': d.inni ?? '',
      'Opis': d.opis ?? ''
    }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(demoRows), 'Demografia');

    // Genealogia – urodzenia wg dekad
    const genAoa = [
      ['Urodzenia wg Dekad'],
      ['Dekada', 'Liczba urodzeń'],
      ...(statsData.genealogy_stats?.births_by_decade?.labels || []).map((label, i) => [
        label, (statsData.genealogy_stats?.births_by_decade?.data || [])[i] ?? 0
      ])
    ];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(genAoa), 'Genealogia');

    // Aktywność spisowa
    const activityRows = (statsData.protocols_per_day || []).map(day => ({
      'Data': new Date(day.protocol_date).toLocaleDateString('pl-PL'),
      'Liczba protokołów': day.protocol_count,
      'Właściciele': (day.owners || []).map(o => o.nazwa_wlasciciela).join(', ')
    }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(activityRows), 'Aktywność spisowa');

    const today = new Date().toISOString().slice(0, 10);
    const fileName = `statystyki_gmina_czarna_${today}.xlsx`;
    XLSX.writeFile(wb, fileName);
    showToast('success', 'Eksport zakończony', `Plik ${fileName} został pobrany.`);

  } catch (error) {
    console.error('Błąd podczas eksportu do Excel:', error);
    showToast('error', 'Błąd eksportu', 'Wystąpił nieoczekiwany problem.');
  }
}

  window.StatsExcelExport = Object.freeze({
    init: init,
    exportChart: exportChart,
    exportToExcel: exportToExcel,
  });
})();
