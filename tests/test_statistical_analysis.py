from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from retail_analytics.statistical_analysis import (
    CORRELATION_FEATURES,
    build_statistical_analysis,
    holm_adjust,
)


def _sample_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    size = 12
    frequency = np.array([1] * 5 + [2, 2, 3, 4, 5, 6, 8])
    monetary = frequency * 100 + np.arange(size)
    rfm = pd.DataFrame(
        {
            "customer_id": [f"C{i}" for i in range(size)],
            "primary_country": ["United Kingdom"] * 7 + ["France"] * 5,
            "recency_days": np.arange(size, 0, -1),
            "frequency_orders": frequency,
            "monetary_value_gbp": monetary.astype(float),
            "average_order_value_gbp": monetary / frequency,
            "active_span_days": np.arange(size) * 10,
            "units_purchased": frequency * 4,
            "distinct_products": frequency + 2,
        }
    )
    orders = pd.DataFrame(
        {
            "invoice_no": [f"I{i}" for i in range(20)],
            "country": ["United Kingdom"] * 12 + ["France"] * 8,
            "order_value_gbp": np.arange(1, 21, dtype=float) * 20,
        }
    )
    return rfm, orders


def test_holm_adjust_is_bounded_and_preserves_order() -> None:
    raw = np.array([0.04, 0.001, 0.03])
    adjusted = holm_adjust(raw)

    assert np.all((0 <= adjusted) & (adjusted <= 1))
    assert adjusted[1] == pytest.approx(0.003)
    assert np.all(adjusted >= raw)


def test_statistical_analysis_reports_every_prespecified_test() -> None:
    rfm, orders = _sample_inputs()
    results = build_statistical_analysis(
        rfm,
        orders,
        expected_customer_count=len(rfm),
        expected_monetary_value_gbp=float(rfm["monetary_value_gbp"].sum()),
    )

    assert results.correlation_matrix.shape == (
        len(CORRELATION_FEATURES),
        len(CORRELATION_FEATURES),
    )
    assert len(results.hypothesis_tests) == 24
    assert results.hypothesis_tests["adjusted_p_value"].between(0, 1).all()
    assert results.hypothesis_tests["business_interpretation"].str.len().gt(0).all()
    assert results.hypothesis_tests["limitations"].str.len().gt(0).all()
    assert results.summary["quality_gates"]["all_passed"] is True


def test_generated_statistical_outputs_when_available() -> None:
    path = Path("reports/statistics/hypothesis_tests.csv")
    if not path.exists():
        pytest.skip("Generated statistical outputs are not available yet.")
    tests = pd.read_csv(path)
    assert len(tests) == 24
    assert tests["adjusted_p_value"].between(0, 1).all()
