import L from 'leaflet';
import type { MeshblockFeature, MeshblockProperties } from './dataLoader';
import type { ColourScale } from './colourScale';
import { createLegend } from './legend';

export interface MapRenderer {
  init(containerId: string): void;
  renderChoropleth(features: MeshblockFeature[], scale: ColourScale): void;
  onMeshblockClick(handler: (props: MeshblockProperties) => void): void;
  onMapClick(handler: () => void): void;
}

export function createMapRenderer(): MapRenderer {
  let map: L.Map | null = null;
  let meshblockClickHandler: ((props: MeshblockProperties) => void) | null = null;
  let mapClickHandler: (() => void) | null = null;

  function init(containerId: string): void {
    map = L.map(containerId);

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
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
          meshblockClickHandler?.((feature as MeshblockFeature).properties);
        });
      },
    });

    geoJsonLayer.addTo(map);

    // Add legend to bottom-right corner (Req 1.2)
    createLegend().render(scale).addTo(map);

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

  return { init, renderChoropleth, onMeshblockClick, onMapClick };
}
