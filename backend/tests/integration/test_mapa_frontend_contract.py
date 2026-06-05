"""Kontrakt mapy ↔ moduł historical_points ↔ backend.

Weryfikuje:
- mapa.html ładuje nowy moduł PO map-script.js,
- panels.js ma checkbox "historical-points" w legendzie,
- map-script.js obsługuje grupę 'historical-points' w setMapLayerVisibility,
- map-script.js eksponuje getMap()/addGeojsonSource()/addGeojsonLayer()
  w window.MapAPI oraz alias window.MapV2 (potrzebne modułowi),
- endpoint /api/historical-points jest dostępny z perspektywy klienta
  (bez HTML fallback - ten sam guard co dla admina).
"""
from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAPA_HTML = PROJECT_ROOT / "static" / "mapa" / "mapa.html"
MAP_JS_DIR = PROJECT_ROOT / "static" / "mapa" / "js"
MAP_SCRIPT_JS = MAP_JS_DIR / "map-script.js"
PANELS_JS = MAP_JS_DIR / "panels.js"
HISTORICAL_POINTS_JS = MAP_JS_DIR / "historical_points.js"
MAP_PANEL_DIR = MAP_JS_DIR / "panel"
PANEL_LEGEND_JS = MAP_PANEL_DIR / "panel-legend.js"
PANEL_LAYOUT_JS = MAP_PANEL_DIR / "panel-layout.js"
PANEL_SEARCH_JS = MAP_PANEL_DIR / "panel-search.js"
PANEL_PARCELS_JS = MAP_PANEL_DIR / "panel-parcels.js"
PANEL_OWNERS_JS = MAP_PANEL_DIR / "panel-owners.js"
MAP_CONSTANTS_JS = MAP_JS_DIR / "constants.js"
MAP_UTILS_JS = MAP_JS_DIR / "utils.js"
MAP_GEOMETRY_JS = MAP_JS_DIR / "geometry.js"
MAP_OWNERSHIP_JS = MAP_JS_DIR / "ownership.js"
MAP_LAYER_CONTROLS_JS = MAP_JS_DIR / "layer-controls.js"
MAP_LAYERS_JS = MAP_JS_DIR / "layers.js"
MAP_INTERACTIONS_JS = MAP_JS_DIR / "interactions.js"
MAP_HIGHLIGHT_MARKERS_JS = MAP_JS_DIR / "highlight-markers.js"
MAP_HIGHLIGHTS_JS = MAP_JS_DIR / "map-highlights.js"
MAP_URL_PARAMETERS_JS = MAP_JS_DIR / "url-parameters.js"
MAP_POPUPS_JS = MAP_JS_DIR / "popups.js"
MAP_INITIALIZER_JS = MAP_JS_DIR / "initializer.js"


# ============================================================================
# Ładowanie skryptów
# ============================================================================


def test_mapa_html_loads_historical_points_module_after_map_script():
    """mapa.html musi załadować ``historical_points.js`` PO ``map-script.js``.

    Moduł polega na ``window.MapV2`` i ``maplibregl`` zdefiniowanych wcześniej.
    """
    html = MAPA_HTML.read_text(encoding="utf-8")
    map_idx = html.find('src="js/map-script.js"')
    hp_idx = html.find('src="js/historical_points.js"')
    assert map_idx != -1, "Brak ładowania js/map-script.js w mapa.html"
    assert hp_idx != -1, "Brak ładowania js/historical_points.js w mapa.html"
    assert hp_idx > map_idx, (
        "historical_points.js musi być ładowany PO map-script.js "
        "(korzysta z window.MapV2 i maplibregl)"
    )


def test_mapa_html_loads_panel_legend_before_panels():
    """panel-legend.js musi ładować się przed panels.js."""
    html = MAPA_HTML.read_text(encoding="utf-8")
    legend_idx = html.find('src="js/panel/panel-legend.js"')
    panels_idx = html.find('src="js/panels.js"')
    assert legend_idx != -1, "Brak ładowania js/panel/panel-legend.js w mapa.html"
    assert panels_idx != -1, "Brak ładowania js/panels.js w mapa.html"
    assert legend_idx < panels_idx, "js/panel/panel-legend.js musi być przed js/panels.js"


def test_mapa_html_loads_panel_layout_before_panels():
    """panel-layout.js musi ładować się przed panels.js."""
    html = MAPA_HTML.read_text(encoding="utf-8")
    layout_idx = html.find('src="js/panel/panel-layout.js"')
    panels_idx = html.find('src="js/panels.js"')
    assert layout_idx != -1, "Brak ładowania js/panel/panel-layout.js w mapa.html"
    assert panels_idx != -1, "Brak ładowania js/panels.js w mapa.html"
    assert layout_idx < panels_idx, "js/panel/panel-layout.js musi być przed js/panels.js"


def test_mapa_html_loads_panel_feature_modules_before_panels():
    """Moduły paneli muszą ładować się przed panels.js."""
    html = MAPA_HTML.read_text(encoding="utf-8")
    panels_idx = html.find('src="js/panels.js"')
    assert panels_idx != -1, "Brak ładowania js/panels.js w mapa.html"
    for script in (
        'src="js/panel/panel-owners.js"',
        'src="js/panel/panel-parcels.js"',
        'src="js/panel/panel-search.js"',
    ):
        idx = html.find(script)
        assert idx != -1, f"Brak ładowania {script} w mapa.html"
        assert idx < panels_idx, f"{script} musi być przed js/panels.js"


def test_mapa_html_loads_map_js_modules_before_map_script():
    """Moduły ``js/`` muszą ładować się przed ``map-script.js``."""
    html = MAPA_HTML.read_text(encoding="utf-8")
    map_idx = html.find('src="js/map-script.js"')
    assert map_idx != -1
    for script in (
        'src="js/constants.js"',
        'src="js/utils.js"',
        'src="js/geometry.js"',
        'src="js/ownership.js"',
        'src="js/layer-controls.js"',
        'src="js/layers.js"',
        'src="js/initializer.js"',
        'src="js/highlight-markers.js"',
        'src="js/map-highlights.js"',
        'src="js/popups.js"',
        'src="js/interactions.js"',
        'src="js/url-parameters.js"',
    ):
        idx = html.find(script)
        assert idx != -1, f"Brak ładowania {script} w mapa.html"
        assert idx < map_idx, f"{script} musi być przed map-script.js"


def test_map_core_helper_modules_register_namespaces():
    modules = (
        (MAP_CONSTANTS_JS, "window.MapConstants", ("PARCEL_COLORS", "PARCEL_FILL_OPACITY", "HIGHLIGHT_PALETTE")),
        (MAP_UTILS_JS, "window.MapUtils", ("parseMaybeJson", "uniqueOwners", "escapeHtml")),
        (MAP_GEOMETRY_JS, "window.MapGeometry", ("featureBBox", "featureCenter")),
        (MAP_OWNERSHIP_JS, "window.MapOwnership", ("isRealOwnershipType", "findMatchingOwner")),
        (MAP_LAYER_CONTROLS_JS, "window.MapLayerControls", ("create", "setMapLayerVisibility", "setPointsExclusion")),
        (MAP_LAYERS_JS, "window.MapLayers", ("splitFeatures", "addCoreSources", "addCoreLayers")),
        (MAP_INITIALIZER_JS, "window.MapInitializer", ("create", "initializeMap", "loadPointIcons", "setupHistoricalOpacityControl")),
        (MAP_HIGHLIGHT_MARKERS_JS, "window.MapHighlightMarkers", ("create", "showHighlightTooltip", "hideHighlightTooltip", "addLpMarker", "clearLpMarkers")),
        (MAP_HIGHLIGHTS_JS, "window.MapHighlights", ("create", "highlightFeatures", "clearTemporaryHighlight", "clearAllHighlights", "setOwnerHoverHighlight", "setHoverFeature", "markSingleFeature")),
        (MAP_POPUPS_JS, "window.MapPopups", ("create", "handleObjectClick", "showOwnerSelectionPopup", "buildFeaturePopupHtml")),
        (MAP_INTERACTIONS_JS, "window.MapInteractions", ("create", "setupHoverInteractions", "setupClickInteractions")),
        (MAP_URL_PARAMETERS_JS, "window.MapUrlParameters", ("create", "handleUrlParameters", "showHouseByOwnerKey")),
        (PANEL_LEGEND_JS, "window.PanelLegend", ("create", "setupLegend", "createBaseLayerControls", "createMapLayerControls", "createLegendItem")),
        (PANEL_LAYOUT_JS, "window.PanelLayout", ("create", "setupPanelToggles", "setupToolbarActions", "setupClearHighlightButton")),
        (PANEL_OWNERS_JS, "window.PanelOwners", ("create", "setupOwnerPanel", "createOwnerCard", "setupOwnerCardEvents")),
        (PANEL_PARCELS_JS, "window.PanelParcels", ("create", "setupParcelPanel", "createParcelItem", "renderSpecialObjects")),
        (PANEL_SEARCH_JS, "window.PanelSearch", ("create", "setupUniversalSearch", "setupMobileSearch", "performSearch")),
    )
    for path, namespace, tokens in modules:
        assert path.exists(), f"Brak modułu {path}"
        source = path.read_text(encoding="utf-8")
        assert namespace in source
        assert "Object.freeze" in source
        assert "'use strict'" in source or '"use strict"' in source
        for token in tokens:
            assert token in source


def test_map_script_uses_map_core_helper_modules():
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    for token in (
        "window.MapConstants",
        "window.MapUtils",
        "window.MapGeometry",
        "window.MapOwnership",
        "window.MapLayerControls",
        "window.MapLayers",
        "window.MapInitializer",
        "window.MapHighlightMarkers",
        "window.MapHighlights",
        "window.MapPopups",
        "window.MapInteractions",
        "window.MapUrlParameters",
        "const PARCEL_COLORS = MAP_CONSTANTS.PARCEL_COLORS",
        "const featureBBox = MAP_GEOMETRY.featureBBox",
        "const parseMaybeJson = MAP_UTILS.parseMaybeJson",
        "const isRealOwnershipType = MAP_OWNERSHIP.isRealOwnershipType",
        "const layerControls = window.MapLayerControls.create",
        "const mapInitializer = window.MapInitializer.create",
        "const highlightMarkers = window.MapHighlightMarkers.create",
        "const mapHighlights = window.MapHighlights.create",
        "const mapPopups = window.MapPopups.create",
        "const mapInteractions = window.MapInteractions.create",
        "const urlParameters = window.MapUrlParameters.create",
    ):
        assert token in source


def test_map_script_delegates_interactions_to_module():
    """map-script.js zostawia orkiestrację, a hover/click są w MapInteractions."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    assert "mapInteractions.setupHoverInteractions" in source
    assert "mapInteractions.setupClickInteractions" in source
    assert "function setupHoverInteractionsV2" not in source
    assert "function setupClickInteractionsV2" not in source


def test_map_script_delegates_initializer_to_module():
    """Tworzenie MapLibre, ikony punktów i opacity są w MapInitializer."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    assert "mapInitializer.initializeMap" in source
    assert "mapInitializer.loadPointIcons" in source
    assert "function initializeMapV2" not in source
    assert "function loadPointIcons" not in source
    assert "function setupHistoricalOpacityControl" not in source


def test_initializer_module_keeps_maplibre_base_layers_contract():
    """Initializer zachowuje bazowe źródła/warstwy MapLibre i historyczny raster."""
    source = MAP_INITIALIZER_JS.read_text(encoding="utf-8")
    for token in (
        "new maplibregl.Map",
        "satellite-layer",
        "osm-layer",
        "historical-layer",
        "raster-opacity",
        "NavigationControl",
        "AttributionControl",
        "mouse-coordinates",
        "icon-budynek",
        "icon-kapliczka",
        "icon-obiekt-specjalny",
    ):
        assert token in source


def test_map_script_delegates_highlight_markers_to_module():
    """Tooltipy i plakietki Lp. są w MapHighlightMarkers, nie w map-script.js."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    assert "highlightMarkers.showHighlightTooltip" in source
    assert "highlightMarkers.hideHighlightTooltip" in source
    assert "highlightMarkers.addLpMarker" in source
    assert "highlightMarkers.clearLpMarkers" in source
    for function_name in (
        "getHighlightTooltip",
        "showHighlightTooltip",
        "hideHighlightTooltip",
        "addLpMarker",
        "clearLpMarkers",
    ):
        assert f"function {function_name}" not in source


def test_map_script_delegates_highlights_to_module():
    """Logika highlightów jest w MapHighlights, a map-script.js tylko ją podpina."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    module_source = MAP_HIGHLIGHTS_JS.read_text(encoding="utf-8")
    assert "window.MapHighlights.create" in source
    assert "mapHighlights.highlightFeatures" in source
    assert "mapHighlights.getHighlightInfo" in source
    for function_name in (
        "highlightFeatures",
        "clearTemporaryHighlight",
        "clearAllHighlights",
        "setOwnerHoverHighlight",
        "setHoverFeature",
        "markSingleFeature",
    ):
        assert f"function {function_name}" not in source
        assert f"function {function_name}" in module_source


def test_map_highlights_module_integrates_marker_and_cleanup_dependencies():
    """MapHighlights zarządza stanem highlightów i woła zależności markerów/czyszczenia."""
    source = MAP_HIGHLIGHTS_JS.read_text(encoding="utf-8")
    for token in (
        "highlightFeatureIds",
        "highlightColor",
        "ownerHoverIds",
        "temporaryHighlightIds",
        "hoveredFromPanelId",
        "highlightOwnerInfo",
        "addLpMarker",
        "clearLpMarkers",
        "hideHighlightTooltip",
        "clearOwnerColored",
        "clearFocusMode",
    ):
        assert token in source


def test_map_script_delegates_url_parameters_to_module():
    """Parametry URL są w MapUrlParameters, a map-script.js tylko orkiestruje."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    assert "urlParameters.handleUrlParameters" in source
    assert "function handleUrlParametersV2" not in source
    assert "function showHouseByOwnerKey" not in source


def test_url_parameters_module_supports_existing_query_contracts():
    """Moduł URL zachowuje dotychczasowe parametry linków z paneli/statystyk."""
    source = MAP_URL_PARAMETERS_JS.read_text(encoding="utf-8")
    for token in (
        "highlightByIds",
        "highlightTopOwners",
        "highlightParcels",
        "highlightParcel",
        "highlightRivers",
        "highlightRoads",
        "findHouseNumber",
        "ownerKey",
        "show",
        "house",
        "/api/wlasciciel/",
    ):
        assert token in source


def test_map_script_delegates_popups_to_module():
    """Popupy działek i wyboru protokołu są w MapPopups."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    assert "mapPopups.handleObjectClick" in source
    assert "mapPopups.showOwnerSelectionPopup" in source
    for function_name in (
        "handleObjectClick",
        "showOwnerSelectionPopup",
        "buildFeaturePopupHtml",
    ):
        assert f"function {function_name}" not in source


def test_popups_module_preserves_protocol_links_contract():
    """Popupy nadal linkują do protokołów właścicieli i używają klas CSS popupu."""
    source = MAP_POPUPS_JS.read_text(encoding="utf-8")
    for token in (
        "protocol-link-in-popup",
        "../wlasciciele/protokol.html?ownerId=",
        "map-popup",
        "map-popup-btn",
        "map-popup-lp",
    ):
        assert token in source


def test_map_script_exposes_map_api_with_map_v2_alias():
    """Nowe publiczne API to ``window.MapAPI``, a ``window.MapV2`` jest aliasem."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    assert "window.MapAPI" in source
    assert "Object.freeze" in source
    assert "window.MapV2 = window.MapAPI" in source


def test_historical_points_module_exposes_namespace():
    """Moduł rejestruje ``window.HistoricalPoints`` jako Object.freeze."""
    source = HISTORICAL_POINTS_JS.read_text(encoding="utf-8")
    assert "window.HistoricalPoints" in source
    assert "Object.freeze" in source, (
        "HistoricalPoints powinno być zamrożone (Object.freeze) - "
        "spójnie z wzorcem admin/js/*.js"
    )
    # Wymagane metody
    for method in ("init", "layerIds", "reload"):
        assert re.search(rf"\b{method}\s*:", source) or re.search(
            rf"\b{method}\s*\(", source
        ), f"Brak metody {method!r} w module"


def test_historical_points_module_handles_missing_maplibre_gracefully():
    """Moduł nie powinien crashować gdy brak window.MapV2 (lazy init)."""
    source = HISTORICAL_POINTS_JS.read_text(encoding="utf-8")
    assert "console.warn" in source, "Moduł powinien logować ostrzeżenie przy braku MapV2"


# ============================================================================
# map-script.js - rozszerzenia API
# ============================================================================


def test_map_script_exposes_get_map_for_modules():
    """``window.MapV2.getMap`` - getter instancji mapy dla modułów."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    assert "getMap" in source, "Brak getMap w map-script.js"


def test_map_script_exposes_geojson_helpers():
    """``window.MapV2.addGeojsonSource`` + ``addGeojsonLayer`` dla modułów."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    for helper in ("addGeojsonSource", "addGeojsonLayer"):
        assert helper in source, f"Brak {helper} w map-script.js"


def test_map_script_handles_historical_points_visibility_group():
    """``setMapLayerVisibility`` obsługuje grupę 'historical-points'."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    # Szukamy w ciele funkcji setMapLayerVisibility
    match = re.search(
        r"function\s+setMapLayerVisibility\s*\([^)]*\)\s*\{(.*?)\n\}",
        source,
        re.S,
    )
    assert match, "Nie znaleziono funkcji setMapLayerVisibility"
    body = match.group(1)
    assert "'historical-points'" in body, (
        "setMapLayerVisibility musi obsługiwać grupę 'historical-points'"
    )
    # Sprawdzamy że używa HistoricalPoints.layerIds (nie hardkodowanej listy)
    assert "HistoricalPoints" in body, (
        "setMapLayerVisibility powinien delegować do HistoricalPoints.layerIds()"
    )


# ============================================================================
# panels.js - checkbox w legendzie
# ============================================================================


def test_panels_has_historical_points_checkbox():
    """panel-legend.js tworzy checkbox data-group="historical-points"."""
    source = PANEL_LEGEND_JS.read_text(encoding="utf-8")
    assert 'data-group="historical-points"' in source, (
        "Brak checkboxa z data-group='historical-points' w panel-legend.js"
    )


def test_panels_historical_points_checkbox_wires_to_map_v2():
    """Checkbox wywołuje ``window.MapV2.setMapLayerVisibility``."""
    source = PANEL_LEGEND_JS.read_text(encoding="utf-8")
    # Generyczny handler: w tej samej linii muszą być setMapLayerVisibility
    # i cb.dataset.group (w dowolnej kolejności).
    matches = re.findall(
        r"setMapLayerVisibility\s*\([^)]*cb\.dataset\.group",
        source,
    )
    assert matches, (
        "Handler checkboxów musi wywoływać setMapLayerVisibility(cb.dataset.group, ...)"
    )


def test_panels_delegates_legend_to_panel_legend_module():
    """panels.js używa PanelLegend i nie trzyma już funkcji legendy."""
    source = PANELS_JS.read_text(encoding="utf-8")
    assert "window.PanelLegend.create" in source
    assert "panelLegend.setupLegend" in source
    for function_name in (
        "setupLegend",
        "createBaseLayerControls",
        "createMapLayerControls",
        "createLegendItem",
    ):
        assert f"function {function_name}" not in source


def test_panels_delegates_layout_to_panel_layout_module():
    """panels.js używa PanelLayout i nie trzyma funkcji layout/toolbar."""
    source = PANELS_JS.read_text(encoding="utf-8")
    assert "window.PanelLayout.create" in source
    assert "panelLayout.setupPanelToggles" in source
    assert "panelLayout.setupToolbarActions" in source
    assert "panelLayout.setupClearHighlightButton" in source
    for function_name in (
        "setupPanelToggles",
        "setupToolbarActions",
        "setupClearHighlightButton",
    ):
        assert f"function {function_name}" not in source


def test_panels_delegates_feature_panels_to_modules():
    """panels.js jest orkiestratorem dla owner/parcel/search."""
    source = PANELS_JS.read_text(encoding="utf-8")
    for token in (
        "window.PanelOwners.create",
        "window.PanelParcels.create",
        "window.PanelSearch.create",
        "panelOwners.setupOwnerPanel",
        "panelParcels.setupParcelPanel",
        "panelSearch.setupUniversalSearch",
        "panelSearch.setupMobileSearch",
    ):
        assert token in source
    for function_name in (
        "setupOwnerPanel",
        "setupParcelPanel",
        "renderSpecialObjects",
        "performSearch",
        "setupUniversalSearch",
        "setupMobileSearch",
    ):
        assert f"function {function_name}" not in source


def test_panel_search_preserves_search_contracts():
    """PanelSearch zachowuje desktop/mobile search i focus na mapie."""
    source = PANEL_SEARCH_JS.read_text(encoding="utf-8")
    for token in (
        "universal-search",
        "universal-search-results",
        "mobile-search-trigger",
        "mobile-search-overlay",
        "mobile-universal-search",
        "mobile-search-results",
        "focusFeature",
        "owner-card",
    ):
        assert token in source


def test_panel_parcels_preserves_special_objects_contracts():
    """PanelParcels zachowuje listę działek i obiektów specjalnych."""
    source = PANEL_PARCELS_JS.read_text(encoding="utf-8")
    for token in (
        "parcelSearch",
        "dzialki_panel",
        "obiekty_panel",
        "parcel-category-filters",
        "special-tab",
        "kapliczka",
        "budynek",
        "obiekt_specjalny",
        "showOwnerSelectionPopup",
        "focusFeature",
    ):
        assert token in source


def test_panel_owners_preserves_compare_and_highlight_contracts():
    """PanelOwners zachowuje compare, sortowanie i highlighty właścicieli."""
    source = PANEL_OWNERS_JS.read_text(encoding="utf-8")
    for token in (
        "compareModeBtn",
        "selectedForCompare",
        "../wlasciciele/compare.html?owners=",
        "../wlasciciele/protokol.html?ownerId=",
        "highlightFeatures",
        "setOwnerHoverHighlight",
        "ownerSearch",
        "filter-btn",
    ):
        assert token in source


def test_panel_layout_preserves_toolbar_keyboard_contracts():
    """PanelLayout zachowuje reset, motyw, modale i skróty klawiaturowe."""
    source = PANEL_LAYOUT_JS.read_text(encoding="utf-8")
    for token in (
        "help-btn",
        "settings-btn",
        "theme-toggle",
        "reset-view-btn",
        "mapTheme",
        "clearAllHighlights",
        "invalidateSize",
        "fitToAll",
        "zoomIn",
        "zoomOut",
        "Escape",
        "universal-search",
        "panel-expand-handle",
    ):
        assert token in source


# ============================================================================
# map-script.js - deduplikacja popupu + ukrywanie w warstwie points
# ============================================================================


def test_map_script_has_only_one_points_click_handler():
    """Klik na punkty: TYLKO ``points-circle-fallback`` ma handler.

    Wcześniej obie warstwy (``points-icons`` i ``points-circle-fallback``) miały
    click handler - dla tego samego punktu odpalały się dwa popupy. Fix: ikona
    jest wizualną nakładką, klik łapie fallback (zawsze renderowany).
    """
    source = MAP_INTERACTIONS_JS.read_text(encoding="utf-8")
    # Zliczamy ``map.on('click', 'points-...'`` (oba warianty)
    icons_clicks = re.findall(r"map\.on\(\s*'click'\s*,\s*'points-icons'\s*,", source)
    fallback_clicks = re.findall(
        r"map\.on\(\s*'click'\s*,\s*'points-circle-fallback'\s*,", source
    )
    assert len(icons_clicks) == 0, (
        "points-icons NIE powinien mieć click handlera (podwójny popup). "
        f"Znaleziono {len(icons_clicks)}."
    )
    assert len(fallback_clicks) == 1, (
        "points-circle-fallback powinien mieć DOKŁADNIE 1 click handler. "
        f"Znaleziono {len(fallback_clicks)}."
    )


def test_map_script_exposes_set_points_exclusion():
    """``window.MapAPI.setPointsExclusion`` - filtr warstw points."""
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    assert "setPointsExclusion" in source, (
        "Brak setPointsExclusion w map-script.js - moduł historical_points "
        "nie może ukryć obiektów w warstwie points"
    )
    # Funkcja musi być eksportowana w window.MapAPI.
    # ``window.MapAPI = Object.freeze({ ... })`` może mieć wiele linii, więc bierzemy
    # kawałek od ``window.MapAPI = Object.freeze({`` do następnego ``}`` na tym samym
    # poziomie indentacji (nie zagnieżdżonego w funkcji).
    match = re.search(
        r"window\.MapAPI\s*=\s*Object\.freeze\s*\(\s*\{",
        source,
    )
    assert match, "Nie znaleziono 'window.MapAPI = Object.freeze({' w map-script.js"
    after = source[match.end():]
    # Szukamy ``}`` zamykającego obiekt na zerowym poziomie zagnieżdżenia.
    depth = 1
    i = 0
    while i < len(after) and depth > 0:
        ch = after[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    obj_body = after[:i]
    assert "setPointsExclusion" in obj_body, (
        "setPointsExclusion musi być w window.MapAPI (jako property obiektu)"
    )


def test_map_script_set_points_exclusion_uses_numer_obiektu():
    """Filtr ``setPointsExclusion`` porównuje po ``numer_obiektu``.

    To pole wspólne z ``object_name`` w odpowiedzi ``/api/historical-points``.
    """
    source = MAP_SCRIPT_JS.read_text(encoding="utf-8")
    match = re.search(
        r"function\s+setPointsExclusion\s*\([^)]*\)\s*\{(.*?)\n\}",
        source,
        re.S,
    )
    assert match, "Nie znaleziono funkcji setPointsExclusion"
    body = match.group(1)
    assert "'numer_obiektu'" in body, (
        "setPointsExclusion musi filtrować po 'numer_obiektu'"
    )


def test_historical_points_module_calls_set_points_exclusion():
    """``historical_points.js`` wywołuje ``setPointsExclusion`` po pobraniu danych."""
    source = HISTORICAL_POINTS_JS.read_text(encoding="utf-8")
    assert "setPointsExclusion" in source, (
        "historical_points.js musi wywołać setPointsExclusion "
        "żeby ukryć obiekty w generycznej warstwie points"
    )


def test_historical_points_module_handles_stringified_photos():
    """Popup obsługuje ``photos`` jako zserializowany string (kwir MapLibre).

    MapLibre trzyma złożone typy w ``properties`` jako JSON-string. ``buildPopupHtml``
    musi rozumieć oba warianty (array + string) - inaczej zdjęcia nie wyświetlają się.
    """
    source = HISTORICAL_POINTS_JS.read_text(encoding="utf-8")
    # Wyciągamy ciało buildPopupHtml
    match = re.search(
        r"function\s+buildPopupHtml\s*\([^)]*\)\s*\{(.*?)\n\s{4}\}",
        source,
        re.S,
    )
    assert match, "Nie znaleziono funkcji buildPopupHtml"
    body = match.group(1)
    # Musi być logika parsowania stringa
    assert "JSON.parse" in body, (
        "buildPopupHtml musi używać JSON.parse dla photos "
        "(MapLibre przechowuje złożone typy jako stringi)"
    )
    # Musi akceptować zarówno array jak i string
    assert "Array.isArray" in body, (
        "buildPopupHtml musi walidować typ photos (Array.isArray)"
    )


# ============================================================================
# CSS - widoczność zdjęć w popupie
# ============================================================================


def test_style_css_has_hp_popup_image_max_width():
    """CSS wymusza ``max-width: 100%`` na zdjęciach popupu historycznego.

    Bez tego obrazki w naturalnym rozmiarze (>360px) przepełniają popup.
    """
    css = (PROJECT_ROOT / "static" / "mapa" / "style.css").read_text(encoding="utf-8")
    assert ".hp-popup-photo" in css, "Brak reguły .hp-popup-photo w style.css"
    # max-width:100% musi dotyczyć ``img`` wewnątrz figure
    assert re.search(
        r"\.hp-popup-photo\s+img\s*\{[^}]*max-width\s*:\s*100%",
        css,
        re.S,
    ), "Brak 'max-width: 100%' dla .hp-popup-photo img w style.css"


def test_style_css_has_hp_popup_max_height_overflow():
    """CSS ogranicza wysokość popupu historycznego i dodaje scroll."""
    css = (PROJECT_ROOT / "static" / "mapa" / "style.css").read_text(encoding="utf-8")
    assert ".hp-popup" in css, "Brak reguły .hp-popup w style.css"
    match = re.search(r"\.hp-popup\s*\{(.*?)\}", css, re.S)
    assert match, "Nie znaleziono bloku .hp-popup { ... }"
    body = match.group(1)
    assert "max-height" in body, "Brak max-height w .hp-popup"
    assert "overflow" in body and "auto" in body, (
        "Brak 'overflow: auto' w .hp-popup (długie opisy ucinają zdjęcia)"
    )


# ============================================================================
# Endpoint z perspektywy frontendu - nie zwraca HTML fallback
# ============================================================================


def test_historical_points_endpoint_not_html_fallback(client):
    """Endpoint /api/historical-points zwraca JSON, nie HTML.

    Analogia do kontraktu admin: response.json() musi działać na froncie.
    """
    resp = client.get("/api/historical-points")
    content_type = resp.headers.get("content-type", "")
    body_start = resp.text[:80].lstrip().lower()
    assert not (
        "text/html" in content_type or body_start.startswith("<!doctype")
    ), (
        f"Endpoint /api/historical-points zwrócił HTML fallback: "
        f"status={resp.status_code}, content-type={content_type}, "
        f"body={resp.text[:120]!r}"
    )
    # Musi być parsowalnym JSON-em
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert isinstance(body["features"], list)


def test_historical_points_module_uses_point_photos_url():
    """``historical_points.js`` serwuje zdjęcia markerów z URL ``/point_photos/``.

    Po refaktorze (Priorytet 3.1) zdjęcia markerów są w osobnym folderze
    ``point_photos/`` - frontend musi używać nowego URL.
    """
    source = HISTORICAL_POINTS_JS.read_text(encoding="utf-8")
    assert "/point_photos/" in source, (
        "historical_points.js musi używać URL /point_photos/ "
        "(zdjęcia markerów w osobnym folderze)"
    )
    # Anty-regresja: nie wracamy do /history_photos/ w markerach
    assert "/history_photos/" not in source, (
        "historical_points.js NIE powinien używać /history_photos/ "
        "(to jest folder galerii, nie markerów)"
    )
