"""The published anomaly-detection evaluation must be reproducible from the data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from backend.app.repositories.warehouse import account_month_frame
from pipelines.evaluation.anomaly_detection import evaluate, load_scenarios

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def result(loaded_engine: Engine, source_dir: Path) -> dict:
    with Session(loaded_engine) as session:
        history = account_month_frame(session, [])
    return evaluate(history, load_scenarios(source_dir))


def test_published_evaluation_matches_a_fresh_run(result: dict, repo_root: Path) -> None:
    """docs/evaluation/anomaly_detection.json is evidence cited by the documentation."""
    published = json.loads(
        (repo_root / "docs" / "evaluation" / "anomaly_detection.json").read_text("utf-8")
    )
    assert result == published


def test_evaluation_accounting_is_coherent(result: dict) -> None:
    assert result["series_evaluated"] == 4 * 13
    assert result["cells_evaluated"] == 36 * 4 * 13
    for block in (result["all_flags"], result["material_flags"]):
        assert block["flagged_cells"] == (
            block["flagged_primary"] + block["flagged_derived"] + block["flagged_unexplained"]
        )
        assert len(block["unexplained_cells"]) == block["flagged_unexplained"]
    assert result["primary_cells"] == sum(s["primary_cells"] for s in result["scenarios"])
    assert result["material_flags"]["flagged_cells"] <= result["all_flags"]["flagged_cells"]


def test_detector_meets_the_documented_performance(result: dict) -> None:
    """Guards the claims made in ANALYSIS_METHODOLOGY.md against regressions."""
    assert result["scenarios_detected"] == result["scenarios_total"] == 9
    assert result["material_flags"]["precision"] >= 0.95
    assert result["all_flags"]["precision"] >= 0.80
    diluted = next(s for s in result["scenarios"] if s["id"] == "S5")
    # The known weak spot: a long, diluted effect is mostly missed. Documented, not hidden.
    assert diluted["cell_recall"] < 0.5
