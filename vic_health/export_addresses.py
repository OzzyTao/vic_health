import geopandas as gpd
from pathlib import Path
from sqlalchemy import create_engine

DATA_DIR = Path(__file__).parent.parent / "data"

# Database connection
engine = create_engine("postgresql://postgres:postgres@localhost:5432/observatory_2024")

# Load address points from database
addresses = gpd.read_postgis(
    "SELECT * FROM locations_raw.addresses",
    con=engine,
    geom_col="geom"
)

# Load the Niddrie clip shapefile
niddrie_clip = gpd.read_file(DATA_DIR / "Niddrie clip 1000 export.shp")

# Ensure both layers use the same CRS
if addresses.crs != niddrie_clip.crs:
    niddrie_clip = niddrie_clip.to_crs(addresses.crs)

# Clip address points to the Niddrie boundary
clipped_addresses = gpd.clip(addresses, niddrie_clip)

# Export clipped addresses to shapefile
clipped_addresses.to_file("niddrie_address_points_2024.shp")

print(f"Exported {len(clipped_addresses)} address points within the Niddrie boundary.")
# --- More efficient approach: push spatial filtering into the database ---
# Instead of loading all addresses into memory, use ST_Intersects in SQL

# First, get the Niddrie boundary as WKT in the database's CRS
# niddrie_clip_db = niddrie_clip.to_crs(addresses.crs)
# niddrie_wkt = niddrie_clip_db.union_all().wkt
# srid = addresses.crs.to_epsg()

# efficient_query = f"""
#     SELECT a.*
#     FROM locations_raw.addresses a
#     WHERE ST_Intersects(
#         a.geom,
#         ST_SetSRID(ST_GeomFromText('{niddrie_wkt}'), {srid})
#     )
# """

# clipped_addresses_efficient = gpd.read_postgis(
#     efficient_query,
#     con=engine,
#     geom_col="geom"
# )

# clipped_addresses_efficient.to_file("niddrie_address_points_efficient.shp")

# print(f"Efficient approach exported {len(clipped_addresses_efficient)} address points.")
