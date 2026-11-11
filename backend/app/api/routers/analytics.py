"""Analytic endpoints. All of them share the global filters (see api/deps.py)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from backend.app.api.deps import ContextDep
from backend.app.schemas import (
    AnomaliesResponse,
    BridgeResponse,
    BudgetMatrixResponse,
    BudgetStatementResponse,
    BudgetVarianceResponse,
    ExpenseBreakdownResponse,
    ExpenseMatrixResponse,
    InsightsResponse,
    KpiSummaryResponse,
    MarginDriversResponse,
    MonthlyRecordsResponse,
    ProfitabilityResponse,
    PvmResponse,
    TimeSeriesResponse,
    UnitTimeSeriesResponse,
)
from backend.app.services import analysis, budget, expenses, exports, insights, performance
from backend.app.services import profitability as profitability_service

router = APIRouter()

RecordSortColumn = Literal[
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
]
ExportDataset = Literal[
    "monthly-pnl", "budget-by-account", "sales-by-product", "expenses-by-cost-center", "anomalies"
]


# --------------------------------------------------------------------------- #
# Executive indicators and time series
# --------------------------------------------------------------------------- #
@router.get(
    "/kpis/summary",
    response_model=KpiSummaryResponse,
    tags=["Executive KPIs"],
    summary="Executive KPIs with comparison and budget",
)
def kpi_summary(ctx: ContextDep) -> KpiSummaryResponse:
    """Revenue, costs, profit and margins for the period, each compared with the
    comparison period and with the budget, plus a monthly sparkline."""
    return performance.kpi_summary(ctx)


@router.get(
    "/timeseries",
    response_model=TimeSeriesResponse,
    tags=["Time series"],
    summary="Monthly P&L with budget and growth rates",
)
def time_series(ctx: ContextDep) -> TimeSeriesResponse:
    return performance.time_series(ctx)


@router.get(
    "/timeseries/business-units",
    response_model=UnitTimeSeriesResponse,
    tags=["Time series"],
    summary="Monthly revenue, profit and margins per business unit",
)
def time_series_by_unit(ctx: ContextDep) -> UnitTimeSeriesResponse:
    return performance.time_series_by_unit(ctx)


# --------------------------------------------------------------------------- #
# Budget versus actual
# --------------------------------------------------------------------------- #
@router.get(
    "/budget/statement",
    response_model=BudgetStatementResponse,
    tags=["Budget vs actual"],
    summary="Income statement: actual vs budget by account",
)
def budget_statement(ctx: ContextDep) -> BudgetStatementResponse:
    """One line per account plus gross profit, total operating expenses and operating
    income. `profit_impact` expresses each variance as its effect on operating income."""
    return budget.budget_statement(ctx)


@router.get(
    "/budget/variance",
    response_model=BudgetVarianceResponse,
    tags=["Budget vs actual"],
    summary="Budget variance by month or business unit",
)
def budget_variance(
    ctx: ContextDep,
    group_by: Annotated[Literal["month", "business_unit"], Query()] = "month",
) -> BudgetVarianceResponse:
    return budget.budget_variance(ctx, group_by)


@router.get(
    "/budget/matrix",
    response_model=BudgetMatrixResponse,
    tags=["Budget vs actual"],
    summary="Budget variance for every business unit x account cell",
)
def budget_matrix(ctx: ContextDep) -> BudgetMatrixResponse:
    return budget.budget_matrix(ctx)


# --------------------------------------------------------------------------- #
# Profitability and expenses
# --------------------------------------------------------------------------- #
@router.get(
    "/profitability",
    response_model=ProfitabilityResponse,
    tags=["Profitability"],
    summary="Revenue and margins by business unit, category or product",
)
def profitability(
    ctx: ContextDep,
    group_by: Annotated[Literal["business_unit", "category", "product"], Query()] = "category",
    category: Annotated[
        str | None,
        Query(min_length=3, max_length=3, description="Restrict to one category code"),
    ] = None,
) -> ProfitabilityResponse:
    """Sales measures and gross margin per segment. Operating income is included only when
    grouping by business unit without a category filter: operating expenses are not
    recorded by product."""
    return profitability_service.profitability(ctx, group_by, category)


@router.get(
    "/expenses/breakdown",
    response_model=ExpenseBreakdownResponse,
    tags=["Expenses"],
    summary="Operating expenses by account, group, cost centre or cost behaviour",
)
def expense_breakdown(
    ctx: ContextDep,
    group_by: Annotated[
        Literal["account", "account_group", "cost_center", "cost_behavior"], Query()
    ] = "account_group",
) -> ExpenseBreakdownResponse:
    """Budget columns are null when grouping by cost centre: the budget has no such
    dimension."""
    return expenses.expense_breakdown(ctx, group_by)


@router.get(
    "/expenses/matrix",
    response_model=ExpenseMatrixResponse,
    tags=["Expenses"],
    summary="Operating expenses by cost centre x account group",
)
def expense_matrix(ctx: ContextDep) -> ExpenseMatrixResponse:
    return expenses.expense_matrix(ctx)


# --------------------------------------------------------------------------- #
# Contribution analysis, anomalies and insights
# --------------------------------------------------------------------------- #
@router.get(
    "/analysis/operating-income-bridge",
    response_model=BridgeResponse,
    tags=["Analysis"],
    summary="Operating income bridge versus the comparison period or the budget",
)
def operating_income_bridge(
    ctx: ContextDep,
    basis: Annotated[Literal["comparison", "budget"], Query()] = "comparison",
) -> BridgeResponse:
    """Steps that add up exactly from the base operating income to the current one."""
    return analysis.income_bridge(ctx, basis)


@router.get(
    "/analysis/price-volume-mix",
    response_model=PvmResponse,
    tags=["Analysis"],
    summary="Price, volume and mix effects on the change in net revenue",
)
def price_volume_mix(
    ctx: ContextDep,
    group_by: Annotated[Literal["category", "business_unit"], Query()] = "category",
) -> PvmResponse:
    return analysis.price_volume_mix_analysis(ctx, group_by)


@router.get(
    "/analysis/margin-drivers",
    response_model=MarginDriversResponse,
    tags=["Analysis"],
    summary="Mix and rate effects on the change in gross margin",
)
def margin_drivers(
    ctx: ContextDep,
    group_by: Annotated[Literal["category", "business_unit"], Query()] = "category",
) -> MarginDriversResponse:
    return analysis.margin_drivers(ctx, group_by)


@router.get(
    "/analysis/anomalies",
    response_model=AnomaliesResponse,
    tags=["Analysis"],
    summary="Months with a statistically unusual budget variance",
)
def anomalies(
    ctx: ContextDep,
    include_immaterial: Annotated[
        bool, Query(description="Also return anomalies below the materiality threshold")
    ] = False,
) -> AnomaliesResponse:
    """Robust z-score (median / MAD) on budget variance per business unit x account,
    scored over the whole history and reported for the selected period."""
    return analysis.anomalies(ctx, include_immaterial)


@router.get(
    "/insights",
    response_model=InsightsResponse,
    tags=["Analysis"],
    summary="Findings computed for the current filters",
)
def insight_list(ctx: ContextDep) -> InsightsResponse:
    return insights.build_insights(ctx)


# --------------------------------------------------------------------------- #
# Analytical table and exports
# --------------------------------------------------------------------------- #
@router.get(
    "/records/monthly",
    response_model=MonthlyRecordsResponse,
    tags=["Records"],
    summary="Paginated monthly P&L by business unit",
)
def monthly_records(
    ctx: ContextDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 12,
    sort_by: Annotated[RecordSortColumn, Query()] = "month",
    sort_dir: Annotated[Literal["asc", "desc"], Query()] = "desc",
    revenue_vs_budget: Annotated[
        Literal["all", "above", "below"],
        Query(description="Keep only rows whose net revenue is above or below its budget"),
    ] = "all",
) -> MonthlyRecordsResponse:
    return performance.monthly_records(ctx, page, page_size, sort_by, sort_dir, revenue_vs_budget)


@router.get(
    "/exports/{dataset}",
    tags=["Exports"],
    summary="Download a filtered dataset as CSV",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV file"}},
)
def export_dataset(dataset: ExportDataset, ctx: ContextDep) -> Response:
    return Response(
        content=exports.export_csv(ctx, dataset),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{exports.export_filename(ctx, dataset)}"'
        },
    )
