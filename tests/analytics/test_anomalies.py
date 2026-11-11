"""Robust anomaly detection on budget variance (pure functions, no database)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.analytics.anomalies import (
    MATERIALITY_SHARE_OF_REVENUE,
    MIN_DEVIATION,
    Z_THRESHOLD,
    detect_anomalies,
    modified_z_scores,
    score_variances,
)

MONTHS = pd.date_range("2023-01-01", periods=36, freq="MS")


def _series(
    account_code: str,
    account_type: str,
    budget: float,
    variance_pct: np.ndarray,
    unit: str = "U1",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "month": MONTHS,
            "business_unit_code": unit,
            "business_unit_name": f"Unit {unit}",
            "account_code": account_code,
            "account_name": f"Account {account_code}",
            "account_type": account_type,
            "budget": budget,
            "actual": budget * (1 + variance_pct),
        }
    )


def _history(expense_variance: np.ndarray, expense_budget: float = 50_000.0) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    revenue = _series("4000", "REVENUE", 1_000_000.0, rng.normal(0, 0.02, 36))
    expense = _series("6400", "OPERATING_EXPENSE", expense_budget, expense_variance)
    return pd.concat([revenue, expense], ignore_index=True)


def test_modified_z_score_matches_the_published_formula() -> None:
    values = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0])
    # median = 3, absolute deviations = [2, 1, 0, 1, 97], MAD = 1
    scores = modified_z_scores(values)
    assert scores.iloc[4] == pytest.approx(0.6745 * 97)
    assert scores.iloc[2] == 0


def test_constant_series_has_no_anomalies() -> None:
    scores = modified_z_scores(pd.Series([0.05] * 36))
    assert (scores == 0).all()


def test_mean_absolute_deviation_fallback_when_mad_is_zero() -> None:
    """A fixed cost: identical variance every month except one."""
    values = pd.Series([0.01] * 35 + [0.60])
    scores = modified_z_scores(values)
    assert scores.iloc[-1] > Z_THRESHOLD
    assert (scores.iloc[:-1] == 0).all()


def _bounded_noise(amplitude: float) -> np.ndarray:
    """Deterministic, bounded month-to-month variation (no chance outliers)."""
    return amplitude * np.sin(np.arange(36) * 2.4)


def test_single_spike_is_detected_and_ordinary_months_are_not() -> None:
    variance = _bounded_noise(0.04)
    variance[20] = 0.45
    found = detect_anomalies(_history(variance))
    expense = found[found["account_code"] == "6400"]
    assert list(expense["month"]) == [MONTHS[20]]
    assert expense.iloc[0]["robust_z"] > Z_THRESHOLD


def test_false_positive_rate_on_pure_noise_is_known_and_bounded() -> None:
    """With only 36 observations the MAD is itself noisy, so Gaussian noise alone
    sometimes crosses the threshold. The rate is documented in ANALYSIS_METHODOLOGY.md:
    about 9% of series show at least one flag, far above the asymptotic 0.05% per point.
    """
    rng = np.random.default_rng(0)
    series_with_flag = sum(
        bool((modified_z_scores(pd.Series(rng.normal(0, 1, 36))).abs() > Z_THRESHOLD).any())
        for _ in range(4000)
    )
    assert 0.05 < series_with_flag / 4000 < 0.12


def test_sustained_shift_does_not_mask_itself() -> None:
    """Six anomalous months out of 36 are all flagged: the median and MAD stay robust,
    whereas a mean / standard-deviation rule would be inflated by the shift itself."""
    rng = np.random.default_rng(2)
    variance = rng.normal(0, 0.03, 36)
    variance[10:16] += 0.35
    found = detect_anomalies(_history(variance))
    flagged = set(found.loc[found["account_code"] == "6400", "month"])
    assert set(MONTHS[10:16]) <= flagged


def test_systematic_planning_bias_is_not_an_anomaly() -> None:
    """A budget that is always 10% too low is a level, not an outlier."""
    variance = 0.10 + _bounded_noise(0.02)
    scored = score_variances(_history(variance))
    expense = scored[scored["account_code"] == "6400"]
    assert expense["typical_variance_pct"].iloc[0] == pytest.approx(0.10, abs=0.02)
    assert (expense["robust_z"].abs() <= Z_THRESHOLD).all()
    # The same months judged against zero instead of the series' own median would all
    # look like large deviations: centring on the median is what removes the bias.
    assert (expense["variance_pct"] > 0.07).all()


def test_materiality_separates_small_accounts_from_large_ones() -> None:
    rng = np.random.default_rng(4)
    variance = rng.normal(0, 0.04, 36)
    variance[5] = 0.60
    small = detect_anomalies(_history(variance, expense_budget=2_000.0))
    large = detect_anomalies(_history(variance, expense_budget=50_000.0))

    small_hit = small[small["account_code"] == "6400"].iloc[0]
    large_hit = large[large["account_code"] == "6400"].iloc[0]
    # Same statistical signal, different financial weight.
    assert small_hit["robust_z"] == pytest.approx(large_hit["robust_z"])
    assert not small_hit["is_material"]  # 1,200 of variance against ~5,000 threshold
    assert large_hit["is_material"]  # 30,000 of variance
    assert large_hit["materiality_threshold"] == pytest.approx(
        MATERIALITY_SHARE_OF_REVENUE * 1_000_000, rel=0.02
    )


def test_series_without_budget_are_ignored() -> None:
    history = _history(np.zeros(36))
    history.loc[history["account_code"] == "6400", "budget"] = 0.0
    scored = score_variances(history)
    assert "6400" not in set(scored["account_code"])


def test_each_series_is_scored_against_its_own_history() -> None:
    rng = np.random.default_rng(5)
    noisy = _series("6600", "OPERATING_EXPENSE", 40_000.0, rng.normal(0, 0.30, 36))
    stable = rng.normal(0, 0.01, 36)
    stable[8] = 0.20  # far outside this series' own noise, well inside the noisy one's
    history = pd.concat(
        [
            _series("4000", "REVENUE", 1_000_000.0, rng.normal(0, 0.02, 36)),
            noisy,
            _series("6100", "OPERATING_EXPENSE", 200_000.0, stable),
        ],
        ignore_index=True,
    )
    found = detect_anomalies(history)
    assert MONTHS[8] in set(found.loc[found["account_code"] == "6100", "month"])


def test_negligible_deviations_of_a_near_constant_series_are_not_flagged() -> None:
    """Fixed costs: a 0.3 pp step caused by budget rounding has an enormous z-score
    (there is no dispersion to compare with) but is not worth anyone's attention."""
    variance = np.full(36, 0.010)
    variance[32:] = 0.013
    history = _history(variance)
    scored = score_variances(history)
    step = scored[(scored["account_code"] == "6400") & (scored["month"] >= MONTHS[32])]
    assert (step["robust_z"].abs() > Z_THRESHOLD).all()
    assert (step["variance_pct"] - step["typical_variance_pct"]).abs().max() < MIN_DEVIATION
    assert "6400" not in set(detect_anomalies(history)["account_code"])
