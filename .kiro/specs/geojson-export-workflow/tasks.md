# Implementation Plan: GeoJSON Export Workflow

## Overview

Implement the `vic_health` Python package as a CLI tool that connects to a local spatial database, discovers meshblock tables, extracts features within a bounding box, and writes a GeoJSON FeatureCollection compatible with the liveability map.

## Tasks

- [x] 1. Scaffold project structure and shared data models
  - Create `vic_health/` package directory with `__init__.py`
  - Add `vic_health/models.py` defining `BoundingBox`, `SubIndicator`, `MeshblockRecord`, `TableInfo`, `ExportResult` dataclasses
  - Add `psycopg2-binary`, `hypothesis`, and `pytest` to `pyproject.toml` dependencies
  - Register `vic-health-export = "vic_health.export_cli:main"` under `[project.scripts]` in `pyproject.toml`
  - Create empty module stubs: `vic_health/explorer.py`, `vic_health/extractor.py`, `vic_health/exporter.py`, `vic_health/export_cli.py`
  - _Requirements: 6.1_

- [x] 2. Implement Explorer
  - [x] 2.1 Implement `DatabaseConnection` protocol and `connect()` in `vic_health/explorer.py`
    - Parse DSN prefix to select `psycopg2` (postgresql) or `sqlite3` wrapper
    - Wrap each driver in a thin adapter implementing `execute(sql, params) -> list[dict]` and `close()`
    - On connection failure, raise `ConnectionError` with credentials redacted from the DSN
    - _Requirements: 1.1, 1.5_

  - [x] 2.2 Implement `discover()` in `vic_health/explorer.py`
    - For PostgreSQL: query `information_schema.columns` for geometry/geography columns and meshblock-id-mappable column names
    - For SQLite: query `geometry_columns` table and `pragma_table_info` for the same heuristic
    - If `table_hint` is provided, validate it exists and has required columns; skip enumeration
    - Raise `DiscoveryError` if no relevant tables found, printing inspected table names
    - Print discovered table names to stdout before returning
    - _Requirements: 1.2, 1.3, 1.4_

  - [ ]* 2.3 Write property test for Table Discovery Correctness (Property 1)
    - **Property 1: Table Discovery Correctness**
    - Generate arbitrary lists of `{name, columns}` dicts via `st.lists(st.fixed_dictionaries(...))`
    - Assert `discover` returns exactly the tables with both a geometry column and a meshblock-id column
    - **Validates: Requirements 1.2**

  - [ ]* 2.4 Write property test for Credential Redaction (Property 2)
    - **Property 2: Credential Redaction**
    - Generate DSNs via `st.from_regex(r"postgresql://\w+:[^@]+@\w+/\w+")`
    - Simulate a connection failure and assert the error message does not contain the raw password
    - **Validates: Requirements 1.5**

  - [ ]* 2.5 Write unit tests for Explorer
    - Connect to an in-memory SQLite DB and assert correct table enumeration
    - Assert `DiscoveryError` is raised when no relevant tables exist
    - Assert `--table` hint skips discovery and uses the specified table
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 3. Implement Extractor
  - [x] 3.1 Implement `validate_bbox()` in `vic_health/extractor.py`
    - Raise `ValueError` with a descriptive message for each invalid condition: `min_lng >= max_lng`, `min_lat >= max_lat`, longitude outside [-180, 180], latitude outside [-90, 90]
    - _Requirements: 2.2, 2.3_

  - [ ]* 3.2 Write property test for Bounding Box Validation (Property 3)
    - **Property 3: Bounding Box Validation**
    - Generate four floats in [-200, 200] via `st.floats(-200, 200)`
    - Partition into valid/invalid cases and assert `validate_bbox` accepts/rejects accordingly
    - **Validates: Requirements 2.3**

  - [x] 3.3 Implement `extract()` in `vic_health/extractor.py`
    - Build dialect-aware SQL: `ST_Intersects` + `ST_MakeEnvelope` for PostGIS; `MbrIntersects` + `BuildMbr` for SpatiaLite
    - Return geometry as WKT via `ST_AsText` / `AsText`
    - Map result rows to `MeshblockRecord` objects; raise `ExtractionError` with bbox extent if zero rows returned
    - _Requirements: 2.1, 2.4, 2.5_

  - [ ]* 3.4 Write property test for Intersection Completeness and Soundness (Property 4)
    - **Property 4: Intersection Completeness and Soundness**
    - Generate a `BoundingBox` and a list of `MeshblockRecord` objects with polygon WKT geometries
    - Assert the spatial filter returns exactly the records whose geometry intersects the bbox (no false positives, no false negatives)
    - **Validates: Requirements 2.1, 2.5**

  - [ ]* 3.5 Write unit tests for Extractor
    - Assert warning and non-zero exit when bbox returns zero features
    - Assert all matching features are returned for a known fixture set
    - _Requirements: 2.4, 2.5_

- [ ] 4. Checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Exporter
  - [x] 5.1 Implement `build_feature()` in `vic_health/exporter.py`
    - Parse `geometry_wkt` (POLYGON / multi-ring) using regex/split — no external geometry library
    - Produce a GeoJSON Feature dict with `geometry.type == "Polygon"`, `[lng, lat]` coordinate pairs, and correct `properties` fields
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 5.2 Write property test for Feature Construction Correctness (Property 5)
    - **Property 5: Feature Construction Correctness**
    - Generate arbitrary `MeshblockRecord` objects via `st.builds(MeshblockRecord, ...)`
    - Assert `geometry.type == "Polygon"`, all coordinate pairs are `[float, float]`, `properties.meshblock_id` is non-empty, `properties.liveability_score` is a number, `properties.sub_indicators` is a list of `{name, score}` dicts
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

  - [x] 5.3 Implement `build_feature_collection()` in `vic_health/exporter.py`
    - Deduplicate by `meshblock_id` (first-occurrence wins), log a warning listing any duplicates
    - Wrap features in `{"type": "FeatureCollection", "features": [...]}`
    - _Requirements: 3.5, 4.2_

  - [ ]* 5.4 Write property test for Deduplication Preserves First Occurrence (Property 6)
    - **Property 6: Deduplication Preserves First Occurrence**
    - Generate lists of `MeshblockRecord` objects with injected duplicate `meshblock_id` values
    - Assert all `meshblock_id` values in the output are unique and each retained feature matches the first occurrence
    - **Validates: Requirements 3.5**

  - [x] 5.5 Implement `export()` in `vic_health/exporter.py`
    - Call `build_feature_collection`, write JSON to `output_path` (create parent dirs, overwrite with stderr warning if exists)
    - Skip write and print dry-run count when `dry_run=True`
    - Print `output_path` and feature count to stdout on success; raise/exit on write failure
    - Return `ExportResult(output_path, feature_count, duplicates_removed)`
    - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.6, 6.4_

  - [ ]* 5.6 Write property test for Serialization Round-Trip (Property 7)
    - **Property 7: Serialization Round-Trip**
    - Generate arbitrary lists of `MeshblockRecord` objects, export to a temp file, parse back as JSON
    - Assert all `type` fields, `meshblock_id` values, `liveability_score` values, coordinate arrays, and `sub_indicators` arrays are preserved
    - **Validates: Requirements 5.1, 5.2, 4.2**

  - [ ]* 5.7 Write property test for Printed Count Matches Written Count (Property 8)
    - **Property 8: Printed Count Matches Written Count**
    - Generate arbitrary lists of `MeshblockRecord` objects, capture stdout during `export()`, parse the written file
    - Assert the count printed to stdout equals `len(output["features"])`
    - **Validates: Requirements 4.5**

  - [ ]* 5.8 Write unit tests for Exporter
    - Assert parent directories are created when output path is nested
    - Assert existing file is overwritten and a warning is printed to stderr
    - Assert `--dry-run` prints count and writes nothing
    - Assert file write failure produces error message and non-zero exit
    - _Requirements: 4.3, 4.4, 4.6, 6.4_

- [x] 6. Implement CLI entry point
  - [x] 6.1 Implement `build_parser()` and `main()` in `vic_health/export_cli.py`
    - Define arguments: positional DSN, `--bbox min_lng min_lat max_lng max_lat`, `--output`, `--table`, `--dry-run`
    - Include `--help` with argument descriptions and an example invocation
    - Call `validate_bbox` before connecting; print validation error to stderr and exit 1 on failure
    - Wire `connect → discover (or use --table) → extract → export`; propagate exit codes from each component
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 6.2 Write unit tests for CLI
    - Assert `--help` output contains all argument names and an example
    - Assert missing required arguments exit non-zero with a descriptive message
    - Assert `--table` bypasses discovery
    - Assert invalid bbox exits 1 with a validation message
    - _Requirements: 6.2, 6.3, 6.5, 2.3_

- [ ] 7. Integration tests
  - [ ]* 7.1 Write end-to-end integration test using in-memory SpatiaLite
    - Spin up an in-memory SpatiaLite DB with known meshblock fixtures
    - Invoke the full CLI via `main()` and assert the output file matches expected GeoJSON structure and feature count
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 4.2_

  - [ ]* 7.2 Write optional PostgreSQL/PostGIS integration test
    - Skip if no PostgreSQL instance is available (`pytest.importorskip` / env-var guard)
    - Same end-to-end assertion as 7.1 against a real PostGIS DB
    - _Requirements: 1.1, 2.1_

- [ ] 8. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use `@given` with `settings(max_examples=100)` and include the tag `Feature: geojson-export-workflow, Property N: ...` in their docstrings
- Unit tests and property tests live under `tests/` at the workspace root
- Checkpoints ensure incremental validation before moving to the next component
