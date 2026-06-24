from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from retail_analytics.clustering import (
    CLUSTERING_FEATURES,
    FINAL_CLUSTER_LABELS,
    choose_operational_k,
    derive_cluster_business_metadata,
    evaluate_k_solutions,
    select_k,
    transform_clustering_features,
)


def _sample_rfm() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    size = 90
    low = pd.DataFrame(
        {
            "recency_days": rng.integers(150, 500, size=size),
            "frequency_orders": rng.integers(1, 4, size=size),
            "monetary_value_gbp": rng.uniform(20, 300, size=size),
        }
    )
    high = pd.DataFrame(
        {
            "recency_days": rng.integers(1, 50, size=size),
            "frequency_orders": rng.integers(10, 40, size=size),
            "monetary_value_gbp": rng.uniform(3000, 12000, size=size),
        }
    )
    rfm = pd.concat([low, high], ignore_index=True)
    rfm["customer_id"] = [f"C{i:03d}" for i in range(len(rfm))]
    rfm["primary_country"] = "United Kingdom"
    rfm["average_order_value_gbp"] = rfm["monetary_value_gbp"] / rfm["frequency_orders"]
    rfm["active_span_days"] = np.maximum(0, 500 - rfm["recency_days"])
    rfm["units_purchased"] = rfm["frequency_orders"] * 5
    rfm["distinct_products"] = rfm["frequency_orders"] + 2
    rfm["segment"] = "Need Attention"
    return rfm


def test_clustering_transform_is_finite_and_standardized() -> None:
    rfm = _sample_rfm()
    transformed, _ = transform_clustering_features(rfm)

    assert transformed.shape == (len(rfm), len(CLUSTERING_FEATURES))
    assert np.isfinite(transformed).all()
    assert np.allclose(transformed.mean(axis=0), 0, atol=1e-10)
    assert np.allclose(transformed.std(axis=0), 1, atol=1e-10)


def test_k_evaluation_uses_five_seed_ari_and_selects_eligible_solution() -> None:
    transformed, _ = transform_clustering_features(_sample_rfm())
    evaluation = evaluate_k_solutions(transformed, k_values=[2, 3], seeds=(42, 7, 21, 84, 123))
    ranked, chosen_k = select_k(evaluation)

    assert chosen_k in {2, 3}
    assert ranked.loc[ranked["metric_optimal"], "eligible"].all()
    assert ranked["stability_seed_count"].eq(5).all()
    assert ranked["mean_pairwise_ari"].between(-1, 1).all()


def test_k_selection_rejects_tiny_cluster_even_with_best_metric_ranks() -> None:
    evaluation = pd.DataFrame(
        {
            "k": [2, 3],
            "silhouette_score": [0.50, 0.80],
            "calinski_harabasz_score": [100, 200],
            "davies_bouldin_score": [0.70, 0.40],
            "minimum_cluster_share_pct": [20.0, 0.5],
            "mean_pairwise_ari": [0.95, 0.99],
        }
    )
    ranked, chosen_k = select_k(evaluation)

    assert chosen_k == 2
    assert ranked.set_index("k").loc[3, "eligible"] == pytest.approx(False)


def test_operational_k4_preserves_k2_metric_benchmark() -> None:
    evaluation = pd.DataFrame(
        {
            "k": [2, 4],
            "silhouette_score": [0.438, 0.366],
            "calinski_harabasz_score": [6205, 5095],
            "davies_bouldin_score": [0.872, 0.929],
            "minimum_cluster_share_pct": [39.95, 20.48],
            "mean_pairwise_ari": [0.995, 0.997],
        }
    )
    ranked, metric_optimal_k = select_k(evaluation)
    marked = choose_operational_k(ranked, operational_k=4)

    assert metric_optimal_k == 2
    assert marked.loc[marked["metric_optimal"], "k"].tolist() == [2]
    assert marked.loc[marked["operational_chosen"], "k"].tolist() == [4]
    assert marked.loc[marked["selected"], "k"].tolist() == [4]


def test_business_labels_are_unique_and_traceable_to_medians() -> None:
    profiles = pd.DataFrame(
        {
            "cluster_id": [1, 2, 3, 4],
            "median_recency_days": [17.0, 25.0, 186.0, 404.5],
            "median_frequency_orders": [13.0, 3.0, 4.0, 1.0],
            "median_monetary_value_gbp": [4965.48, 729.25, 1447.74, 272.04],
        }
    )
    metadata = derive_cluster_business_metadata(profiles)

    assert metadata["cluster_label"].is_unique
    assert metadata.set_index("cluster_id")["cluster_label"].to_dict() == FINAL_CLUSTER_LABELS
    assert metadata["label_basis"].str.contains("Median recency=").all()
    assert metadata["recommended_action"].str.len().gt(0).all()


def test_generated_customer_clusters_when_available() -> None:
    path = Path("data/processed/customer_clusters.parquet")
    if not path.exists():
        pytest.skip("Generated customer clusters are not available yet.")
    clusters = pd.read_parquet(path)
    assert len(clusters) == 5_878
    assert clusters["customer_id"].is_unique
    assert clusters[CLUSTERING_FEATURES + ["cluster_id"]].notna().all().all()
    assert int(clusters.groupby("cluster_id").size().sum()) == 5_878
    assert clusters["cluster_id"].nunique() == 4
    assert clusters["cluster_label"].nunique() == 4
    assert (
        clusters[["cluster_id", "cluster_label"]]
        .drop_duplicates()
        .set_index("cluster_id")["cluster_label"]
        .to_dict()
        == FINAL_CLUSTER_LABELS
    )
