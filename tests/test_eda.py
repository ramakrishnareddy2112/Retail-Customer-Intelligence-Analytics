import pandas as pd

from retail_analytics.cleaning import prepare_transactions, partition_masks
from retail_analytics.eda import build_eda_results
from retail_analytics.ingestion import standardise_frame


def test_eda_summary_reconciles_small_dataset() -> None:
    raw = pd.DataFrame(
        {
            "Invoice": ["100001", "100001", "100002", "100003", "C100004"],
            "StockCode": ["A1", "B2", "A1", "C3", "A1"],
            "Description": ["Mug", "Tea Set", "Mug", "Bag", "Mug"],
            "Quantity": [2, 1, 4, 3, -1],
            "InvoiceDate": [
                "2010-01-01 10:00", "2010-01-01 10:00", "2010-02-01 11:00",
                "2010-02-02 12:00", "2010-02-03 13:00",
            ],
            "Price": [5.0, 8.0, 5.0, 2.0, 5.0],
            "Customer ID": [12345.0, 12345.0, 12345.0, None, 12345.0],
            "Country": ["United Kingdom"] * 5,
        }
    )
    canonical = standardise_frame(raw, "Year 2009-2010")
    canonical, _ = prepare_transactions(canonical)
    masks = partition_masks(canonical)
    results = build_eda_results(
        canonical.loc[masks["completed_sales"]], canonical.loc[masks["returns"]]
    )

    assert results.summary["orders"] == 3
    assert results.summary["identified_customers"] == 1
    assert results.summary["repeat_customer_rate_pct"] == 100.0
    assert len(results.tables["monthly_performance"]) == 2

