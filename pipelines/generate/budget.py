"""Annual budget at the grain month x business unit x account.

The budget is the deterministic plan seen through the planners' eyes: revenue targets
carry a stretch factor, expenses assume small savings, and only effects known when each
year's budget was approved are included. Amounts are rounded to round figures.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipelines.generate import config as cfg
from pipelines.generate.expenses import MonthlyOpex, budget_monthly_opex
from pipelines.generate.sales import DemandModel, monthly_by_unit
from pipelines.generate.timeline import Timeline

BUDGET_COLUMNS = [
    "fiscal_year",
    "fiscal_month",
    "business_unit_code",
    "account_code",
    "budget_amount",
]


def budget_by_account(timeline: Timeline, model: DemandModel) -> MonthlyOpex:
    """Budget amounts (M, B) keyed by account code, before rounding."""
    stretch = np.array([bu.budget_stretch for bu in cfg.BUSINESS_UNITS])[None, :]
    revenue = monthly_by_unit(timeline, model.plan_net_revenue) * stretch
    cogs = monthly_by_unit(timeline, model.plan_cogs) * stretch
    return {
        cfg.REVENUE_ACCOUNT: revenue,
        cfg.COGS_ACCOUNT: cogs,
        **budget_monthly_opex(timeline, revenue),
    }


def generate_budget(timeline: Timeline, model: DemandModel) -> pd.DataFrame:
    amounts = budget_by_account(timeline, model)
    rows = [
        (
            int(timeline.month_year[m]),
            int(timeline.month_number[m]),
            bu_code,
            account.code,
            float(
                np.round(amounts[account.code][m, b] / cfg.BUDGET_ROUNDING) * cfg.BUDGET_ROUNDING
            ),
        )
        for m in range(timeline.n_months)
        for b, bu_code in enumerate(cfg.BU_CODES)
        for account in cfg.ACCOUNTS
    ]
    return pd.DataFrame(rows, columns=BUDGET_COLUMNS)
