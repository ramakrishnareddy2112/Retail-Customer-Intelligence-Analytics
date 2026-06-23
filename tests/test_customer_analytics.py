from pathlib import Path

import pandas as pd
import pytest

from retail_analytics.customer_analytics import (
    EXPECTED_CUSTOMER_COUNT,
    EXPECTED_MONETARY_VALUE_GBP,
    assign_business_segments,
    build_customer_analytics_results,
)


def sample_customer_sales() -> pd.DataFrame:
    rows = [
        ("1001", "A1", "2011-11-20 10:00", "P1", 2, 40.0),
        ("1001", "A2", "2011-12-09 12:50", "P2", 1, 60.0),
        ("1002", "B1", "2011-12-01 09:00", "P1", 3, 45.0),
        ("1003", "C1", "2011-09-15 11:00", "P3", 5, 100.0),
        ("1003", "C2", "2011-10-15 11:00", "P4", 1, 25.0),
        ("1004", "D1", "2011-07-10 08:00", "P2", 1, 15.0),
        ("1005", "E1", "2011-12-08 14:00", "P5", 10, 200.0),
        ("1006", "F1", "2011-01-02 10:00", "P6", 2, 30.0),
        ("1006", "F2", "2011-11-01 10:00", "P7", 4, 80.0),
        ("1007", "G1", "2010-03-02 10:00", "P1", 2, 20.0),
        ("1008", "H1", "2011-12-09 09:00", "P8", 1, 10.0),
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "customer_id",
            "invoice_no",
            "invoice_date",
            "stock_code",
            "quantity",
            "line_revenue",
        ],
    )
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"])
    frame["country"] = "United Kingdom"
    frame["has_customer_id"] = True
    frame["is_completed_sale"] = True
    frame["transaction_type"] = "completed_sale"
    return frame


def test_customer_analytics_builds_rfm_and_cohorts() -> None:
    sales = sample_customer_sales()
    results = build_customer_analytics_results(
        sales,
        expected_customer_count=8,
        expected_monetary_value_gbp=float(sales["line_revenue"].sum()),
    )
    rfm = results.rfm.set_index("customer_id")

    assert results.summary["snapshot_date"] == "2011-12-10"
    assert len(results.rfm) == 8
    assert results.rfm["customer_id"].duplicated().sum() == 0
    assert rfm.loc["1001", "frequency_orders"] == 2
    assert rfm.loc["1001", "recency_days"] == 1
    assert rfm.loc["1007", "recency_days"] > rfm.loc["1001", "recency_days"]
    assert rfm.loc["1001", "r_score"] > rfm.loc["1007", "r_score"]
    assert results.cohort_retention["month_0"].dropna().eq(100).all()
    assert "2011-12" in results.summary["cohort_retention"]["partial_month_note"]
    assert results.summary["quality_gates"]["all_passed"] is True


def test_business_segments_are_mutually_exclusive() -> None:
    rfm = pd.DataFrame(
        {
            "customer_id": ["C", "L", "P", "N", "CL", "AR", "H", "NA"],
            "r_score": [5, 3, 4, 5, 1, 1, 1, 3],
            "f_score": [5, 4, 3, 1, 5, 3, 1, 2],
            "m_score": [5, 3, 2, 4, 5, 2, 1, 2],
            "frequency_orders": [5, 3, 2, 1, 5, 2, 1, 2],
            "monetary_value_gbp": [500, 300, 200, 120, 450, 160, 30, 90],
        }
    )

    segmented = assign_business_segments(rfm)
    segment_map = dict(zip(segmented["customer_id"], segmented["segment"].astype(str)))

    assert segment_map == {
        "C": "Champions",
        "L": "Loyal Customers",
        "P": "Potential Loyalists",
        "N": "New Customers",
        "CL": "Cannot Lose Them",
        "AR": "At Risk",
        "H": "Hibernating",
        "NA": "Need Attention",
    }
    assert segmented["segment"].isna().sum() == 0


def test_processed_customer_sales_pass_quality_gates_when_available() -> None:
    processed_path = Path("data/processed/customer_sales.parquet")
    if not processed_path.exists():
        pytest.skip("Processed customer sales parquet is not available.")

    sales = pd.read_parquet(processed_path)
    results = build_customer_analytics_results(
        sales,
        expected_customer_count=EXPECTED_CUSTOMER_COUNT,
        expected_monetary_value_gbp=EXPECTED_MONETARY_VALUE_GBP,
    )

    assert results.summary["quality_gates"]["all_passed"] is True
    assert results.summary["customers"] == EXPECTED_CUSTOMER_COUNT
    assert results.summary["total_monetary_value_gbp"] == EXPECTED_MONETARY_VALUE_GBP
