"""Data-quality report built from the ETL audit tables."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.analytics.metrics import safe_ratio
from backend.app.repositories import warehouse
from backend.app.schemas import (
    DataQualityResponse,
    EtlRunItem,
    QualityCheckItem,
    QualitySummary,
    TableLoadItem,
)


def _run_item(row: dict[str, Any]) -> EtlRunItem:
    finished = row["finished_at"]
    duration = (finished - row["started_at"]).total_seconds() if finished else None
    return EtlRunItem(**row, duration_seconds=None if duration is None else round(duration, 3))


def data_quality_report(session: Session) -> DataQualityResponse:
    """Latest run with its checks and row accounting, plus the recent run history."""
    runs = [_run_item(row) for row in warehouse.recent_runs(session)]
    row_counts = warehouse.table_row_counts(session)
    if not runs:
        return DataQualityResponse(
            latest_run=None,
            summary=None,
            table_loads=[],
            checks=[],
            table_row_counts=row_counts,
            recent_runs=[],
        )

    latest = runs[0]
    loads = [TableLoadItem(**row) for row in warehouse.table_loads(session, latest.run_id)]
    checks = [QualityCheckItem(**row) for row in warehouse.quality_checks(session, latest.run_id)]
    rows_read = sum(load.rows_read for load in loads)
    rows_loaded = sum(load.rows_loaded for load in loads)
    summary = QualitySummary(
        total_checks=len(checks),
        passed=sum(check.status == "PASS" for check in checks),
        warnings=sum(check.status == "WARN" for check in checks),
        failed=sum(check.status == "FAIL" for check in checks),
        rows_read=rows_read,
        rows_loaded=rows_loaded,
        rows_rejected=sum(load.rows_rejected for load in loads),
        rows_deduplicated=sum(load.rows_deduplicated for load in loads),
        load_rate=safe_ratio(rows_loaded, rows_read),
    )
    return DataQualityResponse(
        latest_run=latest,
        summary=summary,
        table_loads=loads,
        checks=checks,
        table_row_counts=row_counts,
        recent_runs=runs,
    )
