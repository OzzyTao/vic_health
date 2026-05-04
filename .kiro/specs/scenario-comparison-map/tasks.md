# Implementation Plan: Scenario Comparison Map

## Overview

This plan converts the existing single-pane liveability map into a side-by-side scenario comparison tool. Implementation proceeds in three phases: (1) Python data converter to produce `scenarios.geojson` from the GeoPackage, (2) TypeScript frontend modules for data loading, selectors, colour scale, and labels, (3) dual-map rendering with synchronisation, legend, detail panel, and wiring everything together. Testing uses pytest for Python and Vitest + fast-check for TypeScript.

## Tasks

- [-] 1. Build the Python GeoPackage-to-GeoJSON converter
  - [x] 1.1 Create `vic_health/gpkg_to_geojson.py` with `convert_gpkg(gpkg_path, output_path)` function
    - Read the `gpkg_geometry_columns` metadata table to identify the geometry column name
    - Connect to the GeoPackage via `sqlite3` and query all rows from the `vichealth_niddrie` table
    - Parse GeoPackage binary geometry (2-byte magic, version, flags, SRID, envelope, then WKB) into GeoJSON coordinate arrays
    - Emit each row as a GeoJSON Feature with `mb_code` and all `{indicator}_{scenario}` and `{indicator}_diff_{scenario}` columns as flat properties
    - Skip rows with unparseable geometry, log a warning with the `mb_code`, and track skipped count
    - Write the FeatureCollection to the output path
    - Return a `ConversionResult` dataclass with `output_path`, `feature_count`, `skipped_count`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 1.2 Write pytest tests for the converter
    - Test that the converter produces valid GeoJSON from the real GeoPackage
    - Test geometry parser correctly handles GeoPackage binary header + WKB for known test vectors
    - Test geometry parser returns None for malformed binary data
    - Test converter handles empty table gracefully
    - Test output contains `mb_code` and expected `{indicator}_{scenario}` property keys
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 1.3 Write property test for converter output completeness
    - **Property 1: Converter Output Completeness**
    - Generate random rows with mb_code + random indicator/scenario columns and valid geometry bytes
    - Assert: feature count equals input rows with valid geometry, every feature has `mb_code`, all indicator columns preserved
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**

  - [ ]* 1.4 Write property test for graceful geometry skip
    - **Property 2: Graceful Geometry Skip**
    - Generate a mix of valid WKB blobs and garbage bytes
    - Assert: output contains exactly the valid-geometry rows, skipped count equals invalid rows, converter does not abort
    - **Validates: Requirements 1.5**

  - [ ]* 1.5 Write property test for conversion round-trip
    - **Property 3: Conversion Round-Trip**
    - Generate random polygon coordinates + indicator values, convert to GeoJSON and parse back
    - Assert: geometry coordinates and indicator values match originals within floating-point tolerance
    - **Validates: Requirements 1.6**

- [x] 2. Run the converter to produce `scenarios.geojson`
  - Add a CLI entry point or script invocation to run `convert_gpkg` against `liveability-map/public/data/vichealth_niddrie.gpkg`
  - Output to `liveability-map/public/data/scenarios.geojson`
  - _Requirements: 1.1_

- [x] 3. Checkpoint
  - Ensure all Python tests pass, ask the user if questions arise.

- [x] 4. Set up TypeScript testing infrastructure
  - [x] 4.1 Add `vitest` and `fast-check` as dev dependencies in `liveability-map/package.json`
    - Add a `"test"` script to package.json (e.g., `"test": "vitest --run"`)
    - Create `liveability-map/vitest.config.ts` if needed (Vitest auto-detects Vite config)
    - _Requirements: (infrastructure for all frontend testing)_

- [x] 5. Implement IndicatorLabels module
  - [x] 5.1 Create `liveability-map/src/indicatorLabels.ts`
    - Define `INDICATOR_LABELS` record mapping all 8 indicator keys to human-readable strings
    - Define `SCENARIO_LABELS` record mapping all 4 scenario keys to human-readable strings
    - Export `indicatorLabel(key: string): string` — returns label or raw key as fallback
    - Export `scenarioLabel(key: string): string` — returns label or raw key as fallback
    - _Requirements: 3.4, 4.4, 8.3_

  - [ ]* 5.2 Write property test for label completeness
    - **Property 5: Human-Readable Label Completeness**
    - Use `fc.constantFrom(...INDICATOR_KEYS)` and `fc.constantFrom(...SCENARIO_KEYS)`
    - Assert: returned label is non-empty and not equal to the raw key for all known keys
    - **Validates: Requirements 3.4, 4.4**

- [x] 6. Implement ScenarioDataLoader
  - [x] 6.1 Create `liveability-map/src/scenarioDataLoader.ts`
    - Define `ScenarioFeature` and `ScenarioLoadResult` interfaces
    - Implement `loadScenarioData(url: string): Promise<ScenarioLoadResult>`
    - Fetch the GeoJSON file, handle HTTP errors and JSON parse errors
    - Parse property keys to extract unique indicator names and scenario names using the column naming convention
    - Skip features missing `mb_code` with a console warning
    - Return `{ features: [], error: "..." }` for empty FeatureCollections
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 6.2 Write unit tests for ScenarioDataLoader
    - Test: fetches and parses a fixture GeoJSON file correctly
    - Test: returns error for HTTP 404 response
    - Test: returns error for empty FeatureCollection
    - Test: skips features missing `mb_code`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 9.1, 9.2_

  - [ ]* 6.3 Write property test for column name parsing correctness
    - **Property 4: Column Name Parsing Correctness**
    - Use `fc.record` with random `{indicator}_{scenario}` keys from known indicator and scenario sets
    - Assert: parser extracts the complete set of unique indicator names and scenario names with no false positives or omissions
    - **Validates: Requirements 2.3, 2.4**

- [x] 7. Extend ColourScale with `buildIndicatorScale`
  - [x] 7.1 Add `buildIndicatorScale(features, indicator, scenarios)` to `liveability-map/src/colourScale.ts`
    - Collect all values of `{indicator}_{scenario}` for every scenario across all features
    - Filter out `null`/`undefined` values
    - Pass the combined array to the existing `buildColourScale`
    - Return a single `ColourScale` with global min/max for that indicator
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ]* 7.2 Write property test for global indicator scale
    - **Property 6: Global Indicator Scale**
    - Generate arrays of ScenarioFeature-like objects with random indicator values per scenario
    - Assert: resulting scale's `min` equals the minimum across all scenarios/features, `max` equals the maximum (excluding null/undefined)
    - **Validates: Requirements 6.1**

  - [ ]* 7.3 Write property test for colour scale determinism
    - **Property 7: Colour Scale Determinism**
    - Generate a ColourScale from random scores, then generate random values within `[min, max]`
    - Assert: calling `getColour(value)` multiple times always returns the same CSS colour string
    - **Validates: Requirements 6.4**

  - [ ]* 7.4 Write property test for missing value exclusion from scale
    - **Property 9: Missing Value Exclusion from Scale**
    - Generate arrays of features where some have `null` for the indicator column
    - Assert: `buildIndicatorScale` computes min/max only from non-null values
    - **Validates: Requirements 9.3**

- [ ] 8. Checkpoint
  - Ensure all TypeScript tests pass, ask the user if questions arise.

- [x] 9. Implement Selectors
  - [x] 9.1 Create `liveability-map/src/selectors.ts`
    - Implement `createSelector(opts: SelectorOptions): HTMLSelectElement`
    - Accept `containerId`, `label`, `options` array, `defaultValue`, and `onChange` callback
    - Render a `<label>` and `<select>` element into the specified container
    - _Requirements: 3.1, 3.3, 4.1, 4.3_

  - [ ]* 9.2 Write unit tests for Selectors
    - Test: indicator selector renders all 8 indicators as options
    - Test: indicator selector defaults to `urban_liveability_index`
    - Test: scenario selectors display all 4 scenarios
    - Test: left scenario defaults to `original`, right to `liveability`
    - _Requirements: 3.1, 3.3, 4.1, 4.3_

- [x] 10. Implement ComparisonMap
  - [x] 10.1 Create `liveability-map/src/comparisonMap.ts`
    - Implement `MapPane` interface: `init`, `renderChoropleth`, `fitBounds`, `getMap`, `onFeatureClick`, `onBackgroundClick`
    - Each pane creates its own Leaflet map instance with a tile layer
    - `renderChoropleth` styles each feature using the shared `ColourScale`, renders missing-indicator features in `#cccccc` grey
    - Implement `ComparisonMap` interface wrapping two `MapPane` instances
    - Wire `moveend`/`zoomend` sync between panes with a `_syncing` guard flag to prevent infinite recursion
    - Support `onFeatureClick` callback that reports which pane (`'left' | 'right'`) was clicked
    - Support `onBackgroundClick` callback
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 9.3_

  - [ ]* 10.2 Write unit tests for ComparisonMap
    - Test: two panes are rendered side by side (DOM structure)
    - Test: panes sync on pan/zoom (mock Leaflet events)
    - Test: panes are labelled with scenario names
    - Test: both panes fit to data bounds on init
    - Test: missing indicator renders meshblock grey
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 9.3_

- [x] 11. Extend Legend to accept a title parameter
  - [x] 11.1 Update `liveability-map/src/legend.ts`
    - Modify `Legend` interface to include `render(scale, title)` and `update(scale, title)` methods
    - `render` creates the legend DOM with the given title and colour stops
    - `update` replaces the legend content without creating a new Leaflet control
    - The legend is rendered in a fixed DOM position shared between both panes (not inside a map pane)
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 11.2 Write unit tests for Legend
    - Test: renders colour stops and value ranges
    - Test: title shows human-readable indicator name
    - Test: exactly one legend in the DOM
    - _Requirements: 7.1, 7.2, 7.4_

- [x] 12. Implement DetailPanel
  - [x] 12.1 Create `liveability-map/src/detailPanel.ts`
    - Define `DetailPanelData` interface with `mb_code`, `scenario`, `indicators` array, and `diffs` array
    - Implement `createDetailPanel(elementId): DetailPanel` with `show(data)` and `hide()` methods
    - Display meshblock code, scenario name (human-readable), all indicator values with labels, and diff values with +/− formatting
    - Use `escapeHtml` for any user-facing text
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 12.2 Write unit tests for DetailPanel
    - Test: shows mb_code and indicator values on click
    - Test: hides on background click
    - Test: shows human-readable labels
    - Test: displays diff values with +/− sign
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 12.3 Write property test for detail panel data completeness
    - **Property 8: Detail Panel Data Completeness**
    - Generate random ScenarioFeature properties + random scenario selection
    - Assert: extracted data contains `mb_code`, a value (or null) for every indicator, and corresponding diff values
    - **Validates: Requirements 8.1, 8.4**

- [x] 13. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Update HTML layout and wire everything together in main.ts
  - [x] 14.1 Update `liveability-map/index.html` for comparison layout
    - Replace the single `#map` div with a comparison layout: toolbar area (indicator selector, scenario selectors), two side-by-side map containers (`#map-left`, `#map-right`), a shared legend container, and a detail panel container
    - Each map container should occupy approximately half the viewport width
    - Add scenario labels above or overlaid on each pane
    - Keep the `#error-banner` element
    - _Requirements: 5.1, 5.3_

  - [x] 14.2 Rewrite `liveability-map/src/main.ts` to orchestrate the comparison view
    - Import all new modules: `scenarioDataLoader`, `indicatorLabels`, `colourScale` (with `buildIndicatorScale`), `comparisonMap`, `selectors`, `legend`, `detailPanel`
    - On init: fetch `scenarios.geojson` via `loadScenarioData`, handle errors in the error banner
    - Create the three selectors (indicator, left scenario, right scenario) with correct defaults
    - Build the initial `ColourScale` via `buildIndicatorScale` for the default indicator
    - Initialise the `ComparisonMap` with both pane containers
    - Render both panes with the default indicator and scenarios
    - Fit both panes to data bounds
    - Render the shared legend with the indicator title
    - Wire indicator selector `onChange`: recompute scale, re-render both panes, update legend
    - Wire left scenario selector `onChange`: re-render left pane only
    - Wire right scenario selector `onChange`: re-render right pane only
    - Wire `onFeatureClick`: extract detail panel data for the clicked feature and pane's scenario, show detail panel
    - Wire `onBackgroundClick`: hide detail panel
    - _Requirements: 2.1, 2.2, 3.2, 3.3, 4.2, 4.3, 5.4, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 8.1, 8.2, 9.1, 9.2_

  - [x] 14.3 Update `liveability-map/src/style.css` with comparison layout styles
    - Add styles for the toolbar / selector area
    - Add side-by-side map pane layout (flexbox or grid, each ~50% width)
    - Add scenario label overlay styles for each pane
    - Add shared legend positioning styles
    - Update detail panel styles for the new layout
    - _Requirements: 5.1, 5.3_

- [x] 15. Final checkpoint
  - Ensure all tests pass and the build succeeds (`npm run build`), ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The Python converter (tasks 1–2) can be developed independently of the frontend (tasks 4–14)
- The existing `dataLoader.ts`, `mapRenderer.ts`, and `scorePanel.ts` are not deleted — the new modules replace their role in the comparison view
