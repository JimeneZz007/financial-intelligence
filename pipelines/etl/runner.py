"""Orchestrates one ETL run: extract -> transform -> load -> verify -> audit."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Engine, func, insert, update

from backend.app.db.models import EtlDataQualityCheck, EtlRun, EtlTableLoad
from pipelines.etl import quality as dq
from pipelines.etl.extract import read_source
from pipelines.etl.load import load_star_schema, warehouse_checks
from pipelines.etl.quality import CheckResult
from pipelines.etl.transform import (
    CleanExtract,
    build_dim_date,
    clean_budget,
    clean_expenses,
    clean_master_data,
    clean_sales,
)

TARGET_TABLE = {
    "sales_transactions": "fact_sales",
    "expense_ledger": "fact_operating_expenses",
    "budget_plan": "fact_budget",
}


@dataclass
class RunSummary:
    run_id: int
    status: str = "RUNNING"
    error_message: str | None = None
    extracts: list[CleanExtract] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    rows_loaded: dict[str, int] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == "SUCCESS"


def _start_run(engine: Engine) -> int:
    with engine.begin() as connection:
        result = connection.execute(
            insert(EtlRun).values(status="RUNNING").returning(EtlRun.run_id)
        )
        return int(result.scalar_one())


def _finish_run(engine: Engine, summary: RunSummary, run_values: dict[str, Any]) -> None:
    """Persist the audit trail. Runs in its own transaction so failures are recorded too."""
    with engine.begin() as connection:
        connection.execute(
            update(EtlRun)
            .where(EtlRun.run_id == summary.run_id)
            .values(
                status=summary.status,
                finished_at=func.now(),
                error_message=summary.error_message,
                **run_values,
            )
        )
        if summary.extracts:
            connection.execute(
                insert(EtlTableLoad),
                [
                    {
                        "run_id": summary.run_id,
                        "target_table": TARGET_TABLE[extract.name],
                        "source_file": f"{extract.name}.csv",
                        "rows_read": extract.rows_read,
                        "rows_standardized": extract.rows_standardized,
                        "rows_rejected": len(extract.rejected),
                        "rows_deduplicated": extract.rows_deduplicated,
                        "rows_loaded": summary.rows_loaded.get(TARGET_TABLE[extract.name], 0),
                    }
                    for extract in summary.extracts
                ],
            )
        if summary.checks:
            connection.execute(
                insert(EtlDataQualityCheck),
                [
                    {
                        "run_id": summary.run_id,
                        "check_code": check.code,
                        "check_name": check.name,
                        "dataset": check.dataset,
                        "quality_dimension": check.quality_dimension,
                        "stage": check.stage,
                        "severity": check.severity,
                        "status": check.status,
                        "rows_checked": check.rows_checked,
                        "rows_failed": check.rows_failed,
                        "details": check.details or None,
                    }
                    for check in summary.checks
                ],
            )


def _export_processed(
    processed_dir: Path, star: dict[str, pd.DataFrame], extracts: list[CleanExtract]
) -> None:
    """Write the star schema and the quarantined rows as CSV (used by Power BI and audits)."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    for table, frame in star.items():
        frame.to_csv(processed_dir / f"{table}.csv", index=False, float_format="%.2f")
    rejected_dir = processed_dir / "rejected"
    shutil.rmtree(rejected_dir, ignore_errors=True)
    rejected_dir.mkdir()
    for extract in extracts:
        extract.rejected.to_csv(rejected_dir / f"{extract.name}_rejected.csv", index=False)


def run_pipeline(engine: Engine, source_dir: Path, processed_dir: Path | None = None) -> RunSummary:
    """Run the pipeline end to end. Never raises for data problems: inspect the summary."""
    summary = RunSummary(run_id=_start_run(engine))
    run_values: dict[str, Any] = {}
    try:
        source = read_source(source_dir)
        manifest = source.manifest
        run_values = {
            "source_seed": manifest.get("seed"),
            "generator_version": manifest.get("generator_version"),
        }

        master, master_checks = clean_master_data(source.frames)
        summary.checks += master_checks
        dq.raise_on_blocking(summary.checks)

        sales = clean_sales(source.frames["sales_transactions"], master)
        expenses = clean_expenses(source.frames["expense_ledger"], master)
        budget = clean_budget(source.frames["budget_plan"], master)
        summary.extracts = [sales, expenses, budget]
        for extract in summary.extracts:
            summary.checks += extract.checks
        dq.raise_on_blocking(summary.checks)

        period_start: date = min(
            sales.valid["transaction_date"].min(),
            expenses.valid["posting_date"].min(),
            budget.valid["month_start"].min(),
        ).date()
        period_end: date = max(
            sales.valid["transaction_date"].max(),
            expenses.valid["posting_date"].max(),
            budget.valid["month_start"].max(),
        ).date()
        dim_date = build_dim_date(period_start, period_end)
        run_values |= {
            "data_period_start": dim_date["full_date"].iloc[0],
            "data_period_end": dim_date["full_date"].iloc[-1],
        }

        with engine.begin() as connection:
            star = load_star_schema(
                connection, master, dim_date, sales.valid, expenses.valid, budget.valid
            )
            post_load = warehouse_checks(connection, star, manifest["control_totals"])
            summary.checks += post_load
            dq.raise_on_blocking(post_load)  # raising here rolls the load back

        summary.rows_loaded = {table: len(frame) for table, frame in star.items()}
        summary.status = "SUCCESS"
        if processed_dir is not None:
            _export_processed(processed_dir, star, summary.extracts)
    except Exception as error:
        summary.status = "FAILED"
        summary.error_message = f"{type(error).__name__}: {error}"[:2000]
    _finish_run(engine, summary, run_values)
    return summary
