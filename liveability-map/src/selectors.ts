/**
 * Selector factory — creates labelled `<select>` elements for
 * indicator and scenario selection.
 *
 * Requirements: 3.1, 3.3, 4.1, 4.3
 */

export interface SelectorOption {
  value: string;
  label: string;
}

export interface SelectorOptions {
  /** ID of the container element to render into. */
  containerId: string;
  /** Text label displayed next to the select element. */
  label: string;
  /** Available options for the dropdown. */
  options: SelectorOption[];
  /** The option value selected by default. */
  defaultValue: string;
  /** Callback fired when the user changes the selection. */
  onChange: (value: string) => void;
}

/**
 * Create a `<label>` + `<select>` pair inside the specified container.
 *
 * Returns the `<select>` element so callers can read its current value
 * or programmatically update it.
 */
export function createSelector(opts: SelectorOptions): HTMLSelectElement {
  const container = document.getElementById(opts.containerId);
  if (!container) {
    throw new Error(`Selector container not found: #${opts.containerId}`);
  }

  const wrapper = document.createElement('div');
  wrapper.className = 'selector';

  const label = document.createElement('label');
  label.className = 'selector__label';
  label.textContent = opts.label;

  const select = document.createElement('select');
  select.className = 'selector__select';

  // Wire the label to the select via a generated id
  const selectId = `selector-${opts.containerId}-${opts.label.replace(/\s+/g, '-').toLowerCase()}`;
  select.id = selectId;
  label.htmlFor = selectId;

  for (const opt of opts.options) {
    const option = document.createElement('option');
    option.value = opt.value;
    option.textContent = opt.label;
    if (opt.value === opts.defaultValue) {
      option.selected = true;
    }
    select.appendChild(option);
  }

  select.addEventListener('change', () => {
    opts.onChange(select.value);
  });

  wrapper.appendChild(label);
  wrapper.appendChild(select);
  container.appendChild(wrapper);

  return select;
}
