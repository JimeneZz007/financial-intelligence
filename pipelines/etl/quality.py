"""Data-quality primitives used by the ETL.

Two kinds of rules exist:

* **Row rules** flag individual rows of a source extract. Failing rows are quarantined
  (not loaded). The rule reports WARN while the share of quarantined rows stays within
  the tolerance and FAIL above it.
* **Dataset checks** assert a property of a whole dataset or of the loaded warehouse
  (unique grain, reconciliation with control totals...). They either PASS or FAIL.

Any FAIL on a rule with severity ERROR aborts the run and rolls the load back.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

# Maximum share of rows of an extract that may be quarantined before the run aborts.
REJECT_TOLERANCE = 0.01

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
ERROR, WARNING = "ERROR", "WARNING"
SOURCE, WAREHOUSE = "SOURCE", "WAREHOUSE"


@dataclass(frozen=True)
class CheckResult:
    code: str
    name: str
    dataset: str
    quality_dimension: str
    stage: str
    severity: str
    status: str
    rows_checked: int
    rows_failed: int
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_blocking_failure(self) -> bool:
        return self.status == FAIL and self.severity == ERROR


@dataclass(frozen=True)
class RowRule:
    """A rule evaluated per row. ``invalid`` returns True where the row breaks the rule."""

    code: str
    name: str
    quality_dimension: str
    invalid: Callable[[pd.DataFrame], pd.Series]


class DataQualityError(RuntimeError):
    """Raised when a blocking data-quality check fails."""

    def __init__(self, failures: list[CheckResult]) -> None:
        self.failures = failures
        summary = "; ".join(f"{c.code} ({c.rows_failed} rows)" for c in failures)
        super().__init__(f"Blocking data-quality failures: {summary}")


def apply_row_rules(
    frame: pd.DataFrame, rules: list[RowRule], dataset: str
) -> tuple[pd.DataFrame, pd.DataFrame, list[CheckResult]]:
    """Split a frame into valid and rejected rows.

    Rules run in order and a row is attributed to the first rule it breaks, so the
    failures reported per rule add up to the number of rejected rows.
    """
    total_rows = len(frame)
    reason = pd.Series(pd.NA, index=frame.index, dtype="string")
    results: list[CheckResult] = []
    for rule in rules:
        pending = reason.isna()
        broken = rule.invalid(frame).fillna(True).astype(bool) & pending
        reason[broken] = rule.code
        failed = int(broken.sum())
        status = PASS if failed == 0 else WARN
        results.append(
            CheckResult(
                code=rule.code,
                name=rule.name,
                dataset=dataset,
                quality_dimension=rule.quality_dimension,
                stage=SOURCE,
                severity=ERROR,
                status=status,
                rows_checked=total_rows,
                rows_failed=failed,
                details={"action": "rows quarantined"} if failed else {},
            )
        )

    rejected_mask = reason.notna()
    rejected = frame[rejected_mask].assign(reject_reason=reason[rejected_mask])
    reject_rate = len(rejected) / total_rows if total_rows else 0.0
    results.append(
        CheckResult(
            code=f"{dataset.upper()}_REJECT_RATE",
            name=f"Quarantined rows stay below {REJECT_TOLERANCE:.0%} of the extract",
            dataset=dataset,
            quality_dimension="validity",
            stage=SOURCE,
            severity=ERROR,
            status=PASS if reject_rate <= REJECT_TOLERANCE else FAIL,
            rows_checked=total_rows,
            rows_failed=len(rejected),
            details={"reject_rate": round(reject_rate, 6), "tolerance": REJECT_TOLERANCE},
        )
    )
    return frame[~rejected_mask], rejected, results


def dataset_check(
    *,
    code: str,
    name: str,
    dataset: str,
    quality_dimension: str,
    stage: str,
    rows_checked: int,
    rows_failed: int,
    severity: str = ERROR,
    details: dict[str, Any] | None = None,
) -> CheckResult:
    """Build a dataset-level check: PASS when nothing failed; otherwise FAIL (or WARN)."""
    failure_status = FAIL if severity == ERROR else WARN
    status = PASS if rows_failed == 0 else failure_status
    return CheckResult(
        code=code,
        name=name,
        dataset=dataset,
        quality_dimension=quality_dimension,
        stage=stage,
        severity=severity,
        status=status,
        rows_checked=rows_checked,
        rows_failed=rows_failed,
        details=details or {},
    )


def informational(
    *,
    code: str,
    name: str,
    dataset: str,
    quality_dimension: str,
    rows_checked: int,
    rows_affected: int,
) -> CheckResult:
    """A non-blocking observation about rows the pipeline repaired or removed."""
    return CheckResult(
        code=code,
        name=name,
        dataset=dataset,
        quality_dimension=quality_dimension,
        stage=SOURCE,
        severity=WARNING,
        status=PASS if rows_affected == 0 else WARN,
        rows_checked=rows_checked,
        rows_failed=rows_affected,
        details={"action": "rows repaired or removed automatically"} if rows_affected else {},
    )


def raise_on_blocking(results: list[CheckResult]) -> None:
    failures = [result for result in results if result.is_blocking_failure]
    if failures:
        raise DataQualityError(failures)
