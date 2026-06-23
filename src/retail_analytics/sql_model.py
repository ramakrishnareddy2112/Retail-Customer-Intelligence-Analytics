"""Build star-schema dimensions and facts from canonical retail transactions."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


def build_dimensions(canonical: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Create conformed date, product, customer, and country dimensions."""
    dates = pd.Series(canonical["invoice_day"].dropna().unique()).sort_values()
    dim_date = pd.DataFrame({"full_date": pd.to_datetime(dates)})
    dim_date["date_key"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["year"] = dim_date["full_date"].dt.year
    dim_date["quarter"] = dim_date["full_date"].dt.quarter
    dim_date["month"] = dim_date["full_date"].dt.month
    dim_date["month_name"] = dim_date["full_date"].dt.month_name()
    dim_date["year_month"] = dim_date["full_date"].dt.to_period("M").astype(str)
    dim_date["day_of_month"] = dim_date["full_date"].dt.day
    dim_date["day_of_week"] = dim_date["full_date"].dt.day_name()
    dim_date["day_of_week_number"] = dim_date["full_date"].dt.dayofweek + 1
    dim_date["is_weekend"] = dim_date["full_date"].dt.dayofweek.ge(5).astype(int)
    dim_date["full_date"] = dim_date["full_date"].dt.strftime("%Y-%m-%d")
    dim_date = dim_date[
        [
            "date_key", "full_date", "year", "quarter", "month", "month_name",
            "year_month", "day_of_month", "day_of_week", "day_of_week_number",
            "is_weekend",
        ]
    ]

    product_source = (
        canonical.loc[canonical["stock_code"].notna(), ["stock_code", "description", "invoice_date"]]
        .sort_values("invoice_date")
        .drop_duplicates("stock_code", keep="last")
        .sort_values("stock_code")
    )
    dim_product = product_source[["stock_code", "description"]].copy()
    dim_product.insert(0, "product_key", np.arange(1, len(dim_product) + 1))
    dim_product.rename(columns={"description": "product_description"}, inplace=True)
    dim_product["product_description"] = dim_product["product_description"].fillna("Unknown product")

    customer_source = canonical.loc[
        canonical["customer_id"].notna() & canonical["is_completed_sale"],
        ["customer_id", "country", "invoice_date"],
    ]
    purchase_dates = customer_source.groupby("customer_id")["invoice_date"].agg(
        first_purchase_date="min", last_purchase_date="max"
    )
    primary_country = customer_source.groupby("customer_id")["country"].agg(_mode_or_unknown)
    dim_customer = purchase_dates.join(primary_country.rename("primary_country")).reset_index()
    dim_customer.sort_values("customer_id", inplace=True)
    dim_customer.insert(0, "customer_key", np.arange(1, len(dim_customer) + 1))
    for column in ("first_purchase_date", "last_purchase_date"):
        dim_customer[column] = pd.to_datetime(dim_customer[column]).dt.strftime("%Y-%m-%d")

    countries = sorted(canonical["country"].dropna().astype(str).unique().tolist())
    dim_country = pd.DataFrame({"country_name": countries})
    dim_country.insert(0, "country_key", np.arange(1, len(dim_country) + 1))

    return {
        "dim_date": dim_date,
        "dim_product": dim_product,
        "dim_customer": dim_customer,
        "dim_country": dim_country,
    }


def build_fact_tables(
    canonical: pd.DataFrame, dimensions: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    """Map canonical transactions onto star-schema surrogate keys."""
    product_map = dimensions["dim_product"].set_index("stock_code")["product_key"]
    customer_map = dimensions["dim_customer"].set_index("customer_id")["customer_key"]
    country_map = dimensions["dim_country"].set_index("country_name")["country_key"]

    keyed = canonical.assign(
        date_key=canonical["invoice_date"].dt.strftime("%Y%m%d").astype(int),
        product_key=canonical["stock_code"].map(product_map).fillna(0).astype(int),
        customer_key=canonical["customer_id"].map(customer_map).astype("Int64"),
        country_key=canonical["country"].map(country_map).fillna(0).astype(int),
    )

    sales = keyed.loc[keyed["transaction_type"].eq("completed_sale")].copy()
    fact_sales = sales[
        [
            "transaction_line_id", "invoice_no", "date_key", "product_key",
            "customer_key", "country_key", "quantity", "unit_price", "line_revenue",
            "is_quantity_outlier", "is_unit_price_outlier", "is_line_revenue_outlier",
        ]
    ].copy()
    for column in (
        "is_quantity_outlier", "is_unit_price_outlier", "is_line_revenue_outlier"
    ):
        fact_sales[column] = fact_sales[column].astype(int)

    returns = keyed.loc[keyed["transaction_type"].eq("return_or_cancellation")].copy()
    fact_returns = returns[
        [
            "transaction_line_id", "invoice_no", "date_key", "product_key",
            "customer_key", "country_key", "quantity", "unit_price", "line_revenue",
        ]
    ].rename(columns={"line_revenue": "signed_return_value"})

    exclusions = keyed.loc[keyed["transaction_type"].eq("excluded_non_sale")]
    audit_exclusions = exclusions[
        [
            "transaction_line_id", "invoice_no", "stock_code", "invoice_date",
            "quantity", "unit_price", "exclusion_reason",
        ]
    ].copy()
    audit_exclusions["invoice_date"] = audit_exclusions["invoice_date"].astype(str)

    return {
        "fact_sales": fact_sales,
        "fact_returns": fact_returns,
        "audit_exclusions": audit_exclusions,
    }


def create_database(
    database_path: Path,
    schema_path: Path,
    dimensions: dict[str, pd.DataFrame],
    facts: dict[str, pd.DataFrame],
) -> None:
    """Create a fresh indexed SQLite database using the reviewed schema."""
    temporary_path = database_path.with_suffix(".tmp.sqlite")
    if temporary_path.exists():
        temporary_path.unlink()

    connection = sqlite3.connect(temporary_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        for table_name, frame in {**dimensions, **facts}.items():
            frame.to_sql(table_name, connection, if_exists="append", index=False, chunksize=25_000)
        connection.commit()
        failures = connection.execute("PRAGMA foreign_key_check").fetchall()
        if failures:
            raise RuntimeError(f"Foreign key validation failed: {failures[:10]}")
    finally:
        connection.close()

    temporary_path.replace(database_path)


def _mode_or_unknown(series: pd.Series) -> str:
    mode = series.dropna().mode()
    return str(mode.iloc[0]) if not mode.empty else "Unknown"

