"""Decision-focused exploratory analysis for completed retail sales."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


WEEKDAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]


@dataclass(frozen=True)
class EDAResults:
    summary: dict[str, object]
    tables: dict[str, pd.DataFrame]


def build_eda_results(sales: pd.DataFrame, returns: pd.DataFrame) -> EDAResults:
    """Create executive metrics and reusable aggregate tables."""
    order_summary = _build_order_summary(sales)
    customer_summary = _build_customer_summary(sales)
    monthly = _build_monthly_summary(sales, order_summary)
    country = _build_country_summary(sales)
    products = _build_product_summary(sales)
    return_products = _build_return_product_summary(returns)
    weekday = _build_weekday_summary(sales)
    hourly = _build_hourly_summary(sales)
    revenue_deciles = _build_revenue_deciles(customer_summary)

    identified_mask = sales["customer_id"].notna()
    identified_revenue = float(sales.loc[identified_mask, "line_revenue"].sum())
    anonymous_revenue = float(sales.loc[~identified_mask, "line_revenue"].sum())
    flagged_revenue = float(
        sales.loc[sales["is_line_revenue_outlier"], "line_revenue"].sum()
    )
    total_revenue = float(sales["line_revenue"].sum())
    return_value = float(returns["line_revenue"].sum())

    summary: dict[str, object] = {
        "completed_sales_rows": int(len(sales)),
        "completed_sales_value_gbp": round(total_revenue, 2),
        "orders": int(order_summary["invoice_no"].nunique()),
        "units_sold": int(sales["quantity"].sum()),
        "average_order_value_gbp": round(float(order_summary["order_value_gbp"].mean()), 2),
        "median_order_value_gbp": round(float(order_summary["order_value_gbp"].median()), 2),
        "identified_customers": int(customer_summary["customer_id"].nunique()),
        "repeat_customers": int(customer_summary["is_repeat_customer"].sum()),
        "repeat_customer_rate_pct": round(
            float(customer_summary["is_repeat_customer"].mean() * 100), 2
        ),
        "identified_revenue_gbp": round(identified_revenue, 2),
        "anonymous_revenue_gbp": round(anonymous_revenue, 2),
        "anonymous_revenue_share_pct": round(100 * anonymous_revenue / total_revenue, 2),
        "signed_returns_value_gbp": round(return_value, 2),
        "absolute_return_value_to_sales_pct": round(100 * abs(return_value) / total_revenue, 2),
        "line_revenue_outlier_rows": int(sales["is_line_revenue_outlier"].sum()),
        "line_revenue_outlier_share_pct": round(
            100 * float(sales["is_line_revenue_outlier"].mean()), 2
        ),
        "flagged_revenue_gbp": round(flagged_revenue, 2),
        "flagged_revenue_share_pct": round(100 * flagged_revenue / total_revenue, 2),
        "top_customer_decile_revenue_share_pct": round(
            float(revenue_deciles.loc[revenue_deciles["value_decile"].eq(1), "revenue_share_pct"].iloc[0]),
            2,
        ),
        "partial_period_note": (
            "December 2011 contains data only through 9 December and must not be "
            "compared as a complete month."
        ),
    }

    tables = {
        "monthly_performance": monthly,
        "country_performance": country,
        "product_performance": products,
        "return_product_performance": return_products,
        "weekday_performance": weekday,
        "hourly_performance": hourly,
        "order_summary": order_summary,
        "customer_summary": customer_summary,
        "customer_revenue_deciles": revenue_deciles,
    }
    return EDAResults(summary=summary, tables=tables)


def _build_order_summary(sales: pd.DataFrame) -> pd.DataFrame:
    return (
        sales.groupby("invoice_no", as_index=False)
        .agg(
            invoice_date=("invoice_date", "min"),
            customer_id=("customer_id", "first"),
            country=("country", "first"),
            order_value_gbp=("line_revenue", "sum"),
            units=("quantity", "sum"),
            product_lines=("stock_code", "size"),
            distinct_products=("stock_code", "nunique"),
        )
    )


def _build_customer_summary(sales: pd.DataFrame) -> pd.DataFrame:
    identified = sales.loc[sales["customer_id"].notna()]
    customers = (
        identified.groupby("customer_id", as_index=False)
        .agg(
            primary_country=("country", _mode_or_unknown),
            first_purchase=("invoice_date", "min"),
            last_purchase=("invoice_date", "max"),
            orders=("invoice_no", "nunique"),
            customer_revenue_gbp=("line_revenue", "sum"),
            units=("quantity", "sum"),
            distinct_products=("stock_code", "nunique"),
        )
    )
    customers["average_order_value_gbp"] = (
        customers["customer_revenue_gbp"] / customers["orders"]
    )
    customers["active_span_days"] = (
        customers["last_purchase"].dt.normalize()
        - customers["first_purchase"].dt.normalize()
    ).dt.days
    customers["is_repeat_customer"] = customers["orders"].gt(1)
    return customers


def _build_monthly_summary(
    sales: pd.DataFrame, order_summary: pd.DataFrame
) -> pd.DataFrame:
    lines = (
        sales.groupby("year_month", as_index=False)
        .agg(
            revenue_gbp=("line_revenue", "sum"),
            units=("quantity", "sum"),
            sales_lines=("transaction_line_id", "size"),
            identified_customers=("customer_id", "nunique"),
        )
    )
    orders = order_summary.assign(
        year_month=order_summary["invoice_date"].dt.to_period("M").astype(str)
    )
    orders = orders.groupby("year_month", as_index=False).agg(
        orders=("invoice_no", "nunique"),
        average_order_value_gbp=("order_value_gbp", "mean"),
        median_order_value_gbp=("order_value_gbp", "median"),
    )
    monthly = lines.merge(orders, on="year_month", how="left")
    monthly["month_over_month_growth_pct"] = monthly["revenue_gbp"].pct_change() * 100
    monthly["is_partial_period"] = monthly["year_month"].eq("2011-12")
    return monthly


def _build_country_summary(sales: pd.DataFrame) -> pd.DataFrame:
    country = (
        sales.groupby("country", as_index=False)
        .agg(
            revenue_gbp=("line_revenue", "sum"),
            orders=("invoice_no", "nunique"),
            identified_customers=("customer_id", "nunique"),
            units=("quantity", "sum"),
        )
    )
    country["average_order_value_gbp"] = country["revenue_gbp"] / country["orders"]
    country["revenue_share_pct"] = 100 * country["revenue_gbp"] / country["revenue_gbp"].sum()
    return country.sort_values("revenue_gbp", ascending=False, ignore_index=True)


def _latest_product_descriptions(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.loc[frame["stock_code"].notna(), ["stock_code", "description", "invoice_date"]]
        .sort_values("invoice_date")
        .drop_duplicates("stock_code", keep="last")
        .drop(columns="invoice_date")
        .assign(description=lambda data: data["description"].fillna("Unknown product"))
    )


def _build_product_summary(sales: pd.DataFrame) -> pd.DataFrame:
    descriptions = _latest_product_descriptions(sales)
    products = (
        sales.groupby("stock_code", as_index=False)
        .agg(
            units_sold=("quantity", "sum"),
            revenue_gbp=("line_revenue", "sum"),
            orders=("invoice_no", "nunique"),
            identified_customers=("customer_id", "nunique"),
        )
        .merge(descriptions, on="stock_code", how="left")
    )
    products["revenue_share_pct"] = 100 * products["revenue_gbp"] / products["revenue_gbp"].sum()
    return products.sort_values("revenue_gbp", ascending=False, ignore_index=True)


def _build_return_product_summary(returns: pd.DataFrame) -> pd.DataFrame:
    descriptions = _latest_product_descriptions(returns)
    products = (
        returns.groupby("stock_code", as_index=False)
        .agg(
            returned_units=("quantity", lambda values: values.abs().sum()),
            signed_return_value_gbp=("line_revenue", "sum"),
            return_invoices=("invoice_no", "nunique"),
        )
        .merge(descriptions, on="stock_code", how="left")
    )
    products["absolute_return_value_gbp"] = products["signed_return_value_gbp"].abs()
    return products.sort_values("absolute_return_value_gbp", ascending=False, ignore_index=True)


def _build_weekday_summary(sales: pd.DataFrame) -> pd.DataFrame:
    weekday = (
        sales.groupby("day_of_week", observed=True, as_index=False)
        .agg(revenue_gbp=("line_revenue", "sum"), orders=("invoice_no", "nunique"))
    )
    weekday["day_of_week"] = pd.Categorical(
        weekday["day_of_week"], categories=WEEKDAY_ORDER, ordered=True
    )
    return weekday.sort_values("day_of_week", ignore_index=True)


def _build_hourly_summary(sales: pd.DataFrame) -> pd.DataFrame:
    return (
        sales.groupby("hour", as_index=False)
        .agg(revenue_gbp=("line_revenue", "sum"), orders=("invoice_no", "nunique"))
        .sort_values("hour", ignore_index=True)
    )


def _build_revenue_deciles(customers: pd.DataFrame) -> pd.DataFrame:
    ranked = customers.sort_values("customer_revenue_gbp", ascending=False).copy()
    bin_count = min(10, len(ranked))
    if bin_count <= 1:
        ranked["value_decile"] = 1
    else:
        ranked["value_decile"] = pd.qcut(
            ranked["customer_revenue_gbp"].rank(method="first", ascending=False),
            q=bin_count,
            labels=range(1, bin_count + 1),
        ).astype(int)
    result = (
        ranked.groupby("value_decile", as_index=False)
        .agg(customers=("customer_id", "size"), revenue_gbp=("customer_revenue_gbp", "sum"))
    )
    result["revenue_share_pct"] = 100 * result["revenue_gbp"] / result["revenue_gbp"].sum()
    return result


def _mode_or_unknown(series: pd.Series) -> str:
    mode = series.dropna().mode()
    return str(mode.iloc[0]) if not mode.empty else "Unknown"
