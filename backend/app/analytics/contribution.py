"""Contribution analysis: exact decompositions of a change into additive effects.

Every function here returns parts that sum exactly to the total change it explains
(verified by tests). The decompositions are arithmetic identities: they describe *where*
a change sits, not *why* it happened.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.app.analytics.metrics import OPERATING_EXPENSE, profit_and_loss


# --------------------------------------------------------------------------- #
# Operating income bridge
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BridgeStep:
    key: str
    label: str
    kind: str  # "total" for the two end points, "effect" for the steps between them
    amount: float  # for effects: contribution to operating income (positive = improves it)


def operating_income_bridge(
    current: pd.DataFrame,
    base: pd.DataFrame,
    *,
    current_column: str = "actual",
    base_column: str = "actual",
    base_label: str,
    current_label: str,
) -> list[BridgeStep]:
    """Walk from the base operating income to the current one.

        OI_current - OI_base = dRevenue - dDirectCosts - sum_g dOpex_g

    Cost increases appear as negative steps. ``current`` and ``base`` are account-level
    frames; passing the same frame with ``base_column='budget'`` yields the bridge from
    budget to actual.
    """
    current_pnl = profit_and_loss(current, current_column)
    base_pnl = profit_and_loss(base, base_column)

    def opex_by_group(frame: pd.DataFrame, column: str) -> pd.Series:
        opex = frame[frame["account_type"] == OPERATING_EXPENSE]
        return opex.groupby("account_group")[column].sum()

    opex_change = opex_by_group(current, current_column).sub(
        opex_by_group(base, base_column), fill_value=0.0
    )
    steps = [
        BridgeStep("base", base_label, "total", base_pnl.operating_income),
        BridgeStep(
            "net_revenue", "Net revenue", "effect", current_pnl.net_revenue - base_pnl.net_revenue
        ),
        BridgeStep(
            "direct_costs",
            "Direct costs",
            "effect",
            -(current_pnl.direct_costs - base_pnl.direct_costs),
        ),
        *(
            BridgeStep(f"opex:{group}", group, "effect", -float(change))
            for group, change in opex_change.sort_values(ascending=False).items()
        ),
        BridgeStep("current", current_label, "total", current_pnl.operating_income),
    ]
    return steps


# --------------------------------------------------------------------------- #
# Price - volume - mix
# --------------------------------------------------------------------------- #
PVM_COLUMNS = ["volume_effect", "mix_effect", "price_effect"]


def price_volume_mix(current: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """Decompose the change in net revenue per product into volume, mix and price.

    Inputs are frames indexed by product with columns ``units`` and ``net_revenue``.
    With q = units, p = net revenue per unit, Q = total units and s = q / Q:

        volume_i = (Q1 - Q0) * s0_i * p0_i        more or fewer units at the base mix
        mix_i    = (s1_i - s0_i) * Q1 * p0_i      shift of units between products
        price_i  = (p1_i - p0_i) * q1_i           change in realised unit price

    and  sum_i(volume_i + mix_i + price_i) = revenue_1 - revenue_0  exactly.
    A product present in only one period has no price change: its whole effect is mix.
    """
    index = current.index.union(base.index)
    cur = current.reindex(index, fill_value=0.0)
    old = base.reindex(index, fill_value=0.0)

    q1, q0 = cur["units"].astype(float), old["units"].astype(float)
    p1 = (cur["net_revenue"] / q1.where(q1 != 0)).astype(float)
    p0 = (old["net_revenue"] / q0.where(q0 != 0)).astype(float)
    # Where a product did not exist in one period, use the other period's price.
    p0, p1 = p0.fillna(p1).fillna(0.0), p1.fillna(p0).fillna(0.0)

    total_q1, total_q0 = q1.sum(), q0.sum()
    s1 = q1 / total_q1 if total_q1 else q1 * 0.0
    s0 = q0 / total_q0 if total_q0 else q0 * 0.0

    return pd.DataFrame(
        {
            "base_revenue": old["net_revenue"],
            "current_revenue": cur["net_revenue"],
            "volume_effect": (total_q1 - total_q0) * s0 * p0,
            "mix_effect": (s1 - s0) * total_q1 * p0,
            "price_effect": (p1 - p0) * q1,
        },
        index=index,
    )


# --------------------------------------------------------------------------- #
# Margin: mix versus rate
# --------------------------------------------------------------------------- #
def margin_mix_rate(current: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """Decompose the change in gross margin (in ratio points) by segment.

    Inputs are frames indexed by segment with columns ``net_revenue`` and ``gross_profit``.
    With w = share of revenue, m = segment margin and M0 = total base margin:

        rate_i = w1_i * (m1_i - m0_i)             the segment became more / less profitable
        mix_i  = (w1_i - w0_i) * (m0_i - M0)      revenue moved towards / away from it

    and  sum_i(rate_i + mix_i) = M1 - M0  exactly (when total revenue is non-zero).
    """
    index = current.index.union(base.index)
    cur = current.reindex(index, fill_value=0.0)
    old = base.reindex(index, fill_value=0.0)

    revenue1, revenue0 = cur["net_revenue"].sum(), old["net_revenue"].sum()
    w1 = cur["net_revenue"] / revenue1 if revenue1 else cur["net_revenue"] * 0.0
    w0 = old["net_revenue"] / revenue0 if revenue0 else old["net_revenue"] * 0.0
    m1 = (cur["gross_profit"] / cur["net_revenue"].where(cur["net_revenue"] != 0)).astype(float)
    m0 = (old["gross_profit"] / old["net_revenue"].where(old["net_revenue"] != 0)).astype(float)
    # A segment absent in one period has no rate change, only a mix effect.
    m1_filled, m0_filled = m1.fillna(m0).fillna(0.0), m0.fillna(m1).fillna(0.0)
    total_m0 = old["gross_profit"].sum() / revenue0 if revenue0 else 0.0

    return pd.DataFrame(
        {
            "base_share": w0,
            "current_share": w1,
            "base_margin": m0,
            "current_margin": m1,
            "rate_effect": w1 * (m1_filled - m0_filled),
            "mix_effect": (w1 - w0) * (m0_filled - total_m0),
        },
        index=index,
    )
