"""Sales performance and profitability by business unit, category or product."""

from __future__ import annotations

import pandas as pd

from backend.app.analytics.metrics import OPERATING_EXPENSE, pct_change, safe_ratio
from backend.app.schemas import ProfitabilityResponse, ProfitabilityRow
from backend.app.services.context import AnalysisContext, FilterError
from backend.app.services.formatting import money, ratio

SALES_MEASURES = ["units", "gross_sales", "discounts", "net_revenue", "direct_costs"]

# group_by -> (key column, label column, parent key column, parent label column)
GROUPINGS: dict[str, tuple[str, str, str | None, str | None]] = {
    "business_unit": ("business_unit_code", "business_unit_name", None, None),
    "category": ("category_code", "category_name", None, None),
    "product": ("product_code", "product_name", "category_code", "category_name"),
}


def _filter_category(frame: pd.DataFrame, category: str | None) -> pd.DataFrame:
    return frame if category is None else frame[frame["category_code"] == category]


def _row(
    key: str,
    label: str,
    current: pd.Series,
    comparison: pd.Series | None,
    total_revenue: float,
    *,
    parent_key: str | None = None,
    parent_label: str | None = None,
    operating_expenses: float | None = None,
) -> ProfitabilityRow:
    revenue = float(current["net_revenue"])
    gross_profit = revenue - float(current["direct_costs"])
    margin = safe_ratio(gross_profit, revenue)

    comparison_revenue = comparison_margin = None
    if comparison is not None:
        comparison_revenue = float(comparison["net_revenue"])
        comparison_margin = safe_ratio(
            comparison_revenue - float(comparison["direct_costs"]), comparison_revenue
        )
    margin_change = (
        margin - comparison_margin if margin is not None and comparison_margin is not None else None
    )
    operating_income = None if operating_expenses is None else gross_profit - operating_expenses
    return ProfitabilityRow(
        key=key,
        label=label,
        parent_key=parent_key,
        parent_label=parent_label,
        units=float(current["units"]),
        gross_sales=money(current["gross_sales"]),
        discounts=money(current["discounts"]),
        discount_rate=ratio(safe_ratio(current["discounts"], current["gross_sales"])),
        net_revenue=money(revenue),
        revenue_share=ratio(safe_ratio(revenue, total_revenue)),
        direct_costs=money(current["direct_costs"]),
        gross_profit=money(gross_profit),
        gross_margin=ratio(margin),
        operating_expenses=None if operating_expenses is None else money(operating_expenses),
        operating_income=None if operating_income is None else money(operating_income),
        operating_margin=(
            None if operating_income is None else ratio(safe_ratio(operating_income, revenue))
        ),
        comparison_net_revenue=(None if comparison_revenue is None else money(comparison_revenue)),
        revenue_change_pct=(
            None if comparison_revenue is None else ratio(pct_change(revenue, comparison_revenue))
        ),
        comparison_gross_margin=ratio(comparison_margin),
        gross_margin_change=ratio(margin_change),
    )


def profitability(
    ctx: AnalysisContext, group_by: str, category: str | None
) -> ProfitabilityResponse:
    if category is not None:
        category = category.strip().upper()
        known = set(ctx.sales_history["category_code"].unique())
        if category not in known:
            raise FilterError(
                f"Unknown category: {category}. Valid codes: {', '.join(sorted(known))}"
            )

    key_column, label_column, parent_key_column, parent_label_column = GROUPINGS[group_by]
    group_columns = [
        c for c in (key_column, label_column, parent_key_column, parent_label_column) if c
    ]

    current = _filter_category(ctx.sales_current, category)
    grouped = current.groupby(group_columns, observed=True)[SALES_MEASURES].sum()
    totals = current[SALES_MEASURES].sum()

    comparison_grouped = comparison_totals = None
    if ctx.sales_comparison is not None:
        comparison = _filter_category(ctx.sales_comparison, category)
        comparison_grouped = comparison.groupby(key_column, observed=True)[SALES_MEASURES].sum()
        comparison_totals = comparison[SALES_MEASURES].sum()

    # Operating expenses exist per business unit only, and cannot be split by category.
    opex_by_unit: pd.Series | None = None
    if group_by == "business_unit" and category is None:
        opex = ctx.current[ctx.current["account_type"] == OPERATING_EXPENSE]
        opex_by_unit = opex.groupby("business_unit_code", observed=True)["actual"].sum()

    rows = []
    for index, values in grouped.sort_values("net_revenue", ascending=False).iterrows():
        labels = dict(
            zip(group_columns, index if isinstance(index, tuple) else (index,), strict=True)
        )
        key = labels[key_column]
        rows.append(
            _row(
                key,
                labels[label_column],
                values,
                (
                    comparison_grouped.loc[key]
                    if comparison_grouped is not None and key in comparison_grouped.index
                    else None
                ),
                float(totals["net_revenue"]),
                parent_key=labels.get(parent_key_column) if parent_key_column else None,
                parent_label=labels.get(parent_label_column) if parent_label_column else None,
                operating_expenses=(
                    float(opex_by_unit.get(key, 0.0)) if opex_by_unit is not None else None
                ),
            )
        )
    total = _row(
        "total",
        "Total",
        totals,
        comparison_totals,
        float(totals["net_revenue"]),
        operating_expenses=float(opex_by_unit.sum()) if opex_by_unit is not None else None,
    )
    return ProfitabilityResponse(
        filters=ctx.applied_filters(),
        group_by=group_by,
        category=category,
        rows=rows,
        total=total,
    )
