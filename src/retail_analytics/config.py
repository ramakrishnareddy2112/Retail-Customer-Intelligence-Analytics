"""Central paths and source metadata for the project."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

UCI_DATASET_URL = (
    "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
)
UCI_DATASET_PAGE = "https://archive.ics.uci.edu/dataset/502/online+retail+ii"
RAW_ARCHIVE_PATH = RAW_DATA_DIR / "online_retail_ii.zip"
RAW_WORKBOOK_NAME = "online_retail_II.xlsx"
RAW_WORKBOOK_PATH = RAW_DATA_DIR / RAW_WORKBOOK_NAME


def ensure_data_directories() -> None:
    """Create data directories required by the pipeline."""
    for path in (RAW_DATA_DIR, INTERIM_DATA_DIR, PROCESSED_DATA_DIR):
        path.mkdir(parents=True, exist_ok=True)

