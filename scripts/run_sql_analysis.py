"""Run quality and business SQL queries and export reviewable results."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retail_analytics.config import PROCESSED_DATA_DIR  # noqa: E402
from retail_analytics.sql_runner import execute_named_queries  # noqa: E402


DATABASE_PATH = PROCESSED_DATA_DIR / "retail_analytics.sqlite"
SQL_PATHS = [
    PROJECT_ROOT / "sql" / "02_quality_checks.sql",
    PROJECT_ROOT / "sql" / "03_business_queries.sql",
]
OUTPUT_DIR = PROJECT_ROOT / "reports" / "sql_results"
MANIFEST_PATH = PROJECT_ROOT / "reports" / "sql_query_manifest.json"


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"SQL database not found: {DATABASE_PATH}. Run build_sql_database.py first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Executing named SQL quality checks and business questions...")
    results = execute_named_queries(DATABASE_PATH, SQL_PATHS)

    manifest: dict[str, object] = {"database": str(DATABASE_PATH), "queries": {}}
    for name, frame in results.items():
        output_path = OUTPUT_DIR / f"{name}.csv"
        frame.to_csv(output_path, index=False)
        manifest["queries"][name] = {
            "rows": len(frame),
            "columns": frame.columns.tolist(),
            "output": str(output_path),
        }
        print(f"  {name}: {len(frame):,} rows -> {output_path.name}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Saved SQL manifest: {MANIFEST_PATH}")

    foreign_key_results = results["foreign_key_resolution"]
    if foreign_key_results["failure_count"].sum() != 0:
        raise RuntimeError("SQL foreign-key quality checks failed.")
    reconciliation = int(
        results["partition_reconciliation"].iloc[0]["reconciled_unique_rows"]
    )
    if reconciliation != 1_033_036:
        raise RuntimeError(f"Unexpected SQL row reconciliation: {reconciliation:,}")
    print("All SQL quality gates passed.")


if __name__ == "__main__":
    main()

