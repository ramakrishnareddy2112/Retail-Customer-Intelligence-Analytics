import json
from pathlib import Path

import pandas as pd
import pytest


DASHBOARD_DATA_DIR = Path("dashboard/data")
SUMMARY_PATH = Path("reports/dashboard_export_summary.json")
FILE_LIMIT_BYTES = 100 * 1024 * 1024

EXPECTED_COLUMNS = {
    "dim_date.csv": {
        "date", "year", "quarter", "month_number", "month_name", "year_month",
        "month_start", "is_partial_period",
    },
    "fact_orders.csv": {
        "order_id", "order_date", "month_start", "customer_id", "country",
        "order_revenue_gbp", "units_sold", "distinct_products", "line_count",
        "is_identified_customer",
    },
    "dim_customer.csv": {
        "customer_id", "first_purchase_date", "last_purchase_date", "recency_days",
        "frequency_orders", "monetary_value_gbp", "average_order_value_gbp",
        "units_purchased", "distinct_products", "is_repeat_customer", "r_score",
        "f_score", "m_score", "rfm_score", "rfm_segment", "cluster_id",
        "cluster_label",
    },
    "fact_product_month.csv": {
        "month_start", "stock_code", "description", "revenue_gbp", "units_sold",
        "orders", "identified_customers",
    },
    "fact_country_month.csv": {
        "month_start", "country", "revenue_gbp", "orders", "units_sold",
        "identified_customers",
    },
    "fact_returns_month.csv": {
        "month_start", "signed_return_value_gbp", "absolute_return_value_gbp",
        "return_lines", "returned_units",
    },
    "cohort_retention.csv": {
        "acquisition_month", "purchase_month", "cohort_month_index", "cohort_size",
        "active_customers", "retention_pct", "is_partial_period",
    },
    "segment_summary.csv": {
        "rfm_segment", "customer_count", "customer_share_pct",
        "historical_customer_value_gbp", "historical_value_share_pct",
        "median_recency_days", "median_frequency_orders",
        "median_monetary_value_gbp", "repeat_customer_rate_pct", "priority",
        "segment_rule", "recommended_action",
    },
    "cluster_summary.csv": {
        "cluster_id", "cluster_label", "customer_count", "customer_share_pct",
        "historical_customer_value_gbp", "historical_value_share_pct",
        "median_recency_days", "median_frequency_orders",
        "median_monetary_value_gbp", "repeat_customer_rate_pct",
        "dominant_rfm_segment", "dominant_rfm_segment_share_pct", "label_basis",
        "recommended_action",
    },
    "kpi_snapshot.csv": {
        "data_through_date", "completed_revenue_gbp", "completed_orders",
        "completed_units", "average_order_value_gbp", "median_order_value_gbp",
        "identified_customers", "repeat_customers", "repeat_customer_rate_pct",
        "identified_customer_revenue_gbp", "anonymous_revenue_gbp",
        "anonymous_revenue_share_pct", "signed_returns_value_gbp", "partial_period",
        "partial_period_note",
    },
}


def test_dashboard_export_package_has_required_schemas_and_safe_file_sizes() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    assert summary["quality_gates"]["all_passed"] is True
    assert set(summary["exports"]) == {
        filename.removesuffix(".csv") for filename in EXPECTED_COLUMNS
    }
    for filename, expected_columns in EXPECTED_COLUMNS.items():
        path = DASHBOARD_DATA_DIR / filename
        assert path.exists(), f"Missing dashboard export: {path}"
        assert path.stat().st_size < FILE_LIMIT_BYTES
        actual_columns = set(pd.read_csv(path, nrows=0).columns)
        assert actual_columns == expected_columns


def test_dashboard_export_totals_keys_labels_and_partial_period_reconcile() -> None:
    orders = pd.read_csv(
        DASHBOARD_DATA_DIR / "fact_orders.csv", dtype={"order_id": "string", "customer_id": "string"}
    )
    customers = pd.read_csv(
        DASHBOARD_DATA_DIR / "dim_customer.csv", dtype={"customer_id": "string"}
    )
    returns = pd.read_csv(DASHBOARD_DATA_DIR / "fact_returns_month.csv")
    segments = pd.read_csv(DASHBOARD_DATA_DIR / "segment_summary.csv")
    clusters = pd.read_csv(DASHBOARD_DATA_DIR / "cluster_summary.csv")
    dates = pd.read_csv(DASHBOARD_DATA_DIR / "dim_date.csv")

    assert len(orders) == 40_077
    assert orders["order_id"].is_unique
    assert orders["order_revenue_gbp"].sum() == pytest.approx(20_476_260.45, abs=0.01)
    assert int(orders["units_sold"].sum()) == 11_205_148
    assert orders["customer_id"].dropna().str.fullmatch(r"[^.]+|.*\.[^0]$").all()

    assert len(customers) == 5_878
    assert customers["customer_id"].is_unique
    assert int(customers["is_repeat_customer"].sum()) == 4_255
    assert customers["monetary_value_gbp"].sum() == pytest.approx(17_374_804.27, abs=0.01)
    assert customers[["rfm_segment", "cluster_label"]].notna().all().all()
    assert int(segments["customer_count"].sum()) == 5_878
    assert int(clusters["customer_count"].sum()) == 5_878
    assert returns["signed_return_value_gbp"].sum() == pytest.approx(-1_462_050.61, abs=0.01)

    december = dates.loc[dates["year_month"].eq("2011-12")]
    assert len(december) == 9
    assert december["is_partial_period"].all()
