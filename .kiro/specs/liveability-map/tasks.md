# Implementation Plan: Liveability Map

## Overview

Build a static single-page TypeScript + Vite application that renders an interactive choropleth map of liveability scores using Leaflet.js. All data is bundled as a static GeoJSON file with no backend required.

## Tasks

- [x] 1. Scaffold project structure and configuration
  - Initialise a Vite + TypeScript project
  - Install Leaflet and its type definitions (`leaflet`, `@types/leaflet`)
  - Create `data/liveability.geojson` with sample meshblock features for development
  - Set up `index.html` with a full-viewport map container div and score panel placeholder
  - _Requirements: 3.1, 3.2_

- [ ] 2. Implement DataLoader
  - [x] 2.1 Implement `loadGeoJSON(url)` function
    - Define `MeshblockProperties`, `SubIndicator`, `MeshblockFeature`, and `LoadResult` TypeScript interfaces
    - Fetch the GeoJSON file and parse it into a `LoadResult`
    - Skip features missing `meshblock_id` or `liveability_score` with a console warning
    - Return `{ features: [], error: "..." }` on network or parse failure
    - _Requirements: 1.3, 1.4_
  - [ ]* 2.2 Write unit tests for `loadGeoJSON`
    - Test successful load with valid features
    - Test that features missing required fields are skipped
    - Test error result on fetch failure
    - _Requirements: 1.3, 1.4_

- [ ] 3. Implement ColourScale
  - [x] 3.1 Implement `buildColourScale(scores)` function
    - Compute min/max from the provided scores array
    - Produce a sequential colour ramp (light yellow → dark green) using normalised interpolation
    - Handle the degenerate case where all scores are equal (return midpoint colour)
    - Expose `min`, `max`, `stops`, and `getColour(score)` on the returned object
    - _Requirements: 1.1, 1.2_
  - [ ]* 3.2 Write unit tests for `buildColourScale`
    - Test `getColour` returns correct hex values at min, max, and midpoint
    - Test degenerate case (all scores equal)
    - _Requirements: 1.1_

- [x] 4. Implement MapRenderer
  - [x] 4.1 Implement `MapRenderer` wrapping Leaflet
    - `init(containerId)` — initialise Leaflet map centred on the data extent
    - `renderChoropleth(features, scale)` — add a GeoJSON layer with fill colour from `scale.getColour`
    - `onMeshblockClick(handler)` — register click handler on each polygon, stop propagation
    - `onMapClick(handler)` — register click handler on the map background for dismiss
    - _Requirements: 1.1, 1.5, 2.1, 2.4_
  - [ ]* 4.2 Write unit tests for MapRenderer colour application
    - Test that each feature's fill colour matches `scale.getColour(liveability_score)`
    - _Requirements: 1.1_

- [x] 5. Implement ScorePanel
  - [x] 5.1 Implement `ScorePanel` DOM overlay
    - `show(props)` — render overall `liveability_score` and list of `sub_indicators` into the panel element
    - `hide()` — hide the panel
    - When `sub_indicators` is empty or absent, display "detailed data unavailable" message
    - _Requirements: 2.1, 2.2, 2.3, 2.5_
  - [ ]* 5.2 Write unit tests for ScorePanel
    - Test `show` renders score and sub-indicator names/values
    - Test `show` with empty sub-indicators displays the unavailable message
    - Test `hide` removes panel from view
    - _Requirements: 2.2, 2.3, 2.5_

- [x] 6. Implement Legend
  - Implement `Legend.render(scale)` as a Leaflet control
  - Display colour stops with corresponding score range labels
  - Add the control to the map in the bottom-right corner
  - _Requirements: 1.2_

- [x] 7. Wire everything together in `main.ts`
  - Call `loadGeoJSON` on app init; on error display the error message in the UI
  - Build the colour scale from loaded scores
  - Call `MapRenderer.init`, then `renderChoropleth`
  - Register `onMeshblockClick` → `ScorePanel.show` and `onMapClick` → `ScorePanel.hide`
  - Add the Legend control to the map
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.4_

- [ ] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Add Docker support
  - Write a `Dockerfile` using `nginx:alpine` that copies the Vite build output into the nginx html directory
  - Add a `.dockerignore` file
  - _Requirements: 3.3_

- [ ] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- The design has no Correctness Properties, so only unit tests are included (no property-based tests)
