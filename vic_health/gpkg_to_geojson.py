"""Convert a GeoPackage file to a flat GeoJSON FeatureCollection.

Reads the features table declared in a GeoPackage's ``gpkg_contents``,
parses the binary geometry (GeoPackage header + WKB), reprojects from the
source CRS to WGS 84, and writes a GeoJSON file with ``mb_code`` and all
indicator/scenario columns as flat properties.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from pyproj import Transformer

logger = logging.getLogger(__name__)

# Columns that are not indicator/scenario data and should be excluded from
# the flat property output (geometry is handled separately).
_SKIP_COLUMNS = frozenset({"fid", "geom"})


@dataclass
class ConversionResult:
    """Summary returned by :func:`convert_gpkg`."""

    output_path: Path
    feature_count: int
    skipped_count: int


# ---------------------------------------------------------------------------
# GeoPackage binary geometry parsing
# ---------------------------------------------------------------------------

# Envelope byte-sizes indexed by the 3-bit envelope type field.
_ENVELOPE_SIZES: dict[int, int] = {
    0: 0,   # no envelope
    1: 32,  # minx, maxx, miny, maxy
    2: 48,  # + minz, maxz
    3: 48,  # + minm, maxm
    4: 64,  # + minz, maxz, minm, maxm
}


def _parse_gpkg_header(blob: bytes) -> tuple[int, int, int] | None:
    """Parse the GeoPackage binary geometry header.

    Returns ``(srid, wkb_offset, byte_order_flag)`` on success, or ``None``
    if the blob is too short or has an invalid magic number.

    *byte_order_flag* is 0 for big-endian, 1 for little-endian.
    """
    if len(blob) < 8:
        return None

    # Bytes 0-1: magic "GP"
    if blob[0:2] != b"GP":
        return None

    # Byte 3: flags
    flags = blob[3]
    byte_order = flags & 0x01
    bo = "<" if byte_order == 1 else ">"

    envelope_type = (flags >> 1) & 0x07
    env_size = _ENVELOPE_SIZES.get(envelope_type)
    if env_size is None:
        return None

    # Bytes 4-7: SRID
    srid = struct.unpack(f"{bo}i", blob[4:8])[0]

    wkb_offset = 8 + env_size
    if len(blob) < wkb_offset:
        return None

    return srid, wkb_offset, byte_order


def _parse_wkb_polygon(
    wkb: bytes,
) -> list[list[list[float]]] | None:
    """Parse a WKB Polygon into GeoJSON-style coordinate rings.

    Returns ``[[ring], ...]`` where each ring is ``[[x, y], ...]``, or
    ``None`` if the data is malformed.  Coordinates are returned in the
    source CRS — the caller is responsible for reprojection.
    """
    if len(wkb) < 5:
        return None

    wkb_byte_order = wkb[0]
    bo = "<" if wkb_byte_order == 1 else ">"

    geom_type = struct.unpack(f"{bo}I", wkb[1:5])[0]
    if geom_type != 3:  # 3 = Polygon
        return None

    offset = 5
    if offset + 4 > len(wkb):
        return None
    num_rings = struct.unpack(f"{bo}I", wkb[offset : offset + 4])[0]
    offset += 4

    rings: list[list[list[float]]] = []
    for _ in range(num_rings):
        if offset + 4 > len(wkb):
            return None
        num_points = struct.unpack(f"{bo}I", wkb[offset : offset + 4])[0]
        offset += 4

        ring: list[list[float]] = []
        for _ in range(num_points):
            if offset + 16 > len(wkb):
                return None
            x, y = struct.unpack(f"{bo}2d", wkb[offset : offset + 16])
            offset += 16
            ring.append([x, y])
        rings.append(ring)

    return rings


def _parse_gpkg_geometry(
    blob: bytes,
    transformer: Transformer | None,
) -> dict | None:
    """Parse a GeoPackage binary geometry blob into a GeoJSON geometry dict.

    If *transformer* is provided, coordinates are reprojected.  Returns
    ``None`` when the geometry cannot be parsed.
    """
    header = _parse_gpkg_header(blob)
    if header is None:
        return None

    _srid, wkb_offset, _byte_order = header
    wkb = blob[wkb_offset:]

    rings = _parse_wkb_polygon(wkb)
    if rings is None:
        return None

    if transformer is not None:
        reprojected_rings: list[list[list[float]]] = []
        for ring in rings:
            reprojected_ring: list[list[float]] = []
            for x, y in ring:
                lng, lat = transformer.transform(x, y)
                reprojected_ring.append([lng, lat])
            reprojected_rings.append(reprojected_ring)
        rings = reprojected_rings

    return {"type": "Polygon", "coordinates": rings}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _detect_features_table(conn: sqlite3.Connection) -> str:
    """Find the single ``features`` table declared in ``gpkg_contents``.

    Raises ``ValueError`` if there isn't exactly one.
    """
    rows = conn.execute(
        "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
    ).fetchall()
    if len(rows) != 1:
        raise ValueError(
            f"Expected exactly one features table in gpkg_contents, found {len(rows)}"
        )
    return rows[0]["table_name"]


def _centroid(rings: list[list[list[float]]]) -> tuple[float, float]:
    """Compute the centroid of a polygon's outer ring as ``(lng, lat)``."""
    outer_ring = rings[0]
    lngs = [pt[0] for pt in outer_ring]
    lats = [pt[1] for pt in outer_ring]
    return sum(lngs) / len(lngs), sum(lats) / len(lats)


def convert_gpkg(
    gpkg_path: str | Path,
    output_path: str | Path,
    bbox: tuple[float, float, float, float] | None = None,
) -> ConversionResult:
    """Convert a GeoPackage to a flat GeoJSON FeatureCollection.

    Parameters
    ----------
    gpkg_path:
        Path to the ``.gpkg`` file.
    output_path:
        Destination path for the GeoJSON output.
    bbox:
        Optional ``(min_lng, min_lat, max_lng, max_lat)`` in WGS 84. When
        given, only features whose centroid falls inside the box are kept —
        useful when a source table spans multiple disjoint regions.

    Returns
    -------
    ConversionResult
        Summary with output path, feature count, and skipped count.
    """
    gpkg_path = Path(gpkg_path)
    output_path = Path(output_path)

    conn = sqlite3.connect(str(gpkg_path))
    conn.row_factory = sqlite3.Row

    table_name = _detect_features_table(conn)

    # Identify the geometry column from GeoPackage metadata.
    meta_rows = conn.execute(
        "SELECT column_name, srs_id FROM gpkg_geometry_columns "
        "WHERE table_name = ?",
        (table_name,),
    ).fetchall()
    if not meta_rows:
        conn.close()
        raise ValueError(
            f"No geometry column metadata found for table '{table_name}'"
        )

    geom_col = meta_rows[0]["column_name"]
    srs_id = meta_rows[0]["srs_id"]

    # Build a reprojection transformer if the source CRS is not WGS 84.
    transformer: Transformer | None = None
    if srs_id != 4326:
        transformer = Transformer.from_crs(
            f"EPSG:{srs_id}", "EPSG:4326", always_xy=True
        )

    # Discover all non-geometry, non-fid columns.
    col_info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    property_columns = [
        row["name"]
        for row in col_info
        if row["name"].lower() not in _SKIP_COLUMNS
    ]

    # Fetch all rows.
    rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
    conn.close()

    features: list[dict] = []
    skipped = 0

    for row in rows:
        geom_blob = row[geom_col]
        mb_code = row["mb_code"]

        if geom_blob is None:
            logger.warning("Skipping mb_code=%s: geometry is NULL", mb_code)
            skipped += 1
            continue

        geometry = _parse_gpkg_geometry(geom_blob, transformer)
        if geometry is None:
            logger.warning(
                "Skipping mb_code=%s: geometry could not be parsed", mb_code
            )
            skipped += 1
            continue

        if bbox is not None:
            lng, lat = _centroid(geometry["coordinates"])
            min_lng, min_lat, max_lng, max_lat = bbox
            if not (min_lng <= lng <= max_lng and min_lat <= lat <= max_lat):
                continue

        properties: dict = {}
        for col in property_columns:
            properties[col] = row[col]

        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": properties,
            }
        )

    collection = {"type": "FeatureCollection", "features": features}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(collection), encoding="utf-8")

    logger.info(
        "Wrote %d features to %s (%d skipped)", len(features), output_path, skipped
    )

    return ConversionResult(
        output_path=output_path,
        feature_count=len(features),
        skipped_count=skipped,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

_DEFAULT_GPKG = "liveability-map/public/data/vichealth_bendigo.gpkg"
_DEFAULT_OUTPUT = "liveability-map/public/data/scenarios.geojson"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for converting a GeoPackage to GeoJSON.

    Returns 0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        prog="vic-health-gpkg2geojson",
        description="Convert a GeoPackage to a flat GeoJSON FeatureCollection.",
    )
    parser.add_argument(
        "--gpkg",
        metavar="PATH",
        default=_DEFAULT_GPKG,
        help=f"Path to the .gpkg file (default: {_DEFAULT_GPKG}).",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=_DEFAULT_OUTPUT,
        help=f"Destination path for the GeoJSON output (default: {_DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--bbox",
        metavar="MIN_LNG,MIN_LAT,MAX_LNG,MAX_LAT",
        default=None,
        help=(
            "Keep only features whose centroid falls within this WGS 84 "
            "bounding box. Useful when the source table spans multiple "
            "disjoint regions."
        ),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    gpkg_path = Path(args.gpkg)
    if not gpkg_path.exists():
        print(f"Error: GeoPackage not found: {gpkg_path}", file=sys.stderr)
        return 1

    bbox: tuple[float, float, float, float] | None = None
    if args.bbox is not None:
        try:
            parts = [float(p) for p in args.bbox.split(",")]
        except ValueError:
            print(f"Error: invalid --bbox value: {args.bbox}", file=sys.stderr)
            return 1
        if len(parts) != 4:
            print(
                f"Error: --bbox requires 4 comma-separated values, got {len(parts)}",
                file=sys.stderr,
            )
            return 1
        bbox = (parts[0], parts[1], parts[2], parts[3])

    try:
        result = convert_gpkg(gpkg_path, args.output, bbox=bbox)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Converted {result.feature_count} features to {result.output_path}")
    if result.skipped_count:
        print(f"  ({result.skipped_count} rows skipped due to geometry issues)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
