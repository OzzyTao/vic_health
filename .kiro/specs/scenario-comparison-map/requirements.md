# Requirements Document

## Introduction

The liveability-map application currently loads a single GeoJSON file and renders one choropleth showing a liveability score per meshblock. The new `vichealth_niddrie.gpkg` GeoPackage contains eight indicators across four scenarios (original, probable, community, liveability), plus pre-computed diff columns. This feature upgrades the web map to load data from the GeoPackage (via a converted intermediate format), let users select an indicator and two scenarios, display side-by-side comparison maps, and use indicator-wise colour scales so the same value always maps to the same colour regardless of scenario.

## Glossary

- **Map_App**: The Vite + TypeScript + Leaflet web application in `liveability-map/`
- **GeoPackage**: The SQLite-based `vichealth_niddrie.gpkg` file containing meshblock geometries and indicator values
- **Indicator**: One of eight numeric measures (e.g., `urban_liveability_index`, `walkability_index`) computed per meshblock
- **Scenario**: One of four planning variants: `original`, `probable`, `community`, `liveability`
- **Meshblock**: A geographic polygon identified by `mb_code`, the smallest spatial unit in the dataset (1251 rows)
- **Colour_Scale**: A mapping from numeric indicator values to colours, computed from the global min/max of that indicator across all scenarios
- **Comparison_View**: A layout showing two map panes side by side, each rendering the same indicator under a different scenario
- **Indicator_Selector**: A UI control that lets the user choose which indicator to display
- **Scenario_Selector**: A UI control that lets the user choose which scenario to display on a given map pane
- **Data_Converter**: A build-time or pre-processing step that converts the GeoPackage into a web-friendly format (e.g., GeoJSON) consumable by the Map_App
- **Legend**: A map overlay that shows the colour-to-value mapping for the currently selected indicator
- **Diff_Column**: A pre-computed column in the GeoPackage representing the difference between a scenario's indicator value and the original scenario's value (naming pattern: `{indicator}_diff_{scenario}`)

## Requirements

### Requirement 1: Data Conversion

**User Story:** As a developer, I want to convert the GeoPackage into a web-friendly format, so that the Map_App can load indicator data for all scenarios without requiring a server-side GeoPackage reader.

#### Acceptance Criteria

1. WHEN the Data_Converter is run against `vichealth_niddrie.gpkg`, THE Data_Converter SHALL produce a JSON output file containing all 1251 meshblock geometries and all indicator columns for every scenario
2. THE Data_Converter SHALL preserve the column naming convention `{indicator}_{scenario}` in the output so that the Map_App can parse indicator and scenario from each property name
3. THE Data_Converter SHALL include the `mb_code` identifier for each meshblock in the output
4. THE Data_Converter SHALL include the pre-computed diff columns (`{indicator}_diff_{scenario}`) in the output
5. WHEN a meshblock geometry cannot be converted to valid GeoJSON, THE Data_Converter SHALL log a warning and skip that feature rather than aborting the entire conversion
6. FOR ALL valid meshblock records, converting to JSON and parsing back SHALL produce geometries and indicator values equivalent to the original GeoPackage data (round-trip property)

### Requirement 2: Data Loading

**User Story:** As a user, I want the Map_App to load the converted data file on startup, so that I can explore indicator values across scenarios.

#### Acceptance Criteria

1. WHEN the Map_App starts, THE Map_App SHALL fetch and parse the converted JSON data file
2. WHEN the data file fails to load or contains no features, THE Map_App SHALL display a descriptive error message in the error banner
3. THE Map_App SHALL parse each feature's properties to extract indicator values grouped by scenario, using the `{indicator}_{scenario}` naming convention
4. THE Map_App SHALL extract the list of available indicators and scenarios from the loaded data column names

### Requirement 3: Indicator Selection

**User Story:** As a user, I want to choose which indicator to view on the map, so that I can focus on the measure that interests me.

#### Acceptance Criteria

1. THE Indicator_Selector SHALL display all eight indicators as selectable options
2. WHEN the user selects an indicator, THE Map_App SHALL update both map panes to display that indicator
3. THE Indicator_Selector SHALL default to `urban_liveability_index` on initial load
4. THE Indicator_Selector SHALL display human-readable labels for each indicator (e.g., "Urban Liveability Index" instead of "urban_liveability_index")

### Requirement 4: Scenario Selection

**User Story:** As a user, I want to choose which two scenarios to compare, so that I can see how a planning variant changes indicator values.

#### Acceptance Criteria

1. THE Comparison_View SHALL provide two Scenario_Selectors, one for the left pane and one for the right pane
2. WHEN the user changes a Scenario_Selector, THE Map_App SHALL re-render the corresponding map pane with the selected scenario's data
3. THE left Scenario_Selector SHALL default to `original` and the right Scenario_Selector SHALL default to `liveability` on initial load
4. THE Scenario_Selector SHALL display all four scenarios as selectable options with human-readable labels

### Requirement 5: Side-by-Side Comparison Layout

**User Story:** As a user, I want to see two maps side by side, so that I can visually compare the same indicator under two different scenarios.

#### Acceptance Criteria

1. THE Comparison_View SHALL render two map panes positioned side by side, each occupying approximately half the viewport width
2. WHEN the user pans or zooms one map pane, THE Comparison_View SHALL synchronise the other pane to the same centre and zoom level
3. THE Comparison_View SHALL label each pane with the name of its selected scenario
4. WHEN the Map_App starts, THE Comparison_View SHALL fit both map panes to the extent of the loaded meshblock data

### Requirement 6: Indicator-Wise Colour Scale

**User Story:** As a user, I want the same indicator value to map to the same colour in both panes, so that I can make a fair visual comparison between scenarios.

#### Acceptance Criteria

1. WHEN an indicator is selected, THE Colour_Scale SHALL compute its min and max from that indicator's values across all four scenarios
2. THE Colour_Scale SHALL map indicator values to colours using the global min/max so that identical values produce identical colours regardless of scenario
3. WHEN the user switches to a different indicator, THE Colour_Scale SHALL recompute using the new indicator's global min/max
4. FOR ALL indicator values within the global range, THE Colour_Scale SHALL produce a deterministic colour output (same input always yields same colour)

### Requirement 7: Indicator-Wise Legend

**User Story:** As a user, I want a single legend that reflects the currently selected indicator, so that I can interpret colours consistently across both panes.

#### Acceptance Criteria

1. THE Legend SHALL display the colour stops and value ranges for the currently selected indicator
2. THE Legend SHALL update its title to show the human-readable name of the selected indicator
3. WHEN the user selects a different indicator, THE Legend SHALL re-render with the new indicator's colour scale
4. THE Map_App SHALL display exactly one Legend shared between both map panes

### Requirement 8: Meshblock Detail on Click

**User Story:** As a user, I want to click a meshblock and see its indicator values for the pane's scenario, so that I can inspect exact numbers.

#### Acceptance Criteria

1. WHEN the user clicks a meshblock in either map pane, THE Map_App SHALL display a detail panel showing the clicked meshblock's `mb_code` and all indicator values for that pane's scenario
2. WHEN the user clicks the map background outside any meshblock, THE Map_App SHALL hide the detail panel
3. THE detail panel SHALL display human-readable indicator names alongside their numeric values
4. IF the clicked meshblock has a corresponding diff column value, THEN THE detail panel SHALL also display the difference from the original scenario

### Requirement 9: Error Handling

**User Story:** As a user, I want clear feedback when something goes wrong, so that I understand what happened and what to do.

#### Acceptance Criteria

1. IF the data file cannot be fetched, THEN THE Map_App SHALL display the HTTP status and a descriptive message in the error banner
2. IF the data file contains no parseable features, THEN THE Map_App SHALL display a message indicating the data is empty or malformed
3. IF a meshblock feature is missing the selected indicator column, THEN THE Map_App SHALL render that meshblock with a neutral grey fill and exclude it from colour scale computation
