from dataclasses import dataclass, field
from pathlib import Path


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
    geometry_wkt: str
    liveability_score: float
    sub_indicators: list[SubIndicator] = field(default_factory=list)


@dataclass
class TableConfig:
    """Explicit table configuration supplied by the user."""
    geometry_table: str       # table with meshblock geometry + mb id
    indicators_table: str     # table with all indicators (including liveability)
    liveability_column: str   # column in indicators_table that holds the liveability score


@dataclass
class ExportResult:
    output_path: Path
    feature_count: int
    duplicates_removed: int
