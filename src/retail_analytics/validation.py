"""Raw data profiling and validation metrics."""

from __future__ import annotations

from typing import Any

import pandas as pd


TRANSACTION_IDENTITY_COLUMNS = [
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "invoice_date",
    "unit_price",
    "customer_id",
    "country",
]


def profile_transactions(transactions: pd.DataFrame) -> dict[str, Any]:
    """Build a JSON-serialisable profile without changing transaction rows."""
    total_rows = len(transactions)
    completed = transactions["is_completed_sale"]
    returns = transactions["is_return"]
    anonymous = transactions["customer_id"].isna()
    within_sheet_identity = [*TRANSACTION_IDENTITY_COLUMNS, "source_sheet"]

    return {
        "row_counts": {
            "total": total_rows,
            "exact_duplicates_within_sheet": int(
                transactions.duplicated(subset=within_sheet_identity).sum()
            ),
            "exact_duplicates_across_workbook": int(
                transactions.duplicated(subset=TRANSACTION_IDENTITY_COLUMNS).sum()
            ),
            "completed_sales": int(completed.sum()),
            "returns_or_cancellations": int(returns.sum()),
            "anonymous_rows": int(anonymous.sum()),
            "non_positive_price_rows": int(transactions["unit_price"].le(0).sum()),
            "non_positive_quantity_rows": int(transactions["quantity"].le(0).sum()),
            "unparseable_date_rows": int(transactions["invoice_date"].isna().sum()),
        },
        "coverage": {
            "minimum_invoice_date": _timestamp_or_none(transactions["invoice_date"].min()),
            "maximum_invoice_date": _timestamp_or_none(transactions["invoice_date"].max()),
            "source_sheets": sorted(transactions["source_sheet"].dropna().unique().tolist()),
            "countries": int(transactions["country"].nunique(dropna=True)),
            "products": int(transactions["stock_code"].nunique(dropna=True)),
            "customers": int(transactions["customer_id"].nunique(dropna=True)),
            "invoices": int(transactions["invoice_no"].nunique(dropna=True)),
        },
        "missing_values": {
            column: {
                "count": int(transactions[column].isna().sum()),
                "percent": round(float(transactions[column].isna().mean() * 100), 4),
            }
            for column in transactions.columns
            if transactions[column].isna().any()
        },
        "raw_value_totals_gbp": {
            "all_signed_lines": round(float(transactions["line_revenue"].sum()), 2),
            "completed_sales": round(float(transactions.loc[completed, "line_revenue"].sum()), 2),
            "returns_or_cancellations": round(float(transactions.loc[returns, "line_revenue"].sum()), 2),
        },
    }


def validate_minimum_contract(transactions: pd.DataFrame) -> list[str]:
    """Return blocking contract failures; an empty list means validation passed."""
    failures: list[str] = []
    if transactions.empty:
        failures.append("The combined workbook contains no rows.")
    if transactions["invoice_date"].isna().all():
        failures.append("No invoice dates could be parsed.")
    if transactions["invoice_no"].isna().all():
        failures.append("No invoice identifiers were found.")
    if transactions["stock_code"].isna().all():
        failures.append("No product identifiers were found.")
    if not transactions["is_completed_sale"].any():
        failures.append("No valid completed-sale rows were identified.")
    if transactions["source_sheet"].nunique() < 2:
        failures.append("Expected two transaction-year worksheets in Online Retail II.")
    return failures


def _timestamp_or_none(value: object) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()
