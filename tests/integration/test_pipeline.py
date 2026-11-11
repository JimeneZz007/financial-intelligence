"""ETL end to end against PostgreSQL: load, reconciliation, idempotency and rollback."""

from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from pipelines.etl import quality as dq
from pipelines.etl.runner import RunSummary, run_pipeline
from pipelines.generate.dataset import Dataset

pytestmark = pytest.mark.integration


def _scalar(engine: Engine, sql: str) -> object:
    with engine.connect() as connection:
        return connection.execute(text(sql)).scalar_one()


def _fingerprint(engine: Engine) -> dict[str, object]:
    """Row counts and totals that identify the warehouse contents."""
    return {
        "sales_rows": _scalar(engine, "SELECT COUNT(*) FROM fact_sales"),
        "net_sales": _scalar(engine, "SELECT SUM(net_sales_amount) FROM fact_sales"),
        "expense_rows": _scalar(engine, "SELECT COUNT(*) FROM fact_operating_expenses"),
        "expenses": _scalar(engine, "SELECT SUM(amount) FROM fact_operating_expenses"),
        "budget_rows": _scalar(engine, "SELECT COUNT(*) FROM fact_budget"),
        "budget": _scalar(engine, "SELECT SUM(budget_amount) FROM fact_budget"),
        "product_keys": _scalar(
            engine,
            "SELECT string_agg(product_key || product_code, ',' ORDER BY 1) FROM dim_product",
        ),
    }


def test_pipeline_loads_every_valid_row(
    loaded_engine: Engine, pipeline_run: RunSummary, dataset: Dataset
) -> None:
    assert pipeline_run.rows_loaded["fact_sales"] == len(dataset.clean["sales_transactions"])
    assert pipeline_run.rows_loaded["fact_operating_expenses"] == len(
        dataset.clean["expense_ledger"]
    )
    assert pipeline_run.rows_loaded["fact_budget"] == len(dataset.clean["budget_plan"])
    assert _scalar(loaded_engine, "SELECT COUNT(*) FROM dim_date") == 1096
    assert _scalar(loaded_engine, "SELECT COUNT(*) FROM dim_product") == 30


def test_warehouse_totals_reconcile_with_control_totals_to_the_cent(
    loaded_engine: Engine, dataset: Dataset
) -> None:
    totals = dataset.control_totals
    expectations = {
        "SELECT SUM(net_sales_amount) FROM fact_sales": totals["sales_transactions"][
            "net_sales_amount"
        ],
        "SELECT SUM(cogs_amount) FROM fact_sales": totals["sales_transactions"]["cogs_amount"],
        "SELECT SUM(units_sold) FROM fact_sales": totals["sales_transactions"]["units_sold"],
        "SELECT SUM(amount) FROM fact_operating_expenses": totals["expense_ledger"]["amount"],
        "SELECT SUM(budget_amount) FROM fact_budget": totals["budget_plan"]["budget_amount"],
    }
    for sql, expected in expectations.items():
        assert Decimal(str(_scalar(loaded_engine, sql))) == Decimal(str(expected)), sql


def test_no_blocking_failures_and_all_reconciliations_pass(pipeline_run: RunSummary) -> None:
    assert not any(check.is_blocking_failure for check in pipeline_run.checks)
    reconciliations = [c for c in pipeline_run.checks if c.quality_dimension == "reconciliation"]
    assert len(reconciliations) == 7
    assert all(check.status == dq.PASS for check in reconciliations)


def test_audit_trail_is_persisted(loaded_engine: Engine, pipeline_run: RunSummary) -> None:
    with loaded_engine.connect() as connection:
        run = connection.execute(
            text("SELECT status, source_seed, finished_at FROM etl_run WHERE run_id = :id"),
            {"id": pipeline_run.run_id},
        ).one()
        loads = connection.execute(
            text(
                "SELECT rows_read, rows_rejected, rows_deduplicated, rows_loaded "
                "FROM etl_table_load WHERE run_id = :id"
            ),
            {"id": pipeline_run.run_id},
        ).all()
        checks = connection.execute(
            text("SELECT COUNT(*) FROM etl_data_quality_check WHERE run_id = :id"),
            {"id": pipeline_run.run_id},
        ).scalar_one()
    assert run.status == "SUCCESS"
    assert run.source_seed == 20230101
    assert run.finished_at is not None
    assert len(loads) == 3
    for load in loads:
        assert load.rows_read == load.rows_rejected + load.rows_deduplicated + load.rows_loaded
    assert checks == len(pipeline_run.checks)


def test_pipeline_is_idempotent(loaded_engine: Engine, source_dir: Path) -> None:
    before = _fingerprint(loaded_engine)
    summary = run_pipeline(loaded_engine, source_dir)
    assert summary.succeeded
    assert _fingerprint(loaded_engine) == before


def test_processed_exports_match_the_warehouse(
    loaded_engine: Engine, source_dir: Path, tmp_path: Path
) -> None:
    summary = run_pipeline(loaded_engine, source_dir, tmp_path)
    assert summary.succeeded
    exported = pd.read_csv(tmp_path / "fact_sales.csv")
    assert len(exported) == _scalar(loaded_engine, "SELECT COUNT(*) FROM fact_sales")
    assert Decimal(str(round(exported["net_sales_amount"].sum(), 2))) == Decimal(
        str(_scalar(loaded_engine, "SELECT SUM(net_sales_amount) FROM fact_sales"))
    )
    rejected = pd.read_csv(tmp_path / "rejected" / "sales_transactions_rejected.csv")
    assert len(rejected) == 26
    assert "reject_reason" in rejected.columns


def test_failed_run_rolls_back_and_keeps_previous_data(
    loaded_engine: Engine, source_dir: Path, tmp_path: Path
) -> None:
    """A source whose totals do not reconcile must not replace a healthy warehouse."""
    before = _fingerprint(loaded_engine)

    broken = tmp_path / "broken"
    shutil.copytree(source_dir, broken)
    sales = pd.read_csv(broken / "sales_transactions.csv", dtype=str, keep_default_na=False)
    sales.iloc[1000:].to_csv(broken / "sales_transactions.csv", index=False)  # lose 1,000 rows

    summary = run_pipeline(loaded_engine, broken)

    assert summary.status == "FAILED"
    assert "WH_RECONCILE_NET_SALES" in (summary.error_message or "")
    assert _fingerprint(loaded_engine) == before
    status = _scalar(loaded_engine, f"SELECT status FROM etl_run WHERE run_id = {summary.run_id}")
    assert status == "FAILED"


def test_missing_source_files_fail_cleanly(loaded_engine: Engine, tmp_path: Path) -> None:
    summary = run_pipeline(loaded_engine, tmp_path)
    assert summary.status == "FAILED"
    assert "Missing source files" in (summary.error_message or "")


# --------------------------------------------------------------------------- #
# Constraints are enforced by the database itself
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "statement",
    [
        # duplicate grain
        "INSERT INTO fact_sales SELECT * FROM fact_sales LIMIT 1",
        # negative units
        """INSERT INTO fact_sales VALUES
           (20230101, 1, 1, -1, 10, 0, 10, 5)
           ON CONFLICT (date_key, business_unit_key, product_key)
           DO UPDATE SET units_sold = -1""",
        # net <> gross - discount
        "UPDATE fact_sales SET net_sales_amount = net_sales_amount + 1 "
        "WHERE (date_key, business_unit_key, product_key) = "
        "(SELECT date_key, business_unit_key, product_key FROM fact_sales LIMIT 1)",
        # orphan foreign key
        "INSERT INTO fact_operating_expenses VALUES ('EXP-TEST001', 20230101, 99, 1, 1, 10)",
        # budget on a day that is not the first of the month
        "INSERT INTO fact_budget VALUES (20230115, 1, 1, 100)",
        # non-positive expense
        "INSERT INTO fact_operating_expenses VALUES ('EXP-TEST002', 20230101, 1, 1, 3, 0)",
        # invalid account type
        "INSERT INTO dim_account (account_code, account_name, account_type, account_group, "
        "cost_behavior, statement_order) VALUES ('9999', 'x', 'ASSET', 'x', 'FIXED', 1)",
    ],
    ids=[
        "duplicate_grain",
        "negative_units",
        "net_identity",
        "orphan_foreign_key",
        "budget_not_month_start",
        "non_positive_expense",
        "invalid_account_type",
    ],
)
def test_database_constraints_reject_invalid_rows(loaded_engine: Engine, statement: str) -> None:
    with loaded_engine.connect() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text(statement))
        connection.rollback()
