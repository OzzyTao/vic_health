"""Convert a GeoPackage file to a flat GeoJSON FeatureCollection.

Reads the ``vichealth_niddrie`` table from a GeoPackage, parses the binary
geometry (GeoPackage header + WKB), reprojects from the source CRS to WGS 84,
and writes a GeoJSON file with ``mb_code`` and all indicator/scenario columns
as flat properties.
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


def convert_gpkg(gpkg_path: str | Path, output_path: str | Path) -> ConversionResult:
    """Convert a GeoPackage to a flat GeoJSON FeatureCollection.

    Parameters
    ----------
    gpkg_path:
        Path to the ``.gpkg`` file.
    output_path:
        Destination path for the GeoJSON output.

    Returns
    -------
    ConversionResult
        Summary with output path, feature count, and skipped count.
    """
    gpkg_path = Path(gpkg_path)
    output_path = Path(output_path)

    conn = sqlite3.connect(str(gpkg_path))
    conn.row_factory = sqlite3.Row

    # Identify the geometry column from GeoPackage metadata.
    meta_rows = conn.execute(
        "SELECT column_name, srs_id FROM gpkg_geometry_columns "
        "WHERE table_name = 'vichealth_niddrie'"
    ).fetchall()
    if not meta_rows:
        conn.close()
        raise ValueError(
            "No geometry column metadata found for table 'vichealth_niddrie'"
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
    col_info = conn.execute("PRAGMA table_info(vichealth_niddrie)").fetchall()
    property_columns = [
        row["name"]
        for row in col_info
        if row["name"].lower() not in _SKIP_COLUMNS
    ]

    # Fetch all rows.
    rows = conn.execute("SELECT * FROM vichealth_niddrie").fetchall()
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

_DEFAULT_GPKG = "liveability-map/public/data/vichealth_niddrie.gpkg"
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
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    gpkg_path = Path(args.gpkg)
    if not gpkg_path.exists():
        print(f"Error: GeoPackage not found: {gpkg_path}", file=sys.stderr)
        return 1

    try:
        result = convert_gpkg(gpkg_path, args.output)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Converted {result.feature_count} features to {result.output_path}")
    if result.skipped_count:
        print(f"  ({result.skipped_count} rows skipped due to geometry issues)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
