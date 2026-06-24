"""Build Power BI-ready CSV exports from validated project outputs."""

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
    if not venv_python.exists() or Path(sys.executable).resolve() == venv_python.resolve():
        return
    completed = subprocess.run([str(venv_python), *sys.argv], check=False)
    raise SystemExit(completed.returncode)


_restart_with_project_venv_if_needed()

import pandas as pd  # noqa: E402

from retail_analytics.dashboard_exports import (  # noqa: E402
    build_dashboard_exports,
    write_dashboard_exports,
)


PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DASHBOARD_DATA_DIR = PROJECT_ROOT / "dashboard" / "data"
SUMMARY_PATH = PROJECT_ROOT / "reports" / "dashboard_export_summary.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    print("Loading validated processed and analytical outputs...")
    sales = pd.read_parquet(PROCESSED_DIR / "completed_sales.parquet")
    returns = pd.read_parquet(PROCESSED_DIR / "returns.parquet")
    order_summary = pd.read_csv(PROJECT_ROOT / "reports" / "eda_tables" / "order_summary.csv")
    rfm = pd.read_parquet(PROCESSED_DIR / "customer_rfm_segments.parquet")
    clusters = pd.read_parquet(PROCESSED_DIR / "customer_clusters.parquet")
    cohort_counts = pd.read_csv(
        PROJECT_ROOT / "reports" / "customer_analytics" / "cohort_counts.csv"
    )
    cohort_retention = pd.read_csv(
        PROJECT_ROOT / "reports" / "customer_analytics" / "cohort_retention.csv"
    )
    segment_actions = pd.read_csv(
        PROJECT_ROOT / "reports" / "customer_analytics" / "segment_action_plan.csv"
    )
    cluster_profiles = pd.read_csv(
        PROJECT_ROOT / "reports" / "clustering" / "cluster_profiles.csv"
    )
    eda_summary = _load_json(PROJECT_ROOT / "reports" / "eda_summary.json")

    print("Building dashboard dimensions, facts, profiles, and KPI snapshot...")
    results = build_dashboard_exports(
        sales=sales,
        returns=returns,
        order_summary=order_summary,
        rfm=rfm,
        customer_clusters=clusters,
        cohort_counts=cohort_counts,
        cohort_retention=cohort_retention,
        segment_action_plan=segment_actions,
        cluster_profiles=cluster_profiles,
        eda_summary=eda_summary,
    )
    summary = write_dashboard_exports(results, DASHBOARD_DATA_DIR)
    if not summary["quality_gates"]["all_passed"]:
        raise RuntimeError(
            "Dashboard export quality gates failed: "
            f"{json.dumps(summary['quality_gates'], indent=2)}"
        )

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Generated dashboard tables:")
    for name, metadata in summary["exports"].items():
        print(
            f"  {metadata['filename']}: {metadata['rows']:,} rows, "
            f"{metadata['size_mb']:.4f} MB"
        )
    print(f"Total export size: {summary['total_export_size_mb']:.4f} MB")
    print(json.dumps(summary["quality_gates"], indent=2))
    print(f"Saved exports: {DASHBOARD_DATA_DIR}")
    print(f"Saved summary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
