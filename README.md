# vic-health GeoJSON Export Workflow

A CLI tool that connects to a local spatial database, discovers meshblock tables, extracts features within a bounding box, and writes a GeoJSON FeatureCollection for use with the liveability map.

---

## Prerequisites

- Python 3.12+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- A local PostgreSQL/PostGIS or SQLite/SpatiaLite database with meshblock data

---

## Part 1 — GeoJSON Export (Python CLI)

### Setup

Install Python dependencies:

```bash
uv sync
```

### Configuration

Copy and edit `export_config.toml` in the project root:

```toml
[database]
dsn = "postgresql://user:pass@localhost/mydb"

[bbox]
min_lng = 144.87014
min_lat = -37.75558
max_lng = 144.90954
max_lat = -37.72395

[tables]
geometry           = "boundaries.mb"
indicators         = "indicators.indicators_mb"
liveability_column = "urban_liveability_index"

[output]
path = "liveability-map/data/liveability.geojson"
```

- `database.dsn` — PostgreSQL (`postgresql://...`) or SQLite (`sqlite:///path/to/db`)
- `tables.geometry` — table with meshblock polygons
- `tables.indicators` — table containing all indicator columns including liveability
- `tables.liveability_column` — which column in the indicators table is the liveability score
- `output.path` — where the GeoJSON file is written (defaults to `liveability-map/data/liveability.geojson`)

### Running the Export

```bash
uv run vic-health-export
```

Uses `export_config.toml` by default. To use a different config file:

```bash
uv run vic-health-export --config path/to/config.toml
```

Dry run (extract but don't write the file):

```bash
uv run vic-health-export --dry-run
```

### GeoPackage to GeoJSON Converter

The project includes a converter that reads a GeoPackage file (`.gpkg`) and produces a flat GeoJSON FeatureCollection with all indicator×scenario columns as top-level properties. This is used to prepare data for the scenario comparison map.

```python
from vic_health.gpkg_to_geojson import convert_gpkg

result = convert_gpkg(
    "liveability-map/public/data/vichealth_niddrie.gpkg",
    "liveability-map/public/data/scenarios.geojson",
)
print(f"Wrote {result.feature_count} features ({result.skipped_count} skipped)")
```

You can also run it from the command line:

```bash
uv run vic-health-gpkg2geojson
```

This defaults to reading `liveability-map/public/data/vichealth_niddrie.gpkg` and writing `liveability-map/public/data/scenarios.geojson`. Override with `--gpkg` and `--output`:

```bash
uv run vic-health-gpkg2geojson --gpkg path/to/file.gpkg --output path/to/output.geojson
```

The converter:
- Reads the `vichealth_niddrie` table from the GeoPackage via `sqlite3`
- Parses GeoPackage binary geometry (header + WKB) and reprojects to WGS 84
- Preserves `mb_code` and all `{indicator}_{scenario}` / `{indicator}_diff_{scenario}` columns
- Skips rows with unparseable geometry (logs a warning) and reports a skip count

### Running Tests

```bash
uv run pytest
```

### Help

```bash
uv run vic-health-export --help
```

---

## Part 2 — Liveability Map (Vite + TypeScript)

The map is a browser-based app built with [Leaflet](https://leafletjs.com/) and [Vite](https://vite.dev/). It reads the GeoJSON file exported in Part 1 and renders an interactive choropleth map.

### Setup

Install Node dependencies (first time only):

```bash
cd liveability-map
npm install
```

### Development Server

Start the local dev server with hot reload:

```bash
cd liveability-map
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173) in your browser.

### Running Tests

Run the TypeScript test suite (uses [Vitest](https://vitest.dev/) and [fast-check](https://fast-check.dev/) for property-based testing):

```bash
cd liveability-map
npm test
```

### Scenario Comparison Map

The map features a side-by-side scenario comparison view. Users can select one of eight liveability indicators and two of four planning scenarios (Original, Probable, Community, Liveability), then visually compare choropleth maps rendered with a shared colour scale.

Key features:
- **Side-by-side map panes** — two synchronised Leaflet maps, each showing the same indicator under a different scenario
- **Indicator selector** — choose from 8 liveability indicators (defaults to Urban Liveability Index)
- **Scenario selectors** — independent left/right scenario selection (defaults: Original vs Liveability)
- **Shared colour scale** — identical values produce identical colours across both panes for fair comparison
- **Shared legend** — single legend reflecting the currently selected indicator
- **Click-to-inspect** — click any meshblock to see its indicator values and diff-from-original for the pane's scenario
- **Pan/zoom sync** — panning or zooming one pane automatically syncs the other

Data is sourced from `scenarios.geojson`, produced by the GeoPackage converter (see Part 1).

### Production Build

Compile and bundle for production:

```bash
cd liveability-map
npm run build
```

Output is written to `liveability-map/dist/`.

Preview the production build locally:

```bash
cd liveability-map
npm run preview
```

Then open [http://localhost:4173](http://localhost:4173).

---

## Typical End-to-End Workflow

1. Configure `export_config.toml` with your database and bounding box.
2. Run `uv run vic-health-export` to generate `liveability-map/data/liveability.geojson`.
3. `cd liveability-map && npm install` (first time only).
4. Run `npm run dev` and open [http://localhost:5173](http://localhost:5173) to view the map.
