"""Operating-expense breakdowns."""

from __future__ import annotations

import pandas as pd

from backend.app.analytics.metrics import (
    OPERATING_EXPENSE,
    REVENUE,
    favorability,
    pct_change,
    safe_ratio,
)
from backend.app.schemas import (
    ExpenseBreakdownResponse,
    ExpenseMatrixCell,
    ExpenseMatrixResponse,
    ExpenseRow,
)
from backend.app.services.context import AnalysisContext
from backend.app.services.formatting import money, ratio

# Groupings available on the account-level frame (which carries the budget).
ACCOUNT_GROUPINGS: dict[str, tuple[str, str]] = {
    "account": ("account_code", "account_name"),
    "account_group": ("account_group", "account_group"),
    "cost_behavior": ("cost_behavior", "cost_behavior"),
}

BEHAVIOR_LABELS = {
    "FIXED": "Fixed",
    "VARIABLE": "Variable",
    "SEMI_VARIABLE": "Semi-variable",
    "DISCRETIONARY": "Discretionary",
}


def _row(
    key: str,
    label: str,
    actual: float,
    total: float,
    revenue: float,
    budget: float | None,
    comparison: float | None,
) -> ExpenseRow:
    variance = None if budget is None else actual - budget
    return ExpenseRow(
        key=key,
        label=label,
        actual=money(actual),
        share=ratio(safe_ratio(actual, total)),
        pct_of_revenue=ratio(safe_ratio(actual, revenue)),
        budget=None if budget is None else money(budget),
        variance=None if variance is None else money(variance),
        variance_pct=None if budget is None else ratio(pct_change(actual, budget)),
        status=(
            None
            if variance is None or budget is None
            else favorability(variance, budget, higher_is_better=False)
        ),
        comparison=None if comparison is None else money(comparison),
        change_pct=None if comparison is None else ratio(pct_change(actual, comparison)),
    )


def expense_breakdown(ctx: AnalysisContext, group_by: str) -> ExpenseBreakdownResponse:
    revenue = float(ctx.current.loc[ctx.current["account_type"] == REVENUE, "actual"].sum())

    if group_by == "cost_center":
        # The budget is not planned by cost centre, so this grouping has no budget columns.
        key_column, label_column = "cost_center_code", "cost_center_name"
        current = ctx.expenses_current.rename(columns={"amount": "actual"})
        comparison = (
            None
            if ctx.expenses_comparison is None
            else ctx.expenses_comparison.rename(columns={"amount": "actual"})
        )
        has_budget = False
    else:
        key_column, label_column = ACCOUNT_GROUPINGS[group_by]
        current = ctx.current[ctx.current["account_type"] == OPERATING_EXPENSE]
        comparison = (
            None
            if ctx.comparison is None
            else ctx.comparison[ctx.comparison["account_type"] == OPERATING_EXPENSE]
        )
        has_budget = True

    value_columns = ["actual", "budget"] if has_budget else ["actual"]
    group_columns = list(dict.fromkeys([key_column, label_column]))
    grouped = (
        current.groupby(group_columns, observed=True)[value_columns]
        .sum()
        .sort_values("actual", ascending=False)
    )
    comparison_by_key: pd.Series | None = (
        None
        if comparison is None
        else comparison.groupby(key_column, observed=True)["actual"].sum()
    )
    total_actual = float(grouped["actual"].sum())

    rows = []
    for index, values in grouped.iterrows():
        key = index[0] if isinstance(index, tuple) else index
        label = index[-1] if isinstance(index, tuple) else index
        if group_by == "cost_behavior":
            label = BEHAVIOR_LABELS.get(str(key), str(key))
        rows.append(
            _row(
                str(key),
                str(label),
                float(values["actual"]),
                total_actual,
                revenue,
                float(values["budget"]) if has_budget else None,
                (float(comparison_by_key.get(key, 0.0)) if comparison_by_key is not None else None),
            )
        )
    total = _row(
        "total",
        "Total operating expenses",
        total_actual,
        total_actual,
        revenue,
        float(grouped["budget"].sum()) if has_budget else None,
        float(comparison_by_key.sum()) if comparison_by_key is not None else None,
    )
    return ExpenseBreakdownResponse(
        filters=ctx.applied_filters(),
        group_by=group_by,
        rows=rows,
        total=total,
    )


def expense_matrix(ctx: AnalysisContext) -> ExpenseMatrixResponse:
    """Operating expenses by cost centre x account group."""
    grouped = (
        ctx.expenses_current.groupby(
            ["cost_center_code", "cost_center_name", "account_group"], observed=True
        )["amount"]
        .sum()
        .reset_index()
    )
    center_order = (
        grouped.groupby("cost_center_name")["amount"].sum().sort_values(ascending=False).index
    )
    group_order = (
        grouped.groupby("account_group")["amount"].sum().sort_values(ascending=False).index
    )
    return ExpenseMatrixResponse(
        filters=ctx.applied_filters(),
        cost_centers=list(center_order),
        account_groups=list(group_order),
        cells=[
            ExpenseMatrixCell(
                cost_center_code=row.cost_center_code,
                cost_center_name=row.cost_center_name,
                account_group=row.account_group,
                amount=money(row.amount),
            )
            for row in grouped.itertuples(index=False)
        ],
    )
