// Legend — Task 6
import L from 'leaflet';
import type { ColourScale } from './colourScale';

export interface Legend {
  render(scale: ColourScale): L.Control;
}

export function createLegend(): Legend {
  function render(scale: ColourScale): L.Control {
    const control = new L.Control({ position: 'bottomright' });

    control.onAdd = () => {
      const container = L.DomUtil.create('div', 'legend');

      const title = L.DomUtil.create('div', 'legend__title', container);
      title.textContent = 'Liveability Score';

      scale.stops.forEach((stop, i) => {
        const next = scale.stops[i + 1];
        const label = next
          ? `${stop.value.toFixed(1)} – ${next.value.toFixed(1)}`
          : `${stop.value.toFixed(1)}+`;

        const row = L.DomUtil.create('div', 'legend__row', container);

        const swatch = L.DomUtil.create('span', 'legend__swatch', row);
        swatch.style.background = stop.colour;

        const text = L.DomUtil.create('span', 'legend__label', row);
        text.textContent = label;
      });

      return container;
    };

    return control;
  }

  return { render };
}
