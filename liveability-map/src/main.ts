/**
 * Main entry point — orchestrates the scenario comparison view.
 *
 * Requirements: 2.1, 2.2, 3.2, 3.3, 4.2, 4.3, 5.4, 6.1, 6.2, 6.3,
 *               7.1, 7.2, 7.3, 8.1, 8.2, 9.1, 9.2
 */

import './style.css';
import { loadScenarioData } from './scenarioDataLoader';
import type { ScenarioFeature } from './scenarioDataLoader';
import { indicatorLabel, scenarioLabel } from './indicatorLabels';
import { buildIndicatorScale } from './colourScale';
import { createComparisonMap } from './comparisonMap';
import { createSelector } from './selectors';
import { createLegend } from './legend';
import { createDetailPanel, extractDetailData } from './detailPanel';

const DATA_URL = './data/scenarios.geojson';
const DEFAULT_INDICATOR = 'urban_liveability_index';
const DEFAULT_LEFT_SCENARIO = 'original';
const DEFAULT_RIGHT_SCENARIO = 'liveability';

async function init(): Promise<void> {
  const errorBanner = document.getElementById('error-banner');

  // ── Load data ──
  const result = await loadScenarioData(DATA_URL);

  if (result.error) {
    if (errorBanner) {
      errorBanner.textContent = result.error;
      errorBanner.classList.add('visible');
    }
    return;
  }

  const { features, indicators, scenarios } = result;

  // ── Application state ──
  let selectedIndicator = DEFAULT_INDICATOR;
  let leftScenario = DEFAULT_LEFT_SCENARIO;
  let rightScenario = DEFAULT_RIGHT_SCENARIO;

  // ── Build initial colour scale ──
  let currentScale = buildIndicatorScale(features, selectedIndicator, scenarios);

  // ── Initialise comparison map ──
  const comparisonMap = createComparisonMap();
  comparisonMap.init('map-left', 'map-right');

  // ── Render initial state ──
  comparisonMap.renderLeft(features, selectedIndicator, leftScenario, currentScale);
  comparisonMap.renderRight(features, selectedIndicator, rightScenario, currentScale);
  comparisonMap.fitToData(features);

  // ── Update pane labels ──
  function updateLabels(): void {
    const leftLabel = document.getElementById('label-left');
    const rightLabel = document.getElementById('label-right');
    if (leftLabel) leftLabel.textContent = scenarioLabel(leftScenario);
    if (rightLabel) rightLabel.textContent = scenarioLabel(rightScenario);
  }
  updateLabels();

  // ── Shared legend ──
  const legend = createLegend('legend');
  legend.render(currentScale, indicatorLabel(selectedIndicator));

  // ── Detail panel ──
  const detailPanel = createDetailPanel('detail-panel');

  // ── Create selectors ──

  // Indicator selector
  createSelector({
    containerId: 'indicator-selector',
    label: 'Indicator',
    options: indicators.map((key) => ({ value: key, label: indicatorLabel(key) })),
    defaultValue: selectedIndicator,
    onChange: (value: string) => {
      selectedIndicator = value;
      currentScale = buildIndicatorScale(features, selectedIndicator, scenarios);
      comparisonMap.renderLeft(features, selectedIndicator, leftScenario, currentScale);
      comparisonMap.renderRight(features, selectedIndicator, rightScenario, currentScale);
      legend.update(currentScale, indicatorLabel(selectedIndicator));
    },
  });

  // Left scenario selector
  createSelector({
    containerId: 'left-scenario-selector',
    label: 'Left Scenario',
    options: scenarios.map((key) => ({ value: key, label: scenarioLabel(key) })),
    defaultValue: leftScenario,
    onChange: (value: string) => {
      leftScenario = value;
      comparisonMap.renderLeft(features, selectedIndicator, leftScenario, currentScale);
      updateLabels();
    },
  });

  // Right scenario selector
  createSelector({
    containerId: 'right-scenario-selector',
    label: 'Right Scenario',
    options: scenarios.map((key) => ({ value: key, label: scenarioLabel(key) })),
    defaultValue: rightScenario,
    onChange: (value: string) => {
      rightScenario = value;
      comparisonMap.renderRight(features, selectedIndicator, rightScenario, currentScale);
      updateLabels();
    },
  });

  // ── Wire feature click → detail panel ──
  comparisonMap.onFeatureClick((feature: ScenarioFeature, pane: 'left' | 'right') => {
    const scenario = pane === 'left' ? leftScenario : rightScenario;
    const data = extractDetailData(feature.properties, scenario, indicators);
    detailPanel.show(data);
  });

  // ── Wire background click → hide detail panel ──
  comparisonMap.onBackgroundClick(() => {
    comparisonMap.clearSelection();
    detailPanel.hide();
  });
}

init();
