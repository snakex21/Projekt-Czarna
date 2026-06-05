/**
 * Fasada raport?w centrum analitycznego (P2.8 Etap 21).
 *
 * Dost?p przez `window.StatsReports`.
 */
(function () {
  'use strict';

  if (!window.StatsExcelExport) {
    throw new Error('stats-reports.js wymaga js/stats-excel-export.js za?adowanego wcze?niej');
  }
  if (!window.StatsPrintReport) {
    throw new Error('stats-reports.js wymaga js/stats-print-report.js za?adowanego wcze?niej');
  }
  if (!window.StatsShareReport) {
    throw new Error('stats-reports.js wymaga js/stats-share-report.js za?adowanego wcze?niej');
  }

  const EXCEL_EXPORT = window.StatsExcelExport;
  const PRINT_REPORT = window.StatsPrintReport;
  const SHARE_REPORT = window.StatsShareReport;

  function init(callbacks) {
    callbacks = callbacks || {};
    EXCEL_EXPORT.init({
      charts: callbacks.charts,
      getStatsData: callbacks.getStatsData,
      showToast: callbacks.showToast,
    });
    PRINT_REPORT.init({
      getStatsData: callbacks.getStatsData,
      showToast: callbacks.showToast,
    });
    SHARE_REPORT.init({
      showToast: callbacks.showToast,
    });
  }

  function exportChart(chartId) {
    return EXCEL_EXPORT.exportChart(chartId);
  }

  function exportToExcel() {
    return EXCEL_EXPORT.exportToExcel();
  }

  function printReport() {
    return PRINT_REPORT.printReport();
  }

  function closePrintModal() {
    return PRINT_REPORT.closePrintModal();
  }

  function generatePrintReport() {
    return PRINT_REPORT.generatePrintReport();
  }

  function shareReport() {
    return SHARE_REPORT.shareReport();
  }

  window.StatsReports = Object.freeze({
    init: init,
    exportChart: exportChart,
    exportToExcel: exportToExcel,
    printReport: printReport,
    closePrintModal: closePrintModal,
    generatePrintReport: generatePrintReport,
    shareReport: shareReport,
  });
})();
