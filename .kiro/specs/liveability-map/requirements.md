# Requirements Document

## Introduction

A web map application that allows urban planners to explore and analyse liveability scores at the meshblock level across a geographic area. Liveability scores are composite values derived from sub-indicators such as walkability and access to parks. All data is served from a static data file bundled with the application. The application is a single static page with no backend server.

## Glossary

- **Map_Application**: The web-based front-end application that renders the interactive map and liveability data.
- **Static_Data_File**: A static file (e.g. GeoJSON) bundled with the Map_Application that contains Meshblock geometries and liveability score data.
- **Meshblock**: The smallest geographic unit used by the Australian Bureau of Statistics, represented as a polygon on the map.
- **Liveability_Score**: A single composite numeric score assigned to each Meshblock, aggregated from sub-indicator scores. The score is unbounded — larger values indicate better liveability.
- **Sub_Indicator**: A named component of the Liveability_Score (e.g., walkability, access to parks, public transport access, healthcare access).
- **Score_Breakdown**: A detailed view showing the individual Sub_Indicator scores that contribute to a Meshblock's Liveability_Score.
- **Choropleth**: A map visualisation technique where Meshblock polygons are shaded according to their Liveability_Score.
- **Urban_Planner**: The primary user of the Map_Application.

---

## Requirements

### Requirement 1: Display Liveability Scores on a Map

**User Story:** As an urban planner, I want to see liveability scores visualised on a map at the meshblock level, so that I can quickly identify high- and low-liveability areas across a region.

#### Acceptance Criteria

1. THE Map_Application SHALL render a Choropleth map where each Meshblock polygon is shaded according to its Liveability_Score.
2. THE Map_Application SHALL display a colour legend that maps Liveability_Score ranges to their corresponding colours.
3. WHEN the Map_Application loads, THE Map_Application SHALL read Meshblock geometries and Liveability_Scores from the Static_Data_File and render them on the map.
4. IF the Static_Data_File cannot be loaded, THEN THE Map_Application SHALL display a descriptive error message to the Urban_Planner.
5. THE Map_Application SHALL support pan and zoom interactions so that the Urban_Planner can navigate to any area of interest.

---

### Requirement 2: View Score Breakdown for a Meshblock

**User Story:** As an urban planner, I want to click on a meshblock and see a breakdown of its liveability sub-indicator scores, so that I can understand what is driving the overall score.

#### Acceptance Criteria

1. WHEN an Urban_Planner clicks on a Meshblock, THE Map_Application SHALL display the Score_Breakdown for that Meshblock.
2. THE Score_Breakdown SHALL include the overall Liveability_Score and the individual score for each Sub_Indicator.
3. THE Score_Breakdown SHALL display the name of each Sub_Indicator alongside its numeric score.
4. WHEN an Urban_Planner clicks outside a Meshblock or dismisses the Score_Breakdown, THE Map_Application SHALL close the Score_Breakdown panel.
5. IF a Meshblock has no Sub_Indicator data available, THEN THE Map_Application SHALL display a message indicating that detailed data is unavailable for that Meshblock.

---

### Requirement 3: Deployability

**User Story:** As a developer, I want the application to be easy to deploy, so that it can be set up in new environments with minimal effort.

#### Acceptance Criteria

1. THE Map_Application SHALL be deployable by serving its static files from any standard static file host or web server.
2. THE Map_Application SHALL require no server-side runtime or build step to serve to end users.
3. WHERE a container runtime is available, THE Map_Application SHALL be runnable as a container using a provided container image definition.
