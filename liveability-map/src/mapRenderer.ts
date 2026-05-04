import L from 'leaflet';
import type { MeshblockFeature, MeshblockProperties } from './dataLoader';
import type { ColourScale } from './colourScale';
import { createLegend } from './legend';

const SELECTED_STYLE: L.PathOptions = {
  weight: 3,
  color: '#e040fb',
  opacity: 1,
  fillOpacity: 0.9,
};

export interface MapRenderer {
  init(containerId: string): void;
  renderChoropleth(features: MeshblockFeature[], scale: ColourScale): void;
  onMeshblockClick(handler: (props: MeshblockProperties) => void): void;
  onMapClick(handler: () => void): void;
  clearSelection(): void;
}

export function createMapRenderer(): MapRenderer {
  let map: L.Map | null = null;
  let meshblockClickHandler: ((props: MeshblockProperties) => void) | null = null;
  let mapClickHandler: (() => void) | null = null;
  let selectedLayer: L.Path | null = null;
  let selectedOriginalStyle: L.PathOptions | null = null;

  function init(containerId: string): void {
    map = L.map(containerId);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);

    // Map background click → dismiss handler (Req 2.4)
    map.on('click', () => {
      mapClickHandler?.();
    });
  }

  function renderChoropleth(features: MeshblockFeature[], scale: ColourScale): void {
    if (!map) throw new Error('MapRenderer.init() must be called before renderChoropleth()');

    const geoJsonLayer = L.geoJSON(features, {
      style: (feature) => {
        const score = (feature as MeshblockFeature).properties.liveability_score;
        return {
          fillColor: scale.getColour(score),
          fillOpacity: 0.75,
          color: '#555',
          weight: 0.5,
          opacity: 1,
        };
      },
      onEachFeature: (feature, layer) => {
        layer.on('click', (e: L.LeafletMouseEvent) => {
          // Stop propagation so the map background click doesn't also fire (Req 2.1, 2.4)
          L.DomEvent.stopPropagation(e);

          // Clear previous selection
          clearSelection();

          // Highlight the clicked polygon
          const pathLayer = layer as L.Path;
          selectedOriginalStyle = {
            weight: (pathLayer.options as L.PathOptions).weight,
            color: (pathLayer.options as L.PathOptions).color,
            opacity: (pathLayer.options as L.PathOptions).opacity,
            fillOpacity: (pathLayer.options as L.PathOptions).fillOpacity,
          };
          selectedLayer = pathLayer;
          pathLayer.setStyle(SELECTED_STYLE);
          pathLayer.bringToFront();

          meshblockClickHandler?.((feature as MeshblockFeature).properties);
        });
      },
    });

    geoJsonLayer.addTo(map);

    // Add legend to bottom-right corner (Req 1.2)
    // Ensure a legend container exists in the DOM
    let legendEl = document.getElementById('legend');
    if (!legendEl) {
      legendEl = document.createElement('div');
      legendEl.id = 'legend';
      document.body.appendChild(legendEl);
    }
    createLegend('legend').render(scale, 'Liveability Score');

    // Fit map to the extent of the loaded data (Req 1.5)
    const bounds = geoJsonLayer.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds);
    }
  }

  function onMeshblockClick(handler: (props: MeshblockProperties) => void): void {
    meshblockClickHandler = handler;
  }

  function onMapClick(handler: () => void): void {
    mapClickHandler = handler;
  }

  function clearSelection(): void {
    if (selectedLayer && selectedOriginalStyle) {
      selectedLayer.setStyle(selectedOriginalStyle);
      selectedLayer = null;
      selectedOriginalStyle = null;
    }
  }

  return { init, renderChoropleth, onMeshblockClick, onMapClick, clearSelection };
}
