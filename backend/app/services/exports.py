"""CSV exports of the filtered data.

Each dataset is the detail behind a view of the application, computed with the same
functions as the API responses so exported figures always match what is on screen.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from backend.app.analytics.metrics import REVENUE
from backend.app.services import analysis
from backend.app.services.context import AnalysisContext
from backend.app.services.performance import monthly_records_frame

MONEY_DECIMALS, RATIO_DECIMALS = 2, 6


def _monthly_pnl(ctx: AnalysisContext) -> pd.DataFrame:
    return monthly_records_frame(ctx)[
        [
            "month",
            "business_unit_code",
            "business_unit_name",
            "net_revenue",
            "direct_costs",
            "gross_profit",
            "gross_margin",
            "operating_expenses",
            "operating_income",
            "operating_margin",
            "budget_net_revenue",
            "revenue_variance_pct",
            "budget_operating_income",
            "operating_income_variance",
        ]
    ]


def _budget_by_account(ctx: AnalysisContext) -> pd.DataFrame:
    frame = ctx.current[
        [
            "month",
            "business_unit_code",
            "business_unit_name",
            "account_code",
            "account_name",
            "account_type",
            "account_group",
            "actual",
            "budget",
        ]
    ].copy()
    frame["variance"] = frame["actual"] - frame["budget"]
    frame["variance_pct"] = frame["variance"] / frame["budget"].abs().where(frame["budget"] != 0)
    # Positive = the variance improves operating income.
    frame["profit_impact"] = frame["variance"].where(
        frame["account_type"] == REVENUE, -frame["variance"]
    )
    return frame


def _sales_by_product(ctx: AnalysisContext) -> pd.DataFrame:
    keys = [
        "business_unit_code",
        "business_unit_name",
        "category_code",
        "category_name",
        "product_code",
        "product_name",
    ]
    measures = ["units", "gross_sales", "discounts", "net_revenue", "direct_costs"]
    frame = ctx.sales_current.groupby(keys, observed=True)[measures].sum().reset_index()
    frame["gross_profit"] = frame["net_revenue"] - frame["direct_costs"]
    frame["gross_margin"] = frame["gross_profit"] / frame["net_revenue"].where(
        frame["net_revenue"] != 0
    )
    return frame


def _expenses_by_cost_center(ctx: AnalysisContext) -> pd.DataFrame:
    return ctx.expenses_current[
        [
            "month",
            "business_unit_code",
            "business_unit_name",
            "cost_center_code",
            "cost_center_name",
            "account_code",
            "account_name",
            "account_group",
            "cost_behavior",
            "amount",
        ]
    ]


def _anomalies(ctx: AnalysisContext) -> pd.DataFrame:
    return analysis.anomalies_in_period(ctx)


DATASETS: dict[str, Callable[[AnalysisContext], pd.DataFrame]] = {
    "monthly-pnl": _monthly_pnl,
    "budget-by-account": _budget_by_account,
    "sales-by-product": _sales_by_product,
    "expenses-by-cost-center": _expenses_by_cost_center,
    "anomalies": _anomalies,
}

_RATIO_COLUMNS = {
    "gross_margin",
    "operating_margin",
    "revenue_variance_pct",
    "variance_pct",
    "typical_variance_pct",
    "robust_z",
}


def export_csv(ctx: AnalysisContext, dataset: str) -> str:
    """Render a dataset as CSV text with stable number formatting."""
    frame = DATASETS[dataset](ctx).copy()
    if "month" in frame.columns:
        frame["month"] = pd.to_datetime(frame["month"]).dt.strftime("%Y-%m")
    for column in frame.select_dtypes("float").columns:
        decimals = RATIO_DECIMALS if column in _RATIO_COLUMNS else MONEY_DECIMALS
        frame[column] = frame[column].round(decimals)
    return frame.to_csv(index=False, lineterminator="\n")


def export_filename(ctx: AnalysisContext, dataset: str) -> str:
    filters = ctx.applied_filters()
    units = "-".join(filters.business_units) if filters.business_units else "all-units"
    return f"{dataset}_{filters.start}_{filters.end}_{units}.csv"
