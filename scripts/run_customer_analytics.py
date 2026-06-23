"""Generate RFM segments, cohort retention, customer reports, and charts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _restart_with_project_venv_if_needed() -> None:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        return
    if Path(sys.executable).resolve() == venv_python.resolve():
        return
    try:
        import matplotlib  # noqa: F401
        import pandas  # noqa: F401
        import seaborn  # noqa: F401
    except ModuleNotFoundError:
        completed = subprocess.run([str(venv_python), *sys.argv], check=False)
        raise SystemExit(completed.returncode)


_restart_with_project_venv_if_needed()

import pandas as pd

from retail_analytics.config import PROCESSED_DATA_DIR  # noqa: E402
from retail_analytics.customer_analytics import (  # noqa: E402
    EXPECTED_CUSTOMER_COUNT,
    EXPECTED_MONETARY_VALUE_GBP,
    build_customer_analytics_results,
)
from retail_analytics.customer_visualization import create_customer_analytics_charts  # noqa: E402


REPORT_DIR = PROJECT_ROOT / "reports" / "customer_analytics"
CHART_DIR = PROJECT_ROOT / "images" / "customer_analytics"
SUMMARY_PATH = PROJECT_ROOT / "reports" / "customer_analytics_summary.json"
RFM_PARQUET_PATH = PROCESSED_DATA_DIR / "customer_rfm_segments.parquet"
RFM_CSV_PATH = PROCESSED_DATA_DIR / "customer_rfm_segments.csv"


def main() -> None:
    print("Loading identified completed customer sales...")
    sales_path = PROCESSED_DATA_DIR / "customer_sales.parquet"
    sales = pd.read_parquet(sales_path)
    print(f"Loaded {len(sales):,} sales lines from {sales_path}.")

    print("Building RFM scores, business segments, and cohort retention...")
    results = build_customer_analytics_results(
        sales,
        expected_customer_count=EXPECTED_CUSTOMER_COUNT,
        expected_monetary_value_gbp=EXPECTED_MONETARY_VALUE_GBP,
    )
    if not results.summary["quality_gates"]["all_passed"]:
        raise RuntimeError(
            "Customer analytics quality gates failed: "
            f"{json.dumps(results.summary['quality_gates'], indent=2)}"
        )

    print("Writing customer analytics tables...")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    RFM_PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.rfm.to_parquet(RFM_PARQUET_PATH, index=False, compression="snappy")
    results.rfm.to_csv(RFM_CSV_PATH, index=False)
    results.segment_summary.to_csv(REPORT_DIR / "segment_summary.csv", index=False)
    results.cohort_counts.to_csv(REPORT_DIR / "cohort_counts.csv", index=False)
    results.cohort_retention.to_csv(REPORT_DIR / "cohort_retention.csv", index=False)
    results.segment_action_plan.to_csv(
        REPORT_DIR / "segment_action_plan.csv", index=False
    )
    SUMMARY_PATH.write_text(json.dumps(results.summary, indent=2), encoding="utf-8")

    print("Creating customer analytics charts...")
    charts = create_customer_analytics_charts(
        results.rfm,
        results.segment_summary,
        results.cohort_retention,
        CHART_DIR,
    )

    print(json.dumps(results.summary["quality_gates"], indent=2))
    print(f"Saved RFM table: {RFM_PARQUET_PATH}")
    print(f"Saved RFM CSV: {RFM_CSV_PATH}")
    print(f"Saved report tables: {REPORT_DIR}")
    print(f"Saved {len(charts)} charts: {CHART_DIR}")
    print(f"Saved summary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
