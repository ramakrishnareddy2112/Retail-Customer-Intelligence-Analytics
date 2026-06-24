"""Professional visualisations for customer clustering outputs."""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA

from retail_analytics.clustering import CLUSTERING_FEATURES, transform_clustering_features
from retail_analytics.visualization import BLUE, NAVY, RED, TEAL, configure_style


PALETTE = [TEAL, NAVY, BLUE, RED, "#F4A261", "#7FB069", "#6C757D", "#9B5DE5", "#00B4D8", "#E76F51"]


def create_clustering_charts(
    customer_clusters: pd.DataFrame,
    evaluation: pd.DataFrame,
    profiles: pd.DataFrame,
    comparison: pd.DataFrame,
    output_dir: Path,
) -> list[Path]:
    """Create diagnostic, profile, PCA, and RFM-comparison charts."""
    configure_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    return [
        _k_evaluation_chart(evaluation, output_dir / "01_k_evaluation.png"),
        _cluster_contribution_chart(profiles, output_dir / "02_cluster_size_and_revenue.png"),
        _pca_projection(customer_clusters, output_dir / "03_pca_cluster_projection.png"),
        _rfm_comparison_heatmap(comparison, output_dir / "04_rfm_cluster_comparison.png"),
    ]


def _k_evaluation_chart(evaluation: pd.DataFrame, path: Path) -> Path:
    metric_optimal_k = int(
        evaluation.loc[evaluation["metric_optimal"], "k"].iloc[0]
    )
    operational_k = int(
        evaluation.loc[evaluation["operational_chosen"], "k"].iloc[0]
    )
    metrics = [
        ("inertia", "Inertia", False),
        ("silhouette_score", "Silhouette score", True),
        ("calinski_harabasz_score", "Calinski-Harabasz", True),
        ("davies_bouldin_score", "Davies-Bouldin", False),
        ("mean_pairwise_ari", "Mean pairwise ARI", True),
        ("minimum_cluster_share_pct", "Minimum cluster share (%)", True),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    for ax, (column, title, higher_is_better) in zip(axes.flat, metrics):
        ax.plot(evaluation["k"], evaluation[column], marker="o", color=TEAL, linewidth=2)
        ax.axvline(
            metric_optimal_k,
            color=NAVY,
            linestyle=":",
            alpha=0.9,
            label=f"Metric benchmark K={metric_optimal_k}",
        )
        ax.axvline(
            operational_k,
            color=RED,
            linestyle="--",
            alpha=0.9,
            label=f"Operational K={operational_k}",
        )
        ax.set(title=title, xlabel="K", ylabel="")
        ax.set_xticks(evaluation["k"])
        if column == "minimum_cluster_share_pct":
            ax.axhline(2, color=NAVY, linestyle=":", label="2% usability floor")
        if column == "mean_pairwise_ari":
            ax.axhline(0.8, color=NAVY, linestyle=":", label="0.80 stability floor")
        if higher_is_better:
            ax.annotate("higher is better", xy=(0.02, 0.04), xycoords="axes fraction", fontsize=8, color="#555555")
        elif column != "inertia":
            ax.annotate("lower is better", xy=(0.02, 0.04), xycoords="axes fraction", fontsize=8, color="#555555")
    axes[0, 0].legend(loc="best", fontsize=8)
    axes[1, 1].legend(loc="best")
    axes[1, 2].legend(loc="best")
    fig.suptitle("K-Means Candidate Evaluation", fontsize=17, fontweight="bold")
    return _save(fig, path)


def _cluster_contribution_chart(profiles: pd.DataFrame, path: Path) -> Path:
    data = profiles.sort_values("cluster_id").copy()
    labels = data.apply(
        lambda row: _wrapped_cluster_label(row.cluster_id, row.cluster_label), axis=1
    )
    x = np.arange(len(data))
    width = 0.36
    fig, ax = plt.subplots(figsize=(14, 7))
    customer_bars = ax.bar(x - width / 2, data["customer_share_pct"], width, label="Customer share", color=BLUE)
    revenue_bars = ax.bar(x + width / 2, data["revenue_share_pct"], width, label="Revenue share", color=TEAL)
    ax.set(
        title="Cluster Share of Customers and Revenue",
        xlabel="",
        ylabel="Share (%)",
        xticks=x,
        xticklabels=labels,
    )
    ax.legend()
    ax.bar_label(customer_bars, fmt="%.1f%%", padding=3)
    ax.bar_label(revenue_bars, fmt="%.1f%%", padding=3)
    return _save(fig, path)


def _pca_projection(customer_clusters: pd.DataFrame, path: Path) -> Path:
    transformed, _ = transform_clustering_features(customer_clusters)
    pca = PCA(n_components=2, random_state=42)
    projection = pca.fit_transform(transformed)
    data = pd.DataFrame(
        {
            "PCA component 1": projection[:, 0],
            "PCA component 2": projection[:, 1],
            "Cluster": customer_clusters.apply(
                lambda row: f"C{int(row.cluster_id)}: {row.cluster_label}", axis=1
            ).to_numpy(),
        }
    )
    cluster_order = (
        customer_clusters[["cluster_id", "cluster_label"]]
        .drop_duplicates()
        .sort_values("cluster_id")
        .apply(lambda row: f"C{int(row.cluster_id)}: {row.cluster_label}", axis=1)
        .tolist()
    )
    palette = {label: PALETTE[index] for index, label in enumerate(cluster_order)}
    fig, ax = plt.subplots(figsize=(11, 7))
    sns.scatterplot(
        data=data,
        x="PCA component 1",
        y="PCA component 2",
        hue="Cluster",
        hue_order=cluster_order,
        palette=palette,
        alpha=0.55,
        s=28,
        linewidth=0,
        ax=ax,
    )
    explained = 100 * pca.explained_variance_ratio_
    ax.set(
        title="Customer Clusters in a Two-dimensional PCA View",
        xlabel=f"PCA component 1 ({explained[0]:.1f}% variance)",
        ylabel=f"PCA component 2 ({explained[1]:.1f}% variance)",
    )
    ax.legend(title="", loc="center left", bbox_to_anchor=(1.01, 0.5))
    return _save(fig, path)


def _rfm_comparison_heatmap(comparison: pd.DataFrame, path: Path) -> Path:
    data = comparison.copy()
    data["cluster_display"] = data.apply(
        lambda row: _wrapped_cluster_label(row.cluster_id, row.cluster_label), axis=1
    )
    cluster_order = (
        data[["cluster_id", "cluster_display"]]
        .drop_duplicates()
        .sort_values("cluster_id")["cluster_display"]
        .tolist()
    )
    matrix = data.pivot(
        index="rfm_segment",
        columns="cluster_display",
        values="share_of_rfm_segment_pct",
    ).reindex(columns=cluster_order)
    fig, ax = plt.subplots(figsize=(14, 8))
    sns.heatmap(
        matrix,
        annot=True,
        fmt=".1f",
        cmap="YlGnBu",
        vmin=0,
        vmax=100,
        linewidths=0.5,
        cbar_kws={"label": "Share of RFM segment (%)"},
        ax=ax,
    )
    ax.set(
        title="Rule-based RFM Segments Across K-Means Clusters",
        xlabel="K-Means cluster",
        ylabel="Rule-based RFM segment",
    )
    ax.tick_params(axis="x", rotation=0)
    return _save(fig, path)


def _wrapped_cluster_label(cluster_id: int, cluster_label: str) -> str:
    concise_label = str(cluster_label).removesuffix(" Customers")
    return f"C{int(cluster_id)}\n{textwrap.fill(concise_label, width=22)}"


def _save(fig: plt.Figure, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
