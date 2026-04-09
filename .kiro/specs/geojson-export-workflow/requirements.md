# Requirements Document

## Introduction

A Python CLI tool that connects to a local database, discovers relevant tables containing meshblock geometry and liveability data, extracts features intersecting a user-supplied bounding box, and writes a GeoJSON FeatureCollection file compatible with the liveability map application.

The tool is intended to be run locally by data engineers or analysts who need to refresh the `data/liveability.geojson` file consumed by the liveability map.

## Glossary

- **CLI**: Command-line interface — the entry point for the tool, invoked via a terminal command.
- **Database**: A local relational database (e.g. PostgreSQL/PostGIS or SQLite with SpatiaLite) accessible from the machine running the tool.
- **Bounding_Box**: A rectangular geographic extent defined by minimum and maximum longitude/latitude values (`min_lng`, `min_lat`, `max_lng`, `max_lat`) used to spatially filter features.
- **Meshblock**: The smallest geographic unit of analysis, identified by a unique `meshblock_id` string.
- **Feature**: A single GeoJSON Feature object representing one meshblock, containing a Polygon geometry and a properties object.
- **FeatureCollection**: A GeoJSON object of type `FeatureCollection` containing an array of Features.
- **Liveability_Score**: A required numeric value representing the overall liveability of a meshblock. Larger values indicate higher liveability.
- **Sub_Indicator**: An optional named component score contributing to the overall Liveability_Score, represented as `{ name: string, score: number }`.
- **Explorer**: The component responsible for connecting to the Database and discovering relevant tables.
- **Extractor**: The component responsible for querying the Database for meshblock data within the Bounding_Box.
- **Exporter**: The component responsible for serialising extracted data into a valid GeoJSON FeatureCollection file.
- **Output_File**: The destination file path where the GeoJSON FeatureCollection is written.

---

## Requirements

### Requirement 1: Database Exploration

**User Story:** As a data engineer, I want the tool to discover relevant tables in the local database, so that I do not need to manually inspect the schema before running an export.

#### Acceptance Criteria

1. WHEN the CLI is invoked with a valid database connection string, THE Explorer SHALL connect to the Database and enumerate all tables and views.
2. WHEN the Explorer has enumerated tables, THE Explorer SHALL identify tables that contain a geometry column and a column mappable to `meshblock_id`.
3. WHEN no relevant tables are found, THE Explorer SHALL print a descriptive message listing the tables it inspected and exit with a non-zero status code.
4. WHEN relevant tables are found, THE Explorer SHALL print the names of the discovered tables to standard output before proceeding.
5. IF the Database connection fails, THEN THE Explorer SHALL print a descriptive error message including the connection string (with credentials redacted) and exit with a non-zero status code.

---

### Requirement 2: Bounding Box Extraction

**User Story:** As a data engineer, I want to extract only the meshblock features that fall within a specified bounding box, so that I can produce a focused export for a particular geographic area.

#### Acceptance Criteria

1. WHEN the CLI is invoked with a Bounding_Box argument, THE Extractor SHALL query the Database for all meshblock features whose geometry intersects the Bounding_Box.
2. THE Extractor SHALL accept the Bounding_Box as four numeric values: `min_lng`, `min_lat`, `max_lng`, `max_lat`, each in decimal degrees (WGS84).
3. IF the Bounding_Box values are invalid (e.g. `min_lng >= max_lng`, `min_lat >= max_lat`, or any value outside [-180, 180] for longitude or [-90, 90] for latitude), THEN THE CLI SHALL print a descriptive validation error and exit with a non-zero status code.
4. WHEN the Bounding_Box query returns zero features, THE Extractor SHALL print a warning message indicating no features were found for the given extent and exit with a non-zero status code.
5. WHEN the Bounding_Box query returns one or more features, THE Extractor SHALL return all matching features for export.

---

### Requirement 3: GeoJSON Feature Construction

**User Story:** As a data engineer, I want each extracted meshblock to be serialised as a valid GeoJSON Feature, so that the output file is accepted by the liveability map application without modification.

#### Acceptance Criteria

1. THE Exporter SHALL construct each Feature with a `geometry` field of type `Polygon` using `[lng, lat]` coordinate pairs in WGS84.
2. THE Exporter SHALL include a `properties` object on each Feature containing `meshblock_id` as a non-empty string and `liveability_score` as a number.
3. WHERE the source data contains sub-indicator columns, THE Exporter SHALL include a `sub_indicators` array on the `properties` object, where each element has a `name` string and a `score` number.
4. WHERE the source data does not contain sub-indicator columns, THE Exporter SHALL include an empty `sub_indicators` array on the `properties` object.
5. THE Exporter SHALL ensure that `meshblock_id` values are unique across all Features in the FeatureCollection; IF duplicate `meshblock_id` values are detected, THEN THE Exporter SHALL log a warning identifying the duplicates and retain only the first occurrence.

---

### Requirement 4: GeoJSON File Output

**User Story:** As a data engineer, I want the tool to write a valid GeoJSON FeatureCollection to a specified file path, so that I can directly replace the liveability map's data file.

#### Acceptance Criteria

1. THE Exporter SHALL write a GeoJSON FeatureCollection to the Output_File path specified by the user.
2. THE Exporter SHALL set the top-level `type` field of the output to `"FeatureCollection"` and the `features` field to the array of constructed Features.
3. WHEN the Output_File path does not exist, THE Exporter SHALL create any necessary parent directories before writing.
4. IF the Output_File already exists, THE Exporter SHALL overwrite it and print a warning indicating the file was overwritten.
5. WHEN writing is complete, THE Exporter SHALL print the Output_File path and the count of features written to standard output.
6. IF an error occurs during file writing, THEN THE Exporter SHALL print a descriptive error message and exit with a non-zero status code.

---

### Requirement 5: GeoJSON Round-Trip Validity

**User Story:** As a data engineer, I want the exported GeoJSON to be parseable and re-exportable without data loss, so that the output is structurally stable and trustworthy.

#### Acceptance Criteria

1. FOR ALL valid FeatureCollections produced by the Exporter, parsing the Output_File as JSON and re-serialising it SHALL produce an equivalent FeatureCollection (round-trip property).
2. THE Exporter SHALL produce output that is valid against the GeoJSON specification (RFC 7946), including correct `type` fields at the FeatureCollection, Feature, and Geometry levels.

---

### Requirement 6: CLI Interface

**User Story:** As a data engineer, I want a clear command-line interface with documented options, so that I can run the export with minimal friction.

#### Acceptance Criteria

1. THE CLI SHALL accept the following arguments: database connection string, Bounding_Box (`--bbox min_lng min_lat max_lng max_lat`), and Output_File path (`--output`).
2. THE CLI SHALL provide a `--help` flag that prints usage instructions, argument descriptions, and an example invocation.
3. WHEN required arguments are missing, THE CLI SHALL print a descriptive error identifying the missing argument and exit with a non-zero status code.
4. THE CLI SHALL support a `--dry-run` flag that performs database exploration and extraction but does not write the Output_File, instead printing the feature count that would be exported.
5. WHERE a `--table` option is provided, THE CLI SHALL use the specified table name instead of running automatic discovery.
