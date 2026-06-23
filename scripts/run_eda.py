"""Generate EDA tables, visualisations, and an executive metrics summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retail_analytics.config import PROCESSED_DATA_DIR  # noqa: E402
from retail_analytics.eda import build_eda_results  # noqa: E402
from retail_analytics.visualization import create_eda_charts  # noqa: E402


TABLE_DIR = PROJECT_ROOT / "reports" / "eda_tables"
CHART_DIR = PROJECT_ROOT / "images" / "eda"
SUMMARY_PATH = PROJECT_ROOT / "reports" / "eda_summary.json"


def main() -> None:
    print("Loading cleaned sales and returns Parquet datasets...")
    sales = pd.read_parquet(PROCESSED_DATA_DIR / "completed_sales.parquet")
    returns = pd.read_parquet(PROCESSED_DATA_DIR / "returns.parquet")
    print(f"Loaded {len(sales):,} sales lines and {len(returns):,} return lines.")

    print("Building executive metrics and aggregate EDA tables...")
    results = build_eda_results(sales, returns)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in results.tables.items():
        path = TABLE_DIR / f"{name}.csv"
        table.to_csv(path, index=False)
        print(f"  {name}: {len(table):,} rows")

    SUMMARY_PATH.write_text(json.dumps(results.summary, indent=2), encoding="utf-8")
    print("Creating 14 static charts and 2 interactive Plotly views...")
    charts = create_eda_charts(results.tables, results.summary, CHART_DIR)

    print(json.dumps(results.summary, indent=2))
    print(f"Saved EDA summary: {SUMMARY_PATH}")
    print(f"Saved {len(charts)} static charts: {CHART_DIR}")


if __name__ == "__main__":
    main()

