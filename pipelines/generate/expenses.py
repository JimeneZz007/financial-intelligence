"""Operating expenses: monthly amounts per account and their ledger postings.

Monthly amounts are (M months, B business units) arrays keyed by account code.
The same deterministic formulas feed the actuals (plus scenarios and noise) and the
budget (plus planning bias), so budget variance comes only from documented sources.
"""

from __future__ import annotations

import calendar as stdlib_calendar

import numpy as np
import pandas as pd

from pipelines.generate import config as cfg
from pipelines.generate.scenarios import effects_by_lever
from pipelines.generate.timeline import Timeline

LEDGER_COLUMNS = [
    "entry_id",
    "posting_date",
    "business_unit_code",
    "cost_center_code",
    "account_code",
    "amount",
]

MonthlyOpex = dict[str, np.ndarray]

# Accounts whose driver is the revenue actually achieved (the rest follow the plan).
_ACTUAL_REVENUE_DRIVEN = ("6400", "6800")


def _calendar_index(values: tuple[float, ...], timeline: Timeline) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return (array / array.mean())[timeline.month_number - 1][:, None]


def _base_monthly(account_code: str) -> np.ndarray:
    return np.array([cfg.OPEX_BASE_ANNUAL[account_code][code] / 12.0 for code in cfg.BU_CODES])


def _revenue_rate(account_code: str) -> np.ndarray:
    return np.array([cfg.OPEX_REVENUE_RATE[account_code][code] for code in cfg.BU_CODES])


def deterministic_opex(timeline: Timeline, account_code: str, revenue: np.ndarray) -> np.ndarray:
    """Expected monthly amount (M, B) of an account before scenarios, noise or bias."""
    year_offset = (timeline.month_year - timeline.first_year)[:, None]
    month_offset = np.arange(timeline.n_months)[:, None]

    if account_code == "6100":
        raise_level, raise_index = 1.0, {}
        for year in sorted(cfg.SALARY_RAISE_BY_YEAR):
            raise_level *= 1.0 + cfg.SALARY_RAISE_BY_YEAR[year]
            raise_index[year] = raise_level
        raises = np.array([raise_index[int(y)] for y in timeline.month_year])[:, None]
        headcount = np.array([1.0 + bu.headcount_growth for bu in cfg.BUSINESS_UNITS])[None, :]
        return _base_monthly("6100")[None, :] * raises * headcount ** (month_offset / 12.0)
    if account_code == "6150":
        return cfg.BENEFITS_RATE * deterministic_opex(timeline, "6100", revenue)
    if account_code == "6200":
        return (
            _revenue_rate("6200")[None, :]
            * revenue
            * _calendar_index(cfg.ADVERTISING_CALENDAR, timeline)
        )
    if account_code in ("6400", "6800"):
        return _revenue_rate(account_code)[None, :] * revenue
    if account_code == "6300":
        return _base_monthly("6300")[None, :] * (1.0 + cfg.RENT_ESCALATION) ** year_offset
    if account_code == "6350":
        return (
            _base_monthly("6350")[None, :]
            * _calendar_index(cfg.UTILITIES_CALENDAR, timeline)
            * (1.0 + cfg.UTILITIES_INFLATION) ** year_offset
        )
    if account_code == "6500":
        return _base_monthly("6500")[None, :] * (1.0 + cfg.SOFTWARE_ESCALATION) ** year_offset
    if account_code == "6600":
        return np.repeat(_base_monthly("6600")[None, :], timeline.n_months, axis=0)
    if account_code == "6700":
        return _base_monthly("6700")[None, :] * _calendar_index(cfg.TRAVEL_CALENDAR, timeline)
    if account_code == "6900":
        return _base_monthly("6900")[None, :] * (1.0 + cfg.DEPRECIATION_STEP) ** year_offset
    raise ValueError(f"Unknown operating-expense account: {account_code}")


def _scenario_array(
    timeline: Timeline, lever: str, account_code: str, *, budget_view: bool
) -> np.ndarray:
    """(M, B) multiplier or addition for an account.

    With ``budget_view`` only effects already known when each year's budget was approved
    are included.
    """
    neutral = 1.0 if lever == "OPEX_MULTIPLIER" else 0.0
    out = np.full((timeline.n_months, len(cfg.BU_CODES)), neutral)
    for effect in effects_by_lever(lever):
        if effect.account_code != account_code:
            continue
        for month_key, value in effect.months.items():
            if month_key not in timeline.month_keys:
                continue
            if budget_view and (
                effect.budgeted_from_year is None or int(month_key[:4]) < effect.budgeted_from_year
            ):
                continue
            m = timeline.month_keys.index(month_key)
            for code in effect.business_units:
                b = cfg.BU_CODES.index(code)
                if lever == "OPEX_MULTIPLIER":
                    out[m, b] *= value
                else:
                    out[m, b] += value
    return out


def actual_monthly_opex(
    timeline: Timeline,
    plan_revenue: np.ndarray,
    actual_revenue: np.ndarray,
    rng: np.random.Generator,
) -> MonthlyOpex:
    monthly: MonthlyOpex = {}
    for account_code in cfg.OPEX_ACCOUNT_CODES:
        if account_code == "6150":
            base = cfg.BENEFITS_RATE * monthly["6100"]  # benefits follow actual salaries
        else:
            driver = actual_revenue if account_code in _ACTUAL_REVENUE_DRIVEN else plan_revenue
            base = deterministic_opex(timeline, account_code, driver)
        sigma = cfg.OPEX_NOISE[account_code]
        noise = np.exp(rng.normal(-0.5 * sigma**2, sigma, base.shape)) if sigma > 0 else 1.0
        monthly[account_code] = base * noise * _scenario_array(
            timeline, "OPEX_MULTIPLIER", account_code, budget_view=False
        ) + _scenario_array(timeline, "OPEX_ADDITION", account_code, budget_view=False)
    return monthly


def budget_monthly_opex(timeline: Timeline, budget_revenue: np.ndarray) -> MonthlyOpex:
    """Budgeted operating expenses: deterministic plan x planning bias, known effects only."""
    return {
        account_code: deterministic_opex(timeline, account_code, budget_revenue)
        * cfg.OPEX_BUDGET_BIAS
        * _scenario_array(timeline, "OPEX_MULTIPLIER", account_code, budget_view=True)
        + _scenario_array(timeline, "OPEX_ADDITION", account_code, budget_view=True)
        for account_code in cfg.OPEX_ACCOUNT_CODES
    }


# --------------------------------------------------------------------------- #
# Ledger postings
# --------------------------------------------------------------------------- #
def allocate_cents(total_cents: int, weights: np.ndarray) -> np.ndarray:
    """Split an integer amount proportionally; the parts always sum to the total."""
    weights = np.asarray(weights, dtype=float)
    raw = total_cents * weights / weights.sum()
    parts = np.floor(raw).astype(np.int64)
    remainder = int(total_cents - parts.sum())
    if remainder > 0:
        order = np.argsort(-(raw - parts), kind="stable")
        parts[order[:remainder]] += 1
    return parts


def _posting_days(account_code: str, days_in_month: int, rng: np.random.Generator) -> list[int]:
    if account_code in ("6100", "6150"):
        return [15, days_in_month]  # two payroll runs
    if account_code == "6300":
        return [1]
    if account_code == "6500":
        return [5]
    if account_code == "6900":
        return [days_in_month]
    count = int(rng.integers(2, 7))
    return sorted(int(d) for d in rng.choice(np.arange(1, days_in_month + 1), count, replace=False))


def generate_expense_ledger(
    timeline: Timeline, monthly: MonthlyOpex, rng: np.random.Generator
) -> pd.DataFrame:
    """Expense postings at the grain of one ledger entry."""
    rows: list[tuple[str, str, str, str, int]] = []
    for m, month_key in enumerate(timeline.month_keys):
        year, month = int(month_key[:4]), int(month_key[5:])
        days_in_month = stdlib_calendar.monthrange(year, month)[1]
        for b, bu_code in enumerate(cfg.BU_CODES):
            for account_code in cfg.OPEX_ACCOUNT_CODES:
                total_cents = round(float(monthly[account_code][m, b]) * 100)
                split = cfg.cost_center_split(account_code, bu_code)
                by_center = allocate_cents(total_cents, np.array(list(split.values())))
                for cost_center_code, center_cents in zip(split, by_center, strict=True):
                    days = _posting_days(account_code, days_in_month, rng)
                    if len(days) > 2:
                        weights = rng.dirichlet(np.full(len(days), 2.0))
                    else:
                        weights = np.full(len(days), 1.0)
                    for day, cents in zip(
                        days, allocate_cents(int(center_cents), weights), strict=True
                    ):
                        if cents > 0:
                            rows.append(
                                (
                                    f"{month_key}-{day:02d}",
                                    bu_code,
                                    cost_center_code,
                                    account_code,
                                    int(cents),
                                )
                            )
    frame = pd.DataFrame(
        rows,
        columns=[
            "posting_date",
            "business_unit_code",
            "cost_center_code",
            "account_code",
            "cents",
        ],
    ).sort_values(
        ["posting_date", "business_unit_code", "account_code", "cost_center_code"],
        kind="stable",
        ignore_index=True,
    )
    frame["entry_id"] = [f"EXP-{i:07d}" for i in range(1, len(frame) + 1)]
    frame["amount"] = frame["cents"] / 100.0
    return frame[LEDGER_COLUMNS]
