# Extractor: queries the database for meshblock features within a bounding box

from vic_health.explorer import DatabaseConnection, _Sqlite3Connection
from vic_health.models import BoundingBox, MeshblockRecord, SubIndicator, TableConfig


class ExtractionError(Exception):
    """Raised when no features are found for the given bounding box."""


def validate_bbox(bbox: BoundingBox) -> None:
    if bbox.min_lng < -180 or bbox.min_lng > 180:
        raise ValueError(f"min_lng {bbox.min_lng} is outside [-180, 180]")
    if bbox.max_lng < -180 or bbox.max_lng > 180:
        raise ValueError(f"max_lng {bbox.max_lng} is outside [-180, 180]")
    if bbox.min_lat < -90 or bbox.min_lat > 90:
        raise ValueError(f"min_lat {bbox.min_lat} is outside [-90, 90]")
    if bbox.max_lat < -90 or bbox.max_lat > 90:
        raise ValueError(f"max_lat {bbox.max_lat} is outside [-90, 90]")
    if bbox.min_lng >= bbox.max_lng:
        raise ValueError(f"min_lng ({bbox.min_lng}) must be less than max_lng ({bbox.max_lng})")
    if bbox.min_lat >= bbox.max_lat:
        raise ValueError(f"min_lat ({bbox.min_lat}) must be less than max_lat ({bbox.max_lat})")


def _split_table(table: str) -> tuple[str, str]:
    """Split 'schema.table' into (schema, table). Defaults to 'public' if no schema given."""
    if "." in table:
        schema, name = table.split(".", 1)
        return schema, name
    return "public", table


def _detect_mb_column(conn: DatabaseConnection, table: str, is_sqlite: bool) -> str:
    """Return the meshblock id column name for a given table."""
    _CANDIDATES = ("mb_code_2021", "mb_code21", "mb_code", "mb_id", "mb21_code",
                   "mb_2021_code", "meshblock_id")
    if is_sqlite:
        rows = conn.execute(f"PRAGMA table_info({table})")
        cols = {r["name"].lower(): r["name"] for r in rows}
    else:
        schema, tname = _split_table(table)
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
            (schema, tname),
        )
        cols = {r["column_name"].lower(): r["column_name"] for r in rows}

    for candidate in _CANDIDATES:
        if candidate in cols:
            return cols[candidate]
    match = next((v for k, v in cols.items() if k.startswith("mb_code")), None)
    if match:
        return match
    raise ExtractionError(
        f"Cannot find a meshblock id column in table '{table}'. Columns: {list(cols.keys())}"
    )


def _detect_geom_column(conn: DatabaseConnection, table: str, is_sqlite: bool) -> str:
    """Return the geometry column name for a given table."""
    if is_sqlite:
        rows = conn.execute(f"PRAGMA table_info({table})")
        for r in rows:
            if "geometry" in r["type"].lower() or r["type"].lower() == "blob":
                return r["name"]
    else:
        schema, tname = _split_table(table)
        rows = conn.execute(
            "SELECT f_geometry_column FROM geometry_columns WHERE f_table_schema = %s AND f_table_name = %s",
            (schema, tname),
        )
        if rows:
            return rows[0]["f_geometry_column"]
    raise ExtractionError(f"Cannot find a geometry column in table '{table}'")


def _get_indicator_columns(conn: DatabaseConnection, table: str, mb_col: str,
                           liveability_col: str, is_sqlite: bool) -> list[str]:
    """Return all numeric columns except the mb id and liveability columns."""
    exclude = {mb_col.lower(), liveability_col.lower()}
    if is_sqlite:
        rows = conn.execute(f"PRAGMA table_info({table})")
        return [r["name"] for r in rows
                if r["name"].lower() not in exclude
                and r["type"].lower() in ("real", "float", "double", "numeric", "integer", "int")]
    else:
        schema, tname = _split_table(table)
        rows = conn.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema = %s AND table_name = %s
               AND data_type IN ('real','double precision','numeric','integer',
                                 'bigint','smallint','float')""",
            (schema, tname),
        )
        return [r["column_name"] for r in rows if r["column_name"].lower() not in exclude]


def extract(
    conn: DatabaseConnection,
    config: TableConfig,
    bbox: BoundingBox,
) -> list[MeshblockRecord]:
    """
    Joins the geometry table with the indicators table, returning one
    MeshblockRecord per meshblock that intersects the bounding box.
    All numeric indicator columns (except liveability) become sub_indicators.
    """
    is_sqlite = isinstance(conn, _Sqlite3Connection)
    ph = "?" if is_sqlite else "%s"

    geom_col = _detect_geom_column(conn, config.geometry_table, is_sqlite)
    geom_mb = _detect_mb_column(conn, config.geometry_table, is_sqlite)
    ind_mb = _detect_mb_column(conn, config.indicators_table, is_sqlite)

    # Detect the actual SRID from the data (geometry_columns may report 0 for unregistered tables)
    if is_sqlite:
        srid = 4326
    else:
        srid_rows = conn.execute(f"SELECT ST_SRID(g.{geom_col}) AS srid FROM {config.geometry_table} g LIMIT 1")
        srid = int(srid_rows[0]["srid"]) if srid_rows else 4326

    wkt_fn = f"AsText({geom_col})" if is_sqlite else f"ST_AsText(ST_Transform(g.{geom_col}, 4326))"

    if is_sqlite:
        intersects = f"MbrIntersects(g.{geom_col}, BuildMbr({ph},{ph},{ph},{ph}))"
        bbox_params = (bbox.min_lng, bbox.min_lat, bbox.max_lng, bbox.max_lat)
    elif srid == 4326:
        intersects = f"ST_Intersects(g.{geom_col}, ST_MakeEnvelope({ph},{ph},{ph},{ph},4326))"
        bbox_params = (bbox.min_lng, bbox.min_lat, bbox.max_lng, bbox.max_lat)
    else:
        # Transform the bbox envelope from 4326 into the table's SRID
        intersects = (
            f"ST_Intersects(g.{geom_col}, "
            f"ST_Transform(ST_MakeEnvelope({ph},{ph},{ph},{ph},4326), {srid}))"
        )
        bbox_params = (bbox.min_lng, bbox.min_lat, bbox.max_lng, bbox.max_lat)

    # Fetch geometry + liveability score in one query
    sql = f"""
        SELECT
            g.{geom_mb} AS meshblock_id,
            {wkt_fn} AS geometry_wkt,
            i.{config.liveability_column} AS liveability_score
        FROM {config.geometry_table} g
        JOIN {config.indicators_table} i ON i.{ind_mb} = g.{geom_mb}
        WHERE {intersects}
    """
    rows = conn.execute(sql, bbox_params)

    if not rows:
        raise ExtractionError(
            f"No features found within bounding box "
            f"[{bbox.min_lng}, {bbox.min_lat}, {bbox.max_lng}, {bbox.max_lat}]"
        )

    mb_ids = [str(r["meshblock_id"]) for r in rows]
    base = {str(r["meshblock_id"]): r for r in rows}

    # Fetch all other indicator columns in a second query
    ind_cols = _get_indicator_columns(conn, config.indicators_table, ind_mb,
                                      config.liveability_column, is_sqlite)
    indicators: dict[str, list[SubIndicator]] = {mb_id: [] for mb_id in mb_ids}

    if ind_cols:
        placeholders = ",".join([ph] * len(mb_ids))
        ind_sql = (
            f"SELECT {ind_mb}, {', '.join(ind_cols)} "
            f"FROM {config.indicators_table} "
            f"WHERE {ind_mb} IN ({placeholders})"
        )
        for row in conn.execute(ind_sql, tuple(mb_ids)):
            mb_id = str(row[ind_mb])
            if mb_id not in indicators:
                continue
            for col in ind_cols:
                val = row.get(col)
                if val is not None:
                    indicators[mb_id].append(SubIndicator(name=col, score=float(val)))

    return [
        MeshblockRecord(
            meshblock_id=mb_id,
            geometry_wkt=row["geometry_wkt"],
            liveability_score=float(row["liveability_score"]),
            sub_indicators=indicators.get(mb_id, []),
        )
        for mb_id, row in base.items()
    ]
