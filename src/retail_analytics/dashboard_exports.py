"""Power BI-ready exports built from validated analytical outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_COMPLETED_REVENUE_GBP = 20_476_260.45
EXPECTED_COMPLETED_ORDERS = 40_077
EXPECTED_COMPLETED_UNITS = 11_205_148
EXPECTED_IDENTIFIED_CUSTOMERS = 5_878
EXPECTED_REPEAT_CUSTOMERS = 4_255
EXPECTED_IDENTIFIED_REVENUE_GBP = 17_374_804.27
EXPECTED_SIGNED_RETURNS_GBP = -1_462_050.61
EXPECTED_SEGMENT_TOTAL = 5_878
EXPECTED_CLUSTER_TOTAL = 5_878
PARTIAL_PERIOD = "2011-12"
GITHUB_FILE_LIMIT_BYTES = 100 * 1024 * 1024
MONETARY_TOLERANCE_GBP = 0.01


EXPORT_FILENAMES = {
    "dim_date": "dim_date.csv",
    "fact_orders": "fact_orders.csv",
    "dim_customer": "dim_customer.csv",
    "fact_product_month": "fact_product_month.csv",
    "fact_country_month": "fact_country_month.csv",
    "fact_returns_month": "fact_returns_month.csv",
    "cohort_retention": "cohort_retention.csv",
    "segment_summary": "segment_summary.csv",
    "cluster_summary": "cluster_summary.csv",
    "kpi_snapshot": "kpi_snapshot.csv",
}


@dataclass(frozen=True)
class DashboardExportResults:
    """Power BI tables plus their pre-write reconciliation summary."""

    tables: dict[str, pd.DataFrame]
    summary: dict[str, object]


def build_dashboard_exports(
    sales: pd.DataFrame,
    returns: pd.DataFrame,
    order_summary: pd.DataFrame,
    rfm: pd.DataFrame,
    customer_clusters: pd.DataFrame,
    cohort_counts: pd.DataFrame,
    cohort_retention: pd.DataFrame,
    segment_action_plan: pd.DataFrame,
    cluster_profiles: pd.DataFrame,
    eda_summary: dict[str, object],
) -> DashboardExportResults:
    """Build dashboard tables without changing validated analytical logic."""
    _validate_inputs(sales, returns, order_summary, rfm, customer_clusters)

    dim_date = build_date_dimension(sales)
    fact_orders = build_order_fact(order_summary)
    dim_customer = build_customer_dimension(rfm, customer_clusters)
    fact_product_month = build_product_month_fact(sales)
    fact_country_month = build_country_month_fact(sales)
    fact_returns_month = build_returns_month_fact(returns)
    cohort_long = build_cohort_retention_fact(cohort_counts, cohort_retention)
    segment_summary = build_segment_dashboard_summary(rfm, segment_action_plan)
    cluster_summary = build_cluster_dashboard_summary(cluster_profiles)
    kpi_snapshot = build_kpi_snapshot(eda_summary)

    tables = {
        "dim_date": dim_date,
        "fact_orders": fact_orders,
        "dim_customer": dim_customer,
        "fact_product_month": fact_product_month,
        "fact_country_month": fact_country_month,
        "fact_returns_month": fact_returns_month,
        "cohort_retention": cohort_long,
        "segment_summary": segment_summary,
        "cluster_summary": cluster_summary,
        "kpi_snapshot": kpi_snapshot,
    }
    quality_gates = validate_dashboard_tables(tables)
    summary = {
        "sources": {
            "completed_sales": "data/processed/completed_sales.parquet",
            "returns": "data/processed/returns.parquet",
            "orders": "reports/eda_tables/order_summary.csv",
            "rfm": "data/processed/customer_rfm_segments.parquet",
            "clusters": "data/processed/customer_clusters.parquet",
            "cohorts": "reports/customer_analytics/cohort_counts.csv and cohort_retention.csv",
            "validated_kpis": "reports/eda_summary.json",
        },
        "scope": {
            "customer_value_definition": "Historical completed-sales monetary value in GBP; not predictive CLV.",
            "outlier_treatment": "Validated outliers remain included in all export totals; no rows are deleted by this phase.",
            "partial_period": PARTIAL_PERIOD,
            "partial_period_note": str(eda_summary["partial_period_note"]),
        },
        "exports": {
            name: {
                "filename": EXPORT_FILENAMES[name],
                "rows": int(len(table)),
                "columns": list(table.columns),
            }
            for name, table in tables.items()
        },
        "quality_gates": quality_gates,
    }
    return DashboardExportResults(tables=tables, summary=summary)


def build_date_dimension(sales: pd.DataFrame) -> pd.DataFrame:
    """Create a continuous daily date dimension across completed sales."""
    start = pd.to_datetime(sales["invoice_date"]).min().normalize()
    end = pd.to_datetime(sales["invoice_date"]).max().normalize()
    dates = pd.date_range(start, end, freq="D")
    frame = pd.DataFrame({"date": dates})
    frame["year"] = frame["date"].dt.year.astype("int64")
    frame["quarter"] = frame["date"].dt.quarter.astype("int64")
    frame["month_number"] = frame["date"].dt.month.astype("int64")
    frame["month_name"] = frame["date"].dt.month_name()
    frame["year_month"] = frame["date"].dt.strftime("%Y-%m")
    frame["month_start"] = frame["date"].dt.to_period("M").dt.to_timestamp()
    frame["is_partial_period"] = frame["year_month"].eq(PARTIAL_PERIOD)
    return frame


def build_order_fact(order_summary: pd.DataFrame) -> pd.DataFrame:
    """Create one row per validated completed order."""
    orders = order_summary.copy()
    orders["invoice_date"] = pd.to_datetime(orders["invoice_date"])
    orders["customer_id"] = _clean_customer_id(orders["customer_id"])
    fact = pd.DataFrame(
        {
            "order_id": orders["invoice_no"].astype("string"),
            "order_date": orders["invoice_date"].dt.normalize(),
            "month_start": orders["invoice_date"].dt.to_period("M").dt.to_timestamp(),
            "customer_id": orders["customer_id"],
            "country": orders["country"].astype("string"),
            "order_revenue_gbp": orders["order_value_gbp"].astype("float64"),
            "units_sold": orders["units"].astype("int64"),
            "distinct_products": orders["distinct_products"].astype("int64"),
            "line_count": orders["product_lines"].astype("int64"),
            "is_identified_customer": orders["customer_id"].notna(),
        }
    )
    return fact.sort_values(["order_date", "order_id"], ignore_index=True)


def build_customer_dimension(
    rfm: pd.DataFrame, customer_clusters: pd.DataFrame
) -> pd.DataFrame:
    """Combine validated RFM fields with the final four-cluster assignment."""
    cluster_lookup = customer_clusters[
        ["customer_id", "cluster_id", "cluster_label"]
    ].copy()
    cluster_lookup["customer_id"] = _clean_customer_id(cluster_lookup["customer_id"])
    customers = rfm.copy()
    customers["customer_id"] = _clean_customer_id(customers["customer_id"])
    customers = customers.merge(
        cluster_lookup,
        on="customer_id",
        how="left",
        validate="one_to_one",
    )
    customers["is_repeat_customer"] = customers["frequency_orders"].ge(2)
    customers = customers.rename(columns={"segment": "rfm_segment"})
    customers["first_purchase_date"] = pd.to_datetime(
        customers["first_purchase"]
    ).dt.normalize()
    customers["last_purchase_date"] = pd.to_datetime(
        customers["last_purchase"]
    ).dt.normalize()
    columns = [
        "customer_id",
        "first_purchase_date",
        "last_purchase_date",
        "recency_days",
        "frequency_orders",
        "monetary_value_gbp",
        "average_order_value_gbp",
        "units_purchased",
        "distinct_products",
        "is_repeat_customer",
        "r_score",
        "f_score",
        "m_score",
        "rfm_score",
        "rfm_segment",
        "cluster_id",
        "cluster_label",
    ]
    return customers[columns].sort_values("customer_id", ignore_index=True)


def build_product_month_fact(sales: pd.DataFrame) -> pd.DataFrame:
    """Aggregate completed sales to product-month grain."""
    data = sales[
        [
            "invoice_date",
            "stock_code",
            "description",
            "invoice_no",
            "customer_id",
            "quantity",
            "line_revenue",
        ]
    ].copy()
    data["invoice_date"] = pd.to_datetime(data["invoice_date"])
    data["month_start"] = data["invoice_date"].dt.to_period("M").dt.to_timestamp()
    data["description"] = data["description"].fillna("Unknown product").astype("string")
    data = data.sort_values("invoice_date")
    result = (
        data.groupby(["month_start", "stock_code"], as_index=False)
        .agg(
            description=("description", "last"),
            revenue_gbp=("line_revenue", "sum"),
            units_sold=("quantity", "sum"),
            orders=("invoice_no", "nunique"),
            identified_customers=("customer_id", "nunique"),
        )
        .sort_values(["month_start", "revenue_gbp"], ascending=[True, False])
        .reset_index(drop=True)
    )
    return result


def build_country_month_fact(sales: pd.DataFrame) -> pd.DataFrame:
    """Aggregate completed sales to country-month grain."""
    data = sales[
        ["invoice_date", "country", "invoice_no", "customer_id", "quantity", "line_revenue"]
    ].copy()
    data["invoice_date"] = pd.to_datetime(data["invoice_date"])
    data["month_start"] = data["invoice_date"].dt.to_period("M").dt.to_timestamp()
    return (
        data.groupby(["month_start", "country"], as_index=False)
        .agg(
            revenue_gbp=("line_revenue", "sum"),
            orders=("invoice_no", "nunique"),
            units_sold=("quantity", "sum"),
            identified_customers=("customer_id", "nunique"),
        )
        .sort_values(["month_start", "revenue_gbp"], ascending=[True, False])
        .reset_index(drop=True)
    )


def build_returns_month_fact(returns: pd.DataFrame) -> pd.DataFrame:
    """Aggregate validated returns/cancellations to month grain."""
    data = returns[["invoice_date", "quantity", "line_revenue"]].copy()
    data["invoice_date"] = pd.to_datetime(data["invoice_date"])
    data["month_start"] = data["invoice_date"].dt.to_period("M").dt.to_timestamp()
    result = (
        data.groupby("month_start", as_index=False)
        .agg(
            signed_return_value_gbp=("line_revenue", "sum"),
            return_lines=("line_revenue", "size"),
            returned_units=("quantity", lambda values: values.abs().sum()),
        )
        .sort_values("month_start", ignore_index=True)
    )
    result["absolute_return_value_gbp"] = result["signed_return_value_gbp"].abs()
    return result[
        [
            "month_start",
            "signed_return_value_gbp",
            "absolute_return_value_gbp",
            "return_lines",
            "returned_units",
        ]
    ]


def build_cohort_retention_fact(
    cohort_counts: pd.DataFrame, cohort_retention: pd.DataFrame
) -> pd.DataFrame:
    """Reshape validated cohort matrices to Power BI-friendly long form."""
    count_columns = [
        column for column in cohort_counts.columns if str(column).startswith("month_")
    ]
    rows: list[dict[str, object]] = []
    retention_index = cohort_retention.set_index("acquisition_month")
    for count_row in cohort_counts.itertuples(index=False):
        acquisition_label = str(count_row.acquisition_month)
        acquisition_period = pd.Period(acquisition_label, freq="M")
        cohort_size = int(getattr(count_row, "month_0"))
        for column in count_columns:
            active_customers = getattr(count_row, column)
            if pd.isna(active_customers):
                continue
            month_index = int(column.replace("month_", ""))
            purchase_period = acquisition_period + month_index
            retention_pct = retention_index.loc[acquisition_label, column]
            rows.append(
                {
                    "acquisition_month": acquisition_period.to_timestamp(),
                    "purchase_month": purchase_period.to_timestamp(),
                    "cohort_month_index": month_index,
                    "cohort_size": cohort_size,
                    "active_customers": int(active_customers),
                    "retention_pct": float(retention_pct),
                    "is_partial_period": str(purchase_period) == PARTIAL_PERIOD,
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["acquisition_month", "cohort_month_index"], ignore_index=True
    )


def build_segment_dashboard_summary(
    rfm: pd.DataFrame, segment_action_plan: pd.DataFrame
) -> pd.DataFrame:
    """Profile validated RFM segments in original business units."""
    data = rfm.copy()
    data["is_repeat_customer"] = data["frequency_orders"].ge(2)
    summary = (
        data.groupby("segment", observed=False)
        .agg(
            customer_count=("customer_id", "size"),
            historical_customer_value_gbp=("monetary_value_gbp", "sum"),
            median_recency_days=("recency_days", "median"),
            median_frequency_orders=("frequency_orders", "median"),
            median_monetary_value_gbp=("monetary_value_gbp", "median"),
            repeat_customer_rate_pct=(
                "is_repeat_customer",
                lambda values: 100 * values.mean(),
            ),
        )
        .reset_index()
        .rename(columns={"segment": "rfm_segment"})
    )
    summary["customer_share_pct"] = 100 * summary["customer_count"] / len(data)
    summary["historical_value_share_pct"] = (
        100
        * summary["historical_customer_value_gbp"]
        / summary["historical_customer_value_gbp"].sum()
    )
    actions = segment_action_plan[
        ["segment", "priority", "rule", "recommended_action"]
    ].rename(columns={"segment": "rfm_segment", "rule": "segment_rule"})
    summary = summary.merge(actions, on="rfm_segment", how="left", validate="one_to_one")
    return summary[
        [
            "rfm_segment",
            "customer_count",
            "customer_share_pct",
            "historical_customer_value_gbp",
            "historical_value_share_pct",
            "median_recency_days",
            "median_frequency_orders",
            "median_monetary_value_gbp",
            "repeat_customer_rate_pct",
            "priority",
            "segment_rule",
            "recommended_action",
        ]
    ]


def build_cluster_dashboard_summary(cluster_profiles: pd.DataFrame) -> pd.DataFrame:
    """Rename validated K=4 profiles for dashboard-facing terminology."""
    summary = cluster_profiles.rename(
        columns={
            "total_monetary_value_gbp": "historical_customer_value_gbp",
            "revenue_share_pct": "historical_value_share_pct",
        }
    ).copy()
    return summary[
        [
            "cluster_id",
            "cluster_label",
            "customer_count",
            "customer_share_pct",
            "historical_customer_value_gbp",
            "historical_value_share_pct",
            "median_recency_days",
            "median_frequency_orders",
            "median_monetary_value_gbp",
            "repeat_customer_rate_pct",
            "dominant_rfm_segment",
            "dominant_rfm_segment_share_pct",
            "label_basis",
            "recommended_action",
        ]
    ]


def build_kpi_snapshot(eda_summary: dict[str, object]) -> pd.DataFrame:
    """Create a one-row snapshot of confirmed executive metrics."""
    return pd.DataFrame(
        [
            {
                "data_through_date": "2011-12-09",
                "completed_revenue_gbp": eda_summary["completed_sales_value_gbp"],
                "completed_orders": eda_summary["orders"],
                "completed_units": eda_summary["units_sold"],
                "average_order_value_gbp": eda_summary["average_order_value_gbp"],
                "median_order_value_gbp": eda_summary["median_order_value_gbp"],
                "identified_customers": eda_summary["identified_customers"],
                "repeat_customers": eda_summary["repeat_customers"],
                "repeat_customer_rate_pct": eda_summary["repeat_customer_rate_pct"],
                "identified_customer_revenue_gbp": eda_summary["identified_revenue_gbp"],
                "anonymous_revenue_gbp": eda_summary["anonymous_revenue_gbp"],
                "anonymous_revenue_share_pct": eda_summary["anonymous_revenue_share_pct"],
                "signed_returns_value_gbp": eda_summary["signed_returns_value_gbp"],
                "partial_period": PARTIAL_PERIOD,
                "partial_period_note": eda_summary["partial_period_note"],
            }
        ]
    )


def validate_dashboard_tables(
    tables: dict[str, pd.DataFrame],
) -> dict[str, object]:
    """Validate all required dashboard reconciliations before files are written."""
    orders = tables["fact_orders"]
    customers = tables["dim_customer"]
    returns_month = tables["fact_returns_month"]
    segment_summary = tables["segment_summary"]
    cluster_summary = tables["cluster_summary"]
    dim_date = tables["dim_date"]
    cohort = tables["cohort_retention"]

    completed_revenue = float(orders["order_revenue_gbp"].sum())
    completed_units = int(orders["units_sold"].sum())
    identified_revenue = float(customers["monetary_value_gbp"].sum())
    signed_returns = float(returns_month["signed_return_value_gbp"].sum())
    segment_total = int(segment_summary["customer_count"].sum())
    cluster_total = int(cluster_summary["customer_count"].sum())

    product_revenue = float(tables["fact_product_month"]["revenue_gbp"].sum())
    country_revenue = float(tables["fact_country_month"]["revenue_gbp"].sum())
    product_units = int(tables["fact_product_month"]["units_sold"].sum())
    country_units = int(tables["fact_country_month"]["units_sold"].sum())

    gates: dict[str, object] = {
        "completed_revenue": _monetary_gate(
            completed_revenue, EXPECTED_COMPLETED_REVENUE_GBP
        ),
        "completed_orders": _count_gate(len(orders), EXPECTED_COMPLETED_ORDERS),
        "completed_units": _count_gate(completed_units, EXPECTED_COMPLETED_UNITS),
        "identified_customers": _count_gate(
            len(customers), EXPECTED_IDENTIFIED_CUSTOMERS
        ),
        "repeat_customers": _count_gate(
            int(customers["is_repeat_customer"].sum()), EXPECTED_REPEAT_CUSTOMERS
        ),
        "identified_customer_revenue": _monetary_gate(
            identified_revenue, EXPECTED_IDENTIFIED_REVENUE_GBP
        ),
        "signed_returns_value": _monetary_gate(
            signed_returns, EXPECTED_SIGNED_RETURNS_GBP
        ),
        "segment_totals": _count_gate(segment_total, EXPECTED_SEGMENT_TOTAL),
        "cluster_totals": _count_gate(cluster_total, EXPECTED_CLUSTER_TOTAL),
        "duplicate_order_ids": {
            "actual": int(orders["order_id"].duplicated().sum()),
            "expected": 0,
            "passed": bool(orders["order_id"].is_unique),
        },
        "duplicate_customer_ids": {
            "actual": int(customers["customer_id"].duplicated().sum()),
            "expected": 0,
            "passed": bool(customers["customer_id"].is_unique),
        },
        "customer_labels_complete": {
            "missing_rfm_segments": int(customers["rfm_segment"].isna().sum()),
            "missing_cluster_labels": int(customers["cluster_label"].isna().sum()),
            "passed": bool(
                customers["rfm_segment"].notna().all()
                and customers["cluster_label"].notna().all()
            ),
        },
        "december_2011_partial_period": {
            "date_rows_flagged": int(dim_date["is_partial_period"].sum()),
            "cohort_rows_flagged": int(cohort["is_partial_period"].sum()),
            "passed": bool(
                dim_date.loc[dim_date["year_month"].eq(PARTIAL_PERIOD), "is_partial_period"].all()
                and cohort.loc[
                    cohort["purchase_month"].dt.strftime("%Y-%m").eq(PARTIAL_PERIOD),
                    "is_partial_period",
                ].all()
            ),
        },
        "aggregate_fact_reconciliation": {
            "product_revenue_difference_gbp": round(product_revenue - completed_revenue, 6),
            "country_revenue_difference_gbp": round(country_revenue - completed_revenue, 6),
            "product_units_difference": product_units - completed_units,
            "country_units_difference": country_units - completed_units,
            "passed": bool(
                abs(product_revenue - completed_revenue) <= MONETARY_TOLERANCE_GBP
                and abs(country_revenue - completed_revenue) <= MONETARY_TOLERANCE_GBP
                and product_units == completed_units
                and country_units == completed_units
            ),
        },
        "cohort_retention_bounds": {
            "minimum_pct": round(float(cohort["retention_pct"].min()), 2),
            "maximum_pct": round(float(cohort["retention_pct"].max()), 2),
            "passed": bool(cohort["retention_pct"].between(0, 100).all()),
        },
    }
    gates["all_passed"] = bool(all(gate["passed"] for gate in gates.values()))
    return gates


def write_dashboard_exports(
    results: DashboardExportResults,
    output_dir: Path,
) -> dict[str, object]:
    """Write UTF-8 CSVs and add file-size gates to the export summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, table in results.tables.items():
        path = output_dir / EXPORT_FILENAMES[name]
        table.to_csv(path, index=False, encoding="utf-8", date_format="%Y-%m-%d")
        paths[name] = path

    summary = _copy_nested(results.summary)
    file_sizes = {name: int(path.stat().st_size) for name, path in paths.items()}
    total_size = int(sum(file_sizes.values()))
    for name, size_bytes in file_sizes.items():
        summary["exports"][name]["size_bytes"] = size_bytes
        summary["exports"][name]["size_mb"] = round(size_bytes / (1024 * 1024), 4)
    summary["total_export_size_bytes"] = total_size
    summary["total_export_size_mb"] = round(total_size / (1024 * 1024), 4)
    summary["quality_gates"]["csv_file_sizes"] = {
        "limit_bytes_per_file": GITHUB_FILE_LIMIT_BYTES,
        "largest_file_bytes": max(file_sizes.values()),
        "largest_file": max(file_sizes, key=file_sizes.get),
        "files_over_limit": [
            name for name, size in file_sizes.items() if size >= GITHUB_FILE_LIMIT_BYTES
        ],
        "passed": all(size < GITHUB_FILE_LIMIT_BYTES for size in file_sizes.values()),
    }
    summary["quality_gates"]["all_passed"] = bool(
        all(
            gate["passed"]
            for key, gate in summary["quality_gates"].items()
            if key != "all_passed"
        )
    )
    return summary


def _validate_inputs(
    sales: pd.DataFrame,
    returns: pd.DataFrame,
    order_summary: pd.DataFrame,
    rfm: pd.DataFrame,
    customer_clusters: pd.DataFrame,
) -> None:
    required = {
        "sales": {
            "invoice_date",
            "stock_code",
            "description",
            "invoice_no",
            "customer_id",
            "country",
            "quantity",
            "line_revenue",
        },
        "returns": {"invoice_date", "quantity", "line_revenue"},
        "order_summary": {
            "invoice_no",
            "invoice_date",
            "customer_id",
            "country",
            "order_value_gbp",
            "units",
            "product_lines",
            "distinct_products",
        },
        "rfm": {
            "customer_id",
            "first_purchase",
            "last_purchase",
            "recency_days",
            "frequency_orders",
            "monetary_value_gbp",
            "average_order_value_gbp",
            "units_purchased",
            "distinct_products",
            "r_score",
            "f_score",
            "m_score",
            "rfm_score",
            "segment",
        },
        "customer_clusters": {"customer_id", "cluster_id", "cluster_label"},
    }
    frames = {
        "sales": sales,
        "returns": returns,
        "order_summary": order_summary,
        "rfm": rfm,
        "customer_clusters": customer_clusters,
    }
    missing = {
        name: sorted(columns - set(frames[name].columns))
        for name, columns in required.items()
        if columns - set(frames[name].columns)
    }
    if missing:
        raise ValueError(f"Dashboard inputs are missing required columns: {missing}")


def _clean_customer_id(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    return cleaned.mask(cleaned.eq(""), pd.NA)


def _monetary_gate(actual: float, expected: float) -> dict[str, object]:
    return {
        "actual_gbp": round(actual, 2),
        "expected_gbp": expected,
        "difference_gbp": round(actual - expected, 6),
        "passed": abs(actual - expected) <= MONETARY_TOLERANCE_GBP,
    }


def _count_gate(actual: int, expected: int) -> dict[str, object]:
    return {
        "actual": int(actual),
        "expected": int(expected),
        "passed": int(actual) == int(expected),
    }


def _copy_nested(value):
    if isinstance(value, dict):
        return {key: _copy_nested(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_nested(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value
