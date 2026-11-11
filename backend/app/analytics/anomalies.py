"""Anomaly detection on budget variance with a robust (median / MAD) z-score.

Signal
    For each business unit x account series, the monthly budget variance in percent,
    v_t = (actual_t - budget_t) / budget_t. The budget already encodes the expected level,
    trend and seasonality, so v_t is a de-seasonalised residual.

Score
    Modified z-score of Iglewicz & Hoaglin (1993):

        z_t = 0.6745 * (v_t - median(v)) / MAD(v)

    The median and the MAD are barely moved by the anomalies themselves, unlike the mean
    and the standard deviation. Centring on the median also removes any systematic
    planning bias of the series (for example a budget that is always 2% optimistic).
    If MAD = 0 (more than half of the months share one value) the mean absolute deviation
    is used instead: z_t = (v_t - median) / (1.253314 * MeanAD).

Decision
    A month is *anomalous* when |z_t| > 3.5 (the cut-off recommended by the authors) and
    its variance is at least 1 percentage point away from the series' median. The second
    condition matters for nearly constant series (rent, depreciation): their dispersion is
    so small that budget rounding alone produces huge z-scores for negligible differences.
    It is *material* when the absolute variance also reaches 0.5% of the business unit's
    average monthly net revenue.

Limits
    The method flags deviations from a series' own typical variance. It cannot see an
    effect that persists for most of the history (it becomes the "typical" level) nor
    effects diluted below the noise of the series. It states that a month is unusual,
    never why.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.analytics.metrics import REVENUE

Z_THRESHOLD = 3.5
MIN_DEVIATION = 0.01  # minimum distance from the series' median variance, as a ratio
MAD_SCALE = 0.6745
MEAN_AD_SCALE = 1.253314
MATERIALITY_SHARE_OF_REVENUE = 0.005
MIN_OBSERVATIONS = 12

ANOMALY_COLUMNS = [
    "month",
    "business_unit_code",
    "business_unit_name",
    "account_code",
    "account_name",
    "account_type",
    "actual",
    "budget",
    "variance",
    "variance_pct",
    "typical_variance_pct",
    "robust_z",
    "materiality_threshold",
    "is_material",
]


def modified_z_scores(values: pd.Series) -> pd.Series:
    """Robust z-scores of a series; all zeros when the series has no dispersion."""
    median = values.median()
    deviations = (values - median).abs()
    mad = deviations.median()
    if mad > 0:
        return MAD_SCALE * (values - median) / mad
    mean_ad = deviations.mean()
    if mean_ad > 0:
        return (values - median) / (MEAN_AD_SCALE * mean_ad)
    return values * 0.0


def score_variances(history: pd.DataFrame) -> pd.DataFrame:
    """Score every month of every business unit x account series.

    ``history`` is the account-level frame over the *whole* available history: the
    typical behaviour of a series must not depend on the period a user is looking at.
    """
    frame = history[history["budget"] > 0].copy()
    frame["variance"] = frame["actual"] - frame["budget"]
    frame["variance_pct"] = frame["variance"] / frame["budget"]

    series_key = ["business_unit_code", "account_code"]
    grouped = frame.groupby(series_key, observed=True)["variance_pct"]
    frame["typical_variance_pct"] = grouped.transform("median")
    frame["robust_z"] = grouped.transform(modified_z_scores)
    frame["observations"] = grouped.transform("size")

    average_revenue = (
        frame[frame["account_type"] == REVENUE]
        .groupby("business_unit_code", observed=True)["actual"]
        .mean()
    )
    frame["materiality_threshold"] = (
        frame["business_unit_code"].map(average_revenue).astype(float)
        * MATERIALITY_SHARE_OF_REVENUE
    )
    frame["is_material"] = frame["variance"].abs() >= frame["materiality_threshold"]
    return frame


def detect_anomalies(history: pd.DataFrame) -> pd.DataFrame:
    """Months whose budget variance is statistically unusual for their own series."""
    scored = score_variances(history)
    deviation = (scored["variance_pct"] - scored["typical_variance_pct"]).abs()
    flagged = scored[
        (scored["robust_z"].abs() > Z_THRESHOLD)
        & (deviation >= MIN_DEVIATION)
        & (scored["observations"] >= MIN_OBSERVATIONS)
    ]
    ordered = flagged.assign(_severity=np.abs(flagged["robust_z"])).sort_values(
        ["is_material", "_severity"], ascending=[False, False]
    )
    return ordered[ANOMALY_COLUMNS].reset_index(drop=True)
