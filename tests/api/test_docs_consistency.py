"""Documentation must stay aligned with the code it describes."""

from __future__ import annotations

from pathlib import Path

from backend.app.core.kpi_catalog import KPI_CATALOG

DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_kpi_catalog_document_covers_every_kpi_in_code() -> None:
    document = (DOCS / "KPI_CATALOG.md").read_text("utf-8")
    missing = [kpi.id for kpi in KPI_CATALOG if f"### `{kpi.id}`" not in document]
    assert missing == []


def test_kpi_ids_are_unique() -> None:
    ids = [kpi.id for kpi in KPI_CATALOG]
    assert len(ids) == len(set(ids))
