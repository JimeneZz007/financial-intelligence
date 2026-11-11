"""Extract: read the raw source files exactly as delivered (every value as text)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

EXTRACT_NAMES = (
    "business_units",
    "products",
    "cost_centers",
    "chart_of_accounts",
    "sales_transactions",
    "expense_ledger",
    "budget_plan",
)
MANIFEST_NAME = "MANIFEST.json"


class SourceError(RuntimeError):
    """Raised when the source directory is incomplete or unreadable."""


@dataclass(frozen=True)
class SourceData:
    frames: dict[str, pd.DataFrame]
    manifest: dict[str, Any]


def read_source(source_dir: Path) -> SourceData:
    manifest_path = source_dir / MANIFEST_NAME
    missing = [f"{name}.csv" for name in EXTRACT_NAMES if not (source_dir / f"{name}.csv").exists()]
    if not manifest_path.exists():
        missing.append(MANIFEST_NAME)
    if missing:
        raise SourceError(
            f"Missing source files in {source_dir}: {', '.join(missing)}. "
            "Run `python -m pipelines.generate` first."
        )
    frames = {
        # Read as text and keep blanks as empty strings: typing is the transform's job.
        name: pd.read_csv(source_dir / f"{name}.csv", dtype=str, keep_default_na=False)
        for name in EXTRACT_NAMES
    }
    return SourceData(frames=frames, manifest=json.loads(manifest_path.read_text("utf-8")))
