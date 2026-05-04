/**
 * Detail panel — displays meshblock indicator values for a selected scenario.
 *
 * Replaces the single-scenario scorePanel with a scenario-aware detail view
 * that shows indicator values, human-readable labels, and diff-from-original
 * values with +/− formatting.
 *
 * Requirements: 8.1, 8.2, 8.3, 8.4
 */

import { indicatorLabel, scenarioLabel } from './indicatorLabels';

export interface DetailPanelIndicator {
  name: string;
  label: string;
  value: number | null;
}

export interface DetailPanelDiff {
  name: string;
  label: string;
  value: number | null;
}

export interface DetailPanelData {
  mb_code: number;
  scenario: string;
  indicators: DetailPanelIndicator[];
  diffs: DetailPanelDiff[];
}

export interface DetailPanel {
  show(data: DetailPanelData): void;
  hide(): void;
}

/**
 * Extract detail panel data from a feature's properties for a given scenario.
 *
 * Iterates over the provided indicator names, reads `{indicator}_{scenario}`
 * and `{indicator}_diff_{scenario}` from the properties, and returns a
 * structured `DetailPanelData` object.
 */
export function extractDetailData(
  properties: Record<string, unknown>,
  scenario: string,
  indicators: string[],
): DetailPanelData {
  const mbCode = properties['mb_code'] as number;

  const indicatorEntries: DetailPanelIndicator[] = indicators.map((name) => {
    const key = `${name}_${scenario}`;
    const raw = properties[key];
    const value = typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
    return { name, label: indicatorLabel(name), value };
  });

  const diffEntries: DetailPanelDiff[] = indicators.map((name) => {
    const key = `${name}_diff_${scenario}`;
    const raw = properties[key];
    const value = typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
    return { name, label: indicatorLabel(name), value };
  });

  return {
    mb_code: mbCode,
    scenario,
    indicators: indicatorEntries,
    diffs: diffEntries,
  };
}

/**
 * Create a detail panel bound to a DOM element.
 *
 * The panel is shown/hidden by toggling the `visible` CSS class,
 * consistent with the existing score panel and error banner pattern.
 */
export function createDetailPanel(elementId: string): DetailPanel {
  const el = document.getElementById(elementId);
  if (!el) throw new Error(`DetailPanel: element #${elementId} not found`);
  const panel = el;

  function show(data: DetailPanelData): void {
    const scenarioName = escapeHtml(scenarioLabel(data.scenario));

    const rows = data.indicators
      .map((ind, i) => {
        const diff = data.diffs[i];
        const valueStr =
          ind.value != null ? ind.value.toFixed(2) : '<span class="detail-panel__na">N/A</span>';
        const diffStr = formatDiff(diff?.value ?? null);

        return `<tr class="detail-panel__row">
          <td class="detail-panel__indicator-name">${escapeHtml(ind.label)}</td>
          <td class="detail-panel__indicator-value">${valueStr}</td>
          <td class="detail-panel__diff-value">${diffStr}</td>
        </tr>`;
      })
      .join('');

    panel.innerHTML = `
      <div class="detail-panel__header">
        <span class="detail-panel__mb-code">MB ${escapeHtml(String(data.mb_code))}</span>
        <span class="detail-panel__scenario">${scenarioName}</span>
      </div>
      <table class="detail-panel__table" role="table">
        <thead>
          <tr>
            <th class="detail-panel__th">Indicator</th>
            <th class="detail-panel__th">Value</th>
            <th class="detail-panel__th">Diff</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;

    panel.classList.add('visible');
  }

  function hide(): void {
    panel.classList.remove('visible');
    panel.innerHTML = '';
  }

  return { show, hide };
}

/** Format a diff value with +/− sign, or "—" if null. */
function formatDiff(value: number | null): string {
  if (value == null) return '<span class="detail-panel__na">—</span>';
  const sign = value > 0 ? '+' : '';
  const cls = value > 0 ? 'detail-panel__diff--positive' : value < 0 ? 'detail-panel__diff--negative' : '';
  return `<span class="${cls}">${sign}${value.toFixed(2)}</span>`;
}

/** Escape HTML special characters to prevent XSS. */
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
