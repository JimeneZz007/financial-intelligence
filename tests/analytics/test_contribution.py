"""Decompositions must be exact: the parts always add up to the change they explain."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.analytics.contribution import (
    PVM_COLUMNS,
    margin_mix_rate,
    operating_income_bridge,
    price_volume_mix,
)
from backend.app.analytics.metrics import profit_and_loss


def _sales(rows: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """{product: (units, net_revenue)} -> frame indexed by product."""
    return pd.DataFrame.from_dict(rows, orient="index", columns=["units", "net_revenue"])


def _segments(rows: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """{segment: (net_revenue, gross_profit)} -> frame indexed by segment."""
    return pd.DataFrame.from_dict(rows, orient="index", columns=["net_revenue", "gross_profit"])


# --------------------------------------------------------------------------- #
# Price - volume - mix
# --------------------------------------------------------------------------- #
def test_pure_price_change() -> None:
    base = _sales({"A": (100, 1000.0), "B": (50, 1000.0)})
    current = _sales({"A": (100, 1100.0), "B": (50, 1000.0)})  # A: 10 -> 11 per unit
    effects = price_volume_mix(current, base)
    assert effects["price_effect"].sum() == pytest.approx(100.0)
    assert effects["volume_effect"].sum() == pytest.approx(0.0)
    assert effects["mix_effect"].sum() == pytest.approx(0.0)


def test_pure_volume_change_keeps_mix_at_zero() -> None:
    base = _sales({"A": (100, 1000.0), "B": (50, 1000.0)})
    current = _sales({"A": (120, 1200.0), "B": (60, 1200.0)})  # +20% units, same prices and mix
    effects = price_volume_mix(current, base)
    assert effects["volume_effect"].sum() == pytest.approx(400.0)
    assert effects["mix_effect"].sum() == pytest.approx(0.0)
    assert effects["price_effect"].sum() == pytest.approx(0.0)


def test_pure_mix_change() -> None:
    # Same total units and prices; units move from the cheap product to the expensive one.
    base = _sales({"cheap": (100, 1000.0), "premium": (100, 5000.0)})
    current = _sales({"cheap": (50, 500.0), "premium": (150, 7500.0)})
    effects = price_volume_mix(current, base)
    assert effects["volume_effect"].sum() == pytest.approx(0.0)
    assert effects["price_effect"].sum() == pytest.approx(0.0)
    assert effects["mix_effect"].sum() == pytest.approx(2000.0)


def test_new_and_discontinued_products_are_fully_explained() -> None:
    base = _sales({"old": (10, 100.0), "kept": (10, 200.0)})
    current = _sales({"new": (5, 400.0), "kept": (12, 264.0)})
    effects = price_volume_mix(current, base)
    total = effects[PVM_COLUMNS].to_numpy().sum()
    assert total == pytest.approx((400.0 + 264.0) - (100.0 + 200.0))
    assert effects.at["new", "price_effect"] == 0
    assert effects.at["old", "price_effect"] == 0


@pytest.mark.parametrize("seed", range(25))
def test_pvm_effects_always_sum_to_the_revenue_change(seed: int) -> None:
    rng = np.random.default_rng(seed)
    products = [f"P{i}" for i in range(12)]

    def random_period() -> pd.DataFrame:
        units = rng.integers(0, 500, len(products)).astype(float)  # zeros included on purpose
        prices = rng.uniform(5, 900, len(products))
        return pd.DataFrame({"units": units, "net_revenue": units * prices}, index=products)

    base, current = random_period(), random_period()
    effects = price_volume_mix(current, base)
    assert effects[PVM_COLUMNS].to_numpy().sum() == pytest.approx(
        current["net_revenue"].sum() - base["net_revenue"].sum()
    )


# --------------------------------------------------------------------------- #
# Margin mix / rate
# --------------------------------------------------------------------------- #
def test_pure_rate_change() -> None:
    base = _segments({"A": (1000.0, 300.0), "B": (1000.0, 500.0)})
    current = _segments({"A": (1000.0, 250.0), "B": (1000.0, 500.0)})  # A: 30% -> 25%
    effects = margin_mix_rate(current, base)
    assert effects["rate_effect"].sum() == pytest.approx(-0.025)
    assert effects["mix_effect"].sum() == pytest.approx(0.0)
    assert effects.at["B", "rate_effect"] == pytest.approx(0.0)


def test_pure_mix_change_towards_the_low_margin_segment() -> None:
    base = _segments({"low": (1000.0, 200.0), "high": (1000.0, 600.0)})  # total 40%
    current = _segments({"low": (1500.0, 300.0), "high": (500.0, 300.0)})  # total 30%
    effects = margin_mix_rate(current, base)
    assert effects["rate_effect"].sum() == pytest.approx(0.0)
    assert effects["mix_effect"].sum() == pytest.approx(-0.10)
    # Both segments explain half: one below-average segment grew, one above-average shrank.
    assert effects.at["low", "mix_effect"] == pytest.approx(-0.05)
    assert effects.at["high", "mix_effect"] == pytest.approx(-0.05)


@pytest.mark.parametrize("seed", range(25))
def test_margin_effects_always_sum_to_the_margin_change(seed: int) -> None:
    rng = np.random.default_rng(seed)
    segments = [f"S{i}" for i in range(6)]

    def random_period() -> pd.DataFrame:
        revenue = rng.uniform(100, 5000, len(segments))
        return pd.DataFrame(
            {
                "net_revenue": revenue,
                "gross_profit": revenue * rng.uniform(0.05, 0.6, len(segments)),
            },
            index=segments,
        )

    base, current = random_period(), random_period()
    effects = margin_mix_rate(current, base)
    margin_change = (
        current["gross_profit"].sum() / current["net_revenue"].sum()
        - base["gross_profit"].sum() / base["net_revenue"].sum()
    )
    assert effects[["rate_effect", "mix_effect"]].to_numpy().sum() == pytest.approx(margin_change)


def test_segment_present_in_one_period_only_has_no_rate_effect() -> None:
    base = _segments({"A": (1000.0, 300.0)})
    current = _segments({"A": (1000.0, 300.0), "new": (500.0, 300.0)})
    effects = margin_mix_rate(current, base)
    assert effects.at["new", "rate_effect"] == pytest.approx(0.0)
    assert effects[["rate_effect", "mix_effect"]].to_numpy().sum() == pytest.approx(
        600.0 / 1500.0 - 0.30
    )


# --------------------------------------------------------------------------- #
# Operating income bridge
# --------------------------------------------------------------------------- #
def _accounts(revenue: float, cogs: float, personnel: float, marketing: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("REVENUE", "Revenue", revenue),
            ("DIRECT_COST", "Cost of Sales", cogs),
            ("OPERATING_EXPENSE", "Personnel", personnel),
            ("OPERATING_EXPENSE", "Marketing", marketing),
        ],
        columns=["account_type", "account_group", "actual"],
    )


def test_bridge_steps_sum_from_base_to_current() -> None:
    base = _accounts(1000, 600, 200, 50)  # operating income 150
    current = _accounts(1200, 750, 210, 40)  # operating income 200
    steps = operating_income_bridge(current, base, base_label="Before", current_label="After")

    assert steps[0].amount == profit_and_loss(base).operating_income == 150
    assert steps[-1].amount == profit_and_loss(current).operating_income == 200
    effects = {s.key: s.amount for s in steps if s.kind == "effect"}
    assert effects == {
        "net_revenue": 200,
        "direct_costs": -150,
        "opex:Personnel": -10,
        "opex:Marketing": 10,
    }
    assert steps[0].amount + sum(effects.values()) == pytest.approx(steps[-1].amount)


def test_bridge_from_budget_uses_one_frame_with_two_columns() -> None:
    frame = _accounts(1000, 600, 200, 50).assign(budget=[1100, 640, 190, 50])
    steps = operating_income_bridge(
        frame, frame, base_column="budget", base_label="Budget", current_label="Actual"
    )
    effects = {s.key: s.amount for s in steps if s.kind == "effect"}
    assert steps[0].amount == 1100 - 640 - 240
    assert effects["net_revenue"] == -100
    assert effects["direct_costs"] == 40
    assert effects["opex:Personnel"] == -10
    assert steps[0].amount + sum(effects.values()) == pytest.approx(steps[-1].amount)


def test_bridge_handles_expense_groups_missing_on_one_side() -> None:
    base = _accounts(1000, 600, 200, 50)
    current = _accounts(1000, 600, 200, 50)[lambda f: f["account_group"] != "Marketing"]
    steps = operating_income_bridge(current, base, base_label="Before", current_label="After")
    effects = {s.key: s.amount for s in steps if s.kind == "effect"}
    assert effects["opex:Marketing"] == 50  # the expense disappeared: profit improves
    assert steps[0].amount + sum(effects.values()) == pytest.approx(steps[-1].amount)
