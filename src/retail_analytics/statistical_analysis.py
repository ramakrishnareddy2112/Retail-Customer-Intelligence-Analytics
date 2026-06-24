"""Non-parametric statistical analysis of validated retail outputs."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from retail_analytics.customer_analytics import (
    EXPECTED_CUSTOMER_COUNT,
    EXPECTED_MONETARY_VALUE_GBP,
    MONETARY_TOLERANCE_GBP,
)


CORRELATION_FEATURES = [
    "recency_days",
    "frequency_orders",
    "monetary_value_gbp",
    "average_order_value_gbp",
    "active_span_days",
    "units_purchased",
    "distinct_products",
]
ALPHA = 0.05


@dataclass(frozen=True)
class StatisticalAnalysisResults:
    """Container for statistical tables and JSON-ready findings."""

    hypothesis_tests: pd.DataFrame
    correlation_matrix: pd.DataFrame
    summary: dict[str, object]


def holm_adjust(p_values: pd.Series | np.ndarray | list[float]) -> np.ndarray:
    """Return Holm step-down adjusted p-values in their original order."""
    values = np.asarray(p_values, dtype="float64")
    if values.ndim != 1 or np.isnan(values).any():
        raise ValueError("Holm adjustment requires a one-dimensional non-missing array.")
    order = np.argsort(values)
    sorted_values = values[order]
    multipliers = np.arange(len(values), 0, -1)
    adjusted_sorted = np.maximum.accumulate(sorted_values * multipliers).clip(0, 1)
    adjusted = np.empty_like(adjusted_sorted)
    adjusted[order] = adjusted_sorted
    return adjusted


def build_statistical_analysis(
    rfm: pd.DataFrame,
    orders: pd.DataFrame,
    expected_customer_count: int | None = EXPECTED_CUSTOMER_COUNT,
    expected_monetary_value_gbp: float | None = EXPECTED_MONETARY_VALUE_GBP,
) -> StatisticalAnalysisResults:
    """Run the prespecified correlation and group-comparison tests."""
    _validate_inputs(rfm, orders)
    customers = rfm.copy()
    order_values = orders.copy()
    customers["is_repeat_customer"] = customers["frequency_orders"].ge(2)
    customers["geography"] = np.where(
        customers["primary_country"].eq("United Kingdom"),
        "United Kingdom",
        "International",
    )
    order_values["geography"] = np.where(
        order_values["country"].eq("United Kingdom"),
        "United Kingdom",
        "International",
    )

    correlation_matrix = customers[CORRELATION_FEATURES].corr(method="spearman")
    rows = _correlation_test_rows(customers)
    rows.extend(_group_test_rows(customers, order_values))
    tests = pd.DataFrame(rows)
    tests["adjusted_p_value"] = np.nan
    for family, indices in tests.groupby("family").groups.items():
        del family
        tests.loc[indices, "adjusted_p_value"] = holm_adjust(
            tests.loc[indices, "raw_p_value"]
        )
    tests["p_adjustment"] = "Holm (within prespecified test family)"
    tests["alpha"] = ALPHA
    tests["reject_null"] = tests["adjusted_p_value"].lt(ALPHA)
    tests = tests[
        [
            "test_id",
            "family",
            "test_name",
            "comparison",
            "null_hypothesis",
            "alternative_hypothesis",
            "sample_size_total",
            "sample_size_group_1",
            "sample_size_group_2",
            "group_1",
            "group_2",
            "group_1_summary",
            "group_2_summary",
            "statistic_name",
            "statistic",
            "raw_p_value",
            "adjusted_p_value",
            "p_adjustment",
            "effect_size_name",
            "effect_size",
            "effect_magnitude",
            "alpha",
            "reject_null",
            "business_interpretation",
            "limitations",
        ]
    ]

    quality_gates = _quality_gates(
        customers,
        order_values,
        expected_customer_count,
        expected_monetary_value_gbp,
    )
    summary = _build_summary(tests, correlation_matrix, customers, order_values, quality_gates)
    return StatisticalAnalysisResults(tests, correlation_matrix, summary)


def _correlation_test_rows(customers: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for left, right in combinations(CORRELATION_FEATURES, 2):
        statistic, p_value = stats.spearmanr(customers[left], customers[right])
        direction = "positive" if statistic > 0 else "negative"
        magnitude = _effect_magnitude(statistic)
        rows.append(
            {
                "test_id": f"spearman__{left}__{right}",
                "family": "spearman_correlations",
                "test_name": "Spearman rank correlation",
                "comparison": f"{left} versus {right}",
                "null_hypothesis": f"The population Spearman correlation between {left} and {right} is zero.",
                "alternative_hypothesis": f"The population Spearman correlation between {left} and {right} is not zero.",
                "sample_size_total": int(len(customers)),
                "sample_size_group_1": np.nan,
                "sample_size_group_2": np.nan,
                "group_1": left,
                "group_2": right,
                "group_1_summary": f"median={customers[left].median():.4f}",
                "group_2_summary": f"median={customers[right].median():.4f}",
                "statistic_name": "Spearman rho",
                "statistic": float(statistic),
                "raw_p_value": float(p_value),
                "effect_size_name": "Spearman rho",
                "effect_size": float(statistic),
                "effect_magnitude": magnitude,
                "business_interpretation": (
                    f"The customer metrics have a {magnitude} {direction} monotonic association "
                    f"(rho={statistic:.3f}). Statistical evidence should be weighed against the "
                    "effect magnitude before it informs targeting or operational decisions."
                ),
                "limitations": (
                    "Association is not causation; tied ranks, skewed customer behaviour, wholesale "
                    "buyers, and the fixed observation window can influence the coefficient."
                ),
            }
        )
    return rows


def _group_test_rows(
    customers: pd.DataFrame, orders: pd.DataFrame
) -> list[dict[str, object]]:
    repeat = customers.loc[customers["is_repeat_customer"], "monetary_value_gbp"]
    one_time = customers.loc[~customers["is_repeat_customer"], "monetary_value_gbp"]
    repeat_u = stats.mannwhitneyu(repeat, one_time, alternative="two-sided")
    repeat_effect = _rank_biserial(repeat_u.statistic, len(repeat), len(one_time))

    uk_orders = orders.loc[orders["geography"].eq("United Kingdom"), "order_value_gbp"]
    international_orders = orders.loc[
        orders["geography"].eq("International"), "order_value_gbp"
    ]
    order_u = stats.mannwhitneyu(uk_orders, international_orders, alternative="two-sided")
    order_effect = _rank_biserial(
        order_u.statistic, len(uk_orders), len(international_orders)
    )

    contingency = pd.crosstab(customers["geography"], customers["is_repeat_customer"])
    contingency = contingency.reindex(
        index=["United Kingdom", "International"], columns=[False, True], fill_value=0
    )
    chi = stats.chi2_contingency(contingency.to_numpy(), correction=False)
    cramer_v = float(np.sqrt(chi.statistic / contingency.to_numpy().sum()))
    uk_repeat = float(
        customers.loc[customers["geography"].eq("United Kingdom"), "is_repeat_customer"].mean()
    )
    intl_repeat = float(
        customers.loc[customers["geography"].eq("International"), "is_repeat_customer"].mean()
    )

    return [
        {
            "test_id": "mann_whitney__repeat_vs_one_time_customer_value",
            "family": "confirmatory_group_tests",
            "test_name": "Mann-Whitney U",
            "comparison": "Customer monetary value: repeat versus one-time customers",
            "null_hypothesis": "Repeat and one-time customers have the same monetary-value distribution.",
            "alternative_hypothesis": "Repeat and one-time customers have different monetary-value distributions.",
            "sample_size_total": int(len(repeat) + len(one_time)),
            "sample_size_group_1": int(len(repeat)),
            "sample_size_group_2": int(len(one_time)),
            "group_1": "Repeat customers",
            "group_2": "One-time customers",
            "group_1_summary": f"median_gbp={repeat.median():.2f}",
            "group_2_summary": f"median_gbp={one_time.median():.2f}",
            "statistic_name": "Mann-Whitney U",
            "statistic": float(repeat_u.statistic),
            "raw_p_value": float(repeat_u.pvalue),
            "effect_size_name": "Rank-biserial correlation",
            "effect_size": repeat_effect,
            "effect_magnitude": _effect_magnitude(repeat_effect),
            "business_interpretation": (
                f"Repeat customers have a median value of GBP {repeat.median():,.2f} versus "
                f"GBP {one_time.median():,.2f} for one-time customers; the distributional "
                f"difference has a {_effect_magnitude(repeat_effect)} effect (rank-biserial "
                f"r={repeat_effect:.3f}). The effect size, not significance alone, indicates "
                "how meaningful this separation may be for retention investment."
            ),
            "limitations": (
                "Customer value accumulates over unequal observed lifetimes, repeat status is "
                "defined from the same order history, and the test does not isolate causal lift."
            ),
        },
        {
            "test_id": "mann_whitney__uk_vs_international_order_value",
            "family": "confirmatory_group_tests",
            "test_name": "Mann-Whitney U",
            "comparison": "Order value: United Kingdom versus international orders",
            "null_hypothesis": "UK and international orders have the same order-value distribution.",
            "alternative_hypothesis": "UK and international orders have different order-value distributions.",
            "sample_size_total": int(len(uk_orders) + len(international_orders)),
            "sample_size_group_1": int(len(uk_orders)),
            "sample_size_group_2": int(len(international_orders)),
            "group_1": "United Kingdom orders",
            "group_2": "International orders",
            "group_1_summary": f"median_gbp={uk_orders.median():.2f}",
            "group_2_summary": f"median_gbp={international_orders.median():.2f}",
            "statistic_name": "Mann-Whitney U",
            "statistic": float(order_u.statistic),
            "raw_p_value": float(order_u.pvalue),
            "effect_size_name": "Rank-biserial correlation",
            "effect_size": order_effect,
            "effect_magnitude": _effect_magnitude(order_effect),
            "business_interpretation": (
                f"Median UK order value is GBP {uk_orders.median():,.2f} versus GBP "
                f"{international_orders.median():,.2f} internationally; the difference has a "
                f"{_effect_magnitude(order_effect)} effect (rank-biserial r={order_effect:.3f}). "
                "Commercial relevance should be assessed alongside fulfilment cost, market mix, "
                "and order volume."
            ),
            "limitations": (
                "Orders from the same customer are not fully independent, country mix is uneven, "
                "and the data omit shipping cost, margin, exchange-rate effects, and promotions."
            ),
        },
        {
            "test_id": "chi_square__geography_vs_repeat_status",
            "family": "confirmatory_group_tests",
            "test_name": "Pearson chi-square test of independence",
            "comparison": "Repeat-customer status: United Kingdom versus international customers",
            "null_hypothesis": "Repeat-customer status is independent of UK versus international geography.",
            "alternative_hypothesis": "Repeat-customer status is associated with UK versus international geography.",
            "sample_size_total": int(len(customers)),
            "sample_size_group_1": int((customers["geography"] == "United Kingdom").sum()),
            "sample_size_group_2": int((customers["geography"] == "International").sum()),
            "group_1": "United Kingdom customers",
            "group_2": "International customers",
            "group_1_summary": f"repeat_proportion={uk_repeat:.4f}",
            "group_2_summary": f"repeat_proportion={intl_repeat:.4f}",
            "statistic_name": "Chi-square",
            "statistic": float(chi.statistic),
            "raw_p_value": float(chi.pvalue),
            "effect_size_name": "Cramer's V",
            "effect_size": cramer_v,
            "effect_magnitude": _effect_magnitude(cramer_v),
            "business_interpretation": (
                f"Repeat rates are {uk_repeat:.1%} for UK customers and {intl_repeat:.1%} for "
                f"international customers. Geography has a {_effect_magnitude(cramer_v)} "
                f"association with repeat status (Cramer's V={cramer_v:.3f}); this should not "
                "be treated as a strong segmentation signal solely because of its p-value."
            ),
            "limitations": (
                "Primary country compresses multi-country histories, geography may proxy for "
                "shipping access or acquisition mix, and the analysis is observational."
            ),
        },
    ]


def _rank_biserial(u_statistic: float, n_group_1: int, n_group_2: int) -> float:
    return float(2 * u_statistic / (n_group_1 * n_group_2) - 1)


def _effect_magnitude(effect: float) -> str:
    magnitude = abs(float(effect))
    if magnitude < 0.1:
        return "negligible"
    if magnitude < 0.3:
        return "small"
    if magnitude < 0.5:
        return "moderate"
    return "large"


def _validate_inputs(rfm: pd.DataFrame, orders: pd.DataFrame) -> None:
    customer_columns = set(CORRELATION_FEATURES) | {
        "customer_id",
        "primary_country",
    }
    order_columns = {"invoice_no", "country", "order_value_gbp"}
    missing_customers = customer_columns - set(rfm.columns)
    missing_orders = order_columns - set(orders.columns)
    if missing_customers or missing_orders:
        raise ValueError(
            "Statistical inputs are missing required columns: "
            f"customers={sorted(missing_customers)}, orders={sorted(missing_orders)}"
        )
    if rfm[list(customer_columns)].isna().any().any():
        raise ValueError("Customer statistical inputs contain missing values.")
    if orders[list(order_columns)].isna().any().any():
        raise ValueError("Order statistical inputs contain missing values.")


def _quality_gates(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    expected_customer_count: int | None,
    expected_monetary_value_gbp: float | None,
) -> dict[str, object]:
    customer_count = int(customers["customer_id"].nunique())
    monetary_total = float(customers["monetary_value_gbp"].sum())
    gates: dict[str, object] = {
        "customer_count": {
            "actual": customer_count,
            "expected": expected_customer_count,
            "passed": expected_customer_count is None or customer_count == expected_customer_count,
        },
        "missing_analysis_values": {
            "actual": int(customers[CORRELATION_FEATURES].isna().sum().sum()),
            "expected": 0,
            "passed": not customers[CORRELATION_FEATURES].isna().any().any(),
        },
        "unique_orders": {
            "actual": int(orders["invoice_no"].nunique()),
            "rows": int(len(orders)),
            "passed": bool(orders["invoice_no"].is_unique),
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


def _build_summary(
    tests: pd.DataFrame,
    correlations: pd.DataFrame,
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    quality_gates: dict[str, object],
) -> dict[str, object]:
    correlation_rows = tests.loc[tests["family"].eq("spearman_correlations")]
    strongest = correlation_rows.reindex(
        correlation_rows["effect_size"].abs().sort_values(ascending=False).index
    ).head(5)
    confirmatory = tests.loc[tests["family"].eq("confirmatory_group_tests")]
    return {
        "sources": {
            "customers": "data/processed/customer_rfm_segments.parquet",
            "orders": "reports/eda_tables/order_summary.csv",
        },
        "methodology": {
            "alpha": ALPHA,
            "p_value_adjustment": "Holm correction within the 21-correlation family and within the 3 confirmatory group-test family.",
            "correlations": "Two-sided Spearman rank correlations.",
            "continuous_group_tests": "Two-sided Mann-Whitney U tests with rank-biserial effect sizes.",
            "categorical_test": "Pearson chi-square test without continuity correction and Cramer's V effect size.",
            "importance_note": "Statistical significance is reported as evidence, not as a substitute for effect magnitude or commercial importance.",
        },
        "sample": {
            "customers": int(len(customers)),
            "orders": int(len(orders)),
            "repeat_customers": int(customers["is_repeat_customer"].sum()),
            "one_time_customers": int((~customers["is_repeat_customer"]).sum()),
            "uk_customers": int(customers["geography"].eq("United Kingdom").sum()),
            "international_customers": int(customers["geography"].eq("International").sum()),
            "uk_orders": int(orders["geography"].eq("United Kingdom").sum()),
            "international_orders": int(orders["geography"].eq("International").sum()),
        },
        "tests": {
            "total": int(len(tests)),
            "correlations": int(len(correlation_rows)),
            "confirmatory_group_tests": int(len(confirmatory)),
            "holm_adjusted_significant": int(tests["reject_null"].sum()),
        },
        "strongest_correlations": [
            {
                "comparison": row.comparison,
                "spearman_rho": round(float(row.effect_size), 4),
                "adjusted_p_value": float(row.adjusted_p_value),
                "effect_magnitude": row.effect_magnitude,
            }
            for row in strongest.itertuples(index=False)
        ],
        "confirmatory_results": [
            {
                "test_id": row.test_id,
                "statistic": float(row.statistic),
                "raw_p_value": float(row.raw_p_value),
                "adjusted_p_value": float(row.adjusted_p_value),
                "effect_size_name": row.effect_size_name,
                "effect_size": round(float(row.effect_size), 4),
                "effect_magnitude": row.effect_magnitude,
                "reject_null": bool(row.reject_null),
                "business_interpretation": row.business_interpretation,
                "limitations": row.limitations,
            }
            for row in confirmatory.itertuples(index=False)
        ],
        "correlation_matrix_minimum": round(float(correlations.min().min()), 4),
        "correlation_matrix_maximum": round(float(correlations.max().max()), 4),
        "quality_gates": quality_gates,
        "general_limitations": [
            "The analysis is observational and cannot identify causal effects.",
            "The fixed 2009-2011 observation window creates unequal customer exposure time.",
            "The source lacks margin, demographics, acquisition channel, promotion, and shipping-cost fields.",
            "Large samples can make commercially negligible effects statistically significant.",
        ],
    }
