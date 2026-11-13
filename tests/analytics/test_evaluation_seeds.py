"""Multi-seed evaluation: seed selection, per-seed metrics and their summary."""

from __future__ import annotations

from typing import Any

import pytest

from pipelines.evaluation.seeds import seed_list, seed_metrics, summarise
from pipelines.generate import config as generator_config


def _result(flagged: int, primary: int, derived: int, detected: int = 9) -> dict[str, Any]:
    return {
        "material_flags": {
            "flagged_cells": flagged,
            "flagged_primary": primary,
            "cell_recall": primary / 100,
            "precision": (primary + derived) / flagged if flagged else None,
        },
        "all_flags": {"cell_recall": 0.5, "precision": 0.8},
        "scenarios_detected_material": detected,
        "scenarios": [{"id": "S1", "cell_recall": 1.0}, {"id": "S5", "cell_recall": 0.1}],
    }


def test_seed_list_starts_with_the_project_seed_and_is_fixed() -> None:
    seeds = seed_list(3)
    assert seeds == [generator_config.SEED, generator_config.SEED + 1, generator_config.SEED + 2]
    assert seed_list(3) == seeds


def test_seed_list_rejects_an_empty_run() -> None:
    with pytest.raises(ValueError, match="At least one seed"):
        seed_list(0)


def test_strict_precision_counts_derived_cells_as_errors() -> None:
    row = seed_metrics(1, _result(flagged=50, primary=43, derived=6))
    assert row["material_precision"] == pytest.approx(0.98)
    assert row["material_strict_precision"] == pytest.approx(0.86)


def test_strict_precision_is_undefined_without_flags() -> None:
    row = seed_metrics(1, _result(flagged=0, primary=0, derived=0))
    assert row["material_strict_precision"] is None
    assert row["material_precision"] is None


def test_summary_separates_the_held_out_seeds_from_the_project_seed() -> None:
    project = generator_config.SEED
    rows = [
        seed_metrics(project, _result(flagged=50, primary=43, derived=6)),
        seed_metrics(project + 1, _result(flagged=40, primary=30, derived=4)),
        seed_metrics(project + 2, _result(flagged=20, primary=10, derived=2, detected=8)),
    ]
    summary = summarise(rows)

    assert summary["all_seeds"]["seeds"] == 3
    held_out = summary["held_out_seeds"]
    assert held_out["seeds"] == 2
    recall = held_out["metrics"]["material_recall"]
    assert recall["min"] == pytest.approx(0.10)
    assert recall["max"] == pytest.approx(0.30)
    assert recall["mean"] == pytest.approx(0.20)
    assert held_out["metrics"]["scenarios_detected_material"]["min"] == 8
    assert held_out["scenario_recall"]["S5"]["max"] == pytest.approx(0.1)


def test_summary_without_other_seeds_has_no_held_out_block() -> None:
    rows = [seed_metrics(generator_config.SEED, _result(flagged=10, primary=8, derived=1))]
    summary = summarise(rows)
    assert summary["held_out_seeds"] is None
    assert summary["all_seeds"]["metrics"]["material_recall"]["stdev"] == 0.0


def test_summary_rejects_an_empty_list() -> None:
    with pytest.raises(ValueError, match="No seed results"):
        summarise([])
