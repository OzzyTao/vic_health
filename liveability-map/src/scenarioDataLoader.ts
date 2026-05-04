/**
 * Scenario data loader — fetches the converted GeoJSON and parses
 * column names into structured indicator/scenario data.
 *
 * Requirements: 2.1, 2.2, 2.3, 2.4
 */

import type * as GeoJSON from 'geojson';

/** Known scenario names used in the column naming convention. */
const KNOWN_SCENARIOS = ['original', 'probable', 'community', 'liveability'] as const;

export interface ScenarioFeature extends GeoJSON.Feature<GeoJSON.Geometry, Record<string, unknown>> {
  properties: {
    mb_code: number;
    [key: string]: unknown;
  };
}

export interface ScenarioLoadResult {
  features: ScenarioFeature[];
  indicators: string[];
  scenarios: string[];
  error?: string;
}

/**
 * Result of parsing column names from feature properties.
 * Exported for use in property tests.
 */
export interface ParsedColumns {
  indicators: string[];
  scenarios: string[];
}

/**
 * Parse property keys to extract unique indicator names and scenario names.
 *
 * For each property key:
 *  1. If key matches `{prefix}_diff_{scenario}` → diff column (skip)
 *  2. Else if key ends with `_{scenario}` → indicator column;
 *     indicator = key with trailing `_{scenario}` removed
 *  3. Else → non-indicator column (e.g. mb_code)
 */
export function parseColumnNames(keys: string[]): ParsedColumns {
  const indicatorSet = new Set<string>();
  const scenarioSet = new Set<string>();

  for (const key of keys) {
    // 1. Check for diff columns: {prefix}_diff_{scenario}
    let isDiff = false;
    for (const scenario of KNOWN_SCENARIOS) {
      const diffSuffix = `_diff_${scenario}`;
      if (key.endsWith(diffSuffix)) {
        isDiff = true;
        break;
      }
    }
    if (isDiff) continue;

    // 2. Check for indicator columns: {indicator}_{scenario}
    let matched = false;
    for (const scenario of KNOWN_SCENARIOS) {
      const suffix = `_${scenario}`;
      if (key.endsWith(suffix)) {
        const indicator = key.slice(0, -suffix.length);
        if (indicator.length > 0) {
          indicatorSet.add(indicator);
          scenarioSet.add(scenario);
        }
        matched = true;
        break;
      }
    }

    // 3. Non-indicator column (e.g. mb_code) — nothing to do
    if (!matched) continue;
  }

  return {
    indicators: [...indicatorSet].sort(),
    scenarios: [...scenarioSet].sort(),
  };
}

/**
 * Fetch and parse the scenario GeoJSON file.
 *
 * Returns a `ScenarioLoadResult` with features, extracted indicator names,
 * and scenario names. On failure, returns `{ features: [], error: "..." }`.
 */
export async function loadScenarioData(url: string): Promise<ScenarioLoadResult> {
  let data: GeoJSON.FeatureCollection;

  try {
    const response = await fetch(url);
    if (!response.ok) {
      return {
        features: [],
        indicators: [],
        scenarios: [],
        error: `Failed to fetch: ${response.status} ${response.statusText}`,
      };
    }
    data = (await response.json()) as GeoJSON.FeatureCollection;
  } catch (err) {
    return {
      features: [],
      indicators: [],
      scenarios: [],
      error: `Failed to parse: ${err instanceof Error ? err.message : String(err)}`,
    };
  }

  const rawFeatures = data.features ?? [];

  if (rawFeatures.length === 0) {
    return {
      features: [],
      indicators: [],
      scenarios: [],
      error: 'No features found in data file',
    };
  }

  const features: ScenarioFeature[] = [];

  for (const feature of rawFeatures) {
    const props = feature.properties as Record<string, unknown> | null;

    if (!props || props['mb_code'] == null) {
      console.warn('Skipping feature missing mb_code:', feature);
      continue;
    }

    features.push(feature as ScenarioFeature);
  }

  // Parse column names from the first valid feature's properties
  const firstProps = features.length > 0 ? features[0].properties : {};
  const { indicators, scenarios } = parseColumnNames(Object.keys(firstProps));

  return { features, indicators, scenarios };
}
