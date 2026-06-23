"""Auditable cleaning rules for retail transaction analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from retail_analytics.validation import TRANSACTION_IDENTITY_COLUMNS


@dataclass(frozen=True)
class OutlierThresholds:
    """Upper IQR fences used for flags, not automatic row removal."""

    quantity_upper: float
    unit_price_upper: float
    line_revenue_upper: float


def prepare_transactions(transactions: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Deduplicate, enrich, classify, and flag the canonical transaction table."""
    input_rows = len(transactions)
    duplicate_mask = transactions.duplicated(
        subset=TRANSACTION_IDENTITY_COLUMNS, keep="first"
    )
    cleaned = transactions.loc[~duplicate_mask].copy()
    cleaned.reset_index(drop=True, inplace=True)
    cleaned.insert(0, "transaction_line_id", np.arange(1, len(cleaned) + 1))

    _add_date_features(cleaned)
    cleaned["transaction_type"] = np.select(
        [cleaned["is_completed_sale"], cleaned["is_return"]],
        ["completed_sale", "return_or_cancellation"],
        default="excluded_non_sale",
    )
    cleaned["exclusion_reason"] = _build_exclusion_reason(cleaned)

    thresholds = calculate_outlier_thresholds(cleaned)
    cleaned["is_quantity_outlier"] = (
        cleaned["is_completed_sale"] & cleaned["quantity"].gt(thresholds.quantity_upper)
    )
    cleaned["is_unit_price_outlier"] = (
        cleaned["is_completed_sale"] & cleaned["unit_price"].gt(thresholds.unit_price_upper)
    )
    cleaned["is_line_revenue_outlier"] = (
        cleaned["is_completed_sale"]
        & cleaned["line_revenue"].gt(thresholds.line_revenue_upper)
    )

    sales_mask = cleaned["transaction_type"].eq("completed_sale")
    returns_mask = cleaned["transaction_type"].eq("return_or_cancellation")
    excluded_mask = cleaned["transaction_type"].eq("excluded_non_sale")
    customer_sales_mask = sales_mask & cleaned["has_customer_id"]
    anonymous_sales_mask = sales_mask & ~cleaned["has_customer_id"]

    summary: dict[str, object] = {
        "input_rows": input_rows,
        "exact_duplicates_removed": int(duplicate_mask.sum()),
        "unique_rows": len(cleaned),
        "partitions": {
            "completed_sales": int(sales_mask.sum()),
            "returns_or_cancellations": int(returns_mask.sum()),
            "excluded_non_sales": int(excluded_mask.sum()),
            "customer_sales": int(customer_sales_mask.sum()),
            "anonymous_sales": int(anonymous_sales_mask.sum()),
        },
        "reconciliation": {
            "partition_total": int(sales_mask.sum() + returns_mask.sum() + excluded_mask.sum()),
            "matches_unique_rows": bool(
                sales_mask.sum() + returns_mask.sum() + excluded_mask.sum() == len(cleaned)
            ),
        },
        "completed_sales_value_gbp": round(
            float(cleaned.loc[sales_mask, "line_revenue"].sum()), 2
        ),
        "returns_value_gbp": round(
            float(cleaned.loc[returns_mask, "line_revenue"].sum()), 2
        ),
        "missing_customer_id_rows": int(cleaned["customer_id"].isna().sum()),
        "missing_description_rows": int(cleaned["description"].isna().sum()),
        "outlier_thresholds": asdict(thresholds),
        "outlier_flag_counts": {
            "quantity": int(cleaned["is_quantity_outlier"].sum()),
            "unit_price": int(cleaned["is_unit_price_outlier"].sum()),
            "line_revenue": int(cleaned["is_line_revenue_outlier"].sum()),
        },
    }
    return cleaned, summary


def calculate_outlier_thresholds(transactions: pd.DataFrame) -> OutlierThresholds:
    """Calculate Tukey upper fences from completed sales only."""
    sales = transactions.loc[transactions["is_completed_sale"]]
    return OutlierThresholds(
        quantity_upper=_upper_iqr_fence(sales["quantity"]),
        unit_price_upper=_upper_iqr_fence(sales["unit_price"]),
        line_revenue_upper=_upper_iqr_fence(sales["line_revenue"]),
    )


def partition_masks(transactions: pd.DataFrame) -> dict[str, pd.Series]:
    """Return mutually interpretable masks for writing analytical datasets."""
    sales = transactions["transaction_type"].eq("completed_sale")
    returns = transactions["transaction_type"].eq("return_or_cancellation")
    return {
        "completed_sales": sales,
        "returns": returns,
        "excluded_records": transactions["transaction_type"].eq("excluded_non_sale"),
        "customer_sales": sales & transactions["has_customer_id"],
        "anonymous_sales": sales & ~transactions["has_customer_id"],
    }


def _add_date_features(transactions: pd.DataFrame) -> None:
    invoice_date = transactions["invoice_date"]
    transactions["invoice_day"] = invoice_date.dt.normalize()
    transactions["year"] = invoice_date.dt.year.astype("Int16")
    transactions["quarter"] = invoice_date.dt.quarter.astype("Int8")
    transactions["month"] = invoice_date.dt.month.astype("Int8")
    transactions["year_month"] = invoice_date.dt.to_period("M").astype("string")
    transactions["day_of_month"] = invoice_date.dt.day.astype("Int8")
    transactions["day_of_week"] = invoice_date.dt.day_name().astype("category")
    transactions["hour"] = invoice_date.dt.hour.astype("Int8")


def _build_exclusion_reason(transactions: pd.DataFrame) -> pd.Series:
    reason = pd.Series(pd.NA, index=transactions.index, dtype="string")
    excluded = ~transactions["is_completed_sale"] & ~transactions["is_return"]
    reason.loc[excluded & transactions["unit_price"].le(0)] = "non_positive_price"
    reason.loc[excluded & transactions["quantity"].le(0)] = "non_positive_quantity"
    reason.loc[excluded & transactions["invoice_no"].isna()] = "missing_invoice"
    reason.loc[excluded & reason.isna()] = "other_invalid_non_sale"
    return reason


def _upper_iqr_fence(series: pd.Series) -> float:
    valid = series.dropna().astype(float)
    if valid.empty:
        return float("nan")
    first_quartile, third_quartile = valid.quantile([0.25, 0.75])
    return float(third_quartile + 1.5 * (third_quartile - first_quartile))

