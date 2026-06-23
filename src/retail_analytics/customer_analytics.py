"""RFM segmentation and cohort-retention analytics for identified customers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


EXPECTED_CUSTOMER_COUNT = 5_878
EXPECTED_MONETARY_VALUE_GBP = 17_374_804.27
MONETARY_TOLERANCE_GBP = 0.01
PARTIAL_MONTH = "2011-12"

SEGMENT_ORDER = [
    "Champions",
    "Loyal Customers",
    "Potential Loyalists",
    "New Customers",
    "Cannot Lose Them",
    "At Risk",
    "Hibernating",
    "Need Attention",
]

SEGMENT_RULES = {
    "Champions": (
        "R >= 4, F >= 4, M >= 4, and at least 2 completed orders."
    ),
    "Loyal Customers": (
        "R >= 3, F >= 4, M >= 3, and at least 2 completed orders."
    ),
    "Potential Loyalists": (
        "R >= 4, F between 2 and 3, M >= 2, and at least 2 completed orders."
    ),
    "New Customers": "R >= 4 and exactly 1 completed order.",
    "Cannot Lose Them": (
        "R <= 2, F >= 4, M >= 4, and at least 2 completed orders."
    ),
    "At Risk": "R <= 2 and either F >= 3 or M >= 3.",
    "Hibernating": "R <= 2, F <= 2, and M <= 2.",
    "Need Attention": "All remaining customers after the ordered rules above.",
}

SEGMENT_ACTIONS = {
    "Champions": (
        "Protect with early access, premium service, and referral invitations."
    ),
    "Loyal Customers": (
        "Use loyalty rewards, replenishment reminders, and cross-sell offers."
    ),
    "Potential Loyalists": (
        "Nurture with second-next-purchase offers and category recommendations."
    ),
    "New Customers": (
        "Send onboarding, product education, and a timely second-order incentive."
    ),
    "Cannot Lose Them": (
        "Prioritise personal reactivation and service recovery before discounting."
    ),
    "At Risk": (
        "Trigger win-back journeys based on past categories and purchase timing."
    ),
    "Hibernating": (
        "Use low-cost reactivation tests and suppress if engagement stays absent."
    ),
    "Need Attention": (
        "Monitor behaviour and use light-touch merchandising or survey prompts."
    ),
}

RFM_VALUE_COLUMNS = [
    "recency_days",
    "frequency_orders",
    "monetary_value_gbp",
    "average_order_value_gbp",
    "active_span_days",
    "units_purchased",
    "distinct_products",
    "r_score",
    "f_score",
    "m_score",
]


@dataclass(frozen=True)
class CustomerAnalyticsResults:
    """Container for customer analytics tables and validation metadata."""

    rfm: pd.DataFrame
    segment_summary: pd.DataFrame
    cohort_counts: pd.DataFrame
    cohort_retention: pd.DataFrame
    segment_action_plan: pd.DataFrame
    summary: dict[str, object]


def build_customer_analytics_results(
    sales: pd.DataFrame,
    expected_customer_count: int | None = None,
    expected_monetary_value_gbp: float | None = None,
) -> CustomerAnalyticsResults:
    """Build all customer analytics tables from completed identified sales."""
    identified_sales = _identified_completed_sales(sales)
    snapshot_date = identified_sales["invoice_date"].max().normalize() + pd.offsets.Day(1)

    rfm = build_rfm_table(identified_sales, snapshot_date)
    rfm = assign_business_segments(rfm)
    segment_summary = build_segment_summary(rfm)
    cohort_counts, cohort_retention, cohort_metadata = build_cohort_matrices(
        identified_sales
    )
    segment_action_plan = build_segment_action_plan()
    quality_gates = validate_customer_analytics(
        rfm,
        segment_summary,
        cohort_retention,
        expected_customer_count=expected_customer_count,
        expected_monetary_value_gbp=expected_monetary_value_gbp,
    )

    summary = build_summary(
        identified_sales=identified_sales,
        rfm=rfm,
        segment_summary=segment_summary,
        snapshot_date=snapshot_date,
        cohort_metadata=cohort_metadata,
        quality_gates=quality_gates,
    )
    return CustomerAnalyticsResults(
        rfm=rfm,
        segment_summary=segment_summary,
        cohort_counts=cohort_counts,
        cohort_retention=cohort_retention,
        segment_action_plan=segment_action_plan,
        summary=summary,
    )


def build_rfm_table(sales: pd.DataFrame, snapshot_date: pd.Timestamp) -> pd.DataFrame:
    """Calculate customer-level RFM features and quantile scores."""
    if sales.empty:
        raise ValueError("RFM analysis requires at least one completed identified sale.")

    rfm = (
        sales.groupby("customer_id", as_index=False)
        .agg(
            primary_country=("country", _mode_or_unknown),
            first_purchase=("invoice_date", "min"),
            last_purchase=("invoice_date", "max"),
            frequency_orders=("invoice_no", "nunique"),
            monetary_value_gbp=("line_revenue", "sum"),
            units_purchased=("quantity", "sum"),
            distinct_products=("stock_code", "nunique"),
        )
        .sort_values("customer_id", ignore_index=True)
    )
    rfm["recency_days"] = (
        snapshot_date - rfm["last_purchase"].dt.normalize()
    ).dt.days.astype("int64")
    rfm["average_order_value_gbp"] = (
        rfm["monetary_value_gbp"] / rfm["frequency_orders"]
    )
    rfm["active_span_days"] = (
        rfm["last_purchase"].dt.normalize()
        - rfm["first_purchase"].dt.normalize()
    ).dt.days.astype("int64")

    rfm["r_score"] = _quantile_score(rfm["recency_days"], higher_is_better=False)
    rfm["f_score"] = _quantile_score(rfm["frequency_orders"], higher_is_better=True)
    rfm["m_score"] = _quantile_score(rfm["monetary_value_gbp"], higher_is_better=True)
    rfm["rfm_score"] = rfm[["r_score", "f_score", "m_score"]].sum(axis=1).astype("int64")
    rfm["rfm_code"] = (
        rfm["r_score"].astype(str)
        + rfm["f_score"].astype(str)
        + rfm["m_score"].astype(str)
    )

    return rfm[
        [
            "customer_id",
            "primary_country",
            "first_purchase",
            "last_purchase",
            "recency_days",
            "frequency_orders",
            "monetary_value_gbp",
            "average_order_value_gbp",
            "active_span_days",
            "units_purchased",
            "distinct_products",
            "r_score",
            "f_score",
            "m_score",
            "rfm_score",
            "rfm_code",
        ]
    ]


def assign_business_segments(rfm: pd.DataFrame) -> pd.DataFrame:
    """Assign one mutually exclusive business segment to every customer."""
    segmented = rfm.copy()
    r = segmented["r_score"]
    f = segmented["f_score"]
    m = segmented["m_score"]
    repeat_customer = segmented["frequency_orders"].ge(2)

    conditions = [
        r.ge(4) & f.ge(4) & m.ge(4) & repeat_customer,
        r.ge(3) & f.ge(4) & m.ge(3) & repeat_customer,
        r.ge(4) & f.between(2, 3) & m.ge(2) & repeat_customer,
        r.ge(4) & segmented["frequency_orders"].eq(1),
        r.le(2) & f.ge(4) & m.ge(4) & repeat_customer,
        r.le(2) & (f.ge(3) | m.ge(3)),
        r.le(2) & f.le(2) & m.le(2),
    ]
    choices = [
        "Champions",
        "Loyal Customers",
        "Potential Loyalists",
        "New Customers",
        "Cannot Lose Them",
        "At Risk",
        "Hibernating",
    ]
    segmented["segment"] = np.select(conditions, choices, default="Need Attention")
    segmented["segment"] = pd.Categorical(
        segmented["segment"], categories=SEGMENT_ORDER, ordered=True
    )
    return segmented.sort_values(["segment", "monetary_value_gbp"], ascending=[True, False])


def build_segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    """Aggregate customer value and behaviour by business segment."""
    summary = (
        rfm.groupby("segment", observed=False)
        .agg(
            customer_count=("customer_id", "size"),
            monetary_value_gbp=("monetary_value_gbp", "sum"),
            average_monetary_value_gbp=("monetary_value_gbp", "mean"),
            average_order_value_gbp=("average_order_value_gbp", "mean"),
            median_recency_days=("recency_days", "median"),
            average_frequency_orders=("frequency_orders", "mean"),
            units_purchased=("units_purchased", "sum"),
            average_distinct_products=("distinct_products", "mean"),
        )
        .reset_index()
    )
    total_customers = int(summary["customer_count"].sum())
    total_revenue = float(summary["monetary_value_gbp"].sum())
    summary["customer_share_pct"] = 100 * summary["customer_count"] / total_customers
    summary["revenue_share_pct"] = 100 * summary["monetary_value_gbp"] / total_revenue
    summary["segment_rule"] = summary["segment"].map(SEGMENT_RULES)
    summary["recommended_action"] = summary["segment"].map(SEGMENT_ACTIONS)
    return summary[
        [
            "segment",
            "customer_count",
            "customer_share_pct",
            "monetary_value_gbp",
            "revenue_share_pct",
            "average_monetary_value_gbp",
            "average_order_value_gbp",
            "median_recency_days",
            "average_frequency_orders",
            "units_purchased",
            "average_distinct_products",
            "segment_rule",
            "recommended_action",
        ]
    ]


def build_segment_action_plan() -> pd.DataFrame:
    """Create a stakeholder-ready action plan for every segment."""
    priority = {
        "Champions": "Protect",
        "Loyal Customers": "Grow",
        "Potential Loyalists": "Nurture",
        "New Customers": "Onboard",
        "Cannot Lose Them": "Recover",
        "At Risk": "Win back",
        "Hibernating": "Test",
        "Need Attention": "Monitor",
    }
    rows = [
        {
            "segment": segment,
            "priority": priority[segment],
            "rule": SEGMENT_RULES[segment],
            "recommended_action": SEGMENT_ACTIONS[segment],
        }
        for segment in SEGMENT_ORDER
    ]
    return pd.DataFrame(rows)


def build_cohort_matrices(
    sales: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Build monthly cohort count and retention matrices."""
    customer_acquisition = (
        sales.groupby("customer_id")["invoice_date"].min().dt.to_period("M")
    )
    customer_months = (
        sales[["customer_id", "invoice_date"]]
        .assign(purchase_month=lambda data: data["invoice_date"].dt.to_period("M"))
        .drop_duplicates(["customer_id", "purchase_month"])
        .merge(
            customer_acquisition.rename("acquisition_month"),
            left_on="customer_id",
            right_index=True,
            how="left",
        )
    )
    customer_months["cohort_month_index"] = _month_index(
        customer_months["acquisition_month"], customer_months["purchase_month"]
    )

    observed = (
        customer_months.groupby(["acquisition_month", "cohort_month_index"])
        .agg(customers=("customer_id", "nunique"))
        .reset_index()
    )
    acquisition_months = (
        customer_acquisition.drop_duplicates().sort_values().reset_index(drop=True)
    )
    latest_purchase_month = sales["invoice_date"].max().to_period("M")
    max_index = int(
        _month_index(
            pd.Series([acquisition_months.min()]),
            pd.Series([latest_purchase_month]),
        ).iloc[0]
    )

    counts = pd.DataFrame(index=acquisition_months.astype(str), columns=range(max_index + 1))
    counts.index.name = "acquisition_month"
    for acquisition_month in acquisition_months:
        observable_months = int(
            _month_index(
                pd.Series([acquisition_month]),
                pd.Series([latest_purchase_month]),
            ).iloc[0]
        )
        counts.loc[str(acquisition_month), list(range(observable_months + 1))] = 0

    for row in observed.itertuples(index=False):
        counts.loc[str(row.acquisition_month), int(row.cohort_month_index)] = int(
            row.customers
        )

    cohort_sizes = customer_acquisition.value_counts().sort_index()
    cohort_sizes.index = cohort_sizes.index.astype(str)
    retention = counts.astype("float64").div(cohort_sizes, axis=0) * 100

    counts.columns = [f"month_{column}" for column in counts.columns]
    retention.columns = [f"month_{column}" for column in retention.columns]
    counts = counts.astype("Int64").reset_index()
    retention = retention.round(2).reset_index()

    metadata = {
        "acquisition_months": int(len(acquisition_months)),
        "first_acquisition_month": str(acquisition_months.min()),
        "latest_purchase_month": str(latest_purchase_month),
        "max_cohort_month_index": max_index,
        "partial_month": PARTIAL_MONTH,
        "partial_month_note": (
            "December 2011 contains purchases only through 2011-12-09; any "
            "retention cell whose purchase month is 2011-12 is partial."
        ),
    }
    return counts, retention, metadata


def validate_customer_analytics(
    rfm: pd.DataFrame,
    segment_summary: pd.DataFrame,
    cohort_retention: pd.DataFrame,
    expected_customer_count: int | None = EXPECTED_CUSTOMER_COUNT,
    expected_monetary_value_gbp: float | None = EXPECTED_MONETARY_VALUE_GBP,
    tolerance_gbp: float = MONETARY_TOLERANCE_GBP,
) -> dict[str, object]:
    """Run quality gates for the customer analytics phase."""
    customer_count = int(rfm["customer_id"].nunique())
    duplicate_customer_ids = int(rfm["customer_id"].duplicated().sum())
    missing_rfm_values = int(rfm[RFM_VALUE_COLUMNS].isna().sum().sum())
    segment_total = int(segment_summary["customer_count"].sum())
    missing_segments = int(rfm["segment"].isna().sum())
    monetary_total = float(rfm["monetary_value_gbp"].sum())

    month_columns = _month_columns(cohort_retention)
    retention_values = cohort_retention[month_columns].astype("float64").to_numpy()
    invalid_retention_cells = int(
        np.nansum((retention_values < 0) | (retention_values > 100))
    )

    gates = {
        "customer_count": {
            "actual": customer_count,
            "expected": expected_customer_count,
            "passed": (
                True
                if expected_customer_count is None
                else customer_count == expected_customer_count
            ),
        },
        "duplicate_customer_ids": {
            "actual": duplicate_customer_ids,
            "expected": 0,
            "passed": duplicate_customer_ids == 0,
        },
        "missing_rfm_values": {
            "actual": missing_rfm_values,
            "expected": 0,
            "passed": missing_rfm_values == 0,
        },
        "segment_counts_reconcile": {
            "segment_total": segment_total,
            "customer_total": customer_count,
            "missing_segments": missing_segments,
            "passed": segment_total == customer_count and missing_segments == 0,
        },
        "monetary_value_reconciliation": {
            "actual_gbp": round(monetary_total, 2),
            "expected_gbp": expected_monetary_value_gbp,
            "difference_gbp": (
                None
                if expected_monetary_value_gbp is None
                else round(monetary_total - expected_monetary_value_gbp, 6)
            ),
            "passed": (
                True
                if expected_monetary_value_gbp is None
                else abs(monetary_total - expected_monetary_value_gbp) <= tolerance_gbp
            ),
        },
        "cohort_retention_bounds": {
            "invalid_cells": invalid_retention_cells,
            "minimum_pct": round(float(np.nanmin(retention_values)), 2),
            "maximum_pct": round(float(np.nanmax(retention_values)), 2),
            "passed": invalid_retention_cells == 0,
        },
    }
    gates["all_passed"] = bool(
        all(gate["passed"] for key, gate in gates.items() if key != "all_passed")
    )
    return gates


def build_summary(
    identified_sales: pd.DataFrame,
    rfm: pd.DataFrame,
    segment_summary: pd.DataFrame,
    snapshot_date: pd.Timestamp,
    cohort_metadata: dict[str, object],
    quality_gates: dict[str, object],
) -> dict[str, object]:
    """Create a JSON-serialisable executive summary."""
    segment_totals = {
        str(row.segment): int(row.customer_count)
        for row in segment_summary.itertuples(index=False)
    }
    return {
        "source": "data/processed/customer_sales.parquet",
        "identified_completed_sales_rows": int(len(identified_sales)),
        "snapshot_date": snapshot_date.date().isoformat(),
        "customers": int(rfm["customer_id"].nunique()),
        "first_purchase": pd.Timestamp(rfm["first_purchase"].min()).date().isoformat(),
        "last_purchase": pd.Timestamp(rfm["last_purchase"].max()).date().isoformat(),
        "total_monetary_value_gbp": round(float(rfm["monetary_value_gbp"].sum()), 2),
        "average_recency_days": round(float(rfm["recency_days"].mean()), 2),
        "average_frequency_orders": round(float(rfm["frequency_orders"].mean()), 2),
        "average_customer_value_gbp": round(float(rfm["monetary_value_gbp"].mean()), 2),
        "segment_totals": segment_totals,
        "segment_rules": SEGMENT_RULES,
        "cohort_retention": cohort_metadata,
        "quality_gates": quality_gates,
    }


def _identified_completed_sales(sales: pd.DataFrame) -> pd.DataFrame:
    required = {
        "customer_id",
        "invoice_date",
        "invoice_no",
        "country",
        "stock_code",
        "quantity",
        "line_revenue",
    }
    missing = required - set(sales.columns)
    if missing:
        raise ValueError(f"Customer sales data is missing required columns: {sorted(missing)}")

    mask = sales["customer_id"].notna()
    if "has_customer_id" in sales.columns:
        mask &= sales["has_customer_id"].fillna(False).astype(bool)
    if "is_completed_sale" in sales.columns:
        mask &= sales["is_completed_sale"].fillna(False).astype(bool)
    if "transaction_type" in sales.columns:
        mask &= sales["transaction_type"].eq("completed_sale")

    identified = sales.loc[mask].copy()
    identified["invoice_date"] = pd.to_datetime(identified["invoice_date"])
    if identified.empty:
        raise ValueError("No identified completed sales were found.")
    return identified


def _quantile_score(series: pd.Series, higher_is_better: bool) -> pd.Series:
    ranked = series.rank(method="first", ascending=higher_is_better)
    if len(ranked) < 5:
        percent_rank = ranked.rank(method="first", pct=True)
        return np.ceil(percent_rank * 5).clip(1, 5).astype("int64")
    return pd.qcut(ranked, q=5, labels=range(1, 6)).astype("int64")


def _mode_or_unknown(series: pd.Series) -> str:
    mode = series.dropna().mode()
    return str(mode.iloc[0]) if not mode.empty else "Unknown"


def _month_index(
    acquisition_month: pd.Series, purchase_month: pd.Series
) -> pd.Series:
    return (
        (purchase_month.dt.year - acquisition_month.dt.year) * 12
        + (purchase_month.dt.month - acquisition_month.dt.month)
    ).astype("int64")


def _month_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if str(column).startswith("month_")]
