"""Budget versus actual: statement, variance by month / unit, and unit x account matrix."""

from __future__ import annotations

import pandas as pd

from backend.app.analytics.metrics import (
    OPERATING_EXPENSE,
    REVENUE,
    ProfitAndLoss,
    favorability,
    pct_change,
    profit_and_loss,
    safe_ratio,
    statement_by,
)
from backend.app.analytics.periods import month_key
from backend.app.schemas import (
    BudgetMatrixCell,
    BudgetMatrixResponse,
    BudgetStatementResponse,
    BudgetVarianceResponse,
    BudgetVarianceRow,
    StatementLine,
)
from backend.app.services.context import AnalysisContext
from backend.app.services.formatting import impact, measure, money, ratio


def _line(
    *,
    key: str,
    label: str,
    level: str,
    actual: float,
    budget: float,
    revenue: float,
    higher_is_better: bool,
    account_type: str | None = None,
    account_group: str | None = None,
) -> StatementLine:
    variance = actual - budget
    return StatementLine(
        key=key,
        label=label,
        level=level,
        account_type=account_type,
        account_group=account_group,
        higher_is_better=higher_is_better,
        actual=money(actual),
        budget=money(budget),
        variance=money(variance),
        variance_pct=ratio(pct_change(actual, budget)),
        status=favorability(variance, budget, higher_is_better=higher_is_better),
        profit_impact=impact(variance, higher_is_better=higher_is_better),
        pct_of_revenue=ratio(safe_ratio(actual, revenue)),
    )


def account_variances(frame: pd.DataFrame) -> pd.DataFrame:
    """Actual and budget summed per account, in statement order."""
    return (
        frame.groupby(
            ["statement_order", "account_code", "account_name", "account_type", "account_group"],
            observed=True,
        )[["actual", "budget"]]
        .sum()
        .reset_index()
        .sort_values("statement_order")
    )


def budget_statement(ctx: AnalysisContext) -> BudgetStatementResponse:
    """Income statement with one line per account and the three subtotals."""
    actual = profit_and_loss(ctx.current, "actual")
    budget = profit_and_loss(ctx.current, "budget")
    revenue = actual.net_revenue

    def subtotal(key: str, label: str, attribute: str, higher_is_better: bool) -> StatementLine:
        return _line(
            key=key,
            label=label,
            level="subtotal",
            actual=getattr(actual, attribute),
            budget=getattr(budget, attribute),
            revenue=revenue,
            higher_is_better=higher_is_better,
        )

    accounts = account_variances(ctx.current)
    is_opex = accounts["account_type"] == OPERATING_EXPENSE

    def account_lines(rows: pd.DataFrame) -> list[StatementLine]:
        return [
            _line(
                key=row.account_code,
                label=row.account_name,
                level="account",
                actual=row.actual,
                budget=row.budget,
                revenue=revenue,
                higher_is_better=row.account_type == REVENUE,
                account_type=row.account_type,
                account_group=row.account_group,
            )
            for row in rows.itertuples(index=False)
        ]

    lines = [
        *account_lines(accounts[~is_opex]),
        subtotal("gross_profit", "Gross profit", "gross_profit", True),
        *account_lines(accounts[is_opex]),
        subtotal("operating_expenses", "Total operating expenses", "operating_expenses", False),
        subtotal("operating_income", "Operating income", "operating_income", True),
    ]
    return BudgetStatementResponse(filters=ctx.applied_filters(), lines=lines)


def _variance_row(
    key: str, label: str, actual: ProfitAndLoss | pd.Series, budget: ProfitAndLoss | pd.Series
) -> BudgetVarianceRow:
    def pick(source: ProfitAndLoss | pd.Series, name: str) -> float:
        return float(getattr(source, name) if isinstance(source, ProfitAndLoss) else source[name])

    return BudgetVarianceRow(
        key=key,
        label=label,
        net_revenue=measure(
            pick(actual, "net_revenue"), pick(budget, "net_revenue"), higher_is_better=True
        ),
        direct_costs=measure(
            pick(actual, "direct_costs"), pick(budget, "direct_costs"), higher_is_better=False
        ),
        operating_expenses=measure(
            pick(actual, "operating_expenses"),
            pick(budget, "operating_expenses"),
            higher_is_better=False,
        ),
        operating_income=measure(
            pick(actual, "operating_income"),
            pick(budget, "operating_income"),
            higher_is_better=True,
        ),
    )


def budget_variance(ctx: AnalysisContext, group_by: str) -> BudgetVarianceResponse:
    if group_by == "month":
        actual = statement_by(ctx.current, ["month"], "actual").reindex(
            ctx.period.months, fill_value=0.0
        )
        budget = statement_by(ctx.current, ["month"], "budget").reindex(
            ctx.period.months, fill_value=0.0
        )
        rows = [
            _variance_row(
                month_key(month), month.strftime("%b %Y"), actual.loc[month], budget.loc[month]
            )
            for month in actual.index
        ]
    else:
        keys = ["business_unit_code", "business_unit_name"]
        actual = statement_by(ctx.current, keys, "actual")
        budget = statement_by(ctx.current, keys, "budget")
        rows = [
            _variance_row(code, name, actual.loc[(code, name)], budget.loc[(code, name)])
            for code, name in actual.index
        ]
    return BudgetVarianceResponse(
        filters=ctx.applied_filters(),
        group_by=group_by,
        rows=rows,
    )


def budget_matrix(ctx: AnalysisContext) -> BudgetMatrixResponse:
    """Variance of every business unit x account cell over the period."""
    grouped = (
        ctx.current.groupby(
            [
                "business_unit_code",
                "business_unit_name",
                "statement_order",
                "account_code",
                "account_name",
                "account_type",
            ],
            observed=True,
        )[["actual", "budget"]]
        .sum()
        .reset_index()
        .sort_values(["business_unit_code", "statement_order"])
    )
    cells = []
    for row in grouped.itertuples(index=False):
        higher_is_better = row.account_type == REVENUE
        variance = row.actual - row.budget
        cells.append(
            BudgetMatrixCell(
                business_unit_code=row.business_unit_code,
                business_unit_name=row.business_unit_name,
                account_code=row.account_code,
                account_name=row.account_name,
                account_type=row.account_type,
                actual=money(row.actual),
                budget=money(row.budget),
                variance=money(variance),
                variance_pct=ratio(pct_change(row.actual, row.budget)),
                status=favorability(variance, row.budget, higher_is_better=higher_is_better),
                profit_impact=impact(variance, higher_is_better=higher_is_better),
            )
        )
    return BudgetMatrixResponse(filters=ctx.applied_filters(), cells=cells)
