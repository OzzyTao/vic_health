# CLI entry point for the GeoJSON export workflow

import argparse
import sys
import tomllib
from pathlib import Path

from vic_health.explorer import connect
from vic_health.extractor import ExtractionError, extract, validate_bbox
from vic_health.exporter import export, export_csv
from vic_health.models import BoundingBox, TableConfig


def load_config(path: Path) -> dict:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        print(f"Error: config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except tomllib.TOMLDecodeError as exc:
        print(f"Error: invalid TOML in {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def _require(cfg: dict, *keys: str) -> object:
    """Walk nested keys and raise a clear error if any is missing."""
    node = cfg
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            print(f"Error: missing config key: {'.'.join(keys)}", file=sys.stderr)
            sys.exit(1)
        node = node[key]
    return node


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vic-health-export",
        description="Export meshblock GeoJSON from a local spatial database using a TOML config file.",
        epilog=(
            "Example:\n"
            "  vic-health-export --config export_config.toml\n"
            "  vic-health-export --config export_config.toml --dry-run"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default="export_config.toml",
        help="Path to the TOML configuration file (default: export_config.toml).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract but do not write the output file — prints the feature count instead.",
    )
    parser.add_argument(
        "--csv",
        metavar="PATH",
        default=None,
        help=(
            "Also write a CSV file. If omitted, defaults to the GeoJSON output path "
            "with a .csv extension."
        ),
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip CSV output entirely.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    cfg = load_config(Path(args.config))

    dsn = str(_require(cfg, "database", "dsn"))

    raw_bbox = cfg.get("bbox", {})
    bbox = BoundingBox(
        min_lng=float(_require({"bbox": raw_bbox}, "bbox", "min_lng")),
        min_lat=float(_require({"bbox": raw_bbox}, "bbox", "min_lat")),
        max_lng=float(_require({"bbox": raw_bbox}, "bbox", "max_lng")),
        max_lat=float(_require({"bbox": raw_bbox}, "bbox", "max_lat")),
    )
    try:
        validate_bbox(bbox)
    except ValueError as exc:
        print(f"Error: invalid bounding box — {exc}", file=sys.stderr)
        return 1

    tables = cfg.get("tables", {})
    config = TableConfig(
        geometry_table=str(_require({"tables": tables}, "tables", "geometry")),
        indicators_table=str(_require({"tables": tables}, "tables", "indicators")),
        liveability_column=str(_require({"tables": tables}, "tables", "liveability_column")),
    )

    output_path = Path(str(_require(cfg, "output", "path")))

    try:
        conn = connect(dsn)
    except ConnectionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        records = extract(conn, config, bbox)
    except ExtractionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    export(records, output_path, dry_run=args.dry_run)

    if not args.no_csv:
        csv_path = Path(args.csv) if args.csv else output_path.with_suffix(".csv")
        export_csv(records, csv_path, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
