# Exporter: serialises MeshblockRecords into a GeoJSON FeatureCollection

import csv
import json
import logging
import re
import sys
from pathlib import Path

from vic_health.models import ExportResult, MeshblockRecord

logger = logging.getLogger(__name__)


def _parse_wkt_polygon(wkt: str) -> list[list[list[float]]]:
    """Parse a WKT POLYGON string into GeoJSON coordinate rings [[lng, lat], ...]."""
    inner = re.sub(r"(?i)^polygon\s*", "", wkt.strip())
    rings = re.findall(r"\(([^()]+)\)", inner)
    result = []
    for ring in rings:
        pairs = []
        for point in ring.split(","):
            parts = point.strip().split()
            if len(parts) >= 2:
                pairs.append([float(parts[0]), float(parts[1])])
        if pairs:
            result.append(pairs)
    return result


def build_feature(record: MeshblockRecord) -> dict:
    """Convert a MeshblockRecord to a GeoJSON Feature dict."""
    coordinates = _parse_wkt_polygon(record.geometry_wkt)
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": coordinates,
        },
        "properties": {
            "meshblock_id": record.meshblock_id,
            "liveability_score": record.liveability_score,
            "sub_indicators": [
                {"name": si.name, "score": si.score}
                for si in record.sub_indicators
            ],
        },
    }


def build_feature_collection(records: list[MeshblockRecord]) -> tuple[dict, int]:
    """
    Deduplicate by meshblock_id (first-occurrence wins), build each Feature,
    and wrap in a FeatureCollection dict.

    Returns (feature_collection_dict, duplicates_removed_count).
    """
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    unique_records: list[MeshblockRecord] = []

    for record in records:
        if record.meshblock_id in seen:
            duplicates.append(record.meshblock_id)
        else:
            seen[record.meshblock_id] = len(unique_records)
            unique_records.append(record)

    if duplicates:
        logger.warning("Duplicate meshblock_id values removed: %s", duplicates)

    features = [build_feature(r) for r in unique_records]
    collection = {"type": "FeatureCollection", "features": features}
    return collection, len(duplicates)


def export(
    records: list[MeshblockRecord],
    output_path: Path,
    dry_run: bool = False,
) -> ExportResult:
    """
    Build the FeatureCollection, optionally write to disk, print summary to stdout.
    """
    collection, duplicates_removed = build_feature_collection(records)
    feature_count = len(collection["features"])

    if dry_run:
        print(f"Dry run: {feature_count} feature(s) would be written (no file created).")
        return ExportResult(
            output_path=output_path,
            feature_count=feature_count,
            duplicates_removed=duplicates_removed,
        )

    if output_path.exists():
        print(f"Warning: overwriting existing file: {output_path}", file=sys.stderr)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        output_path.write_text(json.dumps(collection, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"Error: failed to write {output_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {feature_count} feature(s) to {output_path}")
    return ExportResult(
        output_path=output_path,
        feature_count=feature_count,
        duplicates_removed=duplicates_removed,
    )


def export_csv(
    records: list[MeshblockRecord],
    output_path: Path,
    dry_run: bool = False,
) -> None:
    """
    Write a flat CSV of meshblock records.

    Columns: meshblock_id, liveability_score, then one column per sub-indicator
    (named by the indicator's name). Sub-indicator columns are derived from the
    first record that has sub-indicators; missing values for a given row are left blank.
    """
    # Collect all sub-indicator names in order of first appearance
    indicator_names: list[str] = []
    seen_names: set[str] = set()
    for r in records:
        for si in r.sub_indicators:
            if si.name not in seen_names:
                indicator_names.append(si.name)
                seen_names.add(si.name)

    fieldnames = ["meshblock_id", "liveability_score"] + indicator_names
    feature_count = len(records)

    if dry_run:
        print(f"Dry run: {feature_count} row(s) would be written to CSV (no file created).")
        return

    if output_path.exists():
        print(f"Warning: overwriting existing file: {output_path}", file=sys.stderr)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                row: dict = {
                    "meshblock_id": record.meshblock_id,
                    "liveability_score": record.liveability_score,
                }
                for si in record.sub_indicators:
                    row[si.name] = si.score
                writer.writerow(row)
    except OSError as exc:
        print(f"Error: failed to write {output_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {feature_count} row(s) to {output_path}")
