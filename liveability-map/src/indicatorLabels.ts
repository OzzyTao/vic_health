/**
 * Human-readable labels for indicator and scenario keys.
 *
 * Requirements: 3.4, 4.4, 8.3
 */

export const INDICATOR_LABELS: Record<string, string> = {
  urban_liveability_index: "Urban Liveability Index",
  social_infrastructure_index: "Social Infrastructure Index",
  walkability_dwelling_density: "Walkability – Dwelling Density",
  walkability_daily_living_score: "Walkability – Daily Living",
  walkability_index: "Walkability Index",
  transport_percent_dwellings_400m_regular_pt: "Transport – Dwellings near PT",
  housing_percent_social_housing: "Housing – Social Housing %",
  pos_closest_large: "Closest Large Public Open Space",
};

export const SCENARIO_LABELS: Record<string, string> = {
  original: "Original",
  probable: "Probable",
  community: "Community",
  liveability: "Liveability",
};

/** Returns the human-readable label for an indicator key, or the raw key if not found. */
export function indicatorLabel(key: string): string {
  return INDICATOR_LABELS[key] ?? key;
}

/** Returns the human-readable label for a scenario key, or the raw key if not found. */
export function scenarioLabel(key: string): string {
  return SCENARIO_LABELS[key] ?? key;
}
