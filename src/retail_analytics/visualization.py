"""Professional static and interactive EDA visualisations."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import seaborn as sns


NAVY = "#16324F"
TEAL = "#2A9D8F"
BLUE = "#3A6EA5"
RED = "#C44536"
LIGHT_BLUE = "#A8DADC"


def configure_style() -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update(
        {
            "figure.figsize": (11, 6),
            "axes.titleweight": "bold",
            "axes.titlesize": 15,
            "axes.labelsize": 11,
            "figure.dpi": 130,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
        }
    )


def create_eda_charts(
    tables: dict[str, pd.DataFrame], summary: dict[str, object], output_dir: Path
) -> list[Path]:
    """Create fourteen decision-focused charts and two interactive HTML views."""
    configure_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    monthly = tables["monthly_performance"].copy()
    monthly["period"] = pd.to_datetime(monthly["year_month"])
    complete_months = monthly.loc[~monthly["is_partial_period"]]

    outputs.append(_line_chart(complete_months, "period", "revenue_gbp", "Monthly Revenue (Complete Months)", "Revenue (GBP)", output_dir / "01_monthly_revenue.png", TEAL))
    outputs.append(_line_chart(complete_months, "period", "orders", "Monthly Completed Orders", "Orders", output_dir / "02_monthly_orders.png", NAVY))
    outputs.append(_line_chart(complete_months, "period", "average_order_value_gbp", "Monthly Average Order Value", "AOV (GBP)", output_dir / "03_monthly_average_order_value.png", BLUE))

    country = tables["country_performance"].head(10).sort_values("revenue_gbp")
    outputs.append(_horizontal_bar(country, "country", "revenue_gbp", "Top 10 Countries by Revenue", "Revenue (GBP)", output_dir / "04_top_countries_revenue.png", TEAL))

    products = tables["product_performance"].head(15).sort_values("revenue_gbp")
    products = products.assign(label=lambda data: data["description"].str.slice(0, 42))
    outputs.append(_horizontal_bar(products, "label", "revenue_gbp", "Top 15 Products by Revenue", "Revenue (GBP)", output_dir / "05_top_products_revenue.png", BLUE))

    weekday = tables["weekday_performance"]
    outputs.append(_bar_chart(weekday, "day_of_week", "orders", "Orders by Day of Week", "Orders", output_dir / "06_orders_by_weekday.png", NAVY))

    hourly = tables["hourly_performance"]
    outputs.append(_line_chart(hourly, "hour", "orders", "Orders by Hour of Day", "Orders", output_dir / "07_orders_by_hour.png", TEAL))

    orders = tables["order_summary"]
    path = output_dir / "08_order_value_distribution.png"
    fig, ax = plt.subplots()
    upper = orders["order_value_gbp"].quantile(0.99)
    sns.histplot(orders.loc[orders["order_value_gbp"].le(upper), "order_value_gbp"], bins=60, color=BLUE, ax=ax)
    ax.set(title="Order Value Distribution (Clipped at 99th Percentile)", xlabel="Order Value (GBP)", ylabel="Orders")
    _save(fig, path)
    outputs.append(path)

    customers = tables["customer_summary"]
    path = output_dir / "09_customer_revenue_distribution.png"
    fig, ax = plt.subplots()
    sns.histplot(np.log1p(customers["customer_revenue_gbp"]), bins=60, color=TEAL, ax=ax)
    ax.set(title="Customer Revenue Distribution (Log Scale)", xlabel="log(1 + Customer Revenue)", ylabel="Customers")
    _save(fig, path)
    outputs.append(path)

    returns = tables["return_product_performance"].head(12).sort_values("absolute_return_value_gbp")
    returns = returns.assign(label=lambda data: data["description"].str.slice(0, 42))
    outputs.append(_horizontal_bar(returns, "label", "absolute_return_value_gbp", "Products with Highest Absolute Return Value", "Absolute Return Value (GBP)", output_dir / "10_top_product_returns.png", RED))

    deciles = tables["customer_revenue_deciles"]
    outputs.append(_bar_chart(deciles, "value_decile", "revenue_share_pct", "Customer Revenue Share by Value Decile", "Revenue Share (%)", output_dir / "11_customer_revenue_deciles.png", BLUE))

    identity = pd.DataFrame(
        {
            "Customer Identification": ["Identified", "Anonymous"],
            "Revenue": [summary["identified_revenue_gbp"], summary["anonymous_revenue_gbp"]],
        }
    )
    outputs.append(_bar_chart(identity, "Customer Identification", "Revenue", "Revenue by Customer Identification Status", "Revenue (GBP)", output_dir / "12_identified_vs_anonymous_revenue.png", TEAL))

    outlier_impact = pd.DataFrame(
        {
            "Line Group": ["High-Revenue Flags", "Other Sales Lines"],
            "Revenue": [summary["flagged_revenue_gbp"], summary["completed_sales_value_gbp"] - summary["flagged_revenue_gbp"]],
        }
    )
    outputs.append(_bar_chart(outlier_impact, "Line Group", "Revenue", "Revenue Contribution of High-Value Line Flags", "Revenue (GBP)", output_dir / "13_outlier_revenue_impact.png", RED))

    path = output_dir / "14_order_feature_correlation.png"
    fig, ax = plt.subplots(figsize=(8, 6))
    correlation = orders[["order_value_gbp", "units", "product_lines", "distinct_products"]].corr(method="spearman")
    sns.heatmap(correlation, annot=True, fmt=".2f", cmap="vlag", center=0, ax=ax)
    ax.set_title("Spearman Correlation of Order Features")
    _save(fig, path)
    outputs.append(path)

    interactive_monthly = px.line(
        monthly,
        x="year_month",
        y="revenue_gbp",
        markers=True,
        title="Interactive Monthly Revenue",
        labels={"year_month": "Month", "revenue_gbp": "Revenue (GBP)"},
    )
    interactive_monthly.write_html(output_dir / "interactive_monthly_revenue.html", include_plotlyjs="cdn")

    interactive_country = px.bar(
        tables["country_performance"].head(15),
        x="country",
        y="revenue_gbp",
        hover_data=["orders", "identified_customers", "average_order_value_gbp"],
        title="Interactive Country Performance",
        labels={"country": "Country", "revenue_gbp": "Revenue (GBP)"},
    )
    interactive_country.write_html(output_dir / "interactive_country_performance.html", include_plotlyjs="cdn")
    return outputs


def _line_chart(data, x, y, title, ylabel, path, color) -> Path:
    fig, ax = plt.subplots()
    ax.plot(data[x], data[y], marker="o", linewidth=2.2, color=color)
    ax.set(title=title, xlabel="", ylabel=ylabel)
    ax.tick_params(axis="x", rotation=45)
    _save(fig, path)
    return path


def _bar_chart(data, x, y, title, ylabel, path, color) -> Path:
    fig, ax = plt.subplots()
    sns.barplot(data=data, x=x, y=y, color=color, ax=ax)
    ax.set(title=title, xlabel="", ylabel=ylabel)
    ax.tick_params(axis="x", rotation=30)
    _save(fig, path)
    return path


def _horizontal_bar(data, label, value, title, xlabel, path, color) -> Path:
    fig, ax = plt.subplots()
    sns.barplot(data=data, x=value, y=label, color=color, ax=ax)
    ax.set(title=title, xlabel=xlabel, ylabel="")
    _save(fig, path)
    return path


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)

