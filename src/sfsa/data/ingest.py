"""Raw data ingestion contracts."""

from pathlib import Path


def csv_paths(data_dir: str | Path) -> list[Path]:
    """Return deterministic CSV input paths from a data directory."""
    paths = sorted(Path(data_dir).glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    return paths
