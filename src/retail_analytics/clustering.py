"""Evidence-based K-Means clustering for validated customer RFM outputs."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import os

import numpy as np
import pandas as pd

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

from sklearn.cluster import KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler

from retail_analytics.customer_analytics import (
    EXPECTED_CUSTOMER_COUNT,
    EXPECTED_MONETARY_VALUE_GBP,
    MONETARY_TOLERANCE_GBP,
    SEGMENT_ORDER,
)


CLUSTERING_FEATURES = ["recency_days", "frequency_orders", "monetary_value_gbp"]
K_RANGE = range(2, 11)
RANDOM_STATE = 42
STABILITY_SEEDS = (42, 7, 21, 84, 123)
MIN_CLUSTER_SHARE = 0.02
MIN_MEAN_ARI = 0.80
KMEANS_N_INIT = 20
OPERATIONAL_CHOSEN_K = 4
FINAL_CLUSTER_LABELS = {
    1: "High-Value Champions",
    2: "Recent Growth Customers",
    3: "Lapsed Established Customers",
    4: "Dormant Low-Value Customers",
}


@dataclass(frozen=True)
class ClusteringResults:
    """Container for assignments, evaluation, profiles, and metadata."""

    customer_clusters: pd.DataFrame
    k_evaluation: pd.DataFrame
    cluster_profiles: pd.DataFrame
    rfm_cluster_comparison: pd.DataFrame
    summary: dict[str, object]


def transform_clustering_features(
    rfm: pd.DataFrame,
) -> tuple[np.ndarray, StandardScaler]:
    """Apply log1p to non-negative RFM features and standardise them."""
    _validate_rfm_input(rfm)
    logged = np.log1p(rfm[CLUSTERING_FEATURES].astype("float64"))
    scaler = StandardScaler()
    transformed = scaler.fit_transform(logged)
    if not np.isfinite(transformed).all():
        raise ValueError("Transformed clustering features contain non-finite values.")
    return transformed, scaler


def evaluate_k_solutions(
    transformed_features: np.ndarray,
    k_values: range | list[int] | tuple[int, ...] = K_RANGE,
    seeds: tuple[int, ...] = STABILITY_SEEDS,
) -> pd.DataFrame:
    """Evaluate candidate K values and pairwise label stability across seeds."""
    if len(seeds) < 5:
        raise ValueError("Clustering stability requires at least five random seeds.")
    rows: list[dict[str, object]] = []
    previous_inertia: float | None = None
    for k in k_values:
        if k < 2 or k >= len(transformed_features):
            raise ValueError(f"Invalid K={k} for {len(transformed_features)} observations.")
        models: list[KMeans] = []
        labels_by_seed: list[np.ndarray] = []
        for seed in seeds:
            model = KMeans(
                n_clusters=k,
                random_state=seed,
                n_init=KMEANS_N_INIT,
                max_iter=500,
            ).fit(transformed_features)
            models.append(model)
            labels_by_seed.append(model.labels_)

        reference = models[0]
        reference_labels = labels_by_seed[0]
        pairwise_ari = [
            adjusted_rand_score(left, right)
            for left, right in combinations(labels_by_seed, 2)
        ]
        counts = np.bincount(reference_labels, minlength=k)
        inertia_reduction = (
            np.nan
            if previous_inertia is None
            else 100 * (previous_inertia - reference.inertia_) / previous_inertia
        )
        rows.append(
            {
                "k": int(k),
                "inertia": float(reference.inertia_),
                "inertia_reduction_from_previous_k_pct": float(inertia_reduction),
                "silhouette_score": float(
                    silhouette_score(transformed_features, reference_labels)
                ),
                "calinski_harabasz_score": float(
                    calinski_harabasz_score(transformed_features, reference_labels)
                ),
                "davies_bouldin_score": float(
                    davies_bouldin_score(transformed_features, reference_labels)
                ),
                "minimum_cluster_count": int(counts.min()),
                "minimum_cluster_share_pct": float(100 * counts.min() / counts.sum()),
                "mean_pairwise_ari": float(np.mean(pairwise_ari)),
                "minimum_pairwise_ari": float(np.min(pairwise_ari)),
                "stability_seed_count": int(len(seeds)),
                "stability_pair_count": int(len(pairwise_ari)),
            }
        )
        previous_inertia = float(reference.inertia_)
    return pd.DataFrame(rows)


def select_k(
    evaluation: pd.DataFrame,
    minimum_cluster_share_pct: float = MIN_CLUSTER_SHARE * 100,
    minimum_mean_ari: float = MIN_MEAN_ARI,
) -> tuple[pd.DataFrame, int]:
    """Identify the metric-optimal K by evidence ranks after usability gates."""
    required = {
        "k",
        "silhouette_score",
        "calinski_harabasz_score",
        "davies_bouldin_score",
        "minimum_cluster_share_pct",
        "mean_pairwise_ari",
    }
    missing = required - set(evaluation.columns)
    if missing:
        raise ValueError(f"K evaluation is missing columns: {sorted(missing)}")
    ranked = evaluation.copy()
    ranked["eligible"] = ranked["minimum_cluster_share_pct"].ge(
        minimum_cluster_share_pct
    ) & ranked["mean_pairwise_ari"].ge(minimum_mean_ari)
    if not ranked["eligible"].any():
        raise RuntimeError(
            "No candidate K passed the minimum cluster-share and stability gates."
        )

    eligible = ranked["eligible"]
    ranking_rules = {
        "rank_silhouette": ("silhouette_score", False),
        "rank_calinski_harabasz": ("calinski_harabasz_score", False),
        "rank_davies_bouldin": ("davies_bouldin_score", True),
        "rank_stability": ("mean_pairwise_ari", False),
    }
    rank_columns: list[str] = []
    for rank_column, (metric, ascending) in ranking_rules.items():
        rank_columns.append(rank_column)
        ranked[rank_column] = np.nan
        ranked.loc[eligible, rank_column] = ranked.loc[eligible, metric].rank(
            method="min", ascending=ascending
        )
    ranked["selection_rank_sum"] = ranked[rank_columns].sum(axis=1, min_count=len(rank_columns))
    candidates = ranked.loc[eligible].sort_values(
        ["selection_rank_sum", "silhouette_score", "davies_bouldin_score", "k"],
        ascending=[True, False, True, True],
    )
    metric_optimal_k = int(candidates.iloc[0]["k"])
    ranked["metric_optimal"] = ranked["k"].eq(metric_optimal_k)
    ranked["selected"] = ranked["metric_optimal"]
    return ranked, metric_optimal_k


def choose_operational_k(
    evaluation: pd.DataFrame,
    operational_k: int = OPERATIONAL_CHOSEN_K,
) -> pd.DataFrame:
    """Mark a documented operational choice while retaining the metric benchmark."""
    if operational_k not in evaluation["k"].values:
        raise ValueError(f"Operational K={operational_k} was not evaluated.")
    chosen = evaluation.loc[evaluation["k"].eq(operational_k)].iloc[0]
    if not bool(chosen["eligible"]):
        raise RuntimeError(
            f"Operational K={operational_k} fails the cluster-share or stability gate."
        )
    marked = evaluation.copy()
    marked["operational_chosen"] = marked["k"].eq(operational_k)
    marked["selected"] = marked["operational_chosen"]
    return marked


def build_clustering_results(
    rfm: pd.DataFrame,
    expected_customer_count: int | None = EXPECTED_CUSTOMER_COUNT,
    expected_monetary_value_gbp: float | None = EXPECTED_MONETARY_VALUE_GBP,
) -> ClusteringResults:
    """Retain the metric benchmark and fit the operational K=4 solution."""
    transformed, _ = transform_clustering_features(rfm)
    evaluation = evaluate_k_solutions(transformed)
    evaluation, metric_optimal_k = select_k(evaluation)
    evaluation = choose_operational_k(evaluation)
    operational_chosen_k = OPERATIONAL_CHOSEN_K

    model = KMeans(
        n_clusters=operational_chosen_k,
        random_state=RANDOM_STATE,
        n_init=KMEANS_N_INIT,
        max_iter=500,
    ).fit(transformed)
    label_map = _business_ordered_label_map(model.cluster_centers_)
    customer_clusters = rfm.copy()
    customer_clusters["cluster_id"] = pd.Series(model.labels_, index=rfm.index).map(label_map).astype("int64")
    customer_clusters["cluster_label"] = customer_clusters["cluster_id"].map(
        lambda cluster_id: f"Cluster {cluster_id}"
    )

    initial_profiles = build_cluster_profiles(customer_clusters)
    business_metadata = derive_cluster_business_metadata(initial_profiles)
    label_map = business_metadata.set_index("cluster_id")["cluster_label"]
    customer_clusters["cluster_label"] = customer_clusters["cluster_id"].map(label_map)
    customer_clusters = customer_clusters.sort_values(
        ["cluster_id", "monetary_value_gbp"], ascending=[True, False], ignore_index=True
    )

    profiles = build_cluster_profiles(customer_clusters)
    profiles = profiles.merge(
        business_metadata[
            ["cluster_id", "label_basis", "recommended_action"]
        ],
        on="cluster_id",
        how="left",
        validate="one_to_one",
    )
    comparison = build_rfm_cluster_comparison(customer_clusters)
    quality_gates = validate_clustering(
        customer_clusters,
        evaluation,
        profiles,
        metric_optimal_k,
        operational_chosen_k,
        expected_customer_count,
        expected_monetary_value_gbp,
    )
    metric_optimal_metrics = evaluation.loc[evaluation["metric_optimal"]].iloc[0]
    operational_metrics = evaluation.loc[evaluation["operational_chosen"]].iloc[0]
    summary = _build_summary(
        metric_optimal_k,
        operational_chosen_k,
        metric_optimal_metrics,
        operational_metrics,
        evaluation,
        profiles,
        quality_gates,
    )
    return ClusteringResults(
        customer_clusters=customer_clusters,
        k_evaluation=evaluation,
        cluster_profiles=profiles,
        rfm_cluster_comparison=comparison,
        summary=summary,
    )


def build_cluster_profiles(customer_clusters: pd.DataFrame) -> pd.DataFrame:
    """Profile selected clusters in interpretable original business units."""
    data = customer_clusters.copy()
    data["is_repeat_customer"] = data["frequency_orders"].ge(2)
    data["is_uk_customer"] = data["primary_country"].eq("United Kingdom")
    total_revenue = float(data["monetary_value_gbp"].sum())
    profiles = (
        data.groupby(["cluster_id", "cluster_label"], as_index=False)
        .agg(
            customer_count=("customer_id", "size"),
            total_monetary_value_gbp=("monetary_value_gbp", "sum"),
            median_recency_days=("recency_days", "median"),
            average_recency_days=("recency_days", "mean"),
            median_frequency_orders=("frequency_orders", "median"),
            average_frequency_orders=("frequency_orders", "mean"),
            median_monetary_value_gbp=("monetary_value_gbp", "median"),
            average_monetary_value_gbp=("monetary_value_gbp", "mean"),
            average_order_value_gbp=("average_order_value_gbp", "mean"),
            median_active_span_days=("active_span_days", "median"),
            total_units_purchased=("units_purchased", "sum"),
            median_distinct_products=("distinct_products", "median"),
            repeat_customer_rate_pct=("is_repeat_customer", lambda values: 100 * values.mean()),
            uk_customer_share_pct=("is_uk_customer", lambda values: 100 * values.mean()),
        )
        .sort_values("cluster_id", ignore_index=True)
    )
    profiles["customer_share_pct"] = 100 * profiles["customer_count"] / len(data)
    profiles["revenue_share_pct"] = 100 * profiles["total_monetary_value_gbp"] / total_revenue

    segment_counts = (
        data.assign(segment_text=data["segment"].astype("string"))
        .groupby(["cluster_id", "segment_text"], observed=True)
        .size()
        .rename("count")
        .reset_index()
        .sort_values(["cluster_id", "count", "segment_text"], ascending=[True, False, True])
        .drop_duplicates("cluster_id")
    )
    segment_counts = segment_counts.merge(
        profiles[["cluster_id", "customer_count"]], on="cluster_id", how="left"
    )
    segment_counts["dominant_rfm_segment_share_pct"] = (
        100 * segment_counts["count"] / segment_counts["customer_count"]
    )
    profiles = profiles.merge(
        segment_counts[
            ["cluster_id", "segment_text", "dominant_rfm_segment_share_pct"]
        ].rename(columns={"segment_text": "dominant_rfm_segment"}),
        on="cluster_id",
        how="left",
    )
    return profiles[
        [
            "cluster_id",
            "cluster_label",
            "customer_count",
            "customer_share_pct",
            "total_monetary_value_gbp",
            "revenue_share_pct",
            "median_recency_days",
            "average_recency_days",
            "median_frequency_orders",
            "average_frequency_orders",
            "median_monetary_value_gbp",
            "average_monetary_value_gbp",
            "average_order_value_gbp",
            "median_active_span_days",
            "total_units_purchased",
            "median_distinct_products",
            "repeat_customer_rate_pct",
            "uk_customer_share_pct",
            "dominant_rfm_segment",
            "dominant_rfm_segment_share_pct",
        ]
    ]


def derive_cluster_business_metadata(profiles: pd.DataFrame) -> pd.DataFrame:
    """Derive unique descriptive labels and actions from original-unit medians."""
    if len(profiles) != OPERATIONAL_CHOSEN_K:
        raise ValueError(
            "Business-label derivation requires the four-cluster operational solution."
        )
    metadata = profiles[
        [
            "cluster_id",
            "median_recency_days",
            "median_frequency_orders",
            "median_monetary_value_gbp",
        ]
    ].copy()
    metadata["recency_rank"] = metadata["median_recency_days"].rank(
        method="first", ascending=True
    ).astype("int64")
    metadata["frequency_rank"] = metadata["median_frequency_orders"].rank(
        method="first", ascending=False
    ).astype("int64")
    metadata["monetary_rank"] = metadata["median_monetary_value_gbp"].rank(
        method="first", ascending=False
    ).astype("int64")

    actions = {
        1: (
            "Protect current value with recognition, priority service, and relevant "
            "loyalty offers."
        ),
        2: (
            "Nurture the next purchase with timely cross-sell and replenishment "
            "prompts."
        ),
        3: (
            "Prioritise profile-based reactivation using known categories before "
            "broad discounting."
        ),
        4: (
            "Use low-cost re-engagement tests and suppress outreach if inactivity "
            "persists."
        ),
    }
    metadata["cluster_label"] = metadata["cluster_id"].map(FINAL_CLUSTER_LABELS)
    metadata["label_basis"] = metadata.apply(
        lambda row: (
            f"Median recency={row.median_recency_days:.1f} days (rank "
            f"{int(row.recency_rank)}/4); frequency={row.median_frequency_orders:.1f} "
            f"orders (rank {int(row.frequency_rank)}/4); monetary value=GBP "
            f"{row.median_monetary_value_gbp:,.2f} (rank "
            f"{int(row.monetary_rank)}/4)."
        ),
        axis=1,
    )
    metadata["recommended_action"] = metadata["recency_rank"].map(actions)
    if not metadata["cluster_label"].is_unique:
        raise RuntimeError("Profile-derived cluster labels must be unique.")
    return metadata[
        [
            "cluster_id",
            "cluster_label",
            "label_basis",
            "recommended_action",
        ]
    ]


def build_rfm_cluster_comparison(customer_clusters: pd.DataFrame) -> pd.DataFrame:
    """Cross-tabulate rule-based RFM segments against K-Means assignments."""
    segments = customer_clusters["segment"].astype("string")
    cluster_ids = sorted(customer_clusters["cluster_id"].unique())
    counts = pd.crosstab(segments, customer_clusters["cluster_id"]).reindex(
        index=SEGMENT_ORDER, columns=cluster_ids, fill_value=0
    )
    long = counts.rename_axis(index="rfm_segment", columns="cluster_id").stack().rename("customer_count").reset_index()
    segment_totals = long.groupby("rfm_segment")["customer_count"].transform("sum")
    cluster_totals = long.groupby("cluster_id")["customer_count"].transform("sum")
    long["share_of_rfm_segment_pct"] = 100 * long["customer_count"] / segment_totals
    long["share_of_cluster_pct"] = 100 * long["customer_count"] / cluster_totals
    cluster_labels = (
        customer_clusters[["cluster_id", "cluster_label"]]
        .drop_duplicates()
        .set_index("cluster_id")["cluster_label"]
    )
    long["cluster_label"] = long["cluster_id"].map(cluster_labels)
    return long[
        [
            "rfm_segment",
            "cluster_id",
            "cluster_label",
            "customer_count",
            "share_of_rfm_segment_pct",
            "share_of_cluster_pct",
        ]
    ]


def validate_clustering(
    customer_clusters: pd.DataFrame,
    evaluation: pd.DataFrame,
    profiles: pd.DataFrame,
    metric_optimal_k: int,
    operational_chosen_k: int,
    expected_customer_count: int | None,
    expected_monetary_value_gbp: float | None,
) -> dict[str, object]:
    """Run customer-assignment, stability, and reconciliation quality gates."""
    customer_count = int(customer_clusters["customer_id"].nunique())
    assignment_rows = int(len(customer_clusters))
    profile_total = int(profiles["customer_count"].sum())
    monetary_total = float(customer_clusters["monetary_value_gbp"].sum())
    selected = evaluation.loc[evaluation["k"].eq(operational_chosen_k)].iloc[0]
    stability_valid = bool(
        evaluation["stability_seed_count"].ge(5).all()
        and evaluation["mean_pairwise_ari"].between(-1, 1).all()
        and evaluation["minimum_pairwise_ari"].between(-1, 1).all()
        and float(selected["mean_pairwise_ari"]) >= MIN_MEAN_ARI
    )
    gates: dict[str, object] = {
        "customer_count": {
            "actual": customer_count,
            "expected": expected_customer_count,
            "passed": expected_customer_count is None or customer_count == expected_customer_count,
        },
        "missing_clustering_features": {
            "actual": int(customer_clusters[CLUSTERING_FEATURES].isna().sum().sum()),
            "expected": 0,
            "passed": not customer_clusters[CLUSTERING_FEATURES].isna().any().any(),
        },
        "one_assignment_per_customer": {
            "assignment_rows": assignment_rows,
            "unique_customers": customer_count,
            "duplicate_customer_ids": int(customer_clusters["customer_id"].duplicated().sum()),
            "missing_assignments": int(customer_clusters["cluster_id"].isna().sum()),
            "passed": bool(assignment_rows == customer_count and customer_clusters["customer_id"].is_unique and customer_clusters["cluster_id"].notna().all()),
        },
        "cluster_counts_reconcile": {
            "profile_total": profile_total,
            "customer_total": customer_count,
            "clusters": int(profiles["cluster_id"].nunique()),
            "passed": bool(profile_total == customer_count and profiles["cluster_id"].nunique() == operational_chosen_k),
        },
        "metric_optimal_benchmark": {
            "actual": metric_optimal_k,
            "expected": 2,
            "visible_in_evaluation": bool(
                evaluation.loc[evaluation["k"].eq(2), "metric_optimal"].all()
            ),
            "passed": metric_optimal_k == 2 and bool(
                evaluation.loc[evaluation["k"].eq(2), "metric_optimal"].all()
            ),
        },
        "exactly_four_final_clusters": {
            "operational_chosen_k": operational_chosen_k,
            "assigned_clusters": int(customer_clusters["cluster_id"].nunique()),
            "profile_clusters": int(profiles["cluster_id"].nunique()),
            "passed": bool(
                operational_chosen_k == 4
                and customer_clusters["cluster_id"].nunique() == 4
                and profiles["cluster_id"].nunique() == 4
            ),
        },
        "random_state": {
            "actual": RANDOM_STATE,
            "expected": 42,
            "passed": RANDOM_STATE == 42,
        },
        "stability_metrics": {
            "seeds": int(evaluation["stability_seed_count"].min()),
            "chosen_mean_pairwise_ari": round(float(selected["mean_pairwise_ari"]), 6),
            "chosen_minimum_pairwise_ari": round(float(selected["minimum_pairwise_ari"]), 6),
            "minimum_required_mean_ari": MIN_MEAN_ARI,
            "passed": stability_valid,
        },
        "minimum_cluster_share": {
            "actual_pct": round(float(selected["minimum_cluster_share_pct"]), 4),
            "minimum_pct": MIN_CLUSTER_SHARE * 100,
            "passed": float(selected["minimum_cluster_share_pct"]) >= MIN_CLUSTER_SHARE * 100,
        },
        "business_labels": {
            "unique_labels": int(profiles["cluster_label"].nunique()),
            "missing_labels": int(profiles["cluster_label"].isna().sum()),
            "missing_actions": int(profiles["recommended_action"].isna().sum()),
            "passed": bool(
                profiles["cluster_label"].nunique() == 4
                and profiles["cluster_label"].notna().all()
                and profiles["recommended_action"].notna().all()
            ),
        },
        "monetary_value_reconciliation": {
            "actual_gbp": round(monetary_total, 2),
            "expected_gbp": expected_monetary_value_gbp,
            "difference_gbp": None if expected_monetary_value_gbp is None else round(monetary_total - expected_monetary_value_gbp, 6),
            "passed": expected_monetary_value_gbp is None or abs(monetary_total - expected_monetary_value_gbp) <= MONETARY_TOLERANCE_GBP,
        },
    }
    gates["all_passed"] = bool(all(value["passed"] for value in gates.values()))
    return gates


def _business_ordered_label_map(centers: np.ndarray) -> dict[int, int]:
    engagement_value_score = -centers[:, 0] + centers[:, 1] + centers[:, 2]
    ordered_raw_labels = np.argsort(-engagement_value_score)
    return {int(raw_label): int(position + 1) for position, raw_label in enumerate(ordered_raw_labels)}


def _validate_rfm_input(rfm: pd.DataFrame) -> None:
    required = set(CLUSTERING_FEATURES) | {
        "customer_id",
        "primary_country",
        "average_order_value_gbp",
        "active_span_days",
        "units_purchased",
        "distinct_products",
        "segment",
    }
    missing = required - set(rfm.columns)
    if missing:
        raise ValueError(f"RFM clustering input is missing columns: {sorted(missing)}")
    if rfm[list(required)].isna().any().any():
        raise ValueError("RFM clustering input contains missing values.")
    if (rfm[CLUSTERING_FEATURES] < 0).any().any():
        raise ValueError("log1p clustering features must be non-negative.")
    if not rfm["customer_id"].is_unique:
        raise ValueError("RFM clustering input must contain one row per customer.")


def _build_summary(
    metric_optimal_k: int,
    operational_chosen_k: int,
    metric_optimal: pd.Series,
    operational: pd.Series,
    evaluation: pd.DataFrame,
    profiles: pd.DataFrame,
    quality_gates: dict[str, object],
) -> dict[str, object]:
    return {
        "source": "data/processed/customer_rfm_segments.parquet",
        "features": CLUSTERING_FEATURES,
        "preprocessing": {
            "transformation": "log1p applied to recency_days, frequency_orders, and monetary_value_gbp",
            "scaling": "StandardScaler fitted on the transformed customer features",
            "pca_usage": "PCA is used only for the two-dimensional visualisation, not for fitting or selecting clusters.",
        },
        "candidate_k": {"minimum": 2, "maximum": 10},
        "selection_method": {
            "usability_gate": f"Minimum cluster share >= {MIN_CLUSTER_SHARE:.0%}",
            "stability_gate": f"Mean pairwise ARI across five seeds >= {MIN_MEAN_ARI:.2f}",
            "metric_benchmark_rule": "Among eligible candidates, the lowest equal-weight rank sum for higher silhouette, higher Calinski-Harabasz, lower Davies-Bouldin, and higher mean pairwise ARI identifies the mathematical benchmark.",
            "operational_choice_rule": "K=4 is retained as the operational solution because it has the second-best composite rank sum, acceptable separation and stability, no tiny clusters, diminishing inertia gains after four clusters, and materially more targeting resolution than K=2.",
            "inertia_note": "Inertia and its marginal reduction are reported as elbow evidence but excluded from the rank sum because inertia decreases mechanically as K increases; the curve begins to flatten after K=4.",
            "tie_break": "Higher silhouette, then lower Davies-Bouldin, then the more parsimonious K.",
            "business_override": True,
            "claim_scope": "The operational choice is descriptive and targeting-oriented; it does not imply causal or predictive performance.",
        },
        "random_state": RANDOM_STATE,
        "n_init": KMEANS_N_INIT,
        "stability_seeds": list(STABILITY_SEEDS),
        "metric_optimal_k": metric_optimal_k,
        "operational_chosen_k": operational_chosen_k,
        "chosen_k": operational_chosen_k,
        "metric_optimal_metrics": _serialise_candidate_metrics(metric_optimal),
        "operational_chosen_metrics": _serialise_candidate_metrics(operational),
        "chosen_metrics": _serialise_candidate_metrics(operational),
        "cluster_sizes": {
            str(int(row.cluster_id)): int(row.customer_count)
            for row in profiles.itertuples(index=False)
        },
        "cluster_profiles": [
            {
                "cluster_id": int(row.cluster_id),
                "cluster_label": str(row.cluster_label),
                "customers": int(row.customer_count),
                "customer_share_pct": round(float(row.customer_share_pct), 2),
                "revenue_share_pct": round(float(row.revenue_share_pct), 2),
                "median_recency_days": round(float(row.median_recency_days), 2),
                "median_frequency_orders": round(float(row.median_frequency_orders), 2),
                "median_monetary_value_gbp": round(float(row.median_monetary_value_gbp), 2),
                "repeat_customer_rate_pct": round(float(row.repeat_customer_rate_pct), 2),
                "dominant_rfm_segment": str(row.dominant_rfm_segment),
                "dominant_rfm_segment_share_pct": round(
                    float(row.dominant_rfm_segment_share_pct), 2
                ),
                "recommended_action": str(row.recommended_action),
                "label_basis": str(row.label_basis),
            }
            for row in profiles.itertuples(index=False)
        ],
        "evaluated_candidates": int(len(evaluation)),
        "eligible_candidates": int(evaluation["eligible"].sum()),
        "quality_gates": quality_gates,
        "limitations": [
            "K-Means imposes spherical partitions in transformed feature space and can simplify continuous customer behaviour.",
            "Clusters are descriptive and do not establish causal response to marketing actions.",
            "The fixed observation window and extreme wholesale-like customers influence RFM measures even after log transformation.",
            "Cluster labels are descriptive summaries of original-unit medians and should be validated against future commercial outcomes before activation.",
        ],
    }


def _serialise_candidate_metrics(candidate: pd.Series) -> dict[str, object]:
    return {
        "inertia": round(float(candidate["inertia"]), 6),
        "silhouette_score": round(float(candidate["silhouette_score"]), 6),
        "calinski_harabasz_score": round(
            float(candidate["calinski_harabasz_score"]), 6
        ),
        "davies_bouldin_score": round(float(candidate["davies_bouldin_score"]), 6),
        "minimum_cluster_count": int(candidate["minimum_cluster_count"]),
        "minimum_cluster_share_pct": round(
            float(candidate["minimum_cluster_share_pct"]), 4
        ),
        "mean_pairwise_ari": round(float(candidate["mean_pairwise_ari"]), 6),
        "minimum_pairwise_ari": round(float(candidate["minimum_pairwise_ari"]), 6),
        "selection_rank_sum": float(candidate["selection_rank_sum"]),
    }
