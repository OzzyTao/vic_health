# Design Document: GeoJSON Export Workflow

## Overview

A Python CLI tool (`vic-health export` or `python -m vic_health.export`) that connects to a local spatial database, discovers relevant meshblock tables, extracts features intersecting a user-supplied bounding box, and writes a GeoJSON FeatureCollection file compatible with the liveability map application.

The tool is structured around three collaborating components — **Explorer**, **Extractor**, and **Exporter** — each with a single, well-defined responsibility. The CLI layer wires them together and handles argument parsing, validation, and exit codes.

### Technology Choices

| Concern | Choice | Rationale |
|---|---|---|
| CLI framework | `argparse` (stdlib) | No extra dependency; sufficient for the argument surface |
| Database connectivity | `psycopg2` (PostgreSQL) + `sqlite3` (stdlib, SQLite) | Both are mature, well-documented drivers; `sqlite3` ships with Python |
| Spatial operations | PostGIS SQL (`ST_Intersects`) for PostgreSQL; SpatiaLite SQL for SQLite | Pushes spatial filtering to the DB engine — no Python geometry library needed for extraction |
| GeoJSON serialisation | `json` (stdlib) | RFC 7946 output is straightforward dict serialisation; no third-party library needed |
| Property-based testing | `hypothesis` | Mature PBT library for Python; integrates with `pytest` |
| Unit testing | `pytest` | Standard Python test runner |

---

## Architecture

The tool is a pure CLI application with no server component. All I/O is local: one database connection and one output file.

```mermaid
graph TD
    CLI[CLI Entry Point] -->|parsed args| Explorer
    CLI -->|bbox + table hint| Extractor
    CLI -->|features + output path| Exporter

    Explorer -->|connection| DB[(Local Database\nPostgreSQL/PostGIS\nor SQLite/SpatiaLite)]
    Extractor -->|spatial query| DB
    Exporter -->|write| OutputFile[Output GeoJSON File]

    subgraph vic_health.export
        CLI
        Explorer
        Extractor
        Exporter
    end
```

### Data Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Explorer
    participant Extractor
    participant Exporter
    participant DB
    participant FS

    User->>CLI: vic-health export --bbox ... --output out.geojson
    CLI->>CLI: validate bbox args
    CLI->>Explorer: discover(conn, table_hint)
    Explorer->>DB: list tables/views + column metadata
    DB-->>Explorer: schema info
    Explorer-->>CLI: [relevant_table, ...]
    CLI->>Extractor: extract(conn, table, bbox)
    Extractor->>DB: ST_Intersects / MbrIntersects query
    DB-->>Extractor: rows (meshblock_id, geometry_wkt, score, sub_indicators)
    Extractor-->>CLI: [MeshblockRecord, ...]
    CLI->>Exporter: export(records, output_path, dry_run)
    Exporter->>Exporter: build FeatureCollection, deduplicate
    Exporter->>FS: write JSON (unless dry_run)
    Exporter-->>CLI: ExportResult(count, path)
    CLI-->>User: stdout summary + exit 0
```

---

## Components and Interfaces

### Explorer

Connects to the database and identifies tables suitable for extraction.

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class TableInfo:
    name: str
    geometry_column: str        # name of the geometry column
    meshblock_column: str       # name of the column mappable to meshblock_id

class DatabaseConnection(Protocol):
    """Thin protocol so Explorer/Extractor are testable without a real DB."""
    def execute(self, sql: str, params: tuple = ()) -> list[dict]: ...
    def close(self) -> None: ...

def connect(dsn: str) -> DatabaseConnection:
    """
    Parse the DSN and return the appropriate connection wrapper.
    Raises ConnectionError (with redacted DSN) on failure.
    """

def discover(conn: DatabaseConnection, table_hint: str | None = None) -> list[TableInfo]:
    """
    If table_hint is given, validate it exists and has required columns.
    Otherwise enumerate all tables/views and return those with a geometry
    column and a meshblock_id-mappable column.
    Raises DiscoveryError if no relevant tables are found.
    """
```

**Discovery heuristic** — a table is considered relevant when:
1. It has at least one column of a recognised geometry type (`geometry`, `geography` for PostGIS; `BLOB` with a `geometry_columns` entry for SpatiaLite).
2. It has at least one column whose name matches the pattern `meshblock_id`, `mb_id`, `mb21_code`, or similar (case-insensitive prefix/suffix match against a configurable list).

### Extractor

Queries the database for meshblock rows intersecting the bounding box.

```python
from dataclasses import dataclass, field

@dataclass
class BoundingBox:
    min_lng: float
    min_lat: float
    max_lng: float
    max_lat: float

@dataclass
class SubIndicator:
    name: str
    score: float

@dataclass
class MeshblockRecord:
    meshblock_id: str
    geometry_wkt: str           # WKT polygon in WGS84
    liveability_score: float
    sub_indicators: list[SubIndicator] = field(default_factory=list)

def validate_bbox(bbox: BoundingBox) -> None:
    """
    Raises ValueError with a descriptive message if the bbox is invalid:
    - min_lng >= max_lng
    - min_lat >= max_lat
    - any longitude outside [-180, 180]
    - any latitude outside [-90, 90]
    """

def extract(
    conn: DatabaseConnection,
    table: TableInfo,
    bbox: BoundingBox,
) -> list[MeshblockRecord]:
    """
    Issues a spatial intersection query and returns matching records.
    Raises ExtractionError if zero features are found.
    """
```

**SQL strategy** — the intersection query is dialect-aware:

- **PostgreSQL/PostGIS**: `WHERE ST_Intersects(geom_col, ST_MakeEnvelope($1,$2,$3,$4,4326))`
- **SQLite/SpatiaLite**: `WHERE MbrIntersects(geom_col, BuildMbr(?,?,?,?))`

Geometry is returned as WKT via `ST_AsText` / `AsText` so the Exporter can parse it without a geometry library.

### Exporter

Converts `MeshblockRecord` objects into a GeoJSON FeatureCollection and writes it to disk.

```python
import json
from pathlib import Path

@dataclass
class ExportResult:
    output_path: Path
    feature_count: int
    duplicates_removed: int

def build_feature(record: MeshblockRecord) -> dict:
    """
    Converts a MeshblockRecord to a GeoJSON Feature dict.
    Parses geometry_wkt to extract coordinate rings.
    """

def build_feature_collection(records: list[MeshblockRecord]) -> dict:
    """
    Deduplicates by meshblock_id (first-occurrence wins),
    builds each Feature, and wraps in a FeatureCollection dict.
    """

def export(
    records: list[MeshblockRecord],
    output_path: Path,
    dry_run: bool = False,
) -> ExportResult:
    """
    Builds the FeatureCollection, optionally writes to disk,
    prints summary to stdout.
    """
```

### CLI Entry Point

```python
# vic_health/export_cli.py
import argparse, sys

def build_parser() -> argparse.ArgumentParser: ...

def main(argv: list[str] | None = None) -> int:
    """
    Returns exit code (0 = success, non-zero = error).
    Wires Explorer → Extractor → Exporter.
    """
```

Registered in `pyproject.toml`:

```toml
[project.scripts]
vic-health-export = "vic_health.export_cli:main"
```

---

## Data Models

### BoundingBox

| Field | Type | Constraint |
|---|---|---|
| `min_lng` | float | [-180, 180), must be < max_lng |
| `min_lat` | float | [-90, 90), must be < max_lat |
| `max_lng` | float | (-180, 180] |
| `max_lat` | float | (-90, 90] |

### MeshblockRecord (internal)

| Field | Type | Notes |
|---|---|---|
| `meshblock_id` | str | Non-empty, unique within an export |
| `geometry_wkt` | str | WKT `POLYGON(...)` in WGS84 |
| `liveability_score` | float | Any finite number |
| `sub_indicators` | list[SubIndicator] | May be empty |

### SubIndicator (internal)

| Field | Type |
|---|---|
| `name` | str |
| `score` | float |

### GeoJSON Output (matches liveability map contract)

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[lng, lat], ...]]
      },
      "properties": {
        "meshblock_id": "MB123456",
        "liveability_score": 72.4,
        "sub_indicators": [
          { "name": "walkability", "score": 80.1 }
        ]
      }
    }
  ]
}
```

**Field rules** (matching `dataLoader.ts` expectations):
- `meshblock_id` — required non-empty string, unique per FeatureCollection.
- `liveability_score` — required finite number.
- `sub_indicators` — always present array (empty if no sub-indicator data).
- Coordinate order: `[longitude, latitude]` per RFC 7946.

### WKT → GeoJSON Coordinate Parsing

WKT polygons from the DB are parsed with a minimal regex/split approach (no external geometry library):

```
POLYGON ((lng1 lat1, lng2 lat2, ...))
→ [[[lng1, lat1], [lng2, lat2], ...]]
```

Multi-ring polygons (with holes) are supported by splitting on `)` boundaries.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Table Discovery Correctness

*For any* collection of table schemas (each described by a name and a list of column name/type pairs), the `discover` function SHALL return exactly those tables that have both a recognised geometry column and a meshblock-id-mappable column — no more, no less.

**Validates: Requirements 1.2**

---

### Property 2: Credential Redaction

*For any* database connection string that contains an embedded password (in the form `scheme://user:password@host/db`), when a connection failure occurs, the error message produced by the Explorer SHALL NOT contain the raw password string.

**Validates: Requirements 1.5**

---

### Property 3: Bounding Box Validation

*For any* four-tuple of floats `(min_lng, min_lat, max_lng, max_lat)`, `validate_bbox` SHALL accept the tuple if and only if `min_lng < max_lng`, `min_lat < max_lat`, `min_lng` and `max_lng` are in [-180, 180], and `min_lat` and `max_lat` are in [-90, 90]. All other tuples SHALL be rejected with a `ValueError`.

**Validates: Requirements 2.3**

---

### Property 4: Intersection Completeness and Soundness

*For any* bounding box and *for any* finite set of meshblock records with polygon geometries, the Extractor's spatial filter SHALL return exactly the records whose geometry intersects the bounding box — every intersecting record is included (completeness) and no non-intersecting record is included (soundness).

**Validates: Requirements 2.1, 2.5**

---

### Property 5: Feature Construction Correctness

*For any* `MeshblockRecord`, `build_feature` SHALL produce a dict where:
- `geometry.type == "Polygon"`
- every coordinate pair is `[float, float]` in `[longitude, latitude]` order
- `properties.meshblock_id` equals the record's `meshblock_id` and is a non-empty string
- `properties.liveability_score` equals the record's `liveability_score` and is a number
- `properties.sub_indicators` is a list where each element has a `name` string and a `score` number

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

---

### Property 6: Deduplication Preserves First Occurrence

*For any* list of `MeshblockRecord` objects (possibly containing duplicate `meshblock_id` values), `build_feature_collection` SHALL produce a FeatureCollection where all `meshblock_id` values are unique, and for every duplicated ID the retained feature corresponds to the first occurrence in the input list.

**Validates: Requirements 3.5**

---

### Property 7: Serialization Round-Trip

*For any* list of `MeshblockRecord` objects, serialising to a GeoJSON file and then parsing the file back as JSON SHALL produce a dict that is structurally equivalent to the original output — all `type` fields, `meshblock_id` values, `liveability_score` values, coordinate arrays, and `sub_indicators` arrays are preserved without loss or mutation.

**Validates: Requirements 5.1, 5.2, 4.2**

---

### Property 8: Printed Count Matches Written Count

*For any* list of `MeshblockRecord` objects exported to a file, the feature count printed to stdout by the Exporter SHALL equal the number of Feature objects in the `features` array of the written file.

**Validates: Requirements 4.5**

---

## Error Handling

| Scenario | Component | Behaviour |
|---|---|---|
| DB connection failure | Explorer | Print error with redacted DSN; exit 1 |
| No relevant tables found | Explorer | Print inspected table names; exit 1 |
| Invalid bbox values | CLI | Print validation error identifying the bad value; exit 1 |
| Zero features in bbox | Extractor | Print warning with bbox extent; exit 1 |
| Duplicate meshblock_ids | Exporter | Log warning listing duplicates; retain first occurrence; continue |
| Output directory missing | Exporter | Create parent dirs with `Path.mkdir(parents=True)` |
| Output file already exists | Exporter | Overwrite; print warning to stderr |
| File write failure | Exporter | Print error; exit 1 |
| Missing required CLI args | CLI (argparse) | Print missing-arg error; exit 2 (argparse default) |

All error messages are written to **stderr**; progress/summary messages go to **stdout**. This allows `--output /dev/stdout` piping without mixing error noise into the GeoJSON stream.

---

## Testing Strategy

### Dual Testing Approach

Unit tests cover specific examples, edge cases, and error conditions. Property-based tests (via `hypothesis`) verify universal properties across randomly generated inputs. Both are needed: unit tests catch concrete bugs, property tests verify general correctness.

### Property-Based Tests (hypothesis)

Each property from the Correctness Properties section maps to one `@given`-decorated test, configured with `settings(max_examples=100)`.

Tag format in test docstrings: `Feature: geojson-export-workflow, Property {N}: {property_text}`

| Test | Property | Key Generators |
|---|---|---|
| `test_discovery_correctness` | P1 | `st.lists(st.fixed_dictionaries({name, columns}))` |
| `test_credential_redaction` | P2 | `st.from_regex(r"postgresql://\w+:[^@]+@\w+/\w+")` |
| `test_bbox_validation` | P3 | `st.floats(-200, 200)` × 4, partitioned into valid/invalid |
| `test_intersection_filter` | P4 | `st.builds(BoundingBox, ...)` + `st.lists(st.builds(MeshblockRecord, ...))` |
| `test_feature_construction` | P5 | `st.builds(MeshblockRecord, ...)` |
| `test_deduplication` | P6 | `st.lists(st.builds(MeshblockRecord, ...))` with injected duplicates |
| `test_serialization_round_trip` | P7 | `st.lists(st.builds(MeshblockRecord, ...))` |
| `test_printed_count` | P8 | `st.lists(st.builds(MeshblockRecord, ...))` |

### Unit / Example-Based Tests

- Explorer connects to an in-memory SQLite DB and enumerates tables correctly.
- Explorer raises `DiscoveryError` when no relevant tables exist (1.3).
- Explorer prints discovered table names to stdout (1.4).
- Extractor returns empty result warning for a bbox with no matching features (2.4).
- Exporter creates parent directories when they don't exist (4.3).
- Exporter overwrites an existing file and prints a warning (4.4).
- Exporter writes nothing and prints count when `--dry-run` is set (6.4).
- CLI `--help` output contains all argument names and an example (6.2).
- CLI exits non-zero when required arguments are missing (6.3).
- CLI uses specified `--table` without running discovery (6.5).
- File write failure produces error message and non-zero exit (4.6).

### Integration Tests

- End-to-end: spin up an in-memory SpatiaLite DB with known fixtures, run the full CLI, assert the output file matches expected GeoJSON.
- PostgreSQL integration (optional, skipped if no PG available): same end-to-end test against a real PostGIS instance.
