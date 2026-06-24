"""Run non-parametric statistical tests on validated analytical outputs."""

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
from retail_analytics.statistical_analysis import build_statistical_analysis  # noqa: E402
from retail_analytics.statistical_visualization import create_statistical_charts  # noqa: E402


REPORT_DIR = PROJECT_ROOT / "reports" / "statistics"
CHART_DIR = PROJECT_ROOT / "images" / "statistics"
SUMMARY_PATH = REPORT_DIR / "statistical_summary.json"


def main() -> None:
    rfm_path = PROCESSED_DATA_DIR / "customer_rfm_segments.parquet"
    orders_path = PROJECT_ROOT / "reports" / "eda_tables" / "order_summary.csv"
    print("Loading validated customer RFM and order outputs...")
    rfm = pd.read_parquet(rfm_path)
    orders = pd.read_csv(orders_path)
    print(f"Loaded {len(rfm):,} customers and {len(orders):,} completed orders.")

    print("Running Spearman, Mann-Whitney U, and chi-square analyses...")
    results = build_statistical_analysis(rfm, orders)
    if not results.summary["quality_gates"]["all_passed"]:
        raise RuntimeError(
            "Statistical-analysis quality gates failed: "
            f"{json.dumps(results.summary['quality_gates'], indent=2)}"
        )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    results.hypothesis_tests.to_csv(REPORT_DIR / "hypothesis_tests.csv", index=False)
    results.correlation_matrix.to_csv(REPORT_DIR / "correlation_matrix.csv", index=True)
    SUMMARY_PATH.write_text(json.dumps(results.summary, indent=2), encoding="utf-8")
    charts = create_statistical_charts(rfm, orders, results.correlation_matrix, CHART_DIR)

    print(json.dumps(results.summary["quality_gates"], indent=2))
    print("Confirmatory hypothesis results:")
    print(
        results.hypothesis_tests.loc[
            results.hypothesis_tests["family"].eq("confirmatory_group_tests"),
            ["test_id", "statistic", "adjusted_p_value", "effect_size", "effect_magnitude"],
        ].to_string(index=False)
    )
    print(f"Saved statistical reports: {REPORT_DIR}")
    print(f"Saved {len(charts)} charts: {CHART_DIR}")


if __name__ == "__main__":
    main()
