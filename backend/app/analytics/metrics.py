"""Core financial formulas. Every KPI in the product is built from these functions.

Definitions (see docs/KPI_CATALOG.md):

    gross profit       = net revenue - direct costs
    operating income   = gross profit - operating expenses
    margin             = profit / net revenue          (ratio of sums, never mean of ratios)
    variance           = actual - reference
    variance %         = variance / |reference|
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

REVENUE, DIRECT_COST, OPERATING_EXPENSE = "REVENUE", "DIRECT_COST", "OPERATING_EXPENSE"

Favorability = Literal["favorable", "unfavorable", "on_target"]

# A variance smaller than this share of its reference is reported as "on target".
ON_TARGET_TOLERANCE = 0.005


def safe_ratio(numerator: float, denominator: float) -> float | None:
    """Division that returns None instead of failing or producing infinities."""
    if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
        return None
    return float(numerator) / float(denominator)


def pct_change(current: float, reference: float) -> float | None:
    """Relative change against a reference; the sign follows the direction of the change."""
    return safe_ratio(current - reference, abs(reference))


def favorability(variance: float, reference: float, *, higher_is_better: bool) -> Favorability:
    """Classify a variance (actual - reference) by its effect on profit."""
    relative = safe_ratio(variance, abs(reference))
    if variance == 0 or (relative is not None and abs(relative) < ON_TARGET_TOLERANCE):
        return "on_target"
    return "favorable" if (variance > 0) == higher_is_better else "unfavorable"


def profit_impact(variance: float, *, higher_is_better: bool) -> float:
    """Variance expressed as its effect on operating income (positive = improves profit)."""
    return variance if higher_is_better else -variance


@dataclass(frozen=True)
class ProfitAndLoss:
    """Income statement down to operating income for any slice of data."""

    net_revenue: float = 0.0
    direct_costs: float = 0.0
    operating_expenses: float = 0.0

    @property
    def gross_profit(self) -> float:
        return self.net_revenue - self.direct_costs

    @property
    def operating_income(self) -> float:
        return self.gross_profit - self.operating_expenses

    @property
    def gross_margin(self) -> float | None:
        return safe_ratio(self.gross_profit, self.net_revenue)

    @property
    def operating_margin(self) -> float | None:
        return safe_ratio(self.operating_income, self.net_revenue)

    @property
    def opex_ratio(self) -> float | None:
        return safe_ratio(self.operating_expenses, self.net_revenue)


def profit_and_loss(account_frame: pd.DataFrame, value_column: str = "actual") -> ProfitAndLoss:
    """Aggregate an account-level frame (one amount per account row) into a P&L."""
    by_type = account_frame.groupby("account_type")[value_column].sum()
    return ProfitAndLoss(
        net_revenue=float(by_type.get(REVENUE, 0.0)),
        direct_costs=float(by_type.get(DIRECT_COST, 0.0)),
        operating_expenses=float(by_type.get(OPERATING_EXPENSE, 0.0)),
    )


def statement_by(
    account_frame: pd.DataFrame, group_columns: list[str], value_column: str = "actual"
) -> pd.DataFrame:
    """P&L measures per group, as columns.

    Returns net_revenue, direct_costs, operating_expenses, gross_profit, operating_income,
    gross_margin and operating_margin indexed by ``group_columns``.
    """
    wide = (
        account_frame.pivot_table(
            index=group_columns,
            columns="account_type",
            values=value_column,
            aggfunc="sum",
            fill_value=0.0,
            observed=True,
        )
        .reindex(columns=[REVENUE, DIRECT_COST, OPERATING_EXPENSE], fill_value=0.0)
        .rename(
            columns={
                REVENUE: "net_revenue",
                DIRECT_COST: "direct_costs",
                OPERATING_EXPENSE: "operating_expenses",
            }
        )
    )
    wide.columns.name = None
    wide["gross_profit"] = wide["net_revenue"] - wide["direct_costs"]
    wide["operating_income"] = wide["gross_profit"] - wide["operating_expenses"]
    revenue = wide["net_revenue"].where(wide["net_revenue"] != 0)
    wide["gross_margin"] = wide["gross_profit"] / revenue
    wide["operating_margin"] = wide["operating_income"] / revenue
    return wide
