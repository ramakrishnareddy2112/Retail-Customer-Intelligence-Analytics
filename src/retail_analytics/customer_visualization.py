"""Static visualisations for the customer analytics phase."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from retail_analytics.customer_analytics import SEGMENT_ORDER
from retail_analytics.visualization import BLUE, LIGHT_BLUE, NAVY, RED, TEAL, configure_style


SEGMENT_PALETTE = {
    "Champions": TEAL,
    "Loyal Customers": BLUE,
    "Potential Loyalists": LIGHT_BLUE,
    "New Customers": "#7FB069",
    "Cannot Lose Them": RED,
    "At Risk": "#F4A261",
    "Hibernating": "#6C757D",
    "Need Attention": NAVY,
}


def create_customer_analytics_charts(
    rfm: pd.DataFrame,
    segment_summary: pd.DataFrame,
    cohort_retention: pd.DataFrame,
    output_dir: Path,
) -> list[Path]:
    """Create professional customer analytics charts."""
    configure_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    outputs.append(_rfm_distributions(rfm, output_dir / "01_rfm_distributions.png"))
    outputs.append(
        _segment_bar(
            segment_summary,
            "customer_count",
            "Customers",
            "Customer Count by Segment",
            output_dir / "02_customer_count_by_segment.png",
        )
    )
    outputs.append(
        _segment_bar(
            segment_summary,
            "monetary_value_gbp",
            "Revenue (GBP)",
            "Revenue by Segment",
            output_dir / "03_revenue_by_segment.png",
        )
    )
    outputs.append(
        _cohort_heatmap(
            cohort_retention,
            output_dir / "04_cohort_retention_heatmap.png",
        )
    )
    outputs.append(
        _recency_frequency_view(
            rfm,
            output_dir / "05_recency_frequency_customer_view.png",
        )
    )
    return outputs


def _rfm_distributions(rfm: pd.DataFrame, path: Path) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    recency_cap = rfm["recency_days"].quantile(0.99)
    frequency_cap = rfm["frequency_orders"].quantile(0.99)

    sns.histplot(
        rfm["recency_days"].clip(upper=recency_cap),
        bins=45,
        color=TEAL,
        ax=axes[0],
    )
    axes[0].set(
        title="Recency Distribution",
        xlabel="Days Since Last Purchase",
        ylabel="Customers",
    )

    sns.histplot(
        rfm["frequency_orders"].clip(upper=frequency_cap),
        bins=35,
        color=BLUE,
        ax=axes[1],
    )
    axes[1].set(title="Frequency Distribution", xlabel="Completed Orders", ylabel="")

    sns.histplot(
        np.log1p(rfm["monetary_value_gbp"]),
        bins=45,
        color=NAVY,
        ax=axes[2],
    )
    axes[2].set(
        title="Monetary Distribution",
        xlabel="log(1 + Customer Revenue GBP)",
        ylabel="",
    )

    fig.suptitle("RFM Customer Metric Distributions", fontweight="bold", fontsize=16)
    _save(fig, path)
    return path


def _segment_bar(
    segment_summary: pd.DataFrame,
    value_column: str,
    xlabel: str,
    title: str,
    path: Path,
) -> Path:
    data = _ordered_segments(segment_summary).sort_values(value_column)
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = [SEGMENT_PALETTE[str(segment)] for segment in data["segment"]]
    sns.barplot(data=data, x=value_column, y="segment", palette=colors, hue="segment", dodge=False, ax=ax)
    legend = ax.get_legend()
    if legend:
        legend.remove()
    ax.set(title=title, xlabel=xlabel, ylabel="")
    for container in ax.containers:
        ax.bar_label(container, fmt=_bar_label_format(value_column), padding=4, fontsize=9)
    _save(fig, path)
    return path


def _cohort_heatmap(cohort_retention: pd.DataFrame, path: Path) -> Path:
    month_columns = [column for column in cohort_retention.columns if column.startswith("month_")]
    matrix = (
        cohort_retention.set_index("acquisition_month")[month_columns]
        .astype("float64")
        .replace({pd.NA: np.nan})
    )
    fig, ax = plt.subplots(figsize=(14, 8))
    sns.heatmap(
        matrix,
        cmap="YlGnBu",
        vmin=0,
        vmax=100,
        mask=matrix.isna(),
        linewidths=0.2,
        linecolor="white",
        cbar_kws={"label": "Retention (%)"},
        ax=ax,
    )
    ax.set(
        title="Monthly Cohort Retention (December 2011 Is Partial)",
        xlabel="Cohort Month Index",
        ylabel="Acquisition Month",
    )
    ax.set_xticklabels([label.get_text().replace("month_", "") for label in ax.get_xticklabels()])
    _save(fig, path)
    return path


def _recency_frequency_view(rfm: pd.DataFrame, path: Path) -> Path:
    data = rfm.copy()
    data["segment"] = pd.Categorical(data["segment"], categories=SEGMENT_ORDER, ordered=True)
    fig, ax = plt.subplots(figsize=(12, 7))
    sns.scatterplot(
        data=data,
        x="recency_days",
        y="frequency_orders",
        hue="segment",
        size="monetary_value_gbp",
        sizes=(18, 260),
        alpha=0.68,
        palette=SEGMENT_PALETTE,
        linewidth=0,
        ax=ax,
    )
    ax.set(
        title="Recency Versus Frequency Customer View",
        xlabel="Days Since Last Purchase",
        ylabel="Completed Orders (Log Scale)",
    )
    ax.set_yscale("log")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=True)
    _save(fig, path)
    return path


def _ordered_segments(segment_summary: pd.DataFrame) -> pd.DataFrame:
    data = segment_summary.copy()
    data["segment"] = pd.Categorical(data["segment"], categories=SEGMENT_ORDER, ordered=True)
    return data.sort_values("segment", ignore_index=True)


def _bar_label_format(value_column: str) -> str:
    if value_column == "monetary_value_gbp":
        return "GBP %.0f"
    return "%.0f"


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
