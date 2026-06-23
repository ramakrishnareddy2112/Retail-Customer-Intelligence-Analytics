import pandas as pd

from retail_analytics.cleaning import prepare_transactions
from retail_analytics.ingestion import standardise_frame
from retail_analytics.sql_model import build_dimensions, build_fact_tables


def test_star_schema_counts_reconcile() -> None:
    raw = pd.DataFrame(
        {
            "Invoice": ["100001", "100001", "C100002", "100003"],
            "StockCode": ["A1", "B2", "A1", "C3"],
            "Description": ["Mug", "Tea Set", "Mug", "Bag"],
            "Quantity": [2, 1, -1, 3],
            "InvoiceDate": [
                "2010-01-01 10:00", "2010-01-01 10:00",
                "2010-01-02 11:00", "2010-01-03 12:00",
            ],
            "Price": [5.0, 8.0, 5.0, 0.0],
            "Customer ID": [12345.0, 12345.0, 12345.0, None],
            "Country": ["United Kingdom"] * 4,
        }
    )
    canonical = standardise_frame(raw, "Year 2009-2010")
    canonical, summary = prepare_transactions(canonical)
    dimensions = build_dimensions(canonical)
    facts = build_fact_tables(canonical, dimensions)

    assert len(facts["fact_sales"]) == summary["partitions"]["completed_sales"]
    assert len(facts["fact_returns"]) == summary["partitions"]["returns_or_cancellations"]
    assert len(facts["audit_exclusions"]) == summary["partitions"]["excluded_non_sales"]
    assert facts["fact_sales"]["product_key"].gt(0).all()
    assert facts["fact_sales"]["country_key"].gt(0).all()

