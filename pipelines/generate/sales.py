"""Demand model and daily sales generation.

The model has two layers:

* a deterministic *plan* (expected units, prices and costs before any scenario), which is
  also what the budget is built from, and
* the *actual* realisation: plan x scenario effects x random noise.

Array axes are (D days, B business units, P products) unless stated otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from pipelines.generate import config as cfg
from pipelines.generate.scenarios import effects_by_lever
from pipelines.generate.timeline import Timeline

SALES_COLUMNS = [
    "transaction_date",
    "business_unit_code",
    "product_code",
    "units_sold",
    "gross_sales_amount",
    "discount_amount",
    "net_sales_amount",
    "cogs_amount",
]


@dataclass(frozen=True)
class DemandModel:
    expected_units: np.ndarray  # (D, B, P) plan, before scenarios and noise
    plan_price_cents: np.ndarray  # (D, B, P) realised unit price assumed by the plan
    actual_price_cents: np.ndarray  # (D, B, P) includes list-price scenarios
    plan_cost_cents: np.ndarray  # (D, P)
    actual_cost_cents: np.ndarray  # (D, P) includes supplier-cost scenarios
    expected_discount_rate: np.ndarray  # (D, B)
    demand_multiplier: np.ndarray  # (D, B) scenario effect on units

    @property
    def plan_net_revenue(self) -> np.ndarray:
        """Expected net revenue (D, B, P) in USD under the plan."""
        net_price = self.plan_price_cents * (1.0 - self.expected_discount_rate[:, :, None])
        return self.expected_units * net_price / 100.0

    @property
    def plan_cogs(self) -> np.ndarray:
        """Expected cost of goods sold (D, B, P) in USD under the plan."""
        return self.expected_units * self.plan_cost_cents[:, None, :] / 100.0


def _normalised(values: tuple[float, ...]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return array / array.mean()


def _annual_index(timeline: Timeline, rates: dict[int, float]) -> np.ndarray:
    """Cumulative index per day from year-on-year rates applied each January 1st."""
    index_by_year: dict[int, float] = {}
    level = 1.0
    for year in sorted(rates):
        level *= 1.0 + rates[year]
        index_by_year[year] = level
    return np.array([index_by_year[int(y)] for y in timeline.year])


def _category_month_multiplier(timeline: Timeline, lever: str) -> np.ndarray:
    """(D, P) multiplier from category-level price or cost scenarios."""
    product_categories = np.array([p.category_code for p in cfg.PRODUCTS])
    multiplier = np.ones((timeline.n_days, len(cfg.PRODUCTS)))
    month_keys = np.array(timeline.month_keys)[timeline.month_index]
    for effect in effects_by_lever(lever):
        product_mask = product_categories == effect.category_code
        for month_key, value in effect.months.items():
            day_mask = month_keys == month_key
            multiplier[np.ix_(day_mask, product_mask)] *= value
    return multiplier


def _demand_multiplier(timeline: Timeline) -> np.ndarray:
    multiplier = np.ones((timeline.n_days, len(cfg.BUSINESS_UNITS)))
    month_keys = np.array(timeline.month_keys)[timeline.month_index]
    for effect in effects_by_lever("DEMAND"):
        unit_idx = [cfg.BU_CODES.index(code) for code in effect.business_units]
        for month_key, value in effect.months.items():
            multiplier[np.ix_(month_keys == month_key, unit_idx)] *= value
    return multiplier


def product_unit_costs(rng: np.random.Generator) -> np.ndarray:
    """Base-year unit cost per product: category standard margin +/- a product spread."""
    margins = np.array(
        [cfg.CATEGORY_BY_CODE[p.category_code].standard_margin for p in cfg.PRODUCTS]
    )
    spread = rng.uniform(-cfg.PRODUCT_MARGIN_SPREAD, cfg.PRODUCT_MARGIN_SPREAD, len(cfg.PRODUCTS))
    list_prices = np.array([p.list_price for p in cfg.PRODUCTS])
    return np.round(list_prices * (1.0 - (margins + spread)), 2)


def build_demand_model(timeline: Timeline, unit_costs: np.ndarray) -> DemandModel:
    units_b = cfg.BUSINESS_UNITS
    products = cfg.PRODUCTS
    n_days = timeline.n_days

    # --- expected net revenue per day, unit and product ------------------------------
    day_number = np.arange(n_days)
    mid_base_year = 182  # growth is centred so the base year totals the base revenue
    growth = np.stack(
        [(1.0 + bu.annual_growth) ** ((day_number - mid_base_year) / 365.0) for bu in units_b],
        axis=1,
    )  # (D, B)
    weekday = np.stack(
        [_normalised(bu.weekday_profile)[timeline.weekday] for bu in units_b], axis=1
    )
    season = np.stack(
        [
            _normalised(cfg.CATEGORY_BY_CODE[p.category_code].seasonality)[timeline.month - 1]
            for p in products
        ],
        axis=1,
    )  # (D, P)
    share = np.array(
        [[bu.category_mix[p.category_code] * p.category_weight for p in products] for bu in units_b]
    )  # (B, P)
    base_daily = np.array([bu.base_annual_revenue / 365.0 for bu in units_b])
    expected_revenue = (
        base_daily[None, :, None]
        * growth[:, :, None]
        * weekday[:, :, None]
        * season[:, None, :]
        * share[None, :, :]
    )

    # --- prices, costs and discounts --------------------------------------------------
    list_price = np.array([p.list_price for p in products])
    price_factor = np.array([bu.price_factor for bu in units_b])
    price_index = _annual_index(timeline, cfg.PRICE_INCREASE_BY_YEAR)
    cost_index = _annual_index(timeline, cfg.COST_INFLATION_BY_YEAR)

    plan_price = (
        price_index[:, None, None] * price_factor[None, :, None] * list_price[None, None, :]
    )
    actual_price = plan_price * _category_month_multiplier(timeline, "LIST_PRICE")[:, None, :]
    plan_cost = cost_index[:, None] * unit_costs[None, :]
    actual_cost = plan_cost * _category_month_multiplier(timeline, "UNIT_COST")

    discount = np.stack(
        [
            np.array(
                [
                    bu.base_discount_rate + cfg.PROMO_DISCOUNT.get(int(m), {}).get(bu.code, 0.0)
                    for m in timeline.month
                ]
            )
            for bu in units_b
        ],
        axis=1,
    )  # (D, B)

    plan_price_cents = np.rint(plan_price * 100.0)
    expected_units = expected_revenue / (plan_price_cents / 100.0 * (1.0 - discount[:, :, None]))

    return DemandModel(
        expected_units=expected_units,
        plan_price_cents=plan_price_cents,
        actual_price_cents=np.rint(actual_price * 100.0),
        plan_cost_cents=np.rint(plan_cost * 100.0),
        actual_cost_cents=np.rint(actual_cost * 100.0),
        expected_discount_rate=discount,
        demand_multiplier=_demand_multiplier(timeline),
    )


def _lognormal(rng: np.random.Generator, sigma: float, size: tuple[int, ...]) -> np.ndarray:
    """Log-normal multiplier with mean exactly 1."""
    return np.exp(rng.normal(-0.5 * sigma**2, sigma, size))


def generate_sales(
    timeline: Timeline, model: DemandModel, rng: np.random.Generator
) -> pd.DataFrame:
    """Daily sales lines at the grain date x business unit x product (only if units > 0)."""
    n_days, n_units, n_products = model.expected_units.shape
    category_codes = [c.code for c in cfg.CATEGORIES]
    product_category_idx = np.array([category_codes.index(p.category_code) for p in cfg.PRODUCTS])

    noise_row = _lognormal(rng, cfg.NOISE_ROW, (n_days, n_units, n_products))
    noise_day = _lognormal(rng, cfg.NOISE_DAY_UNIT, (n_days, n_units, 1))
    noise_month_cat = _lognormal(
        rng, cfg.NOISE_MONTH_UNIT_CATEGORY, (timeline.n_months, n_units, len(category_codes))
    )[timeline.month_index][:, :, product_category_idx]

    rate = model.expected_units * model.demand_multiplier[:, :, None]
    units = rng.poisson(rate * noise_row * noise_day * noise_month_cat)

    discount_rate = np.clip(
        model.expected_discount_rate[:, :, None]
        + rng.normal(0.0, cfg.NOISE_DISCOUNT_RATE, units.shape),
        0.0,
        0.5,
    )
    gross_cents = units * model.actual_price_cents
    discount_cents = np.rint(gross_cents * discount_rate)
    net_cents = gross_cents - discount_cents
    cogs_cents = units * model.actual_cost_cents[:, None, :]

    day_idx, unit_idx, product_idx = np.nonzero(units)
    selector = (day_idx, unit_idx, product_idx)
    frame = pd.DataFrame(
        {
            "transaction_date": timeline.dates[day_idx].strftime("%Y-%m-%d"),
            "business_unit_code": np.array(cfg.BU_CODES)[unit_idx],
            "product_code": np.array([p.code for p in cfg.PRODUCTS])[product_idx],
            "units_sold": units[selector].astype(np.int64),
            "gross_sales_amount": gross_cents[selector] / 100.0,
            "discount_amount": discount_cents[selector] / 100.0,
            "net_sales_amount": net_cents[selector] / 100.0,
            "cogs_amount": cogs_cents[selector] / 100.0,
        }
    )
    return frame[SALES_COLUMNS]


def monthly_by_unit(timeline: Timeline, daily: np.ndarray) -> np.ndarray:
    """Aggregate a (D, B, P) array to (M, B)."""
    per_day_unit = daily.sum(axis=2)
    out = np.zeros((timeline.n_months, per_day_unit.shape[1]))
    np.add.at(out, timeline.month_index, per_day_unit)
    return out


def actual_monthly_revenue(timeline: Timeline, sales: pd.DataFrame) -> np.ndarray:
    """Net revenue actually generated, as an (M, B) array."""
    month_key = sales["transaction_date"].str.slice(0, 7)
    pivot = (
        sales.groupby([month_key, "business_unit_code"])["net_sales_amount"]
        .sum()
        .unstack("business_unit_code")
        .reindex(index=list(timeline.month_keys), columns=list(cfg.BU_CODES))
        .fillna(0.0)
    )
    return pivot.to_numpy()
