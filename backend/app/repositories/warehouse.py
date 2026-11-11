"""Read-only queries against the star schema.

Each function returns a small, already aggregated pandas frame (thousands of rows at
most). Aggregation to the month happens in SQL; the analytics layer never touches
day-level rows. Facts are never joined to each other row by row: each query reads one
fact (or the drill-across view) to rule out fan-out and double counting.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.analytics.periods import Period

_UNIT_FILTER = "(CAST(:all_units AS boolean) OR bu.business_unit_code = ANY(:units))"

_ACCOUNT_MONTH_SQL = f"""
SELECT d.full_date            AS month,
       bu.business_unit_code,
       bu.business_unit_name,
       a.account_code,
       a.account_name,
       a.account_type,
       a.account_group,
       a.cost_behavior,
       a.statement_order,
       v.actual_amount        AS actual,
       v.budget_amount        AS budget
FROM vw_budget_vs_actual v
JOIN dim_date d           ON d.date_key = v.month_date_key
JOIN dim_business_unit bu ON bu.business_unit_key = v.business_unit_key
JOIN dim_account a        ON a.account_key = v.account_key
WHERE {_UNIT_FILTER}
ORDER BY d.full_date, bu.business_unit_code, a.statement_order
"""

_SALES_MONTH_PRODUCT_SQL = f"""
SELECT d.month_start_date     AS month,
       bu.business_unit_code,
       bu.business_unit_name,
       p.product_code,
       p.product_name,
       p.category_code,
       p.category_name,
       SUM(s.units_sold)          AS units,
       SUM(s.gross_sales_amount)  AS gross_sales,
       SUM(s.discount_amount)     AS discounts,
       SUM(s.net_sales_amount)    AS net_revenue,
       SUM(s.cogs_amount)         AS direct_costs
FROM fact_sales s
JOIN dim_date d           ON d.date_key = s.date_key
JOIN dim_business_unit bu ON bu.business_unit_key = s.business_unit_key
JOIN dim_product p        ON p.product_key = s.product_key
WHERE {_UNIT_FILTER}
GROUP BY d.month_start_date, bu.business_unit_code, bu.business_unit_name,
         p.product_code, p.product_name, p.category_code, p.category_name
ORDER BY d.month_start_date, bu.business_unit_code, p.product_code
"""

_EXPENSE_MONTH_CENTER_SQL = f"""
SELECT d.month_start_date     AS month,
       bu.business_unit_code,
       bu.business_unit_name,
       c.cost_center_code,
       c.cost_center_name,
       c.function_area,
       a.account_code,
       a.account_name,
       a.account_group,
       a.cost_behavior,
       SUM(e.amount)          AS amount
FROM fact_operating_expenses e
JOIN dim_date d           ON d.date_key = e.date_key
JOIN dim_business_unit bu ON bu.business_unit_key = e.business_unit_key
JOIN dim_cost_center c    ON c.cost_center_key = e.cost_center_key
JOIN dim_account a        ON a.account_key = e.account_key
WHERE {_UNIT_FILTER}
GROUP BY d.month_start_date, bu.business_unit_code, bu.business_unit_name,
         c.cost_center_code, c.cost_center_name, c.function_area,
         a.account_code, a.account_name, a.account_group, a.cost_behavior
ORDER BY d.month_start_date, bu.business_unit_code, c.cost_center_code, a.account_code
"""


def _read(
    session: Session, sql: str, business_units: list[str], numeric: list[str]
) -> pd.DataFrame:
    frame = pd.read_sql(
        text(sql),
        session.connection(),
        params={"all_units": not business_units, "units": business_units},
    )
    frame["month"] = pd.to_datetime(frame["month"])
    frame[numeric] = frame[numeric].astype(float)  # NUMERIC arrives as Decimal
    return frame


def account_month_frame(session: Session, business_units: list[str]) -> pd.DataFrame:
    """Actual and budget per month x business unit x account, for the whole history."""
    return _read(session, _ACCOUNT_MONTH_SQL, business_units, ["actual", "budget"])


def sales_month_product_frame(session: Session, business_units: list[str]) -> pd.DataFrame:
    """Sales measures per month x business unit x product, for the whole history."""
    return _read(
        session,
        _SALES_MONTH_PRODUCT_SQL,
        business_units,
        ["units", "gross_sales", "discounts", "net_revenue", "direct_costs"],
    )


def expense_month_center_frame(session: Session, business_units: list[str]) -> pd.DataFrame:
    """Operating expenses per month x business unit x cost centre x account."""
    return _read(session, _EXPENSE_MONTH_CENTER_SQL, business_units, ["amount"])


# --------------------------------------------------------------------------- #
# Catalogues and metadata
# --------------------------------------------------------------------------- #
def _rows(session: Session, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in session.execute(text(sql), params).mappings()]


def available_period(session: Session) -> Period | None:
    """First and last month present in the calendar dimension (None before any load)."""
    row = session.execute(
        text("SELECT MIN(month_start_date), MAX(month_start_date) FROM dim_date")
    ).one()
    if row[0] is None:
        return None
    return Period(pd.Timestamp(row[0]), pd.Timestamp(row[1]))


def business_units(session: Session) -> list[dict[str, Any]]:
    return _rows(
        session,
        "SELECT business_unit_code AS code, business_unit_name AS name, sales_channel "
        "FROM dim_business_unit ORDER BY business_unit_key",
    )


def categories(session: Session) -> list[dict[str, Any]]:
    return _rows(
        session,
        "SELECT category_code AS code, category_name AS name, COUNT(*) AS product_count "
        "FROM dim_product GROUP BY category_code, category_name ORDER BY category_name",
    )


def products(session: Session) -> list[dict[str, Any]]:
    return _rows(
        session,
        "SELECT product_code AS code, product_name AS name, category_code, category_name "
        "FROM dim_product ORDER BY product_code",
    )


def cost_centers(session: Session) -> list[dict[str, Any]]:
    return _rows(
        session,
        "SELECT cost_center_code AS code, cost_center_name AS name, function_area "
        "FROM dim_cost_center ORDER BY cost_center_key",
    )


def accounts(session: Session) -> list[dict[str, Any]]:
    return _rows(
        session,
        "SELECT account_code AS code, account_name AS name, account_type, account_group, "
        "cost_behavior FROM dim_account ORDER BY statement_order",
    )


# --------------------------------------------------------------------------- #
# ETL audit
# --------------------------------------------------------------------------- #
_RUN_COLUMNS = (
    "run_id, started_at, finished_at, status, source_seed, generator_version, "
    "data_period_start, data_period_end, error_message"
)


def latest_successful_run(session: Session) -> dict[str, Any] | None:
    rows = _rows(
        session,
        f"SELECT {_RUN_COLUMNS} FROM etl_run WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT 1",
    )
    return rows[0] if rows else None


def recent_runs(session: Session, limit: int = 10) -> list[dict[str, Any]]:
    return _rows(
        session,
        f"SELECT {_RUN_COLUMNS} FROM etl_run ORDER BY run_id DESC LIMIT :limit",
        limit=limit,
    )


def table_loads(session: Session, run_id: int) -> list[dict[str, Any]]:
    return _rows(
        session,
        "SELECT target_table, source_file, rows_read, rows_standardized, rows_rejected, "
        "rows_deduplicated, rows_loaded FROM etl_table_load WHERE run_id = :run_id "
        "ORDER BY target_table",
        run_id=run_id,
    )


def quality_checks(session: Session, run_id: int) -> list[dict[str, Any]]:
    return _rows(
        session,
        "SELECT check_code, check_name, dataset, quality_dimension, stage, severity, status, "
        "rows_checked, rows_failed, details FROM etl_data_quality_check "
        "WHERE run_id = :run_id ORDER BY check_id",
        run_id=run_id,
    )


def table_row_counts(session: Session) -> dict[str, int]:
    tables = (
        "dim_date",
        "dim_business_unit",
        "dim_product",
        "dim_cost_center",
        "dim_account",
        "fact_sales",
        "fact_operating_expenses",
        "fact_budget",
    )
    return {
        table: int(session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
        for table in tables
    }
