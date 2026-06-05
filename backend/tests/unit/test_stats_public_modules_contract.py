"""Kontrakt UI migracji `stats-script.js` do publicznych modułów (P2.8 Etap 1).

Pierwszy etap refaktoryzacji statystyk jest celowo mały: duży skrypt pozostaje
orkiestratorem widoku, ale musi korzystać z istniejącej mapy URL-i i helperów
formatowania wydzielonych dla publicznych stron właścicieli.
"""
from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STATS_JS_DIR = PROJECT_ROOT / "static" / "wlasciciele" / "js" / "stats"
STATS_JS = PROJECT_ROOT / "static" / "wlasciciele" / "stats-script.js"
STATS_UI_JS = STATS_JS_DIR / "stats-ui.js"
STATS_ACTIONS_JS = STATS_JS_DIR / "stats-actions.js"
STATS_DATA_JS = STATS_JS_DIR / "stats-data.js"
STATS_HELP_JS = STATS_JS_DIR / "stats-help.js"
STATS_SEARCH_JS = STATS_JS_DIR / "stats-search.js"
STATS_COUNTERS_JS = STATS_JS_DIR / "stats-counters.js"
STATS_TABS_JS = STATS_JS_DIR / "stats-tabs.js"
STATS_METRICS_JS = STATS_JS_DIR / "stats-metrics.js"
STATS_JEWISH_JS = STATS_JS_DIR / "stats-jewish.js"
STATS_RANKING_JS = STATS_JS_DIR / "stats-ranking.js"
STATS_PARCELS_RANKING_JS = STATS_JS_DIR / "stats-parcels-ranking.js"
STATS_INFRASTRUCTURE_RANKING_JS = STATS_JS_DIR / "stats-infrastructure-ranking.js"
STATS_TIMELINE_JS = STATS_JS_DIR / "stats-timeline.js"
STATS_DEMOGRAPHICS_JS = STATS_JS_DIR / "stats-demographics.js"
STATS_GENEALOGY_JS = STATS_JS_DIR / "stats-genealogy.js"
STATS_EXCEL_EXPORT_JS = STATS_JS_DIR / "stats-excel-export.js"
STATS_PRINT_REPORT_JS = STATS_JS_DIR / "stats-print-report.js"
STATS_SHARE_REPORT_JS = STATS_JS_DIR / "stats-share-report.js"
STATS_REPORTS_JS = STATS_JS_DIR / "stats-reports.js"
STATS_ACTIVITY_INSIGHTS_JS = STATS_JS_DIR / "stats-activity-insights.js"
STATS_CORE_CHARTS_JS = STATS_JS_DIR / "stats-core-charts.js"
STATS_TOP_SELECTORS_JS = STATS_JS_DIR / "stats-top-selectors.js"
STATS_NOTIFICATIONS_KEYBOARD_JS = STATS_JS_DIR / "stats-notifications-keyboard.js"
STATS_APP_JS = STATS_JS_DIR / "stats-app.js"
STATS_HTML = PROJECT_ROOT / "static" / "wlasciciele" / "stats.html"


def _source_no_comments(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def _scripts(path: Path) -> list[str]:
    html = path.read_text(encoding="utf-8")
    return re.findall(r'<script\s+src="([^"]+)"', html)


def test_stats_html_loads_public_modules_before_stats_script():
    scripts = _scripts(STATS_HTML)
    for script in (
        "js/api.js",
        "js/utils.js",
        "js/stats/stats-ui.js",
        "js/stats/stats-actions.js",
        "js/stats/stats-data.js",
        "js/stats/stats-help.js",
        "js/stats/stats-search.js",
        "js/stats/stats-counters.js",
        "js/stats/stats-tabs.js",
        "js/stats/stats-metrics.js",
        "js/stats/stats-jewish.js",
        "js/stats/stats-ranking.js",
        "js/stats/stats-parcels-ranking.js",
        "js/stats/stats-infrastructure-ranking.js",
        "js/stats/stats-timeline.js",
        "js/stats/stats-demographics.js",
        "js/stats/stats-genealogy.js",
        "js/stats/stats-excel-export.js",
        "js/stats/stats-print-report.js",
        "js/stats/stats-share-report.js",
        "js/stats/stats-reports.js",
        "js/stats/stats-activity-insights.js",
        "js/stats/stats-core-charts.js",
        "js/stats/stats-top-selectors.js",
        "js/stats/stats-notifications-keyboard.js",
        "js/stats/stats-app.js",
        "stats-script.js",
    ):
        assert script in scripts
    assert scripts.index("js/api.js") < scripts.index("js/utils.js")
    assert scripts.index("js/utils.js") < scripts.index("js/stats/stats-ui.js")
    assert scripts.index("js/stats/stats-ui.js") < scripts.index("js/stats/stats-actions.js")
    assert scripts.index("js/stats/stats-actions.js") < scripts.index("js/stats/stats-data.js")
    assert scripts.index("js/stats/stats-data.js") < scripts.index("js/stats/stats-help.js")
    assert scripts.index("js/stats/stats-help.js") < scripts.index("js/stats/stats-search.js")
    assert scripts.index("js/stats/stats-search.js") < scripts.index("js/stats/stats-counters.js")
    assert scripts.index("js/stats/stats-counters.js") < scripts.index("js/stats/stats-tabs.js")
    assert scripts.index("js/stats/stats-tabs.js") < scripts.index("js/stats/stats-metrics.js")
    assert scripts.index("js/stats/stats-metrics.js") < scripts.index("js/stats/stats-jewish.js")
    assert scripts.index("js/stats/stats-jewish.js") < scripts.index("js/stats/stats-ranking.js")
    assert scripts.index("js/stats/stats-ranking.js") < scripts.index("js/stats/stats-parcels-ranking.js")
    assert scripts.index("js/stats/stats-parcels-ranking.js") < scripts.index("js/stats/stats-infrastructure-ranking.js")
    assert scripts.index("js/stats/stats-infrastructure-ranking.js") < scripts.index("js/stats/stats-timeline.js")
    assert scripts.index("js/stats/stats-timeline.js") < scripts.index("js/stats/stats-demographics.js")
    assert scripts.index("js/stats/stats-demographics.js") < scripts.index("js/stats/stats-genealogy.js")
    assert scripts.index("js/stats/stats-genealogy.js") < scripts.index("js/stats/stats-excel-export.js")
    assert scripts.index("js/stats/stats-excel-export.js") < scripts.index("js/stats/stats-print-report.js")
    assert scripts.index("js/stats/stats-print-report.js") < scripts.index("js/stats/stats-share-report.js")
    assert scripts.index("js/stats/stats-share-report.js") < scripts.index("js/stats/stats-reports.js")
    assert scripts.index("js/stats/stats-reports.js") < scripts.index("js/stats/stats-activity-insights.js")
    assert scripts.index("js/stats/stats-activity-insights.js") < scripts.index("js/stats/stats-core-charts.js")
    assert scripts.index("js/stats/stats-core-charts.js") < scripts.index("js/stats/stats-top-selectors.js")
    assert scripts.index("js/stats/stats-top-selectors.js") < scripts.index("js/stats/stats-notifications-keyboard.js")
    assert scripts.index("js/stats/stats-notifications-keyboard.js") < scripts.index("js/stats/stats-app.js")
    assert scripts.index("js/stats/stats-app.js") < scripts.index("stats-script.js")


def test_stats_ui_file_exists_and_registers_namespace():
    assert STATS_UI_JS.exists()
    source = STATS_UI_JS.read_text(encoding="utf-8")
    assert "window.StatsUI" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_ui_public_api_and_theme_logic():
    source = STATS_UI_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsUI\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsUI = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"initThemeSync", "applyTheme", "initFullscreen"}
    for token in (
        "localStorage.getItem('mapTheme')",
        "localStorage.setItem('mapTheme', newTheme)",
        "document.body.classList.toggle('dark-mode', isDark)",
        "Przełączono na tryb",
        "document.fullscreenElement",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_ui():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsUI" in source
    assert "const UI = window.StatsUI" in source
    assert "stats-app.js wymaga js/stats-ui.js załadowanego wcześniej" in source
    assert "UI.initThemeSync" in source
    assert "UI.initFullscreen" in source


def test_stats_script_no_longer_contains_migrated_ui_helpers():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function initThemeSync",
        "function applyTheme",
        "function initFullscreen",
        "localStorage.setItem('mapTheme'",
        "document.fullscreenElement",
    ):
        assert forbidden not in source


def test_stats_actions_file_exists_and_registers_namespace():
    assert STATS_ACTIONS_JS.exists()
    source = STATS_ACTIONS_JS.read_text(encoding="utf-8")
    assert "window.StatsActions" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_actions_public_api_and_dependencies():
    source = STATS_ACTIONS_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsActions\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsActions = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init"}
    assert "window.OwnersAPI" in source
    assert "API.mapPage()" in source
    for token in (
        "show-on-map",
        "show-parcels-on-map",
        "show-rivers-on-map",
        "show-roads-on-map",
        "export-chart1",
        "export-chart2",
        "compare-btn",
        "export-btn",
        "print-btn",
        "share-btn",
        "Pokazywanie TOP 10 działek na mapie",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_actions():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsActions" in source
    assert "const ACTIONS = window.StatsActions" in source
    assert "stats-app.js wymaga js/stats-actions.js załadowanego wcześniej" in source
    assert "ACTIONS.init" in source


def test_stats_script_no_longer_contains_action_button_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function initActionButtons",
        "show-on-map",
        "show-parcels-on-map",
        "show-rivers-on-map",
        "show-roads-on-map",
        "export-chart1",
        "export-chart2",
        "compare-btn",
        "export-btn",
        "print-btn",
        "share-btn",
    ):
        assert forbidden not in source


def test_stats_data_file_exists_and_registers_namespace():
    assert STATS_DATA_JS.exists()
    source = STATS_DATA_JS.read_text(encoding="utf-8")
    assert "window.StatsData" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_data_public_api_and_fetch_logic():
    source = STATS_DATA_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsData\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsData = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"load"}
    assert "window.OwnersAPI" in source
    assert "const API = window.OwnersAPI" in source
    assert "fetch(API.stats()" in source
    assert "credentials: 'same-origin'" in source
    assert "API ${API.stats()} zwróciło" in source


def test_stats_script_requires_alias_and_uses_stats_data():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsData" in source
    assert "const DATA = window.StatsData" in source
    assert "stats-app.js wymaga js/stats-data.js załadowanego wcześniej" in source
    assert "DATA.load()" in source


def test_stats_help_file_exists_and_registers_namespace():
    assert STATS_HELP_JS.exists()
    source = STATS_HELP_JS.read_text(encoding="utf-8")
    assert "window.StatsHelp" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_help_public_api_and_modal_logic():
    source = STATS_HELP_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsHelp\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsHelp = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init"}
    for token in (
        "help-btn",
        "help-modal",
        "modal-close",
        "modal.classList.add('active')",
        "modal.classList.remove('active')",
        "event.target === modal",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_help():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsHelp" in source
    assert "const HELP = window.StatsHelp" in source
    assert "stats-app.js wymaga js/stats-help.js załadowanego wcześniej" in source
    assert "HELP.init()" in source


def test_stats_script_no_longer_contains_help_modal_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function initHelpModal",
        "help-btn",
        "help-modal",
    ):
        assert forbidden not in source


def test_stats_search_file_exists_and_registers_namespace():
    assert STATS_SEARCH_JS.exists()
    source = STATS_SEARCH_JS.read_text(encoding="utf-8")
    assert "window.StatsSearch" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_search_public_api_and_search_logic():
    source = STATS_SEARCH_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsSearch\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsSearch = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "perform", "highlightText", "clearHighlights"}
    assert "window.OwnersUtils" in source
    assert "UTILS.formatArea" in source
    for token in (
        "search-toggle",
        "search-bar",
        "search-close",
        "global-search",
        "search-results-container",
        "Nie znaleziono wyników",
        "Właściciele",
        "Działki",
        "search-highlight",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_search():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsSearch" in source
    assert "const SEARCH = window.StatsSearch" in source
    assert "stats-app.js wymaga js/stats-search.js załadowanego wcześniej" in source
    assert "SEARCH.init" in source


def test_stats_script_no_longer_contains_search_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function initSearch",
        "function performGlobalSearch",
        "function highlightText",
        "function clearHighlights",
        "search-results-container",
        "search-highlight",
    ):
        assert forbidden not in source


def test_stats_counters_file_exists_and_registers_namespace():
    assert STATS_COUNTERS_JS.exists()
    source = STATS_COUNTERS_JS.read_text(encoding="utf-8")
    assert "window.StatsCounters" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_counters_public_api_and_counter_logic():
    source = STATS_COUNTERS_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsCounters\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsCounters = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "animate", "update"}
    for token in (
        "IntersectionObserver",
        "document.querySelectorAll('.counter')",
        "toLocaleString('pl-PL')",
        "#total-owners .counter",
        "#total-plots .counter",
        "dataset.target",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_counters():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsCounters" in source
    assert "const COUNTERS = window.StatsCounters" in source
    assert "stats-app.js wymaga js/stats-counters.js załadowanego wcześniej" in source
    assert "COUNTERS.init()" in source
    assert "COUNTERS.update(statsData.general_stats)" in source


def test_stats_script_no_longer_contains_counter_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function initCounters",
        "function animateCounter",
        "function updateCounters",
        "IntersectionObserver",
        "document.querySelectorAll('.counter')",
        "#total-owners .counter",
        "#total-plots .counter",
    ):
        assert forbidden not in source


def test_stats_tabs_file_exists_and_registers_namespace():
    assert STATS_TABS_JS.exists()
    source = STATS_TABS_JS.read_text(encoding="utf-8")
    assert "window.StatsTabs" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_tabs_public_api_and_switching_logic():
    source = STATS_TABS_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsTabs\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsTabs = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "switchRankingView"}
    for token in (
        "tab-button",
        "tab-panel",
        "dataset.tab",
        "loadTimeline",
        "ranking-type",
        "infra-type",
        "infra-view-rivers",
        "infra-view-roads",
        "ranking-view-owners",
        "ranking-view-parcels",
        "ranking-view-infrastructure",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_tabs():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsTabs" in source
    assert "const TABS = window.StatsTabs" in source
    assert "stats-app.js wymaga js/stats-tabs.js załadowanego wcześniej" in source
    assert "TABS.init({ loadTimeline: () => TIMELINE.render(statsData?.protocols_per_day) })" in source


def test_stats_script_no_longer_contains_tab_switching_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function initTabs",
        "function initRankingTypeSelector",
        "function initInfrastructureTypeSelector",
        "function switchRankingView",
        "tab-button",
        "tab-panel",
        "ranking-type",
        "infra-type",
        "ranking-view-owners",
        "ranking-view-parcels",
        "ranking-view-infrastructure",
    ):
        assert forbidden not in source


def test_stats_metrics_file_exists_and_registers_namespace():
    assert STATS_METRICS_JS.exists()
    source = STATS_METRICS_JS.read_text(encoding="utf-8")
    assert "window.StatsMetrics" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_metrics_public_api_and_metric_logic():
    source = STATS_METRICS_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsMetrics\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsMetrics = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"updateArea", "updateRiversRoads", "updateDrawnPercentage", "updateLocationArea"}
    for token in (
        "stat-total-area-ha",
        "stat-avg-area-ares",
        "stat-min-area-m2",
        "stat-max-area-ha",
        "stat-rivers-count",
        "stat-roads-count",
        "drawn-count",
        "protocol-count",
        "drawn-percentage",
        "missing-count",
        "location-area-ha",
        "location-area-km2",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_metrics():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsMetrics" in source
    assert "const METRICS = window.StatsMetrics" in source
    assert "stats-app.js wymaga js/stats-metrics.js załadowanego wcześniej" in source
    for token in (
        "METRICS.updateArea(statsData.area_stats)",
        "METRICS.updateRiversRoads(statsData.rivers_stats, statsData.roads_stats)",
        "METRICS.updateDrawnPercentage(statsData.drawn_percentage)",
        "METRICS.updateLocationArea(statsData.location_area)",
    ):
        assert token in source


def test_stats_script_no_longer_contains_metric_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function updateAreaStats",
        "function updateRiversRoadsStats",
        "function updateDrawnPercentageStats",
        "function updateLocationAreaStats",
        "stat-total-area-ha",
        "stat-rivers-count",
        "drawn-count",
        "location-area-ha",
    ):
        assert forbidden not in source


def test_stats_jewish_file_exists_and_registers_namespace():
    assert STATS_JEWISH_JS.exists()
    source = STATS_JEWISH_JS.read_text(encoding="utf-8")
    assert "window.StatsJewish" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_jewish_public_api_and_section_logic():
    source = STATS_JEWISH_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsJewish\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsJewish = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"update"}
    assert "window.OwnersAPI" in source
    assert "API.mapPage()" in source
    for token in (
        "jewish-stats-section",
        "jewish-owners-count",
        "jewish-parcels-count",
        "jewish-total-area",
        "jewish-owners-table-container",
        "show-jewish-parcels",
        "Właściciel",
        "Nr prot.",
        "highlightTopOwners",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_jewish():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsJewish" in source
    assert "const JEWISH = window.StatsJewish" in source
    assert "stats-app.js wymaga js/stats-jewish.js załadowanego wcześniej" in source
    assert "JEWISH.update(statsData.jewish_stats)" in source


def test_stats_script_no_longer_contains_jewish_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function updateJewishStats",
        "jewish-stats-section",
        "jewish-owners-count",
        "jewish-parcels-count",
        "jewish-total-area",
        "jewish-owners-table-container",
        "show-jewish-parcels",
    ):
        assert forbidden not in source


def test_stats_ranking_file_exists_and_registers_namespace():
    assert STATS_RANKING_JS.exists()
    source = STATS_RANKING_JS.read_text(encoding="utf-8")
    assert "window.StatsRanking" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_ranking_public_api_and_dependencies():
    source = STATS_RANKING_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsRanking\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsRanking = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "display", "filter"}
    assert "window.OwnersUtils" in source
    assert "UTILS.formatArea" in source
    for token in (
        "ranking-list",
        "ownership",
        "sort-by",
        "category-filter",
        "ranking-item",
        "ranking-position-badge",
        "Protokół",
        "global-search",
        "callbacks.getStatsData",
        "callbacks.performSearch",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_ranking():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsRanking" in source
    assert "const RANKING = window.StatsRanking" in source
    assert "stats-app.js wymaga js/stats-ranking.js załadowanego wcześniej" in source
    assert "RANKING.init" in source
    assert "getStatsData: () => statsData" in source
    assert "performSearch: SEARCH.perform" in source


def test_stats_script_no_longer_contains_owner_ranking_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function loadRankings",
        "function displayRanking",
        "function filterRankings",
    ):
        assert forbidden not in source


def test_stats_parcels_ranking_file_exists_and_registers_namespace():
    assert STATS_PARCELS_RANKING_JS.exists()
    source = STATS_PARCELS_RANKING_JS.read_text(encoding="utf-8")
    assert "window.StatsParcelsRanking" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_parcels_ranking_public_api_and_dependencies():
    source = STATS_PARCELS_RANKING_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsParcelsRanking\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsParcelsRanking = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "display"}
    assert "window.OwnersUtils" in source
    assert "UTILS.formatArea" in source
    for token in (
        "parcels-ranking-list",
        "parcel-category-filter",
        "ranking-item",
        "ranking-position-badge",
        "Działka nr",
        "Brak właściciela",
        "protokol.html?ownerId=",
        "highlightParcel=",
        "Pokaż na mapie",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_parcels_ranking():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsParcelsRanking" in source
    assert "const PARCELS_RANKING = window.StatsParcelsRanking" in source
    assert "stats-app.js wymaga js/stats-parcels-ranking.js załadowanego wcześniej" in source
    assert "PARCELS_RANKING.init(statsData.parcels_ranking)" in source


def test_stats_script_no_longer_contains_parcels_ranking_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function loadParcelsRanking",
        "function displayParcelsRanking",
        "parcels-ranking-list",
        "highlightParcel=",
    ):
        assert forbidden not in source


def test_stats_infrastructure_ranking_file_exists_and_registers_namespace():
    assert STATS_INFRASTRUCTURE_RANKING_JS.exists()
    source = STATS_INFRASTRUCTURE_RANKING_JS.read_text(encoding="utf-8")
    assert "window.StatsInfrastructureRanking" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_infrastructure_ranking_public_api_and_dependencies():
    source = STATS_INFRASTRUCTURE_RANKING_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsInfrastructureRanking\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsInfrastructureRanking = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "displayRivers", "displayRoads"}
    assert "window.OwnersAPI" in source
    assert "API.mapPage()" in source
    for token in (
        "rivers-ranking-list",
        "roads-ranking-list",
        "ranking-item",
        "ranking-position-badge",
        "river_name",
        "road_number",
        "length_m",
        "Bez nazwy",
        "Rzeka",
        "Droga",
        "highlightRivers=",
        "highlightRoads=",
        "Pokaż na mapie",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_infrastructure_ranking():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsInfrastructureRanking" in source
    assert "const INFRA_RANKING = window.StatsInfrastructureRanking" in source
    assert "stats-app.js wymaga js/stats-infrastructure-ranking.js załadowanego wcześniej" in source
    assert "INFRA_RANKING.init(statsData.rivers_ranking, statsData.roads_ranking)" in source


def test_stats_script_no_longer_contains_infrastructure_ranking_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function loadRiversRanking",
        "function loadRoadsRanking",
        "rivers-ranking-list",
        "roads-ranking-list",
        "highlightRivers=",
        "highlightRoads=",
    ):
        assert forbidden not in source


def test_stats_timeline_file_exists_and_registers_namespace():
    assert STATS_TIMELINE_JS.exists()
    source = STATS_TIMELINE_JS.read_text(encoding="utf-8")
    assert "window.StatsTimeline" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_timeline_public_api_and_render_logic():
    source = STATS_TIMELINE_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsTimeline\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsTimeline = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"render"}
    for token in (
        "timeline-content",
        "protocol_date",
        "toLocaleDateString('pl-PL'",
        "timeline-item",
        "timeline-marker",
        "timeline-date",
        "timeline-title",
        "timeline-owners-list",
        "protocol_count",
        "protokol.html?ownerId=",
        "kliknij, aby rozwinąć",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_timeline():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsTimeline" in source
    assert "const TIMELINE = window.StatsTimeline" in source
    assert "stats-app.js wymaga js/stats-timeline.js załadowanego wcześniej" in source
    assert "TIMELINE.render(statsData?.protocols_per_day)" in source


def test_stats_script_no_longer_contains_timeline_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function loadTimeline",
        "timeline-content",
        "timeline-item",
        "timeline-marker",
        "timeline-owners-list",
        "protocols_per_day.map",
    ):
        assert forbidden not in source


def test_stats_demographics_file_exists_and_registers_namespace():
    assert STATS_DEMOGRAPHICS_JS.exists()
    source = STATS_DEMOGRAPHICS_JS.read_text(encoding="utf-8")
    assert "window.StatsDemographics" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_demographics_public_api_and_main_logic():
    source = STATS_DEMOGRAPHICS_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsDemographics\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsDemographics = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "render", "initSourceToggle", "openComparison", "performComparison", "closeComparison"}
    for token in (
        "demographicsChart",
        "demo-timeline-track",
        "demo-cards",
        "demo-growth",
        "demo-years",
        "demo-source",
        "demo-summary h3",
        "Dynamika populacji",
        "Populacja ogółem",
        "Katolicy",
        "Żydzi",
        "demo-year-card",
        "decade-group",
        "comparison-modal",
        "compare-execute",
        "comparison-chart",
        "comparison-summary",
        "Wybierz oba okresy do porównania",
        "Wygenerowano porównanie okresów",
        "callbacks.showToast",
        "charts.demographics",
        "charts.comparison",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_demographics():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsDemographics" in source
    assert "const DEMOGRAPHICS = window.StatsDemographics" in source
    assert "stats-app.js wymaga js/stats-demographics.js załadowanego wcześniej" in source
    assert "DEMOGRAPHICS.init({" in source
    assert "charts: charts" in source
    assert "showToast: showToast" in source
    assert "getStatsData: () => statsData" in source
    assert "DEMOGRAPHICS.render(statsData.demografia || [], 'metrical')" in source
    assert "DEMOGRAPHICS.initSourceToggle(statsData.demografia || [], statsData.demografia_official || [])" in source
    assert "openPeriodComparison: DEMOGRAPHICS.openComparison" in source


def test_stats_script_no_longer_contains_demographics_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function loadDemographics",
        "function createDemographicsChart",
        "function createDemographicsTimeline",
        "function createDemographicsCards",
        "function createComparisonAnalysis",
        "function openPeriodComparison",
        "function createComparisonModal",
        "function updateYearOptions",
        "function performComparison",
        "function displayComparisonResults",
        "function createComparisonChart",
        "function generateComparisonSummary",
        "function closeComparisonModal",
        "function initDemographyToggle",
        "function updateDemographicsHeader",
        "function scrollToYear",
        "let demografiaOfficial",
        "let demografiaMetrical",
    ):
        assert forbidden not in source


def test_stats_genealogy_file_exists_and_registers_namespace():
    assert STATS_GENEALOGY_JS.exists()
    source = STATS_GENEALOGY_JS.read_text(encoding="utf-8")
    assert "window.StatsGenealogy" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_genealogy_public_api_and_main_logic():
    source = STATS_GENEALOGY_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsGenealogy\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsGenealogy = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "render", "updateSeries"}
    for token in (
        "callbacks.charts",
        "callbacks.getStatsData",
        "stat-total-people",
        "stat-gender-ratio",
        "top-surnames-list",
        "genealogy-births-chart",
        "genealogy-series-toggle",
        "gen-series",
        "births_by_decade",
        "deaths_by_decade",
        "marriages_by_decade",
        "infant_mortality",
        "lifespan_by_generation",
        "death_age_distribution",
        "family_structure",
        "stat-infant-deaths",
        "infant-mortality-chart",
        "lifespan-chart",
        "death-age-chart",
        "family-structure-chart",
        "Lata $1",
        "Średni wiek śmierci",
        "Zgony niemowląt",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_genealogy():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsGenealogy" in source
    assert "const GENEALOGY = window.StatsGenealogy" in source
    assert "stats-app.js wymaga js/stats-genealogy.js załadowanego wcześniej" in source
    assert "GENEALOGY.init({" in source
    assert "charts: charts" in source
    assert "getStatsData: () => statsData" in source
    assert "GENEALOGY.render(statsData)" in source


def test_stats_script_no_longer_contains_genealogy_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function loadGenealogyStats",
        "function updateGenealogySeries",
        "function renderInfantMortalityChart",
        "function renderLifespanChart",
        "function renderDeathAgeChart",
        "function renderFamilyStructureChart",
        "genealogy-births-chart",
        "infant-mortality-chart",
        "lifespan-chart",
        "death-age-chart",
        "family-structure-chart",
        "top-surnames-list",
    ):
        assert forbidden not in source


def test_stats_reports_file_exists_and_registers_namespace():
    assert STATS_REPORTS_JS.exists()
    source = STATS_REPORTS_JS.read_text(encoding="utf-8")
    assert "window.StatsReports" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_excel_export_file_exists_and_registers_namespace():
    assert STATS_EXCEL_EXPORT_JS.exists()
    source = STATS_EXCEL_EXPORT_JS.read_text(encoding="utf-8")
    assert "window.StatsExcelExport" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_excel_export_public_api_and_export_logic():
    source = STATS_EXCEL_EXPORT_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsExcelExport\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsExcelExport = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "exportChart", "exportToExcel"}
    for token in (
        "charts = callbacks.charts",
        "getStatsData = callbacks.getStatsData",
        "showToast = callbacks.showToast",
        "toBase64Image",
        "wykres-${chartId}",
        "XLSX.utils.book_new",
        "XLSX.utils.book_append_sheet",
        "XLSX.writeFile",
        "statystyki_gmina_czarna_",
    ):
        assert token in source


def test_stats_print_report_file_exists_and_registers_namespace():
    assert STATS_PRINT_REPORT_JS.exists()
    source = STATS_PRINT_REPORT_JS.read_text(encoding="utf-8")
    assert "window.StatsPrintReport" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_print_report_public_api_and_print_logic():
    source = STATS_PRINT_REPORT_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsPrintReport\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsPrintReport = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "printReport", "closePrintModal", "generatePrintReport", "generateReportHTML"}
    for token in (
        "getStatsData = callbacks.getStatsData",
        "showToast = callbacks.showToast",
        "window.closePrintModal",
        "window.generatePrintReport",
        "print-modal",
        "print-general",
        "print-rankings",
        "print-categories",
        "print-demographics",
        "print-genealogy",
        "print-insights",
        "print-rankings-count",
        "print-parcels",
        "print-rivers",
        "print-roads",
        "print-jewish-stats",
        "print-digitalization",
        "generateReportHTML",
        "window.open",
        "document.write",
        "printWindow.print",
        "LOCATION_FULL_NAME",
        "Raport Analityczny",
    ):
        assert token in source


def test_stats_print_report_splits_html_into_section_renderers():
    """Raport drukowany nie trzyma już całego HTML-a w jednej monolitycznej funkcji."""
    source = STATS_PRINT_REPORT_JS.read_text(encoding="utf-8")
    for function_name in (
        "renderReportDocumentStart",
        "renderGeneralSection",
        "renderRankingsSection",
        "renderCategoriesSection",
        "renderDemographicsSection",
        "renderGenealogySection",
        "renderInsightsSection",
        "renderRankingsCountSection",
        "renderParcelsSection",
        "renderRiversSection",
        "renderRoadsSection",
        "renderJewishStatsSection",
        "renderDigitalizationSection",
        "renderReportFooter",
    ):
        assert f"function {function_name}" in source


def test_stats_print_report_generate_report_html_is_orchestrator():
    """generateReportHTML tylko składa sekcje i nie zawiera pełnych template'ów sekcji."""
    source = STATS_PRINT_REPORT_JS.read_text(encoding="utf-8")
    match = re.search(
        r"function\s+generateReportHTML\s*\([^)]*\)\s*\{(?P<body>[\s\S]*?)\n\}",
        source,
    )
    assert match, "Brak function generateReportHTML"
    body = match.group("body")
    for token in (
        "renderReportDocumentStart",
        "renderGeneralSection",
        "renderRankingsSection",
        "renderDigitalizationSection",
        "renderReportFooter",
    ):
        assert token in body
    assert "Top 10 Właścicieli (według powierzchni)" not in body
    assert "Statystyki Właścicieli Żydowskich" not in body


def test_stats_share_report_file_exists_and_registers_namespace():
    assert STATS_SHARE_REPORT_JS.exists()
    source = STATS_SHARE_REPORT_JS.read_text(encoding="utf-8")
    assert "window.StatsShareReport" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_share_report_public_api_and_share_logic():
    source = STATS_SHARE_REPORT_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsShareReport\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsShareReport = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "shareReport"}
    for token in (
        "showToast = callbacks.showToast",
        "share-modal",
        "share-link-input",
        "qrcode",
        "copy-link-btn",
        "new QRCode",
        "QRCode.CorrectLevel.H",
        "navigator.clipboard.writeText",
        "window.location.href",
        "modal.classList.add('active')",
        "modal.classList.remove('active')",
    ):
        assert token in source


def test_stats_reports_public_api_and_report_logic():
    source = STATS_REPORTS_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsReports\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsReports = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {
        "init",
        "exportChart",
        "exportToExcel",
        "printReport",
        "closePrintModal",
        "generatePrintReport",
        "shareReport",
    }
    for token in (
        "window.StatsExcelExport",
        "window.StatsPrintReport",
        "window.StatsShareReport",
        "const EXCEL_EXPORT = window.StatsExcelExport",
        "const PRINT_REPORT = window.StatsPrintReport",
        "const SHARE_REPORT = window.StatsShareReport",
        "EXCEL_EXPORT.init",
        "PRINT_REPORT.init",
        "SHARE_REPORT.init",
        "EXCEL_EXPORT.exportChart",
        "EXCEL_EXPORT.exportToExcel",
        "PRINT_REPORT.printReport",
        "PRINT_REPORT.closePrintModal",
        "PRINT_REPORT.generatePrintReport",
        "SHARE_REPORT.shareReport",
    ):
        assert token in source


def test_stats_reports_facade_no_longer_contains_report_implementation():
    source = _source_no_comments(STATS_REPORTS_JS)
    for forbidden in (
        "XLSX.utils.book_new",
        "XLSX.writeFile",
        "function generateReportHTML",
        "new QRCode",
        "share-link-input",
        "print-general",
        "print-rankings",
        "window.open",
    ):
        assert forbidden not in source


def test_stats_script_requires_alias_and_uses_stats_reports():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsReports" in source
    assert "const REPORTS = window.StatsReports" in source
    assert "stats-app.js wymaga js/stats-reports.js załadowanego wcześniej" in source
    assert "REPORTS.init({" in source
    assert "charts: charts" in source
    assert "getStatsData: () => statsData" in source
    assert "showToast: showToast" in source
    assert "exportChart: REPORTS.exportChart" in source
    assert "exportToExcel: REPORTS.exportToExcel" in source
    assert "printReport: REPORTS.printReport" in source
    assert "shareReport: REPORTS.shareReport" in source


def test_stats_script_no_longer_contains_report_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function exportChart",
        "function exportToExcel",
        "function printReport",
        "function closePrintModal",
        "function generatePrintReport",
        "function generateReportHTML",
        "function shareReport",
        "XLSX.utils.book_new",
        "XLSX.writeFile",
        "new QRCode",
        "share-link-input",
        "print-modal",
    ):
        assert forbidden not in source


def test_stats_activity_insights_file_exists_and_registers_namespace():
    assert STATS_ACTIVITY_INSIGHTS_JS.exists()
    source = STATS_ACTIVITY_INSIGHTS_JS.read_text(encoding="utf-8")
    assert "window.StatsActivityInsights" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_activity_insights_public_api_and_render_logic():
    source = STATS_ACTIVITY_INSIGHTS_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsActivityInsights\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsActivityInsights = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"renderCalendar", "loadInsights"}
    for token in (
        "activity-calendar-container",
        "activity-calendar",
        "activity-legend",
        "calendar-tooltip",
        "data-tooltip",
        "toLocaleDateString('pl-PL')",
        "stat-buildings",
        "stat-chapels",
        "stat-special",
        "biggest-owner",
        "ownership-trend",
        "concentration",
        "Top 10 właścicieli posiada",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_activity_insights():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsActivityInsights" in source
    assert "const ACTIVITY_INSIGHTS = window.StatsActivityInsights" in source
    assert "stats-app.js wymaga js/stats-activity-insights.js załadowanego wcześniej" in source
    assert "ACTIVITY_INSIGHTS.renderCalendar(statsData.protocols_per_day)" in source
    assert "ACTIVITY_INSIGHTS.loadInsights(statsData)" in source


def test_stats_script_no_longer_contains_activity_insights_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function renderActivityCalendar",
        "function loadInsights",
        "activity-calendar-container",
        "calendar-tooltip",
        "stat-buildings",
        "stat-chapels",
        "stat-special",
        "biggest-owner",
        "ownership-trend",
        "concentration",
    ):
        assert forbidden not in source


def test_stats_core_charts_file_exists_and_registers_namespace():
    assert STATS_CORE_CHARTS_JS.exists()
    source = STATS_CORE_CHARTS_JS.read_text(encoding="utf-8")
    assert "window.StatsCoreCharts" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_core_charts_public_api_and_chart_logic():
    source = STATS_CORE_CHARTS_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsCoreCharts\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsCoreCharts = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "createCharts"}
    for token in (
        "Chart.defaults.font.family",
        "charts = callbacks.charts",
        "document.getElementById('pieChart')?.getContext('2d')",
        "data.category_counts",
        "charts.pie = new Chart",
        "type: 'doughnut'",
        "labels: ['Rolne', 'Budowlane', 'Lasy', 'Pastwiska', 'Inne']",
        "backgroundColor: ['#10b981', '#f59e0b', '#3b82f6', '#8b5cf6', '#ef4444']",
        "legend: { position: 'bottom' }",
        "document.getElementById('barChart')?.getContext('2d')",
        "data?.rankings_real?.all_plots",
        "slice(0, 10).reverse()",
        "charts.bar = new Chart",
        "type: 'bar'",
        "label: 'Liczba działek'",
        "indexAxis: 'y'",
        "this.getLabelForValue(value)",
        "label.substring(0, 22) + '…'",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_core_charts():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsCoreCharts" in source
    assert "const CORE_CHARTS = window.StatsCoreCharts" in source
    assert "stats-app.js wymaga js/stats-core-charts.js załadowanego wcześniej" in source
    assert "CORE_CHARTS.init({" in source
    assert "charts: charts" in source
    assert "CORE_CHARTS.createCharts(statsData)" in source


def test_stats_script_no_longer_contains_core_charts_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "Chart.defaults.font.family",
        "function createCharts",
        "document.getElementById('pieChart')?.getContext('2d')",
        "document.getElementById('barChart')?.getContext('2d')",
        "charts.pie = new Chart",
        "charts.bar = new Chart",
        "type: 'doughnut'",
        "type: 'bar'",
        "labels: ['Rolne', 'Budowlane', 'Lasy', 'Pastwiska', 'Inne']",
        "slice(0, 10).reverse()",
    ):
        assert forbidden not in source


def test_stats_top_selectors_file_exists_and_registers_namespace():
    assert STATS_TOP_SELECTORS_JS.exists()
    source = STATS_TOP_SELECTORS_JS.read_text(encoding="utf-8")
    assert "window.StatsTopSelectors" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_top_selectors_public_api_and_selection_logic():
    source = STATS_TOP_SELECTORS_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsTopSelectors\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsTopSelectors = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init", "getTop10Owners", "getTop10Parcels", "getTop10Rivers", "getTop10Roads"}
    for token in (
        "getStatsData = callbacks.getStatsData",
        "ownership === 'real'",
        "rankings_real",
        "rankings_protocol",
        "category === 'all'",
        "input[name=\"sort-by\"]:checked",
        "sortBy === 'area'",
        "total_area_m2",
        "plot_count",
        "slice(0, 10)",
        "parcel-category-filter",
        "parcels_ranking",
        "rivers_ranking",
        "roads_ranking",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_top_selectors():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsTopSelectors" in source
    assert "const TOP_SELECTORS = window.StatsTopSelectors" in source
    assert "stats-app.js wymaga js/stats-top-selectors.js załadowanego wcześniej" in source
    assert "TOP_SELECTORS.init({" in source
    assert "getStatsData: () => statsData" in source
    assert "getTop10Owners: TOP_SELECTORS.getTop10Owners" in source
    assert "getTop10Parcels: TOP_SELECTORS.getTop10Parcels" in source
    assert "getTop10Rivers: TOP_SELECTORS.getTop10Rivers" in source
    assert "getTop10Roads: TOP_SELECTORS.getTop10Roads" in source


def test_stats_script_no_longer_contains_top_selectors_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function getTop10Owners",
        "function getTop10Parcels",
        "function getTop10Rivers",
        "function getTop10Roads",
        "input[name=\"sort-by\"]:checked",
        "parcel-category-filter",
        "statsData.rankings_real",
        "statsData.rankings_protocol",
        "statsData?.parcels_ranking",
        "statsData?.rivers_ranking",
        "statsData?.roads_ranking",
    ):
        assert forbidden not in source


def test_stats_notifications_keyboard_file_exists_and_registers_namespace():
    assert STATS_NOTIFICATIONS_KEYBOARD_JS.exists()
    source = STATS_NOTIFICATIONS_KEYBOARD_JS.read_text(encoding="utf-8")
    assert "window.StatsNotificationsKeyboard" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_notifications_keyboard_public_api_and_ui_logic():
    source = STATS_NOTIFICATIONS_KEYBOARD_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsNotificationsKeyboard\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsNotificationsKeyboard = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"showToast", "initKeyboardShortcuts"}
    for token in (
        "toast-container",
        "document.createElement('div')",
        "toast ${type}",
        "toast-icon",
        "toast-content",
        "toast-title",
        "toast-message",
        "container.appendChild(toast)",
        "toastOut 0.3s ease",
        "toast.remove()",
        "document.addEventListener('keydown'",
        "e.ctrlKey",
        "e.preventDefault()",
        "search-toggle",
        "theme-toggle",
        "input, textarea",
        "Escape",
        ".modal.active",
        "search-bar",
    ):
        assert token in source


def test_stats_script_requires_alias_and_uses_stats_notifications_keyboard():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsNotificationsKeyboard" in source
    assert "const NOTIFICATIONS_KEYBOARD = window.StatsNotificationsKeyboard" in source
    assert "stats-app.js wymaga js/stats-notifications-keyboard.js załadowanego wcześniej" in source
    assert "const showToast = NOTIFICATIONS_KEYBOARD.showToast" in source
    assert "NOTIFICATIONS_KEYBOARD.initKeyboardShortcuts()" in source


def test_stats_script_no_longer_contains_notifications_keyboard_implementation():
    source = _source_no_comments(STATS_JS)
    for forbidden in (
        "function showToast",
        "function initKeyboardShortcuts",
        "toast-container",
        "document.createElement('div')",
        "toast ${type}",
        "toastOut 0.3s ease",
        "document.addEventListener('keydown'",
        "search-toggle",
        "theme-toggle",
        ".modal.active",
        "search-bar",
    ):
        assert forbidden not in source


def test_stats_app_file_exists_and_registers_namespace():
    assert STATS_APP_JS.exists()
    source = STATS_APP_JS.read_text(encoding="utf-8")
    assert "window.StatsApp" in source
    assert "Object.freeze" in source
    assert re.search(r"\(function\s*\(\s*\)\s*\{", source)
    assert "'use strict'" in source or '"use strict"' in source


def test_stats_app_public_api_and_orchestration_logic():
    source = STATS_APP_JS.read_text(encoding="utf-8")
    match = re.search(
        r"window\.StatsApp\s*=\s*Object\.freeze\(\s*\{([\s\S]*?)\}\s*\)",
        source,
    )
    assert match, "Brak window.StatsApp = Object.freeze({ ... })"
    keys = re.findall(r"(\w+)\s*:\s*\w+", match.group(1))
    assert set(keys) == {"init"}
    for token in (
        "let statsData = null",
        "let charts = {}",
        "const showToast = NOTIFICATIONS_KEYBOARD.showToast",
        "function init()",
        "UI.initThemeSync(showToast)",
        "initUI()",
        "loadStatistics()",
        "COUNTERS.init()",
        "NOTIFICATIONS_KEYBOARD.initKeyboardShortcuts()",
        "function initUI()",
        "DEMOGRAPHICS.init({",
        "GENEALOGY.init({",
        "REPORTS.init({",
        "CORE_CHARTS.init({",
        "TOP_SELECTORS.init({",
        "TABS.init({",
        "SEARCH.init({",
        "ACTIONS.init({",
        "HELP.init()",
        "UI.initFullscreen()",
        "async function loadStatistics()",
        "statsData = await DATA.load()",
        "COUNTERS.update(statsData.general_stats)",
        "METRICS.updateArea(statsData.area_stats)",
        "JEWISH.update(statsData.jewish_stats)",
        "CORE_CHARTS.createCharts(statsData)",
        "RANKING.init(statsData,",
        "PARCELS_RANKING.init(statsData.parcels_ranking)",
        "INFRA_RANKING.init(statsData.rivers_ranking, statsData.roads_ranking)",
        "DEMOGRAPHICS.render(statsData.demografia || [], 'metrical')",
        "ACTIVITY_INSIGHTS.renderCalendar(statsData.protocols_per_day)",
        "GENEALOGY.render(statsData)",
        "ACTIVITY_INSIGHTS.loadInsights(statsData)",
    ):
        assert token in source


def test_stats_script_is_minimal_bootstrap_to_stats_app():
    source = _source_no_comments(STATS_JS)
    assert "window.StatsApp" in source
    assert "stats-script.js wymaga js/stats-app.js załadowanego wcześniej" in source
    assert "document.addEventListener('DOMContentLoaded'" in source
    assert "window.StatsApp.init()" in source
    for forbidden in (
        "function initUI",
        "async function loadStatistics",
        "let statsData",
        "let charts",
        "const UI = window.StatsUI",
        "const ACTIONS = window.StatsActions",
        "const DATA = window.StatsData",
        "const HELP = window.StatsHelp",
        "const SEARCH = window.StatsSearch",
        "const COUNTERS = window.StatsCounters",
        "const TABS = window.StatsTabs",
        "const METRICS = window.StatsMetrics",
        "const JEWISH = window.StatsJewish",
        "const RANKING = window.StatsRanking",
        "const PARCELS_RANKING = window.StatsParcelsRanking",
        "const INFRA_RANKING = window.StatsInfrastructureRanking",
        "const TIMELINE = window.StatsTimeline",
        "const DEMOGRAPHICS = window.StatsDemographics",
        "const GENEALOGY = window.StatsGenealogy",
        "const REPORTS = window.StatsReports",
        "const ACTIVITY_INSIGHTS = window.StatsActivityInsights",
        "const CORE_CHARTS = window.StatsCoreCharts",
        "const TOP_SELECTORS = window.StatsTopSelectors",
        "const NOTIFICATIONS_KEYBOARD = window.StatsNotificationsKeyboard",
        "DATA.load()",
        "COUNTERS.update(",
        "METRICS.updateArea(",
        "CORE_CHARTS.createCharts(",
        "RANKING.init(",
        "DEMOGRAPHICS.render(",
        "GENEALOGY.render(",
    ):
        assert forbidden not in source


def test_stats_script_delegates_stats_endpoint_to_stats_data():
    source = _source_no_comments(STATS_APP_JS)
    assert "DATA.load()" in source
    assert "fetch(API.stats())" not in source
    assert "API.stats()" not in source
    assert "fetch('/api/stats')" not in source
    assert 'fetch("/api/stats")' not in source


def test_stats_script_uses_owners_utils_for_area_formatting():
    source = _source_no_comments(STATS_JS)
    modules_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (STATS_SEARCH_JS, STATS_RANKING_JS, STATS_PARCELS_RANKING_JS)
    )
    assert "UTILS.formatArea" in modules_source
    assert "function formatArea" not in source
