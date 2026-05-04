// Legend — Task 11.1
// Requirements: 7.1, 7.2, 7.3, 7.4
import type { ColourScale } from './colourScale';

export interface Legend {
  /** Create the legend DOM inside the target container with the given scale and title. */
  render(scale: ColourScale, title: string): void;
  /** Replace the legend content with a new scale and title without recreating the container. */
  update(scale: ColourScale, title: string): void;
}

/**
 * Build the inner HTML content for the legend: a title and colour-stop rows.
 */
function buildLegendContent(container: HTMLElement, scale: ColourScale, title: string): void {
  // Clear existing content
  container.innerHTML = '';

  const titleEl = document.createElement('div');
  titleEl.className = 'legend__title';
  titleEl.textContent = title;
  container.appendChild(titleEl);

  scale.stops.forEach((stop, i) => {
    const next = scale.stops[i + 1];
    const label = next
      ? `${stop.value.toFixed(1)} – ${next.value.toFixed(1)}`
      : `${stop.value.toFixed(1)}+`;

    const row = document.createElement('div');
    row.className = 'legend__row';

    const swatch = document.createElement('span');
    swatch.className = 'legend__swatch';
    swatch.style.background = stop.colour;
    row.appendChild(swatch);

    const text = document.createElement('span');
    text.className = 'legend__label';
    text.textContent = label;
    row.appendChild(text);

    container.appendChild(row);
  });
}

/**
 * Create a Legend that renders into a fixed DOM element (shared between both map panes).
 *
 * @param elementId - The id of the DOM element to render the legend into.
 *                    The element must already exist in the page.
 */
export function createLegend(elementId: string): Legend {
  let container: HTMLElement | null = null;

  function getContainer(): HTMLElement {
    if (!container) {
      container = document.getElementById(elementId);
      if (!container) {
        throw new Error(`Legend container element "#${elementId}" not found in the DOM`);
      }
      container.classList.add('legend');
    }
    return container;
  }

  function render(scale: ColourScale, title: string): void {
    const el = getContainer();
    buildLegendContent(el, scale, title);
  }

  function update(scale: ColourScale, title: string): void {
    // update reuses the same container — no need to recreate it
    render(scale, title);
  }

  return { render, update };
}
