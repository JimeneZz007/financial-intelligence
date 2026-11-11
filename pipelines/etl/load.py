"""Load: full refresh of the star schema and post-load warehouse checks.

The refresh runs inside the caller's transaction. If any blocking check fails after the
load, the transaction is rolled back and the warehouse keeps its previous contents.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy import Connection, text

from pipelines.etl import quality as dq
from pipelines.etl.quality import CheckResult
from pipelines.etl.transform import date_key

DIMENSION_TABLES = {
    # table: (source master frame, key column, natural key, loaded columns)
    "dim_business_unit": (
        "business_units",
        "business_unit_key",
        "business_unit_code",
        ["business_unit_code", "business_unit_name", "sales_channel"],
    ),
    "dim_product": (
        "products",
        "product_key",
        "product_code",
        [
            "product_code",
            "product_name",
            "category_code",
            "category_name",
            "list_price",
            "standard_unit_cost",
        ],
    ),
    "dim_cost_center": (
        "cost_centers",
        "cost_center_key",
        "cost_center_code",
        ["cost_center_code", "cost_center_name", "function_area"],
    ),
    "dim_account": (
        "chart_of_accounts",
        "account_key",
        "account_code",
        [
            "account_code",
            "account_name",
            "account_type",
            "account_group",
            "cost_behavior",
            "statement_order",
        ],
    ),
}

FACT_COLUMNS = {
    "fact_sales": [
        "date_key",
        "business_unit_key",
        "product_key",
        "units_sold",
        "gross_sales_amount",
        "discount_amount",
        "net_sales_amount",
        "cogs_amount",
    ],
    "fact_operating_expenses": [
        "entry_id",
        "date_key",
        "business_unit_key",
        "cost_center_key",
        "account_key",
        "amount",
    ],
    "fact_budget": ["month_date_key", "business_unit_key", "account_key", "budget_amount"],
}


def _copy(connection: Connection, table: str, frame: pd.DataFrame, columns: list[str]) -> None:
    """Bulk-load a frame with PostgreSQL COPY."""
    payload = frame[columns].to_csv(index=False, header=False, float_format="%.2f")
    driver_connection: Any = connection.connection.driver_connection
    statement = f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv)"
    with driver_connection.cursor() as cursor, cursor.copy(statement) as copy:
        copy.write(payload)


def _key_map(connection: Connection, table: str, key: str, natural_key: str) -> dict[str, int]:
    rows = connection.execute(text(f"SELECT {natural_key}, {key} FROM {table}"))
    return {str(row[0]): int(row[1]) for row in rows}


def load_star_schema(
    connection: Connection,
    master: dict[str, pd.DataFrame],
    dim_date: pd.DataFrame,
    sales: pd.DataFrame,
    expenses: pd.DataFrame,
    budget: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Truncate and reload every dimension and fact. Returns the loaded frames by table."""
    tables = [*FACT_COLUMNS, "dim_date", *DIMENSION_TABLES]
    connection.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY"))

    star: dict[str, pd.DataFrame] = {"dim_date": dim_date}
    _copy(connection, "dim_date", dim_date, list(dim_date.columns))

    keys: dict[str, dict[str, int]] = {}
    for table, (source, key, natural_key, columns) in DIMENSION_TABLES.items():
        frame = master[source]
        _copy(connection, table, frame, columns)
        keys[natural_key] = _key_map(connection, table, key, natural_key)
        star[table] = frame[columns].assign(**{key: frame[natural_key].map(keys[natural_key])})[
            [key, *columns]
        ]

    def keyed(frame: pd.DataFrame, natural_key: str, key: str) -> pd.Series:
        return frame[natural_key].map(keys[natural_key]).astype("int64").rename(key)

    star["fact_sales"] = sales.assign(
        date_key=date_key(sales["transaction_date"]),
        business_unit_key=keyed(sales, "business_unit_code", "business_unit_key"),
        product_key=keyed(sales, "product_code", "product_key"),
    )[FACT_COLUMNS["fact_sales"]]
    star["fact_operating_expenses"] = expenses.assign(
        date_key=date_key(expenses["posting_date"]),
        business_unit_key=keyed(expenses, "business_unit_code", "business_unit_key"),
        cost_center_key=keyed(expenses, "cost_center_code", "cost_center_key"),
        account_key=keyed(expenses, "account_code", "account_key"),
    )[FACT_COLUMNS["fact_operating_expenses"]]
    star["fact_budget"] = budget.assign(
        month_date_key=date_key(budget["month_start"]),
        business_unit_key=keyed(budget, "business_unit_code", "business_unit_key"),
        account_key=keyed(budget, "account_code", "account_key"),
    )[FACT_COLUMNS["fact_budget"]]

    for table, columns in FACT_COLUMNS.items():
        _copy(connection, table, star[table], columns)
    return star


# --------------------------------------------------------------------------- #
# Warehouse checks
# --------------------------------------------------------------------------- #
def _scalar(connection: Connection, sql: str) -> Any:
    return connection.execute(text(sql)).scalar_one()


def _reconcile(
    connection: Connection, code: str, name: str, table: str, column: str, expected: float | int
) -> CheckResult:
    observed = Decimal(str(_scalar(connection, f"SELECT COALESCE(SUM({column}), 0) FROM {table}")))
    target = Decimal(str(expected))
    difference = observed - target
    return dq.dataset_check(
        code=code,
        name=name,
        dataset=table,
        quality_dimension="reconciliation",
        stage=dq.WAREHOUSE,
        rows_checked=int(_scalar(connection, f"SELECT COUNT(*) FROM {table}")),
        rows_failed=0 if difference == 0 else 1,
        details={
            "expected": f"{target:.2f}",
            "observed": f"{observed:.2f}",
            "difference": f"{difference:.2f}",
        },
    )


def warehouse_checks(
    connection: Connection, star: dict[str, pd.DataFrame], control_totals: dict[str, Any]
) -> list[CheckResult]:
    """Checks run against the database after loading, before the transaction commits."""
    checks: list[CheckResult] = []

    for table in FACT_COLUMNS:
        loaded = int(_scalar(connection, f"SELECT COUNT(*) FROM {table}"))
        expected = len(star[table])
        checks.append(
            dq.dataset_check(
                code=f"WH_{table.upper()}_ROW_COUNT",
                name=f"{table}: rows in the database equal rows sent by the pipeline",
                dataset=table,
                quality_dimension="completeness",
                stage=dq.WAREHOUSE,
                rows_checked=expected,
                rows_failed=abs(loaded - expected),
                details={"expected": expected, "observed": loaded},
            )
        )

    sales_totals = control_totals["sales_transactions"]
    reconciliations = [
        ("WH_RECONCILE_UNITS", "units_sold", "fact_sales", sales_totals["units_sold"]),
        (
            "WH_RECONCILE_GROSS_SALES",
            "gross_sales_amount",
            "fact_sales",
            sales_totals["gross_sales_amount"],
        ),
        (
            "WH_RECONCILE_DISCOUNTS",
            "discount_amount",
            "fact_sales",
            sales_totals["discount_amount"],
        ),
        (
            "WH_RECONCILE_NET_SALES",
            "net_sales_amount",
            "fact_sales",
            sales_totals["net_sales_amount"],
        ),
        ("WH_RECONCILE_COGS", "cogs_amount", "fact_sales", sales_totals["cogs_amount"]),
        (
            "WH_RECONCILE_EXPENSES",
            "amount",
            "fact_operating_expenses",
            control_totals["expense_ledger"]["amount"],
        ),
        (
            "WH_RECONCILE_BUDGET",
            "budget_amount",
            "fact_budget",
            control_totals["budget_plan"]["budget_amount"],
        ),
    ]
    for code, column, table, expected in reconciliations:
        checks.append(
            _reconcile(
                connection,
                code,
                f"{table}.{column} total equals the source control total",
                table,
                column,
                expected,
            )
        )

    wrong_account_type = int(
        _scalar(
            connection,
            """
            SELECT COUNT(*) FROM fact_operating_expenses e
            JOIN dim_account a ON a.account_key = e.account_key
            WHERE a.account_type <> 'OPERATING_EXPENSE'
            """,
        )
    )
    checks.append(
        dq.dataset_check(
            code="WH_EXPENSES_ACCOUNT_TYPE",
            name="fact_operating_expenses only uses operating-expense accounts",
            dataset="fact_operating_expenses",
            quality_dimension="consistency",
            stage=dq.WAREHOUSE,
            rows_checked=len(star["fact_operating_expenses"]),
            rows_failed=wrong_account_type,
        )
    )

    expected_days = int(
        _scalar(connection, "SELECT MAX(full_date) - MIN(full_date) + 1 FROM dim_date")
    )
    checks.append(
        dq.dataset_check(
            code="WH_DATE_DIMENSION_CONTINUOUS",
            name="dim_date has one row for every day of the period, without gaps",
            dataset="dim_date",
            quality_dimension="completeness",
            stage=dq.WAREHOUSE,
            rows_checked=expected_days,
            rows_failed=abs(expected_days - len(star["dim_date"])),
        )
    )

    unit_months = int(
        _scalar(
            connection,
            """
            SELECT (SELECT COUNT(DISTINCT year_month) FROM dim_date)
                 * (SELECT COUNT(*) FROM dim_business_unit)
            """,
        )
    )
    unit_months_with_sales = int(
        _scalar(
            connection,
            """
            SELECT COUNT(*) FROM (
                SELECT DISTINCT d.year_month, s.business_unit_key
                FROM fact_sales s JOIN dim_date d ON d.date_key = s.date_key
            ) cells
            """,
        )
    )
    checks.append(
        dq.dataset_check(
            code="WH_SALES_MONTHS_COMPLETE",
            name="Every business unit has sales in every month of the period",
            dataset="fact_sales",
            quality_dimension="completeness",
            stage=dq.WAREHOUSE,
            rows_checked=unit_months,
            rows_failed=unit_months - unit_months_with_sales,
        )
    )

    comparison_cells = int(_scalar(connection, "SELECT COUNT(*) FROM vw_budget_vs_actual"))
    unmatched = int(
        _scalar(
            connection,
            "SELECT COUNT(*) FROM vw_budget_vs_actual WHERE NOT has_budget OR NOT has_actual",
        )
    )
    checks.append(
        dq.dataset_check(
            code="WH_BUDGET_ACTUAL_ALIGNMENT",
            name="Every month x unit x account cell has both a budget and an actual amount",
            dataset="vw_budget_vs_actual",
            quality_dimension="consistency",
            stage=dq.WAREHOUSE,
            severity=dq.WARNING,
            rows_checked=comparison_cells,
            rows_failed=unmatched,
        )
    )
    return checks
