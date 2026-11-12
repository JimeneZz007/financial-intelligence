"""Prepares the inputs of the Power BI report.

1. Copies the star schema exported by the ETL (data/processed/*.csv) to powerbi/data/.
2. Writes powerbi/validation/expected_values.csv: the value every DAX measure must show
   for a set of slicer selections, computed here with plain SQL on the fact tables.

The expected values are an independent calculation (no DAX, no API code), so a report
that reproduces them has its model, relationships and measures right.
"""

from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from backend.app.db.session import build_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
POWERBI_DIR = REPO_ROOT / "powerbi"

SALES_SQL = """
SELECT d.year, d.month, d.year_month, b.business_unit_name AS unit, p.category_name AS category,
       SUM(s.units_sold) AS units, SUM(s.gross_sales_amount) AS gross,
       SUM(s.discount_amount) AS discounts, SUM(s.net_sales_amount) AS revenue,
       SUM(s.cogs_amount) AS cogs
FROM fact_sales s
JOIN dim_date d ON d.date_key = s.date_key
JOIN dim_business_unit b ON b.business_unit_key = s.business_unit_key
JOIN dim_product p ON p.product_key = s.product_key
GROUP BY d.year, d.month, d.year_month, b.business_unit_name, p.category_name
"""

EXPENSES_SQL = """
SELECT d.year, d.month, d.year_month, b.business_unit_name AS unit, a.account_name AS account,
       SUM(e.amount) AS amount
FROM fact_operating_expenses e
JOIN dim_date d ON d.date_key = e.date_key
JOIN dim_business_unit b ON b.business_unit_key = e.business_unit_key
JOIN dim_account a ON a.account_key = e.account_key
GROUP BY d.year, d.month, d.year_month, b.business_unit_name, a.account_name
"""

BUDGET_SQL = """
SELECT d.year, d.month, d.year_month, b.business_unit_name AS unit, a.account_name AS account,
       a.account_type, a.statement_order, SUM(f.budget_amount) AS amount
FROM fact_budget f
JOIN dim_date d ON d.date_key = f.month_date_key
JOIN dim_business_unit b ON b.business_unit_key = f.business_unit_key
JOIN dim_account a ON a.account_key = f.account_key
GROUP BY d.year, d.month, d.year_month, b.business_unit_name, a.account_name,
         a.account_type, a.statement_order
"""

Row = tuple[str, str, str, str]  # slicers, visual context, measure, expected value


def _money(value: float) -> str:
    return f"{value:.2f}"


def _pct(value: float) -> str:
    return f"{value * 100:.4f}%"


def _statement(
    sales: pd.DataFrame, expenses: pd.DataFrame, budget: pd.DataFrame
) -> list[tuple[str, str]]:
    """Measures of the income statement for an already filtered slice."""
    revenue, cogs = float(sales["revenue"].sum()), float(sales["cogs"].sum())
    opex = float(expenses["amount"].sum())
    by_type = budget.groupby("account_type")["amount"].sum()
    b_revenue = float(by_type.get("REVENUE", 0.0))
    b_cogs = float(by_type.get("DIRECT_COST", 0.0))
    b_opex = float(by_type.get("OPERATING_EXPENSE", 0.0))
    income, b_income = revenue - cogs - opex, b_revenue - b_cogs - b_opex
    return [
        ("Net Revenue", _money(revenue)),
        ("Gross Sales", _money(float(sales["gross"].sum()))),
        ("Discount Rate %", _pct(float(sales["discounts"].sum()) / float(sales["gross"].sum()))),
        ("Units Sold", str(int(sales["units"].sum()))),
        ("Direct Costs", _money(cogs)),
        ("Gross Profit", _money(revenue - cogs)),
        ("Gross Margin %", _pct((revenue - cogs) / revenue)),
        ("Operating Expenses", _money(opex)),
        ("Operating Income", _money(income)),
        ("Operating Margin %", _pct(income / revenue)),
        ("Budget Revenue", _money(b_revenue)),
        ("Budget Operating Expenses", _money(b_opex)),
        ("Budget Operating Income", _money(b_income)),
        ("Revenue Variance", _money(revenue - b_revenue)),
        ("Revenue Variance %", _pct((revenue - b_revenue) / abs(b_revenue))),
        ("Operating Expenses Variance", _money(opex - b_opex)),
        ("Operating Income Variance", _money(income - b_income)),
        ("Operating Income Variance %", _pct((income - b_income) / abs(b_income))),
    ]


def expected_values(sales: pd.DataFrame, expenses: pd.DataFrame, budget: pd.DataFrame) -> list[Row]:
    rows: list[Row] = []

    def add(slicers: str, context: str, measures: list[tuple[str, str]]) -> None:
        rows.extend((slicers, context, measure, value) for measure, value in measures)

    add("None (all years, all units)", "Card", _statement(sales, expenses, budget))

    year = 2025
    s25, e25, b25 = (frame[frame["year"] == year] for frame in (sales, expenses, budget))
    add(f"Year = {year}", "Card", _statement(s25, e25, b25))

    for unit in sorted(s25["unit"].unique()):
        slice_ = [frame[frame["unit"] == unit] for frame in (s25, e25, b25)]
        measures = dict(_statement(*slice_))
        add(
            f"Year = {year}",
            f"Row: business_unit_name = {unit}",
            [
                (name, measures[name])
                for name in (
                    "Net Revenue",
                    "Operating Income",
                    "Operating Margin %",
                    "Revenue Variance %",
                )
            ],
        )
    total_revenue = float(s25["revenue"].sum())
    for category, group in s25.groupby("category"):
        revenue, cogs = float(group["revenue"].sum()), float(group["cogs"].sum())
        add(
            f"Year = {year}",
            f"Row: category_name = {category}",
            [
                ("Net Revenue", _money(revenue)),
                ("Gross Margin %", _pct((revenue - cogs) / revenue)),
                ("Revenue Share of Products %", _pct(revenue / total_revenue)),
            ],
        )

    # Time intelligence, evaluated for one month.
    monthly = sales.groupby("year_month")["revenue"].sum().sort_index()
    month, previous_month, previous_year = "2025-03", "2025-02", "2024-03"
    add(
        "year_month = 2025-03",
        "Card",
        [
            ("Net Revenue", _money(monthly[month])),
            ("Net Revenue PM", _money(monthly[previous_month])),
            ("Net Revenue MoM %", _pct(monthly[month] / monthly[previous_month] - 1)),
            ("Net Revenue PY", _money(monthly[previous_year])),
            ("Net Revenue YoY %", _pct(monthly[month] / monthly[previous_year] - 1)),
            ("Net Revenue YTD", _money(monthly["2025-01":month].sum())),
            ("Net Revenue 3M Average", _money(monthly["2025-01":month].mean())),
        ],
    )
    add(
        "year_month = 2023-03",
        "Card",
        [("Net Revenue PY", "(blank)"), ("Net Revenue YoY %", "(blank)")],
    )

    # Statement by account: actual, budget and profit impact.
    actual_by_account = e25.groupby("account")["amount"].sum().to_dict()
    budget_by_account = b25.groupby(["statement_order", "account", "account_type"])["amount"].sum()
    total_impact = 0.0
    for (_, account, account_type), budget_amount in budget_by_account.sort_index().items():
        if account_type == "REVENUE":
            actual = float(s25["revenue"].sum())
        elif account_type == "DIRECT_COST":
            actual = float(s25["cogs"].sum())
        else:
            actual = float(actual_by_account.get(account, 0.0))
        variance = actual - float(budget_amount)
        impact = variance if account_type == "REVENUE" else -variance
        total_impact += impact
        add(
            f"Year = {year}",
            f"Row: account_name = {account}",
            [
                ("Actual Amount", _money(actual)),
                ("Budget Amount", _money(float(budget_amount))),
                ("Profit Impact", _money(impact)),
            ],
        )
    add(
        f"Year = {year}",
        "Matrix grand total (accounts on rows)",
        [("Profit Impact", _money(total_impact))],
    )
    return rows


def main() -> int:
    exported = sorted(PROCESSED_DIR.glob("*.csv"))
    if not exported:
        print(f"No star-schema files in {PROCESSED_DIR}. Run `make etl` first.", file=sys.stderr)
        return 1
    data_dir = POWERBI_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for path in exported:
        shutil.copy2(path, data_dir / path.name)
    print(f"Copied {len(exported)} tables to {data_dir}")

    with build_engine().connect() as connection:
        sales, expenses, budget = (
            pd.read_sql(text(sql), connection) for sql in (SALES_SQL, EXPENSES_SQL, BUDGET_SQL)
        )
    # NUMERIC columns arrive as Decimal.
    sales_measures = ["units", "gross", "discounts", "revenue", "cogs"]
    sales[sales_measures] = sales[sales_measures].astype(float)
    expenses["amount"] = expenses["amount"].astype(float)
    budget["amount"] = budget["amount"].astype(float)

    rows = expected_values(sales, expenses, budget)
    target = POWERBI_DIR / "validation" / "expected_values.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["slicers", "visual_context", "measure", "expected_value"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} expected values to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
