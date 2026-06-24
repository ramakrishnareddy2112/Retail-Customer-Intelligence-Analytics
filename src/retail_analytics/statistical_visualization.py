"""Visualisations for the non-parametric statistical analysis phase."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from retail_analytics.statistical_analysis import CORRELATION_FEATURES
from retail_analytics.visualization import BLUE, NAVY, RED, TEAL, configure_style


FEATURE_LABELS = {
    "recency_days": "Recency",
    "frequency_orders": "Frequency",
    "monetary_value_gbp": "Monetary value",
    "average_order_value_gbp": "Average order value",
    "active_span_days": "Active span",
    "units_purchased": "Units",
    "distinct_products": "Distinct products",
}


def create_statistical_charts(
    rfm: pd.DataFrame,
    orders: pd.DataFrame,
    correlation_matrix: pd.DataFrame,
    output_dir: Path,
) -> list[Path]:
    """Create publication-ready charts for statistical results."""
    configure_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        _correlation_heatmap(correlation_matrix, output_dir / "01_spearman_correlation_heatmap.png"),
        _customer_value_comparison(rfm, output_dir / "02_repeat_customer_value_comparison.png"),
        _order_value_comparison(orders, output_dir / "03_geographic_order_value_comparison.png"),
        _repeat_rate_comparison(rfm, output_dir / "04_geographic_repeat_rate.png"),
    ]
    return outputs


def _correlation_heatmap(matrix: pd.DataFrame, path: Path) -> Path:
    labels = [FEATURE_LABELS[column] for column in CORRELATION_FEATURES]
    chart_data = matrix.loc[CORRELATION_FEATURES, CORRELATION_FEATURES].copy()
    chart_data.index = labels
    chart_data.columns = labels
    mask = np.triu(np.ones_like(chart_data, dtype=bool), k=1)
    fig, ax = plt.subplots(figsize=(11, 8))
    sns.heatmap(
        chart_data,
        mask=mask,
        annot=True,
        fmt=".2f",
        cmap="vlag",
        center=0,
        vmin=-1,
        vmax=1,
        linewidths=0.5,
        cbar_kws={"label": "Spearman rho"},
        ax=ax,
    )
    ax.set_title("Customer Metric Spearman Correlations")
    ax.tick_params(axis="x", rotation=35)
    ax.tick_params(axis="y", rotation=0)
    return _save(fig, path)


def _customer_value_comparison(rfm: pd.DataFrame, path: Path) -> Path:
    data = rfm[["frequency_orders", "monetary_value_gbp"]].copy()
    data["Customer type"] = np.where(
        data["frequency_orders"].ge(2), "Repeat", "One-time"
    )
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.boxplot(
        data=data,
        x="Customer type",
        y="monetary_value_gbp",
        order=["One-time", "Repeat"],
        hue="Customer type",
        palette={"One-time": BLUE, "Repeat": TEAL},
        showfliers=False,
        legend=False,
        ax=ax,
    )
    ax.set_yscale("log")
    ax.set(
        title="Customer Value: Repeat Versus One-time Customers",
        xlabel="",
        ylabel="Monetary value (GBP, log scale)",
    )
    return _save(fig, path)


def _order_value_comparison(orders: pd.DataFrame, path: Path) -> Path:
    data = orders[["country", "order_value_gbp"]].copy()
    data["Geography"] = np.where(
        data["country"].eq("United Kingdom"), "United Kingdom", "International"
    )
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.violinplot(
        data=data,
        x="Geography",
        y="order_value_gbp",
        order=["United Kingdom", "International"],
        hue="Geography",
        palette={"United Kingdom": NAVY, "International": TEAL},
        cut=0,
        inner="quart",
        density_norm="width",
        legend=False,
        ax=ax,
    )
    ax.set_yscale("log")
    ax.set(
        title="Order Value by Customer Geography",
        xlabel="",
        ylabel="Order value (GBP, log scale)",
    )
    return _save(fig, path)


def _repeat_rate_comparison(rfm: pd.DataFrame, path: Path) -> Path:
    data = rfm[["primary_country", "frequency_orders"]].copy()
    data["Geography"] = np.where(
        data["primary_country"].eq("United Kingdom"), "United Kingdom", "International"
    )
    data["repeat"] = data["frequency_orders"].ge(2)
    rates = data.groupby("Geography", as_index=False)["repeat"].mean()
    rates["Repeat rate (%)"] = rates["repeat"] * 100
    rates = rates.set_index("Geography").loc[["United Kingdom", "International"]].reset_index()
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.barplot(
        data=rates,
        x="Geography",
        y="Repeat rate (%)",
        hue="Geography",
        palette={"United Kingdom": NAVY, "International": TEAL},
        legend=False,
        ax=ax,
    )
    ax.set(title="Repeat-customer Rate by Geography", xlabel="", ylim=(0, 100))
    for container in ax.containers:
        ax.bar_label(container, fmt="%.1f%%", padding=4)
    return _save(fig, path)


def _save(fig: plt.Figure, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
