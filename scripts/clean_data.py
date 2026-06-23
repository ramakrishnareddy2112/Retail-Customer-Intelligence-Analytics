"""Create reconciled Parquet datasets from the raw retail workbook."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retail_analytics.cleaning import partition_masks, prepare_transactions  # noqa: E402
from retail_analytics.config import (  # noqa: E402
    INTERIM_DATA_DIR,
    PROCESSED_DATA_DIR,
    RAW_WORKBOOK_PATH,
    ensure_data_directories,
)
from retail_analytics.ingestion import load_workbook  # noqa: E402


SUMMARY_PATH = PROJECT_ROOT / "reports" / "cleaning_summary.json"


def write_parquet(frame, path: Path) -> None:
    """Write compressed Parquet and report its row count and file size."""
    frame.to_parquet(path, index=False, compression="snappy")
    print(f"  {path.name}: {len(frame):,} rows, {path.stat().st_size / 1_048_576:.1f} MB")


def main() -> None:
    ensure_data_directories()
    print("Loading both raw workbook sheets. This can take several minutes...")
    raw = load_workbook(RAW_WORKBOOK_PATH)
    print(f"Loaded {len(raw):,} raw rows.")

    print("Deduplicating, classifying, enriching, and flagging outliers...")
    cleaned, summary = prepare_transactions(raw)
    del raw

    print("Writing reconciled analytical datasets...")
    write_parquet(cleaned, INTERIM_DATA_DIR / "canonical_transactions.parquet")

    for dataset_name, mask in partition_masks(cleaned).items():
        write_parquet(
            cleaned.loc[mask],
            PROCESSED_DATA_DIR / f"{dataset_name}.parquet",
        )

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved cleaning summary: {SUMMARY_PATH}")

    if not summary["reconciliation"]["matches_unique_rows"]:
        raise RuntimeError("Partition reconciliation failed; outputs are not trustworthy.")

    print("Cleaning pipeline completed with successful row reconciliation.")


if __name__ == "__main__":
    main()

