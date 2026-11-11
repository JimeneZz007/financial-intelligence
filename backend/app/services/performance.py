"""Executive KPIs, time series and the monthly analytical table."""

from __future__ import annotations

import math

import pandas as pd

from backend.app.analytics.metrics import (
    ProfitAndLoss,
    favorability,
    pct_change,
    profit_and_loss,
    statement_by,
)
from backend.app.analytics.periods import month_key
from backend.app.schemas import (
    Kpi,
    KpiSummaryResponse,
    MonthlyRecord,
    MonthlyRecordsResponse,
    Pagination,
    TimeSeriesPoint,
    TimeSeriesResponse,
    UnitSeries,
    UnitSeriesPoint,
    UnitTimeSeriesResponse,
)
from backend.app.services.context import AnalysisContext
from backend.app.services.formatting import money, money_or_none, ratio

# id, label, unit, higher_is_better
KPI_SPECS: list[tuple[str, str, str, bool]] = [
    ("net_revenue", "Net revenue", "currency", True),
    ("direct_costs", "Direct costs", "currency", False),
    ("gross_profit", "Gross profit", "currency", True),
    ("gross_margin", "Gross margin", "percent", True),
    ("operating_expenses", "Operating expenses", "currency", False),
    ("operating_income", "Operating income", "currency", True),
    ("operating_margin", "Operating margin", "percent", True),
]


def _kpi(
    spec: tuple[str, str, str, bool],
    actual: ProfitAndLoss,
    budget: ProfitAndLoss,
    comparison: ProfitAndLoss | None,
    monthly: pd.DataFrame,
) -> Kpi:
    kpi_id, label, unit, higher_is_better = spec
    is_percent = unit == "percent"
    rounder = ratio if is_percent else money_or_none

    value = getattr(actual, kpi_id)
    budget_value = getattr(budget, kpi_id)
    comparison_value = getattr(comparison, kpi_id) if comparison is not None else None

    def versus(reference: float | None) -> tuple[float | None, float | None, str | None]:
        """(difference, relative change, favourability) of the value against a reference."""
        if value is None or reference is None:
            return None, None, None
        difference = value - reference
        if is_percent:
            # Margins are compared in percentage points; a tolerance of 0.05 pp is "on target".
            status = (
                "on_target"
                if abs(difference) < 0.0005
                else ("favorable" if (difference > 0) == higher_is_better else "unfavorable")
            )
            return ratio(difference), None, status
        status = favorability(difference, reference, higher_is_better=higher_is_better)
        return money(difference), ratio(pct_change(value, reference)), status

    change, change_pct, comparison_status = versus(comparison_value)
    budget_variance, budget_variance_pct, budget_status = versus(budget_value)
    return Kpi(
        id=kpi_id,
        label=label,
        unit=unit,
        higher_is_better=higher_is_better,
        value=rounder(value),
        comparison_value=rounder(comparison_value),
        change=change,
        change_pct=change_pct,
        comparison_status=comparison_status,
        budget_value=rounder(budget_value),
        budget_variance=budget_variance,
        budget_variance_pct=budget_variance_pct,
        budget_status=budget_status,
        sparkline=[rounder(v) for v in monthly[kpi_id].tolist()],
    )


def kpi_summary(ctx: AnalysisContext) -> KpiSummaryResponse:
    actual = profit_and_loss(ctx.current, "actual")
    budget = profit_and_loss(ctx.current, "budget")
    comparison = profit_and_loss(ctx.comparison, "actual") if ctx.comparison is not None else None
    monthly = statement_by(ctx.current, ["month"]).reindex(ctx.period.months, fill_value=0.0)
    return KpiSummaryResponse(
        filters=ctx.applied_filters(),
        kpis=[_kpi(spec, actual, budget, comparison, monthly) for spec in KPI_SPECS],
    )


def _growth(series: pd.Series, lag: int) -> pd.Series:
    """Relative change against the value ``lag`` months earlier (NaN when unavailable)."""
    previous = series.shift(lag)
    return (series - previous) / previous.abs().where(previous != 0)


def time_series(ctx: AnalysisContext) -> TimeSeriesResponse:
    """Monthly P&L with budget and growth rates.

    Growth is computed on the whole history first and then cut to the period, so the first
    month shown still has its month-over-month and year-over-year rates when data exists.
    """
    all_months = ctx.available.months
    actual = statement_by(ctx.history, ["month"], "actual").reindex(all_months, fill_value=0.0)
    budget = statement_by(ctx.history, ["month"], "budget").reindex(all_months, fill_value=0.0)

    frame = actual.assign(
        revenue_mom_pct=_growth(actual["net_revenue"], 1),
        revenue_yoy_pct=_growth(actual["net_revenue"], 12),
        operating_income_mom_pct=_growth(actual["operating_income"], 1),
        operating_income_yoy_pct=_growth(actual["operating_income"], 12),
        revenue_rolling_3m=actual["net_revenue"].rolling(3).mean(),
    ).loc[ctx.period.months]

    points = [
        TimeSeriesPoint(
            month=month_key(month),
            net_revenue=money(row.net_revenue),
            direct_costs=money(row.direct_costs),
            gross_profit=money(row.gross_profit),
            operating_expenses=money(row.operating_expenses),
            operating_income=money(row.operating_income),
            gross_margin=ratio(row.gross_margin),
            operating_margin=ratio(row.operating_margin),
            budget_net_revenue=money(budget.at[month, "net_revenue"]),
            budget_direct_costs=money(budget.at[month, "direct_costs"]),
            budget_operating_expenses=money(budget.at[month, "operating_expenses"]),
            budget_operating_income=money(budget.at[month, "operating_income"]),
            revenue_mom_pct=ratio(row.revenue_mom_pct),
            revenue_yoy_pct=ratio(row.revenue_yoy_pct),
            operating_income_mom_pct=ratio(row.operating_income_mom_pct),
            operating_income_yoy_pct=ratio(row.operating_income_yoy_pct),
            revenue_rolling_3m=money_or_none(row.revenue_rolling_3m),
        )
        for month, row in zip(frame.index, frame.itertuples(index=False), strict=True)
    ]
    return TimeSeriesResponse(filters=ctx.applied_filters(), points=points)


def time_series_by_unit(ctx: AnalysisContext) -> UnitTimeSeriesResponse:
    by_unit = statement_by(ctx.current, ["business_unit_code", "month"])
    names = ctx.current.drop_duplicates("business_unit_code").set_index("business_unit_code")[
        "business_unit_name"
    ]
    series = []
    for code in by_unit.index.get_level_values("business_unit_code").unique():
        unit = by_unit.xs(code, level="business_unit_code").reindex(
            ctx.period.months, fill_value=0.0
        )
        series.append(
            UnitSeries(
                key=code,
                label=names[code],
                points=[
                    UnitSeriesPoint(
                        month=month_key(month),
                        net_revenue=money(row.net_revenue),
                        gross_profit=money(row.gross_profit),
                        operating_income=money(row.operating_income),
                        gross_margin=ratio(row.gross_margin),
                        operating_margin=ratio(row.operating_margin),
                    )
                    for month, row in zip(unit.index, unit.itertuples(index=False), strict=True)
                ],
            )
        )
    return UnitTimeSeriesResponse(filters=ctx.applied_filters(), series=series)


# --------------------------------------------------------------------------- #
# Monthly analytical table (month x business unit)
# --------------------------------------------------------------------------- #
RECORD_SORT_COLUMNS = (
    "month",
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
)


def monthly_records_frame(ctx: AnalysisContext) -> pd.DataFrame:
    """One row per month x business unit with actuals, budget and variances."""
    keys = ["month", "business_unit_code", "business_unit_name"]
    actual = statement_by(ctx.current, keys, "actual")
    budget = statement_by(ctx.current, keys, "budget")
    frame = actual.assign(
        budget_net_revenue=budget["net_revenue"],
        budget_operating_income=budget["operating_income"],
    ).reset_index()
    frame["revenue_variance_pct"] = (frame["net_revenue"] - frame["budget_net_revenue"]) / frame[
        "budget_net_revenue"
    ].abs().where(frame["budget_net_revenue"] != 0)
    frame["operating_income_variance"] = (
        frame["operating_income"] - frame["budget_operating_income"]
    )
    return frame


def monthly_records(
    ctx: AnalysisContext, page: int, page_size: int, sort_by: str, sort_dir: str
) -> MonthlyRecordsResponse:
    frame = monthly_records_frame(ctx).sort_values(
        [sort_by, "month", "business_unit_code"],
        ascending=[sort_dir == "asc", True, True],
        kind="stable",
        na_position="last",
    )
    total = len(frame)
    total_pages = max(1, math.ceil(total / page_size))
    window = frame.iloc[(page - 1) * page_size : page * page_size]
    rows = [
        MonthlyRecord(
            month=month_key(row.month),
            business_unit_code=row.business_unit_code,
            business_unit_name=row.business_unit_name,
            net_revenue=money(row.net_revenue),
            direct_costs=money(row.direct_costs),
            gross_profit=money(row.gross_profit),
            gross_margin=ratio(row.gross_margin),
            operating_expenses=money(row.operating_expenses),
            operating_income=money(row.operating_income),
            operating_margin=ratio(row.operating_margin),
            budget_net_revenue=money(row.budget_net_revenue),
            revenue_variance_pct=ratio(row.revenue_variance_pct),
            budget_operating_income=money(row.budget_operating_income),
            operating_income_variance=money(row.operating_income_variance),
        )
        for row in window.itertuples(index=False)
    ]
    return MonthlyRecordsResponse(
        filters=ctx.applied_filters(),
        pagination=Pagination(
            page=page, page_size=page_size, total_items=total, total_pages=total_pages
        ),
        sort_by=sort_by,
        sort_dir=sort_dir,
        rows=rows,
    )
