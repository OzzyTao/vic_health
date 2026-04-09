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
