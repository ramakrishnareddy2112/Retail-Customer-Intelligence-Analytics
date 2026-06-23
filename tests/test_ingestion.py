import pandas as pd

from retail_analytics.cleaning import prepare_transactions
from retail_analytics.ingestion import standardise_frame
from retail_analytics.validation import profile_transactions, validate_minimum_contract


def sample_raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Invoice": ["100001", "C100002", "100003", "100004"],
            "StockCode": ["A1", "A1", "B2", "C3"],
            "Description": [" Blue Mug ", "Blue Mug", "Tea Set", "Gift Bag"],
            "Quantity": [2, -1, 1, 3],
            "InvoiceDate": [
                "2010-01-01 10:00",
                "2010-01-02 11:00",
                "2010-01-03 12:00",
                "2010-01-04 13:00",
            ],
            "Price": [5.0, 5.0, 0.0, 2.0],
            "Customer ID": [12345.0, 12345.0, None, 22222.0],
            "Country": ["United Kingdom"] * 4,
        }
    )


def test_standardise_frame_classifies_transaction_types() -> None:
    result = standardise_frame(sample_raw_frame(), "Year 2009-2010")

    assert result["is_completed_sale"].tolist() == [True, False, False, True]
    assert result["is_return"].tolist() == [False, True, False, False]
    assert result["customer_id"].tolist()[:2] == ["12345", "12345"]
    assert result.loc[0, "description"] == "Blue Mug"
    assert result.loc[0, "line_revenue"] == 10.0


def test_profile_reports_expected_counts() -> None:
    first_year = standardise_frame(sample_raw_frame(), "Year 2009-2010")
    second_year = standardise_frame(sample_raw_frame(), "Year 2010-2011")
    result = pd.concat([first_year, second_year], ignore_index=True)

    profile = profile_transactions(result)

    assert profile["row_counts"]["total"] == 8
    assert profile["row_counts"]["completed_sales"] == 4
    assert profile["row_counts"]["returns_or_cancellations"] == 2
    assert profile["row_counts"]["exact_duplicates_within_sheet"] == 0
    assert profile["row_counts"]["exact_duplicates_across_workbook"] == 4
    assert validate_minimum_contract(result) == []


def test_cleaning_deduplicates_across_sheets_and_reconciles() -> None:
    first_year = standardise_frame(sample_raw_frame(), "Year 2009-2010")
    second_year = standardise_frame(sample_raw_frame(), "Year 2010-2011")
    combined = pd.concat([first_year, second_year], ignore_index=True)

    cleaned, summary = prepare_transactions(combined)

    assert len(cleaned) == 4
    assert summary["exact_duplicates_removed"] == 4
    assert summary["reconciliation"]["matches_unique_rows"] is True
    assert summary["partitions"]["completed_sales"] == 2
    assert summary["partitions"]["returns_or_cancellations"] == 1
    assert summary["partitions"]["excluded_non_sales"] == 1
    assert summary["partitions"]["customer_sales"] == 2
