"""Output helpers: convert numpy / pandas numbers into JSON-safe rounded values."""

from __future__ import annotations

import math
from typing import Any

from backend.app.analytics.metrics import favorability, pct_change, profit_impact
from backend.app.schemas import Measure

RATIO_DECIMALS = 6


def money(value: Any) -> float:
    return round(float(value), 2)


def money_or_none(value: Any) -> float | None:
    return None if _missing(value) else money(value)


def ratio(value: Any) -> float | None:
    return None if _missing(value) else round(float(value), RATIO_DECIMALS)


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and not math.isfinite(value))


def measure(actual: float, budget: float, *, higher_is_better: bool) -> Measure:
    variance = actual - budget
    return Measure(
        actual=money(actual),
        budget=money(budget),
        variance=money(variance),
        variance_pct=ratio(pct_change(actual, budget)),
        status=favorability(variance, budget, higher_is_better=higher_is_better),
    )


def impact(variance: float, *, higher_is_better: bool) -> float:
    return money(profit_impact(variance, higher_is_better=higher_is_better))
