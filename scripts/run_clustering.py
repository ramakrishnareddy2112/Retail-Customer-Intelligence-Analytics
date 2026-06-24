"""Evaluate and build stable K-Means customer clusters."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retail_analytics.clustering import build_clustering_results  # noqa: E402
from retail_analytics.clustering_visualization import create_clustering_charts  # noqa: E402
from retail_analytics.config import PROCESSED_DATA_DIR  # noqa: E402


REPORT_DIR = PROJECT_ROOT / "reports" / "clustering"
CHART_DIR = PROJECT_ROOT / "images" / "clustering"
SUMMARY_PATH = REPORT_DIR / "clustering_summary.json"
CLUSTER_PARQUET_PATH = PROCESSED_DATA_DIR / "customer_clusters.parquet"
CLUSTER_CSV_PATH = PROCESSED_DATA_DIR / "customer_clusters.csv"


def main() -> None:
    rfm_path = PROCESSED_DATA_DIR / "customer_rfm_segments.parquet"
    print("Loading validated customer RFM output...")
    rfm = pd.read_parquet(rfm_path)
    print(f"Loaded {len(rfm):,} customers from {rfm_path}.")

    print("Evaluating K=2 through K=10 and five-seed stability...")
    results = build_clustering_results(rfm)
    if not results.summary["quality_gates"]["all_passed"]:
        raise RuntimeError(
            "Clustering quality gates failed: "
            f"{json.dumps(results.summary['quality_gates'], indent=2)}"
        )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    CLUSTER_PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.customer_clusters.to_parquet(CLUSTER_PARQUET_PATH, index=False, compression="snappy")
    results.customer_clusters.to_csv(CLUSTER_CSV_PATH, index=False)
    results.k_evaluation.to_csv(REPORT_DIR / "k_evaluation.csv", index=False)
    results.cluster_profiles.to_csv(REPORT_DIR / "cluster_profiles.csv", index=False)
    results.rfm_cluster_comparison.to_csv(
        REPORT_DIR / "rfm_cluster_comparison.csv", index=False
    )
    SUMMARY_PATH.write_text(json.dumps(results.summary, indent=2), encoding="utf-8")
    charts = create_clustering_charts(
        results.customer_clusters,
        results.k_evaluation,
        results.cluster_profiles,
        results.rfm_cluster_comparison,
        CHART_DIR,
    )

    print(json.dumps(results.summary["quality_gates"], indent=2))
    print(
        f"Metric-optimal benchmark K={results.summary['metric_optimal_k']}; "
        f"operational exported solution K={results.summary['operational_chosen_k']}."
    )
    print(json.dumps(results.summary["operational_chosen_metrics"], indent=2))
    print("Cluster profiles:")
    print(
        results.cluster_profiles[
            [
                "cluster_label",
                "customer_count",
                "customer_share_pct",
                "revenue_share_pct",
                "median_recency_days",
                "median_frequency_orders",
                "median_monetary_value_gbp",
                "repeat_customer_rate_pct",
                "dominant_rfm_segment",
                "recommended_action",
            ]
        ].to_string(index=False)
    )
    print(f"Saved customer clusters: {CLUSTER_PARQUET_PATH} and {CLUSTER_CSV_PATH}")
    print(f"Saved clustering reports: {REPORT_DIR}")
    print(f"Saved {len(charts)} charts: {CHART_DIR}")


if __name__ == "__main__":
    main()
