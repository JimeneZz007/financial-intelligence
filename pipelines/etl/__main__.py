"""CLI: python -m pipelines.etl [--source DIR] [--processed DIR]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.app.db.session import build_engine
from pipelines.etl.quality import PASS
from pipelines.etl.runner import TARGET_TABLE, run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and load the source extracts.")
    parser.add_argument("--source", type=Path, default=REPO_ROOT / "data" / "synthetic")
    parser.add_argument("--processed", type=Path, default=REPO_ROOT / "data" / "processed")
    args = parser.parse_args()

    summary = run_pipeline(build_engine(), args.source, args.processed)

    print(f"ETL run {summary.run_id}: {summary.status}")
    if summary.error_message:
        print(f"  error: {summary.error_message}")
    if summary.extracts:
        print(f"  {'extract':<22}{'read':>9}{'fixed':>8}{'rejected':>10}{'dupes':>8}{'loaded':>9}")
        for extract in summary.extracts:
            loaded = summary.rows_loaded.get(TARGET_TABLE[extract.name], 0)
            print(
                f"  {extract.name:<22}{extract.rows_read:>9,}{extract.rows_standardized:>8,}"
                f"{len(extract.rejected):>10,}{extract.rows_deduplicated:>8,}{loaded:>9,}"
            )
    by_status: dict[str, int] = {}
    for check in summary.checks:
        by_status[check.status] = by_status.get(check.status, 0) + 1
    print(
        "  checks: " + ", ".join(f"{count} {status}" for status, count in sorted(by_status.items()))
    )
    for check in summary.checks:
        if check.status != PASS:
            print(f"    [{check.status}] {check.code}: {check.rows_failed:,} rows — {check.name}")
    return 0 if summary.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
