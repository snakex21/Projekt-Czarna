/**
 * Orkiestrator Centrum Analitycznego (P2.8 Etap 20).
 *
 * Dostęp przez `window.StatsApp`.
 */
(function () {
  'use strict';

  if (!window.OwnersAPI) {
    throw new Error('stats-app.js wymaga js/api.js załadowanego wcześniej');
  }
  if (!window.OwnersUtils) {
    throw new Error('stats-app.js wymaga js/utils.js załadowanego wcześniej');
  }
  if (!window.StatsUI) {
    throw new Error('stats-app.js wymaga js/stats-ui.js załadowanego wcześniej');
  }
  if (!window.StatsActions) {
    throw new Error('stats-app.js wymaga js/stats-actions.js załadowanego wcześniej');
  }
  if (!window.StatsData) {
    throw new Error('stats-app.js wymaga js/stats-data.js załadowanego wcześniej');
  }
  if (!window.StatsHelp) {
    throw new Error('stats-app.js wymaga js/stats-help.js załadowanego wcześniej');
  }
  if (!window.StatsSearch) {
    throw new Error('stats-app.js wymaga js/stats-search.js załadowanego wcześniej');
  }
  if (!window.StatsCounters) {
    throw new Error('stats-app.js wymaga js/stats-counters.js załadowanego wcześniej');
  }
  if (!window.StatsTabs) {
    throw new Error('stats-app.js wymaga js/stats-tabs.js załadowanego wcześniej');
  }
  if (!window.StatsMetrics) {
    throw new Error('stats-app.js wymaga js/stats-metrics.js załadowanego wcześniej');
  }
  if (!window.StatsJewish) {
    throw new Error('stats-app.js wymaga js/stats-jewish.js załadowanego wcześniej');
  }
  if (!window.StatsRanking) {
    throw new Error('stats-app.js wymaga js/stats-ranking.js załadowanego wcześniej');
  }
  if (!window.StatsParcelsRanking) {
    throw new Error('stats-app.js wymaga js/stats-parcels-ranking.js załadowanego wcześniej');
  }
  if (!window.StatsInfrastructureRanking) {
    throw new Error('stats-app.js wymaga js/stats-infrastructure-ranking.js załadowanego wcześniej');
  }
  if (!window.StatsTimeline) {
    throw new Error('stats-app.js wymaga js/stats-timeline.js załadowanego wcześniej');
  }
  if (!window.StatsDemographics) {
    throw new Error('stats-app.js wymaga js/stats-demographics.js załadowanego wcześniej');
  }
  if (!window.StatsGenealogy) {
    throw new Error('stats-app.js wymaga js/stats-genealogy.js załadowanego wcześniej');
  }
  if (!window.StatsReports) {
    throw new Error('stats-app.js wymaga js/stats-reports.js załadowanego wcześniej');
  }
  if (!window.StatsActivityInsights) {
    throw new Error('stats-app.js wymaga js/stats-activity-insights.js załadowanego wcześniej');
  }
  if (!window.StatsCoreCharts) {
    throw new Error('stats-app.js wymaga js/stats-core-charts.js załadowanego wcześniej');
  }
  if (!window.StatsTopSelectors) {
    throw new Error('stats-app.js wymaga js/stats-top-selectors.js załadowanego wcześniej');
  }
  if (!window.StatsNotificationsKeyboard) {
    throw new Error('stats-app.js wymaga js/stats-notifications-keyboard.js załadowanego wcześniej');
  }

  const UI = window.StatsUI;
  const ACTIONS = window.StatsActions;
  const DATA = window.StatsData;
  const HELP = window.StatsHelp;
  const SEARCH = window.StatsSearch;
  const COUNTERS = window.StatsCounters;
  const TABS = window.StatsTabs;
  const METRICS = window.StatsMetrics;
  const JEWISH = window.StatsJewish;
  const RANKING = window.StatsRanking;
  const PARCELS_RANKING = window.StatsParcelsRanking;
  const INFRA_RANKING = window.StatsInfrastructureRanking;
  const TIMELINE = window.StatsTimeline;
  const DEMOGRAPHICS = window.StatsDemographics;
  const GENEALOGY = window.StatsGenealogy;
  const REPORTS = window.StatsReports;
  const ACTIVITY_INSIGHTS = window.StatsActivityInsights;
  const CORE_CHARTS = window.StatsCoreCharts;
  const TOP_SELECTORS = window.StatsTopSelectors;
  const NOTIFICATIONS_KEYBOARD = window.StatsNotificationsKeyboard;
  const showToast = NOTIFICATIONS_KEYBOARD.showToast;

  let statsData = null;
  let charts = {};

  function init() {
    UI.initThemeSync(showToast);
    initUI();
    loadStatistics();
    COUNTERS.init();
    NOTIFICATIONS_KEYBOARD.initKeyboardShortcuts();
  }

  function initUI() {
    DEMOGRAPHICS.init({
      charts: charts,
      showToast: showToast,
      getStatsData: () => statsData,
    });
    GENEALOGY.init({
      charts: charts,
      getStatsData: () => statsData,
    });
    REPORTS.init({
      charts: charts,
      getStatsData: () => statsData,
      showToast: showToast,
    });
    CORE_CHARTS.init({
      charts: charts,
    });
    TOP_SELECTORS.init({
      getStatsData: () => statsData,
    });
    TABS.init({ loadTimeline: () => TIMELINE.render(statsData?.protocols_per_day) });
    SEARCH.init({ getStatsData: () => statsData });
    ACTIONS.init({
      exportChart: REPORTS.exportChart,
      getTop10Owners: TOP_SELECTORS.getTop10Owners,
      getTop10Parcels: TOP_SELECTORS.getTop10Parcels,
      getTop10Rivers: TOP_SELECTORS.getTop10Rivers,
      getTop10Roads: TOP_SELECTORS.getTop10Roads,
      openPeriodComparison: DEMOGRAPHICS.openComparison,
      exportToExcel: REPORTS.exportToExcel,
      printReport: REPORTS.printReport,
      shareReport: REPORTS.shareReport,
      showToast: showToast,
    });
    HELP.init();
    UI.initFullscreen();
  }

  async function loadStatistics() {
    try {
      statsData = await DATA.load();

      COUNTERS.update(statsData.general_stats);
      METRICS.updateArea(statsData.area_stats);
      METRICS.updateRiversRoads(statsData.rivers_stats, statsData.roads_stats);
      METRICS.updateDrawnPercentage(statsData.drawn_percentage);
      METRICS.updateLocationArea(statsData.location_area);
      JEWISH.update(statsData.jewish_stats);
      CORE_CHARTS.createCharts(statsData);
      RANKING.init(statsData, {
        getStatsData: () => statsData,
        performSearch: SEARCH.perform,
      });
      PARCELS_RANKING.init(statsData.parcels_ranking);
      INFRA_RANKING.init(statsData.rivers_ranking, statsData.roads_ranking);

      DEMOGRAPHICS.render(statsData.demografia || [], 'metrical');
      DEMOGRAPHICS.initSourceToggle(statsData.demografia || [], statsData.demografia_official || []);

      ACTIVITY_INSIGHTS.renderCalendar(statsData.protocols_per_day);
      GENEALOGY.render(statsData);
      ACTIVITY_INSIGHTS.loadInsights(statsData);

    } catch (err) {
      console.error('Błąd ładowania statystyk:', err);
      showToast('error', 'Błąd', 'Nie udało się załadować danych');
    }
  }

  window.StatsApp = Object.freeze({
    init: init,
  });
})();
