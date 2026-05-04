// ComparisonMap — Task 10.1
// Requirements: 5.1, 5.2, 5.3, 5.4, 9.3

import L from 'leaflet';
import type { ScenarioFeature } from './scenarioDataLoader';
import type { ColourScale } from './colourScale';

export interface MapPane {
  init(containerId: string): void;
  renderChoropleth(
    features: ScenarioFeature[],
    indicator: string,
    scenario: string,
    scale: ColourScale,
  ): void;
  fitBounds(bounds: L.LatLngBoundsExpression): void;
  getMap(): L.Map;
  onFeatureClick(handler: (feature: ScenarioFeature) => void): void;
  onBackgroundClick(handler: () => void): void;
  onFeatureHover(handler: (mbCode: number | null) => void): void;
  clearSelection(): void;
  /** Select a polygon by mb_code (click highlight). */
  selectByMbCode(mbCode: number): void;
  /** Highlight a polygon by mb_code (hover effect). Pass null to clear. */
  setHover(mbCode: number | null): void;
}

export interface ComparisonMap {
  init(leftContainerId: string, rightContainerId: string): void;
  renderLeft(
    features: ScenarioFeature[],
    indicator: string,
    scenario: string,
    scale: ColourScale,
  ): void;
  renderRight(
    features: ScenarioFeature[],
    indicator: string,
    scenario: string,
    scale: ColourScale,
  ): void;
  fitToData(features: ScenarioFeature[]): void;
  onFeatureClick(
    handler: (feature: ScenarioFeature, pane: 'left' | 'right') => void,
  ): void;
  onBackgroundClick(handler: () => void): void;
  clearSelection(): void;
}

const MISSING_COLOUR = '#cccccc';

const SELECTED_STYLE: L.PathOptions = {
  weight: 3,
  color: '#e040fb',
  opacity: 1,
  fillOpacity: 0.9,
};

const HOVER_STYLE: L.PathOptions = {
  weight: 2,
  color: '#333',
  opacity: 1,
};

export function createMapPane(): MapPane {
  let map: L.Map | null = null;
  let geoJsonLayer: L.GeoJSON | null = null;
  let featureClickHandler: ((feature: ScenarioFeature) => void) | null = null;
  let backgroundClickHandler: (() => void) | null = null;
  let featureHoverHandler: ((mbCode: number | null) => void) | null = null;
  let selectedLayer: L.Path | null = null;
  let selectedOriginalStyle: L.PathOptions | null = null;
  let hoveredLayer: L.Path | null = null;
  let hoveredOriginalStyle: L.PathOptions | null = null;
  let _hoverDirty = false;
  /** Map from mb_code → Leaflet layer for hover lookup */
  const layersByMbCode = new Map<number, L.Path>();

  function init(containerId: string): void {
    map = L.map(containerId);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);

    map.on('click', () => {
      backgroundClickHandler?.();
    });

    // Clear stale hover when the cursor moves over the map but not over a polygon
    map.on('mousemove', () => {
      if (_hoverDirty) {
        _hoverDirty = false;
        featureHoverHandler?.(null);
      }
    });
  }

  function renderChoropleth(
    features: ScenarioFeature[],
    indicator: string,
    scenario: string,
    scale: ColourScale,
  ): void {
    if (!map) {
      throw new Error('MapPane.init() must be called before renderChoropleth()');
    }

    // Clear any existing GeoJSON layer before adding a new one
    if (geoJsonLayer) {
      map.removeLayer(geoJsonLayer);
      geoJsonLayer = null;
    }
    layersByMbCode.clear();
    selectedLayer = null;
    selectedOriginalStyle = null;
    hoveredLayer = null;
    hoveredOriginalStyle = null;

    const propertyKey = `${indicator}_${scenario}`;

    geoJsonLayer = L.geoJSON(features, {
      style: (feature) => {
        const props = (feature as ScenarioFeature).properties;
        const value = props[propertyKey];

        const fillColor =
          value == null || typeof value !== 'number'
            ? MISSING_COLOUR
            : scale.getColour(value);

        return {
          fillColor,
          fillOpacity: 0.75,
          color: '#555',
          weight: 0.5,
          opacity: 1,
        };
      },
      onEachFeature: (feature, layer) => {
        const mbCode = (feature as ScenarioFeature).properties.mb_code;
        if (mbCode != null) {
          layersByMbCode.set(mbCode, layer as L.Path);
        }

        layer.on('click', (e: L.LeafletMouseEvent) => {
          L.DomEvent.stopPropagation(e);
          featureClickHandler?.(feature as ScenarioFeature);
        });

        layer.on('mouseover', () => {
          _hoverDirty = false;
          featureHoverHandler?.(mbCode);
        });

        layer.on('mouseout', () => {
          // Mark dirty — the map-level mousemove will clear hover
          // if the cursor isn't immediately over another polygon
          _hoverDirty = true;
        });
      },
    });

    geoJsonLayer.addTo(map);
  }

  function fitBounds(bounds: L.LatLngBoundsExpression): void {
    if (!map) {
      throw new Error('MapPane.init() must be called before fitBounds()');
    }
    map.fitBounds(bounds);
  }

  function getMap(): L.Map {
    if (!map) {
      throw new Error('MapPane.init() must be called before getMap()');
    }
    return map;
  }

  function onFeatureClick(
    handler: (feature: ScenarioFeature) => void,
  ): void {
    featureClickHandler = handler;
  }

  function onBackgroundClick(handler: () => void): void {
    backgroundClickHandler = handler;
  }

  function onFeatureHover(handler: (mbCode: number | null) => void): void {
    featureHoverHandler = handler;
  }

  function clearSelection(): void {
    if (selectedLayer && selectedOriginalStyle) {
      selectedLayer.setStyle(selectedOriginalStyle);
      selectedLayer = null;
      selectedOriginalStyle = null;
    }
  }

  function selectByMbCode(mbCode: number): void {
    const layer = layersByMbCode.get(mbCode);
    if (!layer) return;

    // Clear any hover on this layer first
    if (hoveredLayer === layer && hoveredOriginalStyle) {
      hoveredLayer.setStyle(hoveredOriginalStyle);
      hoveredLayer = null;
      hoveredOriginalStyle = null;
    }

    selectedOriginalStyle = {
      weight: (layer.options as L.PathOptions).weight,
      color: (layer.options as L.PathOptions).color,
      opacity: (layer.options as L.PathOptions).opacity,
      fillOpacity: (layer.options as L.PathOptions).fillOpacity,
    };
    selectedLayer = layer;
    layer.setStyle(SELECTED_STYLE);
    layer.bringToFront();
  }

  function setHover(mbCode: number | null): void {
    // Clear previous hover (unless it's the selected layer — don't touch that)
    if (hoveredLayer && hoveredLayer !== selectedLayer && hoveredOriginalStyle) {
      hoveredLayer.setStyle(hoveredOriginalStyle);
    }
    hoveredLayer = null;
    hoveredOriginalStyle = null;

    if (mbCode == null) return;

    const layer = layersByMbCode.get(mbCode);
    if (!layer || layer === selectedLayer) return;

    hoveredOriginalStyle = {
      weight: (layer.options as L.PathOptions).weight,
      color: (layer.options as L.PathOptions).color,
      opacity: (layer.options as L.PathOptions).opacity,
    };
    hoveredLayer = layer;
    layer.setStyle(HOVER_STYLE);
    layer.bringToFront();

    // Keep selected layer on top if it exists
    if (selectedLayer) {
      selectedLayer.bringToFront();
    }
  }

  return { init, renderChoropleth, fitBounds, getMap, onFeatureClick, onBackgroundClick, onFeatureHover, clearSelection, selectByMbCode, setHover };
}

export function createComparisonMap(): ComparisonMap {
  const leftPane = createMapPane();
  const rightPane = createMapPane();
  let _syncing = false;

  let featureClickHandler:
    | ((feature: ScenarioFeature, pane: 'left' | 'right') => void)
    | null = null;
  let backgroundClickHandler: (() => void) | null = null;

  function syncMaps(source: L.Map, target: L.Map): void {
    if (_syncing) return;
    _syncing = true;
    target.setView(source.getCenter(), source.getZoom(), { animate: false });
    _syncing = false;
  }

  function init(leftContainerId: string, rightContainerId: string): void {
    leftPane.init(leftContainerId);
    rightPane.init(rightContainerId);

    const leftMap = leftPane.getMap();
    const rightMap = rightPane.getMap();

    // Wire sync: left → right
    leftMap.on('moveend', () => syncMaps(leftMap, rightMap));
    leftMap.on('zoomend', () => syncMaps(leftMap, rightMap));

    // Wire sync: right → left
    rightMap.on('moveend', () => syncMaps(rightMap, leftMap));
    rightMap.on('zoomend', () => syncMaps(rightMap, leftMap));

    // Wire feature click handlers for both panes — clear BOTH panes first, then select on clicked pane only
    leftPane.onFeatureClick((feature) => {
      clearSelection();
      const mbCode = feature.properties.mb_code;
      if (mbCode != null) leftPane.selectByMbCode(mbCode);
      featureClickHandler?.(feature, 'left');
    });
    rightPane.onFeatureClick((feature) => {
      clearSelection();
      const mbCode = feature.properties.mb_code;
      if (mbCode != null) rightPane.selectByMbCode(mbCode);
      featureClickHandler?.(feature, 'right');
    });

    // Wire hover handlers — sync hover across both panes
    leftPane.onFeatureHover((mbCode) => {
      leftPane.setHover(mbCode);
      rightPane.setHover(mbCode);
    });
    rightPane.onFeatureHover((mbCode) => {
      leftPane.setHover(mbCode);
      rightPane.setHover(mbCode);
    });

    // Wire background click handlers for both panes
    leftPane.onBackgroundClick(() => {
      backgroundClickHandler?.();
    });
    rightPane.onBackgroundClick(() => {
      backgroundClickHandler?.();
    });
  }

  function renderLeft(
    features: ScenarioFeature[],
    indicator: string,
    scenario: string,
    scale: ColourScale,
  ): void {
    leftPane.renderChoropleth(features, indicator, scenario, scale);
  }

  function renderRight(
    features: ScenarioFeature[],
    indicator: string,
    scenario: string,
    scale: ColourScale,
  ): void {
    rightPane.renderChoropleth(features, indicator, scenario, scale);
  }

  function fitToData(features: ScenarioFeature[]): void {
    const tempLayer = L.geoJSON(features);
    const bounds = tempLayer.getBounds();
    if (bounds.isValid()) {
      leftPane.fitBounds(bounds);
      rightPane.fitBounds(bounds);
    }
  }

  function onFeatureClick(
    handler: (feature: ScenarioFeature, pane: 'left' | 'right') => void,
  ): void {
    featureClickHandler = handler;
  }

  function onBackgroundClick(handler: () => void): void {
    backgroundClickHandler = handler;
  }

  function clearSelection(): void {
    leftPane.clearSelection();
    rightPane.clearSelection();
  }

  return {
    init,
    renderLeft,
    renderRight,
    fitToData,
    onFeatureClick,
    onBackgroundClick,
    clearSelection,
  };
}
