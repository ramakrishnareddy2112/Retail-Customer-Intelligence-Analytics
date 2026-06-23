"""Build and validate the SQLite star schema from canonical Parquet data."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retail_analytics.config import INTERIM_DATA_DIR, PROCESSED_DATA_DIR  # noqa: E402
from retail_analytics.sql_model import (  # noqa: E402
    build_dimensions,
    build_fact_tables,
    create_database,
)


CANONICAL_PATH = INTERIM_DATA_DIR / "canonical_transactions.parquet"
DATABASE_PATH = PROCESSED_DATA_DIR / "retail_analytics.sqlite"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "01_schema.sql"
QUALITY_SQL_PATH = PROJECT_ROOT / "sql" / "02_quality_checks.sql"
REPORT_PATH = PROJECT_ROOT / "reports" / "sql_model_summary.json"


def main() -> None:
    print("Loading canonical Parquet data...")
    canonical = pd.read_parquet(CANONICAL_PATH)
    print(f"Loaded {len(canonical):,} unique transaction lines.")

    print("Building conformed dimensions...")
    dimensions = build_dimensions(canonical)
    for name, frame in dimensions.items():
        print(f"  {name}: {len(frame):,} rows")

    print("Building fact and audit tables...")
    facts = build_fact_tables(canonical, dimensions)
    for name, frame in facts.items():
        print(f"  {name}: {len(frame):,} rows")

    print("Writing indexed SQLite database...")
    create_database(DATABASE_PATH, SCHEMA_PATH, dimensions, facts)

    with sqlite3.connect(DATABASE_PATH) as connection:
        table_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in [*dimensions, *facts]
        }
        sales_value = connection.execute(
            "SELECT ROUND(SUM(line_revenue), 2) FROM fact_sales"
        ).fetchone()[0]
        returns_value = connection.execute(
            "SELECT ROUND(SUM(signed_return_value), 2) FROM fact_returns"
        ).fetchone()[0]
        foreign_key_failures = len(connection.execute("PRAGMA foreign_key_check").fetchall())

    summary = {
        "database_path": str(DATABASE_PATH),
        "database_size_mb": round(DATABASE_PATH.stat().st_size / 1_048_576, 2),
        "table_counts": table_counts,
        "completed_sales_value_gbp": sales_value,
        "returns_value_gbp": returns_value,
        "foreign_key_failures": foreign_key_failures,
        "quality_check_sql": str(QUALITY_SQL_PATH),
    }
    REPORT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Saved SQL model summary: {REPORT_PATH}")


if __name__ == "__main__":
    main()

