"""Evaluates the anomaly detector against the scenarios injected by the generator.

This is the only place where analytics results meet the generator's ground truth, and it
lives outside the application on purpose: the product never reads scenario definitions.

Definitions
    cell        one (business unit, account, month)
    primary     cell where a scenario has a direct effect (the detector should flag it)
    derived     cell moved mechanically by a scenario (flagging it is correct, not required)
    flagged     cell with |robust z| above the threshold
    recall      flagged primary cells / primary cells
    precision   flagged cells that are primary or derived / flagged cells
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.analytics.anomalies import Z_THRESHOLD, detect_anomalies

Cell = tuple[str, str, str]  # business unit code, account code, 'YYYY-MM'


def _cells(signatures: list[dict[str, Any]], role: str) -> set[Cell]:
    return {
        (unit, signature["account_code"], month)
        for signature in signatures
        if signature["role"] == role
        for unit in signature["business_units"]
        for month in signature["months"]
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def evaluate(history: pd.DataFrame, scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare detected anomalies with scenario signatures.

    ``history`` is the account-level frame (actual and budget per month, unit and account).
    """
    found = detect_anomalies(history)
    found = found.assign(month_key=found["month"].dt.strftime("%Y-%m"))
    flagged: set[Cell] = set(
        zip(found["business_unit_code"], found["account_code"], found["month_key"], strict=True)
    )
    material_rows = found[found["is_material"]]
    material: set[Cell] = set(
        zip(
            material_rows["business_unit_code"],
            material_rows["account_code"],
            material_rows["month_key"],
            strict=True,
        )
    )

    all_primary: set[Cell] = set()
    all_derived: set[Cell] = set()
    per_scenario = []
    for scenario in scenarios:
        primary = _cells(scenario["signatures"], "PRIMARY")
        derived = _cells(scenario["signatures"], "DERIVED") - primary
        all_primary |= primary
        all_derived |= derived
        per_scenario.append(
            {
                "id": scenario["id"],
                "name": scenario["name"],
                "primary_cells": len(primary),
                "primary_flagged": len(primary & flagged),
                "primary_flagged_material": len(primary & material),
                "cell_recall": _ratio(len(primary & flagged), len(primary)),
                "detected": bool(primary & flagged),
                "detected_material": bool(primary & material),
                "derived_cells": len(derived),
                "derived_flagged": len(derived & flagged),
            }
        )
    all_derived -= all_primary
    explained = all_primary | all_derived

    def summary(cells: set[Cell]) -> dict[str, Any]:
        unexplained = sorted(cells - explained)
        return {
            "flagged_cells": len(cells),
            "flagged_primary": len(cells & all_primary),
            "flagged_derived": len(cells & all_derived),
            "flagged_unexplained": len(unexplained),
            "cell_recall": _ratio(len(cells & all_primary), len(all_primary)),
            "precision": _ratio(len(cells & explained), len(cells)),
            "unexplained_cells": [
                {"business_unit": unit, "account": account, "month": month}
                for unit, account, month in unexplained
            ],
        }

    series = history[history["budget"] > 0].groupby(
        ["business_unit_code", "account_code"], observed=True
    )
    return {
        "z_threshold": Z_THRESHOLD,
        "series_evaluated": int(series.ngroups),
        "cells_evaluated": int((history["budget"] > 0).sum()),
        "primary_cells": len(all_primary),
        "scenarios_total": len(scenarios),
        "scenarios_detected": sum(s["detected"] for s in per_scenario),
        "scenarios_detected_material": sum(s["detected_material"] for s in per_scenario),
        "all_flags": summary(flagged),
        "material_flags": summary(material),
        "scenarios": per_scenario,
    }


def load_scenarios(source_dir: Path) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = json.loads((source_dir / "scenarios.json").read_text("utf-8"))
    return scenarios
